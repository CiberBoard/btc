# main.py
import sys
import multiprocessing
from PyQt5.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner

# Убедимся, что freeze_support вызывается до создания QApplication
# и до импорта других модулей, которые могут использовать multiprocessing
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BitcoinGPUCPUScanner()
    window.show()
    sys.exit(app.exec_())