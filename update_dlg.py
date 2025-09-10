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
import sys
import webbrowser
import re

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot

from PyQt5.QtGui import QPalette

from PyQt5.QtWidgets import QDialog, QScrollArea, QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QProgressBar

class UpdateDlg(QDialog):
    """Dialog used for updating SooSL version."""

    def __init__(self, parent, update_info):
        # update_info is normally a list of 2: [update_file, release_notes_str]
        ## NOTE: UpdateDlg no longer used in the next two cases:
        # if -1: Internet error or no Internet
        # if 1: Same version as currently installed version
        super(UpdateDlg, self).__init__(parent=parent, flags=Qt.CustomizeWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        if isinstance(update_info, list):
            self.filename, self.notes = update_info
        else:
            self.filename, self.notes = [update_info, update_info]

        qApp.instance().update_progress.connect(self.onProgress)
        self.pm = qApp.instance().pm

        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)

        scroll_area = QScrollArea()
        scroll_area.setBackgroundRole(QPalette.Base)
        scroll_area.setWidgetResizable(True)

        t2 = qApp.instance().translate('UpdateDlg', 'Downloading updates...')
        t3 = qApp.instance().translate('UpdateDlg', 'When downloading completes, your current version will quit and updating will begin.')
        if sys.platform.startswith('darwin'):
            t3 = qApp.instance().translate('UpdateDlg', 'When downloading completes, installation should begin automatically. If a DMG archive opens, drag SooSL.app into your Applications folder.')
        t4 = qApp.instance().translate('UpdateDlg', "Please be patient if download appears to pause at any time; it should resume shortly.")

        str1 = ''
        if isinstance(update_info, list):
            str1 = self.getStr()

        self.str2 = f"<h3 style='color:blue'><img src='{':/soosl_update.png'}'> {t2}</h3><p>{t3}</p><p>{t4}</p>"

        self.label = QLabel(str1)
        self.label.setContentsMargins(12, 10, 10, 0)
        self.label.setWordWrap(True)

        self.label2 = QLabel('<p>{}</p>'.format(qApp.instance().translate('UpdateDlg', 'Updates are also available from our website.')))
        self.label2.setContentsMargins(12, 0, 0, 5)
        settings = qApp.instance().getSettings()
        _url = settings.value('Website')
        self.websiteBtn = QPushButton(' {}/software.html '.format(_url))
        self.websiteBtn.setToolTip(qApp.instance().translate('UpdateDlg', 'Visit SooSL website'))
        self.websiteBtn.setStyleSheet('QPushButton {color:blue;}')
        self.websiteBtn.clicked.connect(self.onVisitWebsite)

        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 100)
        self.progressBar.hide()

        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnOk = self.btnBox.button(QDialogButtonBox.Ok)
        self.btnNo = self.btnBox.button(QDialogButtonBox.Cancel)
        self.btnOk.setFocusPolicy(Qt.StrongFocus)
        self.btnNo.setFocusPolicy(Qt.StrongFocus)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)
        self.setupButtons()

        scroll_area.setWidget(self.label)
        layout.addWidget(scroll_area)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.btnBox)
        layout.addSpacing(10)
        hlayout = QHBoxLayout()
        hlayout.setSpacing(3)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(self.label2)
        hlayout.addWidget(self.websiteBtn)
        layout.addLayout(hlayout)

        self.setLayout(layout)
        self.setMinimumSize(200, 200)

    def hideEvent(self, evt):
        qApp.processEvents()
        super(UpdateDlg, self).hideEvent(evt)

    def setupButtons(self):
        self.btnOk.setText(qApp.instance().translate('UpdateDlg', "Update"))
        self.btnNo.setText(qApp.instance().translate('UpdateDlg', "Don't update"))
        self.btnOk.show()
        self.btnNo.show()

    def getStr(self):
        txt = qApp.instance().translate('UpdateDlg', 'New SooSL™ available!')
        version_txt = qApp.instance().translate('ReleaseNotesDlg', "Version:")
        release_txt = qApp.instance().translate('ReleaseNotesDlg', "Release date:")
        added_txt = qApp.instance().translate('ReleaseNotesDlg', 'Added')
        fixed_txt = qApp.instance().translate('ReleaseNotesDlg', 'Fixed')
        changed_txt = qApp.instance().translate('ReleaseNotesDlg', 'Changed')

        def wrap_line(line):
            if line.startswith('###'): # 'Add' or 'Fixed'
                line = line.lstrip('# ')
                txt = line
                if line.startswith('Added'):
                    txt = added_txt
                elif line.startswith('Fixed'):
                    txt = fixed_txt
                elif line.startswith('Changed'):
                    txt = changed_txt
                return f'<h3 style="color:blue">{txt}</h3><ul>'
            elif line.startswith('##'): # Version string on first line
                version, release_date = line.split('-', 1)
                version = re.findall('[0-9]+', version) # find the numbers; single digits for version numbers, 6 digit build number
                build = version[-1]
                version = '.'.join(version[:-1]) # Join together version numbers, excluding build number
                line = f"""<h3><span style='color:blue'>{version_txt} </span>SooSL&trade; {version} ({build})&nbsp;&nbsp;&nbsp;&nbsp;
                    <span style='color:blue'>{release_txt} </span>{release_date}</h3>"""
                return line
            elif line.startswith('-'):
                line = line.replace('-', '<li>', 1)
                return f'</li>{line}'
            elif line == '':
                return '</ul>'
            else:
                return line

        #from pprint import pprint
        self.notes = self.notes.strip()
        self.notes = self.notes.split('\r\n')
        self.notes = [wrap_line(l) for l in self.notes]
        self.notes = ''.join(self.notes)

        text =  """<table border="0" cellpadding="10" width="100%"><tr>
                <td style="vertical-align: top;"><img src='{}'></td>
                <td style="text-align: left; vertical-align: top;"><h1 style='color:blue'>{}</h1>
                </tr></table>
                {}<br><br>""".format(':/soosl_update.png', txt, self.notes)
        return text

    ##!!@pyqtSlot()
    def onVisitWebsite(self):
        settings = qApp.instance().getSettings()
        _url = settings.value('Website')
        _url = '{}/software.html'.format(_url)
        b = webbrowser.get()
        b.open(_url, new=1, autoraise=True)
        super(UpdateDlg, self).reject()

    def accept(self):
        self.btnOk.setDisabled(True)
        self.label2.hide()
        self.websiteBtn.hide()
        self.btnNo.setText(qApp.instance().translate('UpdateDlg', 'Cancel update'))
        self.progressBar.show()
        self.label.setText(self.str2)
        qApp.instance().update(self.filename)

    def reject(self):
        qApp.instance().cancelUpdate()
        super(UpdateDlg, self).reject()

    ##!!@pyqtSlot(int)
    def onProgress(self, progress):
        try:
            self.progressBar.setValue(progress)
        except:
            pass
        ## FIXME: seems to be working okay, but...
        ## RuntimeError: wrapped C/C++ object of type QProgressBar has been deleted
        if progress == 100:
            try:
                super(UpdateDlg, self).accept()
            except:
                pass
