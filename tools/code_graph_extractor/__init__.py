"""
Code Graph Extractor

多語言程式碼結構圖提取器。支援 Tree-sitter AST（可選）和 Regex fallback。
不依賴 LLM，產出��定性結果。

支援語言：TypeScript/JavaScript, Python, Java, Rust, Go (Tree-sitter only)

使用方式：
    from tools.code_graph_extractor import extract_from_file, extract_from_directory

    # 單一檔案
    result = extract_from_file('src/api/auth.ts')

    # 整個目錄（增量）
    result = extract_from_directory('src/', incremental=True)

    # 查詢 backend
    from tools.code_graph_extractor.backends import get_backend, list_backends
    backend = get_backend('typescript')
"""

from .extractor import (
    extract_from_file,
    extract_from_directory,
    get_supported_languages,
    normalize_file_path,
    SUPPORTED_EXTENSIONS,
)

__all__ = [
    'extract_from_file',
    'extract_from_directory',
    'get_supported_languages',
    'normalize_file_path',
    'SUPPORTED_EXTENSIONS',
]
