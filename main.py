# main.py

import multiprocessing
import faulthandler
faulthandler.enable()
faulthandler.dump_traceback_later(
    timeout=10,
    repeat=False,
    file=open('crash.log', 'w', encoding='utf-8')
)
import sys
import os
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
# 🔥 КРИТИЧНО: Должно быть ПЕРЕД любым импортом coincurve!
if sys.platform == 'win32':
    multiprocessing.set_start_method('spawn', force=True)


import logging

# 🔑 КРИТИЧНО: Очищаем ВСЕ handlers ДО импорта наших модулей
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


from PyQt6.QtWidgets import QApplication




def main():
    if sys.platform == 'win32':
        multiprocessing.set_start_method('spawn', force=True)
    # 🔑 КРИТИЧНО для Windows с multiprocessing!

    # 🛡 Увеличьте лимит дескрипторов для множества процессов
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetErrorMode(0x0002 | 0x0004)
        except:
            pass
    multiprocessing.freeze_support()


    # ✅ Создаём QApplication ОДИН раз
    app = QApplication(sys.argv)

    # Сбрасываем флаг инициализации логгера (на случай повторного запуска)
    import utils.helpers

    utils.helpers._logger_initialized = False
    from ui.main_window import BitcoinGPUCPUScanner
    app.setApplicationName("BitcoinGPUCPUScanner")
    app.setOrganizationName("Jasst")

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