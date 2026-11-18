# gif.py
"""GIF 옵션과 ffmpeg 필터·명령 생성을 담당합니다."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .color import SDR, ColorInfo, to_rgb_filter, tonemap_filter
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
# 크기 조절 품질. accurate_rnd(정확한 반올림)와 full_chroma_*(색 정보를 줄이지 않고 계산)로 작은 GIF의 색 번짐을 줄입니다.
SCALE_FLAGS = "lanczos+accurate_rnd+full_chroma_int+full_chroma_inp"
# 팔레트: 256색을 모두 씁니다. ffmpeg 기본값은 투명색 자리 하나를 비워 둬서 255색인데, 이 GIF는 투명색을 쓰지 않습니다.
PALETTEGEN_FILTER = "palettegen=stats_mode=full:reserve_transparent=0"
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


def scale_filter(opts: GifOptions, *, hdr: bool = False) -> str:
    """GIF 크기로 줄이고 자르거나 여백을 둡니다. 색 정보는 4:4:4(화소마다 색)로 둡니다.

    4:2:0(가로세로 두 화소에 색 하나)인 채로 160×80까지 줄이면 색 해상도가 80×40이 되어 경계의 색이 번집니다.
    (실측 2026-11-18: 원본과의 색 차이 ΔE 4.5 → 0.8) HDR은 톤매핑 전이라 10비트를 그대로 둡니다.
    """
    w, h = opts.width, opts.height
    fmt = "format=yuv444p10le" if hdr else "format=yuv444p"
    if opts.scale_mode == "letterbox":
        # 비율을 유지해서 안쪽에 맞추고, 남는 곳은 검은 여백으로 채웁니다.
        return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags={SCALE_FLAGS},{fmt},"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black")
    if opts.scale_mode == "stretch":
        # 비율을 무시하고 지정한 크기로 늘립니다.
        return f"scale={w}:{h}:flags={SCALE_FLAGS},{fmt}"
    # cover: 비율을 유지해서 꽉 채우고, 넘치는 부분은 가운데 기준으로 잘라냅니다.
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags={SCALE_FLAGS},{fmt},"
            f"crop={w}:{h}")


def frame_filter(opts: GifOptions, color: ColorInfo = SDR, *, tonemap: bool = False, progress: bool = False) -> str:
    """팔레트 생성과 GIF 변환 양쪽에 똑같이 쓰는 프레임 필터 체인입니다.

    작게 줄인 뒤에 색을 바꿔서 빠릅니다(4K HDR도 160×80에서 톤매핑). tonemap이면 HDR을 SDR로 바꾸고,
    progress면 진행률용 showinfo를 넣습니다. 마지막에 원본 행렬로 RGB를 만들어 팔레트 필터에 넘깁니다.
    """
    chain = [f"fps={opts.fps}", scale_filter(opts, hdr=tonemap)]
    if tonemap:
        chain.append(tonemap_filter(color))
    chain.append("setsar=1")
    if progress:
        chain.append(PROGRESS_FILTER)
    if opts.frame_mode == "dedupe":
        # 중복 프레임을 지우고 타임스탬프를 다시 매깁니다. 정지 구간이 접혀서 재생 시간이 짧아집니다.
        # (mpdecimate는 8비트 YUV만 받으므로 RGB로 바꾸기 전에 둡니다.)
        chain.append(DEDUPE_FILTER)
    chain.append(to_rgb_filter("bt709", "pc", "bgra") if tonemap
                 else to_rgb_filter(color.yuv_matrix, color.yuv_range, "bgra"))
    return ",".join(chain)


def paletteuse_filter(opts: GifOptions) -> str:
    # diff_mode=rectangle: 이전 프레임과 달라진 영역만 다시 그려서 파일 크기를 줄입니다.
    return f"paletteuse=dither={opts.dither}:diff_mode=rectangle"


def _input_args(source: str, start: float, length: float) -> list[str]:
    return ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", source]


@dataclass(frozen=True)
class SourceColor:
    """GIF 명령에 넘기는 원본 색 정보와 HDR 톤매핑 여부."""
    color: ColorInfo = SDR
    tonemap: bool = False


PLAIN = SourceColor()


def build_palette_command(ffmpeg: str, source: str, start: float, length: float,
                          opts: GifOptions, palette: str | Path, src: SourceColor = PLAIN) -> list[str]:
    """2-pass의 1단계: 구간 전체를 분석해서 최적의 256색 팔레트를 만듭니다."""
    return [
        ffmpeg, *QUIET_LOG,
        *_input_args(source, start, length),
        "-an", "-sn", "-dn",
        "-vf", f"{frame_filter(opts, src.color, tonemap=src.tonemap)},{PALETTEGEN_FILTER}",
        "-frames:v", "1", "-update", "1", "-y", str(palette),
    ]


def build_gif_command(ffmpeg: str, source: str, start: float, length: float,
                      opts: GifOptions, palette: str | Path, output: str | Path, src: SourceColor = PLAIN) -> list[str]:
    """2-pass의 2단계: 팔레트를 적용해서 GIF를 만듭니다. (출력 확장자와 관계없이 GIF 형식으로 씁니다.)"""
    return [
        ffmpeg, *PROGRESS_LOG,
        *_input_args(source, start, length),
        "-i", str(palette),
        "-an", "-sn", "-dn",
        "-lavfi", f"{frame_filter(opts, src.color, tonemap=src.tonemap, progress=True)}[x];"
                  f"[x][1:v]{paletteuse_filter(opts)}",
        "-loop", "0", "-f", "gif", "-y", str(output),
    ]


def build_one_pass_command(ffmpeg: str, source: str, start: float, length: float,
                           opts: GifOptions, output: str | Path, src: SourceColor = PLAIN) -> list[str]:
    """1-pass: 한 번 읽은 프레임을 둘로 나눠(split) 팔레트를 만들고 바로 적용합니다. 결과는 2-pass와 같습니다.

    팔레트가 완성될 때까지 프레임을 메모리에 쌓아 두므로 uses_one_pass()가 참일 때만 씁니다.
    """
    graph = (f"{frame_filter(opts, src.color, tonemap=src.tonemap, progress=True)},split[a][b];"
             f"[a]{PALETTEGEN_FILTER}[p];[b][p]{paletteuse_filter(opts)}")
    return [
        ffmpeg, *PROGRESS_LOG,
        *_input_args(source, start, length),
        "-an", "-sn", "-dn",
        "-lavfi", graph,
        "-loop", "0", "-f", "gif", "-y", str(output),
    ]


def suggest_filename(video_path: str, start: float, end: float) -> str:
    """기본 출력 파일 이름: `<영상이름>_<시작ms>_<끝ms>.gif` (v2.x와 같은 규칙)"""
    stem = Path(video_path).stem or "output"
    return f"{stem}_{int(round(start * 1000))}_{int(round(end * 1000))}.gif"
