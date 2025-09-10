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

from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtGui import QCursor, QPixmap

from PyQt5.QtWidgets import QDialog, QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import qApp

from project_merger import ReconcileChangesDialog, MergeDialog

class ContinueEditingDlg(QDialog):
    """Dialog used when editing is about to finish due to inactivity"""

    def __init__(self, parent):
        super(ContinueEditingDlg, self).__init__(parent=parent, flags=Qt.CustomizeWindowHint|Qt.WindowStaysOnTopHint)
        settings = qApp.instance().getSettings()
        self.count = int(settings.value('inactivityCountdownSeconds', 60))
        countdown_timer = QTimer(self)
        countdown_timer.setInterval(1000)
        countdown_timer.timeout.connect(self.onTimeout)

        layout = QVBoxLayout()

        warning_lbl = QLabel()
        warning_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        warning_lbl.setPixmap(QPixmap(':/warning.png'))
        txt = qApp.instance().translate('ContinueEditingDlg', 'Editing will close due to inactivity.')
        txt2 = qApp.instance().translate('ContinueEditingDlg', 'Unsaved changes will be discarded.')
        if isinstance(parent, (ReconcileChangesDialog, MergeDialog)):
            txt = qApp.instance().translate('ContinueEditingDlg', 'Reconciling of versions will stop due to inactivity.')
            txt2 = qApp.instance().translate('ContinueEditingDlg', 'Current progress will be saved.')
        txt_label = QLabel("<center><h3 style='color:blue'>{}</h3><p>{}</p></center>".format(txt, txt2))
        txt_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        txt_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.count_lbl = QLabel()

        hlayout = QHBoxLayout()
        hlayout.setSizeConstraint(QHBoxLayout.SetMinimumSize)
        vlayout = QVBoxLayout()

        hlayout.addWidget(warning_lbl)
        vlayout.addWidget(txt_label)
        vlayout.addWidget(self.count_lbl)
        hlayout.addLayout(vlayout)
        layout.addLayout(hlayout)

        btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
        btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btnBox.button(QDialogButtonBox.Ok).setCursor(QCursor(Qt.PointingHandCursor))
        t = qApp.instance().translate('ContinueEditingDlg', 'Continue editing')
        btnBox.button(QDialogButtonBox.Ok).setText(f' {t} ')

        btnBox.accepted.connect(self.accept)

        layout.addStretch()
        layout.addWidget(btnBox)
        self.setLayout(layout)
        self.setCountLabel()
        countdown_timer.start()

    def setCountLabel(self):
        t = qApp.instance().translate('ContinueEditingDlg', 'Seconds remaining:')
        txt = f'<center>{t} <b><span style="color:blue;">{self.count}</span></b></center>'
        self.count_lbl.setText(txt)

    def onTimeout(self):
        self.count -= 1
        self.setCountLabel()
        if self.count <= 0:
            # dialect or gram cat dialog could be open while sign is being edited
            mw = qApp.instance().getMainWindow()
            if self.parent() is not mw and mw.editing:
                mw.leaveEdit(check_dirty=False)
            self.reject()
