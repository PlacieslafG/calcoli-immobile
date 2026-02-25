# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec per CalcoliImmobile
# Uso: pyinstaller calcoli_immobile.spec

from PyInstaller.utils.hooks import collect_data_files

# customtkinter porta con sé temi, font e icone — va incluso esplicitamente
datas = collect_data_files("customtkinter")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["customtkinter", "darkdetect"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CalcoliImmobile",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # nessuna finestra console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",      # decommentare se aggiungi un'icona .ico
)
