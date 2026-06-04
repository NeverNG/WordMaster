"""WordMaster — Windows 桌面背单词工具"""

import sys
import os
from pathlib import Path
from loguru import logger


VERSION = "1.0.3"          # 当前版本号，发布时更新
VERSION_NAME = "v1.0.3"    # 显示用版本名

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))


def _set_taskbar_icon():
    """Windows: 设置任务栏 AppUserModelID，确保图标正确显示"""
    try:
        import ctypes
        app_id = "WordMaster.WordMaster.1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


class _SplashScreen:
    """启动画面 — 含进度条和加载提示 (延迟创建 Qt 对象)"""
    def __init__(self):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
        from PySide6.QtGui import QFont
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QApplication
        self._app = QApplication.instance()
        self._widget = QWidget()
        self._widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self._widget.setFixedSize(360, 160)
        self._widget.setStyleSheet("background: #fff; border: 1px solid #ddd; border-radius: 10px;")
        self._center_widget()

        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        title = QLabel("⏳ WordMaster 启动中...")
        title.setFont(QFont("Microsoft YaHei", 12))
        title.setStyleSheet("color: #333; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self._msg = QLabel("")
        self._msg.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._msg)

        self._bar = QProgressBar()
        self._bar.setFixedHeight(12)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet("""
            QProgressBar { background: #eee; border: none; border-radius: 6px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4caf50, stop:1 #81c784); border-radius: 6px; }
        """)
        layout.addWidget(self._bar)

    def _center_widget(self):
        screen = self._app.primaryScreen().availableGeometry()
        self._widget.move((screen.width() - 360) // 2, (screen.height() - 160) // 2)

    def show(self):
        self._widget.show()
        self.flush()

    def close(self):
        self._widget.close()

    def flush(self):
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def set_progress(self, value: int, text: str):
        """设置进度百分比(0-100)和提示文字"""
        self._bar.setValue(value)
        self._msg.setText(text)
        self.flush()


def _lazy_import(mod_name: str, splash, step: int, total: int, label: str):
    """延迟导入一个模块，显示进度"""
    pct = int(step / total * 100)
    splash.set_progress(pct, f"[{step}/{total}] {label}")
    __import__(mod_name, fromlist=[''])
    splash.flush()


def setup_logging():
    logger.remove()


def main():
    setup_logging()
    _set_taskbar_icon()

    # 启动 GUI 框架
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    app = QApplication(sys.argv)
    app.setApplicationName("WordMaster")
    _icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / "asset" / "images" / "ABC.ico"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    # 启动画面
    splash = _SplashScreen()
    splash.show()
    splash.set_progress(1, "正在启动...")

    # ── 分步加载模块 ──
    modules = [
        ("PySide6.QtCore",          "加载 Qt 核心库..."),
        ("PySide6.QtGui",           "加载 Qt 图形库..."),
        ("PySide6.QtWidgets",       "加载 Qt 界面框架..."),
        ("PySide6.QtNetwork",       "加载 Qt 网络模块..."),
        ("PySide6.QtMultimedia",    "加载 Qt 多媒体模块..."),
        ("PySide6.QtSvg",           "加载 Qt SVG 模块..."),
        ("numpy",                   "加载科学计算引擎 (numpy)..."),
        ("scipy",                   "加载科学计算扩展 (scipy)..."),
        ("librosa",                 "加载音频分析引擎 (librosa)..."),
        ("httpx",                   "加载网络请求模块..."),
        ("edge_tts",                "加载语音合成模块..."),
        ("app.paths",               "加载路径配置..."),
        ("app.db.schema",           "加载数据库结构..."),
        ("app.db.repository",       "加载数据库接口..."),
        ("app.engine.sm2",          "加载学习算法..."),
        ("app.fetcher.base",        "加载数据获取框架..."),
        ("app.fetcher.tts",         "加载语音引擎..."),
        ("app.audio.player",        "加载音频播放器..."),
        ("app.services.session",    "加载会话管理..."),
        ("app.services.settings",   "加载设置管理..."),
        ("app.services.spectrum",   "加载频谱分析..."),
        ("app.services.spectrum_painter", "加载频谱渲染..."),
        ("app.services.image",      "加载图片服务..."),
        ("app.services.text",       "加载文本工具..."),
        ("app.ui.word_editor",      "加载单词编辑器..."),
        ("app.ui.settings_dialog",  "加载设置弹窗..."),
        ("app.ui.settings_tab",     "加载设置页面..."),
        ("app.ui.stats_tab",        "加载统计页面..."),
        ("app.ui.management_tab",   "加载词库管理页面..."),
        ("app.ui.learning_tab",     "加载学习页面..."),
        ("app.ui.main_window",      "加载主窗口..."),
    ]

    total = len(modules)
    for i, (mod, label) in enumerate(modules, 1):
        _lazy_import(mod, splash, i, total, label)

    # ── 编译 numba JIT (频谱分析预热) ──
    splash.set_progress(96, "正在编译频谱分析程序...")
    splash.flush()
    try:
        import numpy as np
        import librosa
        librosa.stft(np.zeros(22050, dtype=np.float32), n_fft=2048, hop_length=512)
    except Exception:
        pass

    # ── 初始化数据库 ──
    from app.paths import get_db_path
    from app.db import init_db
    db_path = get_db_path()
    splash.set_progress(98, "正在读取词库...")
    splash.flush()
    init_db(db_path)

    # ── 创建主窗口 ──
    from app.ui import MainWindow
    splash.set_progress(99, "正在构建界面...")
    splash.flush()
    window = MainWindow(str(db_path))

    splash.set_progress(100, "准备就绪 ✓")
    splash.flush()
    splash.close()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
