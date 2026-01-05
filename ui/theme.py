# ui/theme.py
from PyQt5.QtGui import QPalette, QColor


def apply_dark_theme(window):
    """
    Применяет тёмную тему к указанному QMainWindow или QWidget.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(20, 20, 30))
    palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.Base, QColor(28, 28, 38))
    palette.setColor(QPalette.AlternateBase, QColor(38, 38, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(40, 40, 45))
    palette.setColor(QPalette.ToolTipText, QColor(230, 230, 230))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(38, 38, 48))
    palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(80, 130, 180))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.PlaceholderText, QColor(120, 120, 120))
    window.setPalette(palette)

    window.setStyleSheet("""
        QWidget, QTabWidget, QTabBar, QGroupBox, QComboBox, QLineEdit, QTextEdit, QSpinBox {
            background: #181822;
            color: #F0F0F0;
            font-size: 9pt;
        }
        QTabWidget::pane { border: 1px solid #222; }
        QTabBar::tab {
            background: #252534;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 4px 4px 0 0;
            padding: 6px 20px;
            min-width: 120px;
        }
        QTabBar::tab:selected { background: #303054; color: #ffffff; }
        QTabBar::tab:!selected { background: #252534; color: #F0F0F0; }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 6px;
            margin-top: 1ex;
            font-weight: bold;
            background: #232332;
            color: #F0F0F0;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 8px;
            background: transparent;
            color: #61afef;
        }
        QPushButton {
            background: #292A36;
            color: #F0F0F0;
            border: 1px solid #555;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-height: 35px;
        }
        QPushButton:hover { background: #3a3a45; }
        QPushButton:pressed { background: #24243A; }
        QPushButton:disabled { background: #202020; color: #777; }
        QLineEdit, QTextEdit {
            background: #202030;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 6px;
            selection-background-color: #3a5680;
        }
        QComboBox {
            background: #23233B;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 4px;
        }
        QComboBox QAbstractItemView {
            background: #23233B;
            color: #F0F0F0;
            selection-background-color: #264080;
        }
        QTableWidget {
            background: #232332;
            color: #F0F0F0;
            gridline-color: #333;
            alternate-background-color: #222228;
            font-size: 10pt;
        }
        QHeaderView::section {
            background: #232332;
            color: #F0F0F0;
            padding: 4px;
            border: none;
            font-weight: bold;
        }
        QLabel { color: #CCCCCC; }
        QProgressBar {
            height: 25px;
            text-align: center;
            font-weight: bold;
            border: 1px solid #444;
            border-radius: 4px;
            background: #202030;
            color: #F0F0F0;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
            border-radius: 3px;
        }
        QCheckBox { color: #CCCCCC; }
    """)