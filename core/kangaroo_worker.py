# core/kangaroo_worker.py
import os
import time
import random
import subprocess
import json
import re
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

    def stop(self):
        self._stop_requested = True

    def hex_to_int(self, h):
        return int(h.lower().replace("0x", ""), 16)

    def int_to_hex(self, x):
        return f"{x:064x}"

    def random_subrange(self, start, end, bits):
        if start >= end:
            raise ValueError("start >= end")
        width = 1 << bits
        total = end - start
        if total <= width:
            return start, end
        max_offset = total - width
        try:
            offset = random.randbelow(max_offset + 1)
        except AttributeError:
            bits_needed = max_offset.bit_length()
            while True:
                candidate = random.getrandbits(bits_needed)
                if candidate <= max_offset:
                    offset = candidate
                    break
        return start + offset, start + offset + width

    def run(self):
        try:
            # 🔴 ВАЖНО: не используем имена модулей (re, os, json и т.д.) как переменные!
            start_int = self.hex_to_int(self.params['rb_hex'])
            end_int = self.hex_to_int(self.params['re_hex'])
            if start_int > end_int:
                start_int, end_int = end_int, start_int
            if start_int == end_int:
                self.log_message.emit("[❌] rb == re")
                self.finished.emit(False)
                return

            os.makedirs(self.params['temp_dir'], exist_ok=True)

            session = 1
            while not self._stop_requested:
                s, e = self.random_subrange(start_int, end_int, self.params['subrange_bits'])
                sub_start_hex = self.int_to_hex(s)
                sub_end_hex = self.int_to_hex(e)

                self.range_update.emit(sub_start_hex, sub_end_hex)

                result_file = os.path.join(self.params['temp_dir'], f"result_{session}.txt")
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

                # Проверка существования EXE
                exe_path = os.path.abspath(self.params['etarkangaroo_exe'])
                self.log_message.emit(f"[🔧] Проверка EXE: {exe_path}")
                if not os.path.exists(self.params['etarkangaroo_exe']):
                    self.log_message.emit("[❌] Файл Kangaroo не найден!")
                    self.finished.emit(False)
                    return

                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True,
                        cwd=self.params['temp_dir']
                    )

                    start_time = time.time()
                    last_speed = 0.0
                    self._last_logged_line = ""

                    while proc.poll() is None and not self._stop_requested:
                        output = proc.stdout.readline()
                        if output:
                            # Очистка ANSI escape и whitespace
                            line = output.strip()
                            # Удаляем ANSI "erase to end of line": \x1b[K или \033[K
                            line = re.sub(r'\x1b\[[0-9;]*[KM]', '', line).strip()
                            if not line:
                                continue

                            # Пропускаем повторяющиеся строки
                            if line == self._last_logged_line:
                                continue
                            self._last_logged_line = line

                            self.log_message.emit(f"    {line}")

                            # 🔍 Парсим скорость: "<число> MKeys/s"
                            m = re.search(r'(\d+(?:\.\d+)?)\s*MKeys/s', line)
                            if m:
                                try:
                                    speed_val = float(m.group(1))
                                    last_speed = speed_val
                                    elapsed = int(time.time() - start_time)
                                    self.status_update.emit(last_speed, elapsed, session)
                                except (ValueError, TypeError):
                                    pass

                        # Принудительный таймаут сессии
                        if time.time() - start_time > self.params['scan_duration']:
                            break

                    # Завершаем процесс, если ещё работает
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            proc.kill()

                    # 🔍 Проверяем результат
                    if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
                        try:
                            with open(result_file, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read().strip()
                            if content:
                                # Формат: pubkey -> private_key
                                if "->" in content:
                                    parts = content.split("->", 1)
                                    private_raw = parts[1].strip()
                                    # Убираем 0x и приводим к нижнему регистру
                                    private_hex = private_raw.replace("0x", "").lower()
                                    # Оставляем только hex-цифры (на случай, если ключ в десятичной системе)
                                    private_hex = re.sub(r'[^a-fA-F0-9]', '', private_hex)

                                    # Если осталось мало символов — возможно, это десятичное число!
                                    # Пробуем интерпретировать как decimal, если строка состоит из цифр и длина < 60
                                    if private_hex.isdigit() and len(private_hex) < 64:
                                        try:
                                            dec_val = int(private_hex)
                                            private_hex = f"{dec_val:064x}"
                                        except (ValueError, OverflowError):
                                            pass  # оставляем как есть

                                    # Приводим к 64 hex символам
                                    if len(private_hex) > 64:
                                        private_hex = private_hex[-64:]
                                    elif len(private_hex) < 64:
                                        private_hex = private_hex.zfill(64)

                                    if len(private_hex) == 64:
                                        self.found_key.emit(private_hex)
                                        self.log_message.emit(f"[✅] Найден ключ: {private_hex}")
                                        self.finished.emit(True)
                                        return
                                    else:
                                        self.log_message.emit(
                                            f"[⚠️] Некорректная длина ключа: {len(private_hex)} (ожидается 64)")

                        except Exception as e:
                            self.log_message.emit(f"[⚠️] Ошибка чтения файла результата: {e}")

                except Exception as e:
                    self.log_message.emit(f"[⚠️] Ошибка запуска Kangaroo: {e}")

                session += 1
                if self._stop_requested:
                    break
                time.sleep(0.5)

            self.log_message.emit("[⏹️] Работа завершена (остановлено пользователем или исчерпаны сессии)")
            self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"[🔥] Критическая ошибка в KangarooWorker: {e}")
            import traceback
            self.log_message.emit(f"[🪵] Traceback:\n{traceback.format_exc()}")
            self.finished.emit(False)