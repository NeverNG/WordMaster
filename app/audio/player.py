"""音频播放模块

基于 PySide6 的 QMediaPlayer 播放本地缓存 MP3。
支持播放/暂停/停止和播放完成信号。
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from loguru import logger


class AudioPlayer(QObject):
    """本地音频播放器封装"""

    # 信号
    playback_started = Signal(str)       # 参数: 文件名
    playback_finished = Signal(str)      # 参数: 文件名
    playback_error = Signal(str, str)    # 参数: 文件名, 错误消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # 当前播放的文件标识
        self._current_file = ""

        # 连接信号
        self._player.mediaStatusChanged.connect(self._on_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def play(self, file_path: str | Path) -> None:
        """播放音频文件"""
        path = Path(file_path)
        if not path.exists():
            msg = f"音频文件不存在: {path}"
            logger.warning(msg)
            self.playback_error.emit(path.name, msg)
            return

        url = QUrl.fromLocalFile(str(path.absolute()))
        self._current_file = path.name
        self._player.setSource(url)
        self._audio_output.setVolume(0.8)  # 默认音量 80%
        self._player.play()
        self.playback_started.emit(path.name)
        logger.debug(f"[Audio] 播放: {path.name}")

    def stop(self) -> None:
        """停止播放"""
        self._player.stop()
        self._current_file = ""

    def pause(self) -> None:
        """暂停"""
        self._player.pause()

    def resume(self) -> None:
        """恢复"""
        self._player.play()

    def set_volume(self, volume: float) -> None:
        """设置音量 0.0~1.0"""
        self._audio_output.setVolume(max(0.0, min(1.0, volume)))

    @property
    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def current_file(self) -> str:
        return self._current_file

    @property
    def duration(self) -> int:
        """音频总时长（毫秒），未知时返回 -1"""
        return self._player.duration()

    @property
    def position(self) -> int:
        """当前播放位置（毫秒）"""
        return self._player.position()

    # ── 内部回调 ──

    def _on_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.debug(f"[Audio] 播放完成: {self._current_file}")
            self.playback_finished.emit(self._current_file)
            self._current_file = ""

    def _on_error(self, error, error_string):
        if error != QMediaPlayer.Error.NoError:
            logger.error(f"[Audio] 播放错误 [{error}]: {error_string}")
            self.playback_error.emit(self._current_file, error_string)
