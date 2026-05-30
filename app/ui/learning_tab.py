"""📖 学习页面"""

import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QFont, QPainter, QColor, QBrush, QPen, QConicalGradient,
)
from pathlib import Path

from loguru import logger

from app.engine import sm2_review
from app.services import session as sess, settings as setsvc, image as img_svc, text as txt_svc
from app.paths import get_cache_dir


class CardFrame(QFrame):
    """卡片外框 — 自动翻页时显示旋转渐变边框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setObjectName("card_frame")

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._timer.start(50)
        else:
            self._timer.stop()
            self._angle = 0
        self.update()

    def _rotate(self):
        self._angle = (self._angle + 3) % 360
        self.update()

    def paintEvent(self, event):
        if not self._active:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        # 先画背景
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(rect, 10, 10)
        # 再画渐变边框
        r = rect.adjusted(2, 2, -2, -2)
        grad = QConicalGradient(r.center(), self._angle)
        grad.setColorAt(0.0, QColor("#ff4444"))
        grad.setColorAt(0.25, QColor("#ffdd00"))
        grad.setColorAt(0.5, QColor("#44cc44"))
        grad.setColorAt(0.75, QColor("#4488ff"))
        grad.setColorAt(1.0, QColor("#ff4444"))
        painter.setPen(QPen(QBrush(grad), 1))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRoundedRect(r, 10, 10)
        painter.end()




class SpectrumWidget(QWidget):
    """音频频谱动画组件 — 模拟频率分布"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars = []
        self._target = []
        self._bar_count = 48
        self._time = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_bars)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(0, 0)
        self.hide()

    def set_spectrum_data(self, data: list):
        self._spec_data = data

    def start(self):
        p = self.parent()
        if p:
            self.setGeometry(0, 0, p.width(), p.height())
        h = max(self.height(), 20)
        self._bars = [2] * self._bar_count
        self._target = [2] * self._bar_count
        self._time = 0
        self._start_ms = 0
        self.show()
        self._timer.start(50)

    def stop(self):
        self._timer.stop()
        self._bars = []
        self._target = []
        self.hide()
        self.update()

    def _update_bars(self):
        import math
        self._time += 1
        if self._time % 10 == 0:
            p = self.parent()
            if p:
                self.setGeometry(0, 0, p.width(), p.height())
        h = max(self.height(), 20)

        spec_data = getattr(self, '_spec_data', None)
        if spec_data:
            from app.services.spectrum import spectrum_to_bars
            audio = getattr(self, '_audio', None)
            progress = 0.5
            if audio:
                dur = getattr(audio._player, 'duration', lambda: 0)()
                pos = getattr(audio._player, 'position', lambda: 0)()
                if dur > 0:
                    progress = min(pos / dur, 1.0)
            target_bars = spectrum_to_bars(spec_data, progress, h)
            for i in range(min(len(target_bars), self._bar_count)):
                self._bars[i] += (target_bars[i] - self._bars[i]) * 0.3
        else:
            import random, math
            for i in range(self._bar_count):
                freq = i / self._bar_count
                audio = getattr(self, '_audio', None)
                progress = 0.5
                if audio:
                    dur = getattr(audio._player, 'duration', lambda: 0)()
                    pos = getattr(audio._player, 'position', lambda: 0)()
                    if dur > 0:
                        progress = min(pos / dur, 1.0)
                base = math.exp(-freq * 2.5) * (0.5 + 0.5 * math.sin(progress * math.pi))
                base += math.sin(freq * math.pi * 3 * (1 + progress)) * 0.3
                base += random.random() * 0.15
                mod = math.sin(self._time * 0.08 + freq * 6 * (1 + progress * 0.5)) * 0.25
                target_h = int((base + mod) * h * 0.85 + 2)
                target_h = max(2, min(target_h, h - 4))
                self._bars[i] = self._bars[i] + (target_h - self._bars[i]) * 0.3

        self.update()

    def paintEvent(self, event):
        if not self._bars:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from app.services.spectrum_painter import paint_spectrum
        paint_spectrum(painter, self._bars, self.width(), self.height(), symmetric=False)
        painter.end()


class ExampleFrame(QFrame):
    """例句框 — 内嵌频谱动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._spectrum_bars = []
        self._spectrum_active = False
        self._spectrum_timer = QTimer(self)
        self._spectrum_timer.timeout.connect(self._update_spectrum)

    def set_spectrum_data(self, data: list):
        self._spec_data = data

    def start_spectrum(self):
        self._spectrum_active = True
        self._spectrum_bars = [2] * 48
        self._spectrum_timer.start(50)

    def stop_spectrum(self):
        self._spectrum_active = False
        self._spectrum_timer.stop()
        self._spectrum_bars = []
        self.update()

    def _update_spectrum(self):
        import random, math
        if not self._spectrum_active:
            return
        h = max(self.height(), 20)
        t = getattr(self, '_spec_time', 0) + 1
        self._spec_time = t

        audio = getattr(self, '_audio', None)
        progress = 0.5
        if audio:
            dur = getattr(audio._player, 'duration', lambda: 0)()
            pos = getattr(audio._player, 'position', lambda: 0)()
            if dur > 0:
                progress = min(pos / dur, 1.0)

        spec_data = getattr(self, '_spec_data', None)
        if spec_data:
            from app.services.spectrum import spectrum_to_bars
            target_bars = spectrum_to_bars(spec_data, progress, h)
            for i in range(min(len(target_bars), len(self._spectrum_bars))):
                self._spectrum_bars[i] += (target_bars[i] - self._spectrum_bars[i]) * 0.3
        else:
            for i in range(len(self._spectrum_bars)):
                freq = i / len(self._spectrum_bars)
                base = math.exp(-freq * 2.5) * (0.5 + 0.5 * math.sin(progress * math.pi))
                base += math.sin(freq * math.pi * 3 * (1 + progress)) * 0.3
                base += random.random() * 0.15
                mod = math.sin(t * 0.08 + freq * 6 * (1 + progress * 0.5)) * 0.25
                target = int((base + mod) * h * 0.85 + 2)
                target = max(2, min(target, h - 4))
                if i < len(self._spectrum_bars):
                    self._spectrum_bars[i] += (target - self._spectrum_bars[i]) * 0.3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#e8f5e9")))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        if self._spectrum_bars:
            from app.services.spectrum_painter import paint_spectrum
            paint_spectrum(painter, self._spectrum_bars, self.width(), self.height())
        painter.end()


class LearningTab(QWidget):
    """学习页面"""

    def __init__(self, repo, audio, main_window):
        super().__init__()
        self.repo = repo
        self.audio = audio
        self.main = main_window

        self._due_words: list[dict] = []
        self._current_word: dict | None = None
        self._current_examples: list[dict] = []
        self._current_example: dict | None = None
        self._word_history: list[dict] = []
        self._play_queue: list[tuple[str, bool]] = []  # (path, is_word)
        self._is_auto_playing = False
        self._auto_advance = False
        self._auto_delay = setsvc.load_auto_delay()
        self._session_total: int = 0
        self._session_pos: int = 0
        self._word_repeat, self._example_repeat = setsvc.load_audio_settings()
        self._playing_word_audio = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        # ── 筛选行 (等级 + 计数 + 自动) ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        filter_row.addWidget(QLabel("等级:", styleSheet="color: #888; font-size: 11px;"))
        self.learn_level_filter = QComboBox()
        self.learn_level_filter.setMinimumContentsLength(10)
        self.learn_level_filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.learn_level_filter.addItem("全部", "")
        filter_row.addWidget(self.learn_level_filter)
        self.vocab_counter = QLabel("0/0", styleSheet="color: #888; font-size: 11px;")
        filter_row.addWidget(self.vocab_counter)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        self.learn_level_filter.currentIndexChanged.connect(self._refresh)

        # ── 操作按钮行 ──
        action_row = QHBoxLayout()
        action_row.setSpacing(4)
        self.skip_learned_btn = QPushButton("⏭ 忽略已会")
        self.skip_learned_btn.setCheckable(True)
        self.skip_learned_btn.setChecked(False)
        self.skip_learned_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.skip_learned_btn.setToolTip("开启后跳过已掌握的单词")
        self.skip_learned_btn.toggled.connect(self._on_skip_toggled)
        action_row.addWidget(self.skip_learned_btn)

        self.clear_history_btn = QPushButton("🔁 从头开始")
        self.clear_history_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; color: #c00;")
        self.clear_history_btn.setToolTip("清除所有学习记录，重新开始")
        self.clear_history_btn.clicked.connect(self._clear_history)
        action_row.addWidget(self.clear_history_btn)

        self.clear_progress_btn = QPushButton("🗑 清除进度")
        self.clear_progress_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; color: #c00;")
        self.clear_progress_btn.setToolTip("清除已掌握标记，统计归零")
        self.clear_progress_btn.clicked.connect(self._clear_progress)
        action_row.addWidget(self.clear_progress_btn)

        action_row.addStretch()
        layout.addLayout(action_row)

        # ── 卡片 ──
        self.card = CardFrame()
        self._set_card_style("#ddd")
        card_v = QVBoxLayout(self.card)
        card_v.setSpacing(4)
        card_v.setContentsMargins(6, 4, 6, 4)

        top_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        self.word_label = QLabel("✨ 添加单词开始学习")
        self.word_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setWordWrap(True)
        self.word_label.setStyleSheet("background: #e3f2fd; border-radius: 6px; padding: 4px 8px;")
        self.word_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.word_label.mousePressEvent = lambda e: self._play_word_audio()
        left_col.addWidget(self.word_label)

        self.word_spectrum = SpectrumWidget(self.word_label)
        self.word_spectrum._audio = self.audio
        self.phonetic_label = QLabel("", styleSheet="color: #666; background: #f3e5f5; border-radius: 4px; padding: 2px 6px;")
        self.phonetic_label.setFont(QFont("Segoe UI", 11))
        self.phonetic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_col.addWidget(self.phonetic_label)
        self.translation_label = QLabel("", styleSheet="color: #333; background: #fff3e0; border-radius: 4px; padding: 3px 6px;")
        self.translation_label.setFont(QFont("Microsoft YaHei", 11))
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translation_label.setWordWrap(True)
        left_col.addWidget(self.translation_label)
        top_row.addLayout(left_col, 1)

        self.card_image = QLabel("")
        self.card_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_image.setScaledContents(True)
        self.card_image.setMinimumSize(80, 60)
        self.card_image.setStyleSheet("border: 1px solid #ddd; border-radius: 6px; background: #eee;")
        top_row.addWidget(self.card_image, 1)
        card_v.addLayout(top_row, 1)

        # 例句块 (英文 + 中文合并)
        self.example_frame = ExampleFrame()
        self.example_frame.setObjectName("example_frame")
        self.example_frame.setStyleSheet("#example_frame { background: #e8f5e9; border-radius: 6px; padding: 4px; }")
        ex_layout = QVBoxLayout(self.example_frame)
        ex_layout.setSpacing(1)
        ex_layout.setContentsMargins(6, 3, 6, 3)



        self.example_label = QLabel("")
        self.example_label.setStyleSheet("color: #555; font-style: italic; background: transparent;")
        self.example_label.setFont(QFont("Segoe UI", 12))
        self.example_label.setWordWrap(True)
        self.example_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.example_label.mousePressEvent = lambda e: self._play_example_audio()
        ex_layout.addWidget(self.example_label)

        self.example_cn_label = QLabel("", styleSheet="color: #777; background: transparent;")
        self.example_cn_label.setFont(QFont("Microsoft YaHei", 9))
        self.example_cn_label.setWordWrap(True)
        self.example_cn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.example_cn_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.example_cn_label.mousePressEvent = lambda e: self._play_example_audio()
        ex_layout.addWidget(self.example_cn_label)

        card_v.addWidget(self.example_frame)
        layout.addWidget(self.card, 1)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.prev_btn = QPushButton("◀ 上一词")
        self.prev_btn.setEnabled(False)
        self.prev_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.prev_btn.clicked.connect(self._prev_word)
        btn_row.addWidget(self.prev_btn)

        self.auto_btn = QPushButton("⏸ 自动翻页")
        self.auto_btn.setCheckable(True)
        self.auto_btn.setChecked(False)
        self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.auto_btn.setToolTip("开启后自动播放并切换到下一个单词")
        self.auto_btn.toggled.connect(self._toggle_auto_advance)
        btn_row.addWidget(self.auto_btn)

        btn_row.addStretch()

        self.familiar_btn = QPushButton("✓ 已掌握")
        self.familiar_btn.setEnabled(False)
        self.familiar_btn.setStyleSheet("padding: 4px 12px; font-size: 12px;")
        self.familiar_btn.clicked.connect(self._mark_familiar)
        btn_row.addWidget(self.familiar_btn)

        self.next_btn = QPushButton("⏭ 下一词")
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet("padding: 4px 12px; font-size: 12px;")
        self.next_btn.clicked.connect(self._next_word)
        btn_row.addWidget(self.next_btn)
        layout.addLayout(btn_row)

        self.audio.playback_finished.connect(self._on_playback_finished)

    def _set_card_style(self, border_color: str):
        self.card.setStyleSheet(
            "#card_frame { background: #ffffff; border: 1px solid #ddd; border-radius: 10px; padding: 6px; }"
        )

    # ── 公共 ──

    def load_levels(self, select_level: str = ""):
        self.learn_level_filter.blockSignals(True)
        self.learn_level_filter.clear()
        self.learn_level_filter.addItem("全部", "")
        for lv in self.repo.get_levels():
            self.learn_level_filter.addItem(lv, lv)
        idx = self.learn_level_filter.findData(select_level)
        if idx >= 0:
            self.learn_level_filter.setCurrentIndex(idx)
        self.learn_level_filter.blockSignals(False)

    def refresh(self):
        self._refresh()

    def reload_audio_settings(self):
        self._word_repeat, self._example_repeat = setsvc.load_audio_settings()

    def save_audio_settings(self, word_repeat: int, example_repeat: int):
        self._word_repeat = word_repeat
        self._example_repeat = example_repeat
        setsvc.save_audio_settings(word_repeat, example_repeat)

    # ── 内部 ──

    def _refresh(self):
        level = self.learn_level_filter.currentData()
        self._word_history.clear()
        self._session_pos = 0

        # 加载该等级所有单词（不按到期筛选）
        all_words = self.repo.search_words(level=level or None, limit=500) if level else \
                    self.repo.search_words(limit=500)
        self._due_words = list(all_words)

        if self.skip_learned_btn.isChecked():
            self._due_words = [w for w in self._due_words if w.get("last_quality") != 4]

        # 所有词都已掌握 → 禁用自动按钮
        if self.skip_learned_btn.isChecked():
            all_w = self.repo.search_words(level=level or None, limit=500) if level else \
                    self.repo.search_words(limit=500)
            any_unlearned = any(w.get("last_quality") != 4 for w in all_w)
            if not any_unlearned:
                self._auto_advance = False
                self.auto_btn.setChecked(False)
                self.auto_btn.setEnabled(False)
                self.auto_btn.setText("⏸ 自动翻页")
                self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; color: #bbb;")
                self.card.set_active(False)
            else:
                self.auto_btn.setEnabled(True)
                self._sync_auto_btn_style()
        else:
            self.auto_btn.setEnabled(True)
            self._sync_auto_btn_style()

        # 忽略已会按钮状态同步
        self.skip_learned_btn.setStyleSheet(self.skip_learned_btn.styleSheet())

        # 如果当前词被过滤掉了, 跳到下一个
        if self._current_word and self._current_word["id"] not in {w["id"] for w in self._due_words}:
            self._current_word = None

        self._session_total = len(self._due_words)

        # 恢复进度: 找到 last_word_id 并移到队列头
        lp = sess.load_progress(level)
        if lp:
            last_id = lp.get("last_word_id")
            saved_pos = lp.get("position", 0)
            found = False
            for i, w in enumerate(self._due_words):
                if w["id"] == last_id:
                    self._due_words.insert(0, self._due_words.pop(i))
                    if saved_pos < len(self._due_words):
                        self._session_pos = saved_pos
                    found = True
                    break
            if not found:
                # 不在 due 列表 → 重新加载所有单词, 把 last_word 放前面
                all_w = self.repo.search_words(
                    level=level or None, limit=500
                ) if level else self.repo.search_words(limit=500)
                if all_w:
                    for i, w in enumerate(all_w):
                        if w["id"] == last_id:
                            all_w.insert(0, all_w.pop(i))
                            break
                    self._due_words = all_w
                    if self.skip_learned_btn.isChecked():
                        self._due_words = [w for w in self._due_words if w.get("last_quality") != 4]
                    self._session_total = len(self._due_words)
                    self._session_pos = min(saved_pos, len(self._due_words) - 1) if self._due_words else 0

        if self._due_words:
            self._show_word_card(self._due_words[0])
            self.prev_btn.setEnabled(False)
        else:
            self._current_word = None
            self._clear_card()
            all_w = self.repo.search_words(level=level or None, limit=200) if level else \
                    self.repo.search_words(limit=200)
            if all_w:
                self._due_words = all_w
                if self.skip_learned_btn.isChecked():
                    self._due_words = [w for w in self._due_words if w.get("last_quality") != 4]
                self._session_total = len(self._due_words)
                self._word_history.clear()
                if self._due_words:
                    self._show_word_card(self._due_words[0])
            else:
                self.word_label.setText(f"📭 该等级暂无单词，去「管理」添加" if level else "✨")
                self.vocab_counter.setText("0/0")

    def _show_word_card(self, word: dict):
        self._current_word = word
        self._current_examples = self.repo.get_examples(word["id"])

        total = self._session_total or len(self._due_words)
        if total > 0:
            self._session_pos = min(self._session_pos, total - 1)
        self.vocab_counter.setText(f"{self._session_pos + 1}/{total}")

        sess.save_progress(word["id"], self.learn_level_filter.currentData(), self._session_pos)

        self.word_label.setText(word["word"])
        ph = word.get("phonetic_us", "")
        self.phonetic_label.setText(f"/{ph}/" if ph and not ph.startswith("/") else ph)

        trans = txt_svc.short_translation(word.get("translation", ""))
        self.translation_label.setText(trans if trans else "(未填写释义)")

        if self._current_examples:
            self._current_example = random.choice(self._current_examples)
            self.example_label.setText(self._current_example["sentence_en"])
            self.example_cn_label.setText(self._current_example.get("sentence_cn", ""))
        else:
            self._current_example = None
            self.example_label.setText("")
            self.example_cn_label.setText("")

        is_learned = word.get("last_quality") == 4
        self.word_label.setStyleSheet(
            "background: #e3f2fd; border-radius: 6px; padding: 4px 8px; color: #2e7d32;" if is_learned
            else "background: #e3f2fd; border-radius: 6px; padding: 4px 8px; color: #e65100;"
        )

        self.familiar_btn.setEnabled(word.get("last_quality") != 4)
        self.next_btn.setEnabled(True)
        self.prev_btn.setEnabled(bool(self._word_history))

        self._load_card_image(word["word"])
        # 预先加载单词和例句的频谱数据
        from app.fetcher import TTSEngine
        _tts = TTSEngine()
        _wp = _tts.generate_word(word["word"])
        if _wp:
            self._load_spectrum_data(_wp, self.word_spectrum)
        if self._current_example:
            _ep = _tts.generate(self._current_example["sentence_en"])
            if _ep:
                self._load_spectrum_data(_ep, self.example_frame)
        QTimer.singleShot(300, self._auto_play_current)

    def _clear_card(self):
        self.word_label.setText("")
        self.phonetic_label.setText("")
        self.translation_label.setText("")
        self.example_label.setText("")
        self.example_cn_label.setText("")
        self.card_image.clear()
        self.card_image.setText("")
        self._current_example = None
        for btn in [self.familiar_btn, self.next_btn, self.prev_btn]:
            btn.setEnabled(False)
        self._current_word = None

    def _load_card_image(self, word: str):
        path = img_svc.get_word_image(word)
        if path:
            pix = img_svc.load_pixmap(path)
            if pix:
                self.card_image.setPixmap(pix)
                return
        self.card_image.setText(word.upper()[:4])
        self.card_image.setStyleSheet("background: #eee; color: #999; font-size: 20px; border-radius: 6px;")

    # ── 导航 ──

    def _prev_word(self):
        if not self._word_history:
            return
        if self._current_word:
            self._due_words.insert(0, self._current_word)
        self._due_words.insert(0, self._word_history.pop())
        self._session_pos = max(0, self._session_pos - 1)
        self._show_word_card(self._due_words[0])

    def _mark_familiar(self):
        w = self._current_word
        if not w:
            return
        self.repo.mark_learned(w["id"])
        w["last_quality"] = 4
        self.word_label.setStyleSheet(
            "background: #e3f2fd; border-radius: 6px; padding: 4px 8px; color: #2e7d32;"
        )
        logger.debug(f"[掌握] {w['word']}")
        if self.skip_learned_btn.isChecked():
            # 跳过已掌握 → 标记后自动移出队列
            self._due_words = [d for d in self._due_words if d["id"] != w["id"]]
            if self._due_words:
                self._show_word_card(self._due_words[0])
                return
            self._try_reload_or_done()
            return
        self.familiar_btn.setEnabled(False)
        self.main.stats_tab.refresh()  # 刷新统计

    def _next_word(self):
        if not self._due_words:
            all_w = self.repo.search_words(level=self.learn_level_filter.currentData() or None, limit=200) if \
                    self.learn_level_filter.currentData() else self.repo.search_words(limit=200)
            if all_w:
                self._due_words = all_w
                self._session_pos = 0
                self._word_history.clear()
                self._session_total = len(all_w)
                self._show_word_card(self._due_words[0])
            return
        if self._current_word:
            self._word_history.append(self._current_word)
            self._session_pos += 1
            # 已掌握的词保持 quality=4, 否则 quality=3
            q = 4 if self._current_word.get("last_quality") == 4 else 3
            self._do_review(quality=q)
        else:
            self._due_words.pop(0)
            if self._due_words:
                self._show_word_card(self._due_words[0])
            else:
                self._try_reload_or_done()

    def _do_review(self, quality: int):
        w = self._current_word
        if not w:
            return
        rr = self.repo.get_or_create_review(w["id"])
        r = sm2_review(quality, rr.get("ease_factor", 2.5), rr.get("interval_days", 0), rr.get("repetitions", 0))
        self.repo.update_review(w["id"], r.ease_factor, r.interval_days, r.repetitions, quality)
        self._due_words = [d for d in self._due_words if d["id"] != w["id"]]
        if self._due_words:
            self._show_word_card(self._due_words[0])
        else:
            self._try_reload_or_done()

    def _try_reload_or_done(self):
        self._clear_card()
        level = self.learn_level_filter.currentData()
        all_w = self.repo.search_words(level=level or None, limit=200) if level else \
                self.repo.search_words(limit=200)
        if all_w:
            self._due_words = all_w
            if self.skip_learned_btn.isChecked():
                self._due_words = [w for w in self._due_words if w.get("last_quality") != 4]
            self._session_pos = 0
            self._word_history.clear()
            self._session_total = len(self._due_words)
            if self._due_words:
                self._show_word_card(self._due_words[0])
            else:
                self.word_label.setText("✨")
                self.vocab_counter.setText("0/0")
        else:
            self.word_label.setText("✨")

    # ── 音频 ──


    def _load_spectrum_data(self, audio_path, target):
        """加载频谱数据 (优先从缓存同步读取, 若无缓存则后台计算)"""
        from app.services.spectrum import get_spectrum
        data = get_spectrum(audio_path)
        if data:
            target.set_spectrum_data(data)
        else:
            import threading
            def _load():
                d = get_spectrum(audio_path)
                if d:
                    target.set_spectrum_data(d)
            threading.Thread(target=_load, daemon=True).start()

    def _play_word_audio(self):
        if not self._current_word:
            return
        self._playing_word_audio = True
        self.example_frame.stop_spectrum()
        from app.fetcher import TTSEngine
        tts = TTSEngine()
        p = tts.generate_word(self._current_word["word"])
        if p:
            try:
                self._load_spectrum_data(p, self.word_spectrum)
            except Exception:
                pass
            self.word_spectrum.start()
            self.audio.play(str(p))

    def _play_example_audio(self):
        if not self._current_example:
            return
        self._playing_word_audio = False
        ex = self._current_example
        self.word_spectrum.stop()
        self.example_frame._audio = self.audio
        played = False
        audio_path = None
        if ex.get("audio_filename"):
            p = get_cache_dir("audio") / ex["audio_filename"]
            if p.exists():
                audio_path = p
                self.audio.play(str(p))
                played = True
        if not played:
            from app.fetcher import TTSEngine
            tts = TTSEngine()
            p = tts.generate(ex["sentence_en"])
            if p:
                audio_path = p
                self.audio.play(str(p))
                played = True
        if not played:
            self.example_frame.stop_spectrum()
        try:
            if audio_path:
                self._load_spectrum_data(audio_path, self.example_frame)
        except Exception:
            pass
        self.example_frame.start_spectrum()

    def _auto_play_current(self):
        self._is_auto_playing = False
        self.audio.stop()
        self._play_queue.clear()
        self.word_spectrum.stop()
        self.example_frame.stop_spectrum()
        from app.fetcher import TTSEngine
        tts = TTSEngine()
        q = []
        if self._current_word and self._word_repeat > 0:
            wp = tts.generate_word(self._current_word["word"])
            if wp:
                q.extend([(str(wp), True)] * self._word_repeat)
        if self._current_example and self._example_repeat > 0:
            ep = tts.generate(self._current_example["sentence_en"])
            if ep:
                q.extend([(str(ep), False)] * self._example_repeat)
        if q:
            self._play_queue = q
            self._is_auto_playing = True
            self._play_next_in_queue()

    def _on_skip_toggled(self, checked: bool):
        self.skip_learned_btn.setStyleSheet(
            "padding: 4px 10px; font-size: 11px; background: #4caf50; color: #fff;" if checked
            else "padding: 4px 10px; font-size: 11px;"
        )
        self._refresh()

    def _clear_progress(self):
        reply = QMessageBox.question(self, "确认清除",
            "清除所有已掌握标记？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.clear_learned(level="")
            self._refresh()
            self.main.stats_tab.refresh()

    def _clear_history(self):
        from app.services import session as sess
        reply = QMessageBox.question(self, "确认清除",
            "清除所有学习历史记录？所有单词将回到初始状态。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.clear_all_progress()
            sess.clear_session()
            self._word_history.clear()
            self._session_pos = 0
            self._refresh()
            self.main.stats_tab.refresh()

    def _sync_auto_btn_style(self):
        if self.auto_btn.isChecked():
            self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; background: #4caf50; color: #fff;")
        else:
            self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.card.set_active(self.auto_btn.isChecked())

    def _toggle_auto_advance(self, checked: bool):
        self._auto_advance = checked
        self.card.set_active(checked)
        if checked:
            self.auto_btn.setText("⏸ 自动翻页")
            self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px; background: #4caf50; color: #fff;")
            self._auto_play_current()
        else:
            self.auto_btn.setText("⏸ 自动翻页")
            self.auto_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")

    def _play_next_in_queue(self):
        if self._play_queue:
            path, is_word = self._play_queue.pop(0)
            if is_word:
                try:
                    self._load_spectrum_data(path, self.word_spectrum)
                except Exception:
                    pass
                self.word_spectrum.start()
            else:
                try:
                    self._load_spectrum_data(path, self.example_frame)
                except Exception:
                    pass
                self.example_frame.start_spectrum()
            self.audio.play(path)
        else:
            self._is_auto_playing = False
            if self._auto_advance:
                QTimer.singleShot(self._auto_delay, self._next_word)

    def _on_playback_finished(self, filename: str):
        self.word_spectrum.stop()
        self.example_frame.stop_spectrum()
        if self._is_auto_playing:
            self._play_next_in_queue()
