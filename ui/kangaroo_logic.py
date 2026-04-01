# ui/kangaroo_logic.py
import os
import time
from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QMessageBox
from core.kangaroo_worker import KangarooWorker
import logging  # ← ДОБАВЛЕНО

logger = logging.getLogger(__name__)


class KangarooLogic:
    """Класс для управления логикой Kangaroo поиска"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.worker_thread = None
        self.worker = None
        self.is_running = False
        self.start_time = None
        self.session_count = 0
        self.total_speed = 0.0
        self.current_range_start = ""
        self.current_range_end = ""

        # Таймер для обновления времени
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_display)

    def toggle_kangaroo_search(self):
        """Переключение запуск/остановка поиска"""
        if self.is_running:
            self.stop_kangaroo_search()
        else:
            self.start_kangaroo_search()

    def start_kangaroo_search(self):
        """Запуск Kangaroo поиска"""
        try:
            # Валидация входных данных
            pubkey = self.main_window.kang_pubkey_edit.text().strip()
            if not pubkey or len(pubkey) < 64:
                QMessageBox.warning(
                    self.main_window,
                    "Ошибка",
                    "Введите корректный публичный ключ (минимум 64 символа)"
                )
                return

            rb_hex = self.main_window.kang_start_key_edit.text().strip()
            re_hex = self.main_window.kang_end_key_edit.text().strip()

            if not rb_hex or not re_hex:
                QMessageBox.warning(
                    self.main_window,
                    "Ошибка",
                    "Введите начальный и конечный ключи диапазона"
                )
                return

            # Проверка существования файла etarkangaroo.exe
            exe_path = self.main_window.kang_exe_edit.text().strip()
            if not os.path.exists(exe_path):
                QMessageBox.critical(
                    self.main_window,
                    "Ошибка",
                    f"Файл не найден: {exe_path}\n\nУкажите правильный путь к etarkangaroo.exe"
                )
                return

            # Создание временной директории
            temp_dir = self.main_window.kang_temp_dir_edit.text().strip()
            os.makedirs(temp_dir, exist_ok=True)

            # Параметры для worker
            params = {
                'etarkangaroo_exe': exe_path,
                'pubkey_hex': pubkey,
                'rb_hex': rb_hex,
                're_hex': re_hex,
                'dp': int(self.main_window.kang_dp_spin.value()),
                'grid_params': self.main_window.kang_grid_edit.text().strip(),
                'temp_dir': temp_dir,
                'scan_duration': int(self.main_window.kang_duration_spin.value()),
                'subrange_bits': int(self.main_window.kang_subrange_spin.value())
            }

            # Создание и запуск worker
            self.worker = KangarooWorker(params)
            self.worker_thread = QThread()
            self.worker.moveToThread(self.worker_thread)

            # Подключение сигналов
            self.worker.log_message.connect(self.handle_log_message)
            self.worker.status_update.connect(self.handle_status_update)
            self.worker.range_update.connect(self.handle_range_update)
            self.worker.found_key.connect(self.handle_found_key)
            self.worker.finished.connect(self.handle_worker_finished)

            self.worker_thread.started.connect(self.worker.run)

            # Запуск
            self.is_running = True
            self.start_time = time.time()
            self.session_count = 0
            self.worker_thread.start()
            self.timer.start(500)

            # Обновление UI
            self.main_window.kang_start_stop_btn.setText("⏹ Остановить Kangaroo")
            self.main_window.kang_start_stop_btn.setStyleSheet("""
                QPushButton {background: #e74c3c; font-weight: bold;}
                QPushButton:hover {background: #c0392b;}
            """)
            self.main_window.kang_status_label.setText("Статус: Работает...")
            self.main_window.kang_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")

            # Блокировка полей ввода
            self.set_input_enabled(False)

            self.main_window.append_log("🦘 Kangaroo поиск запущен", "success")

        except Exception as e:
            logger.exception("Ошибка запуска Kangaroo")
            QMessageBox.critical(
                self.main_window,
                "Ошибка",
                f"Не удалось запустить Kangaroo поиск:\n{str(e)}"
            )
            self.is_running = False

    def stop_kangaroo_search(self):
        """Остановка Kangaroo поиска"""
        try:
            if self.worker:
                self.worker.stop()

            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(3000)

            self.is_running = False
            self.timer.stop()

            # Обновление UI
            self.main_window.kang_start_stop_btn.setText("🚀 Запустить Kangaroo")
            self.main_window.kang_start_stop_btn.setStyleSheet("""
                QPushButton {background: #27ae60; font-weight: bold;}
                QPushButton:hover {background: #2ecc71;}
            """)
            self.main_window.kang_status_label.setText("Статус: Остановлен")
            self.main_window.kang_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

            # Разблокировка полей ввода
            self.set_input_enabled(True)

            self.main_window.append_log("🛑 Kangaroo поиск остановлен", "warning")

        except Exception as e:
            logger.exception("Ошибка остановки Kangaroo")
            self.main_window.append_log(f"Ошибка остановки: {str(e)}", "error")

    def handle_log_message(self, message):
        """Обработка лог-сообщений"""
        self.main_window.append_log(message)

    def handle_status_update(self, speed_mkeys, elapsed_sec, session_num):
        """Обновление статистики"""
        self.total_speed = speed_mkeys
        self.session_count = session_num

        self.main_window.kang_speed_label.setText(f"Скорость: {speed_mkeys:.2f} MKeys/s")
        self.main_window.kang_session_label.setText(f"Сессия: #{session_num}")

    def handle_range_update(self, rb, re):
        self.current_range_start = rb
        self.current_range_end = re

        rb_clean = rb.lstrip('0') or '0'
        re_clean = re.lstrip('0') or '0'

        # Показываем первые/последние 8 символов
        rb_short = f"{rb_clean[:8]}…{rb_clean[-10:]}" if len(rb_clean) > 16 else rb_clean
        re_short = f"{re_clean[:8]}…{re_clean[-10:]}" if len(re_clean) > 16 else re_clean

        self.main_window.kang_range_label.setText(
            f"rb = 0x{rb_short}\n"
            f"re = 0x{re_short}"
        )

    def handle_found_key(self, private_hex):
        """Обработка найденного ключа"""
        try:
            from core.hextowif import generate_all_from_hex

            # Генерация всех форматов ключа
            result = generate_all_from_hex(private_hex, compressed=True, testnet=False)

            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

            # Добавление в таблицу
            key_data = {
                'timestamp': timestamp,
                'address': result['P2PKH'],
                'hex_key': private_hex,
                'wif_key': result['WIF'],
                'source': 'KANGAROO'
            }

            self.main_window.handle_found_key(key_data)

            # Остановка поиска после находки
            self.stop_kangaroo_search()

            QMessageBox.information(
                self.main_window,
                "🎉 Ключ найден!",
                f"<b>Kangaroo нашел приватный ключ!</b><br><br>"
                f"<b>Адрес:</b> {result['P2PKH']}<br>"
                f"<b>HEX:</b> {private_hex[:32]}...<br>"
                f"<b>WIF:</b> {result['WIF'][:20]}...<br><br>"
                f"Ключ сохранен в таблице найденных ключей."
            )

        except Exception as e:
            logger.exception("Ошибка обработки найденного ключа")
            self.main_window.append_log(f"Ошибка обработки ключа: {str(e)}", "error")

    def handle_worker_finished(self, success):
        """Обработка завершения worker"""
        if self.is_running:
            if success:
                self.main_window.append_log("✅ Kangaroo успешно завершен", "success")
            else:
                self.main_window.append_log("⚠ Kangaroo завершен без результата", "warning")

            self.stop_kangaroo_search()

    def update_time_display(self):
        """Обновление отображения времени работы"""
        if self.is_running and self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60

            self.main_window.kang_time_label.setText(
                f"Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )

    def set_input_enabled(self, enabled):
        """Включение/выключение полей ввода"""
        self.main_window.kang_pubkey_edit.setEnabled(enabled)
        self.main_window.kang_start_key_edit.setEnabled(enabled)
        self.main_window.kang_end_key_edit.setEnabled(enabled)
        self.main_window.kang_dp_spin.setEnabled(enabled)
        self.main_window.kang_grid_edit.setEnabled(enabled)
        self.main_window.kang_duration_spin.setEnabled(enabled)
        self.main_window.kang_subrange_spin.setEnabled(enabled)
        self.main_window.kang_exe_edit.setEnabled(enabled)
        self.main_window.kang_temp_dir_edit.setEnabled(enabled)
        self.main_window.kang_browse_exe_btn.setEnabled(enabled)
        self.main_window.kang_browse_temp_btn.setEnabled(enabled)

    def auto_configure(self):
        self.main_window.kang_dp_spin.setValue(22)
        self.main_window.kang_subrange_spin.setValue(36)
        self.main_window.kang_duration_spin.setValue(600)
        self.main_window.append_log("Kangaroo: параметры автонастроены (DP=22, 2^36, 10min)", "success")