# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the SSP project one-file binary.
# Build:    pyinstaller ssp_project_main.spec
# Result:   dist/ssp_project_main(.exe)

from PyInstaller.utils.hooks import collect_submodules

hidden_imports = []
hidden_imports += collect_submodules("pypdf")
hidden_imports += collect_submodules("yaml")
hidden_imports += collect_submodules("pandas")
hidden_imports += collect_submodules("transformers")
hidden_imports += collect_submodules("torch")

added_files = [
    ("src/kde_to_kubescape.yaml", "src"),
]


a = Analysis(
    ["scripts/ssp_project_main.py"],
    pathex=["."],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ssp_project_main",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
