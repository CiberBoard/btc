# core/kangaroo_worker.py
from __future__ import annotations

import os
import time
import random
import subprocess
import json
import re
import select
import sys
import traceback
import logging
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt5.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 🔧 КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════
@dataclass(frozen=True)
class KangarooConfig:
    REQUIRED_PARAMS: Tuple[str, ...] = field(default_factory=lambda: (
        'rb_hex', 're_hex', 'pubkey_hex', 'etarkangaroo_exe',
        'temp_dir', 'dp', 'grid_params', 'subrange_bits', 'scan_duration'
    ))
    HEX_PARAMS: Tuple[str, ...] = field(default_factory=lambda: ('rb_hex', 're_hex', 'pubkey_hex'))
    MIN_SUBRANGE_BITS: int = 1
    MAX_SUBRANGE_BITS: int = 256
    MIN_SCAN_DURATION_SEC: int = 10
    MAX_SCAN_DURATION_SEC: int = 3600
    HEX_KEY_LENGTH: int = 64
    HEX_PREFIX: str = '0x'
    PROCESS_WAIT_TIMEOUT_SEC: int = 3
    SESSION_PAUSE_SEC: float = 0.5
    READ_TIMEOUT_SEC: float = 0.1
    STDERR_READ_LIMIT: int = 500
    FOUND_KEYS_FILENAME: str = "found_keys.txt"
    FOUND_KEYS_JSON_FILENAME: str = "found_keys.json"
    RESULT_FILE_PATTERN: str = "result_{}.txt"
    PRIV_KEY_PATTERN: re.Pattern = re.compile(r'Priv:\s*(?:0x)?([0-9a-fA-F]+)', re.IGNORECASE)
    SPEED_PATTERN: re.Pattern = re.compile(r'(\d+(?:\.\d+)?)\s*MKeys/s')
    ANSI_ESCAPE_PATTERN: re.Pattern = re.compile(r'\x1b\[[0-9;]*[KM]')
    HEX_VALID_PATTERN: re.Pattern = re.compile(r'^[0-9a-fA-F]+$')
    NON_HEX_PATTERN: re.Pattern = re.compile(r'[^0-9a-fA-F]')

KANGAROO_CONFIG: KangarooConfig = KangarooConfig()

MSG_PREFIX_FOUND: str = "✅ НАЙДЕН КЛЮЧ"
MSG_PREFIX_ERROR: str = "❌ Ошибка"
MSG_PREFIX_WARNING: str = "⚠️"
MSG_PREFIX_INFO: str = "ℹ️"


class KangarooWorker(QObject):
    log_message = pyqtSignal(str)
    status_update = pyqtSignal(float, int, int)
    range_update = pyqtSignal(str, str)
    found_key = pyqtSignal(str)
    finished = pyqtSignal(bool)

    params: Dict[str, Any]
    _stop_requested: bool
    _last_logged_line: str

    def __init__(self, params: Dict[str, Any]):
        super().__init__()
        self.params = params
        self._stop_requested = False
        self._last_logged_line = ""
        self._validate_params()

    def _validate_params(self) -> None:
        for key in KANGAROO_CONFIG.REQUIRED_PARAMS:
            if key not in self.params:
                raise ValueError(f"Отсутствует обязательный параметр: {key}")

        for hex_key in KANGAROO_CONFIG.HEX_PARAMS:
            try:
                int(self.params[hex_key].replace(KANGAROO_CONFIG.HEX_PREFIX, ''), 16)
            except ValueError as e:
                raise ValueError(f"Некорректное hex-значение в {hex_key}: {self.params[hex_key]}") from e

        if not os.path.isfile(self.params['etarkangaroo_exe']):
            raise FileNotFoundError(f"Не найден файл: {self.params['etarkangaroo_exe']}")

        if not isinstance(self.params['dp'], (int, str)):
            raise ValueError(f"dp должен быть числом, получено: {type(self.params['dp'])}")

        subrange_bits = int(self.params['subrange_bits'])
        if not (KANGAROO_CONFIG.MIN_SUBRANGE_BITS <= subrange_bits <= KANGAROO_CONFIG.MAX_SUBRANGE_BITS):
            raise ValueError(
                f"subrange_bits должен быть в диапазоне "
                f"{KANGAROO_CONFIG.MIN_SUBRANGE_BITS}-{KANGAROO_CONFIG.MAX_SUBRANGE_BITS}, "
                f"получено: {subrange_bits}"
            )

    def stop(self) -> None:
        self._stop_requested = True

    def hex_to_int(self, hex_str: str) -> int:
        return int(hex_str.lower().replace(KANGAROO_CONFIG.HEX_PREFIX, ""), 16)

    def int_to_hex(self, value: int) -> str:
        return f"{value:0{KANGAROO_CONFIG.HEX_KEY_LENGTH}x}"

    def random_subrange(self, start: int, end: int, bits: int) -> Tuple[int, int]:
        if start >= end:
            raise ValueError(f"Некорректный диапазон: start={start} >= end={end}")

        width = 1 << bits
        total = end - start
        if total <= width:
            return start, end

        max_offset = total - width
        offset = self._generate_random_offset(max_offset)
        return start + offset, start + offset + width

    def _generate_random_offset(self, max_offset: int) -> int:
        try:
            return random.randbelow(max_offset + 1)
        except AttributeError:
            bits_needed = max_offset.bit_length()
            while True:
                candidate = random.getrandbits(bits_needed)
                if candidate <= max_offset:
                    return candidate

    def _parse_private_key(self, raw_result: str) -> Optional[str]:
        try:
            priv_match = KANGAROO_CONFIG.PRIV_KEY_PATTERN.search(raw_result)
            if priv_match:
                clean = priv_match.group(1).strip()
                return self._convert_to_hex_key(clean)

            if "->" in raw_result:
                parts = raw_result.split("->", 1)
                if len(parts) == 2:
                    clean = parts[1].strip().replace(KANGAROO_CONFIG.HEX_PREFIX, "").replace(
                        KANGAROO_CONFIG.HEX_PREFIX.upper(), "")
                    return self._convert_to_hex_key(clean)

            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Неожиданный формат результата: {raw_result[:200]}")
            return None
        except (ValueError, OverflowError, IndexError) as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Ошибка парсинга ключа: {e}")
            return None

    def _convert_to_hex_key(self, clean_str: str) -> Optional[str]:
        try:
            key_int = self._parse_key_string(clean_str)
            if key_int is None:
                return None

            private_hex = f"{key_int:0{KANGAROO_CONFIG.HEX_KEY_LENGTH}x}"
            if len(private_hex) != KANGAROO_CONFIG.HEX_KEY_LENGTH:
                self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Некорректная длина ключа: {len(private_hex)}")
                return None
            return private_hex
        except (ValueError, OverflowError) as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Ошибка конвертации ключа: {e}")
            return None

    def _parse_key_string(self, clean_str: str) -> Optional[int]:
        if KANGAROO_CONFIG.HEX_VALID_PATTERN.match(clean_str):
            return int(clean_str, 16)
        elif clean_str.isdigit():
            return int(clean_str, 10)
        else:
            cleaned = KANGAROO_CONFIG.NON_HEX_PATTERN.sub('', clean_str)
            if not cleaned:
                return None
            return int(cleaned, 16)

    def _cleanup_temp_file(self, filepath: str) -> None:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Не удалось удалить {filepath}: {e}")
        except Exception as e:
            logger.debug(f"Неожиданная ошибка при удалении файла {filepath}: {e}")

    def _save_found_key(self, private_key: str, start_hex: str, end_hex: str, session: int) -> None:
        try:
            found_keys_file = os.path.join(self.params['temp_dir'], KANGAROO_CONFIG.FOUND_KEYS_FILENAME)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            pubkey = self.params.get('pubkey_hex', 'N/A')
            log_entry = self._format_found_key_log(timestamp, session, private_key, pubkey, start_hex, end_hex)

            with open(found_keys_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

            self.log_message.emit(f"[💾] Ключ сохранён в {found_keys_file}")
            self._save_found_key_json(private_key, start_hex, end_hex, session, timestamp)
        except Exception as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Не удалось сохранить ключ в файл: {e}")
            print(f"ERROR saving key: {traceback.format_exc()}")

    def _format_found_key_log(self, timestamp: str, session: int, private_key: str, pubkey: str, start_hex: str, end_hex: str) -> str:
        separator = "=" * 80
        return (
            f"{separator}\n"
            f"[НАЙДЕН КЛЮЧ] {timestamp}\n"
            f"Сессия: #{session}\n"
            f"Приватный ключ (HEX): {private_key}\n"
            f"Публичный ключ: {pubkey}\n"
            f"Диапазон поиска: {start_hex} - {end_hex}\n"
            f"{separator}\n\n"
        )

    def _save_found_key_json(self, private_key: str, start_hex: str, end_hex: str, session: int, timestamp: str) -> None:
        try:
            json_file = os.path.join(self.params['temp_dir'], KANGAROO_CONFIG.FOUND_KEYS_JSON_FILENAME)
            key_data = self._build_key_data(private_key, start_hex, end_hex, session, timestamp)
            data = self._load_json_data(json_file)
            data.append(key_data)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log_message.emit(f"[💾] Ключ также сохранён в JSON: {json_file}")
        except Exception as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Не удалось сохранить JSON: {e}")

    def _build_key_data(self, private_key: str, start_hex: str, end_hex: str, session: int, timestamp: str) -> Dict[str, Any]:
        return {
            'timestamp': timestamp,
            'session': session,
            'private_key_hex': private_key,
            'public_key': self.params.get('pubkey_hex', 'N/A'),
            'range_start': start_hex,
            'range_end': end_hex,
            'dp': self.params.get('dp', 'N/A'),
            'grid_params': self.params.get('grid_params', 'N/A')
        }

    def _load_json_data(self, json_file: str) -> List[Dict[str, Any]]:
        if not os.path.exists(json_file):
            return []
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError, OSError):
            return []

    def _read_result_file(self, result_file: str) -> Optional[str]:
        if not os.path.exists(result_file) or os.path.getsize(result_file) == 0:
            return None
        try:
            with open(result_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
            if not content:
                return None
            return self._parse_private_key(content)
        except OSError as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Ошибка чтения файла результата: {e}")
            return None
        except Exception as e:
            logger.debug(f"Неожиданная ошибка при чтении файла {result_file}: {e}")
            return None

    def _terminate_process(self, proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            self.log_message.emit("[⏸️] Остановка процесса Kangaroo...")
            proc.terminate()
            try:
                proc.wait(timeout=KANGAROO_CONFIG.PROCESS_WAIT_TIMEOUT_SEC)
                self.log_message.emit("[✓] Процесс остановлен корректно")
            except subprocess.TimeoutExpired:
                self.log_message.emit("[⚠️] Процесс не ответил, выполняется kill...")
                proc.kill()
                proc.wait()
                self.log_message.emit("[✓] Процесс принудительно завершён")
            except (ProcessLookupError, OSError) as e:
                logger.debug(f"Процесс уже завершён: {e}")
            except Exception as e:
                logger.warning(f"Неожиданная ошибка при завершении процесса: {e}")

    def _run_kangaroo_session(self, session: int, sub_start_hex: str, sub_end_hex: str) -> Optional[str]:
        result_file = os.path.join(self.params['temp_dir'], KANGAROO_CONFIG.RESULT_FILE_PATTERN.format(session))
        self._cleanup_temp_file(result_file)
        cmd = self._build_kangaroo_command(sub_start_hex, sub_end_hex, result_file)

        self.log_message.emit(f"[🚀] Сессия #{session}: Запуск Kangaroo")
        self.log_message.emit(f"[📦] Команда: {' '.join(cmd)}")

        try:
            # ✅ ИСПРАВЛЕНИЕ: Передаём диапазоны в _execute_kangaroo_command
            return self._execute_kangaroo_command(cmd, result_file, session, sub_start_hex, sub_end_hex)
        except Exception as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Ошибка запуска Kangaroo: {e}")
            self.log_message.emit(f"[🪵] Traceback:\n{traceback.format_exc()}")
            return None

    def _build_kangaroo_command(self, sub_start_hex: str, sub_end_hex: str, result_file: str) -> List[str]:
        return [
            self.params['etarkangaroo_exe'],
            "-dp", str(self.params['dp']),
            "-grid", self.params['grid_params'],
            "-rb", sub_start_hex,
            "-re", sub_end_hex,
            "-pub", self.params['pubkey_hex'],
            "-o", result_file
        ]

    def _execute_kangaroo_command(
            self,
            cmd: List[str],
            result_file: str,
            session: int,
            sub_start_hex: str,  # ✅ ДОБАВЛЕНО: параметр диапазона
            sub_end_hex: str      # ✅ ДОБАВЛЕНО: параметр диапазона
    ) -> Optional[str]:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, universal_newlines=True, cwd=self.params['temp_dir']
        )

        start_time = time.time()
        last_speed = 0.0
        self._last_logged_line = ""
        is_windows = sys.platform.startswith('win')

        while proc.poll() is None and not self._stop_requested:
            if time.time() - start_time > self.params['scan_duration']:
                self.log_message.emit(f"[⏰] Таймаут сессии ({self.params['scan_duration']}s)")
                break

            if not self._read_process_output(proc, is_windows, start_time, session, last_speed):
                break

        self._terminate_process(proc)
        self._check_stderr(proc)

        private_key = self._read_result_file(result_file)
        if private_key:
            self._save_found_key(private_key, sub_start_hex, sub_end_hex, session)

        self._cleanup_temp_file(result_file)
        return private_key

    def _read_process_output(self, proc: subprocess.Popen, is_windows: bool, start_time: float, session: int, last_speed: float) -> bool:
        if not is_windows:
            try:
                readable, _, _ = select.select([proc.stdout], [], [], KANGAROO_CONFIG.READ_TIMEOUT_SEC)
                if not readable:
                    return True
            except (OSError, ValueError):
                pass

        try:
            output = proc.stdout.readline()
            if not output:
                if is_windows:
                    time.sleep(KANGAROO_CONFIG.READ_TIMEOUT_SEC)
                return True

            line = self._clean_output_line(output)
            if not line or line == self._last_logged_line:
                return True

            self._last_logged_line = line
            self.log_message.emit(f"    {line}")

            speed_match = KANGAROO_CONFIG.SPEED_PATTERN.search(line)
            if speed_match:
                try:
                    speed_val = float(speed_match.group(1))
                    last_speed = speed_val
                    elapsed = int(time.time() - start_time)
                    self.status_update.emit(last_speed, elapsed, session)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Ошибка парсинга скорости: {e}")
            return True
        except Exception as e:
            self.log_message.emit(f"[{MSG_PREFIX_WARNING}] Ошибка чтения вывода: {e}")
            return False

    def _clean_output_line(self, output: str) -> str:
        line = output.strip()
        return KANGAROO_CONFIG.ANSI_ESCAPE_PATTERN.sub('', line).strip()

    def _check_stderr(self, proc: subprocess.Popen) -> None:
        try:
            stderr_output = proc.stderr.read()
            if stderr_output:
                self.log_message.emit(f"[{MSG_PREFIX_WARNING}] STDERR: {stderr_output[:KANGAROO_CONFIG.STDERR_READ_LIMIT]}")
        except (OSError, ValueError, AttributeError) as e:
            logger.debug(f"Не удалось прочитать stderr: {e}")
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при чтении stderr: {e}")

    def run(self) -> None:
        try:
            start_int = self.hex_to_int(self.params['rb_hex'])
            end_int = self.hex_to_int(self.params['re_hex'])

            if start_int > end_int:
                start_int, end_int = end_int, start_int
                self.log_message.emit("[⚠️] Диапазон был инвертирован (rb > re)")

            if start_int == end_int:
                self.log_message.emit(f"[{MSG_PREFIX_ERROR}] Ошибка: rb == re (нулевой диапазон)")
                self.finished.emit(False)
                return

            os.makedirs(self.params['temp_dir'], exist_ok=True)
            self.log_message.emit(f"[📁] Временная директория: {self.params['temp_dir']}")

            range_bits = (end_int - start_int).bit_length()
            self.log_message.emit(f"[📊] Полный диапазон: {range_bits} бит")
            self.log_message.emit(f"[📊] Размер подзадачи: {self.params['subrange_bits']} бит")
            self.log_message.emit(f"[⏱️] Таймаут сессии: {self.params['scan_duration']}s")

            session = 1
            while not self._stop_requested:
                sub_start_hex, sub_end_hex = self._generate_subrange(start_int, end_int)

                self.range_update.emit(sub_start_hex, sub_end_hex)
                self.log_message.emit(
                    f"[🎲] Подзадача: {sub_start_hex[:16]}...{sub_start_hex[-8:]} -> {sub_end_hex[-8:]}"
                )

                private_key = self._run_kangaroo_session(session, sub_start_hex, sub_end_hex)

                if private_key:
                    self.found_key.emit(private_key)
                    self.log_message.emit(f"[{MSG_PREFIX_FOUND}]: {private_key}")
                    self.finished.emit(True)
                    return

                if self._stop_requested:
                    break

                session += 1
                time.sleep(KANGAROO_CONFIG.SESSION_PAUSE_SEC)

            self.log_message.emit("[⏹️] Работа завершена (остановлено пользователем)")
            self.finished.emit(False)
        except Exception as e:
            self.log_message.emit(f"[🔥] Критическая ошибка в KangarooWorker: {e}")
            self.log_message.emit(f"[🪵] Traceback:\n{traceback.format_exc()}")
            self.finished.emit(False)

    def _generate_subrange(self, start_int: int, end_int: int) -> Tuple[str, str]:
        sub_start, sub_end = self.random_subrange(start_int, end_int, self.params['subrange_bits'])
        return self.int_to_hex(sub_start), self.int_to_hex(sub_end)


__all__ = [
    'KangarooConfig', 'KANGAROO_CONFIG',
    'MSG_PREFIX_FOUND', 'MSG_PREFIX_ERROR', 'MSG_PREFIX_WARNING', 'MSG_PREFIX_INFO',
    'KangarooWorker',
]