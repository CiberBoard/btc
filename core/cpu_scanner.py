import random
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal
from multiprocessing import Process, Queue
import hashlib
import struct

try:
    from coincurve import PrivateKey

    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False

from logger import config
from utils.helpers import private_key_to_wif, _generate_p2pkh, _generate_p2sh, safe_queue_put
import utils.helpers as helpers

logger = logging.getLogger('bitcoin_scanner')

# Глобальный кеш для хеш-функций
sha256_cache = helpers.sha256
ripemd160_cache = helpers.new_ripemd160


# Предкомпилированные функции хеширования для максимальной скорости
def fast_sha256(data):
    return hashlib.sha256(data).digest()


def fast_ripemd160(data):
    ripemd = ripemd160_cache()
    ripemd.update(data)
    return ripemd.digest()


class WorkerSignals(QObject):
    """Сигналы для CPU воркеров"""
    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    found_key = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)


def create_found_message(address, hex_key, wif_key, worker_id):
    return {
        "type": "found",
        "address": address,
        "hex_key": hex_key,
        "wif_key": wif_key,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "worker_id": worker_id,
        "source": "CPU"
    }


def create_stats_message(scanned, found, speed, progress, worker_id):
    return {
        "type": "stats",
        "scanned": scanned,
        "found": found,
        "speed": speed,
        "progress": progress,
        "worker_id": worker_id
    }


def create_log_message(message):
    return {"type": "log", "message": message}


# Оптимизированная генерация адресов с предкомпиляцией
class AddressGenerator:
    def __init__(self, target_prefix):
        self.target_prefix = target_prefix
        self.addr_type = self._determine_address_type(target_prefix)

    def _determine_address_type(self, prefix):
        if prefix.startswith('1'):
            return 'p2pkh'
        elif prefix.startswith('3'):
            return 'p2sh'
        return None

    def generate_address_fast(self, priv_int):
        """Быстрая генерация адреса с минимальными проверками"""
        if not (1 <= priv_int <= config.MAX_KEY):
            return None, None

        try:
            # Быстрое преобразование в байты
            priv_bytes = priv_int.to_bytes(32, 'big')
            priv = PrivateKey(priv_bytes)
            pub = priv.public_key.format(compressed=True)

            # Оптимизированное хеширование
            pub_sha = fast_sha256(pub)
            pub_ripemd = fast_ripemd160(pub_sha)

            # Генерация только нужного типа адреса
            if self.addr_type == 'p2pkh':
                address = _generate_p2pkh(pub_ripemd)
                return address, None
            elif self.addr_type == 'p2sh':
                address = _generate_p2sh(pub_ripemd)
                return None, address
            else:
                return _generate_p2pkh(pub_ripemd), _generate_p2sh(pub_ripemd)

        except Exception:
            return None, None


def process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator):
    """Обработка пакета ключей для минимизации операций очереди"""
    found_count = 0
    messages_to_send = []

    for key_int in keys_batch:
        hex_key = f"{key_int:064x}"
        addr_p2pkh, addr_p2sh = generator.generate_address_fast(key_int)

        found = False
        if addr_type == 'p2pkh' and addr_p2pkh and addr_p2pkh.startswith(target_prefix):
            wif_key = private_key_to_wif(hex_key)
            messages_to_send.append(create_found_message(addr_p2pkh, hex_key, wif_key, worker_id))
            found = True
        elif addr_type == 'p2sh' and addr_p2sh and addr_p2sh.startswith(target_prefix):
            wif_key = private_key_to_wif(hex_key)
            messages_to_send.append(create_found_message(addr_p2sh, hex_key, wif_key, worker_id))
            found = True
        elif not addr_type:
            if addr_p2pkh and addr_p2pkh.startswith(target_prefix):
                wif_key = private_key_to_wif(hex_key)
                messages_to_send.append(create_found_message(addr_p2pkh, hex_key, wif_key, worker_id))
                found = True
            elif addr_p2sh and addr_p2sh.startswith(target_prefix):
                wif_key = private_key_to_wif(hex_key)
                messages_to_send.append(create_found_message(addr_p2sh, hex_key, wif_key, worker_id))
                found = True

        if found:
            found_count += 1

    # Отправка всех сообщений одним пакетом
    for msg in messages_to_send:
        safe_queue_put(queue, msg, timeout=0.1)

    return found_count


def worker_main(target_prefix, start_int, end_int, attempts, mode, worker_id, total_workers, queue, shutdown_event):
    """Оптимизированная основная функция CPU воркера"""
    logger.info(f"Worker {worker_id} started in {mode} mode")

    # Предкомпиляция часто используемых объектов
    generator = AddressGenerator(target_prefix)
    addr_type = generator.addr_type
    rng = random.SystemRandom()

    total_scanned = 0
    total_found = 0
    start_time = time.time()
    last_update = start_time
    last_scanned = 0
    stats_interval = 1.0  # Уменьшено для более частых обновлений

    # Пакетная обработка для минимизации overhead
    BATCH_SIZE = 100

    try:
        if mode == "sequential":
            # Распределение диапазона между воркерами
            total_keys = max(0, end_int - start_int + 1)
            if total_keys <= 0:
                safe_queue_put(queue, create_log_message(f"Invalid key range: {start_int}-{end_int}"))
                return

            chunk_size = total_keys // total_workers
            chunk_start = start_int + worker_id * chunk_size
            chunk_end = chunk_start + chunk_size - 1
            if worker_id == total_workers - 1:
                chunk_end = end_int

            current = chunk_start
            total_in_chunk = chunk_end - chunk_start + 1

            safe_queue_put(queue, create_log_message(
                f"Воркер {worker_id} начал последовательный поиск: {chunk_start}-{chunk_end} ({total_in_chunk} ключей)"))

            # Пакетная обработка ключей
            keys_batch = []
            for key_int in range(chunk_start, chunk_end + 1):
                if shutdown_event.is_set():
                    break

                keys_batch.append(key_int)

                # Обработка пакета
                if len(keys_batch) >= BATCH_SIZE:
                    batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                    total_found += batch_found
                    total_scanned += len(keys_batch)
                    keys_batch.clear()

                    # Обновление статистики
                    current_time = time.time()
                    if current_time - last_update >= stats_interval:
                        elapsed = max(0.001, current_time - last_update)
                        speed = (total_scanned - last_scanned) / elapsed
                        processed = key_int - chunk_start + 1
                        progress = min(100, int(processed / total_in_chunk * 100))
                        safe_queue_put(queue,
                                       create_stats_message(total_scanned, total_found, speed, progress, worker_id))
                        last_update = current_time
                        last_scanned = total_scanned

            # Обработка оставшихся ключей
            if keys_batch and not shutdown_event.is_set():
                batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                total_found += batch_found
                total_scanned += len(keys_batch)

        elif mode == "random":
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
                if len(keys_batch) >= BATCH_SIZE:
                    batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                    total_found += batch_found
                    total_scanned += len(keys_batch)
                    keys_batch.clear()

                    # Обновление статистики
                    current_time = time.time()
                    if current_time - last_update >= stats_interval:
                        elapsed = max(0.001, current_time - last_update)
                        speed = (total_scanned - last_scanned) / elapsed
                        progress = min(100, int((idx + 1) / total_attempts * 100))
                        safe_queue_put(queue,
                                       create_stats_message(total_scanned, total_found, speed, progress, worker_id))
                        last_update = current_time
                        last_scanned = total_scanned

            # Обработка оставшихся ключей
            if keys_batch and not shutdown_event.is_set():
                batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                total_found += batch_found
                total_scanned += len(keys_batch)

        # Финальное обновление статистики
        elapsed = max(0.001, time.time() - start_time)
        speed = total_scanned / elapsed if elapsed > 0 else 0
        progress = 100
        safe_queue_put(queue, create_stats_message(total_scanned, total_found, speed, progress, worker_id))
        safe_queue_put(queue, create_log_message(f"Воркер {worker_id} успешно завершен"), timeout=1.0)
        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)

    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        safe_queue_put(queue, create_log_message(f"Критическая ошибка в воркере {worker_id}: {str(e)}"), timeout=1.0)
        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)


def stop_cpu_search(processes, shutdown_event):
    """Оптимизированная остановка CPU поиска"""
    logger.info("Остановка CPU процессов...")
    shutdown_event.set()

    # Быстрая проверка и завершение процессов
    start_time = time.time()
    timeout = 5  # Уменьшено время ожидания

    # Сначала мягкая остановка
    active_processes = [p for p in processes.values() if p.is_alive()]

    if active_processes:
        # Ждем короткое время для нормального завершения
        time.sleep(0.1)

        # Принудительное завершение оставшихся процессов
        for worker_id, process in list(processes.items()):
            if process.is_alive():
                try:
                    process.terminate()
                    process.join(timeout=0.5)
                    if process.is_alive():
                        process.kill()
                except Exception as e:
                    logger.error(f"Ошибка остановки воркера {worker_id}: {str(e)}")

    processes.clear()
    shutdown_event.clear()
    logger.info("CPU процессы остановлены.")