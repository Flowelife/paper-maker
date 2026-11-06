# PyInstaller spec — build with: python scripts/build_exe.py
# the entry module lives in src/ on purpose: an entry script placed next to
# scripts/papermaker.py would shadow the ``papermaker`` package during analysis.
from pathlib import Path

project_root = Path(SPECPATH).parent
assets_dir = project_root / "assets"

a = Analysis(
    [str(project_root / "scripts" / "src" / "entry.py")],
    pathex=[str(project_root / "scripts" / "src")],
    binaries=[],
    datas=[(str(assets_dir), "assets")],
    hiddenimports=["win32com.client", "pythoncom", "pywintypes"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "pymupdf",
              "scipy", "sklearn", "lxml", "docx"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="papermaker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
