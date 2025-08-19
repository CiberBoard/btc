import subprocess
import time
import random
import platform
import logging

import logger
from PyQt5.QtCore import QThread, pyqtSignal


try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None
    btc.warning("pynvml не найден. Мониторинг GPU будет недоступен.")


try:
    import win32process
    import win32api

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

import config
from utils.helpers import validate_key_range, private_key_to_wif

logger = logging.getLogger('bitcoin_scanner')


class OptimizedOutputReader(QThread):
    """Чтение вывода GPU процесса"""
    log_message = pyqtSignal(str, str)  # message, level
    stats_update = pyqtSignal(dict)  # {'speed': float, 'checked': int}
    found_key = pyqtSignal(dict)  # key_data dict
    process_finished = pyqtSignal()

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self.current_address = None
        self.current_private_key = None
        self.last_speed = 0.0
        self.last_checked = 0

    def run(self):
        buffer = ""
        try:
            while self.process and self.process.poll() is None:
                chunk = self.process.stdout.read(1024)
                if chunk:
                    buffer += chunk
                    lines = buffer.split('\n')
                    buffer = lines[-1]
                    for line in lines[:-1]:
                        if line.strip():
                            self.process_line(line.strip())
                # Обрабатываем буфер чаще
                # QApplication.processEvents() - не используем, так как это не UI поток
                time.sleep(0.01)  # Небольшая задержка для снижения нагрузки
            if buffer.strip():
                for line in buffer.strip().split('\n'):
                    self.process_line(line.strip())
        except Exception as e:
            logger.exception("Ошибка чтения вывода GPU")
            self.log_message.emit(f"Ошибка чтения вывода: {str(e)}", "error")
        finally:
            self.process_finished.emit()

    def process_line(self, line):
        """Обработка строки вывода GPU"""
        line_lower = line.lower()
        if "ошибка" in line or "error" in line_lower:
            self.log_message.emit(line, "error")
            logger.error(f"GPU Error: {line}")
        elif "найден ключ" in line or "found key" in line_lower:
            self.log_message.emit(line, "success")
            logger.info(f"GPU Key Found: {line}")
        else:
            self.log_message.emit(line, "normal")
            logger.debug(f"GPU Output: {line}")

        # Обработка статистики
        speed_match = config.SPEED_REGEX.search(line)
        total_match = config.TOTAL_REGEX.search(line)
        if speed_match or total_match:
            speed = float(speed_match.group(1)) if speed_match else self.last_speed
            checked = int(total_match.group(1).replace(',', '')) if total_match else self.last_checked
            # Сохраняем последние значения
            if speed_match: self.last_speed = speed
            if total_match: self.last_checked = checked
            self.stats_update.emit({'speed': speed, 'checked': checked})

        # Обработка найденного ключа
        addr_match = config.ADDR_REGEX.search(line)
        if addr_match:
            self.current_address = addr_match.group(1)
        key_match = config.KEY_REGEX.search(line)
        if key_match:
            self.current_private_key = key_match.group(1)

        if self.current_address and self.current_private_key:
            self.process_found_key()

    def process_found_key(self):
        """Обработка найденного ключа"""
        try:
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
            self.current_address = None
            self.current_private_key = None
        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.log_message.emit(f"Ошибка обработки найденного ключа: {str(e)}", "error")


def start_gpu_search_with_range(target_address, start_key, end_key, device, blocks, threads, points, priority_index,
                                parent_window):
    """Запускает GPU поиск с указанным диапазоном"""
    logger.info(f"Запуск GPU поиска для диапазона {hex(start_key)} - {hex(end_key)} на устройстве {device}")

    cmd = [
        config.CUBITCRACK_EXE,
        "-d", str(device),
        "-b", str(blocks),
        "-t", str(threads),
        "-p", str(points),
        "--keyspace", f"{hex(start_key)[2:].upper()}:{hex(end_key)[2:].upper()}",
        target_address
    ]

    # Установка приоритета процесса (Windows)
    creationflags = 0
    if platform.system() == 'Windows':
        priority_value = config.WINDOWS_GPU_PRIORITY_MAP.get(priority_index,
                                                             0x00000020)  # NORMAL_PRIORITY_CLASS по умолчанию
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | priority_value

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
        # output_reader.log_message.connect(parent_window.append_log) # Будет подключено в UI
        # output_reader.stats_update.connect(parent_window.update_gpu_stats_display)
        # output_reader.found_key.connect(parent_window.handle_found_key)
        # output_reader.process_finished.connect(parent_window.handle_gpu_search_finished)

        # Установка приоритета для Windows (дополнительно)
        if platform.system() == 'Windows' and priority_index > 0 and WIN32_AVAILABLE:
            try:
                priority_value = config.WINDOWS_GPU_PRIORITY_MAP.get(priority_index, 0x00000020)
                handle = win32api.OpenProcess(win32process.PROCESS_ALL_ACCESS, True, cuda_process.pid)
                win32process.SetPriorityClass(handle, priority_value)
            except Exception as e:
                logger.error(f"Ошибка установки приоритета: {str(e)}")

        return cuda_process, output_reader

    except Exception as e:
        logger.exception(f"Ошибка запуска cuBitcrack на устройстве {device}")
        raise e  # Передаем исключение в вызывающий код


def stop_gpu_search_internal(processes):
    """Внутренняя остановка GPU поиска"""
    logger.info("Остановка GPU процессов...")
    for process, reader in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
        try:
            reader.quit()
            reader.wait(1000)
        except:
            pass
    processes.clear()
    logger.info("GPU процессы остановлены.")


def generate_gpu_random_range(global_start_hex, global_end_hex, min_range_size_str, max_range_size_str, used_ranges,
                              max_saved_random):
    """Генерирует уникальный случайный диапазон в пределах пользовательского диапазона"""
    try:
        # Получаем глобальные границы
        global_result, error = validate_key_range(global_start_hex, global_end_hex)
        if global_result is None:
            logger.error(f"Ошибка глобального диапазона: {error}")
            # Возвращаем ошибку, чтобы UI мог ее отобразить
            return None, None, error
        global_start, global_end, total_keys = global_result

        # Получаем размеры диапазона
        try:
            min_range_size = int(min_range_size_str)
            max_range_size = int(max_range_size_str)
        except ValueError:
            error_msg = "Минимальный и максимальный диапазон должны быть числами"
            logger.error(error_msg)
            return None, None, error_msg

        # Корректируем размеры диапазона
        if min_range_size <= 0 or max_range_size <= 0:
            error_msg = "Размеры диапазона должны быть положительными числами"
            logger.error(error_msg)
            return None, None, error_msg
        if min_range_size > total_keys:
            min_range_size = total_keys
        if max_range_size > total_keys:
            max_range_size = total_keys
        if min_range_size > max_range_size:
            min_range_size, max_range_size = max_range_size, min_range_size

        # Генерируем случайный размер диапазона
        range_size = random.randint(min_range_size, max_range_size)

        # Генерируем случайную начальную точку
        max_start = global_end - range_size + 1
        if max_start < global_start:
            max_start = global_start

        # Используем системный RNG для безопасности
        if platform.system() == 'Windows':
            start_key = random.SystemRandom().randint(global_start, max_start)
        else:
            # Используем /dev/urandom для лучшей энтропии на Linux
            try:
                with open('/dev/urandom', 'rb') as f:
                    rand_bytes = f.read(8)
                    rand_val = int.from_bytes(rand_bytes, 'big')
                start_key = global_start + (rand_val % (max_start - global_start + 1))
            except:
                # fallback на стандартный random
                start_key = random.randint(global_start, max_start)

        end_key = start_key + range_size - 1

        # Проверяем границы
        if end_key > global_end:
            end_key = global_end

        # Проверяем уникальность диапазона
        range_hash = f"{start_key}-{end_key}"
        if range_hash in used_ranges:
            # Если диапазон уже использовался, генерируем новый (ограничим рекурсию)
            # Используем итерацию вместо рекурсии, чтобы избежать RecursionError
            max_attempts = 100  # Ограничим количество попыток
            attempts = 0
            while range_hash in used_ranges and attempts < max_attempts:
                # Генерируем новый размер и стартовую точку
                range_size = random.randint(min_range_size, max_range_size)
                max_start = global_end - range_size + 1
                if max_start < global_start:
                    max_start = global_start
                if platform.system() == 'Windows':
                    start_key = random.SystemRandom().randint(global_start, max_start)
                else:
                    try:
                        with open('/dev/urandom', 'rb') as f:
                            rand_bytes = f.read(8)
                            rand_val = int.from_bytes(rand_bytes, 'big')
                        start_key = global_start + (rand_val % (max_start - global_start + 1))
                    except:
                        start_key = random.randint(global_start, max_start)
                end_key = start_key + range_size - 1
                if end_key > global_end:
                    end_key = global_end
                range_hash = f"{start_key}-{end_key}"
                attempts += 1

            if attempts >= max_attempts:
                # Если все диапазоны использованы или не удалось сгенерировать уникальный, очищаем историю
                if len(used_ranges) >= max_saved_random:
                    used_ranges.clear()
                # Или возвращаем ошибку
                # error_msg = "Не удалось сгенерировать уникальный диапазон после нескольких попыток"
                # logger.warning(error_msg)
                # return None, None, error_msg
                # Или продолжаем с текущим (неуникальным) диапазоном, если критично важно продолжить
                # pass # Просто используем последний сгенерированный диапазон

        # Сохраняем использованный диапазон
        used_ranges.add(range_hash)
        # if len(used_ranges) > max_saved_random: # Убираем это, так как set сам себя не ограничивает по размеру
        #     # Ограничиваем количество сохраненных диапазонов
        #     used_ranges.pop()  # set не поддерживает pop по индексу, удалим случайный
        #     # Лучше: использовать collections.deque(maxlen=max_saved_random) вместо set, если нужно ограничение

        return start_key, end_key, None

    except Exception as e:
        error_msg = f"Ошибка генерации диапазона GPU: {str(e)}"
        logger.exception(error_msg)
        return None, None, error_msg  # Возвращаем ошибку для отображения в UI


# В конце файла добавьте вспомогательную функцию (или лучше перенесите её в utils/helpers.py)
def get_gpu_status(device_id=0):
    """
    Получает статус GPU (загрузка, память и т.д.) через pynvml.
    :param device_id: ID устройства GPU (по умолчанию 0)
    :return: dict с информацией о GPU или None при ошибке
    """
    if not PYNVML_AVAILABLE:
        return None

    try:
        # Инициализация, если ещё не была выполнена
        # Лучше сделать это один раз при запуске приложения, например в __init__ главного окна
        # if not hasattr(get_gpu_status, '_initialized'):
        #     pynvml.nvmlInit()
        #     get_gpu_status._initialized = True

        # Получаем handle устройства
        handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)

        # Получаем утилизацию (загрузку)
        util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_util = util_info.gpu  # Загрузка в %

        # Получаем информацию о памяти
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_used_mb = mem_info.used / (1024 * 1024)
        mem_total_mb = mem_info.total / (1024 * 1024)
        mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0

        # Получаем температуру (опционально)
        try:
            temp_info = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            temperature = temp_info
        except pynvml.NVMLError:
            temperature = None # Температура может быть недоступна

        return {
            'device_id': device_id,
            'gpu_utilization': gpu_util,
            'memory_used_mb': mem_used_mb,
            'memory_total_mb': mem_total_mb,
            'memory_utilization': mem_util,
            'temperature': temperature
        }
    except Exception as e:
        logger.debug(f"Не удалось получить статус GPU {device_id}: {e}")
        return None