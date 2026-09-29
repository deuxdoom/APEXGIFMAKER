# test_ui.py
"""화면 동작 테스트 (오프스크린). 타임라인에 실제 마우스·휠·키 이벤트를 보내서 구간 규칙을 확인합니다."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap

_bootstrap.setup()

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core import ffmpeg as ff  # noqa: E402
from src.core.encoder import EncodeResult  # noqa: E402
from src.core.ffmpeg import VideoInfo  # noqa: E402
from src.core.gif import GifOptions  # noqa: E402
from src.core.gifinfo import read_gif_info  # noqa: E402
from src.core.settings import Settings  # noqa: E402
from src.core.trim import Selection  # noqa: E402
from src.ui import dialogs, icons, theme  # noqa: E402
from src.ui.app import prepare_app  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.ui.result_dialog import ResultDialog  # noqa: E402
from src.ui.widgets.options_panel import OptionsPanel  # noqa: E402
from src.ui.widgets.output_panel import OutputPanel  # noqa: E402
from src.ui.widgets.timeline import HANDLE_W, TimelineWidget  # noqa: E402
from src.ui.widgets.timeline_panel import TimelinePanel  # noqa: E402
from src.ui.workers import ThumbnailLoader  # noqa: E402

_existing = QApplication.instance()
APP = _existing if isinstance(_existing, QApplication) else QApplication([])
prepare_app(APP, Settings(language="ko", theme="dark"))


def wheel(widget: TimelineWidget, x: float, notches: int, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
    pos = QPointF(x, 40)
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(), QPoint(0, 120 * notches),
                        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


class TimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.w = TimelineWidget()
        self.w.resize(1000, self.w.height())
        self.w.show()
        self.w.set_video(100.0, 16 / 9, 1 / 30)

    def tearDown(self) -> None:
        self.w.close()
        self.w.deleteLater()

    def drag(self, start_x: float, end_x: float) -> Selection:
        y = 50
        QTest.mousePress(self.w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(start_x), y))
        QTest.mouseMove(self.w, QPoint(int((start_x + end_x) / 2), y))
        QTest.mouseMove(self.w, QPoint(int(end_x), y))
        QTest.mouseRelease(self.w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(end_x), y))
        return self.w.selection()

    def test_initial(self):
        self.assertEqual(self.w.selection(), Selection(0.0, 6.0))
        self.assertFalse(self.w.is_zoomed())

    def test_end_handle_moves_only_end(self):
        sel = self.drag(self.w._x(6.0) + HANDLE_W / 2, self.w._x(10.0) + HANDLE_W / 2)
        self.assertAlmostEqual(sel.start, 0.0)
        self.assertAlmostEqual(sel.end, 10.0, delta=0.15)

    def test_start_handle_stops_at_min_length(self):
        self.w.set_selection(Selection(10.0, 16.0))
        sel = self.drag(self.w._x(10.0) - HANDLE_W / 2, self.w._x(15.9) - HANDLE_W / 2)
        self.assertEqual(sel, Selection(15.0, 16.0))

    def test_end_handle_stops_at_max_length(self):
        sel = self.drag(self.w._x(6.0) + HANDLE_W / 2, self.w._x(80.0) + HANDLE_W / 2)
        self.assertEqual(sel, Selection(0.0, 30.0))

    def test_middle_drag_moves_selection(self):
        sel = self.drag(self.w._x(3.0), self.w._x(13.0))
        self.assertAlmostEqual(sel.start, 10.0, delta=0.15)
        self.assertAlmostEqual(sel.length, 6.0, delta=0.002)

    def test_click_outside_recenters(self):
        QTest.mouseClick(self.w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(self.w._x(50.0)), 50))
        sel = self.w.selection()
        self.assertAlmostEqual((sel.start + sel.end) / 2, 50.0, delta=0.15)

    def test_wheel_zoom_and_pan(self):
        wheel(self.w, self.w._x(50.0), 2)
        self.assertTrue(self.w.is_zoomed())
        before = self.w._view0
        wheel(self.w, self.w._x(50.0), -1, Qt.KeyboardModifier.ShiftModifier)
        self.assertGreater(self.w._view0, before)
        self.w.zoom_fit()
        self.assertFalse(self.w.is_zoomed())

    def test_keyboard(self):
        self.w.setFocus()
        QTest.keyClick(self.w, Qt.Key.Key_Right)
        self.assertEqual(self.w.selection(), Selection(0.1, 6.1))
        QTest.keyClick(self.w, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.w.selection(), Selection(1.1, 7.1))
        QTest.keyClick(self.w, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.w.selection(), Selection(1.1, 7.2))
        QTest.keyClick(self.w, Qt.Key.Key_End)
        self.assertEqual(self.w.selection().end, 100.0)

    def test_long_video_starts_zoomed_and_requests_thumbnails(self):
        requested: list[list[float]] = []
        self.w.thumbnailsNeeded.connect(requested.append)
        self.w.set_video(3600.0, 16 / 9, 1 / 30)
        self.assertTrue(self.w.is_zoomed())
        self.w.repaint()
        QTest.qWait(200)
        self.assertTrue(requested and all(0 <= t <= 3600 for t in requested[-1]))


class TimelinePanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.panel = TimelinePanel()
        self.panel.set_video_loaded(True)
        self.panel.timeline.set_video(100.0, 16 / 9, 1 / 30)

    def type_into(self, field, text: str) -> None:
        field.edit.setText(text)
        field.edit.editingFinished.emit()

    def test_typed_values(self):
        self.type_into(self.panel.start_field, "00:10.000")
        self.assertEqual(self.panel.selection(), Selection(10.0, 16.0))
        self.type_into(self.panel.length_field, "3")
        self.assertEqual(self.panel.selection(), Selection(10.0, 13.0))
        self.type_into(self.panel.end_field, "0:12.5")
        self.assertEqual(self.panel.selection(), Selection(10.0, 12.5))
        self.assertEqual(self.panel.end_field.edit.text(), "00:12.500")

    def test_invalid_input_is_reverted(self):
        self.type_into(self.panel.start_field, "abc")
        self.assertEqual(self.panel.start_field.edit.text(), "00:00.000")
        self.assertEqual(self.panel.start_field.box.property("invalid"), "true")

    def test_nudge_buttons(self):
        self.panel.end_field.forward.click()
        self.assertEqual(self.panel.selection(), Selection(0.0, 6.1))
        self.panel.start_field.forward.click()
        self.assertEqual(self.panel.selection(), Selection(0.1, 6.1))

    def test_commit_pending_edit(self):
        # Enter 없이 입력만 한 값도 commit_edits()로 반영됩니다. (Ctrl+Enter 단축키 대비)
        self.panel.start_field.edit.setText("00:20.000")
        self.assertEqual(self.panel.selection(), Selection(0.0, 6.0))
        self.panel.commit_edits()
        self.assertEqual(self.panel.selection(), Selection(20.0, 26.0))
        self.panel.commit_edits()                                  # 바뀐 것이 없으면 그대로
        self.assertEqual(self.panel.selection(), Selection(20.0, 26.0))

    def test_frames_chip(self):
        self.panel.set_frame_settings(10, False)
        self.assertIn("60", self.panel.frames_chip.text())
        self.panel.timeline.set_selection(Selection(0.0, 20.0))
        self.assertFalse(self.panel.reco_chip.isHidden())


class PanelTests(unittest.TestCase):
    def test_output_names(self):
        panel = OutputPanel()
        panel.reset_name("clip_0_6000.gif")
        panel.set_auto_name("clip_1000_7000.gif")
        self.assertEqual(panel.filename(), "clip_1000_7000.gif")
        panel.name_edit.setText("mine")
        panel.name_edit.textEdited.emit("mine")
        panel.set_auto_name("clip_2000_8000.gif")
        self.assertEqual(panel.filename(), "mine.gif")
        panel.use_auto_name()
        self.assertEqual(panel.filename(), "clip_2000_8000.gif")
        panel.name_edit.setText("a:b?.gif")
        self.assertEqual(panel.invalid_chars(), ":?")

    def test_options_round_trip(self):
        panel = OptionsPanel()
        opts = GifOptions(width=240, height=120, fps=20, scale_mode="letterbox", dither="bayer", frame_mode="dedupe")
        panel.set_options(opts)
        self.assertEqual(panel.options(), opts)
        panel.reset_button.click()
        self.assertEqual((panel.options().width, panel.options().height), (160, 80))
        panel.width_spin.lineEdit().setText("320")                 # 입력 중에는 값이 바뀌지 않습니다.
        self.assertEqual(panel.options().width, 160)
        panel.commit_edits()
        self.assertEqual(panel.options().width, 320)


class LoaderTests(unittest.TestCase):
    def test_thumbnail_requests_stop_running_ffmpeg(self):
        started = threading.Event()
        signals: list[threading.Event] = []

        def fake_grab(*_args, **kwargs):
            cancel = kwargs["cancel"]
            signals.append(cancel)
            started.set()
            if cancel.wait(5):
                raise ff.Cancelled()
            return b""

        loader = ThumbnailLoader()
        loader.set_source("ffmpeg", "clip.mp4", 58, 16 / 9)
        with mock.patch("src.ui.workers.ff.grab_frame", fake_grab):
            loader.request([1.0])
            self.assertTrue(started.wait(5))
            loader.request([2.0])              # 1초 칸이 화면에서 사라지면 추출 중인 ffmpeg도 멈춥니다.
            self.assertTrue(signals[0].is_set())
            self.assertEqual(list(loader._jobs), [2000])
            loader.shutdown()                  # 앱을 닫으면 남은 추출도 모두 멈추고, 새 요청은 받지 않습니다.
            self.assertTrue(all(signal.is_set() for signal in signals))
            loader.request([3.0])
            self.assertEqual(loader._jobs, {})


class WindowTests(unittest.TestCase):
    def test_main_window_and_themes(self):
        window = MainWindow(Settings(confirm_exit=False), background=False, persist=False)
        window.show()
        QTest.qWait(50)
        self.assertIn("APEX", window.title_bar.title_label.text())
        window.frame.maximize()
        self.assertEqual(window.shell.surface.property("fullBleed"), "true")
        window.frame.restore()
        for mode in ("light", "dark"):
            self.assertEqual(theme.manager().apply(mode).name, mode)
            icons.refresh_all()
            self.assertFalse(window.grab().isNull())
        window.close()

    def test_generate_uses_pending_edits(self):
        # 시간·크기를 입력하고 Enter 없이 Ctrl+Enter(= generate)를 눌러도 입력한 값으로 만듭니다.
        folder = Path(tempfile.mkdtemp(prefix="window-"))
        self.addCleanup(shutil.rmtree, folder, True)
        window = MainWindow(Settings(confirm_exit=False, output_dir=str(folder)), background=False, persist=False)
        window.show()
        window.ffmpeg = sys.executable                            # 실제로 실행하지는 않습니다(GifJob을 바꿔 끼움).
        window.video = VideoInfo(str(folder / "clip.mp4"), 100.0, 1920, 1080, 30.0, "h264")
        window.timeline.set_video(100.0, 16 / 9, 1 / 30)
        window.timeline_panel.set_video_loaded(True)
        window.timeline_panel.start_field.edit.setText("12")
        window.options_panel.fps_spin.lineEdit().setText("20")
        with mock.patch("src.ui.main_window.GifJob") as job_class:
            window.generate()
        encoder = job_class.call_args.args[0]
        self.assertEqual((encoder.start, encoder.end, encoder.options.fps), (12.0, 18.0, 20))
        self.assertFalse(window.timeline_panel.play_button.isEnabled())    # 만드는 동안 구간 재생은 꺼짐
        window._finish_job()
        self.assertTrue(window.timeline_panel.play_button.isEnabled())
        window.close()

    def test_dialogs(self):
        box = dialogs.MessageDialog(None, "t", "text", kind="question",
                                    buttons=(("no", "", ""), ("yes", "", "primary")), checkbox="c")
        box.show()
        box._choose("yes")
        self.assertEqual(box.choice, "yes")
        about = dialogs.AboutDialog(None, "9.0.2-essentials_build")
        about.show()
        about.close()

    def test_result_dialog(self):
        from test_core import make_gif
        folder = Path(tempfile.mkdtemp(prefix="result-"))
        self.addCleanup(shutil.rmtree, folder, True)
        path = folder / "out.gif"
        path.write_bytes(make_gif([8, 9, 8]))
        dialog = ResultDialog(None, EncodeResult(str(path), read_gif_info(path), 1.2))
        dialog.show()
        QTest.qWait(50)
        dialog.accept()


if __name__ == "__main__":
    unittest.main()
