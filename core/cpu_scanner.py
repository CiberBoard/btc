# core/cpu_scanner.py
import multiprocessing
import random
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal

try:
    from coincurve import PrivateKey

    COINCURVE_AVAILABLE = True
except ImportError:
    COINCURVE_AVAILABLE = False

import config
from utils.helpers import private_key_to_wif, _generate_p2pkh, _generate_p2sh, safe_queue_put, validate_key_range
import utils.helpers as helpers

logger = logging.getLogger('bitcoin_scanner')

# Кеш для хеш-функций
sha256 = helpers.sha256
new_ripemd160 = helpers.new_ripemd160


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


def private_key_to_address(priv_int, target_prefix):
    """Оптимизированная генерация только нужного типа адреса"""
    if not (1 <= priv_int <= config.MAX_KEY):
        return None, None
    try:
        # Определяем тип адреса по префиксу
        if target_prefix.startswith('1'):
            addr_type = 'p2pkh'
        elif target_prefix.startswith('3'):
            addr_type = 'p2sh'
        else:
            addr_type = None

        # Генерация публичного ключа
        priv_bytes = priv_int.to_bytes(32, 'big')
        priv = PrivateKey(priv_bytes)
        pub = priv.public_key.format(compressed=True)

        # Хеширование публичного ключа
        pub_sha = sha256(pub).digest()
        ripemd = new_ripemd160()
        ripemd.update(pub_sha)
        pub_ripemd = ripemd.digest()

        # Генерация ТОЛЬКО нужного типа адреса
        if addr_type == 'p2pkh':
            address = _generate_p2pkh(pub_ripemd)
            return address, None
        elif addr_type == 'p2sh':
            address = _generate_p2sh(pub_ripemd)
            return None, address
        else:
            # Для неизвестных префиксов генерируем оба (редкий случай)
            return _generate_p2pkh(pub_ripemd), _generate_p2sh(pub_ripemd)

    except Exception as e:
        logger.error(f"Ошибка генерации адреса: {str(e)}")
        return None, None


def process_key(key_int, target_prefix, addr_type, worker_id, queue):
    """Обрабатывает один ключ (оптимизированная версия)"""
    hex_key = f"{key_int:064x}"
    addr_p2pkh, addr_p2sh = private_key_to_address(key_int, target_prefix)

    if addr_type == 'p2pkh' and addr_p2pkh and addr_p2pkh.startswith(target_prefix):
        wif_key = private_key_to_wif(hex_key)
        safe_queue_put(queue, create_found_message(addr_p2pkh, hex_key, wif_key, worker_id), timeout=1.0)
        return True
    elif addr_type == 'p2sh' and addr_p2sh and addr_p2sh.startswith(target_prefix):
        wif_key = private_key_to_wif(hex_key)
        safe_queue_put(queue, create_found_message(addr_p2sh, hex_key, wif_key, worker_id), timeout=1.0)
        return True
    elif not addr_type:
        if addr_p2pkh and addr_p2pkh.startswith(target_prefix):
            wif_key = private_key_to_wif(hex_key)
            safe_queue_put(queue, create_found_message(addr_p2pkh, hex_key, wif_key, worker_id), timeout=1.0)
            return True
        if addr_p2sh and addr_p2sh.startswith(target_prefix):
            wif_key = private_key_to_wif(hex_key)
            safe_queue_put(queue, create_found_message(addr_p2sh, hex_key, wif_key, worker_id), timeout=1.0)
            return True
    return False


def worker_main(target_prefix, start_int, end_int, attempts, mode, worker_id, total_workers, queue, shutdown_event):
    """Основная функция CPU воркера (оптимизированная)"""
    logger.info(f"Worker {worker_id} started in {mode} mode")
    try:
        # Предварительная обработка параметров
        addr_type = 'p2pkh' if target_prefix.startswith('1') else 'p2sh' if target_prefix.startswith('3') else None
        rng = random.SystemRandom()
        total_scanned = 0
        total_found = 0
        start_time = time.time()
        last_update = start_time
        last_scanned = 0
        stats_interval = 2.0

        # Локальные ссылки для ускорения доступа
        _process_key = process_key
        _safe_queue_put = safe_queue_put
        _create_stats_message = create_stats_message
        _create_log_message = create_log_message
        _time = time.time

        _safe_queue_put(queue, _create_log_message(f"Воркер {worker_id} запущен"))

        if mode == "sequential":
            total_keys = end_int - start_int + 1
            if total_keys <= 0:
                _safe_queue_put(queue, _create_log_message(f"Invalid key range: {start_int}-{end_int}"))
                return

            # Распределение диапазона между воркерами
            chunk_size = total_keys // total_workers
            chunk_start = start_int + worker_id * chunk_size
            chunk_end = chunk_start + chunk_size - 1
            if worker_id == total_workers - 1:
                chunk_end = end_int

            current = chunk_start
            total_in_chunk = chunk_end - chunk_start + 1

            _safe_queue_put(queue, _create_log_message(
                f"Воркер {worker_id} начал последовательный поиск: {chunk_start}-{chunk_end} ({total_in_chunk} ключей)"))

            # Основной цикл обработки ключей
            for key_int in range(chunk_start, chunk_end + 1):
                if shutdown_event.is_set():
                    _safe_queue_put(queue, _create_log_message(f"Воркер {worker_id} получил сигнал остановки"))
                    break

                if _process_key(key_int, target_prefix, addr_type, worker_id, queue):
                    total_found += 1
                total_scanned += 1

                # Обновление статистики
                current_time = _time()
                if current_time - last_update >= stats_interval:
                    elapsed = max(0.001, current_time - last_update)
                    speed = (total_scanned - last_scanned) / elapsed
                    processed = key_int - chunk_start + 1
                    progress = min(100, int(processed / total_in_chunk * 100))
                    _safe_queue_put(queue,
                                    _create_stats_message(total_scanned, total_found, speed, progress, worker_id))
                    last_update = current_time
                    last_scanned = total_scanned

            # Финальное обновление статистики
            elapsed = max(0.001, _time() - start_time)
            speed = total_scanned / elapsed
            progress = 100
            _safe_queue_put(queue, _create_stats_message(total_scanned, total_found, speed, progress, worker_id))

        elif mode == "random":
            base_attempts = attempts // total_workers
            total_attempts = base_attempts + (1 if worker_id < (attempts % total_workers) else 0)

            _safe_queue_put(queue,
                            _create_log_message(f"Воркер {worker_id} начал случайный поиск: {total_attempts} попыток"))

            # Основной цикл обработки ключей
            for idx in range(total_attempts):
                if shutdown_event.is_set():
                    break

                # Стало:
                if not hasattr(worker_main, 'rng'):
                    worker_main.rng = random.SystemRandom()
                key_int = rng.randint(start_int, end_int)

                if _process_key(key_int, target_prefix, addr_type, worker_id, queue):
                    total_found += 1
                total_scanned += 1

                # Обновление статистики
                current_time = _time()
                if current_time - last_update >= stats_interval:
                    elapsed = max(0.001, current_time - last_update)
                    speed = (total_scanned - last_scanned) / elapsed
                    progress = min(100, int((idx + 1) / total_attempts * 100))
                    _safe_queue_put(queue,
                                    _create_stats_message(total_scanned, total_found, speed, progress, worker_id))
                    last_update = current_time
                    last_scanned = total_scanned

            # Финальное обновление статистики
            elapsed = max(0.001, _time() - start_time)
            speed = total_scanned / elapsed
            progress = 100
            _safe_queue_put(queue, _create_stats_message(total_scanned, total_found, speed, progress, worker_id))

        _safe_queue_put(queue, _create_log_message(f"Воркер {worker_id} успешно завершен"), timeout=1.0)
        _safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)

    except Exception as e:
        logger.exception(f"Critical error in worker {worker_id}")
        _safe_queue_put(queue, _create_log_message(f"Критическая ошибка в воркере {worker_id}: {str(e)}"), timeout=1.0)
        _safe_queue_put(queue, {"type": "worker_finished", "worker_id": worker_id}, timeout=1.0)


def stop_cpu_search(processes, shutdown_event):
    """Остановка CPU поиска"""
    logger.info("Остановка CPU процессов...")
    shutdown_event.set()

    # Даем воркерам время на завершение
    start_time = time.time()
    timeout = 10  # Максимальное время ожидания

    while time.time() - start_time < timeout and any(p.is_alive() for p in processes.values()):
        time.sleep(0.5)

    # Принудительное завершение оставшихся процессов
    for worker_id, process in list(processes.items()):
        if process.is_alive():
            try:
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
            except Exception as e:
                logger.error(f"Ошибка остановки воркера {worker_id}: {str(e)}")

    processes.clear()
    shutdown_event.clear()
    logger.info("CPU процессы остановлены.")