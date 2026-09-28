# dialogs.py
"""테마를 따르는 메시지 대화상자와 정보(About) 창입니다. 모두 프레임 없는 모양으로 감쌉니다."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core import config
from ..core.ffmpeg import short_version
from ..i18n import tr
from . import icons
from .frame import app_icon_pixmap, apply_dialog_frame, run_dialog
from .widgets.common import Chip, make_button, make_label

_KINDS = {"info": ("info", "accent"), "warning": ("warning", "warning"),
          "error": ("error_circle", "danger"), "question": ("help", "accent"),
          "success": ("check_circle", "success")}


class MessageDialog(QDialog):
    """아이콘 + 본문 + (선택) 체크박스 + 단추 줄. 누른 단추의 키가 choice에 남습니다."""

    def __init__(self, parent: QWidget | None, title: str, text: str, *, kind: str = "info",
                 buttons: tuple[tuple[str, str, str], ...] = (("ok", "", "primary"),),
                 default: str = "ok", checkbox: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.choice = ""
        self.setMinimumWidth(380)
        self.setMaximumWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        root.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(14)
        icon_name, role = _KINDS.get(kind, _KINDS["info"])
        glyph = QLabel()
        icons.set_icon(glyph, icon_name, role, 28)
        glyph.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMinimumWidth(300)
        row.addWidget(body, 1)
        root.addLayout(row)
        self.checkbox: QCheckBox | None = None
        if checkbox:
            self.checkbox = QCheckBox(checkbox)
            root.addWidget(self.checkbox)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addStretch(1)
        for key, label, variant in buttons:
            button = make_button(label or tr(f"dlg.{key}"), variant=variant)
            button.clicked.connect(lambda _=False, k=key: self._choose(k))
            if key == default:
                button.setDefault(True)
                button.setFocus()
            buttons_row.addWidget(button)
        root.addLayout(buttons_row)
        apply_dialog_frame(self, title=title)

    def _choose(self, key: str) -> None:
        self.choice = key
        self.accept()

    def checked(self) -> bool:
        return self.checkbox is not None and self.checkbox.isChecked()


def info(parent: QWidget | None, text: str, title: str = "", kind: str = "info") -> None:
    run_dialog(MessageDialog(parent, title or tr("dlg.info"), text, kind=kind))


def warn(parent: QWidget | None, text: str, title: str = "") -> None:
    run_dialog(MessageDialog(parent, title or tr("dlg.warning"), text, kind="warning"))


def error(parent: QWidget | None, text: str, title: str = "") -> None:
    run_dialog(MessageDialog(parent, title or tr("dlg.error"), text, kind="error"))


def ask(parent: QWidget | None, text: str, title: str, *, yes: str = "", no: str = "",
        danger: bool = False, checkbox: str = "") -> tuple[bool, bool]:
    """예/아니요를 묻습니다. (예를 골랐는지, 체크박스를 켰는지)"""
    dialog = MessageDialog(parent, title, text, kind="warning" if danger else "question",
                           buttons=(("no", no, ""), ("yes", yes, "danger" if danger else "primary")),
                           default="yes", checkbox=checkbox)
    try:
        dialog.exec()
        return dialog.choice == "yes", dialog.checked()
    finally:
        dialog.deleteLater()


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


class AboutDialog(QDialog):
    checkUpdateRequested = Signal()

    def __init__(self, parent: QWidget | None, ffmpeg_version: str):
        super().__init__(parent)
        self.setWindowTitle(tr("about.title"))
        self.setModal(True)
        self.setFixedWidth(500)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(app_icon_pixmap(60))
        top.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(3)
        names.addWidget(make_label(config.APP_NAME, "Heading"))
        names.addWidget(make_label(tr("about.tagline"), "Muted"))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(Chip(tr("about.version", version=config.APP_VERSION), "accent"))
        ffmpeg_chip = Chip(tr("about.ffmpeg", version=short_version(ffmpeg_version)) if ffmpeg_version
                           else tr("about.ffmpeg_missing"), "neutral" if ffmpeg_version else "warning")
        ffmpeg_chip.setToolTip(ffmpeg_version)
        chips.addWidget(ffmpeg_chip)
        chips.addStretch(1)
        names.addLayout(chips)
        top.addLayout(names, 1)
        root.addLayout(top)

        description = QLabel(tr("about.description"))
        description.setWordWrap(True)
        root.addWidget(description)

        links = QGridLayout()
        links.setHorizontalSpacing(8)
        links.setVerticalSpacing(8)
        entries = (
            ("GitHub", "code", config.REPO_URL), (tr("about.changelog"), "changelog", config.CHANGELOG_URL),
            (tr("menu.check_update"), "sync", ""), (tr("about.issues"), "bug", config.ISSUES_URL),
            (tr("about.sponsor"), "heart", config.SPONSOR_URL), ("YouTube", "video", config.YOUTUBE_URL),
        )
        for index, (label, icon_name, url) in enumerate(entries):
            button = make_button(label, icon_name)
            if url:
                button.clicked.connect(lambda _=False, u=url: open_url(u))
            else:
                button.clicked.connect(self.checkUpdateRequested.emit)
            links.addWidget(button, index // 3, index % 3)
        root.addLayout(links)

        root.addWidget(make_label(tr("about.credits"), "FieldLabel"))
        credits = make_label(tr("about.credits_text"), "Hint")
        credits.setWordWrap(True)
        root.addWidget(credits)
        root.addWidget(make_label(f"MIT License · © {config.REPO_OWNER}", "Hint"))

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = make_button(tr("dlg.close"), variant="primary")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)
        apply_dialog_frame(self, title=tr("about.title"))
