"""
SSOT-Code Drift Detection Server

偵測 SSOT（意圖層）與 Code Graph（現實層）之間的偏差。

偏差類型：
1. missing_implementation - SSOT 定義了但 Code 沒實作
2. missing_spec - Code 存在但 SSOT 沒文檔化
3. mismatch - 兩者都有但內容不一致
4. stale_spec - SSOT 文檔過時

設計原則：
- 偵測偏差，但不自動修正
- 偏差需要人類決策
- 提供可行動的建議
"""

import os
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# =============================================================================
# SCHEMA（供 Agent 參考）
# =============================================================================

SCHEMA = """
=== Drift Detection API ===

detect_all_drifts(project, project_dir=None) -> DriftReport
    偵測專案所有 SSOT-Code 偏差
    Args:
        project: 專案名稱（用於 Code Graph 查詢）
        project_dir: 專案目錄路徑（用於讀取專案級 SSOT .claude/pfc/INDEX.md）
    Returns: {
        'has_drift': bool,
        'drift_count': int,
        'drifts': [DriftItem],
        'summary': str,
        'checked_at': datetime
    }

detect_flow_drift(project, flow_id) -> DriftReport
    偵測特定 Flow 的偏差
    Returns: 同上

detect_coverage_gaps(project) -> List[CoverageGap]
    偵測測試覆蓋缺口
    Returns: [{
        'node_id': str,
        'node_kind': str,
        'name': str,
        'file_path': str,
        'has_test': bool
    }]

get_drift_summary(project) -> str
    取得偏差摘要（Markdown 格式）

resolve_drift(project, drift_id, resolution) -> bool
    標記偏差已解決
    - resolution: 'fixed_code' | 'updated_spec' | 'intentional' | 'wont_fix'
"""

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class DriftItem:
    """單一偏差項目"""
    id: str                              # 唯一識別符
    type: str                            # missing_implementation, missing_spec, mismatch, stale_spec
    severity: str                        # critical, high, medium, low
    ssot_item: Optional[str] = None      # SSOT 側的項目
    code_item: Optional[str] = None      # Code 側的項目
    description: str = ""
    suggestion: str = ""                 # 建議的修復方式
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'ssot_item': self.ssot_item,
            'code_item': self.code_item,
            'description': self.description,
            'suggestion': self.suggestion,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None
        }


@dataclass
class DriftReport:
    """偏差報告"""
    has_drift: bool = False
    drift_count: int = 0
    drifts: List[DriftItem] = field(default_factory=list)
    summary: str = ""
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'has_drift': self.has_drift,
            'drift_count': self.drift_count,
            'drifts': [d.to_dict() for d in self.drifts],
            'summary': self.summary,
            'checked_at': self.checked_at.isoformat()
        }


# =============================================================================
# Detection Logic
# =============================================================================

def detect_all_drifts(project: str, project_dir: str = None) -> DriftReport:
    """
    偵測專案所有 SSOT-Code 偏差

    Args:
        project: 專案名稱（用於 Code Graph 查詢）
        project_dir: 專案目錄路徑（用於讀取專案級 SSOT INDEX）
                     如果不傳，只會檢查全局 SSOT

    檢查項目：
    1. SSOT 定義的 Flow 是否有對應實作
    2. Code 中的主要模組是否有 SSOT 文檔
    3. SSOT 和 Code 的結構是否一致
    """
    from servers.ssot import parse_index
    from servers.code_graph import get_code_nodes, get_code_graph_stats

    drifts = []
    drift_id = 0

    def make_drift_id():
        nonlocal drift_id
        drift_id += 1
        return f"drift-{project}-{drift_id:04d}"

    # 1. 取得 SSOT 定義（優先使用專案級 INDEX）
    try:
        ssot_data = parse_index(project_dir)
        # parse_index 返回 {'flows': [...], 'domains': [...], ...}
        # 展平為節點列表
        ssot_nodes = []
        for kind, nodes in ssot_data.items():
            for node in nodes:
                if isinstance(node, dict):
                    node['kind'] = kind.rstrip('s')  # flows -> flow
                    ssot_nodes.append(node)
    except Exception as e:
        return DriftReport(
            has_drift=False,
            summary=f"Cannot detect drift: SSOT Index not found ({str(e)})"
        )

    # 2. 取得 Code Graph
    code_nodes = get_code_nodes(project, limit=1000)
    code_stats = get_code_graph_stats(project)

    if code_stats['node_count'] == 0:
        return DriftReport(
            has_drift=False,
            summary="Cannot detect drift: Code Graph is empty. Run sync first."
        )

    # 建立索引
    ssot_by_id = {n.get('id'): n for n in ssot_nodes}
    ssot_flows = [n for n in ssot_nodes if n.get('kind') == 'flow']
    ssot_domains = [n for n in ssot_nodes if n.get('kind') == 'domain']

    code_files = [n for n in code_nodes if n['kind'] == 'file']
    code_file_paths = set(n['file_path'] for n in code_files)

    # 3. 檢查 Flow → 實作
    for flow in ssot_flows:
        flow_id = flow.get('id', '')
        flow_name = flow_id.replace('flow.', '').lower()
        ref = flow.get('ref', '')

        # 正規化名稱（處理 - 和 _ 的差異）
        flow_name_normalized = flow_name.replace('-', '_').replace('.', '_')
        flow_name_parts = set(flow_name.replace('-', ' ').replace('_', ' ').split())

        # 如果有 ref，優先檢查 ref 指向的檔案
        has_impl = False
        matched_files = []

        if ref:
            # ref 直接指定檔案，檢查是否存在於 Code Graph
            for file_path in code_file_paths:
                if ref in file_path or file_path.endswith(ref):
                    has_impl = True
                    matched_files.append(file_path)
                    break

        # 如果沒有 ref 或 ref 沒匹配到，用啟發式匹配
        if not has_impl:
            for file_path in code_file_paths:
                file_name = os.path.basename(file_path).lower()
                file_stem = os.path.splitext(file_name)[0]
                file_stem_normalized = file_stem.replace('-', '_').replace('.', '_')

                # 正規化後匹配
                if flow_name_normalized in file_stem_normalized or file_stem_normalized in flow_name_normalized:
                    has_impl = True
                    matched_files.append(file_path)
                # 部分名稱匹配（至少 2 個詞相符）
                elif len(flow_name_parts) >= 2:
                    file_parts = set(file_stem.replace('-', ' ').replace('_', ' ').split())
                    common = flow_name_parts & file_parts
                    if len(common) >= min(2, len(flow_name_parts)):
                        has_impl = True
                        matched_files.append(file_path)
                # 路徑包含
                elif flow_name_normalized in file_path.lower().replace('-', '_'):
                    has_impl = True
                    matched_files.append(file_path)

        if not has_impl:
            drifts.append(DriftItem(
                id=make_drift_id(),
                type='missing_implementation',
                severity='high',
                ssot_item=flow_id,
                description=f"Flow '{flow_id}' defined in SSOT but no matching code files found",
                suggestion=f"Create implementation file for {flow_id} or update SSOT if flow was removed"
            ))

    # 4. 檢查 Code → SSOT 文檔
    # 找出重要的 Code 模組（api/, routes/, controllers/, services/）
    important_patterns = ['api/', 'routes/', 'controllers/', 'services/', 'handlers/']

    for code_file in code_files:
        file_path = code_file.get('file_path', '')

        # 檢查是否是重要模組
        is_important = any(p in file_path for p in important_patterns)
        if not is_important:
            continue

        # 提取可能的 flow 名稱
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        expected_flow_id = f"flow.{file_name}"

        # 檢查 SSOT 是否有對應文檔
        has_spec = expected_flow_id in ssot_by_id

        # 也檢查模糊匹配
        if not has_spec:
            for ssot_id in ssot_by_id:
                if file_name.lower() in ssot_id.lower():
                    has_spec = True
                    break

        if not has_spec:
            drifts.append(DriftItem(
                id=make_drift_id(),
                type='missing_spec',
                severity='medium',
                code_item=file_path,
                description=f"Code file '{file_path}' exists but no SSOT spec found",
                suggestion=f"Create SSOT spec for '{expected_flow_id}' in brain/ssot/flows/"
            ))

    # 5. 建立報告
    summary_parts = []
    if drifts:
        by_type = {}
        for d in drifts:
            by_type[d.type] = by_type.get(d.type, 0) + 1

        for t, count in sorted(by_type.items()):
            summary_parts.append(f"{count} {t}")

        summary = f"Found {len(drifts)} drift(s): " + ", ".join(summary_parts)
    else:
        summary = "No drift detected. SSOT and Code are in sync."

    return DriftReport(
        has_drift=len(drifts) > 0,
        drift_count=len(drifts),
        drifts=drifts,
        summary=summary
    )


def detect_flow_drift(project: str, flow_id: str) -> DriftReport:
    """偵測特定 Flow 的偏差"""
    from servers.ssot import load_flow_spec
    from servers.graph import get_neighbors
    from servers.code_graph import get_code_nodes

    drifts = []
    drift_id = 0

    def make_drift_id():
        nonlocal drift_id
        drift_id += 1
        return f"drift-{project}-{flow_id}-{drift_id:04d}"

    # 1. 取得 Flow Spec
    flow_spec = None
    try:
        flow_spec = load_flow_spec(flow_id)
    except:
        pass

    if not flow_spec:
        return DriftReport(
            has_drift=True,
            drift_count=1,
            drifts=[DriftItem(
                id=make_drift_id(),
                type='missing_spec',
                severity='high',
                ssot_item=flow_id,
                description=f"Flow spec for '{flow_id}' not found",
                suggestion=f"Create brain/ssot/flows/{flow_id.replace('flow.', '')}.md"
            )],
            summary=f"Flow '{flow_id}' has no SSOT specification"
        )

    # 2. 取得 Graph 鄰居（SSOT 層）
    try:
        neighbors = get_neighbors(flow_id, project, depth=1)
    except:
        neighbors = []

    # 3. 取得相關 Code
    flow_name = flow_id.replace('flow.', '').lower()
    code_nodes = get_code_nodes(project, limit=500)

    related_code = []
    for node in code_nodes:
        if flow_name in node.get('file_path', '').lower():
            related_code.append(node)
        elif flow_name in node.get('name', '').lower():
            related_code.append(node)

    # 4. 檢查一致性
    # 從 Spec 中提取預期的 API endpoints
    api_pattern = re.compile(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', re.IGNORECASE)
    expected_apis = set(api_pattern.findall(flow_spec))

    # 檢查是否有對應的 Code
    if not related_code and expected_apis:
        drifts.append(DriftItem(
            id=make_drift_id(),
            type='missing_implementation',
            severity='high',
            ssot_item=flow_id,
            description=f"Flow '{flow_id}' specifies APIs but no related code found",
            suggestion="Implement the APIs defined in the flow spec"
        ))

    # 5. 檢查測試覆蓋
    has_test = any('test' in n.get('file_path', '').lower() for n in related_code)
    test_neighbors = [n for n in neighbors if n.get('kind') == 'test']

    if not has_test and not test_neighbors:
        drifts.append(DriftItem(
            id=make_drift_id(),
            type='missing_implementation',
            severity='medium',
            ssot_item=flow_id,
            description=f"Flow '{flow_id}' has no test coverage",
            suggestion=f"Create test file for {flow_id}"
        ))

    # 6. 建立報告
    if drifts:
        summary = f"Flow '{flow_id}' has {len(drifts)} drift(s)"
    else:
        summary = f"Flow '{flow_id}' is in sync with code"

    return DriftReport(
        has_drift=len(drifts) > 0,
        drift_count=len(drifts),
        drifts=drifts,
        summary=summary
    )


def detect_coverage_gaps(project: str) -> List[Dict]:
    """
    偵測測試覆蓋缺口

    找出沒有對應測試的重要程式碼。
    """
    from servers.code_graph import get_code_nodes, get_code_edges

    # 取得所有 nodes
    nodes = get_code_nodes(project, limit=1000)
    edges = get_code_edges(project, kind='tests', limit=500)

    # 找出被測試覆蓋的 nodes
    covered_ids = set(e['to_id'] for e in edges)

    # 找出重要但未覆蓋的 nodes
    gaps = []
    important_kinds = {'function', 'class', 'api'}

    for node in nodes:
        if node['kind'] not in important_kinds:
            continue

        # 跳過測試檔案本身
        if 'test' in node.get('file_path', '').lower():
            continue

        # 跳過 private 函式
        if node.get('visibility') == 'private':
            continue

        # 檢查是否有測試
        has_test = node['id'] in covered_ids

        # 也用檔案名稱啟發式檢查
        if not has_test:
            file_path = node.get('file_path', '')
            file_stem = os.path.splitext(os.path.basename(file_path))[0]
            test_patterns = [
                f"{file_stem}.test",
                f"{file_stem}.spec",
                f"test_{file_stem}",
            ]
            for test_node in nodes:
                if test_node['kind'] == 'file' and 'test' in test_node.get('file_path', '').lower():
                    test_file = os.path.basename(test_node.get('file_path', '')).lower()
                    if any(p.lower() in test_file for p in test_patterns):
                        has_test = True
                        break

        if not has_test:
            gaps.append({
                'node_id': node['id'],
                'node_kind': node['kind'],
                'name': node['name'],
                'file_path': node.get('file_path'),
                'line_start': node.get('line_start'),
                'has_test': False
            })

    return gaps


# =============================================================================
# Reporting
# =============================================================================

def get_drift_summary(project: str, project_dir: str = None) -> str:
    """取得偏差摘要（Markdown 格式）

    Args:
        project: 專案名稱
        project_dir: 專案目錄路徑（用於讀取專案級 SSOT）
    """
    report = detect_all_drifts(project, project_dir)

    lines = [
        "# SSOT-Code Drift Report",
        "",
        f"**Project**: {project}",
        f"**Checked at**: {report.checked_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Status**: {'⚠️ Drift detected' if report.has_drift else '✅ In sync'}",
        "",
    ]

    if not report.has_drift:
        lines.append("No drift detected. SSOT and Code are in sync.")
        return "\n".join(lines)

    lines.append(f"## Summary")
    lines.append("")
    lines.append(report.summary)
    lines.append("")

    # 按嚴重程度分組
    by_severity = {'critical': [], 'high': [], 'medium': [], 'low': []}
    for drift in report.drifts:
        by_severity.get(drift.severity, by_severity['medium']).append(drift)

    severity_icons = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }

    for severity in ['critical', 'high', 'medium', 'low']:
        items = by_severity[severity]
        if not items:
            continue

        lines.append(f"## {severity_icons[severity]} {severity.title()} ({len(items)})")
        lines.append("")

        for drift in items:
            lines.append(f"### [{drift.type}] {drift.id}")
            lines.append("")
            lines.append(f"**Description**: {drift.description}")
            if drift.ssot_item:
                lines.append(f"**SSOT**: `{drift.ssot_item}`")
            if drift.code_item:
                lines.append(f"**Code**: `{drift.code_item}`")
            lines.append(f"**Suggestion**: {drift.suggestion}")
            lines.append("")

    return "\n".join(lines)


def get_coverage_summary(project: str) -> str:
    """取得測試覆蓋缺口摘要"""
    gaps = detect_coverage_gaps(project)

    lines = [
        "# Test Coverage Gaps",
        "",
        f"**Project**: {project}",
        f"**Gaps found**: {len(gaps)}",
        "",
    ]

    if not gaps:
        lines.append("All important code has test coverage. ✅")
        return "\n".join(lines)

    lines.append("## Uncovered Code")
    lines.append("")
    lines.append("| Kind | Name | File | Line |")
    lines.append("|------|------|------|------|")

    for gap in gaps[:50]:  # 限制顯示數量
        lines.append(
            f"| {gap['node_kind']} | `{gap['name']}` | {gap['file_path']} | {gap['line_start']} |"
        )

    if len(gaps) > 50:
        lines.append(f"\n... and {len(gaps) - 50} more")

    return "\n".join(lines)
