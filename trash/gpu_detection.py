"""
Модуль для автоматического определения GPU и рекомендации параметров Kangaroo
🛠 УЛУЧШЕНИЕ 1: Добавлены type hints и логирование
"""
import subprocess
import re
import os
import logging
from typing import Dict, Optional, Set, List, Tuple, Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ И ПАТТЕРНЫ
# ═══════════════════════════════════════════════
# 🛠 УЛУЧШЕНИЕ 2: Скомпилированные регулярные выражения (вызываются один раз)
GPU_ID_PATTERNS: List[re.Pattern] = [
    re.compile(r'GPU\s*#(\d+)', re.IGNORECASE),
    re.compile(r'GPU\s+(\d+)[:\s]', re.IGNORECASE),
    re.compile(r'\[GPU\s*(\d+)\]', re.IGNORECASE),
    re.compile(r'Device\s+(\d+)', re.IGNORECASE),
]

GPU_NAME_RAW_PATTERNS: List[str] = [
    r'GPU\s*#{}[:\s]+([^\n\r]+)',
    r'GPU\s+{}[:\s]+([^\n\r]+)',
    r'\[GPU\s*{}\]\s*([^\n\r]+)',
    r'Device\s+{}[:\s]+([^\n\r]+)'
]

# 🛠 УЛУЧШЕНИЕ 3: Константы конфигурации
DEFAULT_TARGET_BITS: int = 134
BASE_SPEED_MKEYS: float = 550.0
EFFICIENCY_FACTOR: float = 0.9


# ═══════════════════════════════════════════════
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════

def _extract_gpu_ids(output: str) -> Set[str]:
    """Извлекает уникальные ID GPU из вывода"""
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


def _detect_via_nvidia_smi() -> int:
    """Резервное определение GPU через nvidia-smi"""
    try:
        logger.debug("Попытка определения через nvidia-smi...")
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            gpu_names = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            if gpu_names:
                count = len(gpu_names)
                logger.info(f"Через nvidia-smi обнаружено GPU: {count}")
                for i, name in enumerate(gpu_names):
                    logger.info(f"    GPU #{i}: {name}")
                return count
    except FileNotFoundError:
        logger.debug("nvidia-smi не найден в системе")
    except Exception as e:
        logger.warning(f"Ошибка nvidia-smi: {e}")
    return 1


# ═══════════════════════════════════════════════
# 🔧 ОСНОВНОЙ API (Совместимость 100%)
# ═══════════════════════════════════════════════

def detect_gpus(etarkangaroo_exe: str) -> int:
    """
    Определяет количество доступных GPU

    :param etarkangaroo_exe: путь к исполняемому файлу etarkangaroo.exe
    :return: количество GPU или 1 (по умолчанию)
    """
    if not os.path.exists(etarkangaroo_exe):
        logger.warning(f"Файл не найден: {etarkangaroo_exe}")
        return 1

    # 🛠 УЛУЧШЕНИЕ 4: Кроссплатформенные флаги запуска
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    methods = [('list', ['-list']), ('help', ['-h']), ('no_args', [])]

    for method_name, args in methods:
        try:
            logger.debug(f"Попытка определения GPU методом: {method_name}")
            result = subprocess.run(
                [etarkangaroo_exe] + args,
                capture_output=True, text=True, timeout=5,
                creationflags=creation_flags
            )
            output = result.stdout + result.stderr
            gpu_ids = _extract_gpu_ids(output)

            if gpu_ids:
                gpu_names = _extract_gpu_names(output, gpu_ids)
                count = len(gpu_ids)
                logger.info(f"Обнаружено GPU: {count}")
                for gid, name in sorted(gpu_names.items(), key=lambda x: int(x[0])):
                    logger.info(f"    GPU #{gid}: {name}")
                return count
        except subprocess.TimeoutExpired:
            logger.warning(f"Таймаут при попытке {method_name}")
        except Exception as e:
            logger.warning(f"Ошибка при попытке {method_name}: {e}")

    # Fallback
    return _detect_via_nvidia_smi()


def suggest_optimal_config(gpu_count: int, target_bits: int = DEFAULT_TARGET_BITS) -> Dict[str, Any]:
    """
    Предлагает оптимальную конфигурацию на основе количества GPU

    :param gpu_count: количество GPU
    :param target_bits: размер целевого диапазона в битах
    :return: рекомендуемая конфигурация
    """
    total_speed = BASE_SPEED_MKEYS * gpu_count * EFFICIENCY_FACTOR
    logger.info(f"Автоконфигурация: GPU={gpu_count}, Скорость~{total_speed:.0f} MKeys/s, Диапазон=2^{target_bits}")

    # 🛠 УЛУЧШЕНИЕ 5: Логика выбора параметров вынесена в словарь для читаемости
    if gpu_count >= 2:
        if total_speed >= 900:
            config = {'subrange_bits': 42, 'dp': 21, 'grid_params': '1024x512', 'scan_duration': 90}
        else:
            config = {'subrange_bits': 40, 'dp': 20, 'grid_params': '512x512', 'scan_duration': 60}
    else:
        config = {'subrange_bits': 38, 'dp': 19, 'grid_params': '256x256', 'scan_duration': 60}

    config.update({
        'estimated_speed': total_speed,
        'gpu_count': gpu_count
    })

    logger.info(
        f"Рекомендуемые параметры: "
        f"subrange_bits={config['subrange_bits']}, dp={config['dp']}, "
        f"grid={config['grid_params']}, duration={config['scan_duration']}s"
    )
    return config


def initialize_kangaroo_with_auto_config(
    etarkangaroo_exe: str,
    target_bits: int = DEFAULT_TARGET_BITS
) -> Dict[str, Any]:
    """
    Инициализация Kangaroo с автоматическим определением конфигурации

    :param etarkangaroo_exe: путь к exe файлу
    :param target_bits: размер диапазона в битах
    :return: оптимальная конфигурация
    """
    gpu_count = detect_gpus(etarkangaroo_exe)
    return suggest_optimal_config(gpu_count, target_bits=target_bits)


def auto_configure_kangaroo(main_window) -> Optional[Dict[str, Any]]:
    """
    Автоматическая настройка параметров Kangaroo
    Вызывается из ui/kangaroo_logic.py

    :param main_window: ссылка на главное окно приложения
    :return: конфигурация или None при ошибке
    """
    try:
        # 🛠 УЛУЧШЕНИЕ 6: Локальный импорт только при необходимости
        from PyQt5.QtWidgets import QMessageBox, QInputDialog
    except ImportError:
        logger.error("PyQt5 не установлен")
        return None

    exe_path = main_window.kang_exe_edit.text().strip()
    if not os.path.exists(exe_path):
        QMessageBox.warning(main_window, "Ошибка", "Сначала укажите правильный путь к etarkangaroo.exe")
        return None

    try:
        # 🛠 УЛУЧШЕНИЕ 7: Безопасный расчёт битности диапазона
        start_hex = main_window.kang_start_key_edit.text().strip()
        end_hex = main_window.kang_end_key_edit.text().strip()
        target_bits = DEFAULT_TARGET_BITS

        if start_hex and end_hex:
            try:
                start_int = int(start_hex.replace('0x', ''), 16)
                end_int = int(end_hex.replace('0x', ''), 16)
                diff = abs(end_int - start_int)
                target_bits = diff.bit_length() if diff > 0 else DEFAULT_TARGET_BITS
            except ValueError:
                logger.warning("Не удалось распознать диапазон, используем 134 бита по умолчанию")

        config = initialize_kangaroo_with_auto_config(exe_path, target_bits)

        # 🛠 УЛУЧШЕНИЕ 8: Уточнение количества GPU через диалог, если обнаружена только 1
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
            main_window, "✅ Автонастройка завершена",
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
        main_window.append_log(
            f"📊 Параметры: Grid={config['grid_params']}, DP={config['dp']}, Subrange={config['subrange_bits']} бит",
            "success"
        )

        return config

    except Exception as e:
        logger.exception("Ошибка автонастройки Kangaroo")
        QMessageBox.critical(
            main_window, "Ошибка",
            f"Не удалось выполнить автонастройку:\n{str(e)}\n\nИспользуйте ручную настройку параметров."
        )
        main_window.append_log(f"❌ Ошибка автонастройки: {str(e)}", "error")
        return None


# 🛠 УЛУЧШЕНИЕ 9: Явный экспорт публичного API
__all__ = [
    'detect_gpus',
    'suggest_optimal_config',
    'initialize_kangaroo_with_auto_config',
    'auto_configure_kangaroo',
]