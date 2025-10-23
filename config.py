# config.py
import os
import sys
import re

from PyQt5.QtWidgets import QComboBox

# ============== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ и КОНСТАНТЫ ==============
# Определяем BASE_DIR перед использованием в setup_logger
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Получить у @BotFather
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # Ваш личный ID или ID группы

# Создаем необходимые папки при старте
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")
FOUND_KEYS_FILE = os.path.join(BASE_DIR, "Found_key_CUDA.txt")
CUBITCRACK_EXE = os.path.join(BASE_DIR, "cuBitcrack.exe")

MAX_KEY = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140
MAX_KEY_HEX = hex(MAX_KEY)[2:].upper()  # Кешированное значение

BTC_ADDR_REGEX = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')
# Стало (более гибкие регулярки):
SPEED_REGEX = re.compile(r'(\d+\.\d+|\d+)\s*MKey/s')
TOTAL_REGEX = re.compile(r'\(([\d,]+)\s*total\)')
ADDR_REGEX = re.compile(r'Address:\s*([13][a-km-zA-HJ-NP-Z1-9]{25,34})')
KEY_REGEX = re.compile(r'Private key:\s*([0-9a-fA-F]{64})')

# Приоритеты для Windows (для использования в core)
WINDOWS_GPU_PRIORITY_MAP = {
    0: 0x00000020,  # NORMAL_PRIORITY_CLASS
    1: 0x00000080,  # HIGH_PRIORITY_CLASS
    2: 0x00000100,  # REALTIME_PRIORITY_CLASS
}

WINDOWS_CPU_PRIORITY_MAP = {
    0: 0x00000040,  # IDLE_PRIORITY_CLASS
    1: 0x00004000,  # BELOW_NORMAL_PRIORITY_CLASS
    2: 0x00000020,  # NORMAL_PRIORITY_CLASS
    3: 0x00008000,  # ABOVE_NORMAL_PRIORITY_CLASS
    4: 0x00000080,  # HIGH_PRIORITY_CLASS
    5: 0x00000100,  # REALTIME_PRIORITY_CLASS
}

def make_combo32(start, end, default=None):
    """Создает выпадающий список с шагом 32"""
    items = [str(x) for x in range(start, end + 1, 32)]
    cb = QComboBox()
    cb.addItems(items)
    if default and str(default) in items:
        cb.setCurrentText(str(default))
    return cb