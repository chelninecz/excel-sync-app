# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None
base_path = os.path.abspath(SPECPATH)

added_datas = []
added_binaries = []

# 1. RapidOCR — модели, конфиги, ВСЕ файлы
import rapidocr_onnxruntime
rapidocr_path = os.path.dirname(rapidocr_onnxruntime.__file__)
for root, dirs, files in os.walk(rapidocr_path):
    for f in files:
        src = os.path.join(root, f)
        dst = os.path.relpath(root, os.path.dirname(rapidocr_path))
        added_datas.append((src, dst))

# 2. ONNX Runtime — бинарники И файлы данных (конфиги, json, yaml)
import onnxruntime
onnx_path = os.path.dirname(onnxruntime.__file__)
for root, dirs, files in os.walk(onnx_path):
    for f in files:
        src = os.path.join(root, f)
        dst = os.path.relpath(root, os.path.dirname(onnx_path))
        if f.endswith(('.dll', '.so', '.dylib', '.pyd', '.onnx')):
            added_binaries.append((src, dst))
        else:
            # Все остальные файлы onnxruntime — в datas (json, yaml, txt, и т.д.)
            added_datas.append((src, dst))

a = Analysis(
    ['haier_ppa_generator.py'],
    pathex=[base_path],
    binaries=added_binaries,
    datas=added_datas,
    hiddenimports=[
        # PyQt6
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip',
        
        # PyMuPDF (fitz)
        'fitz', 'PyMuPDF', '_fitz', 'fitz.fitz',
        
        # RapidOCR + модели (динамические импорты)
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.utils',
        'rapidocr_onnxruntime.rapid_ocr_api',
        'rapidocr_onnxruntime.ch_ppocr_v2_cls',
        'rapidocr_onnxruntime.ch_ppocr_v3_rec',
        'rapidocr_onnxruntime.ch_ppocr_v3_det',
        
        # ONNX Runtime
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
        'onnxruntime.capi._pybind_state',
        'onnxruntime.capi.onnxruntime_inference_collection',
        'onnxruntime.transformers.machine_info',
        
        # NumPy (ключевые подмодули для 2.x)
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
        'numpy.linalg._linalg',
        'numpy.linalg._umath_linalg',
        'numpy.linalg.lapack_lite',
        'numpy.fft._pocketfft',
        'numpy.fft._helper',
        'numpy.random._common',
        'numpy.random._generator',
        'numpy.random.bit_generator',
        'numpy.random.mtrand',
        'numpy.polynomial._polybase',
        'numpy.lib._function_base_impl',
        'numpy.lib._npyio_impl',
        'numpy.lib._index_tricks_impl',
        'numpy.lib._twodim_base_impl',
        'numpy.lib._polynomial_impl',
        'numpy.lib._shape_base_impl',
        'numpy.lib._array_utils_impl',
        'numpy._array_api_info',
        
        # PIL / Pillow (все форматы и C-расширения)
        'PIL',
        'PIL.Image',
        'PIL._imaging',
        'PIL._imagingft',
        'PIL._imagingmath',
        'PIL.ImageDraw',
        'PIL.ImageFilter',
        'PIL.ImageOps',
        'PIL.ImagePalette',
        'PIL.TiffImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.PngImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL.Jpeg2KImagePlugin',
        'PIL.features',
        
        # pdfplumber + pdfminer (полная цепочка зависимостей)
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
        'pdfminer.pdffont',
        'pdfminer.cmapdb',
        'pdfminer.encodingdb',
        'pdfminer.pdfdevice',
        'pdfminer.pdfpage',
        'pdfminer.pdfdocument',
        'pdfminer.arcfour',
        'pdfminer.data_structures',
        'pdfminer._saslprep',
        'pdfminer.jbig2',
        'pdfminer.lzw',
        'pdfminer.ccitt',
        'pdfminer.psparser',
        'pdfminer.utils',
        
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
        'openpyxl.chart',
        'openpyxl.drawing',
        
        # XML / прочее
        'xml.etree.ElementTree',
        'defusedxml',
        'defusedxml.ElementTree',
        'lxml',
        'lxml.etree',
        'yaml',
        
        # pkg_resources (без устаревшего py2_warn)
        'pkg_resources',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pandas', 'tkinter',
        'PyQt5', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook', 'pytest', 'unittest',
        'pdf2image', 'pytesseract',  # ← явно исключаем старые зависимости
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
    upx=False,  # ← ИСПРАВЛЕНО: отключено, чтобы не портить DLL
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