# ui/gpu_tab.py
import os
from PyQt5.QtCore import Qt, QTimer, QRegExp, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QRegExpValidator
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QMessageBox, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QProgressBar, QCheckBox, QComboBox, QSpinBox, QTabWidget, QFileDialog
)
# Предполагается, что config и helpers находятся в соответствующих местах
from logger import config
from utils.helpers import make_combo32, validate_key_range, format_time, is_coincurve_available
# Импорт pynvml (предполагается, что он установлен)
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None

class GpuTab(QWidget):
    """
    Вкладка для управления GPU поиском.
    Содержит UI элементы и методы обновления UI, связанные с GPU.
    """
    # Сигналы для коммуникации с GpuManager или MainWindow
    start_search_signal = pyqtSignal() # Запрос на запуск поиска
    stop_search_signal = pyqtSignal()  # Запрос на остановку поиска
    optimize_signal = pyqtSignal()     # Запрос на авто-оптимизацию

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gpu_range_label = None # Сохраняем ссылку, так как она обновляется
        self.gpu_monitor_available = PYNVML_AVAILABLE # Копируем флаг из main_window.py при инициализации
        self.setup_ui()
        self.setup_connections()
        # self.load_settings() # Загрузка настроек будет делегирована MainWindow или GpuManager

    def setup_ui(self):
        """Создает и компонует UI элементы для вкладки GPU."""
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
        gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0) # Новый ряд (индекс 5)
        self.gpu_workers_per_device_spin = QSpinBox()
        self.gpu_workers_per_device_spin.setRange(1, 16) # Или другой разумный максимум
        self.gpu_workers_per_device_spin.setValue(1) # По умолчанию 1 воркер
        gpu_param_layout.addWidget(self.gpu_workers_per_device_spin, 5, 1) # Новый ряд (индекс 5)
        # --- КОНЕЦ НОВОГО ---
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
        gpu_progress_layout.addWidget(self.gpu_progress_bar, 3, 0, 1, 2)
        layout.addWidget(gpu_progress_group)
        self.gpu_progress_bar.setStyleSheet("""
                    QProgressBar {height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20;}
                    QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px;}
                """)
        self.gpu_range_label = QLabel("Текущий диапазон: -")
        self.gpu_range_label.setStyleSheet("font-weight: bold; color: #e67e22;")
        layout.addWidget(self.gpu_range_label)

        # =============== НОВОЕ: GPU Status Group ===============
        if self.gpu_monitor_available:
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
            layout.addWidget(self.gpu_hw_status_group)
        # =============== КОНЕЦ НОВОГО ===============

    def setup_connections(self):
        """Подключает сигналы UI к слотам."""
        self.gpu_start_stop_btn.clicked.connect(self.on_start_stop_clicked)
        self.gpu_optimize_btn.clicked.connect(self.on_optimize_clicked)
        # Таймеры и другие подключения могут быть добавлены позже или управляться извне

    @pyqtSlot()
    def on_start_stop_clicked(self):
        """Слот для обработки нажатия кнопки Start/Stop."""
        # Логика определения, запущен ли поиск, будет в GpuManager или MainWindow
        # Здесь просто эмитируем сигнал
        self.start_search_signal.emit() # или stop_search_signal.emit() в зависимости от состояния

    @pyqtSlot()
    def on_optimize_clicked(self):
        """Слот для обработки нажатия кнопки Auto-оптимизация."""
        self.optimize_signal.emit()

    # --- Методы обновления UI ---

    @pyqtSlot(str) # Пример: принимает сообщение статуса
    def update_status_label(self, status_text):
        """Обновляет текст метки статуса."""
        self.gpu_status_label.setText(status_text)

    @pyqtSlot(float) # Пример: принимает скорость в MKey/s
    def update_speed_label(self, speed_mkeys):
        """Обновляет текст метки скорости."""
        self.gpu_speed_label.setText(f"Скорость: {speed_mkeys:.2f} MKey/s")

    @pyqtSlot(str) # Пример: принимает отформатированное время
    def update_time_label(self, time_str):
        """Обновляет текст метки времени работы."""
        self.gpu_time_label.setText(time_str)

    @pyqtSlot(int) # Пример: принимает количество проверенных ключей
    def update_checked_label(self, keys_checked):
        """Обновляет текст метки проверенных ключей."""
        self.gpu_checked_label.setText(f"Проверено ключей: {keys_checked:,}")

    @pyqtSlot(int) # Пример: принимает количество найденных ключей
    def update_found_label(self, found_count):
        """Обновляет текст метки найденных ключей."""
        self.gpu_found_label.setText(f"Найдено ключей: {found_count}")

    @pyqtSlot(int, str) # Пример: принимает процент и форматированную строку
    def update_progress_bar(self, value, format_str):
        """Обновляет прогресс-бар."""
        self.gpu_progress_bar.setValue(value)
        self.gpu_progress_bar.setFormat(format_str)

    @pyqtSlot(str, str) # Пример: принимает начальный и конечный hex
    def update_range_label(self, start_hex, end_hex):
        """Обновляет текст метки текущего диапазона."""
        if start_hex == "-" and end_hex == "-":
            self.gpu_range_label.setText("Текущий диапазон: -")
        else:
            self.gpu_range_label.setText(
                f"Текущий диапазон: <span style='color:#f39c12'>{start_hex}</span> - <span style='color:#f39c12'>{end_hex}</span>")

    # --- Методы обновления аппаратного статуса ---

    @pyqtSlot(int, int, float, float, int) # Пример сигнатуры
    def update_gpu_hardware_status(self, gpu_util, mem_used_mb, mem_total_mb, mem_util, temperature):
        """Обновляет отображение аппаратного статуса GPU."""
        if not self.gpu_monitor_available:
             return

        # Обновляем UI
        self.gpu_util_label.setText(f"Загрузка GPU: {gpu_util} %")
        self.gpu_util_bar.setValue(gpu_util)
        self.gpu_mem_label.setText(f"Память GPU: {mem_used_mb:.0f} / {mem_total_mb:.0f} MB ({mem_util:.1f}%)")
        self.gpu_mem_bar.setValue(int(mem_util))
        if temperature is not None:
            self.gpu_temp_label.setText(f"Температура: {temperature} °C")
            # Цветовая индикация температуры
            if temperature > 80:
                self.gpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;") # Красный при высокой температуре
            elif temperature > 65:
                self.gpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;") # Оранжевый
            else:
                self.gpu_temp_label.setStyleSheet("color: #27ae60;") # Зеленый
        else:
            self.gpu_temp_label.setText("Температура: - °C")
            self.gpu_temp_label.setStyleSheet("color: #7f8c8d;") # Серый

    # --- Методы для получения значений UI ---

    def get_target_address(self):
        """Возвращает адрес из поля ввода."""
        return self.gpu_target_edit.text().strip()

    def get_start_key_hex(self):
        """Возвращает начальный ключ в hex."""
        return self.gpu_start_key_edit.text().strip()

    def get_end_key_hex(self):
        """Возвращает конечный ключ в hex."""
        return self.gpu_end_key_edit.text().strip()

    def get_device_combo_text(self):
        """Возвращает текст из комбо-бокса устройств."""
        return self.gpu_device_combo.currentText()

    def get_blocks_text(self):
        """Возвращает текст из комбо-бокса блоков."""
        return self.blocks_combo.currentText()

    def get_threads_text(self):
        """Возвращает текст из комбо-бокса потоков."""
        return self.threads_combo.currentText()

    def get_points_text(self):
        """Возвращает текст из комбо-бокса точек."""
        return self.points_combo.currentText()

    def is_random_mode_checked(self):
        """Возвращает состояние чекбокса случайного режима."""
        return self.gpu_random_checkbox.isChecked()

    def get_restart_interval_text(self):
        """Возвращает текст из комбо-бокса интервала рестарта."""
        return self.gpu_restart_interval_combo.currentText()

    def get_min_range_text(self):
        """Возвращает текст из поля ввода мин. размера диапазона."""
        return self.gpu_min_range_edit.text().strip()

    def get_max_range_text(self):
        """Возвращает текст из поля ввода макс. размера диапазона."""
        return self.gpu_max_range_edit.text().strip()

    def get_priority_index(self):
        """Возвращает индекс выбранного приоритета."""
        return self.gpu_priority_combo.currentIndex()

    def get_workers_per_device_value(self):
        """Возвращает значение из спинбокса воркеров на устройство."""
        return self.gpu_workers_per_device_spin.value()

    # --- Методы для установки значений UI (например, при загрузке настроек) ---

    def set_target_address(self, address):
        """Устанавливает адрес в поле ввода."""
        self.gpu_target_edit.setText(address)

    def set_start_key_hex(self, hex_str):
        """Устанавливает начальный ключ в hex."""
        self.gpu_start_key_edit.setText(hex_str)

    def set_end_key_hex(self, hex_str):
        """Устанавливает конечный ключ в hex."""
        self.gpu_end_key_edit.setText(hex_str)

    def set_device_combo_text(self, text):
        """Устанавливает текст в комбо-боксе устройств."""
        self.gpu_device_combo.setCurrentText(text)

    def set_blocks_text(self, text):
        """Устанавливает текст в комбо-боксе блоков."""
        self.blocks_combo.setCurrentText(text)

    def set_threads_text(self, text):
        """Устанавливает текст в комбо-боксе потоков."""
        self.threads_combo.setCurrentText(text)

    def set_points_text(self, text):
        """Устанавливает текст в комбо-боксе точек."""
        self.points_combo.setCurrentText(text)

    def set_random_mode_checked(self, checked):
        """Устанавливает состояние чекбокса случайного режима."""
        self.gpu_random_checkbox.setChecked(checked)

    def set_restart_interval_text(self, text):
        """Устанавливает текст в комбо-боксе интервала рестарта."""
        self.gpu_restart_interval_combo.setCurrentText(text)

    def set_min_range_text(self, text):
        """Устанавливает текст в поле ввода мин. размера диапазона."""
        self.gpu_min_range_edit.setText(text)

    def set_max_range_text(self, text):
        """Устанавливает текст в поле ввода макс. размера диапазона."""
        self.gpu_max_range_edit.setText(text)

    def set_priority_index(self, index):
        """Устанавливает индекс выбранного приоритета."""
        self.gpu_priority_combo.setCurrentIndex(index)

    def set_workers_per_device_value(self, value):
        """Устанавливает значение в спинбоксе воркеров на устройство."""
        self.gpu_workers_per_device_spin.setValue(value)

    # --- Методы для управления состоянием кнопок ---

    @pyqtSlot(bool) # Пример: принимает True для "Остановить", False для "Запустить"
    def set_start_stop_button_state(self, is_running):
        """Устанавливает текст и стиль кнопки Start/Stop."""
        if is_running:
            self.gpu_start_stop_btn.setText("Остановить GPU")
            self.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
        else:
            self.gpu_start_stop_btn.setText("Запустить GPU поиск")
            self.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    @pyqtSlot(bool) # Пример: принимает True для включения, False для отключения
    def set_restart_interval_enabled(self, enabled):
        """Включает/отключает комбо-бокс интервала рестарта."""
        self.gpu_restart_interval_combo.setEnabled(enabled)

    # --- Методы для сброса UI ---

    @pyqtSlot()
    def reset_ui_on_finish(self):
        """Сбрасывает UI элементы при завершении поиска."""
        # Сброс прогресс бара
        self.gpu_progress_bar.setValue(0)
        self.gpu_progress_bar.setFormat("Прогресс: готов к запуску")
        self.gpu_speed_label.setText("Скорость: 0 MKey/s")
        self.gpu_checked_label.setText("Проверено ключей: 0")
        self.gpu_found_label.setText("Найдено ключей: 0")
        self.gpu_time_label.setText("Время работы: 00:00:00")
        # Сброс статуса
        self.gpu_status_label.setText("Статус: Завершено")
        # Сброс диапазона
        self.update_range_label("-", "-")
        # Сброс кнопки
        self.set_start_stop_button_state(False)
        # Сброс аппаратного статуса (если нужно)
        # self.update_gpu_hardware_status(0, 0, 0, 0, None) # Можно добавить

# Примечание: Этот класс не содержит логики запуска/остановки процессов,
# валидации ввода или сохранения/загрузки настроек. Эта логика должна быть
# в GpuManager или MainWindow.