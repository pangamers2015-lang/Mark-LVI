# PyInstaller spec - build on Windows
from PyInstaller.utils.hooks import collect_all

datas = [("ui", "ui")]
binaries = []
hiddenimports = ["webview", "webview.platforms.edgechromium", "keyring.backends.Windows"]
for package in ["webview", "google.genai", "sounddevice", "keyring"]:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="Jarvis", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True,
    upx_exclude=[], name="Jarvis",
)
