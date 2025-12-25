import os
import time
import random
import subprocess
import json
import sys

# ================== CONFIG ==================
CONFIG_FILE = "config.json"

if not os.path.exists(CONFIG_FILE):
    print(f"[❌] Файл конфигурации не найден: {CONFIG_FILE}")
    sys.exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

ETARKANGAROO_EXE = config["etarkangaroo_exe"]
DP = int(config["dp"])
SCAN_DURATION = int(config["scan_duration"])
SUBRANGE_BITS = int(config["subrange_bits"])
GRID = config["grid_params"]
TEMP_DIR = config["temp_dir"]

pubkey_hex = config["pubkey_hex"].strip()
rb_hex = config["rb_hex"].strip()
re_hex = config["re_hex"].strip()

os.makedirs(TEMP_DIR, exist_ok=True)

# ================== UTILS ==================
def hex_to_int(h):
    h = h.lower().replace("0x", "")
    if not h:
        raise ValueError("Пустая hex-строка")
    return int(h, 16)

def int_to_hex(x):
    return f"{x:064x}"

def random_subrange(start, end, bits):
    if start >= end:
        raise ValueError(f"Некорректный диапазон: start ({start}) >= end ({end})")

    width = 1 << bits
    total = end - start

    print(f"[🔍] Общий диапазон: {total} (~2^{total.bit_length()})")
    print(f"[🔍] Окно поиска:   {width} (2^{bits})")

    if total <= width:
        print("[ℹ️] Диапазон ≤ окна — сканируем ВЕСЬ диапазон")
        return start, end

    max_offset = total - width
    # Поддержка Python < 3.6: используем getrandbits вместо randbelow
    try:
        # Попытка использовать randbelow, если доступно (Python 3.6+)
        offset = random.randbelow(max_offset + 1)
    except AttributeError:
        # Fallback для Python < 3.6
        print("[ℹ️] random.randbelow недоступен — используем getrandbits (Python < 3.6)")
        bits_needed = max_offset.bit_length()
        while True:
            candidate = random.getrandbits(bits_needed)
            if candidate <= max_offset:
                offset = candidate
                break

    s = start + offset
    e = s + width
    return s, e

# ================== MAIN ==================
def main():
    print("🔍 Kangaroo RANDOM scanner (Python 3.5+ совместимая версия)")
    print("⚠️  Режим: СЛУЧАЙНЫЙ")
    print("-" * 70)

    if not os.path.exists(ETARKANGAROO_EXE):
        print(f"[❌] Etarkangaroo не найден: {ETARKANGAROO_EXE}")
        print("💡 Проверьте, лежит ли Etarkangaroo.exe в той же папке, что и скрипт.")
        return

    # Загрузка диапазонов
    try:
        rb = hex_to_int(rb_hex)
        re = hex_to_int(re_hex)
    except Exception as e:
        print(f"[❌] Ошибка парсинга rb/re: {e}")
        return

    print(f"[🔍] Исходный rb = 0x{rb:064x}")
    print(f"[🔍] Исходный re = 0x{re:064x}")

    # Автоисправление rb > re
    if rb > re:
        print("[🔄] rb > re — диапазон перепутан, ИСПРАВЛЯЮ")
        rb, re = re, rb

    if rb == re:
        print("[❌] rb == re — нулевой диапазон. Проверьте config.json!")
        return

    total_range = re - rb
    print(f"[🔍] Диапазон: [{rb}, {re}) → длина = {total_range} (~2^{total_range.bit_length()})")
    print("-" * 70)
    print(f"[⚙️] SUBRANGE_BITS = {SUBRANGE_BITS} → окно = {1 << SUBRANGE_BITS}")
    print(f"[⚙️] SCAN_DURATION = {SCAN_DURATION} сек")
    print("-" * 70)

    session = 1

    while True:
        try:
            s, e = random_subrange(rb, re, SUBRANGE_BITS)
        except Exception as err:
            print(f"[❌] Ошибка генерации поддиапазона: {err}")
            return

        rs = int_to_hex(s)
        re_ = int_to_hex(e)
        diff = e - s
        print(f"\n📌 СЕАНС #{session}")
        print(f"  rb = {rs}")
        print(f"  re = {re_}")
        print(f"  Δ  = {diff} (должно быть {1 << SUBRANGE_BITS})")

        result_file = os.path.abspath(os.path.join(TEMP_DIR, f"result_{session}.txt"))

        cmd = [
            ETARKANGAROO_EXE,
            "-dp", str(DP),
            "-grid", GRID,
            "-rb", rs,
            "-re", re_,
            "-pub", pubkey_hex,
            "-o", result_file
        ]

        print(f"[🚀] Запуск: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            start_time = time.time()
            while proc.poll() is None:
                output = proc.stdout.readline()
                if output:
                    print(f"    {output.strip()}")
                if time.time() - start_time > SCAN_DURATION:
                    print(f"[⏳] Таймаут {SCAN_DURATION} сек — завершаем процесс...")
                    break

            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

            rc = proc.returncode
            print(f"[🏁] Etarkangaroo завершён. Код: {rc}")

        except Exception as e:
            print(f"[⚠️] Ошибка запуска: {e}")
            session += 1
            time.sleep(1)
            continue

        # Проверка результата
        if os.path.exists(result_file):
            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                print(f"[📄] Файл результата: {result_file} ({len(content)} байт)")
                if content:
                    print("\n" + "="*50)
                    print("🎉 КЛЮЧ НАЙДЕН!")
                    print("="*50)
                    print(content)
                    print("="*50)
                    return
                else:
                    print("    → файл пуст (ключ не найден)")
            except Exception as e:
                print(f"[⚠️] Ошибка чтения результата: {e}")
        else:
            print(f"[❌] Файл результата НЕ создан: {result_file}")

        session += 1
        print(f"[💤] Пауза 1 сек...")
        time.sleep(1)

# ================== RUN ==================
if __name__ == "__main__":
    main()