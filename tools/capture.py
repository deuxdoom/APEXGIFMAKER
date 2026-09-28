# capture.py
"""화면을 띄우지 않고(오프스크린) 메인 창과 대화상자를 PNG로 찍습니다. README·소개 페이지 그림과 디자인 확인용입니다.

    python tools/capture.py --docs                 README와 소개 페이지 그림을 새로 만들어 docs/images에 넣습니다.
    python tools/capture.py 동영상.mp4 [--theme dark|light] [--lang ko] [--out 폴더] [--dialogs]

--docs는 현재 화면·버전으로 docs/images/main.png(README)와 docs/images/app-preview.webp(소개 페이지)를
다시 만듭니다. 동영상을 주지 않으면 ffmpeg로 데모 영상을 만들어 씁니다. UI나 버전이 바뀌었으면 커밋 전에 실행합니다.
그 밖의 결과는 기본적으로 F:/temp/APEXGIFMAKER/capture/ 아래에 저장합니다.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.setup()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QImageWriter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from src.core import ffmpeg as ff  # noqa: E402
from src.core.settings import Settings  # noqa: E402
from src.core.trim import Selection  # noqa: E402
from src.ui.app import prepare_app  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_until(condition, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        wait(50)
    return condition()


def save(widget: QWidget, path: Path) -> None:
    widget.grab().save(str(path), "PNG")
    print(f"saved {path}")


def make_demo_video(folder: Path) -> Path:
    """로고 색에 맞춘 20초짜리 그라데이션 데모 영상을 만듭니다. (이미 있으면 그대로 씀)"""
    target = folder / "demo.mp4"
    if target.is_file():
        return target
    ffmpeg_path = ff.find_executable("ffmpeg")
    if not ffmpeg_path:
        raise SystemExit("ffmpeg가 없어 데모 영상을 만들 수 없습니다. 앱을 한 번 실행해 bin 폴더에 받아 두세요.")
    source = ("gradients=s=1280x720:d=20:r=30:c0=0x061a3a:c1=0x398fe1:c2=0x0867c4:c3=0x6d28d9:c4=0x0ea5e9"
              ":n=5:speed=0.04:type=spiral")
    proc = ff.run([ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source,
                   "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(target)], timeout=300)
    if proc.returncode != 0:
        raise SystemExit(f"데모 영상을 만들지 못했습니다: {proc.stderr}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", nargs="?", default="")
    parser.add_argument("--theme", default="dark", choices=("dark", "light"))
    parser.add_argument("--lang", default="ko")
    parser.add_argument("--out", default=str(_bootstrap.TEMP_ROOT / "capture"))
    parser.add_argument("--start", type=float, default=2.0)
    parser.add_argument("--end", type=float, default=7.5)
    parser.add_argument("--dialogs", action="store_true", help="정보·결과·메시지 대화상자도 찍습니다")
    parser.add_argument("--docs", action="store_true", help="README·소개 페이지 그림(docs/images)을 새로 만듭니다")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.docs:
        args.theme, args.lang, args.start, args.end = "dark", "ko", 3.2, 8.4
        args.video = args.video or str(make_demo_video(out))

    app = QApplication(sys.argv)
    settings = Settings(theme=args.theme, language=args.lang, confirm_exit=False)
    prepare_app(app, settings)
    window = MainWindow(settings, background=False, persist=False)
    window.show()
    ffmpeg_path, ffprobe_path = ff.find_executable("ffmpeg"), ff.find_executable("ffprobe")
    window._on_ffmpeg_ready(ffmpeg_path, ffprobe_path, ff.ffmpeg_version(ffmpeg_path) if ffmpeg_path else "")
    wait(200)
    save(window, out / f"empty-{args.theme}.png")

    if args.video:
        window.open_video(str(Path(args.video).resolve()))
        if not wait_until(lambda: window.video is not None, 20):
            print("video did not load", file=sys.stderr)
            return 1
        window.timeline.set_selection(Selection(args.start, args.end))
        wait(3500)
        save(window, out / f"main-{args.theme}.png")
        if args.docs:
            image = window.grab().toImage()
            images = ROOT / "docs" / "images"
            for name, fmt, quality in (("main.png", b"png", -1), ("app-preview.webp", b"webp", 90)):
                writer = QImageWriter(str(images / name), QByteArray(fmt))
                writer.setQuality(quality)
                if not writer.write(image):
                    print(f"failed to save {name}: {writer.errorString()}", file=sys.stderr)
                    return 1
                print(f"updated docs/images/{name} ({image.width()}×{image.height()})")

    if args.dialogs:
        from src.ui import dialogs
        about = dialogs.AboutDialog(window, window.ffmpeg_version)
        about.show()
        wait(300)
        save(about, out / f"about-{args.theme}.png")
        about.close()
        message = dialogs.MessageDialog(window, "종료", "프로그램을 종료하시겠습니까?", kind="question",
                                        buttons=(("no", "", ""), ("yes", "", "primary")), checkbox="다시 묻지 않기")
        message.show()
        wait(200)
        save(message, out / f"message-{args.theme}.png")
        message.close()
    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
