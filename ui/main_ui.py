import os
import json
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QTabWidget, QMessageBox
from .gpu_tab import GPUTab
from .cpu_tab import CPUTab
from .found_keys_tab import FoundKeysTab
from .log_tab import LogTab
from .about_tab import AboutTab
from utils.helpers import setup_logger
from logger import config

logger = setup_logger()

class BitcoinGPUCPUScanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bitcoin GPU/CPU Scanner")
        self.resize(1200, 900)
        self.set_dark_theme()
        self.setup_ui()
        self.load_settings()
        
        # Создаем файл для найденных ключей
        if not os.path.exists(config.FOUND_KEYS_FILE):
            open(config.FOUND_KEYS_FILE, 'w').close()

    def set_dark_theme(self):
        # Код темы остается таким же как в исходном файле
        # ...
        pass

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        self.main_tabs = QTabWidget()
        main_layout.addWidget(self.main_tabs)
        
        # Инициализация вкладок
        self.gpu_tab = GPUTab(self)
        self.cpu_tab = CPUTab(self)
        self.found_keys_tab = FoundKeysTab(self)
        self.log_tab = LogTab(self)
        self.about_tab = AboutTab(self)
        
        # Добавление вкладок
        self.main_tabs.addTab(self.gpu_tab, "GPU Поиск")
        self.main_tabs.addTab(self.cpu_tab, "CPU Поиск")
        self.main_tabs.addTab(self.found_keys_tab, "Найденные ключи")
        self.main_tabs.addTab(self.log_tab, "Лог работы")
        self.main_tabs.addTab(self.about_tab, "О программе")

    def append_log(self, message, level="normal"):
        """Добавляет сообщение в лог"""
        self.log_tab.append_log(message, level)

    def handle_found_key(self, key_data):
        """Обрабатывает найденный ключ"""
        self.found_keys_tab.add_key(key_data)
        # Обновляем счетчики на вкладках GPU и CPU
        if key_data.get('source') == 'GPU':
            self.gpu_tab.update_found_count()
        else:
            self.cpu_tab.update_found_count()

    def load_settings(self):
        """Загружает настройки из файла"""
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                
                # GPU settings
                self.gpu_tab.gpu_target_edit.setText(settings.get("gpu_target", ""))
                self.gpu_tab.gpu_start_key_edit.setText(settings.get("gpu_start_key", "1"))
                self.gpu_tab.gpu_end_key_edit.setText(settings.get("gpu_end_key", config.MAX_KEY_HEX))
                self.gpu_tab.gpu_device_combo.setCurrentText(str(settings.get("gpu_device", "0")))
                self.gpu_tab.blocks_combo.setCurrentText(str(settings.get("blocks", "512")))
                self.gpu_tab.threads_combo.setCurrentText(str(settings.get("threads", "512")))
                self.gpu_tab.points_combo.setCurrentText(str(settings.get("points", "512")))
                self.gpu_tab.gpu_random_checkbox.setChecked(settings.get("gpu_random_mode", False))
                self.gpu_tab.gpu_restart_interval_combo.setCurrentText(str(settings.get("gpu_restart_interval", "300")))
                self.gpu_tab.gpu_min_range_edit.setText(str(settings.get("gpu_min_range_size", "134217728")))
                self.gpu_tab.gpu_max_range_edit.setText(str(settings.get("gpu_max_range_size", "536870912")))
                self.gpu_tab.gpu_priority_combo.setCurrentIndex(settings.get("gpu_priority", 0))
                self.gpu_tab.gpu_workers_per_device_spin.setValue(settings.get("gpu_workers_per_device", 1))
                
                # CPU settings
                self.cpu_tab.cpu_target_edit.setText(settings.get("cpu_target", ""))
                self.cpu_tab.cpu_start_key_edit.setText(settings.get("cpu_start_key", "1"))
                self.cpu_tab.cpu_end_key_edit.setText(settings.get("cpu_end_key", config.MAX_KEY_HEX))
                self.cpu_tab.cpu_prefix_spin.setValue(settings.get("cpu_prefix", 8))
                self.cpu_tab.cpu_workers_spin.setValue(settings.get("cpu_workers", self.cpu_tab.optimal_workers))
                self.cpu_tab.cpu_attempts_edit.setText(str(settings.get("cpu_attempts", 10000000)))
                self.cpu_tab.cpu_mode_combo.setCurrentIndex(1 if settings.get("cpu_mode", "sequential") == "random" else 0)
                self.cpu_tab.cpu_priority_combo.setCurrentIndex(settings.get("cpu_priority", 3))
                
                self.append_log("Настройки загружены", "success")
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {str(e)}")
                self.append_log("Ошибка загрузки настроек: " + str(e), "error")

    def save_settings(self):
        """Сохраняет настройки в файл"""
        settings = {
            # GPU settings
            "gpu_target": self.gpu_tab.gpu_target_edit.text(),
            "gpu_start_key": self.gpu_tab.gpu_start_key_edit.text(),
            "gpu_end_key": self.gpu_tab.gpu_end_key_edit.text(),
            "gpu_device": self.gpu_tab.gpu_device_combo.currentText(),
            "blocks": self.gpu_tab.blocks_combo.currentText(),
            "threads": self.gpu_tab.threads_combo.currentText(),
            "points": self.gpu_tab.points_combo.currentText(),
            "gpu_random_mode": self.gpu_tab.gpu_random_checkbox.isChecked(),
            "gpu_restart_interval": self.gpu_tab.gpu_restart_interval_combo.currentText(),
            "gpu_min_range_size": self.gpu_tab.gpu_min_range_edit.text(),
            "gpu_max_range_size": self.gpu_tab.gpu_max_range_edit.text(),
            "gpu_priority": self.gpu_tab.gpu_priority_combo.currentIndex(),
            "gpu_workers_per_device": self.gpu_tab.gpu_workers_per_device_spin.value(),
            
            # CPU settings
            "cpu_target": self.cpu_tab.cpu_target_edit.text(),
            "cpu_start_key": self.cpu_tab.cpu_start_key_edit.text(),
            "cpu_end_key": self.cpu_tab.cpu_end_key_edit.text(),
            "cpu_prefix": self.cpu_tab.cpu_prefix_spin.value(),
            "cpu_workers": self.cpu_tab.cpu_workers_spin.value(),
            "cpu_attempts": int(self.cpu_tab.cpu_attempts_edit.text()) if self.cpu_tab.cpu_attempts_edit.isEnabled() else 10000000,
            "cpu_mode": self.cpu_tab.cpu_mode,
            "cpu_priority": self.cpu_tab.cpu_priority_combo.currentIndex(),
        }
        
        settings_path = os.path.join(config.BASE_DIR, "settings.json")
        try:
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
            self.append_log("Настройки сохранены", "success")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {str(e)}")
            self.append_log(f"Ошибка сохранения настроек: {str(e)}", "error")

    def closeEvent(self, event):
        """Обработчик закрытия приложения"""
        # Проверка активных процессов
        active_processes = False
        if self.gpu_tab.gpu_is_running:
            active_processes = True
        if self.cpu_tab.processes:
            active_processes = True
        
        if active_processes:
            reply = QMessageBox.question(
                self, 'Подтверждение закрытия',
                "Активные процессы все еще выполняются. Вы уверены, что хотите закрыть приложение?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        # Корректное завершение
        self.save_settings()
        if self.gpu_tab.gpu_is_running:
            self.gpu_tab.stop_gpu_search()
        if self.cpu_tab.processes:
            self.cpu_tab.stop_cpu_search()
        self.cpu_tab.close_queue()
        event.accept()