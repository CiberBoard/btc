# ui/main_window.py
import os
import subprocess
import time
import json
import platform
import psutil
import multiprocessing
import queue
from PyQt5.QtCore import Qt, QTimer, QRegExp, pyqtSignal, QMetaObject
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QRegExpValidator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QMessageBox, QGroupBox, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMenu, QProgressBar, QCheckBox, QComboBox, QTabWidget,
                             QFileDialog, QSpinBox)
import config
from ui.ui_main import MainWindowUI
from ui.theme import apply_dark_theme
from utils.helpers import setup_logger, format_time, is_coincurve_available, make_combo32
from ui.kangaroo_logic import KangarooLogic
from core.hextowif import generate_all_from_hex
try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None
logger = setup_logger()

# Импорт логики
from ui.gpu_logic import GPULogic
from ui.cpu_logic import CPULogic
from ui.vanity_logic import VanityLogic

class BitcoinGPUCPUScanner(QMainWindow):
    # ✅ Объявляем сигнал на уровне КЛАССА
    vanity_update_ui_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ✅ Экспортируем константы для UI
        self.MAX_KEY_HEX = config.MAX_KEY_HEX
        self.BASE_DIR = config.BASE_DIR
        # В __init__ или setup_connections:

        # --- Инициализация pynvml для мониторинга GPU ---
        self.gpu_monitor_available = False
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_monitor_available = True
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    logger.info(f"Найдено {device_count} NVIDIA GPU устройств для мониторинга.")
                else:
                    logger.warning("NVIDIA GPU устройства не найдены.")
                    self.gpu_monitor_available = False
            except Exception as e:
                logger.error(f"Ошибка инициализации pynvml: {e}")
                self.gpu_monitor_available = False
        else:
            logger.warning("Библиотека pynvml не установлена. Мониторинг GPU недоступен.")

        # GPU variables
        self.gpu_range_label = None
        self.random_mode = False
        self.last_random_ranges = set()
        self.max_saved_random = 100
        self.used_ranges = set()
        self.gpu_restart_timer = QTimer()
        self.gpu_restart_delay = 1000  # 1 секунда по умолчанию

        # CPU variables - ИНИЦИАЛИЗИРУЕМ РАНЬШЕ setup_ui
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)

        # --- Инициализация логики ---
        self.gpu_logic = GPULogic(self)  # Инициализируем ДО setup_ui и setup_connections
        self.cpu_logic = CPULogic(self)
        self.kangaroo_logic = KangarooLogic(self)
        self.vanity_logic = VanityLogic(self)
        # ✅ Подключаем сигнал — ПОСЛЕ создания vanity_logic
        self.vanity_update_ui_signal.connect(self.vanity_logic.handle_stats)
        apply_dark_theme(self)  # ✅ вместо self.set_dark_theme()
        self.ui = MainWindowUI(self)  # ✅ Создаём обёртку UI
        self.ui.setup_ui()
        self.setup_connections()  # <-- setup_connections вызывается ПОСЛЕ инициализации логики
        self.load_settings()
        # Создаем файл для найденных ключей, если его нет
        if not os.path.exists(config.FOUND_KEYS_FILE):
            open(config.FOUND_KEYS_FILE, 'w').close()
        # --- Инициализация таймеров и системной информации ---
        # CPU queue timer


        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(100)  # Увеличили частоту обработки до 10 раз в секунду
        # Инициализация системной информации
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(2000)
        # =============== GPU Status Timer (если используется pynvml) ===============
        if self.gpu_monitor_available:
            self.gpu_status_timer = QTimer()
            self.gpu_status_timer.timeout.connect(self.update_gpu_status)
            self.gpu_status_timer.start(1500)  # 1.5 секунды
        else:
            self.gpu_status_timer = None
        # =============== КОНЕЦ GPU Status Timer ===============

        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900)  # Размер окна, если не задан в setup_ui

    # Также добавьте эти два метода в класс BitcoinGPUCPUScanner:

    def browse_kangaroo_exe(self):
        """Выбор файла etarkangaroo.exe"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите etarkangaroo.exe",
            config.BASE_DIR,
            "Executable Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self.kang_exe_edit.setText(file_path)
            self.append_log(f"Выбран файл: {file_path}", "success")

    def browse_kangaroo_temp(self):
        """Выбор временной директории"""
        from PyQt5.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите временную директорию",
            config.BASE_DIR
        )
        if dir_path:
            self.kang_temp_dir_edit.setText(dir_path)
            self.append_log(f"Выбрана директория: {dir_path}", "success")

    def copy_vanity_result(self):
        parts = [
            self.vanity_result_addr.text().strip(),
            self.vanity_result_hex.text().strip(),
            self.vanity_result_wif.text().strip()
        ]
        text = "\n".join([p for p in parts if p])
        if text:
            QApplication.clipboard().setText(text)
            self.append_log("Результат Vanity скопирован", "success")

    def setup_connections(self):
        # GPU connections - подключаем к методам GPULogic
        self.gpu_start_stop_btn.clicked.connect(self.gpu_logic.toggle_gpu_search)
        self.gpu_optimize_btn.clicked.connect(self.gpu_logic.auto_optimize_gpu_parameters)
        # CPU connections - подключаем к методам CPULogic
        self.cpu_start_stop_btn.clicked.connect(self.cpu_logic.toggle_cpu_start_stop)
        self.cpu_pause_resume_btn.clicked.connect(self.cpu_logic.toggle_cpu_pause_resume)
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))
        self.vanity_start_stop_btn.clicked.connect(self.vanity_logic.toggle_search)
        # Common connections
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        # GPU timers - подключаем к методам GPULogic
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.gpu_logic.update_gpu_time_display)
        self.gpu_stats_timer.start(500)  # Увеличили частоту обновления в 2 раза
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(2000)
        # =============== GPU Status Timer ===============
        if self.gpu_monitor_available:
            self.gpu_status_timer = QTimer()
            self.gpu_status_timer.timeout.connect(self.update_gpu_status)
            self.gpu_status_timer.start(1500)  # 1.5 секунды
            self.selected_gpu_device_id = 0
        else:
            self.gpu_status_timer = None
        # =============== КОНЕЦ GPU Status Timer ===============
        self.gpu_logic.setup_gpu_connections()  # <-- ВАЖНО: вызываем ПОСЛЕ создания gpu_restart_timer

    def emit_vanity_stats(self, stats: dict):
        self.vanity_update_ui_signal.emit(stats)

    def setup_converter_tab(self):
        """Создаёт вкладку конвертера HEX → WIF и адреса"""
        converter_tab = QWidget()
        layout = QVBoxLayout(converter_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Инструкция
        info_label = QLabel(
            "Введите приватный ключ в формате HEX (64 символа), выберите опции и нажмите 'Сгенерировать'."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #CCCCCC; font-size: 10pt;")
        layout.addWidget(info_label)

        # HEX input
        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("Приватный ключ (HEX):"))
        self.hex_input = QLineEdit()
        self.hex_input.setPlaceholderText("Например: 1a2b3c4d...")
        self.hex_input.setMaxLength(64)
        hex_layout.addWidget(self.hex_input, 1)
        layout.addLayout(hex_layout)

        # Опции
        options_layout = QHBoxLayout()
        self.compressed_checkbox = QCheckBox("Сжатый публичный ключ")
        self.compressed_checkbox.setChecked(True)
        self.testnet_checkbox = QCheckBox("Testnet")
        self.testnet_checkbox.setChecked(False)
        options_layout.addWidget(self.compressed_checkbox)
        options_layout.addWidget(self.testnet_checkbox)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Генерировать кнопка
        self.generate_btn = QPushButton("Сгенерировать")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.generate_btn)

        # Результаты
        result_group = QGroupBox("Результаты")
        result_layout = QGridLayout(result_group)
        result_layout.setSpacing(8)

        self.result_fields = {}
        row = 0
        for label_text in ["HEX", "WIF", "P2PKH", "P2SH-P2WPKH", "Bech32 (P2WPKH)"]:
            result_layout.addWidget(QLabel(f"{label_text}:"), row, 0)
            value_edit = QLineEdit()
            value_edit.setReadOnly(True)
            value_edit.setStyleSheet("background: #202030; color: #F0F0F0;")
            result_layout.addWidget(value_edit, row, 1)
            copy_btn = QPushButton("Копировать")
            copy_btn.setFixedWidth(100)
            copy_btn.setProperty("target", label_text.lower())
            copy_btn.clicked.connect(self.copy_to_clipboard)
            result_layout.addWidget(copy_btn, row, 2)
            self.result_fields[label_text] = value_edit
            row += 1

        layout.addWidget(result_group)

        # Добавляем вкладку
        self.main_tabs.addTab(converter_tab, "Конвертер HEX → WIF")

    def on_generate_clicked(self):
        hex_key = self.hex_input.text().strip()
        if not hex_key or len(hex_key) > 64 or not all(c in '0123456789abcdefABCDEF' for c in hex_key):
            QMessageBox.warning(self, "Ошибка", "Введите корректный HEX-ключ (до 64 символов).")
            return

        compressed = self.compressed_checkbox.isChecked()
        testnet = self.testnet_checkbox.isChecked()

        try:
            result = generate_all_from_hex(hex_key, compressed=compressed, testnet=testnet)
            for key, value in result.items():
                if key in self.result_fields:
                    self.result_fields[key].setText(value)
            self.append_log(f"Сгенерировано: {result['P2PKH']}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def copy_to_clipboard(self):
        btn = self.sender()
        field_name = btn.property("target")
        field_map = {
            "hex": "HEX",
            "wif": "WIF",
            "p2pkh": "P2PKH",
            "p2sh-p2wpkh": "P2SH-P2WPKH",
            "bech32 (p2wpkh)": "Bech32 (P2WPKH)"
        }
        display_name = field_map.get(field_name.lower())
        if display_name and display_name in self.result_fields:
            text = self.result_fields[display_name].text()
            if text:
                QApplication.clipboard().setText(text)
                self.append_log(f"Скопировано: {display_name}", "success")

    def on_cpu_mode_changed(self, index):
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)
        self.cpu_logic.cpu_mode = "random" if is_random else "sequential"

    def update_system_info(self):
        # ... (оставляем как есть)
        try:
            # --- Существующий код обновления системной информации ---
            mem = psutil.virtual_memory()
            self.mem_label.setText(f"{mem.used // (1024 * 1024)}/{mem.total // (1024 * 1024)} MB")
            self.cpu_usage.setText(f"{psutil.cpu_percent()}%")
            # if self.processes: # Заменено
            if self.cpu_logic.processes:
                # status = "Работает" if not self.cpu_pause_requested else "На паузе" # Заменено
                status = "Работает" if not self.cpu_logic.cpu_pause_requested else "На паузе"
                # self.cpu_status_label.setText(f"{status} ({len(self.processes)} воркеров)") # Заменено
                self.cpu_status_label.setText(f"{status} ({len(self.cpu_logic.processes)} воркеров)")
            else:
                self.cpu_status_label.setText("Ожидание запуска")
            # --- Конец существующего кода ---
            # =============== НОВОЕ: Обновление температуры CPU ===============
            # Попытка получить температуру CPU
            cpu_temp = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Обычно основная температура CPU находится под ключом 'coretemp' (Intel) или 'k10temp' (AMD)
                    # Можно перебирать все, но для простоты возьмем первую подходящую
                    for name, entries in temps.items():
                        # Ищем наиболее вероятные источники температуры CPU
                        if name.lower() in ['coretemp', 'k10temp', 'cpu_thermal', 'acpi']:
                            for entry in entries:
                                # Ищем основную температуру (обычно без суффиксов или с 'package')
                                # или просто первую доступную
                                if entry.current is not None:
                                    if cpu_temp is None or 'package' in entry.label.lower() or entry.label == '':
                                        cpu_temp = entry.current
                                    # Если уже нашли Package, дальше не ищем
                                    if 'package' in entry.label.lower():
                                        break
                            # Если нашли температуру для этого сенсора, выходим
                            if cpu_temp is not None:
                                break
                    # Если не нашли по ключевым словам, берем первую попавшуюся температуру из любого сенсора
                    if cpu_temp is None:
                        for entries in temps.values():
                            for entry in entries:
                                if entry.current is not None:
                                    cpu_temp = entry.current
                                    break
                            if cpu_temp is not None:
                                break
            except (AttributeError, NotImplementedError):
                # sensors_temperatures может не поддерживаться на некоторых системах (например, Windows без WMI)
                pass
            if cpu_temp is not None:
                self.cpu_temp_label.setText(f"Температура: {cpu_temp:.1f} °C")
                # Установка диапазона прогрессбара от 0 до 100°C (можно адаптировать)
                self.cpu_temp_bar.setRange(0, 100)
                self.cpu_temp_bar.setValue(int(cpu_temp))
                self.cpu_temp_bar.setFormat(f"Темп: {cpu_temp:.1f}°C")
                # Цветовая индикация температуры
                if cpu_temp > 80:
                    self.cpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")  # Красный
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);} /* Красный градиент */
                    """)
                elif cpu_temp > 65:
                    self.cpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")  # Оранжевый
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f39c12, stop:1 #d35400);} /* Оранжевый градиент */
                    """)
                else:
                    self.cpu_temp_label.setStyleSheet("color: #27ae60;")  # Зеленый
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);} /* Зеленый градиент */
                    """)
            else:
                self.cpu_temp_label.setText("Температура: N/A")
                self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")  # Серый
                self.cpu_temp_bar.setValue(0)
                self.cpu_temp_bar.setFormat("Темп: N/A")
            # =============== КОНЕЦ НОВОГО ===============
        except Exception as e:
            logger.exception("Ошибка обновления системной информации")
            # --- Существующий код обработки ошибок ---
            self.mem_label.setText("Ошибка данных")
            self.cpu_usage.setText("Ошибка данных")
            self.cpu_status_label.setText("Ошибка данных")
            # --- Конец существующего кода обработки ошибок ---
            # =============== НОВОЕ: Обработка ошибок для температуры ===============
            self.cpu_temp_label.setText("Температура: Ошибка")
            self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")  # Серый
            self.cpu_temp_bar.setValue(0)
            self.cpu_temp_bar.setFormat("Темп: Ошибка")
            # =============== КОНЕЦ НОВОГО ===============

    def process_queue_messages(self):
        # if not self.queue_active: # Заменено
        if not self.cpu_logic.queue_active:
            return
        start_time = time.time()
        processed = 0
        max_messages = 100  # Максимальное количество сообщений за одну итерацию
        max_time = 0.1  # Максимальное время обработки (сек)
        try:
            while processed < max_messages and (time.time() - start_time) < max_time:
                try:
                    # data = self.process_queue.get_nowait() # Заменено
                    data = self.cpu_logic.process_queue.get_nowait()
                    processed += 1
                    msg_type = data.get('type')
                    if msg_type == 'stats':
                        worker_id = data['worker_id']
                        self.cpu_logic.workers_stats[worker_id] = {
                            'scanned': data['scanned'],
                            'found': data['found'],
                            'speed': data['speed'],
                            'progress': data['progress'],
                            'active': True
                        }
                        self.update_cpu_worker_row(worker_id)
                        self.update_cpu_total_stats()
                    elif msg_type == 'found':
                        self.handle_found_key(data)
                    elif msg_type == 'log':
                        self.append_log(data['message'])
                    elif msg_type == 'worker_finished':
                        worker_id = data['worker_id']
                        if worker_id in self.cpu_logic.workers_stats:
                            self.cpu_logic.workers_stats[worker_id]['active'] = False
                        self.cpu_logic.cpu_worker_finished(worker_id)
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {str(e)}")
                    break
        except Exception as e:
            logger.exception("Критическая ошибка обработки очереди")
            # self.queue_active = False # Заменено
            self.cpu_logic.queue_active = False

    def update_cpu_worker_row(self, worker_id):
        # stats = self.workers_stats.get(worker_id, {}) # Заменено
        stats = self.cpu_logic.workers_stats.get(worker_id, {})
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
        # ... (оставляем как есть)
        total_scanned = 0
        total_found = 0
        total_speed = 0
        total_progress = 0
        count = 0
        # for stats in self.workers_stats.values(): # Заменено
        for stats in self.cpu_logic.workers_stats.values():
            total_scanned += stats.get('scanned', 0)
            total_found += stats.get('found', 0)
            total_speed += stats.get('speed', 0)
            if 'progress' in stats:
                total_progress += stats['progress']
                count += 1
        # self.cpu_total_scanned = total_scanned # Заменено
        self.cpu_logic.cpu_total_scanned = total_scanned
        # self.cpu_total_found = total_found # Заменено
        self.cpu_logic.cpu_total_found = total_found
        if count > 0:
            progress = total_progress / count
            self.cpu_total_progress.setValue(int(progress))
        # elapsed = max(1, time.time() - self.cpu_start_time) # Заменено
        elapsed = max(1, time.time() - self.cpu_logic.cpu_start_time)
        # avg_speed = total_scanned / elapsed if elapsed > 0 else 0 # Заменено
        avg_speed = total_scanned / elapsed if elapsed > 0 else 0
        # Расчет оставшегося времени
        eta_text = "-"
        # if self.cpu_mode == "sequential" and self.total_keys > 0: # Заменено
        if self.cpu_logic.cpu_mode == "sequential" and self.cpu_logic.total_keys > 0:
            # processed = self.cpu_total_scanned # Заменено
            processed = self.cpu_logic.cpu_total_scanned
            # remaining = self.total_keys - processed # Заменено
            remaining = self.cpu_logic.total_keys - processed
            if avg_speed > 0:
                eta_seconds = remaining / avg_speed
                eta_text = format_time(eta_seconds)
        self.cpu_eta_label.setText(f"Оставшееся время: {eta_text}")
        self.cpu_total_stats_label.setText(
            f"Всего проверено: {total_scanned:,} | Найдено: {total_found} | "
            f"Скорость: {total_speed:,.0f} keys/sec | "
            f"Средняя скорость: {avg_speed:,.0f} keys/sec | "
            f"Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
        )

    # ============ COMMON METHODS ============
    def export_keys_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", "found_keys.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline='', encoding="utf-8") as f:
                f.write("Время,Адрес,HEX ключ,WIF ключ\n")
                for row in range(self.found_keys_table.rowCount()):
                    row_items = []
                    for col in range(4):
                        item = self.found_keys_table.item(row, col)
                        row_items.append(item.text() if item else "")
                    f.write(','.join(row_items) + "\n")
            self.append_log(f"Экспортировано в {path}", "success")
        except Exception as e:
            logger.error(f"Ошибка экспорта CSV: {str(e)}")
            self.append_log(f"Ошибка экспорта: {str(e)}", "error")

    def show_context_menu(self, position):
        menu = QMenu()
        copy_wif_action = menu.addAction("Копировать WIF ключ")
        copy_hex_action = menu.addAction("Копировать HEX ключ")
        copy_addr_action = menu.addAction("Копировать адрес")
        menu.addSeparator()
        save_all_action = menu.addAction("Сохранить все ключи в файл")
        clear_action = menu.addAction("Очистить таблицу")
        action = menu.exec_(self.found_keys_table.viewport().mapToGlobal(position))
        selected = self.found_keys_table.selectedItems()
        if action == clear_action:
            self.found_keys_table.setRowCount(0)
            self.gpu_found_label.setText("Найдено ключей: 0")
            self.append_log("Таблица найденных ключей очищена", "normal")
            return
        if not selected:
            return
        row = selected[0].row()
        if action == copy_wif_action:
            wif_item = self.found_keys_table.item(row, 3)
            QApplication.clipboard().setText(wif_item.text())
            self.append_log("WIF ключ скопирован в буфер обмена", "success")
        elif action == copy_hex_action:
            hex_item = self.found_keys_table.item(row, 2)
            QApplication.clipboard().setText(hex_item.text())
            self.append_log("HEX ключ скопирован в буфер обмена", "success")
        elif action == copy_addr_action:
            addr_item = self.found_keys_table.item(row, 1)
            QApplication.clipboard().setText(addr_item.text())
            self.append_log("Адрес скопирован в буфер обмена", "success")
        elif action == save_all_action:
            self.save_all_found_keys()

    def save_all_found_keys(self):
        try:
            with open(config.FOUND_KEYS_FILE, 'w', encoding='utf-8') as f:
                for row in range(self.found_keys_table.rowCount()):
                    time = self.found_keys_table.item(row, 0).text()
                    addr = self.found_keys_table.item(row, 1).text()
                    hex_key = self.found_keys_table.item(row, 2).text()
                    wif_key = self.found_keys_table.item(row, 3).text()
                    f.write(f"{time}\t{addr}\t{hex_key}\t{wif_key}\n")
            self.append_log(f"Все ключи сохранены в {config.FOUND_KEYS_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключей: {str(e)}")
            self.append_log(f"Ошибка сохранения ключей: {str(e)}")

    def handle_found_key(self, key_data):
        try:
            found_count = self.found_keys_table.rowCount() + 1
            self.gpu_found_label.setText(f"Найдено ключей: {found_count}")
            row = self.found_keys_table.rowCount()
            self.found_keys_table.insertRow(row)

            # Время
            time_item = QTableWidgetItem(key_data['timestamp'])
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setForeground(QColor(100, 255, 100))
            self.found_keys_table.setItem(row, 0, time_item)

            # Адрес
            addr_item = QTableWidgetItem(key_data['address'])
            addr_item.setTextAlignment(Qt.AlignCenter)
            addr_item.setForeground(QColor(255, 215, 0))
            self.found_keys_table.setItem(row, 1, addr_item)

            # HEX ключ
            hex_item = QTableWidgetItem(key_data['hex_key'])
            hex_item.setTextAlignment(Qt.AlignCenter)
            hex_item.setForeground(QColor(100, 200, 255))
            self.found_keys_table.setItem(row, 2, hex_item)

            # WIF ключ
            wif_item = QTableWidgetItem(key_data['wif_key'])
            wif_item.setTextAlignment(Qt.AlignCenter)
            wif_item.setForeground(QColor(255, 150, 150))
            self.found_keys_table.setItem(row, 3, wif_item)

            # ✨ ИСТОЧНИК (новая колонка 4)
            source = key_data.get('source', 'CPU')  # По умолчанию CPU

            # Цвета для разных источников
            source_colors = {
                'GPU': QColor(50, 205, 50),  # Ярко-зелёный
                'CPU': QColor(100, 149, 237),  # Голубой
                'KANGAROO': QColor(255, 140, 0)  # Оранжевый
            }

            # Эмодзи для источников
            source_emoji = {
                'GPU': '🎮',
                'CPU': '💻',
                'KANGAROO': '🦘'
            }

            source_text = f"{source_emoji.get(source, '❓')} {source}"
            source_item = QTableWidgetItem(source_text)
            source_item.setTextAlignment(Qt.AlignCenter)
            source_item.setForeground(source_colors.get(source, QColor(200, 200, 200)))
            source_item.setFont(QFont('Arial', 10, QFont.Bold))
            self.found_keys_table.setItem(row, 4, source_item)

            self.found_keys_table.scrollToBottom()
            self.save_found_key(key_data)

            # MessageBox с правильным определением источника
            worker_info = f" (Воркер {key_data.get('worker_id', 'N/A')})" if 'worker_id' in key_data else ""

            QMessageBox.information(
                self,
                f"🎉 {source} нашел ключ!",
                f"<b>{source}{worker_info} нашел ключ!</b><br><br>"
                f"<b>Адрес:</b> {key_data['address']}<br>"
                f"<b>HEX ключ:</b> {key_data['hex_key'][:32]}...<br>"
                f"<b>WIF ключ:</b> {key_data['wif_key'][:20]}..."
            )
        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.append_log(f"Ошибка обработки найденного ключа: {str(e)}", "error")

    def save_found_key(self, key_data):
        try:
            with open(config.FOUND_KEYS_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{key_data['timestamp']}\t{key_data['address']}\t{key_data['hex_key']}\t{key_data['wif_key']}\n")
            self.append_log(f"Ключ сохранен в {config.FOUND_KEYS_FILE}", "success")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключа: {str(e)}")
            self.append_log(f"Ошибка сохранения ключа: {str(e)}", "error")

    def append_log(self, message, level="normal"):
        timestamp = time.strftime('[%H:%M:%S]')
        color = "#bbb"
        if level == "error":
            color = "#e74c3c"
            logger.error(message)
        elif level == "success":
            color = "#27ae60"
            logger.info(message)
        elif level == "warning":
            color = "#f1c40f"
            logger.warning(message)
        else:
            logger.debug(message)
        html = f'<span style="color:{color};">{timestamp} {message}</span>'
        self.log_output.append(html)
        # Автопрокрутка к концу
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def open_log_file(self):
        """Открывает файл лога в системном редакторе"""
        try:
            if platform.system() == 'Windows':
                os.startfile(config.LOG_FILE)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', config.LOG_FILE))
            else:  # Linux
                subprocess.call(('xdg-open', config.LOG_FILE))
        except Exception as e:
            self.append_log(f"Не удалось открыть файл лога: {str(e)}", "error")

    def load_settings(self):
        """Загружает настройки из settings.json"""
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                # ✅ ИСПОЛЬЗУЕМ СИСТЕМУ ИЗ config.py
                config.apply_settings_to_ui(self, settings)

                # ✅ Специальная обработка для runtime полей
                if "cpu_mode" in settings:
                    self.cpu_logic.cpu_mode = settings["cpu_mode"]
                    idx = 1 if settings["cpu_mode"] == "random" else 0
                    self.cpu_mode_combo.setCurrentIndex(idx)

                self.append_log("✅ Настройки загружены", "success")

            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {str(e)}")
                self.append_log(f"❌ Ошибка загрузки настроек: {str(e)}", "error")

    def save_settings(self):
        """Сохраняет настройки в settings.json"""
        try:
            # ✅ ИСПОЛЬЗУЕМ СИСТЕМУ ИЗ config.py
            settings = config.extract_settings_from_ui(self)

            settings_path = os.path.join(config.BASE_DIR, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)

            self.append_log("✅ Настройки сохранены", "success")

        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {str(e)}")
            self.append_log(f"❌ Ошибка сохранения: {str(e)}", "error")

    def close_queue(self):
        # try: # Заменено
        #     self.queue_active = False # Заменено
        #     self.process_queue.close() # Заменено
        #     self.process_queue.join_thread() # Заменено
        # except Exception as e: # Заменено
        #     logger.error(f"Ошибка закрытия очереди: {str(e)}") # Заменено
        self.cpu_logic.close_queue()

    # =============== НОВОЕ: Метод обновления статуса GPU ===============
    def update_gpu_status(self):
        """Обновляет отображение аппаратного статуса GPU"""
        if not self.gpu_monitor_available or not PYNVML_AVAILABLE:
            return
        # Определяем ID устройства для мониторинга.
        # Можно брать из self.gpu_device_combo, но там может быть список.
        # Для простоты будем мониторить первое указанное устройство.
        try:
            device_str = self.gpu_device_combo.currentText().split(',')[0].strip()
            if device_str.isdigit():
                device_id = int(device_str)
            else:
                device_id = 0  # По умолчанию
        except:
            device_id = 0
        # Вызываем функцию получения статуса (можно перенести её сюда напрямую)
        # gpu_status = gpu_core.get_gpu_status(device_id) # Если функция в core/gpu_scanner.py
        # Или реализовать прямо здесь:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = util_info.gpu
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used_mb = mem_info.used / (1024 * 1024)
            mem_total_mb = mem_info.total / (1024 * 1024)
            mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0
            try:
                temp_info = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                temperature = temp_info
            except pynvml.NVMLError:
                temperature = None
            # Обновляем UI
            self.gpu_util_label.setText(f"Загрузка GPU: {gpu_util} %")
            self.gpu_util_bar.setValue(gpu_util)
            self.gpu_mem_label.setText(f"Память GPU: {mem_used_mb:.0f} / {mem_total_mb:.0f} MB ({mem_util:.1f}%)")
            self.gpu_mem_bar.setValue(int(mem_util))
            if temperature is not None:
                self.gpu_temp_label.setText(f"Температура: {temperature} °C")
                # Можно добавить цветовую индикацию температуры
                if temperature > 80:
                    self.gpu_temp_label.setStyleSheet(
                        "color: #e74c3c; font-weight: bold;")  # Красный при высокой температуре
                elif temperature > 65:
                    self.gpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")  # Оранжевый
                else:
                    self.gpu_temp_label.setStyleSheet("color: #27ae60;")  # Зеленый
            else:
                self.gpu_temp_label.setText("Температура: - °C")
                self.gpu_temp_label.setStyleSheet("color: #7f8c8d;")  # Серый
        except Exception as e:
            # logger.debug(f"Не удалось обновить статус GPU {device_id}: {e}") # Часто логгировать не нужно
            # Можно сбросить значения на "N/A" или скрыть виджеты
            self.gpu_util_label.setText("Загрузка GPU: N/A")
            self.gpu_util_bar.setValue(0)
            self.gpu_mem_label.setText("Память GPU: N/A")
            self.gpu_mem_bar.setValue(0)
            self.gpu_temp_label.setText("Температура: N/A")
            # Остановить таймер, если GPU больше не доступен? Не обязательно.
            # self.gpu_status_timer.stop() # Лучше оставить, вдруг появится снова

    # =============== КОНЕЦ НОВОГО ===============
    def closeEvent(self, event):
        """Обработка закрытия программы"""
        # ✅ Проверяем активные процессы
        active_processes = []

        if self.gpu_logic.gpu_is_running:
            active_processes.append("GPU")

        if self.cpu_logic.processes:
            active_processes.append("CPU")

        if self.kangaroo_logic.is_running:
            active_processes.append("Kangaroo")

        if self.vanity_logic.is_running:
            active_processes.append("VanitySearch")

        # ✅ Если есть активные процессы - спрашиваем подтверждение
        if active_processes:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                'Подтверждение закрытия',
                f"Активные процессы: {', '.join(active_processes)}.\n"
                f"Вы уверены, что хотите закрыть программу?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return

        # ✅ СОХРАНЯЕМ НАСТРОЙКИ ПЕРЕД ЗАКРЫТИЕМ
        self.save_settings()

        # ✅ Останавливаем все процессы
        if self.gpu_logic.gpu_is_running:
            self.gpu_logic.stop_gpu_search()

        if self.cpu_logic.processes:
            self.cpu_logic.stop_cpu_search()

        if self.kangaroo_logic.is_running:
            self.kangaroo_logic.stop_kangaroo_search()

        if self.vanity_logic.is_running:
            self.vanity_logic.stop_search()

        # ✅ Закрываем очередь CPU
        self.close_queue()

        # ✅ Останавливаем pynvml
        if PYNVML_AVAILABLE and self.gpu_monitor_available:
            try:
                pynvml.nvmlShutdown()
                logger.info("pynvml выключен")
            except Exception as e:
                logger.error(f"Ошибка выключения pynvml: {e}")

        event.accept()
