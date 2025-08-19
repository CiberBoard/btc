# core/gpu_logic.py
import os
import subprocess
import time

from PyQt5.QtWidgets import QMessageBox

import config
from PyQt5.QtCore import QTimer

from core.gpu_scanner import logger
from utils.helpers import validate_key_range
import core.gpu_scanner as gpu_core

class GPULogic:
    def __init__(self, main_window):
        self.main_window = main_window
        self.gpu_processes = []
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_keys_checked = 0
        self.gpu_keys_per_second = 0
        self.current_random_start = None
        self.current_random_end = None
        self.gpu_last_update_time = 0
        self.gpu_start_range_key = 0
        self.gpu_end_range_key = 0
        self.gpu_total_keys_in_range = 0
        # Для таймера перезапуска случайного режима
        self.main_window.gpu_restart_timer.timeout.connect(self.start_gpu_random_search)

    # ============ GPU METHODS ============
    def auto_optimize_gpu_parameters(self):
        """Автоматическая оптимизация параметров GPU"""
        try:
            # Попытка получить информацию о GPU
            gpu_info = ""
            try:
                gpu_info = subprocess.check_output(
                    [config.CUBITCRACK_EXE, "--list-devices"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    timeout=5
                )
            except:
                pass
            # Определение параметров на основе типа GPU
            if "RTX 30" in gpu_info or "RTX 40" in gpu_info:
                self.main_window.blocks_combo.setCurrentText("288")
                self.main_window.threads_combo.setCurrentText("128")
                self.main_window.points_combo.setCurrentText("512")
                self.main_window.append_log("Параметры GPU оптимизированы для RTX 30/40 серии", "success")
            elif "RTX 20" in gpu_info:
                self.main_window.blocks_combo.setCurrentText("256")
                self.main_window.threads_combo.setCurrentText("128")
                self.main_window.points_combo.setCurrentText("256")
                self.main_window.append_log("Параметры GPU оптимизированы для RTX 20 серии", "success")
            else:
                # Параметры по умолчанию
                self.main_window.blocks_combo.setCurrentText("128")
                self.main_window.threads_combo.setCurrentText("64")
                self.main_window.points_combo.setCurrentText("128")
                self.main_window.append_log("Параметры GPU установлены по умолчанию", "info")
        except Exception as e:
            self.main_window.append_log(f"Ошибка оптимизации GPU: {str(e)}", "error")
            # Установка безопасных значений по умолчанию
            self.main_window.blocks_combo.setCurrentText("128")
            self.main_window.threads_combo.setCurrentText("64")
            self.main_window.points_combo.setCurrentText("128")

    def validate_gpu_inputs(self):
        address = self.main_window.gpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self.main_window, "Ошибка", "Введите корректный BTC адрес для GPU")
            return False
        # Проверка диапазона ключей
        result, error = validate_key_range(
            self.main_window.gpu_start_key_edit.text().strip(),
            self.main_window.gpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self.main_window, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False
        # Проверка размеров диапазона
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

    def start_gpu_search(self):
        """Запускает GPU поиск"""
        if not self.validate_gpu_inputs():
            return
        self.main_window.save_settings()
        if self.main_window.gpu_random_checkbox.isChecked():
            self.stop_gpu_search_internal()
            # Вызов функции из модуля core для генерации случайного диапазона
            start_key, end_key, error = gpu_core.generate_gpu_random_range(
                self.main_window.gpu_start_key_edit.text().strip(),  # global_start_hex
                self.main_window.gpu_end_key_edit.text().strip(),  # global_end_hex
                self.main_window.gpu_min_range_edit.text().strip(),  # min_range_size_str
                self.main_window.gpu_max_range_edit.text().strip(),  # max_range_size_str
                self.main_window.used_ranges,  # used_ranges (set)
                self.main_window.max_saved_random  # max_saved_random (int)
            )
            # Обработка ошибки
            if error:
                self.main_window.append_log(f"Ошибка генерации случайного диапазона: {error}", "error")
                QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось сгенерировать диапазон: {error}")
                return  # Прерываем запуск поиска
            if start_key is None or end_key is None:
                self.main_window.append_log("Не удалось сгенерировать случайный диапазон.", "error")
                QMessageBox.warning(self.main_window, "Ошибка", "Не удалось сгенерировать случайный диапазон.")
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

    def restart_gpu_random_search(self):
        """Перезапускает GPU поиск с новым случайным диапазоном"""
        if self.gpu_is_running:
            self.stop_gpu_search_internal()
        self.main_window.append_log("Перезапуск GPU поиска с новым случайным диапазоном...", "normal")
        QTimer.singleShot(1000, self.start_gpu_random_search)

    def start_gpu_random_search(self):
        """Запускает GPU поиск со случайным диапазоном"""
        if self.gpu_is_running:
            return
        # Вызов функции из модуля core для генерации случайного диапазона
        start_key, end_key, error = gpu_core.generate_gpu_random_range(
            self.main_window.gpu_start_key_edit.text().strip(),  # global_start_hex
            self.main_window.gpu_end_key_edit.text().strip(),  # global_end_hex
            self.main_window.gpu_min_range_edit.text().strip(),  # min_range_size_str
            self.main_window.gpu_max_range_edit.text().strip(),  # max_range_size_str
            self.main_window.used_ranges,  # used_ranges (set)
            self.main_window.max_saved_random  # max_saved_random (int)
        )
        # Обработка ошибки
        if error:
            self.main_window.append_log(f"Ошибка генерации случайного диапазона при перезапуске: {error}", "error")
            self.main_window.gpu_restart_timer.stop()  # Останавливаем таймер, чтобы не было бесконечных попыток
            QMessageBox.warning(self.main_window, "Ошибка", f"Не удалось сгенерировать диапазон при перезапуске: {error}")
            return
        if start_key is None or end_key is None:
            self.main_window.append_log("Не удалось сгенерировать случайный диапазон при перезапуске.", "error")
            self.main_window.gpu_restart_timer.stop()
            QMessageBox.warning(self.main_window, "Ошибка", "Не удалось сгенерировать случайный диапазон при перезапуске.")
            return
        self.update_gpu_range_label(start_key, end_key)
        self.main_window.append_log(f"Новый случайный диапазон GPU: {hex(start_key)} - {hex(end_key)}", "normal")
        self.start_gpu_search_with_range(start_key, end_key)

    def update_gpu_range_label(self, start_key, end_key):
        self.main_window.gpu_range_label.setText(
            f"Текущий диапазон: <span style='color:#f39c12'>{hex(start_key)}</span> - <span style='color:#f39c12'>{hex(end_key)}</span>")

    def start_gpu_search_with_range(self, start_key, end_key):
        """Запускает GPU поиск с указанным диапазоном"""
        target_address = self.main_window.gpu_target_edit.text().strip()
        # Сохраняем оригинальный диапазон для расчета прогресса
        self.gpu_start_range_key = start_key
        self.gpu_end_range_key = end_key
        self.gpu_total_keys_in_range = end_key - start_key + 1
        self.gpu_keys_checked = 0  # Сброс счетчика
        # Получаем выбранные устройства GPU
        devices = self.main_window.gpu_device_combo.currentText().split(',')
        if not devices:
            devices = ['0']
        # Получаем параметры
        blocks = self.main_window.blocks_combo.currentText()
        threads = self.main_window.threads_combo.currentText()
        points = self.main_window.points_combo.currentText()
        priority_index = self.main_window.gpu_priority_combo.currentIndex()
        # --- НОВОЕ ---
        # Получаем количество воркеров на устройство
        workers_per_device = self.main_window.gpu_workers_per_device_spin.value()
        total_requested_workers = len(devices) * workers_per_device
        if total_requested_workers <= 0:
            self.main_window.append_log("Количество воркеров должно быть больше 0.", "error")
            return
        # Рассчитываем размер поддиапазона для каждого воркера
        total_keys = self.gpu_total_keys_in_range
        keys_per_worker = max(1, total_keys // total_requested_workers)  # Убедимся, что минимум 1 ключ на воркера
        # Если ключей меньше, чем воркеров, уменьшаем количество воркеров
        if total_keys < total_requested_workers:
            # Пересчитываем workers_per_device, чтобы общее количество воркеров не превышало total_keys
            # Простой способ: используем максимум total_keys воркеров, распределяя их по устройствам
            total_requested_workers = total_keys
            # Распределяем total_keys воркеров по len(devices) устройствам
            # Это простая логика, можно сделать более сложную
            self.main_window.append_log(
                f"Диапазон ключей ({total_keys}) меньше количества запрошенных воркеров ({len(devices)}*{workers_per_device}={total_requested_workers}). Будет запущено {total_keys} воркеров.",
                "warning")
            # Для простоты, можно просто запускать по одному воркеру на ключ, если ключей < воркеров
            # Или уменьшить workers_per_device. Реализуем более простой вариант:
            # Запускаем максимум total_keys воркеров, распределяя их по устройствам.
            # workers_per_device = max(1, total_keys // len(devices))
            # total_requested_workers = len(devices) * workers_per_device
            # Но это всё равно может быть не оптимально. Проще - запустить total_keys воркеров.
            # Но это требует переписывания логики. Оставим предупреждение и будем запускать по одному ключу на воркер если нужно.
            # Или просто запускаем total_requested_workers = total_keys и далее работаем.
            # Лучше: скорректировать общее количество воркеров.
            # Пока что просто используем keys_per_worker = 1 если total_keys < total_requested_workers.
            # И запускаем total_keys воркеров.
            if total_keys < total_requested_workers:
                total_requested_workers = total_keys
                keys_per_worker = 1
        # --- КОНЕЦ НОВОГО ---
        # Запускаем процессы для каждого устройства И для каждого воркера
        success_count = 0
        worker_index_global = 0  # Глобальный индекс для отслеживания поддиапазонов
        for device in devices:
            device = device.strip()
            if not device.isdigit():
                self.main_window.append_log(f"Некорректный ID устройства: {device}", "error")
                continue
            # --- ИЗМЕНЕНИЕ ---
            # Вложенный цикл для запуска нескольких воркеров на одно устройство
            for worker_local_index in range(workers_per_device):
                # Рассчитываем уникальный поддиапазон для этого воркера
                # worker_index_global отслеживает, какой по счету это воркер среди всех
                worker_start_key = start_key + (worker_index_global * keys_per_worker)
                # Для последнего воркера убедимся, что конец диапазона правильный
                if worker_index_global == total_requested_workers - 1:
                    worker_end_key = end_key
                else:
                    worker_end_key = worker_start_key + keys_per_worker - 1
                    # Убедимся, что не вышли за пределы оригинального диапазона (на всякий случай)
                    worker_end_key = min(worker_end_key, end_key)
                # Проверка корректности поддиапазона
                if worker_start_key > worker_end_key:
                    # Это может произойти, если keys_per_worker = 0 или диапазон слишком мал
                    self.main_window.append_log(
                        f"Пропущен воркер {worker_index_global + 1} на устройстве {device}: некорректный поддиапазон {hex(worker_start_key)}-{hex(worker_end_key)}",
                        "warning")
                    worker_index_global += 1
                    continue  # Пропускаем этот воркер
                try:
                    # Передаем УНИКАЛЬНЫЙ поддиапазон каждому воркеру
                    cuda_process, output_reader = gpu_core.start_gpu_search_with_range(
                        target_address, worker_start_key, worker_end_key, device, blocks, threads, points,
                        priority_index, self.main_window
                    )
                    # Подключаем сигналы
                    output_reader.log_message.connect(self.main_window.append_log)
                    output_reader.stats_update.connect(self.update_gpu_stats_display)  # Требует модификации (см. ниже)
                    output_reader.found_key.connect(self.main_window.handle_found_key)
                    output_reader.process_finished.connect(self.handle_gpu_search_finished)
                    output_reader.start()
                    self.gpu_processes.append((cuda_process, output_reader))
                    success_count += 1
                    from core.cpu_scanner import logger
                    logger.info(
                        f"Запущен GPU воркер {worker_local_index + 1}/{workers_per_device} (глобальный {worker_index_global + 1}/{total_requested_workers}) на устройстве {device}. Диапазон: {hex(worker_start_key)} - {hex(worker_end_key)}")
                    self.main_window.append_log(
                        f"Запущен воркер {worker_index_global + 1} на GPU {device}. Диапазон: {hex(worker_start_key)} - {hex(worker_end_key)}",
                        "normal")
                except Exception as e:
                    logger.exception(
                        f"Ошибка запуска cuBitcrack воркера {worker_local_index + 1} (глобальный {worker_index_global + 1}) на устройстве {device}")
                    self.main_window.append_log(
                        f"Ошибка запуска cuBitcrack воркера {worker_index_global + 1} на устройстве {device}: {str(e)}",
                        "error")
                worker_index_global += 1
                # Если мы уже запустили достаточно воркеров (например, если ключей было меньше), выходим
                if worker_index_global >= total_requested_workers:
                    break
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            # Если мы уже запустили достаточно воркеров, выходим из внешнего цикла тоже
            if worker_index_global >= total_requested_workers:
                break
        if success_count > 0:
            if not self.gpu_is_running:
                self.gpu_is_running = True
                self.gpu_start_time = time.time()
                # Эти значения теперь должны агрегироваться из всех воркеров
                self.gpu_keys_checked = 0
                self.gpu_keys_per_second = 0
                self.gpu_last_update_time = time.time()
                # Сбросим прогресс бар
                self.main_window.gpu_progress_bar.setValue(0)
                # Прогресс теперь рассчитывается на основе агрегированных данных
                self.main_window.gpu_progress_bar.setFormat(f"Прогресс: 0% (0 / {self.gpu_total_keys_in_range:,})")
                self.main_window.gpu_start_stop_btn.setText("Остановить GPU")
                self.main_window.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
            self.main_window.append_log(f"Успешно запущено {success_count} GPU воркеров", "success")
        else:
            self.main_window.append_log("Не удалось запустить ни один GPU процесс", "error")
            # self.gpu_search_finished() # Не вызываем, так как ничего не запустилось

    def stop_gpu_search_internal(self):
        """Внутренняя остановка GPU поиска"""
        gpu_core.stop_gpu_search_internal(self.gpu_processes)
        self.gpu_is_running = False

    def stop_gpu_search(self):
        """Полная остановка GPU поиска"""
        self.main_window.gpu_restart_timer.stop()
        self.stop_gpu_search_internal()
        self.gpu_search_finished()
        self.main_window.used_ranges.clear()  # Очищаем историю диапазонов
        self.update_gpu_range_label("-", "-")

    def handle_gpu_search_finished(self):
        """Обработчик завершения GPU поиска"""
        # Проверяем, все ли процессы завершились
        all_finished = True
        for process, reader in self.gpu_processes:
            # Проверяем, завершен ли процесс ОС *и* завершен ли поток чтения
            if process.poll() is None or reader.isRunning():
                all_finished = False
                break
        if all_finished:
            self.gpu_search_finished()
        # Если используется случайный режим с перезапуском, логика должна быть в start_gpu_random_search
        # и обработчике таймера.
        # if self.main_window.gpu_random_checkbox.isChecked() and self.main_window.gpu_restart_timer.isActive():
        #     self.stop_gpu_search_internal()
        #     QTimer.singleShot(1000, self.start_gpu_random_search)

    def update_gpu_stats_display(self, stats):
        """Обновляет отображение статистики GPU. Агрегирует данные от всех воркеров."""
        try:
            # stats приходит от одного воркера. Нужно агрегировать данные от всех.
            # Для этого можно использовать словарь или другой способ хранения последних данных от каждого процесса.
            # Предположим, что sender() возвращает объект OptimizedOutputReader, который отправил сигнал.
            # Мы можем использовать его как ключ для хранения последних stats.
            # Получаем отправителя сигнала
            sender_reader = self.main_window.sender()
            # Сохраняем последние статистики от каждого воркера (если еще не создан)
            if not hasattr(self, 'gpu_worker_stats'):
                self.gpu_worker_stats = {}  # {reader_object: stats_dict}
            # Обновляем статистику для этого воркера
            self.gpu_worker_stats[sender_reader] = stats
            # Агрегируем данные от всех активных воркеров
            total_speed = 0.0
            total_checked = 0
            # Мы должны учитывать только активные (не завершенные) воркеры
            # Можно проверять reader.isRunning() или process.poll() == None
            active_workers = []
            for process, reader in self.gpu_processes:
                if reader.isRunning() and process.poll() is None:  # Проверяем, активен ли процесс и поток
                    active_workers.append(reader)
            for reader in active_workers:
                if reader in self.gpu_worker_stats:
                    worker_stats = self.gpu_worker_stats[reader]
                    total_speed += worker_stats.get('speed', 0)
                    total_checked = max(total_checked, worker_stats.get('checked',
                                                                        0))  # Используем max, если ключи не пересекаются. Но т.к. диапазоны уникальны, скорее всего нужно суммировать.
                    # ИЛИ, если диапазоны уникальны и каждый воркер отслеживает свой счетчик в пределах своего диапазона:
                    # total_checked += worker_stats.get('checked', 0)
                    # Но cuBitcrack, вероятно, показывает абсолютное количество проверенных в диапазоне.
                    # Поэтому max может быть не совсем корректным.
                    # Лучше: сохранять оригинальный стартовый ключ для каждого воркера и добавлять к нему checked.
                    # Или, проще, суммировать checked, предполагая, что каждый воркер сообщает о количестве проверенных *в своём диапазоне*.
                    # Это кажется наиболее правдоподобным.
                    total_checked += worker_stats.get('checked', 0)
            # Обновляем общее количество проверенных ключей и скорость
            # self.gpu_keys_checked = total_checked # Уже обновлено выше
            # self.gpu_keys_per_second = total_speed * 1000000 # Это было для одного воркера. Теперь total_speed уже в MKey/s
            self.gpu_keys_per_second = total_speed  # total_speed уже сумма MKey/s от всех воркеров
            self.gpu_keys_checked = total_checked
            self.gpu_last_update_time = time.time()  # Запоминаем время последнего обновления
            # Расчет прогресса
            if self.gpu_total_keys_in_range > 0:
                # Убедимся, что прогресс не превышает 100%
                progress_percent = min(100.0, (self.gpu_keys_checked / self.gpu_total_keys_in_range) * 100)
                self.main_window.gpu_progress_bar.setValue(int(progress_percent))
                # Форматирование текста прогресса
                if self.main_window.gpu_random_checkbox.isChecked():
                    elapsed = time.time() - self.gpu_start_time
                    self.main_window.gpu_progress_bar.setFormat(
                        f"Оценочный прогресс: {progress_percent:.2f}% ({int(elapsed // 60):02d}:{int(elapsed % 60):02d})"
                    )
                else:
                    self.main_window.gpu_progress_bar.setFormat(
                        f"Прогресс: {progress_percent:.2f}% ({self.gpu_keys_checked:,} / {self.gpu_total_keys_in_range:,})"
                    )
            else:
                self.main_window.gpu_progress_bar.setFormat(f"Проверено: {self.gpu_keys_checked:,} ключей")
            # Обновляем UI
            # Отображаем суммарную скорость
            self.main_window.gpu_speed_label.setText(
                f"Скорость: {self.gpu_keys_per_second:.2f} MKey/s")  # Используем агрегированную скорость
            self.main_window.gpu_checked_label.setText(f"Проверено ключей: {self.gpu_keys_checked:,}")
            # Логирование для отладки (можно убрать или сделать менее частым)
            # logger.debug(f"GPU Update Aggregate: Speed={self.gpu_keys_per_second:.2f} MKey/s, Checked={self.gpu_keys_checked:,}, Progress={progress_percent:.2f}%")
        except Exception as e:
            logger.exception("Ошибка обновления статистики GPU")

    def update_gpu_time_display(self):
        """Обновляет отображение времени работы GPU"""
        if self.gpu_start_time:
            elapsed = time.time() - self.gpu_start_time
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.main_window.gpu_time_label.setText(f"Время работы: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
            # Принудительное обновление прогресса между обновлениями статистики
            if self.gpu_total_keys_in_range > 0 and self.gpu_keys_per_second > 0:
                time_since_last_update = time.time() - self.gpu_last_update_time
                additional_keys = self.gpu_keys_per_second * time_since_last_update
                total_checked = self.gpu_keys_checked + additional_keys
                progress_percent = min(100, (total_checked / self.gpu_total_keys_in_range) * 100)
                self.main_window.gpu_progress_bar.setValue(int(progress_percent))
                if self.main_window.gpu_random_checkbox.isChecked():
                    self.main_window.gpu_progress_bar.setFormat(
                        f"Оценочный прогресс: {progress_percent:.1f}% ({int(total_checked):,} ключей)"
                    )
                else:
                    self.main_window.gpu_progress_bar.setFormat(
                        f"Прогресс: {progress_percent:.1f}% ({int(total_checked):,} / {self.gpu_total_keys_in_range:,})"
                    )
            if self.main_window.gpu_random_checkbox.isChecked():
                self.main_window.gpu_status_label.setText("Статус: Случайный поиск")
            else:
                self.main_window.gpu_status_label.setText("Статус: Последовательный поиск")
        else:
            self.main_window.gpu_time_label.setText("Время работы: 00:00:00")

    def gpu_search_finished(self):
        """Завершение работы GPU поиска"""
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_processes = []
        self.main_window.gpu_start_stop_btn.setText("Запустить GPU поиск")
        self.main_window.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.main_window.gpu_status_label.setText("Статус: Завершено")
        # Сброс прогресс бара (исправлено)
        self.main_window.gpu_progress_bar.setValue(0)
        self.main_window.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.main_window.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.main_window.gpu_checked_label.setText("Проверено ключей: 0")
        self.main_window.gpu_found_label.setText("Найдено ключей: 0")
        self.main_window.append_log("GPU поиск завершен", "normal")
