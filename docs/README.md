# APEX GIF MAKER 웹 페이지

`index.html`을 브라우저에서 열거나, 프로젝트 루트에서 아래 명령으로 미리 봅니다.

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

주소는 `http://127.0.0.1:8765/`입니다. 사이트는 빌드 도구나 외부 UI 라이브러리 없이 동작합니다.
GitHub Pages에서 `main` 브랜치의 `/docs`를 게시하면 같은 상대 경로로 동작합니다.
이 작업에서는 게시 설정, 커밋 또는 푸시를 변경하지 않았습니다.

## 구성

- `index.html`: 한국어 소개, 기능, 사용 방법, FAQ, 다운로드.
- `site.css`: 반응형 레이아웃, 다크/라이트 테마, 모션 감소 대응.
- `site.js`: Canvas 기능 시뮬레이션, 구간·FPS·맞춤 조절, 화면 확대, 최신 릴리스 연결.
- `images/applogo.svg`, `images/appicon.ico`: 앱 자산의 웹용 사본.
- `images/app-preview.webp`: 실제 3.0 개발 화면의 WebP 사본. 기존 `images/main.png`는 보존.
- `fonts/`: 자체 호스팅 WOFF2 폰트와 OFL 라이선스.

미리보기는 절차적으로 그린 샘플 장면의 동작 설명입니다. 실제 영상 업로드나 GIF 인코딩을 하지 않습니다.
애니메이션은 화면 밖·숨겨진 탭에서 멈추고, 모션 감소 설정에서는 사용자가 재생할 때만 움직입니다.
구간당 예상 프레임 수는 균등 모드 기준 `선택 길이 × FPS`입니다.

## 출시 때 확인할 항목

1. `3.0 개발 프리뷰`, 개발 중 안내, 화면 설명을 실제 배포 상태에 맞게 갱신합니다.
2. `tools/capture.py`로 최신 앱 화면을 캡처하여 `images/app-preview.webp`를 갱신합니다.
   현재 이미지 크기는 1300×880이며, HTML의 두 이미지 요소 크기도 함께 맞춥니다.
3. GitHub 다운로드는 최신 안정 릴리스에서 `ApexGIFMaker*.zip` 자산을 찾습니다.
   API 실패·시간 초과·자산 없음에는 기존 `/releases/latest` 링크를 사용합니다.
4. 로고가 바뀌면 `assets/applogo.svg`, `assets/appicon.ico`를 `docs/images/`로 복사합니다.

## 폰트

본문은 사용자 제공 `F:/UTILITY/FONT/PretendardJP/PretendardVariable.ttf`에서 만들었습니다.
페이지 문자를 담은 WOFF2 서브셋이며, OFL의 Reserved Font Name 조건에 따라 내부 이름과
CSS 이름을 **ApexSiteSans**로 바꿨습니다. 숫자는 사용자 제공
`F:/UTILITY/FONT/JetBrainsMono/webfonts/JetBrainsMono-Regular.woff2` 원본을 사용합니다.

문구를 추가한 뒤에는 아래 명령으로 서브셋을 갱신합니다. 폰트 도구는 사이트 실행에 필요하지 않습니다.

```powershell
python -m pip install fonttools brotli
python docs/fonts/build_subset.py --source F:/UTILITY/FONT/PretendardJP/PretendardVariable.ttf
```

GitHub API 이외의 외부 서비스 호출, 외부 폰트 요청, 추적 스크립트는 없습니다.
