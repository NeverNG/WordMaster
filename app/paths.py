"""路径工具 — 统一获取程序根目录和缓存目录"""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """返回程序根目录
    
    开发环境: wordmaster/app/
    打包环境: dist/WordMaster/_internal/ (Python 模块所在目录)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "_internal"
    return Path(__file__).resolve().parent  # paths.py → app/


def get_cache_dir(*parts: str) -> Path:
    """返回缓存目录下的子路径, 自动创建
    
    get_cache_dir("audio") → cache/audio/
    get_cache_dir()        → cache/
    """
    path = get_app_dir() / "cache"
    for p in parts:
        path = path / p
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    """返回数据库文件路径 (持久数据，与缓存分离)"""
    path = get_app_dir().parent / "app" / "db" / "words.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
