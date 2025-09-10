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
import sys
import glob

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QTimer

from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QCursor

from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QToolButton

from validators import FolderNameValidator

class ImportProjectDlg(QDialog):
    """Dialog used when importing a zipped project archive."""

    def __init__(self, import_src, parent=None):
        super(ImportProjectDlg, self).__init__(parent=parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(qApp.instance().translate('ImportProjectDlg', "Import Dictionary (step 2 of 2)"))

        self.import_src = import_src.replace('\\', '/')
        self.project_name, self.project_id, self.project_version, self.project_datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(import_src)
        projects_dir = qApp.instance().getDefaultProjectsDir()
        self.location = projects_dir.replace('\\', '/')
        self.orig_location = projects_dir.replace('\\', '/')
        src_project_dir = qApp.instance().pm.getProjectDirFromImport(import_src)
        src_project_dir = qApp.instance().pm.sooslSlugify(src_project_dir) # in the event that the name is old with mixed case and capitals
        self.replace_flag = False
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(6, 6, 6, 3)
        self.layout.setSpacing(0)

        #widget to show when a project name already exists
        self.exists_label = QLabel()
        self.exists_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.exists_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        h = 2 * (self.fontMetrics().ascent() + self.fontMetrics().lineSpacing())
        self.exists_label.setFixedHeight(h)

        _version = self.project_version
        if not _version:
            _version = '--'
        if self.project_datetime:
            _datetime = qApp.instance().pm.getCurrentDateTimeStr(iso_str=self.project_datetime)
        else:
            _datetime = '--'

        group_box = QGroupBox(' {} '.format(qApp.instance().translate('ImportProjectDlg', 'Import:')))
        group_box.setStyleSheet("""QGroupBox{font-weight:bold;}""")
        group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        vlayout = QVBoxLayout()
        txt = """{} <b>{}</b><br>{} {}<br>{} {}<br>{} {}""".format(qApp.instance().translate('ImportProjectDlg', 'Title:'), self.project_name, qApp.instance().translate('ImportProjectDlg', 'Filename:'), self.import_src, qApp.instance().translate('ImportProjectDlg', 'Version:'), _version, qApp.instance().translate('ImportProjectDlg', 'Modified:'), _datetime)
        label = QLabel(txt)
        label.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vlayout.addWidget(label)
        group_box.setLayout(vlayout)
        self.layout.addWidget(group_box)
        #self.layout.setStretchFactor(group_box, 1)

        changeAction = QAction(QIcon(':/open_file.png'),
            qApp.instance().translate('ImportProjectDlg', 'Change'), self,
            toolTip=qApp.instance().translate('ImportProjectDlg',
            'Change dictionary location'), triggered=self.onLocationBtnClicked)

        ## GRID LAYOUT
        ########################################################
        ## Import to:             ##                          ##
        ## Location  CHANGE       ## Dictionary folder name   ##
        ## parent directory path/ ## [_project folder name_]  ##
        ########################################################
        group_box = QGroupBox(' {} '.format(qApp.instance().translate('ImportProjectDlg', 'Import to:')))
        group_box.setStyleSheet("""QGroupBox{font-weight:bold;}""")
        group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        glayout = QGridLayout()
        glayout.setColumnStretch(1, 1)
        glayout.setVerticalSpacing(1)
        glayout.setHorizontalSpacing(6)

        lbl = QLabel('<i>{}</i>'.format(qApp.instance().translate('ImportProjectDlg', 'Dictionary location:')))
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.change_loc_btn = QToolButton()
        self.change_loc_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.change_loc_btn.setDefaultAction(changeAction)
        self.change_loc_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.change_loc_btn.setCursor(QCursor(Qt.PointingHandCursor))
        glayout.addWidget(lbl, 0, 0)

        lbl = QLabel('<i>{}</i>'.format(qApp.instance().translate('ImportProjectDlg', 'Dictionary folder name:')))
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        glayout.addWidget(lbl, 0, 1)

        self.project_location = QLabel()
        self.project_location.setStyleSheet("color: Blue")
        self.project_location.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.project_location.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.project_location.setText('{}/'.format(self.location))
        glayout.addWidget(self.project_location, 1, 0)

        self.folder_name_edit = QLineEdit()
        validator = FolderNameValidator(self)
        self.waiting_for_valid = False
        validator.invalidChar.connect(self.onInvalidChar)
        validator.intermedChar.connect(self.onIntermedChar)
        validator.validChar.connect(self.onValidChar)
        self.invalid_char_label = QLabel()
        self.invalid_char_label.setFixedHeight(h)
        self.invalid_char_label.setWordWrap(True)
        self.invalid_char_label.setText('')
        self.folder_name_edit.setValidator(validator)
        self.folder_name_edit.textChanged.connect(self.setProjectPath)

        glayout.addWidget(self.folder_name_edit, 1, 1)
        glayout.addWidget(self.invalid_char_label, 2, 1)
        glayout.addWidget(self.change_loc_btn, 2, 0)

        self.replace_checkbox = QCheckBox(qApp.instance().translate('ImportProjectDlg', 'Replace'))
        self.replace_checkbox.setFixedHeight(h)
        self.replace_checkbox.hide()
        self.replace_checkbox.toggled.connect(self.onReplace)

        glayout.addWidget(self.replace_checkbox, 2, 1)
        group_box.setLayout(glayout)
        self.layout.addWidget(group_box)
        #self.layout.setStretchFactor(group_box, 1)

        self.layout.addWidget(self.exists_label)
        self.layout.addStretch()

        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('ImportProjectDlg', 'Ok'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('ImportProjectDlg', 'Cancel'))

        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)

        self.back = False
        tip = '{}\n({})'.format(qApp.instance().translate('ImportProjectDlg', 'Go back to previous file dialog'), qApp.instance().translate('ImportProjectDlg', 'choose different .zoozl file'))
        backAction = QAction(QIcon(':back_arrow.png'), qApp.instance().translate('ImportProjectDlg', 'Back'), self, toolTip=tip, triggered=self.onBack)
        btnLayout = QHBoxLayout()
        back_btn = QToolButton()
        back_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        #back_btn.setArrowType(Qt.LeftArrow)
        back_btn.setDefaultAction(backAction)
        back_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        #back_btn.setStyleSheet('vertical-align: top;')
        back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        btnLayout.addWidget(back_btn)
        btnLayout.addStretch()
        btnLayout.addWidget(self.btnBox)
        self.layout.addLayout(btnLayout)

        self.setLayout(self.layout)
        self.setMinimumSize(350, 230)
        self.btnBox.button(QDialogButtonBox.Ok).setFocus(True)
        self.change_allowed = False

        self.folder_name_edit.setText(src_project_dir)

    def onBack(self):
        self.back = True
        self.reject()

    def onInvalidChar(self, message_str, move_cursor=False):
        if not message_str:
            self.invalid_char_label.setText('')
            if self.exists_label.isVisible():
                self.replace_checkbox.show()
        else:
            text = "<p style='color:red'><b>{}</b></p>".format(message_str)
            self.invalid_char_label.setText(text)
            self.replace_checkbox.hide()
        def move():
            pos = self.folder_name_edit.cursorPosition() + 1
            self.folder_name_edit.setCursorPosition(pos)
        # when checking for duplicate characters in validator, if cursor is 'before' second character I want to move it 'after'
        # following validation; can't seem to do this in the validator since it is an 'invalid' state, so do it here. Also, validator
        # does seem to set the cursor position, so need to make the move after the validator has done its work.
        if move_cursor:
            QTimer.singleShot(0, move)

    def onIntermedChar(self, message_str):
        if not message_str: # 'space' character
            self.invalid_char_label.setText('')
            if self.exists_label.isVisible():
                self.replace_checkbox.show()
        else:
            text = "<p style='color:purple'><b>{}</b></p>".format(message_str)
            self.invalid_char_label.setText(text)
            self.replace_checkbox.hide()
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.waiting_for_valid = True

    def onValidChar(self):
        self.waiting_for_valid = False

    def setProjectPath(self, txt):
        self.project_path = '{0}/{0}.json'.format(txt)
        self.ifExistingProjects()

    def sizeHint(self):
        screen = qApp.screenAt(self.pos())
        if screen:
            s = screen.availableSize()
            w = s.width() * 0.4
            h = s.height() * 0.5
            return QSize(int(w), int(h))
        return QSize(500, 600)

    def hideEvent(self, evt):
        qApp.processEvents()
        super(ImportProjectDlg, self).hideEvent(evt)

    def ifExistingProjects(self):
        src_project_dir = os.path.dirname(self.project_path)
        dst_project_path = '{0}/{1}/{1}.json'.format(self.location, src_project_dir)
        existing_projects = None
        project_path = ''
        project_list = qApp.instance().pm.getProjectList(self.location)
        existing_projects = [p for p in project_list if self.project_id == qApp.instance().pm.getProjectId(p)]
        if not self.folder_name_edit.text():
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.exists_label.setText('')
        elif os.path.exists(dst_project_path):
            msg1 = qApp.instance().translate('ImportProjectDlg', 'This Dictionary already exists in this destination directory.')
            msg2 = qApp.instance().translate('ImportProjectDlg', "Change location, dictionary folder name, or replace.")
            msg = "<b style='color:red'>{}<br>{}</b><br>".format(msg1, msg2)
            self.exists_label.setText(msg)
            self.replace_checkbox.setDisabled(False)
            self.replace_checkbox.show()
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
            # compare project id's as you cannot overwrite if different
            dst_project_id = qApp.instance().pm.getProjectId(dst_project_path)
            if self.project_id != dst_project_id:
                self.replace_checkbox.hide()
                self.invalid_char_label.setText('<div style="color:red;">{}</div>'.format(qApp.instance().translate('ImportProjectDlg', 'Cannot replace - Project IDs differ.')))
        else:
            if not self.invalid_char_label.text():
                self.exists_label.setText('')
                self.replace_checkbox.hide()
                self.replace_checkbox.setChecked(False)
                self.btnBox.button(QDialogButtonBox.Ok).setEnabled(True)
            else:
                self.replace_checkbox.setDisabled(True)

    def onLocationDirEntered(self, _dir):
        dlg = self.sender()

    def onReplace(self):
        check = self.sender()
        if check.isChecked():
            self.replace_flag = True
            self.folder_name_edit.setDisabled(True)
            self.btnBox.button(QDialogButtonBox.Ok).setDisabled(False)
            self.exists_label.hide()
        else:
            self.replace_flag = False
            self.folder_name_edit.setDisabled(False)
            self.btnBox.button(QDialogButtonBox.Ok).setDisabled(True)
            self.exists_label.show()

    ##!!@pyqtSlot()
    def onLocationBtnClicked(self):
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
        mw = qApp.instance().getMainWindow()
        dlg = mw.soosl_file_dlg
        dlg.setupForChangeProjectLocation()
        # dlg.show()
        # dlg.raise_()
        qApp.processEvents()

        if dlg.exec_():
            self.location = dlg.selected_path.replace('\\', '/')
            self.project_location.setText('{}/'.format(self.location))
            self.ifExistingProjects()