import sys
import os
import glob

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QProgressBar,
    QCheckBox,
    QGroupBox,
    QRadioButton,
    QMessageBox,
    QLabel,
    QDialog,
    QListWidget,
    QLineEdit,
    QDialogButtonBox,
    QTextEdit,
)

from mainwindow import MyApp


SUPPORTED_VIDEO_FORMATS = [".mp4", ".mov", ".avi", ".mkv"]
SUPPORTED_IMAGE_FORMATS = [
    ".bmp",
    ".gif",
    ".jpg",
    ".jpeg",
    ".png",
    ".pbm",
    ".pgm",
    ".ppm",
    ".xbm",
    ".xpm",
    ".svg",
]


class AuthorsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Authors")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        list_layout = QHBoxLayout()
        self.list_widget = QListWidget()
        list_layout.addWidget(self.list_widget)

        button_vbox = QVBoxLayout()
        self.addButton = QPushButton("Add")
        self.addButton.setDefault(True)
        self.removeButton = QPushButton("Remove")
        button_vbox.addWidget(self.addButton)
        button_vbox.addWidget(self.removeButton)
        button_vbox.addStretch()
        list_layout.addLayout(button_vbox)

        self.lineEdit = QLineEdit()
        self.lineEdit.setPlaceholderText("Enter author prefix and press enter or Add")
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        layout.addLayout(list_layout)
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.buttonBox)

        self.addButton.clicked.connect(self.addAuthor)
        self.removeButton.clicked.connect(self.removeAuthor)
        self.lineEdit.returnPressed.connect(self.addAuthor)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def addAuthor(self):
        author = self.lineEdit.text().strip()
        if author:
            self.list_widget.addItem(author)
            self.lineEdit.clear()

    def removeAuthor(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def getAuthors(self):
        return {
            self.list_widget.item(i).text() for i in range(self.list_widget.count())
        }


class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    total_files = pyqtSignal(int)
    ask_user = pyqtSignal(str, str)
    user_response = pyqtSignal(bool)
    prompt_for_authors = pyqtSignal()
    authors_submitted = pyqtSignal(set)
    log_message = pyqtSignal(str)

    def __init__(self, pm, import_directory, mode, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.import_directory = import_directory
        self.mode = mode
        self.authors = set()
        self.focal_dialect_id = None
        self.lang_id = None
        self.media_files = []

    def startProcessing(self):
        signs_to_save = []

        self.focal_dialect_id = self.pm.getFocalDialectId()
        self.lang_id = 1

        if self.mode == "individual":
            signs_to_save = self._processIndividual(self.media_files)
        elif self.mode == "group-images":
            signs_to_save = self._processGroupImages(self.media_files)
        elif self.mode == "group-all":
            signs_to_save = self._processGroupAll(self.media_files)

        if not signs_to_save:
            self.finished.emit()
            return

        self.total_files.emit(len(signs_to_save))

        for i, sign_data in enumerate(signs_to_save):
            self.pm.saveSign(sign_data, record=False, update_last_change=False)

            gloss = (
                sign_data.get("senses", [{}])[0]
                .get("glossTexts", [{}])[0]
                .get("text", "UNKNOWN")
            )
            primary = f"({i+1}/{len(signs_to_save)}) Saved [PRIMARY] for '{gloss}': {os.path.basename(sign_data.get('path', ''))}"
            extras = [
                f"  + [EXTRA] {os.path.basename(f.get('path', ''))}"
                for f in sign_data.get("extraMediaFiles", [])
            ]
            for line in [primary] + extras:
                self.log_message.emit(line)

            self.progress.emit(i + 1)
        self.finished.emit()

    def _getMediaFiles(self):
        for ext in SUPPORTED_VIDEO_FORMATS + SUPPORTED_IMAGE_FORMATS:
            self.media_files.extend(
                glob.glob(
                    os.path.join(self.import_directory, "**", f"*{ext}"), recursive=True
                )
            )

    def _parseFilename(self, media_file):
        filename_with_ext = os.path.basename(media_file)
        filename, _ = os.path.splitext(filename_with_ext)
        parts = filename.split("_")
        alt_index = 0
        author = None
        if parts and parts[-1].isdigit():
            alt_index = int(parts.pop(-1))
        if parts and parts[0] in self.authors:
            author = parts.pop(0)
        gloss = " ".join(parts)
        if not gloss:
            return None
        return {"gloss": gloss, "alt_index": alt_index, "author": author}

    def _processIndividual(self, media_files):
        signs_to_save = []
        for media_file in media_files:
            parsed_data = self._parseFilename(media_file)
            if not parsed_data:
                continue
            sign_data = {
                "id": self.pm.getNewId(),
                "new": True,
                "path": media_file,
                "hash": self.pm.getHash(media_file),
                "author": parsed_data.get("author"),
                "altIndex": parsed_data.get("alt_index", 0),
                "senses": [
                    {
                        "id": "n",
                        "dialectIds": [self.focal_dialect_id],
                        "glossTexts": [
                            {"langId": self.lang_id, "text": parsed_data["gloss"]}
                        ],
                    }
                ],
            }

            signs_to_save.append(sign_data)
        return signs_to_save

    def _processGroupAll(self, media_files):
        signs_to_save = []
        media_by_gloss = {}
        for media_file in media_files:
            parsed_data = self._parseFilename(media_file)

            if not parsed_data:
                continue

            parsed_data["path"] = media_file

            gloss = parsed_data.get("gloss")
            if gloss not in media_by_gloss:
                media_by_gloss[gloss] = []
            media_by_gloss[gloss].append(parsed_data)

        for gloss, media_items in media_by_gloss.items():

            def sort_key(item):
                ext = os.path.splitext(item["path"])[-1].lower()
                is_video = ext in SUPPORTED_VIDEO_FORMATS
                return (not is_video, item["alt_index"])

            media_items.sort(key=sort_key)

            primary_media_item = media_items[0]
            extra_media_items = media_items[1:]

            extra_media_data = []
            for extra_item in extra_media_items:
                extra_media_data.append(
                    {
                        "id": "n",
                        "path": extra_item.get("path"),
                        "hash": self.pm.getHash(extra_item.get("path")),
                    }
                )

            sign_data = {
                "id": self.pm.getNewId(),
                "new": True,
                "path": primary_media_item.get("path"),
                "hash": self.pm.getHash(primary_media_item.get("path")),
                "author": primary_media_item.get("author"),
                "altIndex": primary_media_item.get("alt_index", 0),
                "senses": [
                    {
                        "id": "n",
                        "dialectIds": [self.focal_dialect_id],
                        "glossTexts": [{"langId": self.lang_id, "text": gloss}],
                    }
                ],
                "extraMediaFiles": extra_media_data,
            }

            signs_to_save.append(sign_data)
        return signs_to_save

    def _processGroupImages(self, media_files):
        signs_to_save = []
        media_by_gloss = {}

        for media_file in media_files:
            parsed_data = self._parseFilename(media_file)
            if not parsed_data:
                continue

            parsed_data["path"] = media_file
            gloss = parsed_data["gloss"]
            if gloss not in media_by_gloss:
                media_by_gloss[gloss] = {"videos": [], "images": []}

            ext = os.path.splitext(media_file)[-1].lower()
            if ext in SUPPORTED_VIDEO_FORMATS:
                media_by_gloss[gloss]["videos"].append(parsed_data)
            else:
                media_by_gloss[gloss]["images"].append(parsed_data)

        for gloss, media in media_by_gloss.items():
            for video_item in media["videos"]:
                extra_media_data = [
                    {
                        "id": "n",
                        "path": image_item.get("path"),
                        "hash": self.pm.getHash(image_item.get("path")),
                    }
                    for image_item in media.get("images", [])
                ]

                sign_data = {
                    "id": self.pm.getNewId(),
                    "new": True,
                    "path": video_item.get("path"),
                    "hash": self.pm.getHash(video_item.get("path")),
                    "author": video_item.get("author"),
                    "altIndex": video_item.get("alt_index"),
                    "senses": [
                        {
                            "id": "n",
                            "dialectIds": [self.focal_dialect_id],
                            "glossTexts": [{"langId": self.lang_id, "text": gloss}],
                        }
                    ],
                    "extraMediaFiles": extra_media_data,
                }
                signs_to_save.append(sign_data)

        return signs_to_save

    def createAuthors(self, create):
        if create:
            self.prompt_for_authors.emit()
        else:
            self.authors = set()
            self.startProcessing()

    def writeAuthorsTxt(self, authors):
        authors_path = os.path.join(self.import_directory, "authors.txt")
        with open(authors_path, "w") as f:
            for author in authors:
                f.write(f"{author}\n")
            self.authors = set(authors)
        self.startProcessing()

    def run(self):
        self._getMediaFiles()
        if not self.media_files:
            self.finished.emit()
            return

        total_files = len(self.media_files)
        self.total_files.emit(total_files)

        authors_path = os.path.join(self.import_directory, "authors.txt")
        if os.path.exists(authors_path):
            with open(authors_path, "r") as f:
                self.authors = set(line.strip() for line in f)
            self.startProcessing()
        else:
            self.ask_user.emit(
                "No authors.txt found",
                "Would you like to create an authors.txt file? This will allow you to ignore certain authorship prefixes from sign glosses.",
            )


class BatchImporterApp(QWidget):
    def __init__(self, app):
        super().__init__()
        self.pm = app.pm
        self.initUI()
        self.import_directory = ""
        self.project_file = ""

    def initUI(self):
        self.setWindowTitle("Importer")
        layout = QVBoxLayout()

        self.chooseImportDirButton = QPushButton("Select Import Directory")
        self.chooseImportDirButton.clicked.connect(self.chooseImportDir)

        self.importDirLabel = QLabel("No directory selected")
        self.importDirLabel.setAlignment(Qt.AlignCenter)

        self.chooseProjectFileButton = QPushButton("Select SooSL project file")
        self.chooseProjectFileButton.clicked.connect(self.chooseProjectFile)

        self.projectFileLabel = QLabel("No file selected")
        self.projectFileLabel.setAlignment(Qt.AlignCenter)

        self.progressBar = QProgressBar()

        self.logDisplay = QTextEdit()
        self.logDisplay.setReadOnly(True)
        self.logDisplay.setMinimumHeight(150)
        self.logDisplay.setFont(QFont("monospace", 9))

        self.modeGroupBox = QGroupBox("Import Mode")
        modeLayout = QHBoxLayout()
        self.modeGroupBox.setLayout(modeLayout)

        self.individualRadio = QRadioButton("One Sign per Media File")
        modeLayout.addWidget(self.individualRadio)
        self.groupImagesRadio = QRadioButton(
            "One Sign per Video file, Import Images as Extra Media"
        )
        modeLayout.addWidget(self.groupImagesRadio)
        self.groupAllRadio = QRadioButton("One Sign per Gloss")
        self.groupAllRadio.setChecked(True)
        modeLayout.addWidget(self.groupAllRadio)

        self.runButton = QPushButton("Start Import")
        self.runButton.clicked.connect(self.runImport)

        layout.addWidget(self.chooseImportDirButton)
        layout.addWidget(self.importDirLabel)
        layout.addWidget(self.chooseProjectFileButton)
        layout.addWidget(self.projectFileLabel)
        layout.addWidget(self.modeGroupBox)
        layout.addWidget(self.runButton)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.logDisplay)
        layout.addStretch()
        self.setLayout(layout)

    def askQuestion(self, title, message):
        reply = QMessageBox.question(
            self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        is_yes = reply == QMessageBox.Yes
        self.worker.user_response.emit(is_yes)

    def openAuthorsDialog(self):
        dialog = AuthorsDialog(self)
        if dialog.exec_():
            authors = dialog.getAuthors()
            self.worker.authors_submitted.emit(authors)
        else:
            self.worker.authors_submitted.emit(set())

    def chooseImportDir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Please choose the directory to import files from", ""
        )
        if directory:
            self.import_directory = directory
            self.importDirLabel.setText(f"Selected: {os.path.join(directory)}")

    def chooseProjectFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Please choose the SooSL project file", "", "JSON Files (*.json)"
        )
        if file_path:
            project = self.pm.openProject(file_path)
            if project:
                self.project_file = file_path
                self.projectFileLabel.setText(f"Selected: {os.path.join(file_path)}")
            else:
                QMessageBox.warning(
                    self, "Error", f"Could not open the SooSL project at: \n{file_path}"
                )

    def updateProgressBar(self, value):
        self.progressBar.setValue(value)

    def setProgressMax(self, value):
        self.progressBar.setMaximum(value)

    def importFinished(self):
        QMessageBox.information(self, "Done", "All files have been imported.")
        self.thread.quit()
        self.thread.wait()
        self.worker.deleteLater()
        self.thread.deleteLater()

    def updateLog(self, message):
        self.logDisplay.append(message)

    def runImport(self):
        if not self.import_directory:
            QMessageBox.warning(
                self, "Error", "Please select an import directory first."
            )
            return

        if not self.pm:
            QMessageBox.warning(
                self, "Error", "Please select a SooSL project file first."
            )
            return

        if self.individualRadio.isChecked():
            mode = "individual"
        elif self.groupImagesRadio.isChecked():
            mode = "group-images"
        else:
            mode = "group-all"

        self.runButton.setEnabled(False)

        self.thread = QThread()
        self.worker = Worker(self.pm, self.import_directory, mode)
        self.worker.moveToThread(self.thread)
        self.worker.ask_user.connect(self.askQuestion)
        self.worker.user_response.connect(self.worker.createAuthors)
        self.worker.prompt_for_authors.connect(self.openAuthorsDialog)
        self.worker.authors_submitted.connect(self.worker.writeAuthorsTxt)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.importFinished)
        self.worker.progress.connect(self.updateProgressBar)
        self.worker.total_files.connect(self.setProgressMax)
        self.worker.log_message.connect(self.updateLog)
        self.thread.start()


def main():
    """Main function to run the Batch Importer application."""
    app = MyApp(sys.argv)
    importer_window = BatchImporterApp(app)
    importer_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
