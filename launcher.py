import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Import the main functions from the other scripts.
# This helps PyInstaller detect them as dependencies.
try:
    from mainwindow import main as soosl_main
except ImportError:
    soosl_main = None

try:
    from batch_importer import main as batch_importer_main
except ImportError:
    batch_importer_main = None

try:
    from backwards_compatibility import main as backwards_compatibility_main
except ImportError:
    backwards_compatibility_main = None


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SooSL Launcher")
        self.setGeometry(300, 300, 300, 200)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("SooSL Application Launcher")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        soosl_button = QPushButton("Launch SooSL Dictionary Tool")
        soosl_button.setToolTip("The main application for creating and managing sign language dictionaries.")
        soosl_button.clicked.connect(lambda: self.launch_app("--run-soosl"))
        layout.addWidget(soosl_button)

        importer_button = QPushButton("Launch Batch Importer")
        importer_button.setToolTip("A tool for importing multiple media files into a project at once.")
        importer_button.clicked.connect(lambda: self.launch_app("--run-importer"))
        layout.addWidget(importer_button)

        converter_button = QPushButton("Launch Legacy Converter")
        converter_button.setToolTip("A tool to convert older SooSL project formats to the current version.")
        converter_button.clicked.connect(lambda: self.launch_app("--run-converter"))
        layout.addWidget(converter_button)

        self.setLayout(layout)
        self.setFixedSize(self.sizeHint())

    def launch_app(self, arg):
        try:
            # Use sys.executable to run the bundled app with a specific command-line argument.
            # This launches a new process.
            subprocess.Popen([sys.executable, arg])
        except Exception as e:
            error_msg = f"Failed to launch application with argument {arg}:\n{e}"
            # You would typically use a QMessageBox here in a real app
            print(error_msg)


def main_launcher():
    app = QApplication(sys.argv)
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec_())


def main():
    # This is the main entry point for the PyInstaller bundle.
    if '--run-soosl' in sys.argv:
        if soosl_main:
            soosl_main()
        else:
            print("Error: SooSL application entry point not found.")
            sys.exit(1)
    elif '--run-importer' in sys.argv:
        if batch_importer_main:
            batch_importer_main()
        else:
            print("Error: Batch Importer application entry point not found.")
            sys.exit(1)
    elif '--run-converter' in sys.argv:
        if backwards_compatibility_main:
            backwards_compatibility_main()
        else:
            print("Error: Legacy Converter application entry point not found.")
            sys.exit(1)
    else:
        # If no specific argument is passed, run the launcher UI.
        main_launcher()


if __name__ == "__main__":
    main()
