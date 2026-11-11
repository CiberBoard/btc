# ui/theme.py
# 🎨 Современная тёмно-серая тема (neutral dark gray) без ярких акцентов.
# Публичный API полностью совместим со старой версией:
#   COLORS, apply_dark_theme(window), set_button_style(button, style_type)
from typing import Dict, Optional
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QPushButton

# ─────────────────────────────────────────────────────────────
# ПАЛИТРА: нейтральные серые тона + приглушённые (muted) акценты
# Ключи сохранены для обратной совместимости, значения изменены.
# ─────────────────────────────────────────────────────────────
COLORS: Dict[str, str] = {
    # Фоны
    'bg_main': '#1E1E22',        # основной фон окна
    'bg_card': '#26262B',        # карточки / панели
    'bg_input': '#2C2C33',       # поля ввода
    'bg_hover': '#34343D',       # hover-состояния
    'bg_pressed': '#1A1A1F',     # pressed-состояния
    'bg_elevated': '#303038',    # всплывающие элементы, выбранные вкладки

    # Текст
    'text_primary': '#E8E8EC',
    'text_secondary': '#9A9AA5',
    'text_disabled': '#5C5C68',

    # Акценты — спокойные, низконасыщенные (без яркого синего/фиолетового)
    'accent_primary': '#7D8896',     # холодный стальной серый
    'accent_success': '#6E9C7E',     # приглушённый зелёный
    'accent_warning': '#B99A6B',     # приглушённый янтарный
    'accent_danger': '#C0796E',      # приглушённый терракотовый
    'accent_vanity': '#8A8FA3',      # серо-голубой
    'accent_predict': '#83897E',     # серо-зелёный (шалфей)

    # Границы
    'border': '#3A3A44',
    'border_soft': '#30303A',
    'border_focus': '#6B7686',
    'grid_line': '#2A2A32',

    # Оттенки для градиентов кнопок
    'btn_top': '#34343C',
    'btn_bottom': '#2A2A31',
    'btn_hover_top': '#3E3E48',
    'btn_hover_bottom': '#33333B',
}

# Константы для часто используемых градиентов
_GRADIENT_BTN = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {start}, stop:1 {end})"
_GRADIENT_CHUNK = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {start}, stop:1 {end})"


def _get_color(key: str, fallback: str = '#888888') -> str:
    """Вспомогательная функция для безопасного получения цвета"""
    return COLORS.get(key, fallback)


def apply_dark_theme(window: QWidget) -> None:
    """
    Применяет расширенную современную тёмно-серую тему к окну приложения.

    :param window: Экземпляр QMainWindow или QWidget для применения темы
    """
    try:
        # 1️⃣ Палитра для нативных виджетов
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(_get_color('bg_main')))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.Base, QColor(_get_color('bg_input')))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#2A2A31'))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(_get_color('bg_card')))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.Text, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.Button, QColor(_get_color('bg_card')))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(_get_color('accent_danger')))
        palette.setColor(QPalette.ColorRole.Link, QColor(_get_color('accent_primary')))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(_get_color('accent_primary')))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(_get_color('text_secondary')))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(_get_color('text_disabled')))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(_get_color('text_disabled')))

        window.setPalette(palette)
        window.setAutoFillBackground(True)

        # 2️⃣ StyleSheet — современный дизайн в тёмно-серых тонах (с анимациями)
        window.setStyleSheet(f"""
            /* ========== БАЗОВЫЕ НАСТРОЙКИ ========== */
            QWidget {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_primary')};
                font-family: 'Segoe UI', 'Inter', 'Roboto', 'Arial', sans-serif;
                font-size: 9.5pt;
            }}

            /* Страницы-вкладки: мягкий радиальный «свет» сверху — глубина */
            #mainTabs > QWidget {{
                background: qradialgradient(cx:0.5, cy:0, radius:1.4,
                    stop:0 {_get_color('bg_card')}, stop:1 {_get_color('bg_main')});
                border-radius: 12px;
            }}

            /* ========== ВКЛАДКИ (QTabWidget / QTabBar) ========== */
            QTabWidget::pane {{
                border: 1px solid {_get_color('border_soft')};
                border-radius: 10px;
                background: {_get_color('bg_card')};
                top: -1px;
            }}
            QTabWidget::tab-bar {{
                alignment: left;
                left: 6px;
            }}
            QTabBar {{
                qproperty-drawBase: 0;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {_get_color('text_secondary')};
                border: 1px solid transparent;
                padding: 9px 22px;
                min-width: 96px;
                margin-right: 3px;
                margin-top: 6px;
                border-top-left-radius: 9px;
                border-top-right-radius: 9px;
                font-size: 9.5pt;
                letter-spacing: 0.2px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {_get_color('bg_hover')};
                color: {_get_color('text_primary')};
                border-bottom: 1px solid {_get_color('border_soft')};
            }}
            QTabBar::tab:selected {{
                background: {_GRADIENT_BTN.format(start=_get_color('bg_elevated'), end=_get_color('bg_input'))};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-bottom: 2px solid {_get_color('accent_primary')};
                font-weight: 600;
            }}
            QTabBar::tab:!selected {{
                margin-top: 8px;
                padding-bottom: 7px;
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
            }}

            /* ========== ГРУППЫ (QGroupBox) — «карточки» интерфейса ========== */
            QGroupBox {{
                border: 1px solid {_get_color('border_soft')};
                border-radius: 12px;
                margin-top: 16px;
                margin-left: 4px;
                margin-right: 4px;
                padding-top: 22px;
                padding-left: 8px;
                padding-right: 8px;
                padding-bottom: 6px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #292A30, stop:1 {_get_color('bg_card')});
                font-weight: 600;
                color: {_get_color('text_primary')};
            }}
            QGroupBox:hover {{
                border: 1px solid {_get_color('border')};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 3px 12px;
                color: {_get_color('text_secondary')};
                background: {_get_color('bg_input')};
                border: 1px solid {_get_color('border_soft')};
                border-radius: 999px;
                font-size: 8.5pt;
                letter-spacing: 0.4px;
            }}

            /* ========== КНОПКИ ========== */
            QPushButton {{
                background: {_GRADIENT_BTN.format(start=_get_color('btn_top'), end=_get_color('btn_bottom'))};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 9px;
                padding: 8px 20px;
                font-weight: 500;
                min-height: 34px;
            }}
            QPushButton:hover {{
                background: {_GRADIENT_BTN.format(start=_get_color('btn_hover_top'), end=_get_color('btn_hover_bottom'))};
                border-color: {_get_color('border_focus')};
                color: #FFFFFF;
                padding-left: 24px;              /* «дышащая» анимация hover */
            }}
            QPushButton:pressed {{
                background: {_get_color('bg_pressed')};
                border-color: {_get_color('accent_primary')};
                padding-top: 9px;               /* эффект «вжатия» */
                padding-bottom: 7px;
            }}
            QPushButton:focus {{
                border: 1px solid {_get_color('border_focus')};
                outline: none;
            }}
            QPushButton:disabled {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_disabled')};
                border-color: {_get_color('border_soft')};
            }}
            QPushButton:checked {{
                background: {_get_color('bg_elevated')};
                border-color: {_get_color('accent_primary')};
            }}

            /* Типы кнопок — приглушённые, без кислотных цветов */
            QPushButton[cssClass="primary"] {{
                background: {_GRADIENT_BTN.format(start='#565E6B', end='#474D58')};
                color: #EDEFF2;
                border: 1px solid #626B7A;
                font-weight: 600;
            }}
            QPushButton[cssClass="primary"]:hover {{
                background: {_GRADIENT_BTN.format(start='#606978', end='#525964')};
                border-color: {_get_color('border_focus')};
            }}
            QPushButton[cssClass="primary"]:pressed {{
                background: #3F454F;
            }}
            QPushButton[cssClass="success"] {{
                background: {_GRADIENT_BTN.format(start='#4E6B57', end='#415848')};
                color: #E6EFE8; border: 1px solid #5C7C66; font-weight: 600;
            }}
            QPushButton[cssClass="success"]:hover {{
                background: {_GRADIENT_BTN.format(start='#587862', end='#4A6351')};
            }}
            QPushButton[cssClass="warning"] {{
                background: {_GRADIENT_BTN.format(start='#7A6A4E', end='#665842')};
                color: #F2ECDF; border: 1px solid #8C7A5C; font-weight: 600;
            }}
            QPushButton[cssClass="warning"]:hover {{
                background: {_GRADIENT_BTN.format(start='#8A7858', end='#74644B')};
            }}
            QPushButton[cssClass="vanity"] {{
                background: {_GRADIENT_BTN.format(start='#5A5F70', end='#4C5160')};
                color: #EBEDF2; border: 1px solid #6B7186; font-weight: 600;
            }}
            QPushButton[cssClass="vanity"]:hover {{
                background: {_GRADIENT_BTN.format(start='#666C7F', end='#565B6B')};
            }}
            QPushButton[cssClass="predict"] {{
                background: {_GRADIENT_BTN.format(start='#5D635A', end='#4E534B')};
                color: #ECEFEA; border: 1px solid #6E7569;
                border-radius: 9px; font-weight: 600; font-size: 10pt;
            }}
            QPushButton[cssClass="predict"]:hover {{
                background: {_GRADIENT_BTN.format(start='#6A7166', end='#585E55')};
            }}

            /* ========== ПОЛЯ ВВОДА ========== */
            QLineEdit, QPlainTextEdit, QTextEdit {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_soft')};
                border-radius: 7px;
                padding: 6px 10px;
                selection-background-color: {_get_color('accent_primary')};
                selection-color: #FFFFFF;
            }}
            QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{
                border-color: {_get_color('border')};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
                border-color: {_get_color('border_focus')};
                background: #31313A;
            }}
            QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_disabled')};
            }}
            QLineEdit[cssClass="result"] {{
                background: #232329;
                color: {_get_color('accent_success')};
                font-weight: bold;
                border-color: #4A5A4E;
            }}

            /* ========== COMBOBOX / SPINBOX ========== */
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_soft')};
                border-radius: 7px;
                padding: 4px 8px;
                min-height: 28px;
            }}
            QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
                border-color: {_get_color('border')};
            }}
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
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
                border-radius: 8px;
                selection-background-color: {_get_color('bg_elevated')};
                selection-color: {_get_color('text_primary')};
                padding: 4px;
                outline: none;
            }}

            /* ========== ЧЕКБОКСЫ / РАДИО ========== */
            QCheckBox, QRadioButton {{
                color: {_get_color('text_primary')};
                spacing: 6px;
                padding: 2px 0;
                background: transparent;
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 18px; height: 18px;
                border: 2px solid {_get_color('border')};
                border-radius: 5px;
                background: {_get_color('bg_input')};
            }}
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
                border-color: {_get_color('border_focus')};
            }}
            QCheckBox::indicator:checked {{
                background: {_get_color('accent_primary')};
                border-color: {_get_color('accent_primary')};
            }}
            QRadioButton::indicator:checked {{
                background: {_get_color('accent_primary')};
                border-color: {_get_color('accent_primary')};
            }}
            QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
                border-color: {_get_color('border_soft')};
                background: {_get_color('bg_main')};
            }}
            QRadioButton::indicator {{ border-radius: 9px; }}

            /* ========== ПРОГРЕСС-БАРЫ (с бегущим бликом) ========== */
            QProgressBar {{
                background: {_get_color('bg_input')};
                border: 1px solid {_get_color('border_soft')};
                border-radius: 8px;
                text-align: center;
                font-weight: 500;
                color: {_get_color('text_primary')};
            }}
            QProgressBar::chunk {{
                border-radius: 7px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6E7885, stop:0.45 #59616C, stop:0.5 #79838F,
                    stop:0.55 #59616C, stop:1 #6E7885);
            }}
            QProgressBar[cssClass="success"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6E9C7E, stop:0.45 #587F67, stop:0.5 #7FAE8E,
                    stop:0.55 #587F67, stop:1 #6E9C7E);
            }}
            QProgressBar[cssClass="warning"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #B99A6B, stop:0.45 #96805A, stop:0.5 #C9AC7E,
                    stop:0.55 #96805A, stop:1 #B99A6B);
            }}
            QProgressBar[cssClass="danger"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #C0796E, stop:0.45 #9E645B, stop:0.5 #CF8B81,
                    stop:0.55 #9E645B, stop:1 #C0796E);
            }}

            /* ========== ТАБЛИЦЫ ========== */
            QTableWidget, QTreeWidget, QListView {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_soft')};
                border-radius: 8px;
                gridline-color: {_get_color('grid_line')};
                alternate-background-color: #2A2A31;
                selection-background-color: {_get_color('bg_elevated')};
                selection-color: {_get_color('text_primary')};
            }}
            QTableWidget::item, QTreeWidget::item, QListView::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {_get_color('grid_line')};
                border-radius: 4px;
            }}
            QTableWidget::item:hover, QTreeWidget::item:hover, QListView::item:hover {{
                background: #2F2F38;                       /* подсветка строки под курсором */
            }}
            QTableWidget::item:selected, QTreeWidget::item:selected, QListView::item:selected {{
                background: {_get_color('bg_elevated')};
                color: #FFFFFF;
                border: 1px solid {_get_color('border_focus')};
            }}
            QHeaderView::section {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_secondary')};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {_get_color('border')};
                font-weight: 600;
            }}
            QHeaderView::section:hover {{
                color: {_get_color('text_primary')};
            }}

            /* ========== СКРОЛЛ-ОБЛАСТИ ========== */
            QScrollArea {{
                border: 1px solid {_get_color('border_soft')};
                border-radius: 8px;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 12px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {_get_color('border')};
                border-radius: 5px;
                min-height: 30px;
                margin: 1px 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_get_color('border_focus')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 12px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {_get_color('border')};
                border-radius: 5px;
                min-width: 30px;
                margin: 2px 1px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {_get_color('border_focus')};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}

            /* ========== LABELS ========== */
            QLabel {{
                background: transparent;
            }}
            QLabel[cssClass="status"] {{
                font-weight: 600;
                color: {_get_color('text_primary')};
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
                color: {_get_color('text_secondary')};
                font-family: 'Consolas', 'JetBrains Mono', 'Courier New', monospace;
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
                font-weight: 600;
                color: {_get_color('text_primary')};
                padding: 4px 0;
                border-bottom: 1px solid {_get_color('border_soft')};
            }}
            QLabel[cssClass="section-title"] {{
                font-size: 11pt;
                font-weight: 600;
                color: {_get_color('text_primary')};
                padding: 8px 0 4px 0;
                border-bottom: 1px solid {_get_color('border_soft')};
                margin-bottom: 8px;
            }}

            /* ========== INFO BOXES — «пилюли» с подложкой ========== */
            QLabel[cssClass="info-box"] {{
                color: {_get_color('text_secondary')};
                padding: 10px 14px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2B2C33, stop:1 {_get_color('bg_input')});
                border-radius: 10px;
                border-left: 3px solid {_get_color('accent_primary')};
                font-size: 9pt;
            }}
            QLabel[cssClass="info-box-warning"] {{
                border-left-color: {_get_color('accent_warning')};
                background: #2B2822;
            }}
            QLabel[cssClass="info-box-success"] {{
                border-left-color: {_get_color('accent_success')};
                background: #242924;
            }}

            /* ========== РАЗДЕЛИТЕЛИ ========== */
            QFrame[cssClass="separator"] {{
                background: {_get_color('border_soft')};
                margin: 8px 0;
                min-height: 1px;
                max-height: 1px;
                border: none;
            }}
            QFrame[cssClass="separator-vertical"] {{
                background: {_get_color('border_soft')};
                margin: 0 8px;
                min-width: 1px;
                max-width: 1px;
                border: none;
            }}

            /* ========== TOOL TIPS ========== */
            QToolTip {{
                background: {_get_color('bg_elevated')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 9pt;
            }}

            /* ========== MENU / CONTEXT ========== */
            QMenu {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 7px 26px 7px 14px;
                border-radius: 7px;
            }}
            QMenu::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3C3C46, stop:1 {_get_color('bg_elevated')});
                color: #FFFFFF;
            }}
            QMenu::separator {{
                height: 1px;
                background: {_get_color('border_soft')};
                margin: 5px 8px;
            }}

            /* ========== СТАТУС-БАР ========== */
            QStatusBar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {_get_color('bg_card')}, stop:1 #212126);
                color: {_get_color('text_secondary')};
                border-top: 1px solid {_get_color('border_soft')};
            }}
            QStatusBar::item {{
                border: none;
            }}
            QStatusBar QLabel {{
                padding: 2px 8px;
                border-radius: 6px;
                background: transparent;
            }}

            /* ========== СПИНБОКСЫ (стрелки) ========== */
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background: {_get_color('bg_card')};
                border: none;
                width: 18px;
                border-radius: 4px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background: {_get_color('bg_hover')};
            }}

            /* ========== СЛАЙДЕРЫ ========== */
            QSlider::groove:horizontal {{
                background: {_get_color('bg_input')};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {_get_color('bg_elevated')};
                border: 1px solid {_get_color('border_focus')};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {_get_color('bg_hover')};
                border-color: {_get_color('accent_primary')};
            }}
            QSlider::sub-page:horizontal {{
                background: {_get_color('accent_primary')};
                border-radius: 3px;
            }}
        """)
    except Exception as e:  # Обработка ошибок применения темы
        import logging
        logging.getLogger(__name__).warning(f"Не удалось применить тему: {e}")


def set_button_style(button: QPushButton, style_type: str) -> None:
    """
    Устанавливает стиль кнопки через свойство cssClass.

    :param button: Экземпляр QPushButton для стилизации
    :param style_type: Тип стиля: 'primary', 'success', 'warning', 'vanity', 'predict'
    """
    button.setProperty("cssClass", style_type)
    style = button.style()
    if style:
        style.unpolish(button)
        style.polish(button)


class AnimatedButton(QPushButton):
    """QPushButton + ripple-волна от точки клика (поверх стандартного стиля).

    Полностью совместим с QPushButton: можно использовать везде, где
    использовалась обычная кнопка. Анимация — только визуальная.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from ui.animations import attach_ripple
            attach_ripple(self, "#FFFFFF")
        except Exception:
            pass


def enhance_buttons(widget) -> int:
    """Включает ripple-анимацию для всех обычных кнопок внутри `widget`
    (кнопки с собственным paintEvent не трогаем). Меняется только внешний
    вид/ощущение — обработчики сигналов и логика не затрагиваются."""
    n = 0
    try:
        from ui.animations import attach_ripple
    except Exception:
        return 0
    for b in widget.findChildren(QPushButton):
        try:
            # пропускаем кнопки с кастомной отрисовкой (sidebar nav и т.п.)
            if type(b).paintEvent is not QPushButton.paintEvent:
                continue
            if getattr(b, "_ripple_filter", None) is not None:
                continue
            attach_ripple(b, "#FFFFFF")
            n += 1
        except Exception:
            continue
    return n


# Явный экспорт публичного API модуля
__all__ = ["COLORS", "apply_dark_theme", "set_button_style",
           "AnimatedButton", "enhance_buttons"]
