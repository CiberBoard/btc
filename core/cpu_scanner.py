import sys
import multiprocessing
import random
import time
import logging
from typing import Dict, List, Tuple, Optional, Any
from PyQt5.QtCore import QObject, pyqtSignal
import hashlib

try:
    from coincurve import PrivateKey

    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False

import config
from utils.helpers import private_key_to_wif, _generate_p2pkh, _generate_p2sh, safe_queue_put
import utils.helpers as helpers

logger = logging.getLogger('bitcoin_scanner')

# Глобальный кеш для хеш-функций
sha256_cache = helpers.sha256
ripemd160_cache = helpers.new_ripemd160

# Конфигурационные параметры как dataclass для лучшей читаемости
WORKER_CONFIG = {
    'BATCH_SIZE': 500,
    'STATS_INTERVAL': 0.5,
    'QUEUE_TIMEOUT': 0.1,
    'STOP_TIMEOUT': 3,
    'JOIN_TIMEOUT': 0.5
}

# Константы для типов адресов
ADDR_TYPE_P2PKH = 'p2pkh'
ADDR_TYPE_P2SH = 'p2sh'
ADDR_PREFIX_P2PKH = '1'
ADDR_PREFIX_P2SH = '3'


class WorkerSignals(QObject):
    """Сигналы для CPU воркеров"""
    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    found_key = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)


def create_found_message(address: str, hex_key: str, wif_key: str, worker_id: int) -> Dict[str, Any]:
    """Создание сообщения о найденном ключе"""
    return {
        "type": "found",
        "address": address,
        "hex_key": hex_key,
        "wif_key": wif_key,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "worker_id": worker_id,
        "source": "CPU"
    }


def create_stats_message(scanned: int, found: int, speed: float, progress: int, worker_id: int) -> Dict[str, Any]:
    """Создание сообщения со статистикой"""
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
    """Создание лог-сообщения"""
    return {"type": "log", "message": message}


class AddressGenerator:
    """Оптимизированная генерация адресов с предкомпиляцией"""

    def __init__(self, target_prefix: str):
        self.target_prefix = target_prefix
        self.addr_type = self._determine_address_type(target_prefix)
        self.prefix_length = len(target_prefix)
        self.target_chars = target_prefix

        # Предкомпилированные функции для ускорения
        self._fast_sha256 = hashlib.sha256
        self._fast_ripemd160 = ripemd160_cache

    def _determine_address_type(self, prefix: str) -> Optional[str]:
        """Определение типа адреса по префиксу"""
        if prefix.startswith(ADDR_PREFIX_P2PKH):
            return ADDR_TYPE_P2PKH
        elif prefix.startswith(ADDR_PREFIX_P2SH):
            return ADDR_TYPE_P2SH
        return None

    def _generate_address_fallback(self, priv_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        """Резервная реализация генерации адреса"""
        return None, None

    def generate_address_fast(self, priv_int: int) -> Tuple[Optional[str], Optional[str]]:
        """Быстрая генерация адреса с минимальными проверками"""
        # Быстрая проверка диапазона без исключений
        if not (1 <= priv_int <= config.MAX_KEY):
            return None, None

        try:
            priv_bytes = priv_int.to_bytes(32, 'big')

            # Генерация публичного ключа
            if COINCURVE_AVAILABLE:
                priv = PrivateKey(priv_bytes)
                pub = priv.public_key.format(compressed=True)
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
                return _generate_p2pkh(pub_ripemd_digest), _generate_p2sh(pub_ripemd_digest)

        except (ValueError, OverflowError, Exception):
            # Единая обработка всех исключений
            return None, None


def process_key_batch(
        keys_batch: List[int],
        target_prefix: str,
        addr_type: Optional[str],
        worker_id: int,
        queue: multiprocessing.Queue,
        generator: AddressGenerator
) -> int:
    """Обработка пакета ключей для минимизации операций очереди"""
    found_count = 0
    batch_size = len(keys_batch)

    # Предварительное выделение списка для избежания реаллокаций
    messages_to_send = []

    for key_int in keys_batch:
        hex_key = f"{key_int:064x}"
        addr_p2pkh, addr_p2sh = generator.generate_address_fast(key_int)

        found_address = None
        wif_key = None

        # Оптимизированная проверка соответствия префиксу
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
            messages_to_send.append(create_found_message(found_address, hex_key, wif_key, worker_id))
            found_count += 1

    # Отправка всех сообщений одним пакетом
    for message in messages_to_send:
        safe_queue_put(queue, message, timeout=WORKER_CONFIG['QUEUE_TIMEOUT'])

    return found_count


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
    """Оптимизированная основная функция CPU воркера"""
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
    stats_interval = WORKER_CONFIG['STATS_INTERVAL']
    BATCH_SIZE = WORKER_CONFIG['BATCH_SIZE']

    try:
        if mode == "sequential":
            total_scanned, total_found = _process_sequential_mode(
                generator, addr_type, worker_id, total_workers, queue, shutdown_event,
                start_int, end_int, BATCH_SIZE, stats_interval, last_update, last_scanned
            )
        elif mode == "random":
            total_scanned, total_found = _process_random_mode(
                generator, addr_type, worker_id, total_workers, queue, shutdown_event,
                start_int, end_int, attempts, BATCH_SIZE, stats_interval, last_update, last_scanned, rng
            )

        # Финальное обновление статистики
        _send_final_stats(total_scanned, total_found, start_time, worker_id, queue)

    except KeyboardInterrupt:
        safe_queue_put(queue, create_log_message(f"Воркер {worker_id} остановлен пользователем"), timeout=1.0)
    except MemoryError:
        safe_queue_put(queue, create_log_message(f"Недостаточно памяти в воркере {worker_id}"), timeout=1.0)
    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        safe_queue_put(queue, create_log_message(f"Критическая ошибка в воркере {worker_id}: {str(e)}"), timeout=1.0)
    finally:
        _cleanup_worker(worker_id, queue)


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
    """Обработка последовательного режима"""
    total_scanned = 0
    total_found = 0

    # Распределение диапазона между воркерами
    total_keys = max(0, end_int - start_int + 1)
    if total_keys <= 0:
        safe_queue_put(queue, create_log_message(f"Invalid key range: {start_int}-{end_int}"))
        return total_scanned, total_found

    chunk_size = total_keys // total_workers
    chunk_start = start_int + worker_id * chunk_size
    chunk_end = chunk_start + chunk_size - 1
    if worker_id == total_workers - 1:
        chunk_end = end_int

    current = chunk_start
    total_in_chunk = chunk_end - chunk_start + 1

    safe_queue_put(queue, create_log_message(
        f"Воркер {worker_id} начал последовательный поиск: {chunk_start}-{chunk_end} ({total_in_chunk} ключей)"))

    keys_batch = []
    for key_int in range(chunk_start, chunk_end + 1):
        if shutdown_event.is_set():
            break

        keys_batch.append(key_int)

        # Обработка пакета
        if len(keys_batch) >= batch_size:
            batch_found = process_key_batch(keys_batch, generator.target_prefix, addr_type, worker_id, queue, generator)
            total_found += batch_found
            total_scanned += len(keys_batch)
            keys_batch.clear()

            # Обновление статистики
            total_scanned, last_update, last_scanned = _update_stats_sequential(
                total_scanned, last_update, last_scanned, stats_interval,
                key_int, chunk_start, total_in_chunk, total_found, worker_id, queue
            )

    # Обработка оставшихся ключей
    if keys_batch and not shutdown_event.is_set():
        batch_found = process_key_batch(keys_batch, generator.target_prefix, addr_type, worker_id, queue, generator)
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
    """Обработка случайного режима"""
    total_scanned = 0
    total_found = 0

    base_attempts = attempts // total_workers
    total_attempts = base_attempts + (1 if worker_id < (attempts % total_workers) else 0)

    safe_queue_put(queue, create_log_message(
        f"Воркер {worker_id} начал случайный поиск: {total_attempts} попыток"))

    keys_batch = []
    for idx in range(total_attempts):
        if shutdown_event.is_set():
            break

        key_int = rng.randint(start_int, end_int)
        keys_batch.append(key_int)

        # Пакетная обработка
        if len(keys_batch) >= batch_size:
            batch_found = process_key_batch(keys_batch, generator.target_prefix, addr_type, worker_id, queue, generator)
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
        batch_found = process_key_batch(keys_batch, generator.target_prefix, addr_type, worker_id, queue, generator)
        total_found += batch_found
        total_scanned += len(keys_batch)

    return total_scanned, total_found


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
    """Обновление статистики для последовательного режима"""
    current_time = time.time()
    if current_time - last_update >= stats_interval:
        elapsed = max(0.001, current_time - last_update)
        speed = (total_scanned - last_scanned) / elapsed
        processed = current_key - chunk_start + 1
        progress = min(100, int(processed / total_in_chunk * 100))
        safe_queue_put(queue, create_stats_message(total_scanned, total_found, speed, progress, worker_id))
        return total_scanned, current_time, total_scanned
    return total_scanned, last_update, last_scanned


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
    """Обновление статистики для случайного режима"""
    current_time = time.time()
    if current_time - last_update >= stats_interval:
        elapsed = max(0.001, current_time - last_update)
        speed = (total_scanned - last_scanned) / elapsed
        progress = min(100, int((current_idx + 1) / total_attempts * 100))
        safe_queue_put(queue, create_stats_message(total_scanned, total_found, speed, progress, worker_id))
        return total_scanned, current_time, total_scanned
    return total_scanned, last_update, last_scanned


def _send_final_stats(
        total_scanned: int,
        total_found: int,
        start_time: float,
        worker_id: int,
        queue: multiprocessing.Queue
) -> None:
    """Отправка финальной статистики"""
    elapsed = max(0.001, time.time() - start_time)
    speed = total_scanned / elapsed if elapsed > 0 else 0
    progress = 100
    safe_queue_put(queue, create_stats_message(total_scanned, total_found, speed, progress, worker_id))
    safe_queue_put(queue, create_log_message(f"Воркер {worker_id} успешно завершен"), timeout=1.0)
    safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)


def _cleanup_worker(worker_id: int, queue: multiprocessing.Queue) -> None:
    """Очистка ресурсов воркера"""
    try:
        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)
    except:
        pass


def stop_cpu_search(processes: Dict[int, multiprocessing.Process], shutdown_event: multiprocessing.Event) -> None:
    """Оптимизированная остановка CPU поиска"""
    logger.info("Остановка CPU процессов...")
    shutdown_event.set()

    # Параллельная остановка всех процессов
    start_time = time.time()
    timeout = WORKER_CONFIG['STOP_TIMEOUT']

    # Сначала мягкая остановка всех процессов
    active_processes = [(worker_id, process) for worker_id, process in processes.items() if process.is_alive()]

    if active_processes:
        # Небольшая задержка для нормального завершения
        time.sleep(0.05)

        # Быстрая проверка завершения
        still_active = [p for _, p in active_processes if p.is_alive()]
        if still_active:
            # Параллельное принудительное завершение
            for worker_id, process in active_processes:
                if process.is_alive():
                    try:
                        process.terminate()
                    except:
                        pass

            # Ожидание завершения с таймаутом
            for worker_id, process in active_processes:
                try:
                    process.join(timeout=WORKER_CONFIG['JOIN_TIMEOUT'])
                    if process.is_alive():
                        process.kill()
                except Exception as e:
                    logger.warning(f"Ошибка при завершении воркера {worker_id}: {str(e)}")

    processes.clear()
    shutdown_event.clear()
    logger.info("CPU процессы остановлены.")