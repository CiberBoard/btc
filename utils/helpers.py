# utils/helpers.py
import os
import hashlib
import base58
import logging
from logging.handlers import RotatingFileHandler

from typing import Tuple, Optional
import config

# 🔑 ГЛОБАЛЬНЫЙ ФЛАГ — предотвращает повторную инициализацию
_logger_initialized = False

# Создаём логгер (но НЕ настраиваем handlers здесь!)
logger = logging.getLogger('bitcoin_scanner')

# Кеш для хеш-функций
sha256 = hashlib.sha256
new_ripemd160 = lambda: hashlib.new('ripemd160')


def setup_logger(name: str = 'bitcoin_scanner', level: int = logging.DEBUG) -> logging.Logger:
    """
    Настройка расширенного логирования с защитой от дублирования handlers.
    Вызывается ТОЛЬКО ОДИН РАЗ при старте приложения (в main.py).
    """
    global _logger_initialized

    logger = logging.getLogger(name)

    # ✅ ЕСЛИ УЖЕ ИНИЦИАЛИЗИРОВАН — возвращаем существующий
    if _logger_initialized:
        return logger

    # ✅ Очищаем ВСЕ существующие handlers
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False  # 🔑 Важно: не передавать сообщения родительским логгерам

    # Создаем папку для логов, если ее нет
    log_dir = os.path.join(config.BASE_DIR, 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"Ошибка создания папки логов: {str(e)}")
        _logger_initialized = True
        return logger

    # Файловый обработчик с ротацией
    log_file = config.LOG_FILE
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8',
            delay=True
        )
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Ошибка создания лог-файла: {str(e)}")

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 🔑 Помечаем как инициализированный
    _logger_initialized = True

    return logger


def reset_logger() -> None:
    """Сбрасывает флаг инициализации (для тестирования)"""
    global _logger_initialized
    _logger_initialized = False
    logger.handlers.clear()


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def make_combo32(start: int, end: int, default: int = None) -> 'QComboBox':
    from PyQt6.QtWidgets import QComboBox
    from PyQt6.QtCore import QCoreApplication

    # ✅ Проверка: есть ли активное QApplication
    if not QCoreApplication.instance():
        # Возвращаем заглушку или выбрасываем понятную ошибку
        raise RuntimeError("make_combo32() вызван до создания QApplication")

    items = [str(x) for x in range(start, end + 1, 32)]
    cb = QComboBox()
    cb.addItems(items)
    if default and str(default) in items:
        cb.setCurrentText(str(default))
    return cb


def private_key_to_wif(private_key_hex: str) -> str:
    """Конвертирует HEX-ключ в WIF формат"""
    try:
        extended_key = b'\x80' + bytes.fromhex(private_key_hex)
        first_sha = sha256(extended_key).digest()
        checksum = sha256(first_sha).digest()[:4]
        return base58.b58encode(extended_key + checksum).decode()
    except Exception as e:
        logger.error(f"Ошибка конвертации в WIF: {str(e)}")
        return "Ошибка конвертации"


def _generate_p2pkh(pub_ripemd: bytes) -> str:
    """Генерирует P2PKH адрес"""
    prefixed = b'\x00' + pub_ripemd
    first_sha = sha256(prefixed).digest()
    checksum = sha256(first_sha).digest()[:4]
    return base58.b58encode(prefixed + checksum).decode()


def _generate_p2sh(pub_ripemd: bytes) -> str:
    """Генерирует P2SH адрес"""
    prefixed = b'\x05' + pub_ripemd
    first_sha = sha256(prefixed).digest()
    checksum = sha256(first_sha).digest()[:4]
    return base58.b58encode(prefixed + checksum).decode()


def safe_queue_put(q, message, timeout: float = 0.1) -> bool:
    """Безопасное добавление в multiprocessing.Queue"""
    try:
        if q is None:
            return False
        q.put(message, timeout=timeout)
        return True
    except (BrokenPipeError, EOFError, OSError) as e:
        logger.error(f"Ошибка записи в очередь: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Неизвестная ошибка очереди: {str(e)}")
        return False


def validate_key_range(start_hex: str, end_hex: str) -> Tuple[Optional[Tuple[int, int, int]], Optional[str]]:
    """
    Валидация диапазона ключей.
    Возвращает (start_int, end_int, total_keys) или (None, error)
    """
    try:
        start_int = int(start_hex, 16)
        end_int = int(end_hex, 16)

        if start_int <= 0:
            return None, "Начальный ключ должен быть > 0"
        if end_int > config.MAX_KEY:
            return None, f"Конечный ключ > MAX_KEY ({config.MAX_KEY_HEX})"
        if start_int > end_int:
            return None, "Начальный ключ > конечного"

        total_keys = end_int - start_int + 1
        if total_keys <= 0:
            return None, "Диапазон переполнен или пуст"

        logger.debug(
            f"validate_key_range: [{start_hex} → {hex(start_int)}] ... [{end_hex} → {hex(end_int)}], total={total_keys}")

        return (start_int, end_int, total_keys), None

    except ValueError as e:
        return None, f"Некорректный hex: {e}"
    except Exception as e:
        return None, f"Ошибка валидации: {e}"


def format_time(seconds: float) -> str:
    """Форматирует время в читаемый вид"""
    if seconds < 60:
        return f"{seconds:.1f} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин {seconds % 60:.0f} сек"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} час {minutes} мин"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days} дн {hours} час"


def is_coincurve_available() -> bool:
    """Проверяет доступность библиотеки coincurve"""
    try:
        from coincurve import PrivateKey
        return True
    except ImportError:
        return False


def hex_to_int(h: str) -> int:
    """Преобразует hex-строку в целое число"""
    return int(h.strip(), 16)


def int_to_hex(x: int) -> str:
    """Преобразует целое число в hex-строку (64 символа)"""
    return f"{x:064x}"