# ui/ui_main.py
from typing import Optional, TYPE_CHECKING
import os
import multiprocessing
import logging

from PyQt6.QtCore import Qt, QRegularExpression, QSize
from PyQt6.QtGui import QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import (QAbstractItemView,
                             QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTextEdit, QGroupBox, QGridLayout,
                             QTableWidget, QHeaderView, QProgressBar, QCheckBox,
                             QComboBox, QTabWidget, QSpinBox, QMenu, QApplication,
                             QScrollArea, QFrame, QSizePolicy
                             )

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner

import config
from utils.helpers import make_combo32, is_coincurve_available
from ui.theme import apply_dark_theme, set_button_style, COLORS

logger = logging.getLogger(__name__)


class MainWindowUI:
    _MARGIN = 12
    _SPACING = 10
    _MIN_WINDOW_WIDTH = 1100
    _MIN_WINDOW_HEIGHT = 750
    _DEFAULT_WINDOW_WIDTH = 1300
    _DEFAULT_WINDOW_HEIGHT = 900

    def __init__(self, parent: 'BitcoinGPUCPUScanner'):
        self.parent = parent
        self._ui_initialized = False

    def setup_ui(self) -> None:
        self.parent.setWindowTitle("⛏️ Bitcoin GPU/CPU Scanner v5.0")
        self.parent.resize(self._DEFAULT_WINDOW_WIDTH, self._DEFAULT_WINDOW_HEIGHT)
        self.parent.setMinimumSize(self._MIN_WINDOW_WIDTH, self._MIN_WINDOW_HEIGHT)

        apply_dark_theme(self.parent)

        main_widget = QWidget()
        self.parent.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(self._MARGIN, self._MARGIN, self._MARGIN, self._MARGIN)
        main_layout.setSpacing(self._SPACING)

        self.parent.main_tabs = QTabWidget()
        self.parent.main_tabs.setObjectName("mainTabs")
        main_layout.addWidget(self.parent.main_tabs)

        # ✅ Все вкладки должны быть определены в этом классе
        self._setup_gpu_tab()
        self._setup_kangaroo_tab()      # ✅ ДОБАВЛЕНО
        self._setup_cpu_tab()           # ✅ ДОБАВЛЕНО
        self._setup_vanity_tab()        # ✅ ДОБАВЛЕНО
        self._setup_found_keys_tab()    # ✅ ДОБАВЛЕНО
        self.parent.setup_converter_tab()
        self._setup_log_tab()           # ✅ ДОБАВЛЕНО
        self._setup_predict_tab()       # ✅ ДОБАВЛЕНО
        self._setup_about_tab()         # ✅ ДОБАВЛЕНО

        self._ui_initialized = True


    # ─────────────────────────────────────────────────────
    # ВСПОМОГАТЕЛЬНЫЙ МЕТОД: Заполнение списка GPU
    # ─────────────────────────────────────────────────────
    def _populate_gpu_combo(self) -> None:
        if not hasattr(self.parent, 'gpu_device_combo'):
            logger.warning("gpu_device_combo ещё не создан, пропускаем заполнение")
            return

        self.parent.gpu_device_combo.clear()

        if not getattr(self.parent, 'gpu_monitor_available', False):
            self.parent.gpu_device_combo.addItems(["0", "1", "2"])
            return

        try:
            import pynvml
            device_count = pynvml.nvmlDeviceGetCount()
            for idx in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                raw_name = pynvml.nvmlDeviceGetName(handle)
                gpu_name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name
                self.parent.gpu_device_combo.addItem(f"{idx} - {gpu_name}", userData=idx)

            if device_count >= 2:
                self.parent.gpu_device_combo.addItem("0,1 (Multi-GPU)", userData=0)
            if device_count >= 3:
                self.parent.gpu_device_combo.addItem("0,1,2 (Multi-GPU)", userData=0)

        except Exception as e:
            logger.error(f"Не удалось получить список GPU: {e}")
            self.parent.gpu_device_combo.addItems(["0", "1", "2"])


    # ─────────────────────────────────────────────────────
    # GPU TAB
    # ─────────────────────────────────────────────────────
    def _setup_gpu_tab(self) -> None:  # 🛠 УЛУЧШЕНИЕ 6: Добавлен тип возврата
        gpu_tab = QWidget()
        gpu_layout = QVBoxLayout(gpu_tab)
        gpu_layout.setContentsMargins(10, 10, 10, 10)
        gpu_layout.setSpacing(10)

        header = QLabel("🎮 GPU Поиск приватных ключей")
        header.setProperty("cssClass", "header")
        gpu_layout.addWidget(header)

        # ── Целевой адрес и диапазон ──────────────────────
        addr_group = QGroupBox("🎯 Цель и диапазон")
        addr_layout = QGridLayout(addr_group)
        addr_layout.setSpacing(10)
        addr_layout.setColumnStretch(1, 2)
        addr_layout.setColumnStretch(3, 2)

        addr_layout.addWidget(QLabel("BTC адрес:"), 0, 0)
        self.parent.gpu_target_edit = QLineEdit()
        self.parent.gpu_target_edit.setPlaceholderText("1ABC... или 3XYZ... или bc1q...")
        addr_layout.addWidget(self.parent.gpu_target_edit, 0, 1, 1, 3)

        addr_layout.addWidget(QLabel("Начало (hex):"), 1, 0)
        self.parent.gpu_start_key_edit = QLineEdit("1")
        self.parent.gpu_start_key_edit.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]+"), self.parent))
        addr_layout.addWidget(self.parent.gpu_start_key_edit, 1, 1)

        addr_layout.addWidget(QLabel("Конец (hex):"), 1, 2)
        self.parent.gpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.gpu_end_key_edit.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]+"), self.parent))
        addr_layout.addWidget(self.parent.gpu_end_key_edit, 1, 3)

        gpu_layout.addWidget(addr_group)

        # ── Параметры GPU ─────────────────────────────────
        params_group = QGroupBox("⚙️ Параметры сканирования")
        params_layout = QGridLayout(params_group)
        params_layout.setSpacing(10)
        params_layout.setColumnStretch(1, 1)
        params_layout.setColumnStretch(3, 1)

        # Ряд 1
        params_layout.addWidget(QLabel("GPU:"), 0, 0)
        self.parent.gpu_device_combo = QComboBox()
        self.parent.gpu_device_combo.setEditable(True)
        # ✅ Стало (динамическое заполнение с userData):
        self.parent.gpu_device_combo.clear()
        try:
            import pynvml
            device_count = pynvml.nvmlDeviceGetCount()
            for idx in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                raw_name = pynvml.nvmlDeviceGetName(handle)
                gpu_name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name
                # 🔧 Ключевое: сохраняем реальный NVML-индекс в userData
                self.parent.gpu_device_combo.addItem(f"{idx} - {gpu_name}", userData=idx)

            # Опции для мульти-GPU (используют первый индекс для мониторинга)
            if device_count >= 2:
                self.parent.gpu_device_combo.addItem("0,1 (Multi-GPU)", userData=0)
            if device_count >= 3:
                self.parent.gpu_device_combo.addItem("0,1,2 (Multi-GPU)", userData=0)

            self.parent.gpu_device_combo.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Не удалось получить список GPU: {e}")
            self.parent.gpu_device_combo.addItems(["0", "1", "2"])
        self.parent.gpu_device_combo.setCurrentText("0")
        params_layout.addWidget(self.parent.gpu_device_combo, 0, 1)

        params_layout.addWidget(QLabel("Блоки:"), 0, 2)
        self.parent.blocks_combo = make_combo32(32, 2048, 256)
        params_layout.addWidget(self.parent.blocks_combo, 0, 3)

        # Ряд 2
        params_layout.addWidget(QLabel("Потоки/блок:"), 1, 0)
        self.parent.threads_combo = make_combo32(32, 1024, 256)
        params_layout.addWidget(self.parent.threads_combo, 1, 1)

        params_layout.addWidget(QLabel("Точки:"), 1, 2)
        self.parent.points_combo = make_combo32(32, 1024, 256)
        params_layout.addWidget(self.parent.points_combo, 1, 3)

        # Ряд 3: Случайный режим
        self.parent.gpu_random_checkbox = QCheckBox("🎲 Случайный поиск в диапазоне")
        params_layout.addWidget(self.parent.gpu_random_checkbox, 2, 0, 1, 2)

        params_layout.addWidget(QLabel("Рестарт (сек):"), 2, 2)
        self.parent.gpu_restart_interval_combo = QComboBox()
        self.parent.gpu_restart_interval_combo.addItems([str(x) for x in range(10, 3601, 10)])
        self.parent.gpu_restart_interval_combo.setCurrentText("300")
        self.parent.gpu_restart_interval_combo.setEnabled(False)
        params_layout.addWidget(self.parent.gpu_restart_interval_combo, 2, 3)
        # 🛠 УЛУЧШЕНИЕ 7: Использование lambda для передачи аргумента в connect
        self.parent.gpu_random_checkbox.toggled.connect(
            lambda checked: self.parent.gpu_restart_interval_combo.setEnabled(checked)
        )

        # Ряд 4: Размер диапазона
        params_layout.addWidget(QLabel("Мин. диапазон:"), 3, 0)
        self.parent.gpu_min_range_edit = QLineEdit("134217728")
        self.parent.gpu_min_range_edit.setValidator(QRegularExpressionValidator(QRegularExpression("\\d+"), self.parent))
        params_layout.addWidget(self.parent.gpu_min_range_edit, 3, 1)

        params_layout.addWidget(QLabel("Макс. диапазон:"), 3, 2)
        self.parent.gpu_max_range_edit = QLineEdit("536870912")
        self.parent.gpu_max_range_edit.setValidator(QRegularExpressionValidator(QRegularExpression("\\d+"), self.parent))
        params_layout.addWidget(self.parent.gpu_max_range_edit, 3, 3)

        # Ряд 5
        params_layout.addWidget(QLabel("Приоритет:"), 4, 0)
        self.parent.gpu_priority_combo = QComboBox()
        self.parent.gpu_priority_combo.addItems(["Нормальный", "Высокий", "Реального времени"])
        params_layout.addWidget(self.parent.gpu_priority_combo, 4, 1)

        self.parent.gpu_use_compressed_checkbox = QCheckBox("✅ Сжатые ключи (×1.5–2 быстрее)")
        self.parent.gpu_use_compressed_checkbox.setChecked(True)
        self.parent.gpu_use_compressed_checkbox.setToolTip(
            "Использует 33-байтный публичный ключ вместо 65-байтного.\n"
            "Авто-отключается для несовместимых адресов."
        )
        params_layout.addWidget(self.parent.gpu_use_compressed_checkbox, 4, 2, 1, 2)

        # Ряд 6
        params_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0)
        self.parent.gpu_workers_per_device_spin = QSpinBox()
        self.parent.gpu_workers_per_device_spin.setRange(1, 16)
        self.parent.gpu_workers_per_device_spin.setValue(1)
        params_layout.addWidget(self.parent.gpu_workers_per_device_spin, 5, 1)

        gpu_layout.addWidget(params_group)

        # ── Кнопки управления ─────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.parent.gpu_start_stop_btn = QPushButton("▶ Запустить GPU")
        set_button_style(self.parent.gpu_start_stop_btn, "success")
        self.parent.gpu_start_stop_btn.setMinimumHeight(42)
        # ✅ Стало (PyQt6)
        self.parent.gpu_start_stop_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.parent.gpu_optimize_btn = QPushButton("⚡ Авто-оптимизация")
        set_button_style(self.parent.gpu_optimize_btn, "primary")
        self.parent.gpu_optimize_btn.setMinimumHeight(42)
        # Добавьте подключение (если ещё нет):
        self.parent.gpu_optimize_btn.clicked.connect(self.parent.gpu_logic.auto_optimize_gpu_parameters)

        btn_row.addWidget(self.parent.gpu_start_stop_btn)
        btn_row.addWidget(self.parent.gpu_optimize_btn)

        # 🔽 Монитор GPU
        self.parent.gpu_monitor_btn = QPushButton("📊 Монитор")
        self.parent.gpu_monitor_btn.setFixedWidth(100)
        self.parent.gpu_monitor_btn.setMinimumHeight(40)
        self.parent.gpu_monitor_btn.setStyleSheet("""
            QPushButton { background: #9b59b6; color: white; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background: #8e44ad; }
            QPushButton:pressed { background: #7d3c98; }
        """)
        self.parent.gpu_monitor_btn.clicked.connect(self.parent.open_gpu_monitor)
        btn_row.addWidget(self.parent.gpu_monitor_btn)
        # 👇 ВСТАВЬТЕ СЮДА:
        self.parent.gpu_progress_btn = QPushButton("💾 Прогресс")
        self.parent.gpu_progress_btn.setFixedWidth(100)
        self.parent.gpu_progress_btn.setMinimumHeight(40)
        self.parent.gpu_progress_btn.setStyleSheet("""
            QPushButton { background: #2c3e50; color: white; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background: #34495e; }
            QPushButton:pressed { background: #1a252f; }
        """)
        self.parent.gpu_progress_btn.clicked.connect(self.parent.open_gpu_progress_tracker)
        btn_row.addWidget(self.parent.gpu_progress_btn)
        # 👆 КОНЕЦ ВСТАВКИ
        btn_row.addStretch()
        gpu_layout.addLayout(btn_row)



        # ── Прогресс и статистика ─────────────────────────
        progress_group = QGroupBox("📊 Статистика")
        progress_layout = QGridLayout(progress_group)
        progress_layout.setSpacing(8)

        self.parent.gpu_status_label = QLabel("🟢 Статус: Готов")
        self.parent.gpu_status_label.setProperty("cssClass", "status")
        progress_layout.addWidget(self.parent.gpu_status_label, 0, 0, 1, 2)

        self.parent.gpu_speed_label = QLabel("⚡ Скорость: 0 MKey/s")
        self.parent.gpu_speed_label.setProperty("cssClass", "speed")
        progress_layout.addWidget(self.parent.gpu_speed_label, 1, 0)

        self.parent.gpu_time_label = QLabel("⏱ Время: 00:00:00")
        progress_layout.addWidget(self.parent.gpu_time_label, 1, 1)

        self.parent.gpu_checked_label = QLabel("🔍 Проверено: 0")
        progress_layout.addWidget(self.parent.gpu_checked_label, 2, 0)

        self.parent.gpu_found_label = QLabel("✨ Найдено: 0")
        self.parent.gpu_found_label.setProperty("cssClass", "found")
        progress_layout.addWidget(self.parent.gpu_found_label, 2, 1)

        self.parent.gpu_progress_bar = QProgressBar()
        self.parent.gpu_progress_bar.setRange(0, 100)
        self.parent.gpu_progress_bar.setValue(0)
        self.parent.gpu_progress_bar.setFormat("Прогресс: %p%")
        progress_layout.addWidget(self.parent.gpu_progress_bar, 3, 0, 1, 2)

        gpu_layout.addWidget(progress_group)

        self.parent.gpu_range_label = QLabel("📐 Диапазон: —")
        self.parent.gpu_range_label.setProperty("cssClass", "range")
        self.parent.gpu_range_label.setWordWrap(True)
        gpu_layout.addWidget(self.parent.gpu_range_label)

        # ── Аппаратный мониторинг (если доступен) ─────────
        # 🛠 УЛУЧШЕНИЕ 8: Проверка PYNVML_AVAILABLE вынесена из try/except
        PYNVML_AVAILABLE = False
        try:
            import pynvml
            PYNVML_AVAILABLE = True
        except ImportError:
            pass  # 🛠 УЛУЧШЕНИЕ 9: Явный pass вместо молчаливого игнорирования

        if PYNVML_AVAILABLE:
            hw_group = QGroupBox("🌡 Аппаратный статус")
            hw_layout = QGridLayout(hw_group)
            hw_layout.setSpacing(8)

            self.parent.gpu_util_label = QLabel("Загрузка: —%")
            self.parent.gpu_util_label.setProperty("cssClass", "util")
            hw_layout.addWidget(self.parent.gpu_util_label, 0, 0)

            self.parent.gpu_mem_label = QLabel("Память: — / — MB")
            self.parent.gpu_mem_label.setProperty("cssClass", "mem")
            hw_layout.addWidget(self.parent.gpu_mem_label, 0, 1)

            self.parent.gpu_temp_label = QLabel("Темп: —°C")
            self.parent.gpu_temp_label.setProperty("cssClass", "temp")
            hw_layout.addWidget(self.parent.gpu_temp_label, 1, 0)

            self.parent.gpu_util_bar = QProgressBar()
            self.parent.gpu_util_bar.setRange(0, 100)
            self.parent.gpu_util_bar.setValue(0)
            self.parent.gpu_util_bar.setFormat("%p%")
            hw_layout.addWidget(self.parent.gpu_util_bar, 2, 0)

            self.parent.gpu_mem_bar = QProgressBar()
            self.parent.gpu_mem_bar.setRange(0, 100)
            self.parent.gpu_mem_bar.setValue(0)
            self.parent.gpu_mem_bar.setFormat("%p%")
            hw_layout.addWidget(self.parent.gpu_mem_bar, 2, 1)

            gpu_layout.addWidget(hw_group)

        gpu_layout.addStretch()
        self.parent.main_tabs.addTab(gpu_tab, "🎮 GPU")

    # ─────────────────────────────────────────────────────
    # KANGAROO TAB
    # ─────────────────────────────────────────────────────
    def _setup_kangaroo_tab(self) -> None:
        kangaroo_tab = QWidget()
        kang_layout = QVBoxLayout(kangaroo_tab)
        kang_layout.setContentsMargins(12, 12, 12, 12)
        kang_layout.setSpacing(10)

        info = QLabel(
            "🦘 <b>Kangaroo Algorithm</b><br>"
            "Эффективный поиск ключей в диапазоне через Pollard's Kangaroo.<br>"
            "<i>Работает с Etarkangaroo.exe — убедитесь, что путь указан верно.</i>"
        )
        info.setWordWrap(True)
        info.setProperty("cssClass", "info-box")
        kang_layout.addWidget(info)

        main_params = QGroupBox("🔑 Основные параметры")
        mp_layout = QGridLayout(main_params)
        mp_layout.setSpacing(10)
        mp_layout.setColumnStretch(1, 2)
        mp_layout.setColumnStretch(3, 2)

        mp_layout.addWidget(QLabel("Публичный ключ (Hex):"), 0, 0)
        self.parent.kang_pubkey_edit = QLineEdit()
        self.parent.kang_pubkey_edit.setPlaceholderText("02.../03... (66) или 04... (130 символов)")
        mp_layout.addWidget(self.parent.kang_pubkey_edit, 0, 1, 1, 3)

        mp_layout.addWidget(QLabel("Начало диапазона:"), 1, 0)
        self.parent.kang_start_key_edit = QLineEdit("1")
        self.parent.kang_start_key_edit.setPlaceholderText("Hex")
        mp_layout.addWidget(self.parent.kang_start_key_edit, 1, 1)

        mp_layout.addWidget(QLabel("Конец диапазона:"), 1, 2)
        self.parent.kang_end_key_edit = QLineEdit("FFFFFFFFFFFFFFFF")
        self.parent.kang_end_key_edit.setPlaceholderText("Hex")
        mp_layout.addWidget(self.parent.kang_end_key_edit, 1, 3)

        kang_layout.addWidget(main_params)

        algo_params = QGroupBox("⚙️ Алгоритм")
        ap_layout = QGridLayout(algo_params)
        ap_layout.setSpacing(10)
        ap_layout.setColumnStretch(1, 1)
        ap_layout.setColumnStretch(3, 1)

        ap_layout.addWidget(QLabel("DP (Distinguished Point):"), 0, 0)
        self.parent.kang_dp_spin = QSpinBox()
        self.parent.kang_dp_spin.setRange(10, 40)
        self.parent.kang_dp_spin.setValue(20)
        ap_layout.addWidget(self.parent.kang_dp_spin, 0, 1)

        ap_layout.addWidget(QLabel("Grid (H×W):"), 0, 2)
        self.parent.kang_grid_edit = QLineEdit("256x256")
        ap_layout.addWidget(self.parent.kang_grid_edit, 0, 3)

        ap_layout.addWidget(QLabel("Длительность (сек):"), 1, 0)
        self.parent.kang_duration_spin = QSpinBox()
        self.parent.kang_duration_spin.setRange(10, 3600)
        self.parent.kang_duration_spin.setValue(300)
        ap_layout.addWidget(self.parent.kang_duration_spin, 1, 1)

        ap_layout.addWidget(QLabel("Поддиапазон (биты):"), 1, 2)
        self.parent.kang_subrange_spin = QSpinBox()
        self.parent.kang_subrange_spin.setRange(20, 64)
        self.parent.kang_subrange_spin.setValue(32)
        ap_layout.addWidget(self.parent.kang_subrange_spin, 1, 3)

        kang_layout.addWidget(algo_params)

        # Пути
        paths = QGroupBox("📁 Пути")
        pl = QGridLayout(paths)
        pl.setSpacing(10)

        pl.addWidget(QLabel("Etarkangaroo.exe:"), 0, 0)
        self.parent.kang_exe_edit = QLineEdit()
        self.parent.kang_exe_edit.setText(os.path.join(config.BASE_DIR, "Etarkangaroo.exe"))
        pl.addWidget(self.parent.kang_exe_edit, 0, 1)
        self.parent.kang_browse_exe_btn = QPushButton("📁")
        self.parent.kang_browse_exe_btn.setFixedWidth(40)
        self.parent.kang_browse_exe_btn.clicked.connect(self.parent.browse_kangaroo_exe)
        pl.addWidget(self.parent.kang_browse_exe_btn, 0, 2)

        pl.addWidget(QLabel("Temp директория:"), 1, 0)
        self.parent.kang_temp_dir_edit = QLineEdit()
        self.parent.kang_temp_dir_edit.setText(os.path.join(config.BASE_DIR, "kangaroo_temp"))
        pl.addWidget(self.parent.kang_temp_dir_edit, 1, 1)
        self.parent.kang_browse_temp_btn = QPushButton("📁")
        self.parent.kang_browse_temp_btn.setFixedWidth(40)
        self.parent.kang_browse_temp_btn.clicked.connect(self.parent.browse_kangaroo_temp)
        pl.addWidget(self.parent.kang_browse_temp_btn, 1, 2)

        kang_layout.addWidget(paths)

        # Автонастройка + запуск
        auto_row = QHBoxLayout()
        self.parent.kang_auto_config_btn = QPushButton("🔧 Автонастройка")
        set_button_style(self.parent.kang_auto_config_btn, "primary")
        self.parent.kang_auto_config_btn.setMinimumHeight(38)
        self.parent.kang_auto_config_btn.clicked.connect(self.parent.kangaroo_logic.auto_configure)
        auto_row.addWidget(self.parent.kang_auto_config_btn)
        auto_row.addStretch()
        kang_layout.addLayout(auto_row)

        start_row = QHBoxLayout()
        self.parent.kang_start_stop_btn = QPushButton("🚀 Запустить Kangaroo")
        set_button_style(self.parent.kang_start_stop_btn, "success")
        self.parent.kang_start_stop_btn.setMinimumHeight(48)
        self.parent.kang_start_stop_btn.clicked.connect(self.parent.kangaroo_logic.toggle_kangaroo_search)
        start_row.addWidget(self.parent.kang_start_stop_btn)
        start_row.addStretch()
        kang_layout.addLayout(start_row)

        # Статус
        status = QGroupBox("📊 Прогресс")
        sl = QVBoxLayout(status)
        sl.setSpacing(6)

        info_row = QHBoxLayout()
        self.parent.kang_status_label = QLabel("🟢 Готов к запуску")
        self.parent.kang_status_label.setProperty("cssClass", "status")
        info_row.addWidget(self.parent.kang_status_label)
        info_row.addStretch()
        sl.addLayout(info_row)

        stats = QGridLayout()
        stats.setSpacing(10)
        self.parent.kang_speed_label = QLabel("⚡ 0 MKeys/s")
        self.parent.kang_speed_label.setProperty("cssClass", "speed")
        stats.addWidget(self.parent.kang_speed_label, 0, 0)
        self.parent.kang_time_label = QLabel("⏱ 00:00:00")
        stats.addWidget(self.parent.kang_time_label, 0, 1)
        self.parent.kang_session_label = QLabel("🔄 Сессия: #0")
        stats.addWidget(self.parent.kang_session_label, 0, 2)
        sl.addLayout(stats)

        self.parent.kang_range_label = QLabel("📐 Диапазон: —")
        self.parent.kang_range_label.setProperty("cssClass", "range")
        self.parent.kang_range_label.setWordWrap(True)
        sl.addWidget(self.parent.kang_range_label)

        kang_layout.addWidget(status)

        # Справка
        help_box = QGroupBox("ℹ️ Справка")
        help_box.setMaximumHeight(140)
        hl = QVBoxLayout(help_box)
        help_text = QLabel(
            "<b>Как использовать:</b><br>"
            "1. Введите публичный ключ (Hex)<br>"
            "2. Укажите диапазон поиска<br>"
            "3. Настройте параметры<br>"
            "4. Проверьте путь к Etarkangaroo.exe<br>"
            "5. Нажмите «Запустить»"
        )
        help_text.setWordWrap(True)
        help_text.setProperty("cssClass", "info")
        hl.addWidget(help_text)
        kang_layout.addWidget(help_box)

        kang_layout.addStretch()
        self.parent.main_tabs.addTab(kangaroo_tab, "🦘 Kangaroo")

    # ─────────────────────────────────────────────────────
    # CPU TAB (с защитой от наезжания)
    # ─────────────────────────────────────────────────────
    def _setup_cpu_tab(self) -> None:
        cpu_tab = QWidget()
        cpu_layout = QVBoxLayout(cpu_tab)
        cpu_layout.setContentsMargins(10, 10, 10, 10)
        cpu_layout.setSpacing(10)

        # Системная информация
        sys_info = QGroupBox("💻 Система")
        si_layout = QGridLayout(sys_info)
        si_layout.setSpacing(8)
        si_layout.addWidget(QLabel("Процессор:"), 0, 0)
        self.parent.cpu_label = QLabel(f"{multiprocessing.cpu_count()} ядер")
        si_layout.addWidget(self.parent.cpu_label, 0, 1)
        si_layout.addWidget(QLabel("Память:"), 0, 2)
        self.parent.mem_label = QLabel("")
        si_layout.addWidget(self.parent.mem_label, 0, 3)
        si_layout.addWidget(QLabel("Загрузка:"), 1, 0)
        self.parent.cpu_usage = QLabel("0%")
        si_layout.addWidget(self.parent.cpu_usage, 1, 1)
        si_layout.addWidget(QLabel("Статус:"), 1, 2)
        self.parent.cpu_status_label = QLabel("🟡 Ожидание")
        si_layout.addWidget(self.parent.cpu_status_label, 1, 3)
        cpu_layout.addWidget(sys_info)

        # Параметры CPU
        params_cpu = QGroupBox("⚙️ Параметры CPU")
        pc_layout = QGridLayout(params_cpu)
        pc_layout.setSpacing(10)
        pc_layout.setColumnStretch(1, 2)
        pc_layout.setColumnStretch(3, 2)

        pc_layout.addWidget(QLabel("Целевой адрес:"), 0, 0)
        self.parent.cpu_target_edit = QLineEdit()
        self.parent.cpu_target_edit.setPlaceholderText("1... или 3...")
        pc_layout.addWidget(self.parent.cpu_target_edit, 0, 1, 1, 3)

        keys_group = QGroupBox("Диапазон ключей")
        kg_layout = QGridLayout(keys_group)
        kg_layout.addWidget(QLabel("Начало:"), 0, 0)
        self.parent.cpu_start_key_edit = QLineEdit("1")
        self.parent.cpu_start_key_edit.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]+"), self.parent))
        kg_layout.addWidget(self.parent.cpu_start_key_edit, 0, 1)
        kg_layout.addWidget(QLabel("Конец:"), 0, 2)
        self.parent.cpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.cpu_end_key_edit.setValidator(QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]+"), self.parent))
        kg_layout.addWidget(self.parent.cpu_end_key_edit, 0, 3)
        pc_layout.addWidget(keys_group, 1, 0, 1, 4)

        scan_params = QGroupBox("Сканирование")
        sp_layout = QGridLayout(scan_params)
        sp_layout.setSpacing(8)
        sp_layout.addWidget(QLabel("Префикс:"), 0, 0)
        self.parent.cpu_prefix_spin = QSpinBox()
        self.parent.cpu_prefix_spin.setRange(1, 20)
        self.parent.cpu_prefix_spin.setValue(8)
        sp_layout.addWidget(self.parent.cpu_prefix_spin, 0, 1)
        sp_layout.addWidget(QLabel("Попыток:"), 0, 2)
        self.parent.cpu_attempts_edit = QLineEdit("10000000")
        self.parent.cpu_attempts_edit.setEnabled(False)
        self.parent.cpu_attempts_edit.setValidator(QRegularExpressionValidator(QRegularExpression("\\d+"), self.parent))
        sp_layout.addWidget(self.parent.cpu_attempts_edit, 0, 3)
        sp_layout.addWidget(QLabel("Режим:"), 1, 0)
        self.parent.cpu_mode_combo = QComboBox()
        self.parent.cpu_mode_combo.addItems(["Последовательный", "Случайный"])
        self.parent.cpu_mode_combo.currentIndexChanged.connect(self.parent.on_cpu_mode_changed)
        sp_layout.addWidget(self.parent.cpu_mode_combo, 1, 1)
        sp_layout.addWidget(QLabel("Воркеры:"), 1, 2)
        self.parent.cpu_workers_spin = QSpinBox()
        self.parent.cpu_workers_spin.setRange(1, multiprocessing.cpu_count() * 2)
        # 🛠 УЛУЧШЕНИЕ 10: Безопасное получение значения с дефолтом
        self.parent.cpu_workers_spin.setValue(getattr(self.parent, 'optimal_workers', 4))
        sp_layout.addWidget(self.parent.cpu_workers_spin, 1, 3)
        sp_layout.addWidget(QLabel("Приоритет:"), 2, 0)
        self.parent.cpu_priority_combo = QComboBox()
        self.parent.cpu_priority_combo.addItems(
            ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"]
        )
        self.parent.cpu_priority_combo.setCurrentIndex(3)
        sp_layout.addWidget(self.parent.cpu_priority_combo, 2, 1)
        pc_layout.addWidget(scan_params, 2, 0, 1, 4)

        cpu_layout.addWidget(params_cpu)

        # Кнопки
        cpu_btns = QHBoxLayout()
        cpu_btns.setSpacing(10)
        self.parent.cpu_start_stop_btn = QPushButton("▶ Старт CPU")
        set_button_style(self.parent.cpu_start_stop_btn, "success")
        self.parent.cpu_start_stop_btn.setMinimumHeight(38)
        self.parent.cpu_pause_resume_btn = QPushButton("⏸ Пауза")
        set_button_style(self.parent.cpu_pause_resume_btn, "warning")
        # После кнопок старт/пауза добавьте:
        matrix_btn = QPushButton("🔷 Matrix Search")
        matrix_btn.setStyleSheet("""
            QPushButton { background: #8e44ad; color: white; font-weight: bold; padding: 8px; border-radius: 6px; }
            QPushButton:hover { background: #9b59b6; }
        """)
        matrix_btn.clicked.connect(self.parent.open_matrix_window)
        cpu_btns.addWidget(matrix_btn)
        self.parent.cpu_pause_resume_btn.setMinimumHeight(38)
        self.parent.cpu_pause_resume_btn.setEnabled(False)
        cpu_btns.addWidget(self.parent.cpu_start_stop_btn)
        cpu_btns.addWidget(self.parent.cpu_pause_resume_btn)
        cpu_btns.addStretch()
        cpu_layout.addLayout(cpu_btns)
        # ── Кнопка Матрицы Триплетов ─────────────────────
        matrix_btn_row = QHBoxLayout()
        matrix_btn_row.setSpacing(10)

        self.parent.cpu_matrix_btn = QPushButton("🔷 Матрица Триплетов")
        self.parent.cpu_matrix_btn.setToolTip(
            "Конвертация: HEX ↔ Триплеты (3 бита = 1 буква)\n"
            "Визуализация битовых паттернов приватного ключа"
        )
        self.parent.cpu_matrix_btn.setStyleSheet("""
            QPushButton {
                background: #8e44ad;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background: #9b59b6; }
            QPushButton:pressed { background: #7d3c98; }
        """)
        self.parent.cpu_matrix_btn.setMinimumHeight(38)
        # 🔗 Подключение сигнала — обработчик в main_window.py
        self.parent.cpu_matrix_btn.clicked.connect(self.parent.open_matrix_window)

        matrix_btn_row.addWidget(self.parent.cpu_matrix_btn)
        matrix_btn_row.addStretch()
        cpu_layout.addLayout(matrix_btn_row)

        # Прогресс
        cpu_prog = QGroupBox("📊 Прогресс")
        cpl = QVBoxLayout(cpu_prog)
        cpl.setSpacing(6)
        self.parent.cpu_total_stats_label = QLabel("🟡 Статус: Ожидание")
        self.parent.cpu_total_stats_label.setProperty("cssClass", "status")
        cpl.addWidget(self.parent.cpu_total_stats_label)
        self.parent.cpu_total_progress = QProgressBar()
        self.parent.cpu_total_progress.setRange(0, 100)
        self.parent.cpu_total_progress.setValue(0)
        self.parent.cpu_total_progress.setFormat("%p%")
        cpl.addWidget(self.parent.cpu_total_progress)
        self.parent.cpu_eta_label = QLabel("⏳ ETA: —")
        self.parent.cpu_eta_label.setProperty("cssClass", "speed")
        cpl.addWidget(self.parent.cpu_eta_label)
        cpu_layout.addWidget(cpu_prog)

        # Таблица воркеров (в скролл-области)
        cpu_layout.addWidget(QLabel("🔧 Воркеры:"))
        scroll_wrapper = QScrollArea()
        scroll_wrapper.setWidgetResizable(True)
        scroll_wrapper.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_wrapper.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_wrapper.setMaximumHeight(200)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.parent.cpu_workers_table = QTableWidget(0, 5)
        self.parent.cpu_workers_table.setHorizontalHeaderLabels(["ID", "Проверено", "Найдено", "Скорость", "Прогресс"])
        # ✅ Стало (PyQt6)
        self.parent.cpu_workers_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.parent.cpu_workers_table.verticalHeader().setVisible(False)
        self.parent.cpu_workers_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.parent.cpu_workers_table)

        scroll_wrapper.setWidget(table_container)
        cpu_layout.addWidget(scroll_wrapper)

        cpu_layout.addStretch()
        self.parent.main_tabs.addTab(cpu_tab, "💻 CPU")

    # ─────────────────────────────────────────────────────
    # VANITY TAB
    # ─────────────────────────────────────────────────────
    def _setup_vanity_tab(self) -> None:
        vanity_tab = QWidget()
        vanity_layout = QVBoxLayout(vanity_tab)
        vanity_layout.setContentsMargins(12, 12, 12, 12)
        vanity_layout.setSpacing(10)

        info_v = QLabel(
            "🎨 <b>VanitySearch</b><br>"
            "Генерация адресов с префиксом: 1Jasst, bc1qjasst и т.д.<br>"
            "<i>Только генерация — не поиск по целевому адресу.</i>"
        )
        info_v.setWordWrap(True)
        info_v.setProperty("cssClass", "info-box-warning")
        vanity_layout.addWidget(info_v)

        main_v = QGroupBox("🔑 Параметры")
        mv_layout = QGridLayout(main_v)
        mv_layout.setSpacing(10)
        mv_layout.setColumnStretch(1, 2)

        mv_layout.addWidget(QLabel("Префикс:"), 0, 0)
        self.parent.vanity_prefix_edit = QLineEdit()
        self.parent.vanity_prefix_edit.setPlaceholderText("1Jasst или bc1qj")
        mv_layout.addWidget(self.parent.vanity_prefix_edit, 0, 1, 1, 2)

        mv_layout.addWidget(QLabel("Тип адреса:"), 1, 0)
        self.parent.vanity_type_combo = QComboBox()
        self.parent.vanity_type_combo.addItems([
            "P2PKH (1...)", "P2SH-P2WPKH (3...)", "Bech32 (bc1...)", "Bech32m (bc1...)"
        ])
        mv_layout.addWidget(self.parent.vanity_type_combo, 1, 1)

        mv_layout.addWidget(QLabel("Сжатый:"), 1, 2)
        self.parent.vanity_compressed_cb = QCheckBox()
        self.parent.vanity_compressed_cb.setChecked(True)
        mv_layout.addWidget(self.parent.vanity_compressed_cb, 1, 3)

        vanity_layout.addWidget(main_v)

        exec_v = QGroupBox("⚙️ Исполнение")
        ev_layout = QGridLayout(exec_v)
        ev_layout.setSpacing(10)
        ev_layout.addWidget(QLabel("GPU:"), 0, 0)
        self.parent.vanity_gpu_combo = QComboBox()
        self.parent.vanity_gpu_combo.setEditable(True)
        self.parent.vanity_gpu_combo.addItems(["0", "0,1", "0,1,2", "CPU"])
        self.parent.vanity_gpu_combo.setCurrentText("0")
        ev_layout.addWidget(self.parent.vanity_gpu_combo, 0, 1)
        ev_layout.addWidget(QLabel("CPU потоки:"), 0, 2)
        self.parent.vanity_cpu_spin = QSpinBox()
        self.parent.vanity_cpu_spin.setRange(1, multiprocessing.cpu_count())
        self.parent.vanity_cpu_spin.setValue(max(1, multiprocessing.cpu_count() - 1))
        ev_layout.addWidget(self.parent.vanity_cpu_spin, 0, 3)
        vanity_layout.addWidget(exec_v)

        start_v = QHBoxLayout()
        self.parent.vanity_start_stop_btn = QPushButton("🚀 Запустить генерацию")
        set_button_style(self.parent.vanity_start_stop_btn, "vanity")
        self.parent.vanity_start_stop_btn.setMinimumHeight(48)
        start_v.addWidget(self.parent.vanity_start_stop_btn)
        start_v.addStretch()
        vanity_layout.addLayout(start_v)

        stat_v = QGroupBox("📊 Прогресс")
        sv_layout = QGridLayout(stat_v)
        sv_layout.setSpacing(6)
        self.parent.vanity_status_label = QLabel("🟢 Готов")
        self.parent.vanity_status_label.setProperty("cssClass", "status")
        sv_layout.addWidget(self.parent.vanity_status_label, 0, 0, 1, 2)
        self.parent.vanity_speed_label = QLabel("⚡ 0 Keys/s")
        sv_layout.addWidget(self.parent.vanity_speed_label, 1, 0)
        self.parent.vanity_time_label = QLabel("⏱ 00:00:00")
        sv_layout.addWidget(self.parent.vanity_time_label, 1, 1)
        self.parent.vanity_found_label = QLabel("✨ Найдено: 0")
        self.parent.vanity_found_label.setProperty("cssClass", "found")
        sv_layout.addWidget(self.parent.vanity_found_label, 2, 0)
        self.parent.vanity_progress_bar = QProgressBar()
        self.parent.vanity_progress_bar.setRange(0, 0)
        self.parent.vanity_progress_bar.setFormat("Работает...")
        sv_layout.addWidget(self.parent.vanity_progress_bar, 3, 0, 1, 2)
        vanity_layout.addWidget(stat_v)

        result_v = QGroupBox("✅ Результат")
        rv_layout = QGridLayout(result_v)
        rv_layout.setSpacing(8)
        self.parent.vanity_result_addr = QLineEdit()
        self.parent.vanity_result_addr.setReadOnly(True)
        self.parent.vanity_result_addr.setProperty("cssClass", "result")
        rv_layout.addWidget(QLabel("Адрес:"), 0, 0)
        rv_layout.addWidget(self.parent.vanity_result_addr, 0, 1)
        self.parent.vanity_result_hex = QLineEdit()
        self.parent.vanity_result_hex.setReadOnly(True)
        rv_layout.addWidget(QLabel("HEX:"), 1, 0)
        rv_layout.addWidget(self.parent.vanity_result_hex, 1, 1)
        self.parent.vanity_result_wif = QLineEdit()
        self.parent.vanity_result_wif.setReadOnly(True)
        rv_layout.addWidget(QLabel("WIF:"), 2, 0)
        rv_layout.addWidget(self.parent.vanity_result_wif, 2, 1)
        copy_btn = QPushButton("📋 Копировать")
        copy_btn.clicked.connect(self.parent.copy_vanity_result)
        rv_layout.addWidget(copy_btn, 3, 0, 1, 2)
        vanity_layout.addWidget(result_v)

        vanity_layout.addStretch()
        self.parent.main_tabs.addTab(vanity_tab, "🎨 Vanity")

    # ─────────────────────────────────────────────────────
    # FOUND KEYS TAB
    # ─────────────────────────────────────────────────────
    def _setup_found_keys_tab(self) -> None:
        keys_tab = QWidget()
        keys_layout = QVBoxLayout(keys_tab)
        keys_layout.setContentsMargins(10, 10, 10, 10)
        keys_layout.setSpacing(10)

        self.parent.found_keys_table = QTableWidget(0, 5)
        self.parent.found_keys_table.setHorizontalHeaderLabels(["Время", "Адрес", "HEX", "WIF", "Источник"])
        # ✅ Стало (PyQt6)
        self.parent.found_keys_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.parent.found_keys_table.verticalHeader().setVisible(False)
        self.parent.found_keys_table.setAlternatingRowColors(True)
        self.parent.found_keys_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.parent.found_keys_table.customContextMenuRequested.connect(self.parent.show_context_menu)
        keys_layout.addWidget(self.parent.found_keys_table)

        export_row = QHBoxLayout()
        self.parent.export_keys_btn = QPushButton("📤 Экспорт CSV")
        set_button_style(self.parent.export_keys_btn, "primary")
        self.parent.export_keys_btn.clicked.connect(self.parent.export_keys_csv)
        self.parent.save_all_btn = QPushButton("💾 Сохранить все")
        set_button_style(self.parent.save_all_btn, "primary")
        self.parent.save_all_btn.clicked.connect(self.parent.save_all_found_keys)
        export_row.addWidget(self.parent.export_keys_btn)
        export_row.addWidget(self.parent.save_all_btn)
        export_row.addStretch()
        keys_layout.addLayout(export_row)

        self.parent.main_tabs.addTab(keys_tab, "✨ Найденные")

    # ─────────────────────────────────────────────────────
    # LOG TAB
    # ─────────────────────────────────────────────────────
    def _setup_log_tab(self) -> None:
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_layout.setSpacing(10)

        self.parent.log_output = QTextEdit()
        self.parent.log_output.setReadOnly(True)
        self.parent.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.parent.log_output)

        log_btns = QHBoxLayout()
        self.parent.clear_log_btn = QPushButton("🗑 Очистить")
        set_button_style(self.parent.clear_log_btn, "warning")
        self.parent.open_log_btn = QPushButton("📂 Открыть файл")
        set_button_style(self.parent.open_log_btn, "primary")
        self.parent.open_log_btn.clicked.connect(self.parent.open_log_file)
        log_btns.addWidget(self.parent.clear_log_btn)
        log_btns.addWidget(self.parent.open_log_btn)
        log_btns.addStretch()
        log_layout.addLayout(log_btns)

        self.parent.main_tabs.addTab(log_tab, "📋 Лог")

    # ─────────────────────────────────────────────────────
    # PREDICT TAB (ДВУХКОЛОНОЧНЫЙ LAYOUT)
    # ─────────────────────────────────────────────────────
    def _setup_predict_tab(self) -> None:
        predict_tab = QWidget()
        predict_layout = QVBoxLayout(predict_tab)
        predict_layout.setContentsMargins(12, 12, 12, 12)
        predict_layout.setSpacing(10)

        header_p = QLabel("🔮 BTC Puzzle Analyzer v2")
        header_p.setProperty("cssClass", "header")
        header_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
        predict_layout.addWidget(header_p)

        info_p = QLabel(
            "📌 <b>Как использовать:</b> Загрузите файл → настройте параметры → «Запустить анализ» → получите прогноз."
        )
        info_p.setWordWrap(True)
        info_p.setProperty("cssClass", "info-box")
        predict_layout.addWidget(info_p)

        # ═══════════════════════════════════════════════
        # ДВУХКОЛОНОЧНЫЙ LAYOUT
        # ═══════════════════════════════════════════════
        main_split = QHBoxLayout()
        main_split.setSpacing(15)

        # ───────────────────────────────────────────────
        # ЛЕВАЯ КОЛОНКА: РЕЗУЛЬТАТЫ И ГРАФИКИ (60%)
        # ───────────────────────────────────────────────
        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        # 1. Статус и прогресс
        status_group = QGroupBox("📊 Статус анализа")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)

        self.parent.predict_status_label = QLabel("⏳ Ожидание запуска")
        self.parent.predict_status_label.setProperty("cssClass", "status")
        self.parent.predict_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.parent.predict_status_label)

        self.parent.predict_progress_bar = QProgressBar()
        self.parent.predict_progress_bar.setRange(0, 100)
        self.parent.predict_progress_bar.setValue(0)
        self.parent.predict_progress_bar.setFormat("%p%")
        self.parent.predict_progress_bar.setFixedHeight(28)
        self.parent.predict_progress_bar.hide()
        status_layout.addWidget(self.parent.predict_progress_bar)

        left_column.addWidget(status_group)

        # 2. Основные результаты (таблица)
        results_group = QGroupBox("📈 Основные результаты")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(6)

        self.parent.predict_results_table = QTableWidget(0, 2)
        self.parent.predict_results_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.parent.predict_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.parent.predict_results_table.verticalHeader().setVisible(False)
        self.parent.predict_results_table.setAlternatingRowColors(True)
        self.parent.predict_results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parent.predict_results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parent.predict_results_table.setMinimumHeight(150)
        self.parent.predict_results_table.setMaximumHeight(220)
        results_layout.addWidget(self.parent.predict_results_table)

        left_column.addWidget(results_group)

        # 3. Диапазоны моделей
        ranges_group = QGroupBox("🔍 Диапазоны моделей")
        ranges_layout = QVBoxLayout(ranges_group)
        ranges_layout.setSpacing(6)

        ranges_layout.addWidget(QLabel("<i>Прогнозы от разных моделей:</i>"))

        self.parent.predict_ranges_table = QTableWidget(0, 4)
        self.parent.predict_ranges_table.setHorizontalHeaderLabels(["Модель", "Диапазон (hex)", "Ширина", "📋"])
        self.parent.predict_ranges_table.setColumnWidth(0, 100)
        self.parent.predict_ranges_table.setColumnWidth(1, 280)
        self.parent.predict_ranges_table.setColumnWidth(2, 90)
        self.parent.predict_ranges_table.setColumnWidth(3, 40)
        self.parent.predict_ranges_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.parent.predict_ranges_table.verticalHeader().setVisible(False)
        self.parent.predict_ranges_table.setAlternatingRowColors(True)
        self.parent.predict_ranges_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.parent.predict_ranges_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        ranges_scroll = QScrollArea()
        ranges_scroll.setWidgetResizable(True)
        ranges_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        ranges_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        ranges_scroll.setMinimumHeight(180)
        ranges_scroll.setMaximumHeight(250)
        ranges_scroll.setWidget(self.parent.predict_ranges_table)
        ranges_layout.addWidget(ranges_scroll)

        # Легенда
        legend = QHBoxLayout()
        legend.setSpacing(12)
        # 🛠 УЛУЧШЕНИЕ 11: Безопасный доступ к COLORS с .get()
        for txt, col in [("🔵 Position", COLORS.get('accent_primary', '#5B8CFF')),
                         ("🟢 LogGrowth", COLORS.get('accent_success', '#2ECC71')),
                         ("🟠 Ensemble", COLORS.get('accent_warning', '#F39C12')),
                         ("🔴 Final", COLORS.get('accent_danger', '#E74C3C'))]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color:{col}; font-size:9pt; font-weight:bold;")
            legend.addWidget(lbl)
        legend.addStretch()
        ranges_layout.addLayout(legend)

        left_column.addWidget(ranges_group)

        # 4. График
        graph_group = QGroupBox("📊 Визуализация распределения")
        graph_layout = QVBoxLayout(graph_group)
        graph_layout.setSpacing(6)

        self.parent.predict_scroll = QScrollArea()
        self.parent.predict_scroll.setWidgetResizable(True)
        self.parent.predict_scroll.setMinimumHeight(320)
        self.parent.predict_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #3A3A4A; border-radius: 6px; background: transparent; }")

        self.parent.predict_plot_label = QLabel(
            "📊 График появится после анализа\n\n"
            "Отображается:\n"
            "• Распределение ключей\n"
            "• Предсказанные диапазоны\n"
            "• Плотность вероятности"
        )
        self.parent.predict_plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parent.predict_plot_label.setStyleSheet(
            f"color:{COLORS.get('text_secondary', '#B0B0C0')}; font-size:10pt; padding:40px; "
            f"background:{COLORS.get('bg_input', '#232332')}; border:2px dashed {COLORS.get('border', '#3A3A4A')}; border-radius:6px;"
        )

        graph_container = QWidget()
        graph_container_layout = QVBoxLayout(graph_container)
        graph_container_layout.addWidget(self.parent.predict_plot_label)
        graph_container_layout.addStretch()
        self.parent.predict_scroll.setWidget(graph_container)

        graph_layout.addWidget(self.parent.predict_scroll)
        left_column.addWidget(graph_group, 1)

        # ───────────────────────────────────────────────
        # ПРАВАЯ КОЛОНКА: ПАРАМЕТРЫ И НАСТРОЙКИ (40%)
        # ───────────────────────────────────────────────
        right_column = QVBoxLayout()
        right_column.setSpacing(10)

        # 1. Файл с данными
        file_group = QGroupBox("📁 Данные")
        file_layout = QGridLayout(file_group)
        file_layout.setSpacing(8)
        file_layout.setColumnStretch(1, 1)

        file_layout.addWidget(QLabel("Файл с ключами:"), 0, 0)
        self.parent.predict_file_edit = QLineEdit()
        self.parent.predict_file_edit.setPlaceholderText("KNOWN_KEYS_HEX.txt")
        file_layout.addWidget(self.parent.predict_file_edit, 0, 1)

        self.parent.predict_browse_btn = QPushButton("📁")
        self.parent.predict_browse_btn.setFixedWidth(40)
        file_layout.addWidget(self.parent.predict_browse_btn, 0, 2)

        file_status = QHBoxLayout()
        file_status.addWidget(QLabel("✅ Ключей:"))
        self.parent.predict_keys_count_label = QLabel("0")
        self.parent.predict_keys_count_label.setProperty("cssClass", "found")
        file_status.addWidget(self.parent.predict_keys_count_label)
        file_status.addStretch()

        self.parent.preview_keys_btn = QPushButton("👁️ Предпросмотр")
        self.parent.preview_keys_btn.setFixedWidth(110)
        file_status.addWidget(self.parent.preview_keys_btn)

        file_layout.addLayout(file_status, 1, 0, 1, 3)
        right_column.addWidget(file_group)

        # 2. Параметры анализа (в скролле)
        params_scroll = QScrollArea()
        params_scroll.setWidgetResizable(True)
        params_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        params_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        params_scroll.setMaximumHeight(400)
        params_scroll.setMinimumHeight(300)

        params_container = QWidget()
        params_group = QGroupBox("⚙️ Параметры анализа")
        params_layout = QGridLayout(params_group)
        params_layout.setSpacing(8)
        params_layout.setColumnStretch(1, 1)
        params_layout.setColumnStretch(3, 1)

        params_layout.addWidget(QLabel("Q Low:"), 0, 0)
        self.parent.predict_q_low_spin = QSpinBox()
        self.parent.predict_q_low_spin.setRange(0, 100)
        self.parent.predict_q_low_spin.setValue(25)
        self.parent.predict_q_low_spin.setSuffix("%")
        params_layout.addWidget(self.parent.predict_q_low_spin, 0, 1)

        params_layout.addWidget(QLabel("Q High:"), 1, 0)
        self.parent.predict_q_high_spin = QSpinBox()
        self.parent.predict_q_high_spin.setRange(0, 100)
        self.parent.predict_q_high_spin.setValue(75)
        self.parent.predict_q_high_spin.setSuffix("%")
        params_layout.addWidget(self.parent.predict_q_high_spin, 1, 1)

        self.parent.predict_outlier_filter_cb = QCheckBox("Фильтр выбросов")
        self.parent.predict_outlier_filter_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_outlier_filter_cb, 2, 0, 1, 2)

        self.parent.predict_weight_recent_cb = QCheckBox("Вес свежих данных")
        self.parent.predict_weight_recent_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_weight_recent_cb, 3, 0, 1, 2)

        self.parent.predict_log_growth_cb = QCheckBox("Логарифмический рост")
        self.parent.predict_log_growth_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_log_growth_cb, 4, 0, 1, 2)

        self.parent.predict_position_model_cb = QCheckBox("Модель позиций")
        self.parent.predict_position_model_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_position_model_cb, 2, 2, 1, 2)

        self.parent.predict_ensemble_cb = QCheckBox("Ансамбль моделей")
        self.parent.predict_ensemble_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_ensemble_cb, 3, 2, 1, 2)

        self.parent.predict_kde_cb = QCheckBox("Gaussian KDE")
        self.parent.predict_kde_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_kde_cb, 4, 2, 1, 2)

        self.parent.predict_spline_cb = QCheckBox("Spline-сглаживание")
        self.parent.predict_spline_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_spline_cb, 5, 0, 1, 2)

        params_layout.addWidget(QLabel("Моделей:"), 6, 0)
        self.parent.predict_ensemble_models_spin = QSpinBox()
        self.parent.predict_ensemble_models_spin.setRange(1, 10)
        self.parent.predict_ensemble_models_spin.setValue(3)
        params_layout.addWidget(self.parent.predict_ensemble_models_spin, 6, 1)

        params_layout.addWidget(QLabel("KDE точек:"), 6, 2)
        self.parent.predict_kde_points_spin = QSpinBox()
        self.parent.predict_kde_points_spin.setRange(10000, 1000000)
        self.parent.predict_kde_points_spin.setValue(500000)
        self.parent.predict_kde_points_spin.setSingleStep(50000)
        params_layout.addWidget(self.parent.predict_kde_points_spin, 6, 3)

        params_container_layout = QVBoxLayout(params_container)
        params_container_layout.addWidget(params_group)
        params_container_layout.addStretch()
        params_scroll.setWidget(params_container)

        right_column.addWidget(params_scroll)

        # 3. Кнопка запуска
        self.parent.predict_run_btn = QPushButton("🔮 Запустить анализ")
        set_button_style(self.parent.predict_run_btn, "predict")
        self.parent.predict_run_btn.setMinimumHeight(50)
        self.parent.predict_run_btn.setFont(QFont("", 11, QFont.Weight.Bold))
        right_column.addWidget(self.parent.predict_run_btn)

        # 4. Экспорт результатов
        export_group = QGroupBox("💾 Экспорт")
        export_layout = QHBoxLayout(export_group)
        export_layout.setSpacing(8)

        self.parent.predict_export_btn = QPushButton("📥 Экспорт результатов")
        set_button_style(self.parent.predict_export_btn, "primary")
        self.parent.predict_export_btn.setMinimumHeight(38)
        export_layout.addWidget(self.parent.predict_export_btn)

        right_column.addWidget(export_group)
        right_column.addStretch()

        # ═══════════════════════════════════════════════
        # ДОБАВЛЯЕМ КОЛОНКИ В MAIN LAYOUT
        # ═══════════════════════════════════════════════
        main_split.addLayout(left_column, 3)
        main_split.addLayout(right_column, 2)

        predict_layout.addLayout(main_split)
        self.parent.main_tabs.addTab(predict_tab, "🔮 Predict")

    # ─────────────────────────────────────────────────────
    # ABOUT TAB
    # ─────────────────────────────────────────────────────
    def _setup_about_tab(self) -> None:
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setContentsMargins(20, 20, 20, 20)
        about_layout.setSpacing(15)

        coincurve_status = "✓ Доступна" if is_coincurve_available() else "✗ Не установлена"
        cubitcrack_status = "✓ Найден" if os.path.exists(os.path.join(config.BASE_DIR, "cuBitcrack.exe")) else "✗ Не найден"  # 🛠 УЛУЧШЕНИЕ 12: os.path.exists вместо os.path.join

        about_text = QLabel(
            f"<div style='text-align:center; padding:20px; background:{COLORS.get('bg_input', '#232332')}; "
            f"border-radius:10px; border:1px solid {COLORS.get('border', '#3A3A4A')};'>"
            f"<h2 style='color:{COLORS.get('accent_primary', '#5B8CFF')}; margin:0 0 10px 0;'>⛏️ Bitcoin GPU/CPU Scanner</h2>"
            f"<b>Версия:</b> 5.0 (Улучшенная)<br>"
            f"<b>Автор:</b> Jasst<br>"
            f"<b>GitHub:</b> <a href='https://github.com/Jasst' style='color:{COLORS.get('accent_primary', '#5B8CFF')};'>github.com/Jasst</a><br><br>"
            f"<b>Возможности:</b><ul style='text-align:left; display:inline-block;'>"
            f"<li>🎮 GPU поиск через cuBitcrack</li>"
            f"<li>💻 CPU мультипроцессинг</li>"
            f"<li>🎲 Случайный/последовательный режим</li>"
            f"<li>📊 Расширенная статистика и ETA</li>"
            f"<li>⚡ Авто-оптимизация параметров</li>"
            f"<li>🎨 Vanity адрес генерация</li>"
            f"<li>🦘 Kangaroo алгоритм</li>"
            f"<li>🔮 Предиктивная аналитика</li>"
            f"</ul><br>"
            f"<b>Статус:</b><br>"
            f"coincurve: <span style='color:{COLORS.get('accent_success', '#2ECC71') if '✓' in coincurve_status else COLORS.get('accent_danger', '#E74C3C')}'>{coincurve_status}</span><br>"
            f"cuBitcrack.exe: <span style='color:{COLORS.get('accent_success', '#2ECC71') if '✓' in cubitcrack_status else COLORS.get('accent_danger', '#E74C3C')}'>{cubitcrack_status}</span>"
            f"</div>"
        )
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_layout.addWidget(about_text)
        about_layout.addStretch()
        self.parent.main_tabs.addTab(about_tab, "ℹ️ О программе")

    # ─────────────────────────────────────────────────────
    # БЕЗОПАСНЫЕ МЕТОДЫ ОБНОВЛЕНИЯ UI
    # ─────────────────────────────────────────────────────
    def _safe_update_label(self, label_attr: str, text: str, css_class: Optional[str] = None) -> None:
        """Безопасное обновление QLabel с проверкой инициализации"""
        if not self._ui_initialized:
            return
        label = getattr(self.parent, label_attr, None)
        if label is not None:
            try:
                label.setText(text)
                if css_class:
                    label.setProperty("cssClass", css_class)
                    label.style().unpolish(label)
                    label.style().polish(label)
            except (AttributeError, RuntimeError):  # 🛠 УЛУЧШЕНИЕ 13: Конкретные исключения вместо общего Exception
                pass

    def _safe_update_progress(self, bar_attr: str, value: int, fmt: Optional[str] = None, css_class: Optional[str] = None) -> None:
        """Безопасное обновление QProgressBar"""
        if not self._ui_initialized:
            return
        bar = getattr(self.parent, bar_attr, None)
        if bar is not None:
            try:
                bar.setValue(value)
                if fmt:
                    bar.setFormat(fmt)
                if css_class:
                    bar.setProperty("cssClass", css_class)
                    bar.style().unpolish(bar)
                    bar.style().polish(bar)
            except (AttributeError, RuntimeError):
                pass