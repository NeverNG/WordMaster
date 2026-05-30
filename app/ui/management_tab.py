"""📚 单词管理页面"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QComboBox,
)
from PySide6.QtCore import Qt
from app.ui.word_editor import WordEditorDialog
from app.ui.settings_dialog import SettingsDialog
from app.services.text import short_translation


class ManagementTab(QWidget):
    """单词管理页面"""

    def __init__(self, repo, main_window):
        super().__init__()
        self.repo = repo
        self.main = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 搜索行
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索...")
        search_row.addWidget(self.search_input)
        search_row.addWidget(QLabel("等级:"))
        self.level_filter = QComboBox()
        self.level_filter.addItem("全部等级", "")
        search_row.addWidget(self.level_filter)
        self.word_count_label = QLabel("", styleSheet="color: #888; font-size: 11px;")
        search_row.addWidget(self.word_count_label)
        self.level_filter.currentIndexChanged.connect(self._search)
        layout.addLayout(search_row)
        self.search_input.textChanged.connect(self._search)
        
        # 操作按钮
        action_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ 新增")
        self.add_btn.clicked.connect(self._add_word)
        action_row.addWidget(self.add_btn)
        self.edit_btn = QPushButton("✏️ 编辑")
        self.edit_btn.clicked.connect(self._edit_word)
        self.edit_btn.setEnabled(False)
        action_row.addWidget(self.edit_btn)
        self.delete_btn = QPushButton("🗑 删除")
        self.delete_btn.clicked.connect(self._delete_word)
        self.delete_btn.setEnabled(False)
        action_row.addWidget(self.delete_btn)
        self.reset_reps_btn = QPushButton("🔄 归零")
        self.reset_reps_btn.clicked.connect(self._reset_repetitions)
        action_row.addWidget(self.reset_reps_btn)
        self.level_mgr_btn = QPushButton("📋 等级")
        self.level_mgr_btn.clicked.connect(self._open_levels)
        action_row.addWidget(self.level_mgr_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        # 表格
        self.word_table = QTableWidget(0, 5)
        self.word_table.setHorizontalHeaderLabels(["ID", "单词", "音标", "释义", "学习次数"])
        self.word_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.word_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.word_table.setColumnHidden(0, True)
        self.word_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.word_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.word_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.word_table.doubleClicked.connect(self._edit_word)
        layout.addWidget(self.word_table)

    # ── 公共方法 ──

    def load_level_filter(self):
        current = self.level_filter.currentData()
        self.level_filter.blockSignals(True)
        self.level_filter.clear()
        self.level_filter.addItem("全部等级", "")
        for lv in self.repo.get_levels():
            self.level_filter.addItem(lv, lv)
        idx = self.level_filter.findData(current)
        if idx >= 0:
            self.level_filter.setCurrentIndex(idx)
        self.level_filter.blockSignals(False)

    def search(self):
        self._search()

    def _search(self):
        keyword = self.search_input.text().strip()
        level = self.level_filter.currentData()
        words = self.repo.search_words(keyword, limit=500, level=level)
        self.word_table.setRowCount(len(words))
        for row, w in enumerate(words):
            self.word_table.setItem(row, 0, QTableWidgetItem(str(w["id"])))
            self.word_table.setItem(row, 1, QTableWidgetItem(w["word"]))
            self.word_table.setItem(row, 2, QTableWidgetItem(w.get("phonetic_us", "")))
            self.word_table.setItem(row, 3, QTableWidgetItem(short_translation(w.get("translation", ""))))
            self.word_table.setItem(row, 4, QTableWidgetItem(str(w.get("review_count", 0))))
        self.word_table.resizeRowsToContents()
        self.word_count_label.setText(f"共 {len(words)} 词")

    def _on_selection_changed(self):
        sel = len(self.word_table.selectedItems()) > 0
        self.edit_btn.setEnabled(sel)
        self.delete_btn.setEnabled(sel)

    def _get_selected_word_id(self) -> int | None:
        rows = {it.row() for it in self.word_table.selectedItems()}
        if not rows:
            return None
        it = self.word_table.item(rows.pop(), 0)
        return int(it.text()) if it else None

    def _add_word(self):
        dlg = WordEditorDialog(self.repo, parent=self)
        if dlg.exec():
            self._search()
            self.main.learning_tab.refresh()

    def _edit_word(self):
        wid = self._get_selected_word_id()
        if wid is None:
            return
        dlg = WordEditorDialog(self.repo, word_id=wid, parent=self)
        if dlg.exec():
            self._search()
            self.main.learning_tab.refresh()

    def _open_levels(self):
        dlg = SettingsDialog(self.repo, parent=self)
        dlg.exec()
        self.main.learning_tab.load_levels()
        self.main.stats_tab.refresh()
        self.load_level_filter()

    def _reset_repetitions(self):
        reply = QMessageBox.question(self, "确认归零",
            "将所有单词的学习次数归零？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.reset_repetitions()
            self._search()
            QMessageBox.information(self, "完成", "学习次数已归零")

    def _delete_word(self):
        wid = self._get_selected_word_id()
        if wid is None:
            return
        w = self.repo.get_word(wid)
        if not w:
            return
        r = QMessageBox.question(self, "确认", f"删除「{w['word']}」？",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.repo.delete_word(wid)
            self._search()
            self.main.learning_tab.refresh()
