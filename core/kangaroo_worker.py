# core/kangaroo_worker.py
import os
import time
import random
import subprocess
import json
import re
import select
import sys
import traceback
from PyQt5.QtCore import QObject, pyqtSignal


class KangarooWorker(QObject):
    log_message = pyqtSignal(str)
    status_update = pyqtSignal(float, int, int)  # speed_mkeys, elapsed_sec, session_num
    range_update = pyqtSignal(str, str)  # sub_start_hex, sub_end_hex (hex)
    found_key = pyqtSignal(str)  # hex private key
    finished = pyqtSignal(bool)  # success

    def __init__(self, params):
        super().__init__()
        self.params = params
        self._stop_requested = False
        self._last_logged_line = ""
        self._validate_params()

    def _validate_params(self):
        """Валидация входных параметров"""
        required = ['rb_hex', 're_hex', 'pubkey_hex', 'etarkangaroo_exe',
                    'temp_dir', 'dp', 'grid_params', 'subrange_bits', 'scan_duration']

        for key in required:
            if key not in self.params:
                raise ValueError(f"Отсутствует обязательный параметр: {key}")

        # Проверка hex-значений
        for hex_key in ['rb_hex', 're_hex', 'pubkey_hex']:
            try:
                int(self.params[hex_key].replace('0x', ''), 16)
            except ValueError:
                raise ValueError(f"Некорректное hex-значение в {hex_key}: {self.params[hex_key]}")

        # Проверка существования EXE
        if not os.path.isfile(self.params['etarkangaroo_exe']):
            raise FileNotFoundError(f"Не найден файл: {self.params['etarkangaroo_exe']}")

        # Проверка числовых параметров
        if not isinstance(self.params['dp'], (int, str)):
            raise ValueError(f"dp должен быть числом, получено: {type(self.params['dp'])}")

        if self.params['subrange_bits'] < 1 or self.params['subrange_bits'] > 256:
            raise ValueError(f"subrange_bits должен быть в диапазоне 1-256, получено: {self.params['subrange_bits']}")

    def stop(self):
        """Запрос на остановку воркера"""
        self._stop_requested = True

    def hex_to_int(self, hex_str):
        """Преобразование hex-строки в int"""
        return int(hex_str.lower().replace("0x", ""), 16)

    def int_to_hex(self, value):
        """Преобразование int в 64-символьную hex-строку"""
        return f"{value:064x}"

    def random_subrange(self, start, end, bits):
        """
        Генерирует случайный подзадача в диапазоне [start, end)

        Args:
            start: начало диапазона (int)
            end: конец диапазона (int)
            bits: размер подзадачи в битах

        Returns:
            tuple: (sub_start, sub_end)
        """
        if start >= end:
            raise ValueError(f"Некорректный диапазон: start={start} >= end={end}")

        width = 1 << bits
        total = end - start

        if total <= width:
            return start, end

        max_offset = total - width

        # Генерация случайного смещения
        try:
            offset = random.randbelow(max_offset + 1)
        except AttributeError:
            # Для старых версий Python без randbelow
            bits_needed = max_offset.bit_length()
            while True:
                candidate = random.getrandbits(bits_needed)
                if candidate <= max_offset:
                    offset = candidate
                    break

        return start + offset, start + offset + width

    def _parse_private_key(self, raw_result):
        """
        Парсинг приватного ключа из результата Kangaroo

        Поддерживаемые форматы:
        - "Pub: <pubkey>\\nPriv: 0x<key>"
        - "pubkey -> private_key"

        Args:
            raw_result: строка с результатом

        Returns:
            str: 64-символьный hex-ключ или None при ошибке
        """
        try:
            # Формат 1: Многострочный "Pub: ... Priv: ..."
            priv_match = re.search(r'Priv:\s*(?:0x)?([0-9a-fA-F]+)', raw_result, re.IGNORECASE)
            if priv_match:
                clean = priv_match.group(1).strip()
                return self._convert_to_hex_key(clean)

            # Формат 2: Однострочный "pubkey -> private_key"
            if "->" in raw_result:
                parts = raw_result.split("->", 1)
                if len(parts) == 2:
                    clean = parts[1].strip().replace("0x", "").replace("0X", "")
                    return self._convert_to_hex_key(clean)

            self.log_message.emit(f"[⚠️] Неожиданный формат результата: {raw_result[:200]}")
            return None

        except (ValueError, OverflowError, IndexError) as e:
            self.log_message.emit(f"[⚠️] Ошибка парсинга ключа: {e}")
            return None

    def _convert_to_hex_key(self, clean_str):
        """
        Преобразование строки в 64-символьный hex-ключ

        Args:
            clean_str: очищенная строка (без 0x)

        Returns:
            str: 64-символьный hex или None
        """
        try:
            # Попытка интерпретации как hex
            if re.match(r'^[0-9a-fA-F]+$', clean_str):
                key_int = int(clean_str, 16)
            elif clean_str.isdigit():
                # Если только цифры — возможно decimal
                key_int = int(clean_str, 10)
            else:
                # Удаляем всё нехексовое и пробуем снова
                clean_str = re.sub(r'[^0-9a-fA-F]', '', clean_str)
                if not clean_str:
                    return None
                key_int = int(clean_str, 16)

            # Форматируем в 64-символьный hex
            private_hex = f"{key_int:064x}"

            if len(private_hex) != 64:
                self.log_message.emit(f"[⚠️] Некорректная длина ключа: {len(private_hex)}")
                return None

            return private_hex

        except (ValueError, OverflowError) as e:
            self.log_message.emit(f"[⚠️] Ошибка конвертации ключа: {e}")
            return None

    def _cleanup_temp_file(self, filepath):
        """Безопасное удаление временного файла"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError as e:
            self.log_message.emit(f"[⚠️] Не удалось удалить {filepath}: {e}")

    def _save_found_key(self, private_key, start_hex, end_hex, session):
        """
        Сохранение найденного ключа в постоянный файл

        Args:
            private_key: найденный приватный ключ (hex)
            start_hex: начало диапазона поиска
            end_hex: конец диапазона поиска
            session: номер сессии
        """
        try:
            # Файл для сохранения всех найденных ключей
            found_keys_file = os.path.join(self.params['temp_dir'], "found_keys.txt")

            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            pubkey = self.params.get('pubkey_hex', 'N/A')

            # Формируем строку для записи
            log_entry = (
                f"{'=' * 80}\n"
                f"[НАЙДЕН КЛЮЧ] {timestamp}\n"
                f"Сессия: #{session}\n"
                f"Приватный ключ (HEX): {private_key}\n"
                f"Публичный ключ: {pubkey}\n"
                f"Диапазон поиска: {start_hex} - {end_hex}\n"
                f"{'=' * 80}\n\n"
            )

            # Дописываем в файл (append mode)
            with open(found_keys_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

            self.log_message.emit(f"[💾] Ключ сохранён в {found_keys_file}")

            # Дополнительно: сохраняем в JSON для программной обработки
            self._save_found_key_json(private_key, start_hex, end_hex, session, timestamp)

        except Exception as e:
            self.log_message.emit(f"[⚠️] Не удалось сохранить ключ в файл: {e}")
            # Критическая ошибка - логируем в консоль
            print(f"ERROR saving key: {traceback.format_exc()}")

    def _save_found_key_json(self, private_key, start_hex, end_hex, session, timestamp):
        """Сохранение найденного ключа в JSON формате"""
        try:
            json_file = os.path.join(self.params['temp_dir'], "found_keys.json")

            # Подготовка данных
            key_data = {
                'timestamp': timestamp,
                'session': session,
                'private_key_hex': private_key,
                'public_key': self.params.get('pubkey_hex', 'N/A'),
                'range_start': start_hex,
                'range_end': end_hex,
                'dp': self.params.get('dp', 'N/A'),
                'grid_params': self.params.get('grid_params', 'N/A')
            }

            # Читаем существующие данные или создаём новый список
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                except (json.JSONDecodeError, ValueError):
                    data = []
            else:
                data = []

            # Добавляем новый ключ
            data.append(key_data)

            # Записываем обратно
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.log_message.emit(f"[💾] Ключ также сохранён в JSON: {json_file}")

        except Exception as e:
            self.log_message.emit(f"[⚠️] Не удалось сохранить JSON: {e}")

    def _read_result_file(self, result_file):
        """
        Чтение и парсинг файла с результатом

        Returns:
            str: приватный ключ или None
        """
        if not os.path.exists(result_file):
            return None

        if os.path.getsize(result_file) == 0:
            return None

        try:
            with open(result_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()

            if not content:
                return None

            return self._parse_private_key(content)

        except Exception as e:
            self.log_message.emit(f"[⚠️] Ошибка чтения файла результата: {e}")
            return None

    def _terminate_process(self, proc):
        """Корректное завершение процесса без утечек"""
        if proc.poll() is None:
            self.log_message.emit("[⏸️] Остановка процесса Kangaroo...")
            proc.terminate()

            try:
                proc.wait(timeout=3)
                self.log_message.emit("[✓] Процесс остановлен корректно")
            except subprocess.TimeoutExpired:
                self.log_message.emit("[⚠️] Процесс не ответил, выполняется kill...")
                proc.kill()
                proc.wait()  # КРИТИЧНО: ждём завершения после kill()
                self.log_message.emit("[✓] Процесс принудительно завершён")

    def _run_kangaroo_session(self, session, sub_start_hex, sub_end_hex):
        """
        Запуск одной сессии Kangaroo

        Returns:
            str: приватный ключ если найден, иначе None
        """
        result_file = os.path.join(self.params['temp_dir'], f"result_{session}.txt")

        # Удаляем старый файл результата, если есть
        self._cleanup_temp_file(result_file)

        cmd = [
            self.params['etarkangaroo_exe'],
            "-dp", str(self.params['dp']),
            "-grid", self.params['grid_params'],
            "-rb", sub_start_hex,
            "-re", sub_end_hex,
            "-pub", self.params['pubkey_hex'],
            "-o", result_file
        ]

        self.log_message.emit(f"[🚀] Сессия #{session}: Запуск Kangaroo")
        self.log_message.emit(f"[📦] Команда: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.params['temp_dir']
            )

            start_time = time.time()
            last_speed = 0.0
            self._last_logged_line = ""

            # Для Windows используем альтернативный подход
            is_windows = sys.platform.startswith('win')

            while proc.poll() is None and not self._stop_requested:
                # Проверка таймаута
                if time.time() - start_time > self.params['scan_duration']:
                    self.log_message.emit(f"[⏰] Таймаут сессии ({self.params['scan_duration']}s)")
                    break

                # Неблокирующее чтение (для Unix-like систем)
                if not is_windows:
                    try:
                        readable, _, _ = select.select([proc.stdout], [], [], 0.1)
                        if not readable:
                            continue
                    except:
                        # Если select не работает, используем обычное чтение
                        pass

                try:
                    output = proc.stdout.readline()
                    if not output:
                        if is_windows:
                            time.sleep(0.1)
                        continue

                    # Очистка ANSI escape-кодов и whitespace
                    line = output.strip()
                    line = re.sub(r'\x1b\[[0-9;]*[KM]', '', line).strip()

                    if not line or line == self._last_logged_line:
                        continue

                    self._last_logged_line = line
                    self.log_message.emit(f"    {line}")

                    # Парсинг скорости: "<число> MKeys/s"
                    match = re.search(r'(\d+(?:\.\d+)?)\s*MKeys/s', line)
                    if match:
                        try:
                            speed_val = float(match.group(1))
                            last_speed = speed_val
                            elapsed = int(time.time() - start_time)
                            self.status_update.emit(last_speed, elapsed, session)
                        except (ValueError, TypeError):
                            pass

                except Exception as e:
                    self.log_message.emit(f"[⚠️] Ошибка чтения вывода: {e}")
                    break

            # Корректное завершение процесса
            self._terminate_process(proc)

            # Проверка stderr на ошибки
            try:
                stderr_output = proc.stderr.read()
                if stderr_output:
                    self.log_message.emit(f"[⚠️] STDERR: {stderr_output[:500]}")
            except:
                pass

            # Проверка результата
            private_key = self._read_result_file(result_file)

            # Если ключ найден, сохраняем его в постоянный файл
            if private_key:
                self._save_found_key(private_key, sub_start_hex, sub_end_hex, session)

            # Очистка временного файла (безопасно, ключ уже в памяти и сохранён)
            self._cleanup_temp_file(result_file)

            return private_key

        except Exception as e:
            self.log_message.emit(f"[⚠️] Ошибка запуска Kangaroo: {e}")
            self.log_message.emit(f"[🪵] Traceback:\n{traceback.format_exc()}")
            return None

    def run(self):
        """Основной цикл работы воркера"""
        try:
            # Парсинг диапазона
            start_int = self.hex_to_int(self.params['rb_hex'])
            end_int = self.hex_to_int(self.params['re_hex'])

            if start_int > end_int:
                start_int, end_int = end_int, start_int
                self.log_message.emit("[⚠️] Диапазон был инвертирован (rb > re)")

            if start_int == end_int:
                self.log_message.emit("[❌] Ошибка: rb == re (нулевой диапазон)")
                self.finished.emit(False)
                return

            # Создание временной директории
            os.makedirs(self.params['temp_dir'], exist_ok=True)
            self.log_message.emit(f"[📁] Временная директория: {self.params['temp_dir']}")

            # Логирование параметров
            range_bits = (end_int - start_int).bit_length()
            self.log_message.emit(f"[📊] Полный диапазон: {range_bits} бит")
            self.log_message.emit(f"[📊] Размер подзадачи: {self.params['subrange_bits']} бит")
            self.log_message.emit(f"[⏱️] Таймаут сессии: {self.params['scan_duration']}s")

            session = 1

            # Основной цикл сессий
            while not self._stop_requested:
                # Генерация случайного подзадачи
                sub_start, sub_end = self.random_subrange(
                    start_int,
                    end_int,
                    self.params['subrange_bits']
                )

                sub_start_hex = self.int_to_hex(sub_start)
                sub_end_hex = self.int_to_hex(sub_end)

                self.range_update.emit(sub_start_hex, sub_end_hex)
                self.log_message.emit(
                    f"[🎲] Подзадача: {sub_start_hex[:16]}...{sub_start_hex[-8:]} -> {sub_end_hex[-8:]}")

                # Запуск сессии
                private_key = self._run_kangaroo_session(session, sub_start_hex, sub_end_hex)

                # Проверка результата
                if private_key:
                    self.found_key.emit(private_key)
                    self.log_message.emit(f"[✅] НАЙДЕН КЛЮЧ: {private_key}")
                    self.finished.emit(True)
                    return

                if self._stop_requested:
                    break

                session += 1
                time.sleep(0.5)  # Небольшая пауза между сессиями

            self.log_message.emit("[⏹️] Работа завершена (остановлено пользователем)")
            self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"[🔥] Критическая ошибка в KangarooWorker: {e}")
            self.log_message.emit(f"[🪵] Traceback:\n{traceback.format_exc()}")
            self.finished.emit(False)