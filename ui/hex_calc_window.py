# ui/hex_calc_window.py
import re
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QMessageBox, QApplication, QComboBox, QDoubleSpinBox
)
from ui.theme import apply_dark_theme, set_button_style, COLORS


class HexCalcWindow(QDialog):
    """
    HEX-калькулятор Pro с поддержкой:
    • Кастомные множители/делители (*1.5, /2.7)
    • Процентные изменения (+10%, -25%)
    • Сложение/вычитание двух HEX
    • Сохранение длины и ведущих нулей
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔢 HEX Calculator Pro")
        self.resize(800, 580)
        self.setMinimumSize(680, 480)

        apply_dark_theme(self)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # Заголовок
        header = QLabel("🔢 16-ричный калькулятор (проценты + дробные множители)")
        header.setProperty("cssClass", "header")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # Инструкция
        info = QLabel(
            "Форматы: <code>&lt;hex&gt;*1.5</code> | <code>&lt;hex&gt;/2.7</code> | "
            "<code>&lt;hex&gt;+10%</code> | <code>&lt;hex&gt;-25%</code> | "
            "<code>&lt;hex1&gt;+&lt;hex2&gt;</code><br>"
            "💡 Результат сохраняет длину первого числа (нули не обрезаются)"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 9pt;")
        main_layout.addWidget(info)

        # Поле ввода
        input_group = QGroupBox("📥 Ввод выражения")
        input_layout = QHBoxLayout(input_group)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Например: 000...07*1.5  или  00FF+10%")
        self.input_edit.setFont(QFont("Consolas", 10))
        self.input_edit.returnPressed.connect(self._calculate)
        input_layout.addWidget(self.input_edit)

        self.calc_btn = QPushButton("⚡ Вычислить")
        set_button_style(self.calc_btn, "success")
        self.calc_btn.setFixedWidth(120)
        self.calc_btn.clicked.connect(self._calculate)
        input_layout.addWidget(self.calc_btn)

        main_layout.addWidget(input_group)

        # ─────────────────────────────────────────────────────
        # НОВОЕ: Панель пользовательских коэффициентов
        # ─────────────────────────────────────────────────────
        custom_group = QGroupBox("🎛️ Пользовательский коэффициент / процент")
        custom_layout = QHBoxLayout(custom_group)

        self.op_combo = QComboBox()
        self.op_combo.addItems(["× Умножить", "÷ Разделить", "+% Добавить %", "-% Уменьшить %"])
        self.op_combo.setFixedWidth(140)
        custom_layout.addWidget(self.op_combo)

        self.custom_value_spin = QDoubleSpinBox()
        self.custom_value_spin.setRange(0.0001, 100000.0)
        self.custom_value_spin.setDecimals(4)
        self.custom_value_spin.setValue(1.5)
        self.custom_value_spin.setFixedWidth(130)
        self.custom_value_spin.setButtonSymbols(QDoubleSpinBox.PlusMinus)
        custom_layout.addWidget(self.custom_value_spin)

        self.apply_custom_btn = QPushButton("➕ Вставить в формулу")
        self.apply_custom_btn.setFixedWidth(160)
        self.apply_custom_btn.clicked.connect(self._apply_custom_operator)
        custom_layout.addWidget(self.apply_custom_btn)

        custom_layout.addStretch()
        main_layout.addWidget(custom_group)

        # Панель быстрых операций
        quick_group = QGroupBox("⚡ Быстрые операции")
        quick_layout = QHBoxLayout(quick_group)

        for label, val in [("×1.5", "*1.5"), ("×2", "*2"), ("×2.5", "*2.5"), ("×3", "*3")]:
            btn = QPushButton(label)
            btn.setFixedWidth(65)
            btn.setProperty("op", val)
            btn.clicked.connect(self._insert_operator)
            quick_layout.addWidget(btn)

        quick_layout.addStretch()

        for label, val in [("÷1.5", "/1.5"), ("÷2", "/2"), ("÷2.5", "/2.5"), ("÷3", "/3")]:
            btn = QPushButton(label)
            btn.setFixedWidth(65)
            btn.setProperty("op", val)
            btn.clicked.connect(self._insert_operator)
            quick_layout.addWidget(btn)

        quick_layout.addStretch()

        for label, val in [("+10%", "+10%"), ("+25%", "+25%"), ("-10%", "-10%"), ("-25%", "-25%")]:
            btn = QPushButton(label)
            btn.setFixedWidth(65)
            btn.setProperty("op", val)
            btn.clicked.connect(self._insert_operator)
            quick_layout.addWidget(btn)

        main_layout.addWidget(quick_group)

        # Результат
        result_group = QGroupBox("✅ Результат")
        result_layout = QGridLayout(result_group)

        result_layout.addWidget(QLabel("HEX:"), 0, 0)
        self.result_hex = QLineEdit()
        self.result_hex.setReadOnly(True)
        self.result_hex.setFont(QFont("Consolas", 11, QFont.Bold))
        self.result_hex.setStyleSheet(f"background: {COLORS['bg_input']}; color: {COLORS['accent_primary']};")
        result_layout.addWidget(self.result_hex, 0, 1)

        result_layout.addWidget(QLabel("DEC:"), 1, 0)
        self.result_dec = QLineEdit()
        self.result_dec.setReadOnly(True)
        self.result_dec.setFont(QFont("Consolas", 9))
        result_layout.addWidget(self.result_dec, 1, 1)

        result_layout.addWidget(QLabel("BIN:"), 2, 0)
        self.result_bin = QLineEdit()
        self.result_bin.setReadOnly(True)
        self.result_bin.setFont(QFont("Consolas", 8))
        result_layout.addWidget(self.result_bin, 2, 1)

        copy_btn = QPushButton("📋 Копировать HEX")
        copy_btn.clicked.connect(self._copy_result)
        result_layout.addWidget(copy_btn, 3, 0, 1, 2)

        main_layout.addWidget(result_group)

        # Лог операций
        log_group = QGroupBox("📜 История")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 9))
        self.log_output.setMaximumHeight(120)
        log_layout.addWidget(self.log_output)

        clear_log_btn = QPushButton("🗑 Очистить историю")
        clear_log_btn.setFixedWidth(150)
        clear_log_btn.clicked.connect(lambda: self.log_output.clear())
        log_layout.addWidget(clear_log_btn)
        log_layout.addStretch()

        main_layout.addWidget(log_group)

        # Кнопка закрытия
        close_btn = QPushButton("✖ Закрыть")
        set_button_style(close_btn, "danger")
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)

        self.input_edit.setFocus()

    def _insert_operator(self):
        """Вставка оператора в поле ввода в позицию курсора"""
        btn = self.sender()
        op = btn.property("op")
        self._insert_to_input(op)

    def _apply_custom_operator(self):
        """Форматирование и вставка пользовательского коэффициента/процента"""
        op_index = self.op_combo.currentIndex()
        value = self.custom_value_spin.value()

        # Форматируем число: убираем лишние нули (1.5000 → 1.5)
        val_str = f"{value:g}"

        if op_index == 0:
            suffix = f"*{val_str}"
        elif op_index == 1:
            suffix = f"/{val_str}"
        elif op_index == 2:
            suffix = f"+{val_str}%"
        else:
            suffix = f"-{val_str}%"

        self._insert_to_input(suffix)

    def _insert_to_input(self, text):
        """Универсальная вставка текста в поле ввода"""
        cursor_pos = self.input_edit.cursorPosition()
        current = self.input_edit.text()
        self.input_edit.setText(current[:cursor_pos] + text + current[cursor_pos:])
        self.input_edit.setFocus()
        self.input_edit.setCursorPosition(cursor_pos + len(text))

    def _calculate(self):
        """Основная логика вычислений"""
        raw = self.input_edit.text().strip().upper().replace(' ', '')
        if not raw:
            return

        if raw.startswith('0X'):
            raw = raw[2:]

        op = None
        base_hex = ""
        operand_hex = ""
        result_dec = 0

        try:
            # ── 1. Процентные операции: +10%, -25.5% ──────────────────
            percent_match = re.match(r'^(.+?)([+-])(\d+\.?\d*)%$', raw)
            if percent_match:
                base_hex, sign, percent_str = percent_match.groups()
                if not base_hex: raise ValueError
                percent = float(percent_str)
                value = int(base_hex, 16)
                factor = 1 + percent / 100 if sign == '+' else 1 - percent / 100
                result_dec = int(value * factor)
                op = f"{sign}{percent}%"
                operand_hex = f"{percent}%"

            # ── 2. Кастомные множители/делители: *1.5, /2.7 ─────────
            elif re.match(r'^(.+?)[*/]\d+\.?\d*$', raw):
                mult_match = re.match(r'^(.+?)([*\/])(\d+\.?\d*)$', raw)
                if mult_match:
                    base_hex, op_sym, num_str = mult_match.groups()
                    if not base_hex: raise ValueError
                    num = float(num_str)
                    if num == 0:
                        raise ZeroDivisionError("Деление на ноль недопустимо")
                    value = int(base_hex, 16)
                    if op_sym == '*':
                        result_dec = int(value * num)
                        op = '*'
                    else:
                        result_dec = int(value / num)
                        op = '/'
                    operand_hex = num_str

            # ── 3. Сложение/вычитание двух HEX: 00FF+1A ─────────────
            elif '+' in raw and '%' not in raw:
                parts = raw.split('+', 1)
                if len(parts) == 2:
                    base_hex, operand_hex = parts
                    if base_hex and operand_hex:
                        op = '+'
                        result_dec = int(base_hex, 16) + int(operand_hex, 16)

            elif '-' in raw and '%' not in raw:
                parts = raw.split('-', 1)
                if len(parts) == 2:
                    base_hex, operand_hex = parts
                    if base_hex and operand_hex:
                        op = '-'
                        result_dec = int(base_hex, 16) - int(operand_hex, 16)
                        if result_dec < 0:
                            QMessageBox.warning(self, "Отрицательный результат",
                                                f"Результат: {result_dec} (в unsigned HEX не отображается)")
                            return

            # ── 4. Просто конвертация ───────────────────────────────
            else:
                val = int(raw, 16)
                width = len(raw)
                self._show_result(raw, f"{val:X}".zfill(width), val, width)
                self._log(f"Конвертация: {raw} → {val}")
                return

            # ── Форматирование результата ───────────────────────────
            width = len(base_hex)
            res_hex = f"{result_dec:X}"

            if len(res_hex) > width:
                self._show_result(base_hex, res_hex, result_dec, width, overflow=True)
                self._log(f"⚠️ {base_hex} {op}{operand_hex} = {res_hex} (переполнение)")
            else:
                final_res = res_hex.zfill(width)
                self._show_result(base_hex, final_res, result_dec, width)
                self._log(f"✅ {base_hex} {op}{operand_hex} = {final_res}")

        except ZeroDivisionError as e:
            QMessageBox.warning(self, "Ошибка деления", str(e))
        except ValueError:
            QMessageBox.warning(self, "Ошибка формата",
                                "Введите корректное выражение.\nПримеры:\n"
                                "• 00FF*1.5  (умножить на 1.5)\n"
                                "• 0100+10%  (увеличить на 10%)\n"
                                "• 00FF-25%  (уменьшить на 25%)\n"
                                "• 00FF+1A   (сложить два HEX)")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _show_result(self, original, result_hex, result_dec, width, overflow=False):
        """Отображение результата в полях"""
        if overflow:
            self.result_hex.setStyleSheet(f"background: #3d1a1a; color: {COLORS['accent_danger']}; font-weight: bold;")
        else:
            self.result_hex.setStyleSheet(
                f"background: {COLORS['bg_input']}; color: {COLORS['accent_primary']}; font-weight: bold;")

        self.result_hex.setText(result_hex)
        self.result_dec.setText(f"{result_dec:,}")

        bin_str = bin(result_dec)[2:].zfill(width * 4)
        if len(bin_str) > 128:
            bin_str = bin_str[:64] + "..." + bin_str[-64:]
        self.result_bin.setText(bin_str)

    def _copy_result(self):
        """Копирование результата в буфер обмена"""
        text = self.result_hex.text().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._log(f"📋 Скопировано: {text[:32]}{'...' if len(text) > 32 else ''}")

    def _log(self, message: str):
        """Добавление в лог"""
        from time import strftime
        timestamp = strftime("[%H:%M:%S]")
        self.log_output.append(f'<span style="color:{COLORS["text_secondary"]};">{timestamp} {message}</span>')
        scrollbar = self.log_output.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())