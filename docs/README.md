# APEX GIF MAKER 웹 페이지

`index.html`을 브라우저에서 열거나, 프로젝트 루트에서 아래 명령으로 미리 봅니다.

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

주소는 `http://127.0.0.1:8765/`입니다. 사이트는 빌드 도구나 외부 UI 라이브러리 없이 동작합니다.
GitHub Pages에서 `main` 브랜치의 `/docs`를 게시하면 같은 상대 경로로 동작합니다.

## 구성

- `index.html`: 한국어 소개, 웹 체험판, 기능, 화면 구성, 자동 업데이트, 사용 방법, FAQ, 다운로드.
- `site.css`: 반응형 레이아웃, 다크/라이트 테마, 모션 감소 대응. 웹 체험판(`@layer app`)은 앱의
  `src/ui/theme.py` 색 토큰(다크·라이트)을 그대로 씁니다.
- `site.js`: 웹 체험판, 화면 확대, 최신 릴리스 연결.
- `images/applogo.svg`, `images/appicon.ico`: 앱 자산의 웹용 사본.
- `images/main.png`(README·공유 미리보기), `images/app-preview.webp`(소개 페이지): 실제 앱 캡처, 1950×1320.
- `images/FluentUI-Icons-LICENSE.txt`: 체험판에 인라인으로 넣은 앱 아이콘(Fluent UI System Icons, MIT)의 라이선스.
- `fonts/`: 자체 호스팅 WOFF2 폰트와 OFL 라이선스.

## 웹 체험판

v3.1.0 메인 창을 그대로 옮긴 화면입니다. 동작 규칙은 앱 코드를 옮겼습니다.

| 체험판 | 앱 코드 |
|---|---|
| 구간 제한(1~30초, 권장 15초), 손잡이·이동·직접 입력 규칙 | `src/core/trim.py`, `src/core/config.py` |
| 시간 표기·입력(`01:23.500`, `83.5` 등) | `src/core/timecode.py` |
| 타임라인 눈금·필름스트립 칸·확대/축소·개요 막대·단축키 | `src/ui/widgets/timeline.py`, `timeline_math.py` |
| 예상 프레임(균등 `약`, 중복 제거 `최대`), 자동 파일 이름 | `src/core/gif.py`, `src/ui/widgets/timeline_panel.py` |
| 꽉 채우기 크롭 가이드(점선) | `src/ui/widgets/preview.py` |
| 색상 분석 → 변환 → 결과 창, 덮어쓰기 확인, 취소 | `src/ui/main_window.py`, `result_dialog.py` |

샘플 영상은 코드로 그리는 48초 장면이며 처음 4초는 멈춘 타이틀 화면입니다(중복 제거 동작 확인용).
GIF 생성은 샘플 프레임으로 256색 팔레트를 만들고 선택한 디더링을 적용해 결과 창에서 재생합니다.
실제 파일은 만들지 않으므로 결과 창의 용량은 표시하지 않습니다. 영상 업로드나 외부 요청은 없습니다.
타임라인 휠 확대는 페이지 스크롤을 막지 않도록 타임라인을 누르거나 Tab으로 고른 뒤에만 동작합니다.

## 새 버전을 낼 때 확인할 항목

1. 다운로드 버튼과 배지는 GitHub API의 최신 안정 릴리스에서 `ApexGIFMaker*.zip` 자산, 태그, SHA-256(`digest`)을
   읽어 바꿉니다. API 실패·시간 초과·자산 없음에는 HTML에 적힌 기본값(`/releases/latest`, `v3.1.0 정식 출시`)이 남으므로,
   `index.html`의 배지 문구와 링크(`#release-badge`)도 새 태그로 고칩니다.
2. `tools/capture.py <샘플 영상> --docs`로 최신 앱 화면을 캡처하여 `images/main.png`와 `images/app-preview.webp`를 갱신합니다.
   GitHub 소셜 미리보기 그림 `images/social-preview.png`도 함께 새로 만들어지며, `main.png`만 직접 바꿨다면
   `tools/social_preview.py`로 따로 만듭니다.
   크기가 바뀌면 `index.html`의 이미지 `width`·`height`, `og:image:width`·`og:image:height`,
   `.hotspots`의 번호 위치(`--x`, `--y`, 그림 크기 대비 %)도 함께 맞춥니다.
3. 화면이나 기본값이 바뀌면 체험판 HTML(`#sim`)과 `site.js`의 상수(`TRIM_*`, `SIZE_*`, `FPS_*` 등)를 앱과 맞춥니다.
4. 로고가 바뀌면 `assets/applogo.svg`, `assets/appicon.ico`를 `docs/images/`로 복사합니다.

## 폰트

본문 폰트는 저장소의 `assets/fonts/PretendardVariable.ttf`(Pretendard Variable 1.309)에서 만든,
페이지 문자만 담은 WOFF2 서브셋입니다. OFL의 Reserved Font Name 조건에 따라 내부 이름과
CSS 이름을 **ApexSiteSans**로 바꿨습니다. 숫자·시간 표기는 JetBrains Mono WOFF2 원본을 사용합니다.

`index.html`, `site.css`, `site.js`의 문구를 바꾼 뒤에는 아래 명령으로 서브셋을 갱신합니다.
폰트 도구는 사이트 실행에 필요하지 않습니다.

```powershell
python -m pip install fonttools brotli
python docs/fonts/build_subset.py --source assets/fonts/PretendardVariable.ttf
```

GitHub API 이외의 외부 서비스 호출, 외부 폰트 요청, 추적 스크립트는 없습니다.
