# output_panel.py
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QLineEdit, QPushButton
)

class OutputPanel(QWidget):
    chooseClicked = Signal()
    generateClicked = Signal()

    def __init__(self, lang: str = "ko", parent=None):
        super().__init__(parent)
        self.lang = lang
        g = QGridLayout(self)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)

        self.ed_out = QLineEdit()
        self.ed_out.setPlaceholderText("output.gif")

        self.btn_choose = QPushButton("저장 위치..." if self.lang == "ko" else "Choose…")
        self.btn_generate = QPushButton("GIF 생성" if self.lang == "ko" else "Generate GIF")
        self.btn_generate.setObjectName("GenerateButton")     # ✅ QSS 매칭용 ID

        g.addWidget(QLabel("출력:" if self.lang == "ko" else "Output:"), 0, 0)
        g.addWidget(self.ed_out, 0, 1, 1, 3)
        g.addWidget(self.btn_choose, 0, 4)
        g.addWidget(self.btn_generate, 0, 5)

        self.btn_choose.clicked.connect(self.chooseClicked.emit)
        self.btn_generate.clicked.connect(self.generateClicked.emit)

    # 외부 API
    def set_path(self, p: str): self.ed_out.setText(p)
    def get_path(self) -> str:  return self.ed_out.text().strip()

    def apply_texts(self, tr):
        self.btn_choose.setText(tr("choose") if tr else ("저장 위치..." if self.lang=="ko" else "Choose…"))
        self.btn_generate.setText(tr("generate") if tr else ("GIF 생성" if self.lang=="ko" else "Generate GIF"))
