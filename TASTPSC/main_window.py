# ui/main_window.py
import os
import subprocess
import time
import json
import platform
import psutil
import multiprocessing
import queue
from PyQt5.QtCore import Qt, QTimer, QRegExp
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QRegExpValidator
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QMessageBox, QGroupBox, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMenu, QProgressBar, QCheckBox, QComboBox, QTabWidget,
                             QFileDialog, QSpinBox)
import config
from utils.helpers import setup_logger, format_time, is_coincurve_available, make_combo32
from ui.kangaroo_logic import KangarooLogic
# Добавьте после других импортов
from core.hextowif import generate_all_from_hex
# Импорт pynvml (предполагается, что он установлен)
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


class BitcoinGPUCPUScanner(QMainWindow):
    def __init__(self):
        super().__init__()

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

        # --- Инициализация ВСЕХ переменных, используемых в setup_ui и далее ---
        # GPU variables
        self.gpu_range_label = None
        # self.gpu_processes = [] # Перенесено в GPULogic
        # self.gpu_is_running = False # Перенесено в GPULogic
        # self.gpu_start_time = None # Перенесено в GPULogic
        # self.gpu_keys_checked = 0 # Перенесено в GPULogic
        # self.gpu_keys_per_second = 0 # Перенесено в GPULogic
        self.random_mode = False
        self.last_random_ranges = set()
        self.max_saved_random = 100
        # self.current_random_start = None # Перенесено в GPULogic
        # self.current_random_end = None # Перенесено в GPULogic
        self.used_ranges = set()
        # self.gpu_last_update_time = 0 # Перенесено в GPULogic
        # self.gpu_start_range_key = 0 # Перенесено в GPULogic
        # self.gpu_end_range_key = 0 # Перенесено в GPULogic
        # self.gpu_total_keys_in_range = 0 # Перенесено в GPULogic
        # Для таймера перезапуска случайного режима
        self.gpu_restart_timer = QTimer()
        # self.gpu_restart_timer.timeout.connect(self.start_gpu_random_search) # Перенесено в GPULogic
        self.gpu_restart_delay = 1000  # 1 секунда по умолчанию
        # CPU variables - ИНИЦИАЛИЗИРУЕМ РАНЬШЕ setup_ui
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)
        # self.cpu_signals = cpu_core.WorkerSignals() # Перенесено в CPULogic
        # self.processes = {} # Перенесено в CPULogic
        # self.cpu_stop_requested = False # Перенесено в CPULogic
        # self.cpu_pause_requested = False # Перенесено в CPULogic
        # self.cpu_start_time = 0 # Перенесено в CPULogic
        # self.cpu_total_scanned = 0 # Перенесено в CPULogic
        # self.cpu_total_found = 0 # Перенесено в CPULogic
        # self.workers_stats = {} # Перенесено в CPULogic
        # self.last_update_time = time.time() # Перенесено в CPULogic
        # self.start_key = 0 # Перенесено в CPULogic
        # self.end_key = 0 # Перенесено в CPULogic
        # self.total_keys = 0 # Перенесено в CPULogic
        # self.cpu_mode = "sequential" # Перенесено в CPULogic
        # self.worker_chunks = {} # Перенесено в CPULogic
        # self.queue_active = True # Перенесено в CPULogic
        # Очередь и событие остановки для CPU
        # self.process_queue = multiprocessing.Queue() # Перенесено в CPULogic
        # self.shutdown_event = multiprocessing.Event() # Перенесено в CPULogic

        # --- Инициализация логики ---
        self.gpu_logic = GPULogic(self)  # Инициализируем ДО setup_ui и setup_connections
        self.cpu_logic = CPULogic(self)
        self.kangaroo_logic = KangarooLogic(self)

        # --- Основная инициализация UI и подключений ---
        self.set_dark_theme()
        self.setup_ui()  # <-- Теперь setup_ui может безопасно использовать все инициализированные атрибуты
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
        # --- Дополнительная инициализация ---
        # Заголовок окна
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

    def set_dark_theme(self):
        # ... (оставляем как есть)
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(20, 20, 30))
        palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.Base, QColor(28, 28, 38))
        palette.setColor(QPalette.AlternateBase, QColor(38, 38, 48))
        palette.setColor(QPalette.ToolTipBase, QColor(40, 40, 45))
        palette.setColor(QPalette.ToolTipText, QColor(230, 230, 230))
        palette.setColor(QPalette.Text, QColor(220, 220, 220))
        palette.setColor(QPalette.Button, QColor(38, 38, 48))
        palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(80, 130, 180))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.PlaceholderText, QColor(120, 120, 120))
        self.setPalette(palette)
        self.setStyleSheet("""
            QWidget, QTabWidget, QTabBar, QGroupBox, QComboBox, QLineEdit, QTextEdit, QSpinBox {
                background: #181822;
                color: #F0F0F0;
                font-size: 9pt;
            }
            QTabWidget::pane { border: 1px solid #222; }
            QTabBar::tab {
                background: #252534;
                color: #F0F0F0;
                border: 1px solid #444;
                border-radius: 4px 4px 0 0;
                padding: 6px 20px;
                min-width: 120px;
            }
            QTabBar::tab:selected { background: #303054; color: #ffffff; }
            QTabBar::tab:!selected { background: #252534; color: #F0F0F0; }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 6px;
                margin-top: 1ex;
                font-weight: bold;
                background: #232332;
                color: #F0F0F0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background: transparent;
                color: #61afef;
            }
            QPushButton {
                background: #292A36;
                color: #F0F0F0;
                border: 1px solid #555;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 35px;
            }
            QPushButton:hover { background: #3a3a45; }
            QPushButton:pressed { background: #24243A; }
            QPushButton:disabled { background: #202020; color: #777; }
            QLineEdit, QTextEdit {
                background: #202030;
                color: #F0F0F0;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 6px;
                selection-background-color: #3a5680;
            }
            QComboBox {
                background: #23233B;
                color: #F0F0F0;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px;
            }
            QComboBox QAbstractItemView {
                background: #23233B;
                color: #F0F0F0;
                selection-background-color: #264080;
            }
            QTableWidget {
                background: #232332;
                color: #F0F0F0;
                gridline-color: #333;
                alternate-background-color: #222228;
                font-size: 10pt;
            }
            QHeaderView::section {
                background: #232332;
                color: #F0F0F0;
                padding: 4px;
                border: none;
                font-weight: bold;
            }
            QLabel { color: #CCCCCC; }
            QProgressBar {
                height: 25px;
                text-align: center;
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                background: #202030;
                color: #F0F0F0;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
                border-radius: 3px;
            }
            QCheckBox { color: #CCCCCC; }
        """)

    def setup_ui(self):
        # ... (оставляем как есть, но заменяем self на self.gpu_logic или self.cpu_logic где нужно)
        self.setWindowTitle("Bitcoin GPU/CPU Scanner - Улучшенная версия")
        self.resize(1200, 900)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)
        # =============== GPU TAB ===============
        gpu_tab = QWidget()
        gpu_layout = QVBoxLayout(gpu_tab)
        gpu_layout.setSpacing(10)
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
        gpu_layout.addWidget(gpu_addr_group)
        # GPU параметры
        gpu_param_group = QGroupBox("GPU: Параметры и random режим")
        gpu_param_layout = QGridLayout(gpu_param_group)
        gpu_param_layout.setSpacing(8)
        gpu_param_layout.addWidget(QLabel("GPU устройство:"), 0, 0)
        self.gpu_device_combo = QComboBox()
        self.gpu_device_combo.setEditable(True)  # <-- Ключевая строка
        self.gpu_device_combo.addItem("0")
        self.gpu_device_combo.addItem("1")
        self.gpu_device_combo.addItem("2")
        self.gpu_device_combo.addItem("0,1")
        self.gpu_device_combo.addItem("0,1,2")
        self.gpu_device_combo.addItem("0,1,2,3")
        self.gpu_device_combo.setCurrentText("0")
        gpu_param_layout.addWidget(self.gpu_device_combo, 0, 1)
        gpu_param_layout.addWidget(QLabel("Блоки:"), 0, 2)
        self.blocks_combo = make_combo32(32, 2048, 256)
        gpu_param_layout.addWidget(self.blocks_combo, 0, 3)
        gpu_param_layout.addWidget(QLabel("Потоки/блок:"), 1, 0)
        self.threads_combo = make_combo32(32, 1024, 256)
        gpu_param_layout.addWidget(self.threads_combo, 1, 1)
        gpu_param_layout.addWidget(QLabel("Точки:"), 1, 2)
        self.points_combo = make_combo32(32, 1024, 256)
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
        # --- СЖАТЫЕ КЛЮЧИ: чекбокс ---
        self.gpu_use_compressed_checkbox = QCheckBox("Использовать сжатые ключи (--use-compressed / -c)")
        self.gpu_use_compressed_checkbox.setChecked(True)
        self.gpu_use_compressed_checkbox.setToolTip(
            "✅ Ускоряет поиск в ~1.5–2× для адресов 1..., 3..., bc1...\n"
            "Использует 33-байтный публичный ключ вместо 65-байтного.\n"
            "Авто-отключается для несовместимых адресов."
        )
        gpu_param_layout.addWidget(self.gpu_use_compressed_checkbox, 4, 2, 1, 2)  # Занимает 1 ряд, 2 колонки
        # --- НОВОЕ: Воркеры на устройство ---
        gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0)  # Новый ряд (индекс 5)
        self.gpu_workers_per_device_spin = QSpinBox()
        self.gpu_workers_per_device_spin.setRange(1, 16)  # Или другой разумный максимум
        self.gpu_workers_per_device_spin.setValue(1)  # По умолчанию 1 воркер
        gpu_param_layout.addWidget(self.gpu_workers_per_device_spin, 5, 1)  # Новый ряд (индекс 5)
        # --- КОНЕЦ НОВОГО ---
        gpu_layout.addWidget(gpu_param_group)
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
        gpu_layout.addLayout(gpu_button_layout)
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
        gpu_progress_layout.addWidget(self.gpu_progress_bar, 3, 0, 1, 2)
        gpu_layout.addWidget(gpu_progress_group)
        self.gpu_progress_bar.setStyleSheet("""
                    QProgressBar {height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20;}
                    QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px;}
                """)
        self.gpu_range_label = QLabel("Текущий диапазон: -")
        self.gpu_range_label.setStyleSheet("font-weight: bold; color: #e67e22;")
        gpu_layout.addWidget(self.gpu_range_label)
        self.main_tabs.addTab(gpu_tab, "GPU Поиск")
        # =============== НОВОЕ: GPU Status Group ===============
        if PYNVML_AVAILABLE:
            self.gpu_hw_status_group = QGroupBox("GPU: Аппаратный статус")
            gpu_hw_status_layout = QGridLayout(self.gpu_hw_status_group)
            gpu_hw_status_layout.setSpacing(6)
            self.gpu_util_label = QLabel("Загрузка GPU: - %")
            self.gpu_util_label.setStyleSheet("color: #f1c40f;")  # Желтый цвет
            gpu_hw_status_layout.addWidget(self.gpu_util_label, 0, 0)
            self.gpu_mem_label = QLabel("Память GPU: - / - MB")
            self.gpu_mem_label.setStyleSheet("color: #9b59b6;")  # Фиолетовый цвет
            gpu_hw_status_layout.addWidget(self.gpu_mem_label, 0, 1)
            self.gpu_temp_label = QLabel("Температура: - °C")
            self.gpu_temp_label.setStyleSheet("color: #e74c3c;")  # Красный цвет
            gpu_hw_status_layout.addWidget(self.gpu_temp_label, 1, 0)
            # Добавляем прогресс-бары для наглядности
            self.gpu_util_bar = QProgressBar()
            self.gpu_util_bar.setRange(0, 100)
            self.gpu_util_bar.setValue(0)
            self.gpu_util_bar.setFormat("Загрузка: %p%")
            self.gpu_util_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f1c40f, stop:1 #f39c12);} /* Оранжевый градиент */
                    """)
            gpu_hw_status_layout.addWidget(self.gpu_util_bar, 2, 0)
            self.gpu_mem_bar = QProgressBar()
            self.gpu_mem_bar.setRange(0, 100)
            self.gpu_mem_bar.setValue(0)
            self.gpu_mem_bar.setFormat("Память: %p%")
            self.gpu_mem_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #8e44ad);} /* Фиолетовый градиент */
                    """)
            gpu_hw_status_layout.addWidget(self.gpu_mem_bar, 2, 1)
            gpu_layout.addWidget(self.gpu_hw_status_group)
        # =============== КОНЕЦ НОВОГО ===============
            # =============== KANGAROO TAB ===============
            kangaroo_tab = QWidget()
            kang_layout = QVBoxLayout(kangaroo_tab)
            kang_layout.setSpacing(10)
            kang_layout.setContentsMargins(10, 10, 10, 10)

            # Информация
            info_label = QLabel(
                "🦘 <b>Kangaroo Algorithm</b> - эффективный метод поиска приватных ключей "
                "в заданном диапазоне с использованием алгоритма Pollard's Kangaroo."
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet(
                "color: #3498db; font-size: 10pt; padding: 8px; background: #1a2332; border-radius: 4px;")
            kang_layout.addWidget(info_label)

            # Основные параметры
            main_params_group = QGroupBox("Основные параметры")
            main_params_layout = QGridLayout(main_params_group)
            main_params_layout.setSpacing(8)

            # Публичный ключ
            main_params_layout.addWidget(QLabel("Публичный ключ (Hex):"), 0, 0)
            self.kang_pubkey_edit = QLineEdit()
            self.kang_pubkey_edit.setPlaceholderText("02... или 03... (66 символов) или 04... (130 символов)")
            main_params_layout.addWidget(self.kang_pubkey_edit, 0, 1, 1, 3)

            # Начальный ключ
            main_params_layout.addWidget(QLabel("Начальный ключ (Hex):"), 1, 0)
            self.kang_start_key_edit = QLineEdit("1")
            self.kang_start_key_edit.setPlaceholderText("Hex значение начала диапазона")
            main_params_layout.addWidget(self.kang_start_key_edit, 1, 1)

            # Конечный ключ
            main_params_layout.addWidget(QLabel("Конечный ключ (Hex):"), 1, 2)
            self.kang_end_key_edit = QLineEdit("FFFFFFFFFFFFFFFF")
            self.kang_end_key_edit.setPlaceholderText("Hex значение конца диапазона")
            main_params_layout.addWidget(self.kang_end_key_edit, 1, 3)

            kang_layout.addWidget(main_params_group)

            # Параметры алгоритма
            algo_params_group = QGroupBox("Параметры алгоритма")
            algo_params_layout = QGridLayout(algo_params_group)
            algo_params_layout.setSpacing(8)

            # DP
            algo_params_layout.addWidget(QLabel("DP (Distinguished Point):"), 0, 0)
            self.kang_dp_spin = QSpinBox()
            self.kang_dp_spin.setRange(10, 40)
            self.kang_dp_spin.setValue(20)
            self.kang_dp_spin.setToolTip("Параметр Distinguished Point. Чем выше, тем меньше памяти, но медленнее.")
            algo_params_layout.addWidget(self.kang_dp_spin, 0, 1)

            # Grid
            algo_params_layout.addWidget(QLabel("Grid (например, 256x256):"), 0, 2)
            self.kang_grid_edit = QLineEdit("256x256")
            self.kang_grid_edit.setPlaceholderText("ВысотахШирина")
            self.kang_grid_edit.setToolTip("Размер сетки для GPU вычислений")
            algo_params_layout.addWidget(self.kang_grid_edit, 0, 3)

            # Длительность
            algo_params_layout.addWidget(QLabel("Длительность сканирования (сек):"), 1, 0)
            self.kang_duration_spin = QSpinBox()
            self.kang_duration_spin.setRange(10, 3600)
            self.kang_duration_spin.setValue(300)
            self.kang_duration_spin.setToolTip("Время работы каждой сессии")
            algo_params_layout.addWidget(self.kang_duration_spin, 1, 1)

            # Размер поддиапазона
            algo_params_layout.addWidget(QLabel("Размер поддиапазона (биты):"), 1, 2)
            self.kang_subrange_spin = QSpinBox()
            self.kang_subrange_spin.setRange(20, 64)
            self.kang_subrange_spin.setValue(32)
            self.kang_subrange_spin.setToolTip("Размер случайного поддиапазона в битах (2^N)")
            algo_params_layout.addWidget(self.kang_subrange_spin, 1, 3)

            kang_layout.addWidget(algo_params_group)

            # Пути к файлам
            paths_group = QGroupBox("Пути к файлам")
            paths_layout = QGridLayout(paths_group)
            paths_layout.setSpacing(8)

            # Путь к exe
            paths_layout.addWidget(QLabel("Etarkangaroo.exe:"), 0, 0)
            self.kang_exe_edit = QLineEdit()
            default_kang_path = os.path.join(config.BASE_DIR, "Etarkangaroo.exe")
            self.kang_exe_edit.setText(default_kang_path)
            paths_layout.addWidget(self.kang_exe_edit, 0, 1)

            self.kang_browse_exe_btn = QPushButton("📁 Обзор...")
            self.kang_browse_exe_btn.clicked.connect(self.browse_kangaroo_exe)
            self.kang_browse_exe_btn.setFixedWidth(100)
            paths_layout.addWidget(self.kang_browse_exe_btn, 0, 2)

            # Временная директория
            paths_layout.addWidget(QLabel("Временная директория:"), 1, 0)
            self.kang_temp_dir_edit = QLineEdit()
            default_temp = os.path.join(config.BASE_DIR, "kangaroo_temp")
            self.kang_temp_dir_edit.setText(default_temp)
            paths_layout.addWidget(self.kang_temp_dir_edit, 1, 1)

            self.kang_browse_temp_btn = QPushButton("📁 Обзор...")
            self.kang_browse_temp_btn.clicked.connect(self.browse_kangaroo_temp)
            self.kang_browse_temp_btn.setFixedWidth(100)
            paths_layout.addWidget(self.kang_browse_temp_btn, 1, 2)

            kang_layout.addWidget(paths_group)

            # ✨ НОВОЕ: Кнопка автонастройки (ВСТАВЬТЕ ЭТО СЮДА)
            auto_config_layout = QHBoxLayout()
            self.kang_auto_config_btn = QPushButton("🔧 Автонастройка параметров")
            self.kang_auto_config_btn.setMinimumHeight(40)
            self.kang_auto_config_btn.setStyleSheet("""
                   QPushButton {
                       background: #3498db;
                       font-weight: bold;
                       font-size: 11pt;
                   }
                   QPushButton:hover {
                       background: #2980b9;
                   }
                   QPushButton:pressed {
                       background: #21618c;
                   }
               """)
            self.kang_auto_config_btn.clicked.connect(self.kangaroo_logic.auto_configure)
            auto_config_layout.addWidget(self.kang_auto_config_btn)
            auto_config_layout.addStretch()
            kang_layout.addLayout(auto_config_layout)
            # ✨ КОНЕЦ НОВОГО
            # Кнопка запуска
            button_layout = QHBoxLayout()
            self.kang_start_stop_btn = QPushButton("🚀 Запустить Kangaroo")
            self.kang_start_stop_btn.setMinimumHeight(45)
            self.kang_start_stop_btn.setStyleSheet("""
                   QPushButton {
                       background: #27ae60;
                       font-weight: bold;
                       font-size: 12pt;
                   }
                   QPushButton:hover {
                       background: #2ecc71;
                   }
                   QPushButton:pressed {
                       background: #219653;
                   }
               """)
            self.kang_start_stop_btn.clicked.connect(self.kangaroo_logic.toggle_kangaroo_search)
            button_layout.addWidget(self.kang_start_stop_btn)
            button_layout.addStretch()
            kang_layout.addLayout(button_layout)

            # Статус и прогресс
            status_group = QGroupBox("Статус и прогресс")
            status_layout = QVBoxLayout(status_group)
            status_layout.setSpacing(6)

            status_info_layout = QHBoxLayout()
            self.kang_status_label = QLabel("Статус: Готов к запуску")
            self.kang_status_label.setStyleSheet("font-weight: bold; color: #3498db; font-size: 11pt;")
            status_info_layout.addWidget(self.kang_status_label)
            status_info_layout.addStretch()
            status_layout.addLayout(status_info_layout)

            # Информация
            info_grid = QGridLayout()
            info_grid.setSpacing(10)

            self.kang_speed_label = QLabel("Скорость: 0 MKeys/s")
            self.kang_speed_label.setStyleSheet("color: #f39c12;")
            info_grid.addWidget(self.kang_speed_label, 0, 0)

            self.kang_time_label = QLabel("Время работы: 00:00:00")
            self.kang_time_label.setStyleSheet("color: #3498db;")
            info_grid.addWidget(self.kang_time_label, 0, 1)

            self.kang_session_label = QLabel("Сессия: #0")
            self.kang_session_label.setStyleSheet("color: #9b59b6;")
            info_grid.addWidget(self.kang_session_label, 0, 2)

            status_layout.addLayout(info_grid)

            # Текущий диапазон
            self.kang_range_label = QLabel("Текущий диапазон: -")
            self.kang_range_label.setStyleSheet("color: #e67e22; font-family: 'Courier New'; font-size: 9pt;")
            self.kang_range_label.setWordWrap(True)
            status_layout.addWidget(self.kang_range_label)

            kang_layout.addWidget(status_group)

            # Справка
            help_group = QGroupBox("ℹ️ Справка")
            help_layout = QVBoxLayout(help_group)
            help_text = QLabel(
                "<b>Как использовать:</b><br>"
                "1. Введите публичный ключ в формате Hex (сжатый или несжатый)<br>"
                "2. Укажите диапазон поиска (начальный и конечный ключи)<br>"
                "3. Настройте параметры алгоритма (DP, Grid, длительность)<br>"
                "4. Убедитесь, что путь к etarkangaroo.exe правильный<br>"
                "5. Нажмите 'Запустить Kangaroo'<br><br>"
                "<b>Примечание:</b> Алгоритм будет автоматически перебирать случайные "
                "поддиапазоны внутри указанного диапазона, что увеличивает шансы находки."
            )
            help_text.setWordWrap(True)
            help_text.setStyleSheet("color: #95a5a6; font-size: 9pt;")
            help_layout.addWidget(help_text)
            help_group.setMaximumHeight(150)
            kang_layout.addWidget(help_group)

            kang_layout.addStretch()

            self.main_tabs.addTab(kangaroo_tab, "🦘 Kangaroo")
            # =============== END KANGAROO TAB ===============

        # =============== CPU TAB ===============
        cpu_tab = QWidget()
        cpu_layout = QVBoxLayout(cpu_tab)
        cpu_layout.setContentsMargins(10, 10, 10, 10)
        cpu_layout.setSpacing(10)
        # Системная информация
        sys_info_layout = QGridLayout()
        sys_info_layout.setSpacing(6)
        sys_info_layout.addWidget(QLabel("Процессор:"), 0, 0)
        self.cpu_label = QLabel(f"{multiprocessing.cpu_count()} ядер")
        sys_info_layout.addWidget(self.cpu_label, 0, 1)
        sys_info_layout.addWidget(QLabel("Память:"), 0, 2)
        self.mem_label = QLabel("")
        sys_info_layout.addWidget(self.mem_label, 0, 3)
        sys_info_layout.addWidget(QLabel("Загрузка:"), 1, 0)
        self.cpu_usage = QLabel("0%")
        sys_info_layout.addWidget(self.cpu_usage, 1, 1)
        sys_info_layout.addWidget(QLabel("Статус:"), 1, 2)
        self.cpu_status_label = QLabel("Ожидание запуска")
        sys_info_layout.addWidget(self.cpu_status_label, 1, 3)
        cpu_layout.addLayout(sys_info_layout)
        # =============== НОВОЕ: CPU Hardware Status Group ===============
        cpu_hw_status_group = QGroupBox("CPU: Аппаратный статус")
        cpu_hw_status_layout = QGridLayout(cpu_hw_status_group)
        cpu_hw_status_layout.setSpacing(6)
        self.cpu_temp_label = QLabel("Температура: - °C")
        self.cpu_temp_label.setStyleSheet("color: #e74c3c;")  # Красный цвет по умолчанию
        cpu_hw_status_layout.addWidget(self.cpu_temp_label, 0, 0)
        # Добавляем прогресс-бар для температуры (опционально)
        self.cpu_temp_bar = QProgressBar()
        self.cpu_temp_bar.setRange(0, 100)  # Диапазон от 0 до 100°C для примера
        self.cpu_temp_bar.setValue(0)
        self.cpu_temp_bar.setFormat("Темп: %p°C")
        self.cpu_temp_bar.setStyleSheet("""
                            QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);} /* Зеленый градиент */
                        """)
        cpu_hw_status_layout.addWidget(self.cpu_temp_bar, 1, 0)
        cpu_layout.addWidget(cpu_hw_status_group)
        # =============== КОНЕЦ НОВОГО ===============
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
            ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"])
        self.cpu_priority_combo.setCurrentIndex(3)  # Средний по умолчанию
        self.cpu_priority_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_priority_combo, 2, 1)
        cpu_params_layout.addWidget(cpu_scan_params_group, 2, 0, 1, 4)
        cpu_layout.addWidget(cpu_params_group)
        # CPU кнопки управления
        cpu_button_layout = QHBoxLayout()
        cpu_button_layout.setSpacing(10)
        self.cpu_start_stop_btn = QPushButton("Старт CPU (Ctrl+S)")
        self.cpu_start_stop_btn.setMinimumHeight(35)
        self.cpu_start_stop_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2ecc71;
            }
            QPushButton:pressed {
                background: #219653;
            }
        """)
        self.cpu_pause_resume_btn = QPushButton("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setMinimumHeight(35)
        self.cpu_pause_resume_btn.setStyleSheet("""
            QPushButton {
                background: #f39c12;
                color: black;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #f1c40f;
            }
            QPushButton:pressed {
                background: #e67e22;
            }
        """)
        self.cpu_pause_resume_btn.setEnabled(False)
        cpu_button_layout.addWidget(self.cpu_start_stop_btn)
        cpu_button_layout.addWidget(self.cpu_pause_resume_btn)
        cpu_layout.addLayout(cpu_button_layout)
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
        cpu_progress_layout.addWidget(self.cpu_total_progress)
        self.cpu_eta_label = QLabel("Оставшееся время: -")
        self.cpu_eta_label.setStyleSheet("color: #f39c12;")
        cpu_progress_layout.addWidget(self.cpu_eta_label)
        cpu_layout.addLayout(cpu_progress_layout)
        # CPU статистика воркеров
        cpu_layout.addWidget(QLabel("Статистика воркеров:"))
        self.cpu_workers_table = QTableWidget(0, 5)
        self.cpu_workers_table.setHorizontalHeaderLabels(["ID", "Проверено", "Найдено", "Скорость", "Прогресс"])
        self.cpu_workers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cpu_workers_table.verticalHeader().setVisible(False)
        self.cpu_workers_table.setAlternatingRowColors(True)
        cpu_layout.addWidget(self.cpu_workers_table, 1)
        self.main_tabs.addTab(cpu_tab, "CPU Поиск")
        # =============== FOUND KEYS TAB ===============
        keys_tab = QWidget()
        keys_layout = QVBoxLayout(keys_tab)
        keys_layout.setSpacing(10)
        self.found_keys_table = QTableWidget(0, 5)
        self.found_keys_table.setHorizontalHeaderLabels([
            "Время",
            "Адрес",
            "HEX ключ",
            "WIF ключ",
            "Источник"  # ← Новая колонка
        ])
        self.found_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.found_keys_table.verticalHeader().setVisible(False)
        self.found_keys_table.setAlternatingRowColors(True)
        self.found_keys_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.found_keys_table.customContextMenuRequested.connect(self.show_context_menu)
        keys_layout.addWidget(self.found_keys_table)

        export_layout = QHBoxLayout()
        self.export_keys_btn = QPushButton("Экспорт CSV")
        self.export_keys_btn.clicked.connect(self.export_keys_csv)
        export_layout.addWidget(self.export_keys_btn)
        self.save_all_btn = QPushButton("Сохранить все ключи")
        self.save_all_btn.clicked.connect(self.save_all_found_keys)
        export_layout.addWidget(self.save_all_btn)
        export_layout.addStretch()
        keys_layout.addLayout(export_layout)
        self.main_tabs.addTab(keys_tab, "Найденные ключи")
        # Добавляем вкладку конвертера
        self.setup_converter_tab()
        # =============== LOG TAB ===============
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setSpacing(10)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_output)
        log_button_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setStyleSheet("""
            QPushButton {background: #e74c3c; font-weight: bold;}
            QPushButton:hover {background: #c0392b;}
        """)
        log_button_layout.addWidget(self.clear_log_btn)
        self.open_log_btn = QPushButton("Открыть файл лога")
        self.open_log_btn.clicked.connect(self.open_log_file)
        log_button_layout.addWidget(self.open_log_btn)
        log_button_layout.addStretch()
        log_layout.addLayout(log_button_layout)
        self.main_tabs.addTab(log_tab, "Лог работы")




        # =============== ABOUT TAB ===============
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        coincurve_status = "✓ Доступна" if is_coincurve_available() else "✗ Не установлена"
        cubitcrack_status = "✓" if os.path.exists(config.CUBITCRACK_EXE) else "✗"
        about_layout.addWidget(QLabel(
            "<b>Bitcoin GPU/CPU Scanner</b><br>"
            "Версия: 5.0 (Улучшенная)<br>"
            "Автор: Jasst<br>"
            "GitHub: <a href='https://github.com/Jasst'>github.com/Jasst</a><br>"
            "<br><b>Возможности:</b><ul>"
            "<li>GPU поиск с помощью cuBitcrack</li>"
            "<li>Поддержка нескольких GPU устройств</li>"
            "<li>CPU поиск с мультипроцессингом</li>"
            "<li>Случайный и последовательный режимы</li>"
            "<li>Расширенная статистика и ETA</li>"
            "<li>Автоматическая оптимизация параметров GPU</li>"
            "<li>Управление приоритетами процессов</li>"
            "</ul>"
            f"<br><b>Статус библиотек:</b><br>"
            f"coincurve: {coincurve_status}<br>"
            f"cuBitcrack.exe: {cubitcrack_status} Найден<br>"
        ))
        self.main_tabs.addTab(about_tab, "О программе")

    def setup_connections(self):
        # GPU connections - подключаем к методам GPULogic
        self.gpu_start_stop_btn.clicked.connect(self.gpu_logic.toggle_gpu_search)
        self.gpu_optimize_btn.clicked.connect(self.gpu_logic.auto_optimize_gpu_parameters)
        # CPU connections - подключаем к методам CPULogic
        self.cpu_start_stop_btn.clicked.connect(self.cpu_logic.toggle_cpu_start_stop)
        self.cpu_pause_resume_btn.clicked.connect(self.cpu_logic.toggle_cpu_pause_resume)
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))
        # Common connections
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        # GPU timers - подключаем к методам GPULogic
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.gpu_logic.update_gpu_time_display)
        self.gpu_stats_timer.start(500)  # Увеличили частоту обновления в 2 раза
        # self.gpu_restart_timer = QTimer() # Уже создан в __init__
        # self.gpu_restart_timer.timeout.connect(self.gpu_logic.restart_gpu_random_search) # Переносим в GPULogic.setup_gpu_connections
        # CPU signals - подключаем к методам CPULogic
        # self.cpu_signals.update_stats.connect(self.handle_cpu_update_stats) # Перенесено в CPULogic
        # self.cpu_signals.log_message.connect(self.append_log) # Перенесено в CPULogic
        # self.cpu_signals.found_key.connect(self.handle_found_key) # Перенесено в CPULogic
        # self.cpu_signals.worker_finished.connect(self.cpu_worker_finished) # Перенесено в CPULogic
        # System info timer
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
        # Вызываем метод настройки специфичных для GPU соединений
        self.gpu_logic.setup_gpu_connections()  # <-- ВАЖНО: вызываем ПОСЛЕ создания gpu_restart_timer

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
        # ... (оставляем как есть)
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                # GPU settings
                self.gpu_target_edit.setText(settings.get("gpu_target", ""))
                self.gpu_start_key_edit.setText(settings.get("gpu_start_key", "1"))
                self.gpu_end_key_edit.setText(
                    settings.get("gpu_end_key", config.MAX_KEY_HEX))
                self.gpu_device_combo.setCurrentText(str(settings.get("gpu_device", "0")))
                self.blocks_combo.setCurrentText(str(settings.get("blocks", "512")))
                self.threads_combo.setCurrentText(str(settings.get("threads", "512")))
                self.points_combo.setCurrentText(str(settings.get("points", "512")))
                self.gpu_random_checkbox.setChecked(settings.get("gpu_random_mode", False))
                self.gpu_restart_interval_combo.setCurrentText(str(settings.get("gpu_restart_interval", "300")))
                self.gpu_min_range_edit.setText(str(settings.get("gpu_min_range_size", "134217728")))
                self.gpu_max_range_edit.setText(str(settings.get("gpu_max_range_size", "536870912")))
                self.gpu_priority_combo.setCurrentIndex(settings.get("gpu_priority", 0))
                # CPU settings
                self.cpu_target_edit.setText(settings.get("cpu_target", ""))
                self.cpu_start_key_edit.setText(settings.get("cpu_start_key", "1"))
                self.cpu_end_key_edit.setText(settings.get("cpu_end_key", config.MAX_KEY_HEX))
                self.cpu_prefix_spin.setValue(settings.get("cpu_prefix", 8))
                self.cpu_workers_spin.setValue(settings.get("cpu_workers", self.optimal_workers))
                self.cpu_attempts_edit.setText(str(settings.get("cpu_attempts", 10000000)))
                self.cpu_mode_combo.setCurrentIndex(1 if settings.get("cpu_mode", "sequential") == "random" else 0)
                self.cpu_priority_combo.setCurrentIndex(settings.get("cpu_priority", 3))
                self.append_log("Настройки загружены", "success")
                # Kangaroo settings
                self.kang_pubkey_edit.setText(settings.get("kang_pubkey", ""))
                self.kang_start_key_edit.setText(settings.get("kang_start_key", "1"))
                self.kang_end_key_edit.setText(settings.get("kang_end_key", "FFFFFFFFFFFFFFFF"))
                self.kang_dp_spin.setValue(settings.get("kang_dp", 20))
                self.kang_grid_edit.setText(settings.get("kang_grid", "256x256"))
                self.kang_duration_spin.setValue(settings.get("kang_duration", 300))
                self.kang_subrange_spin.setValue(settings.get("kang_subrange_bits", 32))
                self.kang_exe_edit.setText(settings.get("kang_exe_path", os.path.join(config.BASE_DIR, "Etarkangaroo.exe")))
                self.kang_temp_dir_edit.setText(settings.get("kang_temp_dir", os.path.join(config.BASE_DIR, "kangaroo_temp")))

            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {str(e)}")
                self.append_log("Ошибка загрузки настроек: " + str(e), "error")

    def save_settings(self):
        # ... (оставляем как есть)
        settings = {
            # GPU settings
            "gpu_target": self.gpu_target_edit.text(),
            "gpu_start_key": self.gpu_start_key_edit.text(),
            "gpu_end_key": self.gpu_end_key_edit.text(),
            "gpu_device": self.gpu_device_combo.currentText(),
            "blocks": self.blocks_combo.currentText(),
            "threads": self.threads_combo.currentText(),
            "points": self.points_combo.currentText(),
            "gpu_random_mode": self.gpu_random_checkbox.isChecked(),
            "gpu_restart_interval": self.gpu_restart_interval_combo.currentText(),
            "gpu_min_range_size": self.gpu_min_range_edit.text(),
            "gpu_max_range_size": self.gpu_max_range_edit.text(),
            "gpu_priority": self.gpu_priority_combo.currentIndex(),
            # CPU settings
            "cpu_target": self.cpu_target_edit.text(),
            "cpu_start_key": self.cpu_start_key_edit.text(),
            "cpu_end_key": self.cpu_end_key_edit.text(),
            "cpu_prefix": self.cpu_prefix_spin.value(),
            "cpu_workers": self.cpu_workers_spin.value(),
            "cpu_attempts": int(self.cpu_attempts_edit.text()) if self.cpu_attempts_edit.isEnabled() else 10000000,
            "cpu_mode": self.cpu_logic.cpu_mode,  # Заменено
            "cpu_priority": self.cpu_priority_combo.currentIndex(),
            # Kangaroo settings
            "kang_pubkey": self.kang_pubkey_edit.text(),
            "kang_start_key": self.kang_start_key_edit.text(),
            "kang_end_key": self.kang_end_key_edit.text(),
            "kang_dp": self.kang_dp_spin.value(),
            "kang_grid": self.kang_grid_edit.text().strip(),
            "kang_duration": self.kang_duration_spin.value(),
            "kang_subrange_bits": self.kang_subrange_spin.value(),
            "kang_exe_path": self.kang_exe_edit.text().strip(),
            "kang_temp_dir": self.kang_temp_dir_edit.text().strip(),

        }
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        try:
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
            self.append_log("Настройки сохранены", "success")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {str(e)}")
            self.append_log(f"Ошибка сохранения настроек: {str(e)}", "error")

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
        # Проверка активных процессов
        active_processes = False
        # if self.gpu_is_running: # Заменено
        if self.gpu_logic.gpu_is_running:
            active_processes = True
        # if self.processes: # Заменено
        if self.cpu_logic.processes:
            active_processes = True
        if active_processes:
            reply = QMessageBox.question(
                self, 'Подтверждение закрытия',
                "Активные процессы все еще выполняются. Вы уверены, что хотите закрыть приложение?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        if self.kangaroo_logic.is_running:
            self.kangaroo_logic.stop_kangaroo_search()
        # Корректное завершение
        self.save_settings()
        # if self.gpu_is_running: # Заменено
        #     self.stop_gpu_search() # Заменено
        if self.gpu_logic.gpu_is_running:
            self.gpu_logic.stop_gpu_search()
        # if self.processes: # Заменено
        #     self.stop_cpu_search() # Заменено
        if self.cpu_logic.processes:
            self.cpu_logic.stop_cpu_search()
        self.close_queue()
        # =============== НОВОЕ: Остановка pynvml ===============
        if PYNVML_AVAILABLE and self.gpu_monitor_available:
            try:
                pynvml.nvmlShutdown()
                logger.info("pynvml выключен.")
            except Exception as e:
                logger.error(f"Ошибка выключения pynvml: {e}")
        # =============== КОНЕЦ НОВОГО ===============
        event.accept()
