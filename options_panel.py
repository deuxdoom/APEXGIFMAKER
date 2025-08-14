# options_panel.py
# 옵션 영역 위젯 (모드/FPS/가로/세로/스케일/디더링 + ? 도움말)
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QComboBox, QSpinBox, QPushButton
)


class OptionsPanel(QWidget):
    # 디더링 도움말 클릭 시그널
    ditherHelp = Signal()

    def __init__(self, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.lang = lang

        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)

        # ── 컨트롤 생성 ───────────────────────────────────────────────────
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "자동(균등)" if lang == "ko" else "Auto (even)",
            "자동(중복 제거)" if lang == "ko" else "Auto (dedupe)",
        ])

        self.spin_fps = QSpinBox(); self.spin_fps.setRange(1, 60); self.spin_fps.setValue(12)
        self.spin_w   = QSpinBox(); self.spin_w.setRange(8, 1024); self.spin_w.setValue(160)
        self.spin_h   = QSpinBox(); self.spin_h.setRange(8, 1024); self.spin_h.setValue(80)

        self.combo_scale = QComboBox()
        # ▼▼▼ 수정된 부분 1: '꽉 채우기(크롭)'을 리스트의 첫 번째로 이동 ▼▼▼
        self.combo_scale.addItems([
            "꽉 채우기(크롭)" if lang == "ko" else "Cover (crop)",
            "레터박스(비율 유지)" if lang == "ko" else "Letterbox (AR keep)",
            "스트레치(왜곡)" if lang == "ko" else "Stretch (distort)",
        ])
        # ▼▼▼ 수정된 부분 2: 기본 선택 인덱스를 0으로 변경 ▼▼▼
        self.combo_scale.setCurrentIndex(0)
        # ▲▲▲ 수정 완료 ▲▲▲

        self.combo_dither = QComboBox()
        if lang == "ko":
            self.combo_dither.addItems(["플로이드-슈타인버그", "바이어", "없음"])
        else:
            self.combo_dither.addItems(["floyd_steinberg", "bayer", "none"])

        # 옵션별 간단 설명 툴팁 설정
        self.combo_dither.setItemData(
            0,
            "부드럽고 자연스러운 디더링(권장)\n– 색 밴딩을 효과적으로 완화",
            Qt.ToolTipRole,
        )
        self.combo_dither.setItemData(
            1,
            "규칙 격자 패턴(선명)\n– 경우에 따라 패턴이 보일 수 있음",
            Qt.ToolTipRole,
        )
        self.combo_dither.setItemData(
            2,
            "디더링 없음(또렷) – 밴딩이 보일 수 있음",
            Qt.ToolTipRole,
        )

        # 디더링 '?' 도움말 버튼
        self.btn_dither_help = QPushButton("?")
        self.btn_dither_help.setObjectName("HelpBubble")
        self.btn_dither_help.setCursor(Qt.PointingHandCursor)
        self.btn_dither_help.setToolTip("디더링이 뭔가요?" if lang == "ko" else "What is dithering?")
        self.btn_dither_help.setFixedSize(22, 22)
        self.btn_dither_help.setStyleSheet("""
            QPushButton#HelpBubble{
                background:#ffffff;
                color:#111111;
                border:1px solid #111111;
                border-radius:11px;
                padding:0;
                font-weight:700;
            }
            QPushButton#HelpBubble:hover{
                background:#f3f4f6;
            }
        """)
        self.btn_dither_help.clicked.connect(self.ditherHelp.emit)

        # ── 라벨 생성 ───────────────────────────────────────────────────
        lbl_mode   = QLabel("모드:" if lang == "ko" else "Mode:")
        lbl_fps    = QLabel("FPS:")
        lbl_w      = QLabel("가로:" if lang == "ko" else "Width:")
        lbl_h      = QLabel("세로:" if lang == "ko" else "Height:")
        lbl_scale  = QLabel("스케일:" if lang == "ko" else "Scale:")
        lbl_dither = QLabel("디더링" if lang == "ko" else "Dithering:")

        # ── 컨트롤 및 라벨 배치 ──────────────────────────────────────────
        # 0행: 모드 / FPS / 가로 / 세로
        g.addWidget(lbl_mode,     0, 0); g.addWidget(self.combo_mode, 0, 1)
        g.addWidget(lbl_fps,      0, 2); g.addWidget(self.spin_fps,   0, 3)
        g.addWidget(lbl_w,        0, 4); g.addWidget(self.spin_w,     0, 5)
        g.addWidget(lbl_h,        0, 6); g.addWidget(self.spin_h,     0, 7)

        # 1행: 스케일 / 디더링 + ?
        g.addWidget(lbl_scale,    1, 0); g.addWidget(self.combo_scale,   1, 1, 1, 3)
        g.addWidget(lbl_dither,   1, 4)
        g.addWidget(self.btn_dither_help, 1, 5)
        g.addWidget(self.combo_dither,   1, 6, 1, 2)

        # 컬럼 스트레치 설정으로 반응형 레이아웃 조절
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 0)
        g.setColumnStretch(5, 0)
        g.setColumnStretch(7, 1)

    # 다국어 텍스트 적용 (외부에서 호출)
    def apply_texts(self, tr):
        if not callable(tr):
            return
        pass

    def values(self):
        """
        UI 컨트롤에 설정된 모든 옵션 값들을 _generate 함수가 요구하는 형식의 튜플로 반환합니다.
        UI 텍스트를 ffmpeg 백엔드에서 사용하는 실제 키워드 값으로 변환하는 로직을 포함합니다.
        """
        # 1. 스케일 모드 변환
        # ▼▼▼ 수정된 부분 3: 변경된 콤보박스 순서에 맞게 인덱스 매핑 수정 ▼▼▼
        scale_map = {
            0: "cover",      # 꽉 채우기(크롭)
            1: "letterbox",  # 레터박스(비율 유지)
            2: "stretch"     # 스트레치(왜곡)
        }
        # ▲▲▲ 수정 완료 ▲▲▲
        scale_mode = scale_map.get(self.combo_scale.currentIndex(), "cover")

        # 2. 디더링 모드 변환
        dither_map = {
            0: "floyd_steinberg",
            1: "bayer",
            2: "none"
        }
        dither_key = dither_map.get(self.combo_dither.currentIndex(), "floyd_steinberg")

        # 3. 나머지 숫자 및 인덱스 값 가져오기
        mode_idx = self.combo_mode.currentIndex()
        fps = self.spin_fps.value()
        w = self.spin_w.value()
        h = self.spin_h.value()

        # 4. 최종 반환
        return mode_idx, fps, w, h, scale_mode, dither_key