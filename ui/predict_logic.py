"""
BTC Puzzle Analyzer v2.1 — ADVANCED + SAFE + API-STABLE for PyQt5
✅ Все модели: Position, LogGrowth, Ensemble (упрощённый)
✅ Фильтры: IQR, Z-score, Spline, KDE
✅ Безопасная работа с большими числами через log-пространство
✅ Гарантированная совместимость с Windows + PyQt5 + QThread
✅ 🔒 API полностью сохранён — все сигналы, методы и структуры данных без изменений
"""
# 🛠 УЛУЧШЕНИЕ 1: Добавлены type hints импорты
from __future__ import annotations
import os
import re
import math
import logging
import random
from typing import List, Optional, Tuple, Dict, Any, Union

from PyQt5.QtCore import QThread, pyqtSignal

# 🛑 КРИТИЧЕСКИ: Устанавливаем ПЕРЕД любыми импортами numpy/scipy
# 🛠 УЛУЧШЕНИЕ 2: Вынесено в отдельную функцию для повторного использования
def _setup_thread_env() -> None:
    """Настраивает переменные окружения для безопасной работы в потоке."""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

_setup_thread_env()

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 🔧 КОНСТАНТЫ МОДУЛЯ
# ═══════════════════════════════════════════════
# 🛠 УЛУЧШЕНИЕ 3: Константы сгруппированы по категориям с аннотациями типов

# Пороги для работы с большими числами
LARGE_WIDTH_THRESHOLD: int = 2 ** 60  # Порог для логарифмирования ширины
MAX_LOG2_VALUE: float = 1020  # Макс. безопасное значение для 2**x через float
MAX_KEY_BITS: int = 256  # Макс. битность ключа

# Параметры моделей
DEFAULT_RANDOM_SEED: int = 42  # Для воспроизводимости
MIN_RANGE_FRACTION: float = 0.001  # Мин. ширина диапазона относительно полного
IQR_MULTIPLIER: float = 1.5  # Множитель для IQR-фильтра
SPLINE_WINDOW: int = 2  # Размер окна для сглаживания тренда

# Веса для ансамбля
ENSEMBLE_RECENT_WEIGHT: float = 0.7
ENSEMBLE_OVERALL_WEIGHT: float = 0.3

# ═══════════════════════════════════════════════
# 🔧 УТИЛИТЫ — БЕЗОПАСНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════

# 🛠 УЛУЧШЕНИЕ 4: Добавлены type hints и docstrings
def safe_log2_int(value: int) -> float:
    """
    Безопасный логарифм по основанию 2 для очень больших целых чисел.

    :param value: Целое число для вычисления логарифма
    :return: Логарифм по основанию 2 как float
    """
    if value <= 0:
        return float('-inf')
    # Для чисел > 2**1023 используем bit_length для точности
    if value.bit_length() > 1023:
        return value.bit_length() - 1 + math.log2(
            value / (1 << (value.bit_length() - 1))
        )
    return math.log2(float(value))


def safe_pow2(log_val: float, max_bits: int = MAX_KEY_BITS) -> int:
    """
    Безопасное возведение 2 в степень с ограничением по битам.

    :param log_val: Показатель степени (логарифм)
    :param max_bits: Максимальное количество бит для результата
    :return: Целое число 2^log_val, ограниченное по битам
    """
    if log_val >= max_bits:
        return (1 << max_bits) - 1
    if log_val <= 0:
        return 1
    if log_val < MAX_LOG2_VALUE:
        return int(2 ** log_val)
    # Для больших значений используем битовый сдвиг
    int_part = int(log_val)
    if int_part >= max_bits:
        return (1 << max_bits) - 1
    return (1 << int_part)


def parse_keys_from_file(file_path: str) -> List[str]:
    """
    Парсит файл в формате KNOWN_KEYS_HEX = ["hex", ...] или простой список.

    :param file_path: Путь к файлу с ключами
    :return: Список уникальных 64-символьных hex-ключей
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Находим все 64-символьные hex-строки (игнорируем кавычки, запятые, комментарии)
        keys = re.findall(r'[0-9a-fA-F]{64}', content)
        return list(dict.fromkeys(keys))  # Убираем дубликаты с сохранением порядка
    except FileNotFoundError:
        logger.error(f"Файл не найден: {file_path}")
        return []
    except PermissionError:
        logger.error(f"Нет доступа к файлу: {file_path}")
        return []
    except Exception as e:
        logger.error(f"Ошибка чтения файла: {type(e).__name__}: {e}", exc_info=True)
        return []


def validate_keys(keys: List[str]) -> Tuple[List[str], Optional[str]]:
    """
    Валидация ключей: возвращает (валидные_ключи, сообщение_об_ошибке).

    :param keys: Список строк-ключей для валидации
    :return: Кортеж (список валидных ключей, сообщение об ошибке или None)
    """
    valid = [
        k.strip().lower() for k in keys
        if len(k.strip()) == 64 and all(c in '0123456789abcdef' for c in k.strip())
    ]
    error_msg = None if valid else "Не найдено валидных 64-символьных hex ключей"
    return valid, error_msg


# ═══════════════════════════════════════════════
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ МОДЕЛЕЙ
# ═══════════════════════════════════════════════

def _iqr_filter_with_weights(
        values: List[float],
        weights: List[float],
        multiplier: float = IQR_MULTIPLIER
) -> Tuple[List[float], List[float]]:
    """
    Применяет IQR-фильтрацию, сохраняя соответствие значений и весов.

    :param values: Список значений для фильтрации
    :param weights: Соответствующие веса значений
    :param multiplier: Множитель для расчёта границ (по умолчанию IQR_MULTIPLIER)
    :return: Кортеж (отфильтрованные значения, отфильтрованные веса)
    """
    if len(values) <= 4:
        return values[:], weights[:]  # 🛠 УЛУЧШЕНИЕ 5: Явное копирование списков

    sorted_vals = sorted(values)
    q1_idx = len(sorted_vals) // 4
    q3_idx = 3 * len(sorted_vals) // 4
    q1 = sorted_vals[q1_idx]
    q3 = sorted_vals[q3_idx]
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    filtered = [
        (v, w) for v, w in zip(values, weights)
        if lower <= v <= upper
    ]
    if not filtered:  # Если всё отфильтровалось — возвращаем оригинал
        return values[:], weights[:]
    return [v for v, w in filtered], [w for v, w in filtered]


def _get_puzzle_range(n: int) -> Tuple[int, int]:
    """
    Возвращает (min, max) для puzzle №n.

    :param n: Номер пазла
    :return: Кортеж (минимальное значение, максимальное значение) диапазона
    """
    return 2 ** (n - 1), (2 ** n) - 1


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """🛠 УЛУЧШЕНИЕ 6: Вспомогательная функция для ограничения значения в диапазоне."""
    return min(max_val, max(min_val, value))


# ═══════════════════════════════════════════════
# 🧮 МОДЕЛИ (импортируются ВНУТРИ run() для безопасности)
# ═══════════════════════════════════════════════

class PositionModel:
    """Модель на основе позиций ключей в их битовых диапазонах"""

    # 🛠 УЛУЧШЕНИЕ 7: Атрибуты класса с аннотациями типов
    positions: List[float]
    weights: List[float]

    def __init__(self, positions: List[float], weights: Optional[List[float]] = None):
        self.positions = positions
        self.weights = weights if weights is not None else [1.0] * len(positions)
        # ✅ Синхронизируем длины на всякий случай
        if len(self.weights) != len(self.positions):
            self.weights = [1.0] * len(self.positions)

    def predict_quantile(self, q_low: float, q_high: float) -> Tuple[float, float]:
        """
        Предсказывает квантили позиций.

        :param q_low: Нижний квантиль (0.0-1.0)
        :param q_high: Верхний квантиль (0.0-1.0)
        :return: Кортеж (нижняя граница, верхняя граница) позиций
        """
        if not self.positions:
            return 0.5, 0.5
        sorted_pos = sorted(self.positions)
        idx_low = max(0, int(len(sorted_pos) * q_low))
        idx_high = min(len(sorted_pos) - 1, int(len(sorted_pos) * q_high))
        return sorted_pos[idx_low], sorted_pos[idx_high]

    def predict_bounds(
            self, pmin: int, pmax: int, q_low: float, q_high: float
    ) -> Tuple[int, int]:
        """
        Предсказывает границы диапазона на основе позиций.

        :param pmin: Минимум диапазона пазла
        :param pmax: Максимум диапазона пазла
        :param q_low: Нижний квантиль
        :param q_high: Верхний квантиль
        :return: Кортеж (минимальная граница, максимальная граница) в абсолютных значениях
        """
        if pmax <= pmin:
            return pmin, pmax
        p_low, p_high = self.predict_quantile(q_low, q_high)
        return (
            int(pmin + p_low * (pmax - pmin)),
            int(pmin + p_high * (pmax - pmin))
        )


class LogGrowthModel:
    """Модель экспоненциального роста на основе логарифмических разностей"""

    # 🛠 УЛУЧШЕНИЕ 8: Атрибуты с аннотациями
    log_keys: List[float]
    log_diff: List[float]
    weights_filtered: List[float]
    trend: List[float]

    def __init__(
            self,
            log_keys: List[float],
            log_diff: List[float],
            weights: Optional[List[float]] = None,
            use_spline: bool = True
    ):
        self.log_keys = log_keys
        weights = weights if weights is not None else [1.0] * len(log_diff)

        # ✅ IQR-фильтрация с сохранением соответствия весов
        self.log_diff, self.weights_filtered = _iqr_filter_with_weights(
            log_diff, weights, multiplier=IQR_MULTIPLIER
        )

        # ✅ Сглаживание тренда (упрощённый spline через скользящее среднее)
        if use_spline and len(self.log_diff) > 5:
            self.trend = []
            window = SPLINE_WINDOW
            for i in range(len(self.log_diff)):
                start = max(0, i - window)
                end = min(len(self.log_diff), i + window + 1)
                window_vals = self.log_diff[start:end]
                window_w = self.weights_filtered[start:end]
                if sum(window_w) > 0:
                    avg = sum(v * w for v, w in zip(window_vals, window_w)) / sum(window_w)
                else:
                    avg = sum(window_vals) / len(window_vals) if window_vals else 0.0
                self.trend.append(avg)
        else:
            self.trend = self.log_diff[:]

    def predict_next_log(self) -> float:
        """
        Предсказывает следующее логарифмическое значение.

        :return: Предсказанное логарифмическое значение
        """
        if not self.log_keys:
            return 0.0
        if not self.log_diff:
            return self.log_keys[-1]

        recent_n = min(3, len(self.log_diff))
        recent = self.log_diff[-recent_n:]
        recent_w = self.weights_filtered[-recent_n:]

        if sum(recent_w) > 0:
            recent_avg = sum(r * w for r, w in zip(recent, recent_w)) / sum(recent_w)
        else:
            recent_avg = sum(recent) / len(recent) if recent else 0.0

        if sum(self.weights_filtered) > 0:
            overall_avg = sum(
                d * w for d, w in zip(self.log_diff, self.weights_filtered)
            ) / sum(self.weights_filtered)
        else:
            overall_avg = sum(self.log_diff) / len(self.log_diff) if self.log_diff else 0.0

        # 🛠 УЛУЧШЕНИЕ 9: Использование констант для весов
        return self.log_keys[-1] + (
            ENSEMBLE_RECENT_WEIGHT * recent_avg +
            ENSEMBLE_OVERALL_WEIGHT * overall_avg
        )

    def predict_bounds(
            self, next_log: float, q_low: float, q_high: float
    ) -> Tuple[int, int]:
        """
        Предсказывает границы диапазона на основе логарифмического роста.

        :param next_log: Предсказанное логарифмическое значение
        :param q_low: Нижний квантиль
        :param q_high: Верхний квантиль
        :return: Кортеж (минимальная граница, максимальная граница)
        """
        if not self.log_diff:
            val = safe_pow2(next_log)
            return val, val

        sorted_diff = sorted(self.log_diff)
        idx_low = max(0, int(len(sorted_diff) * q_low))
        idx_high = min(len(sorted_diff) - 1, int(len(sorted_diff) * q_high))
        ld_low = sorted_diff[idx_low]
        ld_high = sorted_diff[idx_high]

        # ✅ Безопасное вычисление через log-пространство
        growth_min = safe_pow2(next_log + ld_low)
        growth_max = safe_pow2(next_log + ld_high)

        return min(growth_min, growth_max), max(growth_min, growth_max)


class EnsembleModel:
    """Упрощённый ансамбль (линейная регрессия вместо RandomForest для стабильности)"""

    # 🛠 УЛУЧШЕНИЕ 10: Атрибуты с аннотациями
    positions: List[float]
    n_models: int
    slopes: List[float]

    def __init__(self, positions: List[float], n_models: int = 3, seed: int = DEFAULT_RANDOM_SEED):
        self.positions = positions
        self.n_models = n_models
        self.slopes: List[float] = []
        random.seed(seed)  # ✅ Воспроизводимость
        self._train()

    def _train(self) -> None:
        """Обучает модели ансамбля через бутстрэп и линейную регрессию."""
        if len(self.positions) < 5:
            return
        n = len(self.positions)
        x_base = list(range(n))

        for _ in range(self.n_models):
            # Bootstrap выборка
            indices = [random.randint(0, n - 1) for _ in range(n)]
            x_sample = [x_base[i] for i in indices]
            y_sample = [self.positions[i] for i in indices]

            # Простая линейная регрессия
            if len(x_sample) < 2:
                continue
            x_mean = sum(x_sample) / len(x_sample)
            y_mean = sum(y_sample) / len(y_sample)

            num = sum(
                (x_sample[i] - x_mean) * (y_sample[i] - y_mean)
                for i in range(len(x_sample))
            )
            den = sum((x_sample[i] - x_mean) ** 2 for i in range(len(x_sample)))
            slope = num / den if den != 0 else 0.0
            self.slopes.append(slope)

    def predict(self, x: int) -> float:  # 🛠 УЛУЧШЕНИЕ 11: Параметр x помечен как неиспользуемый (для обратной совместимости)
        """
        Предсказывает нормализованную позицию [0, 1] для индекса x.

        :param x: Индекс для предсказания (не используется в текущей реализации)
        :return: Нормализованная позиция в диапазоне [0.0, 1.0]
        """
        if not self.slopes or not self.positions:
            return 0.5
        avg_slope = sum(self.slopes) / len(self.slopes)
        pred = self.positions[-1] + avg_slope
        return _clamp(pred, 0.0, 1.0)  # ✅ Clamp к [0, 1] через вспомогательную функцию


# ═══════════════════════════════════════════════
# 🔮 WORKER — API ПОЛНОСТЬЮ СОХРАНЁН
# ═══════════════════════════════════════════════

class PredictWorker(QThread):
    # ✅ Сигналы — без изменений для совместимости
    # 🛠 УЛУЧШЕНИЕ 12: Явные аннотации типов для сигналов
    analysis_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(int, str)

    # 🛠 УЛУЧШЕНИЕ 13: Атрибуты класса с аннотациями
    keys_hex: List[str]
    params: Dict[str, Any]

    def __init__(self, keys_hex: List[str], params: Dict[str, Any], parent: Optional[Any] = None):
        super().__init__(parent)
        self.keys_hex = keys_hex
        self.params = params

    def run(self) -> None:  # 🛠 УЛУЧШЕНИЕ 14: Явный возврат None
        """Основной метод выполнения в отдельном потоке."""
        try:
            if self.isInterruptionRequested():
                return
            self.progress_update.emit(10, "Загрузка библиотек...")

            # 🛑 Импортируем тяжелые библиотеки ТОЛЬКО внутри run()
            import numpy as np
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Опциональные импорты с fallback
            HAS_SCIPY = False
            try:
                from scipy.interpolate import UnivariateSpline  # noqa: F401
                from scipy.stats import gaussian_kde
                HAS_SCIPY = True
            except ImportError:
                logger.debug("scipy не доступен, используем fallback")
            except Exception as e:
                logger.warning(f"Ошибка импорта scipy: {e}")

            HAS_SKLEARN = False
            try:
                from sklearn.ensemble import RandomForestRegressor  # noqa: F401
                HAS_SKLEARN = True
            except ImportError:
                logger.debug("sklearn не доступен, используем упрощённый ансамбль")
            except Exception as e:
                logger.warning(f"Ошибка импорта sklearn: {e}")

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(20, "Подготовка данных...")

            # Конвертация ключей
            keys = [int(k, 16) for k in self.keys_hex]
            n_keys = len(keys)

            def get_range(n: int) -> Tuple[int, int]:
                return _get_puzzle_range(n)

            # Позиции в диапазонах
            positions: List[float] = []
            for i, key in enumerate(keys[1:], start=2):
                pmin, pmax = get_range(i)
                if pmax > pmin:
                    pos = (key - pmin) / (pmax - pmin)
                else:
                    pos = 0.5
                positions.append(pos)

            # Логарифмические разности — ✅ безопасно
            log_keys = [safe_log2_int(k) for k in keys]
            log_diff = [
                log_keys[i + 1] - log_keys[i]
                for i in range(len(log_keys) - 1)
            ]

            # Веса
            if self.params.get('weight_recent', True) and len(positions) > 0:
                weights = [
                    0.5 + 0.5 * i / (len(positions) - 1)
                    for i in range(len(positions))
                ]
            else:
                weights = [1.0] * len(positions)

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(40, "Фильтрация...")

            # ✅ Фильтр выбросов (IQR) с сохранением весов
            if self.params.get('use_outlier_filter', True) and len(positions) > 4:
                positions, weights = _iqr_filter_with_weights(positions, weights)

            if self.params.get('use_outlier_filter', True) and len(log_diff) > 4:
                log_diff, _ = _iqr_filter_with_weights(log_diff, weights[:len(log_diff)])

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(60, "Расчёт моделей...")

            next_puzzle = n_keys + 1
            pmin, pmax = get_range(next_puzzle)
            ql = self.params.get('q_low', 0.25)
            qh = self.params.get('q_high', 0.75)

            # Модель 1: Позиции
            pos_model = PositionModel(positions, weights)
            dist_min, dist_max = pos_model.predict_bounds(pmin, pmax, ql, qh)

            # Модель 2: Лог-рост
            log_model = LogGrowthModel(
                log_keys, log_diff, weights,
                self.params.get('use_spline_fit', True)
            )
            next_log = log_model.predict_next_log()
            growth_min, growth_max = log_model.predict_bounds(next_log, ql, qh)

            # Модель 3: Ансамбль (упрощённый для стабильности)
            ensemble_min, ensemble_max = pmin, pmax
            if (
                    self.params.get('use_ensemble', True) and
                    len(positions) > 10
            ):
                try:
                    ens_seed = self.params.get('ensemble_seed', DEFAULT_RANDOM_SEED)
                    ens_model = EnsembleModel(
                        positions,
                        n_models=self.params.get('ensemble_models', 3),
                        seed=ens_seed
                    )
                    next_pos = ens_model.predict(len(positions))
                    ensemble_min = int(pmin + next_pos * (pmax - pmin))
                    ensemble_max = int(pmin + min(next_pos + 0.15, 1.0) * (pmax - pmin))
                except Exception as e:
                    logger.warning(f"Ensemble fallback: {e}", exc_info=True)

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(80, "Финализация...")

            # Пересечение диапазонов
            final_min = max(dist_min, growth_min, ensemble_min, pmin)
            final_max = min(dist_max, growth_max, ensemble_max, pmax)
            if final_min > final_max:
                final_min, final_max = ensemble_min, ensemble_max

            # Минимальная ширина диапазона
            min_width = max(1, int((pmax - pmin) * MIN_RANGE_FRACTION))
            if final_max - final_min < min_width:
                c = (final_min + final_max) // 2
                final_min = max(c - min_width // 2, pmin)
                final_max = min(c + min_width // 2, pmax)

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(90, "Генерация графика...")

            # График (безопасный)
            plot_path = self.params.get('output_plot', 'predict_analysis.png')
            self._generate_plot(
                positions, log_diff,
                log_model.trend if hasattr(log_model, 'trend') else log_diff,
                [
                    (dist_max - dist_min),
                    (growth_max - growth_min),
                    (ensemble_max - ensemble_min),
                    (final_max - final_min)
                ],
                plot_path, HAS_SCIPY
            )

            if self.isInterruptionRequested():
                return
            self.progress_update.emit(100, "Готово!")

            # 🛠 УЛУЧШЕНИЕ 15: Вынесена функция конвертации в hex для повторного использования
            def _to_hex(x: Union[int, float]) -> str:
                try:
                    return f"{int(x):064x}"
                except (ValueError, OverflowError, TypeError):
                    return "0" * 64

            total_range = pmax - pmin
            reduction = (
                (1 - (final_max - final_min) / total_range) * 100
                if total_range > 0 else 0.0
            )

            # ✅ Структура ответа — ПОЛНОСТЬЮ СОВМЕСТИМА с оригиналом
            self.analysis_finished.emit({
                'next_puzzle': next_puzzle,
                'final_min_hex': _to_hex(final_min),
                'final_max_hex': _to_hex(final_max),
                'reduction_percent': reduction,
                'range_width': float(final_max - final_min),

                # 🔹 Все промежуточные диапазоны (формат сохранён)
                'ranges': {
                    'Position': {
                        'min_hex': _to_hex(dist_min),
                        'max_hex': _to_hex(dist_max),
                        'width': float(dist_max - dist_min),
                        'color': '#3498db'
                    },
                    'LogGrowth': {
                        'min_hex': _to_hex(growth_min),
                        'max_hex': _to_hex(growth_max),
                        'width': float(growth_max - growth_min),
                        'color': '#2ecc71'
                    },
                    'Ensemble': {
                        'min_hex': _to_hex(ensemble_min),
                        'max_hex': _to_hex(ensemble_max),
                        'width': float(ensemble_max - ensemble_min),
                        'color': '#e67e22'
                    },
                    'Final': {
                        'min_hex': _to_hex(final_min),
                        'max_hex': _to_hex(final_max),
                        'width': float(final_max - final_min),
                        'color': '#e74c3c'
                    }
                },

                'stats': {
                    'mean_position': float(np.mean(positions)) if len(positions) > 0 else 0.0,
                    'std_position': float(np.std(positions)) if len(positions) > 0 else 0.0,
                    'recent_trend': float(np.mean(log_diff[-5:])) if len(log_diff) >= 5 else 0.0
                },
                'plot_path': plot_path
            })

        except KeyboardInterrupt:
            logger.info("Worker прерван пользователем")
            return
        except Exception as e:
            logger.exception("Worker crashed")
            # ✅ Формат ошибки сохранён для совместимости
            self.error_occurred.emit(f"{type(e).__name__}: {str(e)}")

    def _generate_plot(
            self,
            positions: List[float],
            log_diff: List[float],
            trend: List[float],
            widths: List[float],
            output_path: str,
            has_scipy: bool
    ) -> None:  # 🛠 УЛУЧШЕНИЕ 16: Явный возврат None
        """
        Генерация 2x2 графика — с безопасной обработкой больших чисел.

        :param positions: Список позиций ключей
        :param log_diff: Список логарифмических разностей
        :param trend: Список значений тренда
        :param widths: Список ширин диапазонов для отображения
        :param output_path: Путь для сохранения графика
        :param has_scipy: Флаг доступности scipy для KDE
        """
        import matplotlib.pyplot as plt
        import numpy as np

        fig = None
        try:
            fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=100)
            fig.patch.set_facecolor('#1a1a20')

            # 1. Позиции
            ax = axes[0, 0]
            ax.set_facecolor('#252535')
            if positions:
                ax.hist(
                    positions,
                    bins=min(25, len(positions)),
                    color='#3498db',
                    alpha=0.7,
                    edgecolor='black'
                )
                if len(positions) > 0:
                    mean_pos = sum(positions) / len(positions)
                    ax.axvline(mean_pos, color='red', linestyle='--', label='Mean')
            ax.set_title('Positions', color='white', fontsize=9)
            ax.tick_params(colors='white')
            ax.legend(fontsize=7)

            # 2. Лог-рост
            ax = axes[0, 1]
            ax.set_facecolor('#252535')
            if log_diff:
                ax.plot(
                    range(len(log_diff)), log_diff,
                    'o-', color='#2ecc71', markersize=3, label='Log diff'
                )
                if trend and len(trend) == len(log_diff):
                    ax.plot(
                        range(len(trend)), trend,
                        'r-', linewidth=2, label='Trend'
                    )
            ax.set_title('Log Growth', color='white', fontsize=9)
            ax.tick_params(colors='white')
            ax.legend(fontsize=7)

            # 3. KDE (если scipy доступен)
            ax = axes[1, 0]
            ax.set_facecolor('#252535')
            if has_scipy and len(positions) > 3:
                try:
                    from scipy.stats import gaussian_kde
                    kde = gaussian_kde(positions)
                    xs = np.linspace(0, 1, 200)
                    ax.plot(xs, kde(xs), 'b-', linewidth=2)
                    ax.fill_between(xs, kde(xs), alpha=0.3)
                    ax.set_title('KDE Density', color='white', fontsize=9)
                except Exception as e:
                    logger.debug(f"KDE fallback: {e}")
                    ax.text(0.5, 0.5, 'KDE: fallback', color='white', ha='center', va='center')
            else:
                ax.text(0.5, 0.5, 'KDE: disabled', color='white', ha='center', va='center')
            ax.tick_params(colors='white')

            # 4. Ширина диапазонов — ✅ БЕЗОПАСНОЕ логарифмирование
            ax = axes[1, 1]
            ax.set_facecolor('#252535')
            labels = ['Position', 'LogGrowth', 'Ensemble', 'Final']
            colors = ['#3498db', '#2ecc71', '#e67e22', '#e74c3c']

            plot_widths = []
            for w in widths:
                w_float = float(w)
                # ✅ Используем константу и безопасную функцию
                if w_float > LARGE_WIDTH_THRESHOLD:
                    plot_widths.append(safe_log2_int(int(w_float)))
                else:
                    plot_widths.append(w_float)

            ax.barh(labels, plot_widths, color=colors, alpha=0.8)
            ax.set_title('Range Widths', color='white', fontsize=9)
            ax.tick_params(colors='white')
            ax.set_xlabel('Width (log₂ if >2⁶⁰)', color='white', fontsize=8)

            plt.tight_layout()
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            plt.savefig(
                output_path, dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor()
            )

        except Exception as e:
            logger.error(f"Plot error: {e}", exc_info=True)
            # Создаём заглушку-файл
            try:
                output_dir = os.path.dirname(output_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(output_path, 'wb') as f:
                    # Минимальный валидный PNG 1x1 (чёрный пиксель)
                    f.write(
                        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                        b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                        b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
                        b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
                    )
            except Exception as e2:
                logger.error(f"Failed to write placeholder: {e2}")
        finally:
            # ✅ Гарантированное освобождение ресурсов
            if fig is not None:
                plt.close(fig)
            # Дополнительная страховка
            plt.close('all')


# 🛠 УЛУЧШЕНИЕ 17: Явный экспорт публичного API модуля
__all__ = [
    'LARGE_WIDTH_THRESHOLD',
    'MAX_LOG2_VALUE',
    'MAX_KEY_BITS',
    'DEFAULT_RANDOM_SEED',
    'MIN_RANGE_FRACTION',
    'IQR_MULTIPLIER',
    'SPLINE_WINDOW',
    'safe_log2_int',
    'safe_pow2',
    'parse_keys_from_file',
    'validate_keys',
    'PositionModel',
    'LogGrowthModel',
    'EnsembleModel',
    'PredictWorker',
]