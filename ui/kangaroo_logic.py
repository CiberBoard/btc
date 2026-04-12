# ui/kangaroo_logic.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations

import os
import time
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field  # 🛠 УЛУЧШЕНИЕ 2: dataclass для конфигурации

from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMessageBox

if TYPE_CHECKING:  # 🛠 УЛУЧШЕНИЕ 3: Избегаем циклических импортов для type hints
    from ui.main_window import BitcoinGPUCPUScanner

from core.kangaroo_worker import KangarooWorker

# 🛠 УЛУЧШЕНИЕ 4: Инициализация логгера в начале модуля
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 5: dataclass для конфигурации Kangaroo с типизацией
@dataclass(frozen=True)
class KangarooConfig:
    """Конфигурация параметров Kangaroo поиска"""
    # Валидация
    MIN_PUBKEY_LENGTH: int = 64
    MAX_PUBKEY_LENGTH: int = 130  # 04 + 64*2 для несжатого ключа

    # Тайминги
    TIMER_INTERVAL_MS: int = 500
    THREAD_WAIT_TIMEOUT_MS: int = 3000

    # Параметры по умолчанию для автонастройки
    DEFAULT_DP: int = 22
    DEFAULT_SUBRANGE_BITS: int = 36
    DEFAULT_DURATION_SEC: int = 600

    # Отображение диапазонов
    RANGE_PREVIEW_CUT: int = 8
    RANGE_PREVIEW_SUFFIX: int = 10
    RANGE_PREVIEW_THRESHOLD: int = 16


# 🛠 УЛУЧШЕНИЕ 6: Глобальный экземпляр конфигурации
KANGAROO_CONFIG: KangarooConfig = KangarooConfig()

# 🛠 УЛУЧШЕНИЕ 7: Константы для стилей кнопок
BTN_STYLE_RUNNING: str = """
    QPushButton {background: #e74c3c; font-weight: bold;}
    QPushButton:hover {background: #c0392b;}
"""
BTN_STYLE_STOPPED: str = """
    QPushButton {background: #27ae60; font-weight: bold;}
    QPushButton:hover {background: #2ecc71;}
"""

# 🛠 УЛУЧШЕНИЕ 8: Константы для статусов
STATUS_RUNNING: str = "Работает..."
STATUS_STOPPED: str = "Остановлен"
STATUS_COLOR_RUNNING: str = "#27ae60"
STATUS_COLOR_STOPPED: str = "#e74c3c"


class KangarooLogic:
    """
    Класс для управления логикой Kangaroo поиска.

    🛠 УЛУЧШЕНИЕ 9: Атрибуты класса с аннотациями типов
    """

    # 🛠 УЛУЧШЕНИЕ 10: Явные аннотации атрибутов
    main_window: 'BitcoinGPUCPUScanner'
    worker_thread: Optional[QThread]
    worker: Optional[KangarooWorker]
    is_running: bool
    start_time: Optional[float]
    session_count: int
    total_speed: float
    current_range_start: str
    current_range_end: str
    timer: QTimer

    def __init__(self, main_window: 'BitcoinGPUCPUScanner'):
        """
        Инициализация логики Kangaroo.

        :param main_window: Ссылка на главное окно приложения
        """
        self.main_window = main_window
        self.worker_thread = None
        self.worker = None
        self.is_running = False
        self.start_time = None
        self.session_count = 0
        self.total_speed = 0.0
        self.current_range_start = ""
        self.current_range_end = ""

        # Таймер для обновления времени
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_display)
        # 🛠 УЛУЧШЕНИЕ 11: Используем константу для интервала таймера
        self.timer.setInterval(KANGAROO_CONFIG.TIMER_INTERVAL_MS)

    def toggle_kangaroo_search(self) -> None:  # 🛠 УЛУЧШЕНИЕ 12: Явный возврат None
        """Переключение запуск/остановка поиска."""
        if self.is_running:
            self.stop_kangaroo_search()
        else:
            self.start_kangaroo_search()

    def start_kangaroo_search(self) -> None:
        """
        Запуск Kangaroo поиска с полной валидацией параметров.

        🛠 УЛУЧШЕНИЕ 13: Улучшена структура метода и обработка ошибок
        """
        try:
            # 🛠 УЛУЧШЕНИЕ 14: Вынесена валидация в отдельный метод
            params = self._validate_and_prepare_params()
            if params is None:
                return  # Валидация не пройдена, ошибка уже показана

            # Создание и запуск worker
            self._start_worker_thread(params)

            # Обновление состояния и UI
            self._on_search_started()

            self.main_window.append_log("🦘 Kangaroo поиск запущен", "success")

        except Exception as e:
            logger.exception("Ошибка запуска Kangaroo")
            QMessageBox.critical(
                self.main_window,
                "Ошибка",
                f"Не удалось запустить Kangaroo поиск:\n{type(e).__name__}: {str(e)}"
            )
            self.is_running = False

    def _validate_and_prepare_params(self) -> Optional[Dict[str, Any]]:
        """
        Валидация входных данных и подготовка параметров для worker.

        :return: Словарь параметров или None при ошибке валидации
        """
        # Валидация публичного ключа
        pubkey = self.main_window.kang_pubkey_edit.text().strip()
        if not self._validate_pubkey(pubkey):
            return None

        # Валидация диапазона
        rb_hex = self.main_window.kang_start_key_edit.text().strip()
        re_hex = self.main_window.kang_end_key_edit.text().strip()
        if not self._validate_range(rb_hex, re_hex):
            return None

        # Проверка существования исполняемого файла
        exe_path = self.main_window.kang_exe_edit.text().strip()
        if not self._validate_executable(exe_path):
            return None

        # Создание временной директории
        temp_dir = self.main_window.kang_temp_dir_edit.text().strip()
        try:
            os.makedirs(temp_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Не удалось создать временную директорию: {e}")
            QMessageBox.critical(
                self.main_window,
                "Ошибка",
                f"Не удалось создать директорию {temp_dir}:\n{e}"
            )
            return None

        # 🛠 УЛУЧШЕНИЕ 15: Сбор параметров через отдельный метод
        return self._build_worker_params(pubkey, rb_hex, re_hex, exe_path, temp_dir)

    def _validate_pubkey(self, pubkey: str) -> bool:
        """
        Валидация публичного ключа.

        :param pubkey: Строка публичного ключа
        :return: True если валиден, иначе показывает диалог и возвращает False
        """
        if not pubkey or len(pubkey) < KANGAROO_CONFIG.MIN_PUBKEY_LENGTH:
            QMessageBox.warning(
                self.main_window,
                "Ошибка",
                "Введите корректный публичный ключ (минимум 64 символа)"
            )
            return False
        return True

    def _validate_range(self, rb_hex: str, re_hex: str) -> bool:
        """
        Валидация диапазона ключей.

        :param rb_hex: Начало диапазона в HEX
        :param re_hex: Конец диапазона в HEX
        :return: True если валиден, иначе показывает диалог и возвращает False
        """
        if not rb_hex or not re_hex:
            QMessageBox.warning(
                self.main_window,
                "Ошибка",
                "Введите начальный и конечный ключи диапазона"
            )
            return False
        return True

    def _validate_executable(self, exe_path: str) -> bool:
        """
        Проверка существования исполняемого файла.

        :param exe_path: Путь к etarkangaroo.exe
        :return: True если файл существует, иначе показывает диалог и возвращает False
        """
        if not os.path.exists(exe_path):
            QMessageBox.critical(
                self.main_window,
                "Ошибка",
                f"Файл не найден: {exe_path}\n\nУкажите правильный путь к etarkangaroo.exe"
            )
            return False
        return True

    def _build_worker_params(
            self,
            pubkey: str,
            rb_hex: str,
            re_hex: str,
            exe_path: str,
            temp_dir: str
    ) -> Dict[str, Any]:
        """
        Сборка словаря параметров для KangarooWorker.

        :return: Словарь с параметрами для worker
        """
        return {
            'etarkangaroo_exe': exe_path,
            'pubkey_hex': pubkey,
            'rb_hex': rb_hex,
            're_hex': re_hex,
            'dp': int(self.main_window.kang_dp_spin.value()),
            'grid_params': self.main_window.kang_grid_edit.text().strip(),
            'temp_dir': temp_dir,
            'scan_duration': int(self.main_window.kang_duration_spin.value()),
            'subrange_bits': int(self.main_window.kang_subrange_spin.value())
        }

    def _start_worker_thread(self, params: Dict[str, Any]) -> None:
        """
        Создание и запуск worker в отдельном потоке.

        :param params: Параметры для KangarooWorker
        """
        self.worker = KangarooWorker(params)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # 🛠 УЛУЧШЕНИЕ 16: Вынесено подключение сигналов в отдельный метод
        self._connect_worker_signals()

        self.worker_thread.started.connect(self.worker.run)

        # 🛠 УЛУЧШЕНИЕ 17: Инициализация состояния перед запуском
        self.is_running = True
        self.start_time = time.time()
        self.session_count = 0

        self.worker_thread.start()
        self.timer.start()

    def _connect_worker_signals(self) -> None:
        """Подключение сигналов worker к обработчикам."""
        self.worker.log_message.connect(self.handle_log_message)
        self.worker.status_update.connect(self.handle_status_update)
        self.worker.range_update.connect(self.handle_range_update)
        self.worker.found_key.connect(self.handle_found_key)
        self.worker.finished.connect(self.handle_worker_finished)

    def _on_search_started(self) -> None:
        """Обновление UI после успешного запуска поиска."""
        self.main_window.kang_start_stop_btn.setText("⏹ Остановить Kangaroo")
        self.main_window.kang_start_stop_btn.setStyleSheet(BTN_STYLE_RUNNING)
        self.main_window.kang_status_label.setText(f"Статус: {STATUS_RUNNING}")
        self.main_window.kang_status_label.setStyleSheet(
            f"color: {STATUS_COLOR_RUNNING}; font-weight: bold;"
        )

        # Блокировка полей ввода
        self.set_input_enabled(False)

    def stop_kangaroo_search(self) -> None:
        """
        Остановка Kangaroo поиска с корректным завершением потоков.

        🛠 УЛУЧШЕНИЕ 18: Улучшена обработка ошибок при остановке
        """
        try:
            self._stop_worker_safely()
            self._on_search_stopped()
            self.main_window.append_log("🛑 Kangaroo поиск остановлен", "warning")

        except Exception as e:
            logger.exception("Ошибка остановки Kangaroo")
            self.main_window.append_log(f"Ошибка остановки: {type(e).__name__}: {str(e)}", "error")

    def _stop_worker_safely(self) -> None:
        """Безопасная остановка worker и потока."""
        if self.worker:
            try:
                self.worker.stop()
            except Exception as e:
                logger.warning(f"Ошибка при вызове worker.stop(): {e}")

        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            # 🛠 УЛУЧШЕНИЕ 19: Используем константу для таймаута
            if not self.worker_thread.wait(KANGAROO_CONFIG.THREAD_WAIT_TIMEOUT_MS):
                logger.warning("Worker thread не завершился вовремя")

        self.is_running = False
        self.timer.stop()

    def _on_search_stopped(self) -> None:
        """Обновление UI после остановки поиска."""
        self.main_window.kang_start_stop_btn.setText("🚀 Запустить Kangaroo")
        self.main_window.kang_start_stop_btn.setStyleSheet(BTN_STYLE_STOPPED)
        self.main_window.kang_status_label.setText(f"Статус: {STATUS_STOPPED}")
        self.main_window.kang_status_label.setStyleSheet(
            f"color: {STATUS_COLOR_STOPPED}; font-weight: bold;"
        )

        # Разблокировка полей ввода
        self.set_input_enabled(True)

    def handle_log_message(self, message: str) -> None:
        """
        Обработка лог-сообщений от worker.

        :param message: Текст сообщения для логирования
        """
        self.main_window.append_log(message)

    def handle_status_update(
            self,
            speed_mkeys: float,
            elapsed_sec: float,
            session_num: int
    ) -> None:
        """
        Обновление статистики поиска.

        :param speed_mkeys: Скорость в миллионах ключей в секунду
        :param elapsed_sec: Прошедшее время в секундах
        :param session_num: Номер текущей сессии
        """
        self.total_speed = speed_mkeys
        self.session_count = session_num

        self.main_window.kang_speed_label.setText(f"Скорость: {speed_mkeys:.2f} MKeys/s")
        self.main_window.kang_session_label.setText(f"Сессия: #{session_num}")

    def handle_range_update(self, rb: str, re: str) -> None:
        """
        Обновление отображения текущего диапазона поиска.

        :param rb: Начало диапазона в HEX
        :param re: Конец диапазона в HEX
        """
        self.current_range_start = rb
        self.current_range_end = re

        # 🛠 УЛУЧШЕНИЕ 20: Используем константы для обрезки строк
        rb_short = self._format_range_display(rb)
        re_short = self._format_range_display(re)

        self.main_window.kang_range_label.setText(
            f"rb = 0x{rb_short}\n"
            f"re = 0x{re_short}"
        )

    def _format_range_display(self, hex_value: str) -> str:
        """
        Форматирует шестнадцатеричное значение для компактного отображения.

        :param hex_value: HEX строка для форматирования
        :return: Отформатированная строка с обрезкой при необходимости
        """
        cleaned = hex_value.lstrip('0') or '0'

        if len(cleaned) > KANGAROO_CONFIG.RANGE_PREVIEW_THRESHOLD:
            return f"{cleaned[:KANGAROO_CONFIG.RANGE_PREVIEW_CUT]}…{cleaned[-KANGAROO_CONFIG.RANGE_PREVIEW_SUFFIX:]}"
        return cleaned

    def handle_found_key(self, private_hex: str) -> None:
        """
        Обработка найденного приватного ключа.

        :param private_hex: Найденный приватный ключ в формате HEX
        """
        try:
            from core.hextowif import generate_all_from_hex

            # Генерация всех форматов ключа
            result = generate_all_from_hex(private_hex, compressed=True, testnet=False)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

            # 🛠 УЛУЧШЕНИЕ 21: Создание данных ключа через отдельный метод
            key_data = self._build_found_key_data(timestamp, private_hex, result)

            self.main_window.handle_found_key(key_data)

            # Остановка поиска после находки
            self.stop_kangaroo_search()

            # 🛠 УЛУЧШЕНИЕ 22: Формирование сообщения через отдельный метод
            message = self._build_found_key_message(result, private_hex)
            QMessageBox.information(
                self.main_window,
                "🎉 Ключ найден!",
                message
            )

        except ImportError as e:
            logger.error(f"Не удалось импортировать generate_all_from_hex: {e}")
            self.main_window.append_log(f"Ошибка импорта модуля: {e}", "error")
        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.main_window.append_log(f"Ошибка обработки ключа: {type(e).__name__}: {str(e)}", "error")

    def _build_found_key_data(
            self,
            timestamp: str,
            private_hex: str,
            result: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Создание словаря данных найденного ключа.

        :param timestamp: Время находки
        :param private_hex: Приватный ключ в HEX
        :param result: Результат генерации всех форматов ключа
        :return: Словарь с данными для handle_found_key
        """
        return {
            'timestamp': timestamp,
            'address': result['P2PKH'],
            'hex_key': private_hex,
            'wif_key': result['WIF'],
            'source': 'KANGAROO'
        }

    def _build_found_key_message(self, result: Dict[str, str], private_hex: str) -> str:
        """
        Формирование информационного сообщения о найденном ключе.

        :param result: Результат генерации всех форматов ключа
        :param private_hex: Приватный ключ в HEX
        :return: HTML-строка для QMessageBox
        """
        return (
            f"<b>Kangaroo нашел приватный ключ!</b><br><br>"
            f"<b>Адрес:</b> {result['P2PKH']}<br>"
            f"<b>HEX:</b> {private_hex[:32]}...<br>"
            f"<b>WIF:</b> {result['WIF'][:20]}...<br><br>"
            f"Ключ сохранен в таблице найденных ключей."
        )

    def handle_worker_finished(self, success: bool) -> None:
        """
        Обработка сигнала завершения worker.

        :param success: Флаг успешного завершения
        """
        if self.is_running:
            if success:
                self.main_window.append_log("✅ Kangaroo успешно завершен", "success")
            else:
                self.main_window.append_log("⚠ Kangaroo завершен без результата", "warning")

            self.stop_kangaroo_search()

    def update_time_display(self) -> None:
        """Обновление отображения времени работы поиска."""
        if self.is_running and self.start_time is not None:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60

            self.main_window.kang_time_label.setText(
                f"Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )

    def set_input_enabled(self, enabled: bool) -> None:
        """
        Включение/выключение полей ввода в интерфейсе.

        :param enabled: True для включения, False для блокировки
        """
        # 🛠 УЛУЧШЕНИЕ 23: Список виджетов для избежания дублирования кода
        widgets = [
            self.main_window.kang_pubkey_edit,
            self.main_window.kang_start_key_edit,
            self.main_window.kang_end_key_edit,
            self.main_window.kang_dp_spin,
            self.main_window.kang_grid_edit,
            self.main_window.kang_duration_spin,
            self.main_window.kang_subrange_spin,
            self.main_window.kang_exe_edit,
            self.main_window.kang_temp_dir_edit,
            self.main_window.kang_browse_exe_btn,
            self.main_window.kang_browse_temp_btn,
        ]

        for widget in widgets:
            if widget is not None:  # 🛠 УЛУЧШЕНИЕ 24: Защита от None
                widget.setEnabled(enabled)

    def auto_configure(self) -> None:
        """
        Автоматическая настройка параметров Kangaroo с определением реальных GPU.
        🛠 ИСПРАВЛЕНИЕ: Интеграция с gpu_auto_config.py
        """
        try:
            # 🛠 1. Импортируем функцию автоконфигурации
            from ui.gpu_auto_config import auto_configure_kangaroo

            # 🛠 2. Вызываем с передачей main_window
            result = auto_configure_kangaroo(self.main_window)

            # 🛠 3. Обрабатываем результат
            if result:
                self.main_window.append_log(
                    f"✅ Параметры применены: "
                    f"Grid={result['grid_params']}, "
                    f"DP={result['dp']}, "
                    f"Subrange={result['subrange_bits']} бит, "
                    f"GPU={result['gpu_count']}",
                    "success"
                )
            else:
                # Если автоконфиг вернул None — fallback на дефолты
                self._apply_default_config()

        except ImportError as e:
            logger.warning(f"Модуль gpu_auto_config не найден: {e}")
            self._apply_default_config()
            self.main_window.append_log(
                "⚠️ Использованы параметры по умолчанию (модуль автоконфига недоступен)",
                "warning"
            )
        except Exception as e:
            logger.exception("Ошибка автонастройки Kangaroo")
            QMessageBox.critical(
                self.main_window, "Ошибка",
                f"Не удалось выполнить автонастройку:\n{type(e).__name__}: {str(e)}"
            )
            self._apply_default_config()

    def _apply_default_config(self) -> None:
        """🛠 Вспомогательный метод: применение параметров по умолчанию"""
        self.main_window.kang_dp_spin.setValue(KANGAROO_CONFIG.DEFAULT_DP)
        self.main_window.kang_subrange_spin.setValue(KANGAROO_CONFIG.DEFAULT_SUBRANGE_BITS)
        self.main_window.kang_duration_spin.setValue(KANGAROO_CONFIG.DEFAULT_DURATION_SEC)
        self.main_window.append_log(
            f"⚙️ Параметры сброшены к дефолту: "
            f"DP={KANGAROO_CONFIG.DEFAULT_DP}, "
            f"2^{KANGAROO_CONFIG.DEFAULT_SUBRANGE_BITS}, "
            f"{KANGAROO_CONFIG.DEFAULT_DURATION_SEC // 60}min",
            "info"
        )


# 🛠 УЛУЧШЕНИЕ 26: Явный экспорт публичного API модуля
__all__ = [
    'KangarooConfig',
    'KANGAROO_CONFIG',
    'BTN_STYLE_RUNNING',
    'BTN_STYLE_STOPPED',
    'STATUS_RUNNING',
    'STATUS_STOPPED',
    'STATUS_COLOR_RUNNING',
    'STATUS_COLOR_STOPPED',
    'KangarooLogic',
]