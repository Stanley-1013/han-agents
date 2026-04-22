"""
Regex-based Extractor Backend

Wraps the existing RegexExtractor as an ExtractorBackend.
This is the default fallback when Tree-sitter is unavailable.
"""

import warnings
from typing import Set
from tools.code_graph_extractor.extractor import RegexExtractor, ExtractionResult


class RegexBackend:
    """Regex-based extraction backend (fallback)."""

    _SUPPORTED_LANGUAGES = {
        'typescript', 'javascript', 'python', 'java', 'rust',
    }

    _EXTRACTORS = {
        'typescript': RegexExtractor.extract_typescript,
        'javascript': RegexExtractor.extract_typescript,  # shared with TS
        'python': RegexExtractor.extract_python,
        'java': RegexExtractor.extract_java,
        'rust': RegexExtractor.extract_rust,
    }

    @property
    def name(self) -> str:
        return 'regex'

    @property
    def capabilities(self) -> Set[str]:
        return {'functions', 'classes', 'imports'}

    def can_handle(self, language: str) -> bool:
        return language in self._SUPPORTED_LANGUAGES

    def extract(self, content: str, file_path: str) -> ExtractionResult:
        lang = file_path_to_language(file_path)

        # Lazy import to avoid circular import (backends/__init__.py imports this module)
        from tools.code_graph_extractor.backends import is_regex_deprecated
        if is_regex_deprecated(lang):
            ts_pkg = lang.replace('typescript', 'typescript tree-sitter-javascript')
            warnings.warn(
                f"RegexBackend is deprecated for '{lang}'. "
                f"Install tree-sitter for better extraction: "
                f"pip install tree-sitter tree-sitter-{ts_pkg}",
                DeprecationWarning,
                stacklevel=2,
            )

        extractor_fn = self._EXTRACTORS.get(lang)
        if extractor_fn is None:
            # Try language detection from the dispatch table directly
            for supported_lang in self._SUPPORTED_LANGUAGES:
                if supported_lang in file_path.lower():
                    extractor_fn = self._EXTRACTORS[supported_lang]
                    break
        if extractor_fn is None:
            return ExtractionResult(
                file_path=file_path,
                errors=[f"RegexBackend: no extractor for file: {file_path}"]
            )
        return extractor_fn(content, file_path)

    def extract_language(self, content: str, file_path: str, language: str, abs_file_path: str = None) -> ExtractionResult:
        """Extract with explicit language (preferred over file-path guessing)."""
        extractor_fn = self._EXTRACTORS.get(language)
        if extractor_fn is None:
            return ExtractionResult(
                file_path=file_path,
                language=language,
                errors=[f"RegexBackend: unsupported language: {language}"]
            )
        return extractor_fn(content, file_path)


def file_path_to_language(file_path: str) -> str:
    """Infer language from file extension in path."""
    from tools.code_graph_extractor.extractor import detect_language
    return detect_language(file_path) or ''
