# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# !!! Правильный путь: папка, где лежит .spec файл !!!
base_path = os.path.abspath(SPECPATH)

added_datas = []
added_binaries = []

# 1. RapidOCR модели и конфиги
import rapidocr_onnxruntime
rapidocr_path = os.path.dirname(rapidocr_onnxruntime.__file__)
for root, dirs, files in os.walk(rapidocr_path):
    for f in files:
        src = os.path.join(root, f)
        dst = os.path.relpath(root, os.path.dirname(rapidocr_path))
        added_datas.append((src, dst))

# 2. ONNX Runtime библиотеки
import onnxruntime
onnx_path = os.path.dirname(onnxruntime.__file__)
for root, dirs, files in os.walk(onnx_path):
    for f in files:
        if f.endswith(('.dll', '.so', '.dylib', '.pyd', '.onnx')):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, os.path.dirname(onnx_path))
            added_binaries.append((src, dst))

# 3. Poppler — ВСЕ файлы как datas с сохранением структуры папок
poppler_base = os.path.join(base_path, 'poppler')
print("=" * 50)
print(f"SPEC base_path: {base_path}")
print(f"Poppler base: {poppler_base}")
print(f"Exists: {os.path.exists(poppler_base)}")

if os.path.exists(poppler_base):
    count = 0
    for root, dirs, files in os.walk(poppler_base):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, base_path)
            added_datas.append((src, dst))
            count += 1
    print(f"[OK] Poppler: добавлено {count} файлов")
else:
    print(f"[FAIL] Poppler НЕ найден!")
print("=" * 50)

# 4. pdf2image
import pdf2image
pdf2image_path = os.path.dirname(pdf2image.__file__)
added_datas.append((pdf2image_path, 'pdf2image'))

a = Analysis(
    ['haier_ppa_generator.py'],
    pathex=[base_path],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=[
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
        'rapidocr_onnxruntime', 'rapidocr_onnxruntime.utils', 'rapidocr_onnxruntime.rapid_ocr_api',
        'onnxruntime', 'onnxruntime.capi', 'onnxruntime.capi.onnxruntime_pybind11_state',
        'numpy._core', 'numpy._core._multiarray_umath', 'numpy.linalg._umath_linalg',
        'PIL', 'PIL.Image', 'PIL._imaging', 'PIL.JpegImagePlugin', 'PIL.PngImagePlugin',
        'pdf2image', 'pdfplumber', 'pdfplumber.utils', 'pdfminer', 'pdfminer.high_level',
        'openpyxl', 'openpyxl.xml', 'openpyxl.reader.excel', 'openpyxl.writer.excel',
        'pytesseract', 'pkg_resources', 'pkg_resources.py2_warn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'tkinter', 'PyQt5', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook', 'pytest', 'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Haier_PPA_Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Оставьте True для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
