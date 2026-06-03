"""单词编辑对话框

新增/编辑单词，支持自动从网络获取音标、翻译和例句。
"""

from pathlib import Path
from typing import Optional

import httpx
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox,
    QMessageBox, QGroupBox, QListWidget, QListWidgetItem,
    QWidget,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QPixmap, QFont
from loguru import logger

from app.db import WordRepository
from app.fetcher import WordData, Example
from app.services import image as img_svc, text as txt_svc


EXAM_LEVEL_MAP = {
    "CET4": "CET4", "CET6": "CET6", "考研": "考研",
    "IELTS": "IELTS", "TOEFL": "TOEFL",
    "GRE": "GRE", "SAT": "SAT", "商务英语": "商务英语",
    "专业八级": "TEM8", "专业四级": "TEM4",
}

# 从 database/schema.py 删除硬编码列表 — 改为运行时从 repo 加载


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://dict.youdao.com/",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 各 API Provider 实现 — 每个返回 WordData 或 None
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _fetch_youdao(word: str) -> Optional[WordData]:
    """Provider 1: 有道网页 scraping (jsonapi_s 已失效，改用网页)"""
    try:
        resp = httpx.get(
            f"https://dict.youdao.com/w/eng/{word.lower().strip()}",
            headers=_BROWSER_HEADERS, timeout=10.0, follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        if f"/w/eng/{word.lower().strip()}" not in str(resp.url):
            logger.warning(f"[Fetch] 有道重定向: 查询={word}, 去向={resp.url}")
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # 音标
        phonetic = ""
        ph_el = soup.select_one(".phonetic")
        if ph_el:
            phonetic = ph_el.text.strip().strip("[]")

        # 释义: .trans-container ul li
        translation = ""
        pos = ""
        trans_container = soup.select_one(".trans-container")
        if trans_container:
            first_li = trans_container.select_one("ul li")
            if first_li:
                text = first_li.text.strip()
                import re as _re
                m = _re.match(r"^([a-z]+)\.\s*(.*)", text)
                if m:
                    pos = m.group(1) + "."
                    translation = m.group(2)
                else:
                    translation = text

        # 等级: 从页面查找 CET4/CET6/TEM4/TEM8/考研/IELTS 等标签
        level = ""
        page_text = resp.text
        for et in EXAM_LEVEL_MAP:
            if et in page_text:
                level = EXAM_LEVEL_MAP[et]
                break

        # 例句 (页面中有多个 .examples 块，每个含英文/中文交替 <p>)
        examples = []
        for ex_block in soup.select(".examples"):
            ps = ex_block.select("p")
            for i in range(0, len(ps) - 1, 2):
                en = ps[i].get_text(strip=True)
                cn = ps[i + 1].get_text(strip=True) if i + 1 < len(ps) else ""
                if en and len(en) > 3:
                    examples.append(Example(sentence_en=en, sentence_cn=cn, source="youdao"))
                    if len(examples) >= 5:
                        break
            if len(examples) >= 5:
                break

        if translation:
            return WordData(
                word=word, phonetic_us=phonetic,
                translation=txt_svc.short_translation(translation),
                pos=pos, level=level, examples=examples,
            )
    except ImportError:
        logger.warning("[Fetch] 有道需要安装 bs4: pip install beautifulsoup4 lxml")
    except Exception as e:
        logger.warning(f"[Fetch] 有道异常 {word}: {e}")
    return None


def _fetch_builtin(word: str) -> Optional[WordData]:
    """Provider 2: 内置词典 (离线保底)"""
    import json as _json
    _builtin_path = Path(__file__).parent.parent.parent / "cache" / "builtin_dict.json"
    _builtin = {}
    if _builtin_path.exists():
        try:
            _builtin = _json.loads(_builtin_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    kw = word.lower().strip()
    if kw in _builtin:
        bd = _builtin[kw]
        return WordData(
            word=word, phonetic_us=bd.get("ph", ""),
            translation=bd.get("trans", ""), pos=bd.get("pos", ""),
            level=bd.get("level", ""),
            examples=[Example(**ex) for ex in bd.get("examples", [])],
        )
    return None


def _fetch_free_dict(word: str) -> Optional[WordData]:
    """Provider 3: Free Dictionary API (英文释义 + 例句)"""
    try:
        resp = httpx.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}",
            headers=_BROWSER_HEADERS, timeout=8.0,
        )
        if resp.status_code != 200:
            return None
        entry = resp.json()[0]
        phonetic = entry.get("phonetic", "")
        meanings = entry.get("meanings", [])
        pos = meanings[0].get("partOfSpeech", "") if meanings else ""
        defs = []
        exs = []
        for m in meanings[:2]:
            for d in m.get("definitions", [])[:2]:
                if d.get("definition"):
                    defs.append(d["definition"])
                if d.get("example") and len(exs) < 3:
                    exs.append(Example(sentence_en=d["example"], source="free-dict-api"))
        translation = txt_svc.short_translation("; ".join(defs[:3]))
        return WordData(
            word=word, phonetic_us=phonetic,
            translation=translation, pos=pos, examples=exs,
        )
    except Exception as e:
        logger.warning(f"[Fetch] FreeDict API异常 {word}: {e}")
    return None


def _fetch_baidu(word: str) -> Optional[WordData]:
    """Provider 4: 百度翻译 sug API (国内快、无需 key、中文释义)"""
    try:
        resp = httpx.get(
            f"https://fanyi.baidu.com/sug?kw={word.lower().strip()}",
            headers=_BROWSER_HEADERS, timeout=8.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("errno") != 0:
            return None

        # 精确匹配查询词 (大小写不敏感)
        items = data.get("data", [])
        match = None
        for item in items:
            if item.get("k", "").lower().strip() == word.lower().strip():
                match = item
                break
        if not match:
            return None

        v = match.get("v", "")
        # 解析词性 (如 "n. 苹果; 苹果树" → pos="n.")
        # 格式示例: "n. 书; 卷; 课本 vt.& vi. 预订 vt. 登记"
        import re as _re
        pos = ""
        translation = v
        m = _re.match(r"^([a-z]+(?:\.?&\s*[a-z]+)?)\.?\s+(.*)", v)
        if m:
            pos = m.group(1).strip()
            if not pos.endswith("."):
                pos += "."
            translation = m.group(2)
        # 清理: 只保留第一个词性对应的释义部分 (丢弃后面 "vt. ..." 等)
        translation = _re.sub(r"\s+(?:vt|vi|n|v|adj|adv|prep|pron|conj|int|num|det|art|abbr)\.?(?:&\s*vi|&\s*vt)?\.?\s+.*$", "", translation, count=1)

        return WordData(
            word=word, translation=txt_svc.short_translation(translation), pos=pos,
        )
    except Exception as e:
        logger.warning(f"[Fetch] 百度翻译异常 {word}: {e}")
    return None


def _fetch_datamuse(word: str) -> Optional[WordData]:
    """Provider 4: Datamuse API (免费英文释义，无需 key)"""
    try:
        resp = httpx.get(
            f"https://api.datamuse.com/words?sp={word.lower().strip()}&md=d&max=1",
            headers=_BROWSER_HEADERS, timeout=8.0,
        )
        if resp.status_code != 200:
            return None
        entries = resp.json()
        if not entries:
            return None
        entry = entries[0]
        defs = entry.get("defs") or []
        if not defs:
            return None
        parts = []
        for d in defs[:3]:
            tag, _, text = d.partition("\t")
            parts.append(text)
        translation = txt_svc.short_translation("; ".join(parts))
        pos = ""
        if defs:
            tag = defs[0].partition("\t")[0]
            if tag:
                pos = tag + "."
        return WordData(
            word=word, translation=translation, pos=pos,
        )
    except Exception as e:
        logger.warning(f"[Fetch] Datamuse API异常 {word}: {e}")
    return None


def _fetch_cambridge(word: str) -> Optional[WordData]:
    """Provider 5: 剑桥词典 scraping (英中, 含中文释义)"""
    try:
        resp = httpx.get(
            f"https://dictionary.cambridge.org/dictionary/english-chinese-simplified/{word.lower().strip()}",
            headers=_BROWSER_HEADERS, timeout=10.0, follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # 音标
        phonetic = ""
        pron_els = soup.select(".dpron")
        if pron_els:
            phonetic = pron_els[0].text.strip()

        # 中文释义 (第一个 .trans.dtrans)
        translation = ""
        trans_el = soup.select_one(".trans.dtrans")
        if trans_el:
            translation = trans_el.text.strip()

        # 词性
        pos = ""
        entry = soup.select_one(".pr.di")
        if entry:
            import re
            m = re.search(r"(n|v|adj|adv|prep|pron|conj|interj|num|det)\.", entry.text)
            if m:
                pos = m.group(0)

        # 例句
        examples = []
        for eg in soup.select(".eg.deg")[:5]:
            txt = eg.text.strip()
            if txt:
                examples.append(Example(sentence_en=txt, source="cambridge"))

        if translation:
            return WordData(
                word=word, phonetic_us=phonetic,
                translation=translation, pos=pos, examples=examples,
            )
    except ImportError:
        logger.warning("[Fetch] Cambridge 需要安装 bs4: pip install beautifulsoup4 lxml")
    except Exception as e:
        logger.warning(f"[Fetch] Cambridge 失败 {word}: {e}")
    return None


def _fetch_eudic(word: str) -> Optional[WordData]:
    """Provider 6: 欧陆词典 scraping (英中, 含音标/释义)"""
    try:
        resp = httpx.get(
            f"https://dict.eudic.net/dicts/en/{word.lower().strip()}",
            headers=_BROWSER_HEADERS, timeout=10.0, follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        from bs4 import BeautifulSoup
        import re as _re
        soup = BeautifulSoup(resp.text, "html.parser")

        # 音标: "英/'æpl'/美/'æpl'/" 格式
        phonetic = ""
        info_el = soup.select_one(".explain-word-info")
        if info_el:
            m = _re.search(r"美/([^/]+)/", info_el.text)
            if m:
                phonetic = m.group(1)

        # 释义: 第一个 .explain_wrap 的内容
        translation = ""
        wrap = soup.select_one(".explain_wrap")
        if wrap:
            txt = wrap.get_text(" ", strip=True)
            # 去掉标题头如 "英汉-汉英词典"
            txt = _re.sub(r"^[^\n]*?词典\s*", "", txt)
            # 保留第一个分句
            txt = txt.split("联想词")[0].split("近义词")[0].strip()
            if txt:
                translation = txt_svc.short_translation(txt)

        # 词性
        pos = ""
        if translation:
            m = _re.match(r"^([a-z]+)\.", translation)
            if m:
                pos = m.group(1) + "."

        # 等级
        level = ""
        title_area = soup.select_one(".explain-Word")
        if title_area:
            title_text = title_area.text
            for et in EXAM_LEVEL_MAP:
                if et in title_text:
                    level = EXAM_LEVEL_MAP[et]
                    break

        # 例句 (从英语例句库 section)
        examples = []
        for ex in soup.select(".exp")[:5]:
            txt = ex.text.strip()
            if txt and len(txt) > 5:
                examples.append(Example(sentence_en=txt, source="eudic"))

        if translation:
            return WordData(
                word=word, phonetic_us=phonetic,
                translation=translation, pos=pos, level=level,
                examples=examples,
            )
    except ImportError:
        logger.warning("[Fetch] 欧陆需要安装 bs4: pip install beautifulsoup4 lxml")
    except Exception as e:
        logger.warning(f"[Fetch] 欧陆失败 {word}: {e}")
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主入口 — 按顺序尝试 Provider，一个失败自动试下一个
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_FETCH_PROVIDERS = [
    ("有道API", _fetch_youdao),
    ("百度翻译", _fetch_baidu),
    ("内置词典", _fetch_builtin),
    ("FreeDict API", _fetch_free_dict),
    ("Datamuse API", _fetch_datamuse),
    ("剑桥词典", _fetch_cambridge),
    ("欧陆词典", _fetch_eudic),
]


def _fetch_word_sync(word: str, start_index: int = 0) -> tuple:
    """同步方式获取单词数据 — 从 start_index 开始遍历 Provider 链
    返回 (data, used_index, used_name) — 全部失败返回 (None, -1, None)
    """
    for i in range(start_index, len(_FETCH_PROVIDERS)):
        name, provider_fn = _FETCH_PROVIDERS[i]
        try:
            data = provider_fn(word)
            if data is not None:
                logger.info(f"[Fetch] {name} 成功: {word}")
                return data, i, name
        except Exception as e:
            logger.warning(f"[Fetch] {name} 异常 {word}: {e}")
    logger.warning(f"[Fetch] 所有 API 均失败: {word}")
    return None, -1, None


class FetchWorker(QObject):
    """后台线程 — 从网络获取单词数据 (同步 HTTP，无 asyncio)"""
    finished = Signal(object)       # WordData | None
    # 额外信号: (data, provider_index, provider_name)
    fetch_result = Signal(object, int, object)

    def __init__(self, word: str, start_index: int = 0):
        super().__init__()
        self.word = word
        self.start_index = start_index

    def run(self):
        try:
            data, idx, name = _fetch_word_sync(self.word, self.start_index)
            self.finished.emit(data)
            self.fetch_result.emit(data, idx, name)
        except Exception as e:
            logger.error(f"[FetchWorker] 异常: {e}")
            self.finished.emit(None)
            self.fetch_result.emit(None, -1, None)


class WordEditorDialog(QDialog):
    """新增/编辑单词对话框"""

    def __init__(self, repo: WordRepository, word_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.word_id = word_id

        self.setWindowTitle("新增单词" if word_id is None else "编辑单词")
        self.setMinimumSize(420, 380)
        self.resize(420, 380)

        self._examples: list[dict] = []   # [{"en": ..., "cn": ...}, ...]
        self._example_idx: int = -1
        self._provider_index: int = 0       # 当前使用的 API 序号
        self._provider_name: str = ""       # 当前使用的 API 名称

        self._build_ui()
        self._load_existing()
        # 自动聚焦到单词输入框
        if self.word_id is None:
            self.word_input.setFocus()
            self.word_input.selectAll()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("输入英文单词 (小写)")
        self.word_input.setEnabled(self.word_id is None)
        form.addRow("单词:", self.word_input)

        self.translation_input = QLineEdit()
        self.translation_input.setPlaceholderText("常用释义 (自动截取短释义)")
        form.addRow("释义:", self.translation_input)

        self.phonetic_us_input = QLineEdit()
        self.phonetic_us_input.setPlaceholderText("音标 如 /əˈbɑn.dən/")
        form.addRow("音标:", self.phonetic_us_input)

        self.pos_input = QLineEdit()
        self.pos_input.setPlaceholderText("词性 如 v./n./adj.")
        form.addRow("词性:", self.pos_input)

        # 等级 (从数据库动态加载)
        self.level_combo = QComboBox()
        self.level_combo.addItem("")  # 空 = 不设置
        for lv in self.repo.get_levels():
            self.level_combo.addItem(lv)
        form.addRow("等级:", self.level_combo)

        # ── 左右分栏: 左输入框 + 右图片 ──
        top_row = QHBoxLayout()
        left_col = QVBoxLayout()

        # 缩短输入框宽度
        for i in range(form.count()):
            item = form.itemAt(i)
            if item is not None:
                w = item.widget()
                if isinstance(w, (QLineEdit, QComboBox)):
                    w.setMaximumWidth(180)

        left_col.addLayout(form)

        btn_row = QHBoxLayout()

        self.fetch_btn = QPushButton("🔍 自动获取")
        self.fetch_btn.clicked.connect(self._auto_fetch)
        self.fetch_btn.setMinimumHeight(28)
        btn_row.addWidget(self.fetch_btn)

        self.next_btn = QPushButton("下一个 ▶")
        self.next_btn.setToolTip("切换到下一个 API 重新获取")
        self.next_btn.clicked.connect(self._next_provider)
        self.next_btn.setMinimumHeight(28)
        self.next_btn.setEnabled(False)
        btn_row.addWidget(self.next_btn)

        left_col.addLayout(btn_row)

        top_row.addLayout(left_col, 1)

        # ── 右侧图片区 ──
        self.image_label = QLabel("📷\n暂无图片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setMinimumSize(100, 100)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px dashed #ccc;
                border-radius: 8px;
                background: #fafafa;
                color: #aaa;
                font-size: 12px;
                padding: 4px;
            }
        """)
        top_row.addWidget(self.image_label, 1)

        layout.addLayout(top_row)

        # ── 例句 (单条切换) ──
        group = QGroupBox("例句")
        group_layout = QVBoxLayout(group)

        # 英文例句 (更高字号)
        self.example_en_input = QLineEdit()
        self.example_en_input.setPlaceholderText("English sentence")
        self.example_en_input.setMinimumHeight(36)
        self.example_en_input.setFont(QFont("Segoe UI", 13))
        group_layout.addWidget(self.example_en_input)

        # 中文翻译
        self.example_cn_input = QLineEdit()
        self.example_cn_input.setPlaceholderText("中文翻译")
        self.example_cn_input.setMinimumHeight(36)
        self.example_cn_input.setFont(QFont("Microsoft YaHei", 13))
        group_layout.addWidget(self.example_cn_input)

        # 导航 + 操作按钮
        ex_btn_row = QHBoxLayout()
        self.example_prev_btn = QPushButton("◀ 上一句")
        self.example_prev_btn.setEnabled(False)
        self.example_prev_btn.clicked.connect(self._example_prev)
        self.example_prev_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        ex_btn_row.addWidget(self.example_prev_btn)

        self.example_counter = QLabel("0/0")
        self.example_counter.setStyleSheet("color: #888; font-size: 11px;")
        self.example_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ex_btn_row.addWidget(self.example_counter)

        self.example_next_btn = QPushButton("下一句 ▶")
        self.example_next_btn.setEnabled(False)
        self.example_next_btn.clicked.connect(self._example_next)
        self.example_next_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        ex_btn_row.addWidget(self.example_next_btn)

        ex_btn_row.addStretch()

        self.add_example_btn = QPushButton("+ 添加")
        self.add_example_btn.clicked.connect(self._add_example)
        self.add_example_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        ex_btn_row.addWidget(self.add_example_btn)

        self.del_example_btn = QPushButton("- 删除")
        self.del_example_btn.setEnabled(False)
        self.del_example_btn.clicked.connect(self._delete_current_example)
        self.del_example_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        ex_btn_row.addWidget(self.del_example_btn)

        group_layout.addLayout(ex_btn_row)
        group_layout.addStretch()
        layout.addWidget(group, 1)

        # ── 底部按钮 ──
        bottom = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(self.save_btn)
        bottom.addWidget(self.cancel_btn)
        layout.addLayout(bottom)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

    def _load_existing(self):
        """编辑模式下加载已有数据"""
        if self.word_id is None:
            return
        word = self.repo.get_word(self.word_id)
        if not word:
            return

        self.word_input.setText(word["word"])
        self.word_input.setEnabled(False)
        self.translation_input.setText(word["translation"] or "")
        self.phonetic_us_input.setText(word["phonetic_us"] or "")
        self.pos_input.setText(word["pos"] or "")

        lv = word.get("level", "") or ""
        idx = self.level_combo.findText(lv)
        if idx >= 0:
            self.level_combo.setCurrentIndex(idx)

        # 加载例句
        db_examples = self.repo.get_examples(self.word_id)
        self._examples = [{"en": ex["sentence_en"], "cn": ex.get("sentence_cn", "")}
                          for ex in db_examples]
        self._example_idx = 0 if self._examples else -1
        self._show_example()

        # 加载图片
        self._load_word_image(word["word"])

    def _load_word_image(self, word: str):
        path = img_svc.get_word_image(word)
        if path:
            pix = img_svc.load_pixmap(path)
            if pix:
                self.image_label.setPixmap(pix)
                self.image_label.setStyleSheet("border: 1px solid #ddd; border-radius: 8px; background: #fafafa;")
                return
        self.image_label.setText("📷\n暂无图片")
        self.image_label.setPixmap(QPixmap())
        self.image_label.setStyleSheet("border: 1px dashed #ccc; border-radius: 8px; background: #fafafa; color: #aaa;")

    def _auto_fetch(self):
        """自动从网络获取单词数据 (从第一个 API 开始)"""
        self._provider_index = 0
        self._provider_name = ""
        self._start_fetch()

    def _next_provider(self):
        """切换到下一个 API 重新获取"""
        self._provider_index += 1
        if self._provider_index >= len(_FETCH_PROVIDERS):
            self._provider_index = 0
        self._provider_name = ""
        self._start_fetch()

    def _start_fetch(self):
        """用当前 _provider_index 发起请求"""
        word = self.word_input.text().strip().lower()
        if not word:
            QMessageBox.warning(self, "提示", "请先输入单词")
            return

        provider_count = len(_FETCH_PROVIDERS)
        idx_label = self._provider_index + 1
        provider_name = _FETCH_PROVIDERS[self._provider_index][0]
        self.fetch_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.fetch_btn.setText(f"⏳ 获取中 ({idx_label}/{provider_count})")
        self.status_label.setText(f"正在查询: {provider_name}...")

        # 启动后台线程
        self._worker = FetchWorker(word, start_index=self._provider_index)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_fetch_done)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_fetch_done(self, data: Optional[WordData]):
        self.fetch_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.fetch_btn.setText("🔍 自动获取")

        if data is None:
            self.status_label.setText("❌ 该 API 无结果，点击[下一个]切换来源")
            return

        self.translation_input.setText(data.translation)
        self.phonetic_us_input.setText(data.phonetic_us)
        self.pos_input.setText(data.pos)

        if data.level:
            idx = self.level_combo.findText(data.level)
            if idx >= 0:
                self.level_combo.setCurrentIndex(idx)

        self._examples = [{"en": ex.sentence_en, "cn": ex.sentence_cn}
                          for ex in data.examples[:5]]
        self._example_idx = 0 if self._examples else -1
        self._show_example()

        # 显示数据来源 (优先用 provider 名，更准确)
        provider_count = len(_FETCH_PROVIDERS)
        idx_label = self._provider_index + 1
        src_name = _FETCH_PROVIDERS[self._provider_index][0]
        self.status_label.setText(f"✅ 来源: {src_name} ({idx_label}/{provider_count})")

        # 下载并显示图片
        self._load_word_image(data.word)

    # ── 例句导航 ──────────────────────────────────────

    def _show_example(self):
        """显示当前索引的例句"""
        if 0 <= self._example_idx < len(self._examples):
            ex = self._examples[self._example_idx]
            self.example_en_input.setText(ex.get("en", ""))
            self.example_cn_input.setText(ex.get("cn", ""))
            self.example_counter.setText(f"{self._example_idx + 1}/{len(self._examples)}")
            self.example_prev_btn.setEnabled(self._example_idx > 0)
            self.example_next_btn.setEnabled(self._example_idx < len(self._examples) - 1)
            self.del_example_btn.setEnabled(True)
        else:
            self.example_en_input.clear()
            self.example_cn_input.clear()
            self.example_counter.setText("0/0")
            self.example_prev_btn.setEnabled(False)
            self.example_next_btn.setEnabled(False)
            self.del_example_btn.setEnabled(False)

    def _save_current_example(self):
        """保存当前正在编辑的例句到 _examples 列表"""
        if 0 <= self._example_idx < len(self._examples):
            self._examples[self._example_idx] = {
                "en": self.example_en_input.text().strip(),
                "cn": self.example_cn_input.text().strip(),
            }

    def _example_prev(self):
        self._save_current_example()
        self._example_idx -= 1
        self._show_example()

    def _example_next(self):
        self._save_current_example()
        self._example_idx += 1
        self._show_example()

    def _add_example(self):
        """新增一个空例句并切换到它"""
        self._save_current_example()
        self._examples.append({"en": "", "cn": ""})
        self._example_idx = len(self._examples) - 1
        self._show_example()
        self.example_en_input.setFocus()

    def _delete_current_example(self):
        """删除当前例句"""
        if 0 <= self._example_idx < len(self._examples):
            self._examples.pop(self._example_idx)
            if self._example_idx >= len(self._examples):
                self._example_idx = len(self._examples) - 1
            self._show_example()

    def _collect_examples(self) -> list[tuple[str, str]]:
        """保存当前编辑并从 _examples 收集"""
        self._save_current_example()
        return [(ex["en"], ex["cn"]) for ex in self._examples if ex.get("en", "").strip()]

    def _save(self):
        word = self.word_input.text().strip().lower()
        if not word:
            QMessageBox.warning(self, "提示", "单词不能为空")
            return

        translation = self.translation_input.text().strip()
        phonetic_us = self.phonetic_us_input.text().strip()
        pos = self.pos_input.text().strip()
        level = self.level_combo.currentText()

        if self.word_id:
            self.repo.update_word(
                self.word_id,
                translation=translation,
                phonetic_us=phonetic_us,
                pos=pos,
                level=level,
            )
            self.repo.delete_examples(self.word_id)
            for en, cn in self._collect_examples():
                self.repo.add_example(self.word_id, en, cn, source="manual")
            logger.info(f"[WordEditor] 更新: {word} (id={self.word_id})")
        else:
            wid = self.repo.add_word(
                word, translation=translation,
                phonetic_us=phonetic_us, pos=pos, level=level,
            )
            for en, cn in self._collect_examples():
                self.repo.add_example(wid, en, cn, source="manual")
            logger.info(f"[WordEditor] 新增: {word} (id={wid})")

        self.accept()



