# ui/gpu_monitor_window.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations

import time
import sys
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout,
    QApplication, QScrollArea, QWidget, QSpinBox, QSizePolicy
)

if TYPE_CHECKING:  # 🛠 УЛУЧШЕНИЕ 2: Избегаем циклических импортов для type hints
    import pynvml  # type: ignore

from ui.theme import apply_dark_theme, set_button_style, COLORS

# 🛠 УЛУЧШЕНИЕ 3: Инициализация логгера в начале модуля
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# 🔧 КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ─────────────────────────────────────────────────────

# 🛠 УЛУЧШЕНИЕ 4: dataclass для конфигурации монитора с типизацией
@dataclass(frozen=True)
class GPUMonitorConfig:
    """Конфигурация параметров окна мониторинга GPU"""
    # Размеры окна
    DEFAULT_WIDTH: int = 850
    DEFAULT_HEIGHT: int = 650
    MIN_WIDTH: int = 720
    MIN_HEIGHT: int = 520
    MAX_WIDTH: int = 1200
    OPTIMAL_WIDTH: int = 780
    OPTIMAL_HEIGHT: int = 580

    # Пороги температуры (°C)
    TEMP_OK: int = 70
    TEMP_WARN: int = 85

    # Порог мощности (%)
    PWR_WARN_PERCENT: int = 80

    # Тайминги
    DEFAULT_REFRESH_SEC: int = 2
    MIN_REFRESH_SEC: int = 1
    MAX_REFRESH_SEC: int = 10

    # Демо-режим параметры
    DEMO_GPU_COUNT: int = 4
    DEMO_TEMP_MIN: int = 45
    DEMO_TEMP_MAX: int = 40  # добавляется к MIN
    DEMO_MEM_TOTAL_MB: int = 12288
    DEMO_MEM_MIN_USAGE: float = 0.3
    DEMO_MEM_MAX_USAGE: float = 0.6
    DEMO_PWR_LIMIT_W: float = 350.0
    DEMO_PWR_MIN_USAGE: float = 0.2
    DEMO_PWR_MAX_USAGE: float = 0.75
    DEMO_UTIL_MIN: int = 10
    DEMO_UTIL_MAX: int = 100

    # Форматирование
    FONT_SIZE_VALUE: int = 10
    FONT_SIZE_LABEL: int = 9
    FONT_BOLD_TEMP: bool = True


# 🛠 УЛУЧШЕНИЕ 5: Глобальный экземпляр конфигурации
MONITOR_CONFIG: GPUMonitorConfig = GPUMonitorConfig()

# ─────────────────────────────────────────────────────
# 🔒 БЕЗОПАСНЫЙ ЛЕНИВЫЙ ИМПОРТ PYNVML
# ─────────────────────────────────────────────────────

# 🛠 УЛУЧШЕНИЕ 6: Явные аннотации для глобальных переменных
_pynvml: Optional[Any] = None  # type: ignore
HAS_PYNVML: bool = False


def _safe_import_pynvml() -> bool:
    """
    Импортирует pynvml только при первом вызове.

    :return: True если импорт успешен, False иначе
    """
    global _pynvml, HAS_PYNVML
    if HAS_PYNVML or _pynvml is not None:
        return HAS_PYNVML
    try:
        import pynvml as _p  # type: ignore
        _pynvml = _p
        HAS_PYNVML = True
        return True
    except ImportError:
        logger.debug("pynvml не установлен, включён демо-режим")
        return False
    except Exception as e:
        logger.warning(f"Ошибка импорта pynvml: {e}", exc_info=True)
        return False


class GPUMonitorWindow(QDialog):
    """
    Окно мониторинга GPU с защитой от крашей и демо-режимом.

    🛠 УЛУЧШЕНИЕ 7: Атрибуты класса с аннотациями типов
    """

    # 🛠 УЛУЧШЕНИЕ 8: Явные аннотации атрибутов
    gpu_handles: List[Any]  # type: ignore
    gpu_cards: List[Dict[str, Any]]
    is_monitoring: bool
    demo_mode: bool
    timer: QTimer
    gpu_container: QWidget
    gpu_layout: QVBoxLayout
    total_power_label: QLabel
    refresh_spin: QSpinBox
    toggle_btn: QPushButton

    # Пороги (для совместимости с оригинальным кодом)
    TEMP_OK: int = MONITOR_CONFIG.TEMP_OK
    TEMP_WARN: int = MONITOR_CONFIG.TEMP_WARN
    PWR_WARN_PERCENT: int = MONITOR_CONFIG.PWR_WARN_PERCENT

    def __init__(self, parent: Optional[QDialog] = None):  # 🛠 УЛУЧШЕНИЕ 9: Type hint для parent
        """
        Инициализация окна мониторинга GPU.

        :param parent: Родительское окно (опционально)
        """
        super().__init__(parent)
        self.setWindowTitle("🖥️ GPU Monitor Pro")
        self.resize(MONITOR_CONFIG.DEFAULT_WIDTH, MONITOR_CONFIG.DEFAULT_HEIGHT)
        self.setMinimumSize(MONITOR_CONFIG.MIN_WIDTH, MONITOR_CONFIG.MIN_HEIGHT)

        apply_dark_theme(self)

        self.gpu_handles = []
        self.gpu_cards = []
        self.is_monitoring = True
        self.demo_mode = False
        self.timer = QTimer()

        # Сначала инициализируем железо, потом UI
        self._init_nvml()
        self._init_ui()
        self._start_timer()

    # ─────────────────────────────────────────────────────
    # 🔧 ИНИЦИАЛИЗАЦИЯ
    # ─────────────────────────────────────────────────────

    def _init_nvml(self) -> None:  # 🛠 УЛУЧШЕНИЕ 10: Явный возврат None
        """Безопасная инициализация NVML с обработкой всех возможных ошибок."""
        if not _safe_import_pynvml():
            self.demo_mode = True
            logger.info("NVML не доступен, включён демо-режим")
            return

        try:
            _pynvml.nvmlInit()  # type: ignore
            count = _pynvml.nvmlDeviceGetCount()  # type: ignore
            for i in range(count):
                handle = _pynvml.nvmlDeviceGetHandleByIndex(i)  # type: ignore
                self.gpu_handles.append(handle)
            logger.info(f"Обнаружено {count} GPU устройств")
        except _pynvml.NVMLError_LibraryNotFound:  # type: ignore
            logger.warning("NVML библиотека не найдена, включён демо-режим")
            self.demo_mode = True
        except _pynvml.NVMLError_DriverNotLoaded:  # type: ignore
            logger.warning("NVML драйвер не загружен, включён демо-режим")
            self.demo_mode = True
        except Exception as e:
            logger.warning(f"Ошибка инициализации NVML: {e}", exc_info=True)
            self.demo_mode = True

    def _init_ui(self) -> None:
        """Инициализация пользовательского интерфейса."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Заголовок
        header = QLabel("🖥️ Мониторинг видеокарт (температура + энергопотребление)")
        header.setProperty("cssClass", "header")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        info = QLabel(
            f"📊 Автообновление: каждые {MONITOR_CONFIG.DEFAULT_REFRESH_SEC} сек | "
            f"Режим: {'🧪 Демо' if self.demo_mode else '🟢 Live'}"
        )
        info.setWordWrap(True)
        # 🛠 УЛУЧШЕНИЕ 11: Безопасный доступ к COLORS с .get()
        info.setStyleSheet(f"color: {COLORS.get('text_secondary', '#B0B0C0')}; font-size: 9pt; padding: 4px;")
        main_layout.addWidget(info)

        # Область карточек GPU (растягивается на всё доступное место)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.gpu_container = QWidget()
        self.gpu_layout = QVBoxLayout(self.gpu_container)
        self.gpu_layout.setContentsMargins(5, 5, 5, 5)
        self.gpu_layout.setSpacing(8)
        scroll.setWidget(self.gpu_container)
        main_layout.addWidget(scroll, 1)  # 1 = забирает всё свободное пространство

        self._build_gpu_cards()

        # Сводка и управление
        summary_group = QGroupBox("📈 Сводка и управление")
        summary_layout = QGridLayout(summary_group)
        summary_layout.setSpacing(8)

        summary_layout.addWidget(QLabel("⚡ Общее потребление:"), 0, 0)
        self.total_power_label = QLabel("0.0 W")
        self.total_power_label.setFont(QFont("Consolas", MONITOR_CONFIG.FONT_SIZE_VALUE, QFont.Bold))
        # 🛠 УЛУЧШЕНИЕ 12: Безопасный доступ к цветам
        self.total_power_label.setStyleSheet(f"color: {COLORS.get('accent_primary', '#5B8CFF')};")
        summary_layout.addWidget(self.total_power_label, 0, 1)

        summary_layout.addWidget(QLabel("🔄 Интервал (сек):"), 1, 0)
        self.refresh_spin = QSpinBox()
        # 🛠 УЛУЧШЕНИЕ 13: Использование констант для диапазона
        self.refresh_spin.setRange(MONITOR_CONFIG.MIN_REFRESH_SEC, MONITOR_CONFIG.MAX_REFRESH_SEC)
        self.refresh_spin.setValue(MONITOR_CONFIG.DEFAULT_REFRESH_SEC)
        self.refresh_spin.valueChanged.connect(self._restart_timer)
        self.refresh_spin.setFixedWidth(65)
        summary_layout.addWidget(self.refresh_spin, 1, 1)

        self.toggle_btn = QPushButton("⏸ Остановить")
        self.toggle_btn.setFixedWidth(130)
        self.toggle_btn.clicked.connect(self._toggle_monitoring)
        summary_layout.addWidget(self.toggle_btn, 2, 0, 1, 2, Qt.AlignCenter)

        main_layout.addWidget(summary_group)

        # Кнопка закрытия
        close_btn = QPushButton("✖ Закрыть")
        set_button_style(close_btn, "danger")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        # Оптимальные размеры окна
        self.resize(MONITOR_CONFIG.OPTIMAL_WIDTH, MONITOR_CONFIG.OPTIMAL_HEIGHT)
        self.setMinimumSize(MONITOR_CONFIG.MIN_WIDTH, MONITOR_CONFIG.MIN_HEIGHT)
        self.setMaximumWidth(MONITOR_CONFIG.MAX_WIDTH)

    # ─────────────────────────────────────────────────────
    # 🔧 СОЗДАНИЕ КАРТОЧЕК GPU
    # ─────────────────────────────────────────────────────

    def _build_gpu_cards(self) -> None:
        """Создание карточек для каждого GPU."""
        # 🛠 УЛУЧШЕНИЕ 14: Безопасная очистка лейаута
        while self.gpu_layout.count():
            item = self.gpu_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.gpu_cards.clear()

        count = len(self.gpu_handles) if not self.demo_mode else MONITOR_CONFIG.DEMO_GPU_COUNT
        for idx in range(count):
            card = self._create_gpu_card(idx)
            self.gpu_cards.append(card)
            self.gpu_layout.addWidget(card['group'])
        self.gpu_layout.addStretch()

    def _create_gpu_card(self, idx: int) -> Dict[str, Any]:
        """
        Создание карточки для одного GPU.

        :param idx: Индекс GPU (0-based)
        :return: Словарь с группой виджетов и лейблами
        """
        group = QGroupBox(f"🎮 GPU #{idx + 1}")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        lbls = ["🔹 Модель:", "🌡️ Temp:", "🔌 Power:", "💾 Memory:", "⚙️ Load:", "📊 Status:"]
        labels: Dict[str, QLabel] = {}
        row = 0
        for txt in lbls:
            lb = QLabel(txt)
            # 🛠 УЛУЧШЕНИЕ 15: Использование констант для размеров шрифта
            font_size = MONITOR_CONFIG.FONT_SIZE_VALUE if "Temp" in txt or "Status" in txt else MONITOR_CONFIG.FONT_SIZE_LABEL
            font_bold = MONITOR_CONFIG.FONT_BOLD_TEMP if "Temp" in txt else False
            val = QLabel("--")
            val.setFont(QFont("Consolas", font_size, QFont.Bold if font_bold else QFont.Normal))
            grid.addWidget(lb, row, 0)
            grid.addWidget(val, row, 1)
            labels[txt] = val
            row += 1

        return {'group': group, 'labels': labels}

    # ─────────────────────────────────────────────────────
    # 🔧 УПРАВЛЕНИЕ ТАЙМЕРОМ
    # ─────────────────────────────────────────────────────

    def _start_timer(self) -> None:
        """Запуск таймера обновления метрик."""
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(self.refresh_spin.value() * 1000)

    def _restart_timer(self, value: int) -> None:
        """
        Перезапуск таймера с новым интервалом.

        :param value: Новый интервал в секундах
        """
        if self.timer.isActive():
            self.timer.stop()
        self.timer.start(value * 1000)

    def _toggle_monitoring(self) -> None:
        """Переключение состояния мониторинга (старт/стоп)."""
        if self.is_monitoring:
            self.timer.stop()
            self.toggle_btn.setText("▶ Запустить")
            set_button_style(self.toggle_btn, "success")
        else:
            self.timer.start(self.refresh_spin.value() * 1000)
            self.toggle_btn.setText("⏸ Остановить")
            set_button_style(self.toggle_btn, "warning")
        self.is_monitoring = not self.is_monitoring

    # ─────────────────────────────────────────────────────
    # 🔧 ОБНОВЛЕНИЕ МЕТРИК
    # ─────────────────────────────────────────────────────

    def _update_metrics(self) -> None:
        """Обновление отображаемых метрик для всех GPU."""
        total_power = 0.0

        for idx, card in enumerate(self.gpu_cards):
            try:
                if self.demo_mode:
                    metrics = self._get_demo_metrics(idx)
                else:
                    metrics = self._get_live_metrics(idx)

                self._update_card_display(card, metrics)
                total_power += metrics['power_used']

            except Exception as e:
                logger.debug(f"Ошибка обновления метрик для GPU #{idx}: {e}")
                self._show_card_error(card)

        # Обновление общей мощности
        self._update_total_power_display(total_power)

    def _get_demo_metrics(self, idx: int) -> Dict[str, Any]:
        """
        Генерация демо-метрик для режима без NVML.

        :param idx: Индекс демо-устройства
        :return: Словарь с метриками
        """
        import random  # 🛠 УЛУЧШЕНИЕ 16: Локальный импорт, так как используется только здесь

        return {
            'name': f"Demo GPU #{idx + 1}",
            'temp': MONITOR_CONFIG.DEMO_TEMP_MIN + random.randint(0, MONITOR_CONFIG.DEMO_TEMP_MAX),
            'power_limit': MONITOR_CONFIG.DEMO_PWR_LIMIT_W,
            'power_used': MONITOR_CONFIG.DEMO_PWR_LIMIT_W * (
                    MONITOR_CONFIG.DEMO_PWR_MIN_USAGE + random.random() * MONITOR_CONFIG.DEMO_PWR_MAX_USAGE
            ),
            'mem_total': MONITOR_CONFIG.DEMO_MEM_TOTAL_MB,
            'mem_used': int(MONITOR_CONFIG.DEMO_MEM_TOTAL_MB * (
                    MONITOR_CONFIG.DEMO_MEM_MIN_USAGE + random.random() * MONITOR_CONFIG.DEMO_MEM_MAX_USAGE
            )),
            'util': random.randint(MONITOR_CONFIG.DEMO_UTIL_MIN, MONITOR_CONFIG.DEMO_UTIL_MAX)
        }

    def _get_live_metrics(self, idx: int) -> Dict[str, Any]:
        """
        Получение реальных метрик через NVML.

        :param idx: Индекс GPU устройства
        :return: Словарь с метриками
        :raises: Исключения pynvml при ошибке доступа
        """
        if not _pynvml or idx >= len(self.gpu_handles):
            raise RuntimeError("NVML не инициализирован или неверный индекс")

        handle = self.gpu_handles[idx]

        # Получение имени устройства
        name_raw = _pynvml.nvmlDeviceGetName(handle)
        name = name_raw.decode('utf-8') if isinstance(name_raw, bytes) else name_raw

        # Получение метрик
        temp = _pynvml.nvmlDeviceGetTemperature(handle, _pynvml.NVML_TEMPERATURE_GPU)
        pwr_used = _pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
        pwr_limit = _pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0

        mem_info = _pynvml.nvmlDeviceGetMemoryInfo(handle)
        mem_total = mem_info.total // 1048576  # Конвертация в МиБ
        mem_used = mem_info.used // 1048576

        util_info = _pynvml.nvmlDeviceGetUtilizationRates(handle)
        util = util_info.gpu

        return {
            'name': name,
            'temp': temp,
            'power_limit': pwr_limit,
            'power_used': pwr_used,
            'mem_total': mem_total,
            'mem_used': mem_used,
            'util': util
        }

    def _update_card_display(self, card: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        """
        Обновление отображения карточки с новыми метриками.

        :param card: Словарь карточки с лейблами
        :param metrics: Словарь с новыми метриками
        """
        labels = card['labels']

        # Обновление текстовых значений
        labels['🔹 Модель:'].setText(metrics['name'])
        labels['🌡️ Temp:'].setText(f"{metrics['temp']}°C")
        labels['🔌 Power:'].setText(f"{metrics['power_used']:.1f} / {metrics['power_limit']:.0f} W")
        labels['💾 Memory:'].setText(f"{metrics['mem_used']} / {metrics['mem_total']} MiB")
        labels['⚙️ Load:'].setText(f"{metrics['util']}%")

        # 🛠 УЛУЧШЕНИЕ 17: Вынесена логика определения статуса температуры
        temp_color, status_text, status_color = self._get_temp_status(metrics['temp'])

        labels['🌡️ Temp:'].setStyleSheet(f"color: {temp_color}; font-weight: bold;")
        labels['📊 Status:'].setText(status_text)
        labels['📊 Status:'].setStyleSheet(f"color: {status_color};")

    def _get_temp_status(self, temp: int) -> tuple:
        """
        Определение цветового статуса по температуре.

        :param temp: Температура в градусах Цельсия
        :return: Кортеж (цвет_температуры, текст_статуса, цвет_статуса)
        """
        if temp < self.TEMP_OK:
            return COLORS.get('accent_primary', '#5B8CFF'), "✅ Норма", COLORS.get('accent_primary', '#5B8CFF')
        elif temp < self.TEMP_WARN:
            return COLORS.get('accent_warning', '#F39C12'), "⚠️ Нагрев", COLORS.get('accent_warning', '#F39C12')
        else:
            return COLORS.get('accent_danger', '#E74C3C'), "🔥 Критично", COLORS.get('accent_danger', '#E74C3C')

    def _show_card_error(self, card: Dict[str, Any]) -> None:
        """
        Отображение ошибки в карточке GPU.

        :param card: Словарь карточки с лейблами
        """
        card['labels']['📊 Status:'].setText("❌ Ошибка")
        card['labels']['📊 Status:'].setStyleSheet(
            f"color: {COLORS.get('accent_danger', '#E74C3C')};"
        )

    def _update_total_power_display(self, total_power: float) -> None:
        """
        Обновление отображения общего энергопотребления.

        :param total_power: Суммарная мощность в ваттах
        """
        self.total_power_label.setText(f"{total_power:.1f} W")

        # 🛠 УЛУЧШЕНИЕ 18: Использование константы для порога мощности
        warn_threshold = 800.0  # Можно вынести в конфиг при необходимости
        color = COLORS.get('accent_warning', '#F39C12') if total_power > warn_threshold else COLORS.get(
            'accent_primary', '#5B8CFF')
        self.total_power_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )

    # ─────────────────────────────────────────────────────
    # 🔧 ЗАКРЫТИЕ ОКНА
    # ─────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # 🛠 УЛУЧШЕНИЕ 19: Явный тип для event
        """
        Обработчик закрытия окна с очисткой ресурсов.

        :param event: Событие закрытия
        """
        self.timer.stop()

        # 🛠 УЛУЧШЕНИЕ 20: Безопасное завершение NVML
        if not self.demo_mode and _pynvml:
            try:
                _pynvml.nvmlShutdown()
                logger.debug("NVML корректно завершён")
            except Exception as e:
                logger.warning(f"Ошибка при завершении NVML: {e}")

        # Уведомляем родительское окно, что объект удален
        parent = self.parent()
        if parent and hasattr(parent, 'gpu_monitor_window'):
            try:
                parent.gpu_monitor_window = None
            except RuntimeError:
                # Объект родителя уже удалён
                pass

        super().closeEvent(event)


# 🛠 УЛУЧШЕНИЕ 21: Явный экспорт публичного API модуля
__all__ = [
    'GPUMonitorConfig',
    'MONITOR_CONFIG',
    'GPUMonitorWindow',
]