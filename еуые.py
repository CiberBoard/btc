# test_import_chain.py
import sys
import multiprocessing

if sys.platform == 'win32':
    multiprocessing.set_start_method('spawn', force=True)

print("[1] Setting spawn method... OK")

print("[2] Importing PyQt6...")
from PyQt6.QtWidgets import QApplication

print("[2] OK")

print("[3] Creating QApplication...")
app = QApplication(sys.argv)
print("[3] OK")

print("[4] Importing main_window (с матрицей)...")
try:
    from ui.main_window import BitcoinGPUCPUScanner

    print("[4] OK — импорт успешен")

    print("[5] Creating window...")
    window = BitcoinGPUCPUScanner()
    print("[5] OK — окно создано")

    print("[6] Testing matrix_logic property...")
    logic = window.matrix_logic
    print("[6] OK — логика инициализирована")

    print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")

except Exception as e:
    print(f"\n❌ ПАДЕНИЕ: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("\n🎉 Приложение должно работать!")
sys.exit(0)