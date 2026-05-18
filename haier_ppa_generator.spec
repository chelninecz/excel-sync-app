# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.config import CONF

block_cipher = None

# Определяем базовый путь
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath('.'))

# --- Дополнительные файлы данных ---
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
        if f.endswith(('.dll', '.so', '.dylib', '.pyd')):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, os.path.dirname(onnx_path))
            added_binaries.append((src, dst))

# 3. Poppler (если есть в проекте)
poppler_base = os.path.join(base_path, 'poppler')
if os.path.exists(poppler_base):
    for root, dirs, files in os.walk(poppler_base):
        for f in files:
            src = os.path.join(root, f)
            dst = os.path.relpath(root, base_path)
            added_datas.append((src, dst))

poppler_share = os.path.join(base_path, 'poppler', 'share')
if os.path.exists(poppler_share):
    added_datas.append((poppler_share, 'poppler/share'))

# 4. pdf2image poppler_utils
import pdf2image
pdf2image_path = os.path.dirname(pdf2image.__file__)
added_datas.append((pdf2image_path, 'pdf2image'))

# 5. Tesseract (если используется)
try:
    import pytesseract
    tess_path = os.path.dirname(pytesseract.__file__)
    added_datas.append((tess_path, 'pytesseract'))
except:
    pass

a = Analysis(
    ['haier_ppa_generator.py'],
    pathex=[base_path],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=[
        # PyQt6
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        
        # RapidOCR
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.utils',
        'rapidocr_onnxruntime.rapid_ocr_api',
        'rapidocr_onnxruntime.ch_ppocr_v2_cls',
        'rapidocr_onnxruntime.ch_ppocr_v3_rec',
        'rapidocr_onnxruntime.ch_ppocr_v3_det',
        
        # ONNX
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'onnxruntime.capi._pybind_state',
        
        # NumPy — все подмодули для Python 3.14
        'numpy._core',
        'numpy._core._multiarray_umath',
        'numpy._core._multiarray_tests',
        'numpy._core.numeric',
        'numpy._core.umath',
        'numpy._core.shape_base',
        'numpy._core.fromnumeric',
        'numpy._core._methods',
        'numpy._core.arrayprint',
        'numpy._core.defchararray',
        'numpy._core.records',
        'numpy._core.memmap',
        'numpy._core.function_base',
        'numpy._core.getlimits',
        'numpy._core.machar',
        'numpy._core.einsumfunc',
        'numpy._core._simd',
        'numpy._core._dtype_ctypes',
        'numpy._core._string_helpers',
        'numpy._core._type_aliases',
        'numpy._core._exceptions',
        'numpy._core.overrides',
        'numpy.linalg._umath_linalg',
        'numpy.linalg.lapack_lite',
        'numpy.fft._pocketfft',
        'numpy.random._common',
        'numpy.random._generator',
        'numpy.random.bit_generator',
        'numpy.random.mtrand',
        
        # PIL
        'PIL',
        'PIL.Image',
        'PIL._imaging',
        'PIL._imagingft',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.TiffImagePlugin',
        'PIL.WebPImagePlugin',
        
        # pdf2image
        'pdf2image',
        'pdf2image.pdf2image',
        'pdf2image.exceptions',
        
        # pdfplumber
        'pdfplumber',
        'pdfplumber.utils',
        'pdfplumber.page',
        'pdfplumber.pdf',
        'pdfplumber.table',
        'pdfplumber.display',
        'pdfminer',
        'pdfminer.high_level',
        'pdfminer.layout',
        'pdfminer.pdfparser',
        'pdfminer.pdfinterp',
        'pdfminer.converter',
        
        # openpyxl
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.worksheet',
        'openpyxl.workbook',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.xml',
        'openpyxl.xml.functions',
        'openpyxl.reader.excel',
        'openpyxl.writer.excel',
        
        # pytesseract
        'pytesseract',
        
        # Стандартные
        'pkg_resources',
        'pkg_resources.py2_warn',
        'logging',
        're',
        'json',
        'pathlib',
        'xml.etree.ElementTree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'tkinter',
        'PyQt5',
        'PySide2',
        'PySide6',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'unittest',
        'test',
        'tests',
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
    console=True,  # ВРЕМЕННО True для отладки — увидим ошибки в консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
