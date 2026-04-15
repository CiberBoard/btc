# predictor.py
import json
import sys
import os
from typing import List, Dict, Tuple


def load_puzzle_data(filepath: str = "KNOWN_KEYS_HEX.json") -> List[str]:
    """
    Загружает список известных ключей из JSON-файла.

    Ожидаемый формат файла:
    {
        "KNOWN_KEYS_HEX": [
            "0000000000000000000000000000000000000000000000000000000000000001",
            "0000000000000000000000000000000000000000000000000000000000000003",
            ...
        ]
    }

    ИЛИ просто массив:
    [
        "0000000000000000000000000000000000000000000000000000000000000001",
        "0000000000000000000000000000000000000000000000000000000000000003",
        ...
    ]
    """
    if not os.path.exists(filepath):
        print(f"❌ Файл '{filepath}' не найден!")
        print(f"Поместите {filepath} в папку: {os.getcwd()}")
        print(f"\n📋 Ожидаемый формат содержимого файла:")
        print(f"""
{{
    "KNOWN_KEYS_HEX": [
        "0000000000000000000000000000000000000000000000000000000000000001",
        "0000000000000000000000000000000000000000000000000000000000000003",
        ...
    ]
}}
        """)
        sys.exit(1)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Поддержка двух форматов: объект с ключом или прямой массив
        if isinstance(data, dict) and "KNOWN_KEYS_HEX" in data:
            keys = data["KNOWN_KEYS_HEX"]
        elif isinstance(data, list):
            keys = data
        else:
            raise ValueError("Неизвестный формат JSON. Ожидается массив строк или объект с ключом 'KNOWN_KEYS_HEX'")

        # Очистка и фильтрация ключей
        cleaned_keys = [
            str(k).strip().replace("0x", "").replace("0X", "").zfill(64)
            for k in keys
            if str(k).strip()
        ]

        if not cleaned_keys:
            raise ValueError("Файл не содержит валидных ключей")

        return cleaned_keys

    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON в {filepath}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка при чтении {filepath}: {e}")
        sys.exit(1)


def hex_to_int(h: str) -> int:
    """Конвертирует hex-строку в целое число"""
    if h is None:
        return 0
    h = h.strip().replace("0x", "").replace("0X", "")
    return int(h, 16) if h else 0


def int_to_hex_padded(n: int, width: int = 64) -> str:
    """Конвертирует int в hex-строку с заполнением нулями до заданной ширины"""
    return hex(n)[2:].zfill(width)


def get_puzzle_range(puzzle_num: int) -> Tuple[int, int]:
    """
    Возвращает диапазон поиска для головоломки #N.
    Puzzle N: диапазон [2^(N-1), 2^N - 1]
    """
    low = 1 << (puzzle_num - 1)  # 2^(N-1)
    high = (1 << puzzle_num) - 1  # 2^N - 1
    return low, high


def get_solved_puzzles(keys_hex: List[str]) -> List[Dict]:
    """
    Преобразует список hex-ключей в структурированные данные головоломок.
    Индекс в списке = номер головоломки - 1 (keys_hex[0] → puzzle #1)
    """
    solved = []
    for idx, key_hex in enumerate(keys_hex):
        puzzle_num = idx + 1
        try:
            k = hex_to_int(key_hex)
            low, high = get_puzzle_range(puzzle_num)
            # Проверяем, что ключ действительно попадает в ожидаемый диапазон
            if k != 0 and low <= k <= high:
                solved.append({
                    "puzzle": puzzle_num,
                    "k": k,
                    "low": low,
                    "high": high,
                    "range_width": high - low + 1,
                    "key_hex": key_hex.strip()
                })
        except Exception as e:
            print(f"⚠️ Ошибка при обработке ключа #{puzzle_num}: {e}")
            continue
    return sorted(solved, key=lambda x: x["puzzle"])


def predict_ranges_puzzle71(solved: List[Dict], num_ranges: int = 10) -> List[Dict]:
    """
    Генерирует N оптимизированных диапазонов для puzzle #71
    на основе геометрического тренда: k71 ≈ k70² / k69
    """
    # === Диапазон puzzle 71: [2^70, 2^71 - 1] ===
    LOW, HIGH = get_puzzle_range(71)
    TOTAL_RANGE = HIGH - LOW + 1  # = 2^70

    # === Извлекаем ключи для puzzle 69 и 70 ===
    k69 = next((p["k"] for p in solved if p["puzzle"] == 69), None)
    k70 = next((p["k"] for p in solved if p["puzzle"] == 70), None)

    if not (k69 and k70):
        available = [p["puzzle"] for p in solved]
        raise ValueError(
            f"Необходимы решённые puzzle 69 и 70.\n"
            f"   Доступно головоломок: {len(solved)} (#{min(available)}–#{max(available)})"
        )

    # === Прогноз центра: геометрическая экстраполяция ===
    center_base = (k70 * k70) // k69
    center_base = max(LOW, min(HIGH, center_base))

    # === Адаптивные параметры в зависимости от количества диапазонов ===
    if num_ranges <= 10:
        ZONE_RADIUS = TOTAL_RANGE // 1000  # ±0.1% от общего диапазона
        MIN_WIDTH = 1 << 58  # ~2.9e17 ключей
    elif num_ranges <= 50:
        ZONE_RADIUS = TOTAL_RANGE // 2000  # ±0.05%
        MIN_WIDTH = 1 << 54  # ~1.8e16
    else:
        ZONE_RADIUS = TOTAL_RANGE // 5000  # ±0.02% для 100+ диапазонов
        MIN_WIDTH = 1 << 48  # ~2.8e14

    # === Определяем зону поиска вокруг прогноза ===
    zone_start = max(LOW, center_base - ZONE_RADIUS)
    zone_end = min(HIGH, center_base + ZONE_RADIUS)
    zone_width = zone_end - zone_start + 1

    # === Вычисляем ширину одного поддиапазона ===
    BASE_WIDTH = max(MIN_WIDTH, zone_width // num_ranges)
    BASE_WIDTH = min(BASE_WIDTH, 1 << 62)  # Технический лимит

    # === Генерация основных диапазонов ===
    ranges = []
    actual_num = min(num_ranges, zone_width // BASE_WIDTH, 1000)

    for i in range(int(actual_num)):
        start = zone_start + i * BASE_WIDTH
        end = start + BASE_WIDTH - 1
        if end > HIGH or start >= end:
            break
        ranges.append({
            "id": i + 1,
            "name": f"main_zone_{i + 1:03d}",
            "start": int_to_hex_padded(start, 64),
            "end": int_to_hex_padded(end, 64),
            "center": int_to_hex_padded((start + end) // 2, 64),
            "width_hex": int_to_hex_padded(BASE_WIDTH, 16),
            "width_decimal": f"{BASE_WIDTH:.3e}"
        })

    # === Fallback-диапазоны для повышения надёжности ===
    fallback_centers = []

    # 1. Золотое сечение (эмпирический паттерн)
    try:
        gr_center = int(k70 * 1.61803398875)
        if LOW <= gr_center <= HIGH:
            fallback_centers.append(("golden_ratio", gr_center))
    except:
        pass

    # 2. Верхняя треть полного диапазона (резервная зона)
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
    print("   Загрузка из KNOWN_KEYS_HEX.json")
    print("=" * 78)

    # === Загрузка данных из файла ===
    keys_hex = load_puzzle_data("KNOWN_KEYS_HEX.json")
    print(f"✅ Загружено {len(keys_hex)} ключей из KNOWN_KEYS_HEX.json")

    solved = get_solved_puzzles(keys_hex)

    if not solved:
        print("❌ Не найдено ни одной валидной головоломки.")
        print("   Проверьте, что ключи в файле соответствуют своим диапазонам (#1: 2^0–2^1-1, #2: 2^1–2^2-1, ...)")
        sys.exit(1)

    print(f"✅ Обработано {len(solved)} головоломок (#{solved[0]['puzzle']}–#{solved[-1]['puzzle']})")

    if len(solved) < 70:
        print(f"⚠️ Предупреждение: для точного прогноза нужны головоломки #69 и #70")
        print(f"   Сейчас доступно: {len(solved)}")

    # === Ввод количества диапазонов ===
    try:
        num_input = input("🔢 Сколько диапазонов сгенерировать? (1–1000, по умолчанию 10): ").strip()
        num_ranges = int(num_input) if num_input else 10
        num_ranges = max(1, min(1000, num_ranges))
    except Exception:
        num_ranges = 10
        print(f"   → Использовано значение по умолчанию: {num_ranges}")

    # === Генерация диапазонов ===
    try:
        ranges = predict_ranges_puzzle71(solved, num_ranges)
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        sys.exit(1)

    if not ranges:
        print("❌ Не удалось сгенерировать ни одного валидного диапазона.")
        sys.exit(1)

    # === Вывод результатов ===
    print(f"\n🎯 Сгенерировано {len(ranges)} диапазонов для puzzle #71:")
    print("-" * 92)
    print(f"{'ID':<4} {'Метод':<18} | {'Начало (последние 16 hex)':<18} | {'Конец (последние 16 hex)':<18} | Ширина")
    print("-" * 92)
    for r in ranges:
        start_tail = r['start'][-16:]
        end_tail = r['end'][-16:]
        print(f"{r['id']:<4} {r['name']:<18} | {start_tail} | {end_tail} | {r['width_decimal']}")

    # === Сохранение основного JSON ===
    result = {
        "puzzle": 71,
        "status": "predicted",
        "addr": "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU",
        "source_file": "KNOWN_KEYS_HEX.json",
        "search_ranges": [{"start": r["start"], "end": r["end"]} for r in ranges],
        "metadata": {
            "total_ranges": len(ranges),
            "range_width_per_range_approx": f"~{ranges[0]['width_decimal']} keys",
            "gpu_friendly": True,
            "coverage_zone": "±0.02%–0.1% вокруг прогноза (k70²/k69)",
            "recommendation": "Запускайте диапазоны параллельно на нескольких GPU"
        }
    }

    json_file = "puzzle71_gpu_ranges.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Основной JSON: {json_file}")

    # === Экспорт отдельных файлов для сканеров ===
    ranges_dir = "ranges"
    os.makedirs(ranges_dir, exist_ok=True)
    for r in ranges:
        idx = r['id']
        filename = os.path.join(ranges_dir, f"range_{idx:03d}.txt")
        with open(filename, "w") as f:
            f.write(f"{r['start']}:{r['end']}\n")
    print(f"📁 Экспортировано {len(ranges)} диапазонов в папку '{ranges_dir}/'")

    # === Подсказки по запуску ===
    print(f"\n💡 Советы по запуску:")
    print(f"   • BitCrack (одна GPU):")
    print(
        f"       bitcrack -b 32 -t 256 -p 512 --keyspace $(cat ranges/range_001.txt) 1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU")
    print(f"   • Kangaroo (4 GPU параллельно, Linux):")
    print(f"       for i in {{1..4}}; do ./kangaroo -gpu ranges/range_$(printf \"%03d\" $i).txt & done")
    print(f"   • Ваши диапазоны покрывают зону максимальной вероятности на основе тренда #69→#70→#71")


if __name__ == "__main__":
    main()