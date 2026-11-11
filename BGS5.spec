# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import site
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

if getattr(sys, 'stderr', None) is None:
    sys.stderr = open(os.devnull, 'w')

block_cipher = None
base_path = os.path.abspath(SPECPATH)

print("=" * 60)
print("🔧 Сборка BGS5.5 (ONEFILE)")
print(f"📁 Корень проекта: {base_path}")
print("=" * 60)

datas, binaries, hiddenimports = [], [], []

# ========== 1. ИКОНКА ==========
icon_path = os.path.join(base_path, 'icon.ico')
if os.path.exists(icon_path):
    print(f"✅ Иконка: {icon_path}")
else:
    print(f"⚠️  Иконка не найдена: {icon_path}")
    icon_path = None

# ========== 2. PYTHON-МОДУЛИ ==========
config_py = os.path.join(base_path, 'config.py')
if os.path.exists(config_py):
    datas.append((config_py, '.'))
    print("✅ Добавлен config.py")
else:
    print("❌ config.py не найден — критическая ошибка!")

for folder in ['utils', 'core', 'ui', 'logger']:
    folder_path = os.path.join(base_path, folder)
    if os.path.isdir(folder_path):
        datas.append((folder_path, folder))
        print(f"✅ Добавлена папка: {folder}")

# ========== 3. КОНФИГИ ==========
logging_conf = os.path.join(base_path, 'logger', 'logging.conf')
if os.path.exists(logging_conf):
    datas.append((logging_conf, 'logger'))
    print("✅ Добавлен logger/logging.conf")

# settings.json НЕ пакуем — пользовательские данные
json_files = ['config.json']
for fname in json_files:
    fpath = os.path.join(base_path, fname)
    if os.path.exists(fpath):
        datas.append((fpath, '.'))
        print(f"✅ Добавлен {fname}")
    else:
        print(f"⚠️  {fname} отсутствует")

for fname in ['Found_key_CUDA.txt']:
    fpath = os.path.join(base_path, fname)
    if os.path.exists(fpath):
        datas.append((fpath, '.'))
        print(f"✅ Добавлен {fname}")

# ========== 4. bin/ — ТОЛЬКО datas ==========
exe_files = [
    'bin/Etarkangaroo.exe',
    'bin/cuBitCrack.exe',
    'bin/clBitCrack.exe',
    'bin/VanitySearch.exe',
    'bin/cudart64_101.dll',
]
for rel in exe_files:
    src = os.path.join(base_path, rel)
    if os.path.exists(src):
        datas.append((src, 'bin'))
        print(f"✅ {rel} → bin/")
    else:
        print(f"❌ {rel} НЕ НАЙДЕН!")

# ========== 5. PyQt6 плагины ==========
print("\n🔍 Qt-плагины...")
qt_plugin_dirs = []
for site_pkg in site.getsitepackages():
    for cand in [
        os.path.join(site_pkg, 'PyQt6', 'Qt6', 'plugins'),
        os.path.join(site_pkg, 'PyQt6', 'Qt', 'plugins'),
        os.path.join(site_pkg, 'PyQt6', 'plugins'),
    ]:
        if os.path.isdir(cand):
            qt_plugin_dirs.append(cand)
venv_base = os.path.dirname(sys.executable)
for cand in [
    os.path.join(venv_base, '..', 'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins'),
    os.path.join(venv_base, 'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins'),
]:
    if os.path.isdir(cand):
        qt_plugin_dirs.append(cand)

for plugin_dir in set(qt_plugin_dirs):
    for subdir in ['platforms', 'styles', 'imageformats']:
        src = os.path.join(plugin_dir, subdir)
        if os.path.isdir(src):
            dest = os.path.join('PyQt6', 'Qt6', 'plugins', subdir)
            datas.append((src, dest))
            print(f"✅ Qt-плагин: {subdir}")

# ========== 6. Зависимости ==========
for lib_name in ['coincurve', 'PyQt6', 'pyqtgraph', 'psutil', 'pynvml',
                 'base58', 'numpy', 'Pillow', 'matplotlib', 'scipy', 'sklearn']:
    try:
        d, b, h = collect_all(lib_name)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
        print(f"📦 Собрано: {lib_name}")
    except Exception as e:
        print(f"⚠️  {lib_name}: {e}")

try:
    datas.extend(copy_metadata('coincurve'))
    print("✅ Метаданные coincurve добавлены")
except Exception as e:
    print(f"⚠️  Метаданные coincurve: {e}")

# ========== 7. Скрытые импорты ==========
hiddenimports.extend(
    collect_submodules('PyQt6.QtCore') +
    collect_submodules('PyQt6.QtGui') +
    collect_submodules('PyQt6.QtWidgets') +
    collect_submodules('multiprocessing')
)

additional_hiddenimports = [
    'logging.config', 'logging.handlers', 'configparser',
    'queue', 'threading', 'subprocess', 'platform',
    'json', 'time', 'random', 'collections', 're', 'os', 'sys',
    'pickle', 'traceback', 'signal', 'ctypes',
    'numpy', 'matplotlib', 'scipy', 'sklearn', 'PIL',
    'ui.predict_logic', 'ui.main_window', 'ui.frameless',
    'ui.theme', 'ui.sidebar', 'ui.matrix_window',
    'ui.gpu_monitor_window', 'ui.nav_icons', 'ui.animations',
    'ui.ui_main',
    'core.kangaroo_worker', 'core.cubitcrack_worker',
    'core.cpu_scanner', 'core.gpu_scanner',
    'core.matrix_logic', 'core.predict_logic',
    'core.unified_scanner',
    'utils.helpers', 'utils.hextowif', 'utils.settings_manager',
    'utils.random_range_dialog', 'utils.hex_calc_window',
    'utils.gpu_monitor_window', 'utils.gpu_progress_tracker',
    'utils.gpu_auto_config',
    'ui.vanity_logic',
]
hiddenimports = list(set(hiddenimports + additional_hiddenimports))
print(f"✅ Скрытых импортов: {len(hiddenimports)}")

# ========== 8. Исключения ==========
excludes = [
    'tkinter', 'pandas', 'cv2', 'tensorflow', 'torch', 'jupyter',
    'IPython', 'notebook',
    'PyQt6.QtNetwork', 'PyQt6.QtSql', 'PyQt6.QtMultimedia',
    'PyQt6.QtBluetooth', 'PyQt6.QtNfc',
    'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
    'PyQt6.QtWebEngine', 'PyQt6.QtWebKit', 'PyQt6.QtWebKitWidgets',
    'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.Qt3DInput',
    'PyQt6.QtQuick', 'PyQt6.QtQml', 'PyQt6.QtDesigner',
    'PyQt6.QtTest', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
]
print(f"🚫 Исключено: {len(excludes)}")

# ========== 9. Анализ ==========
a = Analysis(
    [os.path.join(base_path, 'main.py')],
    pathex=[base_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ========== 10. EXE — ONEFILE (без COLLECT) ==========
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BGS5.5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,           # после проверки → False
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

print("=" * 60)
print("✅ ONEFILE сборка настроена.")
print("📁 Результат: dist/BGS5.5.exe (ОДИН файл)")
print("=" * 60)