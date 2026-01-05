def setup_ui(self):
    self.setWindowTitle("Bitcoin GPU/CPU Scanner - Улучшенная версия")
    self.resize(1200, 900)
    main_widget = QWidget()
    self.setCentralWidget(main_widget)
    main_layout = QVBoxLayout(main_widget)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(15)
    self.main_tabs = QTabWidget()
    main_layout.addWidget(self.main_tabs)
    # =============== GPU TAB ===============
    gpu_tab = QWidget()
    gpu_layout = QVBoxLayout(gpu_tab)
    gpu_layout.setSpacing(10)
    # GPU адрес и диапазон
    gpu_addr_group = QGroupBox("GPU: Целевой адрес и диапазон ключей")
    gpu_addr_layout = QGridLayout(gpu_addr_group)
    gpu_addr_layout.setSpacing(8)
    gpu_addr_layout.addWidget(QLabel("BTC адрес:"), 0, 0)
    self.gpu_target_edit = QLineEdit()
    self.gpu_target_edit.setPlaceholderText("Введите Bitcoin адрес (1... или 3...)")
    gpu_addr_layout.addWidget(self.gpu_target_edit, 0, 1, 1, 3)
    gpu_addr_layout.addWidget(QLabel("Начальный ключ (hex):"), 1, 0)
    self.gpu_start_key_edit = QLineEdit("1")
    self.gpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
    gpu_addr_layout.addWidget(self.gpu_start_key_edit, 1, 1)
    gpu_addr_layout.addWidget(QLabel("Конечный ключ (hex):"), 1, 2)
    self.gpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
    self.gpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
    gpu_addr_layout.addWidget(self.gpu_end_key_edit, 1, 3)
    gpu_layout.addWidget(gpu_addr_group)
    # GPU параметры
    gpu_param_group = QGroupBox("GPU: Параметры и random режим")
    gpu_param_layout = QGridLayout(gpu_param_group)
    gpu_param_layout.setSpacing(8)
    gpu_param_layout.addWidget(QLabel("GPU устройство:"), 0, 0)
    self.gpu_device_combo = QComboBox()
    self.gpu_device_combo.setEditable(True)  # <-- Ключевая строка
    self.gpu_device_combo.addItem("0")
    self.gpu_device_combo.addItem("1")
    self.gpu_device_combo.addItem("2")
    self.gpu_device_combo.addItem("0,1")
    self.gpu_device_combo.addItem("0,1,2")
    self.gpu_device_combo.addItem("0,1,2,3")
    self.gpu_device_combo.setCurrentText("0")
    gpu_param_layout.addWidget(self.gpu_device_combo, 0, 1)
    gpu_param_layout.addWidget(QLabel("Блоки:"), 0, 2)
    self.blocks_combo = make_combo32(32, 2048, 256)
    gpu_param_layout.addWidget(self.blocks_combo, 0, 3)
    gpu_param_layout.addWidget(QLabel("Потоки/блок:"), 1, 0)
    self.threads_combo = make_combo32(32, 1024, 256)
    gpu_param_layout.addWidget(self.threads_combo, 1, 1)
    gpu_param_layout.addWidget(QLabel("Точки:"), 1, 2)
    self.points_combo = make_combo32(32, 1024, 256)
    gpu_param_layout.addWidget(self.points_combo, 1, 3)
    self.gpu_random_checkbox = QCheckBox("Случайный поиск в диапазоне")
    gpu_param_layout.addWidget(self.gpu_random_checkbox, 2, 0, 1, 2)
    gpu_param_layout.addWidget(QLabel("Интервал рестарта (сек):"), 2, 2)
    self.gpu_restart_interval_combo = QComboBox()
    self.gpu_restart_interval_combo.addItems([str(x) for x in range(10, 3601, 10)])
    self.gpu_restart_interval_combo.setCurrentText("300")
    self.gpu_restart_interval_combo.setEnabled(False)
    gpu_param_layout.addWidget(self.gpu_restart_interval_combo, 2, 3)
    self.gpu_random_checkbox.toggled.connect(self.gpu_restart_interval_combo.setEnabled)
    gpu_param_layout.addWidget(QLabel("Мин. размер диапазона:"), 3, 0)
    self.gpu_min_range_edit = QLineEdit("134217728")
    self.gpu_min_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
    gpu_param_layout.addWidget(self.gpu_min_range_edit, 3, 1)
    gpu_param_layout.addWidget(QLabel("Макс. размер диапазона:"), 3, 2)
    self.gpu_max_range_edit = QLineEdit("536870912")
    self.gpu_max_range_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
    gpu_param_layout.addWidget(self.gpu_max_range_edit, 3, 3)
    # Приоритет GPU
    gpu_param_layout.addWidget(QLabel("Приоритет GPU:"), 4, 0)
    self.gpu_priority_combo = QComboBox()
    self.gpu_priority_combo.addItems(["Нормальный", "Высокий", "Реального времени"])
    gpu_param_layout.addWidget(self.gpu_priority_combo, 4, 1)
    # --- СЖАТЫЕ КЛЮЧИ: чекбокс ---
    self.gpu_use_compressed_checkbox = QCheckBox("Использовать сжатые ключи (--use-compressed / -c)")
    self.gpu_use_compressed_checkbox.setChecked(True)
    self.gpu_use_compressed_checkbox.setToolTip(
        "✅ Ускоряет поиск в ~1.5–2× для адресов 1..., 3..., bc1...\n"
        "Использует 33-байтный публичный ключ вместо 65-байтного.\n"
        "Авто-отключается для несовместимых адресов."
    )
    gpu_param_layout.addWidget(self.gpu_use_compressed_checkbox, 4, 2, 1, 2)  # Занимает 1 ряд, 2 колонки
    # --- НОВОЕ: Воркеры на устройство ---
    gpu_param_layout.addWidget(QLabel("Воркеры/устройство:"), 5, 0)  # Новый ряд (индекс 5)
    self.gpu_workers_per_device_spin = QSpinBox()
    self.gpu_workers_per_device_spin.setRange(1, 16)  # Или другой разумный максимум
    self.gpu_workers_per_device_spin.setValue(1)  # По умолчанию 1 воркер
    gpu_param_layout.addWidget(self.gpu_workers_per_device_spin, 5, 1)  # Новый ряд (индекс 5)
    # --- КОНЕЦ НОВОГО ---
    gpu_layout.addWidget(gpu_param_group)
    # GPU кнопки
    gpu_button_layout = QHBoxLayout()
    self.gpu_start_stop_btn = QPushButton("Запустить GPU поиск")
    self.gpu_start_stop_btn.setStyleSheet("""
           QPushButton { background: #27ae60; font-weight: bold; font-size: 12pt;}
           QPushButton:hover {background: #2ecc71;}
           QPushButton:pressed {background: #219653;}
       """)
    self.gpu_optimize_btn = QPushButton("Авто-оптимизация")
    gpu_button_layout.addWidget(self.gpu_start_stop_btn)
    gpu_button_layout.addWidget(self.gpu_optimize_btn)
    gpu_button_layout.addStretch()
    gpu_layout.addLayout(gpu_button_layout)
    # GPU прогресс
    gpu_progress_group = QGroupBox("GPU: Прогресс и статистика")
    gpu_progress_layout = QGridLayout(gpu_progress_group)
    self.gpu_status_label = QLabel("Статус: Готов к работе")
    self.gpu_status_label.setStyleSheet("font-weight: bold; color: #3498db;")
    gpu_progress_layout.addWidget(self.gpu_status_label, 0, 0, 1, 2)
    self.gpu_speed_label = QLabel("Скорость: 0 MKey/s")
    gpu_progress_layout.addWidget(self.gpu_speed_label, 1, 0)
    self.gpu_time_label = QLabel("Время работы: 00:00:00")
    gpu_progress_layout.addWidget(self.gpu_time_label, 1, 1)
    self.gpu_checked_label = QLabel("Проверено ключей: 0")
    gpu_progress_layout.addWidget(self.gpu_checked_label, 2, 0)
    self.gpu_found_label = QLabel("Найдено ключей: 0")
    self.gpu_found_label.setStyleSheet("font-weight: bold; color: #27ae60;")
    gpu_progress_layout.addWidget(self.gpu_found_label, 2, 1)
    self.gpu_progress_bar = QProgressBar()
    self.gpu_progress_bar.setRange(0, 100)
    self.gpu_progress_bar.setValue(0)
    self.gpu_progress_bar.setFormat("Прогресс: неизвестен")
    gpu_progress_layout.addWidget(self.gpu_progress_bar, 3, 0, 1, 2)
    gpu_layout.addWidget(gpu_progress_group)
    self.gpu_progress_bar.setStyleSheet("""
                   QProgressBar {height: 25px; text-align: center; font-weight: bold; border: 1px solid #444; border-radius: 4px; background: #1a1a20;}
                   QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9); border-radius: 3px;}
               """)
    self.gpu_range_label = QLabel("Текущий диапазон: -")
    self.gpu_range_label.setStyleSheet("font-weight: bold; color: #e67e22;")
    gpu_layout.addWidget(self.gpu_range_label)
    self.main_tabs.addTab(gpu_tab, "GPU Поиск")
    # =============== НОВОЕ: GPU Status Group ===============
    if PYNVML_AVAILABLE:
        self.gpu_hw_status_group = QGroupBox("GPU: Аппаратный статус")
        gpu_hw_status_layout = QGridLayout(self.gpu_hw_status_group)
        gpu_hw_status_layout.setSpacing(6)
        self.gpu_util_label = QLabel("Загрузка GPU: - %")
        self.gpu_util_label.setStyleSheet("color: #f1c40f;")  # Желтый цвет
        gpu_hw_status_layout.addWidget(self.gpu_util_label, 0, 0)
        self.gpu_mem_label = QLabel("Память GPU: - / - MB")
        self.gpu_mem_label.setStyleSheet("color: #9b59b6;")  # Фиолетовый цвет
        gpu_hw_status_layout.addWidget(self.gpu_mem_label, 0, 1)
        self.gpu_temp_label = QLabel("Температура: - °C")
        self.gpu_temp_label.setStyleSheet("color: #e74c3c;")  # Красный цвет
        gpu_hw_status_layout.addWidget(self.gpu_temp_label, 1, 0)
        # Добавляем прогресс-бары для наглядности
        self.gpu_util_bar = QProgressBar()
        self.gpu_util_bar.setRange(0, 100)
        self.gpu_util_bar.setValue(0)
        self.gpu_util_bar.setFormat("Загрузка: %p%")
        self.gpu_util_bar.setStyleSheet("""
                       QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                       QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f1c40f, stop:1 #f39c12);} /* Оранжевый градиент */
                   """)
        gpu_hw_status_layout.addWidget(self.gpu_util_bar, 2, 0)
        self.gpu_mem_bar = QProgressBar()
        self.gpu_mem_bar.setRange(0, 100)
        self.gpu_mem_bar.setValue(0)
        self.gpu_mem_bar.setFormat("Память: %p%")
        self.gpu_mem_bar.setStyleSheet("""
                       QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                       QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9b59b6, stop:1 #8e44ad);} /* Фиолетовый градиент */
                   """)
        gpu_hw_status_layout.addWidget(self.gpu_mem_bar, 2, 1)
        gpu_layout.addWidget(self.gpu_hw_status_group)
        # =============== КОНЕЦ НОВОГО ===============
        # =============== KANGAROO TAB ===============
        kangaroo_tab = QWidget()
        kang_layout = QVBoxLayout(kangaroo_tab)
        kang_layout.setSpacing(10)
        kang_layout.setContentsMargins(10, 10, 10, 10)
        # Информация
        info_label = QLabel(
            "🦘 <b>Kangaroo Algorithm</b> - эффективный метод поиска приватных ключей "
            "в заданном диапазоне с использованием алгоритма Pollard's Kangaroo."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "color: #3498db; font-size: 10pt; padding: 8px; background: #1a2332; border-radius: 4px;")
        kang_layout.addWidget(info_label)

        # Основные параметры
        main_params_group = QGroupBox("Основные параметры")
        main_params_layout = QGridLayout(main_params_group)
        main_params_layout.setSpacing(8)

        # Публичный ключ
        main_params_layout.addWidget(QLabel("Публичный ключ (Hex):"), 0, 0)
        self.kang_pubkey_edit = QLineEdit()
        self.kang_pubkey_edit.setPlaceholderText("02... или 03... (66 символов) или 04... (130 символов)")
        main_params_layout.addWidget(self.kang_pubkey_edit, 0, 1, 1, 3)

        # Начальный ключ
        main_params_layout.addWidget(QLabel("Начальный ключ (Hex):"), 1, 0)
        self.kang_start_key_edit = QLineEdit("1")
        self.kang_start_key_edit.setPlaceholderText("Hex значение начала диапазона")
        main_params_layout.addWidget(self.kang_start_key_edit, 1, 1)

        # Конечный ключ
        main_params_layout.addWidget(QLabel("Конечный ключ (Hex):"), 1, 2)
        self.kang_end_key_edit = QLineEdit("FFFFFFFFFFFFFFFF")
        self.kang_end_key_edit.setPlaceholderText("Hex значение конца диапазона")
        main_params_layout.addWidget(self.kang_end_key_edit, 1, 3)

        kang_layout.addWidget(main_params_group)

        # Параметры алгоритма
        algo_params_group = QGroupBox("Параметры алгоритма")
        algo_params_layout = QGridLayout(algo_params_group)
        algo_params_layout.setSpacing(8)

        # DP
        algo_params_layout.addWidget(QLabel("DP (Distinguished Point):"), 0, 0)
        self.kang_dp_spin = QSpinBox()
        self.kang_dp_spin.setRange(10, 40)
        self.kang_dp_spin.setValue(20)
        self.kang_dp_spin.setToolTip("Параметр Distinguished Point. Чем выше, тем меньше памяти, но медленнее.")
        algo_params_layout.addWidget(self.kang_dp_spin, 0, 1)

        # Grid
        algo_params_layout.addWidget(QLabel("Grid (например, 256x256):"), 0, 2)
        self.kang_grid_edit = QLineEdit("256x256")
        self.kang_grid_edit.setPlaceholderText("ВысотахШирина")
        self.kang_grid_edit.setToolTip("Размер сетки для GPU вычислений")
        algo_params_layout.addWidget(self.kang_grid_edit, 0, 3)

        # Длительность
        algo_params_layout.addWidget(QLabel("Длительность сканирования (сек):"), 1, 0)
        self.kang_duration_spin = QSpinBox()
        self.kang_duration_spin.setRange(10, 3600)
        self.kang_duration_spin.setValue(300)
        self.kang_duration_spin.setToolTip("Время работы каждой сессии")
        algo_params_layout.addWidget(self.kang_duration_spin, 1, 1)

        # Размер поддиапазона
        algo_params_layout.addWidget(QLabel("Размер поддиапазона (биты):"), 1, 2)
        self.kang_subrange_spin = QSpinBox()
        self.kang_subrange_spin.setRange(20, 64)
        self.kang_subrange_spin.setValue(32)
        self.kang_subrange_spin.setToolTip("Размер случайного поддиапазона в битах (2^N)")
        algo_params_layout.addWidget(self.kang_subrange_spin, 1, 3)

        kang_layout.addWidget(algo_params_group)

        # Пути к файлам
        paths_group = QGroupBox("Пути к файлам")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setSpacing(8)

        # Путь к exe
        paths_layout.addWidget(QLabel("Etarkangaroo.exe:"), 0, 0)
        self.kang_exe_edit = QLineEdit()
        default_kang_path = os.path.join(config.BASE_DIR, "Etarkangaroo.exe")
        self.kang_exe_edit.setText(default_kang_path)
        paths_layout.addWidget(self.kang_exe_edit, 0, 1)

        self.kang_browse_exe_btn = QPushButton("📁 Обзор...")
        self.kang_browse_exe_btn.clicked.connect(self.browse_kangaroo_exe)
        self.kang_browse_exe_btn.setFixedWidth(100)
        paths_layout.addWidget(self.kang_browse_exe_btn, 0, 2)

        # Временная директория
        paths_layout.addWidget(QLabel("Временная директория:"), 1, 0)
        self.kang_temp_dir_edit = QLineEdit()
        default_temp = os.path.join(config.BASE_DIR, "kangaroo_temp")
        self.kang_temp_dir_edit.setText(default_temp)
        paths_layout.addWidget(self.kang_temp_dir_edit, 1, 1)

        self.kang_browse_temp_btn = QPushButton("📁 Обзор...")
        self.kang_browse_temp_btn.clicked.connect(self.browse_kangaroo_temp)
        self.kang_browse_temp_btn.setFixedWidth(100)
        paths_layout.addWidget(self.kang_browse_temp_btn, 1, 2)

        kang_layout.addWidget(paths_group)

        # ✨ НОВОЕ: Кнопка автонастройки (ВСТАВЬТЕ ЭТО СЮДА)
        auto_config_layout = QHBoxLayout()
        self.kang_auto_config_btn = QPushButton("🔧 Автонастройка параметров")
        self.kang_auto_config_btn.setMinimumHeight(40)
        self.kang_auto_config_btn.setStyleSheet("""
                  QPushButton {
                      background: #3498db;
                      font-weight: bold;
                      font-size: 11pt;
                  }
                  QPushButton:hover {
                      background: #2980b9;
                  }
                  QPushButton:pressed {
                      background: #21618c;
                  }
              """)
        self.kang_auto_config_btn.clicked.connect(self.kangaroo_logic.auto_configure)
        auto_config_layout.addWidget(self.kang_auto_config_btn)
        auto_config_layout.addStretch()
        kang_layout.addLayout(auto_config_layout)
        # ✨ КОНЕЦ НОВОГО
        # Кнопка запуска
        button_layout = QHBoxLayout()
        self.kang_start_stop_btn = QPushButton("🚀 Запустить Kangaroo")
        self.kang_start_stop_btn.setMinimumHeight(45)
        self.kang_start_stop_btn.setStyleSheet("""
                  QPushButton {
                      background: #27ae60;
                      font-weight: bold;
                      font-size: 12pt;
                  }
                  QPushButton:hover {
                      background: #2ecc71;
                  }
                  QPushButton:pressed {
                      background: #219653;
                  }
              """)
        self.kang_start_stop_btn.clicked.connect(self.kangaroo_logic.toggle_kangaroo_search)
        button_layout.addWidget(self.kang_start_stop_btn)
        button_layout.addStretch()
        kang_layout.addLayout(button_layout)

        # Статус и прогресс
        status_group = QGroupBox("Статус и прогресс")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(6)

        status_info_layout = QHBoxLayout()
        self.kang_status_label = QLabel("Статус: Готов к запуску")
        self.kang_status_label.setStyleSheet("font-weight: bold; color: #3498db; font-size: 11pt;")
        status_info_layout.addWidget(self.kang_status_label)
        status_info_layout.addStretch()
        status_layout.addLayout(status_info_layout)

        # Информация
        info_grid = QGridLayout()
        info_grid.setSpacing(10)

        self.kang_speed_label = QLabel("Скорость: 0 MKeys/s")
        self.kang_speed_label.setStyleSheet("color: #f39c12;")
        info_grid.addWidget(self.kang_speed_label, 0, 0)

        self.kang_time_label = QLabel("Время работы: 00:00:00")
        self.kang_time_label.setStyleSheet("color: #3498db;")
        info_grid.addWidget(self.kang_time_label, 0, 1)

        self.kang_session_label = QLabel("Сессия: #0")
        self.kang_session_label.setStyleSheet("color: #9b59b6;")
        info_grid.addWidget(self.kang_session_label, 0, 2)

        status_layout.addLayout(info_grid)

        # Текущий диапазон
        self.kang_range_label = QLabel("Текущий диапазон: -")
        self.kang_range_label.setStyleSheet("color: #e67e22; font-family: 'Courier New'; font-size: 9pt;")
        self.kang_range_label.setWordWrap(True)
        status_layout.addWidget(self.kang_range_label)

        kang_layout.addWidget(status_group)

        # Справка
        help_group = QGroupBox("ℹ️ Справка")
        help_layout = QVBoxLayout(help_group)
        help_text = QLabel(
            "<b>Как использовать:</b><br>"
            "1. Введите публичный ключ в формате Hex (сжатый или несжатый)<br>"
            "2. Укажите диапазон поиска (начальный и конечный ключи)<br>"
            "3. Настройте параметры алгоритма (DP, Grid, длительность)<br>"
            "4. Убедитесь, что путь к etarkangaroo.exe правильный<br>"
            "5. Нажмите 'Запустить Kangaroo'<br><br>"
            "<b>Примечание:</b> Алгоритм будет автоматически перебирать случайные "
            "поддиапазоны внутри указанного диапазона, что увеличивает шансы находки."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #95a5a6; font-size: 9pt;")
        help_layout.addWidget(help_text)
        help_group.setMaximumHeight(150)
        kang_layout.addWidget(help_group)

        kang_layout.addStretch()

        self.main_tabs.addTab(kangaroo_tab, "🦘 Kangaroo")
        # =============== END KANGAROO TAB ===============

    # =============== CPU TAB ===============
    cpu_tab = QWidget()
    cpu_layout = QVBoxLayout(cpu_tab)
    cpu_layout.setContentsMargins(10, 10, 10, 10)
    cpu_layout.setSpacing(10)
    # Системная информация
    sys_info_layout = QGridLayout()
    sys_info_layout.setSpacing(6)
    sys_info_layout.addWidget(QLabel("Процессор:"), 0, 0)
    self.cpu_label = QLabel(f"{multiprocessing.cpu_count()} ядер")
    sys_info_layout.addWidget(self.cpu_label, 0, 1)
    sys_info_layout.addWidget(QLabel("Память:"), 0, 2)
    self.mem_label = QLabel("")
    sys_info_layout.addWidget(self.mem_label, 0, 3)
    sys_info_layout.addWidget(QLabel("Загрузка:"), 1, 0)
    self.cpu_usage = QLabel("0%")
    sys_info_layout.addWidget(self.cpu_usage, 1, 1)
    sys_info_layout.addWidget(QLabel("Статус:"), 1, 2)
    self.cpu_status_label = QLabel("Ожидание запуска")
    sys_info_layout.addWidget(self.cpu_status_label, 1, 3)
    cpu_layout.addLayout(sys_info_layout)
    # =============== НОВОЕ: CPU Hardware Status Group ===============
    cpu_hw_status_group = QGroupBox("CPU: Аппаратный статус")
    cpu_hw_status_layout = QGridLayout(cpu_hw_status_group)
    cpu_hw_status_layout.setSpacing(6)
    self.cpu_temp_label = QLabel("Температура: - °C")
    self.cpu_temp_label.setStyleSheet("color: #e74c3c;")  # Красный цвет по умолчанию
    cpu_hw_status_layout.addWidget(self.cpu_temp_label, 0, 0)
    # Добавляем прогресс-бар для температуры (опционально)
    self.cpu_temp_bar = QProgressBar()
    self.cpu_temp_bar.setRange(0, 100)  # Диапазон от 0 до 100°C для примера
    self.cpu_temp_bar.setValue(0)
    self.cpu_temp_bar.setFormat("Темп: %p°C")
    self.cpu_temp_bar.setStyleSheet("""
                           QProgressBar {height: 15px; text-align: center; font-size: 8pt; border: 1px solid #444; border-radius: 3px; background: #1a1a20;}
                           QProgressBar::chunk {background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #27ae60, stop:1 #219653);} /* Зеленый градиент */
                       """)
    cpu_hw_status_layout.addWidget(self.cpu_temp_bar, 1, 0)
    cpu_layout.addWidget(cpu_hw_status_group)
    # =============== КОНЕЦ НОВОГО ===============
    # CPU параметры поиска
    cpu_params_group = QGroupBox("CPU: Параметры поиска")
    cpu_params_layout = QGridLayout(cpu_params_group)
    cpu_params_layout.setSpacing(8)
    cpu_params_layout.setColumnStretch(1, 1)
    cpu_params_layout.addWidget(QLabel("Целевой адрес:"), 0, 0)
    self.cpu_target_edit = QLineEdit()
    self.cpu_target_edit.setPlaceholderText("Введите BTC адрес (1 или 3)")
    cpu_params_layout.addWidget(self.cpu_target_edit, 0, 1, 1, 3)
    # Диапазон ключей для CPU
    cpu_keys_group = QGroupBox("Диапазон ключей")
    cpu_keys_layout = QGridLayout(cpu_keys_group)
    cpu_keys_layout.addWidget(QLabel("Начальный ключ:"), 0, 0)
    self.cpu_start_key_edit = QLineEdit("1")
    self.cpu_start_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
    cpu_keys_layout.addWidget(self.cpu_start_key_edit, 0, 1)
    cpu_keys_layout.addWidget(QLabel("Конечный ключ:"), 0, 2)
    self.cpu_end_key_edit = QLineEdit(config.MAX_KEY_HEX)
    self.cpu_end_key_edit.setValidator(QRegExpValidator(QRegExp("[0-9a-fA-F]+"), self))
    cpu_keys_layout.addWidget(self.cpu_end_key_edit, 0, 3)
    cpu_params_layout.addWidget(cpu_keys_group, 1, 0, 1, 4)
    # Параметры сканирования для CPU
    cpu_scan_params_group = QGroupBox("Параметры сканирования")
    cpu_scan_params_layout = QGridLayout(cpu_scan_params_group)
    param_input_width = 120
    cpu_scan_params_layout.addWidget(QLabel("Префикс:"), 0, 0)
    self.cpu_prefix_spin = QSpinBox()
    self.cpu_prefix_spin.setRange(1, 20)
    self.cpu_prefix_spin.setValue(8)
    self.cpu_prefix_spin.setFixedWidth(param_input_width)
    cpu_scan_params_layout.addWidget(self.cpu_prefix_spin, 0, 1)
    cpu_scan_params_layout.addWidget(QLabel("Попыток:"), 0, 2)
    self.cpu_attempts_edit = QLineEdit("10000000")
    self.cpu_attempts_edit.setEnabled(False)
    self.cpu_attempts_edit.setValidator(QRegExpValidator(QRegExp("\\d+"), self))
    self.cpu_attempts_edit.setFixedWidth(param_input_width)
    cpu_scan_params_layout.addWidget(self.cpu_attempts_edit, 0, 3)
    cpu_scan_params_layout.addWidget(QLabel("Режим:"), 1, 0)
    self.cpu_mode_combo = QComboBox()
    self.cpu_mode_combo.addItems(["Последовательный", "Случайный"])
    self.cpu_mode_combo.currentIndexChanged.connect(self.on_cpu_mode_changed)
    self.cpu_mode_combo.setFixedWidth(param_input_width)
    cpu_scan_params_layout.addWidget(self.cpu_mode_combo, 1, 1)
    cpu_scan_params_layout.addWidget(QLabel("Рабочих:"), 1, 2)
    self.cpu_workers_spin = QSpinBox()
    self.cpu_workers_spin.setRange(1, multiprocessing.cpu_count() * 2)
    self.cpu_workers_spin.setValue(self.optimal_workers)
    self.cpu_workers_spin.setFixedWidth(param_input_width)
    cpu_scan_params_layout.addWidget(self.cpu_workers_spin, 1, 3)
    cpu_scan_params_layout.addWidget(QLabel("Приоритет:"), 2, 0)
    self.cpu_priority_combo = QComboBox()
    self.cpu_priority_combo.addItems(
        ["Низкий", "Ниже среднего", "Средний", "Выше среднего", "Высокий", "Реального времени"])
    self.cpu_priority_combo.setCurrentIndex(3)  # Средний по умолчанию
    self.cpu_priority_combo.setFixedWidth(param_input_width)
    cpu_scan_params_layout.addWidget(self.cpu_priority_combo, 2, 1)
    cpu_params_layout.addWidget(cpu_scan_params_group, 2, 0, 1, 4)
    cpu_layout.addWidget(cpu_params_group)
    # CPU кнопки управления
    cpu_button_layout = QHBoxLayout()
    cpu_button_layout.setSpacing(10)
    self.cpu_start_stop_btn = QPushButton("Старт CPU (Ctrl+S)")
    self.cpu_start_stop_btn.setMinimumHeight(35)
    self.cpu_start_stop_btn.setStyleSheet("""
           QPushButton {
               background: #27ae60;
               font-weight: bold;
           }
           QPushButton:hover {
               background: #2ecc71;
           }
           QPushButton:pressed {
               background: #219653;
           }
       """)
    self.cpu_pause_resume_btn = QPushButton("Пауза (Ctrl+P)")
    self.cpu_pause_resume_btn.setMinimumHeight(35)
    self.cpu_pause_resume_btn.setStyleSheet("""
           QPushButton {
               background: #f39c12;
               color: black;
               font-weight: bold;
           }
           QPushButton:hover {
               background: #f1c40f;
           }
           QPushButton:pressed {
               background: #e67e22;
           }
       """)
    self.cpu_pause_resume_btn.setEnabled(False)
    cpu_button_layout.addWidget(self.cpu_start_stop_btn)
    cpu_button_layout.addWidget(self.cpu_pause_resume_btn)
    cpu_layout.addLayout(cpu_button_layout)
    # CPU общий прогресс
    cpu_progress_layout = QVBoxLayout()
    cpu_progress_layout.setSpacing(6)
    self.cpu_total_stats_label = QLabel("Статус: Ожидание запуска")
    self.cpu_total_stats_label.setStyleSheet("font-weight: bold; color: #3498db;")
    cpu_progress_layout.addWidget(self.cpu_total_stats_label)
    self.cpu_total_progress = QProgressBar()
    self.cpu_total_progress.setRange(0, 100)
    self.cpu_total_progress.setValue(0)
    self.cpu_total_progress.setFormat("Общий прогресс: %p%")
    cpu_progress_layout.addWidget(self.cpu_total_progress)
    self.cpu_eta_label = QLabel("Оставшееся время: -")
    self.cpu_eta_label.setStyleSheet("color: #f39c12;")
    cpu_progress_layout.addWidget(self.cpu_eta_label)
    cpu_layout.addLayout(cpu_progress_layout)
    # CPU статистика воркеров
    cpu_layout.addWidget(QLabel("Статистика воркеров:"))
    self.cpu_workers_table = QTableWidget(0, 5)
    self.cpu_workers_table.setHorizontalHeaderLabels(["ID", "Проверено", "Найдено", "Скорость", "Прогресс"])
    self.cpu_workers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    self.cpu_workers_table.verticalHeader().setVisible(False)
    self.cpu_workers_table.setAlternatingRowColors(True)
    cpu_layout.addWidget(self.cpu_workers_table, 1)
    self.main_tabs.addTab(cpu_tab, "CPU Поиск")
    # =============== FOUND KEYS TAB ===============
    keys_tab = QWidget()
    keys_layout = QVBoxLayout(keys_tab)
    keys_layout.setSpacing(10)
    self.found_keys_table = QTableWidget(0, 5)
    self.found_keys_table.setHorizontalHeaderLabels([
        "Время",
        "Адрес",
        "HEX ключ",
        "WIF ключ",
        "Источник"  # ← Новая колонка
    ])
    self.found_keys_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    self.found_keys_table.verticalHeader().setVisible(False)
    self.found_keys_table.setAlternatingRowColors(True)
    self.found_keys_table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.found_keys_table.customContextMenuRequested.connect(self.show_context_menu)
    keys_layout.addWidget(self.found_keys_table)

    export_layout = QHBoxLayout()
    self.export_keys_btn = QPushButton("Экспорт CSV")
    self.export_keys_btn.clicked.connect(self.export_keys_csv)
    export_layout.addWidget(self.export_keys_btn)
    self.save_all_btn = QPushButton("Сохранить все ключи")
    self.save_all_btn.clicked.connect(self.save_all_found_keys)
    export_layout.addWidget(self.save_all_btn)
    export_layout.addStretch()
    keys_layout.addLayout(export_layout)
    self.main_tabs.addTab(keys_tab, "Найденные ключи")
    # Добавляем вкладку конвертера
    self.setup_converter_tab()
    # =============== LOG TAB ===============
    log_tab = QWidget()
    log_layout = QVBoxLayout(log_tab)
    log_layout.setSpacing(10)
    self.log_output = QTextEdit()
    self.log_output.setReadOnly(True)
    self.log_output.setFont(QFont("Consolas", 10))
    log_layout.addWidget(self.log_output)
    log_button_layout = QHBoxLayout()
    self.clear_log_btn = QPushButton("Очистить лог")
    self.clear_log_btn.setStyleSheet("""
           QPushButton {background: #e74c3c; font-weight: bold;}
           QPushButton:hover {background: #c0392b;}
       """)
    log_button_layout.addWidget(self.clear_log_btn)
    self.open_log_btn = QPushButton("Открыть файл лога")
    self.open_log_btn.clicked.connect(self.open_log_file)
    log_button_layout.addWidget(self.open_log_btn)
    log_button_layout.addStretch()
    log_layout.addLayout(log_button_layout)
    self.main_tabs.addTab(log_tab, "Лог работы")

    # =============== ABOUT TAB ===============
    about_tab = QWidget()
    about_layout = QVBoxLayout(about_tab)
    coincurve_status = "✓ Доступна" if is_coincurve_available() else "✗ Не установлена"
    cubitcrack_status = "✓" if os.path.exists(config.CUBITCRACK_EXE) else "✗"
    about_layout.addWidget(QLabel(
        "<b>Bitcoin GPU/CPU Scanner</b><br>"
        "Версия: 5.0 (Улучшенная)<br>"
        "Автор: Jasst<br>"
        "GitHub: <a href='https://github.com/Jasst'>github.com/Jasst</a><br>"
        "<br><b>Возможности:</b><ul>"
        "<li>GPU поиск с помощью cuBitcrack</li>"
        "<li>Поддержка нескольких GPU устройств</li>"
        "<li>CPU поиск с мультипроцессингом</li>"
        "<li>Случайный и последовательный режимы</li>"
        "<li>Расширенная статистика и ETA</li>"
        "<li>Автоматическая оптимизация параметров GPU</li>"
        "<li>Управление приоритетами процессов</li>"
        "</ul>"
        f"<br><b>Статус библиотек:</b><br>"
        f"coincurve: {coincurve_status}<br>"
        f"cuBitcrack.exe: {cubitcrack_status} Найден<br>"
    ))
    self.main_tabs.addTab(about_tab, "О программе")
def apply_dark_theme(window):
    """
    Применяет тёмную тему к указанному QMainWindow или QWidget.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(20, 20, 30))
    palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.Base, QColor(28, 28, 38))
    palette.setColor(QPalette.AlternateBase, QColor(38, 38, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(40, 40, 45))
    palette.setColor(QPalette.ToolTipText, QColor(230, 230, 230))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(38, 38, 48))
    palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(80, 130, 180))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.PlaceholderText, QColor(120, 120, 120))
    window.setPalette(palette)

    window.setStyleSheet("""
        QWidget, QTabWidget, QTabBar, QGroupBox, QComboBox, QLineEdit, QTextEdit, QSpinBox {
            background: #181822;
            color: #F0F0F0;
            font-size: 9pt;
        }
        QTabWidget::pane { border: 1px solid #222; }
        QTabBar::tab {
            background: #252534;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 4px 4px 0 0;
            padding: 6px 20px;
            min-width: 120px;
        }
        QTabBar::tab:selected { background: #303054; color: #ffffff; }
        QTabBar::tab:!selected { background: #252534; color: #F0F0F0; }
        QGroupBox {
            border: 1px solid #444;
            border-radius: 6px;
            margin-top: 1ex;
            font-weight: bold;
            background: #232332;
            color: #F0F0F0;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 8px;
            background: transparent;
            color: #61afef;
        }
        QPushButton {
            background: #292A36;
            color: #F0F0F0;
            border: 1px solid #555;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-height: 35px;
        }
        QPushButton:hover { background: #3a3a45; }
        QPushButton:pressed { background: #24243A; }
        QPushButton:disabled { background: #202020; color: #777; }
        QLineEdit, QTextEdit {
            background: #202030;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 6px;
            selection-background-color: #3a5680;
        }
        QComboBox {
            background: #23233B;
            color: #F0F0F0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 4px;
        }
        QComboBox QAbstractItemView {
            background: #23233B;
            color: #F0F0F0;
            selection-background-color: #264080;
        }
        QTableWidget {
            background: #232332;
            color: #F0F0F0;
            gridline-color: #333;
            alternate-background-color: #222228;
            font-size: 10pt;
        }
        QHeaderView::section {
            background: #232332;
            color: #F0F0F0;
            padding: 4px;
            border: none;
            font-weight: bold;
        }
        QLabel { color: #CCCCCC; }
        QProgressBar {
            height: 25px;
            text-align: center;
            font-weight: bold;
            border: 1px solid #444;
            border-radius: 4px;
            background: #202030;
            color: #F0F0F0;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3498db, stop:1 #2980b9);
            border-radius: 3px;
        }
        QCheckBox { color: #CCCCCC; }
    """)