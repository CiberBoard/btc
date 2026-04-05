# main.py
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



import logging

# 🔑 КРИТИЧНО: Очищаем ВСЕ handlers ДО импорта наших модулей
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Сбрасываем флаг инициализации логгера (на случай повторного запуска)
import utils.helpers

utils.helpers._logger_initialized = False

from PyQt5.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner
import multiprocessing


def main():
    # 🔑 КРИТИЧНО для Windows с multiprocessing!
    multiprocessing.freeze_support()

    # ✅ Создаём QApplication ОДИН раз
    app = QApplication(sys.argv)
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
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()