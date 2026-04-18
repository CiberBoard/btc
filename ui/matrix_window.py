# ui/matrix_window.py
from __future__ import annotations
import time
import logging
import queue
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Set

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRegularExpression
from PyQt6.QtGui import QFont, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QGridLayout, QMessageBox, QSpinBox, QSlider,
    QScrollArea, QWidget, QProgressBar, QApplication, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView
)

from core.matrix_logic import MatrixConverter, COINCURVE_AVAILABLE, MatrixLogic

if TYPE_CHECKING:
    from ui.main_window import BitcoinGPUCPUScanner

logger = logging.getLogger(__name__)


class TripletDisplay(QWidget):
    """Визуальное отображение триплетов с поддержкой фиксации (как в Windows)"""
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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header_lbl = QLabel("<b>🔤 Триплеты (86 × 3 бита)</b>")
        header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_lbl.setStyleSheet("color: #3498db; font-size: 11pt; padding: 4px;")
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

        # ✅ ИСПРАВЛЕННЫЙ ЦИКЛ СОЗДАНИЯ ТРИПЛЕТОВ
        for i in range(self.triplet_count):
            lbl = QLabel("A")
            lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            lbl.setFixedSize(24, 26)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setStyleSheet(self._get_style(False, False, False))

            # ✅ Лямбда с правильным замыканием: idx=i фиксирует значение
            lbl.mousePressEvent = lambda e, idx=i: self._on_click(idx)

            # ✅ Используем i, а не pos (pos существует только внутри lambda!)
            lbl.setToolTip(f"Позиция {i} — клик для фиксации/разблокировки")

            self.labels.append(lbl)
            row, col = divmod(i, 10)
            grid.addWidget(lbl, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        legend = QLabel(
            "<small style='color: #7f8c8d'>"
            "🟢 норма 🔴 изменено 🔵 зафиксировано 🟡 найдено"
            "</small>",
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(legend)

    # ... [остальные методы без изменений: _get_style, _on_click, update_display, etc.] ...

    def _get_style(self, changed: bool, locked: bool, found: bool) -> str:
        """Генерация стилей для ячеек триплетов"""
        if found:
            return ("background: #f1c40f; color: #2c3e50; font-weight: bold; "
                    "border-radius: 4px; border: 2px solid #f39c12;")
        if locked:
            return ("background: #3498db; color: white; font-weight: bold; "
                    "border-radius: 4px; border: 2px solid #2980b9;")
        if changed:
            return ("background: #e74c3c; color: white; font-weight: bold; "
                    "border-radius: 4px; border: 1px solid #c0392b; animation: pulse 0.3s;")
        return ("background: #2c3e50; color: #ecf0f1; "
                "border-radius: 4px; border: 1px solid #34495e;")

    def _on_click(self, position: int):
        """Обработка клика по триплету — фиксация/разблокировка"""
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
        """Обновляет отображение триплетов с анимацией изменений"""
        changed = set(changed_positions or [])
        self._current_changed = changed
        self._highlight_found = found

        for i, lbl in enumerate(self.labels):
            if i >= len(triplet_str):
                break
            # Обновляем символ только если изменился
            if lbl.text() != triplet_str[i]:
                lbl.setText(triplet_str[i])

            # Применяем стиль с приоритетами: found > locked > changed > normal
            is_locked = i in self._locked_positions
            is_changed = i in changed and not found
            is_found_cell = found and i in changed

            lbl.setStyleSheet(self._get_style(is_changed, is_locked, is_found_cell))

        # Запускаем пульсацию для изменённых (не зафиксированных) позиций
        if changed and not found and not self._pulse_timer.isActive():
            self._pulse_state = 0
            self._pulse_timer.start(60)

    def _pulse_animation(self):
        """Анимация пульсации для изменённых позиций"""
        self._pulse_state += 1
        if self._pulse_state > 6:
            self._pulse_timer.stop()
            self.refresh_styles()
            return

        pulse_alpha = 255 if self._pulse_state % 2 == 0 else 160
        for i in self._current_changed:
            if i < len(self.labels) and i not in self._locked_positions:
                self.labels[i].setStyleSheet(
                    f"background: rgba(231, 76, 60, {pulse_alpha}); "
                    f"color: white; font-weight: bold; border-radius: 4px;"
                )

    def refresh_styles(self):
        """Принудительно обновляет стили всех ячеек"""
        for i, lbl in enumerate(self.labels):
            is_locked = i in self._locked_positions
            is_changed = i in self._current_changed and not self._highlight_found
            is_found = self._highlight_found and i in self._current_changed
            lbl.setStyleSheet(self._get_style(is_changed, is_locked, is_found))

    def clear(self):
        """Сбрасывает отображение к начальному состоянию"""
        for lbl in self.labels:
            lbl.setText("A")
            lbl.setStyleSheet(self._get_style(False, False, False))
        self._locked_positions.clear()
        self._current_changed.clear()
        self._highlight_found = False
        self._pulse_timer.stop()

    def get_locked_positions(self) -> Set[int]:
        """Возвращает множество зафиксированных позиций"""
        return self._locked_positions.copy()

    def set_locked_positions(self, positions: Set[int]):
        """Устанавливает зафиксированные позиции извне"""
        self._locked_positions = positions.copy()
        self.refresh_styles()


class MatrixWindow(QDialog):
    """Основное окно Matrix Search Engine"""
    search_started = pyqtSignal()
    search_stopped = pyqtSignal()
    key_found = pyqtSignal(dict)

    def __init__(self, parent: Optional['BitcoinGPUCPUScanner'] = None):
        super().__init__(parent)
        self.parent_window = parent
        self._last_stats_update = 0
        self._last_viz_update = 0
        self._stats_throttle = 0.05
        self._viz_throttle = 0.025
        self._found_addresses: Set[str] = set()
        self._setup_ui()
        self._connect_signals()
        self._setup_queue_timer()

    def _get_logic(self) -> Optional['MatrixLogic']:
        return getattr(self.parent_window, 'matrix_logic', None) if self.parent_window else None

    def _setup_ui(self) -> None:
        self.setWindowTitle("🔷 Matrix Search Engine v2.3")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #ecf0f1; font-family: 'Segoe UI', sans-serif; }
            QGroupBox { border: 1px solid #34495e; border-radius: 6px; margin-top: 12px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #3498db; }
            QLineEdit, QSpinBox { background: #1e1e1e; border: 1px solid #34495e; border-radius: 4px; padding: 6px; color: #ecf0f1; }
            QPushButton { border-radius: 4px; padding: 8px 16px; font-weight: bold; background: #3498db; color: white; }
            QPushButton:hover { background: #2980b9; } 
            QPushButton:disabled { background: #7f8c8d; }
            QTextEdit, QTableWidget { background: #1e1e1e; border: 1px solid #34495e; border-radius: 4px; color: #ecf0f1; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section { background: #2c3e50; color: #3498db; padding: 5px; border: none; }
            QProgressBar { border: 2px solid #34495e; border-radius: 4px; text-align: center; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #3498db, stop:1 #2ecc71); }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(15)

        # === ЛЕВАЯ ПАНЕЛЬ ===
        left = QVBoxLayout()

        # 🎯 Цель и диапазон
        tg = QGroupBox("🎯 Цель и диапазон")
        tgl = QGridLayout(tg)

        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU")
        tgl.addWidget(QLabel("Целевой адрес:"), 0, 0)
        tgl.addWidget(self.target_edit, 0, 1)

        self.start_edit = QLineEdit()
        self.start_edit.setValidator(QRegularExpressionValidator(QRegularExpression("^[0-9a-fA-F]{0,64}$")))
        tgl.addWidget(QLabel("Диапазон от (HEX):"), 1, 0)
        tgl.addWidget(self.start_edit, 1, 1)

        self.end_edit = QLineEdit()
        self.end_edit.setValidator(QRegularExpressionValidator(QRegularExpression("^[0-9a-fA-F]{0,64}$")))
        tgl.addWidget(QLabel("Диапазон до (HEX):"), 2, 0)
        tgl.addWidget(self.end_edit, 2, 1)

        self.range_label = QLabel(
            "<small style='color: #7f8c8d'>Диапазон: —</small>",
            alignment=Qt.AlignmentFlag.AlignCenter
        )
        tgl.addWidget(self.range_label, 3, 0, 1, 2)
        left.addWidget(tg)

        # ⚙️ Параметры мутации
        pg = QGroupBox("⚙️ Параметры мутации")
        pgl = QGridLayout(pg)

        self.chaos_slider = QSlider(Qt.Orientation.Horizontal)
        self.chaos_slider.setRange(0, 100)
        self.chaos_slider.setValue(70)  # Default: больше случайности
        self.chaos_slider.valueChanged.connect(self._update_chaos_label)
        pgl.addWidget(QLabel("🎲 Вероятность мутации:"), 0, 0)
        pgl.addWidget(self.chaos_slider, 1, 0)
        self.chaos_label = QLabel("70%", alignment=Qt.AlignmentFlag.AlignRight)
        pgl.addWidget(self.chaos_label, 1, 1)

        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(1, 50)
        self.strength_slider.setValue(15)
        self.strength_slider.valueChanged.connect(self._update_strength_label)
        pgl.addWidget(QLabel("✏️ Сила мутации (%):"), 2, 0)
        pgl.addWidget(self.strength_slider, 3, 0)
        self.strength_label = QLabel("15%", alignment=Qt.AlignmentFlag.AlignRight)
        pgl.addWidget(self.strength_label, 3, 1)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(4)
        pgl.addWidget(QLabel("🔧 Воркеры:"), 4, 0)
        pgl.addWidget(self.workers_spin, 4, 1)

        self.viz_check = QCheckBox("👁 Визуализация")
        self.viz_check.setChecked(True)
        pgl.addWidget(self.viz_check, 5, 0, 1, 2)

        # Кнопки управления
        btns = QHBoxLayout()
        self.start_btn = QPushButton("🚀 Запустить")
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setFixedHeight(40)
        btns.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(40)
        btns.addWidget(self.stop_btn)

        self.reset_btn = QPushButton("🔄 Сброс")
        self.reset_btn.clicked.connect(self._on_reset)
        self.reset_btn.setFixedHeight(40)
        btns.addWidget(self.reset_btn)
        pgl.addLayout(btns, 6, 0, 1, 2)
        left.addWidget(pg)

        # Статус и прогресс
        self.status_label = QLabel("⚪ Ожидание запуска", alignment=Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #34495e; padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        left.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        left.addWidget(self.progress_bar)

        # Лог
        log_grp = QGroupBox("📋 Лог")
        log_l = QVBoxLayout(log_grp)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(160)
        log_l.addWidget(self.log_output)
        left.addWidget(log_grp)

        # Статистика
        stats_grp = QGroupBox("📊 Статистика")
        stats_l = QGridLayout(stats_grp)
        self.scanned_label = QLabel("Проверено: <span style='color:#3498db;font-weight:bold'>0</span>")
        self.found_label = QLabel("Найдено: <span style='color:#2ecc71;font-weight:bold'>0</span>")
        self.speed_label = QLabel("Скорость: <span style='color:#95a5a6;font-weight:bold'>0</span> keys/s")
        stats_l.addWidget(self.scanned_label, 0, 0)
        stats_l.addWidget(self.found_label, 0, 1)
        stats_l.addWidget(self.speed_label, 1, 0, 1, 2)
        left.addWidget(stats_grp)
        left.addStretch()

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(460)
        main_layout.addWidget(left_w)

        # === ПРАВАЯ ПАНЕЛЬ ===
        right = QVBoxLayout()

        # 🔤 Визуализация триплетов
        viz = QGroupBox("🔤 Визуализация триплетов")
        viz_l = QVBoxLayout(viz)
        self.triplet_display = TripletDisplay()
        self.triplet_display.triplet_clicked.connect(self._on_triplet_click)
        self.triplet_display.triplet_locked.connect(self._on_triplet_locked)
        viz_l.addWidget(self.triplet_display)

        # Отображение текущего ключа
        self.current_hex = QLabel("HEX: —")
        self.current_addr = QLabel("Адрес: —")
        for lbl in [self.current_hex, self.current_addr]:
            lbl.setFont(QFont("Consolas", 9))
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setStyleSheet("background: #1e1e1e; padding: 4px; border-radius: 3px;")
        viz_l.addWidget(self.current_hex)
        viz_l.addWidget(self.current_addr)
        right.addWidget(viz)

        # ✅ Найденные ключи
        res = QGroupBox("✅ Найденные ключи (История)")
        res_l = QVBoxLayout(res)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Время", "Адрес", "HEX", "WIF", "Воркер"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        res_l.addWidget(self.results_table)

        copy_btn = QPushButton("📋 Копировать выбранный")
        copy_btn.clicked.connect(self._copy_selected)
        res_l.addWidget(copy_btn)
        right.addWidget(res)

        right_w = QWidget()
        right_w.setLayout(right)
        main_layout.addWidget(right_w)

        if not COINCURVE_AVAILABLE:
            QMessageBox.warning(self, "⚠️ Зависимость", "Установите: `pip install coincurve`")

    def _setup_queue_timer(self):
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self._process_queue)
        self.queue_timer.start(20)

    def _process_queue(self):
        logic = self._get_logic()
        if not logic:
            return
        q = logic.get_queue()
        if not q:
            return

        now = time.time()
        processed = 0
        while processed < 100:
            try:
                msg = q.get_nowait()
                msg_type = msg.get('type')

                if msg_type == 'found':
                    self._on_key_found(msg)
                elif msg_type == 'stats' and now - self._last_stats_update >= self._stats_throttle:
                    self._on_stats(msg)
                    self._last_stats_update = now
                elif msg_type == 'log':
                    self._on_log(msg['message'], msg.get('level', 'info'))
                elif msg_type == 'search_state' and now - self._last_viz_update >= self._viz_throttle:
                    self._on_search_state(msg)
                    self._last_viz_update = now
                elif msg_type == 'worker_finished':
                    self._on_worker_done(
                        msg.get('worker_id', -1),
                        msg.get('scanned', 0),
                        msg.get('found', 0)
                    )
                processed += 1
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                break

    def _on_search_state(self, data: Dict[str, Any]):
        """✅ Исправлено: обработка визуального состояния от воркеров"""
        hex_key = data.get('hex_key', '')
        address = data.get('address', '')
        triplets = data.get('triplets', '')
        changed = data.get('changed_positions', [])
        matched = data.get('matched', False)

        # Обновляем отображение ключа (форматированный вывод)
        if hex_key:
            self.current_hex.setText(f"HEX: {hex_key[:16]}...{hex_key[-16:]}")
        if address:
            self.current_addr.setText(f"Адрес: {address[:12]}...{address[-12:]}")
        if triplets:
            self.triplet_display.update_display(triplets, changed, found=matched)

    def _update_chaos_label(self, value: int):
        prob = value / 100
        self.chaos_label.setText(f"{value}%")
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(probability=prob)

    def _update_strength_label(self, value: int):
        strength = value / 100
        self.strength_label.setText(f"{value}%")
        logic = self._get_logic()
        if logic and logic.is_running:
            logic.update_mutation_params(strength=strength)

    def _update_range_info(self):
        s, e = self.start_edit.text().strip(), self.end_edit.text().strip()
        if len(s) == 64 and len(e) == 64:
            try:
                stats = MatrixConverter.get_range_stats(s, e)
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
                self.range_label.setText(f"<small style='color:#3498db'>📊 ~{fmt} ключей</small>")
            except Exception:
                self.range_label.setText("<small style='color:#e74c3c'>❌ Ошибка диапазона</small>")
        else:
            self.range_label.setText("<small style='color:#7f8c8d'>Введите 64-символьные HEX значения</small>")

    def _on_triplet_click(self, pos: int):
        """Обработка клика по триплету"""
        pass  # Логика в _on_triplet_locked

    def _on_triplet_locked(self, pos: int, locked: bool):
        """✅ Обработка фиксации/разблокировки позиции"""
        logic = self._get_logic()
        if logic:
            # Получаем все зафиксированные позиции из дисплея
            locked_positions = list(self.triplet_display.get_locked_positions())
            # Обновляем в логике (для новых воркеров)
            logic.update_locked_positions(locked_positions)
            self._log(f"{'🔒 Зафиксирована' if locked else '🔓 Разблокирована'} позиция {pos}", "info")

    def _on_start(self):
        logic = self._get_logic()
        if not logic:
            return QMessageBox.critical(self, "Ошибка", "MatrixLogic не инициализирован")

        target = self.target_edit.text().strip()
        start_hex = self.start_edit.text().strip()
        end_hex = self.end_edit.text().strip()

        if not all([target, start_hex, end_hex]) or len(start_hex) != 64 or len(end_hex) != 64:
            return QMessageBox.warning(self, "Ошибка", "Заполните адрес и 64-символьные HEX диапазоны")

        # Получаем параметры из UI
        num_workers = self.workers_spin.value()
        mutation_prob = self.chaos_slider.value() / 100
        mutation_strength = self.strength_slider.value() / 100
        visualize = self.viz_check.isChecked()
        locked = list(self.triplet_display.get_locked_positions())

        if logic.start_search(
                target_address=target,
                start_hex=start_hex,
                end_hex=end_hex,
                num_workers=num_workers,
                mutation_mode="random_curve",
                mutation_strength=mutation_strength,
                mutation_probability=mutation_prob,
                visualize_mutations=visualize,
                locked_positions=locked  # ✅ Передаём зафиксированные позиции

        ):
            self._found_addresses.clear()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.status_label.setText("🔍 Активный поиск...")
            self.status_label.setStyleSheet(
                "background: #f39c12; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            )
            self._log(f"🚀 Поиск запущен: {num_workers} воркеров, диапазон разделён", "success")

    def _on_stop(self):
        logic = self._get_logic()
        if logic:
            logic.stop_search()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("⏸ Остановлено")
        self.status_label.setStyleSheet(
            "background: #e74c3c; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        self._log("🛑 Поиск остановлен", "warning")

    def _on_reset(self):
        self._on_stop()
        self.triplet_display.clear()
        self.results_table.setRowCount(0)
        self._found_addresses.clear()
        self.scanned_label.setText("Проверено: <span style='color:#3498db;font-weight:bold'>0</span>")
        self.found_label.setText("Найдено: <span style='color:#2ecc71;font-weight:bold'>0</span>")
        self.speed_label.setText("Скорость: <span style='color:#95a5a6;font-weight:bold'>0</span> keys/s")
        self.status_label.setText("⚪ Готово")
        self.status_label.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #34495e; padding: 8px; border-radius: 4px;"
        )
        self.current_hex.setText("HEX: —")
        self.current_addr.setText("Адрес: —")
        self._log("🔄 Сброс выполнен", "info")

    def _on_stats(self, stats: Dict[str, Any]):
        scanned = stats.get('scanned', 0)
        found = stats.get('found', 0)
        speed = stats.get('speed', 0)

        self.scanned_label.setText(f"Проверено: <span style='color:#3498db;font-weight:bold'>{scanned:,}</span>")
        self.found_label.setText(f"Найдено: <span style='color:#2ecc71;font-weight:bold'>{found}</span>")

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

        self.speed_label.setText(f"Скорость: <span style='color:{color};font-weight:bold'>{spd_text}</span> keys/s")

    def _on_log(self, msg: str, level: str = "info"):
        ts = time.strftime("[%H:%M:%S]")
        colors = {
            "error": "#e74c3c",
            "warning": "#f39c12",
            "success": "#2ecc71",
            "info": "#95a5a6"
        }
        color = colors.get(level, "#ecf0f1")
        self.log_output.append(f'<span style="color:{color}">{ts} {msg}</span>')
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def _on_key_found(self, data: Dict[str, Any]):
        """Обработка найденного ключа"""
        addr = data.get('address', '')
        hex_key = data.get('hex_key', '')
        wif = data.get('wif_key', 'N/A')

        if not addr or addr in self._found_addresses:
            return

        self._found_addresses.add(addr)

        # Добавляем в таблицу
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
            item.setBackground(Qt.GlobalColor.green)
            item.setForeground(Qt.GlobalColor.white)
            item.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            self.results_table.setItem(row, col, item)

        self._log(f"🎉 КЛЮЧ НАЙДЕН: {addr[:12]}...", "success")

        # Сохранение в файл
        try:
            with open("found_keys.txt", "a", encoding='utf-8') as f:
                f.write(
                    f"[{data.get('timestamp')}] {addr} | HEX: {hex_key} | WIF: {wif} | Worker: {data.get('worker_id')}\n")
        except Exception as e:
            self._log(f"❌ Ошибка записи в файл: {e}", "error")

        # Уведомление
        QTimer.singleShot(0, lambda: QMessageBox.information(
            self, "🎉 УСПЕХ!",
            f"Адрес: {addr}\nHEX: {hex_key}\nWIF: {wif}\n✅ Сохранено в found_keys.txt"
        ))

        self.key_found.emit(data)

    def _on_worker_done(self, wid: int, scanned: int, found: int):
        self._log(f"✅ Воркер #{wid} завершён | {scanned:,} проверено, {found} найдено", "info")

        logic = self._get_logic()
        if logic:
            logic._total_scanned += scanned
            logic._total_found += found

            # Проверяем завершение всех воркеров
            if not any(p.is_alive() for p in logic.processes.values()) and not logic.is_running:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.progress_bar.setVisible(False)
                self.status_label.setText(f"✅ Завершено: {logic._total_found} найдено")
                self.status_label.setStyleSheet(
                    "background: #27ae60; color: white; padding: 8px; border-radius: 4px;"
                )

    def _copy_selected(self):
        row = self.results_table.currentRow()
        if row == -1:
            return QMessageBox.information(self, "ℹ️", "Выберите строку в таблице")

        addr = self.results_table.item(row, 1).text()
        hex_key = self.results_table.item(row, 2).text()
        wif = self.results_table.item(row, 3).text()

        text = f"Address: {addr}\nHEX: {hex_key}\nWIF: {wif}"
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "✅", "Скопировано в буфер обмена")

    def _connect_signals(self):
        self.start_edit.textChanged.connect(self._update_range_info)
        self.end_edit.textChanged.connect(self._update_range_info)
        self._update_range_info()

    def _log(self, msg: str, level: str = "info"):
        self._on_log(msg, level)

    def closeEvent(self, event):
        logic = self._get_logic()
        if logic and logic.is_running:
            reply = QMessageBox.question(
                self, "Подтверждение",
                "Поиск активен. Остановить и закрыть?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_stop()
                self.queue_timer.stop()
                event.accept()
            else:
                event.ignore()
        else:
            self.queue_timer.stop()
            event.accept()


# ✅ Добавляем недостающий импорт
from PyQt6.QtWidgets import QCheckBox

__all__ = ['TripletDisplay', 'MatrixWindow']