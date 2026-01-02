# predictor_gpu_full.py
import json
import os
import sys
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from tqdm import tqdm  # индикатор прогресса

# ====================== ЛОГИРОВАНИЕ ======================
LOG_FILE = "predictor_log.txt"

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ====================== УТИЛИТЫ ======================
def load_json(filepath: str) -> List[Dict]:
    if not os.path.exists(filepath):
        log(f"❌ Файл '{filepath}' не найден!")
        sys.exit(1)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log(f"❌ Ошибка JSON: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Ошибка при чтении {filepath}: {e}")
        sys.exit(1)

def hex_to_int(h: Optional[str]) -> int:
    if not h:
        return 0
    return int(h.strip().replace("0x", ""), 16)

def int_to_hex_padded(n: int, width: int = 64) -> str:
    return hex(n)[2:].zfill(width)

def parse_range(range_str: str) -> Tuple[int, int]:
    if not range_str or ':' not in range_str:
        return 0, 0
    start_hex, end_hex = range_str.split(':', 1)
    return hex_to_int(start_hex), hex_to_int(end_hex)

def get_solved_puzzles(data: List[Dict]) -> List[Dict]:
    solved = []
    for item in data:
        if item.get("status") != "solved" or not item.get("private_key"):
            continue
        try:
            k = hex_to_int(item["private_key"])
            low, high = parse_range(item.get("search_range", ""))
            if k != 0 and low < k < high:
                solved.append({
                    "puzzle": item["puzzle"],
                    "k": k,
                    "low": low,
                    "high": high,
                    "range_width": high - low + 1
                })
        except Exception:
            continue
    return sorted(solved, key=lambda x: x["puzzle"])

# ====================== ПРОГНОЗ КЛЮЧЕЙ ======================
def predict_centers(solved: List[Dict]) -> List[Tuple[str, int]]:
    """
    Прогнозирует центры диапазонов для puzzle71 на основе предыдущих головоломок.
    Возвращает список (метод, центр_int)
    """
    # Берём последние solved puzzle 68,69,70
    recent = {p["puzzle"]: p for p in solved if p["puzzle"] in (68,69,70)}
    k68 = recent.get(68, {}).get("k")
    k69 = recent.get(69, {}).get("k")
    k70 = recent.get(70, {}).get("k")

    predictions: List[Tuple[str,int]] = []

    # Мультипликативный
    if k69 and k70:
        predictions.append(("multiplicative_k70²/k69", (k70**2)//k69))
        ratio = k70/k69
        predictions.append(("geometric_extrap", int(k70*ratio)))

    # Линейная экстраполяция
    if k68 and k69 and k70:
        step1 = k69 - k68
        step2 = k70 - k69
        next_step = step2 + (step2 - step1)*0.8
        predictions.append(("linear_accel", int(k70 + next_step)))

    # Золотое сечение и sqrt2
    if k70:
        predictions.append(("golden_ratio", int(k70*1.61803398875)))
        predictions.append(("sqrt2", int(k70*1.41421356237)))

    # Среднее всех прогнозов
    if predictions:
        avg = sum(p[1] for p in predictions)//len(predictions)
        predictions.append(("ensemble_mean", avg))

    return predictions

# ====================== ГЕНЕРАЦИЯ GPU-ДИАПАЗОНОВ ======================
def generate_gpu_ranges_around_centers(
    low: int,
    high: int,
    centers: List[Tuple[str,int]],
    num_ranges: int,
    num_gpus: int
) -> List[Dict]:
    """
    Генерирует диапазоны вокруг прогнозных центров.
    Каждый диапазон GPU-friendly, распределён по GPU.
    """
    log(f"🔹 Генерация {num_ranges} диапазонов для {num_gpus} GPU...")
    total_range = high - low + 1
    BASE_WIDTH = 1 << 61  # ~2.3e18 keys

    ranges = []
    centers = centers[:num_ranges] if centers else [("center_default", (low+high)//2)]

    for i, (name, center) in enumerate(tqdm(centers, desc="Генерация диапазонов")):
        start = max(low, center - BASE_WIDTH//2)
        end = min(high, center + BASE_WIDTH//2 - 1)
        width = end - start + 1
        if width < (1<<32):
            continue
        # Кратность 2^32
        start -= start % (1<<32)
        end -= end % (1<<32)
        ranges.append({
            "id": i+1,
            "gpu_id": (i % num_gpus)+1,
            "name": name,
            "start": int_to_hex_padded(start),
            "end": int_to_hex_padded(end),
            "width_decimal": f"{end-start+1:.3e}"
        })

    return ranges

# ====================== MAIN ======================
def main():
    log("🚀 Puzzle #71 GPU-Optimized Range Generator")
    log("="*75)

    data = load_json("Akey.json")
    solved = get_solved_puzzles(data)
    if not solved:
        log("❌ Нет решённых головоломок для анализа.")
        sys.exit(1)

    # дефолтный диапазон puzzle71
    low = hex_to_int("0000000000000000000000000000000000000000000000400000000000000000")
    high = hex_to_int("00000000000000000000000000000000000000000000007fffffffffffffffff")

    # Ввод пользователя
    try:
        num_ranges = int(input("🔢 Сколько диапазонов сгенерировать? (1–10, по умолчанию 10): ") or 10)
        num_ranges = max(1,min(10,num_ranges))
    except ValueError:
        num_ranges = 10

    try:
        num_gpus = int(input("🖥️ Сколько GPU использовать? (по умолчанию 4): ") or 4)
        num_gpus = max(1,num_gpus)
    except ValueError:
        num_gpus = 4

    centers = predict_centers(solved)
    ranges = generate_gpu_ranges_around_centers(low, high, centers, num_ranges, num_gpus)

    # Вывод
    log(f"🎯 Сгенерировано {len(ranges)} диапазонов:")
    print("-"*80)
    print(f"{'ID':<4}{'GPU':<4}{'Метод':<22}{'Start (last 16 hex)':<20}{'End (last 16 hex)':<20}{'Width'}")
    print("-"*80)
    for r in ranges:
        print(f"{r['id']:<4}{r['gpu_id']:<4}{r['name']:<22}{r['start'][-16:]:<20}{r['end'][-16:]:<20}{r['width_decimal']}")

    # Сохранение
    output_file = "puzzle71_gpu_ranges.json"
    with open(output_file,"w",encoding="utf-8") as f:
        json.dump({
            "puzzle":71,
            "status":"predicted",
            "gpu_count":num_gpus,
            "generated_at": str(datetime.now()),
            "search_ranges": ranges
        }, f, indent=2, ensure_ascii=False)

    log(f"💾 Сохранено: {output_file}")

if __name__=="__main__":
    main()
