# ═══════════════════════════════════════════════
# SAFE ADVANCED BITCOIN PUZZLE ANALYZER (NO CRASH)
# ═══════════════════════════════════════════════

import numpy as np
import matplotlib
matplotlib.use('Agg')  # безопасный режим
import matplotlib.pyplot as plt
import math

# ═══════════════════════════════════════════════
# 1. НАСТРОЙКИ (МОЖНО МЕНЯТЬ)
# ═══════════════════════════════════════════════

Q_LOW = 0.25

Q_HIGH = 0.75

USE_OUTLIER_FILTER = True
WEIGHT_RECENT = True
USE_KDE = True

KDE_POINTS = 500

KNOWN_KEYS_HEX = [

    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000349b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000309b84b6431a6c4ef1",
    "0000000000000000000000000000000000000000000000309b84b6431a6c4ef1",

]

# ═══════════════════════════════════════════════
# 3. ФУНКЦИИ
# ═══════════════════════════════════════════════

def hex_to_dec(h):
    return int(h, 16)

def dec_to_hex(d):
    return f"{d:064x}"

def get_range(n):
    return 2**(n-1), 2**n - 1

def remove_outliers(data):
    if len(data) < 5:
        return data
    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    return data[(data > q1 - 1.5*iqr) & (data < q3 + 1.5*iqr)]

def safe_kde(data, points=500):
    # безопасная KDE без SciPy
    if len(data) < 5 or np.std(data) == 0:
        xs = np.linspace(0, 1, points)
        return xs, np.zeros_like(xs)

    xs = np.linspace(0, 1, points)
    bandwidth = np.std(data) * 0.3

    density = np.zeros_like(xs)
    for d in data:
        density += np.exp(-0.5 * ((xs - d) / bandwidth) ** 2)

    density /= (len(data) * bandwidth * np.sqrt(2 * np.pi))
    return xs, density

# ═══════════════════════════════════════════════
# 4. ПОДГОТОВКА ДАННЫХ
# ═══════════════════════════════════════════════

keys = [hex_to_dec(k) for k in KNOWN_KEYS_HEX]

# log пространство (SAFE)
log_keys = np.array([math.log2(k) for k in keys])
log_diff = np.diff(log_keys)

# позиции
positions = []
for i, key in enumerate(keys[1:], start=2):
    pmin, pmax = get_range(i)

    if pmax - pmin == 0:
        pos = 0
    else:
        pos = (key - pmin) / (pmax - pmin)

    positions.append(pos)

positions = np.array(positions)

# очистка
positions = positions[~np.isnan(positions)]
positions = positions[~np.isinf(positions)]

# фильтр выбросов
if USE_OUTLIER_FILTER:
    positions = remove_outliers(positions)
    log_diff = remove_outliers(log_diff)

# веса
if WEIGHT_RECENT and len(positions) > 0:
    weights = np.linspace(0.5, 1.5, len(positions))
else:
    weights = None

# ═══════════════════════════════════════════════
# 5. ВИЗУАЛИЗАЦИЯ (SAFE KDE)
# ═══════════════════════════════════════════════

if USE_KDE:
    xs, density = safe_kde(positions, KDE_POINTS)

    plt.figure()
    plt.plot(xs, density)
    plt.title("Position Density (SAFE KDE)")
    plt.xlabel("Position")
    plt.ylabel("Density")
    plt.savefig("kde.png")
    plt.close()

# ═══════════════════════════════════════════════
# 6. ПРОГНОЗ
# ═══════════════════════════════════════════════

next_puzzle = len(keys) + 1
pmin, pmax = get_range(next_puzzle)

# защита от пустых данных
if len(positions) == 0 or len(log_diff) == 0:
    print("❌ Недостаточно данных")
    exit()

# 1. позиция
p_low, p_high = np.quantile(positions, [Q_LOW, Q_HIGH])
dist_min = int(pmin + p_low * (pmax - pmin))
dist_max = int(pmin + p_high * (pmax - pmin))

# 2. рост (лог)
ld_low, ld_high = np.quantile(log_diff, [Q_LOW, Q_HIGH])

growth_min = int(2 ** (log_keys[-1] + ld_low))
growth_max = int(2 ** (log_keys[-1] + ld_high))

# 3. финальный диапазон
final_min = max(pmin, dist_min, growth_min)
final_max = min(pmax, dist_max, growth_max)

# ═══════════════════════════════════════════════
# 7. ВЫВОД
# ═══════════════════════════════════════════════

print("\n" + "="*80)
print(f"ПАЗЛ #{next_puzzle}")
print("="*80)

print("\n[1] По позиции:")
print(f"0x{dec_to_hex(dist_min)}")
print(f"0x{dec_to_hex(dist_max)}")

print("\n[2] По росту:")
print(f"0x{dec_to_hex(growth_min)}")
print(f"0x{dec_to_hex(growth_max)}")

print("\n[3] ФИНАЛЬНЫЙ:")
print(f"0x{dec_to_hex(final_min)}")
print(f"0x{dec_to_hex(final_max)}")

reduction = 100 - ((final_max - final_min) / (pmax - pmin) * 100)
print(f"\nСужение диапазона: {reduction:.2f}%")

print("\n📁 Сохранено:")
print(" - kde.png")

print("\n⚠️ Это вероятностная модель, не точное предсказание.")