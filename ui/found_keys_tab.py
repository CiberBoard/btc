import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, \
    QFileDialog, QMenu, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from logger import config

class FoundKeysTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        self.found_keys_table = QTableWidget(0, 4)
        self.found_keys_table.setHorizontalHeaderLabels(["Время", "Адрес", "HEX ключ", "WIF ключ"])
        self.found_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.found_keys_table.verticalHeader().setVisible(False)
        self.found_keys_table.setAlternatingRowColors(True)
        self.found_keys_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.found_keys_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.found_keys_table)
        
        export_layout = QHBoxLayout()
        self.export_keys_btn = QPushButton("Экспорт CSV")
        self.export_keys_btn.clicked.connect(self.export_keys_csv)
        export_layout.addWidget(self.export_keys_btn)
        
        self.save_all_btn = QPushButton("Сохранить все ключи")
        self.save_all_btn.clicked.connect(self.save_all_found_keys)
        export_layout.addWidget(self.save_all_btn)
        
        export_layout.addStretch()
        layout.addLayout(export_layout)

    def add_key(self, key_data):
        """Добавляет найденный ключ в таблицу"""
        row = self.found_keys_table.rowCount()
        self.found_keys_table.insertRow(row)
        
        # Время
        time_item = QTableWidgetItem(key_data['timestamp'])
        time_item.setTextAlignment(Qt.AlignCenter)
        time_item.setForeground(QColor(100, 255, 100))
        self.found_keys_table.setItem(row, 0, time_item)
        
        # Адрес
        addr_item = QTableWidgetItem(key_data['address'])
        addr_item.setTextAlignment(Qt.AlignCenter)
        addr_item.setForeground(QColor(255, 215, 0))
        self.found_keys_table.setItem(row, 1, addr_item)
        
        # HEX ключ
        hex_item = QTableWidgetItem(key_data['hex_key'])
        hex_item.setTextAlignment(Qt.AlignCenter)
        hex_item.setForeground(QColor(100, 200, 255))
        self.found_keys_table.setItem(row, 2, hex_item)
        
        # WIF ключ
        wif_item = QTableWidgetItem(key_data['wif_key'])
        wif_item.setTextAlignment(Qt.AlignCenter)
        wif_item.setForeground(QColor(255, 150, 150))
        self.found_keys_table.setItem(row, 3, wif_item)
        
        self.found_keys_table.scrollToBottom()
        self.save_found_key(key_data)

    def show_context_menu(self, position):
        """Показывает контекстное меню для таблицы ключей"""
        menu = QMenu()
        copy_wif_action = menu.addAction("Копировать WIF ключ")
        copy_hex_action = menu.addAction("Копировать HEX ключ")
        copy_addr_action = menu.addAction("Копировать адрес")
        menu.addSeparator()
        save_all_action = menu.addAction("Сохранить все ключи в файл")
        clear_action = menu.addAction("Очистить таблицу")
        
        action = menu.exec_(self.found_keys_table.viewport().mapToGlobal(position))
        selected = self.found_keys_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        
        if action == clear_action:
            self.found_keys_table.setRowCount(0)
            self.parent.append_log("Таблица найденных ключей очищена", "normal")
            return
        
        if action == copy_wif_action:
            wif_item = self.found_keys_table.item(row, 3)
            QApplication.clipboard().setText(wif_item.text())
            self.parent.append_log("WIF ключ скопирован в буфер обмена", "success")
        
        elif action == copy_hex_action:
            hex_item = self.found_keys_table.item(row, 2)
            QApplication.clipboard().setText(hex_item.text())
            self.parent.append_log("HEX ключ скопирован в буфер обмена", "success")
        
        elif action == copy_addr_action:
            addr_item = self.found_keys_table.item(row, 1)
            QApplication.clipboard().setText(addr_item.text())
            self.parent.append_log("Адрес скопирован в буфер обмена", "success")
        
        elif action == save_all_action:
            self.save_all_found_keys()

    def export_keys_csv(self):
        """Экспортирует ключи в CSV файл"""
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", "found_keys.csv", "CSV files (*.csv)")
        if not path:
            return
        
        try:
            with open(path, "w", newline='', encoding="utf-8") as f:
                f.write("Время,Адрес,HEX ключ,WIF ключ\n")
                for row in range(self.found_keys_table.rowCount()):
                    row_items = []
                    for col in range(4):
                        item = self.found_keys_table.item(row, col)
                        row_items.append(item.text() if item else "")
                    f.write(','.join(row_items) + "\n")
            self.parent.append_log(f"Экспортировано в {path}", "success")
        except Exception as e:
            self.parent.append_log(f"Ошибка экспорта: {str(e)}", "error")

    def save_found_key(self, key_data):
        """Сохраняет ключ в файл"""
        try:
            with open(config.FOUND_KEYS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{key_data['timestamp']}\t{key_data['address']}\t{key_data['hex_key']}\t{key_data['wif_key']}\n")
        except Exception as e:
            self.parent.append_log(f"Ошибка сохранения ключа: {str(e)}", "error")

    def save_all_found_keys(self):
        """Сохраняет все ключи в файл"""
        try:
            with open(config.FOUND_KEYS_FILE, "w", encoding="utf-8") as f:
                for row in range(self.found_keys_table.rowCount()):
                    time = self.found_keys_table.item(row, 0).text()
                    addr = self.found_keys_table.item(row, 1).text()
                    hex_key = self.found_keys_table.item(row, 2).text()
                    wif_key = self.found_keys_table.item(row, 3).text()
                    f.write(f"{time}\t{addr}\t{hex_key}\t{wif_key}\n")
            self.parent.append_log(f"Все ключи сохранены в {config.FOUND_KEYS_FILE}", "success")
        except Exception as e:
            self.parent.append_log(f"Ошибка сохранения ключей: {str(e)}", "error")