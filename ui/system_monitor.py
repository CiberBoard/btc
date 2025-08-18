import psutil
import time
import platform
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QProgressBar
from PyQt5.QtGui import QColor


class SystemMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

        # Таймер для обновления информации
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_system_info)
        self.timer.start(2000)  # Обновление каждые 2 секунды

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(6)

        # Заголовок
        title = QLabel("Системный монитор")
        title.setStyleSheet("font-weight: bold; font-size: 12pt; color: #3498db;")
        layout.addWidget(title, 0, 0, 1, 4, Qt.AlignCenter)

        # CPU
        layout.addWidget(QLabel("Процессор:"), 1, 0)
        self.cpu_label = QLabel(f"{psutil.cpu_count()} ядер")
        layout.addWidget(self.cpu_label, 1, 1)

        layout.addWidget(QLabel("Загрузка CPU:"), 1, 2)
        self.cpu_usage = QLabel("0%")
        self.cpu_usage.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.cpu_usage, 1, 3)

        # Прогресс-бар загрузки CPU
        self.cpu_usage_bar = QProgressBar()
        self.cpu_usage_bar.setRange(0, 100)
        self.cpu_usage_bar.setValue(0)
        self.cpu_usage_bar.setFormat("Загрузка: %p%")
        self.cpu_usage_bar.setStyleSheet("""
            QProgressBar {
                height: 15px;
                text-align: center;
                font-size: 9pt;
                border: 1px solid #444;
                border-radius: 3px;
                background: #1a1a20;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
            }
        """)
        layout.addWidget(self.cpu_usage_bar, 2, 0, 1, 4)

        # Температура CPU
        layout.addWidget(QLabel("Температура CPU:"), 3, 0)
        self.cpu_temp_label = QLabel("- °C")
        self.cpu_temp_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.cpu_temp_label, 3, 1)

        # Прогресс-бар температуры CPU
        self.cpu_temp_bar = QProgressBar()
        self.cpu_temp_bar.setRange(0, 100)
        self.cpu_temp_bar.setValue(0)
        self.cpu_temp_bar.setFormat("Темп: %v°C")
        self.cpu_temp_bar.setStyleSheet("""
            QProgressBar {
                height: 15px;
                text-align: center;
                font-size: 9pt;
                border: 1px solid #444;
                border-radius: 3px;
                background: #1a1a20;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);
            }
        """)
        layout.addWidget(self.cpu_temp_bar, 3, 2, 1, 2)

        # Память
        layout.addWidget(QLabel("Память:"), 4, 0)
        self.mem_label = QLabel("0/0 MB")
        layout.addWidget(self.mem_label, 4, 1)

        layout.addWidget(QLabel("Использовано:"), 4, 2)
        self.mem_percent_label = QLabel("0%")
        layout.addWidget(self.mem_percent_label, 4, 3)

        # Прогресс-бар памяти
        self.mem_usage_bar = QProgressBar()
        self.mem_usage_bar.setRange(0, 100)
        self.mem_usage_bar.setValue(0)
        self.mem_usage_bar.setFormat("Память: %p%")
        self.mem_usage_bar.setStyleSheet("""
            QProgressBar {
                height: 15px;
                text-align: center;
                font-size: 9pt;
                border: 1px solid #444;
                border-radius: 3px;
                background: #1a1a20;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #8e44ad);
            }
        """)
        layout.addWidget(self.mem_usage_bar, 5, 0, 1, 4)

        # Разделитель
        separator = QLabel("")
        separator.setStyleSheet("border-top: 1px solid #444;")
        layout.addWidget(separator, 6, 0, 1, 4)

        # Статус сканирования
        layout.addWidget(QLabel("Статус GPU:"), 7, 0)
        self.gpu_status_label = QLabel("Не активно")
        self.gpu_status_label.setStyleSheet("color: #f39c12;")
        layout.addWidget(self.gpu_status_label, 7, 1)

        layout.addWidget(QLabel("Статус CPU:"), 7, 2)
        self.cpu_status_label = QLabel("Не активно")
        self.cpu_status_label.setStyleSheet("color: #f39c12;")
        layout.addWidget(self.cpu_status_label, 7, 3)

    def update_system_info(self):
        """Обновляет информацию о системе"""
        try:
            # Загрузка CPU
            cpu_percent = psutil.cpu_percent()
            self.cpu_usage.setText(f"{cpu_percent}%")
            self.cpu_usage_bar.setValue(int(cpu_percent))

            # Память
            mem = psutil.virtual_memory()
            mem_used = mem.used // (1024 * 1024)
            mem_total = mem.total // (1024 * 1024)
            mem_percent = mem.percent
            self.mem_label.setText(f"{mem_used}/{mem_total} MB")
            self.mem_percent_label.setText(f"{mem_percent}%")
            self.mem_usage_bar.setValue(int(mem_percent))

            # Температура CPU
            cpu_temp = self.get_cpu_temperature()
            if cpu_temp is not None:
                self.cpu_temp_label.setText(f"{cpu_temp:.1f} °C")
                self.cpu_temp_bar.setValue(int(cpu_temp))

                # Цветовая индикация температуры
                if cpu_temp > 80:
                    self.cpu_temp_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e74c3c, stop:1 #c0392b);
                        }
                    """)
                elif cpu_temp > 65:
                    self.cpu_temp_label.setStyleSheet("color: #f39c12; font-weight: bold;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f39c12, stop:1 #d35400);
                        }
                    """)
                else:
                    self.cpu_temp_label.setStyleSheet("color: #27ae60;")
                    self.cpu_temp_bar.setStyleSheet("""
                        QProgressBar::chunk {
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);
                        }
                    """)
            else:
                self.cpu_temp_label.setText("N/A")
                self.cpu_temp_label.setStyleSheet("color: #7f8c8d;")
                self.cpu_temp_bar.setValue(0)
                self.cpu_temp_bar.setFormat("Темп: N/A")

            # Обновление статусов сканирования
            if self.parent.gpu_tab.gpu_is_running:
                self.gpu_status_label.setText("Активно")
                self.gpu_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.gpu_status_label.setText("Не активно")
                self.gpu_status_label.setStyleSheet("color: #f39c12;")

            if self.parent.cpu_tab.processes:
                if self.parent.cpu_tab.cpu_pause_requested:
                    self.cpu_status_label.setText("На паузе")
                    self.cpu_status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
                else:
                    self.cpu_status_label.setText("Активно")
                    self.cpu_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.cpu_status_label.setText("Не активно")
                self.cpu_status_label.setStyleSheet("color: #f39c12;")

        except Exception as e:
            # В случае ошибки сбрасываем показатели
            self.cpu_usage.setText("Ошибка")
            self.mem_label.setText("Ошибка")
            self.cpu_temp_label.setText("Ошибка")
            self.gpu_status_label.setText("Ошибка")
            self.cpu_status_label.setText("Ошибка")

    def get_cpu_temperature(self):
        """Получает температуру CPU"""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None

            cpu_temp = None

            # Попробуем найти температуру пакета (Package)
            for name, entries in temps.items():
                for entry in entries:
                    if "package" in entry.label.lower():
                        return entry.current

            # Если не нашли Package, попробуем Core
            for name, entries in temps.items():
                for entry in entries:
                    if "core" in entry.label.lower():
                        if cpu_temp is None or entry.current > cpu_temp:
                            cpu_temp = entry.current

            # Если не нашли Core, возьмем первую доступную температуру
            if cpu_temp is None:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current is not None:
                            return entry.current

            return cpu_temp
        except (AttributeError, NotImplementedError):
            # sensors_temperatures не поддерживается на этой системе
            return None
        except Exception:
            return None