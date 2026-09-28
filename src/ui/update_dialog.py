# update_dialog.py
"""새 버전 안내 → 받기 → SHA-256 검증 → 압축 풀기까지를 한 창에서 진행합니다.

교체는 이 창에서 하지 않습니다. 준비가 끝나면 accept()로 닫히고, 호출한 쪽이 적용 모드를 띄운 뒤 앱을 끝냅니다.
자동 업데이트를 할 수 없는 경우(소스 실행, 검증 가능한 파일 없음, 폴더에 쓸 수 없음)에는 이유와 함께
다운로드 페이지 단추만 보여 줍니다.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..core import config, self_update
from ..core.updater import ReleaseInfo, release_highlights
from ..i18n import tr
from .dialogs import open_url
from .frame import apply_dialog_frame
from .result_dialog import format_size
from .widgets.common import Chip, make_button, make_label
from .workers import UpdateDownloadJob


class UpdateDialog(QDialog):
    def __init__(self, parent: QWidget | None, release: ReleaseInfo):
        super().__init__(parent)
        self.setWindowTitle(tr("msg.update.title"))
        self.setModal(True)
        self.setFixedWidth(520)
        self.release = release
        self.work: Path | None = None
        self._job: UpdateDownloadJob | None = None
        asset = release.asset

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 14, 22, 18)
        root.setSpacing(12)
        root.addWidget(make_label(tr("update.heading", version=release.version_text), "Heading"))
        meta = [tr("update.current", version=config.APP_VERSION)]
        if asset is not None:
            meta.append(format_size(asset.size))
        if release.published_at:
            meta.append(release.published_at[:10])
        root.addWidget(make_label(" · ".join(meta), "Muted"))

        notes = release_highlights(release.body)
        if notes:
            text = QLabel("<ul style='margin-left:-18px'>" + "".join(f"<li>{_escape(n)}</li>" for n in notes)
                          + "</ul>")
            text.setWordWrap(True)
            root.addWidget(text)

        self.reason = QLabel()
        self.reason.setWordWrap(True)
        self.reason.setObjectName("Muted")
        root.addWidget(self.reason)

        sha_row = QHBoxLayout()
        sha_row.setSpacing(8)
        self.sha_label = make_label("", "Hint")
        self.verified_chip = Chip(tr("update.verified"), "success")
        self.verified_chip.setVisible(False)
        sha_row.addWidget(self.sha_label, 1)
        sha_row.addWidget(self.verified_chip)
        root.addLayout(sha_row)
        if asset is not None:
            self.sha_label.setText(f"SHA-256  {asset.sha256[:16]}…{asset.sha256[-8:]}")
            self.sha_label.setToolTip(asset.sha256)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.stage = make_label("", "Hint")
        root.addWidget(self.progress)
        root.addWidget(self.stage)
        self.progress.setVisible(False)
        self.stage.setVisible(False)

        buttons = QHBoxLayout()
        self.notes_button = make_button(tr("update.notes"), "changelog")
        self.page_button = make_button(tr("update.open_page"), "open_external")
        self.later_button = make_button(tr("update.later"))
        self.update_button = make_button(tr("update.now"), "download", variant="primary")
        buttons.addWidget(self.notes_button)
        buttons.addStretch(1)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.page_button)
        buttons.addWidget(self.update_button)
        root.addLayout(buttons)

        self.notes_button.clicked.connect(lambda: open_url(release.html_url))
        self.page_button.clicked.connect(self._open_page)
        self.later_button.clicked.connect(self.reject)
        self.update_button.clicked.connect(self._start)
        self._set_mode(self._blocked_reason())
        apply_dialog_frame(self, title=tr("msg.update.title"))

    def _blocked_reason(self) -> str:
        if not self_update.supported():
            return tr("update.source_mode")
        if self.release.asset is None:
            return tr("update.no_verified_asset")
        return ""

    def _set_mode(self, blocked_reason: str) -> None:
        """자동 업데이트가 막혔으면 이유와 다운로드 페이지 단추만 보여 줍니다."""
        self.reason.setText(blocked_reason)
        self.reason.setVisible(bool(blocked_reason))
        self.update_button.setVisible(not blocked_reason)
        self.page_button.setVisible(bool(blocked_reason))
        if blocked_reason:
            self.page_button.setProperty("variant", "primary")

    def _open_page(self) -> None:
        open_url(self.release.html_url)
        self.reject()

    def _start(self) -> None:
        asset = self.release.asset
        work = self_update.prepare_workspace()
        if asset is None or work is None:
            self._set_mode(tr("update.unwritable"))
            return
        self.work = work
        self.update_button.setEnabled(False)
        self.later_button.setText(tr("dlg.cancel"))
        self.progress.setVisible(True)
        self.stage.setVisible(True)
        self.progress.setRange(0, 0)
        job = UpdateDownloadJob(asset, work, self)
        job.progressChanged.connect(self._on_progress)
        job.succeeded.connect(self._on_succeeded)
        job.failed.connect(self._on_failed)
        job.cancelled.connect(self._on_cancelled)
        self._job = job
        job.start()

    def _on_progress(self, task: str, done: int, total: int) -> None:
        if task == "download":
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done * 1000 / total) if total else 0)
            self.stage.setText(tr("update.downloading", done=format_size(done), total=format_size(total)))
        elif task == "verify":
            self.verified_chip.setVisible(True)
            self.progress.setRange(0, 0)
            self.stage.setText(tr("update.extracting"))
        else:
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(done)

    def _on_succeeded(self, _work: str) -> None:
        self._job = None
        self.stage.setText(tr("update.ready"))
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._job = None
        self_update.cleanup_workspace()
        self.work = None
        self.progress.setVisible(False)
        self.verified_chip.setVisible(False)
        self.stage.setText(tr("update.failed", error=message))
        self.update_button.setEnabled(True)
        self.update_button.setText(tr("update.retry"))
        self.later_button.setText(tr("dlg.close"))
        self.page_button.setVisible(True)

    def _on_cancelled(self) -> None:
        self._job = None
        self_update.cleanup_workspace()
        self.work = None
        super().reject()

    def reject(self) -> None:
        """다운로드 중이면 먼저 멈추고, 스레드가 끝난 뒤(_on_cancelled)에 닫습니다."""
        if self._job is not None and self._job.isRunning():
            self._job.cancel()
            self.later_button.setEnabled(False)
            return
        super().reject()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
