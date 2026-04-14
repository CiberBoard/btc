# ui/theme_v2_professional.py
"""
🎨 ПРОФЕССИОНАЛЬНАЯ ТЕМА V2.0
Компонент для Bitcoin GPU/CPU Scanner

✨ Ключевые улучшения:
  • Улучшенная цветовая палитра с контрастом
  • Четкая визуальная иерархия
  • Профессиональный бизнес-стиль
  • Плавные анимации и переходы
  • Лучшая читаемость текста и данных
  • Состояния виджетов (hover, focus, active)
  • Адаптивные отступы и размеры
"""

from PyQt6.QtGui import QPalette, QColor, QFont
from PyQt6.QtCore import Qt

# ═══════════════════════════════════════════════════════════════
# 🎨 РАСШИРЕННАЯ ЦВЕТОВАЯ ПАЛИТРА (ПРОФЕССИОНАЛЬНАЯ)
# ═══════════════════════════════════════════════════════════════

COLORS_V2 = {
    # === ОСНОВНОЙ ФОН ===
    'bg_main': '#0F1419',           # Основной фон (почти черный)
    'bg_secondary': '#151B24',      # Вторичный фон
    'bg_tertiary': '#1A2332',       # Третичный фон (карточки)
    'bg_card': '#1E2A3A',           # Фон групп и карточек
    'bg_input': '#232E3D',          # Фон полей ввода
    'bg_input_dark': '#1A2230',     # Темный фон инпута (фокус)
    'bg_hover': '#2A3847',          # Фон при наведении
    'bg_pressed': '#1A2A38',        # Фон при нажатии
    'bg_disabled': '#151B24',       # Фон отключенных элементов
    'bg_success': '#0D2818',        # Фон успеха (темно-зеленый)
    'bg_warning': '#2D2410',        # Фон предупреждения (темно-оранжевый)
    'bg_danger': '#2D1410',         # Фон ошибки (темно-красный)

    # === ТЕКСТ ===
    'text_primary': '#E8EAED',      # Основной текст (светло-серый)
    'text_secondary': '#A8AEB8',    # Вторичный текст (средний серый)
    'text_tertiary': '#707A8A',     # Третичный текст (темный серый)
    'text_disabled': '#4A5268',     # Отключенный текст
    'text_inverse': '#0F1419',      # Инверсный текст (для светлого фона)

    # === АКЦЕНТЫ (ГЛАВНЫЕ ЦВЕТА) ===
    'accent_primary': '#4A90FF',       # Основной акцент (синий профессиональный)
    'accent_primary_dark': '#3A7BE0',  # Темнее
    'accent_primary_light': '#6BA5FF', # Светлее
    'accent_secondary': '#6B7DFF',     # Вторичный акцент (синее-фиолетовый)

    # === ФУНКЦИОНАЛЬНЫЕ ЦВЕТА ===
    'success': '#10B981',               # Успех (яркий зелёный)
    'success_dark': '#0A8659',          # Темнее
    'success_light': '#34D399',         # Светлее
    'warning': '#F59E0B',               # Предупреждение (оранжевый)
    'warning_dark': '#D97706',          # Темнее
    'warning_light': '#FBBF24',         # Светлее
    'danger': '#EF4444',                # Ошибка (красный)
    'danger_dark': '#DC2626',           # Темнее
    'danger_light': '#F87171',          # Светлее
    'info': '#3B82F6',                  # Информация (голубой)
    'info_dark': '#1D4ED8',             # Темнее
    'info_light': '#60A5FA',            # Светлее

    # === СПЕЦИАЛЬНЫЕ ЦВЕТА ===
    'gpu': '#8B5CF6',                   # GPU (фиолетовый)
    'cpu': '#06B6D4',                   # CPU (голубой)
    'kangaroo': '#EC4899',              # Kangaroo (розовый)
    'vanity': '#F97316',                # Vanity (оранжевый)
    'predict': '#A855F7',               # Predict (фиолетовый)

    # === ГРАНИЦЫ И РАЗДЕЛИТЕЛИ ===
    'border': '#2D3A4A',                # Стандартная граница
    'border_light': '#3A4858',          # Светлая граница
    'border_focus': '#4A90FF',          # Граница в фокусе
    'border_disabled': '#1E2A38',       # Граница отключенного
    'divider': '#1E2A38',               # Разделитель

    # === СЕТКА ===
    'grid_line': '#252E3D',             # Линии таблиц
    'grid_header_bg': '#1A2332',        # Фон заголовка таблицы
    'grid_alternate': '#1F2A38',        # Альтернирующая строка

    # === ТЕНИ И ГЛУБИНА ===
    'shadow_sm': '#00000030',           # Легкая тень
    'shadow_md': '#00000050',           # Средняя тень
    'shadow_lg': '#00000080',           # Сильная тень

    # === ГРАДИЕНТЫ (для кнопок и элементов) ===
    'gradient_primary': '#4A90FF',
    'gradient_success': '#10B981',
    'gradient_warning': '#F59E0B',
    'gradient_danger': '#EF4444',
}

# ═══════════════════════════════════════════════════════════════
# 📐 ТИПОГРАФИЯ И РАЗМЕРЫ
# ═══════════════════════════════════════════════════════════════

TYPOGRAPHY = {
    'font_family': '"Segoe UI", "Roboto", "Inter", "Helvetica", sans-serif',
    'font_mono': '"Fira Code", "Consolas", "Courier New", monospace',

    # === РАЗМЕРЫ ШРИФТОВ ===
    'size_xs': '8pt',
    'size_sm': '9pt',
    'size_base': '10pt',
    'size_lg': '11pt',
    'size_xl': '12pt',
    'size_2xl': '14pt',
    'size_3xl': '16pt',
    'size_4xl': '18pt',

    # === ВЕСА ШРИФТОВ ===
    'weight_light': 300,
    'weight_normal': 400,
    'weight_medium': 500,
    'weight_semibold': 600,
    'weight_bold': 700,

    # === ОТСТУПЫ ===
    'spacing_xs': '4px',
    'spacing_sm': '8px',
    'spacing_md': '12px',
    'spacing_lg': '16px',
    'spacing_xl': '20px',
    'spacing_2xl': '24px',

    # === РАЗМЕРЫ ЭЛЕМЕНТОВ ===
    'button_height_sm': '32px',
    'button_height_md': '40px',
    'button_height_lg': '48px',
    'button_radius': '6px',
    'card_radius': '8px',
    'input_radius': '5px',
}

# ═══════════════════════════════════════════════════════════════
# 🎨 ПРИМЕНЕНИЕ ТЕМЫ
# ═══════════════════════════════════════════════════════════════

def apply_professional_theme(window):
    """
    Применяет профессиональную тему к приложению
    """
    
    # 1️⃣ ПАЛИТРА НАТИВНЫХ ВИДЖЕТОВ
    palette = QPalette()
    
    # Основные цвета
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS_V2['bg_main']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS_V2['text_primary']))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS_V2['bg_input']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS_V2['grid_alternate']))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS_V2['bg_card']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS_V2['text_primary']))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS_V2['text_primary']))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS_V2['bg_card']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS_V2['text_primary']))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(COLORS_V2['danger']))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS_V2['accent_primary']))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(COLORS_V2['accent_secondary']))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS_V2['accent_primary']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS_V2['text_primary']))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS_V2['text_tertiary']))
    
    # Отключенный текст
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(COLORS_V2['text_disabled']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(COLORS_V2['text_disabled']))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(COLORS_V2['text_disabled']))
    
    window.setPalette(palette)
    window.setAutoFillBackground(True)

    # 2️⃣ STYLESHEET ДЛЯ КАСТОМНЫХ СТИЛЕЙ
    stylesheet = generate_stylesheet()
    window.setStyleSheet(stylesheet)


def generate_stylesheet() -> str:
    """Генерирует полный CSS-подобный stylesheet для всех компонентов"""
    
    c = COLORS_V2  # Сокращение для удобства
    t = TYPOGRAPHY
    
    return f"""
/* ════════════════════════════════════════════════════════════
   БАЗОВЫЕ НАСТРОЙКИ
   ════════════════════════════════════════════════════════════ */

* {{
    margin: 0;
    padding: 0;
    border: none;
}}

QWidget {{
    background-color: {c['bg_main']};
    color: {c['text_primary']};
    font-family: {t['font_family']};
    font-size: {t['size_base']};
}}

/* ════════════════════════════════════════════════════════════
   ВКЛАДКИ (QTabWidget / QTabBar)
   ════════════════════════════════════════════════════════════ */

QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: {t['card_radius']};
    background-color: {c['bg_card']};
    margin-top: -1px;
}}

QTabBar::tab {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 20px;
    min-width: 120px;
    font-weight: 500;
    font-size: {t['size_base']};
}}

QTabBar::tab:selected {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border-bottom-color: {c['accent_primary']};
    font-weight: 600;
    border-bottom: 3px solid {c['accent_primary']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {c['bg_hover']};
    color: {c['text_primary']};
    border-bottom-color: {c['border_light']};
}}

/* ════════════════════════════════════════════════════════════
   ГРУППЫ (QGroupBox)
   ════════════════════════════════════════════════════════════ */

QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: {t['card_radius']};
    margin-top: 14px;
    padding-top: 18px;
    padding-left: 12px;
    padding-right: 12px;
    padding-bottom: 12px;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['bg_tertiary']},
        stop:1 {c['bg_card']}
    );
    font-weight: 600;
    color: {c['text_primary']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 8px;
    color: {c['accent_primary']};
    background: {c['bg_main']};
    font-weight: 600;
    font-size: {t['size_lg']};
}}

/* ════════════════════════════════════════════════════════════
   КНОПКИ (QPushButton)
   ════════════════════════════════════════════════════════════ */

QPushButton {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['bg_card']},
        stop:1 {c['bg_input']}
    );
    color: {c['text_primary']};
    border: 1px solid {c['border_light']};
    border-radius: {t['button_radius']};
    padding: 8px 16px;
    font-weight: 500;
    font-size: {t['size_base']};
    min-height: {t['button_height_md']};
    outline: none;
}}

QPushButton:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['bg_hover']},
        stop:1 {c['bg_card']}
    );
    border-color: {c['border_focus']};
    color: {c['text_primary']};
}}

QPushButton:pressed {{
    background: {c['bg_pressed']};
    border-color: {c['accent_primary']};
}}

QPushButton:focus {{
    border: 2px solid {c['accent_primary']};
    padding: 7px 15px;
}}

QPushButton:disabled {{
    background-color: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: {c['border_disabled']};
}}

/* --- ТИПЫ КНОПОК --- */

/* Primary - Основные действия */
QPushButton[cssClass="primary"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['accent_primary_light']},
        stop:1 {c['accent_primary']}
    );
    color: white;
    border: none;
    font-weight: 600;
}}

QPushButton[cssClass="primary"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['accent_primary']},
        stop:1 {c['accent_primary_dark']}
    );
}}

QPushButton[cssClass="primary"]:pressed {{
    background: {c['accent_primary_dark']};
}}

/* Success - Запуск / Применение */
QPushButton[cssClass="success"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['success_light']},
        stop:1 {c['success']}
    );
    color: white;
    border: none;
    font-weight: 600;
}}

QPushButton[cssClass="success"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['success']},
        stop:1 {c['success_dark']}
    );
}}

/* Warning - Паузы / Предупреждения */
QPushButton[cssClass="warning"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['warning_light']},
        stop:1 {c['warning']}
    );
    color: {c['text_inverse']};
    border: none;
    font-weight: 600;
}}

QPushButton[cssClass="warning"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['warning']},
        stop:1 {c['warning_dark']}
    );
}}

/* Danger - Стоп / Удаление */
QPushButton[cssClass="danger"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['danger_light']},
        stop:1 {c['danger']}
    );
    color: white;
    border: none;
    font-weight: 600;
}}

QPushButton[cssClass="danger"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['danger']},
        stop:1 {c['danger_dark']}
    );
}}

/* GPU - Специальная кнопка GPU */
QPushButton[cssClass="gpu"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['gpu']},
        stop:1 #6F3F9F
    );
    color: white;
    border: none;
    font-weight: 600;
}}

/* CPU - Специальная кнопка CPU */
QPushButton[cssClass="cpu"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['cpu']},
        stop:1 #0096A0
    );
    color: white;
    border: none;
    font-weight: 600;
}}

/* Vanity - Генерация адресов */
QPushButton[cssClass="vanity"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['vanity']},
        stop:1 #D85610
    );
    color: white;
    border: none;
    font-weight: 600;
}}

/* Predict - Анализ */
QPushButton[cssClass="predict"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {c['predict']},
        stop:1 #7C3ACA
    );
    color: white;
    border: 2px solid {c['predict']};
    border-radius: {t['card_radius']};
    font-weight: 700;
    font-size: {t['size_lg']};
}}

QPushButton[cssClass="predict"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #B870FF,
        stop:1 {c['predict']}
    );
}}

/* ════════════════════════════════════════════════════════════
   ПОЛЯ ВВОДА (QLineEdit, QPlainTextEdit)
   ════════════════════════════════════════════════════════════ */

QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {t['input_radius']};
    padding: 8px 12px;
    font-size: {t['size_base']};
    selection-background-color: {c['accent_primary']};
    selection-color: white;
    font-family: {t['font_family']};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 2px solid {c['accent_primary']};
    background-color: {c['bg_input_dark']};
    padding: 7px 11px;
}}

QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border-color: {c['border_light']};
}}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    background-color: {c['bg_disabled']};
    color: {c['text_disabled']};
    border-color: {c['border_disabled']};
}}

/* Результаты (успешные) */
QLineEdit[cssClass="result"] {{
    background-color: {c['bg_success']};
    color: {c['success']};
    font-weight: 600;
    border: 1px solid {c['success']};
    font-family: {t['font_mono']};
    font-size: {t['size_sm']};
}}

/* ════════════════════════════════════════════════════════════
   COMBOBOX / SPINBOX
   ════════════════════════════════════════════════════════════ */

QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {t['input_radius']};
    padding: 6px 10px;
    min-height: 32px;
    font-size: {t['size_base']};
}}

QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {c['accent_primary']};
    padding: 5px 9px;
}}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {c['border_light']};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {c['accent_primary']};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {t['input_radius']};
    selection-background-color: {c['accent_primary']};
    outline: none;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {c['bg_hover']};
}}

/* ════════════════════════════════════════════════════════════
   ЧЕКБОКСЫ / РАДИО КНОПКИ
   ════════════════════════════════════════════════════════════ */

QCheckBox, QRadioButton {{
    color: {c['text_primary']};
    spacing: 8px;
    padding: 4px 0;
    font-size: {t['size_base']};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {c['border_light']};
    border-radius: {t['input_radius']};
    background-color: {c['bg_input']};
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {c['accent_primary']};
    background-color: {c['bg_hover']};
}}

QCheckBox::indicator:checked {{
    background-color: {c['accent_primary']};
    border-color: {c['accent_primary']};
}}

QCheckBox::indicator:checked::after {{
    image: none;
}}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: {c['border_disabled']};
    background-color: {c['bg_disabled']};
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QRadioButton::indicator:checked {{
    background: qradial(circle, {c['accent_primary']} 0%, {c['accent_primary']} 40%, 
                        {c['accent_primary']} 45%, transparent 50%);
    border-color: {c['accent_primary']};
}}

/* ════════════════════════════════════════════════════════════
   ПРОГРЕСС БАРЫ
   ════════════════════════════════════════════════════════════ */

QProgressBar {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: {t['input_radius']};
    text-align: center;
    font-weight: 600;
    color: {c['text_primary']};
    font-size: {t['size_sm']};
    padding: 2px;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent_primary_light']},
        stop:1 {c['accent_primary']}
    );
    border-radius: 3px;
}}

/* Success progress */
QProgressBar[cssClass="success"]::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['success_light']},
        stop:1 {c['success']}
    );
}}

/* Warning progress */
QProgressBar[cssClass="warning"]::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['warning_light']},
        stop:1 {c['warning']}
    );
}}

/* Danger progress */
QProgressBar[cssClass="danger"]::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['danger_light']},
        stop:1 {c['danger']}
    );
}}

/* ════════════════════════════════════════════════════════════
   ТАБЛИЦЫ
   ════════════════════════════════════════════════════════════ */

QTableWidget, QTreeWidget, QListView {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {t['card_radius']};
    gridline-color: {c['grid_line']};
    alternate-background-color: {c['grid_alternate']};
    font-size: {t['size_base']};
}}

QTableWidget::item, QTreeWidget::item, QListView::item {{
    padding: 8px 6px;
    border-bottom: 1px solid {c['grid_line']};
    color: {c['text_primary']};
}}

QTableWidget::item:selected, QTreeWidget::item:selected, QListView::item:selected {{
    background-color: {c['accent_primary']};
    color: white;
}}

QTableWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {c['bg_hover']};
}}

QHeaderView::section {{
    background-color: {c['grid_header_bg']};
    color: {c['text_secondary']};
    padding: 10px 8px;
    border: none;
    border-bottom: 2px solid {c['border_light']};
    font-weight: 600;
    font-size: {t['size_base']};
}}

QHeaderView::section:hover {{
    background-color: {c['bg_hover']};
}}

/* ════════════════════════════════════════════════════════════
   СКРОЛЛ-ОБЛАСТИ
   ════════════════════════════════════════════════════════════ */

QScrollArea {{
    border: 1px solid {c['border']};
    border-radius: {t['card_radius']};
    background-color: transparent;
}}

/* Вертикальный скролл */
QScrollBar:vertical {{
    background-color: {c['bg_input']};
    width: 12px;
    border-radius: 6px;
    margin: 4px 0;
}}

QScrollBar::handle:vertical {{
    background-color: {c['border_light']};
    border-radius: 6px;
    min-height: 40px;
    margin: 0 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c['accent_primary']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Горизонтальный скролл */
QScrollBar:horizontal {{
    background-color: {c['bg_input']};
    height: 12px;
    border-radius: 6px;
    margin: 0 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {c['border_light']};
    border-radius: 6px;
    min-width: 40px;
    margin: 2px 0;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c['accent_primary']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ════════════════════════════════════════════════════════════
   LABELS (МЕТКИ ТЕКСТА)
   ════════════════════════════════════════════════════════════ */

QLabel {{
    color: {c['text_primary']};
    font-size: {t['size_base']};
}}

/* Status labels */
QLabel[cssClass="status"] {{
    font-weight: 700;
    color: {c['info']};
    font-size: {t['size_lg']};
}}

QLabel[cssClass="status-running"] {{
    color: {c['success']};
}}

QLabel[cssClass="status-error"] {{
    color: {c['danger']};
}}

QLabel[cssClass="status-warning"] {{
    color: {c['warning']};
}}

/* Speed/Performance labels */
QLabel[cssClass="speed"] {{
    color: {c['warning']};
    font-weight: 600;
    font-size: {t['size_lg']};
}}

/* Success labels */
QLabel[cssClass="found"] {{
    font-weight: 700;
    color: {c['success']};
    font-size: {t['size_lg']};
}}

/* Range labels */
QLabel[cssClass="range"] {{
    font-weight: 600;
    color: {c['accent_primary']};
    font-family: {t['font_mono']};
    font-size: {t['size_sm']};
}}

/* Temperature labels */
QLabel[cssClass="temp"] {{
    color: {c['danger']};
    font-weight: 600;
}}

QLabel[cssClass="temp-normal"] {{
    color: {c['success']};
}}

QLabel[cssClass="temp-warning"] {{
    color: {c['warning']};
}}

/* Memory labels */
QLabel[cssClass="mem"] {{
    color: {c['predict']};
    font-weight: 500;
}}

/* Utility labels */
QLabel[cssClass="util"] {{
    color: {c['warning']};
    font-weight: 500;
}}

/* Header labels */
QLabel[cssClass="header"] {{
    font-size: {t['size_3xl']};
    font-weight: 700;
    color: {c['text_primary']};
    padding: 8px 0;
    letter-spacing: 0.5px;
}}

QLabel[cssClass="section-title"] {{
    font-size: {t['size_xl']};
    font-weight: 700;
    color: {c['accent_primary']};
    padding: 10px 0 6px 0;
    border-bottom: 2px solid {c['border']};
    margin-bottom: 8px;
}}

QLabel[cssClass="subheader"] {{
    font-size: {t['size_lg']};
    font-weight: 600;
    color: {c['text_secondary']};
    padding: 4px 0;
}}

/* Info boxes */
QLabel[cssClass="info"] {{
    color: {c['text_secondary']};
    font-size: {t['size_sm']};
    padding: 4px 0;
}}

QLabel[cssClass="info-box"] {{
    color: {c['text_secondary']};
    padding: 12px 14px;
    background-color: {c['bg_input']};
    border-radius: {t['card_radius']};
    border-left: 4px solid {c['accent_primary']};
    font-size: {t['size_sm']};
}}

QLabel[cssClass="info-box-warning"] {{
    border-left-color: {c['warning']};
    background-color: {c['bg_warning']};
    color: {c['warning']};
}}

QLabel[cssClass="info-box-success"] {{
    border-left-color: {c['success']};
    background-color: {c['bg_success']};
    color: {c['success']};
}}

QLabel[cssClass="info-box-danger"] {{
    border-left-color: {c['danger']};
    background-color: {c['bg_danger']};
    color: {c['danger']};
}}

/* ════════════════════════════════════════════════════════════
   РАЗДЕЛИТЕЛИ
   ════════════════════════════════════════════════════════════ */

QFrame[cssClass="separator"] {{
    background-color: {c['divider']};
    margin: 8px 0;
    min-height: 1px;
    max-height: 1px;
}}

QFrame[cssClass="separator-vertical"] {{
    background-color: {c['divider']};
    margin: 0 8px;
    min-width: 1px;
    max-width: 1px;
}}

/* ════════════════════════════════════════════════════════════
   ПОДСКАЗКИ (TOOLTIPS)
   ════════════════════════════════════════════════════════════ */

QToolTip {{
    background-color: {c['bg_card']};
    color: {c['text_primary']};
    border: 1px solid {c['border_light']};
    border-radius: {t['input_radius']};
    padding: 8px 12px;
    font-size: {t['size_sm']};
    font-family: {t['font_family']};
}}

/* ════════════════════════════════════════════════════════════
   МЕНЮ И КОНТЕКСТНЫЕ МЕНЮ
   ════════════════════════════════════════════════════════════ */

QMenu {{
    background-color: {c['bg_card']};
    color: {c['text_primary']};
    border: 1px solid {c['border_light']};
    border-radius: {t['card_radius']};
    padding: 6px;
    font-size: {t['size_base']};
}}

QMenu::item {{
    padding: 8px 20px 8px 24px;
    border-radius: {t['input_radius']};
}}

QMenu::item:selected {{
    background-color: {c['accent_primary']};
    color: white;
}}

QMenu::separator {{
    height: 1px;
    background-color: {c['divider']};
    margin: 4px 0;
}}

/* ════════════════════════════════════════════════════════════
   ДИАЛОГИ
   ════════════════════════════════════════════════════════════ */

QMessageBox {{
    background-color: {c['bg_main']};
}}

QMessageBox QLabel {{
    color: {c['text_primary']};
}}

/* ════════════════════════════════════════════════════════════
   СПЕЦИАЛЬНЫЕ КЛАССЫ
   ════════════════════════════════════════════════════════════ */

/* GPU элемент */
QWidget[cssClass="gpu-widget"] {{
    border-left: 3px solid {c['gpu']};
    background-color: {c['bg_card']};
}}

/* CPU элемент */
QWidget[cssClass="cpu-widget"] {{
    border-left: 3px solid {c['cpu']};
    background-color: {c['bg_card']};
}}

/* Kangaroo элемент */
QWidget[cssClass="kangaroo-widget"] {{
    border-left: 3px solid {c['kangaroo']};
    background-color: {c['bg_card']};
}}

/* Vanity элемент */
QWidget[cssClass="vanity-widget"] {{
    border-left: 3px solid {c['vanity']};
    background-color: {c['bg_card']};
}}

/* Predict элемент */
QWidget[cssClass="predict-widget"] {{
    border-left: 3px solid {c['predict']};
    background-color: {c['bg_card']};
}}
"""


def set_button_style(button, style_type: str) -> None:
    """
    Устанавливает стиль кнопки через свойство cssClass
    
    Args:
        button: QPushButton объект
        style_type: 'primary', 'success', 'warning', 'danger', 'gpu', 'cpu', 'vanity', 'predict'
    """
    button.setProperty("cssClass", style_type)
    button.style().unpolish(button)
    button.style().polish(button)


def set_label_style(label, style_type: str) -> None:
    """
    Устанавливает стиль метки через свойство cssClass
    """
    label.setProperty("cssClass", style_type)
    label.style().unpolish(label)
    label.style().polish(label)
