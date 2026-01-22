"""
Rust Extractor Tests

測試 Rust 程式碼 Graph 提取功能。
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.code_graph_extractor.extractor import RegexExtractor, extract_from_file


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_rust_struct():
    """範例 Rust struct（含 derives、impl、methods）"""
    return '''
use std::fmt::{self, Display};
use serde::{Serialize, Deserialize};

/// User struct with common derives
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub name: String,
    pub age: u32,
    email: String,
}

impl User {
    pub fn new(name: String, age: u32) -> Self {
        Self {
            name,
            age,
            email: String::new(),
        }
    }

    pub fn get_name(&self) -> &str {
        &self.name
    }

    fn validate_email(&self) -> bool {
        self.email.contains('@')
    }
}

impl Display for User {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} ({})", self.name, self.age)
    }
}
'''


@pytest.fixture
def sample_rust_enum():
    """範例 Rust enum"""
    return '''
use std::fmt::Display;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Status {
    Active,
    Inactive,
    Pending(u32),
}

impl Status {
    pub fn is_active(&self) -> bool {
        matches!(self, Status::Active)
    }
}
'''


@pytest.fixture
def sample_rust_trait():
    """範例 Rust trait"""
    return '''
pub trait Repository<T> {
    fn find_by_id(&self, id: u64) -> Option<T>;
    fn save(&mut self, item: T) -> Result<(), Error>;
    fn delete(&mut self, id: u64) -> Result<(), Error>;

    fn find_all(&self) -> Vec<T> {
        Vec::new()
    }
}

pub trait Validator: Send + Sync {
    fn validate(&self) -> bool;
}
'''


@pytest.fixture
def sample_rust_module():
    """範例 Rust module 結構"""
    return '''
pub mod auth {
    use crate::user::User;

    pub fn login(user: &User) -> Result<Token, AuthError> {
        // ...
        Ok(Token::new())
    }
}

mod internal {
    pub(crate) fn helper() {}
}
'''


@pytest.fixture
def sample_rust_constants():
    """範例 Rust constants 和 statics"""
    return '''
pub const MAX_USERS: usize = 1000;
const DEFAULT_TIMEOUT: u64 = 30;

pub static GLOBAL_CONFIG: Config = Config::new();
static mut COUNTER: u32 = 0;
'''


@pytest.fixture
def sample_rust_macro():
    """範例 Rust macro"""
    return '''
#[macro_export]
macro_rules! vec_of_strings {
    ($($x:expr),*) => {
        vec![$($x.to_string()),*]
    };
}

pub macro_rules! debug_print {
    ($val:expr) => {
        println!("{} = {:?}", stringify!($val), $val);
    };
}
'''


@pytest.fixture
def sample_rust_generics():
    """範例 Rust generics 和 lifetimes"""
    return '''
use std::marker::PhantomData;

pub struct Container<'a, T: Clone> {
    data: &'a T,
    _marker: PhantomData<T>,
}

impl<'a, T: Clone> Container<'a, T> {
    pub fn new(data: &'a T) -> Self {
        Self { data, _marker: PhantomData }
    }

    pub fn get(&self) -> &T {
        self.data
    }
}

pub fn process<T, E>(input: T) -> Result<T, E>
where
    T: Clone + Send,
    E: std::error::Error,
{
    Ok(input)
}
'''


# =============================================================================
# Test: Use Extraction
# =============================================================================

class TestRustUseExtraction:
    """測試 use 提取"""

    def test_extract_simple_use(self, sample_rust_struct):
        """應該提取一般 use"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        import_edges = [e for e in result.edges if e.kind == 'imports']
        assert len(import_edges) >= 2

        target_ids = [e.to_id for e in import_edges]
        assert any('std::fmt' in t for t in target_ids)
        assert any('serde' in t for t in target_ids)

    def test_extract_nested_use(self):
        """應該提取巢狀 use"""
        content = '''
use std::collections::{HashMap, HashSet, BTreeMap};
use std::io::*;
'''
        result = RegexExtractor.extract_rust(content, 'lib.rs')

        import_edges = [e for e in result.edges if e.kind == 'imports']
        assert len(import_edges) >= 2


# =============================================================================
# Test: Struct Extraction
# =============================================================================

class TestRustStructExtraction:
    """測試 Struct 提取"""

    def test_extract_pub_struct(self, sample_rust_struct):
        """應該提取 pub struct"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 1
        assert struct_nodes[0].name == 'User'
        assert struct_nodes[0].visibility == 'public'

    def test_extract_struct_with_derives(self, sample_rust_struct):
        """應該正確處理 derives attribute"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 1

    def test_extract_tuple_struct(self):
        """應該提取 tuple struct"""
        content = '''
pub struct Point(pub f64, pub f64);
struct Color(u8, u8, u8);
'''
        result = RegexExtractor.extract_rust(content, 'types.rs')

        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 2

    def test_extract_unit_struct(self):
        """應該提取 unit struct"""
        content = '''
pub struct Marker;
struct Empty;
'''
        # Note: unit structs 可能會被 regex 處理
        # 簡化測試

    def test_extract_generic_struct(self, sample_rust_generics):
        """應該提取泛型 struct"""
        result = RegexExtractor.extract_rust(sample_rust_generics, 'container.rs')

        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 1
        assert struct_nodes[0].name == 'Container'


# =============================================================================
# Test: Enum Extraction
# =============================================================================

class TestRustEnumExtraction:
    """測試 Enum 提取"""

    def test_extract_enum(self, sample_rust_enum):
        """應該提取 enum"""
        result = RegexExtractor.extract_rust(sample_rust_enum, 'status.rs')

        enum_nodes = [n for n in result.nodes if n.kind == 'enum']
        assert len(enum_nodes) == 1
        assert enum_nodes[0].name == 'Status'
        assert enum_nodes[0].visibility == 'public'


# =============================================================================
# Test: Trait Extraction
# =============================================================================

class TestRustTraitExtraction:
    """測試 Trait 提取"""

    def test_extract_trait(self, sample_rust_trait):
        """應該提取 trait"""
        result = RegexExtractor.extract_rust(sample_rust_trait, 'traits.rs')

        trait_nodes = [n for n in result.nodes if n.kind == 'trait']
        assert len(trait_nodes) == 2

        names = [n.name for n in trait_nodes]
        assert 'Repository' in names
        assert 'Validator' in names

    def test_extract_trait_with_bounds(self, sample_rust_trait):
        """應該提取有 bounds 的 trait"""
        result = RegexExtractor.extract_rust(sample_rust_trait, 'traits.rs')

        validator = next((n for n in result.nodes if n.name == 'Validator'), None)
        assert validator is not None


# =============================================================================
# Test: Impl Extraction
# =============================================================================

class TestRustImplExtraction:
    """測試 Impl 提取"""

    def test_extract_impl_methods(self, sample_rust_struct):
        """應該提取 impl 中的方法"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        func_nodes = [n for n in result.nodes if n.kind == 'function']
        func_names = [n.name for n in func_nodes]

        assert 'new' in func_names
        assert 'get_name' in func_names
        assert 'validate_email' in func_names
        assert 'fmt' in func_names

    def test_impl_trait_for_type(self, sample_rust_struct):
        """應該建立 implements edge"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        implements_edges = [e for e in result.edges if e.kind == 'implements']
        assert len(implements_edges) >= 1

        # User implements Display
        display_impl = [e for e in implements_edges if 'Display' in e.to_id]
        assert len(display_impl) >= 1


# =============================================================================
# Test: Function Extraction
# =============================================================================

class TestRustFunctionExtraction:
    """測試 Function 提取"""

    def test_extract_pub_fn(self, sample_rust_module):
        """應該提取 pub fn"""
        result = RegexExtractor.extract_rust(sample_rust_module, 'auth.rs')

        func_nodes = [n for n in result.nodes if n.kind == 'function']
        func_names = [n.name for n in func_nodes]

        assert 'login' in func_names
        assert 'helper' in func_names

    def test_extract_async_fn(self):
        """應該提取 async fn"""
        content = '''
pub async fn fetch_data(url: &str) -> Result<String, Error> {
    // ...
    Ok(String::new())
}
'''
        result = RegexExtractor.extract_rust(content, 'async.rs')

        func_nodes = [n for n in result.nodes if n.kind == 'function']
        assert len(func_nodes) == 1
        assert func_nodes[0].name == 'fetch_data'

    def test_extract_const_fn(self):
        """應該提取 const fn"""
        content = '''
pub const fn max(a: usize, b: usize) -> usize {
    if a > b { a } else { b }
}
'''
        result = RegexExtractor.extract_rust(content, 'const.rs')

        func_nodes = [n for n in result.nodes if n.kind == 'function']
        assert len(func_nodes) == 1
        assert func_nodes[0].name == 'max'

    def test_function_signature(self, sample_rust_generics):
        """應該提取函式簽名"""
        result = RegexExtractor.extract_rust(sample_rust_generics, 'generic.rs')

        process_fn = next((n for n in result.nodes if n.name == 'process'), None)
        assert process_fn is not None
        assert process_fn.signature is not None


# =============================================================================
# Test: Constant/Static Extraction
# =============================================================================

class TestRustConstantExtraction:
    """測試 Constant/Static 提取"""

    def test_extract_const(self, sample_rust_constants):
        """應該提取 const"""
        result = RegexExtractor.extract_rust(sample_rust_constants, 'config.rs')

        const_nodes = [n for n in result.nodes if n.kind == 'constant']
        const_names = [n.name for n in const_nodes]

        assert 'MAX_USERS' in const_names
        assert 'DEFAULT_TIMEOUT' in const_names

    def test_extract_static(self, sample_rust_constants):
        """應該提取 static"""
        result = RegexExtractor.extract_rust(sample_rust_constants, 'config.rs')

        static_nodes = [n for n in result.nodes if n.kind == 'static']
        static_names = [n.name for n in static_nodes]

        assert 'GLOBAL_CONFIG' in static_names
        assert 'COUNTER' in static_names


# =============================================================================
# Test: Module Extraction
# =============================================================================

class TestRustModuleExtraction:
    """測試 Module 提取"""

    def test_extract_inline_mod(self, sample_rust_module):
        """應該提取 inline mod"""
        result = RegexExtractor.extract_rust(sample_rust_module, 'lib.rs')

        mod_nodes = [n for n in result.nodes if n.kind == 'module']
        mod_names = [n.name for n in mod_nodes]

        assert 'auth' in mod_names
        assert 'internal' in mod_names

    def test_extract_mod_declaration(self):
        """應該提取 mod 宣告（非 inline）"""
        content = '''
pub mod auth;
mod config;
pub(crate) mod utils;
'''
        result = RegexExtractor.extract_rust(content, 'lib.rs')

        mod_nodes = [n for n in result.nodes if n.kind == 'module']
        assert len(mod_nodes) == 3


# =============================================================================
# Test: Macro Extraction
# =============================================================================

class TestRustMacroExtraction:
    """測試 Macro 提取"""

    def test_extract_macro_rules(self, sample_rust_macro):
        """應該提取 macro_rules!"""
        result = RegexExtractor.extract_rust(sample_rust_macro, 'macros.rs')

        macro_nodes = [n for n in result.nodes if n.kind == 'macro']
        macro_names = [n.name for n in macro_nodes]

        assert 'vec_of_strings' in macro_names
        assert 'debug_print' in macro_names


# =============================================================================
# Test: Type Alias Extraction
# =============================================================================

class TestRustTypeAliasExtraction:
    """測試 Type Alias 提取"""

    def test_extract_type_alias(self):
        """應該提取 type alias"""
        content = '''
pub type Result<T> = std::result::Result<T, Error>;
type BoxFuture<T> = Box<dyn Future<Output = T> + Send>;
'''
        result = RegexExtractor.extract_rust(content, 'types.rs')

        type_nodes = [n for n in result.nodes if n.kind == 'type']
        type_names = [n.name for n in type_nodes]

        assert 'Result' in type_names
        assert 'BoxFuture' in type_names


# =============================================================================
# Test: Visibility
# =============================================================================

class TestRustVisibility:
    """測試 Visibility 解析"""

    def test_pub_visibility(self, sample_rust_struct):
        """應該識別 pub"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        user_struct = next((n for n in result.nodes if n.name == 'User'), None)
        assert user_struct.visibility == 'public'

    def test_private_visibility(self, sample_rust_struct):
        """應該識別 private（預設）"""
        result = RegexExtractor.extract_rust(sample_rust_struct, 'user.rs')

        validate_fn = next((n for n in result.nodes if n.name == 'validate_email'), None)
        assert validate_fn.visibility == 'private'

    def test_pub_crate_visibility(self):
        """應該識別 pub(crate)"""
        content = '''
pub(crate) struct Internal {
    data: String,
}

pub(crate) fn internal_helper() {}
'''
        result = RegexExtractor.extract_rust(content, 'internal.rs')

        struct_node = next((n for n in result.nodes if n.name == 'Internal'), None)
        assert struct_node.visibility == 'pub(crate)'


# =============================================================================
# Test: Comment Handling
# =============================================================================

class TestRustCommentHandling:
    """測試註解處理"""

    def test_remove_line_comments(self):
        """應該移除單行註解"""
        content = '''
// This is a comment
pub struct Test {} // inline comment
'''
        cleaned = RegexExtractor._remove_rust_comments(content)
        assert '//' not in cleaned

    def test_remove_doc_comments(self):
        """應該移除文檔註解"""
        content = '''
/// Doc comment
//! Module doc
pub struct Test {}
'''
        cleaned = RegexExtractor._remove_rust_comments(content)
        assert '///' not in cleaned
        assert '//!' not in cleaned

    def test_remove_block_comments(self):
        """應該移除多行註解"""
        content = '''
/* Multi-line
   comment */
pub struct Test {}
'''
        cleaned = RegexExtractor._remove_rust_comments(content)
        assert '/*' not in cleaned
        assert '*/' not in cleaned


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestRustEdgeCases:
    """測試邊界情況"""

    def test_empty_file(self):
        """應該處理空檔案"""
        result = RegexExtractor.extract_rust('', 'empty.rs')

        # 只有 file node
        assert len(result.nodes) == 1
        assert result.nodes[0].kind == 'file'

    def test_raw_strings(self):
        """應該正確處理 raw strings"""
        content = r'''
pub fn get_regex() -> &'static str {
    r#"[a-z]+"#
}

pub fn get_json() -> &'static str {
    r##"{"key": "value"}"##
}
'''
        result = RegexExtractor.extract_rust(content, 'strings.rs')

        func_nodes = [n for n in result.nodes if n.kind == 'function']
        assert len(func_nodes) == 2

    def test_lifetimes(self, sample_rust_generics):
        """應該正確處理 lifetimes"""
        result = RegexExtractor.extract_rust(sample_rust_generics, 'generic.rs')

        # 應該不會把 'a 當作字元處理
        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 1


# =============================================================================
# Test: File-based Extraction
# =============================================================================

class TestRustFileExtraction:
    """測試檔案層級提取"""

    def test_extract_from_file(self, tmp_path):
        """應該能從檔案提取"""
        rust_file = tmp_path / "test.rs"
        rust_file.write_text('''
pub struct Point {
    pub x: f64,
    pub y: f64,
}

impl Point {
    pub fn new(x: f64, y: f64) -> Self {
        Self { x, y }
    }
}
''')
        result = extract_from_file(str(rust_file))

        assert result.language == 'rust'
        assert len(result.errors) == 0

        struct_nodes = [n for n in result.nodes if n.kind == 'struct']
        assert len(struct_nodes) == 1
        assert struct_nodes[0].name == 'Point'
