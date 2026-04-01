# ui/vanity_logic.py
import os
import subprocess
import time
import re
import platform
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from utils.helpers import setup_logger
import config

import logging  # ← ДОБАВЛЕНО

logger = logging.getLogger(__name__)


class VanityOutputReader(QThread):
    log_message = pyqtSignal(str, str)  # message, level
    stats_update = pyqtSignal(dict)  # {'speed': int, 'prob': float, 'found_count': int}
    key_found = pyqtSignal(dict)  # Новый сигнал для найденных ключей
    process_finished = pyqtSignal()

    def __init__(self, process, main_window, prefix):
        super().__init__()
        self.process = process
        self.main_window = main_window
        self.prefix = prefix
        self._running = True
        self.found_count = 0

    def stop(self):
        self._running = False

    def run(self):
        try:
            while self._running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                # ОТЛАДКА: выводим ВСЕ строки для диагностики
                self.log_message.emit(f"[VANITY] {line}", "debug")

                # Парсинг найденного адреса
                # Формат: "PubAddress: 1JasstXXX"
                if line.startswith("PubAddress:") or "Pub Addr:" in line:
                    self.log_message.emit(f"✅ Обнаружен адрес: {line}", "success")

                # Формат: "Priv (HEX): 1A2B3C..."
                if line.startswith("Priv (HEX):") or "PrivKey:" in line:
                    self.log_message.emit(f"🔑 Обнаружен ключ: {line}", "success")

                # Парсинг скорости: различные форматы
                # [1431.26 Mkey/s] или [GPU 1380.39 Mkey/s] или просто "1431.26 MK/s"
                speed_patterns = [
                    r"\[(\d+\.?\d*)\s*Mkey/s\]",
                    r"\[GPU\s+(\d+\.?\d*)\s*Mkey/s\]",
                    r"(\d+\.?\d*)\s*MK/s",
                    r"Speed:\s*(\d+\.?\d*)\s*MKey/s"
                ]

                for pattern in speed_patterns:
                    speed_match = re.search(pattern, line, re.IGNORECASE)
                    if speed_match:
                        try:
                            mkeys = float(speed_match.group(1))
                            keys_per_sec = int(mkeys * 1_000_000)
                            self.stats_update.emit({'speed': keys_per_sec})
                            break
                        except (ValueError, IndexError):
                            pass

                # Парсинг количества найденных: различные форматы
                # [Found 3] или (3 found) или "3 addresses found"
                found_patterns = [
                    r"\[Found\s+(\d+)\]",
                    r"\((\d+)\s+found\)",
                    r"(\d+)\s+addresses?\s+found"
                ]

                for pattern in found_patterns:
                    found_match = re.search(pattern, line, re.IGNORECASE)
                    if found_match:
                        try:
                            new_count = int(found_match.group(1))
                            if new_count > self.found_count:
                                self.found_count = new_count
                                self.stats_update.emit({'found_count': self.found_count})
                            break
                        except (ValueError, IndexError):
                            pass

        except Exception as e:
            logger.exception("Ошибка в VanityOutputReader")
            self.log_message.emit(f"❌ Ошибка чтения вывода: {e}", "error")
        finally:
            self.process_finished.emit()


class VanityLogic:
    def __init__(self, main_window):
        self.main_window = main_window
        self.process = None
        self.reader = None
        self.is_running = False
        self.start_time = None
        self.keys_found = 0
        self.prefix = ""
        self.output_file = ""
        self.last_file_size = 0
        self.last_file_lines = 0  # Отслеживаем количество строк

        # Таймер для обновления времени и чтения файла
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer_tick)

    def toggle_search(self):
        if self.is_running:
            self.stop_search()
        else:
            self.start_search()

    def start_search(self):
        prefix = self.main_window.vanity_prefix_edit.text().strip()
        if not prefix:
            self.main_window.append_log("❌ Укажите префикс адреса", "error")
            return

        exe_path = os.path.join(config.BASE_DIR, "VanitySearch.exe")
        if not os.path.exists(exe_path):
            self.main_window.append_log("❌ VanitySearch.exe не найден в корне проекта", "error")
            return

        cmd = [exe_path]

        # GPU/CPU
        gpu_text = self.main_window.vanity_gpu_combo.currentText().strip()
        use_cpu = (gpu_text == "CPU")
        if use_cpu:
            threads = self.main_window.vanity_cpu_spin.value()
            cmd.extend(["-t", str(threads)])
        else:
            cmd.append("-gpu")
            device_ids = gpu_text.replace(',', ' ').split()
            cmd.extend(["-gpuId"] + device_ids)

        # Тип адреса
        addr_type = self.main_window.vanity_type_combo.currentIndex()
        if addr_type == 1:  # P2SH (3...)
            cmd.append("-p2sh")
        elif addr_type == 2:  # Bech32 (bc1...)
            cmd.append("-bech32")
        elif addr_type == 3:  # Bech32m (bc1...)
            cmd.append("-bech32m")

        # Сжатие
        if not self.main_window.vanity_compressed_cb.isChecked():
            cmd.append("-u")  # uncompressed

        # Output file - явно указываем файл вывода
        output_file = os.path.join(config.BASE_DIR, f"VANITY_{prefix}.txt")
        cmd.extend(["-o", output_file])

        # Префикс — последний аргумент
        cmd.append(prefix)

        # Сохраняем для чтения файла
        self.prefix = prefix
        self.output_file = output_file
        self.last_file_size = 0
        self.last_file_lines = 0

        # Удаляем старый файл результатов, если существует
        if os.path.exists(self.output_file):
            try:
                os.remove(self.output_file)
                self.main_window.append_log(f"🗑️ Удален старый файл результатов", "normal")
            except:
                pass

        # Запуск
        try:
            self.main_window.append_log(f"🚀 Запуск VanitySearch: {' '.join(cmd)}", "info")

            # Создаем процесс с правильными параметрами
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,  # Добавляем stdin
                text=True,
                bufsize=1,
                cwd=config.BASE_DIR,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )

            self.reader = VanityOutputReader(self.process, self.main_window, prefix)
            self.reader.log_message.connect(self.main_window.append_log)
            self.reader.stats_update.connect(self.handle_stats)
            self.reader.process_finished.connect(self.search_finished)
            self.reader.start()

            self.is_running = True
            self.start_time = time.time()
            self.keys_found = 0
            self.main_window.vanity_start_stop_btn.setText("⏹ Остановить")
            self.main_window.vanity_status_label.setText("Статус: Генерация...")
            self.main_window.vanity_progress_bar.setRange(0, 0)  # indeterminate
            self.timer.start(1000)  # раз в секунду

            self.main_window.append_log(f"✅ VanitySearch запущен (PID: {self.process.pid})", "success")
            self.main_window.append_log(f"📁 Результаты будут сохранены в: {self.output_file}", "info")

        except Exception as e:
            self.main_window.append_log(f"❌ Ошибка запуска VanitySearch: {e}", "error")
            logger.exception("VanitySearch start failed")

    def handle_stats(self, stats):
        if 'speed' in stats:
            speed = stats['speed']
            # Форматируем скорость
            if speed >= 1_000_000_000:
                speed_str = f"{speed / 1_000_000_000:.2f} GKeys/s"
            elif speed >= 1_000_000:
                speed_str = f"{speed / 1_000_000:.2f} MKeys/s"
            elif speed >= 1_000:
                speed_str = f"{speed / 1_000:.2f} KKeys/s"
            else:
                speed_str = f"{speed} Keys/s"
            self.main_window.vanity_speed_label.setText(f"Скорость: {speed_str}")

        if 'found_count' in stats:
            if stats['found_count'] > self.keys_found:
                self.keys_found = stats['found_count']
                self.main_window.vanity_found_label.setText(f"Найдено: {self.keys_found}")
                self.main_window.append_log(f"🎉 Найден ключ #{self.keys_found}!", "success")

        if 'prob' in stats:
            pass

    def on_timer_tick(self):
        self.update_time_label()
        if self.is_running:
            self.check_output_file()

    def update_time_label(self):
        if self.start_time is None:
            return
        elapsed = time.time() - self.start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self.main_window.vanity_time_label.setText(f"Время: {h:02d}:{m:02d}:{s:02d}")

    def check_output_file(self):
        """Проверяет файл результатов на наличие новых найденных адресов"""
        try:
            if not os.path.exists(self.output_file):
                return

            # Читаем весь файл заново, если он изменился
            current_size = os.path.getsize(self.output_file)
            if current_size <= self.last_file_size:
                return

            with open(self.output_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Обрабатываем только новые строки
            new_lines = lines[self.last_file_lines:]
            self.last_file_lines = len(lines)
            self.last_file_size = current_size

            if not new_lines:
                return

            # VanitySearch форматы вывода:
            # Формат 1 (старые версии):
            # Addr: 1JasstXXX
            # Priv: 5J...WIF...
            #
            # Формат 2 (новые версии):
            # PubAddress: 1JasstXXX
            # Priv (HEX): 1a2b3c4d...
            # Priv (WIF): 5J...

            i = 0
            while i < len(new_lines):
                line = new_lines[i].strip()

                # Пропускаем пустые строки и комментарии
                if not line or line.startswith('#') or line.startswith('='):
                    i += 1
                    continue

                addr = None
                priv_hex = None
                priv_wif = None

                # Пытаемся найти адрес в текущей и следующих строках
                if 'PubAddress:' in line or 'Addr:' in line or line.startswith('1') or line.startswith(
                        '3') or line.startswith('bc1'):
                    # Извлекаем адрес
                    if ':' in line:
                        addr = line.split(':', 1)[1].strip()
                    else:
                        # Адрес может быть просто в строке
                        parts = line.split()
                        for part in parts:
                            if part.startswith('1') or part.startswith('3') or part.startswith('bc1'):
                                addr = part
                                break

                    # Ищем приватный ключ в следующих строках
                    j = i + 1
                    while j < len(new_lines) and j < i + 5:  # Смотрим до 5 строк вперед
                        next_line = new_lines[j].strip()

                        # HEX ключ
                        if ('Priv' in next_line and 'HEX' in next_line) or 'PrivKey' in next_line:
                            if ':' in next_line:
                                priv_hex = next_line.split(':', 1)[1].strip()

                        # WIF ключ
                        if ('Priv' in next_line and 'WIF' in next_line) or (
                                next_line.startswith('5') or next_line.startswith('K') or next_line.startswith('L')):
                            if ':' in next_line:
                                priv_wif = next_line.split(':', 1)[1].strip()
                            else:
                                # WIF может быть просто в строке
                                parts = next_line.split()
                                for part in parts:
                                    if part.startswith('5') or part.startswith('K') or part.startswith('L'):
                                        priv_wif = part
                                        break

                        # Простой формат: адрес<пробел>hex_key
                        if not priv_hex and len(next_line) > 50 and not ':' in next_line:
                            # Это может быть hex ключ
                            if all(c in '0123456789abcdefABCDEF ' for c in next_line):
                                priv_hex = next_line.strip()

                        j += 1

                    # Если нашли адрес и хотя бы один ключ
                    if addr and (priv_hex or priv_wif):
                        self.process_found_key(addr, priv_hex, priv_wif)
                        i = j  # Пропускаем обработанные строки
                        continue

                # Альтернативный формат: одна строка "Address PrivateKey"
                parts = line.split()
                if len(parts) == 2:
                    potential_addr = parts[0]
                    potential_key = parts[1]

                    # Проверяем, что первая часть похожа на адрес
                    if (potential_addr.startswith('1') or potential_addr.startswith('3') or potential_addr.startswith(
                            'bc1')):
                        # Вторая часть - ключ (HEX или WIF)
                        if len(potential_key) > 50:  # Длинный ключ
                            if all(c in '0123456789abcdefABCDEF' for c in potential_key):
                                # HEX ключ
                                self.process_found_key(potential_addr, potential_key, None)
                            else:
                                # WIF ключ
                                self.process_found_key(potential_addr, None, potential_key)

                i += 1

        except Exception as e:
            logger.exception("Ошибка при чтении файла результатов")
            self.main_window.append_log(f"❌ Ошибка чтения {self.output_file}: {e}", "error")

    def process_found_key(self, addr, priv_hex, priv_wif):
        """Обрабатывает найденный ключ"""
        try:
            # Если нет WIF, но есть HEX - конвертируем
            if priv_hex and not priv_wif:
                try:
                    from core.hextowif import hex_to_wif
                    # Убираем возможные пробелы и префиксы
                    priv_hex_clean = priv_hex.replace(' ', '').lstrip('0x')
                    if len(priv_hex_clean) % 2:
                        priv_hex_clean = '0' + priv_hex_clean

                    compressed = self.main_window.vanity_compressed_cb.isChecked()
                    priv_wif = hex_to_wif(priv_hex_clean, compressed=compressed, is_testnet=False)
                except Exception as e:
                    logger.error(f"Ошибка конвертации HEX→WIF: {e}")
                    priv_wif = "ERROR"

            # Если нет HEX, но есть WIF - пытаемся получить HEX
            if priv_wif and not priv_hex:
                try:
                    from core.hextowif import wif_to_hex
                    priv_hex = wif_to_hex(priv_wif)
                except Exception as e:
                    logger.error(f"Ошибка конвертации WIF→HEX: {e}")
                    priv_hex = "ERROR"

            data = {
                'address': addr,
                'hex_key': priv_hex or "N/A",
                'wif_key': priv_wif or "N/A",
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'VANITY'
            }

            # Обновляем UI
            self.main_window.vanity_result_addr.setText(addr)
            self.main_window.vanity_result_hex.setText(priv_hex or "N/A")
            self.main_window.vanity_result_wif.setText(priv_wif or "N/A")

            # Отправляем в таблицу найденных ключей
            self.main_window.handle_found_key(data)

            # Инкремент счетчика
            self.keys_found += 1
            self.main_window.vanity_found_label.setText(f"Найдено: {self.keys_found}")

            self.main_window.append_log(f"✅ Ключ #{self.keys_found} обработан: {addr[:20]}...", "success")

        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.main_window.append_log(f"❌ Ошибка обработки ключа: {e}", "error")

    def stop_search(self):
        if not self.is_running:
            return

        self.main_window.append_log("⏹ Остановка VanitySearch...", "warning")

        try:
            if self.process and self.process.poll() is None:
                if platform.system() == "Windows":
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.main_window.append_log("⚠️ Принудительное завершение процесса", "warning")
                        self.process.kill()
                        self.process.wait(timeout=2)
                else:
                    self.process.terminate()
                    self.process.wait(timeout=3)
        except Exception as e:
            logger.warning(f"Ошибка остановки VanitySearch: {e}")
            self.main_window.append_log(f"⚠️ Ошибка остановки: {e}", "warning")

        if self.reader:
            self.reader.stop()
            self.reader.wait(2000)

        # Последняя проверка файла результатов
        self.check_output_file()

        self.search_finished()

    def search_finished(self):
        self.is_running = False
        self.timer.stop()
        self.process = None
        self.reader = None

        self.main_window.vanity_start_stop_btn.setText("🚀 Запустить генерацию")
        self.main_window.vanity_status_label.setText("Статус: Готов")
        self.main_window.vanity_progress_bar.setRange(0, 100)
        self.main_window.vanity_progress_bar.setValue(0)
        self.main_window.vanity_progress_bar.setFormat("Готов")

        self.main_window.append_log(f"✅ VanitySearch завершен. Найдено ключей: {self.keys_found}", "success")