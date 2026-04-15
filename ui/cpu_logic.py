# core/cpu_logic.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations

import os
import time
import platform
import logging
import multiprocessing
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox
if TYPE_CHECKING:  # 🛠 УЛУЧШЕНИЕ 2: Избегаем циклических импортов для type hints
    from ui.main_window import BitcoinGPUCPUScanner

import config
import core.cpu_scanner as cpu_core
from utils.helpers import setup_logger, is_coincurve_available, validate_key_range

# 🛠 УЛУЧШЕНИЕ 3: Инициализация логгера в начале модуля
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 4: dataclass для конфигурации CPU с типизацией
@dataclass(frozen=True)
class CPUWorkerConfig:
    """Конфигурация параметров CPU воркера"""
    # Тайминги
    STATS_UPDATE_INTERVAL: float = 0.5  # секунды
    WORKER_JOIN_TIMEOUT: float = 0.1
    STOP_TIMEOUT: float = 3.0

    # Валидация
    MIN_ATTEMPTS: int = 1
    MIN_PREFIX_LENGTH: int = 1
    MAX_PREFIX_LENGTH: int = 20

    # Приоритеты процессов (Windows)
    # NORMAL_PRIORITY_CLASS по умолчанию
    DEFAULT_CREATION_FLAGS: int = 0x00000020  # type: ignore


# 🛠 УЛУЧШЕНИЕ 5: Глобальный экземпляр конфигурации
CPU_CONFIG: CPUWorkerConfig = CPUWorkerConfig()

# 🛠 УЛУЧШЕНИЕ 6: Константы для статусов и стилей
STATUS_IDLE: str = "Ожидание запуска"
STATUS_RUNNING: str = "Поиск запущен"
STATUS_PAUSED: str = "Приостановлен"
STATUS_STOPPED: str = "Остановлено пользователем"
STATUS_COMPLETED: str = "Завершено"

BTN_STYLE_SUCCESS: str = "background: #27ae60; font-weight: bold;"
BTN_STYLE_DANGER: str = "background: #e74c3c; font-weight: bold;"
BTN_STYLE_WARNING: str = "background: #f39c12; font-weight: bold;"
BTN_STYLE_DISABLED: str = "background: #3a3a45;"


class CPULogic(QObject):
    """
    Логика управления мультипроцессным CPU поиском приватных ключей.

    🛠 УЛУЧШЕНИЕ 7: Атрибуты класса с аннотациями типов
    """

    # 🛠 УЛУЧШЕНИЕ 8: Явные аннотации для сигналов
    update_stats = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    found_key = pyqtSignal(dict)
    worker_finished = pyqtSignal(int)

    # 🛠 УЛУЧШЕНИЕ 9: Явные аннотации атрибутов
    main_window: 'BitcoinGPUCPUScanner'
    cpu_signals: cpu_core.WorkerSignals
    processes: Dict[int, multiprocessing.Process]
    cpu_stop_requested: bool
    cpu_pause_requested: bool
    cpu_start_time: float
    cpu_total_scanned: int
    cpu_total_found: int
    workers_stats: Dict[int, Dict[str, Any]]
    last_update_time: float
    start_key: int
    end_key: int
    total_keys: int
    cpu_mode: str
    worker_chunks: Dict[int, Any]
    queue_active: bool
    process_queue: multiprocessing.Queue
    shutdown_event: multiprocessing.Event
    optimal_workers: Optional[int]

    def __init__(self, main_window: 'BitcoinGPUCPUScanner'):
        """
        Инициализация логики CPU.

        :param main_window: Ссылка на главное окно приложения
        """
        super().__init__()
        self.optimal_workers = None
        self.main_window = main_window
        self.cpu_signals = cpu_core.WorkerSignals()
        self.processes = {}  # {worker_id: process}
        self.cpu_stop_requested = False
        self.cpu_pause_requested = False
        self.cpu_start_time = 0.0
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
        self._connect_cpu_signals()

    def _connect_cpu_signals(self) -> None:  # 🛠 УЛУЧШЕНИЕ 10: Вынесено подключение сигналов
        """Подключение сигналов cpu_core к обработчикам."""
        self.cpu_signals.update_stats.connect(self.handle_cpu_update_stats)
        self.cpu_signals.log_message.connect(self.handle_log_message)
        self.cpu_signals.found_key.connect(self.handle_found_key)
        self.cpu_signals.worker_finished.connect(self.handle_worker_finished)

    # ═══════════════════════════════════════════
    # 🔧 МЕТОДЫ ВАЛИДАЦИИ И ПОДГОТОВКИ
    # ═══════════════════════════════════════════

    def validate_cpu_inputs(self) -> bool:
        """
        Валидация входных данных для CPU поиска.

        :return: True если все данные валидны, False иначе
        """
        # Валидация адреса
        address = self.main_window.cpu_target_edit.text().strip()
        if not self._validate_address(address):
            return False

        # Проверка доступности coincurve
        if not self._check_coincurve_available():
            return False

        # Валидация диапазона ключей
        if not self._validate_key_range():
            return False

        # Валидация количества попыток для случайного режима
        if self.cpu_mode == "random" and not self._validate_attempts():
            return False

        return True

    def _validate_address(self, address: str) -> bool:
        """
        Валидация биткоин-адреса.

        :param address: Строка адреса для проверки
        :return: True если адрес валиден
        """
        if not address or not config.BTC_ADDR_REGEX.match(address):
            QMessageBox.warning(self.main_window, "Ошибка", "Введите корректный BTC адрес для CPU")
            return False
        return True

    def _check_coincurve_available(self) -> bool:
        """
        Проверка доступности библиотеки coincurve.

        :return: True если библиотека доступна
        """
        if not is_coincurve_available():
            QMessageBox.warning(
                self.main_window, "Ошибка",
                "Библиотека coincurve не установлена. CPU поиск недоступен."
            )
            return False
        return True

    def _validate_key_range(self) -> bool:
        """
        Валидация диапазона приватных ключей.

        :return: True если диапазон валиден
        """
        result, error = validate_key_range(
            self.main_window.cpu_start_key_edit.text().strip(),
            self.main_window.cpu_end_key_edit.text().strip()
        )
        if result is None:
            QMessageBox.warning(self.main_window, "Ошибка", f"Неверный диапазон ключей: {error}")
            return False

        # 🛠 УЛУЧШЕНИЕ 11: Сохраняем результат валидации в атрибуты
        self.start_key, self.end_key, self.total_keys = result
        return True

    def _validate_attempts(self) -> bool:
        """
        Валидация количества попыток для случайного режима.

        :return: True если количество попыток валидно
        """
        try:
            attempts = int(self.main_window.cpu_attempts_edit.text())
            if attempts < CPU_CONFIG.MIN_ATTEMPTS:
                QMessageBox.warning(
                    self.main_window, "Ошибка",
                    "Количество попыток должно быть положительным числом"
                )
                return False
            return True
        except ValueError:
            QMessageBox.warning(self.main_window, "Ошибка", "Неверный формат количества попыток")
            return False

    # ═══════════════════════════════════════════
    # 🔧 МЕТОДЫ УПРАВЛЕНИЯ ПОИСКОМ
    # ═══════════════════════════════════════════

    def toggle_cpu_start_stop(self) -> None:  # 🛠 УЛУЧШЕНИЕ 12: Явный возврат None
        """Переключение запуск/остановка поиска."""
        if not self.processes:
            self.start_cpu_search()
        else:
            self.stop_cpu_search()

    def start_cpu_search(self) -> None:
        """
        Запуск CPU поиска с полной инициализацией.

        🛠 УЛУЧШЕНИЕ 13: Улучшена структура метода и обработка ошибок
        """
        if not self.validate_cpu_inputs():
            return

        self.main_window.save_settings()
        self._initialize_search_state()

        # Получение параметров поиска
        params = self._get_search_params()

        # Настройка UI для воркеров
        self._setup_workers_ui(params['workers'])

        # Получение флагов создания процесса
        creationflags = self._get_process_creation_flags()

        # Запуск воркеров
        self._start_workers(params, creationflags)

        # Обновление состояния кнопок
        self._on_search_started()

    def _initialize_search_state(self) -> None:
        """Инициализация состояния перед запуском поиска."""
        self.cpu_stop_requested = False
        self.cpu_pause_requested = False
        self.cpu_start_time = time.time()
        self.cpu_total_scanned = 0
        self.cpu_total_found = 0
        self.workers_stats = {}
        self.last_update_time = time.time()
        self.worker_chunks = {}
        self.queue_active = True

    def _get_search_params(self) -> Dict[str, Any]:
        """
        Сборка параметров для запуска воркеров.

        :return: Словарь с параметрами поиска
        """
        return {
            'target': self.main_window.cpu_target_edit.text().strip(),
            'prefix_len': self.main_window.cpu_prefix_spin.value(),
            'workers': self.main_window.cpu_workers_spin.value(),
            'start_int': self.start_key,
            'end_int': self.end_key,
            'attempts': (
                int(self.main_window.cpu_attempts_edit.text())
                if self.cpu_mode == "random" else 0
            ),
            'mode': self.cpu_mode
        }

    def _setup_workers_ui(self, workers_count: int) -> None:
        """
        Настройка таблицы воркеров в интерфейсе.

        :param workers_count: Количество воркеров
        """
        self.main_window.cpu_workers_table.setRowCount(workers_count)
        self.main_window.cpu_workers_table.setUpdatesEnabled(False)
        try:
            for i in range(workers_count):
                self.main_window.update_cpu_worker_row(i)
        finally:
            self.main_window.cpu_workers_table.setUpdatesEnabled(True)

    def _get_process_creation_flags(self) -> int:
        """
        Получение флагов создания процесса для установки приоритета.

        :return: Флаги creationflags для subprocess
        """
        priority_index = self.main_window.cpu_priority_combo.currentIndex()
        # 🛠 УЛУЧШЕНИЕ 14: Используем константу для дефолтного значения
        return config.WINDOWS_CPU_PRIORITY_MAP.get(
            priority_index, CPU_CONFIG.DEFAULT_CREATION_FLAGS
        )

    def _start_workers(self, params: Dict[str, Any], creationflags: int) -> None:
        """
        Запуск всех воркеров в отдельных процессах.

        :param params: Параметры поиска
        :param creationflags: Флаги создания процесса
        """
        for i in range(params['workers']):
            self._start_single_worker(i, params, creationflags)

        mode_name = 'случайного' if params['mode'] == 'random' else 'последовательного'
        self.main_window.append_log(
            f"Запущено {params['workers']} CPU воркеров в режиме {mode_name} поиска"
        )

    def _start_single_worker(
            self,
            worker_id: int,
            params: Dict[str, Any],
            creationflags: int
    ) -> None:
        """
        Запуск одного воркера в отдельном процессе.

        :param worker_id: ID воркера
        :param params: Параметры поиска
        :param creationflags: Флаги создания процесса
        """
        p = multiprocessing.Process(
            target=cpu_core.worker_main,
            args=(
                params['target'][:params['prefix_len']],
                params['start_int'],
                params['end_int'],
                params['attempts'],
                params['mode'],
                worker_id,
                params['workers'],
                self.process_queue,
                self.shutdown_event
            )
        )
        p.daemon = True

        # Установка приоритета (для Windows)
        if platform.system() == 'Windows' and creationflags:
            try:
                p._config['creationflags'] = creationflags  # type: ignore
            except (AttributeError, KeyError) as e:
                logger.debug(f"Не удалось установить приоритет для воркера {worker_id}: {e}")

        p.start()
        self.processes[worker_id] = p

        # Инициализация статистики воркера
        self.workers_stats[worker_id] = {
            'scanned': 0,
            'found': 0,
            'speed': 0,
            'progress': 0,
            'active': True
        }

    def _on_search_started(self) -> None:
        """Обновление UI после успешного запуска поиска."""
        self.main_window.cpu_start_stop_btn.setText("Стоп CPU (Ctrl+Q)")
        self.main_window.cpu_start_stop_btn.setStyleSheet(BTN_STYLE_DANGER)
        self.main_window.cpu_pause_resume_btn.setEnabled(True)
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet(BTN_STYLE_WARNING)

    # ═══════════════════════════════════════════
    # 🔧 ОБРАБОТЧИКИ СОБЫТИЙ И СИГНАЛОВ
    # ═══════════════════════════════════════════

    def handle_cpu_update_stats(self, stats: Dict[str, Any]) -> None:
        """
        Обработка обновления статистики от воркера.

        :param stats: Словарь со статистикой воркера
        """
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

    def handle_log_message(self, message: str) -> None:
        """
        Обработка лог-сообщения от воркера.

        :param message: Текст сообщения для логирования
        """
        self.main_window.append_log(message)

    def handle_found_key(self, key_data: Dict[str, Any]) -> None:
        """
        Обработка найденного ключа.

        :param key_data: Словарь с данными найденного ключа
        """
        self.main_window.handle_found_key(key_data)

    def handle_worker_finished(self, worker_id: int) -> None:
        """
        Обработчик сигнала завершения отдельного воркера.

        :param worker_id: ID завершившегося воркера
        """
        # 🛠 УЛУЧШЕНИЕ 15: Безопасный доступ к атрибуту через проверку
        if hasattr(self.main_window, 'cpu_logic'):
            self.main_window.cpu_logic.cpu_worker_finished(worker_id)

    def cpu_worker_finished(self, worker_id: int) -> None:
        """
        Обработчик завершения отдельного CPU воркера.

        :param worker_id: ID завершившегося воркера
        """
        # Удаляем завершенный процесс из словаря
        if worker_id in self.processes:
            process = self.processes[worker_id]
            if process.is_alive():
                process.join(timeout=CPU_CONFIG.WORKER_JOIN_TIMEOUT)
            del self.processes[worker_id]

        # Проверяем, остались ли еще активные воркеры
        if not self.processes:  # Все воркеры завершены
            self._on_all_workers_finished()

    def _on_all_workers_finished(self) -> None:
        """Обработка завершения всех воркеров."""
        self.main_window.append_log("Все CPU воркеры завершили работу")
        self._reset_ui_to_idle()
        self.main_window.cpu_total_stats_label.setText(f"Статус: {STATUS_COMPLETED}")

    def _reset_ui_to_idle(self) -> None:
        """Сброс интерфейса в состояние ожидания."""
        self.main_window.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.main_window.cpu_start_stop_btn.setStyleSheet(BTN_STYLE_SUCCESS)
        self.main_window.cpu_pause_resume_btn.setEnabled(False)
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet(BTN_STYLE_DISABLED)
        self.main_window.cpu_eta_label.setText("Оставшееся время: -")
        self.main_window.cpu_status_label.setText(STATUS_IDLE)
        self.main_window.cpu_total_progress.setValue(0)

    # ═══════════════════════════════════════════
    # 🔧 МЕТОДЫ УПРАВЛЕНИЯ СОСТОЯНИЕМ
    # ═══════════════════════════════════════════

    def toggle_cpu_pause_resume(self) -> None:
        """Переключение пауза/продолжить поиск."""
        if self.cpu_pause_requested:
            self.resume_cpu_search()
        else:
            self.pause_cpu_search()

    def pause_cpu_search(self) -> None:
        """Приостановка CPU поиска."""
        self.cpu_pause_requested = True

        for worker_id, process in self.processes.items():
            if process.is_alive():
                try:
                    process.terminate()
                    self.main_window.append_log(f"CPU воркер {worker_id} остановлен", "warning")
                except (ProcessLookupError, OSError) as e:
                    logger.debug(f"Воркер {worker_id} уже завершён: {e}")

        self.processes.clear()
        self.main_window.append_log("CPU поиск приостановлен", "warning")
        self.main_window.cpu_pause_resume_btn.setText("Продолжить")
        self.main_window.cpu_pause_resume_btn.setStyleSheet(BTN_STYLE_SUCCESS)

    def resume_cpu_search(self) -> None:
        """Продолжение приостановленного поиска."""
        self.cpu_pause_requested = False
        self.start_cpu_search()
        self.main_window.append_log("CPU поиск продолжен", "success")
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet(BTN_STYLE_WARNING)

    def stop_cpu_search(self) -> None:
        """
        Полная остановка CPU поиска.

        🛠 УЛУЧШЕНИЕ 16: Делегирование остановки в cpu_core с обработкой ошибок
        """
        try:
            cpu_core.stop_cpu_search(self.processes, self.shutdown_event)
            self.main_window.append_log("CPU поиск остановлен", "warning")
        except Exception as e:
            logger.warning(f"Ошибка при остановке процессов: {e}")
            self.main_window.append_log(f"⚠️ Ошибка остановки: {type(e).__name__}: {str(e)}", "error")

        # Восстанавливаем состояние UI
        self._on_search_stopped()

    def _on_search_stopped(self) -> None:
        """Обновление UI после остановки поиска."""
        self.main_window.cpu_start_stop_btn.setText("Старт CPU (Ctrl+S)")
        self.main_window.cpu_start_stop_btn.setStyleSheet(BTN_STYLE_SUCCESS)
        self.main_window.cpu_pause_resume_btn.setEnabled(False)
        self.main_window.cpu_pause_resume_btn.setText("Пауза (Ctrl+P)")
        self.main_window.cpu_pause_resume_btn.setStyleSheet(BTN_STYLE_DISABLED)
        self.main_window.cpu_eta_label.setText("Оставшееся время: -")
        self.main_window.cpu_status_label.setText(STATUS_STOPPED)

        # Очищаем таблицу статистики воркеров
        self.main_window.cpu_workers_table.setRowCount(0)

        # Сброс прогресса
        self.main_window.cpu_total_progress.setValue(0)
        self.main_window.cpu_total_stats_label.setText(f"Статус: {STATUS_STOPPED}")

    def close_queue(self) -> None:
        """
        Закрытие и очистка очереди сообщений.

        🛠 УЛУЧШЕНИЕ 17: Улучшена обработка ошибок при закрытии очереди
        """
        try:
            self.queue_active = False
            if hasattr(self.process_queue, 'close'):
                self.process_queue.close()
            if hasattr(self.process_queue, 'join_thread'):
                self.process_queue.join_thread()
        except (BrokenPipeError, OSError) as e:
            logger.debug(f"Очередь уже закрыта: {e}")
        except Exception as e:
            logger.error(f"Ошибка закрытия очереди: {type(e).__name__}: {str(e)}")


# 🛠 УЛУЧШЕНИЕ 18: Явный экспорт публичного API модуля
__all__ = [
    'CPUWorkerConfig',
    'CPU_CONFIG',
    'STATUS_IDLE',
    'STATUS_RUNNING',
    'STATUS_PAUSED',
    'STATUS_STOPPED',
    'STATUS_COMPLETED',
    'BTN_STYLE_SUCCESS',
    'BTN_STYLE_DANGER',
    'BTN_STYLE_WARNING',
    'BTN_STYLE_DISABLED',
    'CPULogic',
]