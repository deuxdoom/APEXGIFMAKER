# test_core.py
"""src/core와 src/i18n 단위 테스트 (Qt 없이 실행). `python tools/check.py`가 함께 실행합니다."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _bootstrap

_bootstrap.setup()

from src import i18n  # noqa: E402
from src.core import apply_update, ffmpeg, ffmpeg_setup, gif, gifinfo, self_update, settings, timecode  # noqa: E402
from src.core import updater  # noqa: E402
from src.core.trim import Selection, TrimRules  # noqa: E402


def _tmp(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


class TimecodeTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(timecode.format_time(0), "00:00.000")
        self.assertEqual(timecode.format_time(59.9996), "01:00.000")   # v2.x는 "00:60.000"
        self.assertEqual(timecode.format_time(3723.25), "01:02:03.250")
        self.assertEqual(timecode.format_time(5, force_hours=True), "00:00:05.000")
        self.assertEqual(timecode.format_time(-3), "00:00.000")

    def test_parse_valid(self):
        cases = {"90": 90, "90.5": 90.5, "1:30": 90, "01:30.250": 90.25, "1:02:03.5": 3723.5,
                 "3.5s": 3.5, "1,5": 1.5, " 0:05 ": 5}
        for text, expected in cases.items():
            self.assertAlmostEqual(timecode.parse_time(text), expected, msg=text)

    def test_parse_invalid(self):
        for text in ("", "abc", "1:60", "1:60:00", "-1", "1::2", "1:2:3:4", "nan", "inf"):
            with self.assertRaises(ValueError, msg=text):
                timecode.parse_time(text)


class TrimTests(unittest.TestCase):
    rules = TrimRules(100.0)

    def test_initial(self):
        self.assertEqual(self.rules.initial(), Selection(0.0, 6.0))
        self.assertEqual(TrimRules(3.0).initial(), Selection(0.0, 3.0))
        self.assertEqual(TrimRules(0.5).initial(), Selection(0.0, 0.5))   # 최소 길이보다 짧은 영상

    def test_invalid_rules(self):
        with self.assertRaises(ValueError):
            TrimRules(0.0)

    def test_drag_changes_only_that_edge(self):
        sel = Selection(10.0, 16.0)
        self.assertEqual(self.rules.drag_start(sel, 12.0), Selection(12.0, 16.0))
        self.assertEqual(self.rules.drag_end(sel, 20.0), Selection(10.0, 20.0))

    def test_drag_stops_at_limits(self):
        sel = Selection(10.0, 16.0)
        self.assertEqual(self.rules.drag_start(sel, 15.8), Selection(15.0, 16.0))   # 최소 1초
        self.assertEqual(self.rules.drag_start(sel, -50.0), Selection(0.0, 16.0))
        self.assertEqual(self.rules.drag_end(sel, 90.0), Selection(10.0, 40.0))     # 최대 30초
        self.assertEqual(self.rules.drag_end(Selection(80.0, 90.0), 150.0), Selection(80.0, 100.0))

    def test_move_keeps_length(self):
        sel = Selection(10.0, 16.0)
        self.assertEqual(self.rules.move(sel, 50.0), Selection(50.0, 56.0))
        self.assertEqual(self.rules.move(sel, 99.0), Selection(94.0, 100.0))
        self.assertEqual(self.rules.move(sel, -5.0), Selection(0.0, 6.0))

    def test_typed_values(self):
        sel = Selection(10.0, 16.0)
        self.assertEqual(self.rules.set_start(sel, 12.5), Selection(12.5, 16.0))
        self.assertEqual(self.rules.set_start(sel, 30.0), Selection(30.0, 36.0))    # 끝을 넘으면 길이 유지
        self.assertEqual(self.rules.set_end(sel, 14.0), Selection(10.0, 14.0))
        self.assertEqual(self.rules.set_end(sel, 5.0), Selection(0.0, 6.0))
        self.assertEqual(self.rules.set_length(sel, 3.0), Selection(10.0, 13.0))
        self.assertEqual(self.rules.set_length(sel, 99.0), Selection(10.0, 40.0))
        self.assertEqual(self.rules.set_length(Selection(95.0, 100.0), 10.0), Selection(90.0, 100.0))

    def test_float_noise(self):
        sel = Selection(3.7, 4.7)   # 4.7 - 3.7 = 0.99999...
        self.assertEqual(self.rules.set_end(sel, 4.7), Selection(3.7, 4.7))

    def test_normalize(self):
        self.assertEqual(self.rules.normalize(Selection(99.5, 99.6)), Selection(99.0, 100.0))


class GifTests(unittest.TestCase):
    def test_legacy_settings(self):
        opts = gif.GifOptions.from_dict({"mode_idx": 1, "fps": 15, "width": 5000, "height": 80,
                                         "scale_idx": 1, "dither_idx": 2})
        self.assertEqual((opts.frame_mode, opts.fps, opts.width, opts.scale_mode, opts.dither),
                         ("dedupe", 15, 4096, "letterbox", "none"))

    def test_invalid_values(self):
        opts = gif.GifOptions.from_dict({"fps": "x", "scale_mode": "zoom", "dither": 3})
        self.assertEqual(opts, gif.GifOptions())
        self.assertEqual(gif.GifOptions.from_dict(None), gif.GifOptions())

    def test_filters(self):
        cover = gif.frame_filter(gif.GifOptions())
        self.assertIn("force_original_aspect_ratio=increase", cover)
        self.assertIn("crop=160:80", cover)
        letterbox = gif.frame_filter(gif.GifOptions(scale_mode="letterbox"))
        self.assertIn("pad=160:80", letterbox)
        dedupe = gif.frame_filter(gif.GifOptions(frame_mode="dedupe"))
        self.assertIn("mpdecimate", dedupe)

    def test_commands(self):
        palette, gif_cmd = gif.build_gif_commands("ffmpeg", "in.mp4", 1.5, 4.0, gif.GifOptions(dither="bayer"),
                                                  "pal.png", "out.gif.part")
        self.assertEqual(palette[palette.index("-ss") + 1], "1.500")
        self.assertEqual(palette[palette.index("-t") + 1], "2.500")
        self.assertIn("palettegen=stats_mode=full", palette[palette.index("-vf") + 1])
        self.assertIn("paletteuse=dither=bayer", gif_cmd[gif_cmd.index("-lavfi") + 1])
        self.assertEqual(gif_cmd[gif_cmd.index("-f") + 1], "gif")
        with self.assertRaises(ValueError):
            gif.build_gif_commands("ffmpeg", "in.mp4", 3.0, 3.0, gif.GifOptions(), "p", "o")

    def test_helpers(self):
        self.assertEqual(gif.suggest_filename("C:/v/clip.mp4", 1.2, 4.7), "clip_1200_4700.gif")
        self.assertEqual(gif.estimate_frames(6.0, 12), 72)
        self.assertEqual(gif.estimate_frames(0.0, 12), 1)


def make_gif(delays: list[int], loop: int | None = 0) -> bytes:
    data = bytearray(b"GIF89a" + (2).to_bytes(2, "little") * 2 + bytes([0x80, 0, 0]) + b"\x00" * 3 + b"\xff" * 3)
    if loop is not None:
        data += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + loop.to_bytes(2, "little") + b"\x00"
    for delay in delays:
        data += b"\x21\xf9\x04\x00" + delay.to_bytes(2, "little") + b"\x00\x00"
        data += b"\x2c" + b"\x00\x00" * 2 + (2).to_bytes(2, "little") * 2 + b"\x00" + b"\x02\x02\x44\x01\x00"
    return bytes(data + b"\x3b")


class GifInfoTests(unittest.TestCase):
    def test_parse(self):
        info = gifinfo.parse_gif(make_gif([8, 9, 8]))
        self.assertEqual((info.width, info.height, info.frames, info.duration_ms, info.loop), (2, 2, 3, 250, 0))
        self.assertIsNone(gifinfo.parse_gif(make_gif([10], loop=None)).loop)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            gifinfo.parse_gif(b"PNG....")
        with self.assertRaises(ValueError):
            gifinfo.parse_gif(make_gif([8, 8])[:-12])


class ProbeTests(unittest.TestCase):
    def test_rotation_and_rate(self):
        text = json.dumps({"streams": [{"codec_name": "h264", "width": 1920, "height": 1080,
                                        "avg_frame_rate": "30000/1001",
                                        "side_data_list": [{"rotation": -90}]}],
                           "format": {"duration": "12.5"}})
        info = ffmpeg.parse_probe_json("a.mp4", text)
        self.assertEqual((info.width, info.height, info.codec), (1080, 1920, "h264"))
        self.assertAlmostEqual(info.fps, 29.97, places=2)
        self.assertAlmostEqual(info.duration, 12.5)

    def test_missing_duration(self):
        with self.assertRaises(ValueError):
            ffmpeg.parse_probe_json("a.mp4", json.dumps({"streams": [{"width": 1}], "format": {}}))
        with self.assertRaises(ValueError):
            ffmpeg.parse_probe_json("a.mp4", json.dumps({"streams": []}))


class SettingsTests(unittest.TestCase):
    def test_v2_migration(self):
        data = {"output_path": "D:/gifs/out.gif", "options": {"mode_idx": 0, "fps": 20, "width": 160,
                                                              "height": 80, "scale_idx": 2, "dither_idx": 1}}
        loaded = settings.Settings.from_dict(data)
        self.assertEqual(Path(loaded.output_dir), Path("D:/gifs"))
        self.assertEqual((loaded.options.fps, loaded.options.scale_mode, loaded.options.dither),
                         (20, "stretch", "bayer"))

    def test_round_trip_and_corrupt(self):
        folder = _tmp("settings-")
        path = folder / "settings.json"
        original = settings.Settings(theme="dark", language="ja", confirm_exit=False)
        settings.save_settings(original, path)
        loaded, error = settings.load_settings(path)
        self.assertIsNone(error)
        self.assertEqual(loaded, original)
        path.write_text("{broken", encoding="utf-8")
        loaded, error = settings.load_settings(path)
        self.assertIsNotNone(error)
        self.assertEqual(loaded, settings.Settings())


SHA = "a" * 64
TAG = "v3.1.0"
ASSET = "ApexGIFMaker_v310.zip"


def release_payload(**overrides) -> dict:
    asset = {"name": ASSET, "state": "uploaded", "size": 1234, "digest": f"sha256:{SHA}",
             "browser_download_url": f"{updater.DOWNLOAD_PREFIX}{TAG}/{ASSET}"}
    asset.update(overrides.pop("asset", {}))
    payload = {"tag_name": TAG, "name": "APEXGIFMAKER v3.1.0", "html_url": "https://example/rel",
               "body": f"### 🐛 수정\n* **슬라이더:** 고침\n\n**🔐 SHA-256** `{ASSET}`\n```\n{SHA.upper()}\n```",
               "assets": [asset], "draft": False, "prerelease": False}
    payload.update(overrides)
    return payload


class UpdaterTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(updater.parse_version("v2.5.2"), (2, 5, 2))
        self.assertIsNone(updater.parse_version("2.5"))
        self.assertTrue(updater.is_newer("v3.0.0", "2.5.2"))
        self.assertFalse(updater.is_newer("v3.0.0", "3.0.0"))
        self.assertEqual(updater.asset_name("3.0.0"), "ApexGIFMaker_v300.zip")

    def test_verified_asset(self):
        release = updater.parse_release(release_payload())
        assert release is not None
        self.assertIsNotNone(release.asset)
        assert release.asset is not None
        self.assertEqual((release.asset.sha256, release.asset.size, release.problem), (SHA, 1234, ""))
        self.assertEqual(updater.release_highlights(release.body), ["슬라이더: 고침"])

    def test_rejected_assets(self):
        cases = {
            "no_digest": {"asset": {"digest": None}},
            "digest_mismatch": {"body": f"`{ASSET}`\n{'b' * 64}"},
            "no_asset": {"asset": {"browser_download_url": "https://evil.example/x.zip"}},
        }
        for problem, overrides in cases.items():
            release = updater.parse_release(release_payload(**overrides))
            assert release is not None
            self.assertIsNone(release.asset, problem)
            self.assertEqual(release.problem, problem)

    def test_skipped_releases(self):
        self.assertIsNone(updater.parse_release(release_payload(prerelease=True)))
        self.assertIsNone(updater.parse_release(release_payload(tag_name="latest")))


def make_package(entries: dict[str, bytes]) -> Path:
    path = _tmp("pkg-") / "package.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


class SelfUpdateTests(unittest.TestCase):
    def test_paths(self):
        for name in ("/abs", "C:x", "a/../b", "..\\x"):
            self.assertTrue(self_update.escapes_destination(name), name)
        self.assertFalse(self_update.escapes_destination("ApexGIFMaker/bin/a.dll"))
        self.assertTrue(self_update.is_preserved("bin/ffmpeg.exe"))
        self.assertTrue(self_update.is_preserved(Path("bin") / "FFPROBE.EXE.new"))
        self.assertFalse(self_update.is_preserved("bin/sub/ffmpeg.exe"))
        self.assertFalse(self_update.is_preserved("bin/python314.dll"))
        self.assertTrue(self_update.allowed_download_url(f"{updater.DOWNLOAD_PREFIX}v3/x.zip", first_hop=True))
        self.assertFalse(self_update.allowed_download_url("https://evil.example/x.zip", first_hop=True))
        self.assertTrue(self_update.allowed_download_url(
            "https://release-assets.githubusercontent.com/x", first_hop=False))
        self.assertFalse(self_update.allowed_download_url("http://github.com/x", first_hop=False))

    def test_verify_and_extract(self):
        package = make_package({"ApexGIFMaker/ApexGIFMaker.exe": b"MZ", "ApexGIFMaker/bin/a.dll": b"1",
                                "ApexGIFMaker/bin/ffmpeg.exe": b"big", "ApexGIFMaker/README.txt": b"r"})
        root = self_update.verify_package(package)
        self.assertEqual(root, "ApexGIFMaker/")
        target = _tmp("extract-")
        self_update.extract_payload(package, root, target)
        extracted = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
        self.assertEqual(extracted, ["ApexGIFMaker.exe", "bin/a.dll"])   # 교체 대상만 (ffmpeg 제외)

    def test_rejects_bad_packages(self):
        for entries in ({"ApexGIFMaker.exe": b"MZ"},                                   # bin 없음
                        {"ApexGIFMaker.exe": b"MZ", "bin/a": b"", "../evil": b"x"}):
            with self.assertRaises(self_update.VerificationError):
                self_update.verify_package(make_package(entries))


class ApplyUpdateTests(unittest.TestCase):
    def make_layout(self) -> tuple[Path, Path, Path]:
        app = _tmp("app-")
        (app / "bin").mkdir()
        (app / "ApexGIFMaker.exe").write_text("old-exe")
        (app / "bin" / "a.dll").write_text("old-a")
        (app / "bin" / "ffmpeg.exe").write_text("keep")        # 같은 bin 폴더의 ffmpeg는 그대로 남아야 함
        (app / "bin" / "ffprobe.exe").write_text("keep")
        work = app / self_update.WORK_DIR_NAME
        new = work / self_update.NEW_DIR_NAME
        (new / "bin").mkdir(parents=True)
        (new / "ApexGIFMaker.exe").write_text("new-exe")
        (new / "bin" / "a.dll").write_text("new-a")
        (new / "bin" / "b.dll").write_text("new-b")
        return app, work, new

    def run_apply(self, app: Path, work: Path, new: Path, copy=None):
        launched: list[Path] = []
        options = apply_update.ApplyOptions(1234, app, work, "2.5.2")
        result = apply_update.apply_update(
            options, lambda *_: None, current_exe=new / "ApexGIFMaker.exe",
            wait=lambda _pid, _cancel: True, sleep=lambda _s: None,
            copy=copy, launch=launched.append)
        return result, launched

    def test_arguments(self):
        argv = ["--apply-update", "--pid", "12", "--app-dir", "A", "--work-dir", "W", "--from-version", "2.5.2"]
        options = apply_update.parse_arguments(argv)
        assert options is not None
        self.assertEqual(options.pid, 12)
        self.assertIsNone(apply_update.parse_arguments(argv[:-1]))
        self.assertIsNone(apply_update.parse_arguments(["--apply-update", "--pid", "0", "--app-dir", "A",
                                                        "--work-dir", "W", "--from-version", "1"]))

    def test_success(self):
        app, work, new = self.make_layout()
        result, launched = self.run_apply(app, work, new)
        assert result is not None
        self.assertTrue(result["ok"])
        self.assertEqual((app / "ApexGIFMaker.exe").read_text(), "new-exe")
        self.assertEqual((app / "bin" / "b.dll").read_text(), "new-b")
        self.assertEqual((app / "bin" / "ffmpeg.exe").read_text(), "keep")
        self.assertEqual((app / "bin" / "ffprobe.exe").read_text(), "keep")
        self.assertFalse((work / self_update.BACKUP_DIR_NAME / "bin" / "ffmpeg.exe").exists())
        self.assertEqual(launched, [app / "ApexGIFMaker.exe"])
        self.assertTrue(json.loads((work / self_update.RESULT_NAME).read_text(encoding="utf-8"))["ok"])

    def test_rollback(self):
        app, work, new = self.make_layout()
        calls = {"n": 0}

        def failing_copy(src: Path, dst: Path):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("disk full")
            dst.write_bytes(src.read_bytes())

        result, launched = self.run_apply(app, work, new, copy=failing_copy)
        assert result is not None
        self.assertEqual(result["stage"], "rolled_back")
        self.assertEqual((app / "ApexGIFMaker.exe").read_text(), "old-exe")
        self.assertEqual((app / "bin" / "a.dll").read_text(), "old-a")
        self.assertFalse((app / "bin" / "b.dll").exists())
        self.assertEqual((app / "bin" / "ffmpeg.exe").read_text(), "keep")
        self.assertEqual(launched, [app / "ApexGIFMaker.exe"])


class FfmpegSetupTests(unittest.TestCase):
    def test_checksum_formats(self):
        self.assertEqual(ffmpeg_setup.parse_checksum(SHA.upper() + "\n", "f.zip"), SHA)
        listing = f"{'b' * 64}  other.zip\n{SHA}  *f.zip\n"
        self.assertEqual(ffmpeg_setup.parse_checksum(listing, "f.zip"), SHA)
        self.assertEqual(ffmpeg_setup.parse_checksum("not a hash", "f.zip"), "")

    def test_extract_binaries(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ffmpeg-9/bin/ffmpeg.exe", b"ff")
            archive.writestr("ffmpeg-9/bin/ffprobe.exe", b"fp")
            archive.writestr("ffmpeg-9/doc/readme.txt", b"doc")
        path = _tmp("ffzip-") / "f.zip"
        path.write_bytes(buffer.getvalue())
        target = _tmp("ffbin-")
        (target / "python314.dll").write_text("app")          # bin에는 앱 파일도 함께 있음
        ffmpeg_setup.extract_binaries(path, target)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["ffmpeg.exe", "ffprobe.exe", "python314.dll"])

        # 새 버전은 .new로 받아 두었다가 적용합니다. 앱 파일은 그대로입니다.
        ffmpeg_setup.extract_binaries(path, target, ffmpeg_setup.STAGED_SUFFIX)
        (target / "ffmpeg.exe").write_text("old")
        self.assertTrue(ffmpeg_setup.has_staged(target))
        self.assertTrue(ffmpeg_setup.apply_staged(target))
        self.assertEqual((target / "ffmpeg.exe").read_bytes(), b"ff")
        self.assertFalse(ffmpeg_setup.has_staged(target))
        self.assertFalse(ffmpeg_setup.apply_staged(target))
        self.assertEqual((target / "python314.dll").read_text(), "app")

    def test_migrate_legacy_dir(self):
        app = _tmp("legacy-")
        legacy, tools = app / "ffmpeg-bin", app / "bin"
        legacy.mkdir()
        tools.mkdir()
        (tools / "python314.dll").write_text("app")
        for name in ffmpeg_setup.tool_names():
            (legacy / name).write_text(name)
        with mock.patch.object(ffmpeg_setup.config, "legacy_ffmpeg_dir", lambda: legacy), \
                mock.patch.object(ffmpeg_setup.config, "tools_dir", lambda: tools):
            self.assertTrue(ffmpeg_setup.migrate_legacy_dir())
            self.assertFalse(ffmpeg_setup.migrate_legacy_dir())         # 두 번째는 할 일이 없음
        self.assertFalse(legacy.exists())                                # 비어서 지워짐
        self.assertEqual(sorted(p.name for p in tools.iterdir()), ["ffmpeg.exe", "ffprobe.exe", "python314.dll"])

    def test_versions(self):
        self.assertEqual(ffmpeg_setup.version_tuple("9.0.2"), (9, 0, 2))
        self.assertIsNone(ffmpeg_setup.version_tuple("N-12345-gabc"))
        status = ffmpeg_setup.ToolStatus
        self.assertTrue(status("9.0.2", "9.1", True).newer)
        self.assertFalse(status("9.0.2", "9.0.2", True).newer)
        self.assertTrue(status("", "9.0.2", False).newer)            # 버전을 모르면 새로 받음
        self.assertTrue(status("N-12345-gabc", "9.0.2", True).newer)


class I18nTests(unittest.TestCase):
    def test_detect(self):
        cases = {"ko-KR": "ko", "ja_JP": "ja", "es-419": "es", "en-US": "en", "fr-FR": "en", "": "en",
                 "zh-TW": "zh-Hant", "zh-Hant-HK": "zh-Hant", "zh_HK": "zh-Hant", "zh-Hans-HK": "zh-Hans",
                 "zh_CN": "zh-Hans", "zh-SG": "zh-Hans"}
        for name, expected in cases.items():
            self.assertEqual(i18n.detect_language(name), expected, name)

    def test_lookup(self):
        previous = i18n.language()
        try:
            i18n.set_language("en")
            self.assertEqual(i18n.tr("dlg.ok"), "OK")
            self.assertEqual(i18n.tr("msg.file_missing", path="x"), "File not found.\nx")
            self.assertEqual(i18n.tr("no.such.key"), "no.such.key")
        finally:
            i18n.set_language(previous)

    def test_tables_complete(self):
        self.assertEqual(i18n.validate(), [])


if __name__ == "__main__":
    unittest.main()
