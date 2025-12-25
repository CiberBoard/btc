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
    print(f"Добавлена иконка: {icon_path}")
else:
    print(f"Иконка НЕ НАЙДЕНА: {icon_path}")

# Добавляем отдельные файлы проекта
project_files = ['config.py']
for item in project_files:
    item_path = os.path.join(base_path, item)
    if os.path.exists(item_path) and os.path.isfile(item_path):
        datas.append((item_path, '.'))

# Добавляем папки проекта, сохраняя их структуру
project_folders = ['utils', 'core', 'ui', 'logger']
for folder in project_folders:
    folder_path = os.path.join(base_path, folder)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        datas.append((folder_path, folder))
        print(f"Добавлена папка: {folder_path}")

# ========== ГАРАНТИРОВАННОЕ ДОБАВЛЕНИЕ КОНФИГУРАЦИОННЫХ ФАЙЛОВ ==========
logging_conf_path = os.path.join(base_path, 'logger', 'logging.conf')
if os.path.exists(logging_conf_path):
    datas.append((logging_conf_path, 'logger'))
    print(f"Добавлен файл конфигурации логов: {logging_conf_path}")
else:
    print(f"Файл конфигурации логов НЕ НАЙДЕН: {logging_conf_path}")

# Добавляем другие файлы данных
data_files = ['settings.json', 'Found_key_CUDA.txt']
for file_name in data_files:
    file_path = os.path.join(base_path, file_name)
    if os.path.exists(file_path):
        datas.append((file_path, '.'))

# ========== 🔴 КРИТИЧЕСКИ ВАЖНО: ДОБАВЛЕНИЕ Etarkangaroo.exe и cuBitcrack.exe ==========
exe_files = [
    ('Etarkangaroo.exe', '.'),
    ('cuBitcrack.exe', '.'),
]

for exe_name, dest_dir in exe_files:
    exe_path = os.path.join(base_path, exe_name)
    if os.path.exists(exe_path):
        # Добавляем как binary (чтобы сохранились права на исполнение)
        binaries.append((exe_path, dest_dir))
        # И как data — на случай, если код ищет его через os.listdir() или glob
        datas.append((exe_path, dest_dir))
        print(f"✅ Добавлен исполняемый файл: {exe_name}")
    else:
        print(f"❌ ВНИМАНИЕ: {exe_name} НЕ НАЙДЕН в корне проекта!")

# Если у вас есть DLL для Etarkangaroo (часто — cuda, cudnn и т.д.), добавьте их:
cuda_dlls = [
    'cudart64_*.dll', 'cublas64_*.dll', 'curand64_*.dll',
    'nvrtc64_*.dll', 'nvrtc-builtins64_*.dll'
]
# (PyInstaller обычно сам подхватывает нужные DLL при наличии binaries, но если нет — можно явно добавить)

# ========== СБОР ЗАВИСИМОСТЕЙ ==========
libs_to_collect = ['coincurve', 'PyQt5', 'psutil', 'pynvml', 'base58']
for lib_name in libs_to_collect:
    try:
        tmp_ret = collect_all(lib_name)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
        print(f"Собраны зависимости для: {lib_name}")
    except Exception as e:
        print(f"Предупреждение: Не удалось собрать {lib_name}: {e}")

# Метаданные
try:
    datas += copy_metadata('coincurve')
except Exception as e:
    print(f"Предупреждение: Метаданные coincurve: {e}")

# ========== СКРЫТЫЕ ИМПОРТЫ ==========
pyqt5_hidden = collect_submodules('PyQt5.QtCore') + \
               collect_submodules('PyQt5.QtGui') + \
               collect_submodules('PyQt5.QtWidgets')

hiddenimports += pyqt5_hidden
print(f"Добавлены PyQt5 модули: {len(pyqt5_hidden)}")

# Мультипроцессинг — ОБЯЗАТЕЛЬНО для CPU/Kangaroo
hiddenimports += collect_submodules('multiprocessing')

# Дополнительно (ваш список хорош, оставляем)
additional_hiddenimports = [
    'logging.config', 'logging.handlers', 'configparser',
    'queue', 'threading', 'subprocess', 'platform',
    'json', 'time', 'random', 'collections', 're', 'os', 'sys',
    'pickle', 'traceback', 'signal', 'ctypes', 'heapq', 'weakref',
    # Добавляем явно, т.к. KangarooWorker использует:
    'core.kangaroo_worker',
]
hiddenimports = list(set(hiddenimports + additional_hiddenimports))

# ========== ИСКЛЮЧЕНИЯ ==========
excludes = [
    'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL',
    'cv2', 'sklearn', 'tensorflow', 'torch', 'jupyter',
    'email', 'http', 'xml', 'html', 'urllib', 'asyncio',
    # PyQt5 модули, которые не нужны в GUI-приложении:
    'PyQt5.QtNetwork', 'PyQt5.QtSql', 'PyQt5.QtMultimedia',
]

# ========== АНАЛИЗ ==========
a = Analysis(
    ['main.py'],
    pathex=[base_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ========== ФИНАЛЬНАЯ СБОРКА ==========
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
    upx=False,  # ← Рекомендуется False для GPU-софта (иногда ломает CUDA)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # ← False — без консоли (GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)