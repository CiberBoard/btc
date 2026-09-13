# core/unified_scanner.py
"""
Единый модуль для всех сканеров.
Устраняет дублирование логики управления процессами и очередями.
Включает собственный VanityOutputReader (без внешних зависимостей).
"""

from __future__ import annotations

import os
import time
import logging
import platform
import multiprocessing
import subprocess
import random
import re
import sys
from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Any, Optional, Callable, Tuple, List, Set
from queue import Empty
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QMessageBox

import config
import core.cpu_scanner as cpu_worker
import core.gpu_scanner as gpu_worker
from core.kangaroo_worker import KangarooWorker
from core.matrix_logic import MatrixLogic as OldMatrixLogic
import core.matrix_logic as matrix_worker
from utils.helpers import validate_key_range, is_coincurve_available, safe_queue_put, private_key_to_wif

logger = logging.getLogger(__name__)


# ============================================================
#  VANITY OUTPUT READER (с fallback-чтением файла)
# ============================================================
class VanityOutputReader(QThread):
    """
    Поток для чтения и парсинга вывода VanitySearch.
    Извлекает адрес и приватный ключ из stdout/stderr.
    В случае неудачи — читает выходной файл (fallback).
    """
    log_message = pyqtSignal(str, str)
    stats_update = pyqtSignal(dict)
    key_found = pyqtSignal(dict)
    process_finished = pyqtSignal()

    def __init__(self, process: subprocess.Popen, main_window, prefix: str, output_file: str = ""):
        super().__init__()
        self.process = process
        self.main_window = main_window
        self.prefix = prefix
        self.output_file = output_file          # для fallback
        self._running = True
        self.found_count = 0
        self._current_address = None
        self._current_private_key = None

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            # --- Чтение stdout/stderr в реальном времени ---
            while self._running and self.process.poll() is None:
                line = self._read_any_output()
                if not line:
                    time.sleep(0.1)
                    continue

                line = line.strip()
                if not line:
                    continue

                self.log_message.emit(f"[VANITY] {line}", "debug")

                self._handle_address_line(line)
                self._handle_private_key_line(line)
                self._handle_speed_line(line)
                self._handle_found_count_line(line)

            # --- Если процесс завершился, но ключи не найдены — пробуем прочитать файл ---
            if self.output_file and os.path.exists(self.output_file):
                self._read_output_file()

        except Exception as e:
            logger.exception("Ошибка в VanityOutputReader")
            self.log_message.emit(f"❌ Ошибка чтения вывода: {type(e).__name__}: {e}", "error")
        finally:
            self.process_finished.emit()

    def _read_any_output(self) -> Optional[str]:
        if self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if line:
                    return line
            except (ValueError, OSError):
                pass
        if self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if line:
                    return line
            except (ValueError, OSError):
                pass
        return None

    def _handle_address_line(self, line: str) -> None:
        """Извлекает адрес (регистронезависимо)."""
        line_lower = line.lower()
        if line_lower.startswith("pubaddress:") or "pub addr:" in line_lower:
            if ":" in line:
                addr = line.split(":", 1)[1].strip()
            else:
                addr = line.split(" ", 1)[1].strip()
            if addr and addr[0] in '13bc':
                self._current_address = addr
                self.log_message.emit(f"✅ Обнаружен адрес: {addr}", "success")
                self._check_complete()

    def _handle_private_key_line(self, line: str) -> None:
        """Извлекает HEX-ключ (регистронезависимо)."""
        line_lower = line.lower()
        if "priv (hex):" in line_lower or "privkey:" in line_lower:
            if ":" in line:
                hex_key = line.split(":", 1)[1].strip()
            else:
                hex_key = line.split(" ", 1)[1].strip()
            if hex_key.startswith("0x"):
                hex_key = hex_key[2:]
            if len(hex_key) == 64 and all(c in '0123456789abcdefABCDEF' for c in hex_key):
                self._current_private_key = hex_key
                self.log_message.emit(f"🔑 Обнаружен ключ: {hex_key}", "success")
                self._check_complete()

    def _check_complete(self):
        """Если есть и адрес, и ключ — эмитим сигнал."""
        if self._current_address and self._current_private_key:
            self._emit_found_key(self._current_private_key, self._current_address)
            self._current_address = None
            self._current_private_key = None

    def _emit_found_key(self, hex_key: str, address: str) -> None:
        wif_key = private_key_to_wif(hex_key)
        data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'address': address,
            'hex_key': hex_key,
            'wif_key': wif_key,
            'source': 'VANITY'
        }
        self.key_found.emit(data)
        self.found_count += 1
        self.log_message.emit(f"✅ Ключ найден и отправлен в UI: {address}", "success")

    def _read_output_file(self) -> None:
        """Читает файл, созданный VanitySearch, и извлекает ключи (fallback)."""
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.splitlines()
            addr = None
            key = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("PubAddress:") or "Pub Addr:" in line:
                    addr = line.split(":", 1)[1].strip()
                elif "Priv (HEX):" in line or "PrivKey:" in line:
                    hex_part = line.split(":", 1)[1].strip()
                    if hex_part.startswith("0x"):
                        hex_part = hex_part[2:]
                    if len(hex_part) == 64 and all(c in '0123456789abcdefABCDEF' for c in hex_part):
                        key = hex_part
                if addr and key:
                    self._emit_found_key(key, addr)
                    addr = None
                    key = None
        except Exception as e:
            self.log_message.emit(f"⚠️ Ошибка чтения файла результатов: {e}", "warning")

    def _handle_speed_line(self, line: str) -> None:
        line_lower = line.lower()
        patterns = [
            r"\[(\d+\.?\d*)\s*Mkey/s\]",
            r"\[GPU\s+(\d+\.?\d*)\s*Mkey/s\]",
            r"(\d+\.?\d*)\s*MK/s",
            r"Speed:\s*(\d+\.?\d*)\s*MKey/s",
            r"(\d+\.?\d*)\s*MKeys/s",
            r"(\d+\.?\d*)\s*GKeys/s",
            r"(\d+\.?\d*)\s*KKeys/s",
            r"GPU\s+\d+:\s*(\d+\.?\d*)\s*MKeys/s",
            r"Speed:\s*(\d+\.?\d*)",
            r"(\d{4,})\s*keys/sec",
            r"(\d+\.?\d*)[,\s]*M\s*keys",
        ]
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                try:
                    speed_value = float(m.group(1))
                    if 'gkey' in line_lower or 'gkeys' in line_lower:
                        keys_per_sec = int(speed_value * 1_000_000_000)
                    elif 'mkey' in line_lower or 'mkeys' in line_lower or 'mk/s' in line_lower:
                        keys_per_sec = int(speed_value * 1_000_000)
                    elif 'kkey' in line_lower or 'kkeys' in line_lower:
                        keys_per_sec = int(speed_value * 1_000)
                    elif 'keys/sec' in line_lower or 'keys/s' in line_lower:
                        keys_per_sec = int(speed_value)
                    else:
                        keys_per_sec = int(speed_value * 1_000_000)
                    self.stats_update.emit({'speed': keys_per_sec})
                    return
                except (ValueError, IndexError):
                    continue
        if 'key' in line_lower or 'speed' in line_lower:
            m = re.search(r'(\d+\.?\d*)', line)
            if m:
                try:
                    speed_value = float(m.group(1))
                    keys_per_sec = int(speed_value * 1_000_000)
                    self.stats_update.emit({'speed': keys_per_sec})
                except (ValueError, IndexError):
                    pass

    def _handle_found_count_line(self, line: str) -> None:
        patterns = [
            r"\[Found\s+(\d+)\]",
            r"\((\d+)\s+found\)",
            r"(\d+)\s+addresses?\s+found"
        ]
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                try:
                    new_count = int(m.group(1))
                    if new_count > self.found_count:
                        self.found_count = new_count
                        self.stats_update.emit({'found_count': self.found_count})
                    return
                except (ValueError, IndexError):
                    continue


# ============================================================
#  БАЗОВЫЙ КЛАСС (с исправленным метаклассом)
# ============================================================
class MetaQObjectABCMeta(type(QObject), ABCMeta):
    pass


class BaseScanner(QObject, ABC, metaclass=MetaQObjectABCMeta):
    """
    Абстрактный базовый класс для всех сканеров.
    Определяет единый интерфейс управления и стандартные сигналы.
    """
    stats_updated = pyqtSignal(dict)
    log_message = pyqtSignal(str, str)
    key_found = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)
    search_finished = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_running = False
        self._is_paused = False
        self._start_time: Optional[float] = None
        self._params: Optional[Dict[str, Any]] = None

    @abstractmethod
    def start(self, params: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def pause(self) -> None:
        pass

    @abstractmethod
    def resume(self) -> None:
        pass

    def is_running(self) -> bool:
        return self._is_running

    def elapsed_time(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def _set_running(self, state: bool) -> None:
        self._is_running = state
        if state:
            self._start_time = time.time()
        else:
            self._start_time = None

    def process_queue(self) -> None:
        pass


# ============================================================
#  МЕНЕДЖЕР ПРОЦЕССОВ (для мультипроцессинга)
# ============================================================
class ProcessManager:
    def __init__(self, queue_timeout: float = 0.1, stop_timeout: float = 3.0):
        self._processes: Dict[int, multiprocessing.Process] = {}
        self._shutdown_event = multiprocessing.Event()
        self._queue = multiprocessing.Queue()
        self._queue_timeout = queue_timeout
        self._stop_timeout = stop_timeout
        self._worker_counter = 0

    def start_worker(self, target: Callable, args: tuple, worker_id: Optional[int] = None) -> int:
        if worker_id is None:
            worker_id = self._worker_counter
            self._worker_counter += 1
        full_args = args + (self._queue, self._shutdown_event)
        p = multiprocessing.Process(target=target, args=full_args, daemon=True)
        p.start()
        self._processes[worker_id] = p
        return worker_id

    def stop_all(self) -> None:
        if not self._processes:
            return
        self._shutdown_event.set()
        time.sleep(0.05)
        for wid, proc in list(self._processes.items()):
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=self._stop_timeout)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=1.0)
            del self._processes[wid]
        self._shutdown_event.clear()

    def get_queue(self) -> multiprocessing.Queue:
        return self._queue

    def get_shutdown_event(self) -> multiprocessing.Event:
        return self._shutdown_event

    def is_running(self) -> bool:
        return any(p.is_alive() for p in self._processes.values())

    def clear(self) -> None:
        self._processes.clear()

    def process_messages(self, handler: Callable[[dict], None], max_per_frame: int = 100) -> None:
        processed = 0
        while processed < max_per_frame:
            try:
                msg = self._queue.get_nowait()
                handler(msg)
                processed += 1
            except Empty:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                break

    def close_queue(self) -> None:
        try:
            self._queue.close()
            self._queue.join_thread()
        except Exception:
            pass


# ============================================================
#  CPU СКАНЕР
# ============================================================
class CPUScanner(BaseScanner):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pm = ProcessManager()
        self._worker_stats: Dict[int, dict] = {}
        self._total_scanned = 0
        self._total_found = 0

    def start(self, params: Dict[str, Any]) -> bool:
        if self._is_running:
            return False

        target = params.get('target', '')
        start_hex = params.get('start_hex', '')
        end_hex = params.get('end_hex', '')
        if not target or not start_hex or not end_hex:
            self.log_message.emit("Не заполнены обязательные поля", "error")
            return False
        if not is_coincurve_available():
            self.log_message.emit("Библиотека coincurve не установлена. CPU поиск недоступен.", "error")
            return False
        result, err = validate_key_range(start_hex, end_hex)
        if result is None:
            self.log_message.emit(f"Ошибка диапазона: {err}", "error")
            return False
        start_int, end_int, total_keys = result

        self._params = params.copy()
        self._params['start_int'] = start_int
        self._params['end_int'] = end_int
        self._params['total_keys'] = total_keys

        workers_count = params.get('workers', 4)
        mode = params.get('mode', 'sequential')
        attempts = params.get('attempts', 0)
        prefix_len = params.get('prefix_len', 8)
        target_prefix = target[:prefix_len]

        self._worker_stats.clear()
        self._pm.clear()
        for wid in range(workers_count):
            self._pm.start_worker(
                target=cpu_worker.worker_main,
                args=(
                    target_prefix,
                    start_int,
                    end_int,
                    attempts,
                    mode,
                    wid,
                    workers_count
                ),
                worker_id=wid
            )
            self._worker_stats[wid] = {'scanned': 0, 'found': 0, 'speed': 0.0, 'progress': 0}

        self._set_running(True)
        self._total_scanned = 0
        self._total_found = 0
        self.log_message.emit(f"Запущено {workers_count} CPU воркеров в режиме {mode}", "info")
        return True

    def stop(self) -> None:
        self._pm.stop_all()
        self._set_running(False)
        self.log_message.emit("CPU поиск остановлен", "warning")

    def pause(self) -> None:
        if not self._is_running or self._is_paused:
            return
        self._is_paused = True
        self._pm.stop_all()
        self.log_message.emit("CPU поиск приостановлен", "warning")

    def resume(self) -> None:
        if not self._is_paused or self._params is None:
            return
        self._is_paused = False
        self.start(self._params)
        self.log_message.emit("CPU поиск возобновлён", "info")

    def process_queue(self) -> None:
        self._pm.process_messages(self._handle_message)

    def _handle_message(self, msg: dict) -> None:
        typ = msg.get('type')
        if typ == 'stats':
            wid = msg['worker_id']
            if wid in self._worker_stats:
                self._worker_stats[wid].update({
                    'scanned': msg.get('scanned', 0),
                    'found': msg.get('found', 0),
                    'speed': msg.get('speed', 0.0),
                    'progress': msg.get('progress', 0),
                })
                self._total_scanned = sum(s['scanned'] for s in self._worker_stats.values())
                self._total_found = sum(s['found'] for s in self._worker_stats.values())
                total_speed = sum(s['speed'] for s in self._worker_stats.values())
                self.stats_updated.emit({
                    'total_scanned': self._total_scanned,
                    'total_found': self._total_found,
                    'total_speed': total_speed,
                    'workers': self._worker_stats,
                })
        elif typ == 'found':
            self.key_found.emit(msg)
        elif typ == 'log':
            self.log_message.emit(msg.get('message', ''), msg.get('level', 'info'))
        elif typ == 'worker_finished':
            wid = msg['worker_id']
            self.worker_finished.emit(wid)
            if not self._pm.is_running():
                self._set_running(False)
                self.search_finished.emit(True)

    def close_queue(self) -> None:
        self._pm.close_queue()


# ============================================================
#  GPU СКАНЕР
# ============================================================
class GPUScanner(BaseScanner):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._processes: List[Tuple[subprocess.Popen, gpu_worker.OptimizedOutputReader]] = []
        self._worker_stats: Dict[int, dict] = {}
        self._worker_counter = 0
        self._total_checked = 0
        self._total_speed = 0.0
        self._last_update_time = 0.0
        self._start_key = 0
        self._end_key = 0
        self._total_keys_in_range = 0
        self._use_compressed = True

    def start(self, params: Dict[str, Any]) -> bool:
        if self._is_running:
            return False

        target = params.get('target', '')
        start_hex = params.get('start_hex', '')
        end_hex = params.get('end_hex', '')
        if not target or not start_hex or not end_hex:
            self.log_message.emit("Не заполнены обязательные поля", "error")
            return False
        result, err = validate_key_range(start_hex, end_hex)
        if result is None:
            self.log_message.emit(f"Ошибка диапазона: {err}", "error")
            return False
        start_int, end_int, total_keys = result
        if not os.path.exists(config.CUBITCRACK_EXE):
            self.log_message.emit(f"cuBitcrack.exe не найден: {config.CUBITCRACK_EXE}", "error")
            return False

        self._params = params.copy()
        self._start_key = start_int
        self._end_key = end_int
        self._total_keys_in_range = total_keys
        self._use_compressed = params.get('use_compressed', True)

        devices_input = params.get('devices', '0')
        devices = self._parse_devices(devices_input)
        if not devices:
            self.log_message.emit("Не указаны корректные ID GPU", "error")
            return False

        blocks = params.get('blocks', '256')
        threads = params.get('threads', '128')
        points = params.get('points', '256')
        priority_index = params.get('priority_index', 0)
        workers_per_device = params.get('workers_per_device', 1)

        total_workers = len(devices) * workers_per_device
        effective_workers = min(total_workers, total_keys) if total_keys > 0 else 0
        if effective_workers == 0:
            self.log_message.emit("Некорректное количество воркеров", "error")
            return False
        keys_per_worker = max(1, total_keys // effective_workers)

        self._processes.clear()
        self._worker_stats.clear()
        self._worker_counter = 0

        for device in devices:
            for _ in range(workers_per_device):
                if self._worker_counter >= effective_workers:
                    break
                wid = self._worker_counter
                worker_start = start_int + wid * keys_per_worker
                worker_end = min(worker_start + keys_per_worker - 1, end_int)

                if worker_start > worker_end:
                    continue

                try:
                    proc, reader = gpu_worker.start_gpu_search_with_range(
                        target_address=target,
                        start_key=worker_start,
                        end_key=worker_end,
                        device=device,
                        blocks=blocks,
                        threads=threads,
                        points=points,
                        priority_index=priority_index,
                        parent_window=None,
                        use_compressed=self._use_compressed
                    )
                    if proc is None or reader is None:
                        raise RuntimeError("Не удалось запустить воркер")
                    reader.log_message.connect(lambda msg, lvl: self.log_message.emit(msg, lvl))
                    reader.stats_update.connect(lambda stats, wid=wid: self._handle_gpu_stats(wid, stats))
                    reader.found_key.connect(self.key_found.emit)
                    reader.process_finished.connect(lambda: self._handle_gpu_finished(wid))
                    reader.start()
                    self._processes.append((proc, reader))
                    self._worker_stats[wid] = {'checked': 0, 'speed': 0.0}
                    self._worker_counter += 1
                except Exception as e:
                    self.log_message.emit(f"Ошибка запуска воркера {wid}: {e}", "error")

        if self._processes:
            self._set_running(True)
            self._total_checked = 0
            self._total_speed = 0.0
            self.log_message.emit(f"Запущено {len(self._processes)} GPU воркеров", "success")
            return True
        else:
            self.log_message.emit("Не удалось запустить ни одного GPU воркера", "error")
            return False

    def _parse_devices(self, devices_input: str) -> List[str]:
        devices = []
        for part in devices_input.split(','):
            part = part.strip()
            if not part:
                continue
            m = re.match(r'^(\d+)', part)
            if m:
                devices.append(m.group(1))
        return devices

    def _handle_gpu_stats(self, wid: int, stats: dict):
        if wid in self._worker_stats:
            self._worker_stats[wid]['checked'] = stats.get('checked', 0)
            self._worker_stats[wid]['speed'] = stats.get('speed', 0.0)
            self._total_checked = sum(s['checked'] for s in self._worker_stats.values())
            self._total_speed = sum(s['speed'] for s in self._worker_stats.values())
            progress = 0
            if self._total_keys_in_range > 0:
                progress = min(100, int((self._total_checked / self._total_keys_in_range) * 100))
            self.stats_updated.emit({
                'total_scanned': self._total_checked,
                'total_found': 0,
                'total_speed': self._total_speed,
                'progress': progress,
                'workers': self._worker_stats,
            })

    def _handle_gpu_finished(self, wid: int):
        self.worker_finished.emit(wid)
        if all(not reader.isRunning() for _, reader in self._processes):
            self._set_running(False)
            self.search_finished.emit(True)

    def stop(self) -> None:
        gpu_worker.stop_gpu_search_internal(self._processes)
        self._set_running(False)
        self.log_message.emit("GPU поиск остановлен", "warning")

    def pause(self) -> None:
        if self._is_running and not self._is_paused:
            self._is_paused = True
            self.stop()
            self.log_message.emit("GPU поиск приостановлен (остановлен)", "warning")

    def resume(self) -> None:
        if not self._is_paused or self._params is None:
            return
        self._is_paused = False
        self.start(self._params)
        self.log_message.emit("GPU поиск возобновлён", "info")

    def process_queue(self) -> None:
        pass


# ============================================================
#  KANGAROO СКАНЕР
# ============================================================
class KangarooScanner(BaseScanner):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[KangarooWorker] = None
        self._thread: Optional[QThread] = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_time)
        self._timer.setInterval(500)

    def start(self, params: Dict[str, Any]) -> bool:
        if self._is_running:
            return False

        exe = params.get('etarkangaroo_exe', '')
        if not os.path.exists(exe):
            self.log_message.emit(f"Файл не найден: {exe}", "error")
            return False
        pubkey = params.get('pubkey_hex', '')
        rb = params.get('rb_hex', '')
        re = params.get('re_hex', '')
        if not pubkey or not rb or not re:
            self.log_message.emit("Не заполнены обязательные поля", "error")
            return False

        self._params = params.copy()

        self._worker = KangarooWorker(params)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._worker.log_message.connect(lambda msg: self.log_message.emit(msg, "info"))
        self._worker.status_update.connect(self._handle_status)
        self._worker.range_update.connect(lambda rb, re: self.log_message.emit(f"Диапазон: {rb} - {re}", "info"))
        self._worker.found_key.connect(self._handle_found)
        self._worker.finished.connect(self._handle_finished)

        self._thread.started.connect(self._worker.run)
        self._thread.start()

        self._set_running(True)
        self._timer.start()
        self.log_message.emit("Kangaroo поиск запущен", "success")
        return True

    def stop(self) -> None:
        self._safe_stop()
        self.log_message.emit("Kangaroo поиск остановлен", "warning")

    def pause(self) -> None:
        self.log_message.emit("Kangaroo не поддерживает паузу", "warning")

    def resume(self) -> None:
        self.log_message.emit("Kangaroo не поддерживает возобновление", "warning")

    def _safe_stop(self):
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(3000):
                self._thread.terminate()
                self._thread.wait()
        self._timer.stop()
        self._set_running(False)

    def _handle_status(self, speed: float, elapsed: int, session: int):
        self.stats_updated.emit({
            'total_speed': speed,
            'session': session,
            'elapsed': elapsed,
        })

    def _handle_found(self, private_hex: str):
        from utils.hextowif import generate_all_from_hex
        try:
            result = generate_all_from_hex(private_hex, compressed=True, testnet=False)
            key_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'address': result['P2PKH'],
                'hex_key': private_hex,
                'wif_key': result['WIF'],
                'source': 'KANGAROO'
            }
            self.key_found.emit(key_data)
        except Exception as e:
            self.log_message.emit(f"Ошибка обработки найденного ключа: {e}", "error")
        self.stop()

    def _handle_finished(self, success: bool):
        self._safe_stop()
        self.search_finished.emit(success)

    def _update_time(self):
        if self._is_running:
            elapsed = int(self.elapsed_time())
            self.stats_updated.emit({'elapsed': elapsed})


# ============================================================
#  VANITY СКАНЕР (использует встроенный VanityOutputReader)
# ============================================================
class VanityScanner(BaseScanner):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[VanityOutputReader] = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_ui)
        self._timer.setInterval(1000)
        self._keys_found = 0
        self._prefix = ""
        self._output_file = ""

    def start(self, params: Dict[str, Any]) -> bool:
        if self._is_running:
            return False

        prefix = params.get('prefix', '')
        if not prefix:
            self.log_message.emit("Укажите префикс", "error")
            return False

        exe_path = os.path.join(config.BASE_DIR, "VanitySearch.exe")
        if not os.path.exists(exe_path):
            self.log_message.emit("VanitySearch.exe не найден", "error")
            return False

        self._prefix = prefix
        self._output_file = os.path.join(config.BASE_DIR, f"VANITY_{prefix}.txt")
        if os.path.exists(self._output_file):
            try:
                os.remove(self._output_file)
            except OSError:
                pass

        cmd = [exe_path]
        gpu_text = params.get('gpu', '0')
        if gpu_text == "CPU":
            threads = params.get('cpu_threads', 4)
            cmd.extend(["-t", str(threads)])
        else:
            cmd.append("-gpu")
            device_ids = gpu_text.replace(',', ' ').split()
            cmd.extend(["-gpuId"] + device_ids)

        addr_type = params.get('addr_type', 0)
        if addr_type == 1:
            cmd.append("-p2sh")
        elif addr_type == 2:
            cmd.append("-bech32")
        elif addr_type == 3:
            cmd.append("-bech32m")

        if not params.get('compressed', True):
            cmd.append("-u")

        cmd.extend(["-o", self._output_file, prefix])

        try:
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=config.BASE_DIR,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            # ✅ Передаём output_file в reader
            self._reader = VanityOutputReader(self._process, None, prefix, self._output_file)
            self._reader.log_message.connect(lambda msg, lvl: self.log_message.emit(msg, lvl))
            self._reader.stats_update.connect(self._handle_vanity_stats)
            self._reader.key_found.connect(self.key_found.emit)
            self._reader.process_finished.connect(self._handle_vanity_finished)
            self._reader.start()

            self._set_running(True)
            self._keys_found = 0
            self._timer.start()
            self.log_message.emit(f"VanitySearch запущен для префикса '{prefix}'", "success")
            return True
        except Exception as e:
            self.log_message.emit(f"Ошибка запуска VanitySearch: {e}", "error")
            return False

    def _handle_vanity_stats(self, stats: dict):
        if 'speed' in stats:
            self.stats_updated.emit({'total_speed': stats['speed']})
        if 'found_count' in stats:
            self._keys_found = stats['found_count']
            self.stats_updated.emit({'total_found': self._keys_found})

    def _handle_vanity_finished(self):
        self._set_running(False)
        self._timer.stop()
        self.search_finished.emit(True)

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        if self._reader:
            self._reader.stop()
            self._reader.wait(2000)
        self._set_running(False)
        self._timer.stop()
        self.log_message.emit("VanitySearch остановлен", "warning")

    def pause(self) -> None:
        self.log_message.emit("VanitySearch не поддерживает паузу", "warning")

    def resume(self) -> None:
        self.log_message.emit("VanitySearch не поддерживает возобновление", "warning")

    def _update_ui(self):
        if self._is_running and self._process:
            self.stats_updated.emit({'elapsed': int(self.elapsed_time())})


# ============================================================
#  MATRIX СКАНЕР (использует старый MatrixLogic как основу)
# ============================================================
class MatrixScanner(BaseScanner):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._logic = OldMatrixLogic()
        self._logic.log_message.connect(lambda msg: self.log_message.emit(msg, "info"))
        self._logic.key_found.connect(self.key_found.emit)
        self._logic.worker_finished.connect(self.worker_finished.emit)

    def start(self, params: Dict[str, Any]) -> bool:
        if self._is_running:
            return False
        target = params.get('target', '')
        start_hex = params.get('start_hex', '')
        end_hex = params.get('end_hex', '')
        num_workers = params.get('num_workers', 4)
        mode = params.get('mutation_mode', 'random_curve')
        strength = params.get('mutation_strength', 0.15)
        prob = params.get('mutation_probability', 0.7)
        visualize = params.get('visualize_mutations', False)
        locked = params.get('locked_positions', [])
        adaptive = params.get('adaptive_mode', True)

        if not target or not start_hex or not end_hex:
            self.log_message.emit("Не заполнены обязательные поля", "error")
            return False

        result = self._logic.start_search(
            target_address=target,
            start_hex=start_hex,
            end_hex=end_hex,
            num_workers=num_workers,
            mutation_mode=mode,
            mutation_strength=strength,
            mutation_probability=prob,
            visualize_mutations=visualize,
            locked_positions=locked,
            adaptive_mode=adaptive
        )
        if result:
            self._set_running(True)
            self.log_message.emit("Matrix поиск запущен", "success")
        return result

    def stop(self) -> None:
        self._logic.stop_search()
        self._set_running(False)
        self.log_message.emit("Matrix поиск остановлен", "warning")

    def pause(self) -> None:
        self.log_message.emit("Matrix не поддерживает паузу", "warning")

    def resume(self) -> None:
        self.log_message.emit("Matrix не поддерживает возобновление", "warning")

    def process_queue(self) -> None:
        # У MatrixLogic есть своя очередь, но мы можем использовать её
        # Через метод get_queue() и обработку вручную
        pass

    def update_mutation_params(self, strength: float = None, probability: float = None,
                               update_interval: int = None, visualize: bool = None):
        self._logic.update_mutation_params(strength, probability, update_interval, visualize)

    def update_locked_positions(self, positions: List[int]):
        self._logic.update_locked_positions(positions)

    def get_queue(self) -> multiprocessing.Queue:
        return self._logic.get_queue()


# ============================================================
#  ФАБРИКА И МЕНЕДЖЕР
# ============================================================
class ScannerFactory:
    _scanners = {
        'cpu': CPUScanner,
        'gpu': GPUScanner,
        'kangaroo': KangarooScanner,
        'vanity': VanityScanner,
        'matrix': MatrixScanner,
    }

    @classmethod
    def create(cls, scanner_type: str) -> BaseScanner:
        scanner_class = cls._scanners.get(scanner_type)
        if scanner_class is None:
            raise ValueError(f"Unknown scanner type: {scanner_type}")
        return scanner_class()


class ScannerManager(QObject):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._scanners: Dict[str, BaseScanner] = {}

    def get_scanner(self, scanner_type: str) -> BaseScanner:
        if scanner_type not in self._scanners:
            self._scanners[scanner_type] = ScannerFactory.create(scanner_type)
        return self._scanners[scanner_type]

    def stop_all(self) -> None:
        for scanner in self._scanners.values():
            if scanner.is_running():
                scanner.stop()

    def process_all_queues(self) -> None:
        for scanner in self._scanners.values():
            if hasattr(scanner, 'process_queue'):
                scanner.process_queue()