# options_panel.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QComboBox, QSpinBox, QPushButton
)

class OptionsPanel(QWidget):
    """GIF 생성에 필요한 모든 옵션(모드, FPS, 해상도 등)을 설정하는 UI 패널입니다."""
    
    ditherHelp = Signal()

    def __init__(self, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.lang = lang

        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)

        # --- 위젯 컨트롤 생성 ---
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "자동(균등)" if lang == "ko" else "Auto (even)",
            "자동(중복 제거)" if lang == "ko" else "Auto (dedupe)",
        ])

        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1, 60); self.spin_fps.setValue(12)
        self.spin_w   = QSpinBox(); self.spin_w.setRange(8, 1024); self.spin_w.setValue(160)
        self.spin_h   = QSpinBox(); self.spin_h.setRange(8, 1024); self.spin_h.setValue(80)

        self.combo_scale = QComboBox()
        self.combo_scale.addItems([
            "꽉 채우기(크롭)" if lang == "ko" else "Cover (crop)",
            "레터박스(비율 유지)" if lang == "ko" else "Letterbox (AR keep)",
            "스트레치(왜곡)" if lang == "ko" else "Stretch (distort)",
        ])
        self.combo_scale.setCurrentIndex(0)

        self.combo_dither = QComboBox()
        if lang == "ko":
            self.combo_dither.addItems(["플로이드-슈타인버그", "바이어", "없음"])
        else:
            self.combo_dither.addItems(["floyd_steinberg", "bayer", "none"])

        self.combo_dither.setItemData(0, "부드럽고 자연스러운 디더링(권장)", Qt.ToolTipRole)
        self.combo_dither.setItemData(1, "규칙적인 격자 패턴(선명)", Qt.ToolTipRole)
        self.combo_dither.setItemData(2, "디더링 없음(또렷하지만 색상 경계 발생 가능)", Qt.ToolTipRole)

        self.btn_dither_help = QPushButton("?")
        self.btn_dither_help.setObjectName("HelpBubble")
        self.btn_dither_help.setCursor(Qt.PointingHandCursor)
        self.btn_dither_help.setToolTip("디더링이란?" if lang == "ko" else "What is dithering?")
        self.btn_dither_help.setFixedSize(22, 22)
        self.btn_dither_help.setStyleSheet("""
            QPushButton#HelpBubble {
                background: #ffffff; color: #111111; border: 1px solid #111111;
                border-radius: 11px; padding: 0; font-weight: 700;
            }
            QPushButton#HelpBubble:hover { background: #f3f4f6; }
        """)
        self.btn_dither_help.clicked.connect(self.ditherHelp.emit)

        # --- 라벨 및 배치 (기존과 동일) ---
        lbl_mode   = QLabel("모드:" if lang == "ko" else "Mode:")
        lbl_fps    = QLabel("FPS:")
        lbl_w      = QLabel("가로:" if lang == "ko" else "Width:")
        lbl_h      = QLabel("세로:" if lang == "ko" else "Height:")
        lbl_scale  = QLabel("스케일:" if lang == "ko" else "Scale:")
        lbl_dither = QLabel("디더링" if lang == "ko" else "Dithering:")
        g.addWidget(lbl_mode,     0, 0); g.addWidget(self.combo_mode, 0, 1)
        g.addWidget(lbl_fps,      0, 2); g.addWidget(self.spin_fps,   0, 3)
        g.addWidget(lbl_w,        0, 4); g.addWidget(self.spin_w,     0, 5)
        g.addWidget(lbl_h,        0, 6); g.addWidget(self.spin_h,     0, 7)
        g.addWidget(lbl_scale,    1, 0); g.addWidget(self.combo_scale,   1, 1, 1, 3)
        g.addWidget(lbl_dither,   1, 4); g.addWidget(self.btn_dither_help, 1, 5)
        g.addWidget(self.combo_dither,   1, 6, 1, 2)
        g.setColumnStretch(1, 1); g.setColumnStretch(7, 1)

    def values(self) -> tuple:
        """GIF 생성 로직에 필요한 값들을 ffmpeg 키워드로 변환하여 반환합니다."""
        scale_map = { 0: "cover", 1: "letterbox", 2: "stretch" }
        scale_mode = scale_map.get(self.combo_scale.currentIndex(), "cover")
        dither_map = { 0: "floyd_steinberg", 1: "bayer", 2: "none" }
        dither_key = dither_map.get(self.combo_dither.currentIndex(), "floyd_steinberg")
        
        mode_idx = self.combo_mode.currentIndex()
        fps = self.spin_fps.value()
        w = self.spin_w.value()
        h = self.spin_h.value()

        return mode_idx, fps, w, h, scale_mode, dither_key

    # ▼▼▼ 추가된 부분: 설정 로드/저장을 위한 메소드들 ▼▼▼
    def set_values(self, opts: dict):
        """
        settings.json에서 불러온 딕셔너리 값으로 UI 컨트롤 상태를 업데이트합니다.
        - opts: 설정값이 담긴 딕셔너리
        """
        if not isinstance(opts, dict): return
        
        # .get(key, default)를 사용하여 파일에 특정 키가 없어도 오류 없이 안전하게 값을 설정합니다.
        self.combo_mode.setCurrentIndex(opts.get("mode_idx", 0))
        self.spin_fps.setValue(opts.get("fps", 12))
        self.spin_w.setValue(opts.get("width", 160))
        self.spin_h.setValue(opts.get("height", 80))
        self.combo_scale.setCurrentIndex(opts.get("scale_idx", 0))
        self.combo_dither.setCurrentIndex(opts.get("dither_idx", 0))

    def get_options_dict(self) -> dict:
        """
        현재 UI 컨트롤 상태를 settings.json에 저장하기 위한 딕셔너리 형태로 반환합니다.
        콤보박스는 텍스트가 아닌 인덱스(순번)를 저장하여 다국어 환경에 대응합니다.
        """
        return {
            "mode_idx": self.combo_mode.currentIndex(),
            "fps": self.spin_fps.value(),
            "width": self.spin_w.value(),
            "height": self.spin_h.value(),
            "scale_idx": self.combo_scale.currentIndex(),
            "dither_idx": self.combo_dither.currentIndex(),
        }
    # ▲▲▲ 추가 완료 ▲▲▲