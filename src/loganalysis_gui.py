import sys
from PyQt5.QtWidgets import QApplication
from loganalysis_gui.main_window import LogAnalysisMainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("loganalysis")
    app.setDesktopFileName("loganalysis")
    window = LogAnalysisMainWindow()
    window.show()
    sys.exit(app.exec_())
