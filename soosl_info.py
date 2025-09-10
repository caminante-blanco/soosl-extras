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

import os
import io

from PyQt5.QtCore import QTimer, Qt, QUrl

from PyQt5.QtWidgets import QLabel, QWidget, QGridLayout, QPushButton,\
    QTextBrowser
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtGui import QCursor

class SooSLInfoPage(QFrame):
    def __init__(self, parent=None):
        super(SooSLInfoPage, self).__init__(parent)

        self.header = QLabel()
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.setText(self.getHeaderMessage())

        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(self.header, stretch=1)

        self.notebook = QTabWidget()
        self.notebook.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        docs_dir = qApp.instance().getDocsDir()
        about_html = os.path.join(docs_dir, "About.html")
        acknowledge_html = os.path.join(docs_dir, "Acknowledge.html")
        team_html = os.path.join(docs_dir, "Team.html")

        #About Page
        with io.open(about_html, 'r', encoding='utf-8') as f:
            html = f.read().format(docs_dir=docs_dir)
        self.about_page = QTextBrowser(self)
        self.about_page.setOpenExternalLinks(True)
        self.about_page.setAcceptRichText(True)
        self.about_page.setReadOnly(True)
        self.about_page.setHtml(html)
        self.notebook.addTab(self.about_page, qApp.instance().translate('SooSLInfoPage', 'About'))

        #Acknowledgement Page
        self.acknowledge_page = QTextBrowser(self)
        self.acknowledge_page.setOpenExternalLinks(True)
        self.acknowledge_page.setAcceptRichText(True)
        self.acknowledge_page.setReadOnly(True)
        self.acknowledge_page.setAutoFormatting(QTextEdit.AutoBulletList)
        self.acknowledge_page.setSource(QUrl.fromLocalFile(acknowledge_html))
        self.notebook.addTab(self.acknowledge_page, qApp.instance().translate('SooSLInfoPage', 'Thanks!'))

        #Team Page
        self.team_page = QTextBrowser(self)
        self.team_page.setOpenExternalLinks(True)
        self.team_page.setAcceptRichText(True)
        self.team_page.setReadOnly(True)
        self.team_page.setAutoFormatting(QTextEdit.AutoBulletList)
        self.team_page.setSource(QUrl.fromLocalFile(team_html))
        self.notebook.addTab(self.team_page, qApp.instance().translate('SooSLInfoPage', 'Team'))

        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addLayout(header_layout)
        layout.addWidget(self.notebook, stretch=1)
        self.setLayout(layout)

    def getHeaderMessage(self):
        settings = qApp.instance().getSettings()
        message = "<h2 style='color:Blue'><img src=':/about_soosl.png'> SooSL&#8482; {}</h2>".format(qApp.instance().getLongVersion())
        return message
