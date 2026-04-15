"""C/C++ Extractor Tests (Tree-sitter backend)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tools.code_graph_extractor.backends.tree_sitter_backend import TreeSitterBackend
    _BACKEND = TreeSitterBackend()
    _HAS_C = _BACKEND.can_handle('c')
    _HAS_CPP = _BACKEND.can_handle('cpp')
except ImportError:
    _HAS_C = _HAS_CPP = False


pytestmark = pytest.mark.skipif(
    not (_HAS_C and _HAS_CPP),
    reason="tree-sitter c/cpp grammar not installed",
)


def _kinds(result):
    return {(n.kind, n.name) for n in result.nodes}


def _edges(result):
    return {(e.from_id, e.kind, e.to_id) for e in result.edges}


def test_c_struct_and_function():
    src = '''
#include <stdio.h>
#define MAX 100

typedef struct Point {
    int x;
    int y;
} Point;

int add(int a, int b) {
    return a + b;
}

void use(void) {
    add(1, 2);
}
'''
    r = _BACKEND.extract(src, 'sample.c')
    kinds = _kinds(r)
    assert ('struct', 'Point') in kinds
    assert ('function', 'add') in kinds
    assert ('function', 'use') in kinds
    assert ('constant', 'MAX') in kinds
    assert ('type', 'Point') in kinds

    edges = _edges(r)
    # #define creates constant with defines edge
    assert ('file.sample.c', 'defines', 'constant.sample.c:MAX') in edges
    # #include creates import edge
    assert any(e[1] == 'imports' and 'stdio' in e[2] for e in edges)
    # call attribution at function level
    assert ('function.sample.c:use', 'calls', 'symbol.add') in edges


def test_cpp_class_methods_and_inheritance():
    src = '''
#include <string>
namespace app {

class Base {
public:
    virtual void hello();
};

class Derived : public Base {
public:
    void hello() override;
    void bye();
};

}

void app::Derived::bye() {
    hello();
}
'''
    r = _BACKEND.extract(src, 'sample.cpp')
    kinds = _kinds(r)
    assert ('class', 'Base') in kinds
    assert ('class', 'Derived') in kinds

    edges = _edges(r)
    # Inheritance
    assert any(e[1] == 'extends' and e[0].endswith('Derived') for e in edges)
    # Out-of-class method attached to class via contains
    assert any(
        e[1] == 'contains' and e[0].endswith('Derived') and e[2].endswith('Derived.bye')
        for e in edges
    )
    # Call inside method body attributed to the method
    assert any(
        e[1] == 'calls' and e[0].endswith('Derived.bye') and e[2] == 'symbol.hello'
        for e in edges
    )


def test_cpp_alias_declaration():
    src = '''
using Foo = int;
'''
    r = _BACKEND.extract(src, 'alias.cpp')
    kinds = _kinds(r)
    assert ('type', 'Foo') in kinds
    edges = _edges(r)
    assert ('file.alias.cpp', 'defines', 'type.alias.cpp:Foo') in edges
