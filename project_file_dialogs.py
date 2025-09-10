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
from os.path import basename
import sys
import re
import time
import glob
#import uritools
#import locale
from enum import Enum
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QTimer

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QFileSystemModel
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QButtonGroup
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QDialogButtonBox

from validators import FileNameValidator

class DialogType(Enum):
    OPEN_PROJECT = 1
    IMPORT_PROJECT = 2
    EXPORT_PROJECT = 3
    DELETE_PROJECTS = 4
    VIDEO_FILE = 5
    PICTURE_FILE = 6
    MEDIA_FILE = 7
    PROJECT_LOCATION = 8

PROJECT_NAME_COL = 0
FILE_NAME_COL = 1
VERSION_COL = 2
SIZE_COL = 3
DATE_COL = 4

class SooSLFileDialog(QDialog):
    def __init__(self, parent=None):
        super(SooSLFileDialog, self).__init__(parent)
        self.extensions = []
        self.prev_dialog_type = None
        self.dialog_type = None
        self.current_dir = qApp.instance().getDefaultProjectsDir()
        self.directory_history = []
        self.history_idx = -1
        self.selected_path = None
        self.path_dict = {}
        self.sidebar_dirs = []
        self.zoozl_name = None
        self.suggested_zoozl_name = None
        self.waiting_for_valid = False
        # if self.sidebar_dirs:
        #     filters=QDir.Dirs|QDir.NoDotAndDotDot
        #     if self.importing or self.exporting:
        #         filters=QDir.Files
        #     self.sidebar_dirs = [d for d in self.sidebar_dirs if len(QDir(d).entryList(filters)) > 0]

        settings = qApp.instance().getSettings()
        #qApp.instance().logStartup('...getting file system model')
        self.model = QFileSystemModel()

        layout = QVBoxLayout()
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(5)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(3, 3, 3, 3)
        hlayout.setSpacing(3)

        self.lookin_lbl = QLabel()
        self.lookin_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hlayout.addWidget(self.lookin_lbl)

        self.directoryCombo = QComboBox()
        self.directoryCombo.setEditable(True)
        self.directoryCombo.currentTextChanged.connect(self.onComboTextChanged)
        self.directoryCombo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hlayout.addWidget(self.directoryCombo)
        hlayout.setStretchFactor(self.directoryCombo, 1)

        icon = QIcon(':/back_arrow.png')
        icon.addFile(':/back_arrow_disabled.png', mode=QIcon.Disabled)
        self.back_btn = QPushButton(icon, '')
        self.back_btn.setDisabled(True)

        icon = QIcon(':/forward_arrow.png')
        #icon.addFile(':/forward_arrow_disabled.png', mode=QIcon.Disabled)
        self.forward_btn = QPushButton(icon, '')
        self.forward_btn.setDisabled(True)

        icon = QIcon(':/up_arrow.png')
        icon.addFile(':/up_arrow_disabled.png', mode=QIcon.Disabled)
        self.up_btn = QPushButton(icon, '')

        for btn in [self.back_btn, self.forward_btn, self.up_btn]:
            btn.setFlat(True)
            btn.setFixedSize(QSize(18, 18))
            btn.pressed.connect(self.onChangeDirectoryButton)
            hlayout.addWidget(btn)

        hlayout.addSpacing(18)

        self.list_btn = QRadioButton()
        self.list_btn.setStyleSheet('QRadioButton:indicator:checked{image: url(":/detail_view_checked.png")} \
            QRadioButton:indicator:unchecked{image: url(":/detail_view_unchecked.png")}')
        self.list_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.list_btn.setToolTip(qApp.instance().translate('SooSLFileDialog', 'List View'))
        self.list_btn.toggled.connect(self.changeDirectoryView)
        hlayout.addWidget(self.list_btn)

        self.detail_btn = QRadioButton()
        self.detail_btn.setStyleSheet('QRadioButton:indicator:checked{image: url(":/list_view_checked.png")} \
            QRadioButton:indicator:unchecked{image: url(":/list_view_unchecked.png")}')
        self.detail_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.detail_btn.setToolTip(qApp.instance().translate('SooSLFileDialog', 'Detail View'))
        self.detail_btn.toggled.connect(self.changeDirectoryView)
        hlayout.addWidget(self.detail_btn)

        layout.addLayout(hlayout)

        self.splitter = QSplitter(self)
        self.splitter.setChildrenCollapsible(False)

        self.sidebar = QListWidget(self)
        self.sidebar.setItemDelegate(SidebarItemDelegate(self.sidebar))
        self.sidebar.setUniformItemSizes(True)

        self.directoryTable = QTableWidget(self)
        self.directoryTable.setTabKeyNavigation(False)
        self.directoryTable.horizontalHeader().setStyleSheet('QHeaderView::section{font-weight:bold;}')
        self.directoryTable.setShowGrid(False)
        self.directoryTable.setEditTriggers(QTableWidget.NoEditTriggers)
        #self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
        self.directoryTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.directoryTable.setColumnCount(5)
        self.directoryTable.verticalHeader().hide()
        self.directoryTable.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.directoryTable.horizontalHeader().setStretchLastSection(True)
        self.directoryTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.directoryTable.setItemDelegate(ProjectItemDelegate(self))
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.directoryTable)
        layout.addWidget(self.splitter)
        layout.setStretchFactor(self.splitter, 1)

        self.filename_layout = QGridLayout()
        self.filename_layout.setContentsMargins(0, 0, 0, 0)
        self.filename_lbl = QLabel()
        self.filename_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.filename_layout.addWidget(self.filename_lbl, 0, 0)
        self.dict_line_edit = QLineEdit()
        self.dict_line_edit.textChanged.connect(self.onTextChanged)
        self.dict_line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.filename_layout.addWidget(self.dict_line_edit, 0, 1)
        layout.addLayout(self.filename_layout)

        self.footer_layout = QGridLayout()
        # self.filename_lbl = QLabel()
        # self.filename_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # self.footer_layout.addWidget(self.filename_lbl, 0, 0)
        # self.dict_line_edit = QLineEdit()
        # self.dict_line_edit.textChanged.connect(self.onTextChanged)
        # self.dict_line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # self.footer_layout.addWidget(self.dict_line_edit, 0, 1)

        btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        #btnBox.setOrientation(Qt.Vertical)
        btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('SooSLFileDialog', 'Ok'))
        btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('SooSLFileDialog', 'Cancel'))
        btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        self.ok_btn = btnBox.button(QDialogButtonBox.Ok)
        self.cancel_btn = btnBox.button(QDialogButtonBox.Cancel)

        #self.ok_btn.setStyleSheet("""QPushButton:!focus{border: 1px solid grey; background: lightgray;}""")
        self.ok_btn.setDisabled(True)
        self.ok_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        #self.ok_btn.pressed.connect(self.accept)
        #self.footer_layout.addWidget(self.ok_btn, 0, 2)
        self.footer_layout.addWidget(btnBox, 2, 2, alignment=Qt.AlignRight|Qt.AlignBottom)

        txt = '<br>{}  <br>{}  <br>{}  '.format(qApp.instance().translate('SooSLFileDialog', 'Title:'), qApp.instance().translate('SooSLFileDialog', 'Version:'), qApp.instance().translate('SooSLFileDialog', 'Modified:'))
        self.file_info_labels_lbl = QLabel(txt)
        self.file_info_labels_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.file_info_labels_lbl.hide()
        self.file_info_labels_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.footer_layout.addWidget(self.file_info_labels_lbl, 1, 0)

        self.file_info_layout = QHBoxLayout() # use layout here so other widgets may be added from Export dlg
        self.file_info_layout.setContentsMargins(0, 0, 0, 0)
        self.file_info_layout.setSpacing(0)
        self.file_info_lbl = QLabel()
        self.file_info_lbl.hide()
        self.file_info_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_info_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.file_info_layout.addWidget(self.file_info_lbl)
        #self.file_info_layout.addStretch()
        self.footer_layout.addLayout(self.file_info_layout, 1, 1, 1, 2)

        self.filetype_lbl = QLabel('{}  '.format(qApp.instance().translate('SooSLFileDialog', 'Files of type:')))
        self.filetype_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.footer_layout.addWidget(self.filetype_lbl, 1, 0, alignment=Qt.AlignTop)

        self.filetype_combo = QComboBox()
        self.filetype_combo_current_text = None
        self.filetype_combo_texts = []
        self.filetype_combo.setEditable(False)
        self.filetype_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # self.filetype_combo.currentTextChanged.connect(self.onFileTypeChanged)
        self.footer_layout.addWidget(self.filetype_combo, 1, 1, alignment=Qt.AlignTop)

        self.full_path_label = QLabel()
        self.full_path_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.footer_layout.addWidget(self.full_path_label, 2, 1)
        self.full_path_label.hide()

        # self.cancel_btn = QPushButton(qApp.instance().translate('SooSLFileDialog', 'Cancel'))
        # self.cancel_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # self.cancel_btn.clicked.connect(self.reject)
        # self.footer_layout.addWidget(self.cancel_btn, 1, 2, alignment=Qt.AlignTop)
        layout.addLayout(self.footer_layout)
        self.setLayout(layout)
        ##qApp.instance().logStartup('...setup sidebar')
        self.sidebar.itemSelectionChanged.connect(self.onSidebarItemSelected)
        self.directoryTable.itemSelectionChanged.connect(self.onDirectoryTableSelectionChanged)
        self.directoryTable.itemDoubleClicked.connect(self.onDirectoryTableItemDClicked)

        #self.setViewMode()

        self.splitter.handle(1).installEventFilter(self)
        width = int(settings.value('openProjectSidebarWidth', 150))
        self.sidebar.setFixedWidth(width)
        self.directoryTable.setMinimumWidth(20)

    def showFileType(self, _bool):
        self.filetype_lbl.setVisible(_bool)
        self.filetype_combo.setVisible(_bool)

    def setTabOrders(self):
        self.setTabOrder(self.directoryCombo, self.back_btn)
        self.setTabOrder(self.back_btn, self.forward_btn)
        self.setTabOrder(self.forward_btn, self.up_btn)
        self.setTabOrder(self.up_btn, self.list_btn)
        self.setTabOrder(self.list_btn, self.detail_btn)
        self.setTabOrder(self.detail_btn, self.sidebar)
        self.setTabOrder(self.sidebar, self.directoryTable)
        self.setTabOrder(self.directoryTable, self.dict_line_edit)
        self.setTabOrder(self.dict_line_edit, self.ok_btn)
        self.setTabOrder(self.ok_btn, self.cancel_btn)
        self.setTabOrder(self.cancel_btn, self.directoryCombo)

    def setViewMode(self):
        if self.dialog_type:
            settings = qApp.instance().getSettings()
            value = 'SooSLFileDialogViewMode/{}'.format(self.dialog_type)
            self.view_mode = int(settings.value(value, QFileDialog.List))
            if self.view_mode == QFileDialog.List:
                self.list_btn.toggle()
                self.showListView()
            else:
                self.detail_btn.toggle()
                self.showDetailedView()

    def projects(self):
        projects = []
        items = self.directoryTable.selectedItems()
        for item in items:
            filename = item.data(Qt.UserRole)
            if filename:
                dictionary_name = item.data(Qt.DisplayRole)
                projects.append((dictionary_name, filename))
        return projects

    def selectInitialSidebarItem(self):
        settings = qApp.instance().getSettings()
        item_count = self.sidebar.count()
        last_directory=None
        if self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT]:
            default = qApp.instance().getDefaultImportExportDirs()[0]
            last_directory = settings.value('lastImportExportDir', default)
        elif self.dialog_type in [DialogType.VIDEO_FILE, DialogType.PICTURE_FILE, DialogType.MEDIA_FILE]:
            home_dir = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
            last_directory = settings.value('lastMediaDir', home_dir)
        else: # open project, delete project, project location dialog types
            last_project = settings.value('lastOpenedDatabase', None)
            last_directory = qApp.instance().getDefaultProjectsDir()
            if last_project:
                last_directory = os.path.dirname(os.path.dirname(last_project))

        if qApp.instance().startup_widget and qApp.instance().startup_widget.isVisible():
            _dir = qApp.instance().startup_widget.project_dir
        elif last_directory and os.path.exists(last_directory):
            _dir = last_directory
        elif self.sidebar_dirs:
            _dir = self.sidebar_dirs[0]

        items = [self.sidebar.item(x) for x in range(item_count) if self.sidebar.item(x).data(Qt.UserRole) == _dir]
        if items:
            i = items[0]
            self.sidebar.setCurrentItem(i)

    def setDlgGeometry(self):
        #if self.dialog_type is DialogType.OPEN_PROJECT:
        value1 = 'openProjectDlgGeometry'
        value2 = 'openProjectDlgSplitterState'
        if self.dialog_type is DialogType.IMPORT_PROJECT:
            value1 = 'importProjectDlgGeometry'
            value2 = 'importProjectDlgSplitterState'
        elif self.dialog_type is DialogType.EXPORT_PROJECT:
            value1 = 'exportProjectDlgGeometry'
            value2 = 'exportProjectDlgSplitterState'
        elif self.dialog_type is DialogType.DELETE_PROJECTS:
            value1 = 'deleteProjectDlgGeometry'
            value2 = 'deleteProjectDlgSplitterState'

        settings = qApp.instance().getSettings()
        #qApp.instance().logStartup('...setting dialog geometry')
        geom = settings.value(value1, None)
        if geom:
            self.setGeometry(geom)
        else:
            pass
        try:
            split = settings.value(value2, QByteArray())
            if split:
                self.splitter.restoreState(split)
        except:
            pass # old project dlg has not this

    def setupForMergeComparison(self, _type):
        if _type == 'project':
            self.setupForOpenProject()
        elif _type == 'zoozl':
            self.setupForImporting()

    def setupForOpenProject(self):
        #if self.dialog_type is not DialogType.OPEN_PROJECT:
        header_lbls = [qApp.instance().translate('SooSLFileDialog', 'Dictionary title'), qApp.instance().translate('SooSLFileDialog', 'Project filename'), qApp.instance().translate('SooSLFileDialog', 'Project version'), qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
        self.directoryTable.setHorizontalHeaderLabels(header_lbls)
        self.dialog_type = DialogType.OPEN_PROJECT
        self.extensions = ['.json', '.sqlite', '.sqlite.enc', '.zoozl']
        self.directoryTable.showColumn(PROJECT_NAME_COL)
        self.directoryTable.showColumn(VERSION_COL)
        self.sidebar_dirs = qApp.instance().pm.getProjectLocations()
        self.setWindowTitle(qApp.instance().translate('SooSLFileDialog', "Open Dictionary"))
        self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
        self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', "Dictionary's main file:"))
        t = qApp.instance().translate('SooSLFileDialog', 'SooSL dictionary')
        txt = f'{t} (*.json, *.sqlite, *.sqlite.enc, *.zoozl)'
        self.filetype_combo.clear()
        self.filetype_combo.addItem(txt)
        self.filetype_lbl.show()
        self.filetype_combo.show()
        self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
        self.directoryTable.setStyleSheet(None)
        self.setupSidebar()
        self.setOkBtnText()
        self.setDlgGeometry()
        self.setViewMode()
        self.full_path_label.hide()
        self.showFileType(False)

        # existing dictionary name
        self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
        self.dict_line_edit.setReadOnly(True)
        self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForImporting(self):
        #if self.dialog_type is not DialogType.IMPORT_PROJECT:
        self.dialog_type = DialogType.IMPORT_PROJECT
        header_lbls = [qApp.instance().translate('SooSLFileDialog', 'Dictionary title'), qApp.instance().translate('SooSLFileDialog', 'ZooZL file name'), qApp.instance().translate('SooSLFileDialog', 'Project version'), qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
        self.directoryTable.setHorizontalHeaderLabels(header_lbls)
        self.extensions = ['.zoozl']
        self.directoryTable.showColumn(PROJECT_NAME_COL)
        self.directoryTable.showColumn(VERSION_COL)
        self.sidebar_dirs = qApp.instance().pm.getExportLocations()
        self.setWindowTitle(qApp.instance().translate('SooSLFileDialog', "Import Dictionary - Choose ZooZL file to Import (step 1 of 2)"))
        self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Import from:')))
        self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', 'ZooZL file:'))
        txt = '{} (*.zoozl)'.format(qApp.instance().translate('SooSLFileDialog', 'SooSL archive'))
        self.filetype_combo.clear()
        self.filetype_combo.addItem(txt)
        self.filetype_lbl.show()
        self.filetype_combo.show()
        self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
        self.directoryTable.setStyleSheet(None)
        self.setupSidebar()
        self.setOkBtnText()
        self.setDlgGeometry()
        self.setViewMode()
        self.full_path_label.hide()
        self.showFileType(False)

        #existing import name
        self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
        self.dict_line_edit.setReadOnly(True)
        self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForExporting(self):
        #if self.dialog_type is not DialogType.EXPORT_PROJECT:
        self.dialog_type = DialogType.EXPORT_PROJECT
        header_lbls = [qApp.instance().translate('SooSLFileDialog', 'Dictionary title'), qApp.instance().translate('SooSLFileDialog', 'ZooZL file name'), qApp.instance().translate('SooSLFileDialog', 'Project version'), qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
        self.directoryTable.setHorizontalHeaderLabels(header_lbls)
        self.extensions = ['.zoozl']
        self.directoryTable.showColumn(PROJECT_NAME_COL)
        self.directoryTable.showColumn(VERSION_COL)
        self.sidebar_dirs = qApp.instance().pm.getExportLocations()
        title = qApp.instance().translate('SooSLFileDialog', "Export Current Dictionary")
        self.setWindowTitle(title)
        self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Export to:')))
        self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', 'ZooZL file:'))
        txt = '{} (*.zoozl)'.format(qApp.instance().translate('SooSLFileDialog', 'SooSL archive'))
        self.filetype_combo.clear()
        self.filetype_combo.addItem(txt)
        self.filetype_lbl.show()
        self.filetype_combo.show()
        self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
        self.directoryTable.setStyleSheet(None)
        self.setupSidebar()
        self.setOkBtnText()
        self.setDlgGeometry()
        self.setViewMode()
        self.showFileType(False)

        # destination filename can be changed
        self.full_path_label.hide()
        self.dict_line_edit.setReadOnly(False)
        self.dict_line_edit.setFocusPolicy(Qt.StrongFocus)

    def setupForVideoFiles(self, title, media_dir):
        #if self.dialog_type is not DialogType.VIDEO_FILE:
        self.dialog_type = DialogType.VIDEO_FILE
        header_lbls = ['', qApp.instance().translate('SooSLFileDialog', 'Name'), '', qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
        self.sidebar_dirs = qApp.instance().pm.getProjectLocations()
        self.sidebar_dirs.append(media_dir)
        self.directoryTable.setHorizontalHeaderLabels(header_lbls)
        self.extensions = qApp.instance().pm.video_extensions

        self.setWindowTitle(title)
        self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
        self.filename_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "File name:")))
        self.filetype_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "Files of type:")))
        self.filetype_lbl.show()
        self.filetype_combo.show()
        self.filetype_combo.clear()
        self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Video files'))
        self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
        self.directoryTable.setStyleSheet(None)
        self.directoryTable.hideColumn(PROJECT_NAME_COL)
        self.directoryTable.hideColumn(VERSION_COL)
        self.setupSidebar()
        #self.setupProjectTable(media_dir)
        self.setOkBtnText()
        self.setDlgGeometry()
        self.setViewMode()
        self.full_path_label.hide()
        self.showFileType(True)

        #existing file only
        self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
        self.dict_line_edit.setReadOnly(True)
        self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForProjectLogo(self, title, media_dir):
        if self.dialog_type is not DialogType.PICTURE_FILE:
            self.dialog_type = DialogType.PICTURE_FILE
            header_lbls = ['', qApp.instance().translate('SooSLFileDialog', 'Name'), '', qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
            self.sidebar_dirs = qApp.instance().pm.getProjectLocations()
            self.sidebar_dirs.append(media_dir)
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.extensions = qApp.instance().pm.picture_extensions
            self.setWindowTitle(title)
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
            self.filename_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "File name:")))
            self.filetype_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "Files of type:")))
            self.filetype_combo.clear()
            # self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Video and Picture files'))
            # self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Video files'))
            self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Picture files'))
            self.filetype_lbl.show()
            self.filetype_combo.show()
            self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
            self.directoryTable.setStyleSheet(None)
            self.setupSidebar()
            #self.setupProjectTable(media_dir)
            self.setOkBtnText()
            self.setDlgGeometry()
            self.setViewMode()
            self.directoryTable.hideColumn(PROJECT_NAME_COL)
            self.directoryTable.hideColumn(VERSION_COL)
            self.full_path_label.hide()
            self.showFileType(True)

            # existing files only
            self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
            self.dict_line_edit.setReadOnly(True)
            self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForAllMedia(self, title, media_dir):
        if self.dialog_type is not DialogType.MEDIA_FILE:
            self.dialog_type = DialogType.MEDIA_FILE
            header_lbls = ['', qApp.instance().translate('SooSLFileDialog', 'Name'), '', qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
            self.sidebar_dirs = qApp.instance().pm.getProjectLocations()
            self.sidebar_dirs.append(media_dir)
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.extensions = qApp.instance().pm.media_extensions
            self.setWindowTitle(title)
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
            self.filename_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "File name:")))
            self.filetype_lbl.setText('{}  '.format(qApp.instance().translate('SooSLFileDialog', "Files of type:")))
            self.filetype_combo.clear()
            self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Video and Picture files'))
            # self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Video files'))
            # self.filetype_combo.addItem(qApp.instance().translate('SooSLFileDialog', 'Picture files'))
            self.filetype_lbl.show()
            self.filetype_combo.show()
            self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
            self.directoryTable.setStyleSheet(None)
            self.setupSidebar()
            #self.setupProjectTable(media_dir)
            self.setOkBtnText()
            self.setDlgGeometry()
            self.setViewMode()
            self.directoryTable.hideColumn(PROJECT_NAME_COL)
            self.directoryTable.hideColumn(VERSION_COL)
            self.full_path_label.hide()
            self.showFileType(True)

            # existing files only
            self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
            self.dict_line_edit.setReadOnly(True)
            self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForDeleting(self):
        if self.dialog_type is not DialogType.DELETE_PROJECTS:
            self.dialog_type = DialogType.DELETE_PROJECTS
            header_lbls = [qApp.instance().translate('SooSLFileDialog', 'Dictionary title'), qApp.instance().translate('SooSLFileDialog', 'Project filename'), qApp.instance().translate('SooSLFileDialog', 'Project version'), qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.extensions = ['.json', '.sqlite', '.sqlite.enc']
            self.sidebar_dirs = qApp.instance().pm.getProjectLocations()
            self.setWindowTitle(qApp.instance().translate('SooSLFileDialog', "Delete Dictionaries"))
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
            self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', "Dictionary's main file:"))
            txt = '{} (*.json, *.sqlite, *.sqlite.enc)'.format(qApp.instance().translate('SooSLFileDialog', 'SooSL dictionary'))
            self.filetype_combo.clear()
            self.filetype_combo.addItem(txt)
            self.filetype_lbl.show()
            self.filetype_combo.show()
            self.directoryTable.showColumn(PROJECT_NAME_COL)
            self.directoryTable.showColumn(VERSION_COL)
            self.directoryTable.setSelectionMode(QTableWidget.MultiSelection)
            self.directoryTable.setStyleSheet("QTableView::item:selected {color:white; background-color:red;}")
            self.setupSidebar()
            self.setOkBtnText()
            self.setDlgGeometry()
            self.setViewMode()

            self.full_path_label.hide()
            self.showFileType(False)

            # existing files only
            self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
            self.dict_line_edit.setReadOnly(True)
            self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def setupForChangeProjectLocation(self):
        if self.dialog_type is not DialogType.PROJECT_LOCATION:
            self.dialog_type = DialogType.PROJECT_LOCATION
            header_lbls = ['', qApp.instance().translate('SooSLFileDialog', 'Name'), '', qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.setWindowTitle(qApp.instance().translate('SooSLFileDialog', "Choose Dictionary Location (parent folder)"))
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
            self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', 'Dictionary location (parent folder):'))
            self.filetype_lbl.hide()
            self.filetype_combo.clear()
            self.filetype_combo.hide()
            self.extensions = []
            self.directoryTable.hideColumn(PROJECT_NAME_COL)
            self.directoryTable.hideColumn(VERSION_COL)
            self.setupSidebar()
            self.setOkBtnText()
            self.setDlgGeometry()
            self.setViewMode()
            self.full_path_label.show()
            self.showFileType(False)

            # existing directories only
            self.dict_line_edit.setFocusPolicy(Qt.NoFocus)
            self.dict_line_edit.setReadOnly(True)
            self.dict_line_edit.setStyleSheet('border: none; font-weight: bold; background-color: palette(button);')

    def onChangeDirectoryButton(self):
        btn = self.sender()
        if btn is self.up_btn:
            dir = os.path.dirname(self.current_dir)
            self.setupProjectTable(dir)
            self.setHistory(dir)
        elif btn is self.forward_btn and self.directory_history:
            self.history_idx += 1
            dir = self.directory_history[self.history_idx]
            self.setupProjectTable(dir)
            if self.history_idx == len(self.directory_history) - 1:
                self.forward_btn.setDisabled(True)
            self.back_btn.setDisabled(False)
        elif btn is self.back_btn and self.directory_history:
            if self.history_idx < 0: #initial idx before use
                self.history_idx = len(self.directory_history) - 1 #last idx
            self.history_idx -= 1
            dir = self.directory_history[self.history_idx]
            self.setupProjectTable(dir)
            self.forward_btn.setEnabled(True)
            if self.history_idx == 0:
                self.back_btn.setDisabled(True)

    def eventFilter(self, obj, evt): #obj == splitter handle
        if evt.type() == QEvent.MouseButtonPress:
            pos = obj.pos().x()
            self.sidebar.setMinimumWidth(20)
            self.sidebar.setMaximumWidth(self.splitter.width() - 20)
            self.splitter.moveSplitter(int(pos), 1)
            return True
        elif evt.type() == QEvent.MouseButtonRelease:
            w = obj.pos().x()
            self.sidebar.setFixedWidth(w)
            self.directoryTable.setMinimumWidth(20)
            settings = qApp.instance().getSettings()
            settings.setValue('openProjectSidebarWidth', w)
            return True
        return super(SooSLFileDialog, self).eventFilter(obj, evt)

    def hideEvent(self, evt):
        #if self.dialog_type is DialogType.OPEN_PROJECT:
        value1 = 'openProjectDlgGeometry'
        value2 = 'openProjectDlgSplitterState'
        if self.dialog_type is DialogType.IMPORT_PROJECT:
            value1 = 'importProjectDlgGeometry'
            value2 = 'importProjectDlgSplitterState'
        elif self.dialog_type is DialogType.EXPORT_PROJECT:
            value1 = 'exportProjectDlgGeometry'
            value2 = 'exportProjectDlgSplitterState'
        elif self.dialog_type is DialogType.DELETE_PROJECTS:
            value1 = 'deleteProjectDlgGeometry'
            value2 = 'deleteProjectDlgSplitterState'

        settings = qApp.instance().getSettings()
        settings.setValue(value1, self.geometry())
        try:
            settings.setValue(value2, self.splitter.saveState())
        except:
            pass # old project dlg

        settings.sync()
        super(SooSLFileDialog, self).hideEvent(evt)
        self.clearHistory()
        self.prev_dialog_type = self.dialog_type
        self.hideProjectInfoLabel()

    def showEvent(self, evt):
        qApp.processEvents()
        super(SooSLFileDialog, self).showEvent(evt)

        self.zoozl_name = None
        self.current_project_row = -1
        #if self.dialog_type is DialogType.DELETE_PROJECTS:
        self.directoryTable.clearContents()
        self.selected_path = None
        self.waiting_for_valid = False
        self.clearProjectInfoLabel()
        if self.dialog_type in [DialogType.OPEN_PROJECT, DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT]: #, DialogType.DELETE_PROJECTS ]:
            if not self.file_info_lbl.isVisible():
                self.showProjectInfoLabel()
        else:
            self.hideProjectInfoLabel()
        self.setupSidebar()
        if self.dialog_type is not DialogType.EXPORT_PROJECT:
            self.dict_line_edit.clear()
        self.setTabOrders()

    def validPath(self, text):
        # takes a text string and determines if it is a valid path to a project file or directory;
        # return the valid path if so, None if not.
        # text could be input by direct typing or by selecting an entry in the directory_table
        #print('URI', uritools.urisplit(text))
        if text:
            txt = text #self.cleanupPath(text)
            txt = qApp.instance().pm.lowerExt(txt) # ensure any comparisons are case insensitive
            # case where user has selected one of the projects directly from the directory table
            # basename of existing dictionary file in current directory
            if self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT] and txt.endswith('.zoozl'): #import archive
                pth = os.path.join(self.current_dir, txt)
                return pth ##'{}/{}'.format(self.current_dir, txt)
            elif self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT]: # and not txt.endswith('.zoozl'): #os.path.splitext(txt)[1]:
                pth = os.path.join(self.current_dir, '{}{}'.format(txt, '.zoozl'))
                if os.path.exists(pth):
                    return pth ##'{}/{}'.format(self.current_dir, txt)
                if self.dialog_type is DialogType.EXPORT_PROJECT:
                    return pth

            ##project_dir = '{}/{}'.format(self.current_dir, os.path.splitext(txt)[0])
            elif self.dialog_type is DialogType.OPEN_PROJECT:
                _dir, _ext = (txt, '')
                if txt.endswith('.json') or txt.endswith('.sqlite'):
                    _dir, _ext = os.path.splitext(txt)
                elif txt.endswith('.sqlite.enc'):
                    _dir = txt.replace('.sqlite.enc', '') # very old project file
                    _ext = '.sqlite.enc'

                project_dir = os.path.join(self.current_dir, _dir)
                ##project = '{}/{}'.format(project_dir, txt)
                pth = os.path.join(project_dir, txt)
                if _ext:
                    if os.path.isfile(pth):
                        return pth
                else:
                    pth = os.path.join(project_dir, '{}.json'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
                    pth = os.path.join(project_dir, '{}.sqlite'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
                    pth = os.path.join(project_dir, '{}.sqlite.enc'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
            elif self.dialog_type is DialogType.DELETE_PROJECTS:
                _dir, _ext = (txt, '')
                if txt.endswith('.json') or txt.endswith('.sqlite'):
                    _dir, _ext = os.path.splitext(txt)
                elif txt.endswith('.sqlite.enc'):
                    _dir = txt.replace('.sqlite.enc', '') # very old project file
                    _ext = '.sqlite.enc'

                project_dir = os.path.join(self.current_dir, _dir)
                ##project = '{}/{}'.format(project_dir, txt)
                pth = os.path.join(project_dir, txt)
                if _ext:
                    if os.path.isfile(pth):
                        return pth
                else:
                    pth = os.path.join(project_dir, '{}.json'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
                    pth = os.path.join(project_dir, '{}.sqlite'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
                    pth = os.path.join(project_dir, '{}.sqlite.enc'.format(_dir))
                    if os.path.isfile(pth):
                        return pth
            else: #just check for an existing path in current directory
                pth = os.path.join(self.current_dir, txt)
                if self.selectInTable(pth):
                    return pth
        return None

    def realPath(self, _path):
        #pth = self.canonicalPath(_path)
        pth = QDir(_path).canonicalPath()
        if pth is None: # or not self.isReadable(pth):
            return ''
        return QDir.cleanPath(pth)

    def isReadable(self, pth):
        if pth:
            _bool = QDir(pth).isReadable()
        else:
            _bool = False
        return _bool

    def onDirectoryTableItemDClicked(self, item):
        items = self.directoryTable.selectedItems()
        if items:
            col = 0
            item = items[col]
            data = item.data(Qt.UserRole)
            if not data:
                data = item.data(Qt.DisplayRole)
                if data:
                    pth = os.path.join(self.current_dir, data)
                    pth = self.realPath(pth)
                    if os.path.isdir(pth):
                        self.setupProjectTable(pth)
                        self.setHistory(pth)
                    else:
                        self.accept()
            else:
                self.accept()

    def changeDirectoryView(self):
        btn = self.sender()
        settings = qApp.instance().getSettings()
        if btn.isChecked():
            if btn is self.list_btn:
                self.view_mode = QFileDialog.List
                self.showListView()
            else:
                self.view_mode = QFileDialog.Detail
                self.showDetailedView()
            value = 'SooSLFileDialogViewMode/{}'.format(self.dialog_type)
            settings.setValue(value, self.view_mode)

    def showListView(self):
        # just show project name / file name
        self.directoryTable.horizontalHeader().hide()
        if self.dialog_type in [DialogType.OPEN_PROJECT,
            DialogType.IMPORT_PROJECT,
            DialogType.EXPORT_PROJECT,
            DialogType.DELETE_PROJECTS]:
                hide_list = [ # these should be hidden
                    FILE_NAME_COL,
                    VERSION_COL,
                    SIZE_COL,
                    DATE_COL
                    ]
                show_list = [PROJECT_NAME_COL]
        else:
            hide_list = [ # these should be hidden
                PROJECT_NAME_COL,
                VERSION_COL,
                SIZE_COL,
                DATE_COL
                ]
            show_list = [FILE_NAME_COL]

        for col in show_list:
            self.directoryTable.setColumnHidden(col, False)
        for col in hide_list:
            self.directoryTable.setColumnHidden(col, True)

    def showDetailedView(self):
        self.directoryTable.horizontalHeader().show()
        if self.dialog_type in [DialogType.OPEN_PROJECT,
            DialogType.IMPORT_PROJECT,
            DialogType.EXPORT_PROJECT,
            DialogType.DELETE_PROJECTS]:
                show_list = [ # these should be visible
                    PROJECT_NAME_COL,
                    FILE_NAME_COL,
                    VERSION_COL,
                    SIZE_COL,
                    DATE_COL
                    ]
                hide_list = []
        else:
            show_list = [ # these should be visible
                FILE_NAME_COL,
                SIZE_COL,
                DATE_COL
                ]
            hide_list = [PROJECT_NAME_COL, VERSION_COL]
        for col in show_list:
            self.directoryTable.setColumnHidden(col, False)
        for col in hide_list:
            self.directoryTable.setColumnHidden(col, True)

    # def keyReleaseEvent(self, evt):
    #     if evt.key() == Qt.Key_Tab:
    #         if qApp.instance().focusWidget() is not self.ok_btn:
    #             self.ok_btn.setFocus(True)
    #     super(SooSLFileDialog, self).keyReleaseEvent(evt)

    def keyPressEvent(self, evt):
        if self.dialog_type is DialogType.PROJECT_LOCATION and \
            qApp.instance().focusWidget() is self.directoryTable and \
            evt.key() in [Qt.Key_Enter, Qt.Key_Return]:
                item = qApp.instance().focusWidget().currentItem()
                if item:
                    text = item.text()
                    new_dir = os.path.join(self.current_dir, text).replace('\\', '/')
                    self.setupProjectTable(new_dir)
                elif self.ok_btn.isEnabled():
                    self.accept()
        elif self.ok_btn.isEnabled() and evt.key() in [Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space]:
            self.accept()
        else:
            super(SooSLFileDialog, self).keyPressEvent(evt)

    def updateDialog(self, file_path):
        _dir = os.path.dirname(os.path.dirname(file_path))
        if _dir not in self.sidebar_dirs:
            self.sidebar_dirs.append(_dir)
            self.sidebar.clear()
            self.setupSidebar()
            self.selected_path = file_path # this will have been cleared

    @property
    def selected_paths(self):
        items = self.directoryTable.selectedItems()
        return [item.data(Qt.UserRole) for item in items]

    def accept(self):
        if self.selected_path:
            if self.dialog_type is DialogType.PROJECT_LOCATION and os.path.isdir(self.selected_path):
                super(SooSLFileDialog, self).accept()
            elif os.path.isdir(self.selected_path) and self.dialog_type is not DialogType.EXPORT_PROJECT:
                self.setupProjectTable(self.selected_path)
                self.setHistory(self.selected_path)
            elif os.path.isdir(self.selected_path) and self.ok_btn.text() == qApp.instance().translate('SooSLFileDialog', 'Open Folder'):
                ## NOTE: RISKY TO USE LABEL COMPARISON??? MAYBE...property('export') is 0: #DialogType.EXPORT_PROJECT
                self.setupProjectTable(self.selected_path)
                self.setHistory(self.selected_path)
            else:
                if self.dialog_type in [DialogType.OPEN_PROJECT] and self.selected_path.lower().endswith('.zoozl'):
                    print('in accept', self.selected_path)
                elif self.dialog_type in [DialogType.EXPORT_PROJECT, DialogType.IMPORT_PROJECT] and not self.waiting_for_valid:
                    self.selected_path = os.path.join(self.current_dir, self.dict_line_edit.text())
                    if os.path.splitext(self.selected_path)[1].lower() != '.zoozl':
                        self.selected_path = '{}.zoozl'.format(self.selected_path)

                self.updateDialog(self.selected_path) #update sidebar, etc if previously unknown directory
                if self.dialog_type in [DialogType.EXPORT_PROJECT, DialogType.IMPORT_PROJECT]:
                    settings = qApp.instance().getSettings()
                    last = os.path.dirname(self.selected_path)
                    settings.setValue('lastImportExportDir', last)
                    settings.sync()
                super(SooSLFileDialog, self).accept()

    def onTextChanged(self, text):
        valid_path = self.validPath(text)
        if valid_path:
            self.selected_path = valid_path
        if self.selected_path:
            if self.selected_path.endswith('.zoozl'):
                self.zoozl_name = os.path.basename(self.selected_path)
            else:
                self.zoozl_name = None
            if self.file_info_lbl.isVisible():
                self.showProjectInfoLabel(self.selected_path)
        else:
            self.zoozl_name = None
            if self.file_info_lbl.isVisible():
                self.clearProjectInfoLabel()
        _bool = True
        if not text:
            _bool = True
        elif self.dialog_type is DialogType.EXPORT_PROJECT and not self.zoozl_name:
            _bool = False
        elif self.dialog_type is DialogType.PROJECT_LOCATION and not valid_path: #self.selected_path:
            _bool = False
        self.ok_btn.setEnabled(_bool)
        self.setOkBtnText()
        if self.dialog_type is DialogType.PROJECT_LOCATION:
            if not text:
                self.selected_path = self.current_dir
            self.showFullPath(table=True)

    def setOkBtnText(self):
        #self.ok_btn.export = 0
        if self.dialog_type is DialogType.PROJECT_LOCATION:
            text = qApp.instance().translate('SooSLFileDialog', 'Select folder')
        elif self.ok_btn.isEnabled() and self.selected_path and os.path.isdir(self.selected_path):
            text = qApp.instance().translate('SooSLFileDialog', 'Open Folder')
        elif self.dialog_type is DialogType.IMPORT_PROJECT:
            text = qApp.instance().translate('SooSLFileDialog', 'Import')
        elif self.dialog_type is DialogType.EXPORT_PROJECT:
            text = qApp.instance().translate('SooSLFileDialog', 'Export')
            #self.ok_btn.export = 1
        elif self.dialog_type is DialogType.DELETE_PROJECTS:
            text = qApp.instance().translate('SooSLFileDialog', 'Delete')
        else:
            text = qApp.instance().translate('SooSLFileDialog', 'Open')
        self.ok_btn.setText(text)

    def onDirectoryTableSelectionChanged(self):
        self.dict_line_edit.blockSignals(True)
        if self.isVisible():
            selected_path = ''
            col = 0
            if self.dialog_type in [DialogType.VIDEO_FILE, DialogType.PICTURE_FILE, DialogType.MEDIA_FILE, DialogType.PROJECT_LOCATION]:
                col = 1
            items = [item for item in self.directoryTable.selectedItems() if item.column() == col]
            base_name = ''
            if self.dialog_type is DialogType.DELETE_PROJECTS and items:
                dir_items = [item for item in items if not item.data(Qt.UserRole)]
                if dir_items:
                    self.directoryTable.setSelectionMode(QTableWidget.SingleSelection)
                    self.directoryTable.setStyleSheet(None)
                    self.directoryTable.setCurrentItem(dir_items[0])
                    selected_path = os.path.join(self.current_dir, dir_items[0].data(Qt.DisplayRole))
                else:
                    self.directoryTable.setSelectionMode(QTableWidget.MultiSelection)
                    self.directoryTable.setStyleSheet("QTableView::item:selected {color:white; background-color:red;}")
                    base_names = [os.path.basename(item.data(Qt.UserRole)) for item in items]
                    base_name_str = ', '.join(base_names)
                    self.dict_line_edit.setText(base_name_str)
                    selected_path = items[0].data(Qt.UserRole)
                self.ok_btn.setEnabled(True)
            elif items:
                item = items[0]
                if item.data(Qt.UserRole): # user data contains full path to dictionary file
                    selected_path = item.data(Qt.UserRole)
                    if os.path.isfile(selected_path): # don't add a directory path to the file line edit
                        base_name = os.path.basename(selected_path) # only display basename of file
                        self.dict_line_edit.setText(base_name)
                        #if self.dialog_type is not DialogType.EXPORT_PROJECT: # keep label showing current project info
                        self.showProjectInfoLabel(selected_path)
                        if self.dialog_type is DialogType.EXPORT_PROJECT:
                            self.zoozl_name = base_name
                    elif self.dialog_type not in [DialogType.EXPORT_PROJECT]: # want to keep suggested filename shown while changing directories
                        self.dict_line_edit.clear()
                        #if self.dialog_type is not DialogType.EXPORT_PROJECT: # keep label showing current project info
                        self.clearProjectInfoLabel()
                else:
                    data = item.data(Qt.DisplayRole)
                    selected_path = os.path.join(self.current_dir, data)
                    if os.path.isfile(selected_path):
                        self.dict_line_edit.setText(data)
                        if self.dialog_type is DialogType.EXPORT_PROJECT:
                            self.zoozl_name = base_name
                    elif self.dialog_type is DialogType.PROJECT_LOCATION and os.path.isdir(selected_path): # do add directory path to file line edit for this type
                        self.dict_line_edit.setText(data)
                    elif self.dialog_type not in [DialogType.EXPORT_PROJECT]:
                        self.dict_line_edit.clear()
                        self.clearProjectInfoLabel()
                self.ok_btn.setEnabled(True)
            elif self.dialog_type == DialogType.OPEN_PROJECT and self.directoryTable.selectedItems():
                item = self.directoryTable.selectedItems()[0]
                data = item.data(Qt.DisplayRole)
                if data.endswith('.zoozl'):
                    selected_path = os.path.join(self.current_dir, data)
                    self.ok_btn.setEnabled(True)
                else:
                    self.ok_btn.setEnabled(False)
            else:
                self.ok_btn.setEnabled(False)
            pth = selected_path
            selected_path = self.realPath(selected_path)
            qApp.restoreOverrideCursor()
            if not selected_path:
                self.ok_btn.setEnabled(False)
                if self.isVisible():
                    msg = '<b>{}</b><br>{}'.format(qApp.instance().translate('SooSLFileDialog', 'Path cannot be found.'), QDir.cleanPath(pth))
                    qApp.instance().pm.showWarning('Path Error', msg)
            self.selected_path = selected_path
            self.setOkBtnText()
        if self.dialog_type is DialogType.PROJECT_LOCATION:
            self.showFullPath(table=True)
        self.dict_line_edit.blockSignals(False)

    def showProjectInfoLabel(self, dict_file=None):
        project_name, id, _version, _datetime = (None, None, None, None)
        if dict_file:
            project_name, id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(dict_file)
        if not project_name:
            project_name = ''
        if not _version:
            _version = ''
        if not _datetime:
            _datetime = ''
        else:
            _datetime = qApp.instance().pm.getCurrentDateTimeStr(iso_str=_datetime)
        text = '<br><b>{}</b><br>{}<br>{}'.format(project_name, _version,  _datetime)
        if self.dialog_type is DialogType.EXPORT_PROJECT:
            text = '<i>{}</i><br><b>{}</b><br>{}<br>{}'.format(qApp.instance().translate('SooSLFileDialog', 'Replace existing file (.zoozl):'), project_name, _version,  _datetime)
        self.file_info_lbl.setText(text)
        self.file_info_lbl.show()
        self.file_info_labels_lbl.show()
        if dict_file:
            self.selectInTable(dict_file)

    def showFullPath(self, table=False):
        txt = self.current_dir + '/'
        if table:
            txt = txt + self.dict_line_edit.text() + '/'
        txt = re.sub(r'[/]+', '/', txt) # prevent repetitions of '/'
        # self.full_path_label.setText(txt)
        self.dict_line_edit.blockSignals(True)
        self.dict_line_edit.setText(self.realPath(txt))
        self.dict_line_edit.blockSignals(False)

    def clearProjectInfoLabel(self):
        self.file_info_lbl.setText('')
        #self.selectInTable(None)

    def selectInTable(self, filename):
        self.directoryTable.blockSignals(True)
        _bool = False
        if filename:
            name = os.path.splitext(os.path.basename(filename))[0]
            search_mode = Qt.MatchFixedString|Qt.MatchCaseSensitive
            if self.dialog_type in [DialogType.VIDEO_FILE, DialogType.MEDIA_FILE]:
                name = os.path.basename(filename)
            items = self.directoryTable.findItems(name, search_mode)
            if items and len(items) == 1:
                item = items[0]
                self.directoryTable.setCurrentItem(item)
                _bool = True
        else:
            self.directoryTable.setCurrentItem(None)
        self.directoryTable.blockSignals(False)
        return _bool

    def hideProjectInfoLabel(self):
        self.file_info_lbl.hide()
        self.file_info_labels_lbl.hide()

    def getDirFromFullDialog(self):
        d = ""
        if sys.platform.startswith('darwin'):
            d = "//Volumes"
        if self.current_dir:
            d = self.current_dir
        title = qApp.instance().translate('SooSLFileDialog', "Locate Directory")
        if self.dialog_type in [DialogType.VIDEO_FILE, DialogType.PICTURE_FILE, DialogType.MEDIA_FILE]:
            title = qApp.instance().translate('SooSLFileDialog', 'Locate Media Directory')
        elif self.dialog_type in [DialogType.OPEN_PROJECT, DialogType.DELETE_PROJECTS]:
            title = qApp.instance().translate('SooSLFileDialog', 'Locate Dictionary Directory')

        # dir = FullFileDialog.getExistingDirectory(None, title,
        #     d, FullFileDialog.ShowDirsOnly|FullFileDialog.DontResolveSymlinks)

        dlg = FullFileDialog(self)
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOptions(QFileDialog.ShowDirsOnly|QFileDialog.DontResolveSymlinks)
        dlg.setWindowTitle(title)
        dlg.setDirectory(d)
        _dir = None
        if dlg.exec_():
            _dirs = dlg.selectedFiles()
            if _dirs:
                _dir = _dirs[0]
        del dlg
        ### BUG: This seems to raise an error report about fatal Windows errors, but no crash???
        ### just clear report for now so it doesn't flag up when SooSL starts
        qApp.instance().clearCrashReport()
        if self.dialog_type == DialogType.OPEN_PROJECT:
            _dir = self.ensureTopFolder(_dir)
        return _dir

    def ensureTopFolder(self, folder):
        # ensure that foler is not a project sub-folder; return project folder if so
        if folder and \
            os.path.exists('{}/{}.json'.format(folder, os.path.basename(folder))) and \
            os.path.exists('{}/_signs'.format(folder)): # check for dictionary file in folder and a signs subdirectory
                _dir = os.path.dirname(folder)
                return _dir
        elif folder and os.path.basename(folder) in ['_signs', '_sentences', '_extra_pictures', '_extra_videos']:
            _dir = os.path.dirname(folder)
            project_path = '{}/{}.json'.format(_dir, os.path.basename(_dir))
            if os.path.exists(project_path):
                _dir = os.path.dirname(_dir)
                return _dir
        return folder

    def onSidebarItemSelected(self):
        self.sidebar.blockSignals(True)
        items = self.sidebar.selectedItems()
        if items:
            item = items[0]
            _dir = item.data(Qt.UserRole)
            if _dir == 'OPEN_FULL_FILE_DIALOG':
                _dir = self.getDirFromFullDialog()
                item.setSelected(False)
            if _dir:
                #qApp.instance().logStartup('...setup file table')
                self.setupProjectTable(_dir)
                #qApp.instance().logStartup('...file table complete')
                self.setHistory(_dir)
        self.sidebar.blockSignals(False)

    def setHistory(self, dir):
        self.directory_history.append(dir)
        if len(self.directory_history) > 1:
            self.back_btn.setEnabled(True)

    def clearHistory(self):
        self.directory_history.clear()
        self.history_idx = -1
        self.back_btn.setDisabled(True)
        self.forward_btn.setDisabled(True)

    def setupDirectoryCombo(self, dir_pth):
        if dir_pth is None:
            dir_pth = ''
        def _icon(_dir):
            return self.model.fileIcon(self.model.index(_dir))
        self.directoryCombo.blockSignals(True)
        self.directoryCombo.clear()
        self.directoryCombo.addItem(_icon(dir_pth), dir_pth)
        next_dir = os.path.dirname(dir_pth)
        try:
            while not os.path.samefile(next_dir, os.path.dirname(next_dir)):
                self.directoryCombo.addItem(_icon(next_dir), next_dir)
                next_dir = os.path.dirname(next_dir)
        except:
            pass #error not required here???
            # msg = '<b>{}</b><br>{}'.format(qApp.instance().translate('SooSLFileDialog', 'Path cannot be found.'), QDir.cleanPath(next_dir))
            # qApp.instance().pm.showWarning('Path Error', msg)
        else:
            self.directoryCombo.addItem(_icon(next_dir), next_dir.replace('\\', '/'))
            #self.directoryCombo.addItem(self.model.myComputer(Qt.DecorationRole), self.model.myComputer())
        self.directoryCombo.blockSignals(False)

    def onComboTextChanged(self, directory_path):
        pth = directory_path
        base = os.path.basename(pth) # in case spaces are used in base
        if self.dialog_type in [DialogType.PROJECT_LOCATION] and os.path.isdir(pth) and (base.rstrip() or pth.endswith('/') or pth.endswith('\\')):
            if qApp.instance().pm.getProjectFile(pth) or qApp.instance().pm.getProjectFile(os.path.dirname(pth)):
                self.ok_btn.setEnabled(False)
            else:
                self.selected_path = pth
                self.setupProjectTable(pth)
                self.setHistory(pth)
        elif os.path.isdir(pth) and (base.rstrip() or pth.endswith('/') or pth.endswith('\\')):
            self.selected_path = pth
            self.setupProjectTable(pth)
            self.setHistory(pth)
        else:
            self.ok_btn.setEnabled(False)

    def selectInSidebar(self, _dir):
        ##_dir = _dir.replace('\\', '/')
        self.sidebar.blockSignals(True)
        for row in range(self.sidebar.count() - 1):
            item = self.sidebar.item(row)
            if item.data(Qt.UserRole) == _dir:
                self.sidebar.setCurrentItem(item)
                break
            else:
                self.sidebar.clearSelection()
        self.sidebar.blockSignals(False)

    def getFilterStr(self, extension_list):
        filter = ['*{}'.format(ext) for ext in extension_list]
        return filter

    def setupProjectTable(self, _dir):
        qApp.setOverrideCursor(Qt.BusyCursor)
        self.current_project_row = -1
        if _dir is None:
            _dir = ''
        self.setupDirectoryCombo(_dir)
        self.selectInSidebar(_dir)
        self.current_dir = _dir
        self.directoryTable.clearContents()
        self.clearProjectInfoLabel()
        if self.dialog_type not in [DialogType.EXPORT_PROJECT, DialogType.PROJECT_LOCATION]:
            self.dict_line_edit.clear()
            self.ok_btn.setEnabled(False)
        else:
            self.ok_btn.setEnabled(True)
        if self.dialog_type is DialogType.EXPORT_PROJECT and self.zoozl_name != self.suggested_zoozl_name:
            self.zoozl_name = self.suggested_zoozl_name

        qdir = QDir(_dir)
        if self.dialog_type in [DialogType.OPEN_PROJECT,
            DialogType.PROJECT_LOCATION]:
                #qdir.setFilter(QDir.Dirs|QDir.NoDotAndDotDot) # show directories only
                qdir.setFilter(QDir.Files|QDir.Dirs|QDir.NoDotAndDotDot) # show files
                qdir.setSorting(QDir.Name)
        else:
            # name_filter = self.getFilterStr(self.extensions)
            # self.model.setNameFilters(name_filter)
            qdir.setFilter(QDir.Files|QDir.Dirs|QDir.NoDotAndDotDot) # show files
            qdir.setSorting(QDir.Name)

        row = 0
        entries = qdir.entryList()
        self.directoryTable.setRowCount(len(entries))
        # from pprint import pprint
        # pprint(entries)
        for entry in entries:
            pth = qdir.absoluteFilePath(entry)
            pth = self.realPath(pth)
            # Avoid navigating into MacOS bundles
            if pth.lower().endswith('.app') or \
                pth.lower().endswith('.app'):
                    self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                    continue # don't want to include apps or help books
            try:
                if self.extensions and os.path.isfile(pth) and not os.path.splitext(pth)[1].lower() in self.extensions:
                    self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                    continue # only directories and wanted files should be listed
            except:
                self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                continue

            idx = self.model.index(pth)
            icon = idx.data(QFileSystemModel.FileIconRole)
            if not icon:
                icon = QIcon()
            # is directory a project directory?
            project_name = None
            pathname = None
            if self.dialog_type in [DialogType.OPEN_PROJECT, DialogType.DELETE_PROJECTS] and os.path.isdir(pth):
                pathname = qApp.instance().pm.getProjectFile(pth)
            elif self.dialog_type in [DialogType.OPEN_PROJECT] and pth.lower().endswith('.zoozl'):
                pathname = pth
            elif self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT, DialogType.PROJECT_LOCATION] and os.path.isdir(pth) and qApp.instance().pm.getProjectFile(pth):
                # don't want to enter project directories when importing, exporting and changing project location
                self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                continue
            elif self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT] and os.path.isfile(pth):
                pathname = pth

            if pathname: # project directory or other SooSL file
                project_name, id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(pathname)
                if self.dialog_type is DialogType.EXPORT_PROJECT:
                    try:
                        if id != qApp.instance().pm.project.id:
                            self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                            continue # only show project archives with the current project id
                    except:
                        self.directoryTable.removeRow(self.directoryTable.rowCount() - 1)
                        continue # probably no project yet, on startup

                icon = QIcon(':/soosl.ico')
                item = QTableWidgetItem(icon, project_name)
                item.setData(Qt.UserRole, pathname)
                self.directoryTable.setItem(row, PROJECT_NAME_COL, item)
                if self.dialog_type is DialogType.EXPORT_PROJECT:
                    base = os.path.basename(pathname)
                    if base == self.dict_line_edit.text() or base == self.zoozl_name:
                        self.directoryTable.setCurrentItem(item)
                        self.showProjectInfoLabel(pathname)

                icon = QIcon(':/lock_open16.png')
                if not qApp.instance().pm.isReadWrite(pathname):
                    icon = QIcon(':/lock16.png')
                #item = QTableWidgetItem(icon, os.path.splitext(os.path.basename(pathname))[0])
                item = QTableWidgetItem(icon, os.path.basename(pathname))
                self.directoryTable.setItem(row, FILE_NAME_COL, item)

                item = QTableWidgetItem(_version)
                self.directoryTable.setItem(row, VERSION_COL, item)

                _size = None
                if pathname.count('.zoozl'):
                    _size = self.getFileSize(pathname)
                else:
                    _size = self.getProjectSize(pathname)
                item = QTableWidgetItem(_size)
                self.directoryTable.setItem(row, SIZE_COL, item)

                if _datetime:
                    modified = self.getProjectModifiedDate(_datetime)
                else:
                    modified = self.getFileModifiedDate(pathname)
                item = QTableWidgetItem(modified)

                self.directoryTable.setItem(row, DATE_COL, item)
                row += 1

            elif os.path.isdir(pth): # ordinary directory
                col = PROJECT_NAME_COL
                if self.dialog_type in [DialogType.VIDEO_FILE, DialogType.PICTURE_FILE, DialogType.MEDIA_FILE, DialogType.PROJECT_LOCATION]:
                    col = FILE_NAME_COL
                item = QTableWidgetItem(icon, entry)
                self.directoryTable.setItem(row, col, item)
                row += 1
            elif os.path.isfile(pth):
                item = QTableWidgetItem(icon, entry)
                self.directoryTable.setItem(row, FILE_NAME_COL, item)

                item = QTableWidgetItem(self.getFileSize(pth))
                self.directoryTable.setItem(row, SIZE_COL, item)

                item = QTableWidgetItem(self.getFileModifiedDate(pth))
                self.directoryTable.setItem(row, DATE_COL, item)
                row += 1

        self.directoryTable.resizeColumnsToContents()
        self.directoryTable.resizeRowsToContents()
        ## Soted already above
        # self.directoryTable.sortByColumn(0, Qt.AscendingOrder)
        # self.directoryTable.sortByColumn(1, Qt.AscendingOrder) # puts project files at the top

        if os.path.dirname(_dir) == _dir:
            self.up_btn.setDisabled(True)
        else:
            self.up_btn.setDisabled(False)

        if self.dialog_type is DialogType.EXPORT_PROJECT and self.zoozl_name:
            self.selected_path = os.path.join(self.current_dir, self.zoozl_name)
            if self.dict_line_edit.text() != self.zoozl_name:
                self.dict_line_edit.setText(self.zoozl_name)
        elif self.dialog_type is DialogType.PROJECT_LOCATION:
            self.selected_path = self.current_dir
            # self.dict_line_edit.blockSignals(True)
            # self.dict_line_edit.setText(os.path.basename(self.selected_path.rstrip('/')))
            #self.dict_line_edit.blockSignals(False)
            self.dict_line_edit.clear()
            self.ok_btn.setEnabled(True)

        self.setOkBtnText()
        if self.dialog_type is DialogType.EXPORT_PROJECT: # override settings in setOkBtnText when opening new directory
            self.ok_btn.setText(qApp.instance().translate('SooSLFileDialog', 'Export'))
        qApp.restoreOverrideCursor()
        if self.dialog_type is DialogType.PROJECT_LOCATION:
            self.showFullPath()

    def getFileModifiedDate(self, filename):
        return self.model.index(filename, 3).data()

    def getProjectModifiedDate(self, date_time):
        dt = qApp.instance().pm.fromIsoFormat(date_time)
        dt = qApp.instance().pm.to_local_datetime(dt)
        d = dt.strftime('%x') # localized date, unsure if this gives a 2 or 4 digit year?
        d = d.rstrip('0123456789') # strip off the year
        y = dt.strftime('%Y') # get 4 digit year
        d = '{}{}'.format(d, y)
        t = dt.strftime('%I:%M %p')
        time_str = '{} {}'.format(d, t)
        #time_str = dt.strftime('%x %I:%M %p') #('%a,  %d %b %Y %H:%M:%S %Z (UTC%z)')
        return time_str

    def __sizeStr(self, _size):
        # found size, now get units
        # https://forum.qt.io/topic/103496/problem-in-reading-a-size-of-a-dir/3
        units = ["Bytes", "KB", "MB", "GB", "TB", "PB"]
        outputSize = _size
        for unit in units:
            if outputSize < 1024:
                break
            outputSize = outputSize/1024
        return  ' {} {}'.format(round(outputSize, 1), unit).ljust(15)

    def getFileSize(self, filename):
        try:
            file_size = os.path.getsize(filename)
        except:
            return ''
        else:
            return self.__sizeStr(file_size)

    def getProjectSize(self, filename):
        proj_dir = os.path.dirname(filename)
        project_size = os.path.getsize(filename)
        qdir = QDir(proj_dir)
        qdir.setFilter(QDir.Dirs|QDir.NoDotAndDotDot)
        for dir_entry in qdir.entryList():
            pth = qdir.absoluteFilePath(dir_entry)
            qqdir = QDir(pth)
            qqdir.setFilter(QDir.Files)
            for entry in qqdir.entryInfoList():
                project_size += entry.size()
        return self.__sizeStr(project_size)

    def setupSidebar(self):
        settings = qApp.instance().getSettings()
        last_directory=None
        if self.dialog_type in [DialogType.IMPORT_PROJECT, DialogType.EXPORT_PROJECT]:
            default = qApp.instance().getDefaultImportExportDirs()[0]
            last_directory = settings.value('lastImportExportDir', default)
        elif self.dialog_type in [DialogType.VIDEO_FILE, DialogType.PICTURE_FILE, DialogType.MEDIA_FILE]:
            home_dir = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
            last_directory = settings.value('lastMediaDir', home_dir)
        else: # open project, compare project, delete project, project location dialog types
            last_project = settings.value('lastOpenedDatabase', None)
            last_directory = qApp.instance().getDefaultProjectsDir()
            if last_project:
                last_directory = os.path.dirname(os.path.dirname(last_project))

        if last_directory and last_directory not in self.sidebar_dirs:
            self.sidebar_dirs.append(last_directory)
        self.sidebar_dirs.sort()

        self.sidebar.clear()
        dirs = []
        dirs.extend(self.sidebar_dirs)
        desktop = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        download = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        home = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
        for d in [desktop, documents, download, home]:
            if d and d not in dirs:
                dirs.append(d)
        dirs.sort(key=lambda x: os.path.basename(x))
        #qApp.instance().logStartup('...getting drives')
        drives = []
        if sys.platform.startswith('win32'):
            drives = QDir.drives()
            for d in drives:
                if d:
                    dirs.append(d.path())
        else:
            drives = glob.glob('//Volumes//*')
            for d in drives:
                if d and d not in ['//Volumes//com.apple.TimeMachine.localsnapshots']:
                    dirs.append(d)

        def _setItem(d):
            #qApp.instance().logStartup('......getting model index for:\n"{}"'.format(d))
            idx = self.model.index(d)
            name = idx.data(Qt.DisplayRole)
            if d in self.sidebar_dirs:
                icon = QIcon(':/soosl.ico')
            else:
                icon = idx.data(QFileSystemModel.FileIconRole)
            if not icon:
                icon = QIcon()
            if name:
                item = QListWidgetItem(icon, name, self.sidebar)
                item.setData(Qt.UserRole, d)
                if d == self.current_dir:
                    #self.sidebar.blockSignals(True)
                    self.sidebar.setCurrentItem(item)
                    #self.sidebar.blockSignals(False)
        ## NOTE: let's not filter out unreadable drives at this point, as it may delay startup

        # #qApp.instance().logStartup('...remove unreadable drives from list')
        # before = copy.deepcopy(dirs)
        # dirs = [d for d in dirs if self.isReadable(d)]
        # non = set(before).difference(dirs)
        # for d in non:
        #     #qApp.instance().logStartup('.... drive unreadable: {}'.format(d))
        #qApp.instance().logStartup('...listing drives')
        for d in dirs:
            _setItem(d)

        item = QListWidgetItem('', self.sidebar) #empty
        item.setFlags(Qt.NoItemFlags)
        item = QListWidgetItem(QIcon(':/open_file.png'), qApp.instance().translate('SooSLFileDialog', 'Other...'), self.sidebar)
        item.setData(Qt.UserRole, 'OPEN_FULL_FILE_DIALOG')
        item.setToolTip(qApp.instance().translate('SooSLFileDialog', 'Open full file dialog to locate Network drives'))

        self.selectInitialSidebarItem()

    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            header_lbls = [qApp.instance().translate('SooSLFileDialog', 'Dictionary title'), qApp.instance().translate('SooSLFileDialog', 'Project filename'), qApp.instance().translate('SooSLFileDialog', 'Project version'), qApp.instance().translate('SooSLFileDialog', 'Size'), qApp.instance().translate('SooSLFileDialog', 'Date Modified')]
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.list_btn.setToolTip(qApp.instance().translate('SooSLFileDialog', 'List View'))
            self.detail_btn.setToolTip(qApp.instance().translate('SooSLFileDialog', 'Detail View'))
            self.setOkBtnText()
            self.cancel_btn.setText(qApp.instance().translate('SooSLFileDialog', 'Cancel'))
            self.setWindowTitle(qApp.instance().translate('SooSLFileDialog', "Open Dictionary"))
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('SooSLFileDialog', 'Look in:')))
            self.filename_lbl.setText(qApp.instance().translate('SooSLFileDialog', "Dictionary's main file:"))
            txt = '<br>{}  <br>{}  <br>{}  '.format(qApp.instance().translate('SooSLFileDialog', 'Title:'), qApp.instance().translate('SooSLFileDialog', 'Version:'), qApp.instance().translate('SooSLFileDialog', 'Modified:'))
            self.file_info_labels_lbl.setText(txt)
        else:
            super(SooSLFileDialog, self).changeEvent(evt)

class ExportProjectDlg(SooSLFileDialog):
    """Dialog used when exporting a zipped dictionary archive."""

    def __init__(self, parent=None):
        super(ExportProjectDlg, self).__init__(parent=parent)

        validator = FileNameValidator(self)
        validator.invalidChar.connect(self.onInvalidChar)
        validator.intermedChar.connect(self.onIntermedChar)
        validator.validChar.connect(self.onValidChar)
        #validator.invalidName.connect(self.onInvalidName)

        self.dict_line_edit.setValidator(validator)
        self.invalid_char_label = QLabel()
        self.invalid_char_label.hide()
        self.filename_layout.addWidget(self.invalid_char_label, 0, 1, Qt.AlignLeft|Qt.AlignHCenter)
        # self.invalid_name_label = QLabel()
        # self.invalid_name_label.hide()

        self.label1 = QLabel(qApp.instance().translate('ExportProjectDlg', "Permissions:"))
        self.label1.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.label2 = QLabel()
        self.label2.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.label2.setPixmap(QPixmap(':/lock_open16.png'))

        self.unlocked_btn = QRadioButton(qApp.instance().translate('ExportProjectDlg', "Signs can be added and changed"))
        self.unlocked_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', "Anyone can change this dictionary"))
        self.unlocked_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.unlocked_btn.toggled.connect(self.onLockToggled)

        self.locked_btn = QRadioButton(qApp.instance().translate('ExportProjectDlg', "People can only view signs, not change them"))
        self.locked_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', "People can only view this dictionary; they cannot change it"))
        self.locked_btn.setCursor(QCursor(Qt.PointingHandCursor))

        group = QButtonGroup(self)
        group.addButton(self.unlocked_btn)
        group.addButton(self.locked_btn)

        self.footer_layout.addWidget(self.label1, 2, 0, Qt.AlignLeft|Qt.AlignVCenter)
        self.footer_layout.addWidget(self.unlocked_btn, 2, 1, Qt.AlignLeft|Qt.AlignVCenter)
        self.footer_layout.addWidget(self.label2, 3, 0, Qt.AlignRight|Qt.AlignVCenter)
        self.footer_layout.addWidget(self.locked_btn, 3, 1, Qt.AlignLeft|Qt.AlignVCenter)
        #self.footer_layout.addWidget(self.invalid_name_label, 0, 1, Qt.AlignLeft|Qt.AlignHCenter)

        # move ok/cancel buttons down one row
        btnItem = self.footer_layout.itemAtPosition(2, 2)
        idx = self.footer_layout.indexOf(btnItem.widget())
        i = self.footer_layout.takeAt(idx)
        self.footer_layout.addItem(i, 3, 2)

        self.setupForExporting()

    def sizeHint(self):
        screen = qApp.screenAt(self.pos())
        if screen:
            s = screen.availableSize()
            w = s.width() * 0.4
            h = s.height() * 0.5
            return QSize(int(w), int(h))
        return QSize(500, 600)

    def setSuggestedFilename(self, filename):
        self.suggested_zoozl_name = filename
        self.zoozl_name = filename
        self.setupProjectTable(self.current_dir)

    def onLockToggled(self, _bool):
        if self.unlocked_btn.isChecked():
            self.read_write_flag = True
            self.label2.setPixmap(QPixmap(':/lock_open16.png'))
        else:
            self.read_write_flag = False
            self.label2.setPixmap(QPixmap(':/lock16.png'))

    def getGap(self):
        space = ' '
        fm = self.fontMetrics()
        w1 = fm.width(self.dict_line_edit.text())
        while fm.width(space) < w1:
            space += ' '
        space += '   '
        nbsp = '&nbsp;' * len(space)
        return nbsp

    ##!!@pyqtSlot(str)
    def onInvalidChar(self, message_str, move_cursor=False):
        if not message_str:
            self.invalid_char_label.hide()
        else:
            text = "<p style='color:red'>{}<b>{}</b></p>".format(self.getGap(), message_str)
            self.invalid_char_label.setText(text)
            self.invalid_char_label.show()
        def move():
            pos = self.dict_line_edit.cursorPosition() + 1
            self.dict_line_edit.setCursorPosition(pos)
        # when checking for duplicate characters in validator, if cursor is 'before' second character I want to move it 'after'
        # following validation; can't seem to do this in the validator since it is an 'invalid' state, so do it here. Also, validator
        # does seem to set the cursor position, so need to make the move after the validator has done its work.
        if move_cursor:
            QTimer.singleShot(0, move)

    def onIntermedChar(self, message_str):
        if not message_str: # 'space' character
            self.invalid_char_label.hide()
        else:
            text = "<p style='color:purple'>{}<b>{}</b></p>".format(self.getGap(), message_str)
            self.invalid_char_label.setText(text)
            self.invalid_char_label.show()
        self.ok_btn.setEnabled(False)
        self.waiting_for_valid = True

    def onValidChar(self):
        self.waiting_for_valid = False

    def showEvent(self, evt):
        self.read_write_flag = True
        self.unlocked_btn.setChecked(True)
        super(ExportProjectDlg, self).showEvent(evt)
        self.zoozl_name = self.suggested_zoozl_name
        self.selectInTable(self.zoozl_name)
        lbl = QLabel()
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.file_info_layout.setContentsMargins(3, 6, 3, 6)
        self.file_info_layout.insertWidget(0, lbl)
        project = qApp.instance().pm.project
        _datetime = qApp.instance().pm.getCurrentDateTimeStr(iso_str=project.last_save_datetime)
        text = '<i>{}</i><br><b>{}</b><br>{}<br>{}'.format(qApp.instance().translate('ExportProjectDlg', 'Current dictionary:'), project.name, project.version_id, _datetime)
        lbl.setText(text)

    def hideEvent(self, evt):
        self.file_info_layout.setContentsMargins(0, 0, 0, 0)
        i = self.file_info_layout.takeAt(0)
        w = None
        try:
            w = i.widget()
        except:
            pass
        else:
            w.close()
        if w:
            w.close()
        del i
        super(ExportProjectDlg, self).hideEvent(evt)

    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            self.label1.setText(qApp.instance().translate('ExportProjectDlg', "Permissions:"))
            self.unlocked_btn.setText(qApp.instance().translate('ExportProjectDlg', "Signs can be added and changed"))
            self.unlocked_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', "Anyone can change this dictionary"))
            self.locked_btn.setText(qApp.instance().translate('ExportProjectDlg', "People can only view signs, not change them"))
            self.locked_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', "People can only view this dictionary; they cannot change it"))
            header_lbls = [qApp.instance().translate('ExportProjectDlg', 'Dictionary title'),
                qApp.instance().translate('ExportProjectDlg', 'ZooZL file name'),
                qApp.instance().translate('ExportProjectDlg', 'Project version'),
                qApp.instance().translate('ExportProjectDlg', 'Size'),
                qApp.instance().translate('ExportProjectDlg', 'Date Modified')]
            self.directoryTable.setHorizontalHeaderLabels(header_lbls)
            self.setWindowTitle(qApp.instance().translate('ExportProjectDlg', "Export Current Dictionary"))
            self.list_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', 'List View'))
            self.detail_btn.setToolTip(qApp.instance().translate('ExportProjectDlg', 'Detail View'))
            self.lookin_lbl.setText('{}   '.format(qApp.instance().translate('ExportProjectDlg', 'Export to:')))
            self.filename_lbl.setText(qApp.instance().translate('ExportProjectDlg', 'ZooZL file:'))
            self.setOkBtnText()
            self.cancel_btn.setText(qApp.instance().translate('ExportProjectDlg', 'Cancel'))
            txt = '<br>{}  <br>{}  <br>{}  '.format(qApp.instance().translate('ExportProjectDlg', 'Title:'),
                qApp.instance().translate('ExportProjectDlg', 'Version:'),
                qApp.instance().translate('ExportProjectDlg', 'Modified:'))
            self.file_info_labels_lbl.setText(txt)
        else:
            super(ExportProjectDlg, self).changeEvent(evt)

class SidebarItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(SidebarItemDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        sidebar = self.parent()
        painter.save()
        pth = index.data(Qt.UserRole)
        row = index.row()
        if pth and pth != 'OPEN_FULL_FILE_DIALOG':
            _bool = True
            try:
                _bool = (os.path.isdir(pth) and not os.listdir(pth))
            except:
                pass
            if not os.path.exists(pth) or _bool:
                if index in self.parent().selectedIndexes():
                    sidebar.parent().parent().directoryTable.clearContents()
                sidebar.setRowHidden(row, True)

        super(SidebarItemDelegate, self).paint(painter, option, index)
        painter.restore()

class ProjectItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(ProjectItemDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        painter.save()
        #self.current_project_row = False
        if index.column() == 0:
            filename = index.data(Qt.UserRole)
            if filename and os.path.exists(filename):
                current_filename = qApp.instance().pm.current_project_filename
                try:
                    if filename and current_filename and os.path.samefile(filename, current_filename):
                        self.parent().current_project_row = index.row()
                    elif filename and qApp.instance().startup_widget and qApp.instance().startup_widget.isVisible():
                        startup_project = qApp.instance().startup_widget.project
                        if startup_project and os.path.samefile(filename, startup_project):
                            self.parent().current_project_row = index.row()
                except:
                    pass
            elif filename:
                table = self.parent().directoryTable
                table.setRowHidden(index.row(), True)

        if self.parent().current_project_row > -1 and index.row() == self.parent().current_project_row:
            option.font.setBold(True)
            option.palette.setColor(QPalette.Text, Qt.blue)

        super(ProjectItemDelegate, self).paint(painter, option, index)
        painter.restore()

class FullFileDialog(QFileDialog):
    def __init__(self, parent):
        super(FullFileDialog, self).__init__(parent)

        # self.setLabelText(label, string)
        # QFileDialog::LookIn	0
        # QFileDialog::FileName	1
        # QFileDialog::FileType	2
        # QFileDialog::Accept	3
        # QFileDialog::Reject

# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()