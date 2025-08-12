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
        # Кеширование префикса для быстрой проверки
        self.prefix_len = len(target_prefix)
        self.target_bytes = target_prefix.encode('ascii')

    def _determine_address_type(self, prefix):
        if prefix.startswith('1'):
            return 'p2pkh'
        elif prefix.startswith('3'):
            return 'p2sh'
        return None

    def generate_address_fast(self, priv_int):
        """Быстрая генерация адреса с минимальными проверками и early exit"""
        if not (1 <= priv_int <= config.MAX_KEY):
            return None, None

        try:
            # Используем struct для более быстрого преобразования
            priv_bytes = struct.pack('>32s', priv_int.to_bytes(32, 'big'))
            priv = PrivateKey(priv_bytes)
            pub = priv.public_key.format(compressed=True)

            # Оптимизированное хеширование с кешированием
            pub_sha = sha256_cache(pub)
            pub_ripemd = ripemd160_cache(pub_sha)

            # Генерация только нужного типа адреса с early exit
            if self.addr_type == 'p2pkh':
                address = _generate_p2pkh(pub_ripemd)
                if address.startswith(self.target_prefix):
                    return address, None
            elif self.addr_type == 'p2sh':
                address = _generate_p2sh(pub_ripemd)
                if address.startswith(self.target_prefix):
                    return None, address
            elif not self.addr_type:  # Оба типа
                addr_p2pkh = _generate_p2pkh(pub_ripemd)
                if addr_p2pkh.startswith(self.target_prefix):
                    return addr_p2pkh, None
                addr_p2sh = _generate_p2sh(pub_ripemd)
                if addr_p2sh.startswith(self.target_prefix):
                    return None, addr_p2sh

            return None, None

        except Exception:
            return None, None


def process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator):
    """Обработка пакета ключей для минимизации операций очереди"""
    found_count = 0
    messages_to_send = []

    # Предвычисляем часто используемые значения
    prefix_len = len(target_prefix)

    for key_int in keys_batch:
        hex_key = f"{key_int:064x}"
        addr_p2pkh, addr_p2sh = generator.generate_address_fast(key_int)

        found = False
        # Оптимизированные проверки с быстрым сравнением префиксов
        if addr_type == 'p2pkh' and addr_p2pkh:
            if addr_p2pkh[:prefix_len] == target_prefix:
                wif_key = private_key_to_wif(hex_key)
                messages_to_send.append(create_found_message(addr_p2pkh, hex_key, wif_key, worker_id))
                found = True
        elif addr_type == 'p2sh' and addr_p2sh:
            if addr_p2sh[:prefix_len] == target_prefix:
                wif_key = private_key_to_wif(hex_key)
                messages_to_send.append(create_found_message(addr_p2sh, hex_key, wif_key, worker_id))
                found = True
        elif not addr_type:  # Оба типа
            matched_address = None
            if addr_p2pkh and addr_p2pkh[:prefix_len] == target_prefix:
                matched_address = addr_p2pkh
            elif addr_p2sh and addr_p2sh[:prefix_len] == target_prefix:
                matched_address = addr_p2sh

            if matched_address:
                wif_key = private_key_to_wif(hex_key)
                messages_to_send.append(create_found_message(matched_address, hex_key, wif_key, worker_id))
                found = True

        if found:
            found_count += 1

    # Батчевая отправка сообщений
    if messages_to_send:
        for msg in messages_to_send:
            safe_queue_put(queue, msg, timeout=0.01)

    return found_count


def worker_main(target_prefix, start_int, end_int, attempts, mode, worker_id, total_workers, queue, shutdown_event):
    """Оптимизированная основная функция CPU воркера"""

    # Установка приоритета процесса для лучшей производительности
    try:
        import os
        os.nice(10)  # Понижаем приоритет чтобы не блокировать систему
    except:
        pass

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
    stats_interval = 0.5  # Ещё более частые обновления

    # Адаптивный размер пакета в зависимости от нагрузки
    BATCH_SIZE = min(200, max(50, 1000 // total_workers))  # Адаптивный размер

    try:
        if mode == "sequential":
            # Более точное распределение диапазона
            total_keys = max(0, end_int - start_int + 1)
            if total_keys <= 0:
                safe_queue_put(queue, create_log_message(f"Invalid key range: {start_int}-{end_int}"))
                return

            # Улучшенное распределение нагрузки
            chunk_size = total_keys // total_workers
            remainder = total_keys % total_workers

            chunk_start = start_int + worker_id * chunk_size + min(worker_id, remainder)
            chunk_end = chunk_start + chunk_size + (1 if worker_id < remainder else 0) - 1

            current = chunk_start
            total_in_chunk = chunk_end - chunk_start + 1

            safe_queue_put(queue, create_log_message(
                f"Воркер {worker_id} начал последовательный поиск: {chunk_start}-{chunk_end} ({total_in_chunk} ключей)"))

            keys_batch = []

            # Используем xrange-подобный подход для экономии памяти
            for key_int in range(chunk_start, chunk_end + 1):
                if shutdown_event.is_set():
                    break

                keys_batch.append(key_int)

                # Адаптивная пакетная обработка
                if len(keys_batch) >= BATCH_SIZE:
                    batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                    total_found += batch_found
                    total_scanned += len(keys_batch)
                    keys_batch.clear()

                    # Оптимизированное обновление статистики
                    current_time = time.time()
                    if current_time - last_update >= stats_interval:
                        elapsed = max(0.001, current_time - last_update)
                        speed = (total_scanned - last_scanned) / elapsed
                        processed = key_int - chunk_start + 1
                        progress = min(99,
                                       int(processed / total_in_chunk * 100))  # 99% чтобы избежать преждевременного завершения

                        stats_msg = create_stats_message(total_scanned, total_found, speed, progress, worker_id)
                        safe_queue_put(queue, stats_msg, timeout=0.01)

                        last_update = current_time
                        last_scanned = total_scanned

            # Обработка оставшихся ключей
            if keys_batch and not shutdown_event.is_set():
                batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                total_found += batch_found
                total_scanned += len(keys_batch)

        elif mode == "random":
            # Более справедливое распределение попыток
            base_attempts = attempts // total_workers
            extra_attempts = attempts % total_workers
            total_attempts = base_attempts + (1 if worker_id < extra_attempts else 0)

            safe_queue_put(queue, create_log_message(
                f"Воркер {worker_id} начал случайный поиск: {total_attempts} попыток"))

            keys_batch = []
            for idx in range(total_attempts):
                if shutdown_event.is_set():
                    break

                key_int = rng.randint(start_int, end_int)
                keys_batch.append(key_int)

                if len(keys_batch) >= BATCH_SIZE:
                    batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                    total_found += batch_found
                    total_scanned += len(keys_batch)
                    keys_batch.clear()

                    current_time = time.time()
                    if current_time - last_update >= stats_interval:
                        elapsed = max(0.001, current_time - last_update)
                        speed = (total_scanned - last_scanned) / elapsed
                        progress = min(99, int((idx + 1) / total_attempts * 100))

                        stats_msg = create_stats_message(total_scanned, total_found, speed, progress, worker_id)
                        safe_queue_put(queue, stats_msg, timeout=0.01)

                        last_update = current_time
                        last_scanned = total_scanned

            if keys_batch and not shutdown_event.is_set():
                batch_found = process_key_batch(keys_batch, target_prefix, addr_type, worker_id, queue, generator)
                total_found += batch_found
                total_scanned += len(keys_batch)

        # Финальное обновление статистики
        elapsed = max(0.001, time.time() - start_time)
        speed = total_scanned / elapsed if elapsed > 0 else 0
        progress = 100

        # Убедимся что все сообщения отправлены
        final_stats = create_stats_message(total_scanned, total_found, speed, progress, worker_id)
        safe_queue_put(queue, final_stats, timeout=0.1)

        safe_queue_put(queue, create_log_message(f"Воркер {worker_id} успешно завершен"), timeout=0.1)
        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=0.1)

    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        error_msg = create_log_message(f"Критическая ошибка в воркере {worker_id}: {str(e)}")
        safe_queue_put(queue, error_msg, timeout=0.1)
        safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=0.1)


def stop_cpu_search(processes, shutdown_event):
    """Оптимизированная остановка CPU поиска"""
    logger.info("Остановка CPU процессов...")
    shutdown_event.set()

    start_time = time.time()
    soft_timeout = 1.0  # Мягкий таймаут
    hard_timeout = 3.0  # Жесткий таймаут

    # Сначала даем время на мягкое завершение
    active_processes = [p for p in processes.values() if p.is_alive()]

    if active_processes:
        # Ждем мягкое завершение
        time.sleep(0.1)

        # Проверяем кто еще жив
        still_active = [p for p in active_processes if p.is_alive()]

        if still_active:
            # Принудительное завершение с таймаутом
            for worker_id, process in list(processes.items()):
                if process.is_alive():
                    try:
                        process.terminate()
                        process.join(timeout=0.5)
                        if process.is_alive():
                            try:
                                process.kill()  # Python 3.7+
                            except AttributeError:
                                # Для старых версий Python
                                try:
                                    import signal
                                    process.send_signal(signal.SIGKILL)
                                except:
                                    pass
                    except Exception as e:
                        logger.error(f"Ошибка остановки воркера {worker_id}: {str(e)}")

    # Очищаем ресурсы
    processes.clear()
    shutdown_event.clear()

    # Логируем время остановки
    stop_time = time.time() - start_time
    logger.info(f"CPU процессы остановлены за {stop_time:.2f} секунд")