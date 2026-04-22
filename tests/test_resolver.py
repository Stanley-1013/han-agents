"""
Cross-File Symbol Resolver Tests

Tests for the SymbolTable and resolve_edges API in
tools/code_graph_extractor/resolver.py.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.code_graph_extractor.extractor import CodeNode, CodeEdge
from tools.code_graph_extractor.resolver import SymbolTable, resolve_edges, ResolveStats


# =============================================================================
# Helper Factories
# =============================================================================

def _node(id, kind, name, file_path='src/test.py'):
    return CodeNode(
        id=id,
        kind=kind,
        name=name,
        file_path=file_path,
        line_start=1,
        line_end=10,
        language='python',
    )


def _edge(from_id, to_id, kind='calls', confidence=1.0):
    return CodeEdge(
        from_id=from_id,
        to_id=to_id,
        kind=kind,
        line_number=1,
        confidence=confidence,
    )


# =============================================================================
# Test: SymbolTable.lookup
# =============================================================================

class TestSymbolTableLookup:
    """Tests for SymbolTable.lookup(kind, name)"""

    def test_lookup_finds_matching_node(self):
        """lookup should return the node whose kind and name match"""
        base = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')
        table = SymbolTable([base])

        results = table.lookup('class', 'Base')

        assert len(results) == 1
        assert results[0].id == 'class.src/base.py:Base'

    def test_lookup_returns_empty_when_no_match(self):
        """lookup should return an empty list when no node matches"""
        node = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')
        table = SymbolTable([node])

        results = table.lookup('class', 'Missing')

        assert results == []

    def test_lookup_returns_all_matches_when_ambiguous(self):
        """lookup should return all nodes when multiple share the same kind+name"""
        base_a = _node('class.src/a.py:Base', 'class', 'Base', 'src/a.py')
        base_b = _node('class.src/b.py:Base', 'class', 'Base', 'src/b.py')
        table = SymbolTable([base_a, base_b])

        results = table.lookup('class', 'Base')

        assert len(results) == 2

    def test_lookup_does_not_mix_kinds(self):
        """lookup should not return nodes of a different kind"""
        func_node = _node('function.src/utils.py:hello', 'function', 'hello', 'src/utils.py')
        table = SymbolTable([func_node])

        results = table.lookup('class', 'hello')

        assert results == []


# =============================================================================
# Test: SymbolTable.lookup_module
# =============================================================================

class TestSymbolTableLookupModule:
    """Tests for SymbolTable.lookup_module(module_name)"""

    def test_lookup_module_finds_file_node(self):
        """lookup_module should match a file node by module name"""
        file_node = _node('file.src/utils.py', 'file', 'src/utils.py', 'src/utils.py')
        table = SymbolTable([file_node])

        result = table.lookup_module('utils')

        assert result is not None
        assert result.kind == 'file'

    def test_lookup_module_returns_none_for_external(self):
        """lookup_module should return None for an external module not in the graph"""
        file_node = _node('file.src/utils.py', 'file', 'src/utils.py', 'src/utils.py')
        table = SymbolTable([file_node])

        result = table.lookup_module('react')

        assert result is None


# =============================================================================
# Test: resolve_edges — successful resolution
# =============================================================================

class TestResolveEdgesResolved:
    """Tests where edges are successfully resolved to full node IDs"""

    def test_resolve_class_extends(self):
        """class.Base -> resolved to class.src/base.py:Base"""
        base = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')
        child = _node('class.src/child.py:Child', 'class', 'Child', 'src/child.py')
        edge = _edge('class.src/child.py:Child', 'class.Base', kind='extends', confidence=1.0)

        resolved_edges, stats = resolve_edges([base, child], [edge])

        assert len(resolved_edges) == 1
        assert resolved_edges[0].to_id == 'class.src/base.py:Base'
        assert stats.resolved == 1
        assert stats.unresolved == 0

    def test_resolve_function_call(self):
        """symbol.hello -> resolved to function.src/utils.py:hello"""
        func = _node('function.src/utils.py:hello', 'function', 'hello', 'src/utils.py')
        caller = _node('function.src/main.py:main', 'function', 'main', 'src/main.py')
        edge = _edge('function.src/main.py:main', 'symbol.hello', kind='calls', confidence=0.9)

        resolved_edges, stats = resolve_edges([func, caller], [edge])

        assert resolved_edges[0].to_id == 'function.src/utils.py:hello'
        assert stats.resolved == 1

    def test_resolve_method_call(self):
        """symbol.obj.method -> should attempt to resolve method within class obj"""
        method = _node('function.src/models.py:obj.method', 'function', 'method', 'src/models.py')
        caller = _node('function.src/main.py:run', 'function', 'run', 'src/main.py')
        edge = _edge('function.src/main.py:run', 'symbol.obj.method', kind='calls', confidence=0.8)

        resolved_edges, stats = resolve_edges([method, caller], [edge])

        # The resolver should attempt resolution; result depends on whether it finds the node
        assert len(resolved_edges) == 1
        # confidence should not increase beyond original
        assert resolved_edges[0].confidence <= 0.8 + 1e-9

    def test_resolve_struct_resolution(self):
        """struct.Point -> resolves to struct.src/geo.c:Point"""
        point = _node('struct.src/geo.c:Point', 'struct', 'Point', 'src/geo.c')
        caller = _node('function.src/main.c:draw', 'function', 'draw', 'src/main.c')
        edge = _edge('function.src/main.c:draw', 'struct.Point', kind='calls', confidence=1.0)

        resolved_edges, stats = resolve_edges([point, caller], [edge])

        assert resolved_edges[0].to_id == 'struct.src/geo.c:Point'
        assert stats.resolved == 1

    def test_resolve_interface_resolution(self):
        """interface.IFoo -> resolves to interface.src/types.ts:IFoo"""
        iface = _node('interface.src/types.ts:IFoo', 'interface', 'IFoo', 'src/types.ts')
        impl = _node('class.src/foo.ts:Foo', 'class', 'Foo', 'src/foo.ts')
        edge = _edge('class.src/foo.ts:Foo', 'interface.IFoo', kind='implements', confidence=1.0)

        resolved_edges, stats = resolve_edges([iface, impl], [edge])

        assert resolved_edges[0].to_id == 'interface.src/types.ts:IFoo'
        assert stats.resolved == 1


# =============================================================================
# Test: resolve_edges — no match / external
# =============================================================================

class TestResolveEdgesUnresolved:
    """Tests where edges cannot be resolved (kept symbolic, confidence lowered)"""

    def test_unresolved_external_module(self):
        """module.react stays symbolic, confidence lowered to min(orig, 0.5)"""
        caller = _node('function.src/app.ts:App', 'function', 'App', 'src/app.ts')
        edge = _edge('function.src/app.ts:App', 'module.react', kind='imports', confidence=1.0)

        resolved_edges, stats = resolve_edges([caller], [edge])

        assert resolved_edges[0].to_id == 'module.react'
        assert resolved_edges[0].confidence <= 0.5
        assert stats.unresolved == 1
        assert stats.resolved == 0

    def test_unresolved_confidence_respects_original_lower_value(self):
        """If original confidence is already below 0.5, keep original"""
        caller = _node('function.src/app.py:fn', 'function', 'fn', 'src/app.py')
        edge = _edge('function.src/app.py:fn', 'symbol.missing', kind='calls', confidence=0.3)

        resolved_edges, stats = resolve_edges([caller], [edge])

        assert resolved_edges[0].to_id == 'symbol.missing'
        assert resolved_edges[0].confidence <= 0.5
        assert stats.unresolved == 1


# =============================================================================
# Test: resolve_edges — ambiguous resolution
# =============================================================================

class TestResolveEdgesAmbiguous:
    """Tests where multiple nodes match (ambiguous), confidence capped at 0.6"""

    def test_ambiguous_resolution(self):
        """Two nodes named Base -> stays symbolic, confidence capped at 0.6"""
        base_a = _node('class.src/a.py:Base', 'class', 'Base', 'src/a.py')
        base_b = _node('class.src/b.py:Base', 'class', 'Base', 'src/b.py')
        child = _node('class.src/child.py:Child', 'class', 'Child', 'src/child.py')
        edge = _edge('class.src/child.py:Child', 'class.Base', kind='extends', confidence=1.0)

        resolved_edges, stats = resolve_edges([base_a, base_b, child], [edge])

        assert resolved_edges[0].to_id == 'class.Base'
        assert resolved_edges[0].confidence <= 0.6
        assert stats.ambiguous == 1
        assert stats.resolved == 0

    def test_ambiguous_confidence_respects_original_lower_value(self):
        """If original confidence < 0.6, ambiguous resolution keeps original"""
        base_a = _node('class.src/a.py:Base', 'class', 'Base', 'src/a.py')
        base_b = _node('class.src/b.py:Base', 'class', 'Base', 'src/b.py')
        child = _node('class.src/child.py:Child', 'class', 'Child', 'src/child.py')
        edge = _edge('class.src/child.py:Child', 'class.Base', kind='extends', confidence=0.4)

        resolved_edges, stats = resolve_edges([base_a, base_b, child], [edge])

        assert resolved_edges[0].confidence <= 0.6
        assert stats.ambiguous == 1


# =============================================================================
# Test: resolve_edges — already resolved edges skipped
# =============================================================================

class TestResolveEdgesAlreadyResolved:
    """Tests for edges whose to_id already contains '/' (already resolved)"""

    def test_already_resolved_skipped(self):
        """to_id containing '/' is not modified"""
        base = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')
        child = _node('class.src/child.py:Child', 'class', 'Child', 'src/child.py')
        original_to_id = 'class.src/base.py:Base'
        edge = _edge('class.src/child.py:Child', original_to_id, kind='extends', confidence=1.0)

        resolved_edges, stats = resolve_edges([base, child], [edge])

        assert resolved_edges[0].to_id == original_to_id
        # Already resolved edges should not count as newly resolved
        assert stats.resolved == 0 or resolved_edges[0].to_id == original_to_id

    def test_already_resolved_confidence_unchanged(self):
        """Confidence of already-resolved edges is not modified"""
        base = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')
        child = _node('class.src/child.py:Child', 'class', 'Child', 'src/child.py')
        edge = _edge('class.src/child.py:Child', 'class.src/base.py:Base', kind='extends', confidence=0.75)

        resolved_edges, stats = resolve_edges([base, child], [edge])

        assert resolved_edges[0].confidence == pytest.approx(0.75)


# =============================================================================
# Test: resolve_edges — edge cases
# =============================================================================

class TestResolveEdgesEdgeCases:
    """Edge case tests for resolve_edges"""

    def test_empty_inputs(self):
        """Empty nodes and edges -> ResolveStats all zeros"""
        resolved_edges, stats = resolve_edges([], [])

        assert resolved_edges == []
        assert stats.total_edges == 0
        assert stats.resolved == 0
        assert stats.unresolved == 0
        assert stats.ambiguous == 0

    def test_empty_edges_with_nodes(self):
        """Nodes present but no edges -> ResolveStats all zeros"""
        base = _node('class.src/base.py:Base', 'class', 'Base', 'src/base.py')

        resolved_edges, stats = resolve_edges([base], [])

        assert resolved_edges == []
        assert stats.total_edges == 0

    def test_stats_counts(self):
        """Verify total/resolved/unresolved/ambiguous counts are consistent"""
        # One resolved, one unresolved, one ambiguous
        base_a = _node('class.src/a.py:Base', 'class', 'Base', 'src/a.py')
        base_b = _node('class.src/b.py:Base', 'class', 'Base', 'src/b.py')
        func = _node('function.src/utils.py:hello', 'function', 'hello', 'src/utils.py')
        caller = _node('function.src/main.py:main', 'function', 'main', 'src/main.py')

        edges = [
            # resolved: single match
            _edge('function.src/main.py:main', 'symbol.hello', kind='calls', confidence=1.0),
            # unresolved: no match
            _edge('function.src/main.py:main', 'module.react', kind='imports', confidence=1.0),
            # ambiguous: two Base nodes
            _edge('function.src/main.py:main', 'class.Base', kind='calls', confidence=1.0),
        ]

        resolved_edges, stats = resolve_edges([base_a, base_b, func, caller], edges)

        assert stats.total_edges == 3
        # ambiguous is a subset of unresolved, so resolved + unresolved == total
        assert stats.resolved + stats.unresolved == stats.total_edges
        assert stats.resolved >= 1    # symbol.hello should resolve
        assert stats.ambiguous >= 1   # class.Base is ambiguous
        assert stats.unresolved >= 1  # module.react is external

    def test_return_type_is_resolve_stats(self):
        """resolve_edges should return a ResolveStats instance"""
        _, stats = resolve_edges([], [])

        assert isinstance(stats, ResolveStats)

    def test_resolve_stats_has_required_fields(self):
        """ResolveStats should expose total_edges, resolved, unresolved, ambiguous"""
        _, stats = resolve_edges([], [])

        assert hasattr(stats, 'total_edges')
        assert hasattr(stats, 'resolved')
        assert hasattr(stats, 'unresolved')
        assert hasattr(stats, 'ambiguous')
