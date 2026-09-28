"""이 프로그램의 버전 하나만 두는 곳.

아무것도 import 하지 않는다. 빌드 스크립트와 검사 도구가 버전만 알고 싶을 때
PySide6와 앱 전체를 끌어오지 않고 읽을 수 있게 하기 위해서다.

세 자리(major.minor.patch)를 벗어나면 안 된다. 자동 업데이트가 릴리즈 태그와 이 값을
숫자로 비교하고(src/core/updater.py), 릴리즈 ZIP 이름(ApexGIFMaker_v300.zip)도 여기서 만든다.
"""

APP_VERSION = "3.0.0"
