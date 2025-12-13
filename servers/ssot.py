"""
SSOT Server - Single Source of Truth 管理
==========================================

提供注意力樹（Attention Tree）的 L0/L1/L2 加載功能：
- L0: Project Doctrine（核心目標與約束）
- L1: Project Index（Flow/Domain/API/Page 目錄）
- L2: 具體 Spec 文件（按需加載）

使用方式：
    from servers.ssot import load_doctrine, load_index, load_flow_spec, load_ssot_for_branch

    # 加載核心約束
    doctrine = load_doctrine()

    # 加載目錄
    index = load_index()

    # 加載特定 flow 的 spec
    auth_spec = load_flow_spec('flow.auth')

    # 根據 branch 加載完整 context
    context = load_ssot_for_branch({
        'flow_id': 'flow.auth',
        'domain_ids': ['domain.user']
    })
"""

import os
import re
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path

# =============================================================================
# 常量定義
# =============================================================================

SSOT_DIR = os.path.expanduser("~/.claude/neuromorphic/brain/ssot")

SCHEMA = """
=== SSOT Server API ===

load_doctrine() -> str
    加載 PROJECT_DOCTRINE.md (L0)

load_index() -> str
    加載 PROJECT_INDEX.md (L1)

load_flow_spec(flow_id: str) -> str
    加載特定 flow 的 spec 文件 (L2)
    例如: load_flow_spec('flow.auth') -> flows/auth.md

load_domain_spec(domain_id: str) -> str
    加載特定 domain 的 spec 文件 (L2)
    例如: load_domain_spec('domain.user') -> domains/user.md

load_ssot_for_branch(branch: Dict) -> str
    根據 branch 加載完整 SSOT context
    branch = {
        'flow_id': 'flow.auth',
        'domain_ids': ['domain.user']
    }

parse_index() -> Dict
    解析 PROJECT_INDEX.md 為結構化數據
    返回 {'flows': [...], 'domains': [...], 'apis': [...], ...}

get_node_by_id(node_id: str) -> Optional[Dict]
    根據 node id 獲取節點信息
    例如: get_node_by_id('flow.auth')

validate_index_refs(project_dir: str = None) -> Dict
    驗證 INDEX 中所有 ref 指向的檔案是否存在
    返回 {'valid': bool, 'total': int, 'valid_refs': [...], 'missing_refs': [...]}
"""

# =============================================================================
# L0: Doctrine 加載
# =============================================================================

def load_doctrine(project_dir: Optional[str] = None) -> str:
    """
    加載 Project Doctrine (L0)

    Args:
        project_dir: 專案目錄（可選，用於專案特定的 doctrine）

    Returns:
        Doctrine 文件內容，如果不存在返回空字符串
    """
    # 優先嘗試專案特定的 doctrine
    if project_dir:
        project_doctrine = os.path.join(project_dir, ".ssot", "DOCTRINE.md")
        if os.path.exists(project_doctrine):
            with open(project_doctrine, 'r', encoding='utf-8') as f:
                return f.read()

    # 使用全局模板
    global_path = os.path.join(SSOT_DIR, "PROJECT_DOCTRINE.md")
    if os.path.exists(global_path):
        with open(global_path, 'r', encoding='utf-8') as f:
            return f.read()

    return ""


# =============================================================================
# L1: Index 加載與解析
# =============================================================================

def load_index(project_dir: Optional[str] = None) -> str:
    """
    加載 Project Index (L1)

    Args:
        project_dir: 專案目錄（可選）

    Returns:
        Index 文件內容
    """
    # 優先嘗試專案特定的 index
    if project_dir:
        project_index = os.path.join(project_dir, ".ssot", "INDEX.md")
        if os.path.exists(project_index):
            with open(project_index, 'r', encoding='utf-8') as f:
                return f.read()

    # 使用全局模板
    global_path = os.path.join(SSOT_DIR, "PROJECT_INDEX.md")
    if os.path.exists(global_path):
        with open(global_path, 'r', encoding='utf-8') as f:
            return f.read()

    return ""


def parse_index(project_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    解析 PROJECT_INDEX.md 為結構化數據

    **動態解析**：不限定固定類型，任何 YAML 區塊的 key 都會被收集。
    這樣新增類型時只需要修改 INDEX.md，不用改程式碼。

    Returns:
        {
            'flows': [{'id': 'flow.auth', 'name': 'Authentication', ...}, ...],
            'domains': [...],
            'apis': [...],
            ... (任何在 YAML 中定義的類型)
        }
    """
    content = load_index(project_dir)
    if not content:
        return {}

    result = {}  # 動態收集，不預設任何 key

    # 使用正則提取 yaml 代碼塊
    yaml_pattern = r'```yaml\s*\n([\s\S]*?)\n```'
    matches = re.findall(yaml_pattern, content)

    for yaml_content in matches:
        try:
            data = yaml.safe_load(yaml_content)
            if data and isinstance(data, dict):
                for key, items in data.items():
                    if isinstance(items, list):
                        if key not in result:
                            result[key] = []
                        result[key].extend(items)
        except yaml.YAMLError:
            continue

    return result


def get_node_by_id(node_id: str, project_dir: Optional[str] = None) -> Optional[Dict]:
    """
    根據 node id 獲取節點信息

    Args:
        node_id: 節點 ID，如 'flow.auth', 'domain.user'

    Returns:
        節點信息字典，如果不存在返回 None
    """
    index_data = parse_index(project_dir)

    # 根據 id 前綴確定類型
    node_type = node_id.split('.')[0]
    type_mapping = {
        'flow': 'flows',
        'domain': 'domains',
        'api': 'apis',
        'page': 'pages',
        'test': 'tests'
    }

    collection_key = type_mapping.get(node_type)
    if not collection_key:
        return None

    for node in index_data.get(collection_key, []):
        if node.get('id') == node_id:
            return node

    return None


def get_all_nodes(project_dir: Optional[str] = None) -> List[Dict]:
    """
    獲取所有節點

    Returns:
        所有節點的列表
    """
    index_data = parse_index(project_dir)
    all_nodes = []

    for collection in index_data.values():
        all_nodes.extend(collection)

    return all_nodes


# =============================================================================
# L2: Spec 文件加載
# =============================================================================

def load_flow_spec(flow_id: str, project_dir: Optional[str] = None) -> str:
    """
    加載特定 flow 的 spec 文件 (L2)

    Args:
        flow_id: Flow ID，如 'flow.auth'

    Returns:
        Spec 文件內容
    """
    # 從 flow_id 提取文件名
    # flow.auth -> auth.md
    name = flow_id.replace('flow.', '')

    # 優先嘗試專案特定的 spec
    if project_dir:
        project_spec = os.path.join(project_dir, ".ssot", "flows", f"{name}.md")
        if os.path.exists(project_spec):
            with open(project_spec, 'r', encoding='utf-8') as f:
                return f.read()

    # 使用全局 spec
    global_path = os.path.join(SSOT_DIR, "flows", f"{name}.md")
    if os.path.exists(global_path):
        with open(global_path, 'r', encoding='utf-8') as f:
            return f.read()

    return ""


def load_domain_spec(domain_id: str, project_dir: Optional[str] = None) -> str:
    """
    加載特定 domain 的 spec 文件 (L2)

    Args:
        domain_id: Domain ID，如 'domain.user'

    Returns:
        Spec 文件內容
    """
    # 從 domain_id 提取文件名
    # domain.user -> user.md
    name = domain_id.replace('domain.', '')

    # 優先嘗試專案特定的 spec
    if project_dir:
        project_spec = os.path.join(project_dir, ".ssot", "domains", f"{name}.md")
        if os.path.exists(project_spec):
            with open(project_spec, 'r', encoding='utf-8') as f:
                return f.read()

    # 使用全局 spec
    global_path = os.path.join(SSOT_DIR, "domains", f"{name}.md")
    if os.path.exists(global_path):
        with open(global_path, 'r', encoding='utf-8') as f:
            return f.read()

    return ""


def load_spec_by_node_id(node_id: str, project_dir: Optional[str] = None) -> str:
    """
    根據 node id 加載對應的 spec 文件

    Args:
        node_id: 節點 ID

    Returns:
        Spec 文件內容
    """
    node = get_node_by_id(node_id, project_dir)
    if not node:
        return ""

    # 如果節點有 spec 字段，直接使用
    if 'spec' in node:
        spec_path = os.path.join(SSOT_DIR, node['spec'])
        if os.path.exists(spec_path):
            with open(spec_path, 'r', encoding='utf-8') as f:
                return f.read()

    # 否則根據類型推斷
    node_type = node_id.split('.')[0]
    if node_type == 'flow':
        return load_flow_spec(node_id, project_dir)
    elif node_type == 'domain':
        return load_domain_spec(node_id, project_dir)

    return ""


# =============================================================================
# Branch Context 加載
# =============================================================================

def load_ssot_for_branch(
    branch: Dict[str, Any],
    project_dir: Optional[str] = None,
    include_doctrine: bool = True,
    max_spec_length: int = 2000
) -> str:
    """
    根據 branch 加載完整 SSOT context

    Args:
        branch: Branch 信息，如 {'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}
        project_dir: 專案目錄
        include_doctrine: 是否包含 Doctrine
        max_spec_length: 每個 spec 的最大長度（避免 context 爆炸）

    Returns:
        組合的 SSOT context 字符串
    """
    sections = []

    # L0: Doctrine（如果需要）
    if include_doctrine:
        doctrine = load_doctrine(project_dir)
        if doctrine:
            # 只取 Doctrine 的關鍵部分（前 1500 字符）
            doctrine_preview = doctrine[:1500]
            if len(doctrine) > 1500:
                doctrine_preview += "\n\n... (Doctrine 已截斷，完整版請查看 PROJECT_DOCTRINE.md)"
            sections.append(f"# Project Doctrine (L0)\n\n{doctrine_preview}")

    # L2: Flow Spec
    flow_id = branch.get('flow_id')
    if flow_id:
        flow_spec = load_flow_spec(flow_id, project_dir)
        if flow_spec:
            spec_preview = flow_spec[:max_spec_length]
            if len(flow_spec) > max_spec_length:
                spec_preview += f"\n\n... (完整 spec 請查看 flows/{flow_id.replace('flow.', '')}.md)"
            sections.append(f"# Flow: {flow_id}\n\n{spec_preview}")

    # L2: Domain Specs
    domain_ids = branch.get('domain_ids', [])
    for domain_id in domain_ids:
        domain_spec = load_domain_spec(domain_id, project_dir)
        if domain_spec:
            spec_preview = domain_spec[:max_spec_length]
            if len(domain_spec) > max_spec_length:
                spec_preview += f"\n\n... (完整 spec 請查看 domains/{domain_id.replace('domain.', '')}.md)"
            sections.append(f"# Domain: {domain_id}\n\n{spec_preview}")

    return "\n\n---\n\n".join(sections)


# =============================================================================
# 輔助函數
# =============================================================================

def list_available_specs(project_dir: Optional[str] = None) -> Dict[str, List[str]]:
    """
    列出所有可用的 spec 文件

    Returns:
        {'flows': ['auth', 'checkout'], 'domains': ['user', 'order']}
    """
    result = {'flows': [], 'domains': []}

    # 檢查全局目錄
    flows_dir = os.path.join(SSOT_DIR, "flows")
    if os.path.exists(flows_dir):
        for f in os.listdir(flows_dir):
            if f.endswith('.md'):
                result['flows'].append(f[:-3])  # 移除 .md

    domains_dir = os.path.join(SSOT_DIR, "domains")
    if os.path.exists(domains_dir):
        for f in os.listdir(domains_dir):
            if f.endswith('.md'):
                result['domains'].append(f[:-3])

    # 檢查專案特定目錄
    if project_dir:
        project_flows = os.path.join(project_dir, ".ssot", "flows")
        if os.path.exists(project_flows):
            for f in os.listdir(project_flows):
                if f.endswith('.md') and f[:-3] not in result['flows']:
                    result['flows'].append(f[:-3])

        project_domains = os.path.join(project_dir, ".ssot", "domains")
        if os.path.exists(project_domains):
            for f in os.listdir(project_domains):
                if f.endswith('.md') and f[:-3] not in result['domains']:
                    result['domains'].append(f[:-3])

    return result


def validate_branch(branch: Dict[str, Any], project_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    驗證 branch 信息是否有效

    Args:
        branch: Branch 信息

    Returns:
        {'valid': bool, 'errors': [...], 'warnings': [...]}
    """
    result = {'valid': True, 'errors': [], 'warnings': []}
    index_data = parse_index(project_dir)

    # 檢查 flow_id
    flow_id = branch.get('flow_id')
    if flow_id:
        flow_ids = [f['id'] for f in index_data.get('flows', [])]
        if flow_id not in flow_ids:
            result['warnings'].append(f"flow_id '{flow_id}' 不在 INDEX 中")

    # 檢查 domain_ids
    domain_ids = branch.get('domain_ids', [])
    known_domain_ids = [d['id'] for d in index_data.get('domains', [])]
    for domain_id in domain_ids:
        if domain_id not in known_domain_ids:
            result['warnings'].append(f"domain_id '{domain_id}' 不在 INDEX 中")

    return result


def validate_index_refs(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    驗證 INDEX 中所有 ref 指向的檔案是否存在

    Args:
        project_dir: 專案目錄（用於解析相對路徑）

    Returns:
        {
            'valid': bool,
            'total': int,
            'valid_refs': [...],
            'missing_refs': [...],
            'errors': [...]
        }
    """
    result = {
        'valid': True,
        'total': 0,
        'valid_refs': [],
        'missing_refs': [],
        'errors': []
    }

    index_data = parse_index(project_dir)

    # 決定基礎路徑
    if project_dir:
        base_path = Path(project_dir)
    else:
        base_path = Path(SSOT_DIR).parent.parent  # neuromorphic 根目錄

    # 遍歷所有類型的節點
    for node_type, nodes in index_data.items():
        if not isinstance(nodes, list):
            continue

        for node in nodes:
            if not isinstance(node, dict):
                continue

            # 支援多種 ref 字段名
            ref = node.get('ref') or node.get('spec') or node.get('file') or node.get('path')
            if not ref:
                continue

            result['total'] += 1
            node_id = node.get('id', 'unknown')

            # 解析路徑
            ref_path = base_path / ref

            if ref_path.exists():
                result['valid_refs'].append({
                    'node_id': node_id,
                    'ref': ref,
                    'path': str(ref_path)
                })
            else:
                result['missing_refs'].append({
                    'node_id': node_id,
                    'ref': ref,
                    'expected_path': str(ref_path)
                })
                result['valid'] = False

    return result


# =============================================================================
# 測試入口
# =============================================================================

if __name__ == "__main__":
    print(SCHEMA)
    print("\n" + "=" * 50 + "\n")

    # 測試 load_doctrine
    print("=== Testing load_doctrine() ===")
    doctrine = load_doctrine()
    print(f"Doctrine length: {len(doctrine)} chars")
    print(doctrine[:200] + "..." if len(doctrine) > 200 else doctrine)

    print("\n=== Testing load_index() ===")
    index = load_index()
    print(f"Index length: {len(index)} chars")

    print("\n=== Testing parse_index() ===")
    parsed = parse_index()
    for key, items in parsed.items():
        print(f"{key}: {len(items)} items")
        for item in items[:2]:
            print(f"  - {item.get('id')}: {item.get('name')}")

    print("\n=== Testing load_ssot_for_branch() ===")
    branch = {
        'flow_id': 'flow.auth',
        'domain_ids': ['domain.user']
    }
    context = load_ssot_for_branch(branch)
    print(f"Context length: {len(context)} chars")
    print(context[:500] + "..." if len(context) > 500 else context)
