# ffmpeg_tools.py
import os, stat, shutil, platform, zipfile, tarfile, urllib.request, subprocess
from pathlib import Path
from constants import CACHE_DIR, FFMPEG_DIR
from typing import List

def find_executable(name: str) -> str:
    # 로컬 ffmpeg-bin 디렉터리 우선 탐색
    local = FFMPEG_DIR / (name + (".exe" if os.name == "nt" else ""))
    if local.exists():
        return str(local)
    # 없을 경우 시스템 PATH에서 탐색
    return shutil.which(name) or ""

def run_quiet(cmd: list[str]):
    # 콘솔 창 없이 외부 프로세스를 실행하기 위한 설정
    kw = dict(capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if os.name == "nt":
        # Windows에서 cmd 창이 나타나지 않도록 설정
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
    return subprocess.run(cmd, **kw)

def probe_duration_sec(ffprobe_path: str, video_path: str) -> float:
    # ffprobe를 사용하여 동영상의 총 길이를 초 단위로 반환
    p = run_quiet([ffprobe_path, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", video_path])
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "ffprobe failed")
    return float(p.stdout.strip())

def extract_preview_frame(ffmpeg_path: str, video_path: str, ts: float) -> Path:
    # 지정된 타임스탬프(ts)에서 1280x720 해상도의 프리뷰 이미지(png)를 추출
    w, h = 1280, 720
    out_dir = CACHE_DIR / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 파일 경로와 시간을 기반으로 고유한 해시값을 파일명에 사용하여 캐싱
    out_path = out_dir / f"preview_{abs(hash((video_path, round(ts,3), f'{w}x{h}')))}.png"
    if out_path.exists(): # 이미 생성된 파일이 있으면 재사용
        return out_path
    p = run_quiet([ffmpeg_path, "-hide_banner", "-loglevel", "error",
                   "-ss", f"{ts:.3f}", "-i", video_path,
                   "-frames:v", "1", "-vf", f"scale={w}:{h}:flags=lanczos",
                   "-y", str(out_path)])
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "preview failed")
    return out_path

def build_filters(width: int, height: int, mode: str, fps: int, extra: str = "") -> str:
    # GIF 생성을 위한 ffmpeg 비디오 필터(-vf) 문자열을 생성
    if mode == "letterbox":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"; post = f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    elif mode == "cover":
        scale = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos"; post = f",crop={width}:{height}"
    else: # stretch
        scale = f"scale={width}:{height}:flags=lanczos"; post = ""
    base = f"fps={fps},{scale}{post}"
    return f"{base},{extra}" if extra else base

def build_gif_commands_auto(ffmpeg_path, video_path, start, end, fps, w, h, mode, alg, dither, out_path) -> List[list[str]]:
    # 자동 모드 GIF 생성을 위한 2-pass ffmpeg 명령어 리스트를 생성
    duration = max(0.0, end - start)
    if duration <= 0: raise ValueError("bad range")
    extra = "" if alg == "even" else "mpdecimate,setpts=N/FRAME_RATE/TB"
    vf = build_filters(w, h, mode, fps, extra)
    palette = str(CACHE_DIR / "palette.png")
    # Pass 1: 최적의 색상 팔레트 생성
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette]
    # Pass 2: 생성된 팔레트를 사용하여 GIF 생성
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
             "-i", video_path, "-i", palette, "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}",
             "-loop", "0", "-y", out_path]
    return [pass1, pass2]

def build_gif_commands_manual(ffmpeg_path, frames_dir: Path, fps, w, h, mode, dither, out_path) -> List[list[str]]:
    # (현재 미사용) 수동 모드 GIF 생성을 위한 명령어 리스트 생성
    vf = build_filters(w, h, mode, fps)
    palette = str(CACHE_DIR / "palette_manual.png")
    pass1 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"), "-vf", f"{vf},palettegen=stats_mode=full", "-y", palette]
    pass2 = [ffmpeg_path, "-hide_banner", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(frames_dir / "frame_%04d.png"), "-i", palette,
             "-lavfi", f"{vf}[x];[x][1:v]paletteuse=dither={dither}", "-loop", "0", "-y", out_path]
    return [pass1, pass2]

def _onerror_chmod(func, path, excinfo):
    # shutil.rmtree에서 권한 문제 발생 시 읽기/쓰기 권한을 부여하고 다시 시도
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except Exception:
        pass

def _download(url: str, dest_path: Path, log=lambda *_: None) -> bool:
    # 주어진 URL에서 파일을 다운로드하고 진행률을 로그로 남김
    try:
        with urllib.request.urlopen(url) as resp, open(dest_path, "wb") as out:
            total = int(resp.headers.get("Content-Length", "0") or 0); read = 0
            while True:
                chunk = resp.read(1024*256)
                if not chunk: break
                out.write(chunk); read += len(chunk)
                if total: log(f"[DL] {int(read*100/total)}%")
        log(f"[DL] 다운로드 완료: {url}")
        return True
    except Exception as e:
        log(f"[DL] err: {e}")
        if dest_path.exists(): # 실패 시 불완전한 파일 삭제
            dest_path.unlink()
        return False

def auto_setup_ffmpeg(log=lambda *_: None):
    # ffmpeg/ffprobe가 없으면 현재 OS에 맞게 자동으로 다운로드 및 준비
    ffmpeg = find_executable("ffmpeg")
    ffprobe = find_executable("ffprobe")
    if ffmpeg and ffprobe:
        log("[INFO] ffmpeg/ffprobe 준비 완료"); return

    os_name = platform.system().lower()
    if "windows" in os_name:
        _setup_windows_ffmpeg(log)
    elif "darwin" in os_name or "mac" in os_name:
        _setup_macos_ffmpeg(log)
    elif "linux" in os_name:
        _setup_linux_ffmpeg(log)
    else:
        log("[WARN] 지원하지 않는 OS입니다.")

def _setup_windows_ffmpeg(log):
    # Windows용 ffmpeg 다운로드 및 압축 해제
    z = FFMPEG_DIR / "ffmpeg-download.zip"
    
    # ▼▼▼ 수정된 부분: 404 오류를 유발하는 오래된 URL을 제거하고, 현재 유효한 최신 릴리스 URL로 교체 ▼▼▼
    # gyan.dev는 안정적인 리디렉션 링크를 제공하며, BtbN은 대안으로 추가합니다.
    urls = [
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    ]
    # ▲▲▲ 수정 완료 ▲▲▲

    for url in urls:
        log(f"[DL] {url}")
        if not _download(url, z, log): continue
        try:
            with zipfile.ZipFile(z, 'r') as zf:
                zf.extractall(FFMPEG_DIR)
            # 압축 해제된 파일들 중에서 ffmpeg.exe와 ffprobe.exe를 찾아 최상위 디렉터리로 복사
            ffmpeg = ffprobe = None
            for p in FFMPEG_DIR.rglob("*"):
                if p.name.lower()=="ffmpeg.exe": ffmpeg=str(p.resolve())
                elif p.name.lower()=="ffprobe.exe": ffprobe=str(p.resolve())
            if ffmpeg and ffprobe:
                shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg.exe")
                shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe.exe")
                tidy_ffmpeg_dir(log) # 필요 없는 파일 정리
                return
        except Exception as e:
            log(f"[ERR] 압축 해제 실패: {e}")
    log("[ERR] ffmpeg 준비에 실패했습니다.")


def _setup_macos_ffmpeg(log):
    # macOS에서 Homebrew를 이용하여 ffmpeg 설치 시도
    brew = shutil.which("brew")
    if brew:
        log("[INFO] Homebrew를 사용하여 ffmpeg 설치를 시도합니다...")
        try: run_quiet([brew, "install", "ffmpeg"])
        except Exception as e: log(f"[ERR] Homebrew 설치 실패: {e}")
    else:
        log("[WARN] ffmpeg 자동 설치를 위해 Homebrew를 설치해주세요.")

def _setup_linux_ffmpeg(log):
    # Linux에서 apt-get을 이용하여 ffmpeg 설치 시도, 실패 시 정적 빌드 다운로드
    apt = shutil.which("apt-get")
    if apt:
        log("[INFO] apt-get을 사용하여 ffmpeg 설치를 시도합니다...")
        try:
            run_quiet(["sudo","apt-get","update"]); run_quiet(["sudo","apt-get","-y","install","ffmpeg"])
        except Exception as e:
            log(f"[ERR] apt-get 설치 실패: {e}")
    # apt로 설치되지 않았을 경우, johnvansickle.com의 정적 빌드를 다운로드
    if not find_executable("ffmpeg") or not find_executable("ffprobe"):
        arch = platform.machine().lower()
        if arch in ("x86_64","amd64"):
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        elif arch in ("aarch64","arm64"):
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
        else:
            log(f"[WARN] 지원하지 않는 아키텍처입니다: {arch}"); return
        tar = FFMPEG_DIR / url.split("/")[-1]
        if _download(url, tar, log):
            try:
                with tarfile.open(tar, 'r:*') as tf:
                    tf.extractall(FFMPEG_DIR)
                ffmpeg = ffprobe = None
                for p in FFMPEG_DIR.rglob("*"):
                    if p.name=="ffmpeg": ffmpeg=str(p.resolve())
                    elif p.name=="ffprobe": ffprobe=str(p.resolve())
                if ffmpeg and ffprobe:
                    shutil.copy2(ffmpeg, FFMPEG_DIR/"ffmpeg")
                    shutil.copy2(ffprobe, FFMPEG_DIR/"ffprobe")
                    os.chmod(FFMPEG_DIR/"ffmpeg", 0o755); os.chmod(FFMPEG_DIR/"ffprobe", 0o755)
                    tidy_ffmpeg_dir(log)
            except Exception as e:
                log(f"[ERR] 압축 해제 실패: {e}")

def tidy_ffmpeg_dir(log=lambda *_: None):
    # ffmpeg-bin 디렉터리에서 실행 파일(ffmpeg, ffprobe)만 남기고 나머지 파일/디렉터리 정리
    try:
        keep = {"ffmpeg.exe","ffprobe.exe"} if os.name=="nt" else {"ffmpeg","ffprobe"}
        # 핵심 실행 파일이 모두 존재하는지 먼저 확인
        if not all((FFMPEG_DIR/k).exists() for k in keep):
            log("[WARN] 핵심 실행 파일이 없어 정리를 건너뜁니다.")
            return
        for p in FFMPEG_DIR.iterdir():
            if p.name in keep: 
                continue
            try:
                if p.is_dir(): shutil.rmtree(p, onerror=_onerror_chmod)
                else: p.unlink()
            except Exception as e:
                log(f"[WARN] 파일 삭제 실패 {p.name}: {e}")
        log("[OK] ffmpeg-bin 디렉터리 정리 완료")
    except Exception as e:
        log(f"[ERR] 디렉터리 정리 중 오류: {e}")