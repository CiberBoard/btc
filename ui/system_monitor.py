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
from utils.helpers import setup_logger, validate_key_range, format_time, is_coincurve_available, make_combo32
import core.gpu_scanner as gpu_core
import core.cpu_scanner as cpu_core

# Импорт pynvml (предполагается, что он установлен)
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

logger = setup_logger()


import requests
# config.py
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Получить у @BotFather
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # Ваш личный ID или ID группы

def send_telegram_message(message: str) -> bool:
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': config.TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'  # Опционально, для форматирования
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Сообщение отправлено в Telegram")
            return True
        else:
            logger.error(f"❌ Ошибка отправки в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Исключение при отправке в Telegram: {str(e)}")
        return False
    from threading import Thread
    def send_telegram_async(message: str):
        Thread(target=send_telegram_message, args=(message,), daemon=True).start()
        send_telegram_async(telegram_message)

def process_found_key(self) -> None:
    """Обработка найденного ключа"""
    try:
        if not self.current_private_key:
            return

        wif_key = private_key_to_wif(self.current_private_key)
        found_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'address': self.current_address,
            'hex_key': self.current_private_key,
            'wif_key': wif_key,
            'source': 'GPU'
        }
        self.found_key.emit(found_data)
        self.log_message.emit(f"🔑 НАЙДЕН КЛЮЧ! Адрес: {self.current_address}", "success")

        # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        # Отправка в Telegram
        telegram_message = (
            f"🔑 *Найден приватный ключ!* \n"
            f"📅 Время: {found_data['timestamp']}\n"
            f"📍 Адрес: `{found_data['address']}`\n"
            f"🔑 HEX: `{found_data['hex_key']}`\n"
            f"🔐 WIF: `{found_data['wif_key']}`\n"
            f"🖥 Источник: {found_data['source']}"
        )
        send_telegram_message(telegram_message)
        # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

        # Сброс текущих значений
        self.current_address = None
        self.current_private_key = None

    except Exception as e:
        logger.exception("Ошибка обработки найденного ключа")
        self.log_message.emit(f"Ошибка обработки найденного ключа: {str(e)}", "error")

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
        self.gpu_processes = [] # Список кортежей (process, reader)
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
        # Для таймера перезапуска случайного режима
        self.gpu_restart_timer = QTimer()
        self.gpu_restart_timer.timeout.connect(self.start_gpu_random_search)
        self.gpu_restart_delay = 1000 # 1 секунда по умолчанию

        # CPU variables - ИНИЦИАЛИЗИРУЕМ РАНЬШЕ setup_ui
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)
        self.cpu_signals = cpu_core.WorkerSignals()
        self.processes = {} # {worker_id: process}
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
        # Очередь и событие остановки для CPU
        self.process_queue = multiprocessing.Queue()
        self.shutdown_event = multiprocessing.Event()

        # --- Основная инициализация UI и подключений ---
        self.set_dark_theme()
        self.setup_ui() # <-- Теперь setup_ui может безопасно использовать все инициализированные атрибуты
        self.setup_connections()
        self.load_settings()

        # Создаем файл для найденных ключей, если его нет
        if not os.path.exists(config.FOUND_KEYS_FILE):
            open(config.FOUND_KEYS_FILE, 'w').close()

        # --- Инициализация таймеров и системной информации ---
        # CPU queue timer
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(100) # Увеличили частоту обработки до 10 раз в секунду

        # Инициализация системной информации
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(2000)

        # =============== GPU Status Timer (если используется pynvml) ===============
        if self.gpu_monitor_available:
            self.gpu_status_timer = QTimer()
            self.gpu_status_timer.timeout.connect(self.update_gpu_status)
            self.gpu_status_timer.start(1500) # 1.5 секунды
        else:
            self.gpu_status_timer = None
        # =============== КОНЕЦ GPU Status Timer ===============

        # --- Дополнительная инициализация ---
        # Заголовок окна
        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900) # Размер окна, если не задан в setup_ui

    def set_dark_theme(self):
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
        self.gpu_device_combo.addItems([str(x) for x in range(8)])
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
        # --- НОВОЕ: Воркеры на устройство ---
        # Добавляйте это ПОСЛЕ создания gpu_param_layout и ДО добавления gpu_param_group в gpu_layout
        gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0) # Новый ряд (индекс 5)
        self.gpu_workers_per_device_spin = QSpinBox()
        self.gpu_workers_per_device_spin.setRange(1, 16) # Или другой разумный максимум
        self.gpu_workers_per_device_spin.setValue(1) # По умолчанию 1 воркер
        gpu_param_layout.addWidget(self.gpu_workers_per_device_spin, 5, 1) # Новый ряд (индекс 5)
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
        self.found_keys_table = QTableWidget(0, 4)
        self.found_keys_table.setHorizontalHeaderLabels(["Время", "Адрес", "HEX ключ", "WIF ключ"])
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
        # GPU connections
        self.gpu_start_stop_btn.clicked.connect(self.toggle_gpu_search)
        self.gpu_optimize_btn.clicked.connect(self.auto_optimize_gpu_parameters)
        # CPU connections
        self.cpu_start_stop_btn.clicked.connect(self.toggle_cpu_start_stop)
        self.cpu_pause_resume_btn.clicked.connect(self.toggle_cpu_pause_resume)
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))
        # Common connections
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        # GPU timers
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.update_gpu_time_display)
        self.gpu_stats_timer.start(500)  # Увеличили частоту обновления в 2 раза
        self.gpu_restart_timer = QTimer()
        self.gpu_restart_timer.timeout.connect(self.restart_gpu_random_search)
        # CPU signals
        self.cpu_signals.update_stats.connect(self.handle_cpu_update_stats)
        self.cpu_signals.log_message.connect(self.append_log)
        self.cpu_signals.found_key.connect(self.handle_found_key)
        self.cpu_signals.worker_finished.connect(self.cpu_worker_finished)
        # System info timer
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(2000)
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

    def on_cpu_mode_changed(self, index):
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)
        self.cpu_mode = "random" if is_random else "sequential"

    def update_system_info(self):
        try:
            # --- Существующий код обновления системной информации ---
            mem = psutil.virtual_memory()
            self.mem_label.setText(f"{mem.used // (1024 * 1024)}/{mem.total // (1024 * 1024)} MB")
            self.cpu_usage.setText(f"{psutil.cpu_percent()}%")
            if self.processes:
                status = "Работает" if not self.cpu_pause_requested else "На паузе"
                self.cpu_status_label.setText(f"{status} ({len(self.processes)} воркеров)")
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
                    self.cpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;") # Красный
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);} /* Красный градиент */
                    """)
                elif cpu_temp > 65:
                    self.cpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;") # Оранжевый
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f39c12, stop:1 #d35400);} /* Оранжевый градиент */
                    """)
                else:
                    self.cpu_temp_label.setStyleSheet("color: #27ae60;") # Зеленый
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                        QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);} /* Зеленый градиент */
                    """)
            else:
                self.cpu_temp_label.setText("Температура: N/A")
                self.cpu_temp_label.setStyleSheet("color: #7f8c8d;") # Серый
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
            self.cpu_temp_label.setStyleSheet("color: #7f8c8d;") # Серый
            self.cpu_temp_bar.setValue(0)
            self.cpu_temp_bar.setFormat("Темп: Ошибка")
            # =============== КОНЕЦ НОВОГО ===============

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
                self.blocks_combo.setCurrentText("288")
                self.threads_combo.setCurrentText("128")
                self.points_combo.setCurrentText("512")
                self.append_log("Параметры GPU оптимизированы для RTX 30/40 серии", "success")
            elif "RTX 20" in gpu_info:
                self.blocks_combo.setCurrentText("256")
                self.threads_combo.setCurrentText("128")
                self.points_combo.setCurrentText("256")
                self.append_log("Параметры GPU оптимизированы для RTX 20 серии", "success")
            else:
                # Параметры по умолчанию
                self.blocks_combo.setCurrentText("128")
                self.threads_combo.setCurrentText("64")
                self.points_combo.setCurrentText("128")
                self.append_log("Параметры GPU установлены по умолчанию", "info")
        except Exception as e:
            self.append_log(f"Ошибка оптимизации GPU: {str(e)}", "error")
            # Установка безопасных значений по умолчанию
            self.blocks_combo.setCurrentText("128")
            self.threads_combo.setCurrentText("64")
            self.points_combo.setCurrentText("128")

    def validate_gpu_inputs(self):
        address = self.gpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self, "Ошибка", "Введите корректный BTC адрес для GPU")
            return False
        # Проверка диапазона ключей
        result, error = validate_key_range(
            self.gpu_start_key_edit.text().strip(),
            self.gpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False
        # Проверка размеров диапазона
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
        """Запускает GPU поиск"""
        if not self.validate_gpu_inputs():
            return
        self.save_settings()

        if self.gpu_random_checkbox.isChecked():
            self.stop_gpu_search_internal()
            # Вызов функции из модуля core для генерации случайного диапазона
            start_key, end_key, error = gpu_core.generate_gpu_random_range(
                self.gpu_start_key_edit.text().strip(),  # global_start_hex
                self.gpu_end_key_edit.text().strip(),  # global_end_hex
                self.gpu_min_range_edit.text().strip(),  # min_range_size_str
                self.gpu_max_range_edit.text().strip(),  # max_range_size_str
                self.used_ranges,  # used_ranges (set)
                self.max_saved_random  # max_saved_random (int)
            )

            # Обработка ошибки
            if error:
                self.append_log(f"Ошибка генерации случайного диапазона: {error}", "error")
                QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать диапазон: {error}")
                return  # Прерываем запуск поиска

            if start_key is None or end_key is None:
                self.append_log("Не удалось сгенерировать случайный диапазон.", "error")
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

    def restart_gpu_random_search(self):
        """Перезапускает GPU поиск с новым случайным диапазоном"""
        if self.gpu_is_running:
            self.stop_gpu_search_internal()
        self.append_log("Перезапуск GPU поиска с новым случайным диапазоном...", "normal")
        QTimer.singleShot(1000, self.start_gpu_random_search)

    def start_gpu_random_search(self):
        """Запускает GPU поиск со случайным диапазоном"""
        if self.gpu_is_running:
            return
        # Вызов функции из модуля core для генерации случайного диапазона
        start_key, end_key, error = gpu_core.generate_gpu_random_range(
            self.gpu_start_key_edit.text().strip(),  # global_start_hex
            self.gpu_end_key_edit.text().strip(),  # global_end_hex
            self.gpu_min_range_edit.text().strip(),  # min_range_size_str
            self.gpu_max_range_edit.text().strip(),  # max_range_size_str
            self.used_ranges,  # used_ranges (set)
            self.max_saved_random  # max_saved_random (int)
        )
        # Обработка ошибки
        if error:
            self.append_log(f"Ошибка генерации случайного диапазона при перезапуске: {error}", "error")
            self.gpu_restart_timer.stop()  # Останавливаем таймер, чтобы не было бесконечных попыток
            QMessageBox.warning(self, "Ошибка", f"Не удалось сгенерировать диапазон при перезапуске: {error}")
            return
        if start_key is None or end_key is None:
            self.append_log("Не удалось сгенерировать случайный диапазон при перезапуске.", "error")
            self.gpu_restart_timer.stop()
            QMessageBox.warning(self, "Ошибка", "Не удалось сгенерировать случайный диапазон при перезапуске.")
            return
        self.update_gpu_range_label(start_key, end_key)
        self.append_log(f"Новый случайный диапазон GPU: {hex(start_key)} - {hex(end_key)}", "normal")
        self.start_gpu_search_with_range(start_key, end_key)

    def update_gpu_range_label(self, start_key, end_key):
        self.gpu_range_label.setText(
            f"Текущий диапазон: <span style='color:#f39c12'>{hex(start_key)}</span> - <span style='color:#f39c12'>{hex(end_key)}</span>")

    def start_gpu_search_with_range(self, start_key, end_key):
        """Запускает GPU поиск с указанным диапазоном"""
        target_address = self.gpu_target_edit.text().strip()

        # Сохраняем оригинальный диапазон для расчета прогресса
        self.gpu_start_range_key = start_key
        self.gpu_end_range_key = end_key
        self.gpu_total_keys_in_range = end_key - start_key + 1
        self.gpu_keys_checked = 0  # Сброс счетчика

        # Получаем выбранные устройства GPU
        devices = self.gpu_device_combo.currentText().split(',')
        if not devices:
            devices = ['0']

        # Получаем параметры
        blocks = self.blocks_combo.currentText()
        threads = self.threads_combo.currentText()
        points = self.points_combo.currentText()
        priority_index = self.gpu_priority_combo.currentIndex()

        # --- НОВОЕ ---
        # Получаем количество воркеров на устройство
        workers_per_device = self.gpu_workers_per_device_spin.value()
        total_requested_workers = len(devices) * workers_per_device

        if total_requested_workers <= 0:
            self.append_log("Количество воркеров должно быть больше 0.", "error")
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
            self.append_log(
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
                self.append_log(f"Некорректный ID устройства: {device}", "error")
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
                    self.append_log(
                        f"Пропущен воркер {worker_index_global + 1} на устройстве {device}: некорректный поддиапазон {hex(worker_start_key)}-{hex(worker_end_key)}",
                        "warning")
                    worker_index_global += 1
                    continue  # Пропускаем этот воркер

                try:
                    # Передаем УНИКАЛЬНЫЙ поддиапазон каждому воркеру
                    cuda_process, output_reader = gpu_core.start_gpu_search_with_range(
                        target_address, worker_start_key, worker_end_key, device, blocks, threads, points,
                        priority_index, self
                    )
                    # Подключаем сигналы
                    output_reader.log_message.connect(self.append_log)
                    output_reader.stats_update.connect(self.update_gpu_stats_display)  # Требует модификации (см. ниже)
                    output_reader.found_key.connect(self.handle_found_key)
                    output_reader.process_finished.connect(self.handle_gpu_search_finished)
                    output_reader.start()
                    self.gpu_processes.append((cuda_process, output_reader))
                    success_count += 1
                    logger.info(
                        f"Запущен GPU воркер {worker_local_index + 1}/{workers_per_device} (глобальный {worker_index_global + 1}/{total_requested_workers}) на устройстве {device}. Диапазон: {hex(worker_start_key)} - {hex(worker_end_key)}")
                    self.append_log(
                        f"Запущен воркер {worker_index_global + 1} на GPU {device}. Диапазон: {hex(worker_start_key)} - {hex(worker_end_key)}",
                        "normal")
                except Exception as e:
                    logger.exception(
                        f"Ошибка запуска cuBitcrack воркера {worker_local_index + 1} (глобальный {worker_index_global + 1}) на устройстве {device}")
                    self.append_log(
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
                self.gpu_progress_bar.setValue(0)
                # Прогресс теперь рассчитывается на основе агрегированных данных
                self.gpu_progress_bar.setFormat(f"Прогресс: 0% (0 / {self.gpu_total_keys_in_range:,})")
                self.gpu_start_stop_btn.setText("Остановить GPU")
                self.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
            self.append_log(f"Успешно запущено {success_count} GPU воркеров", "success")
        else:
            self.append_log("Не удалось запустить ни один GPU процесс", "error")
            # self.gpu_search_finished() # Не вызываем, так как ничего не запустилось

    def stop_gpu_search_internal(self):
        """Внутренняя остановка GPU поиска"""
        gpu_core.stop_gpu_search_internal(self.gpu_processes)
        self.gpu_is_running = False

    def stop_gpu_search(self):
        """Полная остановка GPU поиска"""
        self.gpu_restart_timer.stop()
        self.stop_gpu_search_internal()
        self.gpu_search_finished()
        self.used_ranges.clear()  # Очищаем историю диапазонов
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
        # if self.gpu_random_checkbox.isChecked() and self.gpu_restart_timer.isActive():
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
            sender_reader = self.sender()

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
                self.gpu_progress_bar.setValue(int(progress_percent))
                # Форматирование текста прогресса
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

            # Обновляем UI
            # Отображаем суммарную скорость
            self.gpu_speed_label.setText(
                f"Скорость: {self.gpu_keys_per_second:.2f} MKey/s")  # Используем агрегированную скорость
            self.gpu_checked_label.setText(f"Проверено ключей: {self.gpu_keys_checked:,}")

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
            self.gpu_time_label.setText(f"Время работы: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
            # Принудительное обновление прогресса между обновлениями статистики
            if self.gpu_total_keys_in_range > 0 and self.gpu_keys_per_second > 0:
                time_since_last_update = time.time() - self.gpu_last_update_time
                additional_keys = self.gpu_keys_per_second * time_since_last_update
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

    def gpu_search_finished(self):
        """Завершение работы GPU поиска"""
        self.gpu_is_running = False
        self.gpu_start_time = None
        self.gpu_processes = []
        self.gpu_start_stop_btn.setText("Запустить GPU поиск")
        self.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.gpu_status_label.setText("Статус: Завершено")
        # Сброс прогресс бара (исправлено)
        self.gpu_progress_bar.setValue(0)
        self.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.gpu_checked_label.setText("Проверено ключей: 0")
        self.gpu_found_label.setText("Найдено ключей: 0")
        self.append_log("GPU поиск завершен", "normal")

    # ============ CPU METHODS ============
    def validate_cpu_inputs(self):
        address = self.cpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self, "Ошибка", "Введите корректный BTC адрес для CPU")
            return False
        if not is_coincurve_available():
            QMessageBox.warning(self, "Ошибка", "Библиотека coincurve не установлена. CPU поиск недоступен.")
            return False
        # Проверка диапазона ключей
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

    def start_cpu_search(self):
        if not self.validate_cpu_inputs():
            return
        self.save_settings()
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

        # Установка приоритета процесса (Windows)
        priority_index = self.cpu_priority_combo.currentIndex()
        creationflags = config.WINDOWS_CPU_PRIORITY_MAP.get(priority_index,
                                                            0x00000020)  # NORMAL_PRIORITY_CLASS по умолчанию

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
            # Установка приоритета (для Windows)
            if platform.system() == 'Windows' and creationflags:
                try:
                    p._config['creationflags'] = creationflags
                except:
                    pass
            p.start()
            self.processes[i] = p
            # Инициализация статистики воркера
            self.workers_stats[i] = {
                'scanned': 0,
                'found': 0,
                'speed': 0,
                'progress': 0,
                'active': True
            }

        self.append_log(
            f"Запущено {workers} CPU воркеров в режиме {'случайного' if self.cpu_mode == 'random' else 'последовательного'} поиска")
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
        max_messages = 100  # Максимальное количество сообщений за одну итерацию
        max_time = 0.1  # Максимальное время обработки (сек)
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
                        self.handle_found_key(data)
                    elif msg_type == 'log':
                        self.append_log(data['message'])
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

    def handle_cpu_update_stats(self, stats):
        worker_id = stats.get('worker_id')
        if worker_id is not None:
            self.workers_stats[worker_id] = {
                'scanned': stats.get('scanned', 0),
                'found': stats.get('found', 0),
                'speed': stats.get('speed', 0),
                'progress': stats.get('progress', 0)
            }
            self.update_cpu_worker_row(worker_id)
            self.update_cpu_total_stats()

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
                eta_text = format_time(eta_seconds)
        self.cpu_eta_label.setText(f"Оставшееся время: {eta_text}")
        self.cpu_total_stats_label.setText(
            f"Всего проверено: {total_scanned:,} | Найдено: {total_found} | "
            f"Скорость: {total_speed:,.0f} keys/sec | "
            f"Средняя скорость: {avg_speed:,.0f} keys/sec | "
            f"Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
        )

    # Замените существующую функцию cpu_worker_finished на эту:
    def cpu_worker_finished(self, worker_id):
        """Обработчик завершения отдельного CPU воркера"""
        # Удаляем завершенный процесс из словаря
        if worker_id in self.processes:
            process = self.processes[worker_id]
            if process.is_alive():
                process.join(timeout=0.1)  # Небольшое ожидание завершения
            del self.processes[worker_id]

        # Проверяем, остались ли еще активные воркеры
        if not self.processes:  # Все воркеры завершены
            self.append_log("Все CPU воркеры завершили работу")
            # Восстанавливаем состояние UI
            self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
            self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.cpu_pause_resume_btn.setEnabled(False)
            self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
            self.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
            self.cpu_eta_label.setText("Оставшееся время: -")
            # Сброс статуса
            self.cpu_status_label.setText("Ожидание запуска")
            # Сброс прогресса
            self.cpu_total_progress.setValue(0)
            self.cpu_total_stats_label.setText("Статус: Завершено")

    def pause_cpu_search(self):
        self.cpu_pause_requested = True
        for worker_id, process in self.processes.items():
            if process.is_alive():
                process.terminate()
                self.append_log(f"CPU воркер {worker_id} остановлен")
        self.processes = {}
        self.append_log("CPU поиск приостановлен")
        self.cpu_pause_resume_btn.setText("Продолжить")
        self.cpu_pause_resume_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    def resume_cpu_search(self):
        self.cpu_pause_requested = False
        self.start_cpu_search()
        self.append_log("CPU поиск продолжен")
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

    # Обновленная функция stop_cpu_search
    def stop_cpu_search(self):
        cpu_core.stop_cpu_search(self.processes, self.shutdown_event)
        self.append_log("CPU поиск остановлен")
        # Восстанавливаем состояние UI
        self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.cpu_pause_resume_btn.setEnabled(False)
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
        self.cpu_eta_label.setText("Оставшееся время: -")
        self.cpu_status_label.setText("Остановлено пользователем")
        # Очищаем таблицу статистики воркеров
        self.cpu_workers_table.setRowCount(0)
        # Сброс прогресса
        self.cpu_total_progress.setValue(0)
        self.cpu_total_stats_label.setText("Статус: Остановлено")

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
            self.found_keys_table.scrollToBottom()
            self.save_found_key(key_data)
            # Определяем источник
            source = "GPU" if 'source' in key_data and key_data['source'] == 'GPU' else "CPU"
            worker_info = f" (Воркер {key_data.get('worker_id', 'N/A')})" if 'worker_id' in key_data else ""
            QMessageBox.information(
                self,
                "Ключ найден!",
                f"<b>{source}{worker_info} нашел ключ!</b><br><br>"
                f"<b>Адрес:</b> {key_data['address']}<br>"
                f"<b>HEX ключ:</b> {key_data['hex_key']}<br>"
                f"<b>WIF ключ:</b> {key_data['wif_key']}"
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
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {str(e)}")
                self.append_log("Ошибка загрузки настроек: " + str(e), "error")

    def save_settings(self):
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
            "cpu_mode": self.cpu_mode,
            "cpu_priority": self.cpu_priority_combo.currentIndex(),
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
        try:
            self.queue_active = False
            self.process_queue.close()
            self.process_queue.join_thread()
        except Exception as e:
            logger.error(f"Ошибка закрытия очереди: {str(e)}")

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
                device_id = 0 # По умолчанию
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
                    self.gpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;") # Красный при высокой температуре
                elif temperature > 65:
                    self.gpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;") # Оранжевый
                else:
                    self.gpu_temp_label.setStyleSheet("color: #27ae60;") # Зеленый
            else:
                self.gpu_temp_label.setText("Температура: - °C")
                self.gpu_temp_label.setStyleSheet("color: #7f8c8d;") # Серый

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
        if self.gpu_is_running:
            active_processes = True
        if self.processes:
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
        # Корректное завершение
        self.save_settings()
        if self.gpu_is_running:
            self.stop_gpu_search()
        if self.processes:
            self.stop_cpu_search()
        self.close_queue()
        # Корректное завершение
        self.save_settings()
        if self.gpu_is_running:
            self.stop_gpu_search()
        if self.processes:
            self.stop_cpu_search()
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

