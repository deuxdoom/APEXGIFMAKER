# ja.py — 日本語
STRINGS: dict[str, str] = {
    # --- 共通 ---
    "dlg.ok": "OK",
    "dlg.cancel": "キャンセル",
    "dlg.yes": "はい",
    "dlg.no": "いいえ",
    "dlg.close": "閉じる",
    "dlg.error": "エラー",
    "dlg.warning": "警告",
    "dlg.info": "お知らせ",
    "unit.seconds": "{value}秒",
    "unit.frames": "{value}フレーム",

    # --- 起動 ---
    "app.already_running.title": "実行中",
    "app.already_running.text": "APEX GIF MAKER はすでに実行中です。\n既存のウィンドウを前面に表示しました。",

    # --- 上部バー ---
    "top.open": "動画を開く",
    "top.open.tip": "動画ファイルを開きます (Ctrl+O)。ウィンドウにファイルをドロップしても開けます。",
    "top.no_video": "動画を開くか、ウィンドウにドロップしてください",
    "top.play": "範囲を再生",
    "top.play.tip": "選択した範囲を既定の動画プレーヤーで再生します (Ctrl+P)。",
    "top.menu.tip": "設定",
    "top.open_dialog": "動画を開く",
    "top.video_filter": "動画 ({patterns});;すべてのファイル (*.*)",

    # --- 設定メニュー ---
    "menu.theme": "テーマ",
    "menu.theme.system": "システム設定に合わせる",
    "menu.theme.light": "ライト",
    "menu.theme.dark": "ダーク",
    "menu.language": "言語",
    "menu.language.auto": "自動（システム）",
    "menu.confirm_exit": "終了時に確認する",
    "menu.check_update": "アップデートを確認",
    "menu.about": "バージョン情報",
    "lang.restart": "言語の変更はアプリを再起動すると反映されます。",

    # --- プレビュー ---
    "preview.start": "開始",
    "preview.end": "終了",
    "preview.empty.title": "ここに動画をドロップ",
    "preview.empty.body": "MP4、MOV、MKV、WEBM、AVI などに対応しています。",
    "preview.crop_hint": "点線の内側が GIF に収まる範囲です。",
    "preview.error": "フレームを読み込めませんでした",

    # --- タイムライン ---
    "timeline.title": "範囲選択",
    "timeline.hint": "ハンドルで開始・終了を調整 · 中央をドラッグで移動 · ホイールで拡大/縮小 · "
                     "Shift+ホイールでスクロール · ダブルクリックで選択範囲を拡大",
    "timeline.placeholder": "動画を開くとタイムラインが表示されます",
    "timeline.zoom_in": "拡大 (+)",
    "timeline.zoom_out": "縮小 (−)",
    "timeline.zoom_fit": "全体を表示 (0)",
    "timeline.zoom_sel": "選択範囲を拡大",
    "timeline.frames": "約 {frames} フレーム",
    "timeline.frames_max": "最大 {frames} フレーム",
    "timeline.over_reco": "推奨の長さ（{sec}秒）を超えています",
    "timeline.limits": "範囲の長さは {min}～{max} 秒の間で設定できます。",
    "field.start": "開始",
    "field.length": "長さ（秒）",
    "field.end": "終了",
    "field.back": "−0.1秒（Shift: −1秒）",
    "field.forward": "+0.1秒（Shift: +1秒）",
    "field.invalid": "時間の形式が正しくありません。（例: 01:23.500 または 83.5）",

    # --- GIF オプション ---
    "options.title": "GIF オプション",
    "options.size": "サイズ",
    "options.size.reset": "APEX の既定値（160×80）に戻す",
    "options.fps": "FPS",
    "options.fps.tip": "1秒あたりのフレーム数です。高いほど滑らかですが、ファイルが大きくなります。",
    "options.scale": "スケール",
    "options.scale.cover": "全面に表示（トリミング）",
    "options.scale.cover.tip": "縦横比を保ったまま画面いっぱいに表示し、はみ出た部分を切り取ります。",
    "options.scale.letterbox": "レターボックス（全体を表示）",
    "options.scale.letterbox.tip": "フレーム全体が収まるように縮小し、余白を黒で埋めます。",
    "options.scale.stretch": "引き伸ばし",
    "options.scale.stretch.tip": "縦横比を無視して指定サイズに引き伸ばします。",
    "options.dither": "ディザリング",
    "options.dither.floyd_steinberg": "Floyd–Steinberg",
    "options.dither.floyd_steinberg.tip": "滑らかで自然なディザリング（推奨）",
    "options.dither.bayer": "Bayer",
    "options.dither.bayer.tip": "規則的な格子パターン（くっきり）",
    "options.dither.none": "なし",
    "options.dither.none.tip": "ディザリングなし（くっきりしますが、色の段差が出ることがあります）",
    "options.dither.help": "ディザリングとは？",
    "options.dither.help_text": (
        "GIF の各フレームで使える色は最大 256 色です。ディザリングは小さな点のパターンを混ぜて、"
        "色の段差（バンディング）を目立ちにくくする手法です。\n\n"
        "• Floyd–Steinberg: 滑らかで自然（推奨）\n"
        "• Bayer: 規則的な格子パターンで、くっきり\n"
        "• なし: くっきりしますが、色の段差が出ることがあります"),
    "options.frames": "フレーム",
    "options.frames.even": "均等（再生時間を維持）",
    "options.frames.even.tip": "範囲を一定の間隔で取り込みます。動きのない部分は自動的に小さく保存されます。",
    "options.frames.dedupe": "重複除去（静止部分をスキップ）",
    "options.frames.dedupe.tip": "連続する同じフレームを取り除きます。静止部分が飛ばされるため、再生時間が短くなることがあります。",

    # --- 出力 ---
    "output.title": "出力",
    "output.folder": "保存先",
    "output.folder.placeholder": "アプリのフォルダー",
    "output.folder.choose": "保存先を選択",
    "output.folder.open": "保存先を開く",
    "output.filename": "ファイル名",
    "output.filename.auto": "自動の名前に戻す",
    "output.generate": "GIF を作成",
    "output.generate.tip": "選択した範囲から GIF を作成します (Ctrl+Enter)。",
    "output.cancel": "キャンセル",
    "output.stage.palette": "色を分析中…",
    "output.stage.encode": "GIF に変換中… {percent}%",

    # --- ログ ---
    "log.title": "ログ",
    "log.clear": "ログを消去",
    "log.ffmpeg_checking": "ffmpeg/ffprobe を確認中…",
    "log.ffmpeg_ready": "ffmpeg: {ffmpeg} | ffprobe: {ffprobe}",
    "log.ffmpeg_progress": "ffmpeg をダウンロード中 {percent}%",
    "log.video_loaded": "読み込み: {name} ({info})",
    "log.settings_error": "設定ファイルを読み込めなかったため、既定値を使います: {error}",
    "log.settings_save_error": "設定を保存できませんでした: {error}",
    "log.legacy_cache": "旧バージョンのキャッシュを削除しました: {items}",
    "log.update_available": "新しいバージョンがあります: {tag}",
    "log.update_latest": "最新バージョンを使用しています。(v{version})",
    "log.update_failed": "アップデートの確認に失敗しました: {error}",
    "log.gif_saved": "GIF を保存しました: {path} ({details})",
    "log.gif_failed": "GIF の作成に失敗しました: {error}",
    "log.gif_cancelled": "GIF の作成をキャンセルしました。",
    "log.frame_failed": "フレームの抽出に失敗しました ({time}): {error}",
    "log.clip_failed": "プレビュー用クリップを作成できませんでした: {error}",

    # --- ステータス ---
    "status.ffmpeg.checking": "ffmpeg を確認中…",
    "status.ffmpeg.downloading": "ffmpeg をダウンロード中… {percent}%",
    "status.ffmpeg.ready": "ffmpeg {version}",
    "status.ffmpeg.missing": "ffmpeg なし",
    "status.loading_video": "動画を読み込み中…",
    "status.exporting_clip": "プレビュー用クリップを準備中…",
    "status.generating": "GIF を作成中…",
    "status.done": "GIF を保存しました: {name}",
    "status.cancelled": "GIF の作成をキャンセルしました。",

    # --- メッセージ ---
    "msg.file_missing": "ファイルが見つかりません。\n{path}",
    "msg.ffmpeg_not_ready": "ffmpeg を準備しています。しばらくしてからもう一度お試しください。",
    "msg.ffmpeg_failed": "ffmpeg を準備できませんでした。\nインターネット接続を確認するか、ffmpeg.exe と ffprobe.exe を "
                         "bin フォルダーに入れてください。\n\n{path}",
    "msg.probe_failed": "動画を読み込めませんでした。\n{error}",
    "msg.load_video_first": "先に動画を開いてください。",
    "msg.overwrite.title": "上書き",
    "msg.overwrite": "同じ名前のファイルがすでにあります。\n{name}\n\n上書きしますか？",
    "msg.invalid_filename": "ファイル名に使えない文字が含まれています。\n{chars}",
    "msg.folder_unwritable": "保存先フォルダーに書き込めません。\n{path}",
    "msg.gif_failed": "GIF を作成できませんでした。\n詳しくはログを確認してください。\n\n{error}",
    "msg.clip_failed": "プレビュー用クリップを作成できませんでした。\n{error}",
    "msg.quit.title": "終了",
    "msg.quit": "APEX GIF MAKER を終了しますか？",
    "msg.quit.busy": "GIF を作成中です。作業をキャンセルして終了しますか？",
    "msg.dont_ask": "今後は確認しない",
    "msg.update.title": "アップデート",
    "msg.update_latest": "最新バージョンを使用しています。(v{version})",
    "msg.update_failed": "アップデートを確認できませんでした。\n{error}",

    # --- 結果ウィンドウ ---
    "result.title": "GIF を作成しました",
    "result.file": "ファイル",
    "result.size": "サイズ",
    "result.dimensions": "解像度",
    "result.frames": "フレーム数",
    "result.duration": "再生時間",
    "result.elapsed": "所要時間",
    "result.open_folder": "フォルダーで表示",
    "result.open_file": "ファイルを開く",

    # --- バージョン情報 ---
    "about.title": "APEX GIF MAKER について",
    "about.tagline": "Flydigi APEX シリーズのコントローラー画面向け GIF メーカー",
    "about.description": "動画から好きな範囲を選び、コントローラーの画面に合わせた高品質な GIF に変換します。"
                         "APEX 4・5・6 など、同じ画面規格のモデルであればどれでも使えます。",
    "about.version": "バージョン {version}",
    "about.ffmpeg": "FFmpeg {version}",
    "about.ffmpeg_missing": "FFmpeg が見つかりません",
    "about.changelog": "変更履歴",
    "about.sponsor": "スポンサー",
    "about.issues": "問題を報告",
    "about.credits": "クレジット",
    "about.credits_text": "動画処理: FFmpeg (LGPL/GPL)\n"
                          "UI: Qt for Python / PySide6 (LGPL)\n"
                          "UI アイコン: Fluent UI System Icons © Microsoft (MIT)\n"
                          "フォント: Pretendard、Pretendard JP、JetBrains Mono (SIL OFL 1.1)",

    # --- ウィンドウボタン ---
    "win.minimize": "最小化",
    "win.maximize": "最大化",
    "win.restore": "元のサイズに戻す",
    "win.close": "閉じる",

    # --- アップデート ---
    "update.heading": "新しいバージョン v{version} が公開されました",
    "update.current": "現在のバージョン v{version}",
    "update.verified": "SHA-256 検証済み",
    "update.now": "今すぐアップデート",
    "update.later": "後で",
    "update.notes": "リリースノート",
    "update.open_page": "ダウンロードページを開く",
    "update.retry": "再試行",
    "update.downloading": "ダウンロード中… {done} / {total}",
    "update.extracting": "展開中…",
    "update.ready": "準備ができました。再起動してアップデートを適用します…",
    "update.failed": "アップデートを準備できませんでした。\n{error}",
    "update.source_mode": "自動アップデートは配布版でのみ利用できます。ダウンロードページから新しいバージョンを入手してください。",
    "update.no_verified_asset": "このリリースには SHA-256 で検証できるアップデートファイルがありません。"
                                "ダウンロードページから入手してください。",
    "update.unwritable": "アプリのフォルダーに書き込めないため、自動でインストールできません。"
                         "ダウンロードページから入手してください。",
    "update.launch_failed": "アップデート適用ウィンドウを起動できませんでした。",
    "update.rate_limited": "GitHub のリクエスト上限に達しました。しばらくしてからもう一度お試しください。",
    "msg.update_applied": "v{version} にアップデートしました。",
    "msg.update_rolled_back": "アップデートに失敗したため、以前のバージョンのままにしました。\n{error}",
    "log.update_applied": "アップデート完了: v{from_version} → v{to_version}",

    # --- アップデート適用 (--apply-update) ---
    "apply.title": "アップデートを適用中",
    "apply.heading": "v{from_version} → v{to_version}",
    "apply.step.wait": "以前のバージョンの終了を待機中",
    "apply.step.backup": "現在のファイルをバックアップ",
    "apply.step.install": "新しいファイルをインストール",
    "apply.step.launch": "再起動",
    "apply.done": "アップデートが完了しました。",
    "apply.rolled_back": "アップデートに失敗したため、以前のバージョンに戻しました。\n{error}",
    "apply.timeout": "以前のバージョンが終了しなかったため、アップデートを開始しませんでした。アプリを閉じてからもう一度お試しください。",
    "apply.bad_arguments": "アップデートのパスが正しくありません。",
    "apply.failed": "アップデートに失敗しました。以前のファイルのバックアップはここに残っています。\n{path}\n{error}",

    # --- ffmpeg の自動準備 ---
    "ffmpeg.unsupported_os": "この OS では ffmpeg の自動セットアップに対応していません。ffmpeg をインストールして PATH に追加してください。",
    "ffmpeg.downloading": "ffmpeg をダウンロード: {url}",
    "ffmpeg.no_checksum": "SHA-256 チェックサムを取得できなかったため、ダウンロードを中止しました。",
    "ffmpeg.verify_ok": "SHA-256 チェックサムを確認しました",
    "ffmpeg.verify_fail": "SHA-256 チェックサムが一致しないため、ダウンロードしたファイルを破棄します。",
    "ffmpeg.extracting": "展開中…",
    "ffmpeg.download_failed": "ダウンロードに失敗しました: {error}",
    "ffmpeg.installed": "ffmpeg の準備ができました: {path}",
    "ffmpeg.setup_failed": "ffmpeg を準備できませんでした。",

    # --- ツール (ffmpeg) の更新 ---
    "menu.update_tools": "ツールを更新 (ffmpeg)",
    "menu.auto_update_tools": "ツールを自動で更新",
    "tools.title": "ツールの更新",
    "tools.checking": "ffmpeg の新しいバージョンを確認中…",
    "tools.latest": "最新の ffmpeg を使用しています。({version})",
    "tools.updated": "ffmpeg を {new} に更新しました。(以前: {old})",
    "tools.staged": "ffmpeg {new} をダウンロードしました。次回アプリを起動したときに適用されます。",
    "tools.failed": "ffmpeg を更新できませんでした。\n{error}",
    "tools.unmanaged": "システムにインストールされた ffmpeg を使用しているため、自動では更新しません。"
                       "設定メニューの「ツールを更新」を選ぶと、アプリ専用の ffmpeg を使用します。",
    "tools.applied_staged": "ダウンロード済みの ffmpeg の新しいバージョンを適用しました。",
    "status.ffmpeg.updating": "ffmpeg を更新中… {percent}%",
    "log.legacy_ffmpeg": "以前の ffmpeg-bin フォルダーの ffmpeg を bin フォルダーに移動しました。",
}
