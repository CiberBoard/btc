# utils/random_range_dialog.py
"""
Диалог генерации случайного диапазона приватных ключей Bitcoin.
"""
from __future__ import annotations

import secrets
import platform
import logging
from typing import Tuple, Optional, Callable

import config
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QApplication, QWidget
)
logger = logging.getLogger(__name__)


class RandomRangeDialog(QDialog):
    """
    Диалог для генерации и отображения случайного диапазона ключей.
    Использует криптографически стойкий генератор (secrets).
    """

    # 🔹 Константы
    MAX_KEY_INT = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140
    DEFAULT_MIN_DISTANCE = 2_000_000_000  # 2 млрд ключей

    def __init__(
            self,
            parent: Optional[QWidget] = None,
            global_start_hex: str = "1",
            global_end_hex: str = "",
            min_distance_callback: Optional[Callable[[], int]] = None,
            on_apply_callback: Optional[Callable[[str, str], None]] = None,
            on_log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        super().__init__(parent)

        # 🔹 Безопасный фоллбэк для config без проверки globals()
        self.global_start_hex = global_start_hex.strip() or "1"
        self.global_end_hex = global_end_hex.strip() or getattr(config, "MAX_KEY_HEX",
                                                                "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140")

        # 🔹 Преобразуем в int один раз при инициализации
        try:
            self._global_start = int(self.global_start_hex, 16)
            self._global_end = int(self.global_end_hex, 16)
        except ValueError as e:
            raise ValueError(f"Некорректный HEX-диапазон: {e}") from e

        self.min_distance_callback = min_distance_callback
        self.on_apply_callback = on_apply_callback
        self.on_log_callback = on_log_callback

        # Текущие значения диапазона
        self.current_start_hex: str = ""
        self.current_end_hex: str = ""
        self.current_start_int: int = 0
        self.current_end_int: int = 0

        self._setup_ui()
        self._setup_shortcuts()
        self._generate_and_display()

    def _setup_shortcuts(self) -> None:
        """Горячие клавиши для ускорения работы."""
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self._on_apply)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.reject)

    def _setup_ui(self) -> None:
        self.setWindowTitle("🎲 Случайный диапазон")
        self.setMinimumWidth(550)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title = QLabel("<b>✅ Диапазон сгенерирован</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 14pt; color: #2ecc71; padding: 10px;")
        layout.addWidget(title)

        # Поля ввода
        self._add_hex_field("🔹 Начало диапазона (hex):", "start")
        self._add_hex_field("🔹 Конец диапазона (hex):", "end")

        # Информация
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 12px; background: #34495e; border-radius: 6px; color: #ecf0f1;")
        layout.addWidget(self.info_label)

        # Кнопки копирования
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._add_copy_button(btn_layout, "📋 Копировать начало", "start")
        self._add_copy_button(btn_layout, "📋 Копировать конец", "end")
        self._add_copy_button(btn_layout, "📋 Копировать оба", "both")

        layout.addLayout(btn_layout)

        # 🔁 Кнопка регенерации
        self.regenerate_btn = QPushButton("🔄 Ещё раз")
        self.regenerate_btn.setStyleSheet("""
            QPushButton { background: #16a085; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }
            QPushButton:hover { background: #1abc9c; }
            QPushButton:pressed { background: #138d75; }
        """)
        self.regenerate_btn.setToolTip("Сгенерировать новый случайный диапазон с теми же параметрами")
        self.regenerate_btn.clicked.connect(self._on_regenerate)
        layout.addWidget(self.regenerate_btn)

        # Кнопка применить
        apply_btn = QPushButton("✅ Применить в поля ввода (Enter)")
        apply_btn.setStyleSheet(
            "background: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(apply_btn)

        # Кнопка закрыть
        close_btn = QPushButton("Закрыть (Esc)")
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet("padding: 8px;")
        layout.addWidget(close_btn)

    def _add_hex_field(self, label_text: str, role: str) -> None:
        """Вспомогательный метод для создания полей HEX."""
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label_text))
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setFont(QFont("Consolas", 9))
        edit.setStyleSheet("background: #2c3e50; color: #ecf0f1; padding: 8px; border-radius: 4px;")
        edit.setProperty("role", role)
        layout.addWidget(edit)
        self.layout().addLayout(layout)
        setattr(self, f"{role}_edit", edit)

    def _add_copy_button(self, parent_layout: QHBoxLayout, text: str, target: str) -> None:
        """Вспомогательный метод для кнопок копирования."""
        btn = QPushButton(text)
        btn.setStyleSheet(
            "background: #3498db; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")

        if target == "start":
            btn.clicked.connect(lambda: QApplication.clipboard().setText(self.start_edit.text()))
        elif target == "end":
            btn.clicked.connect(lambda: QApplication.clipboard().setText(self.end_edit.text()))
        else:
            btn.clicked.connect(lambda: QApplication.clipboard().setText(
                f"{self.start_edit.text()}\n{self.end_edit.text()}"
            ))
        parent_layout.addWidget(btn)

    def _get_min_distance(self) -> int:
        """Получает минимальную дистанцию из коллбэка или дефолт."""
        if self.min_distance_callback:
            try:
                return self.min_distance_callback()
            except Exception as e:
                logger.warning(f"Ошибка получения мин. дистанции: {e}")
        return self.DEFAULT_MIN_DISTANCE

    def _generate_range(self) -> Tuple[str, str, int, int]:
        """Генерирует случайный диапазон ключей (криптографически стойкий)."""
        min_dist = self._get_min_distance()

        if self._global_end - self._global_start < min_dist:
            raise ValueError(
                f"Глобальный диапазон слишком мал!\n"
                f"Требуется минимум {min_dist:,} ключей (0x{min_dist:X})"
            )

        max_start = self._global_end - min_dist
        range_size = max_start - self._global_start + 1

        # 🔹 Современный крипто-генератор (универсальный для всех ОС)
        random_start = self._global_start + secrets.randbelow(range_size)
        random_end = min(random_start + min_dist, self.MAX_KEY_INT)

        start_formatted = hex(random_start)[2:].upper().zfill(64)
        end_formatted = hex(random_end)[2:].upper().zfill(64)

        return start_formatted, end_formatted, random_start, random_end

    def _update_display(self, start_hex: str, end_hex: str, start_int: int, end_int: int) -> None:
        """Обновляет отображение в диалоге с анимацией."""
        self.current_start_hex, self.current_end_hex = start_hex, end_hex
        self.current_start_int, self.current_end_int = start_int, end_int

        self.start_edit.setText(start_hex)
        self.end_edit.setText(end_hex)

        # Анимация подсветки
        highlight = "background: #27ae60; color: white; padding: 8px; border-radius: 4px;"
        default = "background: #2c3e50; color: #ecf0f1; padding: 8px; border-radius: 4px;"
        self.start_edit.setStyleSheet(highlight)
        self.end_edit.setStyleSheet(highlight)
        QTimer.singleShot(300, lambda: self.start_edit.setStyleSheet(default))
        QTimer.singleShot(300, lambda: self.end_edit.setStyleSheet(default))

        min_dist = self._get_min_distance()
        self.info_label.setText(
            f"📊 Дистанция: <b>{min_dist:,}</b> ключей (0x{min_dist:X})<br>"
            f"🔐 В десятичном: {start_int:,} — {end_int:,}"
        )

    def _on_regenerate(self) -> None:
        """Обработчик кнопки регенерации."""
        try:
            start_hex, end_hex, start_int, end_int = self._generate_range()
            self._update_display(start_hex, end_hex, start_int, end_int)
            if self.on_log_callback:
                self.on_log_callback(f"🔄 Сгенерирован новый диапазон: {start_hex[:16]}... — {end_hex[:16]}...",
                                     "success")
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка диапазона", str(e))
        except Exception as e:
            logger.exception("Ошибка регенерации диапазона")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать: {type(e).__name__}: {e}")

    def _on_apply(self) -> None:
        """Обработчик кнопки применения."""
        if self.on_apply_callback and self.current_start_hex and self.current_end_hex:
            self.on_apply_callback(self.current_start_hex, self.current_end_hex)
        self.accept()

    def _generate_and_display(self) -> None:
        """Первичная генерация при открытии диалога."""
        try:
            start_hex, end_hex, start_int, end_int = self._generate_range()
            self._update_display(start_hex, end_hex, start_int, end_int)
            if self.on_log_callback:
                self.on_log_callback(f"🎲 Сгенерирован случайный диапазон: {start_hex[:16]}... — {end_hex[:16]}...",
                                     "success")
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            self.reject()
        except Exception as e:
            logger.exception("Ошибка генерации диапазона")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сгенерировать: {type(e).__name__}: {e}")
            self.reject()

    def get_result(self) -> Optional[Tuple[str, str]]:
        """Возвращает результат (start_hex, end_hex) или None если отменено."""
        if self.result() == QDialog.DialogCode.Accepted:
            return self.current_start_hex, self.current_end_hex
        return None


def show_random_range_dialog(
        parent: Optional[QWidget],
        global_start_hex: str = "1",
        global_end_hex: str = "",
        min_distance: int = 2_000_000_000,
) -> Optional[Tuple[str, str]]:
    """Удобная функция-обёртка для быстрого вызова диалога."""
    dialog = RandomRangeDialog(
        parent=parent,
        global_start_hex=global_start_hex,
        global_end_hex=global_end_hex,
        min_distance_callback=lambda: min_distance,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_result()
    return None