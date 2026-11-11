import sys
import ui.main_window as mw
import ui.ui_main as uim
from PyQt6.QtWidgets import QApplication, QWidget

# Заглушка setup_ui — только пустое окно
_orig_setup = uim.MainWindowUI.setup_ui
def _empty_setup(self):
    self.parent.resize(1200, 800)
    self.parent.setCentralWidget(QWidget())
    self.parent.main_tabs = None
uim.MainWindowUI.setup_ui = _empty_setup
mw.apply_frameless = lambda *a, **k: None

app = QApplication(sys.argv)
window = mw.BitcoinGPUCPUScanner()
window.show()
print("TEST G: shown OK", flush=True)
sys.exit(app.exec())