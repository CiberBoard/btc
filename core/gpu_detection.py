"""
Модуль для автоматического определения GPU и рекомендации параметров Kangaroo
"""
import subprocess
import re
import os


def detect_gpus(etarkangaroo_exe):
    """
    Определяет количество доступных GPU

    Args:
        etarkangaroo_exe: путь к исполняемому файлу etarkangaroo.exe

    Returns:
        int: количество GPU или 1 (по умолчанию)
    """
    if not os.path.exists(etarkangaroo_exe):
        print(f"[⚠️] Файл не найден: {etarkangaroo_exe}")
        return 1

    gpu_count = 1  # По умолчанию

    # Пробуем разные способы определения GPU
    methods = [
        ('list', ['-list']),
        ('help', ['-h']),
        ('no_args', []),
    ]

    for method_name, args in methods:
        try:
            print(f"[🔍] Попытка определения GPU методом: {method_name}")

            result = subprocess.run(
                [etarkangaroo_exe] + args,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            output = result.stdout + result.stderr

            # Метод 1: Ищем "GPU #0:", "GPU #1:", "GPU #2:" и т.д.
            gpu_pattern1 = re.findall(r'GPU\s*#(\d+)', output, re.IGNORECASE)

            # Метод 2: Ищем "GPU 0:", "GPU 1:", "GPU 2:"
            gpu_pattern2 = re.findall(r'GPU\s+(\d+)[:\s]', output, re.IGNORECASE)

            # Метод 3: Ищем "[GPU 0]", "[GPU 1]"
            gpu_pattern3 = re.findall(r'\[GPU\s*(\d+)\]', output, re.IGNORECASE)

            # Метод 4: Ищем "Device 0:", "Device 1:"
            gpu_pattern4 = re.findall(r'Device\s+(\d+)', output, re.IGNORECASE)

            # Объединяем все найденные ID
            all_gpu_ids = set(gpu_pattern1 + gpu_pattern2 + gpu_pattern3 + gpu_pattern4)

            if all_gpu_ids:
                gpu_count = len(all_gpu_ids)
                print(f"[✓] Обнаружено GPU: {gpu_count}")

                # Пытаемся найти названия карт
                for gpu_id in sorted(all_gpu_ids, key=int):
                    # Ищем название после ID
                    name_patterns = [
                        rf'GPU\s*#{gpu_id}[:\s]+([^\n\r]+)',
                        rf'GPU\s+{gpu_id}[:\s]+([^\n\r]+)',
                        rf'\[GPU\s*{gpu_id}\]\s*([^\n\r]+)',
                        rf'Device\s+{gpu_id}[:\s]+([^\n\r]+)',
                    ]

                    gpu_name = None
                    for pattern in name_patterns:
                        match = re.search(pattern, output, re.IGNORECASE)
                        if match:
                            gpu_name = match.group(1).strip()
                            # Очищаем название от лишних символов
                            gpu_name = re.sub(r'\s+', ' ', gpu_name)
                            gpu_name = gpu_name.split('(')[0].strip()
                            break

                    if gpu_name:
                        print(f"    GPU #{gpu_id}: {gpu_name}")
                    else:
                        print(f"    GPU #{gpu_id}: (название не определено)")

                return gpu_count

        except subprocess.TimeoutExpired:
            print(f"[⚠️] Таймаут при попытке {method_name}")
            continue
        except Exception as e:
            print(f"[⚠️] Ошибка при попытке {method_name}: {e}")
            continue

    # Если ничего не нашли, пробуем через nvidia-smi (если доступен)
    try:
        print("[🔍] Попытка определения через nvidia-smi...")
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=3
        )

        if result.returncode == 0:
            gpu_names = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if gpu_names:
                gpu_count = len(gpu_names)
                print(f"[✓] Через nvidia-smi обнаружено GPU: {gpu_count}")
                for i, name in enumerate(gpu_names):
                    print(f"    GPU #{i}: {name}")
                return gpu_count
    except FileNotFoundError:
        print("[ℹ️] nvidia-smi не найден в системе")
    except Exception as e:
        print(f"[⚠️] Ошибка nvidia-smi: {e}")

    # Если всё не сработало, возвращаем значение по умолчанию
    print(f"[⚠️] Не удалось точно определить количество GPU, используем {gpu_count}")
    print("[💡] Подсказка: Укажите количество GPU вручную, если их больше одной")

    return gpu_count


def suggest_optimal_config(gpu_count, target_bits=134):
    """
    Предлагает оптимальную конфигурацию на основе количества GPU

    Args:
        gpu_count: количество GPU
        target_bits: размер целевого диапазона в битах

    Returns:
        dict: рекомендуемая конфигурация
    """
    # Базовая скорость для разных карт
    # GTX 1660 Super: ~450 MKeys/s
    # RTX 3060: ~700 MKeys/s
    # Средняя карта: ~400 MKeys/s
    base_speed_mkeys = 550  # Усреднённое значение для ваших карт

    # Общая скорость (линейное масштабирование с 90% эффективностью)
    total_speed = base_speed_mkeys * gpu_count * 0.9

    print(f"\n{'='*70}")
    print(f"АВТОМАТИЧЕСКАЯ КОНФИГУРАЦИЯ")
    print(f"{'='*70}")
    print(f"GPU найдено: {gpu_count}")
    print(f"Ожидаемая скорость: ~{total_speed:.0f} MKeys/s")
    print(f"Целевой диапазон: 2^{target_bits}")

    # Выбор размера поддиапазона в зависимости от мощности
    if gpu_count >= 2:
        # Две карты (GTX 1660 Super + RTX 3060)
        if total_speed >= 900:
            # Мощная конфигурация
            subrange_bits = 42
            dp = 21
            grid = '1024x512'
            duration = 90
        else:
            # Сбалансированная конфигурация
            subrange_bits = 40
            dp = 20
            grid = '512x512'
            duration = 60
    else:
        # Одна карта: консервативный подход
        subrange_bits = 38
        dp = 19
        grid = '256x256'
        duration = 60

    config = {
        'subrange_bits': subrange_bits,
        'dp': dp,
        'grid_params': grid,
        'scan_duration': duration,
        'estimated_speed': total_speed,
        'gpu_count': gpu_count
    }

    print(f"\n📋 Рекомендуемые параметры:")
    print(f"  • subrange_bits: {subrange_bits}")
    print(f"  • dp: {dp}")
    print(f"  • grid: {grid}")
    print(f"  • scan_duration: {duration}s")

    print(f"\n💡 Обоснование:")
    print(f"  • Размер окна: 2^{subrange_bits} = {2**subrange_bits:,} ключей")
    print(f"  • Время проверки окна: ~{duration}s")
    print(f"  • Окон в час: {3600/duration:.0f}")

    # Дополнительная информация для ваших карт
    if gpu_count == 2:
        print(f"\n🎮 Для GTX 1660 Super + RTX 3060:")
        print(f"  • GTX 1660 Super: ~450 MKeys/s")
        print(f"  • RTX 3060: ~700 MKeys/s")
        print(f"  • Суммарно: ~1000-1150 MKeys/s")

    print(f"{'='*70}\n")

    return config


def initialize_kangaroo_with_auto_config(etarkangaroo_exe, target_bits=134):
    """
    Инициализация Kangaroo с автоматическим определением конфигурации

    Args:
        etarkangaroo_exe: путь к exe файлу
        target_bits: размер диапазона в битах

    Returns:
        dict: оптимальная конфигурация
    """
    # 1. Определяем количество GPU
    gpu_count = detect_gpus(etarkangaroo_exe)

    # 2. Получаем оптимальную конфигурацию
    config = suggest_optimal_config(gpu_count, target_bits=target_bits)

    return config


def auto_configure_kangaroo(main_window):
    """
    Автоматическая настройка параметров Kangaroo
    Вызывается из ui/kangaroo_logic.py

    Args:
        main_window: ссылка на главное окно приложения

    Returns:
        dict или None: конфигурация или None при ошибке
    """
    from PyQt5.QtWidgets import QMessageBox, QInputDialog

    exe_path = main_window.kang_exe_edit.text().strip()

    if not os.path.exists(exe_path):
        QMessageBox.warning(
            main_window,
            "Ошибка",
            "Сначала укажите правильный путь к etarkangaroo.exe"
        )
        return None

    try:
        # Определяем размер диапазона (в битах)
        start_hex = main_window.kang_start_key_edit.text().strip()
        end_hex = main_window.kang_end_key_edit.text().strip()

        if start_hex and end_hex:
            try:
                start_int = int(start_hex.replace('0x', ''), 16)
                end_int = int(end_hex.replace('0x', ''), 16)
                target_bits = (end_int - start_int).bit_length()
            except:
                target_bits = 134  # По умолчанию
        else:
            target_bits = 134

        # Получаем оптимальные параметры
        config = initialize_kangaroo_with_auto_config(exe_path, target_bits)

        # Если обнаружена только 1 GPU, спрашиваем у пользователя
        if config['gpu_count'] == 1:
            reply = QMessageBox.question(
                main_window,
                "Подтверждение количества GPU",
                f"Автоматически обнаружено: <b>{config['gpu_count']} GPU</b><br><br>"
                f"Если у вас на самом деле больше GPU,<br>"
                f"хотите указать количество вручную?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                manual_count, ok = QInputDialog.getInt(
                    main_window,
                    "Количество GPU",
                    "Укажите реальное количество GPU:",
                    value=2,
                    min=1,
                    max=8
                )

                if ok and manual_count > 1:
                    print(f"[ℹ️] Пользователь указал вручную: {manual_count} GPU")
                    config = suggest_optimal_config(manual_count, target_bits)

        # Применяем в UI
        main_window.kang_subrange_spin.setValue(config['subrange_bits'])
        main_window.kang_dp_spin.setValue(config['dp'])
        main_window.kang_grid_edit.setText(config['grid_params'])
        main_window.kang_duration_spin.setValue(config['scan_duration'])

        QMessageBox.information(
            main_window,
            "✅ Автонастройка завершена",
            f"<b>Параметры настроены автоматически:</b><br><br>"
            f"🎮 Обнаружено GPU: <b>{config['gpu_count']}</b><br>"
            f"📊 Grid: <b>{config['grid_params']}</b><br>"
            f"🔢 Subrange: <b>{config['subrange_bits']}</b> бит<br>"
            f"🎯 DP: <b>{config['dp']}</b><br>"
            f"⏱️ Длительность: <b>{config['scan_duration']}</b> сек<br><br>"
            f"⚡ Ожидаемая скорость: ~<b>{config['estimated_speed']:.0f}</b> MKeys/s<br><br>"
            f"<i>Для GTX 1660 Super + RTX 3060:<br>"
            f"рекомендуется Grid 512x512 или 1024x512</i>"
        )

        main_window.append_log("✅ Автонастройка Kangaroo завершена", "success")
        main_window.append_log(f"📊 Параметры: Grid={config['grid_params']}, DP={config['dp']}, Subrange={config['subrange_bits']} бит", "success")

        return config

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[❌] Полная ошибка:\n{error_details}")

        QMessageBox.critical(
            main_window,
            "Ошибка",
            f"Не удалось выполнить автонастройку:\n{str(e)}\n\n"
            f"Используйте ручную настройку параметров."
        )
        main_window.append_log(f"❌ Ошибка автонастройки: {str(e)}", "error")
        return None