"""WordMaster — Windows 桌面背单词工具"""

import sys
import os
from pathlib import Path
from loguru import logger


VERSION = "1.0.3"          # 当前版本号，发布时更新
VERSION_NAME = "v1.0.3"    # 显示用版本名

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.db import init_db
from app.ui import MainWindow
from app.paths import get_cache_dir, get_db_path


def setup_logging():
    # 关闭所有日志输出
    logger.remove()


def main():
    setup_logging()
    logger.info("WordMaster 启动")

    # 初始化数据库 (持久数据与缓存分离)
    db_path = get_db_path()
    init_db(db_path)

    # 启动 GUI
    app = QApplication(sys.argv)
    app.setApplicationName("WordMaster")
    # 设置应用图标（任务栏图标依赖此设置）
    _icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / "asset" / "images" / "icon.ico"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    window = MainWindow(str(db_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
