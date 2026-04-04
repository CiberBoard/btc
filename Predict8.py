# ═══════════════════════════════════════════════
# ADVANCED BTC PUZZLE ANALYZER v2 (IMPROVED)
# ═══════════════════════════════════════════════

import matplotlib

matplotlib.use('Agg')

import numpy as np
import matplotlib.pyplot as plt
import math
from scipy.interpolate import UnivariateSpline
from scipy.stats import gaussian_kde
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

# ═══════════════════════════════════════════════
# ⚙️ НАСТРОЙКИ
# ═══════════════════════════════════════════════

Q_LOW = 0.25
Q_HIGH = 0.75  # ← РАСШИРИЛ для лучшего покрытия

USE_OUTLIER_FILTER = True
WEIGHT_RECENT = True
USE_LOG_GROWTH = True
USE_POSITION_MODEL = True
USE_ENSEMBLE = True  # ← НОВОЕ: ансамбль моделей
USE_GAUSSIAN_KDE = True  # ← НОВОЕ: правильная KDE
USE_SPLINE_FIT = True  # ← НОВОЕ: сплайн-интерполяция

KDE_POINTS = 500000
ENSEMBLE_MODELS = 3  # количество моделей в ансамбле

# ═══════════════════════════════════════════════
# 📦 ДАННЫЕ
# ═══════════════════════════════════════════════

KNOWN_KEYS_HEX = [
    "0000000000000000000000000000000000000000000000000000000000000001",
    "0000000000000000000000000000000000000000000000000000000000000003",
    "0000000000000000000000000000000000000000000000000000000000000007",
    "0000000000000000000000000000000000000000000000000000000000000008",
    "0000000000000000000000000000000000000000000000000000000000000015",
    "0000000000000000000000000000000000000000000000000000000000000031",
    "000000000000000000000000000000000000000000000000000000000000004c",
    "00000000000000000000000000000000000000000000000000000000000001d3",
    "0000000000000000000000000000000000000000000000000000000000000202",
    "0000000000000000000000000000000000000000000000000000000000000483",
    "0000000000000000000000000000000000000000000000000000000000000a7b",
    "0000000000000000000000000000000000000000000000000000000000001460",
    "0000000000000000000000000000000000000000000000000000000000002930",
    "00000000000000000000000000000000000000000000000000000000000068f3",
    "000000000000000000000000000000000000000000000000000000000000c936",
    "000000000000000000000000000000000000000000000000000000000001764f",
    "000000000000000000000000000000000000000000000000000000000003080d",
    "000000000000000000000000000000000000000000000000000000000005749f",
    "00000000000000000000000000000000000000000000000000000000000d2c55",
    "00000000000000000000000000000000000000000000000000000000001ba534",
    "00000000000000000000000000000000000000000000000000000000002de40f",
    "0000000000000000000000000000000000000000000000000000000000556e52",
    "0000000000000000000000000000000000000000000000000000000000dc2a04",
    "0000000000000000000000000000000000000000000000000000000001fa5ee5",
    "000000000000000000000000000000000000000000000000000000000340326e",
    "0000000000000000000000000000000000000000000000000000000006ac3875",
    "000000000000000000000000000000000000000000000000000000000d916ce8",
    "0000000000000000000000000000000000000000000000000000000017e2551e",
    "000000000000000000000000000000000000000000000000000000003d94cd64",
    "000000000000000000000000000000000000000000000000000000007d4fe747",
    "00000000000000000000000000000000000000000000000000000000b862a62e",
    "00000000000000000000000000000000000000000000000000000001a96ca8d8",
    "000000000000000000000000000000000000000000000000000000034a65911d",
    "00000000000000000000000000000000000000000000000000000004aed21170",
    "00000000000000000000000000000000000000000000000000000009de820a7c",
    "0000000000000000000000000000000000000000000000000000001757756a93",
    "00000000000000000000000000000000000000000000000000000022382facd0",
    "0000000000000000000000000000000000000000000000000000004b5f8303e9",
    "000000000000000000000000000000000000000000000000000000e9ae4933d6",
    "00000000000000000000000000000000000000000000000000000153869acc5b",
    "000000000000000000000000000000000000000000000000000002a221c58d8f",
    "000000000000000000000000000000000000000000000000000006bd3b27c591",
    "00000000000000000000000000000000000000000000000000000e02b35a358f",
    "0000000000000000000000000000000000000000000000000000122fca143c05",
    "00000000000000000000000000000000000000000000000000002ec18388d544",
    "00000000000000000000000000000000000000000000000000006cd610b53cba",
    "0000000000000000000000000000000000000000000000000000ade6d7ce3b9b",
    "000000000000000000000000000000000000000000000000000174176b015f4d",
    "00000000000000000000000000000000000000000000000000022bd43c2e9354",
    "00000000000000000000000000000000000000000000000000075070a1a009d4",
    "000000000000000000000000000000000000000000000000000efae164cb9e3c",
    "00000000000000000000000000000000000000000000000000180788e47e326c",
    "00000000000000000000000000000000000000000000000000236fb6d5ad1f43",
    "000000000000000000000000000000000000000000000000006abe1f9b67e114",
    "000000000000000000000000000000000000000000000000009d18b63ac4ffdf",
    "00000000000000000000000000000000000000000000000001eb25c90795d61c",
    "00000000000000000000000000000000000000000000000002c675b852189a21",
    "00000000000000000000000000000000000000000000000007496cbb87cab44f",
    "0000000000000000000000000000000000000000000000000fc07a1825367bbe",
    "00000000000000000000000000000000000000000000000013c96a3742f64906",
    "000000000000000000000000000000000000000000000000363d541eb611abee",
    "0000000000000000000000000000000000000000000000007cce5efdaccf6808",
    "000000000000000000000000000000000000000000000000f7051f27b09112d4",
    "000000000000000000000000000000000000000000000001a838b13505b26867",
    "000000000000000000000000000000000000000000000002832ed74f2b5e35ee",
    "00000000000000000000000000000000000000000000000730fc235c1942c1ae",
    "00000000000000000000000000000000000000000000000bebb3940cd0fc1491",
    "0000000000000000000000000000000000000000000000101d83275fb2bc7e0c",
    #"0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
]

# ═══════════════════════════════════════════════
# 🔢 ПОДГОТОВКА
# ═══════════════════════════════════════════════

keys = np.array([int(k, 16) for k in KNOWN_KEYS_HEX], dtype=object)


def get_range(n):
    return 2 ** (n - 1), 2 ** n - 1


# ПОЗИЦИИ в диапазоне
positions = []
for i, key in enumerate(keys[1:], start=2):
    pmin, pmax = get_range(i)
    positions.append((key - pmin) / (pmax - pmin))

positions = np.array(positions, dtype=float)

# ЛОГ-РАЗНОСТИ (ВЕКТОР РОСТА)
log_keys = np.array([math.log2(int(k)) for k in keys], dtype=float)
log_diff = np.diff(log_keys)

# ДОПОЛНИТЕЛЬНЫЕ ФИЧИ
# 1. Вес свежести (последние данные важнее)
weights = np.linspace(0.5, 1.0, len(positions)) if WEIGHT_RECENT else np.ones(len(positions))

# 2. Второй дифференциал (ускорение роста)
position_diff = np.diff(positions)
log_diff2 = np.diff(log_diff)


# ═══════════════════════════════════════════════
# 🧹 ФИЛЬТР ВЫБРОСОВ
# ═══════════════════════════════════════════════

def remove_outliers_iqr(data, multiplier=1.5):
    """IQR фильтр"""
    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    mask = (data > q1 - multiplier * iqr) & (data < q3 + multiplier * iqr)
    return data[mask], mask


def remove_outliers_zscore(data, threshold=3):
    """Z-score фильтр"""
    z = np.abs((data - np.mean(data)) / np.std(data))
    mask = z < threshold
    return data[mask], mask


if USE_OUTLIER_FILTER:
    # Двойная фильтрация
    positions, mask_pos = remove_outliers_iqr(positions)
    log_diff, mask_diff = remove_outliers_zscore(log_diff)


# ═══════════════════════════════════════════════
# 🎯 МОДЕЛИ ПРЕДСКАЗАНИЯ
# ═══════════════════════════════════════════════

class PositionModel:
    """Модель на основе позиций в диапазоне"""

    def __init__(self, positions, weights=None):
        self.positions = positions
        self.weights = weights if weights is not None else np.ones(len(positions))

    def predict_quantile(self, q_low, q_high):
        """Взвешенные квантили"""
        sorted_pos = np.sort(self.positions)
        idx_low = int(len(sorted_pos) * q_low)
        idx_high = int(len(sorted_pos) * q_high)
        return sorted_pos[idx_low], sorted_pos[idx_high]

    def predict_bounds(self, pmin, pmax, q_low, q_high):
        p_low, p_high = self.predict_quantile(q_low, q_high)
        return (
            int(pmin + p_low * (pmax - pmin)),
            int(pmin + p_high * (pmax - pmin))
        )


class LogGrowthModel:
    """Модель на основе логарифмического роста с фильтрацией выбросов"""

    def __init__(self, log_keys, log_diff, weights=None):
        self.log_keys = log_keys
        self.weights = weights if weights is not None else np.ones(len(log_diff))

        # Фильтруем выбросы в log_diff
        q1, q3 = np.percentile(log_diff, [25, 75])
        iqr = q3 - q1
        mask = (log_diff > q1 - 1.5 * iqr) & (log_diff < q3 + 1.5 * iqr)
        self.log_diff = log_diff[mask]
        self.weights_filtered = self.weights[:len(log_diff)][mask]

        # Тренд сплайном
        if USE_SPLINE_FIT and len(self.log_diff) > 5:
            try:
                x = np.arange(len(self.log_diff))
                self.spline = UnivariateSpline(x, self.log_diff, k=3, s=len(self.log_diff) * 0.1)
                self.trend = self.spline(x)
            except:
                self.spline = None
                self.trend = np.convolve(self.log_diff, np.ones(3) / 3, mode='same')
        else:
            self.spline = None
            self.trend = np.convolve(self.log_diff, np.ones(3) / 3, mode='same')

    def predict_next_log(self):
        """Предсказать следующую разность логарифмов (экспоненциальное сглаживание)"""
        # Экспоненциальное сглаживание: 70% последнее, 30% скользящее среднее
        recent_avg = np.average(self.log_diff[-3:], weights=self.weights_filtered[-3:])
        overall_avg = np.average(self.log_diff, weights=self.weights_filtered)

        next_diff = 0.7 * recent_avg + 0.3 * overall_avg

        return self.log_keys[-1] + next_diff

    def predict_bounds(self, next_log, q_low, q_high):
        """Предсказать границы без выбросов"""
        ld_low, ld_high = np.percentile(self.log_diff, [q_low, q_high])

        log_min = next_log + ld_low
        log_max = next_log + ld_high

        growth_min = int(2 ** log_min)
        growth_max = int(2 ** log_max)

        return growth_min, growth_max


class EnsembleModel:
    """Ансамбль RandomForest для прогноза позиции"""

    def __init__(self, positions, log_diff, weights=None):
        self.positions = positions
        self.log_diff = log_diff
        self.weights = weights if weights is not None else np.ones(len(positions))

        # Подготовка фич
        self.n_features = min(5, len(positions) - 1)
        self.models = []
        self.train()

    def train(self):
        """Обучить несколько моделей на подвыборках"""
        try:
            for _ in range(ENSEMBLE_MODELS):
                # Bootstrap выборка
                indices = np.random.choice(len(self.positions),
                                           size=len(self.positions),
                                           replace=True)
                X = np.arange(len(self.positions)).reshape(-1, 1)
                y = self.positions

                model = RandomForestRegressor(
                    n_estimators=50,
                    max_depth=8,
                    random_state=np.random.randint(0, 10000)
                )
                model.fit(X[indices], y[indices])
                self.models.append(model)
        except Exception as e:
            print(f"⚠️ Ансамбль не обучен: {e}")

    def predict(self, x):
        """Предсказать позицию"""
        if not self.models:
            return np.mean(self.positions)

        predictions = []
        for model in self.models:
            pred = model.predict([[x]])[0]
            predictions.append(pred)

        return np.mean(predictions)


# ═══════════════════════════════════════════════
# 🔮 ОСНОВНОЙ ПРОГНОЗ
# ═══════════════════════════════════════════════

next_puzzle = len(keys) + 1
pmin, pmax = get_range(next_puzzle)

print("\n" + "=" * 60)
print("🔬 BTC PUZZLE ANALYZER v2")
print("=" * 60)
print(f"Анализируется: {len(keys)} известных ключей")
print(f"Предсказание для: puzzle #{next_puzzle}")
print(f"Диапазон: [2^{next_puzzle - 1}, 2^{next_puzzle}-1]")

# МОДЕЛЬ 1: Позиции
pos_model = PositionModel(positions, weights)
dist_min, dist_max = pos_model.predict_bounds(pmin, pmax, Q_LOW, Q_HIGH)

# МОДЕЛЬ 2: Лог-рост
log_model = LogGrowthModel(log_keys, log_diff, weights)
next_log = log_model.predict_next_log()
growth_min, growth_max = log_model.predict_bounds(next_log, Q_LOW, Q_HIGH)

# МОДЕЛЬ 3: Ансамбль
ensemble_model = None
ensemble_min, ensemble_max = pmin, pmax

if USE_ENSEMBLE and len(positions) > 10:
    try:
        ensemble_model = EnsembleModel(positions, log_diff, weights)
        next_pos = ensemble_model.predict(len(positions))
        ensemble_min = int(pmin + next_pos * (pmax - pmin))
        ensemble_max = int(pmin + (next_pos + 0.15) * (pmax - pmin))  # ±15%
    except Exception as e:
        print(f"⚠️ Ансамбль ошибка: {e}")

# ФИНАЛЬНЫЙ ПРОГНОЗ (пересечение + safety checks)
print("\n[DEBUG] Промежуточные значения:")
print(f"  dist: [{dist_min:.2e}, {dist_max:.2e}]")
print(f"  growth: [{growth_min:.2e}, {growth_max:.2e}]")
print(f"  ensemble: [{ensemble_min:.2e}, {ensemble_max:.2e}]")
print(f"  full: [{float(pmin):.2e}, {float(pmax):.2e}]")

# Пересечение с отладкой
ranges = [
    (dist_min, dist_max, "Position"),
    (growth_min, growth_max, "LogGrowth"),
    (ensemble_min, ensemble_max, "Ensemble"),
    (pmin, pmax, "Full")
]

# Берём максимум всех минимумов и минимум всех максимумов
final_min = max([r[0] for r in ranges])
final_max = min([r[1] for r in ranges])

print(f"  final: [{float(final_min):.2e}, {float(final_max):.2e}]")

# Валидация
if final_min > final_max:
    print(f"\n⚠️ Диапазоны НЕ пересекаются! Использую union вместо intersection.")
    # Если нет пересечения, берём наиболее строгие ограничения
    final_min = max(dist_min, ensemble_min)  # Исключаем логарифмическую модель, если она слишком широкая
    final_max = min(dist_max, ensemble_max)

    if final_min > final_max:
        # Если всё ещё нет, используем ансамбль
        final_min, final_max = ensemble_min, ensemble_max
        print(f"  Используется только Ensemble модель")

# Если диапазоны слишком узкие, расширяем
min_width = int((pmax - pmin) * 0.001)  # минимум 0.1% от полного диапазона
if final_max - final_min < min_width:
    center = (final_min + final_max) // 2
    width = min_width // 2
    final_min = max(center - width, pmin)
    final_max = min(center + width, pmax)
    print(f"  Расширено до минимальной ширины")

# ═══════════════════════════════════════════════
# 📊 ВИЗУАЛИЗАЦИЯ
# ═══════════════════════════════════════════════

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# График 1: Распределение позиций
ax = axes[0, 0]
ax.hist(positions, bins=25, alpha=0.7, color='blue', edgecolor='black')
ax.axvline(np.mean(positions), color='red', linestyle='--', label='Mean')
ax.axvline(np.median(positions), color='green', linestyle='--', label='Median')
ax.set_title('Distribution of Positions')
ax.set_xlabel('Position (normalized)')
ax.set_ylabel('Frequency')
ax.legend()

# График 2: Логарифмические разности
ax = axes[0, 1]
ax.plot(log_diff, 'o-', alpha=0.7, label='Log diff')
if log_model.spline:
    ax.plot(log_model.trend, 'r-', linewidth=2, label='Trend (spline)')
else:
    ax.plot(log_model.trend, 'r-', linewidth=2, label='Trend (MA)')
ax.set_title('Logarithmic Growth Rate')
ax.set_xlabel('Index')
ax.set_ylabel('log2(Key_n / Key_n-1)')
ax.legend()
ax.grid(alpha=0.3)

# График 3: KDE для позиций
ax = axes[1, 0]
if USE_GAUSSIAN_KDE and len(positions) > 3:
    try:
        kde = gaussian_kde(positions)
        xs = np.linspace(0, 1, 500)
        ys = kde(xs)
        ax.plot(xs, ys, 'b-', linewidth=2)
        ax.fill_between(xs, ys, alpha=0.3)
        ax.set_title('KDE of Positions')
        ax.set_xlabel('Position')
        ax.set_ylabel('Density')
    except:
        ax.text(0.5, 0.5, 'KDE Failed', ha='center', va='center')
else:
    ax.text(0.5, 0.5, 'KDE Disabled', ha='center', va='center')

# График 4: Прогноз (логарифмическая шкала)
ax = axes[1, 1]

# Преобразуем в float для избежания переполнения
try:
    ranges = [
        float(dist_max - dist_min),
        float(growth_max - growth_min),
        float(ensemble_max - ensemble_min),
        float(final_max - final_min)
    ]
    # Если числа слишком большие, берём логарифм
    ranges = [np.log2(r) if r > 2 ** 60 else r for r in ranges]

    ax.barh(['Position', 'LogGrowth', 'Ensemble', 'Final'],
            ranges,
            color=['blue', 'green', 'orange', 'red'])
    ax.set_title('Prediction Ranges (Width)')
    ax.set_xlabel('Range Width (bits, for large ranges)')
    ax.grid(axis='x', alpha=0.3)
except Exception as e:
    ax.text(0.5, 0.5, f'Plot Error: {str(e)[:30]}',
            ha='center', va='center', transform=ax.transAxes)
    print(f"⚠️ Ошибка графика: {e}")

plt.tight_layout()
plt.savefig('analysis.png', dpi=100, bbox_inches='tight')
print("\n✅ График сохранен: analysis.png")
plt.close()


# ═══════════════════════════════════════════════
# 📤 РЕЗУЛЬТАТЫ
# ═══════════════════════════════════════════════

def h(x):
    return f"{x:064x}"


print("\n" + "=" * 60)
print("📊 ДЕТАЛЬНЫЙ АНАЛИЗ")
print("=" * 60)


def format_range(min_val, max_val, pmin, pmax):
    """Вывести диапазон в компактном формате"""
    width = max_val - min_val
    pct = (width / (pmax - pmin)) * 100 if pmax > pmin else 0
    return f"  Width: {width:.2e} ({pct:.2f}% of total)"


print("\n🔹 МОДЕЛЬ 1: Позиции в диапазоне")
print(f"  Min: 0x{h(dist_min)}")
print(f"  Max: 0x{h(dist_max)}")
print(format_range(dist_min, dist_max, pmin, pmax))

print("\n🔹 МОДЕЛЬ 2: Логарифмический рост")
print(f"  Следующий log2: {next_log:.6f}")
print(f"  Min: 0x{h(growth_min)}")
print(f"  Max: 0x{h(growth_max)}")
print(format_range(growth_min, growth_max, pmin, pmax))

print("\n🔹 МОДЕЛЬ 3: Ансамбль (RandomForest)")
print(f"  Min: 0x{h(ensemble_min)}")
print(f"  Max: 0x{h(ensemble_max)}")
print(format_range(ensemble_min, ensemble_max, pmin, pmax))

print("\n" + "=" * 60)
print("🎯 ФИНАЛЬНЫЙ ПРОГНОЗ")
print("=" * 60)
print(f"\nMin: 0x{h(final_min)}")
print(f"Max: 0x{h(final_max)}")
print(format_range(final_min, final_max, pmin, pmax))

reduction = 100 - ((final_max - final_min) / (pmax - pmin) * 100)
print(f"\n✨ Сужение: {reduction:.2f}%")

# Статистика
print("\n" + "=" * 60)
print("📈 СТАТИСТИКА")
print("=" * 60)
print(f"Mean position: {np.mean(positions):.4f}")
print(f"Std position: {np.std(positions):.4f}")
print(f"Mean log_diff: {np.mean(log_diff):.6f}")
print(f"Std log_diff: {np.std(log_diff):.6f}")
print(f"Recent trend (last 5): {np.mean(log_diff[-5:]):.6f}")

print("\n✅ Анализ завершен!")
