# ui/cpu_tab.py
import multiprocessing
import time
import psutil
import platform
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, 
                             QGroupBox, QSpinBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar
import core.cpu_scanner as cpu_core
import config

class CPUTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.optimal_workers = max(1, multiprocessing.cpu_count() - 1)
        self.processes = {}
        self.setup_ui()
        
        # Очередь и событие остановки
        self.process_queue = multiprocessing.Queue()
        self.shutdown_event = multiprocessing.Event()
        
        # Таймер обработки очереди
        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_queue_messages)
        self.queue_timer.start(100)

    def setup_ui(self):
        # ... (код UI для CPU вкладки)
    
    def validate_cpu_inputs(self):
        # ... (код валидации ввода)
    
    def toggle_cpu_start_stop(self):
        # ... (код управления поиском)
    
    # Остальные методы CPU...
    
    def update_found_count(self):
        found_count = self.parent.found_keys_tab.rowCount()
        self.cpu_found_label.setText(f"Найдено ключей: {found_count}")