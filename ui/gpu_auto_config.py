"""
Модуль для автоматического определения GPU и рекомендации параметров
🔹 Поддерживает: Kangaroo + GPU/CuBitcrack
🛠 УЛУЧШЕНИЕ: Добавлены type hints, логирование и поддержка cuBitcrack
"""
import subprocess
import re
import os
import logging
from typing import Dict, Optional, Set, List, Tuple, Any, Union
# 🛠 ДОБАВЛЕНО: импорт config для доступа к CUBITCRACK_EXE
import config  # ← ЭТА СТРОКА БЫЛА ОТСУТСТВУЕТ

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И ПАТТЕРНЫ
# ═══════════════════════════════════════════════

# 🛠 Скомпилированные регулярные выражения (вызываются один раз)
GPU_ID_PATTERNS: List[re.Pattern] = [
    re.compile(r'GPU\s*#(\d+)', re.IGNORECASE),
    re.compile(r'GPU\s+(\d+)[:\s]', re.IGNORECASE),
    re.compile(r'\[GPU\s*(\d+)\]', re.IGNORECASE),
    re.compile(r'Device\s+(\d+)', re.IGNORECASE),
    # 🛠 ДОБАВЛЕНО: паттерны для cuBitcrack вывода
    re.compile(r'cudaDeviceGetCount.*?(\d+)', re.IGNORECASE),
    re.compile(r'Found\s+(\d+)\s+GPU', re.IGNORECASE),
]

GPU_NAME_RAW_PATTERNS: List[str] = [
    r'GPU\s*#{}[:\s]+([^\n\r]+)',
    r'GPU\s+{}[:\s]+([^\n\r]+)',
    r'\[GPU\s*{}\]\s*([^\n\r]+)',
    r'Device\s+{}[:\s]+([^\n\r]+)',
    # 🛠 ДОБАВЛЕНО: паттерны для cuBitcrack
    r'GPU\s*{}[:\s]+([^\n\r]+)',
]

# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ ДЛЯ KANGAROO
# ═══════════════════════════════════════════════
KANGAROO_DEFAULT_TARGET_BITS: int = 134
KANGAROO_BASE_SPEED_MKEYS: float = 550.0
KANGAROO_EFFICIENCY_FACTOR: float = 0.9

# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ ДЛЯ GPU/CUBITCRACK
# ═══════════════════════════════════════════════
# 🛠 НОВЫЕ: Константы для автоконфигурации cuBitcrack
CUBITCRACK_BASE_SPEED_MKEYS: float = 500.0  # Усреднённая скорость на карту
CUBITCRACK_EFFICIENCY_FACTOR: float = 0.85  # Чуть ниже из-за накладных расходов CUDA

# 🛠 НОВЫЕ: Параметры по умолчанию для разных конфигураций
CUBITCRACK_CONFIGS: Dict[str, Dict[str, Any]] = {
    'single_slow': {  # 1 карта или низкая общая скорость
        'blocks': '128',
        'threads': '64',
        'points': '128',
        'description': 'Консервативная (1 GPU или низкая скорость)'
    },
    'single_fast': {  # 1 быстрая карта (RTX 30/40)
        'blocks': '256',
        'threads': '128',
        'points': '256',
        'description': 'Оптимизированная для 1 быстрой карты'
    },
    'multi_balanced': {  # 2+ карты, средняя скорость
        'blocks': '256',
        'threads': '128',
        'points': '256',
        'description': 'Сбалансированная для нескольких GPU'
    },
    'multi_aggressive': {  # 2+ быстрые карты
        'blocks': '288',
        'threads': '128',
        'points': '512',
        'description': 'Агрессивная для мощных мульти-GPU'
    },
}

# ═══════════════════════════════════════════════
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ОБЩИЕ)
# ═══════════════════════════════════════════════

def _extract_gpu_ids(output: str) -> Set[str]:
    """Извлекает уникальные ID GPU из вывода любого инструмента"""
    ids: Set[str] = set()
    for pattern in GPU_ID_PATTERNS:
        ids.update(pattern.findall(output))
    return ids


def _extract_gpu_names(output: str, gpu_ids: Set[str]) -> Dict[str, str]:
    """Извлекает названия GPU по их ID"""
    names: Dict[str, str] = {}
    for gid in gpu_ids:
        found_name = None
        for raw_pat in GPU_NAME_RAW_PATTERNS:
            try:
                match = re.search(raw_pat.format(gid), output, re.IGNORECASE)
                if match:
                    found_name = match.group(1).strip()
                    found_name = re.sub(r'\s+', ' ', found_name).split('(')[0].strip()
                    break
            except Exception:
                continue
        names[gid] = found_name if found_name else "(название не определено)"
    return names


def _detect_via_nvidia_smi() -> Tuple[int, List[str]]:
    """
    Резервное определение GPU через nvidia-smi

    :return: Кортеж (количество_карт, список_названий)
    """
    try:
        logger.debug("Попытка определения через nvidia-smi...")
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            gpu_names = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if gpu_names:
                logger.info(f"Через nvidia-smi обнаружено {len(gpu_names)} GPU")
                return len(gpu_names), gpu_names
    except FileNotFoundError:
        logger.debug("nvidia-smi не найден в системе")
    except Exception as e:
        logger.warning(f"Ошибка nvidia-smi: {e}")
    return 1, ["Unknown GPU"]


# ═══════════════════════════════════════════════
# 🔧 ФУНКЦИИ ДЛЯ KANGAROO (СОХРАНЕНЫ)
# ═══════════════════════════════════════════════

def detect_gpus(etarkangaroo_exe: str) -> int:
    """
    Определяет количество доступных GPU через etarkangaroo.exe
    🛠 Совместимость: возвращается только количество (как в оригинале)

    :param etarkangaroo_exe: путь к исполняемому файлу
    :return: количество GPU или 1 (по умолчанию)
    """
    count, _ = _detect_gpus_detailed(etarkangaroo_exe)
    return count


def _detect_gpus_detailed(exe_path: str) -> Tuple[int, List[str]]:
    """
    Внутренняя функция: определяет GPU с возвратом названий
    🛠 Используется обеими системами (Kangaroo и CuBitcrack)

    :param exe_path: путь к исполняемому файлу
    :return: Кортеж (количество, список_названий)
    """
    if not os.path.exists(exe_path):
        logger.warning(f"Файл не найден: {exe_path}")
        return 1, ["Unknown"]

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    methods = [('list', ['-list']), ('help', ['-h']), ('no_args', [])]

    for method_name, args in methods:
        try:
            logger.debug(f"Попытка определения GPU методом: {method_name}")
            result = subprocess.run(
                [exe_path] + args,
                capture_output=True, text=True, timeout=5,
                creationflags=creation_flags
            )
            output = result.stdout + result.stderr
            gpu_ids = _extract_gpu_ids(output)

            if gpu_ids:
                gpu_names = _extract_gpu_names(output, gpu_ids)
                count = len(gpu_ids)
                names_list = [gpu_names.get(gid, "Unknown") for gid in sorted(gpu_ids, key=int)]
                logger.info(f"Обнаружено {count} GPU: {', '.join(names_list)}")
                return count, names_list
        except subprocess.TimeoutExpired:
            logger.warning(f"Таймаут при попытке {method_name}")
        except Exception as e:
            logger.warning(f"Ошибка при попытке {method_name}: {e}")

    # Fallback через nvidia-smi
    return _detect_via_nvidia_smi()


def suggest_optimal_config(gpu_count: int, target_bits: int = KANGAROO_DEFAULT_TARGET_BITS) -> Dict[str, Any]:
    """
    Предлагает оптимальную конфигурацию Kangaroo на основе количества GPU
    🛠 Совместимость: сигнатура и возвращаемое значение не изменены

    :param gpu_count: количество GPU
    :param target_bits: размер целевого диапазона в битах
    :return: рекомендуемая конфигурация для Kangaroo
    """
    total_speed = KANGAROO_BASE_SPEED_MKEYS * gpu_count * KANGAROO_EFFICIENCY_FACTOR
    logger.info(f"[Kangaroo] Автоконфигурация: GPU={gpu_count}, Скорость~{total_speed:.0f} MKeys/s")

    if gpu_count >= 2:
        if total_speed >= 900:
            config = {'subrange_bits': 42, 'dp': 21, 'grid_params': '1024x512', 'scan_duration': 90}
        else:
            config = {'subrange_bits': 40, 'dp': 20, 'grid_params': '512x512', 'scan_duration': 60}
    else:
        config = {'subrange_bits': 38, 'dp': 19, 'grid_params': '256x256', 'scan_duration': 60}

    config.update({'estimated_speed': total_speed, 'gpu_count': gpu_count})
    return config


def initialize_kangaroo_with_auto_config(
    etarkangaroo_exe: str,
    target_bits: int = KANGAROO_DEFAULT_TARGET_BITS
) -> Dict[str, Any]:
    """
    Инициализация Kangaroo с автоматическим определением конфигурации
    🛠 Совместимость: сигнатура не изменена

    :return: оптимальная конфигурация для Kangaroo
    """
    gpu_count = detect_gpus(etarkangaroo_exe)
    return suggest_optimal_config(gpu_count, target_bits=target_bits)


def auto_configure_kangaroo(main_window) -> Optional[Dict[str, Any]]:
    """
    Автоматическая настройка параметров Kangaroo
    🛠 Совместимость: сигнатура и поведение не изменены

    :param main_window: ссылка на главное окно приложения
    :return: конфигурация или None при ошибке
    """
    try:
        from PyQt5.QtWidgets import QMessageBox, QInputDialog
    except ImportError:
        logger.error("PyQt5 не установлен")
        return None

    exe_path = main_window.kang_exe_edit.text().strip()
    if not os.path.exists(exe_path):
        QMessageBox.warning(main_window, "Ошибка", "Сначала укажите правильный путь к etarkangaroo.exe")
        return None

    try:
        start_hex = main_window.kang_start_key_edit.text().strip()
        end_hex = main_window.kang_end_key_edit.text().strip()
        target_bits = KANGAROO_DEFAULT_TARGET_BITS

        if start_hex and end_hex:
            try:
                start_int = int(start_hex.replace('0x', ''), 16)
                end_int = int(end_hex.replace('0x', ''), 16)
                diff = abs(end_int - start_int)
                target_bits = diff.bit_length() if diff > 0 else KANGAROO_DEFAULT_TARGET_BITS
            except ValueError:
                logger.warning("Не удалось распознать диапазон, используем 134 бита по умолчанию")

        config = initialize_kangaroo_with_auto_config(exe_path, target_bits)

        # Уточнение количества GPU через диалог
        if config['gpu_count'] == 1:
            reply = QMessageBox.question(
                main_window, "Подтверждение количества GPU",
                f"Автоматически обнаружено: <b>{config['gpu_count']} GPU</b><br><br>"
                f"Если у вас на самом деле больше GPU,<br>"
                f"хотите указать количество вручную?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                manual_count, ok = QInputDialog.getInt(
                    main_window, "Количество GPU", "Укажите реальное количество GPU:",
                    value=2, min=1, max=8
                )
                if ok and manual_count > 1:
                    logger.info(f"Пользователь указал вручную: {manual_count} GPU")
                    config = suggest_optimal_config(manual_count, target_bits)

        # Применение в UI
        main_window.kang_subrange_spin.setValue(config['subrange_bits'])
        main_window.kang_dp_spin.setValue(config['dp'])
        main_window.kang_grid_edit.setText(config['grid_params'])
        main_window.kang_duration_spin.setValue(config['scan_duration'])

        QMessageBox.information(
            main_window, "✅ Автонастройка Kangaroo завершена",
            f"<b>Параметры настроены автоматически:</b><br><br>"
            f"🎮 Обнаружено GPU: <b>{config['gpu_count']}</b><br>"
            f"📊 Grid: <b>{config['grid_params']}</b><br>"
            f"🔢 Subrange: <b>{config['subrange_bits']}</b> бит<br>"
            f"🎯 DP: <b>{config['dp']}</b><br>"
            f"⏱️ Длительность: <b>{config['scan_duration']}</b> сек<br><br>"
            f"⚡ Ожидаемая скорость: ~<b>{config['estimated_speed']:.0f}</b> MKeys/s"
        )

        main_window.append_log("✅ Автонастройка Kangaroo завершена", "success")
        return config

    except Exception as e:
        logger.exception("Ошибка автонастройки Kangaroo")
        QMessageBox.critical(
            main_window, "Ошибка",
            f"Не удалось выполнить автонастройку:\n{str(e)}"
        )
        main_window.append_log(f"❌ Ошибка автонастройки: {str(e)}", "error")
        return None


# ═══════════════════════════════════════════════
# 🔧 НОВЫЕ ФУНКЦИИ ДЛЯ GPU/CUBITCRACK
# ═══════════════════════════════════════════════

def detect_gpus_cubitcrack(cubitcrack_exe: str) -> int:
    """
    Определяет количество доступных GPU через cuBitcrack
    🛠 НОВАЯ ФУНКЦИЯ: для совместимости с Kangaroo версией

    :param cubitcrack_exe: путь к cuBitcrack.exe
    :return: количество обнаруженных GPU
    """
    count, _ = _detect_gpus_detailed(cubitcrack_exe)
    return count


def suggest_optimal_gpu_config(
    gpu_count: int,
    gpu_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Предлагает оптимальные параметры cuBitcrack на основе количества и типа GPU

    :param gpu_count: количество видеокарт
    :param gpu_names: список названий карт (опционально, для точной настройки)
    :return: словарь с параметрами blocks, threads, points
    """
    gpu_names = gpu_names or []

    # 🛠 Определяем, есть ли быстрые карты (RTX 30/40 серии)
    has_fast_gpu = any('RTX 30' in name or 'RTX 40' in name for name in gpu_names)

    # 🛠 Рассчитываем ожидаемую общую скорость
    total_speed = CUBITCRACK_BASE_SPEED_MKEYS * gpu_count * CUBITCRACK_EFFICIENCY_FACTOR
    if has_fast_gpu:
        total_speed *= 1.3  # +30% для быстрых карт

    logger.info(f"[CuBitcrack] Автоконфигурация: GPU={gpu_count}, Скорость~{total_speed:.0f} MKey/s")

    # 🛠 Выбираем конфигурацию на основе количества карт и их типа
    if gpu_count >= 2:
        if total_speed >= 900 or has_fast_gpu:
            config_key = 'multi_aggressive'
        else:
            config_key = 'multi_balanced'
    else:
        if has_fast_gpu:
            config_key = 'single_fast'
        else:
            config_key = 'single_slow'

    result = CUBITCRACK_CONFIGS[config_key].copy()
    result.update({
        'estimated_speed': total_speed,
        'gpu_count': gpu_count,
        'config_profile': config_key,
        'gpu_names': gpu_names
    })

    logger.info(f"[CuBitcrack] Применена конфигурация: {config_key} -> "
                f"blocks={result['blocks']}, threads={result['threads']}, points={result['points']}")

    return result


def initialize_gpu_with_auto_config(
    cubitcrack_exe: str
) -> Dict[str, Any]:
    """
    Инициализация GPU-поиска с автоматическим определением конфигурации

    :param cubitcrack_exe: путь к cuBitcrack.exe
    :return: оптимальная конфигурация для cuBitcrack
    """
    gpu_count, gpu_names = _detect_gpus_detailed(cubitcrack_exe)
    return suggest_optimal_gpu_config(gpu_count, gpu_names)


def auto_configure_gpu(main_window) -> Optional[Dict[str, Any]]:
    """
    Автоматическая настройка параметров cuBitcrack для GPU-поиска
    🛠 НОВАЯ ФУНКЦИЯ: вызывается из core/gpu_logic.py

    :param main_window: ссылка на главное окно приложения
    :return: конфигурация или None при ошибке
    """
    try:
        from PyQt5.QtWidgets import QMessageBox, QInputDialog
    except ImportError:
        logger.error("PyQt5 не установлен")
        return None

    exe_path = config.CUBITCRACK_EXE if hasattr(config, 'CUBITCRACK_EXE') else None
    if not exe_path or not os.path.exists(exe_path):
        QMessageBox.warning(
            main_window, "Ошибка",
            "Сначала укажите правильный путь к cuBitcrack.exe в настройках"
        )
        return None

    try:
        # 🛠 1. Определяем GPU через cuBitcrack
        gpu_count, gpu_names = _detect_gpus_detailed(exe_path)

        # 🛠 2. Рассчитываем оптимальные параметры
        config_params = suggest_optimal_gpu_config(gpu_count, gpu_names)

        # 🛠 3. Уточнение количества GPU через диалог, если обнаружена только 1
        if gpu_count == 1:
            reply = QMessageBox.question(
                main_window, "Подтверждение количества GPU",
                f"Автоматически обнаружено: <b>{gpu_count} GPU</b><br><br>"
                f"Если у вас на самом деле больше GPU,<br>"
                f"хотите указать количество вручную?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                manual_count, ok = QInputDialog.getInt(
                    main_window, "Количество GPU", "Укажите реальное количество GPU:",
                    value=2, min=1, max=8
                )
                if ok and manual_count > 1:
                    logger.info(f"Пользователь указал вручную: {manual_count} GPU")
                    config_params = suggest_optimal_gpu_config(manual_count, gpu_names)

        # 🛠 4. Применяем параметры в UI (через атрибуты main_window)
        main_window.blocks_combo.setCurrentText(str(config_params['blocks']))
        main_window.threads_combo.setCurrentText(str(config_params['threads']))
        main_window.points_combo.setCurrentText(str(config_params['points']))

        # 🛠 5. Показываем результат
        gpu_list = ', '.join(gpu_names) if gpu_names else f"{config_params['gpu_count']} карта(ы)"
        QMessageBox.information(
            main_window, "✅ Автонастройка GPU завершена",
            f"<b>Параметры cuBitcrack настроены автоматически:</b><br><br>"
            f"🎮 Обнаружено GPU: <b>{config_params['gpu_count']}</b><br>"
            f"📋 Карты: <i>{gpu_list}</i><br><br>"
            f"🧱 Blocks: <b>{config_params['blocks']}</b><br>"
            f"🧵 Threads: <b>{config_params['threads']}</b><br>"
            f"🎯 Points: <b>{config_params['points']}</b><br><br>"
            f"⚡ Ожидаемая скорость: ~<b>{config_params['estimated_speed']:.0f}</b> MKey/s<br>"
            f"📊 Профиль: <i>{config_params.get('config_profile', 'custom')}</i>"
        )

        main_window.append_log("✅ Автонастройка cuBitcrack завершена", "success")
        main_window.append_log(
            f"📊 Параметры: Blocks={config_params['blocks']}, "
            f"Threads={config_params['threads']}, Points={config_params['points']}",
            "success"
        )

        return config_params

    except Exception as e:
        logger.exception("Ошибка автонастройки GPU")
        QMessageBox.critical(
            main_window, "Ошибка",
            f"Не удалось выполнить автонастройку:\n{type(e).__name__}: {str(e)}"
        )
        main_window.append_log(f"❌ Ошибка автонастройки GPU: {str(e)}", "error")
        return None


# 🛠 Явный экспорт публичного API
__all__ = [
    # Kangaroo (оригинальные функции)
    'detect_gpus',
    'suggest_optimal_config',
    'initialize_kangaroo_with_auto_config',
    'auto_configure_kangaroo',

    # GPU/CuBitcrack (новые функции)
    'detect_gpus_cubitcrack',
    'suggest_optimal_gpu_config',
    'initialize_gpu_with_auto_config',
    'auto_configure_gpu',

    # Вспомогательные (для внутреннего использования)
    '_detect_gpus_detailed',
]