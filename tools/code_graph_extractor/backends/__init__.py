"""
Extractor Backend Registry

提供 parser backend 抽象層，支援多種解析策略：
- RegexBackend: 基於正則表達式（預設 fallback）
- TreeSitterBackend: 基於 Tree-sitter AST（Phase 2 實現）

使用方式：
    from tools.code_graph_extractor.backends import get_backend

    backend = get_backend('typescript')
    result = backend.extract(content, file_path)
"""

from typing import Protocol, Set, Optional, List, Tuple, runtime_checkable
import sys
import os

# Import data models from parent package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.code_graph_extractor.extractor import ExtractionResult


@runtime_checkable
class ExtractorBackend(Protocol):
    """Parser backend protocol. All backends must implement this interface."""

    @property
    def name(self) -> str:
        """Backend identifier, e.g. 'regex', 'tree_sitter'."""
        ...

    @property
    def capabilities(self) -> Set[str]:
        """
        Supported extraction capabilities:
        - 'functions': function/method definitions
        - 'classes': class/struct/interface definitions
        - 'imports': import/use statements
        - 'methods': class method extraction
        - 'calls': call graph extraction
        - 'cross_file_resolution': cross-file type resolution
        """
        ...

    def can_handle(self, language: str) -> bool:
        """Return True if this backend supports the given language."""
        ...

    def extract(self, content: str, file_path: str) -> ExtractionResult:
        """
        Extract code structure from file content.

        Args:
            content: File content as string
            file_path: Project-relative POSIX path (for node ID generation)

        Returns:
            ExtractionResult with nodes and edges
        """
        ...


# =============================================================================
# Backend Registry
# =============================================================================

# List of (priority, backend) tuples — higher priority = preferred
_BACKENDS: List[Tuple[int, ExtractorBackend]] = []


def register_backend(backend: ExtractorBackend, priority: int = 0):
    """
    Register a parser backend.

    Higher priority backends are checked first.
    Tree-sitter backends should register with priority > 0,
    regex backends with priority 0.
    """
    _BACKENDS.append((priority, backend))
    _BACKENDS.sort(key=lambda x: x[0], reverse=True)


def get_backend(language: str) -> Optional[ExtractorBackend]:
    """
    Get the best available backend for a language.

    Returns the highest-priority backend that can handle the language,
    or None if no backend supports it.
    """
    for _priority, backend in _BACKENDS:
        if backend.can_handle(language):
            return backend
    return None


def list_backends() -> List[dict]:
    """List all registered backends with their capabilities."""
    return [
        {
            'name': backend.name,
            'priority': priority,
            'capabilities': list(backend.capabilities),
        }
        for priority, backend in _BACKENDS
    ]


# =============================================================================
# Language Config
# =============================================================================

LANGUAGE_CONFIGS = {
    'typescript': {
        'extensions': ['.ts', '.tsx'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': 'regex',
    },
    'javascript': {
        'extensions': ['.js', '.jsx'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': 'regex',
    },
    'python': {
        'extensions': ['.py'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': 'regex',
    },
    'java': {
        'extensions': ['.java'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': 'regex',
    },
    'rust': {
        'extensions': ['.rs'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': 'regex',
    },
    'go': {
        'extensions': ['.go'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': None,  # no regex fallback for Go
    },
    'c': {
        'extensions': ['.c', '.h'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': None,  # tree-sitter only
    },
    'cpp': {
        'extensions': ['.cpp', '.cc', '.cxx', '.hpp', '.hh', '.hxx'],
        'preferred_backend': 'tree_sitter',
        'fallback_backend': None,  # tree-sitter only
    },
}


# =============================================================================
# Auto-register default backends
# =============================================================================

def _auto_register():
    """Register available backends at import time."""
    # Always register regex backend as fallback (priority 0)
    from tools.code_graph_extractor.backends.regex_backend import RegexBackend
    register_backend(RegexBackend(), priority=0)

    # Try to register Tree-sitter backend (priority 10) if available
    try:
        from tools.code_graph_extractor.backends.tree_sitter_backend import TreeSitterBackend
        register_backend(TreeSitterBackend(), priority=10)
    except ImportError:
        pass  # tree-sitter not installed — regex fallback only


_auto_register()
