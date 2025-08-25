# utils/helpers.py
import os
import hashlib
import base58
import logging
from logging.handlers import RotatingFileHandler
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import QRegExp
import config

# Кеш для хеш-функций
sha256 = hashlib.sha256
new_ripemd160 = lambda: hashlib.new('ripemd160')


# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def setup_logger():
    """Настройка расширенного логирования"""
    logger = logging.getLogger('bitcoin_scanner')
    logger.setLevel(logging.DEBUG)

    # Создаем папку для логов, если ее нет
    log_dir = os.path.join(config.BASE_DIR, 'logs')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"Ошибка создания папки логов: {str(e)}")
        return logger

    # Файловый обработчик с ротацией
    log_file = config.LOG_FILE
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Ошибка создания лог-файла: {str(e)}")

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def make_combo32(start, end, default=None):
    """Создает выпадающий список с шагом 32"""
    items = [str(x) for x in range(start, end + 1, 32)]
    cb = QComboBox()
    cb.addItems(items)
    if default and str(default) in items:
        cb.setCurrentText(str(default))
    return cb


def private_key_to_wif(private_key_hex):
    """Конвертирует HEX-ключ в WIF формат"""
    try:
        extended_key = b'\x80' + bytes.fromhex(private_key_hex)
        first_sha = sha256(extended_key).digest()
        checksum = sha256(first_sha).digest()[:4]
        return base58.b58encode(extended_key + checksum).decode()
    except Exception as e:
        print(f"Ошибка конвертации в WIF: {str(e)}")
        return "Ошибка конвертации"


def _generate_p2pkh(pub_ripemd):
    """Генерирует P2PKH адрес"""
    prefixed = b'\x00' + pub_ripemd
    first_sha = sha256(prefixed).digest()
    checksum = sha256(first_sha).digest()[:4]
    return base58.b58encode(prefixed + checksum).decode()


def _generate_p2sh(pub_ripemd):
    """Генерирует P2SH адрес"""
    prefixed = b'\x05' + pub_ripemd
    first_sha = sha256(prefixed).digest()
    checksum = sha256(first_sha).digest()[:4]
    return base58.b58encode(prefixed + checksum).decode()


def safe_queue_put(q, message, timeout=0.1):
    """Безопасное добавление в multiprocessing.Queue"""
    try:
        if q is None:
            return False
        q.put(message, timeout=timeout)
        return True
    except (BrokenPipeError, EOFError, OSError) as e:
        print(f"Ошибка записи в очередь: {str(e)}")
        return False
    except Exception as e:
        print(f"Неизвестная ошибка очереди: {str(e)}")
        return False


def validate_key_range(start_hex, end_hex):
    """Проверяет и нормализует диапазон ключей"""
    try:
        start_int = int(start_hex, 16)
        end_int = int(end_hex, 16)
        if start_int <= 0:
            return None, "Начальный ключ должен быть больше 0"
        if end_int > config.MAX_KEY:
            return None, f"Конечный ключ превышает максимальный ({config.MAX_KEY_HEX})"
        if start_int > end_int:
            return None, "Начальный ключ должен быть меньше или равен конечному"
        total_keys = end_int - start_int + 1
        if total_keys <= 0:
            return None, "Недопустимый диапазон ключей"
        return (start_int, end_int, total_keys), None
    except ValueError:
        return None, "Неверный формат ключей (hex)"


def format_time(seconds):
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


def is_coincurve_available():
    try:
        from coincurve import PrivateKey
        return True
    except ImportError:
        return False


# ============== НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С HEX ==============
def hex_to_int(h):
    """Преобразует hex-строку в целое число"""
    return int(h.strip(), 16)


def int_to_hex(x):
    """Преобразует целое число в hex-строку (64 символа, с ведущими нулями)"""
    return f"{x:064x}"