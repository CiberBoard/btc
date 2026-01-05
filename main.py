# ✅ main.py — ЕДИНСТВЕННЫЙ корректный вариант
import sys
import os
from PyQt5.QtWidgets import QApplication
from ui.main_window import BitcoinGPUCPUScanner

def main():
    # Убедимся, что QApplication создаётся ОДИН раз
    app = QApplication(sys.argv)

    # Установим application name (важно для Windows)
    app.setApplicationName("BitcoinGPUCPUScanner")
    app.setOrganizationName("Jasst")

    # Создаём ОДНО окно
    window = BitcoinGPUCPUScanner()
    window.show()

    # Запускаем ЦИКЛ ОДИН РАЗ
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()