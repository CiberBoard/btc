# core/gpu_logic.py
from __future__ import annotations

import os
import subprocess
import time
import logging
from typing import Dict, List, Tuple, Optional, Any, Union, TYPE_CHECKING
from collections import deque
from threading import Thread
from dataclasses import dataclass, field

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner

import config
from utils.helpers import validate_key_range
import core.gpu_scanner as gpu_core
from ui.gpu_auto_config import auto_configure_gpu  # 🛠 ИМПОРТ: автоконфигурация для GPU

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

@dataclass(frozen=True)
class GPUWorkerConfig:
    """Конфигурация параметров GPU воркера"""
    DEFAULT_BLOCKS: str = "128"
    DEFAULT_THREADS: str = "64"
    DEFAULT_POINTS: str = "128"

    # Оптимизированные параметры для разных серий GPU
    RTX_30_40_BLOCKS: str = "288"
    RTX_30_40_THREADS: str = "128"
    RTX_30_40_POINTS: str = "512"

    RTX_20_BLOCKS: str = "256"
    RTX_20_THREADS: str = "128"
    RTX_20_POINTS: str = "256"

    # Тайминги
    RESTART_DELAY_MS: int = 1000
    SUBPROCESS_TIMEOUT_SEC: int = 5
    VALIDATION_TIMEOUT: float = 0.1

    # Диапазоны
    MIN_VALID_RANGE: int = 1
    MAX_RESTART_INTERVAL_SEC: int = 3600


GPU_CONFIG: GPUWorkerConfig = GPUWorkerConfig()

# 🛠 Константы для статусов
STATUS_READY: str = "Готов к работе"
STATUS_SEARCHING: str = "Поиск запущен"
STATUS_RANDOM: str = "Случайный поиск"
STATUS_SEQUENTIAL: str = "Последовательный поиск"
STATUS_ERROR: str = "Ошибка"

# 🛠 Константы для стилей кнопок
BTN_STYLE_SUCCESS: str = "background: #27ae60; font-weight: bold;"
BTN_STYLE_DANGER: str = "background: #e74c3c; font-weight: bold;"


class GPULogic:
    """
    Логика управления GPU поиском приватных ключей Bitcoin.
    """

    main_window: 'BitcoinGPUCPUScanner'
    gpu_processes: List[Tuple[Any, Any]]
    gpu_is_running: bool
    gpu_start_time: Optional[float]
    gpu_keys_checked: int
    gpu_keys_per_second: float
    gpu_last_update_time: float
    gpu_start_range_key: int
    gpu_end_range_key: int
    gpu_total_keys_in_range: int
    gpu_worker_stats: Dict[Any, Dict[str, Any]]

    def __init__(self, main_window: 'BitcoinGPUCPUScanner'):
        self.main_window = main_window
        self.gpu_processes = []
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_keys_checked = 0
        self.gpu_keys_per_second = 0.0
        self.gpu_last_update_time = 0.0
        self.gpu_start_range_key = 0
        self.gpu_end_range_key = 0
        self.gpu_total_keys_in_range = 0
        self.gpu_worker_stats = {}

    def setup_gpu_connections(self) -> None:
        """Настройка подключений сигналов для GPU."""
        self.main_window.gpu_restart_timer.timeout.connect(self.restart_gpu_random_search)

    # ═══════════════════════════════════════════
    # 🔧 МЕТОДЫ УПРАВЛЕНИЯ ПОИСКОМ
    # ═══════════════════════════════════════════

    def auto_optimize_gpu_parameters(self) -> None:
        """
        Автоматическая оптимизация параметров GPU.
        🛠 УЛУЧШЕНИЕ: Использует модуль gpu_auto_config для интеллектуальной настройки
        """
        try:
            # 🛠 Вызываем автоконфигурацию из gpu_auto_config.py
            result = auto_configure_gpu(self.main_window)

            if result:
                # 🛠 Логируем результат
                self.main_window.append_log(
                    f"✅ Параметры применены: "
                    f"Blocks={result['blocks']}, "
                    f"Threads={result['threads']}, "
                    f"Points={result['points']}, "
                    f"GPU={result['gpu_count']}",
                    "success"
                )
            # Если result=None — ошибка уже обработана в auto_configure_gpu

        except ImportError:
            logger.warning("Модуль gpu_auto_config не найден, используем старый метод")
            # 🛠 Fallback на старый метод (если файл автоконфига отсутствует)
            self._auto_optimize_gpu_parameters_legacy()
        except Exception as e:
            logger.exception("Ошибка автооптимизации")
            QMessageBox.critical(
                self.main_window, "Ошибка",
                f"Не удалось оптимизировать параметры:\n{type(e).__name__}: {str(e)}"
            )
            self._apply_default_settings()

    def _auto_optimize_gpu_parameters_legacy(self) -> None:
        """
        🛠 Вспомогательный метод: старый алгоритм оптимизации (fallback)
        """
        try:
            gpu_info = self._get_gpu_device_info()
            if self._is_rtx_30_or_40_series(gpu_info):
                self._apply_rtx_30_40_settings()
            elif self._is_rtx_20_series(gpu_info):
                self._apply_rtx_20_settings()
            else:
                self._apply_default_settings()
        except Exception as e:
            logger.warning(f"Не удалось оптимизировать параметры (legacy): {e}")
            self._apply_default_settings()

    def _get_gpu_device_info(self) -> str:
        """
        Получает информацию об устройствах GPU через cuBitcrack.
        """
        try:
            return subprocess.check_output(
                [config.CUBITCRACK_EXE, "--list-devices"],
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=GPU_CONFIG.SUBPROCESS_TIMEOUT_SEC
            )
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            logger.debug(f"Не удалось получить список GPU устройств: {e}")
            return ""

    def _is_rtx_30_or_40_series(self, gpu_info: str) -> bool:
        """Проверка серии GPU RTX 30/40."""
        return "RTX 30" in gpu_info or "RTX 40" in gpu_info

    def _is_rtx_20_series(self, gpu_info: str) -> bool:
        """Проверка серии GPU RTX 20."""
        return "RTX 20" in gpu_info

    def _apply_rtx_30_40_settings(self) -> None:
        """Применяет оптимизированные настройки для RTX 30/40 серии."""
        self.main_window.blocks_combo.setCurrentText(GPU_CONFIG.RTX_30_40_BLOCKS)
        self.main_window.threads_combo.setCurrentText(GPU_CONFIG.RTX_30_40_THREADS)
        self.main_window.points_combo.setCurrentText(GPU_CONFIG.RTX_30_40_POINTS)
        self.main_window.append_log("Параметры GPU оптимизированы для RTX 30/40 серии", "success")
        self.main_window.gpu_use_compressed_checkbox.setChecked(True)
        self.main_window.append_log("✅ Сжатые ключи включены для максимальной скорости", "success")

    def _apply_rtx_20_settings(self) -> None:
        """Применяет оптимизированные настройки для RTX 20 серии."""
        self.main_window.blocks_combo.setCurrentText(GPU_CONFIG.RTX_20_BLOCKS)
        self.main_window.threads_combo.setCurrentText(GPU_CONFIG.RTX_20_THREADS)
        self.main_window.points_combo.setCurrentText(GPU_CONFIG.RTX_20_POINTS)
        self.main_window.append_log("Параметры GPU оптимизированы для RTX 20 серии", "success")
        self.main_window.gpu_use_compressed_checkbox.setChecked(True)
        self.main_window.append_log("✅ Сжатые ключи включены для максимальной скорости", "success")

    def _apply_default_settings(self) -> None:
        """Применяет настройки по умолчанию."""
        self.main_window.blocks_combo.setCurrentText(GPU_CONFIG.DEFAULT_BLOCKS)
        self.main_window.threads_combo.setCurrentText(GPU_CONFIG.DEFAULT_THREADS)
        self.main_window.points_combo.setCurrentText(GPU_CONFIG.DEFAULT_POINTS)
        self.main_window.append_log("Параметры GPU установлены по умолчанию", "info")

    def validate_gpu_inputs(self) -> bool:
        """
        Валидация входных данных для GPU поиска.
        """
        address = self.main_window.gpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self.main_window, "Ошибка", "Введите корректный BTC адрес для GPU")
            return False

        result, error = validate_key_range(
            self.main_window.gpu_start_key_edit.text().strip(),
            self.main_window.gpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self.main_window, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False

        try:
            min_range = int(self.main_window.gpu_min_range_edit.text().strip())
            max_range = int(self.main_window.gpu_max_range_edit.text().strip())

            if min_range < GPU_CONFIG.MIN_VALID_RANGE or max_range < GPU_CONFIG.MIN_VALID_RANGE:
                QMessageBox.warning(self.main_window, "Ошибка", "Размеры диапазона должны быть положительными числами")
                return False
            if min_range > max_range:
                QMessageBox.warning(self.main_window, "Ошибка",
                                    "Минимальный размер диапазона должен быть <= максимальному")
                return False
        except ValueError as e:
            logger.debug(f"Ошибка парсинга числовых параметров: {e}")
            QMessageBox.warning(self.main_window, "Ошибка", "Минимальный и максимальный диапазон должны быть числами")
            return False

        if not os.path.exists(config.CUBITCRACK_EXE):
            logger.error(f"cuBitcrack.exe не найден: {config.CUBITCRACK_EXE}")
            QMessageBox.warning(self.main_window, "Ошибка", f"Файл cuBitcrack.exe не найден в {config.BASE_DIR}")
            return False

        return True

    def toggle_gpu_search(self) -> None:
        """Переключение состояния поиска (старт/стоп)."""
        if not self.gpu_is_running:
            self.start_gpu_search()
        else:
            self.stop_gpu_search()

    def restart_gpu_random_search(self) -> None:
        """Перезапуск случайного поиска с новым диапазоном."""
        try:
            self.main_window.append_log("🔄 Перезапуск GPU поиска с новым случайным диапазоном...", "info")
            self.stop_gpu_search_internal()
            self.gpu_is_running = False
            QTimer.singleShot(GPU_CONFIG.RESTART_DELAY_MS, self.start_gpu_search)
        except Exception as e:
            logger.exception("❌ Ошибка в restart_gpu_random_search:")
            self.main_window.append_log(f"Критическая ошибка перезапуска: {type(e).__name__}: {e}", "error")
            self.gpu_search_finished()

    def start_gpu_search(self) -> None:
        """Запуск процесса поиска на GPU."""
        if not self.validate_gpu_inputs():
            return

        self.main_window.save_settings()

        raw_start = self.main_window.gpu_start_key_edit.text().strip()
        raw_end = self.main_window.gpu_end_key_edit.text().strip()
        logger.debug(f"🔍 Введённые hex:")
        logger.debug(f"   start_hex = '{raw_start}' (длина: {len(raw_start)})")
        logger.debug(f"   end_hex   = '{raw_end}' (длина: {len(raw_end)})")

        if self.main_window.gpu_random_checkbox.isChecked():
            self._start_gpu_random_search(raw_start, raw_end)
        else:
            self._start_gpu_sequential_search()

    def _start_gpu_random_search(self, raw_start: str, raw_end: str) -> None:
        """Запуск случайного поиска с генерацией нового диапазона."""
        self.stop_gpu_search_internal()

        start_hex = raw_start
        end_hex = raw_end

        logger.debug(f"🔍 Передано в generate_gpu_random_range: start='{start_hex}', end='{end_hex}'")

        start_key, end_key, error = gpu_core.generate_gpu_random_range(
            start_hex, end_hex,
            self.main_window.gpu_min_range_edit.text().strip(),
            self.main_window.gpu_max_range_edit.text().strip(),
            self.main_window.used_ranges,
            self.main_window.max_saved_random
        )

        if error or start_key is None or end_key is None:
            error_msg = error or "Неизвестная ошибка генерации диапазона"
            self.main_window.append_log(f"Ошибка генерации случайного диапазона: {error_msg}", "error")
            QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось сгенерировать диапазон: {error_msg}")
            return

        self.update_gpu_range_label(start_key, end_key)
        self.start_gpu_search_with_range(start_key, end_key)

        interval = int(self.main_window.gpu_restart_interval_combo.currentText()) * 1000
        interval = min(interval, GPU_CONFIG.MAX_RESTART_INTERVAL_SEC * 1000)
        self.main_window.gpu_restart_timer.start(interval)

    def _start_gpu_sequential_search(self) -> None:
        """Запуск последовательного поиска по заданному диапазону."""
        self.stop_gpu_search_internal()

        result, _ = validate_key_range(
            self.main_window.gpu_start_key_edit.text().strip(),
            self.main_window.gpu_end_key_edit.text().strip()
        )
        if result is None:
            return

        start_key, end_key, _ = result
        self.update_gpu_range_label(start_key, end_key)
        self.start_gpu_search_with_range(start_key, end_key)

    def update_gpu_range_label(self, start_key: Union[int, Any], end_key: Union[int, Any]) -> None:
        """Обновление отображения текущего диапазона поиска."""
        if isinstance(start_key, int) and isinstance(end_key, int):
            self.main_window.gpu_range_label.setText(
                f"Текущий диапазон: <span style='color:#f39c12'>{hex(start_key)}</span> - <span style='color:#f39c12'>{hex(end_key)}</span>"
            )
        else:
            self.main_window.gpu_range_label.setText("Текущий диапазон: -")

    def start_gpu_search_with_range(self, start_key: int, end_key: int) -> None:
        """Запуск поиска с указанным диапазоном ключей."""
        target_address = self.main_window.gpu_target_edit.text().strip()
        use_compressed = self.main_window.gpu_use_compressed_checkbox.isChecked()

        if use_compressed and not target_address.startswith(('1', '3', 'bc1')):
            use_compressed = False
            self.main_window.append_log(
                "⚠️ Адрес не поддерживает сжатые ключи. Флаг -c отключён автоматически.",
                "warning"
            )

        self.gpu_start_range_key = start_key
        self.gpu_end_range_key = end_key
        self.gpu_total_keys_in_range = max(0, end_key - start_key + 1)
        self.gpu_keys_checked = 0

        devices = self._parse_gpu_devices()
        if not devices:
            self.main_window.append_log("❌ Не указаны корректные ID GPU.", "error")
            return

        blocks = self.main_window.blocks_combo.currentText()
        threads = self.main_window.threads_combo.currentText()
        points = self.main_window.points_combo.currentText()
        priority_index = self.main_window.gpu_priority_combo.currentIndex()
        workers_per_device = self.main_window.gpu_workers_per_device_spin.value()

        total_keys = self.gpu_total_keys_in_range
        total_workers = len(devices) * workers_per_device
        effective_workers = min(total_workers, total_keys) if total_keys > 0 else 0
        keys_per_worker = max(1, total_keys // effective_workers) if effective_workers > 0 else 0

        if total_keys <= 0:
            self.main_window.append_log("❌ Некорректный диапазон ключей (пуст или переполнен).", "error")
            return

        success_count = 0
        worker_index = 0

        for device in devices:
            for _ in range(workers_per_device):
                if worker_index >= effective_workers:
                    break

                worker_start = start_key + worker_index * keys_per_worker
                if worker_index == effective_workers - 1:
                    worker_end = end_key
                else:
                    worker_end = worker_start + keys_per_worker - 1
                    worker_end = min(worker_end, end_key)

                if worker_start > worker_end:
                    logger.debug(
                        f"Пропущен воркер {worker_index + 1}: некорректный диапазон {hex(worker_start)}-{hex(worker_end)}"
                    )
                    continue

                try:
                    cuda_process, output_reader = gpu_core.start_gpu_search_with_range(
                        target_address=target_address,
                        start_key=worker_start,
                        end_key=worker_end,
                        device=device,
                        blocks=blocks,
                        threads=threads,
                        points=points,
                        priority_index=priority_index,
                        parent_window=self.main_window,
                        use_compressed=use_compressed
                    )

                    if cuda_process is None or output_reader is None:
                        raise RuntimeError("cuda_process или output_reader = None")

                    self._connect_worker_signals(output_reader)
                    output_reader.start()

                    self.gpu_processes.append((cuda_process, output_reader))
                    success_count += 1

                    mode_tag = " (сжатые ключи)" if use_compressed else ""
                    self.main_window.append_log(
                        f"✅ Запущен воркер {worker_index + 1}/{effective_workers} на GPU {device}. "
                        f"Диапазон: {hex(worker_start)} — {hex(worker_end)}{mode_tag}",
                        "normal"
                    )

                    worker_index += 1

                except Exception as e:
                    logger.exception(f"❌ Ошибка запуска воркера {worker_index + 1} на GPU {device}")
                    self.main_window.append_log(
                        f"❌ Ошибка воркера {worker_index + 1} (GPU {device}): {type(e).__name__}: {str(e)}", "error"
                    )

        if success_count > 0:
            self._on_gpu_search_started(success_count, use_compressed)
        else:
            self.main_window.append_log("❌ Не удалось запустить ни один GPU-воркер.", "error")

    def _parse_gpu_devices(self) -> List[str]:
        """Парсит строку ввода устройств GPU в список ID."""
        devices_input = self.main_window.gpu_device_combo.currentText()
        return [d.strip() for d in devices_input.split(',') if d.strip().isdigit()]

    def _connect_worker_signals(self, output_reader: Any) -> None:
        """Подключает сигналы воркера к слотам главного окна."""
        output_reader.log_message.connect(self.main_window.append_log)
        output_reader.stats_update.connect(self.update_gpu_stats_display)
        output_reader.found_key.connect(self.main_window.handle_found_key)
        output_reader.process_finished.connect(self.handle_gpu_search_finished)

    def _on_gpu_search_started(self, success_count: int, use_compressed: bool) -> None:
        """Обработка успешного запуска поиска."""
        self.gpu_is_running = True
        self.gpu_start_time = time.time()
        self.gpu_last_update_time = time.time()

        self.main_window.gpu_progress_bar.setValue(0)
        self.main_window.gpu_progress_bar.setFormat(
            f"Прогресс: 0% (0 / {self.gpu_total_keys_in_range:,})"
        )
        self.main_window.gpu_start_stop_btn.setText("Остановить GPU")
        self.main_window.gpu_start_stop_btn.setStyleSheet(BTN_STYLE_DANGER)
        self.main_window.gpu_status_label.setText(f"Статус: {STATUS_SEARCHING}")

        mode_summary = " (сжатые ключи)" if use_compressed else ""
        self.main_window.append_log(
            f"🚀 Запущено {success_count} GPU воркеров{mode_summary}",
            "success"
        )

    # ═══════════════════════════════════════════
    # 🔧 МЕТОДЫ ОСТАНОВКИ ПОИСКА
    # ═══════════════════════════════════════════

    def stop_gpu_search_internal(self) -> None:
        """Внутренний метод остановки всех GPU процессов."""
        gpu_core.stop_gpu_search_internal(self.gpu_processes)
        self.gpu_is_running = False

    def stop_gpu_search(self) -> None:
        """Публичный метод остановки поиска с очисткой состояния."""
        self.main_window.gpu_restart_timer.stop()
        self.stop_gpu_search_internal()
        self.gpu_search_finished()
        self.main_window.used_ranges.clear()
        self.update_gpu_range_label("-", "-")

    def handle_gpu_search_finished(self) -> None:
        """Обработчик сигнала завершения процесса."""
        all_finished = True
        for process, reader in self.gpu_processes:
            try:
                if process.poll() is None or reader.isRunning():
                    all_finished = False
                    break
            except (AttributeError, OSError) as e:
                logger.debug(f"Ошибка проверки процесса: {e}")
                all_finished = False
                break

        if all_finished:
            self.gpu_search_finished()

    # ═══════════════════════════════════════════
    # 🔧 ОБНОВЛЕНИЕ СТАТИСТИКИ И ИНТЕРФЕЙСА
    # ═══════════════════════════════════════════

    def update_gpu_stats_display(self, stats: Dict[str, Any]) -> None:
        """Обновление отображения статистики GPU."""
        try:
            sender_reader = self.main_window.sender()
            if not hasattr(self, 'gpu_worker_stats'):
                self.gpu_worker_stats = {}
            self.gpu_worker_stats[sender_reader] = stats

            total_speed = 0.0
            total_checked = 0
            active_workers = self._get_active_workers()

            for reader in active_workers:
                if reader in self.gpu_worker_stats:
                    worker_stats = self.gpu_worker_stats[reader]
                    total_speed += worker_stats.get('speed', 0.0)
                    total_checked += worker_stats.get('checked', 0)

            self.gpu_keys_per_second = total_speed
            self.gpu_keys_checked = total_checked
            self.gpu_last_update_time = time.time()

            self._update_progress_display(total_checked, total_speed)

            self.main_window.gpu_speed_label.setText(f"Скорость: {self.gpu_keys_per_second:.2f} MKey/s")
            self.main_window.gpu_checked_label.setText(f"Проверено ключей: {self.gpu_keys_checked:,}")

        except Exception as e:
            logger.exception("Ошибка обновления статистики GPU")

    def _get_active_workers(self) -> List[Any]:
        """Возвращает список активных воркеров."""
        active = []
        for process, reader in self.gpu_processes:
            try:
                if reader.isRunning() and process.poll() is None:
                    active.append(reader)
            except (AttributeError, OSError):
                continue
        return active

    def _update_progress_display(self, total_checked: int, total_speed: float) -> None:
        """Обновление отображения прогресса."""
        if self.gpu_total_keys_in_range <= 0:
            self.main_window.gpu_progress_bar.setFormat(f"Проверено: {self.gpu_keys_checked:,} ключей")
            return

        progress_percent = min(100.0, (self.gpu_keys_checked / self.gpu_total_keys_in_range) * 100)
        self.main_window.gpu_progress_bar.setValue(int(progress_percent))

        elapsed = time.time() - self.gpu_start_time if self.gpu_start_time is not None else 0.0

        if self.main_window.gpu_random_checkbox.isChecked():
            if elapsed > 0:
                mins, secs = divmod(elapsed, 60)
                self.main_window.gpu_progress_bar.setFormat(
                    f"Оценочный прогресс: {progress_percent:.2f}% ({int(mins):02d}:{int(secs):02d})"
                )
            else:
                self.main_window.gpu_progress_bar.setFormat(
                    f"Оценочный прогресс: {progress_percent:.2f}% (00:00)"
                )
        else:
            self.main_window.gpu_progress_bar.setFormat(
                f"Прогресс: {progress_percent:.2f}% ({self.gpu_keys_checked:,} / {self.gpu_total_keys_in_range:,})"
            )

    def update_gpu_time_display(self) -> None:
        """Обновление отображения времени работы GPU поиска."""
        if self.gpu_start_time is not None:
            elapsed = time.time() - self.gpu_start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self.main_window.gpu_time_label.setText(f"Время работы: {h:02d}:{m:02d}:{s:02d}")

            if (self.gpu_total_keys_in_range > 0
                    and self.gpu_keys_per_second > 0
                    and not self.main_window.gpu_random_checkbox.isChecked()):
                self._update_sequential_progress(elapsed)

            status = STATUS_RANDOM if self.main_window.gpu_random_checkbox.isChecked() else STATUS_SEQUENTIAL
            self.main_window.gpu_status_label.setText(f"Статус: {status}")
        else:
            self.main_window.gpu_time_label.setText("Время работы: 00:00:00")
            self.main_window.gpu_status_label.setText(f"Статус: {STATUS_READY}")

    def _update_sequential_progress(self, elapsed: float) -> None:
        """Обновление прогресса для последовательного режима."""
        time_since_update = time.time() - self.gpu_last_update_time
        estimated_total = self.gpu_keys_checked + self.gpu_keys_per_second * time_since_update
        progress = min(100.0, (estimated_total / self.gpu_total_keys_in_range) * 100)

        self.main_window.gpu_progress_bar.setValue(int(progress))
        self.main_window.gpu_progress_bar.setFormat(
            f"Прогресс: {progress:.1f}% ({int(estimated_total):,} / {self.gpu_total_keys_in_range:,})"
        )

    # ═══════════════════════════════════════════
    # 🔧 ЗАВЕРШЕНИЕ ПОИСКА
    # ═══════════════════════════════════════════

    def gpu_search_finished(self) -> None:
        """Сброс состояния после завершения поиска."""
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_processes = []
        self.gpu_worker_stats.clear()

        self.main_window.gpu_start_stop_btn.setText("Запустить GPU поиск")
        self.main_window.gpu_start_stop_btn.setStyleSheet(BTN_STYLE_SUCCESS)
        self.main_window.gpu_status_label.setText(f"Статус: {STATUS_READY}")
        self.main_window.gpu_progress_bar.setValue(0)
        self.main_window.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.main_window.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.main_window.gpu_checked_label.setText("Проверено ключей: 0")
        self.main_window.append_log("GPU поиск завершен", "normal")

    def gpu_status_label_update(self, text: str) -> None:
        """Обновление текста статуса в интерфейсе."""
        self.main_window.gpu_status_label.setText(f"Статус: {text}")


# 🛠 Явный экспорт публичного API модуля
__all__ = [
    'GPUWorkerConfig',
    'GPU_CONFIG',
    'STATUS_READY',
    'STATUS_SEARCHING',
    'STATUS_RANDOM',
    'STATUS_SEQUENTIAL',
    'STATUS_ERROR',
    'BTN_STYLE_SUCCESS',
    'BTN_STYLE_DANGER',
    'GPULogic',
]