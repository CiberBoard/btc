# core/kangaroo_worker.py
import os
import time
import random
import subprocess
import json
from PyQt5.QtCore import QObject, pyqtSignal

class KangarooWorker(QObject):
    log_message = pyqtSignal(str)
    status_update = pyqtSignal(float, int, int)  # speed_mkeys, elapsed_sec, session_num
    range_update = pyqtSignal(str, str)  # rb, re (hex)
    found_key = pyqtSignal(str)  # hex private key
    finished = pyqtSignal(bool)  # success

    def __init__(self, params):
        super().__init__()
        self.params = params
        self._stop_requested = False

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
            rb = self.hex_to_int(self.params['rb_hex'])
            re = self.hex_to_int(self.params['re_hex'])
            if rb > re:
                rb, re = re, rb
            if rb == re:
                self.log_message.emit("[❌] rb == re")
                self.finished.emit(False)
                return

            os.makedirs(self.params['temp_dir'], exist_ok=True)

            session = 1
            while not self._stop_requested:
                s, e = self.random_subrange(rb, re, self.params['subrange_bits'])
                rs = self.int_to_hex(s)
                re_ = self.int_to_hex(e)

                self.range_update.emit(rs, re_)

                result_file = os.path.join(self.params['temp_dir'], f"result_{session}.txt")
                cmd = [
                    self.params['etarkangaroo_exe'],
                    "-dp", str(self.params['dp']),
                    "-grid", self.params['grid_params'],
                    "-rb", rs,
                    "-re", re_,
                    "-pub", self.params['pubkey_hex'],
                    "-o", result_file
                ]

                self.log_message.emit(f"[🚀] Сессия #{session}: {' '.join(cmd)}")

                try:
                    self.log_message.emit(f"[🔧] Проверка EXE: {os.path.abspath(self.params['etarkangaroo_exe'])}")
                    if not os.path.exists(self.params['etarkangaroo_exe']):
                        self.log_message.emit(f"[❌] Файл не найден!")
                        self.finished.emit(False)
                        return

                    self.log_message.emit(f"[🛠️] Текущая раб. директория: {os.getcwd()}")
                    self.log_message.emit(f"[📦] Команда: {' '.join(cmd)}")
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )

                    start_time = time.time()
                    lines_emitted = 0
                    last_speed = 0.0
                    while proc.poll() is None and not self._stop_requested:
                        output = proc.stdout.readline()
                        if output:
                            line = output.strip()
                            if line:
                                self.log_message.emit(f"    {line}")
                                # Извлекаем скорость из лога, например: "1884 MKeys/s"
                                if "MKeys/s" in line and "[" in line:
                                    try:
                                        speed_part = line.split("MKeys/s")[0]
                                        speed_val = float(speed_part.split()[-1])
                                        last_speed = speed_val
                                    except:
                                        pass
                            lines_emitted += 1
                            if lines_emitted % 10 == 0:  # раз в 10 строк — обновляем статус
                                elapsed = int(time.time() - start_time)
                                self.status_update.emit(last_speed, elapsed, session)

                        if time.time() - start_time > self.params['scan_duration']:
                            break

                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except:
                            proc.kill()

                    # Проверка результата
                    if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
                        with open(result_file, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().strip()
                        if content:
                            # Формат: pubkey -> private_key
                            # Пример: 02... -> ed0d5b8c...c5d5ce6123f2
                            if "->" in content:
                                private_hex = content.split("->")[1].strip()
                                # Убираем возможные 0x и приводим к 64 символам
                                private_hex = private_hex.replace("0x", "").lower()
                                if len(private_hex) > 64:
                                    private_hex = private_hex[-64:]
                                elif len(private_hex) < 64:
                                    private_hex = private_hex.zfill(64)
                                self.found_key.emit(private_hex)
                                self.finished.emit(True)
                                return

                except Exception as e:
                    self.log_message.emit(f"[⚠️] Ошибка: {e}")

                session += 1
                if self._stop_requested:
                    break
                time.sleep(0.5)

            self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"[🔥] Критическая ошибка: {e}")
            self.finished.emit(False)