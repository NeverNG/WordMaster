"""单词图片获取与缓存"""

from pathlib import Path
from typing import Optional

import httpx
from loguru import logger
from PySide6.QtGui import QPixmap

from app.paths import get_cache_dir

CACHE_DIR = get_cache_dir("images")


def get_word_image(word: str) -> Optional[str]:
    """获取单词图片, 返回本地路径. 优先级: 缓存 → 有道 → Pillow 文字图"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = word.lower().strip().replace(" ", "_")

    # 1) 检查缓存
    for ext in [".jpg", ".png"]:
        p = CACHE_DIR / f"{safe}{ext}"
        if p.exists():
            return str(p)

    # 2) 尝试有道 pic_dict
    path = _fetch_from_youdao(word, safe)
    if path:
        return path

    # 3) Pillow 文字占位图
    path = _generate_placeholder(word, safe)
    if path:
        return path

    return None


def _fetch_from_youdao(word: str, safe: str) -> Optional[str]:
    try:
        resp = httpx.get(
            f"https://dict.youdao.com/jsonapi_s?doctype=json&jsonversion=4&q={word.lower().strip()}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://dict.youdao.com/"},
            timeout=6.0,
        )
        data = resp.json()
        api_inp = data.get("input", "").lower().strip()
        if api_inp and api_inp == word.lower().strip():
            pics = data.get("pic_dict", {}).get("pic", [])
            if pics:
                img_url = pics[0].get("image", "")
                if img_url:
                    ir = httpx.get(img_url, timeout=8.0)
                    ir.raise_for_status()
                    local = CACHE_DIR / f"{safe}.jpg"
                    local.write_bytes(ir.content)
                    logger.info(f"[Image] 有道下载: {local.name}")
                    return str(local)
    except Exception as e:
        logger.debug(f"[Image] 有道无图: {e}")
    return None


def _generate_placeholder(word: str, safe: str) -> Optional[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (160, 120), color=(232, 232, 232))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
        text = word.upper()
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (160 - (bbox[2] - bbox[0])) / 2
        y = (120 - (bbox[3] - bbox[1])) / 2
        draw.text((x, y), text, fill=(153, 153, 153), font=font)
        local = CACHE_DIR / f"{safe}.png"
        img.save(str(local))
        logger.info(f"[Image] 文字图: {local.name}")
        return str(local)
    except Exception as e:
        logger.warning(f"[Image] 文字图失败: {e}")
    return None


def load_pixmap(path: str) -> Optional[QPixmap]:
    """加载图片为 QPixmap"""
    p = QPixmap(path)
    return p if not p.isNull() else None
