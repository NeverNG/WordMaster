"""设置对话框 — 朗读次数 + 播放间隔"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
)
from app.services import settings as setsvc


class QuickSettingsDialog(QDialog):
    """设置弹窗"""

    def __init__(self, learning_tab, parent=None):
        super().__init__(parent)
        self.learning_tab = learning_tab
        self.setWindowTitle("设置")
        self.setFixedSize(280, 200)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 朗读次数
        layout.addWidget(QLabel("🔊 自动朗读次数"))
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("单词"))
        self.word_spin = QSpinBox()
        self.word_spin.setRange(0, 5)
        self.word_spin.setFixedWidth(55)
        r1.addWidget(self.word_spin)
        r1.addWidget(QLabel("次"))
        r1.addStretch()
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("例句"))
        self.example_spin = QSpinBox()
        self.example_spin.setRange(0, 5)
        self.example_spin.setFixedWidth(55)
        r2.addWidget(self.example_spin)
        r2.addWidget(QLabel("次"))
        r2.addStretch()
        layout.addLayout(r2)

        # 播放间隔
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("播放间隔"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(500, 10000)
        self.delay_spin.setSingleStep(500)
        self.delay_spin.setFixedWidth(105)
        r3.addWidget(self.delay_spin)
        r3.addWidget(QLabel("ms"))
        r3.addStretch()
        layout.addLayout(r3)

        # 加载当前值
        wr, er = setsvc.load_audio_settings()
        self.word_spin.setValue(wr)
        self.example_spin.setValue(er)
        self.delay_spin.setValue(setsvc.load_auto_delay())

        layout.addStretch()

        # 底部按钮
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self):
        wr = self.word_spin.value()
        er = self.example_spin.value()
        delay = self.delay_spin.value()
        self.learning_tab.save_audio_settings(wr, er)
        self.learning_tab._auto_delay = delay
        setsvc.save_auto_delay(delay)
        self.accept()
