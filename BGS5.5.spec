# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import site
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files, copy_metadata

# 🔧 FIX: Защита от sys.stderr=None (редкий баг PyInstaller в некоторых IDE)
if getattr(sys, 'stderr', None) is None:
    sys.stderr = open(os.devnull, 'w')

# Определяем базовые пути
block_cipher = None
base_path = os.path.abspath('.')

print("=" * 60)
print("🔧 Сборка BGS5.5 (GPU Bitcoin Scanner)")
print(f"📁 Рабочая директория: {base_path}")
print("=" * 60)

# Списки
datas = []
binaries = []
hiddenimports = []

# ========== 1. ИКОНКА ==========
icon_path = os.path.join(base_path, 'icon.ico')
if os.path.exists(icon_path):
    print(f"✅ Иконка найдена: {icon_path}")
else:
    print(f"⚠️  Иконка отсутствует: {icon_path}")
    icon_path = None

# ========== 2. PYTHON-МОДУЛИ ==========
config_py = os.path.join(base_path, 'config.py')
if os.path.exists(config_py):
    datas.append((config_py, '.'))
    print("✅ Добавлен config.py")
else:
    print("❌ config.py не найден — критическая ошибка!")

project_folders = ['utils', 'core', 'ui', 'logger']
for folder in project_folders:
    folder_path = os.path.join(base_path, folder)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        datas.append((folder_path, folder))
        print(f"✅ Добавлена папка: {folder}")

# ========== 3. КОНФИГУРАЦИОННЫЕ ФАЙЛЫ ==========
logging_conf = os.path.join(base_path, 'logger', 'logging.conf')
if os.path.exists(logging_conf):
    datas.append((logging_conf, 'logger'))
    print("✅ Добавлен logger/logging.conf")
else:
    print("⚠️  logging.conf отсутствует")

json_files = ['config.json', 'settings.json']
for fname in json_files:
    fpath = os.path.join(base_path, fname)
    if os.path.exists(fpath):
        datas.append((fpath, '.'))
        print(f"✅ Добавлен {fname}")
    else:
        print(f"⚠️  {fname} отсутствует — возможны ошибки при запуске")

other_files = ['Found_key_CUDA.txt']
for fname in other_files:
    fpath = os.path.join(base_path, fname)
    if os.path.exists(fpath):
        datas.append((fpath, '.'))
        print(f"✅ Добавлен {fname}")

# ========== 4. 🔴 ИСПОЛНЯЕМЫЕ ФАЙЛЫ (GPU/CPU TOOLS) ==========
exe_files = [
    ('Etarkangaroo.exe', '.'),
    ('cuBitcrack.exe', '.'),
    ('VanitySearch.exe', '.'),
]

for exe_name, dest_dir in exe_files:
    exe_path = os.path.join(base_path, exe_name)
    if os.path.exists(exe_path):
        binaries.append((exe_path, dest_dir))
        datas.append((exe_path, dest_dir))
        print(f"✅ Добавлен {exe_name}")
    else:
        print(f"❌ {exe_name} НЕ НАЙДЕН!")

# ========== 5. PyQt5 ПЛАГИНЫ ==========
print("\n🔍 Поиск Qt-плагинов...")
qt_plugin_dirs = []
for site_pkg in site.getsitepackages():
    candidates = [
        os.path.join(site_pkg, 'PyQt5', 'Qt', 'plugins'),
        os.path.join(site_pkg, 'PyQt5', 'Qt5', 'plugins'),
        os.path.join(site_pkg, 'PyQt5', 'plugins'),
    ]
    for cand in candidates:
        if os.path.isdir(cand):
            qt_plugin_dirs.append(cand)

venv_base = os.path.dirname(sys.executable)
venv_candidates = [
    os.path.join(venv_base, '..', 'Lib', 'site-packages', 'PyQt5', 'Qt', 'plugins'),
    os.path.join(venv_base, 'Lib', 'site-packages', 'PyQt5', 'Qt', 'plugins'),
]
for cand in venv_candidates:
    if os.path.isdir(cand):
        qt_plugin_dirs.append(cand)

qt_plugin_dirs = list(set(qt_plugin_dirs))
needed_subdirs = ['platforms', 'styles']
for plugin_dir in qt_plugin_dirs:
    for subdir in needed_subdirs:
        src = os.path.join(plugin_dir, subdir)
        if os.path.isdir(src):
            dest = os.path.join('PyQt5', 'Qt', 'plugins', subdir)
            datas.append((src, dest))
            print(f"✅ Qt-плагин: {subdir} ← {src}")

# ========== 6. ЗАВИСИМОСТИ (✅ ИСПРАВЛЕНО: добавлены numpy и ML-библиотеки) ==========
libs_to_collect = ['coincurve', 'PyQt5', 'psutil', 'pynvml', 'base58', 'numpy', 'Pillow']
libs_to_collect.extend(['matplotlib', 'scipy', 'sklearn'])  # Для вкладки Predict

for lib_name in libs_to_collect:
    try:
        tmp_ret = collect_all(lib_name)
        datas.extend(tmp_ret[0])
        binaries.extend(tmp_ret[1])
        hiddenimports.extend(tmp_ret[2])
        print(f"📦 Собраны зависимости: {lib_name}")
    except Exception as e:
        print(f"⚠️  Ошибка сбора {lib_name}: {e}")

try:
    datas.extend(copy_metadata('coincurve'))
    print("✅ Метаданные coincurve добавлены")
except Exception as e:
    print(f"⚠️  Метаданные coincurve: {e}")

# ========== 7. СКРЫТЫЕ ИМПОРТЫ (✅ ИСПРАВЛЕНО: кавычки у numpy, добавлены ML) ==========
pyqt5_hidden = (
    collect_submodules('PyQt5.QtCore') +
    collect_submodules('PyQt5.QtGui') +
    collect_submodules('PyQt5.QtWidgets')
)
hiddenimports.extend(pyqt5_hidden)
print(f"✅ PyQt5: {len(pyqt5_hidden)} модулей")

hiddenimports.extend(collect_submodules('multiprocessing'))
print("✅ Добавлены multiprocessing модули")

additional_hiddenimports = [
    'logging.config', 'logging.handlers', 'configparser',
    'queue', 'threading', 'subprocess', 'platform',
    'json', 'time', 'random', 'collections', 're', 'os', 'sys',
    'pickle', 'traceback', 'signal', 'ctypes', 'numpy',  # ✅ Исправлено: добавлены кавычки
    'matplotlib', 'scipy', 'sklearn', 'Pillow',  # ✅ Добавлено
    'ui.predict_logic',  # ✅ Добавлено для вкладки Predict
    'core.kangaroo_worker',
    'core.cubitcrack_worker',
    'ui.vanity_logic',
]
hiddenimports = list(set(hiddenimports + additional_hiddenimports))
print(f"✅ Всего скрытых импортов: {len(hiddenimports)}")

# ========== 8. ИСКЛЮЧЕНИЯ (✅ ИСПРАВЛЕНО: убраны numpy, matplotlib, scipy, sklearn) ==========
excludes = [
    'tkinter', 'pandas',  'cv2', 'tensorflow', 'torch', 'jupyter',

    'PyQt5.QtNetwork', 'PyQt5.QtSql', 'PyQt5.QtMultimedia',
    'PyQt5.QtBluetooth', 'PyQt5.QtNfc', 'PyQt5.QtWeb*',
]
print(f"🚫 Исключено: {len(excludes)} модулей")

# ========== 9. АНАЛИЗ ==========
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

# ========== 10. ИСПОЛНЯЕМЫЙ ФАЙЛ ==========
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BSG5.5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # ← Важно для GPU-инструментов!
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # ⚠️ Оставлено True для первой проверки. После теста поменяйте на False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

print("=" * 60)
print("✅ Сборка настроена.")
print("💡 Запустите: pyinstaller BGS5.5.spec")
print("⚠️  Не забудьте: multiprocessing.freeze_support() в main.py")
print("=" * 60)