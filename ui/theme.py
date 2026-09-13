# ui/theme.py
# 🎨 Modern Dark Theme with Enhanced Visual Design
from typing import Dict, Optional
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QPushButton

# 🎨 Enhanced Color Palette - Modern Deep Space Theme
COLORS: Dict[str, str] = {
    # Background colors - deeper, richer tones
    'bg_main': '#0D0D14',      # Darker main background
    'bg_card': '#16161F',      # Card/panel background
    'bg_input': '#1E1E2A',     # Input fields background
    'bg_hover': '#252535',     # Hover state
    'bg_pressed': '#151520',   # Pressed state
    'bg_elevated': '#1A1A25',  # Elevated surfaces
    
    # Text colors - better contrast
    'text_primary': '#FFFFFF',
    'text_secondary': '#A0A0B0',
    'text_tertiary': '#707080',
    'text_disabled': '#505060',
    
    # Accent colors - more vibrant and modern
    'accent_primary': '#6B7FFF',    # Brighter blue
    'accent_primary_light': '#8A9BFF',
    'accent_success': '#00DC82',    # Modern green (Vercel-like)
    'accent_success_dark': '#00B86A',
    'accent_warning': '#FFB800',    # Amber warning
    'accent_danger': '#FF4757',     # Coral red
    'accent_vanity': '#A855F7',     # Purple
    'accent_predict': '#EC4899',    # Pink
    'accent_info': '#0EA5E9',       # Sky blue
    'accent_gpu': '#10B981',        # Emerald for GPU
    'accent_cpu': '#3B82F6',        # Blue for CPU
    
    # UI elements
    'border': '#2D2D3A',
    'border_light': '#3D3D4A',
    'border_focus': '#6B7FFF',
    'grid_line': '#252535',
    'divider': '#2A2A38',
    
    # Special effects
    'shadow': 'rgba(0, 0, 0, 0.3)',
    'glow': 'rgba(107, 127, 255, 0.3)',
}

# 🛠 УЛУЧШЕНИЕ 3: Константы для часто используемых градиентов
_GRADIENT_BTN = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {start}, stop:1 {end})"
_GRADIENT_CHUNK = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {start}, stop:1 {end})"


def _get_color(key: str, fallback: str = '#888888') -> str:
    """🛠 УЛУЧШЕНИЕ 4: Вспомогательная функция для безопасного получения цвета"""
    return COLORS.get(key, fallback)


def apply_dark_theme(window: QWidget) -> None:
    """
    Применяет расширенную тёмную тему к окну приложения с современным дизайном.

    :param window: Экземпляр QMainWindow или QWidget для применения темы
    """
    try:
        # 1️⃣ Enhanced Palette for native widgets
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(_get_color('bg_main')))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(_get_color('text_primary')))
        palette.setColor(QPalette.ColorRole.Base, QColor(_get_color('bg_input')))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(_get_color('bg_elevated')))
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

        # 2️⃣ Modern Enhanced StyleSheet
        window.setStyleSheet(f"""
            /* ========== GLOBAL STYLES ========== */
            QWidget {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_primary')};
                font-family: 'Segoe UI', 'Inter', 'Roboto', 'Arial', sans-serif;
                font-size: 9.5pt;
                letter-spacing: 0.3px;
            }}

            /* ========== MAIN WINDOW & TABS ========== */
            QTabWidget::pane {{
                border: 1px solid {_get_color('border')};
                border-radius: 10px;
                background: {_get_color('bg_card')};
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {_get_color('text_secondary')};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 10px 28px;
                min-width: 120px;
                font-weight: 500;
                transition: all 0.2s ease;
            }}
            QTabBar::tab:selected {{
                color: {_get_color('text_primary')};
                border-bottom-color: {_get_color('accent_primary')};
                font-weight: 600;
                background: {_get_color('bg_elevated')};
            }}
            QTabBar::tab:first:selected {{
                border-top-left-radius: 10px;
            }}
            QTabBar::tab:last:selected {{
                border-top-right-radius: 10px;
            }}
            QTabBar::tab:hover:!selected {{
                color: {_get_color('text_primary')};
                background: {_get_color('bg_hover')};
            }}

            /* ========== CARD GROUPS (QGroupBox) ========== */
            QGroupBox {{
                border: 1px solid {_get_color('border_light')};
                border-radius: 12px;
                margin-top: 18px;
                padding-top: 22px;
                background: {_get_color('bg_card')};
                font-weight: 600;
                font-size: 10pt;
                color: {_get_color('text_primary')};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                padding: 0 12px;
                color: {_get_color('accent_primary')};
                background: {_get_color('bg_main')};
                border-radius: 4px;
            }}

            /* ========== BUTTONS - ENHANCED ========== */
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('bg_elevated')}, 
                    stop:1 {_get_color('bg_input')});
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 9.5pt;
                min-height: 40px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('bg_hover')}, 
                    stop:1 {_get_color('bg_elevated')});
                border-color: {_get_color('accent_primary')};
                box-shadow: 0 4px 12px rgba(107, 127, 255, 0.2);
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

            /* Primary Button */
            QPushButton[cssClass="primary"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_primary')}, 
                    stop:1 {_get_color('accent_primary_light')});
                color: white;
                border: none;
                font-weight: 700;
                font-size: 10pt;
            }}
            QPushButton[cssClass="primary"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_primary_light')}, 
                    stop:0.5 {_get_color('accent_primary')},
                    stop:1 {_get_color('accent_primary_light')});
            }}
            
            /* Success Button */
            QPushButton[cssClass="success"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_success')}, 
                    stop:1 {_get_color('accent_success_dark')});
                color: white;
                border: none;
                font-weight: 700;
            }}
            QPushButton[cssClass="success"]:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #00F08A, 
                    stop:1 {_get_color('accent_success')});
            }}
            
            /* Warning Button */
            QPushButton[cssClass="warning"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_warning')}, 
                    stop:1 #F59E0B);
                color: #1a1a1a;
                border: none;
                font-weight: 700;
            }}
            
            /* Vanity Button */
            QPushButton[cssClass="vanity"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_vanity')}, 
                    stop:1 {_get_color('accent_predict')});
                color: white;
                border: none;
                font-weight: 700;
            }}
            
            /* Predict Button */
            QPushButton[cssClass="predict"] {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_predict')}, 
                    stop:1 #DB2777);
                color: white;
                border: 2px solid #BE185D;
                border-radius: 10px;
                font-weight: 700;
                font-size: 10.5pt;
            }}

            /* ========== INPUT FIELDS - ENHANCED ========== */
            QLineEdit, QPlainTextEdit {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1.5px solid {_get_color('border')};
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 9.5pt;
                selection-background-color: {_get_color('accent_primary')};
                selection-color: white;
            }}
            QLineEdit:focus, QPlainTextEdit:focus {{
                border-color: {_get_color('border_focus')};
                background: {_get_color('bg_elevated')};
                outline: none;
            }}
            QLineEdit:disabled, QPlainTextEdit:disabled {{
                background: {_get_color('bg_main')};
                color: {_get_color('text_disabled')};
                border-color: {_get_color('border')};
            }}
            QLineEdit[cssClass="result"] {{
                background: {_get_color('bg_main')};
                color: {_get_color('accent_success')};
                font-weight: 700;
                font-family: 'Consolas', 'Courier New', monospace;
                border-color: {_get_color('accent_success')};
                border-width: 2px;
            }}

            /* ========== DROPDOWNS & SPINBOXES ========== */
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1.5px solid {_get_color('border')};
                border-radius: 8px;
                padding: 6px 12px;
                min-height: 34px;
                font-weight: 500;
            }}
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {_get_color('border_focus')};
                background: {_get_color('bg_elevated')};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid {_get_color('text_primary')};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border')};
                border-radius: 8px;
                selection-background-color: {_get_color('accent_primary')};
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 36px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {_get_color('bg_hover')};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {_get_color('accent_primary')};
                color: white;
            }}

            /* ========== CHECKBOXES & RADIO BUTTONS - ENHANCED ========== */
            QCheckBox, QRadioButton {{
                color: {_get_color('text_primary')};
                spacing: 8px;
                padding: 4px 0;
                font-weight: 500;
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 20px; 
                height: 20px;
                border: 2px solid {_get_color('border_light')};
                border-radius: 6px;
                background: {_get_color('bg_input')};
            }}
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 {_get_color('accent_primary')}, 
                    stop:1 {_get_color('accent_primary_light')});
                border-color: {_get_color('accent_primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {_get_color('accent_primary')};
            }}
            QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
                border-color: {_get_color('border')};
                background: {_get_color('bg_main')};
            }}
            QRadioButton::indicator {{ 
                border-radius: 10px; 
            }}

            /* ========== PROGRESS BARS - ENHANCED ========== */
            QProgressBar {{
                background: {_get_color('bg_input')};
                border: 1px solid {_get_color('border')};
                border-radius: 8px;
                text-align: center;
                font-weight: 600;
                color: {_get_color('text_primary')};
                height: 22px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {_get_color('accent_primary')}, 
                    stop:1 {_get_color('accent_primary_light')});
                border-radius: 6px;
            }}
            QProgressBar[cssClass="success"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {_get_color('accent_success')}, 
                    stop:1 #00F08A);
            }}
            QProgressBar[cssClass="warning"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {_get_color('accent_warning')}, 
                    stop:1 #FCD34D);
            }}
            QProgressBar[cssClass="danger"]::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {_get_color('accent_danger')}, 
                    stop:1 #F87171);
            }}

            /* ========== TABLES & LISTS - ENHANCED ========== */
            QTableWidget, QTreeWidget, QListView {{
                background: {_get_color('bg_input')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_light')};
                border-radius: 10px;
                gridline-color: {_get_color('grid_line')};
                alternate-background-color: {_get_color('bg_elevated')};
                outline: none;
            }}
            QTableWidget::item, QTreeWidget::item, QListView::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {_get_color('grid_line')};
            }}
            QTableWidget::item:selected, QTreeWidget::item:selected, QListView::item:selected {{
                background: {_get_color('accent_primary')};
                color: white;
                border-radius: 6px;
            }}
            QTableWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
                background: {_get_color('bg_hover')};
            }}
            QHeaderView::section {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_secondary')};
                padding: 10px 12px;
                border: none;
                border-bottom: 2px solid {_get_color('border_light')};
                font-weight: 600;
                font-size: 9.5pt;
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 8px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 8px;
            }}

            /* ========== SCROLL AREAS - MODERN ========== */
            QScrollArea {{
                border: 1px solid {_get_color('border')};
                border-radius: 10px;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {_get_color('bg_input')};
                width: 16px;
                border-radius: 8px;
                margin: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {_get_color('border_light')};
                border-radius: 8px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_get_color('accent_primary')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {_get_color('bg_input')};
                height: 16px;
                border-radius: 8px;
                margin: 3px;
            }}
            QScrollBar::handle:horizontal {{
                background: {_get_color('border_light')};
                border-radius: 8px;
                min-width: 40px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {_get_color('accent_primary')};
            }}

            /* ========== LABELS - VARIANTS ========== */
            QLabel[cssClass="status"] {{
                font-weight: 700;
                color: {_get_color('accent_primary')};
                font-size: 10.5pt;
            }}
            QLabel[cssClass="speed"] {{
                color: {_get_color('accent_warning')};
                font-weight: 600;
                font-size: 10pt;
            }}
            QLabel[cssClass="found"] {{
                font-weight: 700;
                color: {_get_color('accent_success')};
                font-size: 10pt;
            }}
            QLabel[cssClass="range"] {{
                font-weight: 600;
                color: {_get_color('accent_warning')};
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9.5pt;
            }}
            QLabel[cssClass="temp"] {{ 
                color: {_get_color('accent_danger')}; 
                font-weight: 600;
            }}
            QLabel[cssClass="mem"] {{ 
                color: {_get_color('accent_vanity')}; 
                font-weight: 600;
            }}
            QLabel[cssClass="util"] {{ 
                color: {_get_color('accent_warning')}; 
                font-weight: 600;
            }}
            QLabel[cssClass="info"] {{ 
                color: {_get_color('text_secondary')}; 
                font-size: 9pt; 
            }}
            QLabel[cssClass="header"] {{
                font-size: 15pt;
                font-weight: 700;
                color: {_get_color('text_primary')};
                padding: 6px 0 10px 0;
                letter-spacing: 0.5px;
            }}
            QLabel[cssClass="section-title"] {{
                font-size: 11.5pt;
                font-weight: 700;
                color: {_get_color('accent_primary')};
                padding: 10px 0 6px 0;
                border-bottom: 2px solid {_get_color('border')};
                margin-bottom: 10px;
            }}

            /* ========== INFO BOXES - ENHANCED ========== */
            QLabel[cssClass="info-box"] {{
                color: {_get_color('text_secondary')};
                padding: 12px 16px;
                background: {_get_color('bg_input')};
                border-radius: 8px;
                border-left: 4px solid {_get_color('accent_primary')};
                font-size: 9.5pt;
            }}
            QLabel[cssClass="info-box-warning"] {{
                border-left-color: {_get_color('accent_warning')};
                background: {_get_color('bg_elevated')};
            }}
            QLabel[cssClass="info-box-success"] {{
                border-left-color: {_get_color('accent_success')};
                background: {_get_color('bg_elevated')};
            }}

            /* ========== SEPARATORS ========== */
            QFrame[cssClass="separator"] {{
                background: {_get_color('divider')};
                margin: 10px 0;
                min-height: 1px;
                max-height: 1px;
                border-radius: 1px;
            }}
            QFrame[cssClass="separator-vertical"] {{
                background: {_get_color('divider')};
                margin: 0 10px;
                min-width: 1px;
                max-width: 1px;
                border-radius: 1px;
            }}

            /* ========== TOOLTIPS - MODERN ========== */
            QToolTip {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_light')};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 9.5pt;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            }}

            /* ========== MENUS / CONTEXT - ENHANCED ========== */
            QMenu {{
                background: {_get_color('bg_card')};
                color: {_get_color('text_primary')};
                border: 1px solid {_get_color('border_light')};
                border-radius: 10px;
                padding: 6px;
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
            }}
            QMenu::item {{
                padding: 8px 32px 8px 16px;
                border-radius: 6px;
                margin: 2px 4px;
            }}
            QMenu::item:selected {{
                background: {_get_color('accent_primary')};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {_get_color('divider')};
                margin: 6px 8px;
            }}
            QMenu::icon {{
                padding-left: 8px;
            }}
        """)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Не удалось применить тему: {e}")


def set_button_style(button: QPushButton, style_type: str) -> None:
    """
    Устанавливает стиль кнопки через свойство cssClass.

    :param button: Экземпляр QPushButton для стилизации
    :param style_type: Тип стиля: 'primary', 'success', 'warning', 'vanity', 'predict', 'gpu', 'cpu'
    """
    button.setProperty("cssClass", style_type)
    style = button.style()
    if style:
        style.unpolish(button)
        style.polish(button)


# 🎨 Enhanced Public API with new color utilities
__all__ = ['COLORS', 'apply_dark_theme', 'set_button_style', '_get_color']