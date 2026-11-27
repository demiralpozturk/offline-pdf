# PyInstaller build: one folder with OfflinePDF.exe (GUI) and offlinepdf-cli.exe (console).
# Build with:  python scripts/build.py
from pathlib import Path

ROOT = Path(SPECPATH)

EXCLUDES = [
    "tkinter", "unittest", "pydoc_data", "numpy", "pytest",
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia", "PySide6.Qt3DCore", "PySide6.QtPdf",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtOpenGL", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtXml", "PySide6.QtSvg", "PySide6.QtDBus",
]

def analysis(script):
    return Analysis(
        [str(ROOT / "scripts" / script)],
        pathex=[str(ROOT)],
        datas=[(str(ROOT / "assets" / "icon.png"), "assets")],
        hiddenimports=["reportlab.graphics.barcode.common"],
        excludes=EXCLUDES,
        noarchive=False,
    )

gui = analysis("entry_gui.py")
cli = analysis("entry_cli.py")

def keep(entry):
    name = entry[0].replace("\\", "/").lower()
    if "pyside6/translations/" in name:
        return any(lang in name for lang in ("qtbase_en", "qtbase_tr"))
    return True

# Qt pieces a widgets app never loads (software OpenGL, QML/Quick, Qt PDF,
# virtual keyboard, network plugins) and Pillow's AVIF codec: ~50 MB saved.
DROP = (
    "opengl32sw.dll", "qt6quick", "qt6qml", "qt6pdf", "qt6virtualkeyboard", "qt6network",
    "plugins/imageformats/qpdf", "plugins/platforminputcontexts/", "plugins/networkinformation/",
    "plugins/tls/", "plugins/generic/", "pil/_avif",
)

def keep_binary(entry):
    name = entry[0].replace("\\", "/").lower()
    return not any(token in name for token in DROP)

gui.datas = [d for d in gui.datas if keep(d)]
gui.binaries = [b for b in gui.binaries if keep_binary(b)]
cli.binaries = [b for b in cli.binaries if keep_binary(b)]

gui_pyz = PYZ(gui.pure)
cli_pyz = PYZ(cli.pure)

gui_exe = EXE(
    gui_pyz, gui.scripts, [], exclude_binaries=True,
    name="OfflinePDF", icon=str(ROOT / "assets" / "icon.ico"),
    console=False, upx=False, version=None,
)
cli_exe = EXE(
    cli_pyz, cli.scripts, [], exclude_binaries=True,
    name="offlinepdf-cli", icon=str(ROOT / "assets" / "icon.ico"),
    console=True, upx=False,
)

coll = COLLECT(
    gui_exe, gui.binaries, gui.datas,
    cli_exe, cli.binaries, [d for d in cli.datas if keep(d)],
    strip=False, upx=False, name="OfflinePDF",
)
