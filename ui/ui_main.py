# ui/ui_main.py
import os
import multiprocessing
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QFont, QColor, QPalette, QRegExpValidator
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QCheckBox, QComboBox, QTabWidget,
    QFileDialog, QSpinBox, QMenu, QApplication
)

import config
from utils.helpers import make_combo32, is_coincurve_available


class MainWindowUI:
    def __init__(self, parent):
        self.parent = parent

    def setup_ui(self):
        self.parent.setWindowTitle("Bitcoin GPU/CPU Scanner - Улучшенная версия")
        self.parent.resize(1200, 900)

        main_widget = QWidget()
        self.parent.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        self.parent.main_tabs = QTabWidget()
        main_layout.addWidget(self.parent.main_tabs)

        # =============== GPU TAB ===============
        gpu_tab = QWidget()
        gpu_layout = QVBoxLayout(gpu_tab)
        gpu_layout.setSpacing(10)

        # GPU адрес и диапазон
        gpu_addr_group = QGroupBox("GPU: Целевой адрес и диапазон ключей")
        gpu_addr_layout = QGridLayout(gpu_addr_group)
        gpu_addr_layout.setSpacing(8)
        gpu_addr_layout.addWidget(QLabel("BTC адрес:"), 0, 0)
        self.parent.gpu_target_edit = QLineEdit()
        self.parent.gpu_target_edit.setPlaceholderText("Введите Bitcoin адрес (1... или 3...)")
        gpu_addr_layout.addWidget(self.parent.gpu_target_edit, 0, 1, 1, 3)
        gpu_addr_layout.addWidget(QLabel("Начальный ключ (hex):"), 1, 0)
        self.parent.gpu_start_key_edit = QLineEdit("1")
        self.parent.gpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent))
        gpu_addr_layout.addWidget(self.parent.gpu_start_key_edit, 1, 1)
        gpu_addr_layout.addWidget(QLabel("Конечный ключ (hex):"), 1, 2)
        self.parent.gpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.gpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent))
        gpu_addr_layout.addWidget(self.parent.gpu_end_key_edit, 1, 3)
        gpu_layout.addWidget(gpu_addr_group)

        # GPU параметры
        gpu_param_group = QGroupBox("GPU: Параметры и random режим")
        gpu_param_layout = QGridLayout(gpu_param_group)
        gpu_param_layout.setSpacing(8)
        gpu_param_layout.addWidget(QLabel("GPU устройство:"), 0, 0)
        self.parent.gpu_device_combo = QComboBox()
        self.parent.gpu_device_combo.setEditable(True)
        self.parent.gpu_device_combo.addItem("0")
        self.parent.gpu_device_combo.addItem("1")
        self.parent.gpu_device_combo.addItem("2")
        self.parent.gpu_device_combo.addItem("0,1")
        self.parent.gpu_device_combo.addItem("0,1,2")
        self.parent.gpu_device_combo.addItem("0,1,2,3")
        self.parent.gpu_device_combo.setCurrentText("0")
        gpu_param_layout.addWidget(self.parent.gpu_device_combo, 0, 1)
        gpu_param_layout.addWidget(QLabel("Блоки:"), 0, 2)
        self.parent.blocks_combo = make_combo32(32, 2048, 256)
        gpu_param_layout.addWidget(self.parent.blocks_combo, 0, 3)
        gpu_param_layout.addWidget(QLabel("Потоки/блок:"), 1, 0)
        self.parent.threads_combo = make_combo32(32, 1024, 256)
        gpu_param_layout.addWidget(self.parent.threads_combo, 1, 1)
        gpu_param_layout.addWidget(QLabel("Точки:"), 1, 2)
        self.parent.points_combo = make_combo32(32, 1024, 256)
        gpu_param_layout.addWidget(self.parent.points_combo, 1, 3)
        self.parent.gpu_random_checkbox = QCheckBox("Случайный поиск в диапазоне")
        gpu_param_layout.addWidget(self.parent.gpu_random_checkbox, 2, 0, 1, 2)
        gpu_param_layout.addWidget(QLabel("Интервал рестарта (сек):"), 2, 2)
        self.parent.gpu_restart_interval_combo = QComboBox()
        self.parent.gpu_restart_interval_combo.addItems([str(x) for x in range(10, 3601, 10)])
        self.parent.gpu_restart_interval_combo.setCurrentText("300")
        self.parent.gpu_restart_interval_combo.setEnabled(False)
        gpu_param_layout.addWidget(self.parent.gpu_restart_interval_combo, 2, 3)
        self.parent.gpu_random_checkbox.toggled.connect(self.parent.gpu_restart_interval_combo.setEnabled)
        gpu_param_layout.addWidget(QLabel("Мин. размер диапазона:"), 3, 0)
        self.parent.gpu_min_range_edit = QLineEdit("134217728")
        self.parent.gpu_min_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self.parent))
        gpu_param_layout.addWidget(self.parent.gpu_min_range_edit, 3, 1)
        gpu_param_layout.addWidget(QLabel("Макс. размер диапазона:"), 3, 2)
        self.parent.gpu_max_range_edit = QLineEdit("536870912")
        self.parent.gpu_max_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self.parent))
        gpu_param_layout.addWidget(self.parent.gpu_max_range_edit, 3, 3)

        # Приоритет GPU
        gpu_param_layout.addWidget(QLabel("Приоритет GPU:"), 4, 0)
        self.parent.gpu_priority_combo = QComboBox()
        self.parent.gpu_priority_combo.addItems(["Нормальный", "Высокий", "Реального времени"])
        gpu_param_layout.addWidget(self.parent.gpu_priority_combo, 4, 1)

        # СЖАТЫЕ КЛЮЧИ
        self.parent.gpu_use_compressed_checkbox = QCheckBox("Использовать сжатые ключи (--use-compressed / -c)")
        self.parent.gpu_use_compressed_checkbox.setChecked(True)
        self.parent.gpu_use_compressed_checkbox.setToolTip(
            "✅ Ускоряет поиск в ~1.5–2× для адресов 1..., 3..., bc1...\n"
            "Использует 33-байтный публичный ключ вместо 65-байтного.\n"
            "Авто-отключается для несовместимых адресов."
        )
        gpu_param_layout.addWidget(self.parent.gpu_use_compressed_checkbox, 4, 2, 1, 2)

        # Воркеры на устройство
        gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0)
        self.parent.gpu_workers_per_device_spin = QSpinBox()
        self.parent.gpu_workers_per_device_spin.setRange(1, 16)
        self.parent.gpu_workers_per_device_spin.setValue(1)
        gpu_param_layout.addWidget(self.parent.gpu_workers_per_device_spin, 5, 1)

        gpu_layout.addWidget(gpu_param_group)

        # GPU кнопки
        gpu_button_layout = QHBoxLayout()
        self.parent.gpu_start_stop_btn = QPushButton("Запустить GPU поиск")
        self.parent.gpu_start_stop_btn.setStyleSheet("""
            QPushButton { background: #27ae60; font-weight: bold; font-size: 12pt;}
            QPushButton:hover {background: #2ecc71;}
            QPushButton:pressed {background: #219653;}
        """)
        self.parent.gpu_optimize_btn = QPushButton("Авто-оптимизация")
        gpu_button_layout.addWidget(self.parent.gpu_start_stop_btn)
        gpu_button_layout.addWidget(self.parent.gpu_optimize_btn)
        gpu_button_layout.addStretch()
        gpu_layout.addLayout(gpu_button_layout)

        # GPU прогресс
        gpu_progress_group = QGroupBox("GPU: Прогресс и статистика")
        gpu_progress_layout = QGridLayout(gpu_progress_group)
        self.parent.gpu_status_label = QLabel("Статус: Готов к работе")
        self.parent.gpu_status_label.setStyleSheet("font-weight: bold; color: #3498db;")
        gpu_progress_layout.addWidget(self.parent.gpu_status_label, 0, 0, 1, 2)
        self.parent.gpu_speed_label = QLabel("Скорость: 0 MKey/s")
        gpu_progress_layout.addWidget(self.parent.gpu_speed_label, 1, 0)
        self.parent.gpu_time_label = QLabel("Время работы: 00:00:00")
        gpu_progress_layout.addWidget(self.parent.gpu_time_label, 1, 1)
        self.parent.gpu_checked_label = QLabel("Проверено ключей: 0")
        gpu_progress_layout.addWidget(self.parent.gpu_checked_label, 2, 0)
        self.parent.gpu_found_label = QLabel("Найдено ключей: 0")
        self.parent.gpu_found_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        gpu_progress_layout.addWidget(self.parent.gpu_found_label, 2, 1)
        self.parent.gpu_progress_bar = QProgressBar()
        self.parent.gpu_progress_bar.setRange(0, 100)
        self.parent.gpu_progress_bar.setValue(0)
        self.parent.gpu_progress_bar.setFormat("Прогресс: неизвестен")
        gpu_progress_layout.addWidget(self.parent.gpu_progress_bar, 3, 0, 1, 2)
        gpu_layout.addWidget(gpu_progress_group)

        self.parent.gpu_progress_bar.setStyleSheet("""
            QProgressBar {height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20;}
            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px;}
        """)

        self.parent.gpu_range_label = QLabel("Текущий диапазон: -")
        self.parent.gpu_range_label.setStyleSheet("font-weight: bold; color: #e67e22;")
        gpu_layout.addWidget(self.parent.gpu_range_label)

        self.parent.main_tabs.addTab(gpu_tab, "GPU Поиск")

        # =============== GPU Status Group ===============
        try:
            import pynvml
            PYNVML_AVAILABLE = True
        except ImportError:
            PYNVML_AVAILABLE = False

        if PYNVML_AVAILABLE:
            self.parent.gpu_hw_status_group = QGroupBox("GPU: Аппаратный статус")
            gpu_hw_status_layout = QGridLayout(self.parent.gpu_hw_status_group)
            gpu_hw_status_layout.setSpacing(6)

            self.parent.gpu_util_label = QLabel("Загрузка GPU: - %")
            self.parent.gpu_util_label.setStyleSheet("color: #f1c40f;")
            gpu_hw_status_layout.addWidget(self.parent.gpu_util_label, 0, 0)

            self.parent.gpu_mem_label = QLabel("Память GPU: - / - MB")
            self.parent.gpu_mem_label.setStyleSheet("color: #9b59b6;")
            gpu_hw_status_layout.addWidget(self.parent.gpu_mem_label, 0, 1)

            self.parent.gpu_temp_label = QLabel("Температура: - °C")
            self.parent.gpu_temp_label.setStyleSheet("color: #e74c3c;")
            gpu_hw_status_layout.addWidget(self.parent.gpu_temp_label, 1, 0)

            self.parent.gpu_util_bar = QProgressBar()
            self.parent.gpu_util_bar.setRange(0, 100)
            self.parent.gpu_util_bar.setValue(0)
            self.parent.gpu_util_bar.setFormat("Загрузка: %p%")
            self.parent.gpu_util_bar.setStyleSheet("""
                QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f1c40f, stop:1 #f39c12);}
            """)
            gpu_hw_status_layout.addWidget(self.parent.gpu_util_bar, 2, 0)

            self.parent.gpu_mem_bar = QProgressBar()
            self.parent.gpu_mem_bar.setRange(0, 100)
            self.parent.gpu_mem_bar.setValue(0)
            self.parent.gpu_mem_bar.setFormat("Память: %p%")
            self.parent.gpu_mem_bar.setStyleSheet("""
                QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #8e44ad);}
            """)
            gpu_hw_status_layout.addWidget(self.parent.gpu_mem_bar, 2, 1)

            gpu_layout.addWidget(self.parent.gpu_hw_status_group)
        # =============== END GPU Status Group ===============

        # =============== KANGAROO TAB ===============
        kangaroo_tab = QWidget()
        kang_layout = QVBoxLayout(kangaroo_tab)
        kang_layout.setSpacing(10)
        kang_layout.setContentsMargins(10, 10, 10, 10)

        info_label = QLabel(
            "🦘 <b>Kangaroo Algorithm</b> - эффективный метод поиска приватных ключей "
            "в заданном диапазоне с использованием алгоритма Pollard's Kangaroo."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "color: #3498db; font-size: 10pt; padding: 8px; background: #1a2332; border-radius: 4px;"
        )
        kang_layout.addWidget(info_label)

        main_params_group = QGroupBox("Основные параметры")
        main_params_layout = QGridLayout(main_params_group)
        main_params_layout.setSpacing(8)

        main_params_layout.addWidget(QLabel("Публичный ключ (Hex):"), 0, 0)
        self.parent.kang_pubkey_edit = QLineEdit()
        self.parent.kang_pubkey_edit.setPlaceholderText("02... или 03... (66 символов) или 04... (130 символов)")
        main_params_layout.addWidget(self.parent.kang_pubkey_edit, 0, 1, 1, 3)

        main_params_layout.addWidget(QLabel("Начальный ключ (Hex):"), 1, 0)
        self.parent.kang_start_key_edit = QLineEdit("1")
        self.parent.kang_start_key_edit.setPlaceholderText("Hex значение начала диапазона")
        main_params_layout.addWidget(self.parent.kang_start_key_edit, 1, 1)

        main_params_layout.addWidget(QLabel("Конечный ключ (Hex):"), 1, 2)
        self.parent.kang_end_key_edit = QLineEdit("FFFFFFFFFFFFFFFF")
        self.parent.kang_end_key_edit.setPlaceholderText("Hex значение конца диапазона")
        main_params_layout.addWidget(self.parent.kang_end_key_edit, 1, 3)

        kang_layout.addWidget(main_params_group)

        algo_params_group = QGroupBox("Параметры алгоритма")
        algo_params_layout = QGridLayout(algo_params_group)
        algo_params_layout.setSpacing(8)

        algo_params_layout.addWidget(QLabel("DP (Distinguished Point):"), 0, 0)
        self.parent.kang_dp_spin = QSpinBox()
        self.parent.kang_dp_spin.setRange(10, 40)
        self.parent.kang_dp_spin.setValue(20)
        self.parent.kang_dp_spin.setToolTip("Параметр Distinguished Point. Чем выше, тем меньше памяти, но медленнее.")
        algo_params_layout.addWidget(self.parent.kang_dp_spin, 0, 1)

        algo_params_layout.addWidget(QLabel("Grid (например, 256x256):"), 0, 2)
        self.parent.kang_grid_edit = QLineEdit("256x256")
        self.parent.kang_grid_edit.setPlaceholderText("ВысотахШирина")
        self.parent.kang_grid_edit.setToolTip("Размер сетки для GPU вычислений")
        algo_params_layout.addWidget(self.parent.kang_grid_edit, 0, 3)

        algo_params_layout.addWidget(QLabel("Длительность сканирования (сек):"), 1, 0)
        self.parent.kang_duration_spin = QSpinBox()
        self.parent.kang_duration_spin.setRange(10, 3600)
        self.parent.kang_duration_spin.setValue(300)
        self.parent.kang_duration_spin.setToolTip("Время работы каждой сессии")
        algo_params_layout.addWidget(self.parent.kang_duration_spin, 1, 1)

        algo_params_layout.addWidget(QLabel("Размер поддиапазона (биты):"), 1, 2)
        self.parent.kang_subrange_spin = QSpinBox()
        self.parent.kang_subrange_spin.setRange(20, 64)
        self.parent.kang_subrange_spin.setValue(32)
        self.parent.kang_subrange_spin.setToolTip("Размер случайного поддиапазона в битах (2^N)")
        algo_params_layout.addWidget(self.parent.kang_subrange_spin, 1, 3)

        kang_layout.addWidget(algo_params_group)

        paths_group = QGroupBox("Пути к файлам")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setSpacing(8)

        paths_layout.addWidget(QLabel("Etarkangaroo.exe:"), 0, 0)
        self.parent.kang_exe_edit = QLineEdit()
        default_kang_path = os.path.join(config.BASE_DIR, "Etarkangaroo.exe")
        self.parent.kang_exe_edit.setText(default_kang_path)
        paths_layout.addWidget(self.parent.kang_exe_edit, 0, 1)
        self.parent.kang_browse_exe_btn = QPushButton("📁 Обзор...")
        self.parent.kang_browse_exe_btn.clicked.connect(self.parent.browse_kangaroo_exe)
        self.parent.kang_browse_exe_btn.setFixedWidth(100)
        paths_layout.addWidget(self.parent.kang_browse_exe_btn, 0, 2)

        paths_layout.addWidget(QLabel("Временная директория:"), 1, 0)
        self.parent.kang_temp_dir_edit = QLineEdit()
        default_temp = os.path.join(config.BASE_DIR, "kangaroo_temp")
        self.parent.kang_temp_dir_edit.setText(default_temp)
        paths_layout.addWidget(self.parent.kang_temp_dir_edit, 1, 1)
        self.parent.kang_browse_temp_btn = QPushButton("📁 Обзор...")
        self.parent.kang_browse_temp_btn.clicked.connect(self.parent.browse_kangaroo_temp)
        self.parent.kang_browse_temp_btn.setFixedWidth(100)
        paths_layout.addWidget(self.parent.kang_browse_temp_btn, 1, 2)

        kang_layout.addWidget(paths_group)

        auto_config_layout = QHBoxLayout()
        self.parent.kang_auto_config_btn = QPushButton("🔧 Автонастройка параметров")
        self.parent.kang_auto_config_btn.setMinimumHeight(40)
        self.parent.kang_auto_config_btn.setStyleSheet("""
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
        self.parent.kang_auto_config_btn.clicked.connect(self.parent.kangaroo_logic.auto_configure)
        auto_config_layout.addWidget(self.parent.kang_auto_config_btn)
        auto_config_layout.addStretch()
        kang_layout.addLayout(auto_config_layout)

        button_layout = QHBoxLayout()
        self.parent.kang_start_stop_btn = QPushButton("🚀 Запустить Kangaroo")
        self.parent.kang_start_stop_btn.setMinimumHeight(45)
        self.parent.kang_start_stop_btn.setStyleSheet("""
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
        self.parent.kang_start_stop_btn.clicked.connect(self.parent.kangaroo_logic.toggle_kangaroo_search)
        button_layout.addWidget(self.parent.kang_start_stop_btn)
        button_layout.addStretch()
        kang_layout.addLayout(button_layout)

        status_group = QGroupBox("Статус и прогресс")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(6)

        status_info_layout = QHBoxLayout()
        self.parent.kang_status_label = QLabel("Статус: Готов к запуску")
        self.parent.kang_status_label.setStyleSheet("font-weight: bold; color: #3498db; font-size: 11pt;")
        status_info_layout.addWidget(self.parent.kang_status_label)
        status_info_layout.addStretch()
        status_layout.addLayout(status_info_layout)

        info_grid = QGridLayout()
        info_grid.setSpacing(10)
        self.parent.kang_speed_label = QLabel("Скорость: 0 MKeys/s")
        self.parent.kang_speed_label.setStyleSheet("color: #f39c12;")
        info_grid.addWidget(self.parent.kang_speed_label, 0, 0)

        self.parent.kang_time_label = QLabel("Время работы: 00:00:00")
        self.parent.kang_time_label.setStyleSheet("color: #3498db;")
        info_grid.addWidget(self.parent.kang_time_label, 0, 1)

        self.parent.kang_session_label = QLabel("Сессия: #0")
        self.parent.kang_session_label.setStyleSheet("color: #9b59b6;")
        info_grid.addWidget(self.parent.kang_session_label, 0, 2)

        status_layout.addLayout(info_grid)

        self.parent.kang_range_label = QLabel("Текущий диапазон: -")
        self.parent.kang_range_label.setStyleSheet("color: #e67e22; font-family: 'Courier New'; font-size: 9pt;")
        self.parent.kang_range_label.setWordWrap(True)
        status_layout.addWidget(self.parent.kang_range_label)

        kang_layout.addWidget(status_group)

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
        self.parent.main_tabs.addTab(kangaroo_tab, "🦘 Kangaroo")
        # =============== END KANGAROO TAB ===============

        # =============== CPU TAB ===============
        cpu_tab = QWidget()
        cpu_layout = QVBoxLayout(cpu_tab)
        cpu_layout.setContentsMargins(10, 10, 10, 10)
        cpu_layout.setSpacing(10)

        sys_info_layout = QGridLayout()
        sys_info_layout.setSpacing(6)
        sys_info_layout.addWidget(QLabel("Процессор:"), 0, 0)
        self.parent.cpu_label = QLabel(f"{multiprocessing.cpu_count()} ядер")
        sys_info_layout.addWidget(self.parent.cpu_label, 0, 1)
        sys_info_layout.addWidget(QLabel("Память:"), 0, 2)
        self.parent.mem_label = QLabel("")
        sys_info_layout.addWidget(self.parent.mem_label, 0, 3)
        sys_info_layout.addWidget(QLabel("Загрузка:"), 1, 0)
        self.parent.cpu_usage = QLabel("0%")
        sys_info_layout.addWidget(self.parent.cpu_usage, 1, 1)
        sys_info_layout.addWidget(QLabel("Статус:"), 1, 2)
        self.parent.cpu_status_label = QLabel("Ожидание запуска")
        sys_info_layout.addWidget(self.parent.cpu_status_label, 1, 3)
        cpu_layout.addLayout(sys_info_layout)

        cpu_hw_status_group = QGroupBox("CPU: Аппаратный статус")
        cpu_hw_status_layout = QGridLayout(cpu_hw_status_group)
        cpu_hw_status_layout.setSpacing(6)
        self.parent.cpu_temp_label = QLabel("Температура: - °C")
        self.parent.cpu_temp_label.setStyleSheet("color: #e74c3c;")
        cpu_hw_status_layout.addWidget(self.parent.cpu_temp_label, 0, 0)

        self.parent.cpu_temp_bar = QProgressBar()
        self.parent.cpu_temp_bar.setRange(0, 100)
        self.parent.cpu_temp_bar.setValue(0)
        self.parent.cpu_temp_bar.setFormat("Темп: %p°C")
        self.parent.cpu_temp_bar.setStyleSheet("""
            QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
            QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);}
        """)
        cpu_hw_status_layout.addWidget(self.parent.cpu_temp_bar, 1, 0)

        cpu_layout.addWidget(cpu_hw_status_group)

        cpu_params_group = QGroupBox("CPU: Параметры поиска")
        cpu_params_layout = QGridLayout(cpu_params_group)
        cpu_params_layout.setSpacing(8)
        cpu_params_layout.setColumnStretch(1, 1)

        cpu_params_layout.addWidget(QLabel("Целевой адрес:"), 0, 0)
        self.parent.cpu_target_edit = QLineEdit()
        self.parent.cpu_target_edit.setPlaceholderText("Введите BTC адрес (1 или 3)")
        cpu_params_layout.addWidget(self.parent.cpu_target_edit, 0, 1, 1, 3)

        cpu_keys_group = QGroupBox("Диапазон ключей")
        cpu_keys_layout = QGridLayout(cpu_keys_group)
        cpu_keys_layout.addWidget(QLabel("Начальный ключ:"), 0, 0)
        self.parent.cpu_start_key_edit = QLineEdit("1")
        self.parent.cpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent))
        cpu_keys_layout.addWidget(self.parent.cpu_start_key_edit, 0, 1)
        cpu_keys_layout.addWidget(QLabel("Конечный ключ:"), 0, 2)
        self.parent.cpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.cpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent))
        cpu_keys_layout.addWidget(self.parent.cpu_end_key_edit, 0, 3)
        cpu_params_layout.addWidget(cpu_keys_group, 1, 0, 1, 4)

        cpu_scan_params_group = QGroupBox("Параметры сканирования")
        cpu_scan_params_layout = QGridLayout(cpu_scan_params_group)

        param_input_width = 120

        cpu_scan_params_layout.addWidget(QLabel("Префикс:"), 0, 0)
        self.parent.cpu_prefix_spin = QSpinBox()
        self.parent.cpu_prefix_spin.setRange(1, 20)
        self.parent.cpu_prefix_spin.setValue(8)
        self.parent.cpu_prefix_spin.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.parent.cpu_prefix_spin, 0, 1)

        cpu_scan_params_layout.addWidget(QLabel("Попыток:"), 0, 2)
        self.parent.cpu_attempts_edit = QLineEdit("10000000")
        self.parent.cpu_attempts_edit.setEnabled(False)
        self.parent.cpu_attempts_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self.parent))
        self.parent.cpu_attempts_edit.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.parent.cpu_attempts_edit, 0, 3)

        cpu_scan_params_layout.addWidget(QLabel("Режим:"), 1, 0)
        self.parent.cpu_mode_combo = QComboBox()
        self.parent.cpu_mode_combo.addItems(["Последовательный", "Случайный"])
        self.parent.cpu_mode_combo.currentIndexChanged.connect(self.parent.on_cpu_mode_changed)
        self.parent.cpu_mode_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.parent.cpu_mode_combo, 1, 1)

        cpu_scan_params_layout.addWidget(QLabel("Рабочих:"), 1, 2)
        self.parent.cpu_workers_spin = QSpinBox()
        self.parent.cpu_workers_spin.setRange(1, multiprocessing.cpu_count() * 2)
        self.parent.cpu_workers_spin.setValue(self.parent.optimal_workers)
        self.parent.cpu_workers_spin.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.parent.cpu_workers_spin, 1, 3)

        cpu_scan_params_layout.addWidget(QLabel("Приоритет:"), 2, 0)
        self.parent.cpu_priority_combo = QComboBox()
        self.parent.cpu_priority_combo.addItems(
            ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"]
        )
        self.parent.cpu_priority_combo.setCurrentIndex(3)
        self.parent.cpu_priority_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.parent.cpu_priority_combo, 2, 1)

        cpu_params_layout.addWidget(cpu_scan_params_group, 2, 0, 1, 4)
        cpu_layout.addWidget(cpu_params_group)

        cpu_button_layout = QHBoxLayout()
        cpu_button_layout.setSpacing(10)
        self.parent.cpu_start_stop_btn = QPushButton("Старт CPU (Ctrl+S)")
        self.parent.cpu_start_stop_btn.setMinimumHeight(35)
        self.parent.cpu_start_stop_btn.setStyleSheet("""
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
        self.parent.cpu_pause_resume_btn = QPushButton("Пауза (Ctrl+P)")
        self.parent.cpu_pause_resume_btn.setMinimumHeight(35)
        self.parent.cpu_pause_resume_btn.setStyleSheet("""
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
        self.parent.cpu_pause_resume_btn.setEnabled(False)
        cpu_button_layout.addWidget(self.parent.cpu_start_stop_btn)
        cpu_button_layout.addWidget(self.parent.cpu_pause_resume_btn)
        cpu_layout.addLayout(cpu_button_layout)

        cpu_progress_layout = QVBoxLayout()
        cpu_progress_layout.setSpacing(6)
        self.parent.cpu_total_stats_label = QLabel("Статус: Ожидание запуска")
        self.parent.cpu_total_stats_label.setStyleSheet("font-weight: bold; color: #3498db;")
        cpu_progress_layout.addWidget(self.parent.cpu_total_stats_label)
        self.parent.cpu_total_progress = QProgressBar()
        self.parent.cpu_total_progress.setRange(0, 100)
        self.parent.cpu_total_progress.setValue(0)
        self.parent.cpu_total_progress.setFormat("Общий прогресс: %p%")
        cpu_progress_layout.addWidget(self.parent.cpu_total_progress)
        self.parent.cpu_eta_label = QLabel("Оставшееся время: -")
        self.parent.cpu_eta_label.setStyleSheet("color: #f39c12;")
        cpu_progress_layout.addWidget(self.parent.cpu_eta_label)
        cpu_layout.addLayout(cpu_progress_layout)

        cpu_layout.addWidget(QLabel("Статистика воркеров:"))
        self.parent.cpu_workers_table = QTableWidget(0, 5)
        self.parent.cpu_workers_table.setHorizontalHeaderLabels(["ID", "Проверено", "Найдено", "Скорость", "Прогресс"])
        self.parent.cpu_workers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parent.cpu_workers_table.verticalHeader().setVisible(False)
        self.parent.cpu_workers_table.setAlternatingRowColors(True)
        cpu_layout.addWidget(self.parent.cpu_workers_table, 1)

        self.parent.main_tabs.addTab(cpu_tab, "CPU Поиск")
        # =============== END CPU TAB ===============

        # =============== VANITY TAB ===============
        vanity_tab = QWidget()
        vanity_layout = QVBoxLayout(vanity_tab)
        vanity_layout.setSpacing(10)
        vanity_layout.setContentsMargins(10, 10, 10, 10)

        # Инфо
        info_label = QLabel(
            "🎨 <b>VanitySearch</b> — генерация адресов с заданным префиксом (например: 1Jasst..., bc1qjasst...).<br>"
            "Поддержка: P2PKH (1...), P2SH (3...), Bech32 (bc1...).<br>"
            "<i>Работает только в режиме генерации (не поиск по целевому адресу).</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #f1c40f; font-size: 10pt; padding: 8px; background: #1a2332; border-radius: 4px;")
        vanity_layout.addWidget(info_label)

        # Основные параметры
        main_group = QGroupBox("Основные параметры")
        main_layout = QGridLayout(main_group)
        main_layout.setSpacing(8)

        main_layout.addWidget(QLabel("Префикс адреса:"), 0, 0)
        self.parent.vanity_prefix_edit = QLineEdit()
        self.parent.vanity_prefix_edit.setPlaceholderText("Например: 1Jasst или bc1qj")
        main_layout.addWidget(self.parent.vanity_prefix_edit, 0, 1, 1, 2)

        main_layout.addWidget(QLabel("Тип адреса:"), 1, 0)
        self.parent.vanity_type_combo = QComboBox()
        self.parent.vanity_type_combo.addItems([
            "P2PKH (1...)",
            "P2SH-P2WPKH (3...)",
            "Bech32 (bc1...)",
            "Bech32m (bc1...)"  # VanitySearch 1.19 поддерживает
        ])
        self.parent.vanity_type_combo.setCurrentIndex(0)
        main_layout.addWidget(self.parent.vanity_type_combo, 1, 1)

        main_layout.addWidget(QLabel("Сжатый ключ:"), 1, 2)
        self.parent.vanity_compressed_cb = QCheckBox()
        self.parent.vanity_compressed_cb.setChecked(True)
        main_layout.addWidget(self.parent.vanity_compressed_cb, 1, 3)

        vanity_layout.addWidget(main_group)

        # Параметры GPU/CPU
        exec_group = QGroupBox("Исполнение")
        exec_layout = QGridLayout(exec_group)
        exec_layout.setSpacing(8)

        exec_layout.addWidget(QLabel("Устройства GPU (0,1...):"), 0, 0)
        self.parent.vanity_gpu_combo = QComboBox()
        self.parent.vanity_gpu_combo.setEditable(True)
        self.parent.vanity_gpu_combo.addItems(["0", "0,1", "0,1,2", "CPU"])
        self.parent.vanity_gpu_combo.setCurrentText("0")
        exec_layout.addWidget(self.parent.vanity_gpu_combo, 0, 1)

        exec_layout.addWidget(QLabel("Потоков CPU:"), 0, 2)
        self.parent.vanity_cpu_spin = QSpinBox()
        self.parent.vanity_cpu_spin.setRange(1, multiprocessing.cpu_count())
        self.parent.vanity_cpu_spin.setValue(max(1, multiprocessing.cpu_count() - 1))
        exec_layout.addWidget(self.parent.vanity_cpu_spin, 0, 3)

        vanity_layout.addWidget(exec_group)

        # Кнопка запуска
        btn_layout = QHBoxLayout()
        self.parent.vanity_start_stop_btn = QPushButton("🚀 Запустить генерацию")
        self.parent.vanity_start_stop_btn.setMinimumHeight(45)
        self.parent.vanity_start_stop_btn.setStyleSheet("""
            QPushButton {
                background: #8e44ad;  /* фиолетовый под Vanity */
                font-weight: bold;
                font-size: 12pt;
                color: white;
            }
            QPushButton:hover { background: #9b59b6; }
            QPushButton:pressed { background: #7d3c98; }
        """)
        btn_layout.addWidget(self.parent.vanity_start_stop_btn)
        btn_layout.addStretch()
        vanity_layout.addLayout(btn_layout)

        # Прогресс
        stat_group = QGroupBox("Прогресс")
        stat_layout = QGridLayout(stat_group)
        stat_layout.setSpacing(6)

        self.parent.vanity_status_label = QLabel("Статус: Готов")
        self.parent.vanity_status_label.setStyleSheet("font-weight: bold; color: #3498db;")
        stat_layout.addWidget(self.parent.vanity_status_label, 0, 0, 1, 2)

        self.parent.vanity_speed_label = QLabel("Скорость: 0 Keys/s")
        stat_layout.addWidget(self.parent.vanity_speed_label, 1, 0)

        self.parent.vanity_time_label = QLabel("Время: 00:00:00")
        stat_layout.addWidget(self.parent.vanity_time_label, 1, 1)

        self.parent.vanity_found_label = QLabel("Найдено: 0")
        self.parent.vanity_found_label.setStyleSheet("font-weight: bold; color: #8e44ad;")
        stat_layout.addWidget(self.parent.vanity_found_label, 2, 0)

        self.parent.vanity_progress_bar = QProgressBar()
        self.parent.vanity_progress_bar.setRange(0, 0)  # indeterminate
        self.parent.vanity_progress_bar.setFormat("Работает...")
        stat_layout.addWidget(self.parent.vanity_progress_bar, 3, 0, 1, 2)

        vanity_layout.addWidget(stat_group)

        # Результат
        res_group = QGroupBox("Последний найденный адрес")
        res_layout = QGridLayout(res_group)
        self.parent.vanity_result_addr = QLineEdit()
        self.parent.vanity_result_addr.setReadOnly(True)
        self.parent.vanity_result_addr.setStyleSheet("font-weight: bold; color: #27ae60; background: #1a1a25;")
        res_layout.addWidget(QLabel("Адрес:"), 0, 0)
        res_layout.addWidget(self.parent.vanity_result_addr, 0, 1)

        self.parent.vanity_result_hex = QLineEdit()
        self.parent.vanity_result_hex.setReadOnly(True)
        self.parent.vanity_result_hex.setStyleSheet("background: #1a1a25;")
        res_layout.addWidget(QLabel("HEX:"), 1, 0)
        res_layout.addWidget(self.parent.vanity_result_hex, 1, 1)

        self.parent.vanity_result_wif = QLineEdit()
        self.parent.vanity_result_wif.setReadOnly(True)
        self.parent.vanity_result_wif.setStyleSheet("background: #1a1a25;")
        res_layout.addWidget(QLabel("WIF:"), 2, 0)
        res_layout.addWidget(self.parent.vanity_result_wif, 2, 1)

        copy_btn = QPushButton("📋 Копировать всё")
        copy_btn.clicked.connect(self.parent.copy_vanity_result)
        res_layout.addWidget(copy_btn, 3, 0, 1, 2)

        vanity_layout.addWidget(res_group, 1)

        self.parent.main_tabs.addTab(vanity_tab, "🎨 Vanity")
        # =============== END VANITY TAB ===============

        # =============== FOUND KEYS TAB ===============
        keys_tab = QWidget()
        keys_layout = QVBoxLayout(keys_tab)
        keys_layout.setSpacing(10)

        self.parent.found_keys_table = QTableWidget(0, 5)
        self.parent.found_keys_table.setHorizontalHeaderLabels([
            "Время", "Адрес", "HEX ключ", "WIF ключ", "Источник"
        ])
        self.parent.found_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parent.found_keys_table.verticalHeader().setVisible(False)
        self.parent.found_keys_table.setAlternatingRowColors(True)
        self.parent.found_keys_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.parent.found_keys_table.customContextMenuRequested.connect(self.parent.show_context_menu)
        keys_layout.addWidget(self.parent.found_keys_table)

        export_layout = QHBoxLayout()
        self.parent.export_keys_btn = QPushButton("Экспорт CSV")
        self.parent.export_keys_btn.clicked.connect(self.parent.export_keys_csv)
        export_layout.addWidget(self.parent.export_keys_btn)

        self.parent.save_all_btn = QPushButton("Сохранить все ключи")
        self.parent.save_all_btn.clicked.connect(self.parent.save_all_found_keys)
        export_layout.addWidget(self.parent.save_all_btn)
        export_layout.addStretch()

        keys_layout.addLayout(export_layout)
        self.parent.main_tabs.addTab(keys_tab, "Найденные ключи")
        # =============== END FOUND KEYS TAB ===============

        # Конвертер
        self.parent.setup_converter_tab()

        # =============== LOG TAB ===============
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setSpacing(10)

        self.parent.log_output = QTextEdit()
        self.parent.log_output.setReadOnly(True)
        self.parent.log_output.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.parent.log_output)

        log_button_layout = QHBoxLayout()
        self.parent.clear_log_btn = QPushButton("Очистить лог")
        self.parent.clear_log_btn.setStyleSheet("""
            QPushButton {background: #e74c3c; font-weight: bold;}
            QPushButton:hover {background: #c0392b;}
        """)
        log_button_layout.addWidget(self.parent.clear_log_btn)

        self.parent.open_log_btn = QPushButton("Открыть файл лога")
        self.parent.open_log_btn.clicked.connect(self.parent.open_log_file)
        log_button_layout.addWidget(self.parent.open_log_btn)
        log_button_layout.addStretch()
        log_layout.addLayout(log_button_layout)

        self.parent.main_tabs.addTab(log_tab, "Лог работы")
        # =============== END LOG TAB ===============

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
        self.parent.main_tabs.addTab(about_tab, "О программе")
        # =============== END ABOUT TAB ===============