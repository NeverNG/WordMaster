"""频谱柱状图绘制工具 — 共享 SpectrumWidget 和 ExampleFrame 的绘制逻辑"""

from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QPainter
from PySide6.QtCore import Qt


COLORS = [
    QColor("#4caf50"), QColor("#66bb6a"), QColor("#81c784"),
    QColor("#a5d6a7"), QColor("#c8e6c9"), QColor("#fff176"),
    QColor("#ffd54f"), QColor("#ffb74d"), QColor("#ff8a65"),
]


def paint_spectrum(painter: QPainter, bars: list, width: int, height: int, symmetric: bool = True):
    """绘制频谱柱状图
    
    Args:
        painter: QPainter 实例 (已激活)
        bars: 柱高数据列表
        width: 绘制区域宽度
        height: 绘制区域高度
        symmetric: 是否镜像对称 (低频在两侧)
    """
    if not bars:
        return
    
    if symmetric:
        half = len(bars) // 2
        display = bars[:half][::-1] + bars[:half]
    else:
        display = bars
    
    gap = 1
    min_w = 2
    max_bars = max(1, (width - 4) // (min_w + gap))
    count = min(len(display), max_bars)
    if count == 0:
        return
    
    bar_w = (width - 4 - (count - 1) * gap) // count
    extra = width - 4 - count * (bar_w + gap)
    
    for i in range(count):
        bh = max(2, int(display[i]))
        bw = bar_w + (1 if i < extra else 0)
        x = 2 + i * (bar_w + gap) + min(i, extra)
        y = height - bh
        ratio = bh / height
        ci = min(int(ratio * len(COLORS)), len(COLORS) - 1)
        c = COLORS[ci]
        c.setAlpha(int(60 + 160 * ratio))
        painter.setBrush(QBrush(c))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(x, y, bw, bh, 1, 1)
