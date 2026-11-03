# main.py
import ctypes
import faulthandler
import multiprocessing
import sys
import os

# faulthandler — печатает трейсбек при нативном крахе
try:
    faulthandler.enable()
except Exception:
    pass

if sys.platform == 'win32':
    multiprocessing.set_start_method('spawn', force=True)

# =========================================================================
# DLL-изоляция на Windows:
#   Qt и нативные модули (coincurve._cffi_backend) при загрузке тянут DLL
#   из папки python.exe и CWD. В venv/PyCharm там могут лежать чужие .dll
#   (cudart64_101.dll, zlib/ssl/ffmpeg и т.п.) → access violation на
#   window.show(). Изолируем PATH и используем SetDefaultDllDirectories.
# =========================================================================
if sys.platform == 'win32':
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    _p = os.environ.get("PATH", "")
    _kept = os.pathsep.join(
        q for q in _p.split(os.pathsep)
        if q and os.path.abspath(q) != _exe_dir
    )
    if _kept != _p:
        os.environ["PATH"] = _kept

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetDefaultDllDirectories.restype = ctypes.c_bool
        kernel32.SetDefaultDllDirectories.argtypes = [ctypes.c_uint32]
        kernel32.SetDefaultDllDirectories(0x00001800)
    except Exception:
        pass

    try:
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    except Exception:
        pass

    # Путь к плагинам PyQt6
    _plugins_root = ''
    try:
        import PyQt6.QtCore as _qc
        _qt_core = os.path.dirname(os.path.abspath(_qc.__file__))
        for _cand in (os.path.join(_qt_core, 'Qt6', 'plugins'),
                      os.path.join(_qt_core, 'plugins')):
            if os.path.isdir(_cand):
                _plugins_root = _cand
                break
    except Exception:
        pass
    if not _plugins_root:
        _plugins_root = os.path.join(
            os.path.dirname(os.path.abspath(sys.executable)),
            'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins'
        )
    _plugin_dir = os.path.join(_plugins_root, 'platforms')
    if os.path.isdir(_plugin_dir):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugin_dir
    if os.path.isdir(_plugins_root):
        try:
            for _sub in os.listdir(_plugins_root):
                _p = os.path.join(_plugins_root, _sub)
                if os.path.isdir(_p):
                    os.add_dll_directory(_p)
        except Exception:
            pass

    # === ПРАВКА: bin/ ищется в _MEIPASS (onefile) или рядом с .exe (onedir) ===
    if getattr(sys, 'frozen', False):
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass and os.path.isdir(os.path.join(_meipass, 'bin')):
            _bin_dir = os.path.join(_meipass, 'bin')
        else:
            _bin_dir = os.path.join(os.path.dirname(sys.executable), 'bin')
    else:
        _bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
    if os.path.isdir(_bin_dir):
        try:
            os.add_dll_directory(_bin_dir)
        except Exception:
            pass

os.environ.setdefault("QT_STYLE_OVERRIDE", "Fusion")
os.environ.setdefault("QT_OPENGL", "software")

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    ctypes.windll.kernel32.SetErrorMode(0x0002 | 0x0004)
except Exception:
    pass

import logging

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

import utils.helpers
utils.helpers._logger_initialized = False

from PyQt6.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner


def main():
    # КРИТИЧНО для Windows + multiprocessing
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setApplicationName("BitcoinGPUCPUScanner")
    app.setOrganizationName("Jasst")

    from ui.frameless import style_app_popups, force_non_native_dialogs
    style_app_popups(app)
    force_non_native_dialogs()

    from utils.helpers import setup_logger
    logger = setup_logger()
    logger.info("=" * 50)
    logger.info("🚀 Запуск Bitcoin GPU/CPU Scanner")
    logger.info("=" * 50)

    # Изоляция PATH от CWD и папки интерпретатора на время show()
    _orig_path = os.environ.get("PATH", "")
    if sys.platform == 'win32':
        _excluded = {os.path.abspath('.').lower(),
                     os.path.dirname(os.path.abspath(sys.executable)).lower()}
        _cleaned = os.pathsep.join(
            p for p in _orig_path.split(os.pathsep)
            if p and os.path.abspath(p).lower() not in _excluded
        )
        os.environ["PATH"] = _cleaned

    try:
        window = BitcoinGPUCPUScanner()
        window.show()
    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        if sys.platform == 'win32':
            os.environ["PATH"] = _orig_path

    sys.exit(app.exec())


if __name__ == "__main__":
    main()