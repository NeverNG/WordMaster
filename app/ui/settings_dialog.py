"""等级管理对话框"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QInputDialog,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from loguru import logger

from app.db import WordRepository


class SettingsDialog(QDialog):
    """等级设置弹窗"""

    def __init__(self, repo: WordRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("等级管理")
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)
        self.resize(320, 350)

        self._build_ui()
        self._load_levels()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("📋 单词等级列表")
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(title)

        tip = QLabel("等级会显示在单词卡片和编辑器的下拉框中")
        tip.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(tip)

        self.level_list = QListWidget()
        self.level_list.setAlternatingRowColors(True)
        self.level_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.level_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.level_list.setDragEnabled(True)
        self.level_list.setAcceptDrops(True)
        self.level_list.setDropIndicatorShown(True)
        # 拖拽排序后自动保存
        self.level_list.model().rowsMoved.connect(self._on_order_changed)
        layout.addWidget(self.level_list)

        # 按钮行
        btn_row = QHBoxLayout()

        self.add_btn = QPushButton("➕ 新增")
        self.add_btn.clicked.connect(self._add_level)
        btn_row.addWidget(self.add_btn)

        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.clicked.connect(self._delete_level)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)

        layout.addLayout(btn_row)

        # 选中状态
        self.level_list.itemSelectionChanged.connect(
            lambda: self.delete_btn.setEnabled(
                len(self.level_list.selectedItems()) > 0
            )
        )

    def _load_levels(self):
        self.level_list.clear()
        levels = self.repo.get_levels()
        for lv in levels:
            item = QListWidgetItem(lv)
            self.level_list.addItem(item)

    def _on_order_changed(self):
        """拖拽排序后保存新顺序到数据库"""
        names = [self.level_list.item(i).text() for i in range(self.level_list.count())]
        self.repo.reorder_levels(names)

    def _add_level(self):
        name, ok = QInputDialog.getText(
            self, "新增等级",
            "等级名称:",
            QLineEdit.Normal, "",
        )
        if not ok or not name.strip():
            return
        name = name.strip().upper()
        ok = self.repo.add_level(name)
        if ok:
            self._load_levels()
            logger.info(f"[Settings] 新增等级: {name}")
        else:
            QMessageBox.warning(self, "提示", f"等级「{name}」已存在")

    def _delete_level(self):
        items = self.level_list.selectedItems()
        if not items:
            return
        name = items[0].text()
        reply = QMessageBox.question(
            self, "确认删除",
            f"删除等级「{name}」？\n所有标记为该等级的单词等级会被清除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.delete_level(name)
            self._load_levels()
            logger.info(f"[Settings] 删除等级: {name}")
