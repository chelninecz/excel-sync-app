# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None
base_path = os.path.abspath(SPECPATH)

added_datas = []
added_binaries = []

# 1. PyMuPDF — полная сборка (имя пакета 'pymupdf', не 'fitz'!)
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all('pymupdf')
added_datas.extend(fitz_datas)
added_binaries.extend(fitz_binaries)

# 2. RapidOCR
rapidocr_datas, rapidocr_binaries, rapidocr_hiddenimports = collect_all('rapidocr_onnxruntime')
added_datas.extend(rapidocr_datas)
added_binaries.extend(rapidocr_binaries)

# 3. ONNX Runtime
onnx_datas, onnx_binaries, onnx_hiddenimports = collect_all('onnxruntime')
added_datas.extend(onnx_datas)
added_binaries.extend(onnx_binaries)

a = Analysis(
    ['haier_ppa_generator.py'],
    pathex=[base_path],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=[
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
        'numpy._core', 'numpy._core._multiarray_umath',
        'PIL', 'PIL.Image', 'PIL._imaging',
        'pdfplumber', 'pdfplumber.utils', 'pdfminer', 'pdfminer.high_level',
        'openpyxl', 'openpyxl.xml', 'openpyxl.reader.excel', 'openpyxl.writer.excel',
        'pkg_resources',
        # Добавленные:
        'lxml', 'lxml.etree',
        'defusedxml', 'defusedxml.ElementTree',
        'fontTools',
        'shapely', 'shapely.geometry',
    ] + fitz_hiddenimports + rapidocr_hiddenimports + onnx_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'tkinter',
        'PyQt5', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook', 'pytest', 'unittest',
        'pdf2image', 'pytesseract',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Haier_PPA_Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
