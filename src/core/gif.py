# gif.py
"""GIF 옵션과 ffmpeg 필터·명령 생성을 담당합니다."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .config import (
    DEFAULT_FPS, DEFAULT_HEIGHT, DEFAULT_WIDTH, FPS_MAX, FPS_MIN, SIZE_MAX, SIZE_MIN,
)

# UI의 콤보박스 순서와 같습니다. (v2 설정 파일은 이 순서의 인덱스를 저장했습니다.)
SCALE_MODES = ("cover", "letterbox", "stretch")
DITHER_MODES = ("floyd_steinberg", "bayer", "none")
FRAME_MODES = ("even", "dedupe")

# 1-pass는 팔레트가 완성될 때(구간 끝)까지 모든 프레임을 메모리에 쌓아 둡니다. 예상 프레임 수 × 가로 × 세로가
# 이 값 이하일 때만 1-pass를 씁니다. 쌓아 두는 프레임은 픽셀당 4바이트라 최대 약 200MB입니다.
# (실측: 기준값 근처인 640×360·216장에서 ffmpeg 최대 메모리 약 410MB, 같은 조건의 2-pass는 약 180MB.
#  APEX 기본 160×80은 60fps·30초도 1-pass이고 이때 쌓는 프레임은 약 90MB, 기본값인 12fps·6초는 약 4MB입니다.)
ONE_PASS_MAX_PIXELS = 50_000_000
DEDUPE_FILTER = "mpdecimate,setpts=N/FRAME_RATE/TB"
# 진행률용: 프레임마다 원본 기준 시각(pts_time)을 로그로 내보냅니다. 중복 제거보다 앞에 두어 정지 구간이 접혀도
# 실제로 처리한 위치를 알 수 있습니다. 체크섬 계산을 끄는 checksum=0은 오래된 ffmpeg(시스템 PATH에 있는 것)에
# 없는 옵션이라 쓰지 않습니다. 추가 비용은 1280×720 GIF에서도 약 1.5%입니다.
PROGRESS_FILTER = "showinfo"
# 진행률을 읽는 명령의 로그 설정. level+ 를 붙이면 줄마다 [info]·[error] 같은 등급이 붙어 오류만 골라낼 수 있습니다.
PROGRESS_LOG = ("-hide_banner", "-nostdin", "-nostats", "-loglevel", "level+info")
QUIET_LOG = ("-hide_banner", "-nostdin", "-loglevel", "error")


def _to_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _pick(value: Any, choices: tuple[str, ...], default: str) -> str:
    return value if value in choices else default


def _pick_index(index: Any, choices: tuple[str, ...], default: str) -> str:
    if isinstance(index, int) and 0 <= index < len(choices):
        return choices[index]
    return default


@dataclass(frozen=True)
class GifOptions:
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = DEFAULT_FPS
    scale_mode: str = "cover"         # cover | letterbox | stretch
    dither: str = "floyd_steinberg"   # floyd_steinberg | bayer | none
    frame_mode: str = "even"          # even | dedupe

    @property
    def aspect(self) -> float:
        return self.width / self.height

    def normalized(self) -> "GifOptions":
        return replace(
            self,
            width=_to_int(self.width, DEFAULT_WIDTH, SIZE_MIN, SIZE_MAX),
            height=_to_int(self.height, DEFAULT_HEIGHT, SIZE_MIN, SIZE_MAX),
            fps=_to_int(self.fps, DEFAULT_FPS, FPS_MIN, FPS_MAX),
            scale_mode=_pick(self.scale_mode, SCALE_MODES, "cover"),
            dither=_pick(self.dither, DITHER_MODES, "floyd_steinberg"),
            frame_mode=_pick(self.frame_mode, FRAME_MODES, "even"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "GifOptions":
        """설정 파일 값으로 옵션을 만듭니다. v2.x의 인덱스 키(mode_idx 등)도 읽습니다."""
        if not isinstance(data, Mapping):
            return cls()
        default = cls()
        opts = cls(
            width=data.get("width", default.width),
            height=data.get("height", default.height),
            fps=data.get("fps", default.fps),
            scale_mode=data.get("scale_mode")
            or _pick_index(data.get("scale_idx"), SCALE_MODES, default.scale_mode),
            dither=data.get("dither")
            or _pick_index(data.get("dither_idx"), DITHER_MODES, default.dither),
            frame_mode=data.get("frame_mode")
            or _pick_index(data.get("mode_idx"), FRAME_MODES, default.frame_mode),
        )
        return opts.normalized()


def estimate_frames(length: float, fps: int) -> int:
    """균등 모드에서 만들어질 프레임 수를 추정합니다.

    ffmpeg에 넘기는 길이(밀리초)로 정수 계산하고 .5는 올립니다. ffmpeg도 경계값에서 올림으로 세기 때문입니다.
    (파이썬 round()는 짝수 쪽으로 반올림해서 16.5가 16이 됩니다.) 실제 수는 원본 FPS에 따라 조금 다를 수 있습니다.
    """
    ms = round(max(0.0, length) * 1000)
    return max(1, (ms * int(fps) + 500) // 1000)


def uses_one_pass(length: float, opts: GifOptions) -> bool:
    """영상을 한 번만 읽는 1-pass로 만들어도 메모리가 넉넉한지. (아니면 팔레트 생성과 변환을 따로 합니다)"""
    return estimate_frames(length, opts.fps) * opts.width * opts.height <= ONE_PASS_MAX_PIXELS


def scale_filter(opts: GifOptions) -> str:
    w, h = opts.width, opts.height
    if opts.scale_mode == "letterbox":
        # 비율을 유지해서 안쪽에 맞추고, 남는 곳은 검은 여백으로 채웁니다.
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black")
    if opts.scale_mode == "stretch":
        # 비율을 무시하고 지정한 크기로 늘립니다.
        return f"scale={w}:{h}:flags=lanczos"
    # cover: 비율을 유지해서 꽉 채우고, 넘치는 부분은 가운데 기준으로 잘라냅니다.
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h}")


def frame_filter(opts: GifOptions, *, progress: bool = False) -> str:
    """팔레트 생성과 GIF 변환 양쪽에 똑같이 쓰는 프레임 필터 체인입니다. progress면 진행률용 showinfo를 넣습니다."""
    chain = [f"fps={opts.fps}", scale_filter(opts), "setsar=1"]
    if progress:
        chain.append(PROGRESS_FILTER)
    if opts.frame_mode == "dedupe":
        # 중복 프레임을 지우고 타임스탬프를 다시 매깁니다. 정지 구간이 접혀서 재생 시간이 짧아집니다.
        chain.append(DEDUPE_FILTER)
    return ",".join(chain)


def paletteuse_filter(opts: GifOptions) -> str:
    # diff_mode=rectangle: 이전 프레임과 달라진 영역만 다시 그려서 파일 크기를 줄입니다.
    return f"paletteuse=dither={opts.dither}:diff_mode=rectangle"


def _input_args(source: str, start: float, length: float) -> list[str]:
    return ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", source]


def build_palette_command(ffmpeg: str, source: str, start: float, length: float,
                          opts: GifOptions, palette: str | Path) -> list[str]:
    """2-pass의 1단계: 구간 전체를 분석해서 최적의 256색 팔레트를 만듭니다."""
    return [
        ffmpeg, *QUIET_LOG,
        *_input_args(source, start, length),
        "-an", "-sn", "-dn",
        "-vf", f"{frame_filter(opts)},palettegen=stats_mode=full",
        "-frames:v", "1", "-update", "1", "-y", str(palette),
    ]


def build_gif_command(ffmpeg: str, source: str, start: float, length: float,
                      opts: GifOptions, palette: str | Path, output: str | Path) -> list[str]:
    """2-pass의 2단계: 팔레트를 적용해서 GIF를 만듭니다. (출력 확장자와 관계없이 GIF 형식으로 씁니다.)"""
    return [
        ffmpeg, *PROGRESS_LOG,
        *_input_args(source, start, length),
        "-i", str(palette),
        "-an", "-sn", "-dn",
        "-lavfi", f"{frame_filter(opts, progress=True)}[x];[x][1:v]{paletteuse_filter(opts)}",
        "-loop", "0", "-f", "gif", "-y", str(output),
    ]


def build_one_pass_command(ffmpeg: str, source: str, start: float, length: float,
                           opts: GifOptions, output: str | Path) -> list[str]:
    """1-pass: 한 번 읽은 프레임을 둘로 나눠(split) 팔레트를 만들고 바로 적용합니다. 결과는 2-pass와 같습니다.

    팔레트가 완성될 때까지 프레임을 메모리에 쌓아 두므로 uses_one_pass()가 참일 때만 씁니다.
    """
    graph = (f"{frame_filter(opts, progress=True)},split[a][b];[a]palettegen=stats_mode=full[p];"
             f"[b][p]{paletteuse_filter(opts)}")
    return [
        ffmpeg, *PROGRESS_LOG,
        *_input_args(source, start, length),
        "-an", "-sn", "-dn",
        "-lavfi", graph,
        "-loop", "0", "-f", "gif", "-y", str(output),
    ]


def build_gif_commands(ffmpeg: str, source: str, start: float, end: float,
                       opts: GifOptions, palette: str | Path, output: str | Path) -> list[list[str]]:
    length = end - start
    if length <= 0:
        raise ValueError("invalid time range")
    return [
        build_palette_command(ffmpeg, source, start, length, opts, palette),
        build_gif_command(ffmpeg, source, start, length, opts, palette, output),
    ]


def suggest_filename(video_path: str, start: float, end: float) -> str:
    """기본 출력 파일 이름: `<영상이름>_<시작ms>_<끝ms>.gif` (v2.x와 같은 규칙)"""
    stem = Path(video_path).stem or "output"
    return f"{stem}_{int(round(start * 1000))}_{int(round(end * 1000))}.gif"
