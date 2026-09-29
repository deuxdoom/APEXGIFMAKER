# social_preview.py
"""GitHub 소셜 미리보기 그림(1280×640)을 만듭니다. 저장소 링크를 공유하면 디스코드·슬랙·X 카드에도 이 그림이 뜹니다.

    python tools/social_preview.py                  docs/images/main.png로 docs/images/social-preview.png를 만듭니다.
    python tools/social_preview.py --guides         GitHub 템플릿의 안전 영역 선을 겹친 확인용 그림도 만듭니다.
    python tools/social_preview.py --source 화면.png --out 결과.png

색과 모양은 소개 페이지(docs/index.html)의 다크 테마를 따릅니다. 왼쪽에 로고·이름·한 줄 설명·대표 기능 3가지를,
오른쪽에 앱 화면(main.png)을 둡니다. GitHub에는 그림을 하나만 올릴 수 있으므로 글은 영어로 씁니다.

언제 다시 만들어도 그때의 화면과 기능이 맞게 담기도록, 시간이 지나면 틀려지는 내용은 넣지 않습니다.
버전 번호·Windows 버전·APEX 모델 목록은 쓰지 않고, 앱 화면 위에 좌표로 찍는 표시도 두지 않습니다.
화면은 늘 main.png에서 가져오므로 UI가 바뀌면 `python tools/capture.py --docs`로 main.png와 이 그림을 함께
새로 만듭니다. main.png가 화면 코드보다 오래되었으면 이 도구가 알려 줍니다. 대표 기능이 바뀌면 FEATURES를 고칩니다.

GitHub 템플릿(Repo Card Template)은 1280×640에서 사방 80px(40pt) 테두리 안에만 중요한 내용을 두라고 권합니다.
(토픽 페이지 카드는 위아래 약 78px를 잘라 냅니다.) 글과 앱 화면은 모두 SAFE 안에 그리고, 벗어나면 실패로 알립니다.
만든 그림은 저장소 Settings → General → Social preview에 직접 올려야 합니다(API 없음). 1MB 미만이어야 합니다.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.setup()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QPoint, QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QImage, QImageWriter, QLinearGradient, QPainter,  # noqa: E402
                           QPainterPath, QPen, QRadialGradient)
from PySide6.QtSvg import QSvgRenderer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.ui import fonts, icons  # noqa: E402

IMAGES = ROOT / "docs" / "images"
SIZE = (1280, 640)                  # GitHub 권장 크기(2:1)
SAFE = QRect(80, 80, 1120, 480)     # 템플릿의 40pt(80px) 테두리 안쪽. 중요한 내용은 모두 여기에 둡니다.
LIMIT = 1024 * 1024                 # GitHub가 받는 최대 크기(1MB)
SHOT_HEIGHT = 464                   # 앱 화면 높이. 안전 영역(480)보다 조금 작게 해서 위아래에 숨 쉴 틈을 둡니다.
GAP = 44                            # 글 영역과 앱 화면 사이

# 소개 페이지(docs/site.css)의 다크 테마 색
BG, INK, MUTED = "#060b14", "#f1f5fc", "#9aaabe"
SURFACE_2, LINE, BLUE, FRAME = "#101d2e", "#233044", "#64b5ff", "#304362"

EYEBROW = "MADE FOR YOUR APEX"
DESCRIPTION = "Turn any video moment into a GIF\nfor your Flydigi APEX controller's screen."
# (앱 아이콘 assets/icons/*.svg, 굵은 제목, 설명). 시간이 지나도 변하지 않을 핵심 기능만 적습니다.
FEATURES = (
    ("zoom_selection", "Precise trim", "down to 0.1 s"),
    ("zoom_fit", "Fits your APEX", "160×80 with crop preview"),
    ("gif", "One-click GIF", "crisp 256-color output"),
)
CHIPS = ("Windows", "Portable", "Free & open source")


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


def _line(painter: QPainter, x: int, top: int, text: str, font: QFont, color: str, caps: bool = False) -> QRect:
    """(x, top)부터 한 줄을 쓰고 차지한 영역을 돌려줍니다. caps면 대문자 높이만큼만 차지합니다."""
    metrics = QFontMetrics(font)
    height = metrics.capHeight() if caps else metrics.height()
    baseline = top + (metrics.capHeight() if caps else metrics.ascent())
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(QPointF(x, baseline), text)
    return QRect(x, top, metrics.horizontalAdvance(text), height)


def _icon_tile(painter: QPainter, rect: QRect, name: str) -> None:
    """소개 페이지의 설치 단계 번호(.install-steps b)처럼 옅은 파란 바탕에 앱 아이콘을 파랗게 그립니다."""
    painter.setPen(QColor(LINE))
    painter.setBrush(QColor(11, 111, 217, 40))
    painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 9, 9)
    size = 20
    painter.drawPixmap(rect.center().x() + 1 - size // 2, rect.center().y() + 1 - size // 2,
                       icons.pixmap(name, BLUE, size))


def _chip_width(text: str, font: QFont) -> int:
    return QFontMetrics(font).horizontalAdvance(text) + 28


def _chip(painter: QPainter, x: int, y: int, text: str, font: QFont) -> QRect:
    """소개 페이지의 알약 표지(.update-points li)."""
    width, height = _chip_width(text, font), 34
    painter.setPen(QColor(LINE))
    painter.setBrush(QColor(SURFACE_2))
    painter.drawRoundedRect(QRectF(x + 0.5, y + 0.5, width - 1, height - 1), height / 2, height / 2)
    metrics = QFontMetrics(font)
    painter.setFont(font)
    painter.setPen(QColor(INK))
    painter.drawText(QPointF(x + 14, y + (height + metrics.capHeight()) / 2), text)
    return QRect(x, y, width, height)


def _screenshot(painter: QPainter, shot: QImage, rect: QRect) -> None:
    """앱 화면: 소개 페이지 캡처 틀(.screenshot-button)처럼 부드러운 그림자, 둥근 모서리, 위쪽이 밝은 테두리."""
    painter.setPen(Qt.PenStyle.NoPen)
    for spread in range(1, 31):
        painter.setBrush(QColor(0, 0, 0, 6))
        painter.drawRoundedRect(QRectF(rect).adjusted(-spread, -spread + 18, spread, spread + 18),
                                10 + spread, 10 + spread)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(rect), 10, 10)
    painter.setClipPath(clip)
    painter.drawImage(rect.topLeft(), shot)
    painter.setClipping(False)
    border = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
    border.setColorAt(0, QColor(100, 181, 255, 200))
    border.setColorAt(0.42, QColor(FRAME))
    border.setColorAt(1, QColor(FRAME))
    painter.setPen(QPen(border, 1.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)


def render(source: Path) -> tuple[QImage, list[str]]:
    """그림을 그리고, 안전 영역을 벗어나거나 앱 화면 쪽으로 넘친 요소 이름 목록을 함께 돌려줍니다. (빈 목록이면 통과)"""
    shot = QImage(str(source))
    if shot.isNull():
        raise SystemExit(f"앱 화면 그림을 읽지 못했습니다: {source}")
    shot = shot.copy(window_rect(shot))
    shot_w = round(SHOT_HEIGHT * shot.width() / shot.height())
    shot = shot.scaled(shot_w, SHOT_HEIGHT, Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    shot_rect = QRect(SAFE.right() + 1 - shot_w, SAFE.center().y() + 1 - SHOT_HEIGHT // 2, shot_w, SHOT_HEIGHT)
    placed: list[tuple[str, QRect]] = []

    width, height = SIZE
    canvas = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(canvas)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                           | QPainter.RenderHint.SmoothPixmapTransform)
    painter.fillRect(canvas.rect(), QColor(BG))
    for center, radius, alpha in ((QPointF(shot_rect.center()), 660, 60), (QPointF(SAFE.left() + 60, SAFE.top()), 460, 26)):
        glow = QRadialGradient(center, radius)
        glow.setColorAt(0, QColor(18, 107, 211, alpha))
        glow.setColorAt(1, QColor(18, 107, 211, 0))
        painter.fillRect(canvas.rect(), glow)
    _screenshot(painter, shot, shot_rect)

    family = fonts.ui_families("en")[0]
    eyebrow_font = _font(family, 14, QFont.Weight.Bold, 2.4)
    title_font = _font(family, 64, QFont.Weight.ExtraBold, -1.5)
    body_font = _font(family, 19, QFont.Weight.Medium)
    label_font = _font(family, 18, QFont.Weight.Bold, -0.2)
    detail_font = _font(family, 16, QFont.Weight.Medium)
    chip_font = _font(family, 14, QFont.Weight.DemiBold)

    # 왼쪽 글 영역: 로고 줄 → 제목 두 줄 → 설명 → 기능 → 표지. 전체 높이를 먼저 재서 안전 영역 가운데에 놓습니다.
    # 로고와 큰 제목은 글자 옆 여백만큼 왼쪽으로 당겨 그려야 세로줄이 맞으므로, 글 영역을 안전선에서 4px 안쪽에 둡니다.
    left = SAFE.left() + 4
    column = QRect(left - 4, SAFE.top(), shot_rect.left() - GAP - left + 4, SAFE.height())
    logo, title_step, row_step, tile = 42, 72, 42, 32
    title_caps = QFontMetrics(title_font).capHeight()
    body_lines = DESCRIPTION.split("\n")
    body_step = QFontMetrics(body_font).lineSpacing() + 4
    blocks = (logo, title_step + title_caps, body_step * len(body_lines), row_step * (len(FEATURES) - 1) + tile, 34)
    gaps = (22, 24, 22, 26)
    y = SAFE.center().y() - (sum(blocks) + sum(gaps)) // 2
    tops = []
    for block, gap in zip(blocks, (*gaps, 0)):
        tops.append(y)
        y += block + gap

    logo_rect = QRect(left - 3, tops[0], logo, logo)
    QSvgRenderer(str(ROOT / "assets" / "applogo.svg")).render(painter, QRectF(logo_rect))
    placed.append(("logo", logo_rect))
    eyebrow_top = tops[0] + (logo - QFontMetrics(eyebrow_font).capHeight()) // 2
    placed.append(("eyebrow", _line(painter, left + logo + 14, eyebrow_top, EYEBROW, eyebrow_font, BLUE, caps=True)))
    for index, (text, color) in enumerate((("APEX", BLUE), ("GIF MAKER", INK))):
        rect = _line(painter, left - 4, tops[1] + index * title_step, text, title_font, color, caps=True)
        placed.append((f"title '{text}'", rect))
    for index, text in enumerate(body_lines):
        placed.append(("description", _line(painter, left, tops[2] + index * body_step, text, body_font, MUTED)))
    for index, (icon, label, detail) in enumerate(FEATURES):
        tile_rect = QRect(left, tops[3] + index * row_step, tile, tile)
        _icon_tile(painter, tile_rect, icon)
        middle = tile_rect.center().y() + 1
        label_rect = _line(painter, tile_rect.right() + 15, middle - QFontMetrics(label_font).capHeight() // 2, label,
                           label_font, INK, caps=True)
        detail_rect = _line(painter, label_rect.right() + 11, middle - QFontMetrics(detail_font).capHeight() // 2,
                            detail, detail_font, MUTED, caps=True)
        placed += [(f"feature '{label}'", tile_rect), (f"feature '{label}'", label_rect.united(detail_rect))]
    x = left
    for text in CHIPS:
        placed.append((f"chip '{text}'", _chip(painter, x, tops[4], text, chip_font)))
        x += _chip_width(text, chip_font) + 8
    painter.end()

    problems = [] if SAFE.contains(shot_rect) else ["app screenshot"]
    problems += [name for name, rect in placed if not SAFE.contains(rect)]
    problems += [f"{name} (앱 화면 쪽으로 넘침)" for name, rect in placed if not column.contains(rect)]
    return canvas, problems


def guides(image: QImage) -> QImage:
    """GitHub 템플릿처럼 안전 영역 밖을 붉게 칠하고 경계선을 그린 확인용 사본."""
    result = image.copy()
    painter = QPainter(result)
    outside = QPainterPath()
    outside.addRect(QRectF(result.rect()))
    inside = QPainterPath()
    inside.addRect(QRectF(SAFE))
    painter.fillPath(outside.subtracted(inside), QColor(255, 80, 80, 60))
    painter.setPen(QPen(QColor("#d33a4a"), 2))
    for x in (SAFE.left(), SAFE.right() + 1):
        painter.drawLine(x, 0, x, result.height())
    for y in (SAFE.top(), SAFE.bottom() + 1):
        painter.drawLine(0, y, result.width(), y)
    painter.end()
    return result


def _write(image: QImage, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = QImageWriter(str(target), QByteArray(b"png"))
    writer.setQuality(0)    # PNG에서는 압축 수준: 0이 가장 많이 압축합니다.
    if not writer.write(image):
        print(f"failed to save {target}: {writer.errorString()}", file=sys.stderr)
        return False
    return True


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _stale(source: Path) -> bool:
    """앱 화면 그림이 화면 코드(src/ui, src/i18n)보다 오래되었는지. (check.py의 문서 검사와 같은 기준)"""
    code = [*(ROOT / "src" / "ui").rglob("*.py"), *(ROOT / "src" / "i18n").glob("*.py")]
    return source.stat().st_mtime + 1 < max(path.stat().st_mtime for path in code)


def build(source: Path, target: Path, *, with_guides: bool = False) -> bool:
    """source(앱 화면)로 소셜 미리보기 그림을 만들어 target에 저장합니다. capture.py --docs도 이 함수를 씁니다."""
    image, problems = render(source)
    if not _write(image, target):
        return False
    size = target.stat().st_size
    print(f"updated {_shown(target)} ({SIZE[0]}×{SIZE[1]}, {size / 1024:.0f} KB)")
    if with_guides:
        check = _bootstrap.TEMP_ROOT / "social" / f"{target.stem}-guides.png"
        if _write(guides(image), check):
            print(f"guides  {check}")
    if _stale(source):
        print(f"참고: {_shown(source)}이(가) 화면 코드보다 오래되었습니다. UI가 바뀌었다면 "
              "python tools/capture.py --docs로 앱 화면과 이 그림을 함께 새로 만드세요")
    ok = True
    if problems:
        print("안전 영역(사방 80px) 밖이나 앱 화면 쪽으로 나간 요소가 있습니다: " + ", ".join(problems), file=sys.stderr)
        ok = False
    if size >= LIMIT:
        print(f"{target.name}이(가) 1MB를 넘어서 GitHub에 올릴 수 없습니다", file=sys.stderr)
        ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(IMAGES / "main.png"), help="앱 화면 그림 (기본: docs/images/main.png)")
    parser.add_argument("--out", default=str(IMAGES / "social-preview.png"),
                        help="저장할 곳 (기본: docs/images/social-preview.png)")
    parser.add_argument("--guides", action="store_true",
                        help=f"안전 영역 선을 겹친 확인용 그림도 {_bootstrap.TEMP_ROOT / 'social'}에 만듭니다")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)    # 폰트 등록과 그림 그리기에 필요합니다.
    ok = build(Path(args.source), Path(args.out), with_guides=args.guides)
    app.quit()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
