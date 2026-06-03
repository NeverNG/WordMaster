"""主窗口 — 装配各 Tab 页面"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from pathlib import Path
import sys
from loguru import logger
from app.services import settings as setsvc

from app.db import WordRepository
from app.audio import AudioPlayer
from app.services import session as sess
from app.ui.learning_tab import LearningTab
from app.ui.management_tab import ManagementTab
from app.ui.stats_tab import StatsTab
from app.ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    """WordMaster 主窗口"""

    def __init__(self, db_path: str):
        super().__init__()
        self.repo = WordRepository(db_path)
        self.audio = AudioPlayer(self)

        self.setWindowTitle("WordMaster")
        self.setFixedSize(420, 380)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

        # PyInstaller 打包后资源在 sys._MEIPASS 下
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).parent.parent))
        icon_path = base / "asset" / "images" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 恢复上次窗口位置
        self._restore_geometry()

        self._build_ui()
        self._init_tabs()

    def _restore_geometry(self):
        data = setsvc._load_all()
        pos = data.get("window_position")
        if pos and len(pos) == 2:
            self.move(pos[0], pos[1])

    def closeEvent(self, event):
        setsvc._save_all({"window_position": [self.x(), self.y()]})
        super().closeEvent(event)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: none; }")
        # 禁用 Tab 切换的左右箭头，避免与学习页快捷键冲突
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.tabs)

        # 创建各 Tab 页
        self.learning_tab = LearningTab(self.repo, self.audio, self)
        self.management_tab = ManagementTab(self.repo, self)
        self.stats_tab = StatsTab(self.repo, self)
        self.settings_tab = SettingsTab(self.repo, self)

        self.tabs.addTab(self.learning_tab, "📖 学习")
        self.tabs.addTab(self.management_tab, "📚 词库")
        self.tabs.addTab(self.stats_tab, "📊 统计")
        self.tabs.addTab(self.settings_tab, "⚙️ 设置")

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _init_tabs(self):
        self.learning_tab.load_levels(select_level=sess.load_current_level())
        self.learning_tab.refresh()
        # 后台预热 librosa/numba JIT，加速首次 FFT 计算
        import threading
        threading.Thread(target=_warmup_librosa, daemon=True).start()

    def _on_tab_changed(self, index: int):
        if index == 0:
            self.learning_tab.refresh()
            self.learning_tab.setFocus()
        elif index == 1:
            self.management_tab.load_level_filter()
            self.management_tab.search()
        elif index == 2:
            self.stats_tab.refresh()



def _warmup_librosa():
    """预先加载 librosa + 预热已有音频的频谱缓存"""
    try:
        import numpy as np
        import librosa
        dummy = np.zeros(22050, dtype=np.float32)
        librosa.stft(dummy, n_fft=2048, hop_length=512)
        from app.services.spectrum import get_spectrum
        import glob, os
        for mp3 in glob.glob(os.path.join("cache", "audio", "*.mp3")):
            get_spectrum(mp3)
    except Exception:
        pass
