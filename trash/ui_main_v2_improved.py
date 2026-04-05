# ui/ui_main_v2_improved.py
"""
🎨 УЛУЧШЕННЫЙ ГЛАВНЫЙ UI v2.0
Полная переработка интерфейса с оптимизацией иерархии и читаемости

✨ Ключевые улучшения:
  • Лучшая организация элементов (компактнее, четче)
  • Улучшенная визуальная иерархия (размеры, веса шрифтов)
  • Профессиональные иконки и цветовые акценты
  • Адаптивные макеты (responsive design)
  • Улучшенные таблицы и отображение данных
  • Лучшая группировка связанных элементов
  • Плавные визуальные переходы
"""

import os
import multiprocessing
from PyQt5.QtCore import Qt, QRegExp, QSize, QTimer
from PyQt5.QtGui import QFont, QRegExpValidator, QColor, QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QTableWidget, QHeaderView, QProgressBar, QCheckBox,
    QComboBox, QTabWidget, QSpinBox, QMenu, QApplication,
    QScrollArea, QFrame, QSizePolicy, QStackedWidget,
    QTableWidgetItem
)

import config
from ui.theme_v2_professional import (
    apply_professional_theme, set_button_style, 
    set_label_style, COLORS_V2, TYPOGRAPHY
)
from utils.helpers import make_combo32, is_coincurve_available


class MainWindowUI_V2:
    """
    Улучшенный UI для Bitcoin GPU/CPU Scanner v5.0+
    
    Главные улучшения:
    • Более компактный и читаемый layout
    • Четкая визуальная иерархия (заголовки, разделы)
    • Лучшая организация параметров (группирование)
    • Улучшенное отображение статистики
    • Профессиональный бизнес-стиль
    """

    def __init__(self, parent):
        self.parent = parent
        self._ui_initialized = False

    def setup_ui(self):
        """Главный метод настройки UI"""
        
        # Базовая настройка окна
        self.parent.setWindowTitle("⛏️ Bitcoin GPU/CPU Scanner v5.0 Pro")
        self.parent.resize(1400, 1000)
        self.parent.setMinimumSize(1200, 800)

        # Применяем новую профессиональную тему
        apply_professional_theme(self.parent)

        # Центральный виджет
        main_widget = QWidget()
        self.parent.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # Заголовок приложения
        self._setup_header(main_layout)

        # Вкладки
        self.parent.main_tabs = QTabWidget()
        self.parent.main_tabs.setObjectName("mainTabs")
        self.parent.main_tabs.setMinimumHeight(500)
        main_layout.addWidget(self.parent.main_tabs, 1)

        # === ВКЛАДКИ ===
        self._setup_gpu_tab()          # 🎮 GPU поиск
        self._setup_kangaroo_tab()     # 🦘 Kangaroo
        self._setup_cpu_tab()          # 💻 CPU поиск
        self._setup_vanity_tab()       # 🎨 Vanity
        self._setup_found_keys_tab()   # ✨ Результаты
        self.parent.setup_converter_tab()  # 🔄 Конвертер
        self._setup_log_tab()          # 📋 Логи
        self._setup_predict_tab()      # 🔮 Прогноз
        self._setup_about_tab()        # ℹ️ О программе

        self._ui_initialized = True

    # ═══════════════════════════════════════════════════════════════
    # ЗАГОЛОВОК И СТАТУС-БАР
    # ═══════════════════════════════════════════════════════════════

    def _setup_header(self, layout):
        """Настройка заголовка приложения"""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Название приложения
        title_label = QLabel("⛏️ Bitcoin GPU/CPU Scanner")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setWeight(700)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {COLORS_V2['accent_primary']};")
        header_layout.addWidget(title_label)

        # Версия
        version_label = QLabel("v5.0 Pro")
        version_font = QFont()
        version_font.setPointSize(9)
        version_label.setFont(version_font)
        version_label.setStyleSheet(f"color: {COLORS_V2['text_secondary']};")
        header_layout.addWidget(version_label)

        header_layout.addStretch()

        # Статус приложения
        self.parent.app_status_label = QLabel("🟢 Готов")
        self.parent.app_status_label.setStyleSheet(
            f"color: {COLORS_V2['success']}; font-weight: 600;"
        )
        header_layout.addWidget(self.parent.app_status_label)

        layout.addLayout(header_layout)

        # Разделитель
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setLineWidth(1)
        divider.setStyleSheet(f"background-color: {COLORS_V2['border']};")
        layout.addWidget(divider)

    # ═══════════════════════════════════════════════════════════════
    # GPU TAB - ПОЛНОСТЬЮ ПЕРЕРАБОТАНА
    # ═══════════════════════════════════════════════════════════════

    def _setup_gpu_tab(self):
        """Полностью переработанная GPU вкладка с улучшенной организацией"""
        gpu_tab = QWidget()
        gpu_layout = QVBoxLayout(gpu_tab)
        gpu_layout.setContentsMargins(12, 12, 12, 12)
        gpu_layout.setSpacing(12)

        # --- ЗАГОЛОВОК ---
        title = QLabel("🎮 GPU Поиск приватных ключей")
        title.setProperty("cssClass", "section-title")
        gpu_layout.addWidget(title)

        # --- ОСНОВНОЙ КОНТЕНТ В СКРОЛЛЕ ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {COLORS_V2['border']}; }}")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        # 1️⃣ ЦЕЛЕВОЙ АДРЕС И ДИАПАЗОН
        self._add_gpu_target_section(scroll_layout)

        # 2️⃣ ПАРАМЕТРЫ СКАНИРОВАНИЯ
        self._add_gpu_parameters_section(scroll_layout)

        # 3️⃣ ОПТИМИЗАЦИЯ И УПРАВЛЕНИЕ
        self._add_gpu_control_section(scroll_layout)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        gpu_layout.addWidget(scroll, 1)

        # --- СТАТИСТИКА И МОНИТОРИНГ (ВНИЗУ) ---
        self._add_gpu_stats_section(gpu_layout)

        self.parent.main_tabs.addTab(gpu_tab, "🎮 GPU")

    def _add_gpu_target_section(self, layout):
        """Раздел целевого адреса и диапазона"""
        group = QGroupBox("🎯 Цель и диапазон поиска")
        grid = QGridLayout(group)
        grid.setSpacing(10)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(3, 2)

        # BTC Адрес
        grid.addWidget(QLabel("BTC адрес:"), 0, 0)
        self.parent.gpu_target_edit = QLineEdit()
        self.parent.gpu_target_edit.setPlaceholderText("1ABC... или 3XYZ... или bc1q...")
        grid.addWidget(self.parent.gpu_target_edit, 0, 1, 1, 3)

        # Начало диапазона
        grid.addWidget(QLabel("Начало (hex):"), 1, 0)
        self.parent.gpu_start_key_edit = QLineEdit("1")
        self.parent.gpu_start_key_edit.setValidator(
            QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent)
        )
        grid.addWidget(self.parent.gpu_start_key_edit, 1, 1)

        # Конец диапазона
        grid.addWidget(QLabel("Конец (hex):"), 1, 2)
        self.parent.gpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.gpu_end_key_edit.setValidator(
            QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent)
        )
        grid.addWidget(self.parent.gpu_end_key_edit, 1, 3)

        layout.addWidget(group)

    def _add_gpu_parameters_section(self, layout):
        """Раздел параметров GPU"""
        group = QGroupBox("⚙️ Параметры сканирования")
        grid = QGridLayout(group)
        grid.setSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        # Ряд 1: GPU и основные параметры
        grid.addWidget(QLabel("GPU ID:"), 0, 0)
        self.parent.gpu_device_combo = QComboBox()
        self.parent.gpu_device_combo.setEditable(True)
        self.parent.gpu_device_combo.addItems(["0", "1", "2", "0,1", "0,1,2", "0,1,2,3"])
        self.parent.gpu_device_combo.setCurrentText("0")
        grid.addWidget(self.parent.gpu_device_combo, 0, 1)

        grid.addWidget(QLabel("Блоки:"), 0, 2)
        self.parent.blocks_combo = make_combo32(32, 2048, 256)
        grid.addWidget(self.parent.blocks_combo, 0, 3)

        # Ряд 2
        grid.addWidget(QLabel("Потоки/блок:"), 1, 0)
        self.parent.threads_combo = make_combo32(32, 1024, 256)
        grid.addWidget(self.parent.threads_combo, 1, 1)

        grid.addWidget(QLabel("Точки:"), 1, 2)
        self.parent.points_combo = make_combo32(32, 1024, 256)
        grid.addWidget(self.parent.points_combo, 1, 3)

        # Ряд 3: Флаги и опции
        self.parent.gpu_random_checkbox = QCheckBox("🎲 Случайный поиск в диапазоне")
        grid.addWidget(self.parent.gpu_random_checkbox, 2, 0, 1, 2)

        grid.addWidget(QLabel("Рестарт (сек):"), 2, 2)
        self.parent.gpu_restart_interval_combo = QComboBox()
        self.parent.gpu_restart_interval_combo.addItems(
            [str(x) for x in range(10, 3601, 10)]
        )
        self.parent.gpu_restart_interval_combo.setCurrentText("300")
        self.parent.gpu_restart_interval_combo.setEnabled(False)
        grid.addWidget(self.parent.gpu_restart_interval_combo, 2, 3)
        self.parent.gpu_random_checkbox.toggled.connect(
            self.parent.gpu_restart_interval_combo.setEnabled
        )

        # Ряд 4: Опции оптимизации
        self.parent.gpu_use_compressed_checkbox = QCheckBox("✅ Сжатые ключи")
        self.parent.gpu_use_compressed_checkbox.setChecked(True)
        self.parent.gpu_use_compressed_checkbox.setToolTip(
            "33-байтный ключ вместо 65-байтного (×1.5-2 быстрее)"
        )
        grid.addWidget(self.parent.gpu_use_compressed_checkbox, 3, 0, 1, 2)

        grid.addWidget(QLabel("Приоритет:"), 3, 2)
        self.parent.gpu_priority_combo = QComboBox()
        self.parent.gpu_priority_combo.addItems(["Нормальный", "Высокий", "Реального времени"])
        grid.addWidget(self.parent.gpu_priority_combo, 3, 3)

        layout.addWidget(group)

    def _add_gpu_control_section(self, layout):
        """Раздел управления и запуска GPU"""
        group = QGroupBox("🎛️ Управление")
        btn_layout = QHBoxLayout(group)
        btn_layout.setSpacing(10)

        self.parent.gpu_start_stop_btn = QPushButton("▶ Запустить GPU")
        set_button_style(self.parent.gpu_start_stop_btn, "success")
        self.parent.gpu_start_stop_btn.setMinimumHeight(44)
        self.parent.gpu_start_stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.parent.gpu_optimize_btn = QPushButton("⚡ Авто-оптимизация")
        set_button_style(self.parent.gpu_optimize_btn, "primary")
        self.parent.gpu_optimize_btn.setMinimumHeight(44)

        btn_layout.addWidget(self.parent.gpu_start_stop_btn, 2)
        btn_layout.addWidget(self.parent.gpu_optimize_btn, 1)

        layout.addWidget(group)

    def _add_gpu_stats_section(self, layout):
        """Раздел статистики GPU"""
        stats_group = QGroupBox("📊 Статистика и мониторинг")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(10)

        # Статус
        status_row = QHBoxLayout()
        self.parent.gpu_status_label = QLabel("🟢 Готов")
        self.parent.gpu_status_label.setProperty("cssClass", "status")
        status_row.addWidget(self.parent.gpu_status_label)
        status_row.addStretch()
        stats_layout.addLayout(status_row)

        # Скорость и время
        perf_grid = QGridLayout()
        perf_grid.setSpacing(15)

        self.parent.gpu_speed_label = QLabel("⚡ Скорость: 0 MKey/s")
        self.parent.gpu_speed_label.setProperty("cssClass", "speed")
        perf_grid.addWidget(self.parent.gpu_speed_label, 0, 0)

        self.parent.gpu_time_label = QLabel("⏱ Время: 00:00:00")
        perf_grid.addWidget(self.parent.gpu_time_label, 0, 1)

        self.parent.gpu_checked_label = QLabel("🔍 Проверено: 0")
        perf_grid.addWidget(self.parent.gpu_checked_label, 1, 0)

        self.parent.gpu_found_label = QLabel("✨ Найдено: 0")
        self.parent.gpu_found_label.setProperty("cssClass", "found")
        perf_grid.addWidget(self.parent.gpu_found_label, 1, 1)

        stats_layout.addLayout(perf_grid)

        # Прогресс-бар
        self.parent.gpu_progress_bar = QProgressBar()
        self.parent.gpu_progress_bar.setRange(0, 100)
        self.parent.gpu_progress_bar.setValue(0)
        self.parent.gpu_progress_bar.setFormat("Прогресс: %p%")
        self.parent.gpu_progress_bar.setMinimumHeight(32)
        stats_layout.addWidget(self.parent.gpu_progress_bar)

        # Диапазон
        self.parent.gpu_range_label = QLabel("📐 Диапазон: —")
        self.parent.gpu_range_label.setProperty("cssClass", "range")
        self.parent.gpu_range_label.setWordWrap(True)
        stats_layout.addWidget(self.parent.gpu_range_label)

        # Аппаратный статус (если доступен)
        try:
            import pynvml
            PYNVML_AVAILABLE = True
        except ImportError:
            PYNVML_AVAILABLE = False

        if PYNVML_AVAILABLE:
            hw_group = QGroupBox("🌡 Аппаратный статус")
            hw_grid = QGridLayout(hw_group)
            hw_grid.setSpacing(10)

            self.parent.gpu_util_label = QLabel("Загрузка: —%")
            hw_grid.addWidget(self.parent.gpu_util_label, 0, 0)

            self.parent.gpu_mem_label = QLabel("Память: — / — MB")
            hw_grid.addWidget(self.parent.gpu_mem_label, 0, 1)

            self.parent.gpu_temp_label = QLabel("Температура: —°C")
            hw_grid.addWidget(self.parent.gpu_temp_label, 1, 0)

            self.parent.gpu_util_bar = QProgressBar()
            self.parent.gpu_util_bar.setRange(0, 100)
            self.parent.gpu_util_bar.setFormat("%p%")
            hw_grid.addWidget(self.parent.gpu_util_bar, 2, 0)

            self.parent.gpu_mem_bar = QProgressBar()
            self.parent.gpu_mem_bar.setRange(0, 100)
            self.parent.gpu_mem_bar.setFormat("%p%")
            hw_grid.addWidget(self.parent.gpu_mem_bar, 2, 1)

            stats_layout.addWidget(hw_group)

        layout.addWidget(stats_group)

    # ═══════════════════════════════════════════════════════════════
    # CPU TAB - УЛУЧШЕННАЯ ВЕРСИЯ
    # ═══════════════════════════════════════════════════════════════

    def _setup_cpu_tab(self):
        """Переработанная CPU вкладка"""
        cpu_tab = QWidget()
        cpu_layout = QVBoxLayout(cpu_tab)
        cpu_layout.setContentsMargins(12, 12, 12, 12)
        cpu_layout.setSpacing(12)

        # Заголовок
        title = QLabel("💻 CPU Поиск приватных ключей")
        title.setProperty("cssClass", "section-title")
        cpu_layout.addWidget(title)

        # Скроллируемый контент
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)

        # Системная информация
        sys_info = QGroupBox("💻 Система")
        si_grid = QGridLayout(sys_info)
        si_grid.setSpacing(10)

        self.parent.cpu_label = QLabel(f"{multiprocessing.cpu_count()} ядер")
        si_grid.addWidget(QLabel("Процессор:"), 0, 0)
        si_grid.addWidget(self.parent.cpu_label, 0, 1)

        self.parent.mem_label = QLabel("— MB")
        si_grid.addWidget(QLabel("Память:"), 0, 2)
        si_grid.addWidget(self.parent.mem_label, 0, 3)

        self.parent.cpu_usage = QLabel("0%")
        si_grid.addWidget(QLabel("Загрузка:"), 1, 0)
        si_grid.addWidget(self.parent.cpu_usage, 1, 1)

        self.parent.cpu_status_label = QLabel("🟡 Ожидание")
        si_grid.addWidget(QLabel("Статус:"), 1, 2)
        si_grid.addWidget(self.parent.cpu_status_label, 1, 3)

        scroll_layout.addWidget(sys_info)

        # Параметры CPU
        params_group = QGroupBox("⚙️ Параметры поиска")
        params_grid = QGridLayout(params_group)
        params_grid.setSpacing(10)
        params_grid.setColumnStretch(1, 2)

        self.parent.cpu_target_edit = QLineEdit()
        self.parent.cpu_target_edit.setPlaceholderText("1... или 3...")
        params_grid.addWidget(QLabel("Целевой адрес:"), 0, 0)
        params_grid.addWidget(self.parent.cpu_target_edit, 0, 1, 1, 3)

        # Диапазон ключей
        keys_group = QGroupBox("Диапазон ключей")
        kg_grid = QGridLayout(keys_group)

        self.parent.cpu_start_key_edit = QLineEdit("1")
        self.parent.cpu_start_key_edit.setValidator(
            QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent)
        )
        kg_grid.addWidget(QLabel("Начало:"), 0, 0)
        kg_grid.addWidget(self.parent.cpu_start_key_edit, 0, 1)

        self.parent.cpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
        self.parent.cpu_end_key_edit.setValidator(
            QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self.parent)
        )
        kg_grid.addWidget(QLabel("Конец:"), 0, 2)
        kg_grid.addWidget(self.parent.cpu_end_key_edit, 0, 3)

        params_grid.addWidget(keys_group, 1, 0, 1, 4)

        # Режим сканирования
        scan_group = QGroupBox("Сканирование")
        sp_grid = QGridLayout(scan_group)

        self.parent.cpu_mode_combo = QComboBox()
        self.parent.cpu_mode_combo.addItems(["Последовательный", "Случайный"])
        sp_grid.addWidget(QLabel("Режим:"), 0, 0)
        sp_grid.addWidget(self.parent.cpu_mode_combo, 0, 1)

        self.parent.cpu_workers_spin = QSpinBox()
        self.parent.cpu_workers_spin.setRange(1, multiprocessing.cpu_count() * 2)
        self.parent.cpu_workers_spin.setValue(getattr(self.parent, 'optimal_workers', 4))
        sp_grid.addWidget(QLabel("Воркеры:"), 0, 2)
        sp_grid.addWidget(self.parent.cpu_workers_spin, 0, 3)

        self.parent.cpu_priority_combo = QComboBox()
        self.parent.cpu_priority_combo.addItems(
            ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"]
        )
        self.parent.cpu_priority_combo.setCurrentIndex(3)
        sp_grid.addWidget(QLabel("Приоритет:"), 1, 0)
        sp_grid.addWidget(self.parent.cpu_priority_combo, 1, 1, 1, 3)

        params_grid.addWidget(scan_group, 2, 0, 1, 4)

        scroll_layout.addWidget(params_group)

        # Кнопки управления
        btn_group = QGroupBox("🎛️ Управление")
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setSpacing(10)

        self.parent.cpu_start_stop_btn = QPushButton("▶ Начать поиск")
        set_button_style(self.parent.cpu_start_stop_btn, "success")
        self.parent.cpu_start_stop_btn.setMinimumHeight(44)

        self.parent.cpu_pause_resume_btn = QPushButton("⏸ Пауза")
        set_button_style(self.parent.cpu_pause_resume_btn, "warning")
        self.parent.cpu_pause_resume_btn.setMinimumHeight(44)
        self.parent.cpu_pause_resume_btn.setEnabled(False)

        btn_layout.addWidget(self.parent.cpu_start_stop_btn, 1)
        btn_layout.addWidget(self.parent.cpu_pause_resume_btn, 1)

        scroll_layout.addWidget(btn_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        cpu_layout.addWidget(scroll, 1)

        # Прогресс и статистика
        progress_group = QGroupBox("📊 Прогресс")
        prog_layout = QVBoxLayout(progress_group)

        self.parent.cpu_total_stats_label = QLabel("🟡 Статус: Ожидание")
        self.parent.cpu_total_stats_label.setProperty("cssClass", "status")
        prog_layout.addWidget(self.parent.cpu_total_stats_label)

        self.parent.cpu_total_progress = QProgressBar()
        self.parent.cpu_total_progress.setRange(0, 100)
        self.parent.cpu_total_progress.setFormat("%p%")
        self.parent.cpu_total_progress.setMinimumHeight(32)
        prog_layout.addWidget(self.parent.cpu_total_progress)

        self.parent.cpu_eta_label = QLabel("⏳ Оставшееся время: —")
        self.parent.cpu_eta_label.setProperty("cssClass", "speed")
        prog_layout.addWidget(self.parent.cpu_eta_label)

        # Таблица воркеров
        prog_layout.addWidget(QLabel("🔧 Воркеры:"))
        scroll_workers = QScrollArea()
        scroll_workers.setWidgetResizable(True)
        scroll_workers.setMaximumHeight(200)

        worker_container = QWidget()
        worker_layout = QVBoxLayout(worker_container)
        worker_layout.setContentsMargins(0, 0, 0, 0)

        self.parent.cpu_workers_table = QTableWidget(0, 5)
        self.parent.cpu_workers_table.setHorizontalHeaderLabels(
            ["ID", "Проверено", "Найдено", "Скорость", "Прогресс"]
        )
        self.parent.cpu_workers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parent.cpu_workers_table.verticalHeader().setVisible(False)
        self.parent.cpu_workers_table.setAlternatingRowColors(True)
        worker_layout.addWidget(self.parent.cpu_workers_table)

        scroll_workers.setWidget(worker_container)
        prog_layout.addWidget(scroll_workers)

        cpu_layout.addWidget(progress_group)
        self.parent.main_tabs.addTab(cpu_tab, "💻 CPU")

    # ═══════════════════════════════════════════════════════════════
    # ОСТАЛЬНЫЕ ВКЛАДКИ (KANGAROO, VANITY и т.д.)
    # ═══════════════════════════════════════════════════════════════

    def _setup_kangaroo_tab(self):
        """Kangaroo алгоритм вкладка"""
        kangaroo_tab = QWidget()
        kang_layout = QVBoxLayout(kangaroo_tab)
        kang_layout.setContentsMargins(12, 12, 12, 12)
        kang_layout.setSpacing(12)

        title = QLabel("🦘 Kangaroo Algorithm")
        title.setProperty("cssClass", "section-title")
        kang_layout.addWidget(title)

        info = QLabel(
            "Эффективный поиск в диапазоне через Pollard's Kangaroo.\n"
            "Убедитесь, что путь к Etarkangaroo.exe указан верно."
        )
        info.setProperty("cssClass", "info-box")
        info.setWordWrap(True)
        kang_layout.addWidget(info)

        # Основные параметры
        main_params = QGroupBox("🔑 Основные параметры")
        mp_layout = QGridLayout(main_params)
        mp_layout.setSpacing(10)
        mp_layout.setColumnStretch(1, 2)

        mp_layout.addWidget(QLabel("Публичный ключ (Hex):"), 0, 0)
        self.parent.kang_pubkey_edit = QLineEdit()
        self.parent.kang_pubkey_edit.setPlaceholderText("02.../03... (66) или 04... (130)")
        mp_layout.addWidget(self.parent.kang_pubkey_edit, 0, 1)

        mp_layout.addWidget(QLabel("Начало диапазона:"), 1, 0)
        self.parent.kang_start_key_edit = QLineEdit("1")
        mp_layout.addWidget(self.parent.kang_start_key_edit, 1, 1)

        mp_layout.addWidget(QLabel("Конец диапазона:"), 2, 0)
        self.parent.kang_end_key_edit = QLineEdit("FFFFFFFFFFFFFFFF")
        mp_layout.addWidget(self.parent.kang_end_key_edit, 2, 1)

        kang_layout.addWidget(main_params)

        # Параметры алгоритма
        algo_params = QGroupBox("⚙️ Параметры алгоритма")
        ap_layout = QGridLayout(algo_params)
        ap_layout.setSpacing(10)

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
        paths = QGroupBox("📁 Пути к файлам")
        pl = QGridLayout(paths)

        pl.addWidget(QLabel("Etarkangaroo.exe:"), 0, 0)
        self.parent.kang_exe_edit = QLineEdit()
        self.parent.kang_exe_edit.setText(
            os.path.join(config.BASE_DIR, "Etarkangaroo.exe")
        )
        pl.addWidget(self.parent.kang_exe_edit, 0, 1)

        self.parent.kang_browse_exe_btn = QPushButton("📁")
        self.parent.kang_browse_exe_btn.setFixedWidth(40)
        self.parent.kang_browse_exe_btn.clicked.connect(self.parent.browse_kangaroo_exe)
        pl.addWidget(self.parent.kang_browse_exe_btn, 0, 2)

        pl.addWidget(QLabel("Временная директория:"), 1, 0)
        self.parent.kang_temp_dir_edit = QLineEdit()
        self.parent.kang_temp_dir_edit.setText(
            os.path.join(config.BASE_DIR, "kangaroo_temp")
        )
        pl.addWidget(self.parent.kang_temp_dir_edit, 1, 1)

        self.parent.kang_browse_temp_btn = QPushButton("📁")
        self.parent.kang_browse_temp_btn.setFixedWidth(40)
        pl.addWidget(self.parent.kang_browse_temp_btn, 1, 2)

        kang_layout.addWidget(paths)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.parent.kang_auto_config_btn = QPushButton("🔧 Автонастройка")
        set_button_style(self.parent.kang_auto_config_btn, "primary")
        self.parent.kang_auto_config_btn.setMinimumHeight(40)

        self.parent.kang_start_stop_btn = QPushButton("🚀 Запустить Kangaroo")
        set_button_style(self.parent.kang_start_stop_btn, "success")
        self.parent.kang_start_stop_btn.setMinimumHeight(40)

        btn_layout.addWidget(self.parent.kang_auto_config_btn, 1)
        btn_layout.addWidget(self.parent.kang_start_stop_btn, 2)
        kang_layout.addLayout(btn_layout)

        # Статус
        status_group = QGroupBox("📊 Прогресс")
        sl = QVBoxLayout(status_group)

        self.parent.kang_status_label = QLabel("🟢 Готов к запуску")
        self.parent.kang_status_label.setProperty("cssClass", "status")
        sl.addWidget(self.parent.kang_status_label)

        stats = QGridLayout()
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

        kang_layout.addWidget(status_group)
        kang_layout.addStretch()

        self.parent.main_tabs.addTab(kangaroo_tab, "🦘 Kangaroo")

    def _setup_vanity_tab(self):
        """Vanity поиск вкладка"""
        vanity_tab = QWidget()
        vanity_layout = QVBoxLayout(vanity_tab)
        vanity_layout.setContentsMargins(12, 12, 12, 12)
        vanity_layout.setSpacing(12)

        title = QLabel("🎨 VanitySearch - Генерация адресов")
        title.setProperty("cssClass", "section-title")
        vanity_layout.addWidget(title)

        info_v = QLabel(
            "Генерирует адреса с желаемым префиксом: 1Jasst, bc1qjasst и т.д.\n"
            "⚠️ Это только генерация, не поиск по целевому адресу."
        )
        info_v.setProperty("cssClass", "info-box-warning")
        info_v.setWordWrap(True)
        vanity_layout.addWidget(info_v)

        # Параметры
        main_v = QGroupBox("🔑 Параметры")
        mv_layout = QGridLayout(main_v)
        mv_layout.setSpacing(10)

        mv_layout.addWidget(QLabel("Префикс адреса:"), 0, 0)
        self.parent.vanity_prefix_edit = QLineEdit()
        self.parent.vanity_prefix_edit.setPlaceholderText("1Jasst или bc1qj")
        mv_layout.addWidget(self.parent.vanity_prefix_edit, 0, 1, 1, 2)

        mv_layout.addWidget(QLabel("Тип адреса:"), 1, 0)
        self.parent.vanity_type_combo = QComboBox()
        self.parent.vanity_type_combo.addItems(
            ["P2PKH (1...)", "P2SH-P2WPKH (3...)", "Bech32 (bc1...)", "Bech32m (bc1...)"]
        )
        mv_layout.addWidget(self.parent.vanity_type_combo, 1, 1)

        self.parent.vanity_compressed_cb = QCheckBox("Сжатый ключ")
        self.parent.vanity_compressed_cb.setChecked(True)
        mv_layout.addWidget(self.parent.vanity_compressed_cb, 1, 2)

        vanity_layout.addWidget(main_v)

        # Исполнение
        exec_v = QGroupBox("⚙️ Параметры выполнения")
        ev_layout = QGridLayout(exec_v)

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

        # Кнопка запуска
        self.parent.vanity_start_stop_btn = QPushButton("🚀 Запустить генерацию")
        set_button_style(self.parent.vanity_start_stop_btn, "vanity")
        self.parent.vanity_start_stop_btn.setMinimumHeight(48)
        vanity_layout.addWidget(self.parent.vanity_start_stop_btn)

        # Статистика
        stat_v = QGroupBox("📊 Статус")
        sv_layout = QGridLayout(stat_v)

        self.parent.vanity_status_label = QLabel("🟢 Готов")
        self.parent.vanity_status_label.setProperty("cssClass", "status")
        sv_layout.addWidget(self.parent.vanity_status_label, 0, 0, 1, 2)

        self.parent.vanity_speed_label = QLabel("⚡ 0 Keys/s")
        sv_layout.addWidget(self.parent.vanity_speed_label, 1, 0)

        self.parent.vanity_time_label = QLabel("⏱ 00:00:00")
        sv_layout.addWidget(self.parent.vanity_time_label, 1, 1)

        self.parent.vanity_found_label = QLabel("✨ Найдено: 0")
        self.parent.vanity_found_label.setProperty("cssClass", "found")
        sv_layout.addWidget(self.parent.vanity_found_label, 2, 0, 1, 2)

        self.parent.vanity_progress_bar = QProgressBar()
        self.parent.vanity_progress_bar.setRange(0, 0)
        self.parent.vanity_progress_bar.setFormat("Работает...")
        sv_layout.addWidget(self.parent.vanity_progress_bar, 3, 0, 1, 2)

        vanity_layout.addWidget(stat_v)

        # Результат
        result_v = QGroupBox("✅ Результат")
        rv_layout = QGridLayout(result_v)

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

        copy_btn = QPushButton("📋 Копировать результат")
        copy_btn.clicked.connect(self.parent.copy_vanity_result)
        rv_layout.addWidget(copy_btn, 3, 0, 1, 2)

        vanity_layout.addWidget(result_v)
        vanity_layout.addStretch()

        self.parent.main_tabs.addTab(vanity_tab, "🎨 Vanity")

    def _setup_found_keys_tab(self):
        """Вкладка найденных ключей"""
        keys_tab = QWidget()
        keys_layout = QVBoxLayout(keys_tab)
        keys_layout.setContentsMargins(12, 12, 12, 12)
        keys_layout.setSpacing(12)

        title = QLabel("✨ Найденные приватные ключи")
        title.setProperty("cssClass", "section-title")
        keys_layout.addWidget(title)

        # Таблица
        self.parent.found_keys_table = QTableWidget(0, 5)
        self.parent.found_keys_table.setHorizontalHeaderLabels(
            ["Время", "Адрес", "HEX ключ", "WIF ключ", "Источник"]
        )
        self.parent.found_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parent.found_keys_table.verticalHeader().setVisible(False)
        self.parent.found_keys_table.setAlternatingRowColors(True)
        self.parent.found_keys_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.parent.found_keys_table.customContextMenuRequested.connect(
            self.parent.show_context_menu
        )
        keys_layout.addWidget(self.parent.found_keys_table, 1)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.parent.export_keys_btn = QPushButton("📤 Экспорт CSV")
        set_button_style(self.parent.export_keys_btn, "primary")
        self.parent.export_keys_btn.clicked.connect(self.parent.export_keys_csv)

        self.parent.save_all_btn = QPushButton("💾 Сохранить все")
        set_button_style(self.parent.save_all_btn, "success")
        self.parent.save_all_btn.clicked.connect(self.parent.save_all_found_keys)

        btn_layout.addWidget(self.parent.export_keys_btn)
        btn_layout.addWidget(self.parent.save_all_btn)
        btn_layout.addStretch()
        keys_layout.addLayout(btn_layout)

        self.parent.main_tabs.addTab(keys_tab, "✨ Результаты")

    def _setup_log_tab(self):
        """Вкладка логов"""
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.setSpacing(12)

        title = QLabel("📋 Логи приложения")
        title.setProperty("cssClass", "section-title")
        log_layout.addWidget(title)

        # Вывод логов
        self.parent.log_output = QTextEdit()
        self.parent.log_output.setReadOnly(True)
        self.parent.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.parent.log_output, 1)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.parent.clear_log_btn = QPushButton("🗑 Очистить логи")
        set_button_style(self.parent.clear_log_btn, "warning")

        self.parent.open_log_btn = QPushButton("📂 Открыть файл логов")
        set_button_style(self.parent.open_log_btn, "primary")
        self.parent.open_log_btn.clicked.connect(self.parent.open_log_file)

        btn_layout.addWidget(self.parent.clear_log_btn)
        btn_layout.addWidget(self.parent.open_log_btn)
        btn_layout.addStretch()
        log_layout.addLayout(btn_layout)

        self.parent.main_tabs.addTab(log_tab, "📋 Логи")

    def _setup_predict_tab(self):
        """Вкладка Predict - переработана в полный тему"""
        predict_tab = QWidget()
        predict_layout = QVBoxLayout(predict_tab)
        predict_layout.setContentsMargins(12, 12, 12, 12)
        predict_layout.setSpacing(12)

        title = QLabel("🔮 BTC Puzzle Analyzer v2")
        title.setProperty("cssClass", "section-title")
        predict_layout.addWidget(title)

        info_p = QLabel(
            "Загрузите файл с ключами → настройте параметры → запустите анализ → получите прогноз диапазона."
        )
        info_p.setProperty("cssClass", "info-box")
        info_p.setWordWrap(True)
        predict_layout.addWidget(info_p)

        # Основной контент в двух колонках
        main_split = QHBoxLayout()
        main_split.setSpacing(15)

        # --- ЛЕВАЯ КОЛОНКА (60%) ---
        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        # Статус анализа
        status_group = QGroupBox("📊 Статус анализа")
        status_layout = QVBoxLayout(status_group)

        self.parent.predict_status_label = QLabel("⏳ Ожидание запуска")
        self.parent.predict_status_label.setProperty("cssClass", "status")
        self.parent.predict_status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.parent.predict_status_label)

        self.parent.predict_progress_bar = QProgressBar()
        self.parent.predict_progress_bar.setRange(0, 100)
        self.parent.predict_progress_bar.setFormat("%p%")
        self.parent.predict_progress_bar.setMinimumHeight(32)
        self.parent.predict_progress_bar.hide()
        status_layout.addWidget(self.parent.predict_progress_bar)

        left_column.addWidget(status_group)

        # Результаты
        results_group = QGroupBox("📈 Основные результаты")
        results_layout = QVBoxLayout(results_group)

        self.parent.predict_results_table = QTableWidget(0, 2)
        self.parent.predict_results_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.parent.predict_results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.parent.predict_results_table.verticalHeader().setVisible(False)
        self.parent.predict_results_table.setAlternatingRowColors(True)
        self.parent.predict_results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parent.predict_results_table.setMinimumHeight(180)
        results_layout.addWidget(self.parent.predict_results_table)

        left_column.addWidget(results_group)

        # Диапазоны моделей
        ranges_group = QGroupBox("🔍 Диапазоны прогноза")
        ranges_layout = QVBoxLayout(ranges_group)

        self.parent.predict_ranges_table = QTableWidget(0, 4)
        self.parent.predict_ranges_table.setHorizontalHeaderLabels(
            ["Модель", "Диапазон (hex)", "Ширина", "📋"]
        )
        self.parent.predict_ranges_table.setColumnWidth(0, 100)
        self.parent.predict_ranges_table.setColumnWidth(1, 250)
        self.parent.predict_ranges_table.setColumnWidth(2, 100)
        self.parent.predict_ranges_table.setColumnWidth(3, 40)
        self.parent.predict_ranges_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.parent.predict_ranges_table.verticalHeader().setVisible(False)
        self.parent.predict_ranges_table.setAlternatingRowColors(True)
        self.parent.predict_ranges_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parent.predict_ranges_table.setMinimumHeight(150)

        ranges_layout.addWidget(self.parent.predict_ranges_table)
        left_column.addWidget(ranges_group)

        # График
        graph_group = QGroupBox("📊 Визуализация")
        graph_layout = QVBoxLayout(graph_group)

        self.parent.predict_scroll = QScrollArea()
        self.parent.predict_scroll.setWidgetResizable(True)
        self.parent.predict_scroll.setMinimumHeight(300)

        self.parent.predict_plot_label = QLabel(
            "📊 График появится после завершения анализа"
        )
        self.parent.predict_plot_label.setAlignment(Qt.AlignCenter)
        self.parent.predict_plot_label.setStyleSheet(
            f"""
            color: {COLORS_V2['text_secondary']};
            font-size: 11pt;
            padding: 40px;
            background: {COLORS_V2['bg_input']};
            border: 2px dashed {COLORS_V2['border']};
            border-radius: 6px;
            """
        )

        graph_container = QWidget()
        graph_container_layout = QVBoxLayout(graph_container)
        graph_container_layout.addWidget(self.parent.predict_plot_label)
        graph_container_layout.addStretch()
        self.parent.predict_scroll.setWidget(graph_container)

        graph_layout.addWidget(self.parent.predict_scroll)
        left_column.addWidget(graph_group, 1)

        # --- ПРАВАЯ КОЛОНКА (40%) ---
        right_column = QVBoxLayout()
        right_column.setSpacing(10)

        # Файл с данными
        file_group = QGroupBox("📁 Данные")
        file_layout = QGridLayout(file_group)

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

        # Параметры анализа (в скролле)
        params_scroll = QScrollArea()
        params_scroll.setWidgetResizable(True)
        params_scroll.setMaximumHeight(400)

        params_container = QWidget()
        params_group = QGroupBox("⚙️ Параметры")
        params_layout = QGridLayout(params_group)
        params_layout.setSpacing(8)

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

        self.parent.predict_ensemble_cb = QCheckBox("Ансамбль моделей")
        self.parent.predict_ensemble_cb.setChecked(True)
        params_layout.addWidget(self.parent.predict_ensemble_cb, 4, 0, 1, 2)

        params_container_layout = QVBoxLayout(params_container)
        params_container_layout.addWidget(params_group)
        params_container_layout.addStretch()
        params_scroll.setWidget(params_container)

        right_column.addWidget(params_scroll)

        # Кнопка запуска
        self.parent.predict_run_btn = QPushButton("🔮 Запустить анализ")
        set_button_style(self.parent.predict_run_btn, "predict")
        self.parent.predict_run_btn.setMinimumHeight(50)
        self.parent.predict_run_btn.setFont(QFont("", 11, QFont.Bold))
        right_column.addWidget(self.parent.predict_run_btn)

        # Экспорт
        self.parent.predict_export_btn = QPushButton("📥 Экспорт результатов")
        set_button_style(self.parent.predict_export_btn, "primary")
        right_column.addWidget(self.parent.predict_export_btn)

        right_column.addStretch()

        # Добавляем колонки в main layout
        main_split.addLayout(left_column, 3)
        main_split.addLayout(right_column, 2)

        predict_layout.addLayout(main_split)
        self.parent.main_tabs.addTab(predict_tab, "🔮 Predict")

    def _setup_about_tab(self):
        """О программе вкладка"""
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setContentsMargins(20, 20, 20, 20)
        about_layout.setSpacing(15)

        coincurve_status = "✓ Доступна" if is_coincurve_available() else "✗ Не установлена"
        cubitcrack_status = "✓ Найден" if os.path.exists(
            os.path.join(config.BASE_DIR, "cuBitcrack.exe")
        ) else "✗ Не найден"

        about_text = QLabel(
            f"""
            <div style='text-align:center; padding:30px; background:{COLORS_V2['bg_card']}; 
                        border-radius:10px; border:2px solid {COLORS_V2['border']};'>
                <h2 style='color:{COLORS_V2['accent_primary']}; margin:0 0 15px 0;'>
                    ⛏️ Bitcoin GPU/CPU Scanner
                </h2>
                <b style='font-size:13pt; color:{COLORS_V2['text_primary']};'>
                    Версия 5.0 Pro (Улучшенная)
                </b><br><br>
                <b>Автор:</b> Jasst<br>
                <b>GitHub:</b> <a href='https://github.com/Jasst' style='color:{COLORS_V2['accent_primary']};'>
                    github.com/Jasst
                </a><br><br>

                <b style='color:{COLORS_V2['accent_primary']}; font-size:11pt;'>Возможности:</b><br>
                <div style='text-align:left; display:inline-block; line-height:1.8;'>
                    🎮 GPU поиск через cuBitcrack<br>
                    💻 CPU мультипроцессинг<br>
                    🎲 Случайный/последовательный режим<br>
                    📊 Расширенная статистика<br>
                    ⚡ Авто-оптимизация параметров<br>
                    🎨 Vanity адрес генерация<br>
                    🦘 Kangaroo алгоритм<br>
                    🔮 Предиктивная аналитика<br>
                </div><br>

                <b style='color:{COLORS_V2['accent_primary']};'>Статус:</b><br>
                coincurve: <span style='color:{COLORS_V2['success'] if '✓' in coincurve_status else COLORS_V2['danger']};'>
                    {coincurve_status}
                </span><br>
                cuBitcrack.exe: <span style='color:{COLORS_V2['success'] if '✓' in cubitcrack_status else COLORS_V2['danger']};'>
                    {cubitcrack_status}
                </span>
            </div>
            """
        )
        about_text.setWordWrap(True)
        about_text.setOpenExternalLinks(True)
        about_layout.addWidget(about_text)
        about_layout.addStretch()

        self.parent.main_tabs.addTab(about_tab, "ℹ️ О программе")
