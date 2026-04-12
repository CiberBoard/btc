from decimal import Decimal, localcontext, ROUND_FLOOR, InvalidOperation
from time import strftime  # 🛠 УЛУЧШЕНИЕ 1: Импорт вынесен в начало (было внутри _log)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QMessageBox, QApplication, QComboBox, QDoubleSpinBox
)
from ui.theme import apply_dark_theme, set_button_style, COLORS

# 🛠 УЛУЧШЕНИЕ 2: Убран глобальный getcontext().prec = 100
# Он менял точность Decimal для всего приложения. Теперь точность задаётся локально в _calculate.

# Порядок кривой secp256k1
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


class HexCalcWindow(QDialog):
    """
    HEX-калькулятор Pro с точной арифметикой для криптографических диапазонов.
    ✅ Decimal-точность + безопасное усечение (floor) + валидация secp256k1
    ✅ Исправлен парсинг: теперь стабильно работает /2, *1.5, +10% и т.д.
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

        header = QLabel("🔢 16-ричный калькулятор (проценты + дробные множители)")
        header.setProperty("cssClass", "header")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        info = QLabel(
            "Форматы: <code>&lt;hex&gt;*1.5</code> | <code>&lt;hex&gt;/2</code> | "
            "<code>&lt;hex&gt;+10%</code> | <code>&lt;hex&gt;-25%</code> | "
            "<code>&lt;hex1&gt;+&lt;hex2&gt;</code><br>"
            "💡 Результат уссекается до целого (floor) и сохраняет длину первого числа"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLORS.get('text_secondary', '#aaaaaa')}; font-size: 9pt;")  # 🛠 УЛУЧШЕНИЕ 3
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

        # Панель пользовательских коэффициентов
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

        # Быстрые операции
        quick_group = QGroupBox("⚡ Быстрые операции")
        quick_layout = QHBoxLayout(quick_group)
        for label, val in [("×1.5", "*1.5"), ("×2", "*2"), ("×2.5", "*2.5"), ("×3", "*3")]:
            btn = QPushButton(label)  # 🛠 УЛУЧШЕНИЕ 4: Убраны лишние точки с запятой
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
        self.result_hex.setStyleSheet(f"background: {COLORS.get('bg_input', '#2b2b2b')}; color: {COLORS.get('accent_primary', '#4CAF50')};")  # 🛠 УЛУЧШЕНИЕ 3
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

        # Лог
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

        close_btn = QPushButton("✖ Закрыть")
        set_button_style(close_btn, "danger")
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn)
        self.input_edit.setFocus()

    def _insert_operator(self):
        btn = self.sender()
        self._insert_to_input(btn.property("op"))

    def _apply_custom_operator(self):
        op_index = self.op_combo.currentIndex()
        val_str = f"{self.custom_value_spin.value():g}"
        suffix = {0: f"*{val_str}", 1: f"/{val_str}", 2: f"+{val_str}%", 3: f"-{val_str}%"}.get(op_index)
        if suffix:
            self._insert_to_input(suffix)

    def _insert_to_input(self, text):
        cursor_pos = self.input_edit.cursorPosition()
        current = self.input_edit.text()
        self.input_edit.setText(current[:cursor_pos] + text + current[cursor_pos:])
        self.input_edit.setFocus()
        self.input_edit.setCursorPosition(cursor_pos + len(text))

    def _calculate(self):
        """Точная арифметика с Decimal, безопасным парсингом и проверкой secp256k1"""
        raw = self.input_edit.text().strip().upper().replace(' ', '')
        if not raw:
            return
        if raw.startswith('0X'):
            raw = raw[2:]

        base_hex = ""
        operand_hex = ""
        op = ""
        result_dec = 0
        parsed = False

        # 🛠 УЛУЧШЕНИЕ 2 (продолжение): Локальный контекст Decimal.
        # Не влияет на другие части приложения, точность изолирована.
        with localcontext() as ctx:
            ctx.prec = 100
            ctx.rounding = ROUND_FLOOR

            try:
                # 1. Проценты: +10%, -25.5%
                if raw.endswith('%'):
                    pct_idx = -1
                    for i in range(len(raw) - 2, 0, -1):
                        if raw[i] in '+-':
                            pct_idx = i
                            break
                    if pct_idx != -1:
                        base_hex = raw[:pct_idx]
                        sign = raw[pct_idx]
                        pct_str = raw[pct_idx + 1:-1]
                        if base_hex and pct_str:
                            val = Decimal(int(base_hex, 16))
                            pct = Decimal(pct_str)
                            factor = Decimal('1') + (pct / Decimal('100')) if sign == '+' else Decimal('1') - (pct / Decimal('100'))
                            result_dec = int((val * factor).to_integral_value(rounding=ROUND_FLOOR))
                            op, operand_hex = f"{sign}{pct_str}%", pct_str
                            parsed = True

                # 2. Умножение/Деление: *1.5, /2, /2.7
                elif '*' in raw or '/' in raw:
                    op_idx = raw.find('/') if '/' in raw else raw.find('*')
                    base_hex = raw[:op_idx]
                    num_str = raw[op_idx + 1:]
                    if base_hex and num_str:
                        val = Decimal(int(base_hex, 16))
                        num = Decimal(num_str)
                        if num == 0:
                            raise ZeroDivisionError("Деление на ноль недопустимо")

                        res_dec = val / num if raw[op_idx] == '/' else val * num
                        result_dec = int(res_dec.to_integral_value(rounding=ROUND_FLOOR))
                        op, operand_hex = raw[op_idx], num_str
                        parsed = True

                # 3. Сложение/Вычитание HEX
                elif '+' in raw:
                    parts = raw.split('+', 1)
                    if len(parts) == 2 and parts[0] and parts[1]:
                        base_hex, operand_hex = parts
                        op = '+'
                        result_dec = int(base_hex, 16) + int(operand_hex, 16)
                        parsed = True
                elif '-' in raw and not raw.startswith('-'):
                    parts = raw.split('-', 1)
                    if len(parts) == 2 and parts[0] and parts[1]:
                        base_hex, operand_hex = parts
                        op = '-'
                        result_dec = int(base_hex, 16) - int(operand_hex, 16)
                        if result_dec < 0:
                            QMessageBox.warning(self, "Отрицательный результат", f"Результат: {result_dec}")
                            return
                        parsed = True

                # 4. Чистая конвертация (если оператор не найден)
                if not parsed:
                    val = int(raw, 16)
                    width = len(raw)
                    is_valid = self._validate_secp256k1(val)
                    self._show_result(raw, f"{val:X}".zfill(width), val, width, valid=is_valid)
                    self._log(f"Конвертация: {raw} → {val}")
                    return

                # Валидация и вывод результата
                is_valid_key = self._validate_secp256k1(result_dec)
                width = len(base_hex)
                res_hex = f"{result_dec:X}"

                if len(res_hex) > width:
                    self._show_result(base_hex, res_hex, result_dec, width, overflow=True, valid=is_valid_key)
                    self._log(f"⚠️ {base_hex} {op}{operand_hex} = {res_hex} (переполнение)")
                else:
                    self._show_result(base_hex, res_hex.zfill(width), result_dec, width, valid=is_valid_key)
                    self._log(f"✅ {base_hex} {op}{operand_hex} = {res_hex.zfill(width)}")

            except ZeroDivisionError as e:
                QMessageBox.warning(self, "Ошибка деления", str(e))
            except (ValueError, InvalidOperation):
                QMessageBox.warning(self, "Ошибка формата",
                                    "Введите корректное выражение.\nПримеры:\n"
                                    "• 00FF*1.5  |  • 0100+10%  |  • 00FF/2")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"{type(e).__name__}: {str(e)}")

    def _validate_secp256k1(self, value: int) -> bool:
        return 1 <= value < SECP256K1_ORDER

    def _show_result(self, original, result_hex, result_dec, width, overflow=False, valid=True):
        # 🛠 УЛУЧШЕНИЕ 3: Безопасный доступ к COLORS.get() с fallback-цветами
        if not valid:
            self.result_hex.setStyleSheet(
                f"background: #4a1a1a; color: {COLORS.get('accent_danger', '#e74c3c')}; font-weight: bold; border: 2px solid #e74c3c;")
            tooltip = "⚠️ Ключ вне диапазона secp256k1 — невалидный приватный ключ!"
        elif overflow:
            self.result_hex.setStyleSheet(f"background: #3d2a1a; color: {COLORS.get('accent_warning', '#f39c12')}; font-weight: bold;")
            tooltip = "⚠️ Результат не помещается в исходную разрядную сетку"
        else:
            self.result_hex.setStyleSheet(
                f"background: {COLORS.get('bg_input', '#2b2b2b')}; color: {COLORS.get('accent_primary', '#4CAF50')}; font-weight: bold;")
            tooltip = "✅ Валидный приватный ключ secp256k1"

        self.result_hex.setText(result_hex)
        self.result_hex.setToolTip(tooltip)
        self.result_dec.setText(f"{result_dec:,}")

        # 🛠 УЛУЧШЕНИЕ 5: Более корректная генерация BIN с учётом ширины
        total_bits = width * 4
        bin_str = bin(result_dec)[2:].zfill(total_bits)
        if len(bin_str) > 256:  # Показываем только начало и конец для очень длинных строк
            bin_str = f"{bin_str[:64]}...{bin_str[-64:]}"
        self.result_bin.setText(bin_str)

        if not valid:
            QMessageBox.warning(
                self, "⚠️ Невалидный ключ",
                f"Результат выходит за пределы диапазона secp256k1.\n"
                f"Допустимый диапазон: 1 — 0x{SECP256K1_ORDER - 1:X}"
            )

    def _copy_result(self):
        text = self.result_hex.text().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._log(f"📋 Скопировано: {text[:32]}{'...' if len(text) > 32 else ''}")

    def _log(self, message: str):
        timestamp = strftime("[%H:%M:%S]")  # 🛠 УЛУЧШЕНИЕ 1: Теперь импорт в начале файла
        # 🛠 УЛУЧШЕНИЕ 3: Безопасный доступ к словарю цветов
        color = COLORS.get('text_secondary', '#888888')
        self.log_output.append(f'<span style="color:{color};">{timestamp} {message}</span>')
        scrollbar = self.log_output.verticalScrollBar()
        if scrollbar: scrollbar.setValue(scrollbar.maximum())