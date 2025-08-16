# src/about_dialog.py
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QTextBrowser
)
from PySide6.QtGui import QFont, QDesktopServices

from .icon import get_app_icon
from .constants import APP_VERSION

# 링크 정보
GITHUB_URL = "https://github.com/deuxdoom/APEXGIFMAKER"
YOUTUBE_URL = "https://www.youtube.com/@LE_SSERAFIM"


class AboutDialog(QDialog):
    """
    프로그램 정보를 표시하는 'About' 다이얼로그입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("APEX GIF MAKER 정보")
        self.setModal(True)
        self.setFixedSize(450, 300) # 창 크기를 약간 늘립니다.

        # --- 메인 레이아웃 ---
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 15, 20, 10)
        root.setSpacing(10)

        # --- 상단: 아이콘과 프로그램 이름 ---
        top_hbox = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(get_app_icon().pixmap(64, 64))

        title_label = QLabel(f"APEX GIF MAKER v{APP_VERSION}")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)

        top_hbox.addWidget(icon_label)
        top_hbox.addWidget(title_label, 1, Qt.AlignLeft | Qt.AlignVCenter)
        root.addLayout(top_hbox)

        # --- 정보 박스 ---
        info_group = QGroupBox("프로그램 정보")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)

        program_description = """
이 앱은 Flydigi APEX 게임 컨트롤러 시리즈의 스크린에 넣을 GIF를 제작하기 위해 만든 프로그램입니다. 사용자가 동영상 파일에서 원하는 구간을 선택하여 고품질 GIF 애니메이션을 쉽게 제작할 수 있도록 다양한 해상도, 프레임 속도, 디더링 방식 등의 옵션을 통해 설정할 수 있습니다.
        """
        
        description_label = QLabel(program_description)
        description_label.setWordWrap(True)
        info_layout.addWidget(description_label)
        info_group.setLayout(info_layout)
        root.addWidget(info_group)

        # --- 링크 버튼들 ---
        links_hbox = QHBoxLayout()
        links_hbox.setSpacing(10)

        github_button = QPushButton("GitHub")
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))

        youtube_button = QPushButton("YouTube")
        youtube_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(YOUTUBE_URL)))

        links_hbox.addWidget(github_button)
        links_hbox.addWidget(youtube_button)
        root.addLayout(links_hbox)

        root.addStretch(1)

        # --- 하단: 확인 버튼 ---
        bottom_hbox = QHBoxLayout()
        self.btn_ok = QPushButton("확인")
        self.btn_ok.clicked.connect(self.accept)

        bottom_hbox.addStretch(1)
        bottom_hbox.addWidget(self.btn_ok)
        root.addLayout(bottom_hbox)