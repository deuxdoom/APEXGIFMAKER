# color.py
"""원본 영상의 색 정보와, GIF·미리보기에 쓰는 색 변환 필터를 다룹니다. (Qt 없이 테스트 가능)

- SDR: 색 정보(YCbCr 행렬)가 없는 HD 영상은 BT.709로 봅니다. ffmpeg는 정보가 없으면 BT.601로 계산해서
  초록·빨강이 조금 틀어지기 때문입니다. (브라우저·동영상 플레이어도 HD는 BT.709로 봅니다.)
- HDR(PQ = HDR10, HLG = 방송·휴대폰): zscale로 빛의 세기(선형)로 바꾼 뒤 mobius로 밝은 부분만 부드럽게
  눌러 SDR(BT.709)로 바꿉니다(톤매핑). 기준 백색은 BT.2408의 203니트, 최대 밝기는 영상에 적힌 값(없으면
  1000니트)입니다. desat=0으로 밝은 부분의 채도를 빼지 않습니다(기본값 2는 색이 회색으로 바랩니다).
  실측(2026-11-18): HLG 4K 방송 영상에서 hable은 어둡고 탁했고, 기준 백색 100니트는 피부가 날아갔습니다.
"""
from __future__ import annotations

from dataclasses import dataclass

REFERENCE_WHITE_NITS = 203.0      # BT.2408: HDR에서 SDR 흰색(100%)에 해당하는 밝기
DEFAULT_PEAK_NITS = 1000.0        # 영상에 최대 밝기 정보가 없을 때 (HDR10 대부분, HLG 기준 표시 장치)
MAX_PEAK_NITS = 10000.0           # PQ가 표현할 수 있는 최대 밝기

HDR_TRANSFERS = {"smpte2084": "pq", "arib-std-b67": "hlg"}
# ffprobe의 color_space 이름 → swscale(scale 필터 in_color_matrix) 이름
_MATRICES = {"bt709": "bt709", "bt470bg": "bt470bg", "smpte170m": "smpte170m", "smpte240m": "smpte240m",
             "fcc": "fcc", "bt2020nc": "bt2020", "bt2020c": "bt2020"}
# HDR 입력으로 받는 행렬·색 영역(zscale도 ffprobe와 같은 이름을 씁니다). 그 밖의 값은 BT.2020으로 봅니다.
_HDR_MATRICES = ("bt2020nc", "bt2020c", "bt709")
_HDR_PRIMARIES = ("bt2020", "bt709", "smpte431", "smpte432")


@dataclass(frozen=True)
class ColorInfo:
    """ffprobe가 알려 준 첫 번째 비디오 스트림의 색 정보. 모르는 값은 빈 문자열입니다."""

    matrix: str = ""          # color_space (YCbCr 행렬)
    transfer: str = ""        # color_transfer (밝기 곡선)
    primaries: str = ""       # color_primaries (색 영역)
    range: str = ""           # color_range: tv(16~235) | pc(0~255)
    peak_nits: float = 0.0    # 최대 밝기(MaxCLL 또는 마스터링 표시 장치 값). 모르면 0
    hd: bool = True           # 가로 1280 또는 세로 720 이상. 행렬 정보가 없을 때 BT.709/BT.601을 고르는 기준

    @property
    def hdr(self) -> str:
        """HDR 방식: "pq" | "hlg" | "" (SDR)"""
        return HDR_TRANSFERS.get(self.transfer, "")

    @property
    def yuv_matrix(self) -> str:
        """YUV → RGB 변환에 쓸 행렬(swscale 이름)."""
        return _MATRICES.get(self.matrix) or ("bt709" if self.hd else "smpte170m")

    @property
    def yuv_range(self) -> str:
        return "pc" if self.range in ("pc", "jpeg", "full") else "tv"

    @property
    def peak(self) -> float:
        """톤매핑의 최대 밝기(기준 백색 = 1). 1보다 작으면 SDR 범위라 누를 것이 없습니다."""
        nits = self.peak_nits if REFERENCE_WHITE_NITS < self.peak_nits <= MAX_PEAK_NITS else DEFAULT_PEAK_NITS
        return round(nits / REFERENCE_WHITE_NITS, 3)


SDR = ColorInfo()


def tonemap_filter(color: ColorInfo, *, out_range: str = "pc") -> str:
    """HDR 프레임을 SDR BT.709 yuv444p(out_range 범위)로 바꾸는 필터 체인. 입력은 원본 YUV(10비트 그대로)입니다."""
    tin = "smpte2084" if color.hdr == "pq" else "arib-std-b67"
    matrix = color.matrix if color.matrix in _HDR_MATRICES else "bt2020nc"
    primaries = color.primaries if color.primaries in _HDR_PRIMARIES else "bt2020"
    # 입력 값을 모두 직접 정하고 출력 색 영역(p)도 정합니다. 출력 값을 비워 두면 zscale이 프레임의 태그를 그대로
    # 쓰려다가, 태그가 빠진 파일에서 "no path between colorspaces"로 실패합니다.
    return (f"zscale=tin={tin}:min={matrix}:pin={primaries}:rin={color.yuv_range}"
            f":t=linear:npl={REFERENCE_WHITE_NITS:g}:p=bt709,format=gbrpf32le,"
            f"tonemap=tonemap=mobius:desat=0:peak={color.peak:g},"
            f"zscale=t=bt709:m=bt709:r={out_range},format=yuv444p")


def to_rgb_filter(matrix: str, yuv_range: str, pix_fmt: str) -> str:
    """YUV를 정한 행렬·범위로 RGB(pix_fmt)로 바꿉니다. ffmpeg가 자동으로 넣는 변환은 태그 없는 HD를 BT.601로
    계산하므로, 색이 틀어지지 않게 직접 지정합니다."""
    return (f"scale=in_color_matrix={matrix}:in_range={yuv_range}:flags=accurate_rnd+full_chroma_int,"
            f"format={pix_fmt}")


def parse_side_data(stream: dict) -> float:
    """스트림 부가 정보에서 최대 밝기(니트)를 읽습니다. MaxCLL을 먼저, 없으면 마스터링 표시 장치 값을 씁니다."""
    cll = mastering = 0.0
    for side in stream.get("side_data_list") or []:
        kind = str(side.get("side_data_type", ""))
        try:
            if kind == "Content light level metadata":
                cll = float(side.get("max_content") or 0)
            elif kind == "Mastering display metadata":
                num, _, den = str(side.get("max_luminance") or "0").partition("/")
                mastering = float(num) / float(den or 1)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    return cll or mastering


def from_probe(stream: dict, width: int, height: int) -> ColorInfo:
    def text(key: str) -> str:
        value = stream.get(key)
        return value if isinstance(value, str) and value not in ("unknown", "reserved", "unspecified") else ""

    return ColorInfo(text("color_space"), text("color_transfer"), text("color_primaries"), text("color_range"),
                     parse_side_data(stream), width >= 1280 or height >= 720)
