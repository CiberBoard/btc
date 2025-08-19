# core/cpu_logic.py
import multiprocessing
import time
import platform

from PyQt5.QtWidgets import QMessageBox

import config
from utils.helpers import is_coincurve_available, validate_key_range
import core.cpu_scanner as cpu_core
from PyQt5.QtCore import QObject, pyqtSignal

class CPULogic(QObject):
    # Сигналы для связи с основным окном
    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    found_key = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
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

        # Подключаем сигналы
        self.cpu_signals.update_stats.connect(self.handle_cpu_update_stats)
        self.cpu_signals.log_message.connect(self.handle_log_message)
        self.cpu_signals.found_key.connect(self.handle_found_key)
        self.cpu_signals.worker_finished.connect(self.handle_worker_finished)

    # ============ CPU METHODS ============
    def validate_cpu_inputs(self):
        address = self.main_window.cpu_target_edit.text().strip()
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self.main_window, "Ошибка", "Введите корректный BTC адрес для CPU")
            return False
        if not is_coincurve_available():
            QMessageBox.warning(self.main_window, "Ошибка", "Библиотека coincurve не установлена. CPU поиск недоступен.")
            return False
        # Проверка диапазона ключей
        result, error = validate_key_range(
            self.main_window.cpu_start_key_edit.text().strip(),
            self.main_window.cpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self.main_window, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False
        self.start_key, self.end_key, self.total_keys = result
        if self.cpu_mode == "random":
            try:
                attempts = int(self.main_window.cpu_attempts_edit.text())
                if attempts <= 0:
                    QMessageBox.warning(self.main_window, "Ошибка", "Количество попыток должно быть положительным числом")
                    return False
            except ValueError:
                QMessageBox.warning(self.main_window, "Ошибка", "Неверный формат количества попыток")
                return False
        return True

    def start_cpu_search(self):
        if not self.validate_cpu_inputs():
            return
        self.main_window.save_settings()
        self.cpu_stop_requested = False
        self.cpu_pause_requested = False
        self.cpu_start_time = time.time()
        self.cpu_total_scanned = 0
        self.cpu_total_found = 0
        self.workers_stats = {}
        self.last_update_time = time.time()
        self.worker_chunks = {}
        self.queue_active = True
        target = self.main_window.cpu_target_edit.text().strip()
        prefix_len = self.main_window.cpu_prefix_spin.value()
        workers = self.main_window.cpu_workers_spin.value()
        start_int = self.start_key
        end_int = self.end_key
        attempts = int(self.main_window.cpu_attempts_edit.text()) if self.cpu_mode == "random" else 0
        # Очистка таблицы воркеров
        self.main_window.cpu_workers_table.setRowCount(workers)
        self.main_window.cpu_workers_table.setUpdatesEnabled(False)
        try:
            for i in range(workers):
                self.main_window.update_cpu_worker_row(i)
        finally:
            self.main_window.cpu_workers_table.setUpdatesEnabled(True)
        # Установка приоритета процесса (Windows)
        priority_index = self.main_window.cpu_priority_combo.currentIndex()
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
        self.main_window.append_log(
            f"Запущено {workers} CPU воркеров в режиме {'случайного' if self.cpu_mode == 'random' else 'последовательного'} поиска")
        self.main_window.cpu_start_stop_btn.setText("Стоп CPU (Ctrl+Q)")
        self.main_window.cpu_start_stop_btn.setStyleSheet("background: #e74c3c; font-weight: bold;")
        self.main_window.cpu_pause_resume_btn.setEnabled(True)
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

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

    def handle_cpu_update_stats(self, stats):
        worker_id = stats.get('worker_id')
        if worker_id is not None:
            self.workers_stats[worker_id] = {
                'scanned': stats.get('scanned', 0),
                'found': stats.get('found', 0),
                'speed': stats.get('speed', 0),
                'progress': stats.get('progress', 0)
            }
            self.main_window.update_cpu_worker_row(worker_id)
            self.main_window.update_cpu_total_stats()

    def handle_log_message(self, message):
        self.main_window.append_log(message)

    def handle_found_key(self, key_data):
        self.main_window.handle_found_key(key_data)

    def handle_worker_finished(self, worker_id):
        self.main_window.cpu_logic.cpu_worker_finished(worker_id)

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
            self.main_window.append_log("Все CPU воркеры завершили работу")
            # Восстанавливаем состояние UI
            self.main_window.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
            self.main_window.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
            self.main_window.cpu_pause_resume_btn.setEnabled(False)
            self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
            self.main_window.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
            self.main_window.cpu_eta_label.setText("Оставшееся время: -")
            # Сброс статуса
            self.main_window.cpu_status_label.setText("Ожидание запуска")
            # Сброс прогресса
            self.main_window.cpu_total_progress.setValue(0)
            self.main_window.cpu_total_stats_label.setText("Статус: Завершено")

    def pause_cpu_search(self):
        self.cpu_pause_requested = True
        for worker_id, process in self.processes.items():
            if process.is_alive():
                process.terminate()
                self.main_window.append_log(f"CPU воркер {worker_id} остановлен")
        self.processes = {}
        self.main_window.append_log("CPU поиск приостановлен")
        self.main_window.cpu_pause_resume_btn.setText("Продолжить")
        self.main_window.cpu_pause_resume_btn.setStyleSheet("background: #27ae60; font-weight: bold;")

    def resume_cpu_search(self):
        self.cpu_pause_requested = False
        self.start_cpu_search()
        self.main_window.append_log("CPU поиск продолжен")
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet("background: #f39c12; font-weight: bold;")

    # Обновленная функция stop_cpu_search
    def stop_cpu_search(self):
        cpu_core.stop_cpu_search(self.processes, self.shutdown_event)
        self.main_window.append_log("CPU поиск остановлен")
        # Восстанавливаем состояние UI
        self.main_window.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.main_window.cpu_start_stop_btn.setStyleSheet("background: #27ae60; font-weight: bold;")
        self.main_window.cpu_pause_resume_btn.setEnabled(False)
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet("background: #3a3a45;")
        self.main_window.cpu_eta_label.setText("Оставшееся время: -")
        self.main_window.cpu_status_label.setText("Остановлено пользователем")
        # Очищаем таблицу статистики воркеров
        self.main_window.cpu_workers_table.setRowCount(0)
        # Сброс прогресса
        self.main_window.cpu_total_progress.setValue(0)
        self.main_window.cpu_total_stats_label.setText("Статус: Остановлено")

    def close_queue(self):
        try:
            self.queue_active = False
            self.process_queue.close()
            self.process_queue.join_thread()
        except Exception as e:
            cpu_core.logger.error(f"Ошибка закрытия очереди: {str(e)}")
