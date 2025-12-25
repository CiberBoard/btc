

# 🦘 Bitcoin GPU/CPU/Kangaroo Scanner  
**v5.1 — The Ultimate Private Key Search Suite**

<div align="center">

[![Version](https://img.shields.io/badge/version-5.0-blue.svg)](https://github.com/Jasst/BTCScanner)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://github.com/Jasst/BTCScanner)
[![Python](https://img.shields.io/badge/python-3.7--3.11-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-As--Is-red.svg)](LICENSE)
[![Kangaroo](https://img.shields.io/badge/algorithm-Pollard's_Kangaroo-orange.svg)](https://en.wikipedia.org/wiki/Pollard%27s_kangaroo_algorithm)

> **💡 Now with Kangaroo (Pollard’s Kangaroo Algorithm)** — *the most efficient method for narrow-range key discovery*.

</div>

## 📋 Overview

**BSG 5.1** is a professional-grade, all-in-one Bitcoin private key scanner supporting **three complementary search strategies**:

| 🔍 Method | Best For | Speed (RTX 3060) | Efficiency |
|----------|----------|------------------|------------|
| **🚀 GPU** (`cuBitcrack.exe`) | Wide ranges (> 2⁴⁸ keys) | ~1–2 GKeys/s | Linear brute-force |
| **🧠 CPU** (`coincurve`) | Targeted, small ranges | ~50–200 KKeys/s | Flexible & precise |
| **🦘 Kangaroo** (`Etarkangaroo.exe`) | **Narrow suspicious ranges (2³²–2⁴⁸)** | ~1–1.5 GKeys/s **+ near-100% find probability** | **✅ Best for puzzle/recovery scenarios** |

> ✅ **Perfect for Bitcoin puzzle transactions** (e.g., #66, #120), wallet recovery, and research.



## ✨ Key Features (v5.1)

### 🦘 **Kangaroo Integration — NEW!**
- Fully integrated **Pollard’s Kangaroo** algorithm via `Etarkangaroo.exe`
- **Automatic random sub-range generation** inside your global range
- Real-time monitoring: session #, speed, *exact* current range
- Smart parsing of results (hex/decimal → 64-char hex)
- Full parameter control: `DP`, `Grid`, duration, subrange bits

### 💾 **Smart Settings Management**
All Kangaroo/GPU/CPU settings are auto-saved & restored in `settings.json`:
```json
{
  "kang_pubkey": "02145d2611c823a396ef6712ce0f712f09b9b4f3135e3e0aa3230fb9b6d08d1e16",
  "kang_start_key": "1",
  "kang_end_key": "FFFFFFFFFFFFFFFF",
  "kang_dp": 20,
  "kang_grid": "256x256",
  "kang_duration": 300,
  "kang_subrange_bits": 32,
  "kang_exe_path": "C:/.../Etarkangaroo.exe",
  "kang_temp_dir": "C:/.../kangaroo_temp"
}
```

### 📊 **Enhanced UI & Diagnostics**
- **✅ Fixed "Current Range" display** — now shows **beginning + end** of hex keys:
  ```
  rb = 0x489b17c1…e7822c9f
  re = 0x489b17c1…e7822c9f
  ```
- Tooltip with full range & width: `Δ = 0x1000000000000 = 281,474,976,710,656 keys`
- Monospace font (`Courier New`) for precise hex alignment
- GPU hardware monitoring (utilization, memory, temperature)
- CPU temperature & load tracking

### 🧰 **Robust Build & Deployment**
- **PyInstaller-ready** — `main.spec` includes `cuBitcrack.exe` & `Etarkangaroo.exe`
- UPX-disabled (prevents CUDA compatibility issues)
- Icon, logging, temp cleanup — all work in single `.exe`

### 🛡️ **Reliability & Safety**
- Graceful stop/restart (no orphaned processes)
- Input validation & error recovery
- Traceback logging for critical failures
- File existence checks before launch

---

## 📋 System Requirements

| Component | Requirement |
|----------|-------------|
| **OS** | Windows 10/11 (primary), Linux/macOS (experimental) |
| **GPU** | NVIDIA with CUDA support (for GPU & Kangaroo modes) |
| **RAM** | ≥ 4 GB |
| **Storage** | ≥ 1 GB free (includes temp files for Kangaroo) |
| **Python** | 3.7 – 3.11 (recommended: 3.9–3.11) |

> ⚠️ **Etarkangaroo.exe is a third-party binary**. Verify its integrity before use.

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/Jasst/BTCScanner.git
cd BTCScanner
python -m venv venv
venv\Scripts\activate  # Windows
# venv/bin/activate   # Linux/macOS
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install PyQt5 psutil coincurve pywin32 pynvml
```

### 3. Get Binaries
| Tool | Source | Place in |
|------|--------|----------|
| `cuBitcrack.exe` | [brichard19/BitCrack](https://github.com/brichard19/BitCrack/releases) | Project root |
| `Etarkangaroo.exe` | *(Community build required)* | Project root |

> 🔧 Ensure NVIDIA drivers & CUDA are up to date.

### 4. Run
```bash
  python main.py
```

---

## 🧪 Kangaroo Usage Guide

1. **Identify a narrow suspicious range**  
   Example: `start = 0x70E4B9B06430023105`, `end = 0x70E4B9B16720023105` (width = 2⁴⁸)

2. **Configure parameters**
   - `subrange_bits = 32` → 4.3B keys/session (~3–5 min/GPU)
   - `DP = 20`, `grid = 256x256`, `duration = 300`

3. **Launch**  
   → Kangaroo will auto-generate non-overlapping random sub-ranges  
   → Stops when key is found or manually stopped

> 💡 **Pro Tip**: Smaller `subrange_bits` = faster sessions, more coverage over time.

---

## 📁 Project Structure

```
BTCScanner/
├── 📄 main.py                    # Entry point
├── ⚙️ config.py                 # Global constants
├── 🔧 cuBitcrack.exe            # GPU scanner
├── 🔧 Etarkangaroo.exe          # Kangaroo solver ← NEW
├── 📁 kangaroo_temp/            # Kangaroo temporary files
├── 💾 Found_key_CUDA.txt        # Key discoveries
├── ⚙️ settings.json             # Auto-saved preferences
│
├── 📁 core/
│   ├── 📄 gpu_scanner.py
│   ├── 📄 cpu_scanner.py
│   └── 📄 kangaroo_worker.py   ← NEW
│
├── 📁 ui/
│   ├── 📄 gpu_logic.py
│   ├── 📄 cpu_logic.py
│   └── 📄 kangaroo_logic.py    ← NEW
│
├── 📁 utils/                    # Helpers, hex→WIF, validators
├── 📁 logger/                   # logging.conf
└── 📄 README.md                 # 
```

---

## ⚙️ Configuration Reference

### Kangaroo Parameters

| Parameter | Description | Recommended |
|----------|-------------|-------------|
| `DP` | Distinguished Points (memory vs speed) | 16–24 |
| `Grid` | GPU occupancy (H×W) | `256x256` |
| `Duration` | Seconds per session | 300 |
| `Subrange Bits` | `2^N` keys/session | 30–34 |
| `Temp Dir` | For `result_*.txt` | `kangaroo_temp/` |

### GPU Parameters

| Parameter | Description | Default |
|----------|-------------|---------|
| Workers/Device | Instances per GPU | `1` |
| Blocks | CUDA blocks | Auto / `512` |
| Threads | Per block | Auto / `512` |
| Points | Per thread | Auto / `512` |

---

## 🐛 Troubleshooting

| Issue | Solution                                                                            |
|------|-------------------------------------------------------------------------------------|
| `Etarkangaroo.exe not found` | Use **«Обзор…»** button; check antivirus quarantine                                 |
| `Current range shows "0000…"` | ✔️ **Fixed in v5.1** — now shows meaningful prefixes/suffixes                       |
| Kangaroo stops early | Increase `subrange_bits` or `duration`; ensure range ≥ 2³²                          |
| CUDA errors | Update drivers; reduce workers; check VRAM usage                                    |
| No key found (but should be) | Kangaroo only covers part of wide ranges — reduce `subrange_bits` for more sessions |

> 📝 All logs go to `logs/app.log` and **Log** tab.

---

## ⚠️ Legal Disclaimer

> This software is provided **“as-is”** without warranty.  
> - Use **only on addresses you own or have explicit permission to test**.  
> - Kangaroo uses third-party `Etarkangaroo.exe` — **verify hashes**.  
> - The author **disclaims all liability** for misuse, data loss, or legal consequences.

---

## 🤝 Contributing

Contributions welcome!  
- ✅ Bug reports & feature requests → [Issues](https://github.com/CiberBoard/btc/issues)  
- ✅ Pull requests → fork & PR  
- ✅ Documentation fixes → edit this `README.md`

---

## 📞 Contact

- **GitHub**: [@Jasst](https://github.com/Jasst)  
- **Issues**: [Report here](https://github.com/CiberBoard/btc/issues)

---

<div align="center">

**BSG 5.1 — From brute-force to targeted recovery.**  
Made with ❤️ by [Jasst](https://github.com/Jasst) • (https://github.com/CiberBoard/btc)

</div>
```

---



