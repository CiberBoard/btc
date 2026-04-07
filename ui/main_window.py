# ui/main_window.py
import os
import subprocess
import time
import json
import platform
import psutil
import multiprocessing
import queue
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QRegExp, pyqtSignal, QMetaObject
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QRegExpValidator, QCursor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QMessageBox, QGroupBox, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMenu, QProgressBar, QCheckBox, QComboBox, QTabWidget,
                             QFileDialog, QSpinBox, QSizePolicy)
import config
from ui.ui_main import MainWindowUI
from ui.theme import apply_dark_theme
from utils.helpers import setup_logger, format_time, is_coincurve_available, make_combo32
from ui.kangaroo_logic import KangarooLogic
from core.hextowif import generate_all_from_hex
# В main_window.py добавьте импорт вверху:
from ui.hex_calc_window import HexCalcWindow
from ui.gpu_monitor_window import GPUMonitorWindow  # <-- ДОБАВИТЬ ЭТУ СТРОКУ



try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None
import logging  # ← ДОБАВЛЕНО

logger = logging.getLogger(__name__)

# Импорт логики
from ui.gpu_logic import GPULogic
from ui.cpu_logic import CPULogic
from ui.vanity_logic import VanityLogic
# В начале файла, после других импортов
# В методе run_predict_analysis (добавьте в начало метода):



class BitcoinGPUCPUScanner(QMainWindow):
    # ==================== КОНСТАНТЫ ====================
    # Таймеры (мс)
    QUEUE_TIMER_INTERVAL = 100
    SYSINFO_TIMER_INTERVAL = 2000
    GPU_STATUS_TIMER_INTERVAL = 1500
    GPU_STATS_TIMER_INTERVAL = 500
    HEALTH_CHECK_INTERVAL = 60000  # 1 минута

    # Обработка очереди
    MAX_QUEUE_MESSAGES = 100
    MAX_QUEUE_PROCESS_TIME = 0.1  # секунды

    # GPU мониторинг
    GPU_TEMP_WARNING = 65
    GPU_TEMP_CRITICAL = 80
    CPU_TEMP_WARNING = 65
    CPU_TEMP_CRITICAL = 80

    # Shutdown
    SHUTDOWN_TIMEOUT = 5  # секунд

    # Память (байты)
    MEMORY_WARNING_THRESHOLD = 2 * 1024 * 1024 * 1024  # 2GB

    # Очередь
    QUEUE_SIZE_WARNING = 1000

    # ✅ Объявляем сигнал на уровне КЛАССА
    vanity_update_ui_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        # ✅ Экспортируем константы для UI
        self.MAX_KEY_HEX = config.MAX_KEY_HEX
        self.BASE_DIR = config.BASE_DIR

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
        self.selected_gpu_device_id = 0

        # CPU variables - ИНИЦИАЛИЗИРУЕМ РАНЬШЕ setup_ui
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)

        # --- Инициализация логики ---
        self.gpu_logic = GPULogic(self)
        self.cpu_logic = CPULogic(self)
        self.kangaroo_logic = KangarooLogic(self)
        self.vanity_logic = VanityLogic(self)

        # ✅ Подключаем сигнал — ПОСЛЕ создания vanity_logic
        self.vanity_update_ui_signal.connect(self.vanity_logic.handle_stats)

        apply_dark_theme(self)
        self.ui = MainWindowUI(self)
        self.ui.setup_ui()
        self.setup_connections()  # <-- setup_connections вызывается ПОСЛЕ инициализации логики
        self.load_settings()

        # Создаем файл для найденных ключей, если его нет
        self.ensure_file_exists(config.FOUND_KEYS_FILE)

        # --- Инициализация таймеров ---
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(self.QUEUE_TIMER_INTERVAL)

        # Health check timer
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.health_check)
        self.health_timer.start(self.HEALTH_CHECK_INTERVAL)

        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900)

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def ensure_file_exists(self, filepath: str) -> None:
        """Гарантирует существование файла"""
        Path(filepath).touch(exist_ok=True)

    def safe_set_text(self, widget_name: str, text: str) -> None:
        """Безопасная установка текста с проверкой существования виджета"""
        if hasattr(self, widget_name):
            widget = getattr(self, widget_name)
            if widget is not None:
                try:
                    widget.setText(text)
                except Exception:
                    pass

    def safe_set_value(self, widget_name: str, value: int) -> None:
        """Безопасная установка значения прогресс-бара"""
        if hasattr(self, widget_name):
            widget = getattr(self, widget_name)
            if widget is not None:
                try:
                    widget.setValue(int(value))
                except Exception:
                    pass

    def set_busy(self, busy: bool = True) -> None:
        """Устанавливает курсор ожидания"""
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def emit_vanity_stats(self, stats: Dict[str, Any]) -> None:
        """Эмитит сигнал статистики vanity"""
        self.vanity_update_ui_signal.emit(stats)

    # КАЛЬКУЛЯТОР
    def open_hex_calculator(self):
        """Открывает окно HEX-калькулятора"""
        if not hasattr(self, 'hex_calc_window') or not self.hex_calc_window:
            self.hex_calc_window = HexCalcWindow(self)
        self.hex_calc_window.show()
        self.hex_calc_window.raise_()
        self.hex_calc_window.activateWindow()

    # ▼▼▼ ВСТАВИТЬ СЮДА ▼▼▼
    def open_gpu_monitor(self):
        """Открывает окно мониторинга GPU с защитой от удаленных объектов"""
        try:
            from ui.gpu_monitor_window import GPUMonitorWindow

            # 1️⃣ Если ссылки нет или она "None" — создаем окно
            if not hasattr(self, 'gpu_monitor_window') or self.gpu_monitor_window is None:
                self.gpu_monitor_window = GPUMonitorWindow(self)
                # ❌ УБРАНО: self.gpu_monitor_window.setAttribute(Qt.WA_DeleteOnClose)
                # Это главная причина ошибки. Qt будет скрывать окно, а не удалять его.

            try:
                # 2️⃣ Проверяем, живо ли окно и не свернуто ли оно
                if self.gpu_monitor_window.isVisible():
                    self.gpu_monitor_window.raise_()
                    self.gpu_monitor_window.activateWindow()
                    return
            except RuntimeError:
                # 🛡️ Если объект уже удален Qt, сбрасываем ссылку и создаем заново
                self.gpu_monitor_window = None
                self.gpu_monitor_window = GPUMonitorWindow(self)

            # 3️⃣ Показываем и выводим на передний план
            self.gpu_monitor_window.show()
            self.gpu_monitor_window.raise_()
            self.gpu_monitor_window.activateWindow()

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка открытия монитора GPU: {e}")
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось открыть монитор:\n{type(e).__name__}: {e}"
            )
    # ▲▲▲ КОНЕЦ ВСТАВКИ ▲▲▲

    # ==================== МЕТОДЫ НАВИГАЦИИ ====================

    def browse_kangaroo_exe(self) -> None:
        """Выбор файла etarkangaroo.exe"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите etarkangaroo.exe",
            config.BASE_DIR,
            "Executable Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self.kang_exe_edit.setText(file_path)
            self.append_log(f"Выбран файл: {file_path}", "success")

    def browse_kangaroo_temp(self) -> None:
        """Выбор временной директории"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите временную директорию",
            config.BASE_DIR
        )
        if dir_path:
            self.kang_temp_dir_edit.setText(dir_path)
            self.append_log(f"Выбрана директория: {dir_path}", "success")

    def copy_vanity_result(self) -> None:
        """Копирование результата vanity в буфер обмена"""
        parts = [
            self.vanity_result_addr.text().strip(),
            self.vanity_result_hex.text().strip(),
            self.vanity_result_wif.text().strip()
        ]
        text = "\n".join([p for p in parts if p])
        if text:
            QApplication.clipboard().setText(text)
            self.append_log("Результат Vanity скопирован", "success")

    # ==================== НАСТРОЙКА ПОДКЛЮЧЕНИЙ ====================

    def setup_connections(self) -> None:
        """Настройка всех подключений сигналов и слотов"""
        # GPU connections
        self.gpu_start_stop_btn.clicked.connect(self.gpu_logic.toggle_gpu_search)
        self.gpu_optimize_btn.clicked.connect(self.gpu_logic.auto_optimize_gpu_parameters)

        # CPU connections
        self.cpu_start_stop_btn.clicked.connect(self.cpu_logic.toggle_cpu_start_stop)
        self.cpu_pause_resume_btn.clicked.connect(self.cpu_logic.toggle_cpu_pause_resume)
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))

        # Vanity connections
        self.vanity_start_stop_btn.clicked.connect(self.vanity_logic.toggle_search)

        # Common connections
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())

        # GPU timers
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.gpu_logic.update_gpu_time_display)
        self.gpu_stats_timer.start(self.GPU_STATS_TIMER_INTERVAL)

        # System info timer (только здесь, не в __init__)
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(self.SYSINFO_TIMER_INTERVAL)

        # GPU Status Timer
        if self.gpu_monitor_available:
            self.gpu_status_timer = QTimer()
            self.gpu_status_timer.timeout.connect(self.update_gpu_status)
            self.gpu_status_timer.start(self.GPU_STATUS_TIMER_INTERVAL)
            self.selected_gpu_device_id = 0
        else:
            self.gpu_status_timer = None

        self.gpu_logic.setup_gpu_connections()

        # Predict connections
        self.setup_predict_connections()

    # ==================== КОНВЕРТЕР ====================

    def setup_converter_tab(self) -> None:
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

        self.result_fields: Dict[str, QLineEdit] = {}
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

        # ▼▼▼ ▼▼▼ ▼▼▼ НОВАЯ КНОПКА КАЛЬКУЛЯТОРА ▼▼▼ ▼▼▼ ▼▼▼
        # Кнопка открытия отдельного окна HEX-калькулятора
        calc_btn = QPushButton("🔢 Открыть HEX-калькулятор")
        calc_btn.setStyleSheet("""
            QPushButton {
                background: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #8e44ad;
            }
        """)
        calc_btn.clicked.connect(self.open_hex_calculator)
        layout.addWidget(calc_btn)
        # ▲▲▲ ▲▲▲ ▲▲▲ КОНЕЦ ВСТАВКИ ▲▲▲ ▲▲▲ ▲▲▲

        # Добавление вкладки в main_tabs (оригинальная строка — не менять)
        self.main_tabs.addTab(converter_tab, "Конвертер HEX → WIF")

    def on_generate_clicked(self) -> None:
        """Обработка нажатия кнопки генерации"""
        self.set_busy(True)
        try:
            hex_key = self.hex_input.text().strip()
            if not hex_key or len(hex_key) > 64 or not all(c in '0123456789abcdefABCDEF' for c in hex_key):
                QMessageBox.warning(self, "Ошибка", "Введите корректный HEX-ключ (до 64 символов).")
                return

            compressed = self.compressed_checkbox.isChecked()
            testnet = self.testnet_checkbox.isChecked()

            result = generate_all_from_hex(hex_key, compressed=compressed, testnet=testnet)
            for key, value in result.items():
                if key in self.result_fields:
                    self.result_fields[key].setText(value)
            self.append_log(f"Сгенерировано: {result['P2PKH']}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            logger.exception("Ошибка генерации ключа")
        finally:
            self.set_busy(False)

    def copy_to_clipboard(self) -> None:
        """Копирование поля в буфер обмена"""
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

    def on_cpu_mode_changed(self, index: int) -> None:
        """Обработка изменения режима CPU"""
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)
        self.cpu_logic.cpu_mode = "random" if is_random else "sequential"

    # ==================== PREDICT TAB METHODS ====================

    def setup_predict_connections(self):
        """Подключение сигналов вкладки Predict"""
        self.predict_browse_btn.clicked.connect(self.browse_predict_file)
        self.preview_keys_btn.clicked.connect(self.preview_predict_keys)
        self.predict_run_btn.clicked.connect(self.run_predict_analysis)

    def browse_predict_file(self):
        """Выбор файла с ключами"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл с ключами", config.BASE_DIR,
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            self.predict_file_edit.setText(file_path)
            self.load_keys_for_preview(file_path)

    def load_keys_for_preview(self, file_path: str):
        # ✅ ДОБАВИТЬ ЭТУ СТРОКУ:
        from ui.predict_logic import parse_keys_from_file, validate_keys

        """Загрузка и валидация ключей из файла ЛЮБОГО формата"""
        try:
            # Используем универсальный парсер из predict_logic.py
            raw_keys = parse_keys_from_file(file_path)
            valid_keys, error = validate_keys(raw_keys)

            if error or len(valid_keys) < 1:
                self.predict_keys_count_label.setText("0 валидных")
                self.append_log(f"⚠️ {error}", "warning")
                return

            self.predict_keys_count_label.setText(f"{len(valid_keys)} валидных ключей")
            self.append_log(f"✅ Загружено {len(valid_keys)} ключей из {os.path.basename(file_path)}", "success")

        except Exception as e:
            self.append_log(f"❌ Ошибка загрузки: {str(e)}", "error")

    def preview_predict_keys(self):
        # ✅ ДОБАВИТЬ ЭТУ СТРОКУ:
        from ui.predict_logic import parse_keys_from_file, validate_keys

        """Показать первые 10 ключей"""
        file_path = self.predict_file_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Предпросмотр", "Сначала выберите файл")
            return

        keys, _ = validate_keys(parse_keys_from_file(file_path))
        if not keys:
            QMessageBox.information(self, "Предпросмотр", "Валидные ключи не найдены")
            return

        preview = "\n".join([f"{i + 1}. {k[:32]}...{k[-8:]}" for i, k in enumerate(keys[:10])])
        if len(keys) > 10:
            preview += f"\n... и ещё {len(keys) - 10} ключей"
        QMessageBox.information(self, "Предпросмотр ключей", preview)

    def run_predict_analysis(self):
        from ui.predict_logic import PredictWorker, parse_keys_from_file, validate_keys

        file_path = self.predict_file_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Ошибка", "Выберите файл с ключами")
            return

        raw_keys = parse_keys_from_file(file_path)
        valid_keys, err = validate_keys(raw_keys)

        if err or len(valid_keys) < 3:
            QMessageBox.warning(self, "Ошибка", err or "Нужно минимум 3 ключа")
            return

        params = {
            'q_low': self.predict_q_low_spin.value() / 100,
            'q_high': self.predict_q_high_spin.value() / 100,
            'use_outlier_filter': self.predict_outlier_filter_cb.isChecked(),
            'weight_recent': self.predict_weight_recent_cb.isChecked(),
            'use_ensemble': self.predict_ensemble_cb.isChecked(),
            'use_gaussian_kde': self.predict_kde_cb.isChecked(),
            'use_spline_fit': self.predict_spline_cb.isChecked(),
            'ensemble_models': self.predict_ensemble_models_spin.value(),
            'output_plot': os.path.join(config.BASE_DIR, 'predict_analysis.png')
        }

        self.predict_status_label.setText("⏳ Запуск анализа...")
        self.predict_progress_bar.show()
        self.predict_progress_bar.setValue(0)
        self.predict_run_btn.setEnabled(False)
        self.predict_results_table.setRowCount(0)

        self.predict_worker = PredictWorker(valid_keys, params)
        self.predict_worker.progress_update.connect(self.on_predict_progress)
        self.predict_worker.analysis_finished.connect(self.on_predict_finished)
        self.predict_worker.error_occurred.connect(self.on_predict_error)
        self.predict_worker.start()

    def on_predict_progress(self, percent: int, message: str):
        """Обновление прогресс-бара"""
        self.predict_progress_bar.setValue(percent)
        self.predict_status_label.setText(f"⏳ {message}")

    def on_predict_finished(self, result: dict):
        """Обработка успешного завершения"""
        self.predict_progress_bar.hide()
        self.predict_run_btn.setEnabled(True)
        self.predict_status_label.setText("✅ Анализ завершён")

        # Заполнение таблицы
        rows_data = [
            ("🎯 Следующий Puzzle", f"#{result['next_puzzle']}"),
            ("📏 Сужение диапазона", f"{result['reduction_percent']:.2f}%"),
            ("📐 Min границы", f"0x{result['final_min_hex']}"),
            ("📐 Max границы", f"0x{result['final_max_hex']}"),
            ("📊 Ширина диапазона", f"{result['range_width']:.2e}"),
            ("⏱️ Время расчёта", f"{result.get('elapsed_seconds', 0):.2f} сек"),
            ("📈 Тренд (последние 5)", f"{result['stats']['recent_trend']:.6f}"),
        ]

        for param, value in rows_data:
            row = self.predict_results_table.rowCount()
            self.predict_results_table.insertRow(row)
            self.predict_results_table.setItem(row, 0, QTableWidgetItem(param))
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.predict_results_table.setItem(row, 1, item)

        # Отображение графика
        self.show_predict_plot(result.get('plot_path', ''))
        self.append_log(f"📊 Анализ завершён. Сужение: {result['reduction_percent']:.2f}%", "success")
        # Заполнение таблицы диапазонов
        self._fill_ranges_table(result.get('ranges', {}))

    def on_predict_error(self, error_msg: str):
        """Обработка ошибки"""
        self.predict_progress_bar.hide()
        self.predict_run_btn.setEnabled(True)
        self.predict_status_label.setText("❌ Ошибка выполнения")
        self.append_log(f"❌ {error_msg}", "error")
        QMessageBox.critical(self, "Ошибка анализа", error_msg)

    def show_predict_plot(self, plot_path: str):
        """Отображение графика с плавной загрузкой"""
        if not plot_path or not os.path.exists(plot_path) or os.path.getsize(plot_path) < 100:
            self.predict_plot_label.setText("📊 График: ожидание данных...")
            self.predict_plot_label.setStyleSheet("""
                QLabel { color: #7f8c8d; font-size: 11pt; padding: 20px; 
                         background: #1a2332; border: 2px dashed #34495e; border-radius: 6px; }
            """)
            return

        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(plot_path)
        if pixmap.isNull():
            self.predict_plot_label.setText("❌ Ошибка загрузки графика")
            return

        # Адаптивное масштабирование с сохранением пропорций
        max_width = max(600, self.predict_scroll.width() - 50)
        max_height = 500
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.predict_plot_label.setPixmap(pixmap)
        self.predict_plot_label.setText("")
        self.predict_plot_label.setStyleSheet("""
            QLabel {
                background: #1a2332;
                border: 1px solid #34495e;
                border-radius: 6px;
                padding: 10px;
            }
        """)

        # Центрируем контент
        if hasattr(self.predict_scroll, 'widget'):
            container = self.predict_scroll.widget()
            if container and container.layout():
                container.layout().setAlignment(Qt.AlignCenter)

    def export_predict_results(self):
        """Экспорт таблицы результатов"""
        if self.predict_results_table.rowCount() == 0:
            QMessageBox.information(self, "Экспорт", "Нет данных для экспорта")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результаты", "predict_results.txt", "Text Files (*.txt)"
        )
        if not path: return

        with open(path, 'w', encoding='utf-8') as f:
            f.write("BTC Puzzle Analyzer v2 - Результаты\n")
            f.write("=" * 50 + "\n")
            for row in range(self.predict_results_table.rowCount()):
                p = self.predict_results_table.item(row, 0).text()
                v = self.predict_results_table.item(row, 1).text()
                f.write(f"{p}: {v}\n")
        self.append_log(f"💾 Результаты сохранены в {path}", "success")

    def _fill_ranges_table(self, ranges: dict):
        """Заполняет таблицу диапазонов моделей с кнопками копирования"""
        if not hasattr(self, 'predict_ranges_table') or not ranges:
            return

        table = self.predict_ranges_table
        table.setRowCount(0)  # Очистка

        # Порядок, иконки и цвета
        order = [
            ('Position', '🔵', '#3498db'),
            ('LogGrowth', '🟢', '#2ecc71'),
            ('Ensemble', '🟠', '#e67e22'),
            ('Final', '🔴', '#e74c3c')
        ]

        for name, icon, color in order:
            if name not in ranges:
                continue
            r = ranges[name]
            row = table.rowCount()
            table.insertRow(row)

            # 1. Название модели
            item = QTableWidgetItem(f"{icon} {name}")
            item.setTextAlignment(Qt.AlignCenter)
            if name == 'Final':
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor(color))
            table.setItem(row, 0, item)

            # 2. Диапазон в hex (сокращённо)
            min_h = r.get('min_hex', '')
            max_h = r.get('max_hex', '')
            range_txt = f"{min_h[:16]}...{max_h[-16:]}" if min_h and max_h else "N/A"
            item = QTableWidgetItem(range_txt)
            item.setToolTip(f"Min: 0x{min_h}\nMax: 0x{max_h}" if min_h and max_h else "Нет данных")
            if name == 'Final':
                item.setForeground(QColor(color))
            table.setItem(row, 1, item)

            # 3. Ширина диапазона
            width = r.get('width', 0)
            width_txt = f"{width:.2e}" if width > 0 else "N/A"
            item = QTableWidgetItem(width_txt)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item.setToolTip(f"Ширина: {int(width):,} ключей" if width > 0 else "Ширина неизвестна")
            if name == 'Final':
                item.setForeground(QColor(color))
            table.setItem(row, 2, item)

            # 🔹 4. КНОПКА КОПИРОВАНИЯ
            copy_btn = QPushButton("📋")
            copy_btn.setFixedWidth(36)
            copy_btn.setFixedHeight(28)
            copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    border: 1px solid #34495e;
                    border-radius: 4px;
                    color: white;
                    font-weight: bold;
                    font-size: 10pt;
                }}
                QPushButton:hover {{
                    background: #ecf0f1;
                    color: #2c3e50;
                    border: 1px solid {color};
                }}
                QPushButton:pressed {{
                    background: #bdc3c7;
                }}
            """)
            # Сохраняем данные диапазона в кнопке
            copy_btn.setProperty('range_data', {
                'model': name,
                'min_hex': min_h,
                'max_hex': max_h,
                'width': width
            })
            # Подключаем сигнал
            copy_btn.clicked.connect(self._on_copy_range_clicked)

            # Центрируем кнопку в ячейке
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addStretch()
            btn_layout.addWidget(copy_btn)
            btn_layout.addStretch()
            table.setCellWidget(row, 3, btn_container)

    def _on_copy_range_clicked(self):
        """Обработчик кнопки копирования диапазона"""
        btn = self.sender()
        if not btn:
            return

        data = btn.property('range_data')
        if not data:
            return

        # Формируем текст для копирования (удобный для вставки в поиск)
        copy_text = (
            f"# {data['model']} range — BTC Puzzle Analyzer\n"
            f"start_key = \"{data['min_hex']}\"\n"
            f"end_key = \"{data['max_hex']}\"\n"
            f"# Ширина: {data['width']:.2e} ключей"
        )

        # Копируем в буфер обмена
        QApplication.clipboard().setText(copy_text)

        # Показываем уведомление
        model_name = data.get('model', 'Range')
        self.append_log(f"📋 Диапазон {model_name} скопирован в буфер обмена", "success")

        # Визуальная обратная связь на кнопке (мигание)
        original_style = btn.styleSheet()
        btn.setStyleSheet(original_style + "QPushButton { background: #2ecc71; }")
        QTimer.singleShot(200, lambda: btn.setStyleSheet(original_style))
    # ==================== МОНИТОРИНГ СИСТЕМЫ ====================

    def update_system_info(self) -> None:
        """Обновление системной информации"""
        try:
            mem = psutil.virtual_memory()
            self.safe_set_text('mem_label', f"{mem.used // (1024 * 1024)}/{mem.total // (1024 * 1024)} MB")
            self.safe_set_text('cpu_usage', f"{psutil.cpu_percent()}%")

            if self.cpu_logic.processes:
                status = "Работает" if not self.cpu_logic.cpu_pause_requested else "На паузе"
                self.safe_set_text('cpu_status_label', f"{status} ({len(self.cpu_logic.processes)} воркеров)")
            else:
                self.safe_set_text('cpu_status_label', "Ожидание запуска")

            # Температура CPU
            cpu_temp = self._get_cpu_temperature()
            self._update_cpu_temp_display(cpu_temp)

        except Exception as e:
            logger.exception("Ошибка обновления системной информации")
            self.safe_set_text('mem_label', "Ошибка данных")
            self.safe_set_text('cpu_usage', "Ошибка данных")
            self.safe_set_text('cpu_status_label', "Ошибка данных")
            self._update_cpu_temp_display(None)

    def _get_cpu_temperature(self) -> Optional[float]:
        """Получение температуры CPU"""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None

            # Приоритетные сенсоры
            priority_sensors = ['coretemp', 'k10temp', 'cpu_thermal', 'acpi']

            for name in priority_sensors:
                if name in temps:
                    for entry in temps[name]:
                        if entry.current is not None:
                            if 'package' in entry.label.lower() or entry.label == '':
                                return entry.current

            # fallback: первая доступная температура
            for entries in temps.values():
                for entry in entries:
                    if entry.current is not None:
                        return entry.current

        except (AttributeError, NotImplementedError):
            pass

        return None

    def _update_cpu_temp_display(self, temp: Optional[float]):
        """Безопасное обновление отображения температуры CPU"""
        # 🔒 Защита: атрибут может ещё не существовать при раннем вызове
        if not hasattr(self, 'cpu_temp_label'):
            return

        if temp is not None:
            self.cpu_temp_label.setText(f"Температура: {temp:.1f} °C")
            # Цветовая индикация
            if temp < 60:
                color = "#2ecc71"  # 🟢 зелёный
            elif temp < 80:
                color = "#f39c12"  # 🟡 жёлтый
            else:
                color = "#e74c3c"  # 🔴 красный
            self.cpu_temp_label.setStyleSheet(f"color: {color}; font-weight: 500;")

            # Обновление прогресс-бара (если есть)
            if hasattr(self, 'cpu_temp_bar'):
                self.cpu_temp_bar.setValue(min(int(temp), 100))
        else:
            self.cpu_temp_label.setText("Температура: — °C")
            self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")
            if hasattr(self, 'cpu_temp_bar'):
                self.cpu_temp_bar.setValue(0)

    def _set_temp_bar_style(self, widget_name: str, color1: str, color2: str) -> None:
        """Установка стиля прогресс-бара температуры"""
        if hasattr(self, widget_name):
            widget = getattr(self, widget_name)
            if widget is not None:
                widget.setStyleSheet(f"""
                    QProgressBar {{height: 15px; text-align: center; font-size: 8pt; 
                    border: 1px solid #444; border-radius: 3px; background: #1a1a20;}}
                    QProgressBar::chunk {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {color1}, stop:1 {color2});}}
                """)

    def update_gpu_status(self) -> None:
        """Обновление отображения аппаратного статуса GPU"""
        if not self.gpu_monitor_available or not PYNVML_AVAILABLE:
            return

        try:
            device_str = self.gpu_device_combo.currentText().split(',')[0].strip()
            device_id = int(device_str) if device_str.isdigit() else 0
        except Exception:
            device_id = 0

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

            # Обновление UI
            self.safe_set_text('gpu_util_label', f"Загрузка GPU: {gpu_util} %")
            self.safe_set_value('gpu_util_bar', gpu_util)
            self.safe_set_text('gpu_mem_label',
                               f"Память GPU: {mem_used_mb:.0f} / {mem_total_mb:.0f} MB ({mem_util:.1f}%)")
            self.safe_set_value('gpu_mem_bar', int(mem_util))

            if temperature is not None:
                self.safe_set_text('gpu_temp_label', f"Температура: {temperature} °C")
                if temperature > self.GPU_TEMP_CRITICAL:
                    self.gpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                elif temperature > self.GPU_TEMP_WARNING:
                    self.gpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")
                else:
                    self.gpu_temp_label.setStyleSheet("color: #27ae60;")
            else:
                self.safe_set_text('gpu_temp_label', "Температура: - °C")
                self.gpu_temp_label.setStyleSheet("color: #7f8c8d;")

        except Exception as e:
            logger.debug(f"Не удалось обновить статус GPU {device_id}: {e}")
            self.safe_set_text('gpu_util_label', "Загрузка GPU: N/A")
            self.safe_set_value('gpu_util_bar', 0)
            self.safe_set_text('gpu_mem_label', "Память GPU: N/A")
            self.safe_set_value('gpu_mem_bar', 0)
            self.safe_set_text('gpu_temp_label', "Температура: N/A")

    # ==================== ОБРАБОТКА ОЧЕРЕДИ ====================

    def process_queue_messages(self) -> None:
        """Обработка сообщений из очереди CPU"""
        if not self.cpu_logic.queue_active:
            return

        start_time = time.time()
        processed = 0

        try:
            while processed < self.MAX_QUEUE_MESSAGES and (time.time() - start_time) < self.MAX_QUEUE_PROCESS_TIME:
                try:
                    data = self.cpu_logic.process_queue.get_nowait()
                    processed += 1
                    self._process_single_message(data)
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {type(e).__name__}: {e}")
                    continue  # Продолжаем обработку остальных сообщений

        except Exception as e:
            logger.exception("Критическая ошибка обработки очереди")
            self.cpu_logic.queue_active = False

    def _process_single_message(self, data: Dict[str, Any]) -> None:
        """Обработка одного сообщения из очереди"""
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

    def update_cpu_worker_row(self, worker_id: int) -> None:
        """Обновление строки воркера в таблице"""
        stats = self.cpu_logic.workers_stats.get(worker_id, {})
        scanned = stats.get('scanned', 0)
        found = stats.get('found', 0)
        speed = stats.get('speed', 0)
        progress = stats.get('progress', 0)

        if self.cpu_workers_table.rowCount() <= worker_id:
            self.cpu_workers_table.setRowCount(worker_id + 1)

        # ID воркера
        item = self.cpu_workers_table.item(worker_id, 0)
        if item is None:
            item = QTableWidgetItem(str(worker_id))
            item.setTextAlignment(Qt.AlignCenter)
            self.cpu_workers_table.setItem(worker_id, 0, item)
        else:
            item.setText(str(worker_id))

        # Проверено ключей
        item = self._get_or_create_item(worker_id, 1, Qt.AlignRight | Qt.AlignVCenter)
        item.setText(f"{scanned:,}")

        # Найдено ключей
        item = self._get_or_create_item(worker_id, 2, Qt.AlignCenter)
        item.setText(str(found))

        # Скорость
        item = self._get_or_create_item(worker_id, 3, Qt.AlignRight | Qt.AlignVCenter)
        item.setText(f"{speed:,.0f} keys/sec")

        # Прогресс бар
        self._update_worker_progress_bar(worker_id, progress)

    def _get_or_create_item(self, row: int, col: int, alignment: Qt.Alignment) -> QTableWidgetItem:
        """Получить или создать элемент таблицы"""
        item = self.cpu_workers_table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            item.setTextAlignment(alignment)
            self.cpu_workers_table.setItem(row, col, item)
        return item

    def _update_worker_progress_bar(self, worker_id: int, progress: int) -> None:
        """Обновление прогресс-бара воркера"""
        progress_bar = self.cpu_workers_table.cellWidget(worker_id, 4)
        if progress_bar is None:
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setAlignment(Qt.AlignCenter)
            progress_bar.setFormat("%p%")
            self.cpu_workers_table.setCellWidget(worker_id, 4, progress_bar)
        progress_bar.setValue(progress)

    def update_cpu_total_stats(self) -> None:
        """Обновление общей статистики CPU"""
        total_scanned = 0
        total_found = 0
        total_speed = 0
        total_progress = 0
        count = 0

        for stats in self.cpu_logic.workers_stats.values():
            total_scanned += stats.get('scanned', 0)
            total_found += stats.get('found', 0)
            total_speed += stats.get('speed', 0)
            if 'progress' in stats:
                total_progress += stats['progress']
                count += 1

        self.cpu_logic.cpu_total_scanned = total_scanned
        self.cpu_logic.cpu_total_found = total_found

        if count > 0:
            progress = total_progress / count
            self.safe_set_value('cpu_total_progress', int(progress))

        elapsed = max(1, time.time() - self.cpu_logic.cpu_start_time)
        avg_speed = total_scanned / elapsed if elapsed > 0 else 0

        # Расчет оставшегося времени
        eta_text = "-"
        if self.cpu_logic.cpu_mode == "sequential" and self.cpu_logic.total_keys > 0:
            processed = self.cpu_logic.cpu_total_scanned
            remaining = self.cpu_logic.total_keys - processed
            if avg_speed > 0:
                eta_seconds = remaining / avg_speed
                eta_text = format_time(eta_seconds)

        self.safe_set_text('cpu_eta_label', f"Оставшееся время: {eta_text}")
        self.safe_set_text('cpu_total_stats_label',
                           f"Всего проверено: {total_scanned:,} | Найдено: {total_found} | "
                           f"Скорость: {total_speed:,.0f} keys/sec | "
                           f"Средняя скорость: {avg_speed:,.0f} keys/sec | "
                           f"Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}"
                           )

    # ==================== HEALTH CHECK ====================

    def health_check(self) -> None:
        """Проверка здоровья приложения"""
        try:
            # Проверка памяти
            mem = psutil.Process().memory_info()
            if mem.rss > self.MEMORY_WARNING_THRESHOLD:
                mem_mb = mem.rss / 1024 / 1024
                logger.warning(f"Высокое использование памяти: {mem_mb:.0f} MB")
                self.append_log(f"⚠️ Высокое использование памяти: {mem_mb:.0f} MB!", "warning")

            # Проверка очереди
            if hasattr(self.cpu_logic, 'process_queue'):
                try:
                    queue_size = self.cpu_logic.process_queue.qsize()
                    if queue_size > self.QUEUE_SIZE_WARNING:
                        logger.warning(f"Большая очередь сообщений: {queue_size}")
                        self.append_log(f"⚠️ Большая очередь: {queue_size} сообщений", "warning")
                except NotImplementedError:
                    pass  # qsize() не поддерживается на некоторых платформах

        except Exception as e:
            logger.debug(f"Health check failed: {e}")

    # ==================== ОБЩИЕ МЕТОДЫ ====================

    def export_keys_csv(self) -> None:
        """Экспорт найденных ключей в CSV"""
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", "found_keys.csv", "CSV files (*.csv)")
        if not path:
            return

        self.set_busy(True)
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
        finally:
            self.set_busy(False)

    def show_context_menu(self, position) -> None:
        """Показ контекстного меню таблицы найденных ключей"""
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
            self.safe_set_text('gpu_found_label', "Найдено ключей: 0")
            self.append_log("Таблица найденных ключей очищена", "normal")
            return

        if not selected:
            return

        row = selected[0].row()

        if action == copy_wif_action:
            wif_item = self.found_keys_table.item(row, 3)
            if wif_item:
                QApplication.clipboard().setText(wif_item.text())
                self.append_log("WIF ключ скопирован в буфер обмена", "success")

        elif action == copy_hex_action:
            hex_item = self.found_keys_table.item(row, 2)
            if hex_item:
                QApplication.clipboard().setText(hex_item.text())
                self.append_log("HEX ключ скопирован в буфер обмена", "success")

        elif action == copy_addr_action:
            addr_item = self.found_keys_table.item(row, 1)
            if addr_item:
                QApplication.clipboard().setText(addr_item.text())
                self.append_log("Адрес скопирован в буфер обмена", "success")

        elif action == save_all_action:
            self.save_all_found_keys()

    def save_all_found_keys(self) -> None:
        """Сохранение всех найденных ключей в файл"""
        self.set_busy(True)
        try:
            with open(config.FOUND_KEYS_FILE, 'w', encoding='utf-8') as f:
                for row in range(self.found_keys_table.rowCount()):
                    time_item = self.found_keys_table.item(row, 0)
                    addr_item = self.found_keys_table.item(row, 1)
                    hex_item = self.found_keys_table.item(row, 2)
                    wif_item = self.found_keys_table.item(row, 3)

                    f.write(f"{time_item.text() if time_item else ''}\t"
                            f"{addr_item.text() if addr_item else ''}\t"
                            f"{hex_item.text() if hex_item else ''}\t"
                            f"{wif_item.text() if wif_item else ''}\n")
            self.append_log(f"Все ключи сохранены в {config.FOUND_KEYS_FILE}")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключей: {str(e)}")
            self.append_log(f"Ошибка сохранения ключей: {str(e)}")
        finally:
            self.set_busy(False)

    def handle_found_key(self, key_data: Dict[str, Any]) -> None:
        """Обработка найденного ключа"""
        try:
            found_count = self.found_keys_table.rowCount() + 1
            self.safe_set_text('gpu_found_label', f"Найдено ключей: {found_count}")
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

            # Источник
            source = key_data.get('source', 'CPU')
            source_colors = {
                'GPU': QColor(50, 205, 50),
                'CPU': QColor(100, 149, 237),
                'KANGAROO': QColor(255, 140, 0)
            }
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

            # MessageBox
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

    def save_found_key(self, key_data: Dict[str, Any]) -> None:
        """Сохранение найденного ключа в файл"""
        try:
            with open(config.FOUND_KEYS_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{key_data['timestamp']}\t{key_data['address']}\t"
                    f"{key_data['hex_key']}\t{key_data['wif_key']}\n"
                )
            self.append_log(f"Ключ сохранен в {config.FOUND_KEYS_FILE}", "success")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключа: {str(e)}")
            self.append_log(f"Ошибка сохранения ключа: {str(e)}", "error")

    def append_log(self, message: str, level: str = "normal") -> None:
        """Добавление сообщения в лог"""
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
        scrollbar = self.log_output.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def open_log_file(self) -> None:
        """Открывает файл лога в системном редакторе"""
        try:
            if platform.system() == 'Windows':
                os.startfile(config.LOG_FILE)
            elif platform.system() == 'Darwin':
                subprocess.call(('open', config.LOG_FILE))
            else:
                subprocess.call(('xdg-open', config.LOG_FILE))
        except Exception as e:
            self.append_log(f"Не удалось открыть файл лога: {str(e)}", "error")

    def load_settings(self) -> None:
        """Загружает настройки из settings.json"""
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                # Валидация настроек
                settings = self.validate_settings(settings)

                config.apply_settings_to_ui(self, settings)

                if "cpu_mode" in settings:
                    self.cpu_logic.cpu_mode = settings["cpu_mode"]
                    idx = 1 if settings["cpu_mode"] == "random" else 0
                    self.cpu_mode_combo.setCurrentIndex(idx)

                self.append_log("✅ Настройки загружены", "success")

            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {str(e)}")
                self.append_log(f"❌ Ошибка загрузки настроек: {str(e)}", "error")

    def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация и исправление настроек по умолчанию"""
        defaults = {
            'gpu_threads': 256,
            'cpu_workers': 4,
            'batch_size': 1000,
        }

        ranges = {
            'gpu_threads': (64, 65536),
            'cpu_workers': (1, 64),
            'batch_size': (100, 100000),
        }

        for key, default_value in defaults.items():
            if key not in settings:
                settings[key] = default_value
            elif not isinstance(settings[key], type(default_value)):
                settings[key] = default_value
            elif key in ranges:
                min_val, max_val = ranges[key]
                if not (min_val <= settings[key] <= max_val):
                    settings[key] = default_value

        return settings

    def save_settings(self) -> None:
        """Сохраняет настройки в settings.json"""
        try:
            settings = config.extract_settings_from_ui(self)
            settings_path = os.path.join(config.BASE_DIR, "settings.json")

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)

            self.append_log("✅ Настройки сохранены", "success")

        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {str(e)}")
            self.append_log(f"❌ Ошибка сохранения: {str(e)}", "error")

    def close_queue(self) -> None:
        """Закрытие очереди CPU"""
        self.cpu_logic.close_queue()

    # ==================== ЗАКРЫТИЕ ПРИЛОЖЕНИЯ ====================

    def closeEvent(self, event) -> None:
        """Обработка закрытия программы"""
        active_processes = []

        if self.gpu_logic.gpu_is_running:
            active_processes.append("GPU")

        if self.cpu_logic.processes:
            active_processes.append("CPU")

        if self.kangaroo_logic.is_running:
            active_processes.append("Kangaroo")

        if self.vanity_logic.is_running:
            active_processes.append("VanitySearch")

        if active_processes:
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

        # Сохраняем настройки перед закрытием
        self.save_settings()

        # Graceful shutdown с таймаутом
        shutdown_timeout = self.SHUTDOWN_TIMEOUT
        start_time = time.time()

        processes_to_stop = [
            ('GPU', self.gpu_logic.stop_gpu_search, lambda: self.gpu_logic.gpu_is_running),
            ('CPU', self.cpu_logic.stop_cpu_search, lambda: bool(self.cpu_logic.processes)),
            ('Kangaroo', self.kangaroo_logic.stop_kangaroo_search, lambda: self.kangaroo_logic.is_running),
            ('VanitySearch', self.vanity_logic.stop_search, lambda: self.vanity_logic.is_running),
        ]

        for name, stop_func, is_running_check in processes_to_stop:
            if is_running_check():
                stop_func()
                # Ждём завершения с таймаутом
                while is_running_check() and (time.time() - start_time) < shutdown_timeout:
                    time.sleep(0.1)
                    QApplication.processEvents()

        # Закрываем очередь CPU
        self.close_queue()

        # Останавливаем pynvml
        if PYNVML_AVAILABLE and self.gpu_monitor_available:
            try:
                pynvml.nvmlShutdown()
                logger.info("pynvml выключен")
            except Exception as e:
                logger.error(f"Ошибка выключения pynvml: {e}")

            # ▼▼▼ ДОБАВИТЬ: закрытие окна монитора ▼▼▼
        if hasattr(self, 'gpu_monitor_window') and self.gpu_monitor_window:
            try:
                self.gpu_monitor_window.close()
            except:
                pass
        # ▲▲▲ КОНЕЦ ВСТАВКИ ▲▲▲

        event.accept()