# ui/theme.py
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

# Цветовая палитра (централизованное управление)
COLORS = {
    'bg_main': '#14141E',  # Основной фон
    'bg_card': '#1C1C28',  # Фон карточек/групп
    'bg_input': '#232332',  # Фон полей ввода
    'bg_hover': '#2A2A3A',  # Фон при наведении
    'bg_pressed': '#1A1A28',  # Фон при нажатии

    'text_primary': '#F0F0F8',  # Основной текст
    'text_secondary': '#B0B0C0',  # Второстепенный текст
    'text_disabled': '#666680',  # Неактивный текст

    'accent_primary': '#5B8CFF',  # Основной акцент (синий)
    'accent_success': '#2ECC71',  # Успех (зелёный)
    'accent_warning': '#F39C12',  # Предупреждение (оранжевый)
    'accent_danger': '#E74C3C',  # Ошибка (красный)
    'accent_vanity': '#9B59B6',  # Vanity (фиолетовый)
    'accent_predict': '#8E44AD',  # Predict (тёмно-фиолетовый)

    'border': '#3A3A4A',  # Границы
    'border_focus': '#5B8CFF',  # Границы в фокусе
    'grid_line': '#2A2A3A',  # Линии сетки таблиц
}


def apply_dark_theme(window):
    """
    Применяет расширенную тёмную тему к окну приложения.
    """
    # 1️⃣ Палитра для нативных виджетов
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS['bg_main']))
    palette.setColor(QPalette.WindowText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Base, QColor(COLORS['bg_input']))
    palette.setColor(QPalette.AlternateBase, QColor('#252535'))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS['bg_card']))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Text, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.Button, QColor(COLORS['bg_card']))
    palette.setColor(QPalette.ButtonText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.BrightText, QColor(COLORS['accent_danger']))
    palette.setColor(QPalette.Link, QColor(COLORS['accent_primary']))
    palette.setColor(QPalette.Highlight, QColor(COLORS['accent_primary']))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS['text_primary']))
    palette.setColor(QPalette.PlaceholderText, QColor(COLORS['text_secondary']))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(COLORS['text_disabled']))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(COLORS['text_disabled']))

    window.setPalette(palette)
    window.setAutoFillBackground(True)

    # 2️⃣ StyleSheet для кастомных стилей
    window.setStyleSheet(f"""
        /* ========== БАЗОВЫЕ НАСТРОЙКИ ========== */
        QWidget {{
            background: {COLORS['bg_main']};
            color: {COLORS['text_primary']};
            font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
            font-size: 9pt;
        }}

        /* ========== ВКЛАДКИ ========== */
        QTabWidget::pane {{
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            background: {COLORS['bg_card']};
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background: {COLORS['bg_card']};
            color: {COLORS['text_secondary']};
            border: 1px solid transparent;
            border-bottom: 2px solid transparent;
            padding: 8px 24px;
            min-width: 100px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border-bottom-color: {COLORS['accent_primary']};
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            background: {COLORS['bg_hover']};
            color: {COLORS['text_primary']};
        }}

        /* ========== ГРУППЫ (QGroupBox) ========== */
        QGroupBox {{
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            margin-top: 16px;
            padding-top: 20px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['bg_card']}, stop:1 {COLORS['bg_main']});
            font-weight: bold;
            color: {COLORS['text_primary']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: {COLORS['accent_primary']};
            background: transparent;
        }}

        /* ========== КНОПКИ ========== */
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['bg_card']}, stop:1 {COLORS['bg_input']});
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 5px;
            padding: 8px 20px;
            font-weight: 500;
            min-height: 36px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['bg_hover']}, stop:1 {COLORS['bg_card']});
            border-color: {COLORS['accent_primary']};
        }}
        QPushButton:pressed {{
            background: {COLORS['bg_pressed']};
            border-color: {COLORS['accent_primary']};
        }}
        QPushButton:disabled {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_disabled']};
            border-color: {COLORS['border']};
        }}

        /* Типы кнопок */
        QPushButton[cssClass="primary"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['accent_primary']}, stop:1 #4A7ACC);
            color: white;
            border: none;
            font-weight: bold;
        }}
        QPushButton[cssClass="primary"]:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 #6B9CFF, stop:1 {COLORS['accent_primary']});
        }}
        QPushButton[cssClass="success"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['accent_success']}, stop:1 #27AE60);
            color: white; border: none; font-weight: bold;
        }}
        QPushButton[cssClass="warning"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['accent_warning']}, stop:1 #E67E22);
            color: black; border: none; font-weight: bold;
        }}
        QPushButton[cssClass="vanity"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['accent_vanity']}, stop:1 {COLORS['accent_predict']});
            color: white; border: none; font-weight: bold;
        }}
        QPushButton[cssClass="predict"] {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 {COLORS['accent_predict']}, stop:1 #7D3C98);
            color: white; border: 2px solid #6C3483; 
            border-radius: 8px; font-weight: bold; font-size: 10pt;
        }}

        /* ========== ПОЛЯ ВВОДА ========== */
        QLineEdit, QPlainTextEdit {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 6px 10px;
            selection-background-color: {COLORS['accent_primary']};
            selection-color: white;
        }}
        QLineEdit:focus, QPlainTextEdit:focus {{
            border-color: {COLORS['border_focus']};
            background: #282838;
        }}
        QLineEdit:disabled, QPlainTextEdit:disabled {{
            background: {COLORS['bg_main']};
            color: {COLORS['text_disabled']};
        }}
        QLineEdit[cssClass="result"] {{
            background: #1A1A28;
            color: {COLORS['accent_success']};
            font-weight: bold;
            border-color: {COLORS['accent_success']};
        }}

        /* ========== COMBOBOX / SPINBOX ========== */
        QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 4px 8px;
            min-height: 28px;
        }}
        QComboBox:focus, QSpinBox:focus {{
            border-color: {COLORS['border_focus']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {COLORS['text_secondary']};
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            selection-background-color: {COLORS['accent_primary']};
        }}

        /* ========== ЧЕКБОКСЫ / РАДИО ========== */
        QCheckBox, QRadioButton {{
            color: {COLORS['text_primary']};
            spacing: 6px;
            padding: 2px 0;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px; height: 18px;
            border: 2px solid {COLORS['border']};
            border-radius: 4px;
            background: {COLORS['bg_input']};
        }}
        QCheckBox::indicator:checked {{
            background: {COLORS['accent_primary']};
            border-color: {COLORS['accent_primary']};
        }}
        QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
            border-color: {COLORS['border']};
            background: {COLORS['bg_main']};
        }}
        QRadioButton::indicator {{ border-radius: 9px; }}

        /* ========== ПРОГРЕСС-БАРЫ ========== */
        QProgressBar {{
            background: {COLORS['bg_input']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            text-align: center;
            font-weight: 500;
            color: {COLORS['text_primary']};
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {COLORS['accent_primary']}, stop:1 #4A7ACC);
            border-radius: 3px;
        }}
        QProgressBar[cssClass="success"]::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {COLORS['accent_success']}, stop:1 #27AE60);
        }}
        QProgressBar[cssClass="warning"]::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {COLORS['accent_warning']}, stop:1 #E67E22);
        }}
        QProgressBar[cssClass="danger"]::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {COLORS['accent_danger']}, stop:1 #C0392B);
        }}

        /* ========== ТАБЛИЦЫ ========== */
        QTableWidget, QTreeWidget, QListView {{
            background: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            gridline-color: {COLORS['grid_line']};
            alternate-background-color: #202030;
        }}
        QTableWidget::item, QTreeWidget::item, QListView::item {{
            padding: 6px 8px;
            border-bottom: 1px solid {COLORS['grid_line']};
        }}
        QTableWidget::item:selected, QTreeWidget::item:selected {{
            background: {COLORS['accent_primary']};
            color: white;
        }}
        QHeaderView::section {{
            background: {COLORS['bg_card']};
            color: {COLORS['text_secondary']};
            padding: 8px;
            border: none;
            border-bottom: 2px solid {COLORS['border']};
            font-weight: bold;
        }}

        /* ========== СКРОЛЛ-ОБЛАСТИ ========== */
        QScrollArea {{
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: {COLORS['bg_input']};
            width: 14px;
            border-radius: 7px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS['border']};
            border-radius: 7px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS['accent_primary']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {COLORS['bg_input']};
            height: 14px;
            border-radius: 7px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS['border']};
            border-radius: 7px;
            min-width: 30px;
        }}

        /* ========== LABELS ========== */
        QLabel[cssClass="status"] {{
            font-weight: bold;
            color: {COLORS['accent_primary']};
            font-size: 10pt;
        }}
        QLabel[cssClass="speed"] {{
            color: {COLORS['accent_warning']};
            font-weight: 500;
        }}
        QLabel[cssClass="found"] {{
            font-weight: bold;
            color: {COLORS['accent_success']};
        }}
        QLabel[cssClass="range"] {{
            font-weight: bold;
            color: {COLORS['accent_warning']};
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 9pt;
        }}
        QLabel[cssClass="temp"] {{ color: {COLORS['accent_danger']}; }}
        QLabel[cssClass="mem"] {{ color: {COLORS['accent_vanity']}; }}
        QLabel[cssClass="util"] {{ color: {COLORS['accent_warning']}; }}
        QLabel[cssClass="info"] {{ 
            color: {COLORS['text_secondary']}; 
            font-size: 9pt; 
        }}
        QLabel[cssClass="header"] {{
            font-size: 13pt;
            font-weight: bold;
            color: {COLORS['text_primary']};
            padding: 4px 0;
        }}
        QLabel[cssClass="section-title"] {{
            font-size: 11pt;
            font-weight: bold;
            color: {COLORS['accent_primary']};
            padding: 8px 0 4px 0;
            border-bottom: 1px solid {COLORS['border']};
            margin-bottom: 8px;
        }}

        /* ========== INFO BOXES ========== */
        QLabel[cssClass="info-box"] {{
            color: {COLORS['text_secondary']};
            padding: 10px 14px;
            background: {COLORS['bg_input']};
            border-radius: 6px;
            border-left: 4px solid {COLORS['accent_primary']};
            font-size: 9pt;
        }}
        QLabel[cssClass="info-box-warning"] {{
            border-left-color: {COLORS['accent_warning']};
            background: #2A2520;
        }}
        QLabel[cssClass="info-box-success"] {{
            border-left-color: {COLORS['accent_success']};
            background: #1E2A20;
        }}

        /* ========== РАЗДЕЛИТЕЛИ ========== */
        QFrame[cssClass="separator"] {{
            background: {COLORS['border']};
            margin: 8px 0;
            min-height: 1px;
            max-height: 1px;
        }}
        QFrame[cssClass="separator-vertical"] {{
            background: {COLORS['border']};
            margin: 0 8px;
            min-width: 1px;
            max-width: 1px;
        }}

        /* ========== TOOL TIPS ========== */
        QToolTip {{
            background: {COLORS['bg_card']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 6px;
            font-size: 9pt;
        }}

        /* ========== MENU / CONTEXT ========== */
        QMenu {{
            background: {COLORS['bg_card']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {COLORS['accent_primary']};
            color: white;
        }}
        QMenu::separator {{
            height: 1px;
            background: {COLORS['border']};
            margin: 4px 0;
        }}
    """)


def set_button_style(button, style_type: str):
    """
    Устанавливает стиль кнопки через свойство cssClass.
    style_type: 'primary', 'success', 'warning', 'vanity', 'predict'
    """
    button.setProperty("cssClass", style_type)
    button.style().unpolish(button)
    button.style().polish(button)