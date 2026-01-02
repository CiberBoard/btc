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
project_files = ['config.py', 'main.py'] # main.py обычно не добавляется как data, но на всякий случай
for item in project_files:
    item_path = os.path.join(base_path, item)
    if os.path.exists(item_path) and os.path.isfile(item_path):
        datas.append((item_path, '.'))

# Добавляем папки проекта, сохраняя их структуру
project_folders = ['utils', 'core', 'ui', 'logger']
for folder in project_folders:
    folder_path = os.path.join(base_path, folder)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Это добавит всю папку и её содержимое, сохраняя структуру
        datas.append((folder_path, folder))
        print(f"Добавлена папка: {folder_path}")

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
    # Добавляем как бинарный файл, чтобы PyInstaller знал, что это исполняемый файл
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
        # collect_all собирает datas, binaries, hiddenimports
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
# Добавляем модули, которые могут не быть обнаружены автоматически
# или те, которые импортируются динамически/условно

# PyQt5 модули (часто требуются)
pyqt5_hidden = collect_submodules('PyQt5')
hiddenimports += pyqt5_hidden
print(f"Добавлены PyQt5 подмодули: {len(pyqt5_hidden)}")

# Модули для мультипроцессинга (критично для CPU поиска)
multiprocessing_hidden = collect_submodules('multiprocessing')
hiddenimports += multiprocessing_hidden
print(f"Добавлены multiprocessing подмодули: {len(multiprocessing_hidden)}")

# Дополнительные скрытые импорты
additional_hiddenimports = [
    # Системные модули, которые явно используются
    'logging.config', # ВАЖНО для fileConfig
    'logging.handlers',
    'configparser',

    # Модули Windows API (если используются напрямую или через psutil)
    # 'win32api', # Раскомментируйте, если используете напрямую
    # 'win32process', # Раскомментируйте, если используете напрямую
    # 'win32con', # Раскомментируйте, если используете напрямую

    # Другие потенциально полезные
    'queue', 'threading', 'subprocess', 'platform',
    'json', 'time', 'random', 'collections', 're', 'os', 'sys',
    'pickle', 'traceback', 'signal', 'ctypes', 'heapq', 'weakref',
]

# Убираем дубликаты
hiddenimports = list(set(hiddenimports + additional_hiddenimports))
print(f"Добавлены дополнительные скрытые импорты: {len(additional_hiddenimports)}")

# ========== ИСКЛЮЧЕНИЯ ==========
# Исключаем крупные библиотеки, которые НЕ используются, чтобы уменьшить размер .exe
excludes = [
    'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL',
    'cv2', 'sklearn', 'tensorflow', 'torch', 'jupyter', 'IPython',
    'notebook', 'sphinx', 'pytest', 'unittest', 'email', 'http',
    'xml', 'html', 'urllib', 'asyncio', 'concurrent',
]
print(f"Исключены библиотеки: {excludes}")

# ========== АНАЛИЗ ОСНОВНОГО ФАЙЛА ==========
a = Analysis(
    ['main.py'], # Ваш основной скрипт
    pathex=[base_path], # Добавляем базовый путь в пути поиска модулей
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes, # Передаем список исключений
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1, # Включает базовую оптимизацию
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ========== СОЗДАНИЕ ИСПОЛНЯЕМОГО ФАЙЛА ==========
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [], # Дополнительные runtime опции, если нужны
    name='BSG4.0', # Имя вашего .exe файла
    debug=False, # Установите True для отладки
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Установите True, если хотите сжать exe (нужен UPX)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # False для GUI приложений (без консоли)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None, # Иконка
)
