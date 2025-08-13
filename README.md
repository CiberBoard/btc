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
- Automatic parameter optimization (blocks, threads, points)
- Custom configuration for experienced users
- NVIDIA CUDA acceleration

### 🎯 **Flexible Search Strategies**

- **Sequential Mode**: Systematic key space exploration
- **Random Mode**: Probabilistic search with unique range generation
- Configurable search ranges and intervals

### 🛠️ **System Optimization**

- Process priority management (Windows)
- Resource usage monitoring
- Automatic performance tuning

### 📊 **Real-Time Analytics**

- Speed monitoring (keys/sec)
- Progress tracking with ETA
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
- cuBitcrack.exe (included separately)

## 🚀 Installation

### **Step 1: Download Project**

```bash
git clone https://github.com/Jasst/bitcoin-scanner.git
cd bitcoin-scanner
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

# Windows process management (optional)
pip install pywin32
```

### **Step 4: cuBitcrack Setup**

1. Download `cuBitcrack.exe` from the [official repository](https://github.com/brichard19/cuBitcrack)
1. Place the executable in the project root directory
1. Ensure CUDA drivers are installed and up to date

## 🎮 Usage Guide

### **Application Launch**

```bash
# Ensure virtual environment is active
python main.py
```

### **GPU Search Configuration**

1. **Basic Setup**
- Enter target Bitcoin address (1xxx or 3xxx format)
- Specify search range in hexadecimal format
- Select GPU device(s) from dropdown
1. **Performance Optimization**
- Enable “Auto-optimization” for automatic tuning
- Manual configuration: adjust blocks, threads, points
- Set process priority for resource management
1. **Advanced Options**
- Random search mode with configurable sub-ranges
- Restart intervals for continuous operation
- Unique range generation to prevent overlap

### **CPU Search Configuration**

1. **Search Parameters**
- Target Bitcoin address input
- Hexadecimal range specification
- Mode selection (Sequential/Random)
1. **Performance Tuning**
- Worker count (recommended: CPU cores - 1)
- Attempt count for random mode
- Process priority adjustment
1. **Execution Control**
- Start: `Ctrl+S`
- Stop: `Ctrl+Q`

### **Monitoring & Results**

- **Statistics Tab**: Real-time performance metrics
- **Logs Tab**: Detailed operation logging
- **Found Keys Tab**: Discovery results with export options
- **Progress Tracking**: ETA calculations and completion status

## 📁 Project Structure

```
BTCScanner/
│
├── 📄 main.py                    # Application entry point
├── ⚙️ config.py                 # Global configuration
├── 🔧 cuBitcrack.exe            # GPU scanning executable
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
│   ├── 📄 gpu_scanner.py        # GPU search engine
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

|Parameter|Description      |Default|Range  |
|---------|-----------------|-------|-------|
|Blocks   |CUDA blocks      |Auto   |1-65535|
|Threads  |Threads per block|Auto   |1-1024 |
|Points   |Points per thread|Auto   |1-2^20 |

### **CPU Parameters**

|Parameter|Description      |Recommended  |
|---------|-----------------|-------------|
|Workers  |Process count    |CPU cores - 1|
|Attempts |Random iterations|1000000+     |
|Priority |Process priority |Normal       |

## 🐛 Troubleshooting

### **Common Issues**

**cuBitcrack.exe not found**

- Ensure the executable is in the project root
- Check file permissions and antivirus exclusions

**CUDA errors**

- Update NVIDIA drivers
- Verify GPU compatibility
- Check available VRAM

**Python dependency errors**

- Verify Python version (3.7-3.11)
- Reinstall dependencies in virtual environment
- Check for conflicting packages

**Performance issues**

- Enable auto-optimization
- Adjust worker count
- Monitor system resources

### **Logging**

All application events are logged to:

- Console output (real-time)
- `logs/app.log` (persistent)
- Found keys: `Found_key_CUDA.txt`

## ⚠️ Legal Disclaimer

This software is provided “as-is” without any warranties or guarantees. Users assume all responsibility and risk associated with its use. The software is intended for educational and research purposes only.

**Important Notice**:

- Only scan addresses you own or have explicit permission to test
- Respect applicable laws and regulations in your jurisdiction
- The author disclaims all liability for misuse or illegal activities

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### **Development Setup**

```bash
git clone https://github.com/Jasst/bitcoin-scanner.git
cd bitcoin-scanner
pip install -r requirements.txt
```

## 📞 Support & Contact

- **GitHub**: [@Jasst](https://github.com/Jasst)
- **Issues**: [Report bugs or request features](https://github.com/Jasst/bitcoin-scanner/issues)

## 📜 Version History

### **v5.0 - Enhanced Edition**

- Dual-mode GPU/CPU support
- Auto-optimization features
- Modern dark UI theme
- Comprehensive logging system
- Multi-GPU support
- Advanced statistics tracking

-----

<div align="center">

**Bitcoin GPU/CPU Scanner** - Professional Bitcoin Key Discovery Tool

Made with ❤️ by [Jasst](https://github.com/Jasst)

</div>