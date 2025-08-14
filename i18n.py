# i18n.py
# 간단한 다국어(한국어/영어) 키-값 사전 + 안전 폴백 t(lang, key)

from __future__ import annotations

# 한국어 문자열
_KO = {
    # 공통 라벨
    "start": "시작:",
    "end": "끝:",
    "play_range": "구간 재생",
    "input_video": "입력 비디오:",
    "output": "출력:",
    "choose": "저장 위치...",
    "generate": "GIF 생성",

    # 옵션 패널
    "mode": "모드:",
    "fps": "FPS:",
    "width": "가로:",
    "height": "세로:",
    "scale": "스케일:",
    "dither": "디더링:",
    "dither_help": "디더링이란?",
    "dither_help_text": (
        "GIF는 256색 팔레트를 사용합니다. 디더링은 색 밴딩을 줄이기 위해 작은 패턴/노이즈를 섞는 기법입니다.\n\n"
        "• 플로이드-슈타인버그: 부드럽고 자연스러움\n"
        "• 바이어: 격자 패턴, 선명\n"
        "• 없음: 또렷하지만 밴딩 가능"
    ),
    "dither_fs": "플로이드-슈타인버그",
    "dither_bayer": "바이어",
    "dither_none": "없음",

    # 메시지
    "error": "오류",
    "warn": "경고",
    "done": "완료",
    "quit": "종료",
    "update": "업데이트",
    "update_prompt": "새로운 버전이 나왔습니다.\n다운하러 이동하시겠습니까?",
    "gif_saved": "GIF 생성 완료:\n{}",
    "load_video_first": "먼저 비디오를 불러오세요.",
    "need_ffmpeg": "ffmpeg/ffprobe 준비가 필요합니다.",
    "range_invalid": "구간은 1~15초입니다.",
}

# 영어 문자열
_EN = {
    "start": "Start:",
    "end": "End:",
    "play_range": "Play Range",
    "input_video": "Input Video:",
    "output": "Output:",
    "choose": "Choose…",
    "generate": "Generate GIF",

    "mode": "Mode:",
    "fps": "FPS:",
    "width": "Width:",
    "height": "Height:",
    "scale": "Scale:",
    "dither": "Dithering:",
    "dither_help": "What is dithering?",
    "dither_help_text": (
        "GIF uses a 256-color palette. Dithering mixes patterns/noise to reduce banding.\n\n"
        "• Floyd–Steinberg: smooth/natural\n"
        "• Bayer: ordered grid, crisp\n"
        "• None: sharp but may band"
    ),
    "dither_fs": "floyd_steinberg",
    "dither_bayer": "bayer",
    "dither_none": "none",

    "error": "Error",
    "warn": "Warning",
    "done": "Done",
    "quit": "Quit",
    "update": "Update",
    "update_prompt": "A new version is available.\nOpen downloads page?",
    "gif_saved": "Saved:\n{}",
    "load_video_first": "Load a video first.",
    "need_ffmpeg": "ffmpeg/ffprobe required.",
    "range_invalid": "Range must be 1–15s.",
}

_LANGS = {"ko": _KO, "en": _EN}


def t(lang: str, key: str) -> str:
    """
    안전한 번역 조회. lang가 'ko'가 아니면 영어로 처리.
    키가 없으면 KeyError 대신 key 자체를 반환(폴백).
    """
    table = _KO if (lang or "").lower().startswith("ko") else _EN
    return table.get(key, key)
