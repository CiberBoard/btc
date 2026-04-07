# ui/gpu_monitor_window.py
import time
import sys
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout,
    QApplication, QScrollArea, QWidget, QSpinBox, QSizePolicy
)
from ui.theme import apply_dark_theme, set_button_style, COLORS

# ─────────────────────────────────────────────────────
# 🔒 БЕЗОПАСНЫЙ ЛЕНИВЫЙ ИМПОРТ PYNVML
# ─────────────────────────────────────────────────────
_pynvml = None
HAS_PYNVML = False


def _safe_import_pynvml():
    """Импортирует pynvml только при первом вызове"""
    global _pynvml, HAS_PYNVML
    if HAS_PYNVML or _pynvml is not None:
        return True
    try:
        import pynvml as _p
        _pynvml = _p
        HAS_PYNVML = True
        return True
    except Exception:
        return False


class GPUMonitorWindow(QDialog):
    """Окно мониторинга GPU с защитой от крашей и демо-режимом"""
    TEMP_OK = 70
    TEMP_WARN = 85
    PWR_WARN_PERCENT = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖥️ GPU Monitor Pro")
        self.resize(850, 650)
        self.setMinimumSize(720, 520)

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
    def _init_nvml(self):
        """Безопасная инициализация NVML"""
        if not _safe_import_pynvml():
            self.demo_mode = True
            return

        try:
            _pynvml.nvmlInit()
            count = _pynvml.nvmlDeviceGetCount()
            for i in range(count):
                self.gpu_handles.append(_pynvml.nvmlDeviceGetHandleByIndex(i))
        except _pynvml.NVMLError_LibraryNotFound:
            self.demo_mode = True
        except _pynvml.NVMLError_DriverNotLoaded:
            self.demo_mode = True
        except Exception as e:
            self.demo_mode = True

    # ─────────────────────────────────────────────────────
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Заголовок
        header = QLabel("🖥️ Мониторинг видеокарт (температура + энергопотребление)")
        header.setProperty("cssClass", "header")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        info = QLabel(
            f"📊 Автообновление: каждые 2 сек | "
            f"Режим: {'🧪 Демо' if self.demo_mode else '🟢 Live'}"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 9pt; padding: 4px;")
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
        self.total_power_label.setFont(QFont("Consolas", 11, QFont.Bold))
        self.total_power_label.setStyleSheet(f"color: {COLORS['accent_primary']};")
        summary_layout.addWidget(self.total_power_label, 0, 1)

        summary_layout.addWidget(QLabel("🔄 Интервал (сек):"), 1, 0)
        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(1, 10)
        self.refresh_spin.setValue(2)
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
        self.resize(780, 580)
        self.setMinimumSize(620, 420)
        self.setMaximumWidth(1200)

    # ─────────────────────────────────────────────────────
    def _build_gpu_cards(self):
        for i in reversed(range(self.gpu_layout.count())):
            self.gpu_layout.itemAt(i).widget().setParent(None)
        self.gpu_cards.clear()

        count = len(self.gpu_handles) if not self.demo_mode else 4
        for idx in range(count):
            card = self._create_gpu_card(idx)
            self.gpu_cards.append(card)
            self.gpu_layout.addWidget(card['group'])
        self.gpu_layout.addStretch()

    def _create_gpu_card(self, idx: int) -> dict:
        group = QGroupBox(f"🎮 GPU #{idx + 1}")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        lbls = ["🔹 Модель:", "🌡️ Temp:", "🔌 Power:", "💾 Memory:", "⚙️ Load:", "📊 Status:"]
        self.labels = {}
        row = 0
        for txt in lbls:
            lb = QLabel(txt)
            val = QLabel("--")
            val.setFont(QFont("Consolas", 10 if "Temp" in txt or "Status" in txt else 9,
                              QFont.Bold if "Temp" in txt else QFont.Normal))
            grid.addWidget(lb, row, 0)
            grid.addWidget(val, row, 1)
            self.labels[txt] = val
            row += 1

        return {'group': group, 'labels': self.labels}

    # ─────────────────────────────────────────────────────
    def _start_timer(self):
        self.timer.timeout.connect(self._update_metrics)
        self.timer.start(self.refresh_spin.value() * 1000)

    def _restart_timer(self, value: int):
        if self.timer.isActive(): self.timer.stop()
        self.timer.start(value * 1000)

    def _toggle_monitoring(self):
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
    def _update_metrics(self):
        total_power = 0.0
        for idx, card in enumerate(self.gpu_cards):
            try:
                if self.demo_mode:
                    import random
                    name = f"Demo GPU #{idx + 1}"
                    temp = 45 + random.randint(0, 40)
                    pwr_limit, pwr_used = 350.0, 350.0 * (0.2 + random.random() * 0.75)
                    mem_total, mem_used = 12288, int(12288 * (0.3 + random.random() * 0.6))
                    util = random.randint(10, 100)
                else:
                    handle = self.gpu_handles[idx]
                    name_raw = _pynvml.nvmlDeviceGetName(handle)
                    name = name_raw.decode('utf-8') if isinstance(name_raw, bytes) else name_raw

                    temp = _pynvml.nvmlDeviceGetTemperature(handle, _pynvml.NVML_TEMPERATURE_GPU)
                    pwr_used = _pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    pwr_limit = _pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0
                    mem_info = _pynvml.nvmlDeviceGetMemoryInfo(handle)
                    mem_total = mem_info.total // 1048576
                    mem_used = mem_info.used // 1048576
                    util_info = _pynvml.nvmlDeviceGetUtilizationRates(handle)
                    util = util_info.gpu

                # Обновляем UI
                card['labels']['🔹 Модель:'].setText(name)
                card['labels']['🌡️ Temp:'].setText(f"{temp}°C")
                card['labels']['🔌 Power:'].setText(f"{pwr_used:.1f} / {pwr_limit:.0f} W")
                card['labels']['💾 Memory:'].setText(f"{mem_used} / {mem_total} MiB")
                card['labels']['⚙️ Load:'].setText(f"{util}%")

                # Цвета температуры
                if temp < self.TEMP_OK:
                    card['labels']['🌡️ Temp:'].setStyleSheet(f"color: {COLORS['accent_primary']}; font-weight: bold;")
                    status, status_color = "✅ Норма", COLORS['accent_primary']
                elif temp < self.TEMP_WARN:
                    card['labels']['🌡️ Temp:'].setStyleSheet(f"color: {COLORS['accent_warning']}; font-weight: bold;")
                    status, status_color = "⚠️ Нагрев", COLORS['accent_warning']
                else:
                    card['labels']['🌡️ Temp:'].setStyleSheet(f"color: {COLORS['accent_danger']}; font-weight: bold;")
                    status, status_color = "🔥 Критично", COLORS['accent_danger']

                card['labels']['📊 Status:'].setText(status)
                card['labels']['📊 Status:'].setStyleSheet(f"color: {status_color};")
                total_power += pwr_used

            except Exception:
                card['labels']['📊 Status:'].setText("❌ Ошибка")
                card['labels']['📊 Status:'].setStyleSheet(f"color: {COLORS['accent_danger']};")

        self.total_power_label.setText(f"{total_power:.1f} W")
        self.total_power_label.setStyleSheet(
            f"color: {COLORS['accent_warning'] if total_power > 800 else COLORS['accent_primary']}; font-weight: bold;"
        )

    def closeEvent(self, event):
        self.timer.stop()
        if not self.demo_mode and _pynvml:
            try:
                _pynvml.nvmlShutdown()
            except:
                pass

        # Уведомляем родительское окно, что объект удален
        if self.parent() and hasattr(self.parent(), 'gpu_monitor_window'):
            self.parent().gpu_monitor_window = None

        super().closeEvent(event)