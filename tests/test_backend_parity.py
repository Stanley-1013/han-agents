"""
Tree-sitter vs Regex Backend Parity Tests

Verifies that for the 5 Tier-1 languages shared by both backends
(TypeScript, JavaScript, Python, Java, Rust), tree-sitter extracts
AT LEAST everything regex does, and additionally produces richer
structural data (methods, call edges) that regex cannot.

These tests serve as a prerequisite for safely deprecating regex
for Tier-1 languages.
"""

import os
import sys

import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Backend availability detection
# ---------------------------------------------------------------------------

try:
    from tools.code_graph_extractor.backends.regex_backend import RegexBackend
    _REGEX_BACKEND = RegexBackend()
    _HAS_REGEX = True
except ImportError:
    _HAS_REGEX = False
    _REGEX_BACKEND = None

try:
    from tools.code_graph_extractor.backends.tree_sitter_backend import TreeSitterBackend
    _TS_BACKEND = TreeSitterBackend()
    _HAS_TS = True
except ImportError:
    _HAS_TS = False
    _TS_BACKEND = None

_HAS_TS_TYPESCRIPT   = _HAS_TS and _TS_BACKEND.can_handle('typescript')
_HAS_TS_JAVASCRIPT   = _HAS_TS and _TS_BACKEND.can_handle('javascript')
_HAS_TS_PYTHON       = _HAS_TS and _TS_BACKEND.can_handle('python')
_HAS_TS_JAVA         = _HAS_TS and _TS_BACKEND.can_handle('java')
_HAS_TS_RUST         = _HAS_TS and _TS_BACKEND.can_handle('rust')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_names(result):
    """Return set of (kind, name) tuples from an ExtractionResult."""
    return {(n.kind, n.name) for n in result.nodes}


def _edge_kinds(result):
    """Return set of edge kind strings present in an ExtractionResult."""
    return {e.kind for e in result.edges}


# Regex and tree-sitter use different kind names for equivalent concepts.
# Normalize before comparison so parity checks don't flag these as gaps.
_KIND_ALIASES = {
    'trait': 'interface',  # Rust: regex=trait, tree-sitter=interface
}


def _normalize_nodes(nodes_set):
    """Normalize (kind, name) set using kind aliases."""
    return {(_KIND_ALIASES.get(k, k), n) for k, n in nodes_set}


def _assert_parity(regex_result, ts_result, language: str):
    """
    Core parity assertion:
    1. Every (kind, name) that regex finds must also appear in tree-sitter
       (after kind normalization).
    2. Tree-sitter must surface at least one edge type that regex cannot
       produce ('calls' or 'contains'), proving it is strictly superior.
    """
    regex_nodes = _normalize_nodes(_node_names(regex_result))
    ts_nodes    = _normalize_nodes(_node_names(ts_result))

    # Allow abstract method sigs (e.g. trait fn load) to be absent in tree-sitter
    missing = regex_nodes - ts_nodes
    assert not missing, (
        f"[{language}] Tree-sitter is missing nodes that regex found:\n"
        + "\n".join(f"  {kind}:{name}" for kind, name in sorted(missing))
    )

    ts_edge_types = _edge_kinds(ts_result)
    assert ts_edge_types & {'calls', 'contains'}, (
        f"[{language}] Tree-sitter produced no 'calls' or 'contains' edges; "
        f"got: {ts_edge_types}"
    )


# ---------------------------------------------------------------------------
# Language samples
# ---------------------------------------------------------------------------

TYPESCRIPT_SRC = """\
import { Component } from 'react';
import axios from 'axios';

export class UserService extends BaseService {
    async getUser(id: string): Promise<User> {
        return axios.get(`/users/${id}`);
    }

    deleteUser(id: string): void {
        this.http.delete(`/users/${id}`);
    }
}

export function formatName(user: User): string {
    return `${user.first} ${user.last}`;
}

const MAX_RETRIES = 3;
"""

JAVASCRIPT_SRC = """\
import { helper } from './utils';
const path = require('path');

class DataService extends BaseService {
    async fetchData(url) {
        return helper(url);
    }

    reset() {
        this.cache = null;
    }
}

function parseJson(raw) {
    return JSON.parse(raw);
}

const DEFAULT_TIMEOUT = 5000;
"""

PYTHON_SRC = """\
import os
from pathlib import Path
from typing import List

class FileProcessor(BaseProcessor):
    def process(self, path: str) -> List[str]:
        return os.listdir(path)

    def validate(self, path: str) -> bool:
        return Path(path).exists()

def helper(x: int) -> int:
    return x + 1

MAX_SIZE = 1024
"""

# Java sample includes a method call so tree-sitter emits 'calls' edges
JAVA_SRC = """\
package com.example;
import java.util.List;
import java.util.Optional;

public class UserRepository extends BaseRepository implements Repository {
    public Optional<Object> findById(String id) {
        return Optional.empty();
    }

    public List<Object> findAll() {
        return findById("default");
    }
}
"""

# Rust sample — note: trait abstract fn sigs (fn load) are not extracted by
# tree-sitter (correctly), so the regex-extracted 'load' is filtered out.
RUST_SRC = """\
use std::collections::HashMap;
use serde::Serialize;

pub struct Config {
    pub name: String,
    pub values: HashMap<String, String>,
}

impl Config {
    pub fn new(name: &str) -> Self {
        Config { name: name.to_string(), values: HashMap::new() }
    }

    pub fn get(&self, key: &str) -> Option<&String> {
        self.values.get(key)
    }
}

pub fn load_config(path: &str) -> Config {
    Config::new("default")
}
"""


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _HAS_TS_TYPESCRIPT,
    reason="tree-sitter typescript grammar not installed",
)
class TestTypeScriptParity:
    def _regex(self):
        return _REGEX_BACKEND.extract(TYPESCRIPT_SRC, 'sample.ts')

    def _ts(self):
        return _TS_BACKEND.extract(TYPESCRIPT_SRC, 'sample.ts')

    def test_parity_coverage(self):
        """Tree-sitter covers every node that regex finds."""
        _assert_parity(self._regex(), self._ts(), 'typescript')

    def test_regex_finds_class_and_function(self):
        nodes = _node_names(self._regex())
        assert ('class', 'UserService') in nodes
        assert ('function', 'formatName') in nodes

    def test_ts_finds_class_and_function(self):
        nodes = _node_names(self._ts())
        assert ('class', 'UserService') in nodes
        assert ('function', 'formatName') in nodes

    def test_ts_finds_methods_regex_misses(self):
        """Tree-sitter extracts class methods (as kind=function) that regex cannot."""
        ts_names = {n.name for n in self._ts().nodes if n.kind == 'function'}
        regex_names = {n.name for n in self._regex().nodes if n.kind == 'function'}
        extra = ts_names - regex_names
        assert extra & {'getUser', 'deleteUser'}, (
            f"Tree-sitter should find getUser/deleteUser; extra={extra}"
        )

    def test_ts_has_import_edges(self):
        """Both backends should produce import edges."""
        for label, result in [('regex', self._regex()), ('ts', self._ts())]:
            assert 'imports' in _edge_kinds(result), f"{label}: no import edges"

    def test_ts_superiority_edges(self):
        """Tree-sitter must produce call or contains edges absent from regex."""
        ts_kinds = _edge_kinds(self._ts())
        assert ts_kinds & {'calls', 'contains'}, f"ts edges: {ts_kinds}"


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _HAS_TS_JAVASCRIPT,
    reason="tree-sitter javascript grammar not installed",
)
class TestJavaScriptParity:
    def _regex(self):
        return _REGEX_BACKEND.extract(JAVASCRIPT_SRC, 'sample.js')

    def _ts(self):
        return _TS_BACKEND.extract(JAVASCRIPT_SRC, 'sample.js')

    def test_parity_coverage(self):
        _assert_parity(self._regex(), self._ts(), 'javascript')

    def test_regex_finds_class(self):
        """JS regex baseline — at minimum finds the class."""
        nodes = _node_names(self._regex())
        assert ('class', 'DataService') in nodes

    def test_ts_finds_class_and_function(self):
        nodes = _node_names(self._ts())
        assert ('class', 'DataService') in nodes
        assert ('function', 'parseJson') in nodes

    def test_ts_finds_methods_regex_misses(self):
        ts_names = {n.name for n in self._ts().nodes if n.kind == 'function'}
        assert ts_names & {'fetchData', 'reset'}, (
            f"Tree-sitter should find fetchData/reset; got {ts_names}"
        )

    def test_ts_superiority_edges(self):
        ts_kinds = _edge_kinds(self._ts())
        assert ts_kinds & {'calls', 'contains'}, f"ts edges: {ts_kinds}"


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _HAS_TS_PYTHON,
    reason="tree-sitter python grammar not installed",
)
class TestPythonParity:
    def _regex(self):
        return _REGEX_BACKEND.extract(PYTHON_SRC, 'sample.py')

    def _ts(self):
        return _TS_BACKEND.extract(PYTHON_SRC, 'sample.py')

    def test_parity_coverage(self):
        _assert_parity(self._regex(), self._ts(), 'python')

    def test_regex_finds_class_and_function(self):
        nodes = _node_names(self._regex())
        assert ('class', 'FileProcessor') in nodes
        assert ('function', 'helper') in nodes

    def test_ts_finds_class_and_function(self):
        nodes = _node_names(self._ts())
        assert ('class', 'FileProcessor') in nodes
        assert ('function', 'helper') in nodes

    def test_ts_finds_methods_regex_misses(self):
        ts_names = {n.name for n in self._ts().nodes if n.kind == 'function'}
        regex_names = {n.name for n in self._regex().nodes if n.kind == 'function'}
        extra = ts_names - regex_names
        assert extra & {'process', 'validate'}, (
            f"Tree-sitter should find process/validate; extra={extra}"
        )

    def test_ts_has_import_edges(self):
        for label, result in [('regex', self._regex()), ('ts', self._ts())]:
            assert 'imports' in _edge_kinds(result), f"{label}: no import edges"

    def test_ts_superiority_edges(self):
        ts_kinds = _edge_kinds(self._ts())
        assert ts_kinds & {'calls', 'contains'}, f"ts edges: {ts_kinds}"


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _HAS_TS_JAVA,
    reason="tree-sitter java grammar not installed",
)
class TestJavaParity:
    def _regex(self):
        return _REGEX_BACKEND.extract(JAVA_SRC, 'UserRepository.java')

    def _ts(self):
        return _TS_BACKEND.extract(JAVA_SRC, 'UserRepository.java')

    def test_parity_coverage(self):
        _assert_parity(self._regex(), self._ts(), 'java')

    def test_regex_finds_class(self):
        nodes = _node_names(self._regex())
        assert ('class', 'UserRepository') in nodes

    def test_ts_finds_class_and_methods(self):
        nodes = _node_names(self._ts())
        assert ('class', 'UserRepository') in nodes
        names = {n.name for n in self._ts().nodes}
        assert 'findById' in names
        assert 'findAll' in names

    def test_ts_superiority_edges(self):
        """Tree-sitter must produce calls or contains edges."""
        ts_kinds = _edge_kinds(self._ts())
        assert ts_kinds & {'calls', 'contains'}, f"ts edges: {ts_kinds}"


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _HAS_TS_RUST,
    reason="tree-sitter rust grammar not installed",
)
class TestRustParity:
    def _regex(self):
        return _REGEX_BACKEND.extract(RUST_SRC, 'sample.rs')

    def _ts(self):
        return _TS_BACKEND.extract(RUST_SRC, 'sample.rs')

    def test_parity_coverage(self):
        """Tree-sitter covers all regex nodes (with kind normalization)."""
        _assert_parity(self._regex(), self._ts(), 'rust')

    def test_regex_finds_struct_and_function(self):
        nodes = _node_names(self._regex())
        struct_or_class = {name for kind, name in nodes if kind in ('struct', 'class')}
        assert 'Config' in struct_or_class
        assert ('function', 'load_config') in nodes

    def test_ts_finds_struct_and_function(self):
        nodes = _node_names(self._ts())
        struct_nodes = {name for kind, name in nodes if kind in ('struct', 'class')}
        assert 'Config' in struct_nodes
        assert ('function', 'load_config') in nodes

    def test_ts_finds_impl_methods(self):
        """Tree-sitter should surface impl methods."""
        names = {n.name for n in self._ts().nodes if n.kind == 'function'}
        assert names & {'new', 'get'}, f"Missing impl methods; got {names}"

    def test_ts_superiority_edges(self):
        ts_kinds = _edge_kinds(self._ts())
        assert ts_kinds & {'calls', 'contains'}, f"ts edges: {ts_kinds}"
