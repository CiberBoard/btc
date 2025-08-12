# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files, copy_metadata

# Определяем базовые пути
block_cipher = None
base_path = os.path.abspath('.')

# Сбор данных и зависимостей
datas = []
binaries = []
hiddenimports = []

# ========== ОСНОВНОЕ ДОБАВЛЕНИЕ ДАННЫХ ПРОЕКТА ==========
# Добавляем иконку если есть
icon_path = os.path.join(base_path, 'icon.ico')
if os.path.exists(icon_path):
    datas.append((icon_path, '.'))

# Добавляем основные папки и файлы проекта
# Включаем config.py как модуль и все папки проекта
project_items = ['config.py', 'utils', 'core', 'ui', 'logger']
for item in project_items:
    item_path = os.path.join(base_path, item)
    if os.path.exists(item_path):
        if os.path.isfile(item_path):
            # Для файлов типа config.py
            datas.append((item_path, '.'))
        else: # Папка
            # Для папок сохраняем их структуру
            datas.append((item_path, item))

# ========== ГАРАНТИРОВАННОЕ ДОБАВЛЕНИЕ КОНФИГУРАЦИОННЫХ ФАЙЛОВ ==========
# Явно добавляем logging.conf из папки logger - КРИТИЧНО ВАЖНО
logging_conf_path = os.path.join(base_path, 'logger', 'logging.conf')
if os.path.exists(logging_conf_path):
    datas.append((logging_conf_path, 'logger'))
    print(f"Добавлен файл конфигурации логов: {logging_conf_path}")
else:
    print(f"Файл конфигурации логов НЕ НАЙДЕН: {logging_conf_path}")

# Добавляем другие файлы данных, если они существуют
data_files = ['settings.json', 'Found_key_CUDA.txt'] # Имя файла из config.py
for file_name in data_files:
    file_path = os.path.join(base_path, file_name)
    if os.path.exists(file_path):
        datas.append((file_path, '.'))
        print(f"Добавлен файл данных: {file_path}")

# ========== ДОБАВЛЕНИЕ cuBitcrack.exe ==========
cubitcrack_exe_path = os.path.join(base_path, 'cuBitcrack.exe')
if os.path.exists(cubitcrack_exe_path):
    binaries.append((cubitcrack_exe_path, '.'))
    # Также добавляем в datas, если код ожидает найти его в текущей директории
    datas.append((cubitcrack_exe_path, '.'))
    print(f"Добавлен cuBitcrack.exe: {cubitcrack_exe_path}")
else:
    print("cuBitcrack.exe НЕ НАЙДЕН в корне проекта")

# ========== СБОР ЗАВИСИМОСТЕЙ ДЛЯ БИБЛИОТЕК ==========
libs_to_collect = ['coincurve', 'PyQt5', 'psutil', 'pynvml', 'base58']
for lib_name in libs_to_collect:
    try:
        tmp_ret = collect_all(lib_name)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
        print(f"Собраны зависимости для: {lib_name}")
    except Exception as e:
        print(f"Предупреждение: Не удалось собрать {lib_name} data: {e}")

# Добавляем метаданные для важных пакетов
try:
    datas += copy_metadata('coincurve')
    print("Добавлены метаданные для coincurve")
except Exception as e:
    print(f"Предупреждение: Не удалось добавить метаданные coincurve: {e}")

# ========== СКРЫТЫЕ ИМПОРТЫ ==========
hiddenimports += [
    # Криптографические библиотеки
    'coincurve',
    'coincurve._libsecp256k1',
    'coincurve.context',
    'coincurve.keys',
    'coincurve.ecdsa',
    'coincurve.utils',
    'base58',

    # PyQt5 модули
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',
    'PyQt5.QtWidgets.QApplication',
    'PyQt5.QtWidgets.QMainWindow',
    'PyQt5.QtCore.QTimer',
    'PyQt5.QtCore.QThread',
    'PyQt5.QtCore.pyqtSignal',

    # Системные модули
    'multiprocessing',
    'multiprocessing.spawn',
    'multiprocessing.util',
    'multiprocessing.connection',
    'multiprocessing.queues',
    'multiprocessing.context',
    'multiprocessing.reduction',
    'multiprocessing.shared_memory',
    'queue',
    'threading',
    'subprocess',
    'platform',
    'psutil',
    'pynvml',
    'json',
    'time',
    'random',
    'collections',
    'collections.deque',
    're',
    'os',
    'sys',
    'logging',
    'logging.config', # ВАЖНО для fileConfig
    'logging.handlers',
    'configparser',

    # Дополнительные модули
    'pickle',
    'traceback',
    'signal',
    'ctypes',
    'ctypes.util',
    'heapq',
    'weakref',

    # Модули Windows API (если используются)
    'win32api',
    'win32process',
    'win32con',
]

# ========== АНАЛИЗ ОСНОВНОГО ФАЙЛА ==========
a = Analysis(
    ['main.py'],
    pathex=[base_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL',
        'cv2', 'sklearn', 'tensorflow', 'torch', 'jupyter', 'IPython',
        'notebook', 'sphinx', 'pytest', 'unittest', 'email', 'http',
        'xml', 'html', 'urllib', 'asyncio', 'concurrent',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ========== СОЗДАНИЕ ИСПОЛНЯЕМОГО ФАЙЛА ==========
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BSG4.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Для GUI приложений
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)
