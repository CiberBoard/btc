# ui/main_window.py
# 🛠 УЛУЧШЕНИЕ 1: Оптимизированы импорты — стандартная библиотека → third-party → локальные
import os
import subprocess
import time
import json
import platform
import logging  # 🛠 УЛУЧШЕНИЕ 2: Импорт logging вынесен в начало (было дублирование)
import psutil
import multiprocessing
import queue
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette, QKeySequence, QRegularExpressionValidator, QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QGroupBox, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QProgressBar, QCheckBox, QComboBox,
    QTabWidget, QFileDialog, QSpinBox, QSizePolicy
)

# 🛠 УЛУЧШЕНИЕ 4: Локальные импорты сгруппированы и отсортированы
import config
from core.matrix_logic import MatrixLogic

from utils.hextowif import generate_all_from_hex
from utils.hex_calc_window import HexCalcWindow
from utils.gpu_monitor_window import GPUMonitorWindow
from core.kangaroo_logic import KangarooLogic
from ui.theme import apply_dark_theme
from ui.ui_main import MainWindowUI
from core.cpu_logic import CPULogic
from core.gpu_logic import GPULogic
from core.vanity_logic import VanityLogic
from utils.helpers import setup_logger, format_time, is_coincurve_available, make_combo32
# После других импортов из ui/
from ui.matrix_window import MatrixWindow

# 🛠 УЛУЧШЕНИЕ 5: Инициализация логгера один раз в начале модуля
logger = logging.getLogger(__name__)

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None  # 🛠 УЛУЧШЕНИЕ 6: Явное присваивание None для безопасных проверок


class BitcoinGPUCPUScanner(QMainWindow):
    """
    Главное окно приложения Bitcoin GPU/CPU Scanner.
    Объединяет логику сканирования, мониторинга и конвертации ключей.
    """

    # ==================== КОНСТАНТЫ ====================
    # 🛠 УЛУЧШЕНИЕ 7: Константы сгруппированы по категориям с пояснениями

    # Таймеры (мс)
    QUEUE_TIMER_INTERVAL = 100
    SYSINFO_TIMER_INTERVAL = 2000
    GPU_STATUS_TIMER_INTERVAL = 1500
    GPU_STATS_TIMER_INTERVAL = 500
    HEALTH_CHECK_INTERVAL = 60000  # 1 минута

    # Обработка очереди
    MAX_QUEUE_MESSAGES = 100
    MAX_QUEUE_PROCESS_TIME = 0.1  # секунды

    # Температурные пороги (°C)
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

    # 🛠 УЛУЧШЕНИЕ 8: Сигналы объявлены с типизацией
    vanity_update_ui_signal = pyqtSignal(object)
    log_gpu_progress_signal = pyqtSignal(str, str, float, int)  # 👈 ДОБАВЛЕНО

    def __init__(self):
        super().__init__()

        # 🛠 УЛУЧШЕНИЕ 9: Экспорт констант конфигурации с явными типами
        self.MAX_KEY_HEX: str = config.MAX_KEY_HEX
        self.BASE_DIR: Path = config.BASE_DIR

        # --- Инициализация pynvml для мониторинга GPU ---
        self.gpu_monitor_available: bool = False
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

        # 🛠 УЛУЧШЕНИЕ 10: Атрибуты GPU с явной типизацией
        self.gpu_range_label: Optional[QLabel] = None
        self.random_mode: bool = False
        self.last_random_ranges: set = set()
        self.max_saved_random: int = 100
        self.used_ranges: set = set()
        self.gpu_restart_timer: QTimer = QTimer()
        self.gpu_restart_delay: int = 1000  # 1 секунда по умолчанию
        self.selected_gpu_device_id: int = 0

        # CPU variables
        self.optimal_workers: int = max(1, multiprocessing.cpu_count() - 1)

        # --- Инициализация логики ---
        self.gpu_logic: GPULogic = GPULogic(self)
        self.cpu_logic: CPULogic = CPULogic(self)
        self.kangaroo_logic: KangarooLogic = KangarooLogic(self)
        self.vanity_logic: VanityLogic = VanityLogic(self)
        # 🛠 УЛУЧШЕНИЕ: Атрибут для окна матрицы
        self._matrix_logic: Optional[MatrixLogic] = None
        self.progress_tracker_window: Optional[Any] = None  # 👈 ДОБАВИТЬ!
        # 🔥 ДОБАВИТЬ ЭТУ СТРОКУ:
        self.matrix_window: Optional[MatrixWindow] = None  # ← КРИТИЧНО!
        # 🛠 УЛУЧШЕНИЕ 11: Подключение сигнала после создания vanity_logic
        self.vanity_update_ui_signal.connect(self.vanity_logic.handle_stats)

        apply_dark_theme(self)
        # 🔧 После apply_dark_theme(self) добавьте:
        self.log_gpu_progress_signal.connect(self._save_gpu_progress)
        self.ui = MainWindowUI(self)
        self.ui.setup_ui()
        self.setup_connections()
        self.load_settings()
        # ✅ Теперь безопасно заполняем GPU combo
        # 3. Теперь виджеты существуют, можно безопасно работать с ними
        if self.gpu_monitor_available:
            self.ui._populate_gpu_combo()
        if hasattr(self, 'gpu_device_combo') and self.gpu_device_combo.count() > 0:
            self.gpu_device_combo.setCurrentIndex(0)
        self.ensure_file_exists(config.FOUND_KEYS_FILE)

        # --- Инициализация таймеров ---
        self.queue_timer: QTimer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(self.QUEUE_TIMER_INTERVAL)

        self.health_timer: QTimer = QTimer()
        self.health_timer.timeout.connect(self.health_check)
        self.health_timer.start(self.HEALTH_CHECK_INTERVAL)

        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900)

        # 🛠 УЛУЧШЕНИЕ 12: Атрибуты для окон инициализируются как None
        self.hex_calc_window: Optional[HexCalcWindow] = None
        self.gpu_monitor_window: Optional[GPUMonitorWindow] = None
        self.progress_tracker_window: Optional[Any] = None  # 👈 ДОБАВИТЬ!



    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    @staticmethod
    def ensure_file_exists(filepath: str) -> None:
        """Гарантирует существование файла"""
        Path(filepath).touch(exist_ok=True)

    def safe_set_text(self, widget_name: str, text: str) -> None:
        """Безопасная установка текста с проверкой существования виджета"""
        widget = getattr(self, widget_name, None)
        if widget is not None:
            try:
                widget.setText(str(text))  # 🛠 УЛУЧШЕНИЕ 13: Явное преобразование в str
            except (AttributeError, RuntimeError):
                pass  # 🛠 УЛУЧШЕНИЕ 14: Ловим конкретные исключения вместо общего Exception

    def safe_set_value(self, widget_name: str, value: int) -> None:
        """Безопасная установка значения прогресс-бара"""
        widget = getattr(self, widget_name, None)
        if widget is not None:
            try:
                widget.setValue(int(value))
            except (AttributeError, RuntimeError):
                pass

    def set_busy(self, busy: bool = True) -> None:
        """Устанавливает курсор ожидания"""
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def emit_vanity_stats(self, stats: Dict[str, Any]) -> None:
        """Эмитит сигнал статистики vanity"""
        self.vanity_update_ui_signal.emit(stats)

    # ==================== ОКНА ====================

    def open_hex_calculator(self) -> None:
        """Открывает окно HEX-калькулятора с защитой от множественных экземпляров"""
        if self.hex_calc_window is None or not self.hex_calc_window.isVisible():
            self.hex_calc_window = HexCalcWindow(self)
        self.hex_calc_window.show()
        self.hex_calc_window.raise_()
        self.hex_calc_window.activateWindow()

    def open_gpu_monitor(self) -> None:
        """Открывает окно мониторинга GPU с защитой от удаленных объектов"""
        try:
            # 🛠 УЛУЧШЕНИЕ 15: Проверка на None + isVisible() вместо двойной проверки
            if self.gpu_monitor_window is None or not self.gpu_monitor_window.isVisible():
                self.gpu_monitor_window = GPUMonitorWindow(self)
                # 🛠 УЛУЧШЕНИЕ 16: Убрано WA_DeleteOnClose — Qt сам управляет жизненным циклом

            try:
                if self.gpu_monitor_window.isVisible():
                    self.gpu_monitor_window.raise_()
                    self.gpu_monitor_window.activateWindow()
                    return
            except RuntimeError:
                # 🛠 УЛУЧШЕНИЕ 17: Обработка случая, когда объект уже удалён Qt
                self.gpu_monitor_window = None

                self.gpu_monitor_window = GPUMonitorWindow(self)

            self.gpu_monitor_window.show()
            self.gpu_monitor_window.raise_()
            self.gpu_monitor_window.activateWindow()

        except Exception as e:
            logger.error(f"Ошибка открытия монитора GPU: {e}", exc_info=True)  # 🛠 УЛУЧШЕНИЕ 18: exc_info для полного трейса
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось открыть монитор:\n{type(e).__name__}: {e}"
            )

    @property
    def matrix_logic(self) -> 'MatrixLogic':
        """
        Ленивая инициализация матричной логики.
        Импорт и создание происходит ТОЛЬКО при первом обращении.
        """
        if not hasattr(self, '_matrix_logic_instance'):
            # 🔥 Локальный импорт — только когда действительно нужно
            from core.matrix_logic import MatrixLogic
            self._matrix_logic_instance = MatrixLogic()
            # Подключаем сигналы к методам главного окна
            self._matrix_logic_instance.log_message.connect(self.append_log)
            self._matrix_logic_instance.key_found.connect(self.handle_found_key)
        return self._matrix_logic_instance

    def open_matrix_window(self) -> None:
        """Открывает окно матрицы триплетов (немодальное)"""
        import sys
        print("[DEBUG] open_matrix_window: START", flush=True, file=sys.stderr)

        try:
            print("[DEBUG] Getting matrix_logic property...", flush=True, file=sys.stderr)
            logic = self.matrix_logic
            print("[DEBUG] matrix_logic obtained", flush=True, file=sys.stderr)

            if self.matrix_window is None or not self.matrix_window.isVisible():
                print("[DEBUG] Creating MatrixWindow...", flush=True, file=sys.stderr)
                self.matrix_window = MatrixWindow(self)
                print("[DEBUG] MatrixWindow created", flush=True, file=sys.stderr)

                # 🔥 Для немодального окна: показать и активировать
                self.matrix_window.show()
                self.matrix_window.raise_()
                self.matrix_window.activateWindow()
            else:
                # Если окно уже открыто — просто активируем его
                self.matrix_window.raise_()
                self.matrix_window.activateWindow()

            print("[DEBUG] Window shown successfully", flush=True, file=sys.stderr)

        except Exception as e:
            print(f"[DEBUG] ❌ CRASH: {type(e).__name__}: {e}", flush=True, file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            QMessageBox.critical(self, "Ошибка матрицы", f"{e}")

    def _on_triplet_from_matrix(self, triplet_str: str) -> None:
        """
        Обработчик: триплет из матрицы → можно использовать в CPU поиске.
        Здесь демо: просто логгируем. В продакшене можно конвертировать в int и подставить в диапазон.
        """
        try:
            # Конвертируем обратно в int для потенциального использования
            key_int = MatrixLogic.triplets_to_int(triplet_str)
            key_hex = hex(key_int)[2:].zfill(64)
            self.append_log(f"🔷 Из матрицы: {triplet_str[:20]}... → {key_hex[:32]}...", "success")

            # Опционально: подставить в поля диапазона (с подтверждением)
            # reply = QMessageBox.question(...)
            # if reply == QMessageBox.StandardButton.Yes:
            #     self.cpu_start_key_edit.setText(key_hex)

        except Exception as e:
            logger.warning(f"Ошибка обработки триплета из матрицы: {e}")

    def open_gpu_progress_tracker(self) -> None:
        """Открывает окно сохраненного прогресса GPU"""
        logger.debug("🔍 [1/4] Вход в open_gpu_progress_tracker")  # 👈 ДОБАВИТЬ
        try:
            if self.progress_tracker_window is None or not self.progress_tracker_window.isVisible():
                logger.debug("🔍 [2/4] Создание экземпляра...")  # 👈 ДОБАВИТЬ
                from pathlib import Path
                from utils.gpu_progress_tracker import GpuProgressTrackerWindow

                log_path = Path(config.BASE_DIR) / "gpu_progress.txt"
                self.progress_tracker_window = GpuProgressTrackerWindow(self, log_path)

                logger.debug("🔍 [3/4] Подключение сигнала...")  # 👈 ДОБАВИТЬ
                self.progress_tracker_window.range_selected.connect(self.apply_gpu_progress_range)

                logger.debug("🔍 [4/4] Показ окна...")  # 👈 ДОБАВИТЬ
                self.progress_tracker_window.show()
            else:
                self.progress_tracker_window.raise_()
                self.progress_tracker_window.activateWindow()
        except Exception as e:
            logger.exception(f"❌ КРАШ в open_gpu_progress_tracker: {e}")  # 👈 ДОБАВИТЬ
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно:\n{e}")


    def apply_gpu_progress_range(self, start_hex: str, end_hex: str) -> None:
        """Загружает выбранный диапазон в поля GPU поиска"""
        self.gpu_start_key_edit.setText(start_hex)
        self.gpu_end_key_edit.setText(end_hex)
        self.append_log(f"📥 Загружен сохраненный диапазон: {start_hex[:16]}... -> {end_hex[:16]}...", "success")
        QMessageBox.information(self, "✅ Загружено",
                                "Диапазон применен к полям поиска. Нажмите 'Запустить GPU' для продолжения.")
    # ==================== МЕТОДЫ НАВИГАЦИИ ====================

    def browse_kangaroo_exe(self) -> None:
        """Выбор файла etarkangaroo.exe"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите etarkangaroo.exe",
            str(self.BASE_DIR),  # 🛠 УЛУЧШЕНИЕ 19: Path → str для QFileDialog
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
            str(self.BASE_DIR)
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

        # 🛠 УЛУЧШЕНИЕ 20: Инициализация таймеров с проверкой на существование
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self.gpu_logic.update_gpu_time_display)
        self.gpu_stats_timer.start(self.GPU_STATS_TIMER_INTERVAL)

        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(self.SYSINFO_TIMER_INTERVAL)

        if self.gpu_monitor_available:
            self.gpu_status_timer = QTimer()
            self.gpu_status_timer.timeout.connect(self.update_gpu_status)
            self.gpu_status_timer.start(self.GPU_STATUS_TIMER_INTERVAL)
            self.selected_gpu_device_id = 0
        else:
            self.gpu_status_timer = None

        self.gpu_logic.setup_gpu_connections()
        self.setup_predict_connections()

    # ==================== КОНВЕРТЕР ====================

    def setup_converter_tab(self) -> None:
        """Создаёт вкладку конвертера HEX → WIF и адреса"""
        converter_tab = QWidget()
        layout = QVBoxLayout(converter_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        info_label = QLabel(
            "Введите приватный ключ в формате HEX (64 символа), выберите опции и нажмите 'Сгенерировать'."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #CCCCCC; font-size: 10pt;")
        layout.addWidget(info_label)

        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("Приватный ключ (HEX):"))
        self.hex_input = QLineEdit()
        self.hex_input.setPlaceholderText("Например: 1a2b3c4d...")
        self.hex_input.setMaxLength(64)
        hex_layout.addWidget(self.hex_input, 1)
        layout.addLayout(hex_layout)

        options_layout = QHBoxLayout()
        self.compressed_checkbox = QCheckBox("Сжатый публичный ключ")
        self.compressed_checkbox.setChecked(True)
        self.testnet_checkbox = QCheckBox("Testnet")
        self.testnet_checkbox.setChecked(False)
        options_layout.addWidget(self.compressed_checkbox)
        options_layout.addWidget(self.testnet_checkbox)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        self.generate_btn = QPushButton("Сгенерировать")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background: #2980b9; }
        """)
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.generate_btn)

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

        calc_btn = QPushButton("🔢 Открыть HEX-калькулятор")
        calc_btn.setStyleSheet("""
            QPushButton {
                background: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover { background: #8e44ad; }
        """)
        calc_btn.clicked.connect(self.open_hex_calculator)
        layout.addWidget(calc_btn)

        self.main_tabs.addTab(converter_tab, "Конвертер HEX → WIF")

    def on_generate_clicked(self) -> None:
        """Обработка нажатия кнопки генерации"""
        self.set_busy(True)
        try:
            hex_key = self.hex_input.text().strip()
            # 🛠 УЛУЧШЕНИЕ 21: Валидация через строковый метод вместо all()+генератора
            if not hex_key or len(hex_key) > 64 or not self._is_valid_hex(hex_key):
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

    @staticmethod
    def _is_valid_hex(s: str) -> bool:
        """🛠 УЛУЧШЕНИЕ 22: Выделена валидация HEX в отдельный метод"""
        try:
            int(s, 16)
            return True
        except ValueError:
            return False

    def copy_to_clipboard(self) -> None:
        """Копирование поля в буфер обмена"""
        btn = self.sender()
        if not btn:
            return
        field_name = btn.property("target")
        field_map = {
            "hex": "HEX",
            "wif": "WIF",
            "p2pkh": "P2PKH",
            "p2sh-p2wpkh": "P2SH-P2WPKH",
            "bech32 (p2wpkh)": "Bech32 (P2WPKH)"
        }
        display_name = field_map.get(str(field_name).lower())
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

    def setup_predict_connections(self) -> None:
        """Подключение сигналов вкладки Predict"""
        self.predict_browse_btn.clicked.connect(self.browse_predict_file)
        self.preview_keys_btn.clicked.connect(self.preview_predict_keys)
        self.predict_run_btn.clicked.connect(self.run_predict_analysis)

    def browse_predict_file(self) -> None:
        """Выбор файла с ключами"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл с ключами", str(self.BASE_DIR),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            self.predict_file_edit.setText(file_path)
            self.load_keys_for_preview(file_path)

    def load_keys_for_preview(self, file_path: str) -> None:
        """Загрузка и валидация ключей из файла ЛЮБОГО формата"""
        from core.predict_logic import parse_keys_from_file, validate_keys

        try:
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
            logger.exception("Ошибка в load_keys_for_preview")

    def preview_predict_keys(self) -> None:
        """Показать первые 10 ключей"""
        from core.predict_logic import parse_keys_from_file, validate_keys

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

    def on_predict_plot_data_ready(self, plot_data: dict) -> None:
        """Генерация графика в главном потоке (безопасно для matplotlib)"""
        try:
            from core.predict_logic import PredictWorker  # для доступа к _generate_plot
            # Создаём временный экземпляр только для вызова статического метода
            worker = PredictWorker([], {})
            worker._generate_plot(
                plot_data['positions'],
                plot_data['log_diff'],
                plot_data['trend'],
                plot_data['widths'],
                plot_data['plot_path'],
                plot_data['has_scipy']
            )
            # Обновляем отображение графика
            self.show_predict_plot(plot_data['plot_path'])
        except Exception as e:
            logger.error(f"Ошибка генерации графика: {e}", exc_info=True)
            # Создаём заглушку
            try:
                with open(plot_data['plot_path'], 'wb') as f:
                    f.write(
                        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                        b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
                    )
            except:
                pass

    def run_predict_analysis(self) -> None:
        """Запуск анализа предсказания"""
        from core.predict_logic import PredictWorker, parse_keys_from_file, validate_keys

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
            'output_plot': os.path.join(str(self.BASE_DIR), 'predict_analysis.png')
        }

        self.predict_status_label.setText("⏳ Запуск анализа...")
        self.predict_progress_bar.show()
        self.predict_progress_bar.setValue(0)
        self.predict_run_btn.setEnabled(False)
        self.predict_results_table.setRowCount(0)

        self.predict_worker = PredictWorker(valid_keys, params, parent=self)  # 👈 parent=self!
        self.predict_worker.progress_update.connect(self.on_predict_progress)
        self.predict_worker.analysis_finished.connect(self.on_predict_finished)
        self.predict_worker.plot_data_ready.connect(self.on_predict_plot_data_ready)  # <- НОВОЕ
        self.predict_worker.error_occurred.connect(self.on_predict_error)
        self.predict_worker.start()

    def on_predict_progress(self, percent: int, message: str) -> None:
        """Обновление прогресс-бара"""
        self.predict_progress_bar.setValue(percent)
        self.predict_status_label.setText(f"⏳ {message}")

    def on_predict_finished(self, result_json: str) -> None:  # <- принимаем строку!
        """Обработка успешного завершения (принимает JSON-строку)"""
        import json

        # ✅ Парсим JSON обратно в dict
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от PredictWorker: {e}")
            self.on_predict_error("Некорректные данные от PredictWorker")
            return

        # ✅ Дальше ваш существующий код (result теперь — dict)
        self.predict_progress_bar.hide()
        self.predict_run_btn.setEnabled(True)
        self.predict_status_label.setText("✅ Анализ завершён")

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
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.predict_results_table.setItem(row, 1, item)

        self.show_predict_plot(result.get('plot_path', ''))
        self.append_log(f"📊 Анализ завершён. Сужение: {result['reduction_percent']:.2f}%", "success")
        self._fill_ranges_table(result.get('ranges', {}))

    def on_predict_error(self, error_msg: str) -> None:
        """Обработка ошибки"""
        self.predict_progress_bar.hide()
        self.predict_run_btn.setEnabled(True)
        self.predict_status_label.setText("❌ Ошибка выполнения")
        self.append_log(f"❌ {error_msg}", "error")
        QMessageBox.critical(self, "Ошибка анализа", error_msg)

    def show_predict_plot(self, plot_path: str) -> None:
        """Отображение графика с плавной загрузкой"""
        if not plot_path or not os.path.exists(plot_path) or os.path.getsize(plot_path) < 100:
            self.predict_plot_label.setText("📊 График: ожидание данных...")
            self.predict_plot_label.setStyleSheet("""
                QLabel { color: #7f8c8d; font-size: 11pt; padding: 20px; 
                         background: #1a2332; border: 2px dashed #34495e; border-radius: 6px; }
            """)
            return

        pixmap = QPixmap(plot_path)
        if pixmap.isNull():
            self.predict_plot_label.setText("❌ Ошибка загрузки графика")
            return

        max_width = max(600, self.predict_scroll.width() - 50)
        max_height = 500
        if pixmap.width() > max_width or pixmap.height() > max_height:
            # ✅ ИСПРАВЛЕНО: PyQt6 Enum'ы для масштабирования
            pixmap = pixmap.scaled(
                max_width,
                max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

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

        if hasattr(self.predict_scroll, 'widget'):
            container = self.predict_scroll.widget()
            if container and container.layout():
                container.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)

    def export_predict_results(self) -> None:
        """Экспорт таблицы результатов"""
        if self.predict_results_table.rowCount() == 0:
            QMessageBox.information(self, "Экспорт", "Нет данных для экспорта")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результаты", "predict_results.txt", "Text Files (*.txt)"
        )
        if not path:
            return

        with open(path, 'w', encoding='utf-8') as f:
            f.write("BTC Puzzle Analyzer v2 - Результаты\n")
            f.write("=" * 50 + "\n")
            for row in range(self.predict_results_table.rowCount()):
                p = self.predict_results_table.item(row, 0).text()
                v = self.predict_results_table.item(row, 1).text()
                f.write(f"{p}: {v}\n")
        self.append_log(f"💾 Результаты сохранены в {path}", "success")

    def _fill_ranges_table(self, ranges: dict) -> None:
        """Заполняет таблицу диапазонов моделей с кнопками копирования"""
        if not hasattr(self, 'predict_ranges_table') or not ranges:
            return

        table = self.predict_ranges_table
        table.setRowCount(0)

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

            item = QTableWidgetItem(f"{icon} {name}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if name == 'Final':
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor(color))
            table.setItem(row, 0, item)

            min_h = r.get('min_hex', '')
            max_h = r.get('max_hex', '')
            range_txt = f"{min_h[:16]}...{max_h[-16:]}" if min_h and max_h else "N/A"
            item = QTableWidgetItem(range_txt)
            item.setToolTip(f"Min: 0x{min_h}\nMax: 0x{max_h}" if min_h and max_h else "Нет данных")
            if name == 'Final':
                item.setForeground(QColor(color))
            table.setItem(row, 1, item)

            width = r.get('width', 0)
            width_txt = f"{width:.2e}" if width > 0 else "N/A"
            item = QTableWidgetItem(width_txt)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(f"Ширина: {int(width):,} ключей" if width > 0 else "Ширина неизвестна")
            if name == 'Final':
                item.setForeground(QColor(color))
            table.setItem(row, 2, item)

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
            copy_btn.setProperty('range_data', {
                'model': name,
                'min_hex': min_h,
                'max_hex': max_h,
                'width': width
            })
            copy_btn.clicked.connect(self._on_copy_range_clicked)

            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addStretch()
            btn_layout.addWidget(copy_btn)
            btn_layout.addStretch()
            table.setCellWidget(row, 3, btn_container)

    def _on_copy_range_clicked(self) -> None:
        """Обработчик кнопки копирования диапазона"""
        btn = self.sender()
        if not btn:
            return

        data = btn.property('range_data')
        if not data:
            return

        copy_text = (
            f"# {data['model']} range — BTC Puzzle Analyzer\n"
            f"start_key = \"{data['min_hex']}\"\n"
            f"end_key = \"{data['max_hex']}\"\n"
            f"# Ширина: {data['width']:.2e} ключей"
        )

        QApplication.clipboard().setText(copy_text)
        model_name = data.get('model', 'Range')
        self.append_log(f"📋 Диапазон {model_name} скопирован в буфер обмена", "success")

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

            priority_sensors = ['coretemp', 'k10temp', 'cpu_thermal', 'acpi']

            for name in priority_sensors:
                if name in temps:
                    for entry in temps[name]:
                        if entry.current is not None:
                            if 'package' in entry.label.lower() or entry.label == '':
                                return float(entry.current)  # 🛠 УЛУЧШЕНИЕ 23: Явное преобразование в float

            for entries in temps.values():
                for entry in entries:
                    if entry.current is not None:
                        return float(entry.current)

        except (AttributeError, NotImplementedError):
            pass

        return None

    def _update_cpu_temp_display(self, temp: Optional[float]) -> None:
        """Безопасное обновление отображения температуры CPU"""
        if not hasattr(self, 'cpu_temp_label'):
            return

        if temp is not None:
            self.cpu_temp_label.setText(f"Температура: {temp:.1f} °C")
            if temp < 60:
                color = "#2ecc71"
            elif temp < 80:
                color = "#f39c12"
            else:
                color = "#e74c3c"
            self.cpu_temp_label.setStyleSheet(f"color: {color}; font-weight: 500;")

            if hasattr(self, 'cpu_temp_bar'):
                self.cpu_temp_bar.setValue(min(int(temp), 100))
        else:
            self.cpu_temp_label.setText("Температура: — °C")
            self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")
            if hasattr(self, 'cpu_temp_bar'):
                self.cpu_temp_bar.setValue(0)

    def _set_temp_bar_style(self, widget_name: str, color1: str, color2: str) -> None:
        """Установка стиля прогресс-бара температуры"""
        widget = getattr(self, widget_name, None)
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
            # 🔧 БЕЗОПАСНОЕ ПОЛУЧЕНИЕ NVML-ИНДЕКСА через userData
            device_id = self.gpu_device_combo.currentData()

            # Фоллбэк для старых версий или ошибок
            if device_id is None or device_id == -1:
                device_str = self.gpu_device_combo.currentText().split(',')[0].strip()
                device_id = int(device_str) if device_str.isdigit() else 0
        except (ValueError, AttributeError):
            device_id = 0

        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = int(util_info.gpu)

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used_mb = mem_info.used / (1024 * 1024)
            mem_total_mb = mem_info.total / (1024 * 1024)
            mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0

            try:
                temperature = int(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
            except pynvml.NVMLError:
                temperature = None

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
                    continue
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

        item = self.cpu_workers_table.item(worker_id, 0)
        if item is None:
            item = QTableWidgetItem(str(worker_id))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cpu_workers_table.setItem(worker_id, 0, item)
        else:
            item.setText(str(worker_id))

        item = self._get_or_create_item(worker_id, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setText(f"{scanned:,}")

        item = self._get_or_create_item(worker_id, 2, Qt.AlignmentFlag.AlignCenter)
        item.setText(str(found))

        item = self._get_or_create_item(worker_id, 3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setText(f"{speed:,.0f} keys/sec")

        self._update_worker_progress_bar(worker_id, progress)

    def _get_or_create_item(self, row: int, col: int, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
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
            progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
            mem = psutil.Process().memory_info()
            if mem.rss > self.MEMORY_WARNING_THRESHOLD:
                mem_mb = mem.rss / 1024 / 1024
                logger.warning(f"Высокое использование памяти: {mem_mb:.0f} MB")
                self.append_log(f"⚠️ Высокое использование памяти: {mem_mb:.0f} MB!", "warning")

            if hasattr(self.cpu_logic, 'process_queue'):
                try:
                    queue_size = self.cpu_logic.process_queue.qsize()
                    if queue_size > self.QUEUE_SIZE_WARNING:
                        logger.warning(f"Большая очередь сообщений: {queue_size}")
                        self.append_log(f"⚠️ Большая очередь: {queue_size} сообщений", "warning")
                except NotImplementedError:
                    pass
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

    def show_context_menu(self, position: QPoint) -> None:  # <- явный тип
        """Показ контекстного меню таблицы найденных ключей"""
        menu = QMenu()
        copy_wif_action = menu.addAction("Копировать WIF ключ")
        copy_hex_action = menu.addAction("Копировать HEX ключ")
        copy_addr_action = menu.addAction("Копировать адрес")
        menu.addSeparator()
        save_all_action = menu.addAction("Сохранить все ключи в файл")
        clear_action = menu.addAction("Очистить таблицу")

        action = menu.exec(self.found_keys_table.viewport().mapToGlobal(position))
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

            time_item = QTableWidgetItem(key_data['timestamp'])
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setForeground(QColor(100, 255, 100))
            self.found_keys_table.setItem(row, 0, time_item)

            addr_item = QTableWidgetItem(key_data['address'])
            addr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            addr_item.setForeground(QColor(255, 215, 0))
            self.found_keys_table.setItem(row, 1, addr_item)

            hex_item = QTableWidgetItem(key_data['hex_key'])
            hex_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            hex_item.setForeground(QColor(100, 200, 255))
            self.found_keys_table.setItem(row, 2, hex_item)

            wif_item = QTableWidgetItem(key_data['wif_key'])
            wif_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            wif_item.setForeground(QColor(255, 150, 150))
            self.found_keys_table.setItem(row, 3, wif_item)

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
            source_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            source_item.setForeground(source_colors.get(source, QColor(200, 200, 200)))
            source_item.setFont(QFont('Arial', 10, QFont.Weight.Bold))
            self.found_keys_table.setItem(row, 4, source_item)

            self.found_keys_table.scrollToBottom()
            self.save_found_key(key_data)

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
        settings_path = os.path.join(str(self.BASE_DIR), "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)

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
            settings_path = os.path.join(str(self.BASE_DIR), "settings.json")

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)

            self.append_log("✅ Настройки сохранены", "success")

        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {str(e)}")
            self.append_log(f"❌ Ошибка сохранения: {str(e)}", "error")

    def _save_gpu_progress(self, start_hex: str, end_hex: str, percent: float, gpu_id: int) -> None:
        """Безопасное сохранение прогресса (вызывается только в главном потоке)"""
        try:
            from pathlib import Path
            log_path = Path(config.BASE_DIR) / "gpu_progress.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            line = f"{start_hex.zfill(64)}-{end_hex.zfill(64)} {int(percent)}% пройдено GPU{gpu_id}\n"
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка сохранения прогресса: {e}")

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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        self.save_settings()

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
                while is_running_check() and (time.time() - start_time) < shutdown_timeout:
                    time.sleep(0.1)
                    QApplication.processEvents()

        self.close_queue()

        # ── NVML Shutdown с защитой от двойного выключения ──
        if PYNVML_AVAILABLE and self.gpu_monitor_available:
            try:
                # Проверяем флаг инициализации перед shutdown
                if getattr(pynvml, '_nvml_initialized', True):  # Если атрибута нет — считаем инициализированным
                    pynvml.nvmlShutdown()
                    pynvml._nvml_initialized = False  # 👈 Помечаем как выключенный
                    logger.info("pynvml выключен")
            except pynvml.NVMLError_LibraryNotFound:  # type: ignore
                logger.debug("NVML библиотека уже выгружена")
            except pynvml.NVMLError_DriverNotLoaded:  # type: ignore
                logger.debug("NVML драйвер не загружен")
            except Exception as e:
                # Игнорируем ошибки повторного shutdown — это нормально
                logger.debug(f"NVML shutdown (ожидаемо): {type(e).__name__}: {e}")

        # 🛠 УЛУЧШЕНИЕ 25: Безопасное закрытие окна монитора с проверкой
        if hasattr(self, 'gpu_monitor_window') and self.gpu_monitor_window:
            try:
                self.gpu_monitor_window.close()
            except RuntimeError:
                pass  # Объект уже удалён
        # 🛠 УЛУЧШЕНИЕ: Закрытие окна матрицы
        if hasattr(self, 'matrix_window') and self.matrix_window:
            try:
                self.matrix_window.close()
            except RuntimeError:
                pass  # Объект уже удалён

        event.accept()