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

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QTimer, QSize

from PyQt5.QtGui import QPixmap

from PyQt5.QtWidgets import QDialog, QSizePolicy, QWidget, QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import qApp

class ProgressDlg(QDialog):
    canceled = pyqtSignal()

    def __init__(self, parent=None, title=None):
        super(ProgressDlg, self).__init__(parent, flags=Qt.CustomizeWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.file_dict = {}
        self.total_duration = 0

        main_layout = QVBoxLayout()
        main_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(4)

        self.label = QLabel()
        self.label.setStyleSheet("""QLabel {color:Blue}""")
        if title:
            self.label.setText(title)
        main_layout.addWidget(self.label)
        main_layout.addSpacing(4)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setTextVisible(False)

        show_info_btn = QPushButton(qApp.instance().translate('ProgressDlg', 'Show info'))
        show_info_btn.clicked.connect(self.onShowInfo)
        self.cancel_btn = QPushButton(qApp.instance().translate('ProgressDlg', 'Cancel'))
        self.cancel_btn.clicked.connect(self.onCancel)
        btns = QDialogButtonBox()
        btns.addButton(show_info_btn, QDialogButtonBox.NoRole)
        btns.addButton(self.cancel_btn, QDialogButtonBox.NoRole)

        self.more_info_widget = QWidget()
        self.more_info_widget.setHidden(True)
        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(3, 3, 3, 3)
        self.more_info_widget.setLayout(vlayout)

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(btns)
        main_layout.addWidget(self.more_info_widget)
        self.setLayout(main_layout)
        self.setVisible(False)

    def setSize(self):
        self.setModal(False)
        self.resize(QSize(500, 500))
        self.setModal(True)

    def setProgressText(self, text):
        try:
            self.label.setText(text)
        except:
            pass #may have been deleted before last request comes

    ##!!@pyqtSlot()
    def onShowInfo(self):
        btn = self.sender()
        if self.more_info_widget.isHidden():
            self.more_info_widget.setHidden(False)
            btn.setText(qApp.instance().translate('ProgressDlg', 'Hide info'))
        else:
            self.more_info_widget.setHidden(True)
            btn.setText(qApp.instance().translate('ProgressDlg', 'Show info'))
        #self.setSize()

    ##!!@pyqtSlot(bool)
    def onCancel(self, _bool):
        self.canceled.emit()
        try:
            self.close()
        except:
            pass

    def setMaximum(self, _int):
        self.progress_bar.setMaximum(_int)

    def __setProgressLabels(self, filepath, duration):
        if duration:
            filepath = filepath.replace('\\', '/')
            self.total_duration += duration
            lbl = QLabel()
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            lbl.setStyleSheet("""QLabel {color:green}""")
            lbl.setAlignment(Qt.AlignLeft|Qt.AlignHCenter)
            lbl.setMinimumWidth(36)
            lbl.setMinimumHeight(22)
            lbl.progress = 0
            self.file_dict[filepath] = lbl
            text = '{}   '.format(filepath)
            lbl2 = QLabel(text)
            lbl2.setMinimumHeight(22)
            lbl2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lbl2.setAlignment(Qt.AlignLeft)
            hlayout = QHBoxLayout()
            hlayout.addWidget(lbl)
            hlayout.addWidget(lbl2)
            self.more_info_widget.layout().addLayout(hlayout)
            self.more_info_widget.layout().addSpacing(2)

    def setFileDurations(self, file_durations):
        if not file_durations:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)
        else:
            for filepath, duration in file_durations:
                try:
                    self.__setProgressLabels(filepath, duration)
                except:
                    pass # may have been deleted

    ##!!@pyqtSlot(str, int, float, bool)
    def onProgress(self, filepath, progress, duration, completed):
        if not duration:
            duration = 50 #to give it at least a percent value for progress
            progress = round(progress/2) #progress given out of 100%, so cut in half to relate to duration of 50

        if self.isHidden():
            self.show()
            self.setEnabled(True)
        filepath = filepath.replace('\\', '/')
        progress_lbl = self.file_dict.get(filepath)

        if progress > 0 and self.progress_bar.maximum() == 0:
            self.progress_bar.setMaximum(100)
        if not completed and progress_lbl:
            progress_lbl.progress = progress

        if progress_lbl:
            percent_progress = 0
            try:
                percent_progress = round(progress/duration*100)
            except:
                percent_progress = 0
            if percent_progress == 0:
                progress_lbl.setText('  ')
            elif percent_progress < 10:
                progress_lbl.setText(' {}{}  '.format(percent_progress, self.locale().percent()))
            elif percent_progress < 100:
                progress_lbl.setText('{}{}  '.format(percent_progress, self.locale().percent()))
            else:
                progress_lbl.setPixmap(QPixmap(':/green_check.png'))

        current_progress = 0
        for lbl in self.file_dict.values():
            if hasattr(lbl, 'progress'):
                current_progress += lbl.progress

        total_progress_percent = 0
        try:
            total_progress_percent = round(current_progress/self.total_duration*100)
        except:
            total_progress_percent = 0
        self.progress_bar.setValue(total_progress_percent)
