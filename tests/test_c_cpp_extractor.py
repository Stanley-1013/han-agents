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


def test_cpp_namespace_free_function_not_method():
    """Regression: `namespace ns { void f(); } void ns::f() {}` must NOT
    create a `contains class.ns -> function.ns.f` edge."""
    src = '''
namespace ns {
    void f();
}

void ns::f() {}
'''
    r = _BACKEND.extract(src, 'ns.cpp')
    edges = _edges(r)
    # No contains edge from a bogus "class ns"
    assert not any(
        e[1] == 'contains' and 'class.' in e[0] and 'ns' in e[0]
        for e in edges
    ), f"free function wrongly attached as method: {edges}"
    # Function should exist as a plain defines from file
    assert any(
        e[1] == 'defines' and e[2].startswith('function.ns.cpp') and 'f' in e[2]
        for e in edges
    )


def test_cpp_struct_out_of_class_method_uses_struct_kind():
    """Regression: out-of-class method on a struct must attach via
    `contains struct.<file>:S -> function.<file>:S.m`, not class.*"""
    src = '''
struct S {
    void m();
};

void S::m() {}
'''
    r = _BACKEND.extract(src, 'st.cpp')
    edges = _edges(r)
    assert ('struct.st.cpp:S', 'contains', 'function.st.cpp:S.m') in edges
    # Must NOT produce the wrong class.* edge
    assert not any(
        e == ('class.st.cpp:S', 'contains', 'function.st.cpp:S.m')
        for e in edges
    )


def test_cpp_struct_extends_struct_uses_struct_kind():
    """Regression: struct inheriting a struct should emit `extends struct.<Base>`."""
    src = '''
struct Base {};
struct Derived : public Base {};
'''
    r = _BACKEND.extract(src, 'inh.cpp')
    edges = _edges(r)
    assert ('struct.inh.cpp:Derived', 'extends', 'struct.Base') in edges


def test_h_heuristic_ignores_cpp_tokens_in_macros_and_comments():
    """Regression: .h with `::` only in macro bodies/comments/strings
    must NOT be upgraded to C++."""
    import os
    import tempfile
    from tools.code_graph_extractor.extractor import extract_from_file

    pure_c = '''
// cross-reference: see Foo::bar in docs
#define NS_JOIN(a, b) a::b
const char *msg = "class Foo is cool";
int plain_c_var;
'''
    real_cpp = '''
class Foo {
public:
    void m();
};
'''
    with tempfile.TemporaryDirectory() as td:
        p1 = os.path.join(td, 'pure.h')
        with open(p1, 'w') as f:
            f.write(pure_c)
        assert extract_from_file(p1).language == 'c'

        p2 = os.path.join(td, 'real.h')
        with open(p2, 'w') as f:
            f.write(real_cpp)
        assert extract_from_file(p2).language == 'cpp'


def test_cpp_alias_declaration():
    src = '''
using Foo = int;
'''
    r = _BACKEND.extract(src, 'alias.cpp')
    kinds = _kinds(r)
    assert ('type', 'Foo') in kinds
    edges = _edges(r)
    assert ('file.alias.cpp', 'defines', 'type.alias.cpp:Foo') in edges
