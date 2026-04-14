# test_numpy_qt.py
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QCoreApplication
import sys

print(f"NumPy version: {np.__version__}")

class TestWorker(QThread):
    result = pyqtSignal(str)
    def run(self):
        # Тест операции с большими числами
        arr = np.array([200.0, 201.0, 202.0], dtype=np.float64)
        mean = np.mean(arr)
        # Безопасная конвертация
        val = int(2.0 ** mean) if mean < 200 else (1 << 256) - 1
        self.result.emit(f"OK: {val}")

app = QCoreApplication(sys.argv)
worker = TestWorker()
worker.result.connect(lambda r: print(r) or app.quit())
worker.start()
sys.exit(app.exec())