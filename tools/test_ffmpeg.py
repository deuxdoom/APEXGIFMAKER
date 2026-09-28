# test_ffmpeg.py
"""ffmpeg 종단 테스트. bin 폴더 또는 PATH에 ffmpeg/ffprobe가 없으면 건너뜁니다.

테스트 영상(5초): 앞 3초는 움직이는 패턴, 뒤 2초는 정지 화면입니다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _bootstrap

_bootstrap.setup()

from src.core import ffmpeg as ff  # noqa: E402
from src.core.encoder import EncodeCancelled, GifEncoder  # noqa: E402
from src.core.gif import GifOptions  # noqa: E402

FFMPEG = ff.find_executable("ffmpeg")
FFPROBE = ff.find_executable("ffprobe")


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe not found")
class FfmpegTests(unittest.TestCase):
    folder: Path
    video: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.folder = Path(tempfile.mkdtemp(prefix="ffmpeg-test-"))
        cls.video = str(cls.folder / "source.mp4")
        proc = ff.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                       "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=30:duration=3",
                       "-f", "lavfi", "-i", "color=c=0x0867c4:size=320x240:rate=30:duration=2",
                       "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p",
                       "-c:v", "libx264", "-g", "60", cls.video], timeout=120)
        if proc.returncode != 0:
            raise unittest.SkipTest(f"cannot create test video: {proc.stderr}")

    def test_probe(self):
        info = ff.probe_video(FFPROBE, self.video)
        self.assertAlmostEqual(info.duration, 5.0, delta=0.05)
        self.assertEqual((info.width, info.height), (320, 240))
        self.assertAlmostEqual(info.fps, 30.0, delta=0.01)

    def test_grab_frame_including_end(self):
        for ts in (0.0, 2.5, 5.0):       # 5.0초는 마지막 프레임 이후라 앞쪽으로 다시 시도해야 합니다.
            data = ff.grab_frame(FFMPEG, self.video, ts, 640, 360)
            self.assertEqual(data[:2], b"\xff\xd8", ts)

    def encode(self, start: float, end: float, opts: GifOptions, name: str, **callbacks):
        encoder = GifEncoder(FFMPEG, self.video, start, end, opts, self.folder / name)
        return encoder, encoder.run(**callbacks)

    def test_encode_even(self):
        stages: list[str] = []
        progress: list[float] = []
        _, result = self.encode(1.0, 4.0, GifOptions(), "even.gif", on_stage=stages.append,
                                on_progress=progress.append)
        info = result.info
        assert info is not None
        self.assertEqual((info.width, info.height), (160, 80))
        self.assertEqual(info.frames, 36)
        self.assertAlmostEqual(info.duration_ms, 3000, delta=100)
        self.assertEqual(info.loop, 0)
        self.assertEqual(stages, ["palette", "encode"])
        self.assertAlmostEqual(progress[-1], 1.0)
        self.assertFalse((self.folder / "even.gif.part").exists())

    def test_encode_letterbox_dedupe(self):
        opts = GifOptions(width=120, height=120, scale_mode="letterbox", frame_mode="dedupe", dither="bayer")
        _, result = self.encode(2.0, 5.0, opts, "dedupe.gif")
        info = result.info
        assert info is not None
        self.assertEqual((info.width, info.height), (120, 120))
        self.assertLess(info.frames, 36)          # 뒤 2초 정지 구간이 접힙니다.

    def test_cancel_during_encode(self):
        target = self.folder / "cancelled.gif"
        encoder = GifEncoder(FFMPEG, self.video, 0.0, 5.0, GifOptions(), target)

        def on_stage(stage: str) -> None:
            if stage == "encode":
                encoder.cancel()

        with self.assertRaises(EncodeCancelled):
            encoder.run(on_stage=on_stage)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + ".part").exists())

    def test_export_clip(self):
        target = self.folder / "clip.mp4"
        proc = ff.export_clip(FFMPEG, self.video, 1.0, 2.0, target)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertAlmostEqual(ff.probe_video(FFPROBE, str(target)).duration, 2.0, delta=0.1)


if __name__ == "__main__":
    unittest.main()
