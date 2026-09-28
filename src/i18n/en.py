# en.py — English (reference language)
STRINGS: dict[str, str] = {
    # --- common ---
    "dlg.ok": "OK",
    "dlg.cancel": "Cancel",
    "dlg.yes": "Yes",
    "dlg.no": "No",
    "dlg.close": "Close",
    "dlg.error": "Error",
    "dlg.warning": "Warning",
    "dlg.info": "Notice",
    "unit.seconds": "{value} s",
    "unit.frames": "{value} frames",

    # --- startup ---
    "app.already_running.title": "Already Running",
    "app.already_running.text": "APEX GIF MAKER is already running.\nBrought the existing window to the front.",

    # --- top bar ---
    "top.open": "Open Video",
    "top.open.tip": "Open a video file (Ctrl+O). You can also drop a file onto the window.",
    "top.no_video": "Open a video or drop one onto the window",
    "top.play": "Play Range",
    "top.play.tip": "Play the selected range in your default video player (Ctrl+P).",
    "top.menu.tip": "Settings",
    "top.open_dialog": "Open Video",
    "top.video_filter": "Videos ({patterns});;All files (*.*)",

    # --- settings menu ---
    "menu.theme": "Theme",
    "menu.theme.system": "Follow System",
    "menu.theme.light": "Light",
    "menu.theme.dark": "Dark",
    "menu.language": "Language",
    "menu.language.auto": "Automatic (System)",
    "menu.confirm_exit": "Confirm on Exit",
    "menu.check_update": "Check for Updates",
    "menu.about": "About",
    "lang.restart": "The language change takes effect after restarting the app.",

    # --- preview ---
    "preview.start": "Start",
    "preview.end": "End",
    "preview.empty.title": "Drop a video here",
    "preview.empty.body": "MP4, MOV, MKV, WEBM, AVI and more are supported.",
    "preview.crop_hint": "The dashed box shows the area kept in the GIF.",
    "preview.error": "Couldn't load the frame",

    # --- timeline ---
    "timeline.title": "Range",
    "timeline.hint": "Drag handles to trim · drag the middle to move · wheel to zoom · "
                     "Shift+wheel to scroll · double-click to zoom to the selection",
    "timeline.placeholder": "The timeline appears after you open a video",
    "timeline.zoom_in": "Zoom In (+)",
    "timeline.zoom_out": "Zoom Out (−)",
    "timeline.zoom_fit": "Fit (0)",
    "timeline.zoom_sel": "Zoom to Selection",
    "timeline.frames": "≈ {frames} frames",
    "timeline.frames_max": "up to {frames} frames",
    "timeline.over_reco": "Over {sec} s recommended",
    "timeline.limits": "The range can be {min}–{max} seconds long.",
    "field.start": "Start",
    "field.length": "Length (s)",
    "field.end": "End",
    "field.back": "−0.1 s (Shift: −1 s)",
    "field.forward": "+0.1 s (Shift: +1 s)",
    "field.invalid": "Invalid time. (e.g. 01:23.500 or 83.5)",

    # --- GIF options ---
    "options.title": "GIF Options",
    "options.size": "Size",
    "options.size.reset": "Reset to the APEX default (160×80)",
    "options.fps": "FPS",
    "options.fps.tip": "Frames per second. Higher is smoother but makes a bigger file.",
    "options.scale": "Scale",
    "options.scale.cover": "Cover (crop)",
    "options.scale.cover.tip": "Keeps the aspect ratio, fills the screen and crops the overflow.",
    "options.scale.letterbox": "Letterbox (fit)",
    "options.scale.letterbox.tip": "Shrinks the whole frame to fit and fills the rest with black bars.",
    "options.scale.stretch": "Stretch",
    "options.scale.stretch.tip": "Ignores the aspect ratio and stretches to the size.",
    "options.dither": "Dithering",
    "options.dither.floyd_steinberg": "Floyd–Steinberg",
    "options.dither.floyd_steinberg.tip": "Smooth, natural dithering (recommended)",
    "options.dither.bayer": "Bayer",
    "options.dither.bayer.tip": "Ordered grid pattern (crisp)",
    "options.dither.none": "None",
    "options.dither.none.tip": "No dithering (sharp, may band)",
    "options.dither.help": "What is dithering?",
    "options.dither.help_text": (
        "GIF frames can use at most 256 colors. Dithering mixes in small dot patterns so that color "
        "banding is less visible.\n\n"
        "• Floyd–Steinberg: smooth and natural (recommended)\n"
        "• Bayer: ordered grid pattern, crisp\n"
        "• None: sharp, but banding may appear"),
    "options.frames": "Frames",
    "options.frames.even": "Even (keep timing)",
    "options.frames.even.tip": "Samples the range at even intervals. Still parts are stored compactly.",
    "options.frames.dedupe": "Dedupe (skip still parts)",
    "options.frames.dedupe.tip": "Drops repeated frames. Still parts are skipped, so playback may get shorter.",

    # --- output ---
    "output.title": "Output",
    "output.folder": "Folder",
    "output.folder.placeholder": "App folder",
    "output.folder.choose": "Choose Folder",
    "output.folder.open": "Open Folder",
    "output.filename": "File Name",
    "output.filename.auto": "Use the automatic name",
    "output.generate": "Generate GIF",
    "output.generate.tip": "Create a GIF from the range (Ctrl+Enter).",
    "output.cancel": "Cancel",
    "output.stage.palette": "Analyzing colors…",
    "output.stage.encode": "Encoding GIF… {percent}%",

    # --- log ---
    "log.title": "Log",
    "log.clear": "Clear Log",
    "log.ffmpeg_checking": "Checking ffmpeg/ffprobe…",
    "log.ffmpeg_ready": "ffmpeg: {ffmpeg} | ffprobe: {ffprobe}",
    "log.ffmpeg_progress": "Downloading ffmpeg {percent}%",
    "log.video_loaded": "Loaded: {name} ({info})",
    "log.settings_error": "Couldn't read the settings file, using defaults: {error}",
    "log.settings_save_error": "Couldn't save settings: {error}",
    "log.legacy_cache": "Removed the old cache: {items}",
    "log.update_available": "New version available: {tag}",
    "log.update_latest": "You're up to date. (v{version})",
    "log.update_failed": "Update check failed: {error}",
    "log.gif_saved": "GIF saved: {path} ({details})",
    "log.gif_failed": "GIF generation failed: {error}",
    "log.gif_cancelled": "GIF generation cancelled.",
    "log.frame_failed": "Frame grab failed ({time}): {error}",
    "log.clip_failed": "Couldn't create the preview clip: {error}",

    # --- status bar ---
    "status.ffmpeg.checking": "Checking ffmpeg…",
    "status.ffmpeg.downloading": "Downloading ffmpeg… {percent}%",
    "status.ffmpeg.ready": "ffmpeg {version}",
    "status.ffmpeg.missing": "ffmpeg missing",
    "status.loading_video": "Reading the video…",
    "status.exporting_clip": "Preparing the preview clip…",
    "status.generating": "Generating GIF…",
    "status.done": "GIF saved: {name}",
    "status.cancelled": "GIF generation cancelled.",

    # --- messages ---
    "msg.file_missing": "File not found.\n{path}",
    "msg.ffmpeg_not_ready": "ffmpeg is being prepared. Please try again in a moment.",
    "msg.ffmpeg_failed": "Couldn't prepare ffmpeg.\nCheck your internet connection, or put ffmpeg.exe and "
                         "ffprobe.exe into the bin folder yourself.\n\n{path}",
    "msg.probe_failed": "Couldn't read the video.\n{error}",
    "msg.load_video_first": "Open a video first.",
    "msg.overwrite.title": "Overwrite",
    "msg.overwrite": "A file with the same name already exists.\n{name}\n\nDo you want to replace it?",
    "msg.invalid_filename": "The file name contains characters that aren't allowed.\n{chars}",
    "msg.folder_unwritable": "Can't write to the output folder.\n{path}",
    "msg.gif_failed": "Couldn't create the GIF.\nSee the log for details.\n\n{error}",
    "msg.clip_failed": "Couldn't create the preview clip.\n{error}",
    "msg.quit.title": "Quit",
    "msg.quit": "Quit APEX GIF MAKER?",
    "msg.quit.busy": "A GIF is being generated. Cancel it and quit?",
    "msg.dont_ask": "Don't ask again",
    "msg.update.title": "Update",
    "msg.update_latest": "You're using the latest version. (v{version})",
    "msg.update_failed": "Couldn't check for updates.\n{error}",

    # --- result dialog ---
    "result.title": "GIF Created",
    "result.file": "File",
    "result.size": "Size",
    "result.dimensions": "Dimensions",
    "result.frames": "Frames",
    "result.duration": "Duration",
    "result.elapsed": "Time Taken",
    "result.open_folder": "Show in Folder",
    "result.open_file": "Open File",

    # --- about dialog ---
    "about.title": "About APEX GIF MAKER",
    "about.tagline": "GIF maker for Flydigi APEX series controller screens",
    "about.description": "Pick a range from any video and turn it into a high-quality GIF sized for the "
                         "controller screen. Works with APEX 4, 5, 6 and any other model that shares the "
                         "same screen format.",
    "about.version": "Version {version}",
    "about.ffmpeg": "FFmpeg {version}",
    "about.ffmpeg_missing": "FFmpeg not found",
    "about.changelog": "Changelog",
    "about.sponsor": "Sponsor",
    "about.issues": "Report an Issue",
    "about.credits": "Credits",
    "about.credits_text": "Video processing: FFmpeg (LGPL/GPL)\n"
                          "UI: Qt for Python / PySide6 (LGPL)\n"
                          "UI icons: Fluent UI System Icons © Microsoft (MIT)\n"
                          "Fonts: Pretendard, Pretendard JP, JetBrains Mono (SIL OFL 1.1)",

    # --- window buttons ---
    "win.minimize": "Minimize",
    "win.maximize": "Maximize",
    "win.restore": "Restore Down",
    "win.close": "Close",

    # --- update dialog ---
    "update.heading": "Version {version} is available",
    "update.current": "Current version v{version}",
    "update.verified": "SHA-256 verified",
    "update.now": "Update Now",
    "update.later": "Later",
    "update.notes": "Release Notes",
    "update.open_page": "Open Download Page",
    "update.retry": "Try Again",
    "update.downloading": "Downloading… {done} / {total}",
    "update.extracting": "Extracting…",
    "update.ready": "Ready. Restarting to apply the update…",
    "update.failed": "Couldn't prepare the update.\n{error}",
    "update.source_mode": "Automatic update is only available in the released app. Please download the new version from the release page.",
    "update.no_verified_asset": "This release has no update file that can be verified with SHA-256. Please download it from the release page.",
    "update.unwritable": "The app folder isn't writable, so the update can't be installed automatically. Please download it from the release page.",
    "update.launch_failed": "Couldn't start the update window.",
    "update.rate_limited": "GitHub's request limit was reached. Please try again later.",
    "msg.update_applied": "Updated to v{version}.",
    "msg.update_rolled_back": "The update failed, so the previous version was kept.\n{error}",
    "log.update_applied": "Updated: v{from_version} → v{to_version}",

    # --- apply window (--apply-update) ---
    "apply.title": "Applying Update",
    "apply.heading": "v{from_version} → v{to_version}",
    "apply.step.wait": "Waiting for the app to close",
    "apply.step.backup": "Backing up the current files",
    "apply.step.install": "Installing the new files",
    "apply.step.launch": "Restarting",
    "apply.done": "Update complete.",
    "apply.rolled_back": "The update failed and the previous version was restored.\n{error}",
    "apply.timeout": "The app didn't close, so the update wasn't started. Close it and try again.",
    "apply.bad_arguments": "The update paths are invalid.",
    "apply.failed": "The update failed. A backup of the previous files is kept here:\n{path}\n{error}",

    # --- automatic ffmpeg setup (core.ffmpeg_setup) ---
    "ffmpeg.unsupported_os": "Automatic ffmpeg setup isn't supported on this OS. "
                             "Please install ffmpeg and add it to PATH.",
    "ffmpeg.downloading": "Downloading ffmpeg: {url}",
    "ffmpeg.no_checksum": "Couldn't get the SHA-256 checksum, so the download was skipped.",
    "ffmpeg.verify_ok": "SHA256 checksum verified",
    "ffmpeg.verify_fail": "SHA256 checksum mismatch; discarding the download.",
    "ffmpeg.extracting": "Extracting…",
    "ffmpeg.download_failed": "Download failed: {error}",
    "ffmpeg.installed": "ffmpeg is ready: {path}",
    "ffmpeg.setup_failed": "Couldn't prepare ffmpeg.",

    # --- tool (ffmpeg) updates ---
    "menu.update_tools": "Update Tools (ffmpeg)",
    "menu.auto_update_tools": "Update Tools Automatically",
    "tools.title": "Update Tools",
    "tools.checking": "Checking for a new ffmpeg…",
    "tools.latest": "You're using the latest ffmpeg. ({version})",
    "tools.updated": "Updated ffmpeg to {new}. (previous: {old})",
    "tools.staged": "Downloaded ffmpeg {new}. It will be applied the next time you start the app.",
    "tools.failed": "Couldn't update ffmpeg.\n{error}",
    "tools.unmanaged": "A system-wide ffmpeg is in use, so it isn't updated automatically. "
                       "Choose 'Update Tools' in the settings menu to use the app's own copy.",
    "tools.applied_staged": "Applied the ffmpeg update downloaded earlier.",
    "status.ffmpeg.updating": "Updating ffmpeg… {percent}%",
    "log.legacy_ffmpeg": "Moved ffmpeg from the old ffmpeg-bin folder into bin.",
}
