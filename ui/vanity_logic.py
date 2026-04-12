# ui/vanity_logic.py
from __future__ import annotations

import os
import subprocess
import time
import re
import platform
import logging
from typing import Dict, Any, Optional, List, Pattern, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt5.QtCore import QThread, QTimer, pyqtSignal

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner

import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

@dataclass(frozen=True)
class VanityConfig:
    """Конфигурация параметров Vanity поиска"""
    # Тайминги
    TIMER_INTERVAL_MS: int = 1000
    READER_WAIT_TIMEOUT_MS: int = 2000
    PROCESS_WAIT_TIMEOUT_SEC: int = 3

    # 🛠 РАСШИРЕННЫЕ паттерны для парсинга вывода VanitySearch
    SPEED_PATTERNS: List[str] = field(default_factory=lambda: [
        r"\[(\d+\.?\d*)\s*Mkey/s\]",
        r"\[GPU\s+(\d+\.?\d*)\s*Mkey/s\]",
        r"(\d+\.?\d*)\s*MK/s",
        r"Speed:\s*(\d+\.?\d*)\s*MKey/s",
        r"(\d+\.?\d*)\s*MKeys/s",  # 1234.56 MKeys/s
        r"(\d+\.?\d*)\s*GKeys/s",  # 1.23 GKeys/s
        r"(\d+\.?\d*)\s*KKeys/s",  # 123456 KKeys/s
        r"GPU\s+\d+:\s*(\d+\.?\d*)\s*MKeys/s",  # GPU 0: 1234.56 MKeys/s
        r"Speed:\s*(\d+\.?\d*)",  # Speed: 1234.56 (без единиц)
        r"(\d{4,})\s*keys/sec",  # 1234567 keys/sec
        r"(\d+\.?\d*)[,\s]*M\s*keys",  # 1,234.56 M keys
    ])

    FOUND_PATTERNS: List[str] = field(default_factory=lambda: [
        r"\[Found\s+(\d+)\]",
        r"\((\d+)\s+found\)",
        r"(\d+)\s+addresses?\s+found"
    ])

    # Пороги для форматирования скорости
    SPEED_GIGA_THRESHOLD: int = 1_000_000_000
    SPEED_MEGA_THRESHOLD: int = 1_000_000
    SPEED_KILO_THRESHOLD: int = 1_000

    # Максимальное количество строк для поиска ключа
    MAX_KEY_SEARCH_LINES: int = 5

    # Порог длины для определения ключа
    MIN_KEY_LENGTH: int = 50


VANITY_CONFIG: VanityConfig = VanityConfig()

# 🛠 Компилированные регулярные выражения для производительности
SPEED_REGEXES: List[Pattern] = [re.compile(p, re.IGNORECASE) for p in VANITY_CONFIG.SPEED_PATTERNS]
FOUND_REGEXES: List[Pattern] = [re.compile(p, re.IGNORECASE) for p in VANITY_CONFIG.FOUND_PATTERNS]

# 🛠 Константы для статусов и стилей
STATUS_RUNNING: str = "Генерация..."
STATUS_STOPPED: str = "Готов"
BTN_STYLE_RUNNING: str = "background: #e74c3c; font-weight: bold;"
BTN_STYLE_STOPPED: str = "background: #27ae60; font-weight: bold;"


class VanityOutputReader(QThread):
    """
    Поток для чтения и парсинга вывода VanitySearch.
    """

    log_message = pyqtSignal(str, str)
    stats_update = pyqtSignal(dict)
    key_found = pyqtSignal(dict)
    process_finished = pyqtSignal()

    process: subprocess.Popen
    main_window: 'BitcoinGPUCPUScanner'
    prefix: str
    _running: bool
    found_count: int

    def __init__(self, process: subprocess.Popen, main_window: 'BitcoinGPUCPUScanner', prefix: str):
        super().__init__()
        self.process = process
        self.main_window = main_window
        self.prefix = prefix
        self._running = True
        self.found_count = 0

    def stop(self) -> None:
        """Остановка чтения вывода."""
        self._running = False

    def run(self) -> None:
        """Основной цикл чтения и парсинга вывода процесса."""
        try:
            while self._running and self.process.poll() is None:
                # 🛠 Читаем из stdout и stderr
                line = self._read_any_output()
                if not line:
                    time.sleep(VANITY_CONFIG.TIMER_INTERVAL_MS / 1000)
                    continue

                line = line.strip()
                if not line:
                    continue

                # ОТЛАДКА: выводим ВСЕ строки для диагностики
                self.log_message.emit(f"[VANITY] {line}", "debug")

                self._handle_address_line(line)
                self._handle_private_key_line(line)
                self._handle_speed_line(line)
                self._handle_found_count_line(line)

                # 🛠 ОТЛАДКА: если строка не распознана ни одним паттерном
                line_lower = line.lower()
                if not any(keyword in line_lower for keyword in
                           ['pubaddress', 'priv', 'found', 'speed', 'mkey', 'gkey', 'kkey', 'keys/sec', 'keys/s']):
                    logger.debug(f"🔍 Нераспознанная строка VanitySearch: {line[:200]}")

        except Exception as e:
            logger.exception("Ошибка в VanityOutputReader")
            self.log_message.emit(f"❌ Ошибка чтения вывода: {type(e).__name__}: {e}", "error")
        finally:
            self.process_finished.emit()

    def _read_any_output(self) -> Optional[str]:
        """
        Читает строку из stdout или stderr процесса.
        🛠 НОВАЯ ФУНКЦИЯ: обрабатывает вывод из обоих потоков
        """
        # Сначала пробуем stdout
        if self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if line:
                    return line
            except (ValueError, OSError):
                pass

        # Если stdout пуст, пробуем stderr (некоторые версии VanitySearch пишут туда)
        if self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if line:
                    return line
            except (ValueError, OSError):
                pass

        return None

    def _handle_address_line(self, line: str) -> None:
        """Обработка строк с найденным адресом."""
        if line.startswith("PubAddress:") or "Pub Addr:" in line:
            self.log_message.emit(f"✅ Обнаружен адрес: {line}", "success")

    def _handle_private_key_line(self, line: str) -> None:
        """Обработка строк с найденным приватным ключом."""
        if line.startswith("Priv (HEX):") or "PrivKey:" in line:
            self.log_message.emit(f"🔑 Обнаружен ключ: {line}", "success")

    def _handle_speed_line(self, line: str) -> None:
        """
        Парсинг и эмиссия скорости из строки вывода с определением единиц.
        """
        line_lower = line.lower()

        for pattern in SPEED_REGEXES:
            speed_match = pattern.search(line)
            if speed_match:
                try:
                    speed_value = float(speed_match.group(1))

                    # 🛠 ОПРЕДЕЛЕНИЕ ЕДИНИЦ ИЗМЕРЕНИЯ
                    if 'gkey' in line_lower or 'gkeys' in line_lower:
                        keys_per_sec = int(speed_value * 1_000_000_000)
                    elif 'mkey' in line_lower or 'mkeys' in line_lower or 'mk/s' in line_lower:
                        keys_per_sec = int(speed_value * 1_000_000)
                    elif 'kkey' in line_lower or 'kkeys' in line_lower:
                        keys_per_sec = int(speed_value * 1_000)
                    elif 'keys/sec' in line_lower or 'keys/s' in line_lower:
                        keys_per_sec = int(speed_value)
                    else:
                        # 🛠 ПО УМОЛЧАНИЮ: предполагаем MKeys/s (как в оригинале)
                        keys_per_sec = int(speed_value * 1_000_000)

                    # 🛠 ЛОГИРОВАНИЕ для отладки
                    logger.debug(
                        f"🔍 Распознана скорость: {speed_value} → {keys_per_sec:,} keys/sec из строки: {line[:100]}")

                    self.stats_update.emit({'speed': keys_per_sec})
                    return  # 🛠 Используем return вместо break для выхода из метода

                except (ValueError, IndexError) as e:
                    logger.debug(f"Ошибка парсинга скорости '{line[:50]}': {e}")
                    continue

        # 🛠 РЕЗЕРВНЫЙ ПАРСЕР: если ни один паттерн не сработал
        if 'key' in line_lower or 'speed' in line_lower:
            fallback_match = re.search(r'(\d+\.?\d*)', line)
            if fallback_match:
                try:
                    speed_value = float(fallback_match.group(1))
                    # Предполагаем MKeys/s как наиболее частый формат
                    keys_per_sec = int(speed_value * 1_000_000)
                    logger.debug(f"🔧 Резервный парсер: {speed_value} → {keys_per_sec:,} keys/sec")
                    self.stats_update.emit({'speed': keys_per_sec})
                except (ValueError, IndexError):
                    pass

    def _handle_found_count_line(self, line: str) -> None:
        """Парсинг и эмиссия количества найденных ключей."""
        for pattern in FOUND_REGEXES:
            found_match = pattern.search(line)
            if found_match:
                try:
                    new_count = int(found_match.group(1))
                    if new_count > self.found_count:
                        self.found_count = new_count
                        self.stats_update.emit({'found_count': self.found_count})
                    return  # 🛠 Используем return вместо break
                except (ValueError, IndexError) as e:
                    logger.debug(f"Ошибка парсинга found_count: {e}")
                    continue


class VanityLogic:
    """
    Логика управления VanitySearch генерацией адресов.
    """

    main_window: 'BitcoinGPUCPUScanner'
    process: Optional[subprocess.Popen]
    reader: Optional[VanityOutputReader]
    is_running: bool
    start_time: Optional[float]
    keys_found: int
    prefix: str
    output_file: str
    last_file_size: int
    last_file_lines: int
    timer: QTimer

    def __init__(self, main_window: 'BitcoinGPUCPUScanner'):
        self.main_window = main_window
        self.process = None
        self.reader = None
        self.is_running = False
        self.start_time = None
        self.keys_found = 0
        self.prefix = ""
        self.output_file = ""
        self.last_file_size = 0
        self.last_file_lines = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer_tick)
        self.timer.setInterval(VANITY_CONFIG.TIMER_INTERVAL_MS)

    def toggle_search(self) -> None:
        """Переключение запуск/остановка поиска."""
        if self.is_running:
            self.stop_search()
        else:
            self.start_search()

    def start_search(self) -> None:
        """Запуск VanitySearch с полной валидацией параметров."""
        prefix = self.main_window.vanity_prefix_edit.text().strip()
        if not prefix:
            self.main_window.append_log("❌ Укажите префикс адреса", "error")
            return

        exe_path = os.path.join(config.BASE_DIR, "VanitySearch.exe")
        if not self._validate_executable(exe_path):
            return

        cmd = self._build_vanity_command(prefix, exe_path)
        self._prepare_file_tracking(prefix)
        self._cleanup_old_output_file()
        self._start_vanity_process(cmd)

    def _validate_executable(self, exe_path: str) -> bool:
        """Проверка существования исполняемого файла."""
        if not os.path.exists(exe_path):
            self.main_window.append_log("❌ VanitySearch.exe не найден в корне проекта", "error")
            return False
        return True

    def _build_vanity_command(self, prefix: str, exe_path: str) -> List[str]:
        """Сборка команды для запуска VanitySearch."""
        cmd = [exe_path]

        gpu_text = self.main_window.vanity_gpu_combo.currentText().strip()
        use_cpu = (gpu_text == "CPU")
        if use_cpu:
            threads = self.main_window.vanity_cpu_spin.value()
            cmd.extend(["-t", str(threads)])
        else:
            cmd.append("-gpu")
            device_ids = gpu_text.replace(',', ' ').split()
            cmd.extend(["-gpuId"] + device_ids)

        addr_type = self.main_window.vanity_type_combo.currentIndex()
        if addr_type == 1:
            cmd.append("-p2sh")
        elif addr_type == 2:
            cmd.append("-bech32")
        elif addr_type == 3:
            cmd.append("-bech32m")

        if not self.main_window.vanity_compressed_cb.isChecked():
            cmd.append("-u")

        output_file = os.path.join(config.BASE_DIR, f"VANITY_{prefix}.txt")
        cmd.extend(["-o", output_file])
        cmd.append(prefix)

        return cmd

    def _prepare_file_tracking(self, prefix: str) -> None:
        """Подготовка состояния для отслеживания файла результатов."""
        self.prefix = prefix
        self.output_file = os.path.join(config.BASE_DIR, f"VANITY_{prefix}.txt")
        self.last_file_size = 0
        self.last_file_lines = 0

    def _cleanup_old_output_file(self) -> None:
        """Удаление старого файла результатов, если существует."""
        if os.path.exists(self.output_file):
            try:
                os.remove(self.output_file)
                self.main_window.append_log(f"🗑️ Удален старый файл результатов", "normal")
            except OSError as e:
                logger.warning(f"Не удалось удалить старый файл: {e}")

    def _start_vanity_process(self, cmd: List[str]) -> None:
        """Запуск процесса VanitySearch."""
        try:
            self.main_window.append_log(f"🚀 Запуск VanitySearch: {' '.join(cmd)}", "info")

            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            creationflags = 0
            if platform.system() == "Windows":
                try:
                    creationflags = subprocess.CREATE_NO_WINDOW
                except AttributeError:
                    pass

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # 🛠 Открываем stderr для чтения
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=config.BASE_DIR,
                startupinfo=startupinfo,
                creationflags=creationflags
            )

            self.reader = VanityOutputReader(self.process, self.main_window, self.prefix)
            self._connect_reader_signals()
            self.reader.start()

            self._on_search_started()

            self.main_window.append_log(f"✅ VanitySearch запущен (PID: {self.process.pid})", "success")
            self.main_window.append_log(f"📁 Результаты будут сохранены в: {self.output_file}", "info")

        except Exception as e:
            self.main_window.append_log(f"❌ Ошибка запуска VanitySearch: {type(e).__name__}: {e}", "error")
            logger.exception("VanitySearch start failed")
            self.is_running = False

    def _connect_reader_signals(self) -> None:
        """Подключение сигналов читателя к обработчикам."""
        self.reader.log_message.connect(self.main_window.append_log)
        self.reader.stats_update.connect(self.handle_stats)
        self.reader.process_finished.connect(self.search_finished)

    def _on_search_started(self) -> None:
        """Обновление состояния и UI после успешного запуска."""
        self.is_running = True
        self.start_time = time.time()
        self.keys_found = 0
        self.main_window.vanity_start_stop_btn.setText("⏹ Остановить")
        self.main_window.vanity_status_label.setText(f"Статус: {STATUS_RUNNING}")
        self.main_window.vanity_progress_bar.setRange(0, 0)
        self.timer.start()

    def handle_stats(self, stats: Dict[str, Any]) -> None:
        """Обработка обновления статистики от читателя."""
        if 'speed' in stats:
            self._update_speed_display(stats['speed'])

        if 'found_count' in stats:
            self._update_found_count_display(stats['found_count'])

    def _update_speed_display(self, speed: int) -> None:
        """Форматирование и отображение скорости сканирования."""
        if speed >= VANITY_CONFIG.SPEED_GIGA_THRESHOLD:
            speed_str = f"{speed / VANITY_CONFIG.SPEED_GIGA_THRESHOLD:.2f} GKeys/s"
        elif speed >= VANITY_CONFIG.SPEED_MEGA_THRESHOLD:
            speed_str = f"{speed / VANITY_CONFIG.SPEED_MEGA_THRESHOLD:.2f} MKeys/s"
        elif speed >= VANITY_CONFIG.SPEED_KILO_THRESHOLD:
            speed_str = f"{speed / VANITY_CONFIG.SPEED_KILO_THRESHOLD:.2f} KKeys/s"
        else:
            speed_str = f"{speed} Keys/s"
        self.main_window.vanity_speed_label.setText(f"Скорость: {speed_str}")

    def _update_found_count_display(self, new_count: int) -> None:
        """Обновление отображения количества найденных ключей."""
        if new_count > self.keys_found:
            self.keys_found = new_count
            self.main_window.vanity_found_label.setText(f"Найдено: {self.keys_found}")
            self.main_window.append_log(f"🎉 Найден ключ #{self.keys_found}!", "success")

    def on_timer_tick(self) -> None:
        """Обработчик таймера: обновление времени и проверка файла."""
        self.update_time_label()
        if self.is_running:
            self.check_output_file()

    def update_time_label(self) -> None:
        """Обновление отображения времени работы поиска."""
        if self.start_time is None:
            return
        elapsed = time.time() - self.start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self.main_window.vanity_time_label.setText(f"Время: {h:02d}:{m:02d}:{s:02d}")

    def check_output_file(self) -> None:
        """Проверка файла результатов на наличие новых найденных адресов."""
        try:
            if not os.path.exists(self.output_file):
                return

            current_size = os.path.getsize(self.output_file)
            if current_size <= self.last_file_size:
                return

            with open(self.output_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            new_lines = lines[self.last_file_lines:]
            self.last_file_lines = len(lines)
            self.last_file_size = current_size

            if not new_lines:
                return

            self._process_new_lines(new_lines)

        except FileNotFoundError:
            logger.debug(f"Файл результатов не найден: {self.output_file}")
        except Exception as e:
            logger.exception("Ошибка при чтении файла результатов")
            self.main_window.append_log(f"❌ Ошибка чтения {self.output_file}: {type(e).__name__}: {e}", "error")

    def _process_new_lines(self, new_lines: List[str]) -> None:
        """Обработка новых строк из файла результатов."""
        i = 0
        while i < len(new_lines):
            line = new_lines[i].strip()

            if not line or line.startswith('#') or line.startswith('='):
                i += 1
                continue

            addr, priv_hex, priv_wif = None, None, None

            if self._is_address_line(line):
                addr = self._extract_address(line)
                if addr:
                    priv_hex, priv_wif, i = self._search_for_keys(new_lines, i)
                    if addr and (priv_hex or priv_wif):
                        self.process_found_key(addr, priv_hex, priv_wif)
                        continue

            self._handle_single_line_format(line)
            i += 1

    def _is_address_line(self, line: str) -> bool:
        """Проверка, является ли строка содержащей адрес."""
        return ('PubAddress:' in line or 'Addr:' in line or
                line.startswith('1') or line.startswith('3') or line.startswith('bc1'))

    def _extract_address(self, line: str) -> Optional[str]:
        """Извлечение адреса из строки."""
        if ':' in line:
            return line.split(':', 1)[1].strip()
        else:
            parts = line.split()
            for part in parts:
                if part.startswith('1') or part.startswith('3') or part.startswith('bc1'):
                    return part
        return None

    def _search_for_keys(self, lines: List[str], start_idx: int) -> Tuple[Optional[str], Optional[str], int]:
        """Поиск приватных ключей в следующих строках после адреса."""
        priv_hex, priv_wif = None, None
        j = start_idx + 1

        while j < len(lines) and j < start_idx + VANITY_CONFIG.MAX_KEY_SEARCH_LINES:
            next_line = lines[j].strip()

            if ('Priv' in next_line and 'HEX' in next_line) or 'PrivKey' in next_line:
                if ':' in next_line:
                    priv_hex = next_line.split(':', 1)[1].strip()

            if ('Priv' in next_line and 'WIF' in next_line) or (
                    next_line.startswith('5') or next_line.startswith('K') or next_line.startswith('L')):
                if ':' in next_line:
                    priv_wif = next_line.split(':', 1)[1].strip()
                else:
                    parts = next_line.split()
                    for part in parts:
                        if part.startswith('5') or part.startswith('K') or part.startswith('L'):
                            priv_wif = part
                            break

            if not priv_hex and len(next_line) > VANITY_CONFIG.MIN_KEY_LENGTH and ':' not in next_line:
                if all(c in '0123456789abcdefABCDEF ' for c in next_line):
                    priv_hex = next_line.strip()

            j += 1

        return priv_hex, priv_wif, j

    def _handle_single_line_format(self, line: str) -> None:
        """Обработка формата "одна строка: адрес ключ"."""
        parts = line.split()
        if len(parts) == 2:
            potential_addr = parts[0]
            potential_key = parts[1]

            if (potential_addr.startswith('1') or potential_addr.startswith('3') or
                    potential_addr.startswith('bc1')):
                if len(potential_key) > VANITY_CONFIG.MIN_KEY_LENGTH:
                    if all(c in '0123456789abcdefABCDEF' for c in potential_key):
                        self.process_found_key(potential_addr, potential_key, None)
                    else:
                        self.process_found_key(potential_addr, None, potential_key)

    def process_found_key(self, addr: str, priv_hex: Optional[str], priv_wif: Optional[str]) -> None:
        """Обработка найденного ключа с конвертацией форматов."""
        try:
            if priv_hex and not priv_wif:
                priv_wif = self._convert_hex_to_wif(priv_hex)

            if priv_wif and not priv_hex:
                priv_hex = self._convert_wif_to_hex(priv_wif)

            data = self._build_found_key_data(addr, priv_hex, priv_wif)

            self.main_window.vanity_result_addr.setText(addr)
            self.main_window.vanity_result_hex.setText(priv_hex or "N/A")
            self.main_window.vanity_result_wif.setText(priv_wif or "N/A")

            self.main_window.handle_found_key(data)

            self.keys_found += 1
            self.main_window.vanity_found_label.setText(f"Найдено: {self.keys_found}")

            self.main_window.append_log(f"✅ Ключ #{self.keys_found} обработан: {addr[:20]}...", "success")

        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.main_window.append_log(f"❌ Ошибка обработки ключа: {type(e).__name__}: {str(e)}", "error")

    def _convert_hex_to_wif(self, priv_hex: str) -> Optional[str]:
        """Конвертация HEX ключа в WIF формат."""
        try:
            from core.hextowif import hex_to_wif
            priv_hex_clean = priv_hex.replace(' ', '').lstrip('0x')
            if len(priv_hex_clean) % 2:
                priv_hex_clean = '0' + priv_hex_clean

            compressed = self.main_window.vanity_compressed_cb.isChecked()
            return hex_to_wif(priv_hex_clean, compressed=compressed, is_testnet=False)
        except ImportError as e:
            logger.error(f"Не удалось импортировать hex_to_wif: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка конвертации HEX→WIF: {e}")
            return None

    def _convert_wif_to_hex(self, priv_wif: str) -> Optional[str]:
        """Конвертация WIF ключа в HEX формат."""
        try:
            from core.hextowif import wif_to_hex
            return wif_to_hex(priv_wif)
        except ImportError as e:
            logger.error(f"Не удалось импортировать wif_to_hex: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка конвертации WIF→HEX: {e}")
            return None

    def _build_found_key_data(self, addr: str, priv_hex: Optional[str], priv_wif: Optional[str]) -> Dict[str, Any]:
        """Создание словаря данных найденного ключа."""
        return {
            'address': addr,
            'hex_key': priv_hex or "N/A",
            'wif_key': priv_wif or "N/A",
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'VANITY'
        }

    def stop_search(self) -> None:
        """Остановка VanitySearch с корректным завершением процессов."""
        if not self.is_running:
            return

        self.main_window.append_log("⏹ Остановка VanitySearch...", "warning")

        try:
            self._stop_process_safely()

            if self.reader:
                self.reader.stop()
                if not self.reader.wait(VANITY_CONFIG.READER_WAIT_TIMEOUT_MS):
                    logger.warning("VanityOutputReader не завершился вовремя")

            self.check_output_file()

        except Exception as e:
            logger.warning(f"Ошибка остановки VanitySearch: {e}")
            self.main_window.append_log(f"⚠️ Ошибка остановки: {type(e).__name__}: {str(e)}", "warning")
        finally:
            self.search_finished()

    def _stop_process_safely(self) -> None:
        """Безопасная остановка процесса VanitySearch."""
        if self.process and self.process.poll() is None:
            try:
                if platform.system() == "Windows":
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=VANITY_CONFIG.PROCESS_WAIT_TIMEOUT_SEC)
                    except subprocess.TimeoutExpired:
                        self.main_window.append_log("⚠️ Принудительное завершение процесса", "warning")
                        self.process.kill()
                        self.process.wait(timeout=2)
                else:
                    self.process.terminate()
                    self.process.wait(timeout=VANITY_CONFIG.PROCESS_WAIT_TIMEOUT_SEC)
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"Процесс уже завершён: {e}")
            except Exception as e:
                logger.warning(f"Неожиданная ошибка при остановке процесса: {e}")

    def search_finished(self) -> None:
        """Сброс состояния после завершения поиска."""
        self.is_running = False
        self.timer.stop()
        self.process = None
        self.reader = None

        self.main_window.vanity_start_stop_btn.setText("🚀 Запустить генерацию")
        self.main_window.vanity_status_label.setText(f"Статус: {STATUS_STOPPED}")
        self.main_window.vanity_progress_bar.setRange(0, 100)
        self.main_window.vanity_progress_bar.setValue(0)
        self.main_window.vanity_progress_bar.setFormat("Готов")

        self.main_window.append_log(
            f"✅ VanitySearch завершен. Найдено ключей: {self.keys_found}", "success"
        )


__all__ = [
    'VanityConfig',
    'VANITY_CONFIG',
    'STATUS_RUNNING',
    'STATUS_STOPPED',
    'BTN_STYLE_RUNNING',
    'BTN_STYLE_STOPPED',
    'VanityOutputReader',
    'VanityLogic',
]