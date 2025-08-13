![Apex GIF Maker](./main.png)
<h1 align=center>
  <img src="./logo.png" alt="APEX GIF MAKER Logo" width="60" style="vertical-align: middle;">
  Apex GIF Maker (MP4 → GIF)
</h1>

[![Release](https://img.shields.io/github/release/deuxdoom/APEXGIFMAKER?logo=github&style=flat&label=RELEASE)](https://github.com/deuxdoom/TVerDownloader/releases/latest)
[![Downloads Latest](https://img.shields.io/github/downloads/deuxdoom/APEXGIFMAKER/latest/total?logo=github&style=flat&label=DOWNLOADS@LATEST)](https://github.com/deuxdoom/APEXGIFMAKER/releases/latest)
[![Downloads Total](https://img.shields.io/github/downloads/deuxdoom/APEXGIFMAKER/total?logo=github&style=flat&label=DOWNLOADS)](https://github.com/deuxdoom/APEXGIFMAKER/releases)
[![Release](https://img.shields.io/badge/Download-Releases-2ea44f?logo=github)](https://github.com/deuxdoom/APEXGIFMAKER/releases)
[![Runtime](https://img.shields.io/badge/Runtime-Embedded%20Python-blue)](https://python.org)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Auto%20Setup-2ea44f?logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![Version](https://img.shields.io/badge/Version-v1.0.0-6f42c1)](#)
[![OS](https://img.shields.io/badge/OS-Windows%2010%2F11%20x64-2ea44f?logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-informational)](./LICENSE)



<p align="center">
  듀얼 핸들 타임라인과 2분할 프리뷰로 <b>2–10초</b> 구간을 잘라 고품질 GIF를 만드는 포터블(무설치) GUI 툴.<br/>
  <code>FFmpeg</code>를 사용하며, 최초 실행 시 자동으로 다운함.
</p>

---

## ✨ 주요 기능
- ✂️ **구간 트림**: 듀얼 핸들 + 직접 시간 입력(`mm:ss.mmm` / `hh:mm:ss.mmm`), 길이 **2–10초** 강제
- 🪟 **프리뷰 2분할**: 시작/끝 프레임을 **1280×720**으로 자동 추출해 좌/우 표시(슬라이더/시간 입력 변경 시 자동 갱신)
- 🧭 **타임라인 미니 썸네일**: 2초 간격 스트립으로 구간 탐색
- 🧩 **스케일 모드 3종**: **꽉 채우기(크롭, 기본)** / 레터박스(비율 유지) / 스트레치(왜곡), Lanczos 스케일
- 🤖 **자동·수동 프레임 선택**: 자동(균등 FPS) / 자동(중복 제거 `mpdecimate`) / 수동 체크 선택
- 🎨 **팔레트 2패스**: `palettegen` → `paletteuse` (디더링: `floyd_steinberg`, `bayer`, `none`)
- ⛏️ **FFmpeg 자동 준비(Windows)**: `./ffmpeg-bin`에 essentials ZIP 자동 다운로드/해제(영구), 콘솔창 무표시 실행
- 💾 **기본 저장 경로**: 출력 경로 미지정 시 실행 폴더에 자동 파일명으로 저장
- 🗂️ **캐시 디렉토리**: 실행 폴더 기준 `./cache` (프리뷰/프레임/타임라인)

---

## ⬇️ 다운로드
> **설치가 필요 없다.** 압축 해제 후 실행만 하면 된다.

- 🔽 **최신 버전 받기**  
  👉 [**Releases 페이지**](https://github.com/deuxdoom/APEXGIFMAKER/releases)에서  
  `ApexGIFMaker_xxx.zip` 다운로드 → 압축 해제 → `ApexGIFMaker.exe` 실행

- 📦 포함 파일(권장 배포 형태)
```text
ApexGIFMaker/
├─ ApexGIFMaker.exe       # 메인 실행 파일
├─ ffmpeg-bin/            # ffmpeg.exe / ffprobe.exe (없으면 최초 실행 시 자동 다운로드)
│  ├─ ffmpeg.exe
│  └─ ffprobe.exe
├─ cache/                 # 썸네일 프리뷰, 프레임등 관련 캐시 저장 폴더
├─ ATTRIBUTION.txt        # Flaticon
└─ LICENSE (MIT)
```

- 🧾 바이러스 오진이 발생하면 Windows SmartScreen/백신에서 예외로 등록 후 재실행.

---

## 🚀 사용 방법
1) **비디오 열기**: `.mp4/.mov/.mkv/.webm/.avi` 지원  
2) **구간 설정**: 슬라이더 드래그 또는 시작/끝 시간 직접 입력 
 - 2초 간격 **타임라인 썸네일**로 직관적으로 확인 가능  
 - 좌/우 **2분할 프리뷰**로 시작/끝 프레임 자동 갱신  
3) **옵션 선택**: 프레임 모드(자동/수동), FPS, 출력 크기, 스케일, 디더링  
4) **GIF 저장 경로**: 기본값은 실행 폴더에 자동 파일명으로 저장  
5) **GIF 생성** 클릭

> 기본 스케일: **꽉 채우기(크롭)**. 원본 영상 크롭없이 비율 유지가 필요하면 레터박스 선택.

---

## ⚙️ 옵션 요약

| 옵션 | 값/범위 | 설명 |
|---|---|---|
| 모드 | 자동(균등) / 자동(중복 제거) / 수동 선택 | 자동은 균등 FPS 또는 `mpdecimate`로 중복 프레임 제거 |
| FPS | 1–60 | 프레임률 |
| 크기 | 기본 160×80 | 임의 조정 가능 |
| 스케일 | **꽉 채우기(기본)** / 레터박스 / 스트레치 | <ul><li>꽉 채우기: `scale=...:force_original_aspect_ratio=increase,crop=...`</li><li>레터박스: `scale=...:force_original_aspect_ratio=decrease,pad=...`</li><li>스트레치: `scale=...`</li></ul> |
| 디더링 | `floyd_steinberg` / `bayer` / `none` | 팔레트 적용 시 디더링 방식 |
| 프리뷰 | 1280×720 | 시작/끝 2분할, 입력 변경 시 자동 갱신(디바운스 200ms) |

---

## 🧯 트러블슈팅
- **FFmpeg 다운로드 실패**: 네트워크/방화벽 환경일 수 있음. `ffmpeg-bin` 폴더에 직접 `ffmpeg.exe`/`ffprobe.exe`를 넣고 실행.  
- **콘솔 창 깜빡임**: 내부적으로 숨김 실행. 외부 FFmpeg 경로를 수동 지정했다면 동일 옵션이 적용되는지 확인.  
- **권한 문제**: Program Files 등 보호 폴더에서는 캐시/출력 쓰기가 막힐 수 있다. 사용자 폴더에서 실행 권장.  
- **바이러스 오진**: 파이썬으로 코딩하여 빌드한 경우 자연적인 현상. 서명되지 않은 실행파일은 오진임. 예외 등록 후 사용.

---

## 📝 릴리스 노트
### v1.0.0
- 듀얼 핸들 구간 트림(2–10s), 시간 직접 입력
- 시작/끝 **2분할 프리뷰(1280×720)**, 자동 갱신
- **2초 간격 타임라인 썸네일** 스트립
- 스케일 3종(기본: **크롭하여 꽉 채우기**)
- 자동(균등/중복 제거) & 수동 선택 모드
- 팔레트 2패스 + 디더링 옵션
- FFmpeg 자동 준비/영구 재사용, 콘솔 무표시
- 캐시/저장 경로: 실행 폴더 기준

---

## 🗺️ 로드맵
- 보다 깔끔한 UI
- 기타 필요한 기능 추가

---

## 📜 라이선스
- 본 프로젝트는 **MIT License**를 따릅니다. (상세는 [`LICENSE`](./LICENSE) 참조)

> **서드파티 고지**  
> - **FFmpeg**는 각자의 라이선스(LGPL/GPL 등) 조건을 따른다. 번들/재배포 시 FFmpeg 라이선스 의무 준수.  
> - **PySide6 (Qt for Python)**는 LGPL-3.0 등 Qt 라이선스를 따른다. 정적 링크/재배포 시 의무 조항을 확인.

---

## 🤝 기여
- 버그 리포트/PR 환영  
- 이슈 등록 시 **Windows 버전 / 재현 단계 / 로그** 첨부