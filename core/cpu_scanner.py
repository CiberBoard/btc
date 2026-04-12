# cpu_logic.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations

import multiprocessing
import random
import time
import logging
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field  # 🛠 УЛУЧШЕНИЕ 2: dataclass для конфигурации
from PyQt5.QtCore import QObject, pyqtSignal

try:
    from coincurve import PrivateKey

    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False
    PrivateKey = None  # 🛠 УЛУЧШЕНИЕ 3: Явное присваивание для безопасных проверок

import config
from utils.helpers import private_key_to_wif, _generate_p2pkh, _generate_p2sh, safe_queue_put
import utils.helpers as helpers

logger = logging.getLogger('bitcoin_scanner')


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 4: dataclass для конфигурации воркера с типизацией
@dataclass(frozen=True)
class WorkerConfig:
    """Конфигурация параметров CPU воркера"""
    BATCH_SIZE: int = 500
    STATS_INTERVAL: float = 0.5
    QUEUE_TIMEOUT: float = 0.1
    STOP_TIMEOUT: float = 3.0
    JOIN_TIMEOUT: float = 0.5
    MIN_PRIVATE_KEY: int = 1
    MAX_PRIVATE_KEY: int = config.MAX_KEY  # type: ignore
    KEY_BYTES: int = 32
    COMPRESSED_PUBKEY: bool = True


# 🛠 УЛУЧШЕНИЕ 5: Глобальный экземпляр конфигурации
WORKER_CONFIG: WorkerConfig = WorkerConfig()

# 🛠 УЛУЧШЕНИЕ 6: Константы для типов адресов с аннотациями
ADDR_TYPE_P2PKH: str = 'p2pkh'
ADDR_TYPE_P2SH: str = 'p2sh'
ADDR_PREFIX_P2PKH: str = '1'
ADDR_PREFIX_P2SH: str = '3'

# 🛠 УЛУЧШЕНИЕ 7: Кеш для хеш-функций с явной типизацией
sha256_cache: Callable[[], hashlib._Hash] = helpers.sha256  # type: ignore
ripemd160_cache: Callable[[], hashlib._Hash] = helpers.new_ripemd160  # type: ignore


class WorkerSignals(QObject):
    """Сигналы для CPU воркеров"""
    # 🛠 УЛУЧШЕНИЕ 8: Явные аннотации для сигналов (документация)
    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    found_key = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)


# ═══════════════════════════════════════════════
# 🔧 ФАБРИКИ СООБЩЕНИЙ
# ═══════════════════════════════════════════════

def create_found_message(
        address: str,
        hex_key: str,
        wif_key: str,
        worker_id: int
) -> Dict[str, Any]:
    """
    Создание сообщения о найденном ключе.

    :param address: Найденный биткоин-адрес
    :param hex_key: Приватный ключ в HEX формате
    :param wif_key: Приватный ключ в WIF формате
    :param worker_id: ID воркера, нашедшего ключ
    :return: Словарь с данными для отправки в очередь
    """
    return {
        "type": "found",
        "address": address,
        "hex_key": hex_key,
        "wif_key": wif_key,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "worker_id": worker_id,
        "source": "CPU"
    }


def create_stats_message(
        scanned: int,
        found: int,
        speed: float,
        progress: int,
        worker_id: int
) -> Dict[str, Any]:
    """
    Создание сообщения со статистикой.

    :param scanned: Количество проверенных ключей
    :param found: Количество найденных ключей
    :param speed: Скорость сканирования (keys/sec)
    :param progress: Прогресс в процентах (0-100)
    :param worker_id: ID воркера
    :return: Словарь со статистикой для отправки в очередь
    """
    return {
        "type": "stats",
        "scanned": scanned,
        "found": found,
        "speed": speed,
        "progress": progress,
        "worker_id": worker_id,
        "timestamp": time.time()
    }


def create_log_message(message: str) -> Dict[str, str]:
    """
    Создание лог-сообщения.

    :param message: Текст сообщения
    :return: Словарь с логом для отправки в очередь
    """
    return {"type": "log", "message": message}


# ═══════════════════════════════════════════════
# 🔐 ADDRESS GENERATOR
# ═══════════════════════════════════════════════

class AddressGenerator:
    """
    Оптимизированная генерация адресов с предкомпиляцией.

    🛠 УЛУЧШЕНИЕ 9: Атрибуты класса с аннотациями типов
    """

    target_prefix: str
    addr_type: Optional[str]
    prefix_length: int
    target_chars: str
    _fast_sha256: Callable
    _fast_ripemd160: Callable

    def __init__(self, target_prefix: str):
        self.target_prefix = target_prefix
        self.addr_type = self._determine_address_type(target_prefix)
        self.prefix_length = len(target_prefix)
        self.target_chars = target_prefix

        # Предкомпилированные функции для ускорения
        self._fast_sha256 = hashlib.sha256
        self._fast_ripemd160 = ripemd160_cache

    def _determine_address_type(self, prefix: str) -> Optional[str]:
        """
        Определение типа адреса по префиксу.

        :param prefix: Префикс адреса для определения типа
        :return: Тип адреса (p2pkh/p2sh) или None
        """
        if prefix.startswith(ADDR_PREFIX_P2PKH):
            return ADDR_TYPE_P2PKH
        elif prefix.startswith(ADDR_PREFIX_P2SH):
            return ADDR_TYPE_P2SH
        return None

    def _generate_address_fallback(
            self,
            priv_bytes: bytes
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Резервная реализация генерации адреса (при отсутствии coincurve).

        :param priv_bytes: Приватный ключ в байтах
        :return: Кортеж (P2PKH адрес, P2SH адрес) или (None, None)
        """
        # 🛠 УЛУЧШЕНИЕ 10: Явный возврат вместо молчаливого pass
        logger.warning("coincurve не доступен, генерация адреса невозможна")
        return None, None

    def generate_address_fast(
            self,
            priv_int: int
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Быстрая генерация адреса с минимальными проверками.

        :param priv_int: Приватный ключ как целое число
        :return: Кортеж (P2PKH адрес, P2SH адрес) или (None, None) при ошибке
        """
        # 🛠 УЛУЧШЕНИЕ 11: Использование констант из конфигурации
        if not (WORKER_CONFIG.MIN_PRIVATE_KEY <= priv_int <= WORKER_CONFIG.MAX_PRIVATE_KEY):
            return None, None

        try:
            # 🛠 УЛУЧШЕНИЕ 12: Явное преобразование с фиксированной длиной
            priv_bytes = priv_int.to_bytes(WORKER_CONFIG.KEY_BYTES, 'big')

            # Генерация публичного ключа
            if COINCURVE_AVAILABLE and PrivateKey is not None:
                priv = PrivateKey(priv_bytes)
                pub = priv.public_key.format(compressed=WORKER_CONFIG.COMPRESSED_PUBKEY)
            else:
                return self._generate_address_fallback(priv_bytes)

            # Оптимизированное хеширование
            pub_sha = self._fast_sha256(pub).digest()
            pub_ripemd = self._fast_ripemd160()
            pub_ripemd.update(pub_sha)
            pub_ripemd_digest = pub_ripemd.digest()

            # Генерация адреса в зависимости от типа
            if self.addr_type == ADDR_TYPE_P2PKH:
                return _generate_p2pkh(pub_ripemd_digest), None
            elif self.addr_type == ADDR_TYPE_P2SH:
                return None, _generate_p2sh(pub_ripemd_digest)
            else:
                # 🛠 УЛУЧШЕНИЕ 13: Возврат обоих типов при неопределённом префиксе
                return (
                    _generate_p2pkh(pub_ripemd_digest),
                    _generate_p2sh(pub_ripemd_digest)
                )

        except (ValueError, OverflowError, TypeError) as e:
            # 🛠 УЛУЧШЕНИЕ 14: Логирование конкретных исключений
            logger.debug(f"Ошибка генерации адреса для ключа {priv_int}: {e}")
            return None, None
        except Exception as e:
            # 🛠 УЛУЧШЕНИЕ 15: Логирование непредвиденных ошибок
            logger.warning(f"Непредвиденная ошибка при генерации адреса: {e}", exc_info=True)
            return None, None


# ═══════════════════════════════════════════════
# 🔧 ОБРАБОТКА ПАКЕТОВ КЛЮЧЕЙ
# ═══════════════════════════════════════════════

def process_key_batch(
        keys_batch: List[int],
        target_prefix: str,
        addr_type: Optional[str],
        worker_id: int,
        queue: multiprocessing.Queue,
        generator: AddressGenerator
) -> int:
    """
    Обработка пакета ключей для минимизации операций очереди.

    :param keys_batch: Список целочисленных приватных ключей
    :param target_prefix: Целевой префикс адреса
    :param addr_type: Тип адреса (p2pkh/p2sh) или None для поиска по обоим
    :param worker_id: ID воркера
    :param queue: Очередь multiprocessing для отправки результатов
    :param generator: Экземпляр AddressGenerator для генерации адресов
    :return: Количество найденных ключей в пакете
    """
    found_count = 0
    batch_size = len(keys_batch)

    # 🛠 УЛУЧШЕНИЕ 16: Предварительное выделение списка с известной ёмкостью
    messages_to_send: List[Dict[str, Any]] = []

    for key_int in keys_batch:
        hex_key = f"{key_int:064x}"
        addr_p2pkh, addr_p2sh = generator.generate_address_fast(key_int)

        found_address: Optional[str] = None
        wif_key: Optional[str] = None

        # 🛠 УЛУЧШЕНИЕ 17: Оптимизированная проверка соответствия префиксу
        if addr_type == ADDR_TYPE_P2PKH and addr_p2pkh and addr_p2pkh.startswith(target_prefix):
            found_address = addr_p2pkh
        elif addr_type == ADDR_TYPE_P2SH and addr_p2sh and addr_p2sh.startswith(target_prefix):
            found_address = addr_p2sh
        elif not addr_type:
            # Поиск по обоим типам адресов
            if addr_p2pkh and addr_p2pkh.startswith(target_prefix):
                found_address = addr_p2pkh
            elif addr_p2sh and addr_p2sh.startswith(target_prefix):
                found_address = addr_p2sh

        # Если адрес найден, создаем сообщение
        if found_address:
            wif_key = private_key_to_wif(hex_key)
            messages_to_send.append(
                create_found_message(found_address, hex_key, wif_key, worker_id)
            )
            found_count += 1

    # 🛠 УЛУЧШЕНИЕ 18: Пакетная отправка сообщений с обработкой ошибок
    for message in messages_to_send:
        try:
            safe_queue_put(queue, message, timeout=WORKER_CONFIG.QUEUE_TIMEOUT)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в очередь: {e}")

    return found_count


# ═══════════════════════════════════════════════
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ОБНОВЛЕНИЯ СТАТИСТИКИ
# ═══════════════════════════════════════════════

def _calculate_speed(
        current_scanned: int,
        last_scanned: int,
        elapsed: float
) -> float:
    """🛠 УЛУЧШЕНИЕ 19: Вынесена общая логика расчёта скорости."""
    if elapsed <= 0:
        return 0.0
    return (current_scanned - last_scanned) / elapsed


def _update_stats_common(
        total_scanned: int,
        last_update: float,
        last_scanned: int,
        stats_interval: float,
        progress: int,
        total_found: int,
        worker_id: int,
        queue: multiprocessing.Queue
) -> Tuple[int, float, int]:
    """
    Общая функция обновления статистики.

    :return: Обновлённые (total_scanned, last_update, last_scanned)
    """
    current_time = time.time()
    if current_time - last_update >= stats_interval:
        elapsed = max(0.001, current_time - last_update)
        speed = _calculate_speed(total_scanned, last_scanned, elapsed)

        safe_queue_put(
            queue,
            create_stats_message(total_scanned, total_found, speed, progress, worker_id),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
        return total_scanned, current_time, total_scanned
    return total_scanned, last_update, last_scanned


def _update_stats_sequential(
        total_scanned: int,
        last_update: float,
        last_scanned: int,
        stats_interval: float,
        current_key: int,
        chunk_start: int,
        total_in_chunk: int,
        total_found: int,
        worker_id: int,
        queue: multiprocessing.Queue
) -> Tuple[int, float, int]:
    """
    Обновление статистики для последовательного режима.

    :return: Обновлённые (total_scanned, last_update, last_scanned)
    """
    # 🛠 УЛУЧШЕНИЕ 20: Безопасный расчёт прогресса с защитой от деления на ноль
    processed = max(0, current_key - chunk_start + 1)
    progress = min(100, int(processed / total_in_chunk * 100)) if total_in_chunk > 0 else 0

    return _update_stats_common(
        total_scanned, last_update, last_scanned, stats_interval,
        progress, total_found, worker_id, queue
    )


def _update_stats_random(
        total_scanned: int,
        last_update: float,
        last_scanned: int,
        stats_interval: float,
        current_idx: int,
        total_attempts: int,
        total_found: int,
        worker_id: int,
        queue: multiprocessing.Queue
) -> Tuple[int, float, int]:
    """
    Обновление статистики для случайного режима.

    :return: Обновлённые (total_scanned, last_update, last_scanned)
    """
    # 🛠 УЛУЧШЕНИЕ 21: Безопасный расчёт прогресса
    progress = min(100, int((current_idx + 1) / total_attempts * 100)) if total_attempts > 0 else 0

    return _update_stats_common(
        total_scanned, last_update, last_scanned, stats_interval,
        progress, total_found, worker_id, queue
    )


# ═══════════════════════════════════════════════
# 🔧 ФУНКЦИИ ЗАВЕРШЕНИЯ И ОЧИСТКИ
# ═══════════════════════════════════════════════

def _send_final_stats(
        total_scanned: int,
        total_found: int,
        start_time: float,
        worker_id: int,
        queue: multiprocessing.Queue
) -> None:
    """
    Отправка финальной статистики воркера.

    :param total_scanned: Общее количество проверенных ключей
    :param total_found: Общее количество найденных ключей
    :param start_time: Время начала работы воркера
    :param worker_id: ID воркера
    :param queue: Очередь для отправки сообщений
    """
    elapsed = max(0.001, time.time() - start_time)
    speed = total_scanned / elapsed if elapsed > 0 else 0.0
    progress = 100

    try:
        safe_queue_put(
            queue,
            create_stats_message(total_scanned, total_found, speed, progress, worker_id),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
        safe_queue_put(
            queue,
            create_log_message(f"Воркер {worker_id} успешно завершен"),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
        safe_queue_put(
            queue,
            {"type": "worker_finished", "worker_id": worker_id},
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
    except Exception as e:
        logger.warning(f"Ошибка отправки финальной статистики воркера {worker_id}: {e}")


def _cleanup_worker(worker_id: int, queue: multiprocessing.Queue) -> None:
    """
    Очистка ресурсов воркера.

    :param worker_id: ID воркера
    :param queue: Очередь для отправки сигнала завершения
    """
    try:
        safe_queue_put(
            queue,
            {"type": "worker_finished", "worker_id": worker_id},
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
    except Exception as e:
        # 🛠 УЛУЧШЕНИЕ 22: Логирование вместо молчаливого pass
        logger.debug(f"Не удалось отправить сигнал завершения для воркера {worker_id}: {e}")


# ═══════════════════════════════════════════════
# 🔧 ОБРАБОТКА РЕЖИМОВ ПОИСКА
# ═══════════════════════════════════════════════

def _process_sequential_mode(
        generator: AddressGenerator,
        addr_type: Optional[str],
        worker_id: int,
        total_workers: int,
        queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        start_int: int,
        end_int: int,
        batch_size: int,
        stats_interval: float,
        last_update: float,
        last_scanned: int
) -> Tuple[int, int]:
    """
    Обработка последовательного режима поиска.

    :return: Кортеж (total_scanned, total_found)
    """
    total_scanned = 0
    total_found = 0

    # 🛠 УЛУЧШЕНИЕ 23: Валидация диапазона с понятным сообщением
    total_keys = max(0, end_int - start_int + 1)
    if total_keys <= 0:
        safe_queue_put(
            queue,
            create_log_message(f"Invalid key range: {start_int}-{end_int}"),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
        return total_scanned, total_found

    # Распределение диапазона между воркерами
    chunk_size = total_keys // total_workers
    remainder = total_keys % total_workers

    # 🛠 УЛУЧШЕНИЕ 24: Более справедливое распределение ключей
    chunk_start = start_int + worker_id * chunk_size + min(worker_id, remainder)
    chunk_end = chunk_start + chunk_size - 1 + (1 if worker_id < remainder else 0)

    if worker_id == total_workers - 1:
        chunk_end = end_int

    total_in_chunk = max(0, chunk_end - chunk_start + 1)

    safe_queue_put(
        queue,
        create_log_message(
            f"Воркер {worker_id} начал последовательный поиск: "
            f"{chunk_start}-{chunk_end} ({total_in_chunk} ключей)"
        ),
        timeout=WORKER_CONFIG.QUEUE_TIMEOUT
    )

    keys_batch: List[int] = []
    for key_int in range(chunk_start, chunk_end + 1):
        if shutdown_event.is_set():
            break

        keys_batch.append(key_int)

        # Обработка пакета
        if len(keys_batch) >= batch_size:
            batch_found = process_key_batch(
                keys_batch, generator.target_prefix, addr_type,
                worker_id, queue, generator
            )
            total_found += batch_found
            total_scanned += len(keys_batch)
            keys_batch.clear()

            # Обновление статистики
            total_scanned, last_update, last_scanned = _update_stats_sequential(
                total_scanned, last_update, last_scanned, stats_interval,
                key_int, chunk_start, total_in_chunk, total_found, worker_id, queue
            )

    # 🛠 УЛУЧШЕНИЕ 25: Обработка оставшихся ключей в одном блоке
    if keys_batch and not shutdown_event.is_set():
        batch_found = process_key_batch(
            keys_batch, generator.target_prefix, addr_type,
            worker_id, queue, generator
        )
        total_found += batch_found
        total_scanned += len(keys_batch)

    return total_scanned, total_found


def _process_random_mode(
        generator: AddressGenerator,
        addr_type: Optional[str],
        worker_id: int,
        total_workers: int,
        queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        start_int: int,
        end_int: int,
        attempts: int,
        batch_size: int,
        stats_interval: float,
        last_update: float,
        last_scanned: int,
        rng: random.SystemRandom
) -> Tuple[int, int]:
    """
    Обработка случайного режима поиска.

    :return: Кортеж (total_scanned, total_found)
    """
    total_scanned = 0
    total_found = 0

    # 🛠 УЛУЧШЕНИЕ 26: Более точное распределение попыток
    base_attempts = attempts // total_workers
    extra = attempts % total_workers
    total_attempts = base_attempts + (1 if worker_id < extra else 0)

    safe_queue_put(
        queue,
        create_log_message(f"Воркер {worker_id} начал случайный поиск: {total_attempts} попыток"),
        timeout=WORKER_CONFIG.QUEUE_TIMEOUT
    )

    keys_batch: List[int] = []
    for idx in range(total_attempts):
        if shutdown_event.is_set():
            break

        # 🛠 УЛУЧШЕНИЕ 27: Безопасная генерация случайного числа
        try:
            key_int = rng.randint(start_int, end_int)
        except ValueError:
            # Fallback при некорректном диапазоне
            key_int = start_int if start_int == end_int else (start_int + end_int) // 2

        keys_batch.append(key_int)

        # Пакетная обработка
        if len(keys_batch) >= batch_size:
            batch_found = process_key_batch(
                keys_batch, generator.target_prefix, addr_type,
                worker_id, queue, generator
            )
            total_found += batch_found
            total_scanned += len(keys_batch)
            keys_batch.clear()

            # Обновление статистики
            total_scanned, last_update, last_scanned = _update_stats_random(
                total_scanned, last_update, last_scanned, stats_interval,
                idx, total_attempts, total_found, worker_id, queue
            )

    # Обработка оставшихся ключей
    if keys_batch and not shutdown_event.is_set():
        batch_found = process_key_batch(
            keys_batch, generator.target_prefix, addr_type,
            worker_id, queue, generator
        )
        total_found += batch_found
        total_scanned += len(keys_batch)

    return total_scanned, total_found


# ═══════════════════════════════════════════════
# 🔧 ОСНОВНАЯ ФУНКЦИЯ ВОРКЕРА
# ═══════════════════════════════════════════════

def worker_main(
        target_prefix: str,
        start_int: int,
        end_int: int,
        attempts: int,
        mode: str,
        worker_id: int,
        total_workers: int,
        queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event
) -> None:
    """
    Оптимизированная основная функция CPU воркера.

    :param target_prefix: Целевой префикс адреса для поиска
    :param start_int: Начало диапазона приватных ключей
    :param end_int: Конец диапазона приватных ключей
    :param attempts: Количество попыток (для случайного режима)
    :param mode: Режим работы ("sequential" или "random")
    :param worker_id: Уникальный идентификатор воркера
    :param total_workers: Общее количество воркеров
    :param queue: Очередь multiprocessing для коммуникации
    :param shutdown_event: Событие для сигнализации остановки
    """
    logger.info(f"Worker {worker_id} started in {mode} mode")

    # Предкомпиляция часто используемых объектов
    generator = AddressGenerator(target_prefix)
    addr_type = generator.addr_type
    rng = random.SystemRandom()

    # Инициализация статистики
    total_scanned = 0
    total_found = 0
    start_time = time.time()
    last_update = start_time
    last_scanned = 0
    stats_interval = WORKER_CONFIG.STATS_INTERVAL
    batch_size = WORKER_CONFIG.BATCH_SIZE

    try:
        if mode == "sequential":
            total_scanned, total_found = _process_sequential_mode(
                generator, addr_type, worker_id, total_workers, queue, shutdown_event,
                start_int, end_int, batch_size, stats_interval, last_update, last_scanned
            )
        elif mode == "random":
            total_scanned, total_found = _process_random_mode(
                generator, addr_type, worker_id, total_workers, queue, shutdown_event,
                start_int, end_int, attempts, batch_size, stats_interval,
                last_update, last_scanned, rng
            )
        else:
            # 🛠 УЛУЧШЕНИЕ 28: Обработка неизвестного режима
            logger.warning(f"Worker {worker_id}: неизвестный режим '{mode}', используется sequential")
            total_scanned, total_found = _process_sequential_mode(
                generator, addr_type, worker_id, total_workers, queue, shutdown_event,
                start_int, end_int, batch_size, stats_interval, last_update, last_scanned
            )

        # Финальное обновление статистики
        _send_final_stats(total_scanned, total_found, start_time, worker_id, queue)

    except KeyboardInterrupt:
        safe_queue_put(
            queue,
            create_log_message(f"Воркер {worker_id} остановлен пользователем"),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
    except MemoryError:
        logger.error(f"Worker {worker_id}: недостаточно памяти")
        safe_queue_put(
            queue,
            create_log_message(f"Недостаточно памяти в воркере {worker_id}"),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        safe_queue_put(
            queue,
            create_log_message(f"Критическая ошибка в воркере {worker_id}: {type(e).__name__}: {str(e)}"),
            timeout=WORKER_CONFIG.QUEUE_TIMEOUT
        )
    finally:
        _cleanup_worker(worker_id, queue)


# ═══════════════════════════════════════════════
# 🔧 УПРАВЛЕНИЕ ПРОЦЕССАМИ
# ═══════════════════════════════════════════════

def stop_cpu_search(
        processes: Dict[int, multiprocessing.Process],
        shutdown_event: multiprocessing.Event
) -> None:
    """
    Оптимизированная остановка CPU поиска.

    :param processes: Словарь {worker_id: Process} активных процессов
    :param shutdown_event: Событие для сигнализации остановки всем воркерам
    """
    logger.info("Остановка CPU процессов...")
    shutdown_event.set()

    # 🛠 УЛУЧШЕНИЕ 29: Локальные переменные для конфигурации
    stop_timeout = WORKER_CONFIG.STOP_TIMEOUT
    join_timeout = WORKER_CONFIG.JOIN_TIMEOUT

    # Сначала мягкая остановка всех процессов
    active_processes = [
        (worker_id, process)
        for worker_id, process in processes.items()
        if process.is_alive()
    ]

    if active_processes:
        # Небольшая задержка для нормального завершения
        time.sleep(0.05)

        # 🛠 УЛУЧШЕНИЕ 30: Двухэтапное завершение: terminate → kill
        still_active = [p for _, p in active_processes if p.is_alive()]
        if still_active:
            for worker_id, process in active_processes:
                if process.is_alive():
                    try:
                        process.terminate()
                    except (AttributeError, OSError) as e:
                        logger.warning(f"Не удалось terminate воркера {worker_id}: {e}")

            # Ожидание завершения с таймаутом
            for worker_id, process in active_processes:
                try:
                    process.join(timeout=join_timeout)
                    if process.is_alive():
                        logger.warning(f"Воркер {worker_id} не завершён, используем kill")
                        process.kill()
                        process.join(timeout=join_timeout)
                except Exception as e:
                    logger.warning(f"Ошибка при завершении воркера {worker_id}: {e}")

    # 🛠 УЛУЧШЕНИЕ 31: Безопасная очистка словаря процессов
    processes.clear()

    # 🛠 УЛУЧШЕНИЕ 32: Сброс события только если оно установлено
    if shutdown_event.is_set():
        shutdown_event.clear()

    logger.info("CPU процессы остановлены.")


# 🛠 УЛУЧШЕНИЕ 33: Явный экспорт публичного API модуля
__all__ = [
    'WorkerConfig',
    'WORKER_CONFIG',
    'ADDR_TYPE_P2PKH',
    'ADDR_TYPE_P2SH',
    'ADDR_PREFIX_P2PKH',
    'ADDR_PREFIX_P2SH',
    'WorkerSignals',
    'create_found_message',
    'create_stats_message',
    'create_log_message',
    'AddressGenerator',
    'process_key_batch',
    'worker_main',
    'stop_cpu_search',
]