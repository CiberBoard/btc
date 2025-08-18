import os
import time
import math
import multiprocessing
import queue
import psutil
import platform
from PyQt5.QtCore import Qt, QTimer, QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
                             QPushButton, QGroupBox, QSpinBox, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QProgressBar, QMessageBox, QHBoxLayout)

import core.cpu_scanner as cpu_core
from logger import config
from ui.main_ui import logger
from utils.helpers import validate_key_range, is_coincurve_available

class CPUTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)
        self.processes = {}
        self.cpu_stop_requested = False
        self.cpu_pause_requested = False
        self.cpu_start_time = 0
        self.cpu_total_scanned = 0
        self.cpu_total_found = 0
        self.workers_stats = {}
        self.last_update_time = time.time()
        self.start_key = 0
        self.end_key = 0
        self.total_keys = 0
        self.cpu_mode = "sequential"
        self.worker_chunks = {}
        self.queue_active = True
        
        self.process_queue = multiprocessing.Queue()
        self.shutdown_event = multiprocessing.Event()
        
        self.setup_ui()
        self.setup_connections()
        
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(100)
        
        # CPU Hardware Monitor
        self.cpu_hw_timer = QTimer()
        self.cpu_hw_timer.timeout.connect(self.update_cpu_hardware_status)
        self.cpu_hw_timer.start(2000)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # CPU параметры поиска
        cpu_params_group = QGroupBox("CPU: Параметры поиска")
        cpu_params_layout = QGridLayout(cpu_params_group)
        cpu_params_layout.setSpacing(8)
        cpu_params_layout.setColumnStretch(1, 1)
        
        cpu_params_layout.addWidget(QLabel("Целевой адрес:"), 0, 0)
        self.cpu_target_edit = QLineEdit()
        self.cpu_target_edit.setPlaceholderText("Введите BTC адрес (1 или 3)")
        cpu_params_layout.addWidget(self.cpu_target_edit, 0, 1, 1, 3)
        
        # Диапазон ключей для CPU
        cpu_keys_group = QGroupBox("Диапазон ключей")
        cpu_keys_layout = QGridLayout(cpu_keys_group)
        cpu_keys_layout.addWidget(QLabel("Начальный ключ:"), 0, 0)
        self.cpu_start_key_edit = QLineEdit("1")
        self.cpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
        cpu_keys_layout.addWidget(self.cpu_start_key_edit, 0, 1)
        
        cpu_keys_layout.addWidget(QLabel("Конечный ключ:"), 0, 2)
        self.cpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.cpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
        cpu_keys_layout.addWidget(self.cpu_end_key_edit, 0, 3)
        
        cpu_params_layout.addWidget(cpu_keys_group, 1, 0, 1, 4)
        
        # Параметры сканирования для CPU
        cpu_scan_params_group = QGroupBox("Параметры сканирования")
        cpu_scan_params_layout = QGridLayout(cpu_scan_params_group)
        param_input_width = 120
        
        cpu_scan_params_layout.addWidget(QLabel("Префикс:"), 0, 0)
        self.cpu_prefix_spin = QSpinBox()
        self.cpu_prefix_spin.setRange(1, 20)
        self.cpu_prefix_spin.setValue(8)
        self.cpu_prefix_spin.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_prefix_spin, 0, 1)
        
        cpu_scan_params_layout.addWidget(QLabel("Попыток:"), 0, 2)
        self.cpu_attempts_edit = QLineEdit("10000000")
        self.cpu_attempts_edit.setEnabled(False)
        self.cpu_attempts_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
        self.cpu_attempts_edit.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_attempts_edit, 0, 3)
        
        cpu_scan_params_layout.addWidget(QLabel("Режим:"), 1, 0)
        self.cpu_mode_combo = QComboBox()
        self.cpu_mode_combo.addItems(["Последовательный", "Случайный"])
        self.cpu_mode_combo.currentIndexChanged.connect(self.on_cpu_mode_changed)
        self.cpu_mode_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_mode_combo, 1, 1)
        
        cpu_scan_params_layout.addWidget(QLabel("Рабочих:"), 1, 2)
        self.cpu_workers_spin = QSpinBox()
        self.cpu_workers_spin.setRange(1, multiprocessing.cpu_count() * 2)
        self.cpu_workers_spin.setValue(self.optimal_workers)
        self.cpu_workers_spin.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_workers_spin, 1, 3)
        
        cpu_scan_params_layout.addWidget(QLabel("Приоритет:"), 2, 0)
        self.cpu_priority_combo = QComboBox()
        self.cpu_priority_combo.addItems(
            ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"]
        )
        self.cpu_priority_combo.setCurrentIndex(3)
        self.cpu_priority_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_priority_combo, 2, 1)
        
        cpu_params_layout.addWidget(cpu_scan_params_group, 2, 0, 1, 4)
        layout.addWidget(cpu_params_group)
        
        # CPU кнопки управления
        cpu_button_layout = QHBoxLayout()
        cpu_button_layout.setSpacing(10)
        
        self.cpu_start_stop_btn = QPushButton("Старт CPU (Ctrl+S)")
        self.cpu_start_stop_btn.setMinimumHeight(35)
        self.cpu_start_stop_btn.setStyleSheet("""
            QPushButton { background: #27ae60; font-weight: bold; }
            QPushButton:hover { background: #2ecc71; }
            QPushButton:pressed { background: #219653; }
        """)
        
        self.cpu_pause_resume_btn = QPushButton("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setMinimumHeight(35)
        self.cpu_pause_resume_btn.setStyleSheet("""
            QPushButton { background: #f39c12; color: black; font-weight: bold; }
            QPushButton:hover { background: #f1c40f; }
            QPushButton:pressed { background: #e67e22; }
        """)
        self.cpu_pause_resume_btn.setEnabled(False)
        
        cpu_button_layout.addWidget(self.cpu_start_stop_btn)
        cpu_button_layout.addWidget(self.cpu_pause_resume_btn)
        layout.addLayout(cpu_button_layout)
        
        # CPU общий прогресс
        cpu_progress_layout = QVBoxLayout()
        cpu_progress_layout.setSpacing(6)
        
        self.cpu_total_stats_label = QLabel("Статус: Ожидание запуска")
        self.cpu_total_stats_label.setStyleSheet("font-weight: bold; color: #3498db;")
        cpu_progress_layout.addWidget(self.cpu_total_stats_label)
        
        self.cpu_total_progress = QProgressBar()
        self.cpu_total_progress.setRange(0, 100)
        self.cpu_total_progress.setValue(0)
        self.cpu_total_progress.setFormat("Общий прогресс: %p%")
        self.cpu_total_progress.setStyleSheet("""
            QProgressBar { height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px; }
        """)
        cpu_progress_layout.addWidget(self.cpu_total_progress)
        
        self.cpu_eta_label = QLabel("Оставшееся время: -")
        self.cpu_eta_label.setStyleSheet("color: #f39c12;")
        cpu_progress_layout.addWidget(self.cpu_eta_label)
        
        layout.addLayout(cpu_progress_layout)
        
        # CPU статистика воркеров
        layout.addWidget(QLabel("Статистика воркеров:"))
        
        self.cpu_workers_table = QTableWidget(0, 5)
        self.cpu_workers_table.setHorizontalHeaderLabels(["ID", "Проверено", "Найдено", "Скорость", "Прогресс"])
        self.cpu_workers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cpu_workers_table.verticalHeader().setVisible(False)
        self.cpu_workers_table.setAlternatingRowColors(True)
        self.cpu_workers_table.setStyleSheet("""
            QTableWidget { background: #232332; color: #F0F0F0; gridline-color: #333; alternate-background-color: #222228; }
            QHeaderView::section { background: #232332; color: #F0F0F0; padding: 4px; border: none; font-weight: bold; }
        """)
        layout.addWidget(self.cpu_workers_table, 1)
        
        # CPU Hardware Status
        cpu_hw_status_group = QGroupBox("CPU: Аппаратный статус")
        cpu_hw_status_layout = QGridLayout(cpu_hw_status_group)
        cpu_hw_status_layout.setSpacing(6)
        
        self.cpu_temp_label = QLabel("Температура: - °C")
        self.cpu_temp_label.setStyleSheet("color: #e74c3c;")
        cpu_hw_status_layout.addWidget(self.cpu_temp_label, 0, 0)
        
        self.cpu_temp_bar = QProgressBar()
        self.cpu_temp_bar.setRange(0, 100)
        self.cpu_temp_bar.setValue(0)
        self.cpu_temp_bar.setFormat("Темп: %p°C")
        self.cpu_temp_bar.setStyleSheet("""
            QProgressBar { height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653); }
        """)
        cpu_hw_status_layout.addWidget(self.cpu_temp_bar, 1, 0)
        
        layout.addWidget(cpu_hw_status_group)

    def setup_connections(self):
        self.cpu_start_stop_btn.clicked.connect(self.toggle_cpu_start_stop)
        self.cpu_pause_resume_btn.clicked.connect(self.toggle_cpu_pause_resume)

    def on_cpu_mode_changed(self, index):
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)
        self.cpu_mode = "random" if is_random else "sequential"

    def validate_cpu_inputs(self):
        address = self.cpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self, "Ошибка", "Введите корректный BTC адрес для CPU")
            return False
        
        if not is_coincurve_available():
            QMessageBox.warning(self, "Ошибка", "Библиотека coincurve не установлена. CPU поиск недоступен.")
            return False
        
        result, error = validate_key_range(
            self.cpu_start_key_edit.text().strip(),
            self.cpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False
        
        self.start_key, self.end_key, self.total_keys = result
        
        if self.cpu_mode == "random":
            try:
                attempts = int(self.cpu_attempts_edit.text())
                if attempts <= 0:
                    QMessageBox.warning(self, "Ошибка", "Количество попыток должно быть положительным числом")
                    return False
            except ValueError:
                QMessageBox.warning(self, "Ошибка", "Неверный формат количества попыток")
                return False
        
        return True

    def toggle_cpu_start_stop(self):
        if not self.processes:
            self.start_cpu_search()
        else:
            self.stop_cpu_search()

    def toggle_cpu_pause_resume(self):
        if self.cpu_pause_requested:
            self.resume_cpu_search()
        else:
            self.pause_cpu_search()

    def start_cpu_search(self):
        if not self.validate_cpu_inputs():
            return
        
        self.cpu_stop_requested = False
        self.cpu_pause_requested = False
        self.cpu_start_time = time.time()
        self.cpu_total_scanned = 0
        self.cpu_total_found = 0
        self.workers_stats = {}
        self.last_update_time = time.time()
        self.worker_chunks = {}
        self.queue_active = True
        
        target = self.cpu_target_edit.text().strip()
        prefix_len = self.cpu_prefix_spin.value()
        workers = self.cpu_workers_spin.value()
        start_int = self.start_key
        end_int = self.end_key
        attempts = int(self.cpu_attempts_edit.text()) if self.cpu_mode == "random" else 0
        
        # Очистка таблицы воркеров
        self.cpu_workers_table.setRowCount(workers)
        self.cpu_workers_table.setUpdatesEnabled(False)
        
        try:
            for i in range(workers):
                self.update_cpu_worker_row(i)
        finally:
            self.cpu_workers_table.setUpdatesEnabled(True)
        
        # Установка приоритета процесса
        priority_index = self.cpu_priority_combo.currentIndex()
        creationflags = config.WINDOWS_CPU_PRIORITY_MAP.get(priority_index, 0x00000020)
        
        # Запуск воркеров
        for i in range(workers):
            p = multiprocessing.Process(
                target=cpu_core.worker_main,
                args=(
                    target[:prefix_len],
                    start_int,
                    end_int,
                    attempts,
                    self.cpu_mode,
                    i,
                    workers,
                    self.process_queue,
                    self.shutdown_event
                )
            )
            p.daemon = True
            
            if platform.system() == 'Windows' and creationflags:
                try:
                    p._config['creationflags'] = creationflags
                except:
                    pass
            
            p.start()
            self.processes[i] = p
            self.workers_stats[i] = {
                'scanned': 0,
                'found': 0,
                'speed': 0,
                'progress': 0,
                'active': True
            }
        
        self.parent.append_log(
            f"Запущено {workers} CPU воркеров в режиме {'случайного' if self.cpu_mode == 'random' else 'последовательного'} поиска"
        )
        
        self.cpu_start_stop_btn.setText("Стоп CPU (Ctrl+Q)")
        self.cpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
        self.cpu_pause_resume_btn.setEnabled(True)
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

    def process_queue_messages(self):
        if not self.queue_active:
            return
        
        start_time = time.time()
        processed = 0
        max_messages = 100
        max_time = 0.1
        
        try:
            while processed < max_messages and (time.time() - start_time) < max_time:
                try:
                    data = self.process_queue.get_nowait()
                    processed += 1
                    msg_type = data.get('type')
                    
                    if msg_type == 'stats':
                        worker_id = data['worker_id']
                        self.workers_stats[worker_id] = {
                            'scanned': data['scanned'],
                            'found': data['found'],
                            'speed': data['speed'],
                            'progress': data['progress'],
                            'active': True
                        }
                        self.update_cpu_worker_row(worker_id)
                        self.update_cpu_total_stats()
                    
                    elif msg_type == 'found':
                        self.parent.handle_found_key(data)
                    
                    elif msg_type == 'log':
                        self.parent.append_log(data['message'])
                    
                    elif msg_type == 'worker_finished':
                        worker_id = data['worker_id']
                        if worker_id in self.workers_stats:
                            self.workers_stats[worker_id]['active'] = False
                        self.cpu_worker_finished(worker_id)
                
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {str(e)}")
                    break
        except Exception as e:
            logger.exception("Критическая ошибка обработки очереди")
            self.queue_active = False

    def update_cpu_worker_row(self, worker_id):
        stats = self.workers_stats.get(worker_id, {})
        scanned = stats.get('scanned', 0)
        found = stats.get('found', 0)
        speed = stats.get('speed', 0)
        progress = stats.get('progress', 0)
        
        if self.cpu_workers_table.rowCount() <= worker_id:
            self.cpu_workers_table.setRowCount(worker_id + 1)
        
        # ID воркера
        if self.cpu_workers_table.item(worker_id, 0) is None:
            item = QTableWidgetItem(str(worker_id))
            item.setTextAlignment(Qt.AlignCenter)
            self.cpu_workers_table.setItem(worker_id, 0, item)
        else:
            self.cpu_workers_table.item(worker_id, 0).setText(str(worker_id))
        
        # Проверено ключей
        if self.cpu_workers_table.item(worker_id, 1) is None:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cpu_workers_table.setItem(worker_id, 1, item)
        self.cpu_workers_table.item(worker_id, 1).setText(f"{scanned:,}")
        
        # Найдено ключей
        if self.cpu_workers_table.item(worker_id, 2) is None:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignCenter)
            self.cpu_workers_table.setItem(worker_id, 2, item)
        self.cpu_workers_table.item(worker_id, 2).setText(str(found))
        
        # Скорость
        if self.cpu_workers_table.item(worker_id, 3) is None:
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cpu_workers_table.setItem(worker_id, 3, item)
        self.cpu_workers_table.item(worker_id, 3).setText(f"{speed:,.0f} keys/sec")
        
        # Прогресс бар
        if self.cpu_workers_table.cellWidget(worker_id, 4) is None:
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setAlignment(Qt.AlignCenter)
            progress_bar.setFormat("%p%")
            self.cpu_workers_table.setCellWidget(worker_id, 4, progress_bar)
        else:
            progress_bar = self.cpu_workers_table.cellWidget(worker_id, 4)
        progress_bar.setValue(progress)

    def update_cpu_total_stats(self):
        total_scanned = 0
        total_found = 0
        total_speed = 0
        total_progress = 0
        count = 0
        
        for stats in self.workers_stats.values():
            total_scanned += stats.get('scanned', 0)
            total_found += stats.get('found', 0)
            total_speed += stats.get('speed', 0)
            if 'progress' in stats:
                total_progress += stats['progress']
                count += 1
        
        self.cpu_total_scanned = total_scanned
        self.cpu_total_found = total_found
        
        if count > 0:
            progress = total_progress / count
            self.cpu_total_progress.setValue(int(progress))
        
        elapsed = max(1, time.time() - self.cpu_start_time)
        avg_speed = total_scanned / elapsed if elapsed > 0 else 0
        
        # Расчет оставшегося времени
        eta_text = "-"
        if self.cpu_mode == "sequential" and self.total_keys > 0:
            processed = self.cpu_total_scanned
            remaining = self.total_keys - processed
            if avg_speed > 0:
                eta_seconds = remaining / avg_speed
                hours, remainder = divmod(eta_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                eta_text = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        self.cpu_eta_label.setText(f"Оставшееся время: {eta_text}")
        self.cpu_total_stats_label.setText(
            f"Всего проверено: {total_scanned:,} | Найдено: {total_found} | "
            f"Скорость: {total_speed:,.0f} keys/sec | "
            f"Средняя скорость: {avg_speed:,.0f} keys/sec | "
            f"Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
        )

    def cpu_worker_finished(self, worker_id):
        if worker_id in self.processes:
            process = self.processes[worker_id]
            if process.is_alive():
                process.join(timeout=0.1)
            del self.processes[worker_id]
        
        if not self.processes:
            self.parent.append_log("Все CPU воркеры завершили работу")
            self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
            self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.cpu_pause_resume_btn.setEnabled(False)
            self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
            self.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
            self.cpu_eta_label.setText("Оставшееся время: -")
            self.cpu_total_stats_label.setText("Статус: Завершено")

    def pause_cpu_search(self):
        self.cpu_pause_requested = True
        for worker_id, process in self.processes.items():
            if process.is_alive():
                process.terminate()
                self.parent.append_log(f"CPU воркер {worker_id} остановлен")
        
        self.processes = {}
        self.parent.append_log("CPU поиск приостановлен")
        self.cpu_pause_resume_btn.setText("Продолжить")
        self.cpu_pause_resume_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    def resume_cpu_search(self):
        self.cpu_pause_requested = False
        self.start_cpu_search()
        self.parent.append_log("CPU поиск продолжен")
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

    def stop_cpu_search(self):
        self.cpu_stop_requested = True
        self.shutdown_event.set()
        
        for worker_id, process in self.processes.items():
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
        
        self.processes = {}
        self.shutdown_event.clear()
        
        self.parent.append_log("CPU поиск остановлен")
        self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.cpu_pause_resume_btn.setEnabled(False)
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
        self.cpu_eta_label.setText("Оставшееся время: -")
        self.cpu_total_stats_label.setText("Статус: Остановлено")
        self.cpu_workers_table.setRowCount(0)
        self.cpu_total_progress.setValue(0)

    def update_cpu_hardware_status(self):
        try:
            cpu_temp = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if name.lower() in ['coretemp', 'k10temp', 'cpu_thermal', 'acpi']:
                            for entry in entries:
                                if entry.current is not None:
                                    if cpu_temp is None or 'package' in entry.label.lower() or entry.label == '':
                                        cpu_temp = entry.current
                                    if 'package' in entry.label.lower():
                                        break
                            if cpu_temp is not None:
                                break
                    if cpu_temp is None:
                        for entries in temps.values():
                            for entry in entries:
                                if entry.current is not None:
                                    cpu_temp = entry.current
                                    break
                            if cpu_temp is not None:
                                break
            except (AttributeError, NotImplementedError):
                pass

            if cpu_temp is not None:
                self.cpu_temp_label.setText(f"Температура: {cpu_temp:.1f} °C")
                self.cpu_temp_bar.setRange(0, 100)
                self.cpu_temp_bar.setValue(int(cpu_temp))
                self.cpu_temp_bar.setFormat(f"Темп: {cpu_temp:.1f}°C")
                
                if cpu_temp > 80:
                    self.cpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar { height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20; }
                        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b); }
                    """)
                elif cpu_temp > 65:
                    self.cpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar { height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20; }
                        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f39c12, stop:1 #d35400); }
                    """)
                else:
                    self.cpu_temp_label.setStyleSheet("color: #27ae60;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar { height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20; }
                        QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653); }
                    """)
            else:
                self.cpu_temp_label.setText("Температура: N/A")
                self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")
                self.cpu_temp_bar.setValue(0)
                self.cpu_temp_bar.setFormat("Темп: N/A")
        except Exception as e:
            self.cpu_temp_label.setText("Температура: Ошибка")
            self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")
            self.cpu_temp_bar.setValue(0)
            self.cpu_temp_bar.setFormat("Темп: Ошибка")