import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QMessageBox

class LauncherApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SooSL Launcher')
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.batch_importer_button = QPushButton('Batch Importer')
        self.batch_importer_button.clicked.connect(self.launch_batch_importer)
        layout.addWidget(self.batch_importer_button)

        self.backwards_compatibility_button = QPushButton('Backwards Compatibility Tool')
        self.backwards_compatibility_button.clicked.connect(self.launch_backwards_compatibility)
        layout.addWidget(self.backwards_compatibility_button)

        self.main_app_button = QPushButton('Main SooSL App')
        self.main_app_button.clicked.connect(self.launch_main_app)
        layout.addWidget(self.main_app_button)

        self.setLayout(layout)

    def launch_script(self, script_name):
        try:
            # We use Popen to launch the script in a new process
            subprocess.Popen([sys.executable, script_name])
        except FileNotFoundError:
            QMessageBox.critical(self, 'Error', f"Could not find '{script_name}'. Make sure it's in the same directory as the launcher.")
        except Exception as e:
            QMessageBox.critical(self, 'Error', f"An unexpected error occurred: {e}")

    def launch_batch_importer(self):
        self.launch_script('batch_importer.py')

    def launch_backwards_compatibility(self):
        self.launch_script('backwards_compatibility.py')

    def launch_main_app(self):
        self.launch_script('soosl.py')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LauncherApp()
    ex.show()
    sys.exit(app.exec_())
