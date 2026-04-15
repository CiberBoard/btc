# main.py
# 🛡 Bitcoin GPU/CPU Scanner — точка входа

import sys
import os

# ═══════════════════════════════════════════════
# 🔧 НАСТРОЙКА ОКРУЖЕНИЯ (ДО ЛЮБЫХ ИМПОРТОВ)
# ═══════════════════════════════════════════════

# 🛡 Ограничиваем потоки для библиотек линейной алгебры (конфликты с multiprocessing)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Для Windows + Intel MKL

# 🛡 Подавляем системные диалоги ошибок Windows
if sys.platform == 'win32':
    try:
        import ctypes

        ctypes.windll.kernel32.SetErrorMode(0x0002 | 0x0004)  # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
    except Exception:
        pass

# 🛡 Включаем отладку падений на уровне ОС
import faulthandler

faulthandler.enable()
# 🛡 Корректное открытие файла с контекстным менеджером
_crash_log = open('crash.log', 'w', encoding='utf-8')
faulthandler.dump_traceback_later(timeout=10, repeat=False, file=_crash_log)

# 🔥 КРИТИЧНО: Устанавливаем метод запуска ДО любых импортов с multiprocessing
# Это должно быть ЕДИНСТВЕННОЕ место вызова set_start_method в проекте
if sys.platform == 'win32':
    import multiprocessing

    multiprocessing.set_start_method('spawn', force=True)

# ═══════════════════════════════════════════════
# 🔧 ИМПОРТЫ (ПОСЛЕ настройки окружения)
# ═══════════════════════════════════════════════

import logging
import multiprocessing  # уже импортирован выше для Windows, но безопасно импортировать снова

# 🔑 Очищаем handlers логгера ДО импорта наших модулей
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

from PyQt6.QtWidgets import QApplication


def main():
    """
    Основная функция запуска приложения.
    🛡 Все настройки multiprocessing уже выполнены в __main__ блоке.
    """
    # 🛡 freeze_support() для Windows — должен быть в __main__, не здесь!
    # Здесь только инициализация PyQt

    # ✅ Создаём QApplication ОДИН раз
    app = QApplication(sys.argv)
    app.setApplicationName("BitcoinGPUCPUScanner")
    app.setOrganizationName("Jasst")

    # 🛡 Сбрасываем флаг инициализации логгера (на случай повторного запуска)
    import utils.helpers
    utils.helpers._logger_initialized = False

    from ui.main_window import BitcoinGPUCPUScanner

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


# ═══════════════════════════════════════════════
# 🔥 ТОЧКА ВХОДА — ЗАЩИЩЕНА ДЛЯ WINDOWS + MULTIPROCESSING
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    # 🛡 freeze_support() ОБЯЗАТЕЛЕН здесь для Windows/PyInstaller
    multiprocessing.freeze_support()

    # ✅ Запускаем приложение
    main()

    # 🛡 Закрываем файл лога крашей при нормальном завершении
    try:
        _crash_log.close()
    except Exception:
        pass