"""📊 统计页面"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QScrollArea,
)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QFont, QPainter, QColor, QBrush, QPen


class BarWidget(QWidget):
    """单条水平堆叠柱状图组件"""
    def __init__(self, level_name: str, learned: int, total: int, parent=None):
        super().__init__(parent)
        self.level_name = level_name
        self.learned = learned
        self.total = total
        self.setFixedHeight(22)
        self.setMinimumWidth(200)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_max_w = w - 110  # 留出标签空间

        # 等级名称
        p.setPen(QColor("#333"))
        p.setFont(QFont("Microsoft YaHei", 9))
        p.drawText(QRect(0, 0, 100, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.level_name)

        if self.total == 0:
            p.setPen(QColor("#ccc"))
            p.drawText(QRect(70, 0, bar_max_w, h), Qt.AlignmentFlag.AlignCenter, "无数据")
            p.end()
            return

        learned_w = int(bar_max_w * self.learned / self.total) if self.total > 0 else 0
        unlearned_w = bar_max_w - learned_w

        bar_h = 14
        bar_y = (h - bar_h) / 2

        # 已掌握（绿色）
        bar_x = 100
        if learned_w > 0:
            p.setBrush(QBrush(QColor("#4caf50")))
            p.setPen(QPen(Qt.PenStyle.NoPen))
            p.drawRoundedRect(QRect(bar_x, int(bar_y), learned_w, bar_h), 3, 3)

        if unlearned_w > 0:
            p.setBrush(QBrush(QColor("#e0e0e0")))
            p.setPen(QPen(Qt.PenStyle.NoPen))
            p.drawRoundedRect(QRect(bar_x + learned_w, int(bar_y), unlearned_w, bar_h), 3, 3)

        p.setPen(QColor("#666"))
        p.setFont(QFont("Segoe UI", 8))
        label = f"{self.learned}/{self.total}"
        p.drawText(QRect(bar_x, 0, bar_max_w, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   label)

        p.end()


class StatsTab(QWidget):
    """统计页面"""

    def __init__(self, repo, main_window):
        super().__init__()
        self.repo = repo
        self.main = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 顶部总览数字
        overview = QFrame()
        overview.setStyleSheet("background: #ffffff; border: 1px solid #eee; border-radius: 8px; padding: 8px;")
        gl = QGridLayout(overview)
        fs = QFont("Segoe UI", 28, QFont.Weight.Bold)
        for col, (k, emoji, txt) in enumerate([
            ("total", "📚", "总词汇"),
            ("learned", "✅", "已掌握"),
        ]):
            vbox = QVBoxLayout()
            lbl = QLabel("--")
            lbl.setFont(fs)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            setattr(self, f"_stat_{k}", lbl)
            t = QLabel(f"{emoji} {txt}", styleSheet="color: #888; font-size: 11px;")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(lbl)
            vbox.addWidget(t)
            gl.addLayout(vbox, 0, col)
        layout.addWidget(overview)

        layout.addWidget(QLabel("各等级详情", styleSheet="color: #888; font-size: 10px; font-weight: bold; padding-top: 2px;"))

        # 柱状图卡片
        bars_card = QFrame()
        bars_card.setStyleSheet("background: #ffffff; border: 1px solid #eee; border-radius: 8px;")
        bars_card_layout = QVBoxLayout(bars_card)
        bars_card_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        bars_widget = QWidget()
        bars_widget.setStyleSheet("background: transparent;")
        self.bars_container = QVBoxLayout(bars_widget)
        self.bars_container.setContentsMargins(0, 0, 0, 0)
        self.bars_container.addStretch()
        scroll.setWidget(bars_widget)
        bars_card_layout.addWidget(scroll)
        layout.addWidget(bars_card, 1)

    # ── 公共方法 ──

    def refresh(self):
        self._refresh()

    def _refresh(self):
        # 总览
        s = self.repo.get_statistics()
        self._stat_total.setText(str(s["total"]))
        self._stat_learned.setText(str(s["learned"]))

        # 清除旧柱状图（保留最后一个 stretch）
        while self.bars_container.count() > 1:
            item = self.bars_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 各等级柱状图
        levels = self.repo.get_levels()
        if not levels:
            self.bars_container.insertWidget(0, QLabel("暂无等级数据", styleSheet="color: #ccc; font-size: 11px;"))
            return

        for lv in levels:
            stats = self.repo.get_statistics(level=lv)
            total = stats["total"]
            learned = stats["learned"]
            bar = BarWidget(lv, learned, total)
            self.bars_container.insertWidget(self.bars_container.count() - 1, bar)
