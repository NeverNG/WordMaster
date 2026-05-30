"""设置对话框 — 朗读设置 + 词库同步 + 检查升级"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QProgressBar,
)
from PySide6.QtCore import QThread, Signal
from loguru import logger
from app.services import settings as setsvc
from app.paths import get_cache_dir


# ── GitHub 仓库配置 ──
GITHUB_REPO = "NeverNG/WordMaster"
GITHUB_BRANCH = "master"
WORDS_DB_PATH = "app/cache/words.db"


class _SyncWorker(QThread):
    """后台下载 words.db 的线程"""
    progress = Signal(str)
    done = Signal(bool, str)

    def run(self):
        import httpx
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{WORDS_DB_PATH}"
        self.progress.emit("正在从 GitHub 下载词库...")
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            db_path = get_cache_dir() / "words.db"
            backup = db_path.with_suffix(".db.bak")
            if db_path.exists():
                import shutil
                shutil.copy2(db_path, backup)
            db_path.write_bytes(resp.content)
            size_kb = len(resp.content) // 1024
            self.done.emit(True, f"✅ 词库同步完成！({size_kb} KB)")
        except httpx.HTTPStatusError as e:
            self.done.emit(False, f"❌ 下载失败 (HTTP {e.response.status_code})")
        except Exception as e:
            self.done.emit(False, f"❌ 同步失败: {e}")


class _UpdateWorker(QThread):
    """检查 GitHub 最新版本的线程"""
    progress = Signal(str)
    done = Signal(bool, str, str)

    def run(self):
        import httpx
        from main import VERSION as _local_ver
        self.progress.emit("正在检查更新...")
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                timeout=15,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 404:
                self.done.emit(False, "暂无发布版本", "")
                return
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name", "").lstrip("v")
            name = data.get("name", tag)
            body = (data.get("body") or "")[:300]
            assets = data.get("assets", [])
            dl_url = assets[0].get("browser_download_url", "") if assets else ""
            if not dl_url:
                dl_url = data.get("zipball_url", "")

            # 版本比较
            from packaging.version import Version
            remote_v = Version(tag) if tag else None
            local_v = Version(_local_ver)
            if remote_v and remote_v > local_v:
                summary = f"发现新版本: {name}\n当前版本: v{_local_ver}\n\n{body}"
            elif remote_v:
                summary = f"✅ 已是最新版本 (v{_local_ver})"
            else:
                summary = f"当前版本: v{_local_ver}\n无法获取远程版本号"

            self.done.emit(True, summary, dl_url)
        except ImportError:
            # 没有 packaging 库时降级
            self.done.emit(True, f"当前版本: v{_local_ver}\n最新: {name}\n\n{body}", dl_url)
        except Exception as e:
            self.done.emit(False, f"检查失败: {e}", "")


class QuickSettingsDialog(QDialog):
    """设置弹窗 — 朗读设置 + 词库同步 + 检查升级"""

    def __init__(self, learning_tab, parent=None):
        super().__init__(parent)
        self.learning_tab = learning_tab
        self.repo = learning_tab.repo
        self.setWindowTitle("设置")
        self.setFixedSize(340, 300)
        self._sync_worker = None
        self._update_worker = None
        self._dl_url = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ========== 区域 1: 朗读设置 ==========
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

        wr, er = setsvc.load_audio_settings()
        self.word_spin.setValue(wr)
        self.example_spin.setValue(er)
        self.delay_spin.setValue(setsvc.load_auto_delay())

        # ========== 区域 2: 更新 ==========
        layout.addSpacing(8)
        sep = QLabel("─" * 30)
        sep.setStyleSheet("color: #ddd;")
        layout.addWidget(sep)

        layout.addWidget(QLabel("🔄 同步与升级"))

        sync_row = QHBoxLayout()
        self.sync_btn = QPushButton("📥 同步词库")
        self.sync_btn.setToolTip("从 GitHub 下载最新词库")
        self.sync_btn.clicked.connect(self._sync_words)
        sync_row.addWidget(self.sync_btn)

        self.update_btn = QPushButton("🔍 检查升级")
        self.update_btn.setToolTip("检查 GitHub 是否有新版本")
        self.update_btn.clicked.connect(self._check_update)
        sync_row.addWidget(self.update_btn)

        self.open_url_btn = QPushButton("🌐 下载")
        self.open_url_btn.setToolTip("在浏览器中打开下载页面")
        self.open_url_btn.clicked.connect(self._open_releases)
        self.open_url_btn.setEnabled(False)
        sync_row.addWidget(self.open_url_btn)

        layout.addLayout(sync_row)

        self.update_progress = QProgressBar()
        self.update_progress.setVisible(False)
        self.update_progress.setMaximum(0)
        layout.addWidget(self.update_progress)

        self.sync_status = QLabel("")
        self.sync_status.setStyleSheet("color: #888; font-size: 11px;")
        self.sync_status.setWordWrap(True)
        layout.addWidget(self.sync_status)

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

    # ── 同步词库 ──

    def _sync_words(self):
        self.sync_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.update_progress.setVisible(True)
        self.sync_status.setText("🔄 准备同步...")

        self._sync_worker = _SyncWorker()
        self._sync_worker.progress.connect(self.sync_status.setText)
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.start()

    def _on_sync_done(self, ok: bool, msg: str):
        self.sync_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.sync_status.setText(msg)
        if ok:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "同步成功", "词库已更新！")

    # ── 检查升级 ──

    def _check_update(self):
        self.sync_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.open_url_btn.setEnabled(False)
        self.update_progress.setVisible(True)
        self.sync_status.setText("🔍 正在检查...")

        self._update_worker = _UpdateWorker()
        self._update_worker.progress.connect(self.sync_status.setText)
        self._update_worker.done.connect(self._on_update_done)
        self._update_worker.start()

    def _on_update_done(self, ok: bool, version_text: str, dl_url: str):
        self.sync_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.sync_status.setText(version_text if ok else f"❌ {version_text}")
        self._dl_url = dl_url
        is_new = "发现新版本" in version_text if ok else False
        self.open_url_btn.setEnabled(bool(dl_url) and is_new)
        if ok:
            from PySide6.QtWidgets import QMessageBox
            if "已是最新" in version_text:
                QMessageBox.information(self, "检查更新", version_text)
            else:
                reply = QMessageBox.question(self, "发现新版本",
                    version_text + "\n\n是否前往下载？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes and dl_url:
                    self._open_releases()

    def _open_releases(self):
        import webbrowser
        if self._dl_url:
            webbrowser.open(self._dl_url)
        else:
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases")
