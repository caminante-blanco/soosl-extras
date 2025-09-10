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

import sys, os

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal

from PyQt5.QtGui import QPixmap

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import qApp

from video_widget_vlc import Player

class ExistingMediaDlg(QDialog):
    """how to deal with existing media file (video/picture); use any existing text also?
    """
    view_signs_for_file = pyqtSignal(str)

    def __init__(self, parent, filename, existing_filename, file_type, change=False):
        super(ExistingMediaDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
        self.existing_filename = existing_filename
        if file_type == 'ex_media':
            if self.existing_filename.count('extra_pictures'):
                file_type = 'ex_picture'
            else:
                file_type = 'ex_video'

        location = 'out' # file located outside of dictionary directory
        if os.path.normpath(filename).startswith(os.path.normpath(qApp.instance().pm.getCurrentProjectDir())):
            location = 'in' # file located within the dictionary directory
        name = os.path.basename(filename)
        type_txt = qApp.instance().translate('ExistingMediaDlg', "You have used this file before")
        window_title = qApp.instance().translate('ExistingMediaDlg', 'Already Used')
        if location == 'in':
            if file_type == 'sign':
                type_txt = qApp.instance().translate('ExistingMediaDlg', "This video already used for another sign")
            elif file_type == 'sent':
                type_txt = qApp.instance().translate('ExistingMediaDlg', "This video already used for another sentence")
                #self.video_id = qApp.instance().pm.getSentenceVideoId(filename)
            elif file_type == 'ex_video':
                type_txt = qApp.instance().translate('ExistingMediaDlg', "This extra video already used for another sign")
            elif file_type == 'ex_picture':
                type_txt = qApp.instance().translate('ExistingMediaDlg', "This extra picture already used for another sign")
            window_title = qApp.instance().translate('ExistingMediaDlg', 'Use It Again')
        self.setWindowTitle(window_title)

        self.selected_texts = None
        self.case = None
        self.text_lbls = []

        layout = QVBoxLayout()
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        self.setLayout(layout)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        lbl = QLabel()
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl.setPixmap(QPixmap(':/warning.png'))
        txt_label = QLabel("<h3 style='color:blue'>{}</h3>".format(type_txt))
        txt_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        txt_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hlayout = QHBoxLayout()
        hlayout.setSizeConstraint(QHBoxLayout.SetMinimumSize)
        hlayout.addWidget(lbl)
        hlayout.addWidget(txt_label)
        hlayout.addStretch()
        layout.addLayout(hlayout)
        #case 1: do nothing
        #case 2: view existing
        #case 3: use existing
        #case 4: use original
        lbl = QLabel(qApp.instance().translate('ExistingMediaDlg', 'What do you want to do?'))
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(lbl)
        if file_type == 'sign':
            if location == 'out':
                self.btn_original = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use original video'))
                self.btn_original.setProperty('case', 4)
                layout.addWidget(self.btn_original)
                self.btn_original.clicked.connect(self.onCaseClicked)
            self.btn_existing = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use existing video'))
            self.btn_existing.setProperty('case', 3)
            layout.addWidget(self.btn_existing)
            self.btn_existing.clicked.connect(self.onCaseClicked)

        elif file_type == 'sent':
            if location == 'out':
                self.btn_original = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use original video'))
                self.btn_original.setProperty('case', 4)
                layout.addWidget(self.btn_original)
                self.btn_original.clicked.connect(self.onCaseClicked)
            self.btn_existing = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use existing video'))
            self.btn_existing.setProperty('case', 3)
            layout.addWidget(self.btn_existing)
            self.btn_existing.clicked.connect(self.onCaseClicked)

        elif file_type == 'ex_video':
            if location == 'out':
                self.btn_original = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use original video'))
                self.btn_original.setProperty('case', 4)
                layout.addWidget(self.btn_original)
                self.btn_original.clicked.connect(self.onCaseClicked)
            self.btn_existing = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use existing video'))
            self.btn_existing.setProperty('case', 3)
            layout.addWidget(self.btn_existing)
            self.btn_existing.clicked.connect(self.onCaseClicked)

        elif file_type == 'ex_picture':
            if location == 'out':
                self.btn_original = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use original picture'))
                self.btn_original.setProperty('case', 4)
                layout.addWidget(self.btn_original)
                self.btn_original.clicked.connect(self.onCaseClicked)
            self.btn_existing = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Use existing picture'))
            self.btn_existing.setProperty('case', 3)
            layout.addWidget(self.btn_existing)
            self.btn_existing.clicked.connect(self.onCaseClicked)

        self.btn_existing.setToolTip('{}<br><br>{}'.format(qApp.instance().translate('ExistingMediaDlg', 'Use file that already exists in the dictionary.'),
            qApp.instance().translate('ExistingMediaDlg', 'This option is quicker as the file only needs to be copied when the sign is saved.')))
        if location == 'out':
            self.btn_original.setToolTip(qApp.instance().translate('ExistingMediaDlg', """Use original file."""))

        texts = qApp.instance().pm.getTextsByMediaFile(existing_filename, file_type) #returns dict
        lang_id = qApp.instance().pm.search_lang_id
        try:
            t1 = texts[0]
        except:
            t1 = None
        if t1 and file_type == 'sent': #in ['sign', 'sent']:
            if location == 'out':
                self.btn_original.setText(qApp.instance().translate('ExistingMediaDlg', 'Use original video with a text option below'))
            self.btn_existing.setText(qApp.instance().translate('ExistingMediaDlg', 'Use existing video with a text option below'))
            layout.addSpacing(10)
            used_texts = []
            for text in texts:
                if text and text.lang_id == lang_id and text.text and text not in used_texts:
                    _text = text.text
                    used_texts.append(_text)
                    radio = QRadioButton()
                    radio.text = texts
                    radio.toggled.connect(self.onToggled)
                    radio.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    lbl = QLabel(_text)
                    lbl.radio = radio
                    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                    lbl.setWordWrap(True)
                    lbl.setAlignment(Qt.AlignLeft|Qt.AlignTop)
                    self.text_lbls.append(lbl)
                    hlayout = QHBoxLayout()
                    hlayout.addSpacing(24)
                    hlayout.addWidget(radio)
                    hlayout.addWidget(lbl)
                    hlayout.addStretch()
                    hlayout.setAlignment(radio, Qt.AlignRight|Qt.AlignTop)
                    hlayout.setAlignment(lbl, Qt.AlignLeft|Qt.AlignTop)
                    layout.addLayout(hlayout)
            hlayout = QHBoxLayout()
            hlayout.addSpacing(24)
            radio = QRadioButton()
            radio.text = None
            radio.toggled.connect(self.onToggled)
            radio.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            radio.setChecked(True)
            lbl = QLabel(qApp.instance().translate('ExistingMediaDlg', 'No text'))
            lbl.radio = radio
            self.text_lbls.append(lbl)
            hlayout.addWidget(radio)
            hlayout.addWidget(lbl)
            hlayout.addStretch()
            hlayout.setAlignment(radio, Qt.AlignRight|Qt.AlignTop)
            hlayout.setAlignment(lbl, Qt.AlignLeft|Qt.AlignTop)
            layout.addLayout(hlayout)
        layout.addSpacing(24)


        mw = qApp.instance().getMainWindow()
        if not mw.editing:
            btn_view = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'View signs that use this video'))
            btn_view.setProperty('case', 2)
            btn_view.clicked.connect(self.onCaseClicked)
            layout.addWidget(btn_view)
        btn_last = QPushButton(qApp.instance().translate('ExistingMediaDlg', 'Do nothing (cancel)'))
        btn_last.setProperty('case', 1)
        btn_last.clicked.connect(self.onCaseClicked)
        layout.addWidget(btn_last)

    ##!!@pyqtSlot(bool)
    def onToggled(self, _bool):
        btn = self.sender()
        if _bool:
            self.selected_texts = btn.text
        self.btn_existing.setFocus(True)

    ##!!@pyqtSlot()
    def onCaseClicked(self):
        btn = self.sender()
        self.case = btn.property('case')
        if self.case == 2:
            btn.setEnabled(False)
            self.view_signs_for_file.emit(self.existing_filename)
        self.done(self.case)

    def mousePressEvent(self, evt):
        for lbl in self.text_lbls:
            if lbl.underMouse():
                lbl.radio.setChecked(True)
        super(ExistingMediaDlg, self).mousePressEvent(evt)
