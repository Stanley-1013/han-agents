"""
SSOT Server - 專案 Skill 管理
==============================

讀取專案的 SKILL.md 和相關文檔。
新架構：專案 Skill 位於 <project>/.<platform>/skills/<project-name>/

支援平台：
- Claude Code: .claude/skills/<name>/
- Cursor: .cursor/skills/<name>/
- Windsurf: .windsurf/skills/<name>/
- Cline: .cline/skills/<name>/
- Codex CLI: .codex/skills/<name>/
- Gemini CLI: .gemini/skills/<name>/
- Antigravity: .agent/skills/<name>/

使用方式：
    from servers.ssot import load_skill, load_flow_spec, load_project_skill

    # 加載專案 SKILL.md
    skill = load_skill('/path/to/project')

    # 加載特定 flow 的 spec
    auth_spec = load_flow_spec('auth', '/path/to/project')

    # 加載完整專案 context
    context = load_project_skill('/path/to/project')
"""

import os
import re
import glob
from typing import Dict, List, Optional, Any
from pathlib import Path


# 支援的平台 skills 目錄（優先順序）
PLATFORM_SKILL_DIRS = [
    '.claude/skills',
    '.cursor/skills',
    '.windsurf/skills',
    '.cline/skills',
    '.codex/skills',
    '.gemini/skills',
    '.agent/skills',  # Antigravity
]

SCHEMA = """
=== SSOT Server API ===

load_skill(project_dir: str) -> str
    加載專案 SKILL.md

load_flow_spec(flow_name: str, project_dir: str) -> str
    加載特定 flow 的 spec 文件
    例如: load_flow_spec('auth', '/path/to/project')

load_domain_spec(domain_name: str, project_dir: str) -> str
    加載特定 domain 的 spec 文件

load_project_skill(project_dir: str) -> Dict
    加載完整專案 Skill context
    返回 {'skill': str, 'flows': [...], 'domains': [...], 'apis': [...]}

find_skill_dir(project_dir: str) -> Optional[str]
    尋找專案的 Skill 目錄

parse_skill_links(skill_content: str) -> Dict
    從 SKILL.md 解析 Markdown 連結
    返回 {'flows': [...], 'domains': [...], 'apis': [...]}

validate_skill_refs(project_dir: str) -> Dict
    驗證 SKILL.md 中所有連結是否有效
"""

# =============================================================================
# 向下相容：舊版 .claude/pfc/ 路徑
# =============================================================================

def _find_legacy_ssot(project_dir: str) -> Optional[str]:
    """尋找舊版 SSOT 結構"""
    legacy_path = os.path.join(project_dir, ".claude", "pfc", "INDEX.md")
    if os.path.exists(legacy_path):
        return legacy_path
    return None


def _load_legacy_index(project_dir: str) -> str:
    """載入舊版 INDEX.md"""
    legacy_path = _find_legacy_ssot(project_dir)
    if legacy_path:
        with open(legacy_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


# =============================================================================
# 專案 Skill 目錄尋找
# =============================================================================

def find_skill_dir(project_dir: str) -> Optional[str]:
    """
    尋找專案的 Skill 目錄

    搜尋順序：
    1. <project>/SKILL.md（根目錄，skill 套件自身的情況）
    2. <project>/.<platform>/skills/<name>/SKILL.md（多平台新格式）
    3. <project>/.claude/pfc/INDEX.md（舊格式，向下相容）

    支援平台：claude, cursor, windsurf, cline, codex, gemini, antigravity

    Args:
        project_dir: 專案目錄

    Returns:
        Skill 目錄路徑，如果不存在返回 None
    """
    # 根目錄 SKILL.md（skill 套件自身）
    root_skill = os.path.join(project_dir, "SKILL.md")
    if os.path.exists(root_skill):
        return project_dir

    # 新格式：搜尋所有支援的平台
    for platform_dir in PLATFORM_SKILL_DIRS:
        skills_base = os.path.join(project_dir, platform_dir)
        if os.path.exists(skills_base):
            pattern = os.path.join(skills_base, "*", "SKILL.md")
            matches = glob.glob(pattern)
            if matches:
                # 返回第一個找到的 Skill 目錄
                return os.path.dirname(matches[0])

    # 舊格式：.claude/pfc/（向下相容）
    legacy_path = os.path.join(project_dir, ".claude", "pfc")
    if os.path.exists(os.path.join(legacy_path, "INDEX.md")):
        return legacy_path

    return None


def get_skill_name(project_dir: str) -> Optional[str]:
    """從 Skill 目錄路徑取得專案名稱"""
    skill_dir = find_skill_dir(project_dir)
    if skill_dir:
        return os.path.basename(skill_dir)
    return None


# =============================================================================
# Skill 加載
# =============================================================================

def load_skill(project_dir: str) -> str:
    """
    加載專案 SKILL.md

    Args:
        project_dir: 專案目錄

    Returns:
        SKILL.md 內容，如果不存在返回空字符串
    """
    skill_dir = find_skill_dir(project_dir)

    if not skill_dir:
        return ""

    # 新格式：SKILL.md
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if os.path.exists(skill_md):
        with open(skill_md, 'r', encoding='utf-8') as f:
            return f.read()

    # 舊格式：INDEX.md（向下相容）
    index_md = os.path.join(skill_dir, "INDEX.md")
    if os.path.exists(index_md):
        with open(index_md, 'r', encoding='utf-8') as f:
            return f.read()

    return ""


# 向下相容別名
def load_doctrine(project_dir: Optional[str] = None) -> str:
    """向下相容：load_doctrine -> load_skill"""
    if project_dir:
        return load_skill(project_dir)
    return ""


def load_index(project_dir: Optional[str] = None) -> str:
    """向下相容：load_index -> load_skill"""
    if project_dir:
        return load_skill(project_dir)
    return ""


# =============================================================================
# Spec 文件加載
# =============================================================================

def load_flow_spec(flow_name: str, project_dir: str) -> str:
    """
    加載特定 flow 的 spec 文件

    Args:
        flow_name: Flow 名稱（不含 flow. 前綴），如 'auth'
        project_dir: 專案目錄

    Returns:
        Spec 文件內容
    """
    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return ""

    # 移除可能的 flow. 前綴
    if flow_name.startswith('flow.'):
        flow_name = flow_name[5:]

    # 嘗試多種路徑
    paths = [
        os.path.join(skill_dir, "flows", f"{flow_name}.md"),
        os.path.join(skill_dir, "flows", flow_name, "README.md"),
    ]

    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    return ""


def load_domain_spec(domain_name: str, project_dir: str) -> str:
    """
    加載特定 domain 的 spec 文件

    Args:
        domain_name: Domain 名稱（不含 domain. 前綴），如 'user'
        project_dir: 專案目錄

    Returns:
        Spec 文件內容
    """
    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return ""

    # 移除可能的 domain. 前綴
    if domain_name.startswith('domain.'):
        domain_name = domain_name[7:]

    paths = [
        os.path.join(skill_dir, "domains", f"{domain_name}.md"),
        os.path.join(skill_dir, "domains", domain_name, "README.md"),
    ]

    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    return ""


def load_api_spec(api_name: str, project_dir: str) -> str:
    """
    加載特定 API 的 spec 文件

    Args:
        api_name: API 名稱，如 'endpoints'
        project_dir: 專案目錄

    Returns:
        Spec 文件內容
    """
    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return ""

    paths = [
        os.path.join(skill_dir, "apis", f"{api_name}.md"),
        os.path.join(skill_dir, "apis", api_name, "README.md"),
    ]

    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    return ""


# =============================================================================
# Skill 解析
# =============================================================================

def parse_skill_links(skill_content: str) -> Dict[str, any]:
    """
    從 SKILL.md 解析 Markdown 連結

    提取格式：[name](path) - description

    返回結構化資料供 Agent 判斷使用，不做硬編碼分類。

    Returns:
        {
            'links': [
                {'name': 'API Reference', 'path': 'reference/API.md', 'description': '...', 'section': '## Reference'},
                ...
            ],
            'sections': {
                '## Reference': [link1, link2, ...],
                '## 功能模組': [link3, ...],
                ...
            }
        }
    """
    links = []
    sections = {}

    # 先找出所有 section headings 的位置
    section_pattern = r'^(#{1,3}\s+.+)$'
    section_positions = []
    for match in re.finditer(section_pattern, skill_content, re.MULTILINE):
        section_positions.append({
            'heading': match.group(1).strip(),
            'start': match.start(),
            'end': match.end()
        })

    def get_section_for_position(pos: int) -> str:
        """找出某個位置屬於哪個 section"""
        current_section = ""
        for sec in section_positions:
            if sec['start'] <= pos:
                current_section = sec['heading']
            else:
                break
        return current_section

    # 匹配 Markdown 連結：[text](path) 或 [text](path) - description
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)(?:\s*[-–—]\s*(.+))?'

    for match in re.finditer(link_pattern, skill_content):
        name = match.group(1).strip()
        path = match.group(2).strip()
        description = match.group(3).strip() if match.group(3) else ""

        # 跳過外部連結
        if path.startswith('http://') or path.startswith('https://'):
            continue

        section = get_section_for_position(match.start())

        link_info = {
            'name': name,
            'path': path,
            'description': description,
            'section': section
        }

        links.append(link_info)

        # 同時按 section 分組（供 Agent 參考）
        if section not in sections:
            sections[section] = []
        sections[section].append(link_info)

    return {
        'links': links,
        'sections': sections
    }


def parse_index(project_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    向下相容：解析專案 Skill 為結構化數據

    Returns:
        {'flows': [...], 'domains': [...], 'apis': [...]}
    """
    if not project_dir:
        return {}

    skill_content = load_skill(project_dir)
    if not skill_content:
        return {}

    return parse_skill_links(skill_content)


# =============================================================================
# 完整 Context 加載
# =============================================================================

def load_project_skill(
    project_dir: str,
    include_specs: bool = True,
    max_spec_length: int = 2000
) -> Dict[str, Any]:
    """
    加載完整專案 Skill context

    Args:
        project_dir: 專案目錄
        include_specs: 是否包含 spec 文件內容
        max_spec_length: 每個 spec 的最大長度

    Returns:
        {
            'skill': str,           # SKILL.md 內容
            'skill_dir': str,       # Skill 目錄路徑
            'project_name': str,    # 專案名稱
            'flows': [...],         # Flow specs
            'domains': [...],       # Domain specs
            'apis': [...]           # API specs
        }
    """
    result = {
        'skill': '',
        'skill_dir': None,
        'project_name': None,
        'flows': [],
        'domains': [],
        'apis': []
    }

    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return result

    result['skill_dir'] = skill_dir
    result['project_name'] = os.path.basename(skill_dir)
    result['skill'] = load_skill(project_dir)

    if not include_specs:
        return result

    # 解析 SKILL.md 中的連結
    links = parse_skill_links(result['skill'])

    # 加載 flow specs
    for flow in links.get('flows', []):
        flow_name = os.path.basename(flow['path']).replace('.md', '')
        content = load_flow_spec(flow_name, project_dir)
        if content:
            if len(content) > max_spec_length:
                content = content[:max_spec_length] + f"\n\n... (截斷，完整內容請查看 {flow['path']})"
            result['flows'].append({
                'name': flow['name'],
                'path': flow['path'],
                'content': content
            })

    # 加載 domain specs
    for domain in links.get('domains', []):
        domain_name = os.path.basename(domain['path']).replace('.md', '')
        content = load_domain_spec(domain_name, project_dir)
        if content:
            if len(content) > max_spec_length:
                content = content[:max_spec_length] + f"\n\n... (截斷，完整內容請查看 {domain['path']})"
            result['domains'].append({
                'name': domain['name'],
                'path': domain['path'],
                'content': content
            })

    # 加載 API specs
    for api in links.get('apis', []):
        api_name = os.path.basename(api['path']).replace('.md', '')
        content = load_api_spec(api_name, project_dir)
        if content:
            if len(content) > max_spec_length:
                content = content[:max_spec_length] + f"\n\n... (截斷，完整內容請查看 {api['path']})"
            result['apis'].append({
                'name': api['name'],
                'path': api['path'],
                'content': content
            })

    return result


# 向下相容別名
def load_ssot_for_branch(
    branch: Dict[str, Any],
    project_dir: Optional[str] = None,
    include_doctrine: bool = True,
    max_spec_length: int = 2000
) -> str:
    """向下相容：轉換為 load_project_skill"""
    if not project_dir:
        return ""

    context = load_project_skill(project_dir, max_spec_length=max_spec_length)

    sections = []

    if context['skill']:
        sections.append(f"# Project Skill\n\n{context['skill'][:1500]}")

    for flow in context['flows']:
        sections.append(f"# Flow: {flow['name']}\n\n{flow['content']}")

    for domain in context['domains']:
        sections.append(f"# Domain: {domain['name']}\n\n{domain['content']}")

    return "\n\n---\n\n".join(sections)


# =============================================================================
# 驗證
# =============================================================================

def validate_skill_refs(project_dir: str) -> Dict[str, Any]:
    """
    驗證 SKILL.md 中所有連結是否有效

    Returns:
        {
            'valid': bool,
            'total': int,
            'valid_refs': [...],
            'missing_refs': [...]
        }
    """
    result = {
        'valid': True,
        'total': 0,
        'valid_refs': [],
        'missing_refs': []
    }

    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return result

    skill_content = load_skill(project_dir)
    links = parse_skill_links(skill_content)

    # 檢查所有連結
    all_links = links.get('flows', []) + links.get('domains', []) + links.get('apis', []) + links.get('other', [])

    for link in all_links:
        result['total'] += 1
        ref_path = os.path.join(skill_dir, link['path'])

        if os.path.exists(ref_path):
            result['valid_refs'].append({
                'name': link['name'],
                'path': link['path'],
                'full_path': ref_path
            })
        else:
            result['missing_refs'].append({
                'name': link['name'],
                'path': link['path'],
                'expected_path': ref_path
            })
            result['valid'] = False

    return result


# 向下相容別名
def validate_index_refs(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """向下相容：validate_index_refs -> validate_skill_refs"""
    if project_dir:
        return validate_skill_refs(project_dir)
    return {'valid': True, 'total': 0, 'valid_refs': [], 'missing_refs': []}


# =============================================================================
# 輔助函數
# =============================================================================

def get_node_by_id(node_id: str, project_dir: Optional[str] = None) -> Optional[Dict]:
    """
    向下相容：根據 node id 獲取節點信息

    Args:
        node_id: 節點 ID，如 'flow.auth', 'domain.user'

    Returns:
        節點信息字典，如果不存在返回 None
    """
    if not project_dir:
        return None

    links = parse_index(project_dir)

    # 根據 id 前綴確定類型
    if node_id.startswith('flow.'):
        name = node_id[5:]
        for flow in links.get('flows', []):
            if name in flow['path']:
                return {'id': node_id, 'name': flow['name'], 'ref': flow['path']}
    elif node_id.startswith('domain.'):
        name = node_id[7:]
        for domain in links.get('domains', []):
            if name in domain['path']:
                return {'id': node_id, 'name': domain['name'], 'ref': domain['path']}
    elif node_id.startswith('api.'):
        name = node_id[4:]
        for api in links.get('apis', []):
            if name in api['path']:
                return {'id': node_id, 'name': api['name'], 'ref': api['path']}

    return None


def list_available_specs(project_dir: str) -> Dict[str, List[str]]:
    """
    列出專案中所有可用的 spec 文件

    Returns:
        {'flows': ['auth', 'checkout'], 'domains': ['user', 'order'], 'apis': [...]}
    """
    result = {'flows': [], 'domains': [], 'apis': []}

    skill_dir = find_skill_dir(project_dir)
    if not skill_dir:
        return result

    # 掃描 flows 目錄
    flows_dir = os.path.join(skill_dir, "flows")
    if os.path.exists(flows_dir):
        for f in os.listdir(flows_dir):
            if f.endswith('.md'):
                result['flows'].append(f[:-3])

    # 掃描 domains 目錄
    domains_dir = os.path.join(skill_dir, "domains")
    if os.path.exists(domains_dir):
        for f in os.listdir(domains_dir):
            if f.endswith('.md'):
                result['domains'].append(f[:-3])

    # 掃描 apis 目錄
    apis_dir = os.path.join(skill_dir, "apis")
    if os.path.exists(apis_dir):
        for f in os.listdir(apis_dir):
            if f.endswith('.md'):
                result['apis'].append(f[:-3])

    return result


# =============================================================================
# 測試入口
# =============================================================================

if __name__ == "__main__":
    import sys

    print(SCHEMA)
    print("\n" + "=" * 50 + "\n")

    # 使用當前目錄或命令列參數
    test_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    print(f"=== Testing with project_dir: {test_dir} ===\n")

    # 測試 find_skill_dir
    skill_dir = find_skill_dir(test_dir)
    print(f"Skill directory: {skill_dir}")

    # 測試 load_skill
    skill = load_skill(test_dir)
    print(f"\nSKILL.md length: {len(skill)} chars")
    if skill:
        print(skill[:300] + "..." if len(skill) > 300 else skill)

    # 測試 parse_skill_links
    if skill:
        links = parse_skill_links(skill)
        print(f"\n=== Parsed links ===")
        for category, items in links.items():
            if items:
                print(f"{category}: {len(items)} items")
                for item in items[:2]:
                    print(f"  - {item['name']}: {item['path']}")

    # 測試 validate_skill_refs
    validation = validate_skill_refs(test_dir)
    print(f"\n=== Validation ===")
    print(f"Valid: {validation['valid']}")
    print(f"Total refs: {validation['total']}")
    print(f"Valid refs: {len(validation['valid_refs'])}")
    print(f"Missing refs: {len(validation['missing_refs'])}")
    for missing in validation['missing_refs']:
        print(f"  ❌ {missing['name']}: {missing['path']}")
