# Bitcoin GPU/CPU Scanner

<div align="center">

![Version](https://img.shields.io/badge/version-5.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.7--3.11-green.svg)
![License](https://img.shields.io/badge/license-As--Is-red.svg)

*Advanced Bitcoin private key scanner with GPU and CPU support*

</div>

## 📋 Overview

Bitcoin GPU/CPU Scanner is a professional-grade application designed to search for Bitcoin private keys that correspond to specified addresses. The application features dual-mode operation with comprehensive configuration options and real-time monitoring capabilities.

## ✨ Key Features

### 🚀 **Dual-Mode Operation**

- **GPU Mode**: High-performance scanning using NVIDIA CUDA via `cuBitcrack.exe`
- **CPU Mode**: Multi-threaded scanning using `coincurve` library with multiprocessing

### ⚡ **Advanced GPU Support**

- Multi-GPU support with device selection
- Multiple **workers (instances) per GPU device** for increased throughput
- Automatic parameter optimization (blocks, threads, points)
- Custom configuration for experienced users
- NVIDIA CUDA acceleration

### 🎯 **Flexible Search Strategies**

- **Sequential Mode**: Systematic key space exploration with **automatic range splitting** for multiple workers
- **Random Mode**: Probabilistic search with unique range generation and optional auto-restart
- Configurable search ranges and intervals

### 🛠️ **System Optimization**

- Process priority management (Windows)
- Real-time GPU hardware monitoring (utilization, memory, temperature)
- Resource usage monitoring
- Automatic performance tuning

### 📊 **Real-Time Analytics**

- Aggregated speed monitoring (keys/sec) from all workers
- Progress tracking with ETA (for sequential mode)
- Comprehensive statistics dashboard
- Live logging with file output

### 💾 **Data Management**

- Automatic key discovery logging
- CSV export functionality
- Settings persistence
- Search history tracking

### 🎨 **Modern Interface**

- Dark-themed PyQt5 interface
- Tabbed navigation
- Real-time status updates
- Keyboard shortcuts

## 📋 System Requirements

### **Operating System**

- Windows 10/11 (Primary support)
- Linux/macOS (Limited compatibility)

### **Hardware**

- **GPU Mode**: NVIDIA GPU with CUDA support
- **CPU Mode**: Multi-core processor recommended
- Minimum 4GB RAM
- 1GB free disk space

### **Software Dependencies**

- Python 3.7 - 3.11 (Recommended: 3.9-3.11)
- NVIDIA CUDA Toolkit (for GPU mode)
- `cuBitcrack.exe` (included separately or downloaded)

## 🚀 Installation

### **Step 1: Download Project**

```bash
git clone https://github.com/Jasst/BTCScanner.git
cd BTCScanner
```

### **Step 2: Python Environment Setup**

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### **Step 3: Install Dependencies**

```bash
# Upgrade pip
pip install --upgrade pip

# Core dependencies
pip install PyQt5 psutil

# CPU scanning support
pip install coincurve

# Windows process management (optional but recommended for priority control)
pip install pywin32

# GPU Monitoring (optional, for hardware stats)
pip install pynvml
```

### **Step 4: cuBitcrack Setup**

1. Download `cuBitcrack.exe` (e.g., from [https://github.com/brichard19/BitCrack](https://github.com/brichard19/BitCrack) or a similar source).
2. Place the executable in the project root directory (next to `main.py`).
3. Ensure NVIDIA CUDA drivers are installed and up to date.

## 🎮 Usage Guide

### **Application Launch**

```bash
# Ensure virtual environment is active
python main.py
```

### **GPU Search Configuration**

1.  **Basic Setup**
    -   Enter target Bitcoin address (1xxx or 3xxx format).
    -   Specify the overall search range in hexadecimal format.
    -   Select GPU device(s) from the dropdown (e.g., `0`, `0,1`).
2.  **Worker Configuration**
    -   Use the **"Воркеры/устройство"** spin box to specify how many `cuBitcrack.exe` instances to run on *each* selected GPU.
    -   The application will **automatically split the total range** among all launched workers for efficient, non-overlapping search in sequential mode.
3.  **Performance Optimization**
    -   Enable “Авто-оптимизация” for automatic tuning of blocks, threads, and points.
    -   Manual configuration: adjust blocks, threads, points.
    -   Set process priority for resource management.
4.  **Advanced Options**
    -   **Random search mode**: Generates a unique random sub-range for each run. The generated range is then split among workers.
    -   Configure restart intervals for continuous random scanning.
    -   Set minimum and maximum size for random sub-ranges.

### **CPU Search Configuration**

1.  **Search Parameters**
    -   Target Bitcoin address input.
    -   Hexadecimal range specification.
    -   Mode selection (Sequential/Random).
2.  **Performance Tuning**
    -   Worker count (recommended: CPU cores - 1).
    -   Attempt count for random mode.
    -   Process priority adjustment.
3.  **Execution Control**
    -   Start: `Ctrl+S`
    -   Stop: `Ctrl+Q`

### **Monitoring & Results**

-   **Statistics Tab**: Real-time performance metrics (aggregated for GPU).
-   **Logs Tab**: Detailed operation logging.
-   **Found Keys Tab**: Discovery results with export options (CSV).
-   **Progress Tracking**: ETA calculations and completion status (for sequential GPU/CPU).

## 📁 Project Structure

```
BTCScanner/
│
├── 📄 main.py                    # Application entry point
├── ⚙️ config.py                 # Global configuration
├── 🔧 cuBitcrack.exe            # GPU scanning executable (place here)
├── 💾 Found_key_CUDA.txt        # Key discovery log
├── 🔧 settings.json             # User preferences
│
├── 📁 logs/                     # Application logs
│   └── 📄 app.log
│
├── 📁 ui/                       # User interface module
│   ├── 📄 __init__.py
│   └── 📄 main_window.py        # Main UI logic
│
├── 📁 core/                     # Core functionality
│   ├── 📄 __init__.py
│   ├── 📄 gpu_scanner.py        # GPU search engine & process management
│   └── 📄 cpu_scanner.py        # CPU search engine
│
├── 📁 utils/                    # Utility functions
│   ├── 📄 __init__.py
│   └── 📄 helpers.py            # Helper functions
│
└── 📄 README.md                 # Documentation
```

## 🔧 Configuration Options

### **GPU Parameters**

| Parameter | Description         | Default | Range   |
| :-------- | :------------------ | :------ | :------ |
| Blocks    | CUDA blocks         | Auto    | 1-65535 |
| Threads   | Threads per block   | Auto    | 1-1024  |
| Points    | Points per thread   | Auto    | 1-2^20  |
| Workers/Device | Instances per GPU | 1       | 1-16    |

### **CPU Parameters**

| Parameter | Description         | Recommended     |
| :-------- | :------------------ | :-------------- |
| Workers   | Process count       | CPU cores - 1   |
| Attempts  | Random iterations   | 1000000+        |
| Priority  | Process priority    | Normal          |

## 🐛 Troubleshooting

### **Common Issues**

**cuBitcrack.exe not found**

- Ensure the executable is named `cuBitcrack.exe` and is in the project root directory.
- Check file permissions and antivirus exclusions.

**CUDA errors**

- Update NVIDIA drivers.
- Verify GPU compatibility with CUDA.
- Check available VRAM (especially with multiple workers).

**Python dependency errors**

- Verify Python version (3.7-3.11).
- Reinstall dependencies in a clean virtual environment.
- Check for conflicting packages.

**Performance issues**

- Enable auto-optimization.
- Adjust worker count per GPU.
- Monitor system resources (GPU Utilization, Memory).
- Ensure no other heavy GPU tasks are running.

**Only one worker starts even if more are requested**

- Check the application log (`logs/app.log` or the Log tab) for errors during worker startup.
- Ensure the total key range is large enough to be split among the requested number of workers.

### **Logging**

All application events are logged to:

- Console output (real-time)
- `logs/app.log` (persistent)
- Found keys: `Found_key_CUDA.txt`

## ⚠️ Legal Disclaimer

This software is provided “as-is” without any warranties or guarantees. Users assume all responsibility and risk associated with its use. The software is intended for educational and research purposes only.

**Important Notice**:

- Only scan addresses you own or have explicit permission to test.
- Respect applicable laws and regulations in your jurisdiction.
- The author disclaims all liability for misuse or illegal activities.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### **Development Setup**

```bash
git clone https://github.com/Jasst/BTCScanner.git
cd BTCScanner
pip install -r requirements.txt # (Create this file based on the pip install commands above)
```

## 📞 Support & Contact

- **GitHub**: [@Jasst](https://github.com/Jasst)
- **Issues**: [Report bugs or request features](https://github.com/Jasst/BTCScanner/issues)

## 📜 Version History

### **v5.0 - Enhanced Edition**

- Dual-mode GPU/CPU support
- Multi-worker per GPU device capability
- Auto-optimization features
- Automatic range splitting for GPU workers
- Aggregated GPU statistics
- Modern dark UI theme
- Comprehensive logging system
- Multi-GPU support
- Advanced statistics tracking
- Real-time GPU hardware monitoring

-----

<div align="center">

**Bitcoin GPU/CPU Scanner** - Professional Bitcoin Key Discovery Tool

Made with ❤️ by [Jasst](https://github.com/Jasst)

</div>
```

---
