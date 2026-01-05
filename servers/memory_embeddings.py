"""
記憶嵌入模組 - 提供語義搜尋能力

依賴安裝（可選）：
pip install sentence-transformers numpy

如未安裝依賴，所有函數會優雅降級，返回空結果或原始順序。
"""

import os
from typing import List, Dict, Optional

# 嵌入模型配置
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384
CACHE_DIR = os.path.expanduser("~/.claude/neuromorphic/cache/embeddings")

_model = None  # 延遲載入


def get_model():
    """延遲載入嵌入模型

    Returns:
        SentenceTransformer 模型實例，或 None（如未安裝依賴）
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(EMBEDDING_MODEL)
        except ImportError:
            return None
    return _model


def get_embedding(text: str) -> Optional[List[float]]:
    """計算文本嵌入向量

    Args:
        text: 要嵌入的文本

    Returns:
        嵌入向量（384 維浮點數列表），或 None（如模型不可用）
    """
    model = get_model()
    if model is None:
        return None
    return model.encode(text).tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """計算餘弦相似度

    Args:
        a: 向量 A
        b: 向量 B

    Returns:
        餘弦相似度（-1.0 到 1.0）
    """
    try:
        import numpy as np
        a_arr, b_arr = np.array(a), np.array(b)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
    except ImportError:
        # numpy 不可用，使用純 Python 實作
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def rerank_by_embedding(
    query: str,
    candidates: List[Dict],
    limit: int = 5
) -> List[Dict]:
    """使用嵌入向量重排候選記憶

    Args:
        query: 搜尋查詢
        candidates: FTS5 召回的候選記憶
        limit: 返回數量

    Returns:
        重排後的記憶列表，每個記憶添加 'semantic_score' 欄位
    """
    query_emb = get_embedding(query)
    if query_emb is None:
        # 嵌入模型不可用，返回原順序
        return candidates[:limit]

    # 計算每個候選的相似度
    scored = []
    for c in candidates:
        # 優先使用快取的嵌入（如果 DB 中有存儲）
        if 'embedding' in c and c['embedding']:
            emb = c['embedding']
        else:
            # 即時計算（較慢）
            text = (c.get('title', '') or '') + ' ' + (c.get('content', '') or '')[:500]
            emb = get_embedding(text)

        if emb:
            score = cosine_similarity(query_emb, emb)
            scored.append((c, score))
        else:
            scored.append((c, 0.0))

    # 按相似度降序排列
    scored.sort(key=lambda x: x[1], reverse=True)

    # 添加相似度分數到結果
    results = []
    for c, score in scored[:limit]:
        # 創建副本避免修改原始數據
        result = dict(c)
        result['semantic_score'] = round(score, 4)
        results.append(result)

    return results


def batch_get_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """批次計算多個文本的嵌入向量

    Args:
        texts: 文本列表

    Returns:
        嵌入向量列表，每個元素對應輸入的文本
    """
    model = get_model()
    if model is None:
        return [None] * len(texts)

    embeddings = model.encode(texts)
    return [emb.tolist() for emb in embeddings]


def is_available() -> bool:
    """檢查嵌入功能是否可用

    Returns:
        True 如果 sentence-transformers 已安裝且可用
    """
    return get_model() is not None


__all__ = [
    'EMBEDDING_MODEL',
    'EMBEDDING_DIM',
    'get_model',
    'get_embedding',
    'cosine_similarity',
    'rerank_by_embedding',
    'batch_get_embeddings',
    'is_available'
]
