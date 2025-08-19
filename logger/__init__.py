# logger/__init__.py
import logging
import logging.config
import sys
import os

def setup_logger():
    logger = None
    try:
        # --- PyInstaller friendly path resolution ---
        if getattr(sys, 'frozen', False):
            # Если запущено из .exe, created by PyInstaller
            # Файл будет в папке logger внутри временной директории _MEIxxxx
            bundle_dir = sys._MEIPASS
            config_path = os.path.join(bundle_dir, 'logger', 'logging.conf')
        else:
            # Если запущено как обычный скрипт
            # Предполагаем, что __init__.py и logging.conf в одной папке logger
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'logging.conf') # Прямой путь

        # Проверка существования файла (полезно для отладки)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Logger config file not found at: {config_path}")

        logging.config.fileConfig(config_path, disable_existing_loggers=False)
        logger = logging.getLogger(__name__) # Или конкретное имя, например, 'app'
        logger.debug("Logger configured using file: %s", config_path)
    except Exception as e:
        # Fallback: базовая настройка логгера, если файл конфигурации не найден
        print(f"Warning: Could not load logging.conf: {e}. Using basic config.")
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        logger.warning("Logger initialized with basic config due to error loading fileConfig.")

    return logger

# Вызов функции для настройки логгера при импорте модуля
logger = setup_logger()