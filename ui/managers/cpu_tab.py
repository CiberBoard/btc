# ui/cpu_tab.py
import multiprocessing
import os
import platform
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QRegExpValidator
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QMessageBox, QGroupBox, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QProgressBar, QCheckBox, QComboBox, QTabWidget, QFileDialog, QSpinBox, QFormLayout
)
# Предполагается, что config и helpers находятся в соответствующих местах
from logger import config
from utils.helpers import setup_logger, is_coincurve_available, validate_key_range, format_time

# Импорт psutil (предполагается, что он установлен)
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = setup_logger()


class CpuTab(QWidget):
    """
    Вкладка для управления CPU поиском.
    Содержит UI элементы и методы обновления UI, связанные с CPU.
    """
    # Сигналы для коммуникации с CpuManager или MainWindow
    start_search_signal = pyqtSignal()  # Запрос на запуск поиска
    stop_search_signal = pyqtSignal()  # Запрос на остановку поиска
    pause_search_signal = pyqtSignal()  # Запрос на паузу
    resume_search_signal = pyqtSignal()  # Запрос на продолжение

    def __init__(self, parent=None):
        super().__init__(parent)
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1) if PSUTIL_AVAILABLE else 1
        self.setup_ui()
        self.setup_connections()
        # self.load_settings() # Загрузка настроек будет делегирована MainWindow или CpuManager

    def setup_ui(self):
        """Создает и компонует UI элементы для вкладки CPU."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Системная информация
        sys_info_group = QGroupBox("Системная информация")
        sys_info_layout = QGridLayout(sys_info_group)
        sys_info_layout.setSpacing(6)

        # CPU Info Row
        sys_info_layout.addWidget(QLabel("Процессор:"), 0, 0)
        self.cpu_label = QLabel(f"{multiprocessing.cpu_count() if PSUTIL_AVAILABLE else 'N/A'} ядер")
        sys_info_layout.addWidget(self.cpu_label, 0, 1)
        sys_info_layout.addWidget(QLabel("Память:"), 0, 2)
        self.mem_label = QLabel("N/A")
        sys_info_layout.addWidget(self.mem_label, 0, 3)

        # Status Row
        sys_info_layout.addWidget(QLabel("Загрузка:"), 1, 0)
        self.cpu_usage = QLabel("0%")
        sys_info_layout.addWidget(self.cpu_usage, 1, 1)
        sys_info_layout.addWidget(QLabel("Статус:"), 1, 2)
        self.cpu_status_label = QLabel("Ожидание запуска")
        sys_info_layout.addWidget(self.cpu_status_label, 1, 3)

        layout.addWidget(sys_info_group)

        # =============== НОВОЕ: CPU Hardware Status Group ===============
        self.cpu_hw_status_group = QGroupBox("CPU: Аппаратный статус")
        cpu_hw_status_layout = QGridLayout(self.cpu_hw_status_group)
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
        layout.addWidget(self.cpu_hw_status_group)
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
        # self.cpu_mode_combo.currentIndexChanged.connect(self.on_cpu_mode_changed) # Подключение будет в setup_connections
        self.cpu_mode_combo.setFixedWidth(param_input_width)
        cpu_scan_params_layout.addWidget(self.cpu_mode_combo, 1, 1)
        cpu_scan_params_layout.addWidget(QLabel("Рабочих:"), 1, 2)
        self.cpu_workers_spin = QSpinBox()
        max_workers = (multiprocessing.cpu_count() * 2) if PSUTIL_AVAILABLE else 8
        self.cpu_workers_spin.setRange(1, max_workers)
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

        layout.addWidget(cpu_params_group)

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
        layout.addWidget(self.cpu_workers_table, 1)

    def setup_connections(self):
        """Подключает сигналы UI к слотам."""
        self.cpu_start_stop_btn.clicked.connect(self.on_start_stop_clicked)
        self.cpu_pause_resume_btn.clicked.connect(self.on_pause_resume_clicked)
        self.cpu_mode_combo.currentIndexChanged.connect(self.on_cpu_mode_changed)
        # Устанавливаем горячие клавиши
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))

    @pyqtSlot()
    def on_start_stop_clicked(self):
        """Слот для обработки нажатия кнопки Start/Stop."""
        # Логика определения, запущен ли поиск, будет в CpuManager или MainWindow
        # Здесь просто эмитируем сигнал
        self.start_search_signal.emit()  # или stop_search_signal.emit() в зависимости от состояния

    @pyqtSlot()
    def on_pause_resume_clicked(self):
        """Слот для обработки нажатия кнопки Pause/Resume."""
        # Логика определения, на паузе ли поиск, будет в CpuManager или MainWindow
        # Здесь просто эмитируем сигнал
        self.pause_search_signal.emit()  # или resume_search_signal.emit() в зависимости от состояния

    @pyqtSlot(int)
    def on_cpu_mode_changed(self, index):
        """Слот для обработки изменения режима поиска."""
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)
        # cpu_mode будет установлен в менеджере или главном окне

    # --- Методы обновления UI ---

    @pyqtSlot(str, str, str, str)  # cpu_label, mem_label, cpu_usage, cpu_status_label
    def update_system_info_labels(self, cpu_text, mem_text, usage_text, status_text):
        """Обновляет тексты меток системной информации."""
        self.cpu_label.setText(cpu_text)
        self.mem_label.setText(mem_text)
        self.cpu_usage.setText(usage_text)
        self.cpu_status_label.setText(status_text)

    @pyqtSlot(float)  # Температура CPU
    def update_cpu_temperature(self, temperature):
        """Обновляет отображение температуры CPU."""
        if temperature is not None:
            self.cpu_temp_label.setText(f"Температура: {temperature:.1f} °C")
            self.cpu_temp_bar.setValue(int(temperature))
            self.cpu_temp_bar.setFormat(f"Темп: {temperature:.1f}°C")
            # Цветовая индикация температуры
            if temperature > 80:
                self.cpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")  # Красный
                self.cpu_temp_bar.setStyleSheet("""
                    QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                    QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);} /* Красный градиент */
                """)
            elif temperature > 65:
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

    @pyqtSlot(str)  # Текст статуса
    def update_cpu_status_label(self, status_text):
        """Обновляет текст метки статуса CPU."""
        self.cpu_status_label.setText(status_text)

    @pyqtSlot(str)  # ETA текст
    def update_eta_label(self, eta_text):
        """Обновляет текст метки оставшегося времени."""
        self.cpu_eta_label.setText(eta_text)

    @pyqtSlot(str)  # Текст общей статистики
    def update_total_stats_label(self, stats_text):
        """Обновляет текст метки общей статистики."""
        self.cpu_total_stats_label.setText(stats_text)

    @pyqtSlot(int)  # Значение прогресса
    def update_total_progress_bar(self, value):
        """Обновляет значение прогресс-бара."""
        self.cpu_total_progress.setValue(value)

    @pyqtSlot(int, dict)  # worker_id, stats_dict
    def update_worker_row(self, worker_id, stats):
        """Обновляет строку статистики для конкретного воркера."""
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

    # --- Методы для получения значений UI ---

    def get_target_address(self):
        """Возвращает адрес из поля ввода."""
        return self.cpu_target_edit.text().strip()

    def get_start_key_hex(self):
        """Возвращает начальный ключ в hex."""
        return self.cpu_start_key_edit.text().strip()

    def get_end_key_hex(self):
        """Возвращает конечный ключ в hex."""
        return self.cpu_end_key_edit.text().strip()

    def get_prefix_length(self):
        """Возвращает длину префикса."""
        return self.cpu_prefix_spin.value()

    def get_attempts_text(self):
        """Возвращает текст из поля попыток."""
        return self.cpu_attempts_edit.text().strip()

    def get_mode_index(self):
        """Возвращает индекс выбранного режима."""
        return self.cpu_mode_combo.currentIndex()

    def get_workers_count(self):
        """Возвращает количество воркеров."""
        return self.cpu_workers_spin.value()

    def get_priority_index(self):
        """Возвращает индекс выбранного приоритета."""
        return self.cpu_priority_combo.currentIndex()

    # --- Методы для установки значений UI (например, при загрузке настроек) ---

    def set_target_address(self, address):
        """Устанавливает адрес в поле ввода."""
        self.cpu_target_edit.setText(address)

    def set_start_key_hex(self, hex_str):
        """Устанавливает начальный ключ в hex."""
        self.cpu_start_key_edit.setText(hex_str)

    def set_end_key_hex(self, hex_str):
        """Устанавливает конечный ключ в hex."""
        self.cpu_end_key_edit.setText(hex_str)

    def set_prefix_length(self, value):
        """Устанавливает длину префикса."""
        self.cpu_prefix_spin.setValue(value)

    def set_attempts_text(self, text):
        """Устанавливает текст в поле попыток."""
        self.cpu_attempts_edit.setText(text)

    def set_mode_index(self, index):
        """Устанавливает индекс выбранного режима."""
        self.cpu_mode_combo.setCurrentIndex(index)

    def set_workers_count(self, count):
        """Устанавливает количество воркеров."""
        self.cpu_workers_spin.setValue(count)

    def set_priority_index(self, index):
        """Устанавливает индекс выбранного приоритета."""
        self.cpu_priority_combo.setCurrentIndex(index)

    # --- Методы для управления состоянием кнопок ---

    @pyqtSlot(bool)  # Пример: принимает True для "Остановить", False для "Запустить"
    def set_start_stop_button_state(self, is_running):
        """Устанавливает текст и стиль кнопки Start/Stop."""
        if is_running:
            self.cpu_start_stop_btn.setText("Стоп CPU (Ctrl+Q)")
            self.cpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
        else:
            self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
            self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    @pyqtSlot(bool)  # Пример: принимает True для включения, False для отключения
    def set_pause_resume_button_state(self, is_paused):
        """Устанавливает текст, стиль и доступность кнопки Pause/Resume."""
        if is_paused:
            self.cpu_pause_resume_btn.setText("Продолжить")
            self.cpu_pause_resume_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        else:
            self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
            self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")
        self.cpu_pause_resume_btn.setEnabled(not is_running)  # Доступна только если запущен

    @pyqtSlot(bool)  # Пример: принимает True для включения, False для отключения
    def set_pause_resume_button_enabled(self, enabled):
        """Включает/отключает кнопку Pause/Resume."""
        self.cpu_pause_resume_btn.setEnabled(enabled)

    # --- Методы для сброса UI ---

    @pyqtSlot()
    def reset_ui_on_finish(self):
        """Сбрасывает UI элементы при завершении поиска."""
        # Сброс статуса
        self.cpu_status_label.setText("Ожидание запуска")
        # Сброс прогресса
        self.cpu_total_progress.setValue(0)
        self.cpu_total_stats_label.setText("Статус: Завершено")
        self.cpu_eta_label.setText("Оставшееся время: -")
        # Сброс кнопок
        self.set_start_stop_button_state(False)
        self.set_pause_resume_button_enabled(False)
        self.set_pause_resume_button_state(False)
        # Очистка таблицы статистики воркеров
        self.cpu_workers_table.setRowCount(0)

    @pyqtSlot()
    def clear_worker_table(self):
        """Очищает таблицу статистики воркеров."""
        self.cpu_workers_table.setRowCount(0)

# Примечание: Этот класс не содержит логики запуска/остановки процессов,
# валидации ввода или сохранения/загрузки настроек. Эта логика должна быть
# в CpuManager или MainWindow.