"""设置对话框 — 等级管理 + 同步词库 + 检查升级"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QInputDialog,
    QAbstractItemView, QGroupBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from loguru import logger

from app.db import WordRepository
from app.paths import get_cache_dir


# ── GitHub 仓库配置 ──
GITHUB_REPO = "NeverNG/WordMaster"
GITHUB_BRANCH = "master"
WORDS_DB_PATH = "app/cache/words.db"


# ── 后台工作线程 ──

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
            # 先备份原文件
            backup = db_path.with_suffix(".db.bak")
            if db_path.exists():
                import shutil
                shutil.copy2(db_path, backup)
            db_path.write_bytes(resp.content)
            self.done.emit(True, f"✅ 词库同步完成！({len(resp.content) // 1024} KB)")
        except httpx.HTTPStatusError as e:
            self.done.emit(False, f"❌ 下载失败 (HTTP {e.response.status_code})")
        except Exception as e:
            self.done.emit(False, f"❌ 同步失败: {e}")


class _UpdateWorker(QThread):
    """检查 GitHub 最新版本的线程"""
    progress = Signal(str)
    done = Signal(bool, str, str)  # (success, version_text, download_url)

    def run(self):
        import httpx, json
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
            tag = data.get("tag_name", "unknown")
            name = data.get("name", tag)
            body = (data.get("body") or "")[:300]
            # 找第一个 zip 下载链接
            assets = data.get("assets", [])
            dl_url = assets[0].get("browser_download_url", "") if assets else ""
            if not dl_url:
                dl_url = data.get("zipball_url", "")
            version_text = f"最新版本: {name}\n\n{body}"
            self.done.emit(True, version_text, dl_url)
        except Exception as e:
            self.done.emit(False, f"检查失败: {e}", "")


# ── 设置对话框 ──

class SettingsDialog(QDialog):
    """设置弹窗 — 等级管理 + 词库同步 + 升级检查"""

    def __init__(self, repo: WordRepository, db_path: str = "", parent=None):
        super().__init__(parent)
        self.repo = repo
        self._db_path = db_path or str(get_cache_dir() / "words.db")
        self.setWindowTitle("设置")
        self.setMinimumWidth(420)
        self.setMinimumHeight(420)
        self.resize(440, 480)
        self._sync_worker = None
        self._update_worker = None

        self._build_ui()
        self._load_levels()

    # ── UI 构建 ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ============================================
        # 区域 1: 词库同步 & 升级检查
        # ============================================
        update_group = QGroupBox("🔄 更新")
        update_layout = QVBoxLayout(update_group)

        sync_btn_row = QHBoxLayout()
        self.sync_btn = QPushButton("📥 同步词库")
        self.sync_btn.setToolTip("从 GitHub 下载最新词库")
        self.sync_btn.clicked.connect(self._sync_words)
        sync_btn_row.addWidget(self.sync_btn)

        self.update_btn = QPushButton("🔍 检查升级")
        self.update_btn.setToolTip("检查 GitHub 是否有新版本")
        self.update_btn.clicked.connect(self._check_update)
        sync_btn_row.addWidget(self.update_btn)

        self.open_url_btn = QPushButton("🌐 前往发布页")
        self.open_url_btn.setToolTip("在浏览器中打开 GitHub Releases")
        self.open_url_btn.clicked.connect(self._open_releases)
        self.open_url_btn.setEnabled(False)
        sync_btn_row.addWidget(self.open_url_btn)

        sync_btn_row.addStretch()
        update_layout.addLayout(sync_btn_row)

        self.update_progress = QProgressBar()
        self.update_progress.setVisible(False)
        self.update_progress.setMaximum(0)  # 不确定进度
        update_layout.addWidget(self.update_progress)

        self.update_status = QLabel("")
        self.update_status.setStyleSheet("color: #888; font-size: 11px;")
        self.update_status.setWordWrap(True)
        update_layout.addWidget(self.update_status)

        layout.addWidget(update_group)

        # ============================================
        # 区域 2: 等级管理
        # ============================================
        level_group = QGroupBox("📋 单词等级")
        level_layout = QVBoxLayout(level_group)

        level_tip = QLabel("拖拽可调整顺序，等级显示在卡片和编辑器下拉框中")
        level_tip.setStyleSheet("color: #888; font-size: 11px;")
        level_layout.addWidget(level_tip)

        self.level_list = QListWidget()
        self.level_list.setAlternatingRowColors(True)
        self.level_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.level_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.level_list.setDragEnabled(True)
        self.level_list.setAcceptDrops(True)
        self.level_list.setDropIndicatorShown(True)
        self.level_list.model().rowsMoved.connect(self._on_order_changed)
        level_layout.addWidget(self.level_list)

        level_btn_row = QHBoxLayout()
        self.add_btn = QPushButton("➕ 新增")
        self.add_btn.clicked.connect(self._add_level)
        level_btn_row.addWidget(self.add_btn)

        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.clicked.connect(self._delete_level)
        self.delete_btn.setEnabled(False)
        level_btn_row.addWidget(self.delete_btn)
        level_btn_row.addStretch()
        level_layout.addLayout(level_btn_row)

        self.level_list.itemSelectionChanged.connect(
            lambda: self.delete_btn.setEnabled(
                len(self.level_list.selectedItems()) > 0
            )
        )

        layout.addWidget(level_group, 1)

        # ============================================
        # 底部关闭按钮
        # ============================================
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(self.close_btn)
        layout.addLayout(bottom_row)

    # ── 等级管理 ──

    def _load_levels(self):
        self.level_list.clear()
        levels = self.repo.get_levels()
        for lv in levels:
            item = QListWidgetItem(lv)
            self.level_list.addItem(item)

    def _on_order_changed(self):
        names = [self.level_list.item(i).text() for i in range(self.level_list.count())]
        self.repo.reorder_levels(names)

    def _add_level(self):
        name, ok = QInputDialog.getText(
            self, "新增等级", "等级名称:", QLineEdit.Normal, "",
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

    # ── 词库同步 ──

    def _sync_words(self):
        """从 GitHub 下载最新 words.db"""
        self.sync_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.update_progress.setVisible(True)
        self.update_status.setText("🔄 准备同步...")

        self._sync_worker = _SyncWorker()
        self._sync_worker.progress.connect(self.update_status.setText)
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.start()

    def _on_sync_done(self, ok: bool, msg: str):
        self.sync_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.update_status.setText(msg)
        if ok:
            QMessageBox.information(self, "同步成功",
                "词库已更新。\n提示：如果启用了新的单词，请在管理页面刷新查看。")
        else:
            QMessageBox.warning(self, "同步失败", msg)

    # ── 升级检查 ──

    def _check_update(self):
        """检查 GitHub 最新版本"""
        self.sync_btn.setEnabled(False)
        self.update_btn.setEnabled(False)
        self.open_url_btn.setEnabled(False)
        self.update_progress.setVisible(True)
        self.update_status.setText("🔍 正在检查...")

        self._update_worker = _UpdateWorker()
        self._update_worker.progress.connect(self.update_status.setText)
        self._update_worker.done.connect(self._on_update_done)
        self._update_worker.start()

    def _on_update_done(self, ok: bool, version_text: str, dl_url: str):
        self.sync_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.update_status.setText(version_text if ok else f"❌ {version_text}")

        self._dl_url = dl_url
        self.open_url_btn.setEnabled(bool(dl_url))

        if ok:
            QMessageBox.information(self, "检查更新", version_text)
        else:
            QMessageBox.warning(self, "检查更新", version_text)

    def _open_releases(self):
        """打开 GitHub Releases 页面"""
        import webbrowser
        dl = getattr(self, "_dl_url", "")
        if dl:
            webbrowser.open(dl)
        else:
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases")
