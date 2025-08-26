import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import os
import time
import random
import subprocess
import sys
import hashlib
import base58
import json


# ================== ЗАГРУЗКА КОНФИГА ==================
CONFIG_FILE = "config.json"

if not os.path.exists(CONFIG_FILE):
    print(f"[❌] Не найден файл конфигурации: {CONFIG_FILE}")
    print("Создайте его с параметрами. Пример:")
    example_config = {
        "target_address": "16RGFo6hjq9ym6Pj7N5H7L1NR1rVPJyw2v",
        "pubkey_hex": "02145d2611c823a396ef6712ce0f712f09b9b4f3135e3e0aa3230fb9b6d08d1e16",
        "rb_hex": "00000000000000000000000000000040067A9BF03190CC89839FBA76C6D897DF",
        "re_hex": "00000000000000000000000000000058067A9BF03190CC89839FBA76C6D897DF",
        "scan_duration": 300,
        "subrange_bits": 32,
        "dp": 16,
        "grid_params": "88,128",
        "temp_dir": "./kangaroo_work/",
        "etarkangaroo_exe": "Etarkangaroo.exe"
    }
    print(json.dumps(example_config, indent=2))
    input("Нажмите Enter для выхода...")
    sys.exit(1)

try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
except Exception as e:
    print(f"[❌] Ошибка чтения config.json: {e}")
    input("Нажмите Enter для выхода...")
    sys.exit(1)

# Извлечение настроек
ETARKANGAROO_EXE = config.get("etarkangaroo_exe", "Etarkangaroo.exe")
GRID_PARAMS = config.get("grid_params", "88,128")
DP = config.get("dp", 16)
SCAN_DURATION = config.get("scan_duration", 300)
SUBRANGE_BITS = config.get("subrange_bits", 32)
TEMP_DIR = config.get("temp_dir", "./kangaroo_work/")

# Данные
target_address = config["target_address"]
pubkey_hex = config["pubkey_hex"]
rb_hex = config["rb_hex"]
re_hex = config["re_hex"]

os.makedirs(TEMP_DIR, exist_ok=True)

# Проверка EtarKangaroo.exe
if not os.path.exists(ETARKANGAROO_EXE):
    print(f"[❌] Не найден: {ETARKANGAROO_EXE}")
    input("Нажмите Enter для выхода...")
    sys.exit(1)


# ================== КРИПТОГРАФИЯ ==================
def sha256(data):
    return hashlib.sha256(data).digest()

def ripemd160(data):
    h = hashlib.new('ripemd160')
    h.update(data)
    return h.digest()

def hash160(pubkey_bytes):
    return ripemd160(sha256(pubkey_bytes))

def pubkey_to_p2pkh_address(pubkey_hex):
    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        if len(pubkey_bytes) not in (33, 65):
            return None
        h160 = hash160(pubkey_bytes)
        versioned = b'\x00' + h160
        checksum = sha256(sha256(versioned))[:4]
        address = base58.b58encode(versioned + checksum)
        return address.decode('utf-8')
    except Exception:
        return None


# ================== РАБОТА С GPU ==================
def get_gpu_list():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name', '--format=csv,noheader'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if line:
                idx, name = line.split(', ')
                gpus.append((idx.strip(), name.strip()))
        return gpus
    except:
        return None


def get_grid_for_gpu(gpu_name):
    gpu_name = gpu_name.lower()
    if 'rtx 4090' in gpu_name: return "104,256"
    elif 'rtx 4080' in gpu_name: return "96,256"
    elif 'rtx 3090' in gpu_name or 'rtx 3080' in gpu_name: return "96,256"
    elif 'rtx 3070' in gpu_name: return "92,256"
    elif 'rtx 3060' in gpu_name or 'gtx 1660' in gpu_name or 'gtx 1650' in gpu_name: return "88,128"
    elif 'rtx 20' in gpu_name or 'gtx 10' in gpu_name: return "64,128"
    else: return GRID_PARAMS


def hex_to_int(h):
    return int(h.strip().strip('0x').lower(), 16)

def int_to_hex(x):
    return f"{x:064x}"

def random_subrange(full_start, full_end, bits=32):
    width = 1 << bits  # 2^32
    if full_end - full_start <= width:
        return full_start, full_end

    max_start = full_end - width
    if max_start <= full_start:
        return full_start, full_end

    # Попробуем через random.randint
    try:
        offset = random.randint(0, max_start - full_start)
        rand_start = full_start + offset
        return rand_start, rand_start + width
    except (ValueError, OverflowError):
        # Если диапазон слишком большой
        diff = max_start - full_start
        if diff <= 0:
            return full_start, full_end
        num_bytes = (diff.bit_length() + 7) // 8
        while True:
            rand_bytes = os.urandom(num_bytes)
            rand_offset = int.from_bytes(rand_bytes, 'big')
            if rand_offset <= diff:
                rand_start = full_start + rand_offset
                return rand_start, rand_start + width


# ================== ДИАЛОГ ВЫБОРА GPU (ПОЛНОСТЬЮ ТЁМНЫЙ) ==================
def gpu_selection_dialog(root, gpus):
    dialog = tk.Toplevel(root)
    dialog.title("🎮 GPU")
    dialog.minsize(350, 200)
    dialog.geometry("380x300")
    dialog.config(bg="#252525")
    dialog.transient(root)
    dialog.grab_set()

    # Grid-сетка для полного контроля
    dialog.grid_columnconfigure(0, weight=1)
    dialog.grid_rowconfigure(1, weight=1)

    # 0: Заголовок
    tk.Label(
        dialog,
        text="  Выберите GPU:",
        bg="#252525",
        fg="white",
        font=("Arial", 9, "bold"),
        anchor="w"
    ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

    # 1: Canvas + Scrollbar (в одной ячейке)
    canvas = tk.Canvas(dialog, bg="#252525", highlightthickness=0, height=100)
    scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#252525")

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=340)
    canvas.configure(yscrollcommand=scrollbar.set)

    # Размещаем canvas и scrollbar в сетке
    canvas.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=4)
    scrollbar.grid(row=1, column=1, sticky="ns", pady=4)

    # Чекбоксы
    vars = [tk.BooleanVar() for _ in gpus]
    for i, (idx, name) in enumerate(gpus):
        short_name = name[:28] + "..." if len(name) > 28 else name
        cb = tk.Checkbutton(
            scroll_frame,
            text=f"ID:{idx} | {short_name}",
            variable=vars[i],
            bg="#252525",
            fg="white",
            selectcolor="#3a3a3a",
            font=("Arial", 8),
            anchor="w",
            padx=2,
            pady=1
        )
        cb.grid(row=i, column=0, sticky="w", padx=2)

    # 2: Режим выбора — в строку
    mode = tk.StringVar(value="selected")
    mode_frame = tk.Frame(dialog, bg="#252525")
    mode_frame.grid(row=2, column=0, sticky="w", padx=10, pady=(6, 4))

    tk.Radiobutton(
        mode_frame, text="Выбранные", variable=mode, value="selected",
        bg="#252525", fg="white", selectcolor="#3a3a3a", font=("Arial", 8)
    ).pack(side="left", padx=(0, 10))

    tk.Radiobutton(
        mode_frame, text="Все", variable=mode, value="all",
        bg="#252525", fg="white", selectcolor="#3a3a3a", font=("Arial", 8)
    ).pack(side="left")

    # 3: КНОПКИ — СЛЕВА, с помощью grid
    btn_frame = tk.Frame(dialog, bg="#252525")
    btn_frame.grid(row=3, column=0, sticky="w", padx=10, pady=(10, 8))

    result = []

    def submit():
        if mode.get() == "all":
            result.extend([idx for idx, _ in gpus])
        else:
            result.extend([gpus[i][0] for i, var in enumerate(vars) if var.get()])
        if not result:
            messagebox.showwarning("⚠️", "Ничего не выбрано!")
            return
        dialog.destroy()

    # Кнопки в grid-фрейме слева
    tk.Button(
        btn_frame, text="✅ OK", width=8, font=("Arial", 8, "bold"),
        bg="#00a86b", fg="white", command=submit
    ).grid(row=0, column=0)

    tk.Button(
        btn_frame, text="❌ Отм", width=8, font=("Arial", 8, "bold"),
        bg="#d9534f", fg="white", command=dialog.destroy
    ).grid(row=0, column=1, padx=(6, 0))

    # Центрируем
    dialog.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() // 2) - (dialog.winfo_width() // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    dialog.resizable(True, True)
    root.wait_window(dialog)
    return ','.join(result) if result else None


def input_dialog(root, prompt):
    value = tk.StringVar()
    dialog = tk.Toplevel(root)
    dialog.title("⌨️ Ввод")
    dialog.geometry("320x100")
    dialog.config(bg="#252525")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text=prompt, bg="#252525", fg="white", font=("Arial", 9)).pack(pady=5)
    entry = tk.Entry(
        dialog, textvariable=value, width=28,
        bg="#3a3a3a", fg="white", insertbackground="white", font=("Arial", 9)
    )
    entry.pack(pady=5)
    entry.focus()

    tk.Button(
        dialog, text="OK", command=dialog.destroy,
        bg="#007acc", fg="white", width=8
    ).pack(pady=5)

    root.wait_window(dialog)
    return value.get().strip()


# ================== ГЛАВНОЕ ОКНО — КОМПАКТНОЕ, ТЁМНОЕ ==================
class KangarooGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 EtarKangaroo")
        self.root.geometry("680x520")
        self.root.config(bg="#1e1e1e")
        self.root.resizable(False, True)

        self.setup_ui()
        self.log("Готов. Нажмите 'Запустить'.")

    def setup_ui(self):
        # Заголовок
        tk.Label(
            self.root,
            text="🔑 EtarKangaroo — GPU Bitcoin Scanner",
            font=("Arial", 12, "bold"),
            bg="#1e1e1e", fg="#00a86b"
        ).pack(pady=(10, 5))

        # === ИНФО ПАНЕЛЬ ===
        info_frame = tk.LabelFrame(
            self.root,
            text="  ℹ️ Информация  ",
            font=("Arial", 9, "bold"),
            bg="#1e1e1e", fg="white",
            bd=2, relief="solid",
            highlightthickness=0
        )
        info_frame.pack(padx=15, pady=6, fill="x")
        info_frame.config(highlightbackground="#333", highlightcolor="#333")

        self.addr_label = tk.Label(
            info_frame,
            text=f"Адрес: {target_address[:35]}...",
            font=("Arial", 9),
            bg="#1e1e1e", fg="#e0e0e0"
        )
        self.addr_label.pack(anchor="w", padx=5, pady=1)

        self.gpu_label = tk.Label(
            info_frame,
            text="GPU: —",
            font=("Arial", 9),
            bg="#1e1e1e", fg="#ccc"
        )
        self.gpu_label.pack(anchor="w", padx=5, pady=1)

        self.status_label = tk.Label(
            info_frame,
            text="⚪ Ожидание",
            font=("Arial", 9, "bold"),
            bg="#1e1e1e", fg="orange"
        )
        self.status_label.pack(anchor="w", padx=5, pady=(1, 4))

        # === ЛОГ ===
        log_frame = tk.LabelFrame(
            self.root,
            text="  📄 Лог процесса  ",
            font=("Arial", 9, "bold"),
            bg="#1e1e1e", fg="white",
            bd=2, relief="solid"
        )
        log_frame.pack(padx=15, pady=6, fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=14,
            font=("Consolas", 9),
            bg="#252525",
            fg="#e0e0e0",
            insertbackground="white",
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0
        )
        self.log_text.pack(fill="both", expand=True, padx=3, pady=3)

        # === КНОПКИ ===
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=8)

        self.start_btn = tk.Button(
            btn_frame, text="▶ Запустить", width=12, font=("Arial", 9, "bold"),
            bg="#00a86b", fg="white", command=self.start_scan
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(
            btn_frame, text="⏹ Остановить", width=12, font=("Arial", 9, "bold"),
            bg="#d9534f", fg="white", state="disabled", command=self.stop_scan
        )
        self.stop_btn.pack(side="left", padx=5)

        self.clear_btn = tk.Button(
            btn_frame, text="🗑 Очистить", width=10, font=("Arial", 9),
            bg="#555", fg="white", command=self.clear_log
        )
        self.clear_btn.pack(side="left", padx=5)

        # === Служебные ===
        self.proc = None
        self.scanning = False
        self.session_id = 1
        self.gpu_ids = None
        self.grid = None

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')


    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="🟢 Сканирование", fg="lightgreen")

        def run():
            try:
                gpus = get_gpu_list()
                if not gpus:
                    self.log("[⚠️] nvidia-smi недоступен.")
                    self.gpu_ids = input_dialog(self.root, "Введите ID GPU (например: 0,1):")
                else:
                    self.log("Открывается окно выбора GPU...")
                    self.gpu_ids = gpu_selection_dialog(self.root, gpus)

                if not self.gpu_ids:
                    self.log("[❌] GPU не выбраны.")
                    self.finish()
                    return

                self.gpu_label.config(text=f"GPU: {self.gpu_ids}")
                self.log(f"✅ Выбраны GPU: {self.gpu_ids}")

                first_gpu_name = gpus[0][1] if gpus and gpus[0][0] in self.gpu_ids else "unknown"
                self.grid = get_grid_for_gpu(first_gpu_name)
                self.log(f"🔧 Grid: {self.grid} (под {first_gpu_name})")

                derived = pubkey_to_p2pkh_address(pubkey_hex)
                if not derived or derived != target_address:
                    self.log(f"[❌] Адрес не совпадает: {derived}")
                    self.finish()
                    return
                else:
                    self.log("[✅] Публичный ключ валиден")

                rb, re = hex_to_int(rb_hex), hex_to_int(re_hex)
                if rb >= re:
                    self.log("[❌] Неверный диапазон")
                    self.finish()
                    return
                self.log(f"📊 Диапазон: ...{rb_hex[-12:]} → ...{re_hex[-12:]}")

                sid = 1
                while self.scanning:
                    s, e = random_subrange(rb, re, SUBRANGE_BITS)
                    rb_s, re_s = int_to_hex(s), int_to_hex(e)
                    self.log(f"📌 Сеанс #{sid}: ...{rb_s[-10:]} → ...{re_s[-10:]}")

                    res_file = f"{TEMP_DIR}result_{sid}.txt"
                    cmd = [
                        ETARKANGAROO_EXE, "-dp", str(DP), "-d", self.gpu_ids,
                        "-grid", self.grid, "-rb", rb_s, "-re", re_s,
                        "-pub", pubkey_hex, "-o", res_file,
                        "-kf", f"{TEMP_DIR}kang_{sid}.dat",
                        "-wf", f"{TEMP_DIR}ht_{sid}.dat",
                        "-wi", str(SCAN_DURATION), "-wsplit", "-wmerge"
                    ]

                    try:
                        self.proc = subprocess.Popen(
                            cmd,
                            cwd=".",
                            creationflags=subprocess.CREATE_NEW_CONSOLE
                        )
                        for _ in range(SCAN_DURATION):
                            if not self.scanning:
                                break
                            time.sleep(1)

                        self.log("⏹ Остановка...")
                        self.proc.terminate()
                        self.proc.wait(timeout=10)
                    except:
                        self.proc.kill()

                    if os.path.exists(res_file):
                        with open(res_file, "r") as f:
                            content = f.read().strip()
                        if content:
                            self.log(f"🎉 🔑 КЛЮЧ НАЙДЕН! → {res_file}")
                            self.root.bell()
                            self.scanning = False
                    else:
                        self.log("❌ Результат не создан")

                    sid += 1
                    time.sleep(2)

                self.finish()
            except Exception as e:
                self.log(f"[❌] Ошибка: {e}")
                self.finish()

        threading.Thread(target=run, daemon=True).start()

    def stop_scan(self):
        self.scanning = False
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except:
                self.proc.kill()
        self.log("🛑 Остановлено вручную")

    def finish(self):
        self.scanning = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="🔴 Остановлено", fg="red")


# ================== ЗАПУСК ==================
if __name__ == "__main__":
    root = tk.Tk()
    app = KangarooGUI(root)
    root.mainloop()