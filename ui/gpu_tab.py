import os
import time
import math
import json
import subprocess
import platform
import multiprocessing
from PyQt5.QtCore import Qt, QTimer, QRegExp
from PyQt5.QtGui import QFont, QColor, QPalette, QRegExpValidator
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QGroupBox, QComboBox, QProgressBar,
                             QCheckBox, QSpinBox, QMessageBox)

import core.gpu_scanner as gpu_core
import config
from utils.helpers import setup_logger

logger = setup_logger()

class GPUTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.gpu_processes = []
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_keys_checked = 0
        self.gpu_keys_per_second = 0
        self.random_mode = False
        self.last_random_ranges = set()
        self.max_saved_random = 100
        self.current_random_start = None
        self.current_random_end = None
        self.used_ranges = set()
        self.gpu_last_update_time = 0
        self.gpu_start_range_key = 0
        self.gpu_end_range_key = 0
        self.gpu_total_keys_in_range = 0
        
        self.setup_ui()
        self.setup_connections()
        
        # GPU Status Timer
        self.gpu_status_timer = QTimer()
        self.gpu_status_timer.timeout.connect(self.update_gpu_status)
        self.gpu_status_timer.start(1500)
        
        # GPU Stats Timer
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.update_gpu_time_display)
        self.gpu_stats_timer.start(500)
        
        # GPU Restart Timer
        self.gpu_restart_timer = QTimer()
        self.gpu_restart_timer.timeout.connect(self.restart_gpu_random_search)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # GPU адрес и диапазон
        gpu_addr_group = QGroupBox("GPU: Целевой адрес и диапазон ключей")
        gpu_addr_layout = QGridLayout(gpu_addr_group)
        gpu_addr_layout.setSpacing(8)
        gpu_addr_layout.addWidget(QLabel("BTC адрес:"), 0, 0)
        self.gpu_target_edit = QLineEdit()
        self.gpu_target_edit.setPlaceholderText("Введите Bitcoin адрес (1... или 3...)")
        gpu_addr_layout.addWidget(self.gpu_target_edit, 0, 1, 1, 3)
        gpu_addr_layout.addWidget(QLabel("Начальный ключ (hex):"), 1, 0)
        self.gpu_start_key_edit = QLineEdit("1")
        self.gpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
        gpu_addr_layout.addWidget(self.gpu_start_key_edit, 1, 1)
        gpu_addr_layout.addWidget(QLabel("Конечный ключ (hex):"), 1, 2)
        self.gpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.gpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
        gpu_addr_layout.addWidget(self.gpu_end_key_edit, 1, 3)
        layout.addWidget(gpu_addr_group)
        
        # GPU параметры
        gpu_param_group = QGroupBox("GPU: Параметры и random режим")
        gpu_param_layout = QGridLayout(gpu_param_group)
        gpu_param_layout.setSpacing(8)
        gpu_param_layout.addWidget(QLabel("GPU устройство:"), 0, 0)
        self.gpu_device_combo = QComboBox()
        self.gpu_device_combo.addItems([str(x) for x in range(8)])
        gpu_param_layout.addWidget(self.gpu_device_combo, 0, 1)
        gpu_param_layout.addWidget(QLabel("Блоки:"), 0, 2)
        self.blocks_combo = self.make_combo32(32, 2048, 256)
        gpu_param_layout.addWidget(self.blocks_combo, 0, 3)
        gpu_param_layout.addWidget(QLabel("Потоки/блок:"), 1, 0)
        self.threads_combo = self.make_combo32(32, 1024, 256)
        gpu_param_layout.addWidget(self.threads_combo, 1, 1)
        gpu_param_layout.addWidget(QLabel("Точки:"), 1, 2)
        self.points_combo = self.make_combo32(32, 1024, 256)
        gpu_param_layout.addWidget(self.points_combo, 1, 3)
        
        self.gpu_random_checkbox = QCheckBox("Случайный поиск в диапазоне")
        gpu_param_layout.addWidget(self.gpu_random_checkbox, 2, 0, 1, 2)
        gpu_param_layout.addWidget(QLabel("Интервал рестарта (сек):"), 2, 2)
        self.gpu_restart_interval_combo = QComboBox()
        self.gpu_restart_interval_combo.addItems([str(x) for x in range(10, 3601, 10)])
        self.gpu_restart_interval_combo.setCurrentText("300")
        self.gpu_restart_interval_combo.setEnabled(False)
        gpu_param_layout.addWidget(self.gpu_restart_interval_combo, 2, 3)
        self.gpu_random_checkbox.toggled.connect(self.gpu_restart_interval_combo.setEnabled)
        
        gpu_param_layout.addWidget(QLabel("Мин. размер диапазона:"), 3, 0)
        self.gpu_min_range_edit = QLineEdit("134217728")
        self.gpu_min_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
        gpu_param_layout.addWidget(self.gpu_min_range_edit, 3, 1)
        gpu_param_layout.addWidget(QLabel("Макс. размер диапазона:"), 3, 2)
        self.gpu_max_range_edit = QLineEdit("536870912")
        self.gpu_max_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
        gpu_param_layout.addWidget(self.gpu_max_range_edit, 3, 3)
        
        # Приоритет GPU
        gpu_param_layout.addWidget(QLabel("Приоритет GPU:"), 4, 0)
        self.gpu_priority_combo = QComboBox()
        self.gpu_priority_combo.addItems(["Нормальный", "Высокий", "Реального времени"])
        gpu_param_layout.addWidget(self.gpu_priority_combo, 4, 1)
        
        # Воркеры на устройство
        gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0)
        self.gpu_workers_per_device_spin = QSpinBox()
        self.gpu_workers_per_device_spin.setRange(1, 16)
        self.gpu_workers_per_device_spin.setValue(1)
        gpu_param_layout.addWidget(self.gpu_workers_per_device_spin, 5, 1)
        
        layout.addWidget(gpu_param_group)
        
        # GPU кнопки
        gpu_button_layout = QHBoxLayout()
        self.gpu_start_stop_btn = QPushButton("Запустить GPU поиск")
        self.gpu_start_stop_btn.setStyleSheet("""
            QPushButton { background: #27ae60; font-weight: bold; font-size: 12pt;}
            QPushButton:hover {background: #2ecc71;}
            QPushButton:pressed {background: #219653;}
        """)
        self.gpu_optimize_btn = QPushButton("Авто-оптимизация")
        gpu_button_layout.addWidget(self.gpu_start_stop_btn)
        gpu_button_layout.addWidget(self.gpu_optimize_btn)
        gpu_button_layout.addStretch()
        layout.addLayout(gpu_button_layout)
        
        # GPU прогресс
        gpu_progress_group = QGroupBox("GPU: Прогресс и статистика")
        gpu_progress_layout = QGridLayout(gpu_progress_group)
        
        self.gpu_status_label = QLabel("Статус: Готов к работе")
        self.gpu_status_label.setStyleSheet("font-weight: bold; color: #3498db;")
        gpu_progress_layout.addWidget(self.gpu_status_label, 0, 0, 1, 2)
        
        self.gpu_speed_label = QLabel("Скорость: 0 MKey/s")
        gpu_progress_layout.addWidget(self.gpu_speed_label, 1, 0)
        
        self.gpu_time_label = QLabel("Время работы: 00:00:00")
        gpu_progress_layout.addWidget(self.gpu_time_label, 1, 1)
        
        self.gpu_checked_label = QLabel("Проверено ключей: 0")
        gpu_progress_layout.addWidget(self.gpu_checked_label, 2, 0)
        
        self.gpu_found_label = QLabel("Найдено ключей: 0")
        self.gpu_found_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        gpu_progress_layout.addWidget(self.gpu_found_label, 2, 1)
        
        self.gpu_progress_bar = QProgressBar()
        self.gpu_progress_bar.setRange(0, 100)
        self.gpu_progress_bar.setValue(0)
        self.gpu_progress_bar.setFormat("Прогресс: неизвестен")
        self.gpu_progress_bar.setStyleSheet("""
            QProgressBar {height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20;}
            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px;}
        """)
        gpu_progress_layout.addWidget(self.gpu_progress_bar, 3, 0, 1, 2)
        
        layout.addWidget(gpu_progress_group)
        
        self.gpu_range_label = QLabel("Текущий диапазон: -")
        self.gpu_range_label.setStyleSheet("font-weight: bold; color: #e67e22;")
        layout.addWidget(self.gpu_range_label)
        
        # GPU Hardware Status
        self.gpu_hw_status_group = QGroupBox("GPU: Аппаратный статус")
        gpu_hw_status_layout = QGridLayout(self.gpu_hw_status_group)
        gpu_hw_status_layout.setSpacing(6)
        
        self.gpu_util_label = QLabel("Загрузка GPU: - %")
        self.gpu_util_label.setStyleSheet("color: #f1c40f;")
        gpu_hw_status_layout.addWidget(self.gpu_util_label, 0, 0)
        
        self.gpu_mem_label = QLabel("Память GPU: - / - MB")
        self.gpu_mem_label.setStyleSheet("color: #9b59b6;")
        gpu_hw_status_layout.addWidget(self.gpu_mem_label, 0, 1)
        
        self.gpu_temp_label = QLabel("Температура: - °C")
        self.gpu_temp_label.setStyleSheet("color: #e74c3c;")
        gpu_hw_status_layout.addWidget(self.gpu_temp_label, 1, 0)
        
        self.gpu_util_bar = QProgressBar()
        self.gpu_util_bar.setRange(0, 100)
        self.gpu_util_bar.setValue(0)
        self.gpu_util_bar.setFormat("Загрузка: %p%")
        self.gpu_util_bar.setStyleSheet("""
            QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f1c40f, stop:1 #f39c12);}
        """)
        gpu_hw_status_layout.addWidget(self.gpu_util_bar, 2, 0)
        
        self.gpu_mem_bar = QProgressBar()
        self.gpu_mem_bar.setRange(0, 100)
        self.gpu_mem_bar.setValue(0)
        self.gpu_mem_bar.setFormat("Память: %p%")
        self.gpu_mem_bar.setStyleSheet("""
            QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #8e44ad);}
        """)
        gpu_hw_status_layout.addWidget(self.gpu_mem_bar, 2, 1)
        
        layout.addWidget(self.gpu_hw_status_group)

    def make_combo32(self, min_val, max_val, step):
        combo = QComboBox()
        vals = [str(2**i) for i in range(int(math.log2(min_val)), int(math.log2(max_val)) + 1)]
        combo.addItems(vals)
        combo.setCurrentText(str(step))
        return combo

    def setup_connections(self):
        self.gpu_start_stop_btn.clicked.connect(self.toggle_gpu_search)
        self.gpu_optimize_btn.clicked.connect(self.auto_optimize_gpu_parameters)

    def auto_optimize_gpu_parameters(self):
        try:
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
            
            if "RTX 30" in gpu_info or "RTX 40" in gpu_info:
                self.blocks_combo.setCurrentText("288")
                self.threads_combo.setCurrentText("128")
                self.points_combo.setCurrentText("512")
                self.parent.append_log("Параметры GPU оптимизированы для RTX 30/40 серии", "success")
            elif "RTX 20" in gpu_info:
                self.blocks_combo.setCurrentText("256")
                self.threads_combo.setCurrentText("128")
                self.points_combo.setCurrentText("256")
                self.parent.append_log("Параметры GPU оптимизированы для RTX 20 серии", "success")
            else:
                self.blocks_combo.setCurrentText("128")
                self.threads_combo.setCurrentText("64")
                self.points_combo.setCurrentText("128")
                self.parent.append_log("Параметры GPU установлены по умолчанию", "info")
        except Exception as e:
            self.parent.append_log(f"Ошибка оптимизации GPU: {str(e)}", "error")
            self.blocks_combo.setCurrentText("128")
            self.threads_combo.setCurrentText("64")
            self.points_combo.setCurrentText("128")

    def validate_gpu_inputs(self):
        address = self.gpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self, "Ошибка", "Введите корректный BTC адрес для GPU")
            return False
        
        result, error = validate_key_range(
            self.gpu_start_key_edit.text().strip(),
            self.gpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False
        
        try:
            min_range = int(self.gpu_min_range_edit.text().strip())
            max_range = int(self.gpu_max_range_edit.text().strip())
            if min_range <= 0 or max_range <= 0:
                QMessageBox.warning(self, "Ошибка", "Размеры диапазона должны быть положительными числами")
                return False
            if min_range > max_range:
                QMessageBox.warning(self, "Ошибка", "Минимальный размер диапазона должен быть <= максимальному")
                return False
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Минимальный и максимальный диапазон должны быть числами")
            return False
        
        if not os.path.exists(config.CUBITCRACK_EXE):
            QMessageBox.warning(self, "Ошибка", f"Файл cuBitcrack.exe не найден в {config.BASE_DIR}")
            return False
        
        return True

    def toggle_gpu_search(self):
        if not self.gpu_is_running:
            self.start_gpu_search()
        else:
            self.stop_gpu_search()

    def start_gpu_search(self):
        if not self.validate_gpu_inputs():
            return
        
        if self.gpu_random_checkbox.isChecked():
            self.stop_gpu_search_internal()
            start_key, end_key, error = gpu_core.generate_gpu_random_range(
                self.gpu_start_key_edit.text().strip(),
                self.gpu_end_key_edit.text().strip(),
                self.gpu_min_range_edit.text().strip(),
                self.gpu_max_range_edit.text().strip(),
                self.used_ranges,
                self.max_saved_random
            )
            
            if error:
                self.parent.append_log(f"Ошибка генерации случайного диапазона: {error}", "error")
                QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать диапазон: {error}")
                return
            
            if start_key is None or end_key is None:
                self.parent.append_log("Не удалось сгенерировать случайный диапазон.", "error")
                QMessageBox.warning(self, "Ошибка", "Не удалось сгенерировать случайный диапазон.")
                return
            
            self.update_gpu_range_label(start_key, end_key)
            self.start_gpu_search_with_range(start_key, end_key)
            interval = int(self.gpu_restart_interval_combo.currentText()) * 1000
            self.gpu_restart_timer.start(interval)
        else:
            self.stop_gpu_search_internal()
            result, _ = validate_key_range(
                self.gpu_start_key_edit.text().strip(),
                self.gpu_end_key_edit.text().strip()
            )
            if result is None:
                return
            start_key, end_key, _ = result
            self.update_gpu_range_label(start_key, end_key)
            self.start_gpu_search_with_range(start_key, end_key)

    def start_gpu_search_with_range(self, start_key, end_key):
        target_address = self.gpu_target_edit.text().strip()
        self.gpu_start_range_key = start_key
        self.gpu_end_range_key = end_key
        self.gpu_total_keys_in_range = end_key - start_key + 1
        self.gpu_keys_checked = 0
        
        devices = self.gpu_device_combo.currentText().split(',')
        if not devices:
            devices = ['0']
        
        blocks = self.blocks_combo.currentText()
        threads = self.threads_combo.currentText()
        points = self.points_combo.currentText()
        priority_index = self.gpu_priority_combo.currentIndex()
        workers_per_device = self.gpu_workers_per_device_spin.value()
        total_requested_workers = len(devices) * workers_per_device
        
        if total_requested_workers <= 0:
            self.parent.append_log("Количество воркеров должно быть больше 0.", "error")
            return
        
        total_keys = self.gpu_total_keys_in_range
        keys_per_worker = max(1, total_keys // total_requested_workers)
        
        if total_keys < total_requested_workers:
            total_requested_workers = total_keys
            keys_per_worker = 1
        
        success_count = 0
        worker_index_global = 0
        
        for device in devices:
            device = device.strip()
            if not device.isdigit():
                self.parent.append_log(f"Некорректный ID устройства: {device}", "error")
                continue
            
            for worker_local_index in range(workers_per_device):
                if worker_index_global >= total_requested_workers:
                    break
                
                worker_start_key = start_key + (worker_index_global * keys_per_worker)
                
                if worker_index_global == total_requested_workers - 1:
                    worker_end_key = end_key
                else:
                    worker_end_key = worker_start_key + keys_per_worker - 1
                    worker_end_key = min(worker_end_key, end_key)
                
                if worker_start_key > worker_end_key:
                    self.parent.append_log(
                        f"Пропущен воркер {worker_index_global + 1} на устройстве {device}: некорректный поддиапазон",
                        "warning")
                    worker_index_global += 1
                    continue
                
                try:
                    cuda_process, output_reader = gpu_core.start_gpu_search_with_range(
                        target_address, worker_start_key, worker_end_key, device, blocks, 
                        threads, points, priority_index, self
                    )
                    
                    output_reader.log_message.connect(self.parent.append_log)
                    output_reader.stats_update.connect(self.update_gpu_stats_display)
                    output_reader.found_key.connect(self.parent.handle_found_key)
                    output_reader.process_finished.connect(self.handle_gpu_search_finished)
                    
                    output_reader.start()
                    self.gpu_processes.append((cuda_process, output_reader))
                    success_count += 1
                    
                    self.parent.append_log(
                        f"Запущен воркер {worker_index_global + 1} на GPU {device}. Диапазон: {hex(worker_start_key)} - {hex(worker_end_key)}",
                        "normal")
                except Exception as e:
                    logger.exception(
                        f"Ошибка запуска cuBitcrack воркера {worker_index_global + 1} на устройстве {device}")
                    self.parent.append_log(
                        f"Ошибка запуска cuBitcrack воркера {worker_index_global + 1} на устройстве {device}: {str(e)}",
                        "error")
                
                worker_index_global += 1
            
            if worker_index_global >= total_requested_workers:
                break
        
        if success_count > 0:
            if not self.gpu_is_running:
                self.gpu_is_running = True
                self.gpu_start_time = time.time()
                self.gpu_keys_checked = 0
                self.gpu_keys_per_second = 0
                self.gpu_last_update_time = time.time()
                self.gpu_progress_bar.setValue(0)
                self.gpu_progress_bar.setFormat(f"Прогресс: 0% (0 / {self.gpu_total_keys_in_range:,})")
                self.gpu_start_stop_btn.setText("Остановить GPU")
                self.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
            
            self.parent.append_log(f"Успешно запущено {success_count} GPU воркеров", "success")
        else:
            self.parent.append_log("Не удалось запустить ни один GPU процесс", "error")

    def update_gpu_range_label(self, start_key, end_key):
        self.gpu_range_label.setText(
            f"Текущий диапазон: <span style='color:#f39c12'>{hex(start_key)}</span> - <span style='color:#f39c12'>{hex(end_key)}</span>")

    def update_gpu_stats_display(self, stats):
        if not hasattr(self, 'gpu_worker_stats'):
            self.gpu_worker_stats = {}
        
        sender_reader = self.sender()
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
        
        if self.gpu_total_keys_in_range > 0:
            progress_percent = min(100.0, (self.gpu_keys_checked / self.gpu_total_keys_in_range) * 100)
            self.gpu_progress_bar.setValue(int(progress_percent))
            
            if self.gpu_random_checkbox.isChecked():
                elapsed = time.time() - self.gpu_start_time
                self.gpu_progress_bar.setFormat(
                    f"Оценочный прогресс: {progress_percent:.2f}% ({int(elapsed // 60):02d}:{int(elapsed % 60):02d})"
                )
            else:
                self.gpu_progress_bar.setFormat(
                    f"Прогресс: {progress_percent:.2f}% ({self.gpu_keys_checked:,} / {self.gpu_total_keys_in_range:,})"
                )
        else:
            self.gpu_progress_bar.setFormat(f"Проверено: {self.gpu_keys_checked:,} ключей")
        
        self.gpu_speed_label.setText(f"Скорость: {self.gpu_keys_per_second:.2f} MKey/s")
        self.gpu_checked_label.setText(f"Проверено ключей: {self.gpu_keys_checked:,}")

    def update_gpu_time_display(self):
        if self.gpu_start_time:
            elapsed = time.time() - self.gpu_start_time
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.gpu_time_label.setText(f"Время работы: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
            
            if self.gpu_total_keys_in_range > 0 and self.gpu_keys_per_second > 0:
                time_since_last_update = time.time() - self.gpu_last_update_time
                additional_keys = self.gpu_keys_per_second * time_since_last_update * 1000000
                total_checked = self.gpu_keys_checked + additional_keys
                progress_percent = min(100, (total_checked / self.gpu_total_keys_in_range) * 100)
                self.gpu_progress_bar.setValue(int(progress_percent))
                
                if self.gpu_random_checkbox.isChecked():
                    self.gpu_progress_bar.setFormat(
                        f"Оценочный прогресс: {progress_percent:.1f}% ({int(total_checked):,} ключей)"
                    )
                else:
                    self.gpu_progress_bar.setFormat(
                        f"Прогресс: {progress_percent:.1f}% ({int(total_checked):,} / {self.gpu_total_keys_in_range:,})"
                    )
            
            if self.gpu_random_checkbox.isChecked():
                self.gpu_status_label.setText("Статус: Случайный поиск")
            else:
                self.gpu_status_label.setText("Статус: Последовательный поиск")
        else:
            self.gpu_time_label.setText("Время работы: 00:00:00")

    def handle_gpu_search_finished(self):
        all_finished = True
        for process, reader in self.gpu_processes:
            if process.poll() is None or reader.isRunning():
                all_finished = False
                break
        
        if all_finished:
            self.gpu_search_finished()

    def gpu_search_finished(self):
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_processes = []
        self.gpu_start_stop_btn.setText("Запустить GPU поиск")
        self.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.gpu_status_label.setText("Статус: Завершено")
        self.gpu_progress_bar.setValue(0)
        self.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.gpu_checked_label.setText("Проверено ключей: 0")
        self.gpu_found_label.setText("Найдено ключей: 0")
        self.parent.append_log("GPU поиск завершен", "normal")

    def stop_gpu_search_internal(self):
        for process, reader in self.gpu_processes:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                if reader.isRunning():
                    reader.terminate()
                    reader.wait()
            except:
                pass
        self.gpu_processes = []
        self.gpu_is_running = False

    def stop_gpu_search(self):
        self.gpu_restart_timer.stop()
        self.stop_gpu_search_internal()
        self.gpu_search_finished()
        self.used_ranges.clear()
        self.update_gpu_range_label("-", "-")

    def restart_gpu_random_search(self):
        if self.gpu_is_running:
            self.stop_gpu_search_internal()
        self.parent.append_log("Перезапуск GPU поиска с новым случайным диапазоном...", "normal")
        QTimer.singleShot(1000, self.start_gpu_random_search)

    def start_gpu_random_search(self):
        if self.gpu_is_running:
            return
        
        start_key, end_key, error = gpu_core.generate_gpu_random_range(
            self.gpu_start_key_edit.text().strip(),
            self.gpu_end_key_edit.text().strip(),
            self.gpu_min_range_edit.text().strip(),
            self.gpu_max_range_edit.text().strip(),
            self.used_ranges,
            self.max_saved_random
        )
        
        if error:
            self.parent.append_log(f"Ошибка генерации случайного диапазона при перезапуске: {error}", "error")
            self.gpu_restart_timer.stop()
            QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать диапазон при перезапуске: {error}")
            return
        
        if start_key is None or end_key is None:
            self.parent.append_log("Не удалось сгенерировать случайный диапазон при перезапуске.", "error")
            self.gpu_restart_timer.stop()
            QMessageBox.warning(self, "Ошибка", "Не удалось сгенерировать случайный диапазон при перезапуске.")
            return
        
        self.update_gpu_range_label(start_key, end_key)
        self.parent.append_log(f"Новый случайный диапазон GPU: {hex(start_key)} - {hex(end_key)}", "normal")
        self.start_gpu_search_with_range(start_key, end_key)

    def update_gpu_status(self):
        try:
            import pynvml
            device_str = self.gpu_device_combo.currentText().split(',')[0].strip()
            device_id = int(device_str) if device_str.isdigit() else 0
            
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            
            util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = util_info.gpu
            
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used_mb = mem_info.used / (1024 * 1024)
            mem_total_mb = mem_info.total / (1024 * 1024)
            mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0
            
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                temperature = None
            
            self.gpu_util_label.setText(f"Загрузка GPU: {gpu_util} %")
            self.gpu_util_bar.setValue(gpu_util)
            
            self.gpu_mem_label.setText(f"Память GPU: {mem_used_mb:.0f} / {mem_total_mb:.0f} MB ({mem_util:.1f}%)")
            self.gpu_mem_bar.setValue(int(mem_util))
            
            if temperature is not None:
                self.gpu_temp_label.setText(f"Температура: {temperature} °C")
                if temperature > 80:
                    self.gpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                elif temperature > 65:
                    self.gpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")
                else:
                    self.gpu_temp_label.setStyleSheet("color: #27ae60;")
            else:
                self.gpu_temp_label.setText("Температура: - °C")
                self.gpu_temp_label.setStyleSheet("color: #7f8c8d;")
            
            pynvml.nvmlShutdown()
        except ImportError:
            self.gpu_util_label.setText("Загрузка GPU: N/A")
            self.gpu_mem_label.setText("Память GPU: N/A")
            self.gpu_temp_label.setText("Температура: N/A")
        except Exception as e:
            logger.error(f"Ошибка обновления статуса GPU: {str(e)}")
            self.gpu_util_label.setText("Загрузка GPU: Ошибка")
            self.gpu_mem_label.setText("Память GPU: Ошибка")
            self.gpu_temp_label.setText("Температура: Ошибка")