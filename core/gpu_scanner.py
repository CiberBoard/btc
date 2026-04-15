# core/gpu_scanner.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations

import subprocess
import time
import random
import platform
import logging
import atexit
import secrets
from typing import Tuple, Optional, Dict, Any, Set, List, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:  # 🛠 УЛУЧШЕНИЕ 2: Избегаем циклических импортов для type hints
    import pynvml  # type: ignore

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None
    logging.getLogger('bitcoin_scanner').warning("pynvml не найден. Мониторинг GPU будет недоступен.")

try:
    import win32process
    import win32api

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

import config
from utils.helpers import validate_key_range, private_key_to_wif

# 🛠 УЛУЧШЕНИЕ 3: Инициализация логгера в начале модуля
logger = logging.getLogger('bitcoin_scanner')


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 4: dataclass для конфигурации GPU сканера с типизацией
@dataclass(frozen=True)
class GPUScannerConfig:
    """Конфигурация параметров GPU сканера"""
    # Тайминги
    READER_SLEEP_SEC: float = 0.01
    PROCESS_WAIT_TIMEOUT_SEC: int = 3
    READER_WAIT_TIMEOUT_MS: int = 3000

    # Буферизация
    READ_CHUNK_SIZE: int = 1024

    # Генерация диапазонов
    MAX_RETRY_ATTEMPTS: int = 500
    MAX_SAVED_RANGES_DEFAULT: int = 100

    # Приоритеты процессов
    DEFAULT_PRIORITY_CLASS: int = 0x00000020  # NORMAL_PRIORITY_CLASS

    # NVML
    NVML_TEMPERATURE_SENSOR: int = 0  # NVML_TEMPERATURE_GPU


# 🛠 УЛУЧШЕНИЕ 5: Глобальный экземпляр конфигурации
SCANNER_CONFIG: GPUScannerConfig = GPUScannerConfig()

# 🛠 УЛУЧШЕНИЕ 6: Константы статусов с аннотациями
GPU_STATUS_INITIALIZED: bool = False

# 🛠 УЛУЧШЕНИЕ 7: Компактные константы для приоритетов (для удобства)
CREATE_NEW_PROCESS_GROUP_FLAG: int = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess,
                                                                                    'CREATE_NEW_PROCESS_GROUP') else 0

# ═══════════════════════════════════════════════
# 🔧 NVML SHUTDOWN HANDLER
# ═══════════════════════════════════════════════

# 🔹 ДОБАВЛЕНО: корректный shutdown NVML
if PYNVML_AVAILABLE:
    def _shutdown_nvml() -> None:  # 🛠 УЛУЧШЕНИЕ 8: Явный возврат None
        """Корректное завершение NVML при выходе из программы."""
        global GPU_STATUS_INITIALIZED
        if GPU_STATUS_INITIALIZED:
            try:
                pynvml.nvmlShutdown()
                GPU_STATUS_INITIALIZED = False
                logger.debug("NVML shutdown completed")
            except Exception as e:
                logger.warning(f"NVML shutdown error: {e}")


    # atexit.register(_shutdown_nvml)  # 👈 ЗАКОММЕНТИРОВАТЬ


# ═══════════════════════════════════════════════
# 🔧 OPTIMIZED OUTPUT READER
# ═══════════════════════════════════════════════

class OptimizedOutputReader(QThread):
    """
    Поток для чтения и парсинга вывода GPU процесса.

    🛠 УЛУЧШЕНИЕ 9: Атрибуты класса с аннотациями типов
    """

    # 🛠 УЛУЧШЕНИЕ 10: Явные аннотации для сигналов
    log_message = pyqtSignal(str, str)  # message, level
    stats_update = pyqtSignal(dict)  # {'speed': float, 'checked': int}
    found_key = pyqtSignal(dict)  # key_data dict
    process_finished = pyqtSignal()

    # 🛠 УЛУЧШЕНИЕ 11: Атрибуты с аннотациями
    process: Optional[subprocess.Popen]
    current_address: Optional[str]
    current_private_key: Optional[str]
    last_speed: float
    last_checked: int
    _running: bool

    def __init__(self, process: subprocess.Popen, parent: Optional[Any] = None):
        """
        Инициализация читателя вывода.

        :param process: subprocess.Popen экземпляр GPU процесса
        :param parent: Родительский объект QObject (опционально)
        """
        super().__init__(parent)
        self.process = process
        self.current_address = None
        self.current_private_key = None
        self.last_speed = 0.0
        self.last_checked = 0
        self._running = True

    def run(self) -> None:  # 🛠 УЛУЧШЕНИЕ 12: Явный возврат None
        """Основной цикл чтения вывода процесса."""
        buffer = ""
        try:
            while self._running and self.process and self.process.poll() is None:
                chunk = self._read_process_output()
                if chunk:
                    buffer = self._process_buffer(buffer + chunk)
                # 🛠 УЛУЧШЕНИЕ 13: Используем константу для задержки
                time.sleep(SCANNER_CONFIG.READER_SLEEP_SEC)

            # Обработка оставшегося буфера
            if buffer.strip():
                self._process_remaining_buffer(buffer)

        except Exception as e:
            logger.exception("Ошибка чтения вывода GPU")
            self.log_message.emit(f"Ошибка чтения вывода: {type(e).__name__}: {str(e)}", "error")
        finally:
            self.process_finished.emit()

    def _read_process_output(self) -> str:
        """
        Чтение данных из stdout процесса.

        :return: Прочитанная строка или пустая строка при ошибке
        """
        try:
            # 🛠 УЛУЧШЕНИЕ 14: Используем константу для размера чанка
            return self.process.stdout.read(SCANNER_CONFIG.READ_CHUNK_SIZE) or "" if self.process.stdout else ""
        except (AttributeError, OSError, ValueError) as e:
            logger.debug(f"Ошибка чтения stdout: {e}")
            return ""
        except Exception as e:
            logger.warning(f"Неожиданная ошибка чтения stdout: {e}")
            return ""

    def _process_buffer(self, buffer: str) -> str:
        """
        Обработка буфера вывода: разделение на строки и обработка полных строк.

        :param buffer: Буфер с данными
        :return: Оставшаяся неполная строка для следующего цикла
        """
        lines = buffer.split('\n')
        remaining_buffer = lines[-1]

        for line in lines[:-1]:
            if line.strip():
                self.process_line(line.strip())

        return remaining_buffer

    def _process_remaining_buffer(self, buffer: str) -> None:
        """
        Обработка оставшегося буфера при завершении чтения.

        :param buffer: Оставшиеся данные для обработки
        """
        for line in buffer.strip().split('\n'):
            if line.strip():
                self.process_line(line.strip())

    def process_line(self, line: str) -> None:
        """
        Обработка строки вывода GPU.

        :param line: Строка вывода для обработки
        """
        if not line.strip():
            return

        line_lower = line.lower()

        # Определение типа сообщения
        if self._is_error_message(line_lower):
            self._handle_error_message(line)
        elif self._is_found_key_message(line_lower):
            self._handle_found_key_message(line)
        else:
            self._handle_normal_message(line)

        # Обработка статистики и найденных ключей
        self._process_statistics(line)
        self._process_key_finding(line)

    def _is_error_message(self, line_lower: str) -> bool:
        """
        Проверка, является ли сообщение ошибкой.

        :param line_lower: Строка в нижнем регистре
        :return: True если сообщение об ошибке
        """
        return "ошибка" in line_lower or "error" in line_lower

    def _is_found_key_message(self, line_lower: str) -> bool:
        """
        Проверка, содержит ли сообщение информацию о найденном ключе.

        :param line_lower: Строка в нижнем регистре
        :return: True если сообщение о найденном ключе
        """
        return "найден ключ" in line_lower or "found key" in line_lower

    def _handle_error_message(self, line: str) -> None:
        """
        Обработка сообщения об ошибке.

        :param line: Строка сообщения об ошибке
        """
        self.log_message.emit(line, "error")
        logger.error(f"GPU Error: {line}")

    def _handle_found_key_message(self, line: str) -> None:
        """
        Обработка сообщения о найденном ключе.

        :param line: Строка сообщения о найденном ключе
        """
        self.log_message.emit(line, "success")
        logger.info(f"GPU Key Found: {line}")

    def _handle_normal_message(self, line: str) -> None:
        """
        Обработка обычного сообщения.

        :param line: Строка обычного сообщения
        """
        self.log_message.emit(line, "normal")
        logger.debug(f"GPU Output: {line}")

    def _process_statistics(self, line: str) -> None:
        """
        Обработка статистики из строки вывода.

        :param line: Строка для парсинга статистики
        """
        speed_match = config.SPEED_REGEX.search(line)
        total_match = config.TOTAL_REGEX.search(line)

        if speed_match or total_match:
            speed = float(speed_match.group(1)) if speed_match else self.last_speed
            checked = int(total_match.group(1).replace(',', '')) if total_match else self.last_checked

            # Сохраняем последние значения
            if speed_match:
                self.last_speed = speed
            if total_match:
                self.last_checked = checked

            self.stats_update.emit({'speed': speed, 'checked': checked})

    def _process_key_finding(self, line: str) -> None:
        """
        Обработка нахождения адреса и ключа.

        :param line: Строка для парсинга ключей
        """
        addr_match = config.ADDR_REGEX.search(line)
        if addr_match:
            self.current_address = addr_match.group(1)

        key_match = config.KEY_REGEX.search(line)
        if key_match:
            self.current_private_key = key_match.group(1)

        if self.current_address and self.current_private_key:
            self.process_found_key()

    def process_found_key(self) -> None:
        """Обработка найденного ключа с генерацией данных для UI."""
        try:
            if not self.current_private_key:
                return

            wif_key = private_key_to_wif(self.current_private_key)
            found_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'address': self.current_address,
                'hex_key': self.current_private_key,
                'wif_key': wif_key,
                'source': 'GPU'
            }
            self.found_key.emit(found_data)
            self.log_message.emit(f"🔑 НАЙДЕН КЛЮЧ! Адрес: {self.current_address}", "success")

            # Сброс текущих значений
            self.current_address = None
            self.current_private_key = None

        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.log_message.emit(f"Ошибка обработки найденного ключа: {type(e).__name__}: {str(e)}", "error")

    def stop(self) -> None:
        """Остановка чтения вывода."""
        self._running = False


# ═══════════════════════════════════════════════
# 🔧 ЗАПУСК ПОИСКА
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 15: Типизация возвращаемого значения
def start_gpu_search_with_range(
        target_address: str,
        start_key: int,
        end_key: int,
        device: int,
        blocks: int,
        threads: int,
        points: int,
        priority_index: int,
        parent_window: Any,
        use_compressed: bool = True
) -> Tuple[Optional[subprocess.Popen], Optional[OptimizedOutputReader]]:
    """
    Запускает GPU поиск с указанным диапазоном.

    :param target_address: Целевой биткоин-адрес для поиска
    :param start_key: Начало диапазона приватных ключей (целое число)
    :param end_key: Конец диапазона приватных ключей (целое число)
    :param device: ID GPU устройства
    :param blocks: Количество блоков для cuBitcrack
    :param threads: Количество потоков на блок
    :param points: Количество точек
    :param priority_index: Индекс приоритета процесса
    :param parent_window: Родительское окно для связи (любой тип)
    :param use_compressed: Флаг использования сжатых публичных ключей
    :return: Кортеж (процесс, читатель) или (None, None) при ошибке
    """
    logger.info(f"Запуск GPU поиска для диапазона {hex(start_key)} - {hex(end_key)} на устройстве {device} "
                f"(compressed={use_compressed})")

    # 🔹 1. СНАЧАЛА — базовая команда
    cmd = [
        config.CUBITCRACK_EXE,
        "-d", str(device),
        "-b", str(blocks),
        "-t", str(threads),
        "-p", str(points),
        "--keyspace", f"{hex(start_key)[2:].upper()}:{hex(end_key)[2:].upper()}",
    ]

    # 🔹 2. ЗАТЕМ — добавление -c
    if use_compressed and target_address.startswith(('1', '3', 'bc1')):
        cmd.append("-c")
        logger.debug("GPU: добавлен флаг -c (сжатые ключи)")
    elif use_compressed:
        logger.warning(f"GPU: адрес {target_address} не поддерживает -c, флаг пропущен")

    # 🔹 3. И ТОЛЬКО ПОСЛЕ — адрес
    cmd.append(target_address)

    creationflags = _get_process_creation_flags(priority_index)

    try:
        logger.debug(f"Команда запуска cuBitcrack: {' '.join(cmd)}")
        cuda_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=0,
            cwd=config.BASE_DIR,
            creationflags=creationflags
        )

        output_reader = OptimizedOutputReader(cuda_process)
        _set_windows_process_priority(cuda_process, priority_index)

        return cuda_process, output_reader

    except FileNotFoundError:
        logger.error(f"Файл cuBitcrack не найден: {config.CUBITCRACK_EXE}")
        return None, None
    except PermissionError:
        logger.error(f"Нет прав на запуск cuBitcrack: {config.CUBITCRACK_EXE}")
        return None, None
    except Exception as e:
        logger.exception(f"Ошибка запуска cuBitcrack на устройстве {device}")
        return None, None


def _get_process_creation_flags(priority_index: int) -> int:
    """
    Получение флагов создания процесса для платформы.

    :param priority_index: Индекс приоритета из конфигурации
    :return: Флаги creationflags для subprocess.Popen
    """
    if platform.system() != 'Windows':
        return 0

    # 🛠 УЛУЧШЕНИЕ 16: Используем константу для дефолтного приоритета
    priority_value = config.WINDOWS_GPU_PRIORITY_MAP.get(
        priority_index, SCANNER_CONFIG.DEFAULT_PRIORITY_CLASS
    )
    return CREATE_NEW_PROCESS_GROUP_FLAG | priority_value


def _set_windows_process_priority(process: subprocess.Popen, priority_index: int) -> None:
    """
    Установка приоритета процесса для Windows.
    :param process: Экземпляр subprocess.Popen
    :param priority_index: Индекс приоритета
    """
    if platform.system() != 'Windows' or not WIN32_AVAILABLE or priority_index <= 0:
        return

    handle = None  # 👈 Инициализируем для безопасного закрытия
    try:
        priority_value = config.WINDOWS_GPU_PRIORITY_MAP.get(
            priority_index, SCANNER_CONFIG.DEFAULT_PRIORITY_CLASS
        )
        handle = win32api.OpenProcess(win32process.PROCESS_ALL_ACCESS, True, process.pid)
        if handle:  # 👈 Проверяем, что хендл получен
            win32process.SetPriorityClass(handle, priority_value)
    except (OSError, AttributeError) as e:
        logger.debug(f"Не удалось установить приоритет процесса: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка установки приоритета: {e}")
    finally:
        # 👈 КРИТИЧНО: закрываем хендл в любом случае
        if handle is not None:
            try:
                win32api.CloseHandle(handle)
            except Exception as e:
                logger.debug(f"Не удалось закрыть хендл процесса: {e}")


# ═══════════════════════════════════════════════
# 🔧 ОСТАНОВКА ПОИСКА
# ═══════════════════════════════════════════════

def stop_gpu_search_internal(processes: List[Tuple[subprocess.Popen, OptimizedOutputReader]]) -> None:
    """
    Внутренняя остановка всех GPU процессов.

    :param processes: Список кортежей (процесс, читатель) для остановки
    """
    logger.info("Остановка GPU процессов...")

    for process, reader in processes:
        try:
            _stop_single_process(process, reader)
        except Exception as e:
            logger.warning(f"Ошибка остановки процесса: {type(e).__name__}: {str(e)}")

    processes.clear()
    logger.info("GPU процессы остановлены.")


def _stop_single_process(process: subprocess.Popen, reader: OptimizedOutputReader) -> None:
    """
    Остановка одного GPU процесса с ожиданием завершения потока.

    :param process: subprocess.Popen для остановки
    :param reader: OptimizedOutputReader для остановки
    """
    # 1. Запрашиваем остановку reader'а
    reader.stop()

    # 2. Мягкая остановка процесса
    try:
        process.terminate()
        # 🛠 УЛУЧШЕНИЕ 17: Используем константу для таймаута
        process.wait(timeout=SCANNER_CONFIG.PROCESS_WAIT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            # ← КРИТИЧНО: дожидаемся после kill()
            process.wait(timeout=SCANNER_CONFIG.PROCESS_WAIT_TIMEOUT_SEC)
        except (ProcessLookupError, OSError):
            # Процесс уже завершён
            pass
        except Exception as e:
            logger.debug(f"Ошибка при kill процесса: {e}")
    except (ProcessLookupError, OSError):
        # Процесс уже завершён
        pass
    except Exception as e:
        logger.debug(f"Неожиданная ошибка при terminate: {e}")

    # 3. Корректная остановка Qt-потока
    try:
        if reader.isRunning():
            reader.quit()
            # 🛠 УЛУЧШЕНИЕ 18: Используем константу для таймаута
            if not reader.wait(SCANNER_CONFIG.READER_WAIT_TIMEOUT_MS):
                reader.terminate()
                reader.wait(1000)
    except (AttributeError, RuntimeError) as e:
        logger.debug(f"Reader уже завершён: {e}")
    except Exception as e:
        logger.warning(f"Ошибка остановки reader'а: {e}")


# ═══════════════════════════════════════════════
# 🔧 ГЕНЕРАЦИЯ СЛУЧАЙНЫХ ДИАПАЗОНОВ
# ═══════════════════════════════════════════════

def generate_gpu_random_range(
        global_start_hex: str,
        global_end_hex: str,
        min_range_size_str: str,
        max_range_size_str: str,
        used_ranges: Set[str],
        max_saved_random: int
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Генерирует уникальный случайный диапазон в пределах пользовательского диапазона.

    :param global_start_hex: Начало глобального диапазона в HEX
    :param global_end_hex: Конец глобального диапазона в HEX
    :param min_range_size_str: Минимальный размер диапазона (строка)
    :param max_range_size_str: Максимальный размер диапазона (строка)
    :param used_ranges: Множество уже использованных диапазонов
    :param max_saved_random: Максимальное количество сохраняемых диапазонов
    :return: Кортеж (start_key, end_key, error_message)
    """
    try:
        # 🔹 Используем оригинальные hex-строки — validate_key_range сам обработает ведущие нули
        global_result, error = validate_key_range(global_start_hex, global_end_hex)
        if global_result is None:
            logger.error(f"Ошибка валидации диапазона после очистки: {error}")
            return None, None, error

        global_start, global_end, total_keys = global_result

        min_range_size, max_range_size, error = _validate_range_sizes(
            min_range_size_str, max_range_size_str, total_keys
        )
        if error:
            return None, None, error

        # 🔹 ЛОГИРОВАНИЕ для отладки
        logger.debug(f"GPU random: parsed range [{hex(global_start)} ... {hex(global_end)}], total_keys={total_keys}")

        start_key, end_key = _generate_unique_range(
            global_start, global_end, min_range_size, max_range_size,
            used_ranges, max_saved_random
        )

        # Сохранение использованного диапазона
        # 🛠 УЛУЧШЕНИЕ 19: hex без 0x — короче и эффективнее
        range_hash = f"{start_key:x}-{end_key:x}"
        used_ranges.add(range_hash)

        return start_key, end_key, None

    except Exception as e:
        error_msg = f"Ошибка генерации диапазона GPU: {type(e).__name__}: {str(e)}"
        logger.exception(error_msg)
        return None, None, error_msg


def _validate_range_sizes(
        min_range_size_str: str,
        max_range_size_str: str,
        total_keys: int
) -> Tuple[int, int, Optional[str]]:
    """
    Валидация и нормализация размеров диапазона.

    :param min_range_size_str: Минимальный размер (строка)
    :param max_range_size_str: Максимальный размер (строка)
    :param total_keys: Общее количество ключей в глобальном диапазоне
    :return: Кортеж (min_size, max_size, error_message)
    """
    try:
        min_range_size = int(min_range_size_str)
        max_range_size = int(max_range_size_str)
    except ValueError:
        return 0, 0, "Минимальный и максимальный диапазон должны быть числами"

    if min_range_size <= 0 or max_range_size <= 0:
        return 0, 0, "Размеры диапазона должны быть положительными числами"

    # Нормализация относительно общего количества ключей
    if min_range_size > total_keys:
        min_range_size = total_keys
    if max_range_size > total_keys:
        max_range_size = total_keys
    if min_range_size > max_range_size:
        min_range_size, max_range_size = max_range_size, min_range_size

    return min_range_size, max_range_size, None


def _generate_unique_range(
        global_start: int,
        global_end: int,
        min_range_size: int,
        max_range_size: int,
        used_ranges: Set[str],
        max_saved_random: int  # ✅ Этот параметр уже есть
) -> Tuple[int, int]:
    """
    Генерация уникального диапазона в пределах глобального.
    """
    range_size = random.randint(min_range_size, max_range_size)
    max_start = global_end - range_size + 1

    if max_start < global_start:
        max_start = global_start

    # 🛠 ИСПРАВЛЕНИЕ: передаём max_saved_random в _generate_range_with_retry
    start_key, end_key = _generate_range_with_retry(
        global_start, max_start, range_size, global_end,
        used_ranges, SCANNER_CONFIG.MAX_RETRY_ATTEMPTS, max_saved_random  # ✅ Добавлен третий аргумент
    )

    return start_key, end_key


def _generate_range_with_retry(
        global_start: int,
        max_start: int,
        range_size: int,
        global_end: int,
        used_ranges: Set[str],
        max_attempts: int,
        max_saved_random: int  # ✅ НОВЫЙ ПАРАМЕТР
) -> Tuple[int, int]:
    """
    Генерация диапазона с повторными попытками для уникальности.
    """
    for _ in range(max_attempts):
        start_key = _generate_random_start_key(global_start, max_start)
        end_key = start_key + range_size - 1

        if end_key > global_end:
            end_key = global_end

        range_hash = f"{start_key:x}-{end_key:x}"
        if range_hash not in used_ranges:
            return start_key, end_key

    # Если не удалось — очищаем историю и пробуем последний раз
    # 🛠 ИСПРАВЛЕНИЕ: теперь используем переданный параметр, а не глобальную переменную
    if len(used_ranges) >= max_saved_random:
        used_ranges.clear()

    # Генерируем последний диапазон
    start_key = _generate_random_start_key(global_start, max_start)
    end_key = min(start_key + range_size - 1, global_end)

    return start_key, end_key


def _generate_random_start_key(global_start: int, max_start: int) -> int:
    """
    Генерация случайной начальной точки диапазона.

    :param global_start: Минимальное значение
    :param max_start: Максимальное значение
    :return: Случайное целое число в диапазоне [global_start, max_start]
    """
    if platform.system() == 'Windows':
        return random.SystemRandom().randint(global_start, max_start)
    else:
        return _generate_secure_random_int(global_start, max_start)


# 🔹 БЕЗОПАСНАЯ ГЕНЕРАЦИЯ для больших чисел
# 🛠 УЛУЧШЕНИЕ 22: Типизация возвращаемого значения
def _generate_secure_random_int(min_val: int, max_val: int) -> int:
    """
    Генерирует криптографически стойкое случайное число в [min_val, max_val] (включительно).
    Работает с произвольно большими целыми (256 бит и более).

    :param min_val: Минимальное значение (включительно)
    :param max_val: Максимальное значение (включительно)
    :return: Случайное целое число в заданном диапазоне
    :raises ValueError: Если min_val > max_val
    """
    if min_val > max_val:
        raise ValueError("min_val must be <= max_val")
    if min_val == max_val:
        return min_val

    range_size = max_val - min_val + 1
    bits_needed = range_size.bit_length()

    while True:
        rand_int = secrets.randbits(bits_needed)
        if rand_int < range_size:
            return min_val + rand_int


# ═══════════════════════════════════════════════
# 🔧 ПОЛУЧЕНИЕ СТАТУСА GPU
# ═══════════════════════════════════════════════

def get_gpu_status(device_id: int = 0) -> Optional[Dict[str, Any]]:
    """
    Получает статус GPU (загрузка, память и т.д.) через pynvml.

    :param device_id: ID устройства GPU (по умолчанию 0)
    :return: dict с информацией о GPU или None при ошибке
    """
    global GPU_STATUS_INITIALIZED

    if not PYNVML_AVAILABLE:
        return None

    try:
        # Инициализация NVML (atexit позаботится о shutdown)
        if not GPU_STATUS_INITIALIZED:
            pynvml.nvmlInit()
            GPU_STATUS_INITIALIZED = True

        return _get_gpu_info(device_id)

    except pynvml.NVMLError_LibraryNotFound:  # type: ignore
        logger.debug("NVML библиотека не найдена")
        return None
    except pynvml.NVMLError_DriverNotLoaded:  # type: ignore
        logger.debug("NVML драйвер не загружен")
        return None
    except Exception as e:
        logger.debug(f"Не удалось получить статус GPU {device_id}: {type(e).__name__}: {e}")
        return None


def _get_gpu_info(device_id: int) -> Dict[str, Any]:
    """
    Получение детальной информации о GPU устройстве.

    :param device_id: ID устройства
    :return: Словарь с метриками GPU
    """
    handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)

    # Получаем утилизацию
    util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
    gpu_util = util_info.gpu

    # Получаем информацию о памяти
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    mem_used_mb = mem_info.used / (1024 * 1024)
    mem_total_mb = mem_info.total / (1024 * 1024)
    mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0

    # Получаем температуру
    temperature = _get_gpu_temperature(handle)

    return {
        'device_id': device_id,
        'gpu_utilization': gpu_util,
        'memory_used_mb': mem_used_mb,
        'memory_total_mb': mem_total_mb,
        'memory_utilization': mem_util,
        'temperature': temperature
    }


def _get_gpu_temperature(handle) -> Optional[int]:
    """
    Получение температуры GPU через NVML.

    :param handle: Handle устройства NVML
    :return: Температура в градусах Цельсия или None при ошибке
    """
    try:
        # 🛠 УЛУЧШЕНИЕ 23: Используем константу для типа сенсора
        return pynvml.nvmlDeviceGetTemperature(handle, SCANNER_CONFIG.NVML_TEMPERATURE_SENSOR)
    except (pynvml.NVMLError, AttributeError, OSError) as e:
        logger.debug(f"Не удалось получить температуру GPU: {e}")
        return None
    except Exception as e:
        logger.warning(f"Неожиданная ошибка при получении температуры: {e}")
        return None


# 🛠 УЛУЧШЕНИЕ 24: Явный экспорт публичного API модуля
__all__ = [
    'GPUScannerConfig',
    'SCANNER_CONFIG',
    'GPU_STATUS_INITIALIZED',
    'OptimizedOutputReader',
    'start_gpu_search_with_range',
    'stop_gpu_search_internal',
    'generate_gpu_random_range',
    'get_gpu_status',
]