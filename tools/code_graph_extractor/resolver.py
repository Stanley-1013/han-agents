"""Cross-file symbol resolver for code graph edges.

After all files in a project are extracted, run resolve_edges() to replace
symbolic to_id references (e.g. 'class.Base', 'symbol.hello') with fully
qualified node IDs (e.g. 'class.src/base.py:Base').
"""
from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from tools.code_graph_extractor.extractor import CodeEdge, CodeNode


@dataclass
class ResolveStats:
    total_edges: int
    resolved: int
    unresolved: int
    ambiguous: int


class SymbolTable:
    """In-memory index of CodeNodes for O(1) symbol lookup."""

    def __init__(self, nodes: List[CodeNode]) -> None:
        # (kind, simple_name) -> list of CodeNode
        self._by_kind_name: Dict[Tuple[str, str], List[CodeNode]] = defaultdict(list)
        # file nodes indexed by path segments for module lookup
        self._file_nodes: List[CodeNode] = []

        for node in nodes:
            simple_name = node.name.split(".")[-1] if node.name else ""
            self._by_kind_name[(node.kind, simple_name)].append(node)

            # Also index by the full qualified name so "MyClass.hello" can be
            # found with key (kind, "MyClass.hello")
            if node.name and "." in node.name:
                self._by_kind_name[(node.kind, node.name)].append(node)

            if node.kind == "file":
                self._file_nodes.append(node)

    def lookup(self, kind: str, name: str) -> List[CodeNode]:
        """Return all nodes matching kind + name. May return multiple (ambiguous)."""
        return list(self._by_kind_name.get((kind, name), []))

    def lookup_module(self, module_name: str) -> Optional[CodeNode]:
        """Resolve a module/import reference to a file node if possible.

        E.g. 'src/utils' would match 'file.src/utils.py'.
        External packages (no '/' and no matching file) return None.
        """
        # Normalise: strip leading ./ and trailing extension for comparison
        normalised = module_name.lstrip("./")

        candidates = []
        for file_node in self._file_nodes:
            fp = file_node.file_path or ""
            # Strip common source extensions for comparison
            fp_no_ext = fp
            for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"):
                if fp_no_ext.endswith(ext):
                    fp_no_ext = fp_no_ext[: -len(ext)]
                    break

            if fp_no_ext == normalised or fp_no_ext.endswith("/" + normalised):
                candidates.append(file_node)

        if len(candidates) == 1:
            return candidates[0]
        return None


def _is_already_resolved(to_id: str) -> bool:
    """Return True if to_id already contains a file path (has '/' after kind prefix)."""
    # Format: kind.path/to/file:Name  — the '/' must appear after the first '.'
    dot_idx = to_id.find(".")
    if dot_idx == -1:
        return False
    rest = to_id[dot_idx + 1:]
    return "/" in rest


def _parse_symbolic(to_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'kind.Name' into (kind, name). Returns (None, None) if malformed."""
    dot_idx = to_id.find(".")
    if dot_idx == -1:
        return None, None
    kind = to_id[:dot_idx]
    name = to_id[dot_idx + 1:]
    return kind, name


def resolve_edges(
    nodes: List[CodeNode],
    edges: List[CodeEdge],
) -> Tuple[List[CodeEdge], ResolveStats]:
    """Resolve symbolic to_id references in edges using the provided node list.

    Returns a new list of edges (original edges are not mutated) and stats.
    """
    table = SymbolTable(nodes)

    resolved_edges: List[CodeEdge] = []
    total = len(edges)
    resolved_count = 0
    unresolved_count = 0
    ambiguous_count = 0

    for edge in edges:
        # Work on a shallow copy so we never mutate the original
        new_edge = copy.copy(edge)

        to_id = edge.to_id

        # Already fully resolved — pass through unchanged
        if _is_already_resolved(to_id):
            resolved_edges.append(new_edge)
            # Count as resolved since it already has a file path
            resolved_count += 1
            continue

        kind, name = _parse_symbolic(to_id)
        if kind is None or name is None:
            # Malformed — keep as-is
            resolved_edges.append(new_edge)
            unresolved_count += 1
            continue

        # ---- module resolution ----
        if kind == "module":
            file_node = table.lookup_module(name)
            if file_node is not None:
                new_edge.to_id = file_node.id
                resolved_count += 1
            else:
                # External dependency or ambiguous — keep symbolic
                new_edge.confidence = min(edge.confidence, 0.5)
                unresolved_count += 1
            resolved_edges.append(new_edge)
            continue

        # ---- symbol resolution (try function then class) ----
        if kind == "symbol":
            # Check for qualified name pattern like "obj.method"
            if "." in name:
                # e.g. "obj.method" — try (function, "obj.method") first
                matches = table.lookup("function", name)
                if not matches:
                    # Try just the method part
                    method_name = name.split(".")[-1]
                    matches = table.lookup("function", method_name)
            else:
                matches = table.lookup("function", name)
                if not matches:
                    matches = table.lookup("class", name)

            if len(matches) == 1:
                new_edge.to_id = matches[0].id
                resolved_count += 1
            elif len(matches) == 0:
                new_edge.confidence = min(edge.confidence, 0.5)
                unresolved_count += 1
            else:
                new_edge.confidence = min(edge.confidence, 0.6)
                ambiguous_count += 1
                unresolved_count += 1
            resolved_edges.append(new_edge)
            continue

        # ---- direct kind resolution: class, struct, interface, function, etc. ----
        matches = table.lookup(kind, name)
        if len(matches) == 1:
            new_edge.to_id = matches[0].id
            resolved_count += 1
        elif len(matches) == 0:
            new_edge.confidence = min(edge.confidence, 0.5)
            unresolved_count += 1
        else:
            new_edge.confidence = min(edge.confidence, 0.6)
            ambiguous_count += 1
            unresolved_count += 1

        resolved_edges.append(new_edge)

    stats = ResolveStats(
        total_edges=total,
        resolved=resolved_count,
        unresolved=unresolved_count,
        ambiguous=ambiguous_count,
    )
    return resolved_edges, stats
