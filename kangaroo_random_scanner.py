import os
import time
import random
import subprocess
import sys
import hashlib
import base58


# ================== НАСТРОЙКИ ПО УМОЛЧАНИЮ ==================
ETARKANGAROO_EXE = "Etarkangaroo.exe"  # Убедись, что лежит в этой папке
GRID_PARAMS = "88,128"                 # Базовый grid (подбирается под GPU)
DP = 16                                # Distinguished points
SCAN_DURATION = 300                    # 5 минут на сеанс
SUBRANGE_BITS = 32                     # Размер поддиапазона: 2^32
TEMP_DIR = "./kangaroo_work/"
os.makedirs(TEMP_DIR, exist_ok=True)
# ============================================================


def sha256(data):
    return hashlib.sha256(data).digest()


def ripemd160(data):
    h = hashlib.new('ripemd160')
    h.update(data)
    return h.digest()


def hash160(pubkey_bytes):
    return ripemd160(sha256(pubkey_bytes))


def pubkey_to_p2pkh_address(pubkey_hex):
    """Преобразует публичный ключ в P2PKH адрес"""
    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        if len(pubkey_bytes) not in (33, 65):
            print(f"[!] Неверная длина публичного ключа: {len(pubkey_bytes)}")
            return None
        h160 = hash160(pubkey_bytes)
        versioned = b'\x00' + h160
        checksum = sha256(sha256(versioned))[:4]
        address = base58.b58encode(versioned + checksum)
        return address.decode('utf-8')
    except Exception as e:
        print(f"[!] Ошибка генерации адреса: {e}")
        return None


def get_gpu_list():
    """Получает список GPU через nvidia-smi"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,driver_version,memory.total',
             '--format=csv,noheader'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(', ')
                idx = parts[0]
                name = parts[1]
                gpus.append((idx, name))
        return gpus
    except FileNotFoundError:
        return None  # nvidia-smi не найден
    except Exception as e:
        print(f"[!] Ошибка при получении GPU: {e}")
        return None


def select_gpus():
    """Позволяет пользователю выбрать GPU (одну или несколько)"""
    print("🔍 Поиск GPU...\n")
    gpus = get_gpu_list()

    if not gpus:
        print("[⚠️] Не удалось получить список GPU.")
        print("     Убедитесь, что установлены драйверы NVIDIA и nvidia-smi работает.")
        print("     Или введите ID GPU вручную (например: 0,1,2)")
        gpu_input = input("Введите ID GPU: ").strip()
        return gpu_input

    print("📌 Доступные GPU:")
    for i, (idx, name) in enumerate(gpus):
        print(f"   [{i}] ID: {idx} | {name}")

    print("\nВыберите GPU:")
    print("   Введите номер (например: 0)")
    print("   Или несколько через запятую (например: 0,1)")
    print("   Или 'all' для всех")

    choice = input("Выбор: ").strip()

    selected_ids = []
    if choice.lower() == 'all':
        selected_ids = [idx for idx, _ in gpus]
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(',')]
            for i in indices:
                if 0 <= i < len(gpus):
                    selected_ids.append(gpus[i][0])
                else:
                    print(f"[❌] Неверный индекс: {i}")
            if not selected_ids:
                print("[❌] Нет корректных индексов.")
                sys.exit(1)
        except ValueError:
            print("[❌] Неверный ввод.")
            sys.exit(1)

    print(f"\n✅ Выбраны GPU: {','.join(selected_ids)}")
    return ','.join(selected_ids)


def hex_to_int(h):
    return int(h.strip(), 16)


def int_to_hex(x):
    return f"{x:064x}"


def random_subrange(full_start, full_end, bits=32):
    width = (1 << bits)
    max_start = full_end - width
    if max_start <= full_start:
        return full_start, full_end
    rand_start = random.randint(full_start, max_start)
    rand_end = rand_start + width
    return rand_start, rand_end


def get_grid_for_gpu(gpu_name):
    """Возвращает рекомендуемый grid под GPU"""
    gpu_name = gpu_name.lower()
    if 'rtx 4090' in gpu_name:
        return "104,256"
    elif 'rtx 4080' in gpu_name:
        return "96,256"
    elif 'rtx 3090' in gpu_name or 'rtx 3080' in gpu_name:
        return "96,256"
    elif 'rtx 3070' in gpu_name:
        return "92,256"
    elif 'rtx 3060' in gpu_name or 'gtx 1660' in gpu_name or 'gtx 1650' in gpu_name:
        return "88,128"
    elif 'rtx 20' in gpu_name or 'gtx 10' in gpu_name:
        return "64,128"  # старые GPU
    else:
        print(f"[⚠️] Неизвестная GPU: {gpu_name}. Используем стандартный grid: {GRID_PARAMS}")
        return GRID_PARAMS


def main():
    print("🔍 EtarKangaroo — Мульти-GPU Автосканер")
    print("⚙️  Поддержка нескольких видеокарт\n")

    # === ВЫБОР GPU ===
    gpu_ids = select_gpus()

    # Получим модель первой GPU для подбора grid
    gpus = get_gpu_list()
    if gpus and gpus[0][0] in gpu_ids.split(','):
        first_gpu_name = gpus[0][1]
    else:
        first_gpu_name = "unknown"
    grid = get_grid_for_gpu(first_gpu_name)
    print(f"[🔧] Автоподбор grid: {grid} (под {first_gpu_name})\n")

    # === ДАННЫЕ ===
    target_address = "16RGFo6hjq9ym6Pj7N5H7L1NR1rVPJyw2v"
    pubkey_hex = "02145d2611c823a396ef6712ce0f712f09b9b4f3135e3e0aa3230fb9b6d08d1e16"
    rb_hex = "00000000000000000000000000000040067A9BF03190CC89839FBA76C6D897DF"
    re_hex = "00000000000000000000000000000058067A9BF03190CC89839FBA76C6D897DF"

    # Проверка публичного ключа
    derived_addr = pubkey_to_p2pkh_address(pubkey_hex)
    if not derived_addr:
        print("[❌] Ошибка при обработке публичного ключа.")
        sys.exit(1)

    if derived_addr != target_address:
        print(f"[⚠️] Публичный ключ даёт адрес: {derived_addr}")
        print(f"      Но вы ищете: {target_address}")
        cont = input("Продолжить? (y/N): ")
        if cont.lower() != 'y':
            sys.exit(0)
    else:
        print(f"[✅] Публичный ключ соответствует адресу: {target_address}")

    # Парсим диапазон
    try:
        rb = hex_to_int(rb_hex)
        re = hex_to_int(re_hex)
    except Exception as e:
        print(f"[❌] Ошибка парсинга диапазона: {e}")
        sys.exit(1)

    if rb >= re:
        print("[❌] Начало диапазона >= конца")
        sys.exit(1)

    print(f"[📊] Общий диапазон: {int_to_hex(rb)} → {int_to_hex(re)}")
    print(f"[⚙️] Поддиапазон: 2^{SUBRANGE_BITS} ключей")
    print(f"[⏱] Длительность сеанса: {SCAN_DURATION} секунд")
    print(f"[🔄] Новый случайный поддиапазон каждые 5 минут...\n")

    session_id = 1
    while True:
        print(f"📌 СЕАНС #{session_id}")
        session_id += 1

        start, end = random_subrange(rb, re, SUBRANGE_BITS)
        rb_sub = int_to_hex(start)
        re_sub = int_to_hex(end)

        kf_file = f"{TEMP_DIR}kang_{session_id}.dat"
        wf_file = f"{TEMP_DIR}ht_{session_id}.dat"
        result_file = f"{TEMP_DIR}result_{session_id}.txt"

        cmd = [
            ETARKANGAROO_EXE,
            "-dp", str(DP),
            "-d", gpu_ids,
            "-grid", grid,
            "-rb", rb_sub,
            "-re", re_sub,
            "-pub", pubkey_hex,
            "-o", result_file,
            "-kf", kf_file,
            "-wf", wf_file,
            "-wi", str(SCAN_DURATION),
            "-wsplit",
            "-wmerge"
        ]

        print(f"🚀 Запуск EtarKangaroo...")
        print(f"   GPU: {gpu_ids}")
        print(f"   Диапазон: {rb_sub} → {re_sub}")
        cmd_str = " ".join(cmd)
        print(f"   Команда: {cmd_str[:100]}...")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(ETARKANGAROO_EXE) or ".",
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

            time.sleep(SCAN_DURATION)

            print(f"⏹ Остановка сеанса #{session_id}...")
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

            if os.path.exists(result_file):
                with open(result_file, "r") as f:
                    content = f.read().strip()
                if content:
                    print(f"🎉 🔑 КЛЮЧ НАЙДЕН! Сохранён в: {result_file}")
                    print(f"Содержимое: {content}")
                    input("\nНажмите Enter для завершения...")
                    sys.exit(0)
                else:
                    print("❌ Ключ не найден в этом сеансе.")
            else:
                print("❌ Файл результата не создан.")

        except KeyboardInterrupt:
            print("\n\n👋 Остановлено пользователем.")
            break
        except Exception as e:
            print(f"[⚠️] Ошибка: {e}")

        print(f"💤 Пауза перед следующим сеансом...\n")
        time.sleep(3)

    print("✅ Завершено.")


if __name__ == "__main__":
    main()