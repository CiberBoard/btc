# ui/gpu_progress_tracker.py
import re
import logging
from pathlib import Path
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLabel, QMessageBox,
                             QHeaderView, QApplication, QWidget, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

logger = logging.getLogger(__name__)


class GpuProgressTrackerWindow(QDialog):
    """Окно управления сохраненными диапазонами поиска"""
    range_selected = pyqtSignal(str, str)  # start_hex, end_hex

    def __init__(self, parent, log_file_path: Path):
        super().__init__(parent)
        self.parent = parent
        self.log_file_path = log_file_path
        self.setWindowTitle("💾 Сохраненный прогресс GPU поиска")
        self.resize(1150, 680)
        self.setMinimumSize(950, 520)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── Заголовок ──
        header_layout = QHBoxLayout()
        title_label = QLabel("📋 Сохраненные диапазоны поиска")
        title_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title_label.setStyleSheet("color: #E0E0E0;")

        self.stats_label = QLabel("Записей: 0")
        self.stats_label.setStyleSheet("color: #888; font-size: 10pt; font-weight: 500;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)
        main_layout.addLayout(header_layout)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background: #3A3A4A; margin: 4px 0;")
        main_layout.addWidget(sep)

        # ── Таблица ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["GPU", "Начало (HEX)", "Конец (HEX)", "Прогресс", "Действия"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 210)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet(self._table_style())
        main_layout.addWidget(self.table)

        # ── Панель инструментов ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.refresh_btn = self._create_tool_button("🔄 Обновить", "#5B8CFF")
        self.refresh_btn.clicked.connect(self._load_data)

        self.load_btn = self._create_tool_button("📥 Загрузить в поиск", "#2ECC71")
        self.load_btn.clicked.connect(self._apply_selected)

        self.clear_btn = self._create_tool_button("🗑 Очистить лог", "#E74C3C")
        self.clear_btn.clicked.connect(self._clear_log)

        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.load_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.clear_btn)
        main_layout.addLayout(toolbar)

        # Глобальные стили диалога
        self.setStyleSheet(self._dialog_style())

    def _create_tool_button(self, text: str, base_color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {base_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background: {self._darken_color(base_color, 20)}; }}
            QPushButton:pressed {{ background: {self._darken_color(base_color, 40)}; }}
        """)
        return btn

    @staticmethod
    def _darken_color(hex_color: str, amount: int = 20) -> str:
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = max(0, r - amount), max(0, g - amount), max(0, b - amount)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _table_style(self) -> str:
        return """
            QTableWidget {
                background: #1E1E2E;
                color: #E0E0E0;
                border: 1px solid #3A3A4A;
                border-radius: 8px;
                gridline-color: #2A2A3A;
                font-size: 10pt;
                outline: none;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background: #2D4A7A;
                color: #FFFFFF;
            }
            QTableWidget::item:hover:!selected {
                background: #252535;
            }
            QHeaderView::section {
                background: #2D2D3D;
                color: #AAAAAA;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #3A3A4A;
                font-weight: bold;
                font-size: 10pt;
            }
            QScrollBar:vertical {
                background: #1E1E2E;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4A4A5A;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5B8CFF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0px;
                width: 0px;
            }
        """

    def _dialog_style(self) -> str:
        return """
            QDialog {
                background: #151520;
                color: #E0E0E0;
            }
            QLabel { color: #E0E0E0; }
            QFrame { background: #3A3A4A; }
            QMessageBox { background: #1E1E2E; color: #E0E0E0; }
            QMessageBox QLabel { color: #E0E0E0; font-size: 10pt; }
            QMessageBox QPushButton {
                background: #3A3A4A; color: white;
                border: 1px solid #555; border-radius: 6px;
                padding: 6px 14px; min-width: 80px;
            }
            QMessageBox QPushButton:hover { background: #4A4A5A; }
        """

    def _load_data(self):
        self.table.setRowCount(0)
        if not self.log_file_path.exists():
            self.stats_label.setText("Записей: 0")
            return

        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            pattern = re.compile(
                r"([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+(\d+)%\s+пройдено\s+GPU\s*(\d+)", re.IGNORECASE
            )

            count = 0
            for line in lines:
                match = pattern.search(line)
                if not match:
                    continue
                start, end, percent, gpu_id = match.groups()
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setRowHeight(row, 38)

                self._set_item(row, 0, f"GPU {gpu_id}")
                self._set_item(row, 1, start.zfill(64))
                self._set_item(row, 2, end.zfill(64))
                self._set_item(row, 3, f"{percent}%")

                act_widget = self._create_action_row(start.zfill(64), end.zfill(64))
                self.table.setCellWidget(row, 4, act_widget)
                count += 1

            self.stats_label.setText(f"Записей: {count}")

        except Exception as e:
            logger.error(f"Ошибка загрузки прогресса: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")
            self.stats_label.setText("Записей: 0")

    def _set_item(self, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        if col in (1, 2):
            item.setToolTip(text)  # Подсказка с полным HEX при наведении
        self.table.setItem(row, col, item)

    def _create_action_row(self, start: str, end: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        copy_btn = QPushButton("📋 Копировать")
        copy_btn.setFixedHeight(28)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #3498db; color: white; border: none;
                border-radius: 4px; font-size: 9pt; padding: 0 8px;
            }
            QPushButton:hover { background: #2980b9; }
            QPushButton:pressed { background: #1a5276; }
        """)
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(start, end))

        load_btn = QPushButton("📥 В поиск")
        load_btn.setFixedHeight(28)
        load_btn.setCursor(Qt.PointingHandCursor)
        load_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60; color: white; border: none;
                border-radius: 4px; font-size: 9pt; padding: 0 8px;
            }
            QPushButton:hover { background: #219a52; }
            QPushButton:pressed { background: #1e8449; }
        """)
        load_btn.clicked.connect(lambda: self.range_selected.emit(start, end))

        layout.addWidget(copy_btn)
        layout.addWidget(load_btn)
        layout.addStretch()
        return container

    def _copy_to_clipboard(self, start: str, end: str):
        QApplication.clipboard().setText(f"{start}\n{end}")
        QMessageBox.information(self, "✅ Скопировано",
                                f"Диапазон скопирован в буфер:\n"
                                f"Начало: {start[:16]}...\n"
                                f"Конец: {end[:16]}...")

    def _apply_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            QMessageBox.warning(self, "⚠️ Выбор", "Выделите строку с диапазоном перед загрузкой.")
            return
        row = sel[0].row()
        start = self.table.item(row, 1).text()
        end = self.table.item(row, 2).text()
        self.range_selected.emit(start, end)
        self.accept()

    def _clear_log(self):
        reply = QMessageBox.question(self, "🗑 Очистка",
                                     "Удалить все записи прогресса?\nЭто действие нельзя отменить.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.log_file_path.exists():
                self.log_file_path.unlink()
            self._load_data()

    @staticmethod
    def log_progress(start_hex: str, end_hex: str, percent: float, gpu_id: int, log_file_path: Path) -> None:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            line = f"{start_hex.zfill(64)}-{end_hex.zfill(64)} {int(percent)}% пройдено GPU{gpu_id}\n"
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")