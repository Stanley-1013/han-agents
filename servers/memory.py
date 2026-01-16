"""
Memory Server - 記憶管理工具
"""

import sqlite3
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

# 動態計算資料庫路徑（相對於此模組位置）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(_BASE_DIR, 'brain', 'brain.db')

SCHEMA = """
=== Memory Server ===

# 語義增強搜尋（推薦用於重要查詢）
search_memory_semantic(query, project=None, limit=5, rerank_mode='claude', **kwargs) -> Dict
    語義增強搜尋 - 混合 FTS5 召回 + 語義重排

    Parameters:
        query: 搜尋查詢
        project: 專案名稱 (可選)
        limit: 回傳筆數
        rerank_mode: 重排模式
            - 'claude': 返回候選 + prompt（由 Agent 執行重排）⭐ 推薦
            - 'embedding': 使用本地嵌入模型（需安裝 sentence-transformers）
            - 'none': 純 FTS5（等同 search_memory）
        **kwargs: 傳遞給 search_memory 的其他參數（category, status, branch_flow 等）

    Returns (claude 模式):
        {
            'candidates': [...],     # 20 條候選記憶
            'rerank_prompt': str,    # 重排提示詞
            'mode': 'claude_rerank'
        }

    Returns (embedding/none 模式):
        {
            'results': [...],        # 重排後的結果
            'mode': 'embedding_rerank' | 'fts5_only' | 'fts5_fallback'
        }

    使用範例 (claude 模式):
        result = search_memory_semantic("authentication error handling", rerank_mode='claude')
        if result['mode'] == 'claude_rerank':
            print(result['rerank_prompt'])
            # Agent 輸出：[2, 0, 5]
            # 然後取 result['candidates'][2], result['candidates'][0], result['candidates'][5]
        else:
            memories = result['results']

# 標準全文搜尋
search_memory(query, project=None, category=None, limit=5, status='active', include_all=False,
              branch_flow=None, branch_domain=None, branch_page=None) -> List[Dict]
    全文搜尋長期記憶

    Parameters:
        query: 搜尋關鍵字
        project: 專案名稱 (可選)
        category: 類別過濾 ('sop', 'knowledge', 'error', 'preference')
        limit: 回傳筆數上限
        status: 狀態過濾 ('active' 預設)
        include_all: 設為 True 時搜尋所有狀態
        branch_flow: Flow ID 過濾 (可選，如 'flow.auth')
        branch_domain: Domain ID 過濾 (可選，如 'domain.user')
        branch_page: Page ID 過濾 (可選，如 'page.login')

    Returns: [{id, category, title, content, importance, access_count, branch_flow, branch_domain}]

store_memory(category, content, title=None, project=None, importance=5,
             branch_flow=None, branch_domain=None, branch_page=None) -> int
    儲存到長期記憶

    Parameters:
        category: 'sop', 'knowledge', 'error', 'preference', 'skill'
        content: 記憶內容
        title: 標題 (可選)
        project: 專案名稱 (可選，NULL 為全局)
        importance: 重要性 1-10
        branch_flow: 關聯的 Flow ID (可選，如 'flow.auth')
        branch_domain: 關聯的 Domain ID (可選，如 'domain.user')
        branch_page: 關聯的 Page ID (可選，如 'page.login')

    Returns: memory_id

calculate_similarity(text1, text2) -> float
    計算兩段文本的相似度（詞彙重疊率）

    使用算法：Jaccard 相似度（詞彙重疊率）
    - 將文本轉換為單詞集合（簡單分詞）
    - 計算交集與聯集的比率
    - 適用於小規模記憶庫（本地化）
    - 限制：不支援同義詞識別、特殊字符處理有限

    Parameters:
        text1: 第一段文本
        text2: 第二段文本

    Returns: 0.0-1.0 的相似度分數

find_similar_memories(content, category=None, threshold=0.7, limit=5) -> List[Dict]
    查找相似的現有記憶

    Parameters:
        content: 要對比的內容
        category: 限制在特定類別 (可選)
        threshold: 相似度閾值 (0.0-1.0)
        limit: 回傳筆數上限

    Returns: [{id, title, content, category, similarity_score}]

store_memory_smart(category, content, title=None, project=None, importance=5, auto_supersede=True) -> Dict
    智慧儲存：先檢查是否有相似記憶

    Parameters:
        category: 記憶類別
        content: 記憶內容
        title: 標題 (可選)
        project: 專案名稱 (可選)
        importance: 重要性 1-10
        auto_supersede: 是否自動標記舊記憶為 superseded

    Returns: {id, action, superseded_ids}
        - action: 'created' 或 'superseded'
        - superseded_ids: 被替代的記憶 ID 列表

challenge_memory(memory_id, reason, challenger='system') -> Dict
    將記憶標記為「被挑戰」狀態

    Parameters:
        memory_id: 要挑戰的記憶 ID
        reason: 挑戰原因
        challenger: 挑戰者識別 (預設 'system')

    Returns: {success, memory_id, previous_status}

resolve_challenge(memory_id, resolution, new_content=None) -> Dict
    處理被挑戰的記憶

    Parameters:
        memory_id: 記憶 ID
        resolution: 'keep' | 'update' | 'deprecate'
        new_content: 新內容 (當 resolution='update' 時必須提供)

    Returns: {success, memory_id, resolution, new_status}

deprecate_memory(memory_id, reason=None) -> Dict
    直接廢棄記憶（不經過 challenge 流程）

    Parameters:
        memory_id: 記憶 ID
        reason: 廢棄原因 (可選)

    Returns: {success, memory_id}

get_challenged_memories(project=None, limit=10) -> List[Dict]
    取得所有被挑戰的記憶

    Parameters:
        project: 專案名稱過濾 (可選)
        limit: 回傳筆數上限

    Returns: [{id, title, content, category, challenged_at}]

validate_memory(memory_id) -> Dict
    更新 last_validated 為當前時間

    Parameters:
        memory_id: 記憶 ID

    Returns: {success, memory_id, validated_at}

get_working_memory(task_id, key=None) -> Dict | Any
    讀取工作記憶

set_working_memory(task_id, key, value, project=None) -> None
    設定工作記憶

add_episode(project, event_type, summary, details=None, session_id=None) -> int
    記錄事件到情節記憶

get_recent_episodes(project, limit=5) -> List[Dict]
    取得最近的情節記憶
"""

def get_db():
    """取得資料庫連線"""
    return sqlite3.connect(BRAIN_DB)

def calculate_similarity(text1: str, text2: str) -> float:
    """計算兩段文本的相似度（詞彙重疊率）

    使用簡單的詞彙重疊率演算法：
    - 將文本轉換為單詞集合
    - 計算交集與聯集的比率（Jaccard 相似度）
    - 適用於小規模記憶庫
    - 限制：不支援同義詞識別

    Args:
        text1: 第一段文本
        text2: 第二段文本

    Returns:
        0.0-1.0 的相似度分數
    """
    # 標準化：轉小寫、分詞
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    # 如果都是空集合，相似度為 1.0
    if not words1 and not words2:
        return 1.0

    # 計算 Jaccard 相似度：交集 / 聯集
    intersection = len(words1 & words2)
    union = len(words1 | words2)

    if union == 0:
        return 0.0

    return intersection / union

def find_similar_memories(content: str, category: str = None,
                         threshold: float = 0.7, limit: int = 5) -> List[Dict]:
    """查找相似的現有記憶

    Args:
        content: 要對比的內容
        category: 限制在特定類別 (可選)
        threshold: 相似度閾值 (0.0-1.0)
        limit: 回傳筆數上限

    Returns:
        [{id, title, content, category, similarity_score}] - 按相似度降序排列
    """
    db = get_db()
    cursor = db.cursor()

    # 查詢所有 active 記憶
    sql = '''
        SELECT id, title, content, category
        FROM long_term_memory
        WHERE status = 'active'
    '''

    if category:
        sql += ' AND category = ?'
        cursor.execute(sql, (category,))
    else:
        cursor.execute(sql)

    rows = cursor.fetchall()
    db.close()

    # 計算相似度
    similar = []
    for row in rows:
        memory_id, title, stored_content, mem_category = row
        similarity = calculate_similarity(content, stored_content)

        if similarity >= threshold:
            similar.append({
                'id': memory_id,
                'title': title,
                'content': stored_content,
                'category': mem_category,
                'similarity_score': round(similarity, 3)
            })

    # 按相似度降序排列，回傳 limit 筆
    similar.sort(key=lambda x: x['similarity_score'], reverse=True)
    return similar[:limit]

def search_memory(query: str, project: str = None,
                  category: str = None, limit: int = 5,
                  status: str = 'active', include_all: bool = False,
                  branch_flow: str = None, branch_domain: str = None,
                  branch_page: str = None) -> List[Dict]:
    """全文搜尋長期記憶

    Args:
        query: 搜尋關鍵字
        project: 專案名稱 (可選)
        category: 類別過濾 (可選)
        limit: 回傳筆數上限
        status: 狀態過濾，預設 'active'
        include_all: 設為 True 時搜尋所有狀態
        branch_flow: Flow ID 過濾 (可選，如 'flow.auth')
        branch_domain: Domain ID 過濾 (可選，如 'domain.user')
        branch_page: Page ID 過濾 (可選，如 'page.login')
    """
    db = get_db()
    cursor = db.cursor()

    # FTS5 查詢 - 加上 * 做前綴匹配
    fts_query = ' OR '.join([f'{word}*' for word in query.split()])

    sql = '''
        SELECT ltm.id, ltm.category, ltm.title, ltm.content,
               ltm.importance, ltm.access_count,
               ltm.branch_flow, ltm.branch_domain
        FROM long_term_memory ltm
        JOIN memory_fts fts ON ltm.id = fts.rowid
        WHERE memory_fts MATCH ?
    '''
    params = [fts_query]

    if project:
        sql += ' AND (ltm.project = ? OR ltm.project IS NULL)'
        params.append(project)

    if category:
        sql += ' AND ltm.category = ?'
        params.append(category)

    # 狀態過濾
    if not include_all:
        sql += ' AND ltm.status = ?'
        params.append(status)

    # Branch 過濾（Story 2: Memory 查詢增強）
    if branch_flow:
        sql += ' AND (ltm.branch_flow = ? OR ltm.branch_flow IS NULL)'
        params.append(branch_flow)

    if branch_domain:
        sql += ' AND (ltm.branch_domain = ? OR ltm.branch_domain IS NULL)'
        params.append(branch_domain)

    if branch_page:
        sql += ' AND (ltm.branch_page = ? OR ltm.branch_page IS NULL)'
        params.append(branch_page)

    sql += ' ORDER BY rank LIMIT ?'
    params.append(limit)

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'category': row[1],
            'title': row[2],
            'content': row[3],
            'importance': row[4],
            'access_count': row[5],
            'branch_flow': row[6],
            'branch_domain': row[7]
        })
        # 更新存取計數
        cursor.execute('''
            UPDATE long_term_memory
            SET access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (row[0],))

    db.commit()
    db.close()
    return results


def search_memory_semantic(
    query: str,
    project: str = None,
    limit: int = 5,
    rerank_mode: str = 'claude',
    **kwargs
) -> Dict:
    """語義增強搜尋

    混合搜尋架構：
    1. FTS5 召回 - 快速取 top 30 候選
    2. 語義重排 - Claude 或本地嵌入模型
    3. 返回 top K 結果

    Args:
        query: 搜尋查詢
        project: 專案名稱 (可選)
        limit: 最終回傳數量
        rerank_mode: 重排模式
            - 'claude': 返回候選 + rerank prompt（由呼叫方執行）
            - 'embedding': 使用本地嵌入模型重排
            - 'none': 純 FTS5，等同原 search_memory()
        **kwargs: 傳遞給 search_memory 的其他參數

    Returns:
        {
            'results': [...],           # 最終結果（embedding/none 模式）
            'candidates': [...],        # 候選記憶（claude 模式）
            'rerank_prompt': str,       # 重排提示（claude 模式）
            'mode': str                 # 使用的模式
        }
    """
    # 空查詢處理
    if not query or not query.strip():
        return {
            'results': [],
            'mode': 'fts5_only'
        }

    # Step 1: FTS5 召回（擴大範圍）
    candidates = search_memory(query, project, limit=30, **kwargs)

    # 候選不足或不需重排時，直接返回
    if rerank_mode == 'none' or len(candidates) <= limit:
        return {
            'results': candidates[:limit],
            'mode': 'fts5_only'
        }

    if rerank_mode == 'claude':
        # 準備 Claude 重排 prompt
        rerank_context = "\n".join([
            f"[{i}] **{c.get('title', 'Untitled')}**: {c['content'][:150]}..."
            for i, c in enumerate(candidates[:20])
        ])

        return {
            'candidates': candidates[:20],
            'rerank_prompt': f"""根據查詢「{query}」的語義相關性，選出最相關的 {limit} 條記憶。

{rerank_context}

請返回最相關的記憶編號，格式：[0, 3, 7, ...]""",
            'mode': 'claude_rerank'
        }

    if rerank_mode == 'embedding':
        # 使用本地嵌入模型重排
        try:
            from servers.memory_embeddings import rerank_by_embedding, is_available
            if is_available():
                reranked = rerank_by_embedding(query, candidates, limit)
                return {
                    'results': reranked,
                    'mode': 'embedding_rerank'
                }
            else:
                # 嵌入模型不可用，降級為 FTS5
                return {
                    'results': candidates[:limit],
                    'mode': 'fts5_fallback'
                }
        except ImportError:
            # 模組不存在，降級為 FTS5
            return {
                'results': candidates[:limit],
                'mode': 'fts5_fallback'
            }

    # 未知模式，回退為 FTS5
    return {'results': candidates[:limit], 'mode': 'fallback'}


def store_memory(category: str, content: str, title: str = None,
                 project: str = None, subcategory: str = None,
                 importance: int = 5, branch_flow: str = None,
                 branch_domain: str = None, branch_page: str = None) -> int:
    """儲存到長期記憶

    Args:
        category: 記憶類別 ('sop', 'knowledge', 'error', 'preference', 'skill')
        content: 記憶內容
        title: 標題 (可選)
        project: 專案名稱 (可選，NULL 為全局)
        subcategory: 子類別 (可選)
        importance: 重要性 1-10
        branch_flow: 關聯的 Flow ID (可選，如 'flow.auth')
        branch_domain: 關聯的 Domain ID (可選，如 'domain.user')
        branch_page: 關聯的 Page ID (可選，如 'page.login')

    Returns:
        memory_id: 新建記憶的 ID
    """
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        INSERT INTO long_term_memory
        (category, subcategory, project, title, content, importance,
         branch_flow, branch_domain, branch_page)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (category, subcategory, project, title, content, importance,
          branch_flow, branch_domain, branch_page))

    memory_id = cursor.lastrowid
    db.commit()
    db.close()
    return memory_id

def store_memory_smart(category: str, content: str, title: str = None,
                      project: str = None, importance: int = 5,
                      auto_supersede: bool = True) -> Dict:
    """智慧儲存：先檢查是否有相似記憶

    流程：
    1. 查找相似記憶 (相似度 >= 0.7)
    2. 如果找到且 auto_supersede=True：
       - 將舊記憶狀態設為 'superseded'
       - 記錄 superseded_by 指向新記憶
    3. 建立新記憶

    並發控制：使用 EXCLUSIVE 事務鎖確保原子性

    Args:
        category: 記憶類別
        content: 記憶內容
        title: 標題 (可選)
        project: 專案名稱 (可選)
        importance: 重要性 1-10
        auto_supersede: 是否自動標記舊記憶為 superseded

    Returns:
        {
            'id': int,              # 新建記憶 ID
            'action': str,          # 'created' 或 'superseded'
            'superseded_ids': []    # 被替代的記憶 ID 列表
        }
    """
    # 查找相似記憶
    similar_memories = find_similar_memories(
        content,
        category=category,
        threshold=0.7,
        limit=10
    )

    superseded_ids = []

    if similar_memories and auto_supersede:
        db = get_db()
        cursor = db.cursor()

        try:
            # 使用 EXCLUSIVE 事務鎖確保並發控制
            cursor.execute('BEGIN EXCLUSIVE')

            # 先建立新記憶
            cursor.execute('''
                INSERT INTO long_term_memory
                (category, project, title, content, importance, status)
                VALUES (?, ?, ?, ?, ?, 'active')
            ''', (category, project, title, content, importance))

            new_memory_id = cursor.lastrowid

            # 標記相似記憶為 superseded
            for similar in similar_memories:
                old_id = similar['id']
                cursor.execute('''
                    UPDATE long_term_memory
                    SET status = 'superseded', superseded_by = ?
                    WHERE id = ?
                ''', (new_memory_id, old_id))
                superseded_ids.append(old_id)

            db.commit()
            db.close()

            return {
                'id': new_memory_id,
                'action': 'superseded',
                'superseded_ids': superseded_ids
            }

        except Exception as e:
            db.rollback()
            db.close()
            raise e

    else:
        # 沒有相似記憶或 auto_supersede=False，直接建立
        memory_id = store_memory(
            category=category,
            content=content,
            title=title,
            project=project,
            importance=importance
        )

        return {
            'id': memory_id,
            'action': 'created',
            'superseded_ids': []
        }

def challenge_memory(memory_id: int, reason: str, challenger: str = 'system') -> Dict:
    """將記憶標記為「被挑戰」狀態

    流程：
    1. 查詢記憶的當前狀態
    2. 將狀態改為 'challenged'
    3. 記錄挑戰事件到 episodes

    Args:
        memory_id: 要挑戰的記憶 ID
        reason: 挑戰原因
        challenger: 挑戰者識別 (預設 'system')

    Returns:
        {
            'success': bool,
            'memory_id': int,
            'previous_status': str
        }
    """
    db = get_db()
    cursor = db.cursor()

    try:
        # 查詢記憶的當前狀態
        cursor.execute('''
            SELECT status, project, title FROM long_term_memory
            WHERE id = ?
        ''', (memory_id,))

        row = cursor.fetchone()
        if not row:
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': 'Memory not found'
            }

        previous_status, project, title = row

        # 更新狀態為 challenged
        cursor.execute('''
            UPDATE long_term_memory
            SET status = 'challenged'
            WHERE id = ?
        ''', (memory_id,))

        # 記錄挑戰事件到 episodes
        cursor.execute('''
            INSERT INTO episodes (project, event_type, summary, details)
            VALUES (?, 'memory_challenged', ?, ?)
        ''', (project, f"Memory #{memory_id} ({title}) challenged",
              json.dumps({
                  'memory_id': memory_id,
                  'title': title,
                  'reason': reason,
                  'challenger': challenger,
                  'previous_status': previous_status
              })))

        db.commit()
        db.close()

        return {
            'success': True,
            'memory_id': memory_id,
            'previous_status': previous_status
        }

    except Exception as e:
        db.close()
        return {
            'success': False,
            'memory_id': memory_id,
            'error': str(e)
        }

def resolve_challenge(memory_id: int, resolution: str, new_content: str = None) -> Dict:
    """處理被挑戰的記憶

    流程：
    1. 驗證記憶存在且狀態為 'challenged'
    2. 根據 resolution 執行對應操作：
       - 'keep': 恢復為 'active'，更新 last_validated
       - 'update': 更新內容，恢復為 'active'，更新 last_validated
       - 'deprecate': 標記為 'deprecated'
    3. 記錄解決過程到 episodes

    Args:
        memory_id: 記憶 ID
        resolution: 解決方式 ('keep', 'update', 'deprecate')
        new_content: 新內容 (當 resolution='update' 時必須提供)

    Returns:
        {
            'success': bool,
            'memory_id': int,
            'resolution': str,
            'new_status': str
        }
    """
    db = get_db()
    cursor = db.cursor()

    try:
        # 驗證記憶存在且狀態為 challenged
        cursor.execute('''
            SELECT status, project, title, content FROM long_term_memory
            WHERE id = ?
        ''', (memory_id,))

        row = cursor.fetchone()
        if not row:
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': 'Memory not found'
            }

        current_status, project, title, current_content = row

        if current_status != 'challenged':
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': f'Memory status is {current_status}, not challenged'
            }

        # 根據 resolution 執行操作
        if resolution == 'keep':
            cursor.execute('''
                UPDATE long_term_memory
                SET status = 'active', last_validated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (memory_id,))
            new_status = 'active'

        elif resolution == 'update':
            if new_content is None:
                db.close()
                return {
                    'success': False,
                    'memory_id': memory_id,
                    'error': 'new_content required for update resolution'
                }

            cursor.execute('''
                UPDATE long_term_memory
                SET status = 'active', content = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    last_validated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_content, memory_id))
            new_status = 'active'

        elif resolution == 'deprecate':
            cursor.execute('''
                UPDATE long_term_memory
                SET status = 'deprecated'
                WHERE id = ?
            ''', (memory_id,))
            new_status = 'deprecated'

        else:
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': f'Invalid resolution: {resolution}'
            }

        # 記錄解決過程到 episodes
        cursor.execute('''
            INSERT INTO episodes (project, event_type, summary, details)
            VALUES (?, 'challenge_resolved', ?, ?)
        ''', (project, f"Challenge resolved for memory #{memory_id}",
              json.dumps({
                  'memory_id': memory_id,
                  'title': title,
                  'resolution': resolution,
                  'new_status': new_status
              })))

        db.commit()
        db.close()

        return {
            'success': True,
            'memory_id': memory_id,
            'resolution': resolution,
            'new_status': new_status
        }

    except Exception as e:
        db.close()
        return {
            'success': False,
            'memory_id': memory_id,
            'error': str(e)
        }

def deprecate_memory(memory_id: int, reason: str = None) -> Dict:
    """直接廢棄記憶（不經過 challenge 流程）

    流程：
    1. 驗證記憶存在
    2. 將狀態設為 'deprecated'
    3. 記錄廢棄事件到 episodes

    Args:
        memory_id: 記憶 ID
        reason: 廢棄原因 (可選)

    Returns:
        {
            'success': bool,
            'memory_id': int
        }
    """
    db = get_db()
    cursor = db.cursor()

    try:
        # 驗證記憶存在
        cursor.execute('''
            SELECT project, title FROM long_term_memory
            WHERE id = ?
        ''', (memory_id,))

        row = cursor.fetchone()
        if not row:
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': 'Memory not found'
            }

        project, title = row

        # 更新狀態為 deprecated
        cursor.execute('''
            UPDATE long_term_memory
            SET status = 'deprecated'
            WHERE id = ?
        ''', (memory_id,))

        # 記錄廢棄事件到 episodes
        cursor.execute('''
            INSERT INTO episodes (project, event_type, summary, details)
            VALUES (?, 'memory_deprecated', ?, ?)
        ''', (project, f"Memory #{memory_id} ({title}) deprecated",
              json.dumps({
                  'memory_id': memory_id,
                  'title': title,
                  'reason': reason
              })))

        db.commit()
        db.close()

        return {
            'success': True,
            'memory_id': memory_id
        }

    except Exception as e:
        db.close()
        return {
            'success': False,
            'memory_id': memory_id,
            'error': str(e)
        }

def get_challenged_memories(project: str = None, limit: int = 10) -> List[Dict]:
    """取得所有被挑戰的記憶

    Args:
        project: 專案名稱過濾 (可選)
        limit: 回傳筆數上限

    Returns:
        [{id, title, content, category, challenged_at}]
    """
    db = get_db()
    cursor = db.cursor()

    sql = '''
        SELECT id, title, content, category, updated_at
        FROM long_term_memory
        WHERE status = 'challenged'
    '''
    params = []

    if project:
        sql += ' AND (project = ? OR project IS NULL)'
        params.append(project)

    sql += ' ORDER BY updated_at DESC LIMIT ?'
    params.append(limit)

    cursor.execute(sql, params)
    results = []

    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'title': row[1],
            'content': row[2],
            'category': row[3],
            'challenged_at': row[4]
        })

    db.close()
    return results

def validate_memory(memory_id: int) -> Dict:
    """更新 last_validated 為當前時間

    用於定期驗證記憶仍然有效。當驗證成功時，更新 last_validated 時間戳。

    Args:
        memory_id: 記憶 ID

    Returns:
        {
            'success': bool,
            'memory_id': int,
            'validated_at': str (ISO timestamp)
        }
    """
    db = get_db()
    cursor = db.cursor()

    try:
        # 驗證記憶存在
        cursor.execute('''
            SELECT id FROM long_term_memory
            WHERE id = ?
        ''', (memory_id,))

        if not cursor.fetchone():
            db.close()
            return {
                'success': False,
                'memory_id': memory_id,
                'error': 'Memory not found'
            }

        # 更新 last_validated 為當前時間
        cursor.execute('''
            UPDATE long_term_memory
            SET last_validated = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (memory_id,))

        db.commit()

        # 取得更新後的時間戳
        cursor.execute('''
            SELECT last_validated FROM long_term_memory
            WHERE id = ?
        ''', (memory_id,))

        validated_at = cursor.fetchone()[0]
        db.close()

        return {
            'success': True,
            'memory_id': memory_id,
            'validated_at': validated_at
        }

    except Exception as e:
        db.close()
        return {
            'success': False,
            'memory_id': memory_id,
            'error': str(e)
        }

def get_working_memory(task_id: str, key: str = None) -> Any:
    """讀取工作記憶"""
    db = get_db()
    cursor = db.cursor()

    if key:
        cursor.execute('''
            SELECT value, data_type FROM working_memory
            WHERE task_id = ? AND key = ?
        ''', (task_id, key))
        row = cursor.fetchone()
        db.close()
        if row:
            return json.loads(row[0]) if row[1] == 'json' else row[0]
        return None
    else:
        cursor.execute('''
            SELECT key, value, data_type FROM working_memory
            WHERE task_id = ?
        ''', (task_id,))
        result = {
            row[0]: json.loads(row[1]) if row[2] == 'json' else row[1]
            for row in cursor.fetchall()
        }
        db.close()
        return result

def set_working_memory(task_id: str, key: str, value: Any,
                       project: str = None) -> None:
    """設定工作記憶"""
    db = get_db()
    cursor = db.cursor()

    data_type = 'json' if isinstance(value, (dict, list)) else 'string'
    stored_value = json.dumps(value) if data_type == 'json' else str(value)

    # 檢查是否存在
    cursor.execute('''
        SELECT id FROM working_memory WHERE task_id = ? AND key = ?
    ''', (task_id, key))

    if cursor.fetchone():
        cursor.execute('''
            UPDATE working_memory
            SET value = ?, data_type = ?
            WHERE task_id = ? AND key = ?
        ''', (stored_value, data_type, task_id, key))
    else:
        cursor.execute('''
            INSERT INTO working_memory (task_id, project, key, value, data_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_id, project, key, stored_value, data_type))

    db.commit()
    db.close()

def clear_working_memory(task_id: str) -> None:
    """清除任務的工作記憶"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('DELETE FROM working_memory WHERE task_id = ?', (task_id,))
    db.commit()
    db.close()

def add_episode(project: str, event_type: str, summary: str,
                details: Dict = None, session_id: str = None) -> int:
    """記錄事件到情節記憶"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        INSERT INTO episodes (project, session_id, event_type, summary, details)
        VALUES (?, ?, ?, ?, ?)
    ''', (project, session_id, event_type, summary,
          json.dumps(details) if details else None))

    episode_id = cursor.lastrowid
    db.commit()
    db.close()
    return episode_id

def get_recent_episodes(project: str, limit: int = 5) -> List[Dict]:
    """取得最近的情節記憶"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        SELECT id, event_type, summary, details, timestamp
        FROM episodes
        WHERE project = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (project, limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'event_type': row[1],
            'summary': row[2],
            'details': json.loads(row[3]) if row[3] else None,
            'timestamp': row[4]
        })

    db.close()
    return results

def save_checkpoint(project: str, task_id: str, agent: str,
                    state: Dict, summary: str) -> int:
    """儲存 checkpoint"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        INSERT INTO checkpoints (project, task_id, agent, state, context_summary)
        VALUES (?, ?, ?, ?, ?)
    ''', (project, task_id, agent, json.dumps(state), summary))

    checkpoint_id = cursor.lastrowid
    db.commit()
    db.close()
    return checkpoint_id

def load_checkpoint(task_id: str) -> Optional[Dict]:
    """載入最新的 checkpoint"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        SELECT state, context_summary, created_at
        FROM checkpoints
        WHERE task_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (task_id,))

    row = cursor.fetchone()
    db.close()

    if row:
        return {
            'state': json.loads(row[0]),
            'summary': row[1],
            'created_at': row[2]
        }
    return None

def get_project_context(project: str) -> Dict:
    """取得專案的完整上下文（用於斷點重連）

    整合三層資訊：
    1. 進行中的任務
    2. 最近的階段完成記錄
    3. 最近活動

    Args:
        project: 專案名稱

    Returns:
        {
            'active_tasks': [...],      # 進行中任務
            'last_phase': {...},        # 最近的階段完成記錄
            'recent_activity': [...],   # 最近活動
            'suggestion': str           # 建議的下一步
        }
    """
    # 延遲 import 避免循環依賴
    from servers.tasks import get_active_tasks_for_project

    # 1. 查進行中任務
    active_tasks = get_active_tasks_for_project(project)

    # 2. 查最近 episodes
    recent_episodes = get_recent_episodes(project, limit=5)

    # 3. 找「階段完成」類型的 episode
    phase_complete = [e for e in recent_episodes
                      if e['event_type'] == 'phase_complete']
    last_phase = phase_complete[0] if phase_complete else None

    # 4. 生成建議
    suggestion = None
    if active_tasks:
        task = active_tasks[0]
        suggestion = f"繼續任務：{task['description'][:30]}... ({task['progress']})"
    elif last_phase:
        details = last_phase.get('details', {})
        next_steps = details.get('next_steps', [])
        if next_steps:
            suggestion = f"上次完成：{last_phase['summary']}。建議下一步：{next_steps[0]}"
        else:
            suggestion = f"上次完成：{last_phase['summary']}"

    return {
        'active_tasks': active_tasks,
        'last_phase': last_phase,
        'recent_activity': recent_episodes,
        'suggestion': suggestion
    }


__all__ = [
    'SCHEMA',
    'search_memory',
    'search_memory_semantic',
    'store_memory',
    'calculate_similarity',
    'find_similar_memories',
    'store_memory_smart',
    'challenge_memory',
    'resolve_challenge',
    'deprecate_memory',
    'get_challenged_memories',
    'validate_memory',
    'get_working_memory',
    'set_working_memory',
    'clear_working_memory',
    'add_episode',
    'get_recent_episodes',
    'save_checkpoint',
    'load_checkpoint',
    'get_project_context'
]
