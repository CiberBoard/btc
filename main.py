# main.py
import sys
import multiprocessing

# Эта строка КРИТИЧЕСКИ ВАЖНА для корректной работы multiprocessing в PyInstaller .exe
multiprocessing.freeze_support()

from PyQt5.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner
import config # Импортируем config для инициализации путей, если нужно

def main():
    app = QApplication(sys.argv)
    window = BitcoinGPUCPUScanner()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()