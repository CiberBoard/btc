# core/gpu_logic.py
import os
import subprocess
import time
import config
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
from utils.helpers import validate_key_range
import core.gpu_scanner as gpu_core
from core.gpu_scanner import logger


class GPULogic:
    def __init__(self, main_window):
        self.main_window = main_window
        self.gpu_processes = []
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_keys_checked = 0
        self.gpu_keys_per_second = 0
        self.gpu_last_update_time = 0
        self.gpu_start_range_key = 0
        self.gpu_end_range_key = 0
        self.gpu_total_keys_in_range = 0
        self.gpu_worker_stats = {}

    def setup_gpu_connections(self):
        self.main_window.gpu_restart_timer.timeout.connect(self.restart_gpu_random_search)

    # ============ GPU METHODS ============

    def auto_optimize_gpu_parameters(self):
        """Автоматическая оптимизация параметров GPU"""
        try:
            gpu_info = ""
            try:
                gpu_info = subprocess.check_output(
                    [config.CUBITCRACK_EXE, "--list-devices"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Не удалось получить список устройств: {e}")

            if "RTX 30" in gpu_info or "RTX 40" in gpu_info:
                self.main_window.blocks_combo.setCurrentText("288")
                self.main_window.threads_combo.setCurrentText("128")
                self.main_window.points_combo.setCurrentText("512")
                self.main_window.append_log("Параметры GPU оптимизированы для RTX 30/40 серии", "success")
                self.main_window.gpu_use_compressed_checkbox.setChecked(True)
                self.main_window.append_log("✅ Сжатые ключи включены для максимальной скорости", "success")
            elif "RTX 20" in gpu_info:
                self.main_window.blocks_combo.setCurrentText("256")
                self.main_window.threads_combo.setCurrentText("128")
                self.main_window.points_combo.setCurrentText("256")
                self.main_window.append_log("Параметры GPU оптимизированы для RTX 20 серии", "success")
                self.main_window.gpu_use_compressed_checkbox.setChecked(True)
                self.main_window.append_log("✅ Сжатые ключи включены для максимальной скорости", "success")
            else:
                self.main_window.blocks_combo.setCurrentText("128")
                self.main_window.threads_combo.setCurrentText("64")
                self.main_window.points_combo.setCurrentText("128")
                self.main_window.append_log("Параметры GPU установлены по умолчанию", "info")
        except Exception as e:
            self.main_window.append_log(f"Ошибка оптимизации GPU: {str(e)}", "error")
            self.main_window.blocks_combo.setCurrentText("128")
            self.main_window.threads_combo.setCurrentText("64")
            self.main_window.points_combo.setCurrentText("128")

    def validate_gpu_inputs(self):
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
            if min_range <= 0 or max_range <= 0:
                QMessageBox.warning(self.main_window, "Ошибка", "Размеры диапазона должны быть положительными числами")
                return False
            if min_range > max_range:
                QMessageBox.warning(self.main_window, "Ошибка", "Минимальный размер диапазона должен быть <= максимальному")
                return False
        except ValueError:
            QMessageBox.warning(self.main_window, "Ошибка", "Минимальный и максимальный диапазон должны быть числами")
            return False

        if not os.path.exists(config.CUBITCRACK_EXE):
            QMessageBox.warning(self.main_window, "Ошибка", f"Файл cuBitcrack.exe не найден в {config.BASE_DIR}")
            return False

        return True

    def toggle_gpu_search(self):
        if not self.gpu_is_running:
            self.start_gpu_search()
        else:
            self.stop_gpu_search()

    def restart_gpu_random_search(self):
        try:
            self.main_window.append_log("🔄 Перезапуск GPU поиска с новым случайным диапазоном...", "info")
            self.stop_gpu_search_internal()
            self.gpu_is_running = False
            QTimer.singleShot(1000, self.start_gpu_search)
        except Exception as e:
            logger.exception("❌ Ошибка в restart_gpu_random_search:")
            self.main_window.append_log(f"Критическая ошибка перезапуска: {e}", "error")
            self.gpu_search_finished()  # возвращаем UI в безопасное состояние

    def start_gpu_search(self):
        if not self.validate_gpu_inputs():
            return

        self.main_window.save_settings()

        # 🔍 ДИАГНОСТИКА: ЛОГИРУЕМ ВХОДНЫЕ HEX
        raw_start = self.main_window.gpu_start_key_edit.text().strip()
        raw_end = self.main_window.gpu_end_key_edit.text().strip()
        logger.debug(f"🔍 Введённые hex:")
        logger.debug(f"   start_hex = '{raw_start}' (длина: {len(raw_start)})")
        logger.debug(f"   end_hex   = '{raw_end}' (длина: {len(raw_end)})")

        if self.main_window.gpu_random_checkbox.isChecked():
            self.stop_gpu_search_internal()

            # НЕ чистим lstrip — пусть validate_key_range сам разбирается
            start_hex = raw_start
            end_hex = raw_end

            logger.debug(f"🔍 Передано в generate_gpu_random_range: start='{start_hex}', end='{end_hex}'")
            start_key, end_key, error = gpu_core.generate_gpu_random_range(
                start_hex, end_hex,  # ← без .lstrip!
                self.main_window.gpu_min_range_edit.text().strip(),
                self.main_window.gpu_max_range_edit.text().strip(),
                self.main_window.used_ranges,
                self.main_window.max_saved_random
            )
            if error or start_key is None or end_key is None:
                self.main_window.append_log(f"Ошибка генерации случайного диапазона: {error}", "error")
                QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось сгенерировать диапазон: {error}")
                return

            self.update_gpu_range_label(start_key, end_key)
            self.start_gpu_search_with_range(start_key, end_key)

            interval = int(self.main_window.gpu_restart_interval_combo.currentText()) * 1000
            self.main_window.gpu_restart_timer.start(interval)
        else:
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

    def update_gpu_range_label(self, start_key, end_key):
        if isinstance(start_key, int) and isinstance(end_key, int):
            self.main_window.gpu_range_label.setText(
                f"Текущий диапазон: <span style='color:#f39c12'>{hex(start_key)}</span> - <span style='color:#f39c12'>{hex(end_key)}</span>")
        else:
            self.main_window.gpu_range_label.setText("Текущий диапазон: -")

    def start_gpu_search_with_range(self, start_key: int, end_key: int):
        target_address = self.main_window.gpu_target_edit.text().strip()
        use_compressed = self.main_window.gpu_use_compressed_checkbox.isChecked()

        # 🔹 Авто-отключение -c для несовместимых адресов
        if use_compressed and not target_address.startswith(('1', '3', 'bc1')):
            use_compressed = False
            self.main_window.append_log(
                "⚠️ Адрес не поддерживает сжатые ключи. Флаг -c отключён автоматически.",
                "warning"
            )

        # 🔹 Инициализация состояния
        self.gpu_start_range_key = start_key
        self.gpu_end_range_key = end_key
        self.gpu_total_keys_in_range = max(0, end_key - start_key + 1)
        self.gpu_keys_checked = 0

        # 🔹 Парсинг устройств GPU
        devices_input = self.main_window.gpu_device_combo.currentText()
        devices = [d.strip() for d in devices_input.split(',') if d.strip().isdigit()]
        if not devices:
            self.main_window.append_log("❌ Не указаны корректные ID GPU.", "error")
            return

        # 🔹 Параметры для cuBitcrack
        blocks = self.main_window.blocks_combo.currentText()
        threads = self.main_window.threads_combo.currentText()
        points = self.main_window.points_combo.currentText()
        priority_index = self.main_window.gpu_priority_combo.currentIndex()
        workers_per_device = self.main_window.gpu_workers_per_device_spin.value()

        # 🔹 Расчёт распределения диапазона
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

                # 🔹 Расчёт поддиапазона воркера
                worker_start = start_key + worker_index * keys_per_worker
                # Последний воркер берёт остаток (включая возможный "хвост")
                if worker_index == effective_workers - 1:
                    worker_end = end_key
                else:
                    worker_end = worker_start + keys_per_worker - 1
                    worker_end = min(worker_end, end_key)

                if worker_start > worker_end:
                    logger.debug(
                        f"Пропущен воркер {worker_index + 1}: некорректный диапазон {hex(worker_start)}-{hex(worker_end)}")
                    continue

                try:
                    # 🔹 ЗАПУСК ВОРКЕРА
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

                    # 🔹 Подключение сигналов
                    output_reader.log_message.connect(self.main_window.append_log)
                    output_reader.stats_update.connect(self.update_gpu_stats_display)
                    output_reader.found_key.connect(self.main_window.handle_found_key)
                    output_reader.process_finished.connect(self.handle_gpu_search_finished)
                    output_reader.start()

                    self.gpu_processes.append((cuda_process, output_reader))
                    success_count += 1

                    # ✅ ЛОГ ТОЛЬКО УСПЕШНО ЗАПУЩЕННОГО ВОРКЕРА
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
                        f"❌ Ошибка воркера {worker_index + 1} (GPU {device}): {str(e)}", "error"
                    )

        # ✅ ФИНАЛЬНЫЙ ЛОГ — ТОЛЬКО 1 РАЗ, ВНЕ ЦИКЛА
        if success_count > 0:
            self.gpu_is_running = True
            self.gpu_start_time = time.time()
            self.gpu_last_update_time = time.time()

            self.main_window.gpu_progress_bar.setValue(0)
            self.main_window.gpu_progress_bar.setFormat(
                f"Прогресс: 0% (0 / {self.gpu_total_keys_in_range:,})"
            )
            self.main_window.gpu_start_stop_btn.setText("Остановить GPU")
            self.main_window.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
            self.main_window.gpu_status_label.setText("Статус: Поиск запущен")

            mode_summary = " (сжатые ключи)" if use_compressed else ""
            self.main_window.append_log(
                f"🚀 Запущено {success_count} GPU воркеров{mode_summary}",
                "success"
            )
        else:
            self.main_window.append_log("❌ Не удалось запустить ни один GPU-воркер.", "error")

    def stop_gpu_search_internal(self):
        gpu_core.stop_gpu_search_internal(self.gpu_processes)
        self.gpu_is_running = False

    def stop_gpu_search(self):
        self.main_window.gpu_restart_timer.stop()
        self.stop_gpu_search_internal()
        self.gpu_search_finished()
        self.main_window.used_ranges.clear()
        self.update_gpu_range_label("-", "-")

    def handle_gpu_search_finished(self):
        all_finished = True
        for process, reader in self.gpu_processes:
            if process.poll() is None or reader.isRunning():
                all_finished = False
                break
        if all_finished:
            self.gpu_search_finished()

    def update_gpu_stats_display(self, stats):
        try:
            sender_reader = self.main_window.sender()
            if not hasattr(self, 'gpu_worker_stats'):
                self.gpu_worker_stats = {}
            self.gpu_worker_stats[sender_reader] = stats

            total_speed = 0.0
            total_checked = 0
            active_workers = []

            for process, reader in self.gpu_processes:
                if reader.isRunning() and process.poll() is None:
                    active_workers.append(reader)

            for reader in active_workers:
                if reader in self.gpu_worker_stats:
                    worker_stats = self.gpu_worker_stats[reader]
                    total_speed += worker_stats.get('speed', 0)
                    total_checked += worker_stats.get('checked', 0)

            self.gpu_keys_per_second = total_speed
            self.gpu_keys_checked = total_checked
            self.gpu_last_update_time = time.time()

            # 🔹 ЗАЩИТА: gpu_start_time может быть None
            progress_percent = 0.0
            if self.gpu_total_keys_in_range > 0:
                progress_percent = min(100.0, (self.gpu_keys_checked / self.gpu_total_keys_in_range) * 100)
                self.main_window.gpu_progress_bar.setValue(int(progress_percent))

                # 🔹 Безопасный расчёт elapsed
                elapsed = time.time() - self.gpu_start_time if self.gpu_start_time is not None else 0

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
            else:
                self.main_window.gpu_progress_bar.setFormat(f"Проверено: {self.gpu_keys_checked:,} ключей")

            self.main_window.gpu_speed_label.setText(f"Скорость: {self.gpu_keys_per_second:.2f} MKey/s")
            self.main_window.gpu_checked_label.setText(f"Проверено ключей: {self.gpu_keys_checked:,}")

        except Exception as e:
            logger.exception("Ошибка обновления статистики GPU")

    def update_gpu_time_display(self):
        """Обновление отображения времени работы GPU поиска"""
        if self.gpu_start_time is not None:
            elapsed = time.time() - self.gpu_start_time
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self.main_window.gpu_time_label.setText(f"Время работы: {h:02d}:{m:02d}:{s:02d}")

            # Обновление прогресс-бара (если в последовательном режиме)
            if (self.gpu_total_keys_in_range > 0
                    and self.gpu_keys_per_second > 0
                    and not self.main_window.gpu_random_checkbox.isChecked()):
                time_since_update = time.time() - self.gpu_last_update_time
                estimated_total = self.gpu_keys_checked + self.gpu_keys_per_second * time_since_update
                progress = min(100.0, (estimated_total / self.gpu_total_keys_in_range) * 100)

                self.main_window.gpu_progress_bar.setValue(int(progress))
                self.main_window.gpu_progress_bar.setFormat(
                    f"Прогресс: {progress:.1f}% ({int(estimated_total):,} / {self.gpu_total_keys_in_range:,})"
                )

            # Обновление статуса
            if self.main_window.gpu_random_checkbox.isChecked():
                self.main_window.gpu_status_label.setText("Статус: Случайный поиск")
            else:
                self.main_window.gpu_status_label.setText("Статус: Последовательный поиск")
        else:
            # Сброс при остановке
            self.main_window.gpu_time_label.setText("Время работы: 00:00:00")
            self.main_window.gpu_status_label.setText("Статус: Готов к работе")

    def gpu_search_finished(self):
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_processes = []
        self.gpu_worker_stats.clear()
        self.main_window.gpu_start_stop_btn.setText("Запустить GPU поиск")
        self.main_window.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.main_window.gpu_status_label.setText("Статус: Готов к работе")
        self.main_window.gpu_progress_bar.setValue(0)
        self.main_window.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.main_window.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.main_window.gpu_checked_label.setText("Проверено ключей: 0")
        self.main_window.append_log("GPU поиск завершен", "normal")