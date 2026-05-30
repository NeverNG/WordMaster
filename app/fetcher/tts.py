"""Edge TTS 语音生成引擎

调用 edge-tts Python API 生成例句朗读 MP3，进行本地缓存管理。
"""

from pathlib import Path
from typing import Optional

from loguru import logger


# 可用音色:
#   en-GB-SoniaNeural     — 英音 (女)
#   en-GB-RyanNeural      — 英音 (男)
#   en-US-AriaNeural      — 美音 (女)
#   en-US-GuyNeural       — 美音 (男)
#   zh-CN-XiaoxiaoNeural  — 中文 (女)

VOICE_UK = "en-GB-SoniaNeural"
VOICE_US = "en-US-AriaNeural"
VOICE_CN = "zh-CN-XiaoxiaoNeural"


class TTSEngine:
    """Edge TTS 语音生成与缓存"""

    def __init__(self, cache_dir: str | Path = None):
        if cache_dir is None:
            from app.paths import get_cache_dir
            self.cache_dir = get_cache_dir("audio")
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _filename(self, text: str, voice: str) -> str:
        """生成缓存文件名"""
        # 取文本前 60 字符，只保留字母数字下划线
        safe = "".join(c if c.isalnum() or c in "_ -" else "_" for c in text[:60])
        voice_short = voice.replace("-", "_")
        return f"{safe}_{voice_short}.mp3"

    def _cached_path(self, text: str, voice: str) -> Path:
        return self.cache_dir / self._filename(text, voice)

    def _is_cached(self, text: str, voice: str) -> bool:
        return self._cached_path(text, voice).exists()

    def generate(self, text: str, voice: str = VOICE_US, force: bool = False) -> Optional[Path]:
        """生成语音，返回本地 MP3 路径。缓存命中直接返回。"""
        out_path = self._cached_path(text, voice)

        if not force and out_path.exists():
            logger.debug(f"[TTS] 缓存命中: {out_path.name}")
            return out_path

        try:
            # 使用 edge_tts Python API (兼容打包环境，无需 CLI)
            from edge_tts import Communicate
            Communicate(text, voice).save_sync(str(out_path))
            if out_path.exists() and out_path.stat().st_size > 0:
                logger.info(f"[TTS] 生成成功: {out_path.name}")
                return out_path
            else:
                logger.error(f"[TTS] 生成结果为空: {out_path.name}")
                return None
        except ImportError:
            logger.error("[TTS] edge_tts 包未安装: pip install edge-tts")
            return None
        except Exception as e:
            logger.error(f"[TTS] 生成失败 {out_path.name}: {e}")
            return None

    def generate_word(self, word: str, voice: str = VOICE_US) -> Optional[Path]:
        """生成单个单词的发音"""
        return self.generate(word, voice=voice)

    def get_absolute_path(self, filename: str) -> str:
        """根据数据库存储的文件名返回完整路径"""
        return str(self.cache_dir / filename)
