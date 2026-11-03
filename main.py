# main.py
import faulthandler
import multiprocessing
import sys
import os

# 🔥 ДИАГНОСТИКА: код 0xC0000409 (STATUS_STACK_BUFFER_OVERRUN) — это падение
# внутри нативной библиотеки, а не ошибка Python. faulthandler печатает
# трейсбек Python-потоков прямо перед падением — по нему видно, какой модуль
# (какой импорт/вызов) стал причиной.
try:
    faulthandler.enable()
except Exception:
    pass

# 🔥 КРИТИЧНО: УСТАНАВЛИВАЕМ МЕТОД ЗАПУСКА ДО ВСЕГО ОСТАЛЬНОГО
if sys.platform == 'win32':
    multiprocessing.set_start_method('spawn', force=True)

# 🔥 КРИТИЧНО для Windows + PyQt6: защита от "Windows fatal exception: access
# violation" (код 0xC0000005) при window.show().
#
# Причина падения: Qt при создании окна вызывает LoadLibrary для своих плагинов
# (platforms\windows.dll, стили, imageformats и т.д.). Windows ИЩЕТ эти DLL, в
# том числе в текущей директории проекта, а в ней лежат чужие нативные библиотеки
# (cudart64_101.dll, VanitySearch/cuBitCrack и пр.). Если Qt подхватывает их —
# происходит обращение к неверной памяти и процесс падает с access violation
# ровно на строке show() (страница 93), без Python-трейсбека.
#
# Исправления:
#   1. os.add_dll_directory(путь к плагинам PyQt6) — добавляем ВСЕ подпапки
#      plugins (platforms, styles, imageformats...) в легальный путь поиска DLL.
#   2. Убираем текущую директорию проекта из PATH на время show(), чтобы Qt (и
#      любые ctypes/LoadLibrary) не могли загрузить наши CUDA-DLL вместо системных.
#
# Также: QT_STYLE_OVERRIDE=Fusion — не трогаем нативный стиль Windows,
# QT_OPENGL=software — не дёргаем видеодрайвер OpenGL.
if sys.platform == 'win32':
    _plugins_root = os.path.join(
        os.path.dirname(os.path.abspath(sys.executable)),
        'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins'
    )
    _plugin_dir = os.path.join(_plugins_root, 'platforms')
    if os.path.isdir(_plugin_dir):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugin_dir
    # Регистрируем все подпапки plugins как легальные пути поиска DLL (Win 3.8+)
    if os.path.isdir(_plugins_root):
        try:
            for _sub in os.listdir(_plugins_root):
                _p = os.path.join(_plugins_root, _sub)
                if os.path.isdir(_p):
                    os.add_dll_directory(_p)
        except Exception:
            pass

os.environ.setdefault("QT_STYLE_OVERRIDE", "Fusion")
os.environ.setdefault("QT_OPENGL", "software")

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Для Windows + Intel MKL
import ctypes
try:
    ctypes.windll.kernel32.SetErrorMode(0x0002 | 0x0004)  # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
except:
    pass

import logging

# 🔑 КРИТИЧНО: Очищаем ВСЕ handlers ДО импорта наших модулей
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Сбрасываем флаг инициализации логгера (на случай повторного запуска)
import utils.helpers
utils.helpers._logger_initialized = False

from PyQt6.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner



def main():
    # 🔑 КРИТИЧНО для Windows с multiprocessing!
    multiprocessing.freeze_support()

    # ✅ Создаём QApplication ОДИН раз
    app = QApplication(sys.argv)
    app.setApplicationName("BitcoinGPUCPUScanner")
    app.setOrganizationName("Jasst")

    # 🪟 Единый стиль всех окон и попапов (QMessageBox/QFileDialog/QMenu):
    #    Fusion + тёмная тема вместо белых нативных окон Windows.
    from ui.frameless import style_app_popups, force_non_native_dialogs
    style_app_popups(app)
    force_non_native_dialogs()

    # ✅ Инициализируем логгер ТОЛЬКО ЗДЕСЬ (перед созданием окна)
    from utils.helpers import setup_logger
    logger = setup_logger()
    logger.info("=" * 50)
    logger.info("🚀 Запуск Bitcoin GPU/CPU Scanner")
    logger.info("=" * 50)

    # ✅ Создаём ОДНО окно
    # 🔥 На Windows изолируем текущую директорию проекта от поиска DLL:
    # временно убираем '' и папку проекта из PATH, чтобы Qt при show() не
    # подхватил cudart64_101.dll / чужие нативные DLL из папки проекта
    # (это и даёт access violation 0xC0000005). После show() — восстанавливаем.
    _orig_path = os.environ.get("PATH", "")
    if sys.platform == 'win32':
        _proj_dir = os.path.abspath('.')
        _cleaned = os.pathsep.join(
            p for p in _orig_path.split(os.pathsep)
            if p and os.path.abspath(p) != _proj_dir
        )
        os.environ["PATH"] = _cleaned

    try:
        window = BitcoinGPUCPUScanner()
        window.show()
    finally:
        if sys.platform == 'win32':
            os.environ["PATH"] = _orig_path

    # ✅ Запускаем цикл ОДИН раз
    sys.exit(app.exec())


if __name__ == "__main__":
    main()