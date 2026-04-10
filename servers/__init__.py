"""
HAN System - Server Tools
提供給 Agent 使用的工具庫
"""

import os
import sqlite3
import threading

# 動態計算 han-agents 根目錄和資料庫路徑
# 這樣無論安裝在哪個平台的 skills 目錄，都能正確找到資料庫
HAN_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(HAN_BASE_DIR, 'brain', 'brain.db')
SCHEMA_PATH = os.path.join(HAN_BASE_DIR, 'brain', 'schema.sql')
CACHE_DIR = os.path.join(HAN_BASE_DIR, 'cache', 'embeddings')

_db_initialized = False
_db_init_lock = threading.Lock()


def ensure_db() -> sqlite3.Connection:
    """取得資料庫連線，首次呼叫時自動從 schema.sql 初始化。"""
    global _db_initialized
    if not _db_initialized:
        with _db_init_lock:
            if not _db_initialized:
                if not os.path.exists(BRAIN_DB):
                    _init_db_from_schema()
                _db_initialized = True
    return sqlite3.connect(BRAIN_DB)


def _init_db_from_schema():
    """從 schema.sql 建立全新的資料庫。"""
    os.makedirs(os.path.dirname(BRAIN_DB), exist_ok=True)
    conn = sqlite3.connect(BRAIN_DB)
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


from .memory import *
from .tasks import *

__version__ = "1.0.0"
