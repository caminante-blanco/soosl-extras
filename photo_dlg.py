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

from PyQt5.QtGui import QPixmap

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel

class PhotoDlg(QDialog):
    def __init__(self, pths, description, parent=None):
        super(PhotoDlg, self).__init__(parent, flags=Qt.CustomizeWindowHint | Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout2 = QHBoxLayout()
        layout2.setContentsMargins(0, 0, 0, 0)
        layout2.setSpacing(0)
        for p in pths:
            label = QLabel()
            px = QPixmap(p)
            label.setPixmap(px)
            layout2.addWidget(label)

        label = QLabel(description)
        label.setFixedHeight(16)

        layout.addLayout(layout2)
        layout.addWidget(label)
        self.setLayout(layout)
