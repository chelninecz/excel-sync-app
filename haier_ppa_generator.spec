# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['haier_ppa_generator.py'],
    pathex=[],
    binaries=[
        # Poppler binaries для Windows
        ('poppler/Library/bin', 'poppler/Library/bin'),
        ('poppler/share', 'poppler/share'),
    ],
    datas=[
        # Если есть дополнительные файлы данных - добавить сюда
    ],
    hiddenimports=[
        # PyQt6 модули
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        
        # RapidOCR и зависимости
        'rapidocr_onnxruntime',
        'rapidocr_onnxruntime.utils',
        'onnxruntime',
        'numpy',
        'PIL',
        'PIL.Image',
        
        # pdf2image
        'pdf2image',
        'pdf2image.pdf2image',
        
        # Другие зависимости
        'pdfplumber',
        'openpyxl',
        'pytesseract',
        
        # Стандартные библиотеки, которые могут быть пропущены
        'pkg_resources.py2_warn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'tkinter',
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Установить True для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Добавить путь к .ico файлу при необходимости
)
