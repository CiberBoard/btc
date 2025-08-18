import os
import platform
import subprocess
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PyQt5.QtGui import QFont, QColor
import logger.config
from logger import config

class LogTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Текстовое поле для вывода логов
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        self.log_output.setStyleSheet("""
            QTextEdit {
                background: #202030;
                color: #F0F0F0;
                border: 1px solid #444;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.log_output)

        # Панель кнопок
        log_button_layout = QHBoxLayout()

        # Кнопка очистки лога
        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c0392b;
            }
        """)
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_button_layout.addWidget(self.clear_log_btn)

        # Кнопка открытия файла лога
        self.open_log_btn = QPushButton("Открыть файл лога")
        self.open_log_btn.clicked.connect(self.open_log_file)
        log_button_layout.addWidget(self.open_log_btn)

        log_button_layout.addStretch()
        layout.addLayout(log_button_layout)

    def append_log(self, message, level="normal"):
        """
        Добавляет сообщение в лог с цветом в зависимости от уровня

        Параметры:
            message (str): Текст сообщения
            level (str): Уровень сообщения (error, success, warning, normal)
        """
        if level == "error":
            color = "#e74c3c"  # Красный
        elif level == "success":
            color = "#27ae60"  # Зеленый
        elif level == "warning":
            color = "#f1c40f"  # Желтый
        else:
            color = "#bbb"  # Серый

        # Форматирование времени
        timestamp = time.strftime('[%H:%M:%S]')

        # Форматирование сообщения как HTML
        html = f'<span style="color:{color};">{timestamp} {message}</span>'

        # Добавление сообщения в лог
        self.log_output.append(html)

        # Автопрокрутка к последнему сообщению
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def clear_log(self):
        """Очищает содержимое окна лога"""
        self.log_output.clear()

    def open_log_file(self):
        """Открывает файл лога в системном редакторе по умолчанию"""
        try:
            # Создаем файл, если он не существует
            if not os.path.exists(config.LOG_FILE):
                open(config.LOG_FILE, 'a').close()

            # Открываем файл в зависимости от ОС
            if platform.system() == 'Windows':
                os.startfile(config.LOG_FILE)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', config.LOG_FILE])
            else:  # Linux
                subprocess.call(['xdg-open', config.LOG_FILE])
        except Exception as e:
            # В случае ошибки выводим сообщение в лог
            self.append_log(f"Не удалось открыть файл лога: {str(e)}", "error")