"""学习进度持久化 — session.json 读写"""

from pathlib import Path
import json
from typing import Optional

from loguru import logger

from app.paths import get_cache_dir

SESSION_PATH = get_cache_dir() / "session.json"


def save_progress(word_id: int, level: str, position: int) -> None:
    """保存当前等级的学习进度"""
    try:
        state = {}
        if SESSION_PATH.exists():
            state = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        progress = state.get("progress", {})
        progress[level] = {"last_word_id": word_id, "position": position}
        state["current_level"] = level
        state["progress"] = progress
        SESSION_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Session] 保存失败: {e}")


def load_progress(level: str) -> Optional[dict]:
    """加载指定等级的进度, 返回 {last_word_id, position} 或 None"""
    if not SESSION_PATH.exists():
        return None
    try:
        state = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        return state.get("progress", {}).get(level)
    except Exception as e:
        logger.warning(f"[Session] 读取失败: {e}")
        return None


def load_current_level() -> str:
    """加载上次选中的等级"""
    if not SESSION_PATH.exists():
        return ""
    try:
        state = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        return state.get("current_level", "")
    except Exception:
        return ""


def clear_session() -> None:
    """清除所有学习进度"""
    try:
        SESSION_PATH.unlink(missing_ok=True)
    except Exception:
        pass
