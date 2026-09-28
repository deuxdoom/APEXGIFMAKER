# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정. 보통은 `python tools/build.py`로 실행합니다. (검사 → 빌드 → 스모크 테스트 → ZIP)
# 참고: TVerDownloader의 TVerDownloader.spec
import importlib.util
import os
import shutil

import PySide6
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

APP_NAME = "ApexGIFMaker"
APP_PUBLISHER = "deuxdoom"
APP_DESCRIPTION = "APEX GIF MAKER"


def read_app_version():
    """버전은 versioninfo.py 한 줄에서만 읽습니다. 여기에 숫자를 적어 두면 둘이 조용히 어긋납니다."""
    spec = importlib.util.spec_from_file_location("_apex_versioninfo", os.path.join(SPECPATH, "versioninfo.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.APP_VERSION


def build_version_resource(version):
    """Windows 파일 속성의 버전 정보. CompanyName이 작업 관리자 등에서 '게시자'로 보입니다."""
    numbers = tuple(int(part) for part in version.split(".")) + (0,)
    strings = [
        StringStruct("CompanyName", APP_PUBLISHER),
        StringStruct("FileDescription", APP_DESCRIPTION),
        StringStruct("FileVersion", version),
        StringStruct("InternalName", APP_NAME),
        StringStruct("LegalCopyright", "Copyright (c) " + APP_PUBLISHER + " · MIT License"),
        StringStruct("OriginalFilename", APP_NAME + ".exe"),
        StringStruct("ProductName", APP_DESCRIPTION),
        StringStruct("ProductVersion", version),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[StringFileInfo([StringTable("041204B0", strings)]),
              VarFileInfo([VarStruct("Translation", [0x0412, 1200])])],
    )


APP_VERSION = read_app_version()
VERSION_RESOURCE = build_version_resource(APP_VERSION)

# Qt 기본 위젯(입력칸 오른쪽 클릭 메뉴 등) 번역. 앱이 지원하는 언어만 싣습니다. (src/ui/app.py의 QT_TRANSLATIONS)
QT_TRANSLATIONS_DIR = os.path.join(os.path.dirname(PySide6.__file__), "translations")
TRANSLATION_LANGS = ["ko", "ja", "es", "zh_CN", "zh_TW"]
TRANSLATION_DATAS = [
    (os.path.join(QT_TRANSLATIONS_DIR, f"qtbase_{lang}.qm"), "translations")
    for lang in TRANSLATION_LANGS
    if os.path.isfile(os.path.join(QT_TRANSLATIONS_DIR, f"qtbase_{lang}.qm"))
]

# 쓰지 않는 Qt 모듈. QtSvg(아이콘·로고)와 QtNetwork(단일 실행)는 쓰므로 빼면 안 됩니다.
EXCLUDED_QT = [f"PySide6.{name}" for name in (
    "Qt3DAnimation", "Qt3DCore", "Qt3DExtras", "Qt3DInput", "Qt3DLogic", "Qt3DRender", "QtAxContainer",
    "QtBluetooth", "QtCharts", "QtConcurrent", "QtDataVisualization", "QtDBus", "QtDesigner", "QtGraphs",
    "QtHelp", "QtHttpServer", "QtLocation", "QtMultimedia", "QtMultimediaWidgets", "QtNfc", "QtOpenGL",
    "QtOpenGLWidgets", "QtPdf", "QtPdfWidgets", "QtPositioning", "QtPrintSupport", "QtQml", "QtQuick",
    "QtQuick3D", "QtQuickControls2", "QtQuickWidgets", "QtRemoteObjects", "QtScxml", "QtSensors",
    "QtSerialBus", "QtSerialPort", "QtSpatialAudio", "QtSql", "QtStateMachine", "QtSvgWidgets", "QtTest",
    "QtTextToSpeech", "QtUiTools", "QtWebChannel", "QtWebEngineCore", "QtWebEngineQuick",
    "QtWebEngineWidgets", "QtWebSockets", "QtWebView", "QtXml",
)]
EXCLUDED_STDLIB = ["tkinter", "unittest", "test", "pydoc_data"]

a = Analysis(
    ["apexgifmaker.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets/applogo.svg", "assets"),
        ("assets/applogo.png", "assets"),
        ("assets/appicon.ico", "assets"),
        ("assets/fonts", "assets/fonts"),
        ("assets/icons", "assets/icons"),
    ] + TRANSLATION_DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_QT + EXCLUDED_STDLIB,
    noarchive=False,
    optimize=1,
)

# 쓰지 않는 큰 DLL과 플러그인. (소프트웨어 OpenGL, PDF, 쓰지 않는 이미지 형식·플랫폼·네트워크 플러그인)
# libcrypto/libssl-3-x64는 Qt TLS 플러그인용입니다(파이썬 HTTPS는 접미사 없는 libcrypto-3.dll을 씀).
DROP_BINARIES = {"opengl32sw.dll", "qt6pdf.dll", "qt6qml.dll", "qt6quick.dll", "qt6virtualkeyboard.dll",
                 "libcrypto-3-x64.dll", "libssl-3-x64.dll"}
DROP_PATH_PARTS = (
    "pyside6/translations/",
    "plugins/imageformats/qpdf", "plugins/imageformats/qtiff", "plugins/imageformats/qwebp",
    "plugins/imageformats/qicns", "plugins/imageformats/qtga", "plugins/imageformats/qwbmp",
    "plugins/platforms/qminimal", "plugins/platforms/qdirect2d",
    "plugins/networkinformation/", "plugins/tls/", "plugins/platforminputcontexts/",
    "plugins/generic/", "plugins/styles/",
)


def prune(entries, label):
    kept, dropped = [], []
    for entry in entries:
        dest = str(entry[0]).replace("\\", "/").lower()
        if dest.rsplit("/", 1)[-1] in DROP_BINARIES or any(part in dest for part in DROP_PATH_PARTS):
            dropped.append(dest)
        else:
            kept.append(entry)
    print("[spec] {}: {}개 제외".format(label, len(dropped)))
    for item in dropped:
        print("[spec]   - {}".format(item))
    return kept


a.binaries = prune(a.binaries, "binaries")
a.datas = prune(a.datas, "datas")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/appicon.ico",
    version=VERSION_RESOURCE,
    # PyInstaller 기본 이름(_internal) 대신 bin. ffmpeg·ffprobe도 같은 폴더에 두어 exe 옆에는 bin 하나만 보입니다.
    # 이 이름은 src/core/config.py의 TOOLS_DIR_NAME, 자동 업데이트의 교체 대상 폴더와 같아야 합니다.
    contents_directory="bin",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)


def install_documents():
    """사용자가 열어 볼 안내문과 라이선스는 bin이 아니라 exe 옆에 둡니다."""
    target = os.path.join(DISTPATH, APP_NAME)
    for source in ("README.txt", "LICENSE", "ATTRIBUTION.txt"):
        path = os.path.join(SPECPATH, source)
        if os.path.isfile(path):
            name = source if source.endswith(".txt") else source + ".txt"
            shutil.copyfile(path, os.path.join(target, name))


install_documents()
