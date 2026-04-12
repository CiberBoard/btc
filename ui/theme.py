# ui/theme.py
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints и документация
from typing import Dict, Optional
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QPushButton

# 🛠 УЛУЧШЕНИЕ 2: Типизация словаря цветов через Dict[str, str]
COLORS: Dict[str, str] = {
    'bg_main': '#14141E',
    'bg_card': '#1C1C28',
    'bg_input': '#232332',
    'bg_hover': '#2A2A3A',
    'bg_pressed': '#1A1A28',

    'text_primary': '#F0F0F8',
    'text_secondary': '#B0B0C0',
    'text_disabled': '#666680',

    'accent_primary': '#5B8CFF',
    'accent_success': '#2ECC71',
    'accent_warning': '#F39C12',
    'accent_danger': '#E74C3C',
    'accent_vanity': '#9B59B6',
    'accent_predict': '#8E44AD',

    'border': '#3A3A4A',
    'border_focus': '#5B8CFF',
    'grid_line': '#2A2A3A',
}

# 🛠 УЛУЧШЕНИЕ 3: Константы для часто используемых градиентов
_GRADIENT_BTN = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {start}, stop:1 {end})"
_GRADIENT_CHUNK = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {start}, stop:1 {end})"


def _get_color(key: str, fallback: str = '#888888') -> str:
    """🛠 УЛУЧШЕНИЕ 4: Вспомогательная функция для безопасного получения цвета"""
    return COLORS.get(key, fallback)


def apply_dark_theme(window: QWidget) -> None:
    """
    Применяет расширенную тёмную тему к окну приложения.

    :param window: Экземпляр QMainWindow или QWidget для применения темы
    """
    try:
        # 1️⃣ Палитра для нативных виджетов
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(_get_color('bg_main')))
        palette.setColor(QPalette.WindowText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.Base, QColor(_get_color('bg_input')))
        palette.setColor(QPalette.AlternateBase, QColor('#252535'))
        palette.setColor(QPalette.ToolTipBase, QColor(_get_color('bg_card')))
        palette.setColor(QPalette.ToolTipText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.Text, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.Button, QColor(_get_color('bg_card')))
        palette.setColor(QPalette.ButtonText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.BrightText, QColor(_get_color('accent_danger')))
        palette.setColor(QPalette.Link, QColor(_get_color('accent_primary')))
        palette.setColor(QPalette.Highlight, QColor(_get_color('accent_primary')))
        palette.setColor(QPalette.HighlightedText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.PlaceholderText, QColor(_get_color('text_secondary')))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(_get_color('text_disabled')))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(_get_color('text_disabled')))

        window.setPalette(palette)
        window.setAutoFillBackground(True)

        # 2️⃣ StyleSheet для кастомных стилей
        # 🛠 УЛУЧШЕНИЕ 5: Использование _get_color() для всех обращений к COLORS
        window.setStyleSheet(f"""
            /* ========== БАЗОВЫЕ НАСТРОЙКИ ========== */
            QWidget {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_primary')};
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                font-size: 9pt;
            }}

            /* ========== ВКЛАДКИ ========== */
            QTabWidget::pane {{
                border: 1px solid {_get_color('border')};
                border-radius: 6px;
                background: {_get_color('bg_card')};
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_secondary')};
                border: 1px solid transparent;
                border-bottom: 2px solid transparent;
                padding: 8px 24px;
                min-width: 100px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border-bottom-color: {_get_color('accent_primary')};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background: {_get_color('bg_hover')};
                color: {_get_color('text_primary')};
            }}

            /* ========== ГРУППЫ (QGroupBox) ========== */
            QGroupBox {{
                border: 1px solid {_get_color('border')};
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 20px;
                background: {_GRADIENT_BTN.format(start=_get_color('bg_card'), end=_get_color('bg_main'))};
                font-weight: bold;
                color: {_get_color('text_primary')};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 8px;
                color: {_get_color('accent_primary')};
                background: transparent;
            }}

            /* ========== КНОПКИ ========== */
            QPushButton {{
                background: {_GRADIENT_BTN.format(start=_get_color('bg_card'), end=_get_color('bg_input'))};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: 500;
                min-height: 36px;
            }}
            QPushButton:hover {{
                background: {_GRADIENT_BTN.format(start=_get_color('bg_hover'), end=_get_color('bg_card'))};
                border-color: {_get_color('accent_primary')};
            }}
            QPushButton:pressed {{
                background: {_get_color('bg_pressed')};
                border-color: {_get_color('accent_primary')};
            }}
            QPushButton:disabled {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_disabled')};
                border-color: {_get_color('border')};
            }}

            /* Типы кнопок */
            QPushButton[cssClass="primary"] {{
                background: {_GRADIENT_BTN.format(start=_get_color('accent_primary'), end='#4A7ACC')};
                color: white;
                border: none;
                font-weight: bold;
            }}
            QPushButton[cssClass="primary"]:hover {{
                background: {_GRADIENT_BTN.format(start='#6B9CFF', end=_get_color('accent_primary'))};
            }}
            QPushButton[cssClass="success"] {{
                background: {_GRADIENT_BTN.format(start=_get_color('accent_success'), end='#27AE60')};
                color: white; border: none; font-weight: bold;
            }}
            QPushButton[cssClass="warning"] {{
                background: {_GRADIENT_BTN.format(start=_get_color('accent_warning'), end='#E67E22')};
                color: black; border: none; font-weight: bold;
            }}
            QPushButton[cssClass="vanity"] {{
                background: {_GRADIENT_BTN.format(start=_get_color('accent_vanity'), end=_get_color('accent_predict'))};
                color: white; border: none; font-weight: bold;
            }}
            QPushButton[cssClass="predict"] {{
                background: {_GRADIENT_BTN.format(start=_get_color('accent_predict'), end='#7D3C98')};
                color: white; border: 2px solid #6C3483; 
                border-radius: 8px; font-weight: bold; font-size: 10pt;
            }}

            /* ========== ПОЛЯ ВВОДА ========== */
            QLineEdit, QPlainTextEdit {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 4px;
                padding: 6px 10px;
                selection-background-color: {_get_color('accent_primary')};
                selection-color: white;
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{
                border-color: {_get_color('border_focus')};
                background: #282838;
            }}
            QLineEdit:disabled, QPlainTextEdit:disabled {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_disabled')};
            }}
            QLineEdit[cssClass="result"] {{
                background: #1A1A28;
                color: {_get_color('accent_success')};
                font-weight: bold;
                border-color: {_get_color('accent_success')};
            }}

            /* ========== COMBOBOX / SPINBOX ========== */
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 28px;
            }}
            QComboBox:focus, QSpinBox:focus {{
                border-color: {_get_color('border_focus')};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {_get_color('text_secondary')};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                selection-background-color: {_get_color('accent_primary')};
            }}

            /* ========== ЧЕКБОКСЫ / РАДИО ========== */
            QCheckBox, QRadioButton {{
                color: {_get_color('text_primary')};
                spacing: 6px;
                padding: 2px 0;
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 18px; height: 18px;
                border: 2px solid {_get_color('border')};
                border-radius: 4px;
                background: {_get_color('bg_input')};
            }}
            QCheckBox::indicator:checked {{
                background: {_get_color('accent_primary')};
                border-color: {_get_color('accent_primary')};
            }}
            QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
                border-color: {_get_color('border')};
                background: {_get_color('bg_main')};
            }}
            QRadioButton::indicator {{ border-radius: 9px; }}

            /* ========== ПРОГРЕСС-БАРЫ ========== */
            QProgressBar {{
                background: {_get_color('bg_input')};
                border: 1px solid {_get_color('border')};
                border-radius: 4px;
                text-align: center;
                font-weight: 500;
                color: {_get_color('text_primary')};
            }}
            QProgressBar::chunk {{
                background: {_GRADIENT_CHUNK.format(start=_get_color('accent_primary'), end='#4A7ACC')};
                border-radius: 3px;
            }}
            QProgressBar[cssClass="success"]::chunk {{
                background: {_GRADIENT_CHUNK.format(start=_get_color('accent_success'), end='#27AE60')};
            }}
            QProgressBar[cssClass="warning"]::chunk {{
                background: {_GRADIENT_CHUNK.format(start=_get_color('accent_warning'), end='#E67E22')};
            }}
            QProgressBar[cssClass="danger"]::chunk {{
                background: {_GRADIENT_CHUNK.format(start=_get_color('accent_danger'), end='#C0392B')};
            }}

            /* ========== ТАБЛИЦЫ ========== */
            QTableWidget, QTreeWidget, QListView {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 6px;
                gridline-color: {_get_color('grid_line')};
                alternate-background-color: #202030;
            }}
            QTableWidget::item, QTreeWidget::item, QListView::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {_get_color('grid_line')};
            }}
            QTableWidget::item:selected, QTreeWidget::item:selected {{
                background: {_get_color('accent_primary')};
                color: white;
            }}
            QHeaderView::section {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_secondary')};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {_get_color('border')};
                font-weight: bold;
            }}

            /* ========== СКРОЛЛ-ОБЛАСТИ ========== */
            QScrollArea {{
                border: 1px solid {_get_color('border')};
                border-radius: 6px;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {_get_color('bg_input')};
                width: 14px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {_get_color('border')};
                border-radius: 7px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_get_color('accent_primary')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {_get_color('bg_input')};
                height: 14px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {_get_color('border')};
                border-radius: 7px;
                min-width: 30px;
            }}

            /* ========== LABELS ========== */
            QLabel[cssClass="status"] {{
                font-weight: bold;
                color: {_get_color('accent_primary')};
                font-size: 10pt;
            }}
            QLabel[cssClass="speed"] {{
                color: {_get_color('accent_warning')};
                font-weight: 500;
            }}
            QLabel[cssClass="found"] {{
                font-weight: bold;
                color: {_get_color('accent_success')};
            }}
            QLabel[cssClass="range"] {{
                font-weight: bold;
                color: {_get_color('accent_warning')};
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }}
            QLabel[cssClass="temp"] {{ color: {_get_color('accent_danger')}; }}
            QLabel[cssClass="mem"] {{ color: {_get_color('accent_vanity')}; }}
            QLabel[cssClass="util"] {{ color: {_get_color('accent_warning')}; }}
            QLabel[cssClass="info"] {{ 
                color: {_get_color('text_secondary')}; 
                font-size: 9pt; 
            }}
            QLabel[cssClass="header"] {{
                font-size: 13pt;
                font-weight: bold;
                color: {_get_color('text_primary')};
                padding: 4px 0;
            }}
            QLabel[cssClass="section-title"] {{
                font-size: 11pt;
                font-weight: bold;
                color: {_get_color('accent_primary')};
                padding: 8px 0 4px 0;
                border-bottom: 1px solid {_get_color('border')};
                margin-bottom: 8px;
            }}

            /* ========== INFO BOXES ========== */
            QLabel[cssClass="info-box"] {{
                color: {_get_color('text_secondary')};
                padding: 10px 14px;
                background: {_get_color('bg_input')};
                border-radius: 6px;
                border-left: 4px solid {_get_color('accent_primary')};
                font-size: 9pt;
            }}
            QLabel[cssClass="info-box-warning"] {{
                border-left-color: {_get_color('accent_warning')};
                background: #2A2520;
            }}
            QLabel[cssClass="info-box-success"] {{
                border-left-color: {_get_color('accent_success')};
                background: #1E2A20;
            }}

            /* ========== РАЗДЕЛИТЕЛИ ========== */
            QFrame[cssClass="separator"] {{
                background: {_get_color('border')};
                margin: 8px 0;
                min-height: 1px;
                max-height: 1px;
            }}
            QFrame[cssClass="separator-vertical"] {{
                background: {_get_color('border')};
                margin: 0 8px;
                min-width: 1px;
                max-width: 1px;
            }}

            /* ========== TOOL TIPS ========== */
            QToolTip {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 4px;
                padding: 6px;
                font-size: 9pt;
            }}

            /* ========== MENU / CONTEXT ========== */
            QMenu {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {_get_color('accent_primary')};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {_get_color('border')};
                margin: 4px 0;
            }}
        """)
    except Exception as e:  # 🛠 УЛУЧШЕНИЕ 6: Обработка ошибок применения темы
        import logging
        logging.getLogger(__name__).warning(f"Не удалось применить тему: {e}")


def set_button_style(button: QPushButton, style_type: str) -> None:
    """
    Устанавливает стиль кнопки через свойство cssClass.

    :param button: Экземпляр QPushButton для стилизации
    :param style_type: Тип стиля: 'primary', 'success', 'warning', 'vanity', 'predict'
    """
    button.setProperty("cssClass", style_type)
    # 🛠 УЛУЧШЕНИЕ 7: Проверка на существование style() перед unpolish/polish
    style = button.style()
    if style:
        style.unpolish(button)
        style.polish(button)


# 🛠 УЛУЧШЕНИЕ 8: Явный экспорт публичного API модуля
__all__ = ['COLORS', 'apply_dark_theme', 'set_button_style']