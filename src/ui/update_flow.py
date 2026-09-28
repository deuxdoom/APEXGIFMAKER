# update_flow.py
"""업데이트 확인부터 적용 모드 실행, 다음 실행 때 결과 안내까지의 흐름을 메인 창에서 떼어 둡니다."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QDialog

from ..core import config, self_update
from ..core.updater import ReleaseInfo, UpdateCheckError, fetch_latest_release, is_newer
from ..i18n import tr
from . import dialogs
from .frame import run_dialog
from .update_dialog import UpdateDialog

if TYPE_CHECKING:
    from .main_window import MainWindow


def _fetch() -> ReleaseInfo:
    try:
        return fetch_latest_release()
    except UpdateCheckError as exc:
        if exc.reason == "rate_limited":
            raise RuntimeError(tr("update.rate_limited")) from None
        raise


class UpdateFlow(QObject):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.window = window
        self._checking = False

    def check(self, silent: bool) -> None:
        """silent=True(시작할 때)이면 최신 버전이거나 실패했을 때 창을 띄우지 않고 로그만 남깁니다."""
        if self._checking:
            return
        self._checking = True
        self.window.tasks.submit(("update", silent), _fetch)

    def on_result(self, silent: bool, release: object) -> None:
        self._checking = False
        if not isinstance(release, ReleaseInfo):
            return
        if is_newer(release.tag, config.APP_VERSION):
            self.window.log(f"[UPDATE] {tr('log.update_available', tag=release.tag)}")
            self._offer(release)
        else:
            self.window.log(f"[UPDATE] {tr('log.update_latest', version=config.APP_VERSION)}")
            if not silent:
                dialogs.info(self.window, tr("msg.update_latest", version=config.APP_VERSION),
                             tr("msg.update.title"), kind="success")

    def on_error(self, silent: bool, message: str) -> None:
        self._checking = False
        self.window.log(f"[UPDATE] {tr('log.update_failed', error=message)}")
        if not silent:
            dialogs.error(self.window, tr("msg.update_failed", error=message), tr("msg.update.title"))

    def _offer(self, release: ReleaseInfo) -> None:
        dialog = UpdateDialog(self.window, release)
        accepted = run_dialog(dialog) == QDialog.DialogCode.Accepted.value
        work = dialog.work
        if not accepted or work is None:
            return
        if self_update.launch_apply_mode(work, os.getpid(), config.APP_VERSION):
            self.window.log(f"[UPDATE] {tr('update.ready')}")
            self.window.quit_for_update()
            return
        self_update.cleanup_workspace()
        dialogs.error(self.window, tr("update.launch_failed"), tr("msg.update.title"))
        dialogs.open_url(release.html_url)

    def report_previous_result(self) -> None:
        """직전 실행에서 적용한 업데이트의 결과(result.json)를 알리고 작업 폴더를 정리합니다."""
        result = self_update.read_result()
        if not result:
            self_update.cleanup_workspace()     # 중간에 멈춘 업데이트가 남긴 폴더
            return
        from_version, to_version = str(result.get("from_version", "")), str(result.get("to_version", ""))
        if result.get("ok"):
            self.window.log(f"[UPDATE] {tr('log.update_applied', from_version=from_version, to_version=to_version)}")
            QTimer.singleShot(400, lambda: dialogs.info(
                self.window, tr("msg.update_applied", version=to_version), tr("msg.update.title"), kind="success"))
        else:
            error = str(result.get("error", ""))
            self.window.log(f"[UPDATE] {tr('msg.update_rolled_back', error=error)}")
            QTimer.singleShot(400, lambda: dialogs.warn(
                self.window, tr("msg.update_rolled_back", error=error), tr("msg.update.title")))
        # 적용 창이 아직 new/ 폴더의 exe로 떠 있을 수 있어 조금 기다렸다가 지웁니다. (남으면 다음 실행 때 지움)
        QTimer.singleShot(5000, self_update.cleanup_workspace)
