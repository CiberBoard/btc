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

# 🔥 КРИТИЧНО для Windows + PyQt6 + pyqtgraph/numpy:
# Падение с Fatal Python error: Aborted на строке создания окна означает,
# что Qt аварийно завершил процесс при инициализации GUI-плагина/стиля или
# аппаратного OpenGL (Qt использует LoadLibrary по системному пути и может
# подхватить чужую DLL из PATH — например cudart64_101.dll из папки проекта,
# что даёт fastfail/abort без трейсбека).
# Решения (переменные задаются ДО импорта модулей PyQt6):
#   1. QT_QPA_PLATFORM_PLUGIN_PATH — грузим плагин windows только из venv,
#      перекрывая поиск по PATH.
#   2. QT_STYLE_OVERRIDE=Fusion — не трогаем нативный стиль Windows.
#   3. QT_OPENGL=software — не дёргаем видеодрайвер OpenGL вообще.
if sys.platform == 'win32':
    _plugin_dir = os.path.join(
        os.path.dirname(os.path.abspath(sys.executable)),
        'Lib', 'site-packages', 'PyQt6', 'Qt6', 'plugins', 'platforms'
    )
    if os.path.isdir(_plugin_dir):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugin_dir

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
    window = BitcoinGPUCPUScanner()
    window.show()

    # ✅ Запускаем цикл ОДИН раз
    sys.exit(app.exec())


if __name__ == "__main__":
    main()