import os
os.environ["MPLBACKEND"] = "Agg"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from PyQt6.QtCore import QThread, pyqtSignal
import sys

class TestThread(QThread):
    finished = pyqtSignal()

    def run(self):
        print("🔹 Thread started")
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        print("🔹 Matplotlib imported successfully")
        plt.figure()
        plt.plot([1, 2, 3])
        plt.savefig("test.png")
        plt.close('all')
        print("🔹 Plot saved")
        self.finished.emit()

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    t = TestThread()
    t.finished.connect(lambda: print("✅ Test passed") or app.quit())
    t.start()
    sys.exit(app.exec())