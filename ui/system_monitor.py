# ui/system_monitor.py
import psutil
import time
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QProgressBar

class SystemMonitor(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()
        
        # Таймер обновления информации
        self.sysinfo_timer = QTimer()
        self.sysinfo_timer.timeout.connect(self.update_system_info)
        self.sysinfo_timer.start(2000)

    def setup_ui(self):
        layout = QGridLayout(self)
        # ... (код UI для системной информации)
    
    def update_system_info(self):
        # ... (код обновления системной информации)