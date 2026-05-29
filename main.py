"""WordMaster — Windows 桌面背单词工具"""

import sys
import os
from pathlib import Path
from loguru import logger

# 确保项目根在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from app.db import init_db
from app.ui import MainWindow
from app.paths import get_cache_dir


def setup_logging():
    cache_dir = get_cache_dir()
    logger.add(
        cache_dir / "wordmaster.log",
        rotation="1 MB",
        retention=3,
        level="INFO",
        enqueue=True,
    )


def main():
    setup_logging()
    logger.info("WordMaster 启动")

    # 初始化数据库
    db_path = get_cache_dir() / "words.db"
    init_db(db_path)

    # 启动 GUI
    app = QApplication(sys.argv)
    app.setApplicationName("WordMaster")
    app.setApplicationDisplayName("联网使用")

    window = MainWindow(str(db_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
