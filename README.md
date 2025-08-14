<p align="center">
  <img src="main.png" alt="ApexGIFMaker 메인 UI" width="820">
</p>

## 🎥 데모

| [![Watch the video](https://img.youtube.com/vi/-bZaF1CrjNI/maxresdefault.jpg)](https://youtu.be/-bZaF1CrjNI "Apex GIF Maker Demo") |
|:--:|
| *클릭하면 YouTube로 이동* |

---

<h1 align=center>
  <img src="./logo.png" alt="APEX GIF MAKER Logo" width="60" style="vertical-align: middle;">
  APEX GIF MAKER (MP4 → GIF)
</h1>

<p align="center">

[![GitHub release](https://img.shields.io/github/release/deuxdoom/APEXGIFMAKER?logo=github&style=flat)](https://github.com/deuxdoom/APEXGIFMAKER/releases/latest)
[![GitHub downloads latest](https://img.shields.io/github/downloads/deuxdoom/APEXGIFMAKER/latest/total?logo=github&style=flat)](https://github.com/deuxdoom/APEXGIFMAKER/releases/latest)
[![GitHub downloads total](https://img.shields.io/github/downloads/deuxdoom/APEXGIFMAKER/total?logo=github&style=flat)](https://github.com/deuxdoom/APEXGIFMAKER/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-blue?style=flat&logo=windows)](https://github.com/deuxdoom/APEXGIFMAKER)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat&logo=python)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide-6-green?style=flat)](https://pypi.org/project/PySide6/)
[![FFmpeg](https://img.shields.io/badge/made%20with-FFmpeg-black?style=flat&logo=ffmpeg)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)

</p>

---

## 🎨 설명
플라이디지 **APEX** 게임패드 스크린용 **MP4 to GIF 메이커** <br>
영상을 불러와 원하는 구간을 선택하고, 프리뷰 확인 후 GIF로 변환하는 프로그램

---

## ✨ 주요 기능
- **구간 선택**: 슬라이더 드래그 + 시간 직접 입력(hh:mm:ss.mmm)
- **시작·끝 2분할 프리뷰**(1280×720), **2초 간격 타임라인 썸네일**
- GIF 품질 최적화: **2-pass 팔레트**, **디더링(FS/Bayer/None)**, **FPS/해상도** 조절
- 스케일 3가지: **꽉 채우기(크롭·기본)** / 레터박스(비율 유지) / 스트레치
- 자동(균등/중복제거) + **수동 프레임 선택**(체크로 골라서 합성)
- **FFmpeg 자동 준비**(Windows essentials.zip 다운로드·해제) 후 **정리(ffmpeg/ffprobe만 유지)**
- **포터블 배포**(one-folder), 콘솔창 숨김, **아이콘 내장(Base64 PNG)**

---

## ⬇️ 다운로드
- **Latest Release**: https://github.com/deuxdoom/APEXGIFMAKER/releases/latest  
  내려받은 ZIP을 풀고 `ApexGIFMaker.exe` 실행.

---

## ❗ 필독 사항

- **Windows에서 'PC 보호' 또는 '서명되지 않은 파일' 경고**가 표시될 수 있습니다.  
  이 프로그램은 직접 빌드한 오픈소스 프로젝트로, 악성코드가 없으니 안심하고 실행해도 됩니다.

---

## 🚀 빠른 사용
1. `ApexGIFMaker.exe` 실행 → **입력 비디오** 선택(MP4 등)
2. 슬라이더로 구간 지정(또는 시간 직접 입력) → **시작/끝 프리뷰** 확인
3. 옵션(FPS/해상도/스케일/디더링, 자동/수동)을 필요만큼 조정
4. **GIF 생성** → 실행 폴더에 저장(기본 파일명 자동 제안)

> 캐시는 `./cache` 폴더에 저장됨(프리뷰/타임라인/스캔 이미지).

---

## 📦 릴리즈 구성
```text
ApexGIFMaker_x64/
├─ ApexGIFMaker.exe
├─ ffmpeg-bin/
│ ├─ ffmpeg.exe
│ └─ ffprobe.exe
└─ cache/ # 프리뷰/타임라인/스캔 캐시
```

---

## 🧩 호환
- **Windows 10/11 x64**
- 실행에 추가 설치 불필요(FFmpeg 자동 준비)

---

## 🛠 트러블슈팅
- **아이콘/작업표시줄이 기본 아이콘으로 나옴** → 기존 “작업 표시줄 고정” 해제 후 다시 고정(캐시 갱신)
- **FFmpeg 다운로드 실패** → 네트워크 확인 후 재실행, 또는 메뉴에서 경로 수동 지정
- **출력 GIF 없음** → 로그 창 오류 확인
- **FSS 4.0 GIF 업로드 실패** → 컨트롤러의 USB을 뽑고 전원을 껐다가 다시키고 USB 연결

---

## 📝 Attribution
- Icon: **“GIF file”** by **Freepik** on **Flaticon**  
  https://www.flaticon.com/free-icon/gif-file_3979434  
  License: Free for commercial use with attribution.  
  → 배포 ZIP에 `ATTRIBUTION.txt` 포함

## 📄 License
- MIT License — 상세 내용은 [LICENSE](./LICENSE) 참조.