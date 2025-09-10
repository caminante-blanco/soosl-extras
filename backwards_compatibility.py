import sys
import os
import json
import shutil
import time
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QLabel,
    QTextEdit,
    QMessageBox,
    QFormLayout,
)
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
from PyQt5.QtCore import Qt

# --- Core Conversion Logic (from our previous script) ---
# We'll wrap this logic in a QObject to run on a separate thread


class ConversionWorker(QObject):
    """
    Worker thread to handle the file conversion process, preventing the GUI from freezing.
    """

    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, src_dir, dest_parent_dir, target_version):
        super().__init__()
        self.src_dir = src_dir
        self.dest_parent_dir = dest_parent_dir
        self.target_version = target_version
        self.is_running = True

    def stop(self):
        self.is_running = False

    def find_main_json_file(self, directory):
        """Scans a directory for a .json file containing the 'projectId' key."""
        for item in os.listdir(directory):
            if not self.is_running:
                return None, None
            if item.lower().endswith(".json"):
                file_path = os.path.join(directory, item)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "projectId" in data and "sooslVersion" in data:
                            return item, data.get("projectId")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        return None, None

    def run(self):
        """The main conversion logic that will be executed in the thread."""
        try:
            self.progress_signal.emit(
                f"Scanning source: {os.path.abspath(self.src_dir)}"
            )

            main_json_filename, project_id = self.find_main_json_file(self.src_dir)

            if not main_json_filename or not project_id:
                raise ValueError(
                    "Could not find a valid main dictionary file in the source directory."
                )

            self.progress_signal.emit(f"  -> Found main file: '{main_json_filename}'")
            self.progress_signal.emit(f"  -> Project ID: '{project_id}'")

            dest_project_dir = os.path.join(self.dest_parent_dir, project_id)

            if os.path.exists(dest_project_dir):
                raise FileExistsError(
                    f"Destination project directory '{dest_project_dir}' already exists."
                )

            self.progress_signal.emit(
                f"Creating destination project at: {os.path.abspath(dest_project_dir)}"
            )
            os.makedirs(dest_project_dir)

            for src_root, dirs, files in os.walk(self.src_dir):
                if not self.is_running:
                    self.progress_signal.emit("\nConversion cancelled by user.")
                    self.finished_signal.emit(False, "Cancelled")
                    return

                dest_root = src_root.replace(self.src_dir, dest_project_dir, 1)
                if not os.path.exists(dest_root):
                    os.makedirs(dest_root)

                for filename in files:
                    src_path = os.path.join(src_root, filename)
                    dest_filename = (
                        f"{project_id}.json"
                        if filename == main_json_filename
                        else filename
                    )
                    dest_path = os.path.join(dest_root, dest_filename)

                    if filename.lower().endswith(".json"):
                        self.progress_signal.emit(f"Converting: {filename}")
                        with open(src_path, "r", encoding="utf-8") as f_in:
                            data = json.load(f_in)

                        if filename == main_json_filename:
                            data["sooslVersion"] = self.target_version
                            data["minSooSLVersion"] = self.target_version
                            if "projectCreator" in data:
                                self.progress_signal.emit(
                                    "  -> Removing 'projectCreator' key for legacy compatibility."
                                )
                                del data["projectCreator"]

                        with open(dest_path, "w", encoding="utf-8") as f_out:
                            json.dump(data, f_out, ensure_ascii=True, indent=4)
                    else:
                        self.progress_signal.emit(f"Copying:    {filename}")
                        shutil.copy2(src_path, dest_path)
                    time.sleep(0.01)  # Small sleep to make UI updates feel smoother

            self.finished_signal.emit(True, dest_project_dir)

        except Exception as e:
            self.progress_signal.emit(f"\nERROR: {e}")
            self.finished_signal.emit(False, str(e))


# --- Main Application Window ---


class ConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SooSL Legacy Converter")
        self.setGeometry(100, 100, 700, 500)
        self.init_ui()
        self.worker_thread = None
        self.worker = None

    def init_ui(self):
        # Layouts
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        button_layout = QHBoxLayout()

        # --- Widgets ---
        # Source Directory
        self.source_dir_label = QLineEdit("Select source project directory...")
        self.source_dir_label.setReadOnly(True)
        source_button = QPushButton("Browse...")
        source_button.clicked.connect(self.select_source_directory)

        # Destination Directory
        self.dest_dir_label = QLineEdit("Select output parent directory...")
        self.dest_dir_label.setReadOnly(True)
        dest_button = QPushButton("Browse...")
        dest_button.clicked.connect(self.select_dest_directory)

        # Target Version
        self.version_input = QLineEdit("0.9.3")

        # Log Console
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setFont(QFont("Courier", 9))

        # Convert Button
        self.convert_button = QPushButton("Convert Project")
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setFixedHeight(40)

        # --- Assembling the Layout ---
        form_layout.addRow(
            QLabel("Source Project:"),
            self.create_path_layout(self.source_dir_label, source_button),
        )
        form_layout.addRow(
            QLabel("Output Location:"),
            self.create_path_layout(self.dest_dir_label, dest_button),
        )
        form_layout.addRow(QLabel("Target Version:"), self.version_input)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.log_console)
        main_layout.addWidget(self.convert_button)

        self.setLayout(main_layout)

    def create_path_layout(self, line_edit, button):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        return layout

    def select_source_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select SooSL Project Directory"
        )
        if directory:
            self.source_dir_label.setText(directory)

    def select_dest_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Parent Directory"
        )
        if directory:
            self.dest_dir_label.setText(directory)

    def start_conversion(self):
        src_dir = self.source_dir_label.text()
        dest_dir = self.dest_dir_label.text()
        target_version = self.version_input.text()

        if not os.path.isdir(src_dir) or "Select" in src_dir:
            self.show_error_message(
                "Invalid Source", "Please select a valid source project directory."
            )
            return
        if not os.path.isdir(dest_dir) or "Select" in dest_dir:
            self.show_error_message(
                "Invalid Destination", "Please select a valid output parent directory."
            )
            return

        self.log_console.clear()
        self.convert_button.setText("Converting...")
        self.convert_button.setEnabled(False)

        # Setup and start the worker thread
        self.worker_thread = QThread()
        self.worker = ConversionWorker(src_dir, dest_dir, target_version)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished_signal.connect(self.on_conversion_finished)
        self.worker.progress_signal.connect(self.update_log)

        self.worker_thread.start()

    def update_log(self, message):
        self.log_console.append(message)

    def on_conversion_finished(self, success, result_message):
        if success:
            self.log_console.append(
                f"\nSUCCESS: Legacy project created at:\n{result_message}"
            )
            QMessageBox.information(
                self, "Success", "Project conversion completed successfully!"
            )
        else:
            if result_message != "Cancelled":
                self.show_error_message(
                    "Conversion Failed", f"An error occurred: {result_message}"
                )

        self.convert_button.setText("Convert Project")
        self.convert_button.setEnabled(True)

        self.worker_thread.quit()
        self.worker_thread.wait()
        self.worker_thread = None
        self.worker = None

    def show_error_message(self, title, message):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText(message)
        msg_box.setWindowTitle(title)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def closeEvent(self, event):
        """Ensure the worker thread is stopped when closing the window."""
        if self.worker:
            self.worker.stop()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        event.accept()


def apply_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)


def main():
    """Main function to run the Legacy Converter application."""
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    ex = ConverterApp()
    ex.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
