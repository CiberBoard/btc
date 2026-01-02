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
# config/settings_schema.py

# === Схемы полей: (key_in_json, widget_attr, getter/setter_type)
GPU_FIELDS = [
    ("gpu_target", "gpu_target_edit", "text"),
    ("gpu_start_key", "gpu_start_key_edit", "text"),
    ("gpu_end_key", "gpu_end_key_edit", "text"),
    ("gpu_device", "gpu_device_combo", "currentText"),
    ("blocks", "blocks_combo", "currentText"),
    ("threads", "threads_combo", "currentText"),
    ("points", "points_combo", "currentText"),
    ("gpu_random_mode", "gpu_random_checkbox", "isChecked"),
    ("gpu_restart_interval", "gpu_restart_interval_combo", "currentText"),
    ("gpu_min_range_size", "gpu_min_range_edit", "text"),
    ("gpu_max_range_size", "gpu_max_range_edit", "text"),
    ("gpu_priority", "gpu_priority_combo", "currentIndex"),
]

CPU_FIELDS = [
    ("cpu_target", "cpu_target_edit", "text"),
    ("cpu_start_key", "cpu_start_key_edit", "text"),
    ("cpu_end_key", "cpu_end_key_edit", "text"),
    ("cpu_prefix", "cpu_prefix_spin", "value"),
    ("cpu_workers", "cpu_workers_spin", "value"),
    ("cpu_attempts", "cpu_attempts_edit", "text"),
    ("cpu_mode", "cpu_mode", "runtime"),  # особый случай — из логики
    ("cpu_priority", "cpu_priority_combo", "currentIndex"),
]

KANGAROO_FIELDS = [
    ("kang_pubkey", "kang_pubkey_edit", "text"),
    ("kang_start_key", "kang_start_key_edit", "text"),
    ("kang_end_key", "kang_end_key_edit", "text"),
    ("kang_dp", "kang_dp_spin", "value"),
    ("kang_grid", "kang_grid_edit", "text"),
    ("kang_duration", "kang_duration_spin", "value"),
    ("kang_subrange_bits", "kang_subrange_spin", "value"),
    ("kang_exe_path", "kang_exe_edit", "text"),
    ("kang_temp_dir", "kang_temp_dir_edit", "text"),
]

ALL_FIELDS = GPU_FIELDS + CPU_FIELDS + KANGAROO_FIELDS

def apply_settings_to_ui(window, settings: dict):
    for key, attr_name, access_type in ALL_FIELDS:
        if not hasattr(window, attr_name):
            continue
        widget = getattr(window, attr_name)
        value = settings.get(key)

        if value is None:
            continue

        if access_type == "text":
            widget.setText(str(value))
        elif access_type == "value":
            widget.setValue(int(value))
        elif access_type == "isChecked":
            widget.setChecked(bool(value))
        elif access_type == "currentText":
            widget.setCurrentText(str(value))
        elif access_type == "currentIndex":
            widget.setCurrentIndex(int(value))
        # 'runtime' — пропускаем, обрабатываем отдельно

def extract_settings_from_ui(window) -> dict:
    settings = {}
    for key, attr_name, access_type in ALL_FIELDS:
        if not hasattr(window, attr_name):
            continue
        widget = getattr(window, attr_name)

        if access_type == "text":
            settings[key] = widget.text()
        elif access_type == "value":
            settings[key] = widget.value()
        elif access_type == "isChecked":
            settings[key] = widget.isChecked()
        elif access_type == "currentText":
            settings[key] = widget.currentText()
        elif access_type == "currentIndex":
            settings[key] = widget.currentIndex()
        elif access_type == "runtime":
            # Особые случаи: например, cpu_mode из логики
            if key == "cpu_mode":
                settings[key] = window.cpu_logic.cpu_mode
    return settings

def make_combo32(start, end, default=None):
    """Создает выпадающий список с шагом 32"""
    items = [str(x) for x in range(start, end + 1, 32)]
    cb = QComboBox()
    cb.addItems(items)
    if default and str(default) in items:
        cb.setCurrentText(str(default))
    return cb