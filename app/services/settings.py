"""通用设置持久化 — settings.json 读写"""

from pathlib import Path
import json
from typing import Tuple
from loguru import logger

from app.paths import get_cache_dir

SETTINGS_PATH = get_cache_dir() / "settings.json"

DEFAULT_WORD_REPEAT = 2
DEFAULT_EXAMPLE_REPEAT = 1

DEFAULT_AUTO_DELAY = 2000  # 毫秒


def _load_all() -> dict:
    """加载全部设置"""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[Settings] 读取失败: {e}")
        return {}


def _save_all(data: dict) -> None:
    """保存全部设置（合并写入）"""
    try:
        old = _load_all()
        old.update(data)
        SETTINGS_PATH.write_text(
            json.dumps(old, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[Settings] 保存失败: {e}")


def load_audio_settings() -> Tuple[int, int]:
    data = _load_all()
    return (
        data.get("word_repeat", DEFAULT_WORD_REPEAT),
        data.get("example_repeat", DEFAULT_EXAMPLE_REPEAT),
    )


def save_audio_settings(word_repeat: int, example_repeat: int) -> None:
    _save_all({"word_repeat": word_repeat, "example_repeat": example_repeat})



def load_auto_delay() -> int:
    return _load_all().get("auto_delay", DEFAULT_AUTO_DELAY)


def save_auto_delay(delay: int) -> None:
    _save_all({"auto_delay": delay})
