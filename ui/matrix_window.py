# ui/matrix_window.py
"""
🔷 Matrix Window v2.4 — УЛУЧШЕННАЯ UI
======================================
PyQt6 интерфейс для Matrix Search Engine с:
- Оптимизированной обработкой событий
- Правильным управлением памятью
- Расширенной визуализацией
- Поддержкой сохранения настроек
- Надёжной обработкой ошибок
"""

from __future__ import annotations
import time
import logging
import queue
import json
import os
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Set

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRegularExpression, QSettings
from PyQt6.QtGui import QFont, QRegularExpressionValidator, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QGridLayout, QMessageBox, QSpinBox, QSlider,
    QScrollArea, QWidget, QProgressBar, QApplication, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QComboBox, QDoubleSpinBox
)

from core.matrix_logic import MatrixConverter, COINCURVE_AVAILABLE, MatrixLogic
# В начале файла, после других импортов:
from utils.settings_manager import get_settings

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🎨 КОМПОНЕНТ: ВИЗУАЛИЗАЦИЯ ТРИПЛЕТОВ
# ═══════════════════════════════════════════════

class TripletDisplay(QWidget):
    """✅ Улучшенное визуальное отображение триплетов с фиксацией"""

    triplet_clicked = pyqtSignal(int)
    triplet_locked = pyqtSignal(int, bool)

    def __init__(self, parent=None, triplet_count: int = 86):
        super().__init__(parent)
        self.triplet_count = triplet_count
        self.labels: List[QLabel] = []
        self._locked_positions: Set[int] = set()
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse_animation)
        self._pulse_state = 0
        self._current_changed: Set[int] = set()
        self._highlight_found = False
        self._animation_enabled = True
        self._setup_ui()

    def _setup_ui(self):
        """✅ Инициализация UI с оптимизацией"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header_lbl = QLabel("<b>🔤 Triplets (86 × 3 bits)</b>")
        header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_lbl.setStyleSheet(
            "color: #3498db; font-size: 11pt; padding: 4px; font-weight: bold;"
        )
        layout.addWidget(header_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(1)

        # ✅ Создание триплет-ячеек с правильным замыканием
        for i in range(self.triplet_count):
            lbl = QLabel("A")
            lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            lbl.setFixedSize(28, 28)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setStyleSheet(self._get_style(False, False, False))

            # ✅ Правильное замыкание с параметром по умолчанию
            lbl.mousePressEvent = lambda e, idx=i: self._on_click(idx)
            lbl.setToolTip(f"Position {i} — Click to lock/unlock")

            self.labels.append(lbl)
            row, col = divmod(i, 10)
            grid.addWidget(lbl, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Легенда
        legend = QLabel(
            "<small style='color: #7f8c8d;'>"
            "🟢 Normal  🔴 Changed  🔵 Locked  🟡 Found"
            "</small>",
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(legend)

    def _get_style(self, changed: bool, locked: bool, found: bool) -> str:
        """✅ Оптимизированная генерация стилей"""
        if found:
            return (
                "background: #f1c40f; color: #2c3e50; font-weight: bold; "
                "border-radius: 4px; border: 2px solid #f39c12;"
            )
        if locked:
            return (
                "background: #3498db; color: white; font-weight: bold; "
                "border-radius: 4px; border: 2px solid #2980b9;"
            )
        if changed:
            return (
                "background: #e74c3c; color: white; font-weight: bold; "
                "border-radius: 4px; border: 1px solid #c0392b;"
            )
        return (
            "background: #2c3e50; color: #ecf0f1; "
            "border-radius: 4px; border: 1px solid #34495e;"
        )

    def _on_click(self, position: int):
        """✅ Обработка клика с излучением сигнала"""
        if position in self._locked_positions:
            self._locked_positions.remove(position)
            self.triplet_locked.emit(position, False)
        else:
            self._locked_positions.add(position)
            self.triplet_locked.emit(position, True)

        self.refresh_styles()
        self.triplet_clicked.emit(position)

    def update_display(self, triplet_str: str, changed_positions: Optional[List[int]] = None,
                       found: bool = False) -> None:
        """✅ Оптимизированное обновление дисплея"""
        changed = set(changed_positions or [])
        self._current_changed = changed
        self._highlight_found = found

        # Обновляем только изменённые ячейки
        for i, lbl in enumerate(self.labels):
            if i >= len(triplet_str):
                break

            old_text = lbl.text()
            new_text = triplet_str[i]

            if old_text != new_text:
                lbl.setText(new_text)

            is_locked = i in self._locked_positions
            is_changed = i in changed and not found
            is_found_cell = found and i in changed

            lbl.setStyleSheet(self._get_style(is_changed, is_locked, is_found_cell))

        # Пульсация для изменённых позиций
        if changed and not found and self._animation_enabled:
            if not self._pulse_timer.isActive():
                self._pulse_state = 0
                self._pulse_timer.start(60)

    def _pulse_animation(self):
        """✅ Анимация пульсации для изменённых позиций"""
        self._pulse_state += 1
        if self._pulse_state > 6:
            self._pulse_timer.stop()
            self.refresh_styles()
            return

        pulse_intensity = 255 if self._pulse_state % 2 == 0 else 180
        for i in self._current_changed:
            if i < len(self.labels) and i not in self._locked_positions:
                self.labels[i].setStyleSheet(
                    f"background: rgba(231, 76, 60, {pulse_intensity}); "
                    f"color: white; font-weight: bold; border-radius: 4px;"
                )

    def refresh_styles(self):
        """Принудительное обновление стилей"""
        for i, lbl in enumerate(self.labels):
            is_locked = i in self._locked_positions
            is_changed = i in self._current_changed and not self._highlight_found
            is_found = self._highlight_found and i in self._current_changed
            lbl.setStyleSheet(self._get_style(is_changed, is_locked, is_found))

    def clear(self):
        """Сброс дисплея"""
        for lbl in self.labels:
            lbl.setText("A")
            lbl.setStyleSheet(self._get_style(False, False, False))
        self._locked_positions.clear()
        self._current_changed.clear()
        self._highlight_found = False
        self._pulse_timer.stop()

    def get_locked_positions(self) -> Set[int]:
        """Получить зафиксированные позиции"""
        return self._locked_positions.copy()

    def set_locked_positions(self, positions: Set[int]):
        """Установить зафиксированные позиции"""
        self._locked_positions = positions.copy()
        self.refresh_styles()

    def set_animation_enabled(self, enabled: bool):
        """Включить/отключить анимацию"""
        self._animation_enabled = enabled


# ═══════════════════════════════════════════════
# 🔧 ГЛАВНОЕ ОКНО MATRIX ENGINE
# ═══════════════════════════════════════════════

class MatrixWindow(QDialog):
    """✅ Главное окно Matrix Search Engine с улучшенной логикой"""

    search_started = pyqtSignal()
    search_stopped = pyqtSignal()
    key_found = pyqtSignal(dict)

    def __init__(self, parent: Optional['BitcoinGPUCPUScanner'] = None):
        super().__init__(parent)
        self.parent_window = parent
        self._last_stats_update = 0.0
        self._last_viz_update = 0.0
        self._stats_throttle = 0.05
        self._viz_throttle = 0.025
        self._found_addresses: Set[str] = set()
        self._worker_stats: Dict[int, Dict[str, Any]] = {}
        self.settings = get_settings(parent.BASE_DIR if parent else None)
        self.settings._ui_parent = self  # Для работы load_ui_settings

        self._setup_ui()
        self._connect_signals()
        self._setup_queue_timer()
        self._load_settings()

    def _get_logic(self) -> Optional['MatrixLogic']:
        """✅ Получить логику с проверкой"""
        return getattr(self.parent_window, 'matrix_logic', None) if self.parent_window else None

    def _setup_ui(self) -> None:
        """✅ Инициализация UI"""
        self.setWindowTitle("🔷 Matrix Search Engine v2.4")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QDialog { 
                background-color: #121212; 
                color: #ecf0f1; 
                font-family: 'Segoe UI', sans-serif; 
            }
            QGroupBox { 
                border: 1px solid #34495e; 
                border-radius: 6px; 
                margin-top: 12px; 
                padding-top: 8px; 
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
                color: #3498db; 
                font-weight: bold;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox { 
                background: #1e1e1e; 
                border: 1px solid #34495e; 
                border-radius: 4px; 
                padding: 6px; 
                color: #ecf0f1; 
            }
            QPushButton { 
                border-radius: 4px; 
                padding: 8px 16px; 
                font-weight: bold; 
                background: #3498db; 
                color: white; 
                border: none;
            }
            QPushButton:hover { 
                background: #2980b9; 
            } 
            QPushButton:pressed {
                background: #1a5276;
            }
            QPushButton:disabled { 
                background: #7f8c8d; 
            }
            QTextEdit, QTableWidget { 
                background: #1e1e1e; 
                border: 1px solid #34495e; 
                border-radius: 4px; 
                color: #ecf0f1; 
            }
            QTableWidget::item { 
                padding: 4px; 
            }
            QHeaderView::section { 
                background: #2c3e50; 
                color: #3498db; 
                padding: 5px; 
                border: none; 
            }
            QProgressBar { 
                border: 2px solid #34495e; 
                border-radius: 4px; 
                text-align: center; 
            }
            QProgressBar::chunk { 
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3498db, stop:1 #2ecc71); 
            }
            QSlider::groove:horizontal {
                background: #34495e;
                border-radius: 4px;
                height: 8px;
            }
            QSlider::handle:horizontal {
                background: #3498db;
                border-radius: 4px;
                width: 18px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #2980b9;
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(15)

        # === ЛЕВАЯ ПАНЕЛЬ ===
        left = self._setup_left_panel()
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(480)
        main_layout.addWidget(left_w)

        # === ПРАВАЯ ПАНЕЛЬ ===
        right = self._setup_right_panel()
        right_w = QWidget()
        right_w.setLayout(right)
        main_layout.addWidget(right_w, 1)

        if not COINCURVE_AVAILABLE:
            QMessageBox.warning(self, "⚠️ Dependency",
                                "Install: `pip install coincurve`")

    def _setup_left_panel(self) -> QVBoxLayout:
        """✅ Левая панель с параметрами"""
        left = QVBoxLayout()

        # 🎯 Цель и диапазон
        tg = QGroupBox("🎯 Target & Range")
        tgl = QGridLayout(tg)

        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU")
        tgl.addWidget(QLabel("Target Address:"), 0, 0)
        tgl.addWidget(self.target_edit, 0, 1)

        self.start_edit = QLineEdit()
        self.start_edit.setValidator(QRegularExpressionValidator(
            QRegularExpression("^[0-9a-fA-F]{0,64}$")))
        tgl.addWidget(QLabel("Range From (HEX):"), 1, 0)
        tgl.addWidget(self.start_edit, 1, 1)

        self.end_edit = QLineEdit()
        self.end_edit.setValidator(QRegularExpressionValidator(
            QRegularExpression("^[0-9a-fA-F]{0,64}$")))
        tgl.addWidget(QLabel("Range To (HEX):"), 2, 0)
        tgl.addWidget(self.end_edit, 2, 1)

        self.range_label = QLabel(
            "<small style='color: #7f8c8d'>Range: —</small>",
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        tgl.addWidget(self.range_label, 3, 0, 1, 2)
        left.addWidget(tg)

        # ⚙️ Параметры мутации
        pg = QGroupBox("⚙️ Mutation Parameters")
        pgl = QGridLayout(pg)

        # Вероятность
        self.chaos_slider = QSlider(Qt.Orientation.Horizontal)
        self.chaos_slider.setRange(0, 100)
        self.chaos_slider.setValue(70)
        self.chaos_slider.valueChanged.connect(self._update_chaos_label)
        pgl.addWidget(QLabel("🎲 Probability:"), 0, 0)
        pgl.addWidget(self.chaos_slider, 1, 0)
        self.chaos_label = QLabel("70%", alignment=Qt.AlignmentFlag.AlignRight)
        pgl.addWidget(self.chaos_label, 1, 1)

        # Сила
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(1, 50)
        self.strength_slider.setValue(15)
        self.strength_slider.valueChanged.connect(self._update_strength_label)
        pgl.addWidget(QLabel("✏️ Strength (%):"), 2, 0)
        pgl.addWidget(self.strength_slider, 3, 0)
        self.strength_label = QLabel("15%", alignment=Qt.AlignmentFlag.AlignRight)
        pgl.addWidget(self.strength_label, 3, 1)

        # Режим
        pgl.addWidget(QLabel("🔄 Mode:"), 4, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["random_curve", "pure_random", "drift", "adaptive"])
        pgl.addWidget(self.mode_combo, 4, 1)

        # Воркеры
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(4)
        pgl.addWidget(QLabel("🔧 Workers:"), 5, 0)
        pgl.addWidget(self.workers_spin, 5, 1)

        # Опции
        self.viz_check = QCheckBox("👁 Visualization")
        self.viz_check.setChecked(True)
        pgl.addWidget(self.viz_check, 6, 0, 1, 2)

        self.adaptive_check = QCheckBox("🧠 Adaptive Mode")
        self.adaptive_check.setChecked(True)
        pgl.addWidget(self.adaptive_check, 7, 0, 1, 2)

        # Кнопки управления
        btns = QHBoxLayout()
        self.start_btn = QPushButton("🚀 Start")
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setFixedHeight(40)
        btns.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(40)
        btns.addWidget(self.stop_btn)

        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self._on_reset)
        self.reset_btn.setFixedHeight(40)
        btns.addWidget(self.reset_btn)

        pgl.addLayout(btns, 8, 0, 1, 2)
        left.addWidget(pg)

        # Статус
        self.status_label = QLabel(
            "⚪ Ready",
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        self.status_label.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #34495e; "
            "padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        left.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        left.addWidget(self.progress_bar)

        # Лог
        log_grp = QGroupBox("📋 Log")
        log_l = QVBoxLayout(log_grp)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(160)
        log_l.addWidget(self.log_output)
        left.addWidget(log_grp)

        # Статистика
        stats_grp = QGroupBox("📊 Statistics")
        stats_l = QGridLayout(stats_grp)
        self.scanned_label = QLabel(
            "Scanned: <span style='color:#3498db;font-weight:bold'>0</span>"
        )
        self.found_label = QLabel(
            "Found: <span style='color:#2ecc71;font-weight:bold'>0</span>"
        )
        self.speed_label = QLabel(
            "Speed: <span style='color:#95a5a6;font-weight:bold'>0</span> keys/s"
        )
        self.time_label = QLabel(
            "Time: <span style='color:#95a5a6;font-weight:bold'>0:00</span>"
        )
        stats_l.addWidget(self.scanned_label, 0, 0)
        stats_l.addWidget(self.found_label, 0, 1)
        stats_l.addWidget(self.speed_label, 1, 0, 1, 2)
        stats_l.addWidget(self.time_label, 2, 0, 1, 2)
        left.addWidget(stats_grp)
        left.addStretch()

        return left

    def _setup_right_panel(self) -> QVBoxLayout:
        """✅ Правая панель с визуализацией"""
        right = QVBoxLayout()

        # 🔤 Триплеты
        viz = QGroupBox("🔤 Triplet Visualization")
        viz_l = QVBoxLayout(viz)
        self.triplet_display = TripletDisplay()
        self.triplet_display.triplet_clicked.connect(self._on_triplet_click)
        self.triplet_display.triplet_locked.connect(self._on_triplet_locked)
        viz_l.addWidget(self.triplet_display)

        # Текущий ключ
        self.current_hex = QLabel("HEX: —")
        self.current_addr = QLabel("Addr: —")
        for lbl in [self.current_hex, self.current_addr]:
            lbl.setFont(QFont("Consolas", 8))
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setStyleSheet("background: #1e1e1e; padding: 4px; border-radius: 3px;")
        viz_l.addWidget(self.current_hex)
        viz_l.addWidget(self.current_addr)
        right.addWidget(viz)

        # ✅ Найденные ключи
        res = QGroupBox("✅ Found Keys (History)")
        res_l = QVBoxLayout(res)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Time", "Address", "HEX", "WIF", "Worker"])
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        res_l.addWidget(self.results_table)

        copy_btn = QPushButton("📋 Copy Selected")
        copy_btn.clicked.connect(self._copy_selected)
        res_l.addWidget(copy_btn)
        right.addWidget(res)

        return right

    def _setup_queue_timer(self):
        """✅ Таймер для обработки очереди"""
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self._process_queue)
        self.queue_timer.start(20)  # 20ms интервал

    def _process_queue(self):
        """✅ Обработка сообщений из очереди с оптимизацией"""
        logic = self._get_logic()
        if not logic:
            return

        q = logic.get_queue()
        if not q:
            return

        now = time.time()
        processed = 0
        max_per_frame = 100

        while processed < max_per_frame:
            try:
                msg = q.get_nowait()
                msg_type = msg.get('type')

                if msg_type == 'found':
                    self._on_key_found(msg)

                elif msg_type == 'stats':
                    if now - self._last_stats_update >= self._stats_throttle:
                        self._on_stats(msg)
                        self._last_stats_update = now

                elif msg_type == 'log':
                    self._on_log(msg.get('message', ''), msg.get('level', 'info'))

                elif msg_type == 'search_state':
                    if now - self._last_viz_update >= self._viz_throttle:
                        self._on_search_state(msg)
                        self._last_viz_update = now

                elif msg_type == 'worker_finished':
                    wid = msg.get('worker_id', -1)
                    self._worker_stats[wid] = msg
                    self._on_worker_done(wid, msg.get('scanned', 0), msg.get('found', 0))

                processed += 1

            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                break

    def _on_search_state(self, data: Dict[str, Any]):
        """✅ Обновление визуального состояния"""
        hex_key = data.get('hex_key', '')
        address = data.get('address', '')
        triplets = data.get('triplets', '')
        changed = data.get('changed_positions', [])
        matched = data.get('matched', False)

        if hex_key:
            display_hex = f"{hex_key[:16]}...{hex_key[-16:]}"
            self.current_hex.setText(f"HEX: {display_hex}")

        if address and len(address) > 20:
            display_addr = f"{address[:12]}...{address[-12:]}"
            self.current_addr.setText(f"Addr: {display_addr}")

        if triplets:
            self.triplet_display.update_display(triplets, changed, found=matched)

    def _update_chaos_label(self, value: int):
        """Обновить метку вероятности"""
        self.chaos_label.setText(f"{value}%")
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(probability=value / 100)

    def _update_strength_label(self, value: int):
        """Обновить метку силы"""
        self.strength_label.setText(f"{value}%")
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(strength=value / 100)

    def _update_range_info(self):
        """✅ Обновить информацию о диапазоне"""
        s, e = self.start_edit.text().strip(), self.end_edit.text().strip()
        if len(s) == 64 and len(e) == 64:
            try:
                stats = MatrixConverter.get_range_stats(s, e)
                if not stats.get('is_valid'):
                    raise ValueError("Invalid range")

                tot = stats['total_keys']
                if tot > 1e18:
                    fmt = f"{tot / 1e18:.2f}E"
                elif tot > 1e15:
                    fmt = f"{tot / 1e15:.2f}P"
                elif tot > 1e12:
                    fmt = f"{tot / 1e12:.2f}T"
                elif tot > 1e9:
                    fmt = f"{tot / 1e9:.2f}B"
                elif tot > 1e6:
                    fmt = f"{tot / 1e6:.2f}M"
                else:
                    fmt = f"{tot:,}"

                self.range_label.setText(
                    f"<small style='color:#3498db'>📊 ~{fmt} keys</small>"
                )
            except Exception:
                self.range_label.setText(
                    "<small style='color:#e74c3c'>❌ Invalid range</small>"
                )
        else:
            self.range_label.setText(
                "<small style='color:#7f8c8d'>Enter 64-char HEX values</small>"
            )

    def _on_triplet_click(self, pos: int):
        """Обработка клика по триплету"""
        pass

    def _on_triplet_locked(self, pos: int, locked: bool):
        """✅ Обработка фиксации позиции"""
        logic = self._get_logic()
        if logic:
            locked_positions = list(self.triplet_display.get_locked_positions())
            logic.update_locked_positions(locked_positions)
            msg = f"{'🔒 Locked' if locked else '🔓 Unlocked'} position {pos}"
            self._log(msg, "info")

    def _on_start(self):
        """✅ Запуск поиска"""
        logic = self._get_logic()
        if not logic:
            return QMessageBox.critical(self, "Error", "MatrixLogic not initialized")

        target = self.target_edit.text().strip()
        start_hex = self.start_edit.text().strip()
        end_hex = self.end_edit.text().strip()

        if not all([target, start_hex, end_hex]) or len(start_hex) != 64 or len(end_hex) != 64:
            return QMessageBox.warning(
                self, "Error",
                "Fill address and 64-char HEX ranges"
            )

        num_workers = self.workers_spin.value()
        mutation_prob = self.chaos_slider.value() / 100
        mutation_strength = self.strength_slider.value() / 100
        visualize = self.viz_check.isChecked()
        adaptive = self.adaptive_check.isChecked()
        mode = self.mode_combo.currentText()
        locked = list(self.triplet_display.get_locked_positions())

        if logic.start_search(
                target_address=target,
                start_hex=start_hex,
                end_hex=end_hex,
                num_workers=num_workers,
                mutation_mode=mode,
                mutation_strength=mutation_strength,
                mutation_probability=mutation_prob,
                visualize_mutations=visualize,
                locked_positions=locked,
                adaptive_mode=adaptive
        ):
            self._found_addresses.clear()
            self._worker_stats.clear()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.status_label.setText("🔍 Searching...")
            self.status_label.setStyleSheet(
                "background: #f39c12; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            )
            self._log(f"🚀 Started: {num_workers} workers, mode: {mode}", "success")

    def _on_stop(self):
        """Остановка поиска"""
        logic = self._get_logic()
        if logic:
            logic.stop_search()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("⏸ Stopped")
        self.status_label.setStyleSheet(
            "background: #e74c3c; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        self._log("🛑 Search stopped", "warning")

    def _on_reset(self):
        """Сброс состояния"""
        self._on_stop()
        self.triplet_display.clear()
        self.results_table.setRowCount(0)
        self._found_addresses.clear()
        self._worker_stats.clear()
        self.scanned_label.setText(
            "Scanned: <span style='color:#3498db;font-weight:bold'>0</span>"
        )
        self.found_label.setText(
            "Found: <span style='color:#2ecc71;font-weight:bold'>0</span>"
        )
        self.speed_label.setText(
            "Speed: <span style='color:#95a5a6;font-weight:bold'>0</span> keys/s"
        )
        self.time_label.setText(
            "Time: <span style='color:#95a5a6;font-weight:bold'>0:00</span>"
        )
        self.status_label.setText("⚪ Ready")
        self.status_label.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #34495e; padding: 8px; border-radius: 4px;"
        )
        self.current_hex.setText("HEX: —")
        self.current_addr.setText("Addr: —")
        self._log("🔄 Reset complete", "info")

    def _on_stats(self, stats: Dict[str, Any]):
        """✅ Обновление статистики"""
        scanned = stats.get('scanned', 0)
        found = stats.get('found', 0)
        speed = stats.get('speed', 0)
        elapsed = stats.get('elapsed_time', 0)

        self.scanned_label.setText(
            f"Scanned: <span style='color:#3498db;font-weight:bold'>{scanned:,}</span>"
        )
        self.found_label.setText(
            f"Found: <span style='color:#2ecc71;font-weight:bold'>{found}</span>"
        )

        # Форматирование скорости
        if speed >= 1_000_000:
            spd_text = f"{speed / 1_000_000:.2f}M"
            color = "#27ae60"
        elif speed >= 1_000:
            spd_text = f"{speed / 1_000:.2f}K"
            color = "#f39c12"
        else:
            spd_text = f"{speed:.0f}"
            color = "#95a5a6"

        self.speed_label.setText(
            f"Speed: <span style='color:{color};font-weight:bold'>{spd_text}</span> keys/s"
        )

        # Форматирование времени
        minutes = int(elapsed) // 60
        seconds = int(elapsed) % 60
        self.time_label.setText(
            f"Time: <span style='color:#95a5a6;font-weight:bold'>{minutes}:{seconds:02d}</span>"
        )

    def _on_log(self, msg: str, level: str = "info"):
        """✅ Логирование с цветной маркировкой"""
        ts = time.strftime("[%H:%M:%S]")
        colors = {
            "error": "#e74c3c",
            "warning": "#f39c12",
            "success": "#2ecc71",
            "info": "#95a5a6"
        }
        color = colors.get(level, "#ecf0f1")
        self.log_output.append(f'<span style="color:{color}">{ts} {msg}</span>')

        # Автоматическая прокрутка
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def _on_key_found(self, data: Dict[str, Any]):
        """✅ Обработка найденного ключа"""
        addr = data.get('address', '')
        hex_key = data.get('hex_key', '')
        wif = data.get('wif_key', 'N/A')

        if not addr or addr in self._found_addresses:
            return

        self._found_addresses.add(addr)

        # Добавка в таблицу
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        items = [
            data.get('timestamp', ''),
            addr,
            hex_key,
            wif,
            str(data.get('worker_id', '?'))
        ]

        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setBackground(QColor("#27ae60"))
            item.setForeground(QColor("#ffffff"))
            item.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            self.results_table.setItem(row, col, item)

        self._log(f"🎉 KEY FOUND: {addr[:12]}...", "success")

        # Сохранение
        try:
            with open("found_keys.txt", "a", encoding='utf-8') as f:
                f.write(
                    f"[{data.get('timestamp')}] {addr} | "
                    f"HEX: {hex_key} | WIF: {wif} | Worker: {data.get('worker_id')}\n"
                )
        except Exception as e:
            self._log(f"❌ File write error: {e}", "error")

        # Уведомление
        QTimer.singleShot(0, lambda: QMessageBox.information(
            self, "🎉 SUCCESS!",
            f"Address: {addr}\nHEX: {hex_key}\nWIF: {wif}\n✅ Saved to found_keys.txt"
        ))

        self.key_found.emit(data)

    def _on_worker_done(self, wid: int, scanned: int, found: int):
        """✅ Обработка завершения воркера"""
        self._log(
            f"✅ Worker #{wid} done | {scanned:,} scanned, {found} found",
            "info"
        )

        logic = self._get_logic()
        if logic:
            # Проверка, все ли воркеры завершены
            active_workers = sum(1 for p in logic.processes.values() if p.is_alive())
            if active_workers == 0 and not logic.is_running:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.progress_bar.setVisible(False)
                total_found = len(self._found_addresses)
                self.status_label.setText(f"✅ Complete: {total_found} found")
                self.status_label.setStyleSheet(
                    "background: #27ae60; color: white; padding: 8px; border-radius: 4px;"
                )

    def _copy_selected(self):
        """✅ Копирование выбранной строки"""
        row = self.results_table.currentRow()
        if row == -1:
            return QMessageBox.information(self, "ℹ️", "Select a row in the table")

        try:
            addr = self.results_table.item(row, 1).text()
            hex_key = self.results_table.item(row, 2).text()
            wif = self.results_table.item(row, 3).text()

            text = f"Address: {addr}\nHEX: {hex_key}\nWIF: {wif}"
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "✅", "Copied to clipboard")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Copy failed: {e}")

    def _connect_signals(self):
        """✅ Подключение сигналов"""
        self.start_edit.textChanged.connect(self._update_range_info)
        self.end_edit.textChanged.connect(self._update_range_info)
        self._update_range_info()

    def _log(self, msg: str, level: str = "info"):
        """Логирование"""
        self._on_log(msg, level)

    def _load_settings(self):
        """✅ Загрузить настройки через SettingsManager (авто-синк)"""
        try:
            # 🔄 Авто-загрузка всех стандартных виджетов в неймспейс 'matrix'
            self.settings.auto_sync_all_widgets(self, namespace='matrix', save_mode=False)

            # 🔐 Загрузка зафиксированных позиций триплетов (специальный случай)
            locked = self.settings.get('locked_triplets', [], 'matrix')
            if locked:
                self.triplet_display.set_locked_positions(set(locked))

            logger.info("✅ Настройки Matrix загружены")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки настроек Matrix: {e}")

    def _save_settings(self):
        """✅ Сохранить настройки через SettingsManager (авто-синк)"""
        try:
            # 🔄 Авто-сохранение всех стандартных виджетов в неймспейс 'matrix'
            self.settings.auto_sync_all_widgets(self, namespace='matrix', save_mode=True)

            # 🔐 Сохранение зафиксированных позиций триплетов (специальный случай)
            locked = list(self.triplet_display.get_locked_positions())
            self.settings.set('locked_triplets', locked, 'matrix')

            # 💾 Запись на диск
            self.settings.save()

            logger.info("💾 Настройки Matrix сохранены")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения настроек Matrix: {e}")

    def closeEvent(self, event):
        """✅ Обработка закрытия окна"""
        logic = self._get_logic()
        if logic and logic.is_running:
            reply = QMessageBox.question(
                self, "Confirm",
                "Search is active. Stop and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_stop()
                self._save_settings()  # ← Сохранение
                self.queue_timer.stop()
                event.accept()
            else:
                event.ignore()
        else:
            self._save_settings()  # ← Сохранение
            self.queue_timer.stop()
            event.accept()


__all__ = ['TripletDisplay', 'MatrixWindow']