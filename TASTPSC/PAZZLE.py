# predictor.py
import json
import sys
import os
from typing import List, Dict, Tuple

def load_puzzle_data(filepath: str = "Akey.json") -> List[Dict]:
    """Загружает данные из Akey.json"""
    if not os.path.exists(filepath):
        print(f"❌ Файл '{filepath}' не найден!")
        print(f"Поместите Akey.json в папку: {os.getcwd()}")
        sys.exit(1)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ Ошибка при чтении {filepath}: {e}")
        sys.exit(1)

def hex_to_int(h: str) -> int:
    if h is None:
        return 0
    h = h.strip().replace("0x", "")
    return int(h, 16) if h else 0

def int_to_hex_padded(n: int, width: int = 64) -> str:
    return hex(n)[2:].zfill(width)

def parse_range(range_str: str) -> Tuple[int, int]:
    """Преобразует 'start : end' → (int_start, int_end)"""
    if not range_str or ':' not in range_str:
        return 0, 0
    parts = range_str.strip().split(':', 1)
    start_hex, end_hex = parts[0].strip(), parts[1].strip()
    return hex_to_int(start_hex), hex_to_int(end_hex)

def get_solved_puzzles(data: List[Dict]) -> List[Dict]:
    """Возвращает только решённые головоломки с валидным private_key"""
    solved = []
    for item in data:
        if item.get("status") == "solved" and item.get("private_key"):
            try:
                k = hex_to_int(item["private_key"])
                low, high = parse_range(item.get("search_range", ""))
                if k != 0 and low < k < high:
                    puzzle_num = item.get("puzzle", 0)
                    solved.append({
                        "puzzle": puzzle_num,
                        "k": k,
                        "low": low,
                        "high": high,
                        "range_width": high - low + 1
                    })
            except Exception:
                continue
    return sorted(solved, key=lambda x: x["puzzle"])

def predict_ranges_puzzle71(solved: List[Dict], num_ranges: int = 10) -> List[Dict]:
    """Генерирует N (вплоть до 1000) оптимизированных диапазонов для puzzle 71"""
    # --- Диапазон puzzle 71 ---
    puzzle71_range = "0000000000000000000000000000000000000000000000400000000000000000 : 00000000000000000000000000000000000000000000007fffffffffffffffff"
    LOW, HIGH = parse_range(puzzle71_range)
    TOTAL_RANGE = HIGH - LOW + 1  # = 2^158

    # --- Получаем последние ключи ---
    k69 = next((p["k"] for p in solved if p["puzzle"] == 69), None)
    k70 = next((p["k"] for p in solved if p["puzzle"] == 70), None)

    if not (k69 and k70):
        raise ValueError("Необходимы решённые puzzle 69 и 70")

    # --- Основной прогноз (наиболее вероятный центр) ---
    center_base = (k70 * k70) // k69
    center_base = max(LOW, min(HIGH, center_base))

    # --- Подбор параметров под N диапазонов ---
    if num_ranges <= 10:
        ZONE_RADIUS = TOTAL_RANGE // 1000      # ±0.1%
        MIN_WIDTH = 1 << 58  # ~2.9e17 (1–3 дня на 4090)
    elif num_ranges <= 50:
        ZONE_RADIUS = TOTAL_RANGE // 2000      # ±0.05%
        MIN_WIDTH = 1 << 54  # ~1.8e16
    else:
        ZONE_RADIUS = TOTAL_RANGE // 5000      # ±0.02% для 100+
        MIN_WIDTH = 1 << 48  # ~2.8e14 (1–2 часа на 4090)

    zone_start = max(LOW, center_base - ZONE_RADIUS)
    zone_end = min(HIGH, center_base + ZONE_RADIUS)
    zone_width = zone_end - zone_start + 1

    # Ширина одного диапазона
    BASE_WIDTH = max(MIN_WIDTH, zone_width // num_ranges)
    BASE_WIDTH = min(BASE_WIDTH, 1 << 62)  # лимит 2^62

    # --- Генерация основных диапазонов ---
    ranges = []
    actual_num = min(num_ranges, zone_width // BASE_WIDTH, 1000)

    for i in range(int(actual_num)):
        start = zone_start + i * BASE_WIDTH
        end = start + BASE_WIDTH - 1
        if end > HIGH or start >= end:
            break
        ranges.append({
            "id": i + 1,
            "name": f"main_zone_{i+1:03d}",
            "start": int_to_hex_padded(start, 64),
            "end": int_to_hex_padded(end, 64),
            "center": int_to_hex_padded((start + end) // 2, 64),
            "width_hex": int_to_hex_padded(BASE_WIDTH, 16),
            "width_decimal": f"{BASE_WIDTH:.3e}"
        })

    # --- Добавка: 2 fallback-диапазона для надёжности ---
    fallback_centers = []

    # 1. Golden ratio
    try:
        gr_center = int(k70 * 1.61803398875)
        if LOW <= gr_center <= HIGH:
            fallback_centers.append(("golden_ratio", gr_center))
    except:
        pass

    # 2. Верхняя треть диапазона
    third2_center = LOW + 2 * (TOTAL_RANGE // 3)
    fallback_centers.append(("upper_third", third2_center))

    for name, center in fallback_centers:
        if len(ranges) >= num_ranges:
            break
        start = max(LOW, center - BASE_WIDTH // 2)
        end = start + BASE_WIDTH - 1
        if end <= HIGH and start < end:
            ranges.append({
                "id": len(ranges) + 1,
                "name": name,
                "start": int_to_hex_padded(start, 64),
                "end": int_to_hex_padded(end, 64),
                "center": int_to_hex_padded((start + end) // 2, 64),
                "width_hex": int_to_hex_padded(BASE_WIDTH, 16),
                "width_decimal": f"{BASE_WIDTH:.3e}"
            })

    return ranges[:num_ranges]

def main():
    print("🚀 Puzzle #71 Targeted Search Generator")
    print("   Версия с поддержкой 100+ GPU-friendly диапазонов")
    print("=" * 78)

    # Загрузка данных
    data = load_puzzle_data("Akey.json")
    solved = get_solved_puzzles(data)
    if not solved:
        print("❌ Не найдено ни одной решённой головоломки.")
        sys.exit(1)
    print(f"✅ Загружено {len(solved)} решённых головоломок (puzzle {solved[0]['puzzle']}-{solved[-1]['puzzle']})")

    # Ввод количества диапазонов
    try:
        num_input = input("🔢 Сколько диапазонов сгенерировать? (1–1000, по умолчанию 10): ").strip()
        num_ranges = int(num_input) if num_input else 10
        num_ranges = max(1, min(1000, num_ranges))
    except Exception:
        num_ranges = 10

    # Генерация
    try:
        ranges = predict_ranges_puzzle71(solved, num_ranges)
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        sys.exit(1)

    if not ranges:
        print("❌ Не удалось сгенерировать ни одного валидного диапазона.")
        sys.exit(1)

    # Вывод
    print(f"\n🎯 Сгенерировано {len(ranges)} диапазонов для puzzle #71:")
    print("-" * 92)
    print(f"{'ID':<4} {'Метод':<18} | {'Начало (последние 16 hex)':<18} | {'Конец (последние 16 hex)':<18} | Ширина (dec)")
    print("-" * 92)
    for r in ranges:
        start_tail = r['start'][-16:]
        end_tail = r['end'][-16:]
        print(f"{r['id']:<4} {r['name']:<18} | {start_tail} | {end_tail} | {r['width_decimal']}")

    # Сохранение основного JSON
    result = {
        "puzzle": 71,
        "status": "predicted",
        "addr": "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU",
        "source_file": "Akey.json",
        "search_ranges": [{"start": r["start"], "end": r["end"]} for r in ranges],
        "metadata": {
            "total_ranges": len(ranges),
            "range_width_per_range_approx": f"~{ranges[0]['width_decimal']} keys",
            "gpu_friendly": True,
            "coverage_zone": "±0.02%–0.1% around k70^2/k69",
            "recommendation": "Run ranges in parallel on multiple GPUs"
        }
    }

    json_file = "puzzle71_gpu_ranges.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Основной JSON: {json_file}")

    # Экспорт отдельных файлов для GPU-сканеров
    ranges_dir = "ranges"
    os.makedirs(ranges_dir, exist_ok=True)
    for r in ranges:
        idx = r['id']
        filename = os.path.join(ranges_dir, f"range_{idx:03d}.txt")
        with open(filename, "w") as f:
            f.write(f"{r['start']}:{r['end']}\n")
    print(f"📁 Экспортировано {len(ranges)} диапазонов в папку '{ranges_dir}/'")

    # Подсказки
    print(f"\n💡 Советы:")
    print(f"   • Запуск на одной GPU (BitCrack):")
    print(f"       bitcrack -b 32 -t 256 -p 512 --keyspace $(cat ranges/range_001.txt) 1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU")
    print(f"   • Запуск на 4 GPU параллельно (Linux):")
    print(f"       for i in {{1..4}}; do ./kangaroo -gpu ranges/range_$(printf \"%03d\" $i).txt & done")
    print(f"   • Ваши диапазоны покрывают зону максимальной вероятности на основе тренда 60→70.")

if __name__ == "__main__":
    main()
