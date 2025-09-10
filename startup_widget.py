#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright SIL International 2009 - 2025.

This file is part of SooSL™.

SooSL™ is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

SooSL™ is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with SooSL™.  If not, see <http://www.gnu.org/licenses/>.
"""

import os, sys

from PyQt5.QtCore import Qt, QEvent, QSize, QTimer
from PyQt5.QtCore import pyqtSignal, pyqtSlot

from PyQt5.QtGui import QPixmap, QImage, QBrush, QPalette
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import qApp, QWidget
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
# from PyQt5.QtWidgets import QButtonGroup
# from PyQt5.QtWidgets import QLineEdit
# from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QPushButton

class StartupWidget(QWidget):
    canceled = pyqtSignal()
    startup = pyqtSignal(str)

    def __init__(self, __version__, __build__, parent=None):
        super(StartupWidget, self).__init__(parent)
        self.__version__ = __version__
        self.__build__ = __build__
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        #self.translations = translations
        self.projects = {}

        self.progress_bar = QProgressBar()
        self.progress_bar.setHidden(True)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        self.total_duration = 0
        self.last_progress = 0
        self.current_progress = 0
        self.current_filepath = ''

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(3)
        layout.addStretch()

        self.messageLabel = QLabel()
        self.messageLabel.setStyleSheet('color:blue;')
        self.messageLabel.setAlignment(Qt.AlignCenter|Qt.AlignBottom)
        self.messageLabel.setWordWrap(True)
        layout.addWidget(self.messageLabel)

        self.trans_combo = QComboBox()
        self.trans_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.trans_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.trans_combo.setToolTip(qApp.instance().translate('StartupWidget', 'Display language'))
        for name in sorted(qApp.instance().translation_dict.keys()):
            self.trans_combo.addItem(name)
        settings = qApp.instance().getSettings()
        self.trans_combo.currentTextChanged.connect(self.onDisplayLangChange)

        display_lang = settings.value('displayLang', 'English')
        self.trans_combo.setCurrentText(display_lang)

        NO_PROJECT_NAME = qApp.instance().translate('StartupWidget', 'No dictionary')
        last_project_name = NO_PROJECT_NAME
        last_opened_project = settings.value("lastOpenedDatabase")
        if last_opened_project:
            last_opened_project = last_opened_project.replace('\\', '/')
            if os.path.exists(last_opened_project):
                last_project_name = qApp.instance().pm.getProjectNameIdVersionDatetime(last_opened_project)[0] #os.path.splitext(os.path.basename(last_opened_project))[0]

        if last_project_name == NO_PROJECT_NAME:
            last_opened_project = 'NO DICTIONARY'

        layout.addWidget(self.trans_combo)

        self.project_btn = QPushButton(last_project_name)
        self.project_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.project_btn.setIcon(QIcon(':/open_file.png'))
        self.project_btn.setToolTip(qApp.instance().translate('StartupWidget', 'Select dictionary to open'))
        self.project_btn.setStyleSheet('text-align: left; vertical-align: top;')
        self.project_btn.setProperty('project_filename', last_opened_project)
        self.project_btn.clicked.connect(self.selectProject)
        layout.addWidget(self.project_btn)

        self.project_info_lbl = QLabel()
        self.project_info_lbl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        layout.addWidget(self.project_info_lbl)
        self.setProjectInfo(last_opened_project)

        self.btnBox = QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cancel_btn = self.btnBox.button(QDialogButtonBox.Cancel)
        self.cancel_btn.setText(qApp.instance().translate('StartupWidget', 'Cancel'))
        self.btnBox.button(QDialogButtonBox.Cancel).setCursor(QCursor(Qt.PointingHandCursor))
        self.start_btn = self.btnBox.button(QDialogButtonBox.Ok)
        self.start_btn.setText(qApp.instance().translate('StartupWidget', 'Start'))
        self.btnBox.button(QDialogButtonBox.Ok).setCursor(QCursor(Qt.PointingHandCursor))

        self.btnBox.accepted.connect(self.onStart)
        self.btnBox.rejected.connect(self.onCancel)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)
        self.version_build_lbl = QLabel()
        self.version_build_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setProgressText()
        hlayout.addWidget(self.version_build_lbl)
        hlayout.addWidget(self.progress_bar)
        hlayout.addWidget(self.btnBox)

        layout.addLayout(hlayout)
        self.setLayout(layout)
        qApp.processEvents()

        self.showProjectControls(False)

    def setProjectInfo(self, dict_file):
        project_name, id, _version, _datetime = (None, None, None, None)
        project_folder = ''
        if dict_file:
            project_name, id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(dict_file)
            project_folder = os.path.dirname(dict_file)
        # tip_txt = os.path.basename(dict_file)
        # if not project_name:
        #     tip_txt = ''
        # self.project_btn.setToolTip(tip_txt)
        if project_name:
            self.project_info_lbl.show()
            if not _version:
                _version = ''
            if not _datetime:
                _datetime = ''
            else:
                _datetime = qApp.instance().pm.getCurrentDateTimeStr(iso_str=_datetime)
            version_txt = qApp.instance().translate('StartupWidget', 'Version:')
            modified_txt = qApp.instance().translate('StartupWidget', 'Modified:')
            folder_txt = qApp.instance().translate('StartupWidget', 'Folder:')
            text = f'{folder_txt} {project_folder}<br>{version_txt} {_version}<br>{modified_txt} {_datetime}'
            self.project_info_lbl.setText(text)
        else:
            self.project_info_lbl.hide()

    def onStart(self):
        if self.project and not qApp.instance().pm.minSooSLVersionCheck(self.project):
            project_name = qApp.instance().translate('StartupWidget', 'No dictionary')
            project = 'NO DICTIONARY'
            self.project_btn.setText(project_name)
            self.project_btn.setProperty('project_filename', project)
            self.setProjectInfo(project)
        else:
            self.showProjectControls(False)
            self.startup.emit(self.project)

    def onCancel(self):
        #qApp.instance().error_log.close()
        qApp.instance().removeTempDir()
        qApp.instance().clearCrashReport()
        qApp.instance().removeLogs()
        sys.exit()

    def showProjectControls(self, _bool=True):
        self.messageLabel.setVisible(not _bool)
        for widget in [self.trans_combo,
            self.project_btn,
            self.project_info_lbl,
            self.btnBox]:
                widget.setVisible(_bool)

    def showMessage(self, msg):
        #self.showProjectControls(False)
        self.messageLabel.setText(msg)
        qApp.processEvents()

    def resizeEvent(self, evt):
        _size = self.sizeHint()
        self.setFixedSize(_size)

        w = _size.width()
        img_size = QSize(w, w)
        # https://stackoverflow.com/questions/56658401/setting-background-image-for-a-widget-in-another-class
        img = QImage(':/soosl_logo.png')
        palette = self.palette()
        sImage = img.scaled(img_size, transformMode=Qt.SmoothTransformation)
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)
        super(StartupWidget, self).resizeEvent(evt)

    def sizeHint(self):
        try:
            s = qApp.screenAt(self.pos()).availableSize()
        except:
            s = QSize(1280, 800)
        w = s.width() * 0.3
        h = w
        return QSize(int(w), int(h))

    def selectProject(self):
        mw = qApp.instance().getMainWindow()
        dlg = mw.soosl_file_dlg #open_project_dlg
        # dlg.show()
        # dlg.raise_()
        qApp.processEvents()
        mw.ensureUsingActiveMonitor(dlg)
        project_name = qApp.instance().translate('StartupWidget', 'No dictionary')
        project = 'NO DICTIONARY'
        if dlg.exec_():
            project = dlg.selected_path
            if not project or not qApp.instance().pm.minSooSLVersionCheck(project):
                return self.selectProject()
            project_name = qApp.instance().pm.getProjectNameIdVersionDatetime(project)[0]
        #del dlg
        self.project_btn.setText(project_name)
        self.project_btn.setProperty('project_filename', project)
        self.setProjectInfo(project)
        qApp.processEvents()

    @property
    def project(self):
        return self.project_btn.property('project_filename').replace('\\', '/')

    @property
    def project_dir(self):
        return os.path.dirname(os.path.dirname(self.project))

    def translation(self):
        t = qApp.instance().translation_dict.get(self.trans_combo.currentText())
        if t:
            return t
        return None

    #@pyqtSlot(str)
    def onDisplayLangChange(self, lang):
        settings = qApp.instance().getSettings()
        settings.setValue('displayLang', lang)
        qApp.instance().setupTranslators(lang)
        QTimer.singleShot(80, self.changeDisplay)
        ## NOTE: button texts seem to get changed to 'Ok' and 'Cancel'
        # somewhere else; adding a delay here gets around this.
        # Where is the other change???

    def changeDisplay(self):
        try:
            ok_text = qApp.instance().translate('StartupWidget', 'Start')
            cancel_text = qApp.instance().translate('StartupWidget', 'Cancel')
            self.start_btn.setText(ok_text)
            self.cancel_btn.setText(cancel_text)
            self.project_btn.setToolTip(qApp.instance().translate('StartupWidget', 'Select dictionary to open'))
            if self.project_btn.property('project_filename') == 'NO DICTIONARY':
                NO_PROJECT_NAME = qApp.instance().translate('StartupWidget', 'No dictionary')
                self.project_btn.setText(NO_PROJECT_NAME)
            self.trans_combo.setToolTip(qApp.instance().translate('StartupWidget', 'Display language'))
            project = self.project_btn.property('project_filename')
            self.setProjectInfo(project)
        except:
            pass

    # @pyqtSlot(str)
    # def onProjectChange(self, project_name):
    #     settings = qApp.instance().getSettings()
    #     project = self.project_btn.property('project_filename')
    #     if project:
    #         project = project.replace('\\', '/')
    #     settings.setValue("lastOpenedDatabase", project)

    def hideEvent(self, evt):
        self.trans_combo.setHidden(True)
        self.project_btn.setHidden(True)
        self.btnBox.setHidden(True)
        qApp.processEvents()
#         super(StartupWidget, self).hideEvent(evt)

    def setProgressText(self, text=None):
        if text and not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)
        if text is None:
            text = f'SooSL™ {self.__version__} ({self.__build__})'
        self.version_build_lbl.setText(text)

    def setProgressValue(self, value):
        self.progress_bar.setValue(value)

    def setFileDurations(self, file_durations):
        # file_durations; tuples of (file, duration) pairs
        if not file_durations:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)
        else:
            for fd in file_durations:
                file, duration = fd
                if duration:
                    self.total_duration += duration
                else:
                    self.progress_bar.setMinimum(0)
                    self.progress_bar.setMaximum(0)

    # used when applying changes; see project_manager.__applyChanges
    def onProgress(self, filepath, progress, duration, completed):
        if not duration:
            return
        if self.current_filepath == filepath:
            self.current_progress = self.last_progress + progress
        else:
            self.current_filepath = filepath
            self.last_progress = self.last_progress + self.current_progress
            if progress:
                self.current_progress += progress #most likely 0 on  file change
        total_progress_percent = round(self.current_progress/self.total_duration*100)
        if completed:
            total_progress_percent = 100
        self.setProgressValue(total_progress_percent)
        #self.setProgressText('{}...{}'.format(qApp.instance().translate('StartupWidget', 'Saving'), filepath))

# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()
