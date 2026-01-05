"""
語義記憶增強測試

測試 search_memory_semantic() 函數的各種模式和邊界情況
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servers.memory import search_memory_semantic, search_memory, store_memory


class TestSemanticSearchClaudeMode:
    """測試 Claude 重排模式"""

    def test_claude_mode_returns_candidates_and_prompt(self, sample_memories):
        """Claude 模式應返回候選和重排提示"""
        result = search_memory_semantic(
            "authentication patterns",
            project="test",
            limit=3,
            rerank_mode='claude'
        )

        # 有足夠候選時應進入 claude_rerank 模式
        if len(result.get('candidates', [])) > 0:
            assert result['mode'] == 'claude_rerank'
            assert 'candidates' in result
            assert 'rerank_prompt' in result
            assert isinstance(result['rerank_prompt'], str)
            assert len(result['candidates']) <= 20
        else:
            # 無候選時回退到 fts5_only
            assert result['mode'] == 'fts5_only'

    def test_claude_mode_prompt_format(self, sample_memories):
        """重排提示應包含查詢和候選格式"""
        result = search_memory_semantic(
            "token validation",
            project="test",
            limit=2,
            rerank_mode='claude'
        )

        if result['mode'] == 'claude_rerank':
            prompt = result['rerank_prompt']
            # 應包含查詢
            assert "token validation" in prompt
            # 應包含格式說明
            assert "[" in prompt  # 格式說明中有 [0, 3, 7, ...]

    def test_insufficient_candidates_fallback(self, mock_db_path):
        """候選不足時應回退到 fts5_only"""
        # 存入極少量記憶
        store_memory("test_cat", "unique xyz content", "Unique", "test")

        result = search_memory_semantic(
            "unique xyz",
            project="test",
            limit=10,  # 請求比候選多
            rerank_mode='claude'
        )

        # 候選 <= limit 時應直接返回結果
        assert result['mode'] == 'fts5_only'
        assert 'results' in result


class TestSemanticSearchNoneMode:
    """測試 None 模式（純 FTS5）"""

    def test_none_mode_equals_search_memory(self, sample_memories):
        """none 模式應等同於 search_memory"""
        semantic_result = search_memory_semantic(
            "auth",
            project="test",
            limit=5,
            rerank_mode='none'
        )

        direct_result = search_memory(
            "auth",
            project="test",
            limit=5
        )

        assert semantic_result['mode'] == 'fts5_only'
        assert 'results' in semantic_result
        # 結果應相同（順序可能略有不同，比較 ID）
        semantic_ids = {r['id'] for r in semantic_result['results']}
        direct_ids = {r['id'] for r in direct_result}
        assert semantic_ids == direct_ids


class TestSemanticSearchEmbeddingMode:
    """測試 Embedding 模式"""

    def test_embedding_mode_graceful_degradation(self, sample_memories):
        """嵌入模型不可用時應優雅降級"""
        result = search_memory_semantic(
            "user management",
            project="test",
            limit=3,
            rerank_mode='embedding'
        )

        # 不管嵌入模型是否可用，都應返回結果
        assert 'results' in result
        # fts5_only 也是可能的（候選不足時）
        assert result['mode'] in ['embedding_rerank', 'fts5_fallback', 'fts5_only']

    def test_embedding_mode_returns_semantic_score(self, sample_memories):
        """如果嵌入可用，結果應包含 semantic_score"""
        result = search_memory_semantic(
            "user management",
            project="test",
            limit=3,
            rerank_mode='embedding'
        )

        if result['mode'] == 'embedding_rerank':
            for r in result['results']:
                assert 'semantic_score' in r
                assert 0.0 <= r['semantic_score'] <= 1.0


class TestSemanticSearchKwargsPassthrough:
    """測試參數透傳"""

    def test_category_filter_passthrough(self, sample_memories):
        """category 參數應正確傳遞到 search_memory"""
        result = search_memory_semantic(
            "auth",
            project="test",
            limit=5,
            rerank_mode='none',
            category='pattern'
        )

        assert result['mode'] == 'fts5_only'
        for r in result['results']:
            assert r['category'] == 'pattern'

    def test_branch_filter_passthrough(self, mock_db_path):
        """branch 參數應正確傳遞"""
        # 存入帶 branch 的記憶
        store_memory(
            "knowledge", "Auth branch content", "Auth Memory",
            project="test", branch_flow="flow.auth"
        )
        store_memory(
            "knowledge", "User branch content", "User Memory",
            project="test", branch_flow="flow.user"
        )

        result = search_memory_semantic(
            "content",
            project="test",
            limit=5,
            rerank_mode='none',
            branch_flow='flow.auth'
        )

        # 應只返回 flow.auth 的記憶（或 NULL）
        for r in result['results']:
            assert r.get('branch_flow') in [None, 'flow.auth']


class TestSemanticSearchEdgeCases:
    """測試邊界情況"""

    def test_empty_query(self, mock_db_path):
        """空查詢應返回空結果"""
        result = search_memory_semantic(
            "",
            project="test",
            limit=5,
            rerank_mode='claude'
        )

        assert result['mode'] == 'fts5_only'
        assert len(result['results']) == 0

    def test_no_matching_results(self, mock_db_path):
        """無匹配時應返回空結果"""
        result = search_memory_semantic(
            "completely random nonexistent xyz123",
            project="test",
            limit=5,
            rerank_mode='claude'
        )

        assert result['mode'] == 'fts5_only'
        assert len(result['results']) == 0

    def test_unknown_mode_fallback(self, sample_memories):
        """未知模式應回退"""
        result = search_memory_semantic(
            "auth",
            project="test",
            limit=5,
            rerank_mode='unknown_mode'
        )

        # 未知模式回退，但如果候選不足也可能是 fts5_only
        assert result['mode'] in ['fallback', 'fts5_only']
        assert 'results' in result


class TestMemoryEmbeddingsModule:
    """測試 memory_embeddings 模組"""

    def test_is_available_function(self):
        """is_available 應返回布林值"""
        from servers.memory_embeddings import is_available
        result = is_available()
        assert isinstance(result, bool)

    def test_cosine_similarity_identical(self):
        """相同向量的餘弦相似度應為 1"""
        from servers.memory_embeddings import cosine_similarity
        vec = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self):
        """正交向量的餘弦相似度應為 0"""
        from servers.memory_embeddings import cosine_similarity
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(vec1, vec2)) < 0.0001

    def test_cosine_similarity_opposite(self):
        """反向向量的餘弦相似度應為 -1"""
        from servers.memory_embeddings import cosine_similarity
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        assert abs(cosine_similarity(vec1, vec2) - (-1.0)) < 0.0001

    def test_rerank_by_embedding_fallback(self):
        """嵌入不可用時 rerank_by_embedding 應返回原順序"""
        from servers.memory_embeddings import rerank_by_embedding, is_available

        candidates = [
            {'id': 1, 'title': 'First', 'content': 'First content'},
            {'id': 2, 'title': 'Second', 'content': 'Second content'},
        ]

        result = rerank_by_embedding("query", candidates, limit=2)

        # 不管嵌入是否可用，應返回正確數量
        assert len(result) == 2

        if not is_available():
            # 嵌入不可用時，順序應保持
            assert result[0]['id'] == 1
            assert result[1]['id'] == 2
