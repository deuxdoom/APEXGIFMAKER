# capture.py
"""화면을 띄우지 않고(오프스크린) 메인 창과 대화상자를 PNG로 찍습니다. README·소개 페이지 그림과 디자인 확인용입니다.

    python tools/capture.py --docs                 README와 소개 페이지 그림을 새로 만들어 docs/images에 넣습니다.
    python tools/capture.py --social               지금 있는 main.png로 GitHub 소셜 미리보기 그림만 다시 만듭니다.
    python tools/capture.py 동영상.mp4 [--theme dark|light] [--lang ko] [--out 폴더] [--dialogs]

--docs는 현재 화면·버전으로 docs/images/main.png(README)와 docs/images/app-preview.webp(소개 페이지)를
다시 만듭니다. 동영상을 주지 않으면 ffmpeg로 데모 영상을 만들어 씁니다. UI나 버전이 바뀌었으면 커밋 전에 실행합니다.
--docs와 --social은 docs/images/social-preview.png(1280×640)도 만듭니다. 이 그림은 저장소 Settings → General →
Social preview에 직접 올려야 합니다(API 없음). GitHub 토픽 페이지는 이 그림을 카드 폭에 맞춘 뒤 높이를 275px로
잘라서 위아래 약 78px가 가려지므로, 글자와 화면은 가운데 띠(SOCIAL_SAFE) 안에만 그립니다.
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

from PySide6.QtCore import QByteArray, QEventLoop, QPoint, QRect, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QImage, QImageWriter, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QRadialGradient)
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from src.core import ffmpeg as ff  # noqa: E402
from src.core.settings import Settings  # noqa: E402
from src.core.trim import Selection  # noqa: E402
from src.ui import fonts  # noqa: E402
from src.ui.app import prepare_app  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from versioninfo import APP_VERSION  # noqa: E402

SOCIAL_SIZE = (1280, 640)       # GitHub 권장 크기(2:1). 링크 미리보기(디스코드·슬랙·X)도 이 비율을 씁니다.
SOCIAL_SAFE = (96, 544)         # 토픽 카드(폭 약 727px, 높이 275px)에서 보이는 세로 범위 78~562 안쪽
SOCIAL_LIMIT = 1024 * 1024      # GitHub가 받는 최대 크기(1MB)


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


def window_rect(image: QImage) -> QRect:
    """직접 찍은 스크린샷의 회색 그림자·여백을 뺀 창 영역. 창은 남색 계열이라 무채색 여백과 구별됩니다."""
    def navy(x: int, y: int) -> bool:
        color = image.pixelColor(x, y)
        return color.blue() - max(color.red(), color.green()) > 8

    w, h = image.width(), image.height()
    left = next((x for x in range(48) if navy(x, h // 2)), 0)
    right = next((x for x in range(w - 1, w - 49, -1) if navy(x, h // 2)), w - 1)
    top = next((y for y in range(48) if navy(w // 2, y)), 0)
    bottom = next((y for y in range(h - 1, h - 49, -1) if navy(w // 2, y)), h - 1)
    return QRect(QPoint(left, top), QPoint(right, bottom))


def _font(family: str, size: int, weight: QFont.Weight, spacing: float = 0.0) -> QFont:
    font = fonts.apply_rendering(QFont(family))
    font.setPixelSize(size)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def _chip(painter: QPainter, x: int, y: int, text: str, font: QFont, accent: bool = False) -> int:
    """알약 모양 표지를 그리고 오른쪽 끝 x를 돌려줍니다."""
    width = QFontMetrics(font).horizontalAdvance(text) + 28
    rect = QRectF(x + 0.5, y + 0.5, width - 1, 33)
    painter.setPen(QColor("#3f7fc4") if accent else QColor("#26374f"))
    painter.setBrush(QColor(57, 143, 225, 46) if accent else QColor("#0d1829"))
    painter.drawRoundedRect(rect, 16.5, 16.5)
    painter.setFont(font)
    painter.setPen(QColor("#8cc8ff") if accent else QColor("#c3d2e7"))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    return x + width


def make_social_preview(source: Path, target: Path) -> bool:
    """메인 화면 스크린샷에 로고·이름·버전을 얹어 GitHub 소셜 미리보기 그림(1280×640)을 만듭니다."""
    shot = QImage(str(source))
    if shot.isNull():
        print(f"failed to read {source}", file=sys.stderr)
        return False
    shot = shot.copy(window_rect(shot))
    width, height = SOCIAL_SIZE
    safe_top, safe_bottom = SOCIAL_SAFE
    shot_h = safe_bottom - safe_top
    shot_w = round(shot_h * shot.width() / shot.height())
    shot = shot.scaled(shot_w, shot_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    shot_rect = QRect(width - 60 - shot_w, safe_top, shot_w, shot_h)

    canvas = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(canvas)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                           | QPainter.RenderHint.SmoothPixmapTransform)
    background = QLinearGradient(0, 0, width, height)
    background.setColorAt(0, QColor("#081223"))
    background.setColorAt(1, QColor("#050910"))
    painter.fillRect(canvas.rect(), background)
    glow = QRadialGradient(shot_rect.center().x(), shot_rect.center().y(), 560)
    glow.setColorAt(0, QColor(18, 107, 211, 70))
    glow.setColorAt(1, QColor(18, 107, 211, 0))
    painter.fillRect(canvas.rect(), glow)

    # 스크린샷: 부드러운 그림자 → 둥근 모서리로 잘라 그리기 → 테두리
    painter.setPen(Qt.PenStyle.NoPen)
    for spread in range(1, 25):
        painter.setBrush(QColor(0, 0, 0, 7))
        painter.drawRoundedRect(QRectF(shot_rect).adjusted(-spread, -spread + 10, spread, spread + 10),
                                10 + spread, 10 + spread)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(shot_rect), 8, 8)
    painter.setClipPath(clip)
    painter.drawImage(shot_rect.topLeft(), shot)
    painter.setClipping(False)
    painter.setPen(QColor("#34496a"))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(shot_rect).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

    # 왼쪽 글 영역: 로고, 이름(두 줄), 설명, 표지. 전체 높이를 재서 안전 영역 가운데에 놓습니다.
    family = fonts.ui_families("en")[0]
    title_font = _font(family, 66, QFont.Weight.ExtraBold, -0.5)
    body_font = _font(family, 21, QFont.Weight.Medium)
    chip_font = _font(family, 15, QFont.Weight.DemiBold)
    left = 72
    column = QRect(left, 0, shot_rect.left() - 56 - left, 0)
    description = "Turn any video moment into a GIF for your Flydigi APEX controller's screen."
    flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
    body_h = QFontMetrics(body_font).boundingRect(QRect(0, 0, column.width(), 400), flags, description).height()
    title_line = 70
    blocks = (68, 26, title_line * 2, 18, body_h, 28, 34)
    y = safe_top + (safe_bottom - safe_top - sum(blocks)) // 2

    QSvgRenderer(str(ROOT / "assets" / "applogo.svg")).render(painter, QRectF(left - 4, y, 68, 68))
    y += blocks[0] + blocks[1]
    painter.setFont(title_font)
    for text, color in (("APEX", "#4ea7f5"), ("GIF MAKER", "#f1f5fc")):
        painter.setPen(QColor(color))
        painter.drawText(QRect(left - 3, y, column.width() + 40, title_line),
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)
        y += title_line
    y += blocks[3]
    painter.setFont(body_font)
    painter.setPen(QColor("#a3b3c9"))
    painter.drawText(QRect(left, y, column.width(), body_h), flags, description)
    y += body_h + blocks[5]
    x = _chip(painter, left, y, f"v{APP_VERSION}", chip_font, accent=True) + 10
    for text in ("APEX 4 · 5 · 6", "160×80", "Windows"):
        x = _chip(painter, x, y, text, chip_font) + 10
    painter.end()

    writer = QImageWriter(str(target), QByteArray(b"png"))
    writer.setQuality(0)    # PNG에서는 압축 수준: 0이 가장 많이 압축합니다.
    if not writer.write(canvas):
        print(f"failed to save {target.name}: {writer.errorString()}", file=sys.stderr)
        return False
    size = target.stat().st_size
    print(f"updated docs/images/{target.name} ({width}×{height}, {size / 1024:.0f} KB)")
    if size >= SOCIAL_LIMIT:
        print(f"{target.name}이(가) 1MB를 넘어서 GitHub에 올릴 수 없습니다", file=sys.stderr)
        return False
    return True


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
    parser.add_argument("--social", action="store_true", help="main.png로 GitHub 소셜 미리보기 그림만 새로 만듭니다")
    args = parser.parse_args()
    images = ROOT / "docs" / "images"
    if args.social and not args.docs:
        app = QApplication(sys.argv)    # 폰트 등록과 그림 그리기에 필요합니다.
        ok = make_social_preview(images / "main.png", images / "social-preview.png")
        app.quit()
        return 0 if ok else 1
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
            for name, fmt, quality in (("main.png", b"png", -1), ("app-preview.webp", b"webp", 90)):
                writer = QImageWriter(str(images / name), QByteArray(fmt))
                writer.setQuality(quality)
                if not writer.write(image):
                    print(f"failed to save {name}: {writer.errorString()}", file=sys.stderr)
                    return 1
                print(f"updated docs/images/{name} ({image.width()}×{image.height()})")
            if not make_social_preview(images / "main.png", images / "social-preview.png"):
                return 1

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
