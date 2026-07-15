# ui/main_window.py
import os
import subprocess
import time
import json
import platform
import logging
import psutil
import multiprocessing
import queue
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, QPoint, QByteArray
from PyQt6.QtGui import QFont, QColor, QPalette, QKeySequence, QRegularExpressionValidator, QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QGroupBox, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QProgressBar, QCheckBox, QComboBox,
    QTabWidget, QFileDialog, QSpinBox, QSizePolicy, QDialog
)

import config
from ui.theme import apply_dark_theme
from ui.ui_main import MainWindowUI
from core.unified_scanner import ScannerManager
from utils.helpers import setup_logger, format_time, is_coincurve_available, make_combo32
from utils.settings_manager import get_settings
from utils.hextowif import generate_all_from_hex
from utils.hex_calc_window import HexCalcWindow
from utils.gpu_monitor_window import GPUMonitorWindow
from ui.matrix_window import MatrixWindow
from core.matrix_logic import MatrixLogic  # только для статических методов, если нужно

logger = logging.getLogger(__name__)

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    pynvml = None


class BitcoinGPUCPUScanner(QMainWindow):
    # Константы
    QUEUE_TIMER_INTERVAL = 100
    SYSINFO_TIMER_INTERVAL = 2000
    GPU_STATUS_TIMER_INTERVAL = 1500
    GPU_STATS_TIMER_INTERVAL = 500
    HEALTH_CHECK_INTERVAL = 60000
    MAX_QUEUE_MESSAGES = 100
    MAX_QUEUE_PROCESS_TIME = 0.1
    GPU_TEMP_WARNING = 65
    GPU_TEMP_CRITICAL = 80
    CPU_TEMP_WARNING = 65
    CPU_TEMP_CRITICAL = 80
    SHUTDOWN_TIMEOUT = 5
    MEMORY_WARNING_THRESHOLD = 2 * 1024 * 1024 * 1024
    QUEUE_SIZE_WARNING = 1000

    vanity_update_ui_signal = pyqtSignal(object)
    log_gpu_progress_signal = pyqtSignal(str, str, float, int)

    def __init__(self):
        super().__init__()

        self.MAX_KEY_HEX = config.MAX_KEY_HEX
        self.BASE_DIR = config.BASE_DIR
        self.settings = get_settings(self.BASE_DIR)
        self.settings._ui_parent = self

        # --- Инициализация pynvml для мониторинга GPU ---
        self.gpu_monitor_available = False
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_monitor_available = True
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    logger.info(f"Найдено {device_count} NVIDIA GPU устройств.")
                else:
                    logger.warning("NVIDIA GPU не найдены.")
                    self.gpu_monitor_available = False
            except Exception as e:
                logger.error(f"Ошибка инициализации pynvml: {e}")
                self.gpu_monitor_available = False
        else:
            logger.warning("pynvml не установлена. Мониторинг GPU недоступен.")

        # --- Атрибуты GPU (для UI) ---
        self.gpu_range_label = None
        self.random_mode = False
        self.last_random_ranges = set()
        self.max_saved_random = 100
        self.used_ranges = set()
        self.gpu_restart_timer = QTimer()
        self.gpu_restart_delay = 1000
        self.selected_gpu_device_id = 0
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)

        # --- Менеджер сканеров ---
        self.scanner_manager = ScannerManager(self)
        # Получаем ссылки на сканеры для удобства
        self.cpu_scanner = self.scanner_manager.get_scanner('cpu')
        self.gpu_scanner = self.scanner_manager.get_scanner('gpu')
        self.kangaroo_scanner = self.scanner_manager.get_scanner('kangaroo')
        self.vanity_scanner = self.scanner_manager.get_scanner('vanity')
        self.matrix_scanner = self.scanner_manager.get_scanner('matrix')

        # --- Вспомогательные окна ---
        self.matrix_window = None
        self.hex_calc_window = None
        self.gpu_monitor_window = None
        self.progress_tracker_window = None

        # --- UI ---
        apply_dark_theme(self)
        self.log_gpu_progress_signal.connect(self._save_gpu_progress)
        self.ui = MainWindowUI(self)
        self.ui.setup_ui()
        self.setup_connections()
        self.load_settings()

        if self.gpu_monitor_available:
            self.ui._populate_gpu_combo()
        if hasattr(self, 'gpu_device_combo') and self.gpu_device_combo.count() > 0:
            self.gpu_device_combo.setCurrentIndex(0)
        self.ensure_file_exists(config.FOUND_KEYS_FILE)

        # --- Таймеры ---
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_all_queues)
        self.queue_timer.start(self.QUEUE_TIMER_INTERVAL)

        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.health_check)
        self.health_timer.start(self.HEALTH_CHECK_INTERVAL)

        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900)

        logger.info(f"📁 Settings path: {self.settings.filepath}")

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    @staticmethod
    def ensure_file_exists(filepath: str) -> None:
        Path(filepath).touch(exist_ok=True)

    def safe_set_text(self, widget_name: str, text: str) -> None:
        widget = getattr(self, widget_name, None)
        if widget is not None:
            try:
                widget.setText(str(text))
            except (AttributeError, RuntimeError):
                pass

    def safe_set_value(self, widget_name: str, value: int) -> None:
        widget = getattr(self, widget_name, None)
        if widget is not None:
            try:
                widget.setValue(int(value))
            except (AttributeError, RuntimeError):
                pass

    def set_busy(self, busy: bool = True) -> None:
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    # ==================== ОКНА ====================
    def open_hex_calculator(self) -> None:
        if self.hex_calc_window is None or not self.hex_calc_window.isVisible():
            self.hex_calc_window = HexCalcWindow(self)
        self.hex_calc_window.show()
        self.hex_calc_window.raise_()
        self.hex_calc_window.activateWindow()

    def open_gpu_monitor(self) -> None:
        try:
            if self.gpu_monitor_window is None or not self.gpu_monitor_window.isVisible():
                self.gpu_monitor_window = GPUMonitorWindow(self)
            if self.gpu_monitor_window.isVisible():
                self.gpu_monitor_window.raise_()
                self.gpu_monitor_window.activateWindow()
        except RuntimeError:
            self.gpu_monitor_window = None
            self.gpu_monitor_window = GPUMonitorWindow(self)
            self.gpu_monitor_window.show()
        except Exception as e:
            logger.error(f"Ошибка открытия монитора GPU: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть монитор:\n{type(e).__name__}: {e}")

    def open_matrix_window(self) -> None:
        if self.matrix_window is None or not self.matrix_window.isVisible():
            self.matrix_window = MatrixWindow(self)
            # ✅ Подключаем сигнал найденного ключа к обработчику главного окна
            self.matrix_window.key_found.connect(self.handle_found_key)
        self.matrix_window.show()
        self.matrix_window.raise_()
        self.matrix_window.activateWindow()

    def open_gpu_progress_tracker(self) -> None:
        try:
            if self.progress_tracker_window is None or not self.progress_tracker_window.isVisible():
                from pathlib import Path
                from utils.gpu_progress_tracker import GpuProgressTrackerWindow
                log_path = Path(config.BASE_DIR) / "gpu_progress.txt"
                self.progress_tracker_window = GpuProgressTrackerWindow(self, log_path)
                self.progress_tracker_window.range_selected.connect(self.apply_gpu_progress_range)
                self.progress_tracker_window.show()
            else:
                self.progress_tracker_window.raise_()
                self.progress_tracker_window.activateWindow()
        except Exception as e:
            logger.exception(f"❌ Ошибка открытия трекера прогресса: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно:\n{e}")

    def apply_gpu_progress_range(self, start_hex: str, end_hex: str) -> None:
        self.gpu_start_key_edit.setText(start_hex)
        self.gpu_end_key_edit.setText(end_hex)
        self.append_log(f"📥 Загружен сохраненный диапазон: {start_hex[:16]}... -> {end_hex[:16]}...", "success")
        QMessageBox.information(self, "✅ Загружено",
                                "Диапазон применен к полям поиска. Нажмите 'Запустить GPU' для продолжения.")

    def generate_and_show_random_range(self) -> None:
        try:
            from utils.random_range_dialog import RandomRangeDialog
            global_start = self.gpu_start_key_edit.text().strip() or "1"
            global_end = self.gpu_end_key_edit.text().strip() or config.MAX_KEY_HEX

            def get_min_distance() -> int:
                spin = getattr(self, 'gpu_min_distance_spin', None)
                if spin:
                    return spin.value() * 1_000_000_000
                return 2_000_000_000

            def on_apply(start_hex: str, end_hex: str) -> None:
                self.gpu_start_key_edit.setText(start_hex)
                self.gpu_end_key_edit.setText(end_hex)
                self.append_log("✅ Диапазон применён в поля ввода", "success")

            dialog = RandomRangeDialog(
                parent=self,
                global_start_hex=global_start,
                global_end_hex=global_end,
                min_distance_callback=get_min_distance,
                on_apply_callback=on_apply,
                on_log_callback=self.append_log,
            )
            dialog.exec()
        except Exception as e:
            logger.exception("Ошибка открытия диалога случайного диапазона")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть диалог:\n{type(e).__name__}: {e}")

    # ==================== МЕТОДЫ НАВИГАЦИИ ====================
    def browse_kangaroo_exe(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите etarkangaroo.exe", str(self.BASE_DIR),
            "Executable Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self.kang_exe_edit.setText(file_path)
            self.append_log(f"Выбран файл: {file_path}", "success")

    def browse_kangaroo_temp(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите временную директорию", str(self.BASE_DIR))
        if dir_path:
            self.kang_temp_dir_edit.setText(dir_path)
            self.append_log(f"Выбрана директория: {dir_path}", "success")

    def copy_vanity_result(self) -> None:
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
        # GPU кнопки
        self.gpu_start_stop_btn.clicked.connect(self._toggle_gpu)
        self.gpu_optimize_btn.clicked.connect(self._auto_optimize_gpu)

        # CPU кнопки
        self.cpu_start_stop_btn.clicked.connect(self._toggle_cpu)
        self.cpu_pause_resume_btn.clicked.connect(self._toggle_cpu_pause)
        self.cpu_start_stop_btn.setShortcut(QKeySequence("Ctrl+S"))
        self.cpu_pause_resume_btn.setShortcut(QKeySequence("Ctrl+P"))

        # Vanity
        self.vanity_start_stop_btn.clicked.connect(self._toggle_vanity)

        # Общие
        self.clear_log_btn.clicked.connect(lambda: self.log_output.clear())

        # Таймеры
        self.gpu_stats_timer = QTimer()
        self.gpu_stats_timer.timeout.connect(self._update_gpu_time)
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

        # Подключаем сигналы сканеров к слотам главного окна
        # CPU
        cpu = self.cpu_scanner
        cpu.log_message.connect(self.append_log)
        cpu.key_found.connect(self.handle_found_key)
        cpu.stats_updated.connect(self.update_cpu_stats)
        cpu.worker_finished.connect(self._on_cpu_worker_finished)
        cpu.search_finished.connect(self._on_cpu_search_finished)

        # GPU
        gpu = self.gpu_scanner
        gpu.log_message.connect(self.append_log)
        gpu.key_found.connect(self.handle_found_key)
        gpu.stats_updated.connect(self.update_gpu_stats)

        # Kangaroo
        kang = self.kangaroo_scanner
        kang.log_message.connect(self.append_log)
        kang.key_found.connect(self.handle_found_key)
        kang.stats_updated.connect(self.update_kangaroo_stats)

        # Vanity
        vanity = self.vanity_scanner
        vanity.log_message.connect(self.append_log)
        vanity.key_found.connect(self.handle_found_key)
        vanity.stats_updated.connect(self.update_vanity_stats)

        # Matrix
        matrix = self.matrix_scanner
        matrix.log_message.connect(self.append_log)
        matrix.key_found.connect(self.handle_found_key)

        # Автонастройка Kangaroo
        self.kang_auto_config_btn.clicked.connect(self._auto_configure_kangaroo)

        # ✅ ДОБАВЛЕНО: подключение кнопки запуска/остановки Kangaroo
        self.kang_start_stop_btn.clicked.connect(self._toggle_kangaroo)

        # Predict
        self.setup_predict_connections()

    # ---------- Обработчики кнопок ----------
    def _toggle_cpu(self):
        scanner = self.cpu_scanner
        if scanner.is_running():
            scanner.stop()
        else:
            params = {
                'target': self.cpu_target_edit.text().strip(),
                'start_hex': self.cpu_start_key_edit.text().strip(),
                'end_hex': self.cpu_end_key_edit.text().strip(),
                'workers': self.cpu_workers_spin.value(),
                'mode': 'sequential' if self.cpu_mode_combo.currentIndex() == 0 else 'random',
                'attempts': int(self.cpu_attempts_edit.text()) if self.cpu_mode_combo.currentIndex() == 1 else 0,
                'prefix_len': self.cpu_prefix_spin.value(),
            }
            if scanner.start(params):
                self.cpu_start_stop_btn.setText("Стоп CPU (Ctrl+Q)")
                self.cpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
                self.cpu_pause_resume_btn.setEnabled(True)
                self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
                self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")
            else:
                self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
                self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
                self.cpu_pause_resume_btn.setEnabled(False)

    def _toggle_cpu_pause(self):
        scanner = self.cpu_scanner
        if scanner.is_running() and not scanner._is_paused:
            scanner.pause()
            self.cpu_pause_resume_btn.setText("Продолжить")
            self.cpu_pause_resume_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        elif scanner._is_paused:
            scanner.resume()
            self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
            self.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

    def _toggle_gpu(self):
        scanner = self.gpu_scanner
        if scanner.is_running():
            scanner.stop()
            self.gpu_start_stop_btn.setText("Запустить GPU поиск")
            self.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.gpu_status_label.setText("Статус: Готов к работе")
        else:
            params = {
                'target': self.gpu_target_edit.text().strip(),
                'start_hex': self.gpu_start_key_edit.text().strip(),
                'end_hex': self.gpu_end_key_edit.text().strip(),
                'devices': self.gpu_device_combo.currentText(),
                'blocks': self.blocks_combo.currentText(),
                'threads': self.threads_combo.currentText(),
                'points': self.points_combo.currentText(),
                'priority_index': self.gpu_priority_combo.currentIndex(),
                'workers_per_device': self.gpu_workers_per_device_spin.value(),
                'use_compressed': self.gpu_use_compressed_checkbox.isChecked(),
                'random_mode': self.gpu_random_checkbox.isChecked(),
                'min_range_size': self.gpu_min_range_edit.text().strip(),
                'max_range_size': self.gpu_max_range_edit.text().strip(),
                'restart_interval': int(self.gpu_restart_interval_combo.currentText()),
            }
            if scanner.start(params):
                self.gpu_start_stop_btn.setText("Остановить GPU")
                self.gpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
                self.gpu_status_label.setText("Статус: Поиск запущен")
            else:
                self.gpu_start_stop_btn.setText("Запустить GPU поиск")
                self.gpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    def _toggle_vanity(self):
        scanner = self.vanity_scanner
        if scanner.is_running():
            scanner.stop()
            self.vanity_start_stop_btn.setText("🚀 Запустить генерацию")
            self.vanity_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.vanity_status_label.setText("Статус: Готов")
        else:
            params = {
                'prefix': self.vanity_prefix_edit.text().strip(),
                'gpu': self.vanity_gpu_combo.currentText(),
                'addr_type': self.vanity_type_combo.currentIndex(),
                'compressed': self.vanity_compressed_cb.isChecked(),
                'cpu_threads': self.vanity_cpu_spin.value(),
            }
            if scanner.start(params):
                self.vanity_start_stop_btn.setText("⏹ Остановить")
                self.vanity_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
                self.vanity_status_label.setText("Статус: Генерация...")
                self.vanity_progress_bar.setRange(0, 0)

    def _auto_optimize_gpu(self):
        from utils.gpu_auto_config import auto_configure_gpu
        result = auto_configure_gpu(self)
        if result:
            self.append_log(
                f"✅ Параметры GPU оптимизированы: Blocks={result['blocks']}, Threads={result['threads']}, Points={result['points']}",
                "success"
            )

    def _auto_configure_kangaroo(self):
        from utils.gpu_auto_config import auto_configure_kangaroo
        result = auto_configure_kangaroo(self)
        if result:
            self.append_log(
                f"✅ Параметры Kangaroo оптимизированы: Grid={result['grid_params']}, DP={result['dp']}, Subrange={result['subrange_bits']}",
                "success"
            )

    # ✅ ДОБАВЛЕНО: метод для кнопки запуска/остановки Kangaroo
    def _toggle_kangaroo(self):
        """
        Обработчик кнопки запуска/остановки Kangaroo.
        """
        scanner = self.kangaroo_scanner
        if scanner.is_running():
            scanner.stop()
            self.kang_start_stop_btn.setText("🚀 Запустить Kangaroo")
            self.kang_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.kang_status_label.setText("Статус: Готов к запуску")
            self.append_log("Kangaroo поиск остановлен", "warning")
        else:
            params = {
                'pubkey_hex': self.kang_pubkey_edit.text().strip(),
                'rb_hex': self.kang_start_key_edit.text().strip(),
                're_hex': self.kang_end_key_edit.text().strip(),
                'etarkangaroo_exe': self.kang_exe_edit.text().strip(),
                'temp_dir': self.kang_temp_dir_edit.text().strip(),
                'dp': self.kang_dp_spin.value(),
                'grid_params': self.kang_grid_edit.text().strip(),
                'subrange_bits': self.kang_subrange_spin.value(),
                'scan_duration': self.kang_duration_spin.value(),
            }
            if scanner.start(params):
                self.kang_start_stop_btn.setText("⏹ Остановить Kangaroo")
                self.kang_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
                self.kang_status_label.setText("Статус: Поиск запущен")
                self.append_log("Kangaroo поиск запущен", "success")
            else:
                self.kang_start_stop_btn.setText("🚀 Запустить Kangaroo")
                self.kang_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
                self.kang_status_label.setText("Статус: Ошибка запуска")
                self.append_log("Ошибка запуска Kangaroo", "error")

    def _on_cpu_worker_finished(self, worker_id: int):
        pass

    def _on_cpu_search_finished(self, success: bool):
        self.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.cpu_pause_resume_btn.setEnabled(False)
        self.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
        self.cpu_eta_label.setText("Оставшееся время: -")
        self.cpu_status_label.setText("Ожидание запуска")
        self.cpu_total_progress.setValue(0)
        self.cpu_total_stats_label.setText("Статус: Завершено")

    # ---------- Обновление статистики ----------
    def update_cpu_stats(self, stats: dict):
        total_scanned = stats.get('total_scanned', 0)
        total_found = stats.get('total_found', 0)
        total_speed = stats.get('total_speed', 0)
        workers = stats.get('workers', {})
        # Обновляем UI
        # Обновляем таблицу воркеров
        for wid, wstats in workers.items():
            self.update_cpu_worker_row(wid)
        self.update_cpu_total_stats()

    def update_gpu_stats(self, stats: dict):
        # Обновление GPU статистики
        progress = stats.get('progress', 0)
        total_speed = stats.get('total_speed', 0)
        total_checked = stats.get('total_scanned', 0)
        self.gpu_progress_bar.setValue(progress)
        self.gpu_speed_label.setText(f"Скорость: {total_speed:.2f} MKey/s")
        self.gpu_checked_label.setText(f"Проверено ключей: {total_checked:,}")

    def update_kangaroo_stats(self, stats: dict):
        speed = stats.get('total_speed', 0)
        session = stats.get('session', 0)
        elapsed = stats.get('elapsed', 0)
        self.kang_speed_label.setText(f"Скорость: {speed:.2f} MKeys/s")
        self.kang_session_label.setText(f"Сессия: #{session}")
        if elapsed:
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.kang_time_label.setText(f"⏱ {h:02d}:{m:02d}:{s:02d}")

    def update_vanity_stats(self, stats: dict):
        if 'total_speed' in stats:
            speed = stats['total_speed']
            if speed >= 1_000_000_000:
                spd_str = f"{speed/1_000_000_000:.2f} GKeys/s"
            elif speed >= 1_000_000:
                spd_str = f"{speed/1_000_000:.2f} MKeys/s"
            elif speed >= 1_000:
                spd_str = f"{speed/1_000:.2f} KKeys/s"
            else:
                spd_str = f"{speed} Keys/s"
            self.vanity_speed_label.setText(f"Скорость: {spd_str}")
        if 'total_found' in stats:
            self.vanity_found_label.setText(f"Найдено: {stats['total_found']}")
        if 'elapsed' in stats:
            elapsed = stats['elapsed']
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.vanity_time_label.setText(f"⏱ {h:02d}:{m:02d}:{s:02d}")

    # ==================== КОНВЕРТЕР ====================
    def setup_converter_tab(self) -> None:
        # Этот метод остаётся без изменений (не зависит от логик)
        converter_tab = QWidget()
        layout = QVBoxLayout(converter_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        info_label = QLabel("Введите приватный ключ в формате HEX (64 символа), выберите опции и нажмите 'Сгенерировать'.")
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
        self.set_busy(True)
        try:
            hex_key = self.hex_input.text().strip()
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
        try:
            int(s, 16)
            return True
        except ValueError:
            return False

    def copy_to_clipboard(self) -> None:
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
        is_random = (index == 1)
        self.cpu_attempts_edit.setEnabled(is_random)

    # ==================== PREDICT TAB ====================
    def setup_predict_connections(self) -> None:
        self.predict_browse_btn.clicked.connect(self.browse_predict_file)
        self.preview_keys_btn.clicked.connect(self.preview_predict_keys)
        self.predict_run_btn.clicked.connect(self.run_predict_analysis)

    def browse_predict_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл с ключами", str(self.BASE_DIR),
            "Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            self.predict_file_edit.setText(file_path)
            self.load_keys_for_preview(file_path)

    def load_keys_for_preview(self, file_path: str) -> None:
        from core.predict_logic import parse_keys_from_file, validate_keys
        raw_keys = parse_keys_from_file(file_path)
        valid_keys, error = validate_keys(raw_keys)
        if error or len(valid_keys) < 1:
            self.predict_keys_count_label.setText("0 валидных")
            self.append_log(f"⚠️ {error}", "warning")
            return
        self.predict_keys_count_label.setText(f"{len(valid_keys)} валидных ключей")
        self.append_log(f"✅ Загружено {len(valid_keys)} ключей из {os.path.basename(file_path)}", "success")

    def preview_predict_keys(self) -> None:
        from core.predict_logic import parse_keys_from_file, validate_keys
        file_path = self.predict_file_edit.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Предпросмотр", "Сначала выберите файл")
            return
        keys, _ = validate_keys(parse_keys_from_file(file_path))
        if not keys:
            QMessageBox.information(self, "Предпросмотр", "Валидные ключи не найдены")
            return
        preview = "\n".join([f"{i+1}. {k[:32]}...{k[-8:]}" for i, k in enumerate(keys[:10])])
        if len(keys) > 10:
            preview += f"\n... и ещё {len(keys)-10} ключей"
        QMessageBox.information(self, "Предпросмотр ключей", preview)

    def run_predict_analysis(self) -> None:
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
        self.predict_worker = PredictWorker(valid_keys, params, parent=self)
        self.predict_worker.progress_update.connect(self.on_predict_progress)
        self.predict_worker.analysis_finished.connect(self.on_predict_finished)
        self.predict_worker.plot_data_ready.connect(self.on_predict_plot_data_ready)
        self.predict_worker.error_occurred.connect(self.on_predict_error)
        self.predict_worker.start()

    def on_predict_progress(self, percent: int, message: str) -> None:
        self.predict_progress_bar.setValue(percent)
        self.predict_status_label.setText(f"⏳ {message}")

    def on_predict_finished(self, result_json: str) -> None:
        import json
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            self.on_predict_error("Некорректные данные от PredictWorker")
            return
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

    def on_predict_plot_data_ready(self, plot_data: dict) -> None:
        try:
            from core.predict_logic import PredictWorker
            # Используем статический метод для генерации графика
            worker = PredictWorker([], {})
            worker._generate_plot(
                plot_data['positions'],
                plot_data['log_diff'],
                plot_data['trend'],
                plot_data['widths'],
                plot_data['plot_path'],
                plot_data['has_scipy']
            )
            self.show_predict_plot(plot_data['plot_path'])
        except Exception as e:
            logger.error(f"Ошибка генерации графика: {e}", exc_info=True)

    def on_predict_error(self, error_msg: str) -> None:
        self.predict_progress_bar.hide()
        self.predict_run_btn.setEnabled(True)
        self.predict_status_label.setText("❌ Ошибка выполнения")
        self.append_log(f"❌ {error_msg}", "error")
        QMessageBox.critical(self, "Ошибка анализа", error_msg)

    def show_predict_plot(self, plot_path: str) -> None:
        if not plot_path or not os.path.exists(plot_path) or os.path.getsize(plot_path) < 100:
            self.predict_plot_label.setText("📊 График: ожидание данных...")
            self.predict_plot_label.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11pt; padding: 20px; background: #1a2332; border: 2px dashed #34495e; border-radius: 6px; }")
            return
        pixmap = QPixmap(plot_path)
        if pixmap.isNull():
            self.predict_plot_label.setText("❌ Ошибка загрузки графика")
            return
        max_width = max(600, self.predict_scroll.width() - 50)
        max_height = 500
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.predict_plot_label.setPixmap(pixmap)
        self.predict_plot_label.setText("")
        self.predict_plot_label.setStyleSheet("QLabel { background: #1a2332; border: 1px solid #34495e; border-radius: 6px; padding: 10px; }")

    def _fill_ranges_table(self, ranges: dict) -> None:
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

    def export_predict_results(self) -> None:
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

    # ==================== МОНИТОРИНГ СИСТЕМЫ ====================
    def update_system_info(self) -> None:
        try:
            mem = psutil.virtual_memory()
            self.safe_set_text('mem_label', f"{mem.used // (1024*1024)}/{mem.total // (1024*1024)} MB")
            self.safe_set_text('cpu_usage', f"{psutil.cpu_percent()}%")
            if self.cpu_scanner.is_running():
                status = "Работает" if not self.cpu_scanner._is_paused else "На паузе"
                self.safe_set_text('cpu_status_label', f"{status} ({len(self.cpu_scanner._pm._processes)} воркеров)")
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
                                return float(entry.current)
            for entries in temps.values():
                for entry in entries:
                    if entry.current is not None:
                        return float(entry.current)
        except (AttributeError, NotImplementedError):
            pass
        return None

    def _update_cpu_temp_display(self, temp: Optional[float]) -> None:
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

    def update_gpu_status(self) -> None:
        if not self.gpu_monitor_available or not PYNVML_AVAILABLE:
            return
        try:
            device_id = self.gpu_device_combo.currentData()
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
            mem_used_mb = mem_info.used / (1024*1024)
            mem_total_mb = mem_info.total / (1024*1024)
            mem_util = (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0
            try:
                temperature = int(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
            except pynvml.NVMLError:
                temperature = None
            self.safe_set_text('gpu_util_label', f"Загрузка GPU: {gpu_util} %")
            self.safe_set_value('gpu_util_bar', gpu_util)
            self.safe_set_text('gpu_mem_label', f"Память GPU: {mem_used_mb:.0f} / {mem_total_mb:.0f} MB ({mem_util:.1f}%)")
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

    # ==================== ОБРАБОТКА ОЧЕРЕДЕЙ ====================
    def process_all_queues(self) -> None:
        # Обрабатываем все очереди сканеров, у которых есть метод process_queue
        for scanner in [self.cpu_scanner, self.matrix_scanner]:
            if hasattr(scanner, 'process_queue'):
                scanner.process_queue()

    def update_cpu_worker_row(self, worker_id: int) -> None:
        stats = self.cpu_scanner._worker_stats.get(worker_id, {})
        scanned = stats.get('scanned', 0)
        found = stats.get('found', 0)
        speed = stats.get('speed', 0)
        progress = stats.get('progress', 0)
        table = self.cpu_workers_table
        if table.rowCount() <= worker_id:
            table.setRowCount(worker_id + 1)
        # ID
        item = table.item(worker_id, 0)
        if item is None:
            item = QTableWidgetItem(str(worker_id))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(worker_id, 0, item)
        else:
            item.setText(str(worker_id))
        # Проверено
        item = self._get_or_create_item(worker_id, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setText(f"{scanned:,}")
        # Найдено
        item = self._get_or_create_item(worker_id, 2, Qt.AlignmentFlag.AlignCenter)
        item.setText(str(found))
        # Скорость
        item = self._get_or_create_item(worker_id, 3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setText(f"{speed:,.0f} keys/sec")
        # Прогресс-бар
        bar = table.cellWidget(worker_id, 4)
        if bar is None:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar.setFormat("%p%")
            table.setCellWidget(worker_id, 4, bar)
        bar.setValue(progress)

    def _get_or_create_item(self, row: int, col: int, alignment: Qt.AlignmentFlag) -> QTableWidgetItem:
        item = self.cpu_workers_table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            item.setTextAlignment(alignment)
            self.cpu_workers_table.setItem(row, col, item)
        return item

    def update_cpu_total_stats(self) -> None:
        total_scanned = sum(s.get('scanned', 0) for s in self.cpu_scanner._worker_stats.values())
        total_found = sum(s.get('found', 0) for s in self.cpu_scanner._worker_stats.values())
        total_speed = sum(s.get('speed', 0) for s in self.cpu_scanner._worker_stats.values())
        total_progress = 0
        count = 0
        for s in self.cpu_scanner._worker_stats.values():
            if 'progress' in s:
                total_progress += s['progress']
                count += 1
        if count > 0:
            progress = total_progress / count
            self.safe_set_value('cpu_total_progress', int(progress))
        elapsed = max(1, self.cpu_scanner.elapsed_time())
        avg_speed = total_scanned / elapsed if elapsed > 0 else 0
        eta_text = "-"
        if self.cpu_scanner._params and self.cpu_scanner._params.get('total_keys', 0) > 0:
            total_keys = self.cpu_scanner._params['total_keys']
            processed = total_scanned
            remaining = max(0, total_keys - processed)
            if avg_speed > 0:
                eta_seconds = remaining / avg_speed
                eta_text = format_time(eta_seconds)
        self.safe_set_text('cpu_eta_label', f"Оставшееся время: {eta_text}")
        self.safe_set_text('cpu_total_stats_label',
                           f"Всего проверено: {total_scanned:,} | Найдено: {total_found} | "
                           f"Скорость: {total_speed:,.0f} keys/sec | "
                           f"Средняя скорость: {avg_speed:,.0f} keys/sec | "
                           f"Время работы: {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

    def _update_gpu_time(self) -> None:
        if self.gpu_scanner.is_running():
            elapsed = self.gpu_scanner.elapsed_time()
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            s = int(elapsed % 60)
            self.gpu_time_label.setText(f"Время работы: {h:02d}:{m:02d}:{s:02d}")
            status = "Случайный поиск" if self.gpu_random_checkbox.isChecked() else "Последовательный поиск"
            self.gpu_status_label.setText(f"Статус: {status}")
        else:
            self.gpu_time_label.setText("Время работы: 00:00:00")
            self.gpu_status_label.setText("Статус: Готов к работе")

    # ==================== HEALTH CHECK ====================
    def health_check(self) -> None:
        try:
            mem = psutil.Process().memory_info()
            if mem.rss > self.MEMORY_WARNING_THRESHOLD:
                mem_mb = mem.rss / 1024 / 1024
                logger.warning(f"Высокое использование памяти: {mem_mb:.0f} MB")
                self.append_log(f"⚠️ Высокое использование памяти: {mem_mb:.0f} MB!", "warning")
            # Проверка размера очереди CPU
            if hasattr(self.cpu_scanner, '_pm'):
                try:
                    qsize = self.cpu_scanner._pm._queue.qsize()
                    if qsize > self.QUEUE_SIZE_WARNING:
                        logger.warning(f"Большая очередь CPU: {qsize}")
                        self.append_log(f"⚠️ Большая очередь CPU: {qsize} сообщений", "warning")
                except NotImplementedError:
                    pass
        except Exception as e:
            logger.debug(f"Health check failed: {e}")

    # ==================== ОБЩИЕ МЕТОДЫ ====================
    def export_keys_csv(self) -> None:
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

    def show_context_menu(self, position: QPoint) -> None:
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
                'KANGAROO': QColor(255, 140, 0),
                'VANITY': QColor(255, 105, 180),
                'MATRIX': QColor(155, 89, 182)  # фиолетовый
            }
            source_emoji = {
                'GPU': '🎮',
                'CPU': '💻',
                'KANGAROO': '🦘',
                'VANITY': '🎨',
                'MATRIX': '🔷'
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
        try:
            if platform.system() == 'Windows':
                os.startfile(config.LOG_FILE)
            elif platform.system() == 'Darwin':
                subprocess.call(('open', config.LOG_FILE))
            else:
                subprocess.call(('xdg-open', config.LOG_FILE))
        except Exception as e:
            self.append_log(f"Не удалось открыть файл лога: {str(e)}", "error")

    # ==================== НАСТРОЙКИ ====================
    def load_settings(self) -> None:
        try:
            self.settings.auto_sync_all_widgets(self, namespace='main', save_mode=False)
            self.settings.auto_sync_all_widgets(self, namespace='cpu', save_mode=False)
            self.settings.auto_sync_all_widgets(self, namespace='gpu', save_mode=False)
            self.settings.auto_sync_all_widgets(self, namespace='kangaroo', save_mode=False)
            self.settings.auto_sync_all_widgets(self, namespace='vanity', save_mode=False)
            if geom := self.settings.get_global('window_geometry'):
                self.restoreGeometry(QByteArray.fromBase64(geom.encode('ascii')))
            if state := self.settings.get_global('window_state'):
                self.restoreState(QByteArray.fromBase64(state.encode('ascii')))
            self.append_log("✅ Настройки загружены", "success")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки: {e}")
            self.append_log(f"❌ Ошибка загрузки: {e}", "error")

    def save_settings(self) -> None:
        try:
            self.settings.auto_sync_all_widgets(self, namespace='main', save_mode=True)
            self.settings.auto_sync_all_widgets(self, namespace='cpu', save_mode=True)
            self.settings.auto_sync_all_widgets(self, namespace='gpu', save_mode=True)
            self.settings.auto_sync_all_widgets(self, namespace='kangaroo', save_mode=True)
            self.settings.auto_sync_all_widgets(self, namespace='vanity', save_mode=True)
            self.settings.set_global('window_geometry', self.saveGeometry())
            self.settings.set_global('window_state', self.saveState())
            self.settings.save()
            self.append_log("💾 Настройки сохранены", "success")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            self.append_log(f"❌ Ошибка сохранения: {e}", "error")

    def _save_gpu_progress(self, start_hex: str, end_hex: str, percent: float, gpu_id: int) -> None:
        try:
            log_path = Path(config.BASE_DIR) / "gpu_progress.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            line = f"{start_hex.zfill(64)}-{end_hex.zfill(64)} {int(percent)}% пройдено GPU{gpu_id}\n"
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")

    # ==================== ЗАКРЫТИЕ ПРИЛОЖЕНИЯ ====================
    def closeEvent(self, event) -> None:
        active = []
        for name, scanner in [("GPU", self.gpu_scanner), ("CPU", self.cpu_scanner),
                              ("Kangaroo", self.kangaroo_scanner), ("Vanity", self.vanity_scanner)]:
            if scanner.is_running():
                active.append(name)
        if active:
            reply = QMessageBox.question(
                self, 'Подтверждение закрытия',
                f"Активные процессы: {', '.join(active)}.\nВы уверены, что хотите закрыть программу?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self.save_settings()
        # Останавливаем все сканеры
        self.scanner_manager.stop_all()
        # Закрываем очереди
        for scanner in [self.cpu_scanner]:
            if hasattr(scanner, 'close_queue'):
                scanner.close_queue()
        # NVML shutdown
        if PYNVML_AVAILABLE and self.gpu_monitor_available:
            try:
                if getattr(pynvml, '_nvml_initialized', True):
                    pynvml.nvmlShutdown()
                    pynvml._nvml_initialized = False
                    logger.info("pynvml выключен")
            except Exception as e:
                logger.debug(f"NVML shutdown (ожидаемо): {type(e).__name__}: {e}")
        # Закрываем окна
        if self.gpu_monitor_window:
            try:
                self.gpu_monitor_window.close()
            except RuntimeError:
                pass
        if self.matrix_window:
            try:
                self.matrix_window.close()
            except RuntimeError:
                pass
        event.accept()