# ui/gpu_progress_tracker.py
import re
import logging
from pathlib import Path
# В начало файла добавьте:
from functools import partial  # 👈 ДОБАВИТЬ
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QAbstractItemView,
                             QTableWidgetItem, QPushButton, QLabel, QMessageBox,
                             QHeaderView, QApplication, QWidget, QFrame, QLineEdit, QComboBox, QSpinBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

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
        title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #E0E0E0;")

        self.stats_label = QLabel("Записей: 0")
        self.stats_label.setStyleSheet("color: #888; font-size: 10pt; font-weight: 500;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)
        main_layout.addLayout(header_layout)

        # Разделитель
        sep = QFrame()
        # ✅ Стало (PyQt6)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("background: #3A3A4A; margin: 4px 0;")
        main_layout.addWidget(sep)

        # ── Таблица ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["GPU", "Начало (HEX)", "Конец (HEX)", "Прогресс", "Действия"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 210)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setStyleSheet(self._table_style())
        # Контекстное меню для таблицы
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Double-click для быстрой загрузки
        self.table.doubleClicked.connect(self._apply_selected)
        main_layout.addWidget(self.table)

        # ── Панель фильтров ──
        main_layout.addLayout(self._setup_filters())

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
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def _setup_filters(self):
        """Панель фильтров для таблицы"""
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # 🔍 Поиск по HEX
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Поиск по HEX...")
        self.search_edit.textChanged.connect(self._filter_table)
        self.search_edit.setFixedWidth(220)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background: #2A2A3A; border: 1px solid #3A3A4A;
                border-radius: 4px; color: #E0E0E0; padding: 4px 8px;
            }
            QLineEdit:focus { border-color: #5B8CFF; }
        """)

        # 🎛 Фильтр по GPU
        self.gpu_filter = QComboBox()
        self.gpu_filter.addItem("Все GPU")
        self.gpu_filter.addItems([f"GPU {i}" for i in range(8)])
        self.gpu_filter.currentTextChanged.connect(self._filter_table)
        self.gpu_filter.setFixedWidth(100)
        self.gpu_filter.setStyleSheet("""
            QComboBox {
                background: #2A2A3A; border: 1px solid #3A3A4A;
                border-radius: 4px; color: #E0E0E0; padding: 4px 8px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1E1E2E; color: #E0E0E0; }
        """)

        # 📊 Минимальный прогресс
        self.min_progress = QSpinBox()
        self.min_progress.setRange(0, 100)
        self.min_progress.setSuffix("%")
        self.min_progress.setValue(0)
        self.min_progress.valueChanged.connect(self._filter_table)
        self.min_progress.setFixedWidth(70)

        filter_layout.addWidget(QLabel("Фильтры:"))
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(self.gpu_filter)
        filter_layout.addWidget(QLabel("Мин:"))
        filter_layout.addWidget(self.min_progress)
        filter_layout.addStretch()

        return filter_layout

    def _filter_table(self):
        """Фильтрация записей по поиску и параметрам"""
        search = self.search_edit.text().lower()
        gpu_filter = self.gpu_filter.currentText()
        min_percent = self.min_progress.value()

        for row in range(self.table.rowCount()):
            # Получаем данные
            item_gpu = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            item_start = self.table.item(row, 1).text().lower() if self.table.item(row, 1) else ""
            item_end = self.table.item(row, 2).text().lower() if self.table.item(row, 2) else ""
            item_percent_text = self.table.item(row, 3).text() if self.table.item(row, 3) else "0%"
            item_percent = int(item_percent_text.replace('%', ''))

            # Проверяем условия
            match_search = not search or (search in item_start or search in item_end)
            match_gpu = (gpu_filter == "Все GPU" or item_gpu == gpu_filter)
            match_percent = item_percent >= min_percent

            # Показываем/скрываем строку
            self.table.setRowHidden(row, not (match_search and match_gpu and match_percent))

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
        """Загрузка и отображение данных из файла прогресса"""
        self.table.setRowCount(0)

        if not self.log_file_path.exists():
            self.stats_label.setText("Записей: 0")
            return

        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            pattern = re.compile(
                r"([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+(\d+)%\s+пройдено\s+GPU\s*(\d+)",
                re.IGNORECASE
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

            # 🔧 Автоочистка дубликатов при большом количестве записей
            if count > 1000:
                self._cleanup_duplicates()

        except Exception as e:
            logger.error(f"Ошибка загрузки прогресса: {e}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")
            self.stats_label.setText("Записей: 0")



    def _set_item(self, row: int, col: int, text: str):
        """Создание элемента таблицы с улучшенными tooltip"""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        if col in (1, 2):  # HEX колонки
            # 🔧 Полный HEX в tooltip с переносом
            item.setToolTip(f"Полный HEX:\n{text}")
            # 🔧 Сохраняем полный HEX в UserRole для копирования
            item.setData(Qt.ItemDataRole.UserRole, text)

        self.table.setItem(row, col, item)

    def _create_action_row(self, start: str, end: str) -> QWidget:
        container = QWidget()
        # 👇 Важно для PyQt6: устанавливаем атрибут для безопасного удаления
        container.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        copy_btn = QPushButton("📋 Копировать")
        copy_btn.setFixedHeight(28)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #3498db; color: white; border: none;
                border-radius: 4px; font-size: 9pt; padding: 0 8px;
            }
            QPushButton:hover { background: #2980b9; }
            QPushButton:pressed { background: #1a5276; }
        """)
        # ✅ ИСПРАВЛЕНО: partial вместо lambda — безопасный захват аргументов
        copy_btn.clicked.connect(partial(self._copy_to_clipboard, start, end))

        load_btn = QPushButton("📥 В поиск")
        load_btn.setFixedHeight(28)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60; color: white; border: none;
                border-radius: 4px; font-size: 9pt; padding: 0 8px;
            }
            QPushButton:hover { background: #219a52; }
            QPushButton:pressed { background: #1e8449; }
        """)
        # ✅ ИСПРАВЛЕНО: partial для сигнала с аргументами
        load_btn.clicked.connect(partial(lambda s, e: self.range_selected.emit(s, e), start, end))

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
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.log_file_path.exists():
                self.log_file_path.unlink()
            self._load_data()

    def _cleanup_duplicates(self):
        """
        Оставляет только последнюю запись с максимальным % для каждого уникального диапазона.
        Вызывается после загрузки данных при большом количестве записей (>1000).
        """
        if self.table.rowCount() == 0:
            return

        # Словарь: (start, end, gpu_id) -> (row_index, max_percent)
        best_entries = {}

        # Проходим по всем строкам и находим лучший прогресс для каждого диапазона
        for row in range(self.table.rowCount()):
            item_start = self.table.item(row, 1)
            item_end = self.table.item(row, 2)
            item_gpu = self.table.item(row, 0)
            item_percent = self.table.item(row, 3)

            # Пропускаем строки с пустыми ячейками
            if not all([item_start, item_end, item_gpu, item_percent]):
                continue

            start = item_start.text()
            end = item_end.text()
            gpu = item_gpu.text()
            percent = int(item_percent.text().replace('%', ''))

            key = (start, end, gpu)

            # Сохраняем строку если её ещё нет ИЛИ если прогресс больше
            if key not in best_entries or percent > best_entries[key][1]:
                best_entries[key] = (row, percent)

        # Собираем индексы строк для удаления (все КРОМЕ лучших)
        rows_to_keep = {info[0] for info in best_entries.values()}
        rows_to_delete = [r for r in range(self.table.rowCount()) if r not in rows_to_keep]

        # Удаляем в обратном порядке (чтобы индексы не сдвигались при удалении)
        for row in sorted(rows_to_delete, reverse=True):
            self.table.removeRow(row)

        # Обновляем статистику
        cleaned_count = len(rows_to_delete)
        self.stats_label.setText(f"Записей: {self.table.rowCount()} (очищено {cleaned_count})")
        logger.info(f"🧹 Очищено {cleaned_count} дубликатов прогресса, осталось {self.table.rowCount()} записей")


    def keyPressEvent(self, event):
        """Обработка горячих клавиш"""
        if event.key() == Qt.Key.Key_Return and self.table.selectedItems():
            self._apply_selected()  # Enter = загрузить в поиск
        elif event.key() == Qt.Key.Key_F5:
            self._load_data()  # F5 = обновить
        elif event.key() == Qt.Key.Key_Delete and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._clear_log()  # Ctrl+Del = очистить лог
        else:
            super().keyPressEvent(event)

    def _show_context_menu(self, pos):
        """Контекстное меню для строки таблицы"""
        menu = QMenu()

        # Действия
        load_action = menu.addAction("📥 Загрузить в поиск")
        copy_action = menu.addAction("📋 Копировать диапазон")
        menu.addSeparator()
        delete_action = menu.addAction("🗑 Удалить запись")

        action = menu.exec(self.table.mapToGlobal(pos))

        if not self.table.selectedItems():
            return

        row = self.table.selectedItems()[0].row()

        if action == load_action:
            self._apply_selected()
        elif action == copy_action:
            start = self.table.item(row, 1).text()
            end = self.table.item(row, 2).text()
            self._copy_to_clipboard(start, end)
        elif action == delete_action:
            self._delete_row(row)

    def _delete_row(self, row: int):
        """Удаление строки из таблицы и лога"""
        # Получаем данные для удаления из файла
        start = self.table.item(row, 1).text()
        end = self.table.item(row, 2).text()
        gpu_id = self.table.item(row, 0).text().replace("GPU ", "")

        # Удаляем из UI
        self.table.removeRow(row)

        # Перезаписываем лог без этой строки
        if self.log_file_path.exists():
            pattern = re.compile(
                rf"{re.escape(start)}-{re.escape(end)}\s+\d+%\s+пройдено\s+GPU\s*{re.escape(gpu_id)}",
                re.IGNORECASE
            )
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if not pattern.search(line):
                        f.write(line)

            self.stats_label.setText(f"Записей: {self.table.rowCount()}")

    @staticmethod
    def log_progress(start_hex: str, end_hex: str, percent: float, gpu_id: int, log_file_path: Path) -> None:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            line = f"{start_hex.zfill(64)}-{end_hex.zfill(64)} {int(percent)}% пройдено GPU{gpu_id}\n"

            # 📦 Буферизированная запись (уменьшает количество системных вызовов)
            with open(log_file_path, 'a', encoding='utf-8', buffering=8192) as f:
                f.write(line)
                f.flush()  # Гарантируем запись, но не слишком часто
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")