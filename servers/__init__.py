"""
HAN System - Server Tools
提供給 Agent 使用的工具庫
"""

import os

# 動態計算 han-agents 根目錄和資料庫路徑
# 這樣無論安裝在哪個平台的 skills 目錄，都能正確找到資料庫
HAN_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DB = os.path.join(HAN_BASE_DIR, 'brain', 'brain.db')
SCHEMA_PATH = os.path.join(HAN_BASE_DIR, 'brain', 'schema.sql')
CACHE_DIR = os.path.join(HAN_BASE_DIR, 'cache', 'embeddings')

from .memory import *
from .tasks import *

__version__ = "1.0.0"
