# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files
import os

# Определяем базовые пути
block_cipher = None
base_path = os.path.abspath('.')

# Сбор данных и зависимостей
datas = []
binaries = []
hiddenimports = []

# Добавляем иконку если есть
if os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))

# Собираем все зависимости для coincurve
try:
    tmp_ret = collect_all('coincurve')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# Собираем PyQt5 зависимости
try:
    tmp_ret = collect_all('PyQt5')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
except:
    pass

# Добавляем дополнительные скрытые импорты
hiddenimports += [
    # Криптографические библиотеки
    'coincurve',
    'coincurve._cffi_backend',
    'coincurve.context',
    'coincurve.keys',
    'coincurve.ecdsa',

    # Хеширование
    'hashlib',
    'base58',

    # PyQt5 модули
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',

    # Системные модули
    'multiprocessing',
    'multiprocessing.spawn',
    'multiprocessing.util',
    'multiprocessing.connection',
    'multiprocessing.queues',
    'multiprocessing.managers',
    'multiprocessing.pool',
    'multiprocessing.context',
    'queue',
    'threading',
    'subprocess',
    'platform',
    'psutil',
    'psutil._psutil_windows' if os.name == 'nt' else 'psutil._psutil_linux',

    # JSON и другие утилиты
    'json',
    'time',
    'random',
    'collections',
    're',
    'os',
    'sys',

    # Дополнительные модули для работы с процессами
    'pickle',
    'traceback',
    'signal',
]

# Добавляем файлы cuBitcrack.exe если существует
if os.path.exists('cuBitcrack.exe'):
    datas.append(('cuBitcrack.exe', '.'))

# Анализ основного файла
a = Analysis(
    ['main.py'],  # Замените на имя вашего основного файла
    pathex=[base_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'sklearn',
        'tensorflow',
        'torch',
        'jupyter',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

# Удаляем дубликаты
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Создание исполняемого файла
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BitcoinScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Отключаем консоль для GUI приложения
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)