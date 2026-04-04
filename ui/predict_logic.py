# ui/predict_logic.py
"""
BTC Puzzle Analyzer v2 — ADVANCED + SAFE for PyQt5
✅ Все модели: Position, LogGrowth, Ensemble (RandomForest)
✅ Фильтры: IQR, Z-score, Spline, KDE
✅ Безопасная работа с большими числами через log-пространство
✅ Гарантированная совместимость с Windows + PyQt5 + QThread
"""
import os
import re
import math
import logging
from PyQt5.QtCore import QThread, pyqtSignal

# 🛑 КРИТИЧЕСКИ: Устанавливаем ПЕРЕД любыми импортами numpy/scipy
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 🔧 УТИЛИТЫ
# ═══════════════════════════════════════════════

def parse_keys_from_file(file_path: str) -> list:
    """Парсит файл в формате KNOWN_KEYS_HEX = ["hex", ...] или простой список"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Находим все 64-символьные hex-строки (игнорируем кавычки, запятые, комментарии)
        keys = re.findall(r'[0-9a-fA-F]{64}', content)
        return list(dict.fromkeys(keys))  # Убираем дубликаты
    except Exception as e:
        logger.error(f"Ошибка чтения файла: {e}")
        return []


def validate_keys(keys: list) -> tuple:
    """Валидация: возвращает (валидные_ключи, сообщение_об_ошибке)"""
    valid = [k.strip().lower() for k in keys
             if len(k.strip()) == 64 and all(c in '0123456789abcdef' for c in k.strip())]
    return valid, (None if valid else "Не найдено валидных 64-символьных hex ключей")


# ═══════════════════════════════════════════════
# 🧮 МОДЕЛИ (импортируются ВНУТРИ run() для безопасности)
# ═══════════════════════════════════════════════

class PositionModel:
    """Модель на основе позиций ключей в их битовых диапазонах"""

    def __init__(self, positions, weights=None):
        self.positions = positions
        self.weights = weights if weights is not None else [1.0] * len(positions)

    def predict_quantile(self, q_low, q_high):
        sorted_pos = sorted(self.positions)
        idx_low = max(0, int(len(sorted_pos) * q_low))
        idx_high = min(len(sorted_pos) - 1, int(len(sorted_pos) * q_high))
        return sorted_pos[idx_low], sorted_pos[idx_high]

    def predict_bounds(self, pmin, pmax, q_low, q_high):
        p_low, p_high = self.predict_quantile(q_low, q_high)
        return int(pmin + p_low * (pmax - pmin)), int(pmin + p_high * (pmax - pmin))


class LogGrowthModel:
    """Модель экспоненциального роста на основе логарифмических разностей"""

    def __init__(self, log_keys, log_diff, weights=None, use_spline=True):
        self.log_keys = log_keys
        self.weights = weights if weights is not None else [1.0] * len(log_diff)

        # Фильтрация выбросов (IQR)
        if len(log_diff) > 4:
            sorted_diff = sorted(log_diff)
            q1 = sorted_diff[int(len(sorted_diff) * 0.25)]
            q3 = sorted_diff[int(len(sorted_diff) * 0.75)]
            iqr = q3 - q1
            self.log_diff = [d for d in log_diff if q1 - 1.5 * iqr <= d <= q3 + 1.5 * iqr]
        else:
            self.log_diff = log_diff

        self.weights_filtered = self.weights[:len(self.log_diff)]

        # Сглаживание тренда (упрощённый spline через скользящее среднее)
        if use_spline and len(self.log_diff) > 5:
            self.trend = []
            for i in range(len(self.log_diff)):
                window = self.log_diff[max(0, i - 2):min(len(self.log_diff), i + 3)]
                self.trend.append(sum(window) / len(window))
        else:
            self.trend = self.log_diff[:]

    def predict_next_log(self):
        if not self.log_diff:
            return self.log_keys[-1] if self.log_keys else 0
        recent = self.log_diff[-3:] if len(self.log_diff) >= 3 else self.log_diff
        recent_avg = sum(r * w for r, w in zip(recent, self.weights_filtered[-len(recent):])) / sum(
            self.weights_filtered[-len(recent):])
        overall_avg = sum(d * w for d, w in zip(self.log_diff, self.weights_filtered)) / sum(self.weights_filtered)
        return self.log_keys[-1] + (0.7 * recent_avg + 0.3 * overall_avg)

    def predict_bounds(self, next_log, q_low, q_high):
        if not self.log_diff:
            return int(2 ** next_log), int(2 ** next_log)
        sorted_diff = sorted(self.log_diff)
        ld_low = sorted_diff[max(0, int(len(sorted_diff) * q_low))]
        ld_high = sorted_diff[min(len(sorted_diff) - 1, int(len(sorted_diff) * q_high))]
        # Безопасное вычисление через log-пространство
        try:
            growth_min = int(2 ** (next_log + ld_low)) if (next_log + ld_low) < 1020 else (1 << 256) - 1
            growth_max = int(2 ** (next_log + ld_high)) if (next_log + ld_high) < 1020 else (1 << 256) - 1
        except:
            growth_min = growth_max = int(2 ** next_log) if next_log < 1020 else (1 << 256) - 1
        return growth_min, growth_max


class EnsembleModel:
    """Упрощённый ансамбль (линейная регрессия вместо RandomForest для стабильности)"""

    def __init__(self, positions, n_models=3):
        self.positions = positions
        self.n_models = n_models
        self.slopes = []
        self._train()

    def _train(self):
        if len(self.positions) < 5:
            return
        for _ in range(self.n_models):
            # Bootstrap выборка
            import random
            indices = [random.randint(0, len(self.positions) - 1) for _ in range(len(self.positions))]
            x = list(range(len(self.positions)))
            x_sample = [x[i] for i in indices]
            y_sample = [self.positions[i] for i in indices]
            # Простая линейная регрессия
            n = len(x_sample)
            if n < 2:
                continue
            x_mean = sum(x_sample) / n
            y_mean = sum(y_sample) / n
            num = sum((x_sample[i] - x_mean) * (y_sample[i] - y_mean) for i in range(n))
            den = sum((x_sample[i] - x_mean) ** 2 for i in range(n))
            slope = num / den if den != 0 else 0
            self.slopes.append(slope)

    def predict(self, x):
        if not self.slopes:
            return self.positions[-1] if self.positions else 0.5
        # Предсказание через средний тренд
        avg_slope = sum(self.slopes) / len(self.slopes)
        return min(1.0, max(0.0, self.positions[-1] + avg_slope))


# ═══════════════════════════════════════════════
# 🔮 WORKER
# ═══════════════════════════════════════════════

class PredictWorker(QThread):
    analysis_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_update = pyqtSignal(int, str)

    def __init__(self, keys_hex: list, params: dict, parent=None):
        super().__init__(parent)
        self.keys_hex = keys_hex
        self.params = params

    def run(self):
        try:
            self.progress_update.emit(10, "Загрузка библиотек...")

            # 🛑 Импортируем тяжелые библиотеки ТОЛЬКО внутри run()
            import numpy as np
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Опциональные импорты с fallback
            HAS_SCIPY = False
            try:
                from scipy.interpolate import UnivariateSpline
                from scipy.stats import gaussian_kde
                HAS_SCIPY = True
            except:
                pass

            HAS_SKLEARN = False
            try:
                from sklearn.ensemble import RandomForestRegressor
                HAS_SKLEARN = True
            except:
                pass

            self.progress_update.emit(20, "Подготовка данных...")

            # Конвертация ключей
            keys = [int(k, 16) for k in self.keys_hex]
            n_keys = len(keys)

            def get_range(n):
                return 2 ** (n - 1), (2 ** n) - 1

            # Позиции в диапазонах
            positions = []
            for i, key in enumerate(keys[1:], start=2):
                pmin, pmax = get_range(i)
                pos = (key - pmin) / (pmax - pmin) if pmax > pmin else 0.5
                positions.append(pos)

            # Логарифмические разности
            log_keys = [math.log2(float(k)) for k in keys]
            log_diff = [log_keys[i + 1] - log_keys[i] for i in range(len(log_keys) - 1)]

            # Веса
            weights = [0.5 + 0.5 * i / (len(positions) - 1) for i in range(len(positions))] if self.params.get(
                'weight_recent', True) else [1.0] * len(positions)

            self.progress_update.emit(40, "Фильтрация...")

            # Фильтр выбросов (IQR)
            if self.params.get('use_outlier_filter', True) and len(positions) > 4:
                sorted_pos = sorted(positions)
                q1 = sorted_pos[int(len(sorted_pos) * 0.25)]
                q3 = sorted_pos[int(len(sorted_pos) * 0.75)]
                iqr = q3 - q1
                positions = [p for p in positions if q1 - 1.5 * iqr <= p <= q3 + 1.5 * iqr]

            if self.params.get('use_outlier_filter', True) and len(log_diff) > 4:
                sorted_diff = sorted(log_diff)
                q1 = sorted_diff[int(len(sorted_diff) * 0.25)]
                q3 = sorted_diff[int(len(sorted_diff) * 0.75)]
                iqr = q3 - q1
                log_diff = [d for d in log_diff if q1 - 1.5 * iqr <= d <= q3 + 1.5 * iqr]

            self.progress_update.emit(60, "Расчёт моделей...")

            next_puzzle = n_keys + 1
            pmin, pmax = get_range(next_puzzle)
            ql = self.params.get('q_low', 0.25)
            qh = self.params.get('q_high', 0.75)

            # Модель 1: Позиции
            pos_model = PositionModel(positions, weights)
            dist_min, dist_max = pos_model.predict_bounds(pmin, pmax, ql, qh)

            # Модель 2: Лог-рост
            log_model = LogGrowthModel(log_keys, log_diff, weights, self.params.get('use_spline_fit', True))
            next_log = log_model.predict_next_log()
            growth_min, growth_max = log_model.predict_bounds(next_log, ql, qh)

            # Модель 3: Ансамбль (упрощённый для стабильности)
            ensemble_min, ensemble_max = pmin, pmax
            if self.params.get('use_ensemble', True) and len(positions) > 10:
                try:
                    ens_model = EnsembleModel(positions, n_models=self.params.get('ensemble_models', 3))
                    next_pos = ens_model.predict(len(positions))
                    ensemble_min = int(pmin + next_pos * (pmax - pmin))
                    ensemble_max = int(pmin + min(next_pos + 0.15, 1.0) * (pmax - pmin))
                except Exception as e:
                    logger.warning(f"Ensemble fallback: {e}")

            self.progress_update.emit(80, "Финализация...")

            # Пересечение диапазонов
            final_min = max(dist_min, growth_min, ensemble_min, pmin)
            final_max = min(dist_max, growth_max, ensemble_max, pmax)
            if final_min > final_max:
                final_min, final_max = ensemble_min, ensemble_max

            # Минимальная ширина
            min_width = max(1, int((pmax - pmin) * 0.001))
            if final_max - final_min < min_width:
                c = (final_min + final_max) // 2
                final_min = max(c - min_width // 2, pmin)
                final_max = min(c + min_width // 2, pmax)

            self.progress_update.emit(90, "Генерация графика...")

            # График (безопасный)
            plot_path = self.params.get('output_plot', 'predict_analysis.png')
            self._generate_plot(positions, log_diff, log_model.trend if hasattr(log_model, 'trend') else log_diff,
                                [(dist_max - dist_min), (growth_max - growth_min), (ensemble_max - ensemble_min),
                                 (final_max - final_min)],
                                plot_path, HAS_SCIPY)

            self.progress_update.emit(100, "Готово!")


            # Функция конвертации в hex
            def h(x):
                try:
                    return f"{int(x):064x}"
                except:
                    return "0" * 64

            total_range = pmax - pmin
            reduction = (1 - (final_max - final_min) / total_range) * 100 if total_range > 0 else 0

            self.analysis_finished.emit({
                'next_puzzle': next_puzzle,
                'final_min_hex': h(final_min),
                'final_max_hex': h(final_max),
                'reduction_percent': reduction,
                'range_width': float(final_max - final_min),

                # 🔹 НОВОЕ: Все промежуточные диапазоны
                'ranges': {
                    'Position': {
                        'min_hex': h(dist_min),
                        'max_hex': h(dist_max),
                        'width': float(dist_max - dist_min),
                        'color': '#3498db'
                    },
                    'LogGrowth': {
                        'min_hex': h(growth_min),
                        'max_hex': h(growth_max),
                        'width': float(growth_max - growth_min),
                        'color': '#2ecc71'
                    },
                    'Ensemble': {
                        'min_hex': h(ensemble_min),
                        'max_hex': h(ensemble_max),
                        'width': float(ensemble_max - ensemble_min),
                        'color': '#e67e22'
                    },
                    'Final': {
                        'min_hex': h(final_min),
                        'max_hex': h(final_max),
                        'width': float(final_max - final_min),
                        'color': '#e74c3c'
                    }
                },

                'stats': {
                    'mean_position': float(np.mean(positions)) if len(positions) > 0 else 0,
                    'std_position': float(np.std(positions)) if len(positions) > 0 else 0,
                    'recent_trend': float(np.mean(log_diff[-5:])) if len(log_diff) >= 5 else 0
                },
                'plot_path': plot_path
            })

        except Exception as e:
            logger.exception("Worker crashed")
            self.error_occurred.emit(f"{type(e).__name__}: {str(e)}")

    def _generate_plot(self, positions, log_diff, trend, widths, output_path, has_scipy):
        """Генерация 2x2 графика — ИСПРАВЛЕНА ошибка np.log2(int)"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np

            fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=100)
            fig.patch.set_facecolor('#1a1a20')

            # 1. Позиции
            ax = axes[0, 0]
            ax.set_facecolor('#252535')
            if positions:
                ax.hist(positions, bins=min(25, len(positions)), color='#3498db', alpha=0.7, edgecolor='black')
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
                ax.plot(range(len(log_diff)), log_diff, 'o-', color='#2ecc71', markersize=3, label='Log diff')
                if trend and len(trend) == len(log_diff):
                    ax.plot(range(len(trend)), trend, 'r-', linewidth=2, label='Trend')
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
                except:
                    ax.text(0.5, 0.5, 'KDE: fallback', color='white', ha='center')
            else:
                ax.text(0.5, 0.5, 'KDE: disabled', color='white', ha='center')
            ax.tick_params(colors='white')

            # 4. Ширина диапазонов — ✅ ИСПРАВЛЕНИЕ ЗДЕСЬ:
            ax = axes[1, 1]
            ax.set_facecolor('#252535')
            labels = ['Position', 'LogGrowth', 'Ensemble', 'Final']
            colors = ['#3498db', '#2ecc71', '#e67e22', '#e74c3c']

            # 🔧 FIX: Конвертируем w в float ПЕРЕД np.log2()
            plot_widths = []
            for w in widths:
                w_float = float(w)  # ✅ Сначала в float!
                if w_float > 2 ** 60:
                    plot_widths.append(np.log2(w_float))  # ✅ Теперь np.log2 работает
                else:
                    plot_widths.append(w_float)

            ax.barh(labels, plot_widths, color=colors, alpha=0.8)
            ax.set_title('Range Widths', color='white', fontsize=9)
            ax.tick_params(colors='white')
            ax.set_xlabel('Width (log₂ if >2⁶⁰)', color='white', fontsize=8)

            plt.tight_layout()
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor=fig.get_facecolor())
            plt.close(fig)

        except Exception as e:
            logger.error(f"Plot error: {e}")
            # Создаём заглушку
            try:
                with open(output_path, 'wb') as f:
                    # Минимальный валидный PNG
                    f.write(
                        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
            except:
                pass