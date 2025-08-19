# main.py
import sys
import os
# Добавляем корневую директорию проекта в sys.path, если нужно
# Это позволяет импортировать модули из корня, если main.py находится там же или глубже
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BitcoinGPUCPUScanner()
    window.show()
    sys.exit(app.exec_())