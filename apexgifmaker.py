# apexgifmaker.py
"""APEX GIF MAKER 진입점. 시작 순서는 src/ui/app.py에 있습니다.

    python apexgifmaker.py [동영상 파일]
    python apexgifmaker.py --smoke-test      (창 없이 구성 점검, 빌드 검증용)
"""
import sys

from src.ui.app import run

if __name__ == "__main__":
    sys.exit(run(sys.argv))
