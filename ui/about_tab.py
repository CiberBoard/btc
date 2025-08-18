import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from utils.helpers import is_coincurve_available
import config

class AboutTab(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        coincurve_status = "✓ Доступна" if is_coincurve_available() else "✗ Не установлена"
        cubitcrack_status = "✓ Найден" if os.path.exists(config.CUBITCRACK_EXE) else "✗ Не найден"
        
        about_text = f"""
            <b>Bitcoin GPU/CPU Scanner</b><br>
            Версия: 5.0 (Улучшенная)<br>
            Автор: Jasst<br>
            GitHub: <a href='https://github.com/Jasst'>github.com/Jasst</a><br>
            <br><b>Возможности:</b><ul>
            <li>GPU поиск с помощью cuBitcrack</li>
            <li>Поддержка нескольких GPU устройств</li>
            <li>CPU поиск с мультипроцессингом</li>
            <li>Случайный и последовательный режимы</li>
            <li>Расширенная статистика и ETA</li>
            <li>Автоматическая оптимизация параметров GPU</li>
            <li>Управление приоритетами процессов</li>
            </ul>
            <br><b>Статус библиотек:</b><br>
            coincurve: {coincurve_status}<br>
            cuBitcrack.exe: {cubitcrack_status}<br>
        """
        
        label = QLabel(about_text)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)