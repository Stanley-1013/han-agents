"""
Code Graph Extractor - 核心提取邏輯

使用 Tree-sitter 解析 AST，提取：
- Node: file, class, function, interface, type, constant, variable
- Edge: imports, calls, extends, implements, defines, contains

設計原則：
1. 不依賴 LLM，結果確定性
2. 增量更新，只處理變更檔案
3. 多語言支援（可擴展）
"""

import os
import hashlib
import re
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CodeNode:
    """程式碼節點"""
    id: str                          # e.g. 'func.src/api/auth.ts:validateToken'
    kind: str                        # e.g. 'function', 'class', 'file'
    name: str                        # e.g. 'validateToken'
    file_path: str                   # e.g. 'src/api/auth.ts'
    line_start: int = 0
    line_end: int = 0
    signature: Optional[str] = None  # 函式簽名或類別定義
    language: Optional[str] = None   # 'typescript', 'python'
    visibility: Optional[str] = None # 'public', 'private', 'protected'
    hash: Optional[str] = None       # 內容 hash

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'kind': self.kind,
            'name': self.name,
            'file_path': self.file_path,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'signature': self.signature,
            'language': self.language,
            'visibility': self.visibility,
            'hash': self.hash,
        }


@dataclass
class CodeEdge:
    """程式碼邊（關係）"""
    from_id: str                     # 來源 node id
    to_id: str                       # 目標 node id
    kind: str                        # 'imports', 'calls', 'extends', etc.
    line_number: Optional[int] = None
    confidence: float = 1.0          # 確定性程度

    def to_dict(self) -> Dict:
        return {
            'from_id': self.from_id,
            'to_id': self.to_id,
            'kind': self.kind,
            'line_number': self.line_number,
            'confidence': self.confidence,
        }


@dataclass
class ExtractionResult:
    """提取結果"""
    nodes: List[CodeNode] = field(default_factory=list)
    edges: List[CodeEdge] = field(default_factory=list)
    file_path: str = ''
    file_hash: str = ''
    language: str = ''
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Constants
# =============================================================================

SUPPORTED_EXTENSIONS = {
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.py': 'python',
    '.go': 'go',
    '.java': 'java',
    '.rs': 'rust',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
    '.hh': 'cpp',
    '.hxx': 'cpp',
}

# 忽略的目錄
IGNORED_DIRS = {
    'node_modules',
    '.git',
    '__pycache__',
    '.venv',
    'venv',
    'dist',
    'build',
    '.next',
    'coverage',
}

# =============================================================================
# Helper Functions
# =============================================================================

def get_supported_languages() -> List[str]:
    """取得支援的語言列表"""
    return list(set(SUPPORTED_EXTENSIONS.values()))

def normalize_file_path(file_path: str, project_root: Optional[str] = None) -> str:
    """Normalize to project-relative POSIX-style path for stable IDs and DB keys."""
    if project_root:
        file_path = os.path.relpath(file_path, project_root)
    return Path(file_path).as_posix()

def compute_file_hash(file_path: str) -> str:
    """計算檔案內容 hash"""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def make_node_id(kind: str, file_path: str, name: str = None) -> str:
    """
    生成 Node ID

    格式：{kind}.{file_path}[:{name}]
    例如：
    - file.src/api/auth.ts
    - func.src/api/auth.ts:validateToken
    - class.src/models/User.ts:User
    """
    base = f"{kind}.{file_path}"
    if name:
        return f"{base}:{name}"
    return base

def detect_language(file_path: str) -> Optional[str]:
    """偵測檔案語言"""
    ext = os.path.splitext(file_path)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext)

# =============================================================================
# Regex-Based Extractors (Fallback when Tree-sitter unavailable)
# =============================================================================

class RegexExtractor:
    """
    基於正則表達式的提取器

    當 Tree-sitter 不可用時作為 fallback。
    準確度較低但無需額外依賴。
    """

    # TypeScript/JavaScript patterns
    TS_PATTERNS = {
        'import': re.compile(
            r'^import\s+(?:(?:\{[^}]+\}|\*\s+as\s+\w+|\w+)\s+from\s+)?[\'"]([^\'"]+)[\'"]',
            re.MULTILINE
        ),
        'export_function': re.compile(
            r'^export\s+(?:async\s+)?function\s+(\w+)',
            re.MULTILINE
        ),
        'export_const_arrow': re.compile(
            r'^export\s+const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>',
            re.MULTILINE
        ),
        'function': re.compile(
            r'^(?:async\s+)?function\s+(\w+)',
            re.MULTILINE
        ),
        'const_arrow': re.compile(
            r'^const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?',
            re.MULTILINE
        ),
        'interface': re.compile(
            r'^(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?',
            re.MULTILINE
        ),
        'type': re.compile(
            r'^(?:export\s+)?type\s+(\w+)\s*=',
            re.MULTILINE
        ),
        'const': re.compile(
            r'^(?:export\s+)?const\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*[^=]',
            re.MULTILINE
        ),
    }

    # Python patterns
    PY_PATTERNS = {
        'import': re.compile(
            r'^(?:from\s+(\S+)\s+)?import\s+(.+)$',
            re.MULTILINE
        ),
        'function': re.compile(
            r'^(?:async\s+)?def\s+(\w+)\s*\(',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^class\s+(\w+)(?:\s*\(([^)]*)\))?:',
            re.MULTILINE
        ),
        'const': re.compile(
            r'^([A-Z][A-Z0-9_]*)\s*=',
            re.MULTILINE
        ),
    }

    # Java patterns
    JAVA_PATTERNS = {
        'package': re.compile(
            r'^\s*package\s+([\w.]+)\s*;',
            re.MULTILINE
        ),
        'import': re.compile(
            r'^\s*import\s+(?:static\s+)?([\w.*]+)\s*;',
            re.MULTILINE
        ),
        'class': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:final\s+)?(?:static\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w.<>]+))?(?:\s+implements\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'interface': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'enum': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?enum\s+(\w+)(?:\s+implements\s+([\w\s,.<>]+))?\s*\{',
            re.MULTILINE
        ),
        'annotation': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?@interface\s+(\w+)\s*\{',
            re.MULTILINE
        ),
        'method': re.compile(
            r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected)\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:synchronized\s+)?(?:native\s+)?(?:<[^>]+>\s+)?([A-Z][\w.<>\[\]]*|void|int|long|short|byte|char|boolean|float|double)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+([\w\s,.<>]+))?\s*(?:\{|;)',
            re.MULTILINE
        ),
        'field': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:transient\s+)?(?:volatile\s+)?([\w.<>\[\],\s]+)\s+(\w+)(?:\s*=\s*[^;]+)?\s*;',
            re.MULTILINE
        ),
        'constant': re.compile(
            r'^\s*(?:public\s+|private\s+|protected\s+)?static\s+final\s+([\w.<>\[\]]+)\s+([A-Z][A-Z0-9_]*)\s*=',
            re.MULTILINE
        ),
        # 新增：欄位上的依賴注入註解（Spring/Jakarta）
        'injected_field': re.compile(
            r'^\s*(@(?:Autowired|Inject|Resource|Value|MockBean|Mock|InjectMocks)(?:\([^)]*\))?)\s*(?:private\s+|protected\s+|public\s+)?(?:final\s+)?([\w.<>\[\]]+)\s+(\w+)\s*;',
            re.MULTILINE
        ),
    }

    # Rust patterns
    RUST_PATTERNS = {
        'mod': re.compile(
            r'^\s*(?:pub(?:\s*\([^)]+\))?\s+)?mod\s+(\w+)\s*(?:\{|;)',
            re.MULTILINE
        ),
        'use': re.compile(
            r'^\s*(?:pub(?:\s*\([^)]+\))?\s+)?use\s+([^;]+);',
            re.MULTILINE
        ),
        'struct': re.compile(
            r'^\s*(?:#\[[^\]]+\]\s*)*(?:pub(?:\s*\([^)]+\))?\s+)?struct\s+(\w+)(?:<[^>]+>)?(?:\s*\([^)]*\)\s*;|\s*(?:where\s+[^{]+)?\{)',
            re.MULTILINE
        ),
        'enum': re.compile(
            r'^\s*(?:#\[[^\]]+\]\s*)*(?:pub(?:\s*\([^)]+\))?\s+)?enum\s+(\w+)(?:<[^>]+>)?(?:\s+where\s+[^{]+)?\s*\{',
            re.MULTILINE
        ),
        'trait': re.compile(
            r'^\s*(?:#\[[^\]]+\]\s*)*(?:pub(?:\s*\([^)]+\))?\s+)?(?:unsafe\s+)?trait\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[^{]+)?(?:\s+where\s+[^{]+)?\s*\{',
            re.MULTILINE
        ),
        'impl': re.compile(
            r'^\s*(?:unsafe\s+)?impl(?:<[^>]+>)?\s+(?:([\w:]+)(?:<[^>]+>)?\s+for\s+)?(\w+)(?:<[^>]+>)?(?:\s+where\s+[^{]+)?\s*\{',
            re.MULTILINE
        ),
        'fn': re.compile(
            r'^\s*(?:#\[[^\]]+\]\s*)*(?:pub(?:\s*\([^)]+\))?\s+)?(?:const\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+"[^"]*"\s+)?fn\s+(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*->\s*([^\{;]+))?(?:\s+where\s+[^{]+)?(?:\s*\{|\s*;)',
            re.MULTILINE
        ),
        'const': re.compile(
            r'^\s*(?:pub(?:\s*\([^)]+\))?\s+)?const\s+([A-Z][A-Z0-9_]*)\s*:\s*([^=]+)\s*=',
            re.MULTILINE
        ),
        'static': re.compile(
            r'^\s*(?:pub(?:\s*\([^)]+\))?\s+)?static\s+(?:mut\s+)?([A-Z][A-Z0-9_]*)\s*:\s*([^=]+)\s*=',
            re.MULTILINE
        ),
        'type_alias': re.compile(
            r'^\s*(?:pub(?:\s*\([^)]+\))?\s+)?type\s+(\w+)(?:<[^>]+>)?\s*=',
            re.MULTILINE
        ),
        'macro': re.compile(
            r'^\s*(?:#\[[^\]]+\]\s*)*(?:pub(?:\s*\([^)]+\))?\s+)?macro_rules!\s+(\w+)\s*\{',
            re.MULTILINE
        ),
    }

    @classmethod
    def extract_typescript(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 TypeScript/JavaScript"""
        result = ExtractionResult(
            file_path=file_path,
            language='typescript',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='typescript',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        lines = content.split('\n')

        # Extract imports
        for match in cls.TS_PATTERNS['import'].finditer(content):
            import_path = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            # 建立 edge 到被導入的模組
            target_id = f"module.{import_path}"
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # Extract functions (export function)
        for match in cls.TS_PATTERNS['export_function'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            # 找到函式結束行（簡化：找下一個同層級的定義）
            line_end = cls._find_block_end(lines, line_num - 1)

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract arrow functions (export const xxx = () =>)
        for match in cls.TS_PATTERNS['export_const_arrow'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract classes
        for match in cls.TS_PATTERNS['class'].finditer(content):
            name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            class_node = CodeNode(
                id=make_node_id('class', file_path, name),
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility='public',
                language='typescript'
            )
            result.nodes.append(class_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=class_node.id,
                kind='defines'
            ))

            # 繼承關係
            if extends:
                result.edges.append(CodeEdge(
                    from_id=class_node.id,
                    to_id=f"class.{extends}",
                    kind='extends',
                    line_number=line_num,
                    confidence=0.8  # 不確定目標檔案
                ))

            # 實作關係
            if implements:
                for iface in implements.split(','):
                    iface = iface.strip()
                    if iface:
                        result.edges.append(CodeEdge(
                            from_id=class_node.id,
                            to_id=f"interface.{iface}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # Extract interfaces
        for match in cls.TS_PATTERNS['interface'].finditer(content):
            name = match.group(1)
            extends = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_block_end(lines, line_num - 1)

            iface_node = CodeNode(
                id=make_node_id('interface', file_path, name),
                kind='interface',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='typescript'
            )
            result.nodes.append(iface_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=iface_node.id,
                kind='defines'
            ))

        # Extract type aliases
        for match in cls.TS_PATTERNS['type'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            type_node = CodeNode(
                id=make_node_id('type', file_path, name),
                kind='type',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='typescript'
            )
            result.nodes.append(type_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=type_node.id,
                kind='defines'
            ))

        return result

    @classmethod
    def extract_python(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 Python"""
        result = ExtractionResult(
            file_path=file_path,
            language='python',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='python',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        lines = content.split('\n')

        # Extract imports
        for match in cls.PY_PATTERNS['import'].finditer(content):
            from_module = match.group(1)
            imports = match.group(2)
            line_num = content[:match.start()].count('\n') + 1

            if from_module:
                target_id = f"module.{from_module}"
            else:
                # import xxx, yyy
                target_id = f"module.{imports.split(',')[0].strip().split()[0]}"

            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # Extract functions
        for match in cls.PY_PATTERNS['function'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_python_block_end(lines, line_num - 1)

            # 判斷 visibility
            visibility = 'private' if name.startswith('_') else 'public'

            func_node = CodeNode(
                id=make_node_id('function', file_path, name),
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='python'
            )
            result.nodes.append(func_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=func_node.id,
                kind='defines'
            ))

        # Extract classes
        for match in cls.PY_PATTERNS['class'].finditer(content):
            name = match.group(1)
            bases = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            line_end = cls._find_python_block_end(lines, line_num - 1)

            class_node = CodeNode(
                id=make_node_id('class', file_path, name),
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='python'
            )
            result.nodes.append(class_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=class_node.id,
                kind='defines'
            ))

            # 繼承關係
            if bases:
                for base in bases.split(','):
                    base = base.strip()
                    if base and base != 'object':
                        result.edges.append(CodeEdge(
                            from_id=class_node.id,
                            to_id=f"class.{base}",
                            kind='extends',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # Extract constants (UPPER_CASE)
        for match in cls.PY_PATTERNS['const'].finditer(content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1

            const_node = CodeNode(
                id=make_node_id('constant', file_path, name),
                kind='constant',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='python'
            )
            result.nodes.append(const_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=const_node.id,
                kind='defines'
            ))

        return result

    @staticmethod
    def _find_block_end(lines: List[str], start_line: int) -> int:
        """找到 JS/TS block 結束行（簡化版：計算括號）"""
        brace_count = 0
        started = False

        for i, line in enumerate(lines[start_line:], start=start_line):
            for char in line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed

        return len(lines)

    @staticmethod
    def _find_python_block_end(lines: List[str], start_line: int) -> int:
        """找到 Python block 結束行（基於縮排）"""
        if start_line >= len(lines):
            return start_line + 1

        # 取得起始縮排
        start_indent = len(lines[start_line]) - len(lines[start_line].lstrip())

        for i, line in enumerate(lines[start_line + 1:], start=start_line + 1):
            stripped = line.strip()
            if not stripped:  # 空行
                continue
            if stripped.startswith('#'):  # 註解
                continue

            current_indent = len(line) - len(line.lstrip())
            if current_indent <= start_indent:
                return i

        return len(lines)

    @staticmethod
    def _remove_java_comments(content: str) -> str:
        """
        移除 Java 註解以避免 regex 誤判

        處理：
        - 單行註解: // ...
        - 多行註解: /* ... */
        - Javadoc 註解: /** ... */
        """
        # 移除多行註解（包含 javadoc）
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        # 移除單行註解
        content = re.sub(r'//[^\n]*', '', content)
        return content

    @staticmethod
    def _find_java_block_end(lines: List[str], start_line: int) -> int:
        """
        找到 Java block 結束行（括號配對，考慮字串/字元字面值）

        處理：
        - 巢狀括號
        - 字串字面值中的括號
        - 字元字面值中的括號
        """
        brace_count = 0
        started = False
        in_string = False
        in_char = False
        escape_next = False

        for i, line in enumerate(lines[start_line:], start=start_line):
            for char in line:
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not in_char:
                    in_string = not in_string
                    continue

                if char == "'" and not in_string:
                    in_char = not in_char
                    continue

                if in_string or in_char:
                    continue

                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed

        return len(lines)

    @classmethod
    def extract_java(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 Java 程式碼結構"""
        result = ExtractionResult(
            file_path=file_path,
            language='java',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # 前處理：移除註解
        cleaned_content = cls._remove_java_comments(content)
        lines = cleaned_content.split('\n')

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='java',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        # 追蹤 package 名稱用於 qualified ID
        package_name = ''

        # 提取 package
        for match in cls.JAVA_PATTERNS['package'].finditer(cleaned_content):
            package_name = match.group(1)
            break  # 每個檔案只有一個 package

        # 提取 imports
        for match in cls.JAVA_PATTERNS['import'].finditer(cleaned_content):
            import_path = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 處理萬用字元 import
            if import_path.endswith('.*'):
                target_id = f"package.{import_path[:-2]}"
            else:
                target_id = f"class.{import_path}"

            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # 追蹤 class 堆疊處理 inner class
        class_stack = []  # [(class_name, class_id, line_end)]

        # 提取 classes
        for match in cls.JAVA_PATTERNS['class'].finditer(cleaned_content):
            name = match.group(1)
            extends = match.group(2)
            implements = match.group(3)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            # 判斷 visibility
            match_text = match.group(0)
            if 'public' in match_text:
                visibility = 'public'
            elif 'protected' in match_text:
                visibility = 'protected'
            elif 'private' in match_text:
                visibility = 'private'
            else:
                visibility = 'package'  # Java 預設

            # 生成 qualified ID
            qualified_name = f"{package_name}.{name}" if package_name else name
            class_id = make_node_id('class', file_path, qualified_name)

            class_node = CodeNode(
                id=class_id,
                kind='class',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='java'
            )
            result.nodes.append(class_node)

            # 父子關係
            if class_stack and line_num < class_stack[-1][2]:
                # Inner class - 包含於父 class
                parent_id = class_stack[-1][1]
                result.edges.append(CodeEdge(
                    from_id=parent_id,
                    to_id=class_id,
                    kind='contains',
                    line_number=line_num
                ))
            else:
                # 頂層 class - 由 file 定義
                result.edges.append(CodeEdge(
                    from_id=file_node.id,
                    to_id=class_id,
                    kind='defines'
                ))

            # 繼承
            if extends:
                extends_name = extends.strip().split('<')[0].strip()
                result.edges.append(CodeEdge(
                    from_id=class_id,
                    to_id=f"class.{extends_name}",
                    kind='extends',
                    line_number=line_num,
                    confidence=0.8
                ))

            # 實作
            if implements:
                for iface in implements.split(','):
                    iface_name = iface.strip().split('<')[0].strip()
                    if iface_name:
                        result.edges.append(CodeEdge(
                            from_id=class_id,
                            to_id=f"interface.{iface_name}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

            # 清理過期的 class stack
            while class_stack and line_num >= class_stack[-1][2]:
                class_stack.pop()

            class_stack.append((name, class_id, line_end))

        # 提取 interfaces
        for match in cls.JAVA_PATTERNS['interface'].finditer(cleaned_content):
            name = match.group(1)
            extends = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            iface_id = make_node_id('interface', file_path, qualified_name)

            iface_node = CodeNode(
                id=iface_id,
                kind='interface',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(iface_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=iface_id,
                kind='defines'
            ))

            # Interface 繼承
            if extends:
                for parent in extends.split(','):
                    parent_name = parent.strip().split('<')[0].strip()
                    if parent_name:
                        result.edges.append(CodeEdge(
                            from_id=iface_id,
                            to_id=f"interface.{parent_name}",
                            kind='extends',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # 提取 enums
        for match in cls.JAVA_PATTERNS['enum'].finditer(cleaned_content):
            name = match.group(1)
            implements = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            enum_id = make_node_id('enum', file_path, qualified_name)

            enum_node = CodeNode(
                id=enum_id,
                kind='enum',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(enum_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=enum_id,
                kind='defines'
            ))

            # Enum 實作
            if implements:
                for iface in implements.split(','):
                    iface_name = iface.strip().split('<')[0].strip()
                    if iface_name:
                        result.edges.append(CodeEdge(
                            from_id=enum_id,
                            to_id=f"interface.{iface_name}",
                            kind='implements',
                            line_number=line_num,
                            confidence=0.8
                        ))

        # 提取 annotations (@interface)
        for match in cls.JAVA_PATTERNS['annotation'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_java_block_end(lines, line_num - 1)

            qualified_name = f"{package_name}.{name}" if package_name else name
            annotation_id = make_node_id('annotation', file_path, qualified_name)

            annotation_node = CodeNode(
                id=annotation_id,
                kind='annotation',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                language='java'
            )
            result.nodes.append(annotation_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=annotation_id,
                kind='defines'
            ))

        # 收集所有 class/interface/enum 名稱和範圍用於過濾建構子和定位 containing class
        type_names = set()
        type_ranges = []  # [(name, id, line_start, line_end)]
        for node in result.nodes:
            if node.kind in ('class', 'interface', 'enum', 'annotation'):
                type_names.add(node.name)
                type_ranges.append((node.name, node.id, node.line_start, node.line_end))

        # 按 line_start 排序，用於找到最內層的 containing class
        type_ranges.sort(key=lambda x: x[2])

        # 提取 methods（排除建構子）
        for match in cls.JAVA_PATTERNS['method'].finditer(cleaned_content):
            return_type = match.group(1).strip()
            name = match.group(2)
            params = match.group(3)
            throws = match.group(4)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 跳過建構子（方法名等於 class 名稱且沒有 return type）
            # 建構子的特徵：名稱等於其所在 class，且 return type 也等於該 class
            # 例如：public User(String name) 會被 regex 匹配為 return_type=User, name=User
            if name in type_names and return_type == name:
                continue

            # 跳過看起來不像方法的匹配（例如 throw new X()）
            if return_type in ('throw', 'return', 'new', 'if', 'for', 'while', 'switch'):
                continue

            line_end = cls._find_java_block_end(lines, line_num - 1)

            # 判斷 visibility
            match_text = match.group(0)
            if 'public' in match_text:
                visibility = 'public'
            elif 'protected' in match_text:
                visibility = 'protected'
            elif 'private' in match_text:
                visibility = 'private'
            else:
                visibility = 'package'

            method_id = make_node_id('function', file_path, name)
            signature = f"{return_type} {name}({params})"
            if throws:
                signature += f" throws {throws.strip()}"

            method_node = CodeNode(
                id=method_id,
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                signature=signature,
                visibility=visibility,
                language='java'
            )
            result.nodes.append(method_node)

            # 找到包含此 method 的最內層 class
            containing_class = None
            for type_name, type_id, type_start, type_end in reversed(type_ranges):
                if type_start < line_num < type_end:
                    containing_class = type_id
                    break

            if containing_class:
                result.edges.append(CodeEdge(
                    from_id=containing_class,
                    to_id=method_id,
                    kind='contains',
                    line_number=line_num
                ))
            else:
                result.edges.append(CodeEdge(
                    from_id=file_node.id,
                    to_id=method_id,
                    kind='defines'
                ))

        # 提取依賴注入欄位（@Autowired, @Inject, @MockBean 等）
        for match in cls.JAVA_PATTERNS['injected_field'].finditer(cleaned_content):
            annotation = match.group(1)  # @Autowired 等
            field_type = match.group(2).strip()  # 欄位類型
            field_name = match.group(3)  # 欄位名稱
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 找到包含此欄位的 class
            containing_class = None
            for type_name, type_id, type_start, type_end in reversed(type_ranges):
                if type_start < line_num < type_end:
                    containing_class = type_id
                    break

            if containing_class:
                # 移除泛型部分取得基本類型
                base_type = field_type.split('<')[0].strip()

                # 建立 injects edge（隱式依賴）
                result.edges.append(CodeEdge(
                    from_id=containing_class,
                    to_id=f"class.{base_type}",
                    kind='injects',
                    line_number=line_num,
                    confidence=0.9
                ))

        # 提取 constants (static final UPPER_CASE)
        for match in cls.JAVA_PATTERNS['constant'].finditer(cleaned_content):
            type_name = match.group(1)
            name = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1

            const_id = make_node_id('constant', file_path, name)

            const_node = CodeNode(
                id=const_id,
                kind='constant',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='java'
            )
            result.nodes.append(const_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=const_id,
                kind='defines'
            ))

        return result

    @staticmethod
    def _remove_rust_comments(content: str) -> str:
        """
        移除 Rust 註解以避免 regex 誤判

        處理：
        - 單行註解: // ...
        - 文檔註解: /// ... 和 //! ...
        - 多行註解: /* ... */ (支援巢狀)
        """
        # 移除多行註解 (Rust 支援巢狀註解，但簡化處理)
        # 首先處理非巢狀情況
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        # 移除單行/文檔註解
        content = re.sub(r'//[^\n]*', '', content)
        return content

    @staticmethod
    def _find_rust_block_end(lines: List[str], start_line: int) -> int:
        """
        找到 Rust block 結束行（括號配對，考慮字串/字元字面值和 raw strings）

        處理：
        - 巢狀括號
        - 字串字面值 "..." 和 raw strings r#"..."#
        - 字元字面值 '.'
        - 生命週期 'a（不是字元）
        """
        brace_count = 0
        started = False
        in_string = False
        in_raw_string = False
        raw_string_hashes = 0
        in_char = False
        escape_next = False

        for i, line in enumerate(lines[start_line:], start=start_line):
            j = 0
            while j < len(line):
                char = line[j]

                if escape_next:
                    escape_next = False
                    j += 1
                    continue

                # 處理 raw string r#"..."#
                if not in_string and not in_char and not in_raw_string:
                    if char == 'r' and j + 1 < len(line):
                        # 計算 # 數量
                        hash_count = 0
                        k = j + 1
                        while k < len(line) and line[k] == '#':
                            hash_count += 1
                            k += 1
                        if k < len(line) and line[k] == '"':
                            in_raw_string = True
                            raw_string_hashes = hash_count
                            j = k + 1
                            continue

                if in_raw_string:
                    # 尋找結束: "###
                    if char == '"':
                        # 檢查後面是否有足夠的 #
                        hash_count = 0
                        k = j + 1
                        while k < len(line) and line[k] == '#' and hash_count < raw_string_hashes:
                            hash_count += 1
                            k += 1
                        if hash_count == raw_string_hashes:
                            in_raw_string = False
                            j = k
                            continue
                    j += 1
                    continue

                if char == '\\':
                    escape_next = True
                    j += 1
                    continue

                if char == '"' and not in_char:
                    in_string = not in_string
                    j += 1
                    continue

                # 處理字元字面值和生命週期
                if char == "'" and not in_string:
                    # 檢查是否是生命週期 'a 或字元 'x'
                    if j + 2 < len(line) and line[j + 2] == "'":
                        # 這是字元字面值 'x'
                        j += 3
                        continue
                    elif j + 3 < len(line) and line[j + 1] == '\\' and line[j + 3] == "'":
                        # 這是轉義字元 '\n'
                        j += 4
                        continue
                    else:
                        # 這是生命週期 'a，跳過
                        j += 1
                        continue

                if in_string:
                    j += 1
                    continue

                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed

                j += 1

        return len(lines)

    @staticmethod
    def _parse_rust_visibility(match_text: str) -> str:
        """解析 Rust visibility"""
        if 'pub(crate)' in match_text:
            return 'pub(crate)'
        elif 'pub(super)' in match_text:
            return 'pub(super)'
        elif 'pub(in' in match_text:
            return 'pub(in)'
        elif 'pub' in match_text:
            return 'public'
        return 'private'

    @classmethod
    def extract_rust(cls, content: str, file_path: str) -> ExtractionResult:
        """提取 Rust 程式碼結構"""
        result = ExtractionResult(
            file_path=file_path,
            language='rust',
            file_hash=hashlib.md5(content.encode()).hexdigest()
        )

        # 前處理：移除註解
        cleaned_content = cls._remove_rust_comments(content)
        lines = cleaned_content.split('\n')

        # File node
        file_node = CodeNode(
            id=make_node_id('file', file_path),
            kind='file',
            name=os.path.basename(file_path),
            file_path=file_path,
            language='rust',
            hash=result.file_hash
        )
        result.nodes.append(file_node)

        # 追蹤模組用於 qualified ID（從檔案路徑推斷）
        # 例如: src/auth/login.rs -> auth::login
        module_path = ''
        path_parts = Path(file_path).parts
        if 'src' in path_parts:
            src_idx = path_parts.index('src')
            mod_parts = list(path_parts[src_idx + 1:])
            if mod_parts:
                # 移除 .rs 副檔名
                mod_parts[-1] = mod_parts[-1].replace('.rs', '')
                # lib.rs 和 mod.rs 代表父模組
                if mod_parts[-1] in ('lib', 'mod', 'main'):
                    mod_parts = mod_parts[:-1]
                module_path = '::'.join(mod_parts)

        # 提取 use statements
        for match in cls.RUST_PATTERNS['use'].finditer(cleaned_content):
            use_path = match.group(1).strip()
            line_num = cleaned_content[:match.start()].count('\n') + 1

            # 處理各種 use 形式
            # use std::collections::HashMap;
            # use std::collections::{HashMap, HashSet};
            # use std::io::*;
            # use crate::module::Type;

            # 簡化處理：提取主要路徑
            base_path = use_path.split('::')[0].strip()
            if '{' in use_path:
                # 多重導入，取基礎路徑
                base_path = use_path.split('{')[0].rstrip(':').strip()
                target_id = f"module.{base_path}"
            elif use_path.endswith('::*'):
                target_id = f"module.{use_path[:-3]}"
            else:
                target_id = f"module.{use_path}"

            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=target_id,
                kind='imports',
                line_number=line_num
            ))

        # 提取 mod declarations
        for match in cls.RUST_PATTERNS['mod'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            # 判斷是 mod 宣告還是 mod 定義
            is_inline = match_text.strip().endswith('{')
            if is_inline:
                line_end = cls._find_rust_block_end(lines, line_num - 1)
            else:
                line_end = line_num

            qualified_name = f"{module_path}::{name}" if module_path else name
            mod_id = make_node_id('module', file_path, qualified_name)

            mod_node = CodeNode(
                id=mod_id,
                kind='module',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(mod_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=mod_id,
                kind='defines'
            ))

        # 追蹤類型用於 impl 匹配
        type_info = {}  # name -> (id, line_start, line_end)

        # 提取 structs
        for match in cls.RUST_PATTERNS['struct'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            # 判斷是 tuple struct (;結尾) 還是 regular struct ({結尾)
            if match_text.strip().endswith(';'):
                line_end = line_num
            else:
                line_end = cls._find_rust_block_end(lines, line_num - 1)

            qualified_name = f"{module_path}::{name}" if module_path else name
            struct_id = make_node_id('struct', file_path, qualified_name)

            struct_node = CodeNode(
                id=struct_id,
                kind='struct',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(struct_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=struct_id,
                kind='defines'
            ))

            type_info[name] = (struct_id, line_num, line_end)

        # 提取 enums
        for match in cls.RUST_PATTERNS['enum'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)
            line_end = cls._find_rust_block_end(lines, line_num - 1)

            qualified_name = f"{module_path}::{name}" if module_path else name
            enum_id = make_node_id('enum', file_path, qualified_name)

            enum_node = CodeNode(
                id=enum_id,
                kind='enum',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(enum_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=enum_id,
                kind='defines'
            ))

            type_info[name] = (enum_id, line_num, line_end)

        # 提取 traits
        for match in cls.RUST_PATTERNS['trait'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)
            line_end = cls._find_rust_block_end(lines, line_num - 1)

            qualified_name = f"{module_path}::{name}" if module_path else name
            trait_id = make_node_id('trait', file_path, qualified_name)

            trait_node = CodeNode(
                id=trait_id,
                kind='trait',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(trait_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=trait_id,
                kind='defines'
            ))

            type_info[name] = (trait_id, line_num, line_end)

        # 提取 impl blocks
        impl_ranges = []  # [(impl_for_type, line_start, line_end)]
        for match in cls.RUST_PATTERNS['impl'].finditer(cleaned_content):
            trait_name = match.group(1)  # 可能是 None
            type_name = match.group(2)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            line_end = cls._find_rust_block_end(lines, line_num - 1)

            impl_ranges.append((type_name, trait_name, line_num, line_end))

            # 如果是 impl Trait for Type，建立 implements edge
            if trait_name and type_name in type_info:
                type_id = type_info[type_name][0]
                result.edges.append(CodeEdge(
                    from_id=type_id,
                    to_id=f"trait.{trait_name}",
                    kind='implements',
                    line_number=line_num,
                    confidence=0.8
                ))

        # 提取 functions
        for match in cls.RUST_PATTERNS['fn'].finditer(cleaned_content):
            name = match.group(1)
            params = match.group(2)
            return_type = match.group(3)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            # 判斷是函式定義還是宣告
            if match_text.strip().endswith(';'):
                line_end = line_num
            else:
                line_end = cls._find_rust_block_end(lines, line_num - 1)

            func_id = make_node_id('function', file_path, name)

            # 建立簽名
            signature = f"fn {name}({params.strip()})"
            if return_type:
                signature += f" -> {return_type.strip()}"

            func_node = CodeNode(
                id=func_id,
                kind='function',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                signature=signature,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(func_node)

            # 找到包含此函式的 impl block 或 trait
            containing_type = None

            # 首先檢查 impl blocks
            for impl_type, impl_trait, impl_start, impl_end in impl_ranges:
                if impl_start < line_num < impl_end:
                    if impl_type in type_info:
                        containing_type = type_info[impl_type][0]
                    break

            # 如果不在 impl block 中，檢查是否在 trait 定義中
            if not containing_type:
                for type_name, (type_id, type_start, type_end) in type_info.items():
                    if type_start < line_num < type_end and 'trait.' in type_id:
                        containing_type = type_id
                        break

            if containing_type:
                result.edges.append(CodeEdge(
                    from_id=containing_type,
                    to_id=func_id,
                    kind='contains',
                    line_number=line_num
                ))
            else:
                result.edges.append(CodeEdge(
                    from_id=file_node.id,
                    to_id=func_id,
                    kind='defines'
                ))

        # 提取 constants
        for match in cls.RUST_PATTERNS['const'].finditer(cleaned_content):
            name = match.group(1)
            const_type = match.group(2).strip()
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            const_id = make_node_id('constant', file_path, name)

            const_node = CodeNode(
                id=const_id,
                kind='constant',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                signature=f"const {name}: {const_type}",
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(const_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=const_id,
                kind='defines'
            ))

        # 提取 static variables
        for match in cls.RUST_PATTERNS['static'].finditer(cleaned_content):
            name = match.group(1)
            static_type = match.group(2).strip()
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            static_id = make_node_id('static', file_path, name)

            static_node = CodeNode(
                id=static_id,
                kind='static',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                signature=f"static {name}: {static_type}",
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(static_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=static_id,
                kind='defines'
            ))

        # 提取 type aliases
        for match in cls.RUST_PATTERNS['type_alias'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)

            type_id = make_node_id('type', file_path, name)

            type_node = CodeNode(
                id=type_id,
                kind='type',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(type_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=type_id,
                kind='defines'
            ))

        # 提取 macros
        for match in cls.RUST_PATTERNS['macro'].finditer(cleaned_content):
            name = match.group(1)
            line_num = cleaned_content[:match.start()].count('\n') + 1
            match_text = match.group(0)

            visibility = cls._parse_rust_visibility(match_text)
            line_end = cls._find_rust_block_end(lines, line_num - 1)

            macro_id = make_node_id('macro', file_path, name)

            macro_node = CodeNode(
                id=macro_id,
                kind='macro',
                name=name,
                file_path=file_path,
                line_start=line_num,
                line_end=line_end,
                visibility=visibility,
                language='rust'
            )
            result.nodes.append(macro_node)
            result.edges.append(CodeEdge(
                from_id=file_node.id,
                to_id=macro_id,
                kind='defines'
            ))

        return result


# =============================================================================
# Main API
# =============================================================================

def extract_from_file(file_path: str, project_root: Optional[str] = None) -> ExtractionResult:
    """
    從單一檔案提取程式碼結構

    Args:
        file_path: 檔案路徑（absolute）
        project_root: 專案根目錄（用於正規化為 relative path）

    Returns:
        ExtractionResult 包含 nodes 和 edges
    """
    if not os.path.exists(file_path):
        return ExtractionResult(
            file_path=file_path,
            errors=[f"File not found: {file_path}"]
        )

    language = detect_language(file_path)
    if not language:
        return ExtractionResult(
            file_path=file_path,
            errors=[f"Unsupported file type: {file_path}"]
        )

    try:
        from servers.utils import read_text_file
        content = read_text_file(file_path)
    except (FileNotFoundError, UnicodeDecodeError) as e:
        return ExtractionResult(
            file_path=file_path,
            errors=[f"Failed to read file: {str(e)}"]
        )

    logical_path = normalize_file_path(file_path, project_root)

    # Try backend registry first (supports Tree-sitter + future backends)
    from tools.code_graph_extractor.backends import get_backend
    backend = get_backend(language)
    if backend is not None:
        return backend.extract_language(content, logical_path, language, abs_file_path=file_path)

    # Direct fallback for unregistered languages (legacy path)
    if language in ('typescript', 'javascript'):
        return RegexExtractor.extract_typescript(content, logical_path)
    elif language == 'python':
        return RegexExtractor.extract_python(content, logical_path)
    elif language == 'java':
        return RegexExtractor.extract_java(content, logical_path)
    elif language == 'rust':
        return RegexExtractor.extract_rust(content, logical_path)
    else:
        return ExtractionResult(
            file_path=file_path,
            language=language,
            errors=[f"Extractor not implemented for: {language}"]
        )


def extract_from_directory(
    directory: str,
    incremental: bool = True,
    project: str = None,
    file_hashes: Dict[str, str] = None
) -> Dict:
    """
    從目錄提取程式碼結構

    Args:
        directory: 目錄路徑
        incremental: 是否增量更新（跳過未變更檔案）
        project: 專案名稱
        file_hashes: 已知的檔案 hash（用於增量比對）

    Returns:
        {
            'nodes': List[Dict],
            'edges': List[Dict],
            'files_processed': int,
            'files_skipped': int,
            'errors': List[str],
            'file_hashes': Dict[str, str]  # 新的 hash 對照表
        }
    """
    if not os.path.isdir(directory):
        return {
            'nodes': [],
            'edges': [],
            'files_processed': 0,
            'files_skipped': 0,
            'errors': [f"Directory not found: {directory}"],
            'file_hashes': {}
        }

    file_hashes = file_hashes or {}
    all_nodes = []
    all_edges = []
    new_hashes = {}
    errors = []
    files_processed = 0
    files_skipped = 0

    # 遍歷目錄
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        files.sort()
        # 跳過忽略的目錄
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for filename in files:
            abs_path = os.path.join(root, filename)
            if detect_language(abs_path) is None:
                continue

            rel_path = normalize_file_path(abs_path, directory)

            # 增量檢查
            if incremental:
                current_hash = compute_file_hash(abs_path)
                if rel_path in file_hashes and file_hashes[rel_path] == current_hash:
                    files_skipped += 1
                    new_hashes[rel_path] = current_hash
                    continue

            # 提取（傳入 project_root 確保 node ID 使用 relative path）
            result = extract_from_file(abs_path, project_root=directory)

            if result.errors:
                errors.extend(result.errors)
            else:
                all_nodes.extend([n.to_dict() for n in result.nodes])
                all_edges.extend([e.to_dict() for e in result.edges])
                new_hashes[rel_path] = result.file_hash
                files_processed += 1

    return {
        'nodes': all_nodes,
        'edges': all_edges,
        'files_processed': files_processed,
        'files_skipped': files_skipped,
        'errors': errors,
        'file_hashes': new_hashes
    }
