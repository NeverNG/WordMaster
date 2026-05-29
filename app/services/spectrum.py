"""音频频谱分析服务 — 使用 librosa 计算真实 FFT"""

from pathlib import Path
from typing import Optional
import json
import math
import numpy as np

from app.paths import get_cache_dir

CACHE_DIR = get_cache_dir("spectrum")


def compute_spectrum(audio_path: str | Path, bands: int = 64, frames: int = 100) -> Optional[list]:
    """读取音频文件并计算 FFT 频谱数据
    
    Args:
        audio_path: MP3 文件路径
        bands: 频率条数量 (默认 64)
        frames: 时间帧数量 (默认 100)
    
    Returns:
        list of list: [time_frame][freq_band] 归一化 0.0~1.0
        None: 失败时返回 None
    """
    import librosa
    try:
        y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    except Exception as e:
        return None
    
    # 计算 STFT
    hop_length = max(1, len(y) // frames)
    D = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length))
    
    # 降到 bands 个频段
    result = []
    for t in range(D.shape[1]):
        frame = D[:, t]
        resampled = np.interp(
            np.linspace(0, len(frame) - 1, bands),
            np.arange(len(frame)),
            frame
        )
        result.append(resampled.tolist())
    
    return result


def get_spectrum(audio_path: str | Path, bands: int = 64, frames: int = 100) -> Optional[list]:
    """获取频谱数据 (优先缓存)
    
    缓存文件: cache/spectrum/{filename}.json
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = Path(audio_path)
    cache_path = CACHE_DIR / f"{audio_path.stem}.json"
    
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    data = compute_spectrum(audio_path, bands, frames)
    if data:
        try:
            cache_path.write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass
    return data


def spectrum_to_bars(spectrum_data: list, position: float, height: int) -> list[int]:
    """根据播放进度将频谱数据转换为柱状图高度"""
    if not spectrum_data:
        return [2] * 80
    
    idx = int(position * len(spectrum_data))
    idx = max(0, min(idx, len(spectrum_data) - 1))
    
    frame = spectrum_data[idx]
    max_val = max(frame) if max(frame) > 0 else 1
    bars = [max(2, int(v / max_val * height * 0.85)) for v in frame]
    return bars
