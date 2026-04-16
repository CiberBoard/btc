# ui/matrix_window.py
from __future__ import annotations

import time
import logging
import multiprocessing
import queue
from typing import TYPE_CHECKING, Optional, Dict, Any, List

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRegularExpression, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QRegularExpressionValidator, QColor, QPalette
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout, QMessageBox,
    QTabWidget, QWidget, QSpinBox, QComboBox, QProgressBar,
    QSlider, QCheckBox, QFrame, QScrollArea
)

from core.matrix_logic import MatrixConverter, COINCURVE_AVAILABLE, MatrixConfig

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner
    from core.matrix_logic import MatrixLogic

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🎨 Визуализатор триплетов (новый виджет)
# ═══════════════════════════════════════════════

class TripletVisualizer(QWidget):
    """Виджет для визуального отображения текущих триплетов с подсветкой изменений"""

    def __init__(self, parent=None, max_display: int = 86):
        super().__init__(parent)
        self.max_display = max_display  # 256 бит / 3 ≈ 86 триплетов
        self.labels: List[QLabel] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Скролл для длинных последовательностей
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.setSpacing(1)

        for i in range(self.max_display):
            lbl = QLabel("A")
            lbl.setFont(QFont("Consolas", 7))
            lbl.setFixedWidth(11)
            lbl.setFixedHeight(18)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background: #2c3e50; color: #ecf0f1; border-radius: 2px;")
            self.labels.append(lbl)
            container_layout.addWidget(lbl)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Легенда
        legend = QLabel("<small>🟢 неизм. 🔴 изменено 🟡 новый</small>")
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(legend)

    def update_triplets(self, triplet_str: str, changed_positions: Optional[List[int]] = None,
                        is_new: bool = False):
        """Обновляет отображение с подсветкой изменений"""
        for i, (lbl, char) in enumerate(zip(self.labels, triplet_str[:self.max_display])):
            lbl.setText(char)

            if changed_positions and i in changed_positions:
                # 🔴 Изменённый символ
                lbl.setStyleSheet("background: #e74c3c; color: white; font-weight: bold; border-radius: 2px;")
                # Анимация возврата
                QTimer.singleShot(300, lambda l=lbl: self._reset_style(l))
            elif is_new:
                # 🟡 Новый триплет
                lbl.setStyleSheet("background: #f39c12; color: white; border-radius: 2px;")
                QTimer.singleShot(500, lambda l=lbl: self._reset_style(l))
            else:
                # 🟢 Нормальное состояние
                self._reset_style(lbl)

    def _reset_style(self, label: QLabel):
        label.setStyleSheet("background: #2c3e50; color: #ecf0f1; border-radius: 2px;")

    def clear(self):
        for lbl in self.labels:
            lbl.setText("A")
            self._reset_style(lbl)


# ═══════════════════════════════════════════════
# 📊 Виджет статистики мутаций
# ═══════════════════════════════════════════════

class MutationStatsWidget(QGroupBox):
    """Отображает статистику эффективности мутаций"""

    def __init__(self, parent=None):
        super().__init__("📈 Статистика мутаций", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QGridLayout(self)

        self.in_range_label = QLabel("В диапазоне: —")
        self.fallback_label = QLabel("Fallback'и: —")
        self.avg_changed_label = QLabel("Симв./мутация: —")
        self.total_ops_label = QLabel("Операций: 0")

        layout.addWidget(QLabel("🎯 Точность:"), 0, 0)
        layout.addWidget(self.in_range_label, 0, 1)
        layout.addWidget(QLabel("🔄 Откаты:"), 1, 0)
        layout.addWidget(self.fallback_label, 1, 1)
        layout.addWidget(QLabel("✏️ Изменений:"), 2, 0)
        layout.addWidget(self.avg_changed_label, 2, 1)
        layout.addWidget(self.total_ops_label, 3, 0, 1, 2)

        # Прогресс эффективности
        self.efficiency_bar = QProgressBar()
        self.efficiency_bar.setFormat("Эффективность: %p%")
        self.efficiency_bar.setRange(0, 100)
        layout.addWidget(self.efficiency_bar, 4, 0, 1, 2)

    def update_stats(self, stats: Dict[str, Any]):
        """Обновляет отображение статистики"""
        self.in_range_label.setText(f"{stats.get('in_range_rate', '—')}")
        self.fallback_label.setText(f"{stats.get('fallback_rate', '—')}")
        self.avg_changed_label.setText(stats.get('avg_chars_changed', '—'))
        self.total_ops_label.setText(f"Операций: {stats.get('total_operations', 0):,}")

        # Рассчитываем эффективность
        try:
            efficiency = float(stats.get('in_range_rate', '0%').rstrip('%'))
            self.efficiency_bar.setValue(int(efficiency))

            # Цветовая индикация
            if efficiency >= 80:
                color = "#27ae60"  # зелёный
            elif efficiency >= 50:
                color = "#f39c12"  # жёлтый
            else:
                color = "#e74c3c"  # красный
            self.efficiency_bar.setStyleSheet(f"""
                QProgressBar {{ border: 1px solid grey; border-radius: 3px; text-align: center; }}
                QProgressBar::chunk {{ background: {color}; }}
            """)
        except:
            pass

    def reset(self):
        self.in_range_label.setText("—")
        self.fallback_label.setText("—")
        self.avg_changed_label.setText("—")
        self.total_ops_label.setText("Операций: 0")
        self.efficiency_bar.setValue(0)


# ═══════════════════════════════════════════════
# 🔷 Основное окно
# ═══════════════════════════════════════════════

class MatrixWindow(QDialog):
    """Модальное окно матричного поиска с расширенным управлением"""

    search_started = pyqtSignal()
    search_stopped = pyqtSignal()

    def __init__(self, parent: Optional['BitcoinGPUCPUScanner'] = None):
        try:
            super().__init__(parent)
            self.parent_window = parent
            self._mutation_viz_buffer: List[Dict] = []  # Буфер для визуализаций
            self._setup_ui()
            self._connect_signals()
            self._setup_queue_timer()
        except Exception as e:
            import sys
            print(f"[MatrixWindow] Init error: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            QMessageBox.critical(None, "Ошибка", f"Не удалось создать окно матрицы:\n{e}")
            raise

    def _get_logic(self) -> Optional['MatrixLogic']:
        if self.parent_window is None:
            return None
        return getattr(self.parent_window, 'matrix_logic', None)

    def _setup_ui(self) -> None:
        self.setWindowTitle("🔷 Matrix Search: Triplet Random Curve")
        self.setMinimumSize(950, 850)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # 🏷️ Заголовок
        header = QLabel(
            "🔷 <b>Matrix Search</b><br>"
            "<small>Случайная мутация триплетов с визуализацией и контролем диапазона</small>"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold; padding: 8px; background: #34495e; color: white; border-radius: 5px;")
        main_layout.addWidget(header)

        # 🎯 Цель и диапазон
        target_group = QGroupBox("🎯 Цель и диапазон")
        tg_layout = QGridLayout(target_group)

        tg_layout.addWidget(QLabel("Целевой адрес:"), 0, 0)
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU")
        tg_layout.addWidget(self.target_edit, 0, 1, 1, 3)

        tg_layout.addWidget(QLabel("Начало (HEX):"), 1, 0)
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("0000...41D793200092700000")
        self.start_edit.setValidator(QRegularExpressionValidator(
            QRegularExpression("^[0-9a-fA-F]{0,64}$"), self))
        self.start_edit.textChanged.connect(self._on_range_changed)
        tg_layout.addWidget(self.start_edit, 1, 1)

        tg_layout.addWidget(QLabel("Конец (HEX):"), 1, 2)
        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("0000...71D79320ff92700000")
        self.end_edit.setValidator(QRegularExpressionValidator(
            QRegularExpression("^[0-9a-fA-F]{0,64}$"), self))
        self.end_edit.textChanged.connect(self._on_range_changed)
        tg_layout.addWidget(self.end_edit, 1, 3)

        self.range_info_label = QLabel("<small>Диапазон: —</small>")
        self.range_info_label.setWordWrap(True)
        tg_layout.addWidget(self.range_info_label, 2, 0, 1, 4)
        main_layout.addWidget(target_group)

        # ⚙️ Параметры
        params_group = QGroupBox("⚙️ Параметры поиска")
        pg_layout = QGridLayout(params_group)

        pg_layout.addWidget(QLabel("Воркеры:"), 0, 0)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(4)
        pg_layout.addWidget(self.workers_spin, 0, 1)

        pg_layout.addWidget(QLabel("Режим:"), 0, 2)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "random_curve — мутация + случайные прыжки",
            "random_full — полностью случайные"
        ])
        self.mode_combo.setCurrentIndex(0)
        pg_layout.addWidget(self.mode_combo, 0, 3)

        pg_layout.addWidget(QLabel("Сила мутации:"), 1, 0)
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(1, 50)
        self.strength_slider.setValue(15)
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        pg_layout.addWidget(self.strength_slider, 1, 1)
        self.strength_value_label = QLabel("15%")
        self.strength_value_label.setFixedWidth(40)
        pg_layout.addWidget(self.strength_value_label, 1, 2)

        pg_layout.addWidget(QLabel("Шанс мутации:"), 2, 0)
        self.prob_slider = QSlider(Qt.Orientation.Horizontal)
        self.prob_slider.setRange(0, 100)
        self.prob_slider.setValue(70)
        self.prob_slider.valueChanged.connect(self._on_prob_changed)
        pg_layout.addWidget(self.prob_slider, 2, 1)
        self.prob_value_label = QLabel("70%")
        self.prob_value_label.setFixedWidth(40)
        pg_layout.addWidget(self.prob_value_label, 2, 2)

        pg_layout.addWidget(QLabel("Обновлять базу:"), 3, 0)
        self.base_update_spin = QSpinBox()
        self.base_update_spin.setRange(0, 10000)
        self.base_update_spin.setValue(1000)
        self.base_update_spin.setSuffix(" итераций")
        self.base_update_spin.setSpecialValueText("Никогда")
        pg_layout.addWidget(self.base_update_spin, 3, 1, 1, 3)

        self.viz_checkbox = QCheckBox("🎨 Визуализировать мутации в логе")
        self.viz_checkbox.setChecked(False)
        pg_layout.addWidget(self.viz_checkbox, 4, 0, 1, 4)
        main_layout.addWidget(params_group)

        # 🔤 Визуализация триплетов
        triplet_group = QGroupBox("🔤 Визуализатор триплетов")
        triplet_layout = QVBoxLayout(triplet_group)

        demo_layout = QHBoxLayout()
        demo_layout.addWidget(QLabel("HEX → триплеты:"))
        self.demo_hex = QLineEdit("000000000000000000000000000000000000000000000041D793200092700000")
        self.demo_hex.setReadOnly(True)
        demo_layout.addWidget(self.demo_hex)
        convert_btn = QPushButton("➡️")
        convert_btn.setFixedWidth(40)
        convert_btn.clicked.connect(self._on_demo_convert)
        demo_layout.addWidget(convert_btn)
        triplet_layout.addLayout(demo_layout)

        self.triplet_viz = TripletVisualizer()
        triplet_layout.addWidget(self.triplet_viz)

        self.current_triplet_label = QLabel("Ожидание запуска...")
        self.current_triplet_label.setFont(QFont("Consolas", 8))
        self.current_triplet_label.setWordWrap(True)
        triplet_layout.addWidget(self.current_triplet_label)
        main_layout.addWidget(triplet_group)

        # 📈 Статистика мутаций
        self.mutation_stats_widget = MutationStatsWidget()
        main_layout.addWidget(self.mutation_stats_widget)

        # 🎮 Управление
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 Запустить поиск")
        self.start_btn.setStyleSheet("""
            QPushButton { background: #27ae60; color: white; font-weight: bold; padding: 12px; border-radius: 6px; }
            QPushButton:hover { background: #2ecc71; }
            QPushButton:disabled { background: #3a3a45; color: #7f8c8d; }
        """)
        self.start_btn.setMinimumHeight(45)
        self.start_btn.clicked.connect(self._on_start_stop)

        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; font-weight: bold; padding: 12px; border-radius: 6px; }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #3a3a45; color: #7f8c8d; }
        """)
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        main_layout.addLayout(control_layout)

        # 📊 Общая статистика
        stats_group = QGroupBox("📊 Статистика поиска")
        stats_layout = QGridLayout(stats_group)

        self.status_label = QLabel("🟡 Ожидание")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stats_layout.addWidget(self.status_label, 0, 0, 1, 3)

        self.scanned_label = QLabel("Проверено: 0")
        self.found_label = QLabel("Найдено: 0")
        self.speed_label = QLabel("Скорость: 0 keys/s")
        stats_layout.addWidget(self.scanned_label, 1, 0)
        stats_layout.addWidget(self.found_label, 1, 1)
        stats_layout.addWidget(self.speed_label, 1, 2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("🔄 Работает...")
        stats_layout.addWidget(self.progress_bar, 2, 0, 1, 3)
        main_layout.addWidget(stats_group)

        # 📋 Лог — ✅ ИСПРАВЛЕНО: сначала создаём log_output, потом кнопку очистки!
        log_group = QGroupBox("📋 Лог событий")
        log_layout = QVBoxLayout(log_group)

        # ✅ 1. Сначала создаём QTextEdit
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(180)

        # ✅ 2. Теперь можно безопасно подключать кнопку к уже существующему виджету
        filter_layout = QHBoxLayout()
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["Все", "Только мутации", "Только ошибки", "Только находки"])
        self.log_filter_combo.currentTextChanged.connect(self._apply_log_filter)
        filter_layout.addWidget(QLabel("Фильтр:"))
        filter_layout.addWidget(self.log_filter_combo)
        filter_layout.addStretch()

        clear_log_btn = QPushButton("🗑 Очистить")
        clear_log_btn.setFixedWidth(100)
        clear_log_btn.clicked.connect(self.log_output.clear)  # ✅ Теперь log_output уже существует!
        filter_layout.addWidget(clear_log_btn)

        log_layout.addLayout(filter_layout)
        log_layout.addWidget(self.log_output)  # ✅ Добавляем в лейаут после создания
        main_layout.addWidget(log_group)

        # ✅ Результат
        result_group = QGroupBox("✅ Найденный ключ")
        rg_layout = QGridLayout(result_group)

        self.result_address = QLineEdit()
        self.result_address.setReadOnly(True)
        self.result_address.setPlaceholderText("Адрес появится здесь при находке...")
        self.result_address.setStyleSheet("background: #34495e; color: #ecf0f1;")
        rg_layout.addWidget(QLabel("Адрес:"), 0, 0)
        rg_layout.addWidget(self.result_address, 0, 1)

        self.result_hex = QLineEdit()
        self.result_hex.setReadOnly(True)
        self.result_hex.setFont(QFont("Consolas", 8))
        rg_layout.addWidget(QLabel("HEX:"), 1, 0)
        rg_layout.addWidget(self.result_hex, 1, 1)

        self.result_wif = QLineEdit()
        self.result_wif.setReadOnly(True)
        self.result_wif.setFont(QFont("Consolas", 8))
        rg_layout.addWidget(QLabel("WIF:"), 2, 0)
        rg_layout.addWidget(self.result_wif, 2, 1)

        copy_btn = QPushButton("📋 Копировать всё")
        copy_btn.clicked.connect(self._copy_result)
        rg_layout.addWidget(copy_btn, 3, 0, 1, 2)
        main_layout.addWidget(result_group)

        if not COINCURVE_AVAILABLE:
            QMessageBox.warning(self, "Внимание",
                                "⚠️ coincurve не установлен!\nБез него генерация адресов невозможна.\nУстановите: pip install coincurve")

    def _connect_signals(self) -> None:
        logic = self._get_logic()
        if not logic:
            return

        # Безопасное переподключение
        for signal, slot in [
            (logic.update_stats, self._on_stats_update),
            (logic.log_message, self._on_log),
            (logic.key_found, self._on_key_found),
            (logic.worker_finished, self._on_worker_finished),
            (logic.mutation_viz, self._on_mutation_viz),  # 🆕 Новый сигнал
        ]:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
            signal.connect(slot)

    def _setup_queue_timer(self) -> None:
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self._process_queue)
        self.queue_timer.start(100)

    def _process_queue(self) -> None:
        logic = self._get_logic()
        if not logic or not logic.is_running:
            return

        try:
            q = logic.get_queue()
            if q is None:
                return

            while True:
                try:
                    msg = q.get_nowait()
                    msg_type = msg.get('type')

                    if msg_type == 'stats':
                        self._on_stats_update(msg)
                    elif msg_type == 'log':
                        self._on_log(msg['message'], msg.get('level', 'info'))
                    elif msg_type == 'found':
                        self._on_key_found(msg)
                    elif msg_type == 'worker_finished':
                        self._on_worker_finished(msg['worker_id'])
                    elif msg_type == 'mutation_viz':  # 🆕 Обработка визуализации
                        self._on_mutation_viz(msg)
                except queue.Empty:
                    break
                except (EOFError, BrokenPipeError, OSError):
                    break
        except Exception as e:
            logger.debug(f"Queue processing error (safe): {e}")

    # ─────────────────────────────────────────────────────
    # ОБРАБОТЧИКИ СОБЫТИЙ
    # ─────────────────────────────────────────────────────

    def _on_range_changed(self):
        """Обновляет инфо о диапазоне при изменении полей"""
        start = self.start_edit.text().strip()
        end = self.end_edit.text().strip()

        if start and end and len(start) == 64 and len(end) == 64:
            try:
                info = MatrixConverter.get_range_stats(start, end)
                total = info['total_keys']
                if total > 1e12:
                    total_str = f"{total / 1e12:.2f} трлн"
                elif total > 1e9:
                    total_str = f"{total / 1e9:.2f} млрд"
                elif total > 1e6:
                    total_str = f"{total / 1e6:.2f} млн"
                else:
                    total_str = f"{total:,}"

                self.range_info_label.setText(
                    f"<small>📊 Диапазон: {total_str} ключей | "
                    f"Триплетов: {info['total_triplets']}</small>"
                )
            except:
                self.range_info_label.setText("<small>❌ Ошибка расчёта диапазона</small>")
        else:
            self.range_info_label.setText("<small>Диапазон: —</small>")

    def _on_strength_changed(self, value: int):
        """Обработчик изменения силы мутации"""
        percent = value
        self.strength_value_label.setText(f"{percent}%")
        # Обновляем в логике если запущено
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(strength=percent / 100)

    def _on_prob_changed(self, value: int):
        """Обработчик изменения вероятности мутации"""
        percent = value
        self.prob_value_label.setText(f"{percent}%")
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(probability=percent / 100)

    def _on_demo_convert(self) -> None:
        hex_val = self.demo_hex.text().strip()
        if not hex_val or len(hex_val) != 64:
            return
        try:
            triplet_str = MatrixConverter.hex_to_triplets(hex_val)
            self.triplet_display.setText(triplet_str) if hasattr(self, 'triplet_display') else None
            self.triplet_viz.update_triplets(triplet_str, is_new=True)
        except Exception as e:
            logger.warning(f"Ошибка конвертации: {e}")

    def _on_start_stop(self) -> None:
        logic = self._get_logic()
        if not logic:
            QMessageBox.critical(self, "Ошибка", "MatrixLogic не инициализирован")
            return

        target = self.target_edit.text().strip()
        start_hex = self.start_edit.text().strip()
        end_hex = self.end_edit.text().strip()
        workers = self.workers_spin.value()
        mode = "random_curve" if self.mode_combo.currentIndex() == 0 else "random_full"

        if not target or not start_hex or not end_hex:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return

        # 🎛️ Собираем параметры
        mut_strength = self.strength_slider.value() / 100
        mut_prob = self.prob_slider.value() / 100
        base_interval = self.base_update_spin.value()
        do_viz = self.viz_checkbox.isChecked()

        if not logic.start_search(
                target, start_hex, end_hex, workers, mode,
                mutation_strength=mut_strength,
                mutation_probability=mut_prob,
                update_base_interval=base_interval,
                visualize_mutations=do_viz
        ):
            QMessageBox.warning(self, "Ошибка", "Не удалось запустить поиск")
            return

        # UI обновления
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("🟢 Поиск запущен")
        self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 14px;")

        params_summary = (
            f"{workers} воркеров | сила:{mut_strength:.0%} | шанс:{mut_prob:.0%} | "
            f"база:{base_interval}ит | виз:{'✅' if do_viz else '❌'}"
        )
        self.log_output.append(f"🚀 Запуск: {params_summary}")
        self.search_started.emit()

        # Сброс статистики
        self.mutation_stats_widget.reset()

    def _on_stop(self) -> None:
        logic = self._get_logic()
        if logic:
            logic.stop_search()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("🔴 Остановлено")
        self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        self.search_stopped.emit()

    def _on_stats_update(self, stats: Dict[str, Any]) -> None:
        self.scanned_label.setText(f"Проверено: {stats.get('scanned', 0):,}")
        self.found_label.setText(f"Найдено: {stats.get('found', 0)}")
        speed = stats.get('speed', 0)
        self.speed_label.setText(f"Скорость: {speed:,.0f} keys/s")

        # 📈 Обновляем статистику мутаций если есть
        if 'mutation_stats' in stats and stats['mutation_stats']:
            self.mutation_stats_widget.update_stats(stats['mutation_stats'])

    def _on_log(self, message: str, level: str = "info") -> None:
        timestamp = time.strftime('[%H:%M:%S]')

        # Цветовое кодирование по уровню
        if level == "error":
            formatted = f"<span style='color:#e74c3c'>{timestamp} ❌ {message}</span>"
        elif level == "warning":
            formatted = f"<span style='color:#f39c12'>{timestamp} ⚠️ {message}</span>"
        elif "мутация" in message.lower() or "mutation" in message.lower():
            formatted = f"<span style='color:#9b59b6'>{timestamp} 🔀 {message}</span>"
        else:
            formatted = f"{timestamp} {message}"

        self.log_output.append(formatted)

        # Автопрокрутка
        scrollbar = self.log_output.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

        # 🎨 Обработка визуализаций в буфере
        if self._mutation_viz_buffer:
            self._flush_mutation_viz()

    # ✅ СТАЛО:
    def _on_mutation_viz(self, viz_data: Dict[str, Any]) -> None:
        """🆕 Обработка сообщения с визуализацией мутации"""
        self._mutation_viz_buffer.append(viz_data)
        if len(self._mutation_viz_buffer) >= 5:
            self._flush_mutation_viz()

    def _flush_mutation_viz(self):
        """Обработка буфера визуализаций"""
        if not self._mutation_viz_buffer:
            return

        # Берём последнюю (самую свежую) для отображения
        latest = self._mutation_viz_buffer[-1]

        # Обновляем визуализатор
        self.triplet_viz.update_triplets(
            latest.get('visualization', '').replace('🔴', '').replace('🔴', ''),
            changed_positions=None,  # Можно парсить из viz_data если нужно
            is_new=True
        )

        # Обновляем текстовую метку
        prefix = latest.get('new_prefix', '')
        changes = latest.get('changes_count', 0)
        self.current_triplet_label.setText(
            f"Последнее: {prefix}... | Изменено символов: {changes}"
        )

        # Логируем кратко
        if changes > 0:
            self.log_output.append(
                f"<span style='color:#9b59b6'>🔀 Мутация: {changes} изменений</span>"
            )

        self._mutation_viz_buffer.clear()

    def _apply_log_filter(self, filter_text: str):
        """Простая фильтрация лога (можно улучшить)"""
        # Для полноценной фильтрации нужно хранить сообщения отдельно
        # Здесь просто пример — в продакшене лучше использовать модель
        pass

    def _on_key_found(self, key_data: Dict[str, Any]) -> None:
        self.result_address.setText(key_data['address'])
        self.result_hex.setText(key_data['hex_key'])
        self.result_wif.setText(key_data['wif_key'])

        self.result_address.setStyleSheet("background: #27ae60; color: white; font-weight: bold;")

        # 🎉 Анимация успеха
        self.status_label.setText("🎉 КЛЮЧ НАЙДЕН!")
        self.status_label.setStyleSheet("color: #f1c40f; font-weight: bold; font-size: 16px;")

        QMessageBox.information(self, "🎉 Ключ найден!",
                                f"Адрес: {key_data['address']}\n\n"
                                f"HEX: {key_data['hex_key'][:32]}...\n"
                                f"WIF: {key_data['wif_key'][:20]}...")

    def _on_worker_finished(self, worker_id: int) -> None:
        self.log_output.append(f"✅ Воркер {worker_id} завершён")
        logic = self._get_logic()
        if logic and len(logic.processes) == 0 and not logic.is_running:
            self.status_label.setText("🟡 Все воркеры завершены")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def _copy_result(self) -> None:
        from PyQt6.QtWidgets import QApplication
        if not self.result_address.text():
            return
        text = (
            f"Address: {self.result_address.text()}\n"
            f"HEX: {self.result_hex.text()}\n"
            f"WIF: {self.result_wif.text()}"
        )
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Скопировано", "Результат скопирован в буфер обмена")

    def closeEvent(self, event) -> None:
        logic = self._get_logic()
        if logic and logic.is_running:
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Поиск активен. Остановить и закрыть?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            logic.stop_search()
        self.queue_timer.stop()
        event.accept()