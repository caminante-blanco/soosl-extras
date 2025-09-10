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
import json
import os
import shutil
import glob
import copy
import pickle
from datetime import datetime, timezone
from pyuca import Collator
import difflib
import filecmp
from itertools import zip_longest

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QRectF
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QSize
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QEvent

from PyQt5.QtGui import QBrush
from PyQt5.QtGui import QStandardItem
from PyQt5.QtGui import QTextDocument
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPen
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QTextOption
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QFontMetrics

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QRadioButton

from project import *
from components.component_drop_widget import ComponentDropWidget
from location_widget import LocationView
from video_widget_vlc import Player
from media_wrappers import VideoWrapper as Video
from media_wrappers import PictureWrapper as Picture
from importer import Importer

from pprint import pprint        

# COLUMNS ON PROJECT TREE
SECONDARY_COL = 0
DECISION_COL = 1
MOVE_DOWN_COL = 2
MOVE_UP_COL = 3
EDIT_COL = 4
PRIMARY_COL = 5
# USER ROLES
ITEM_WIDTH_ROLE = Qt.UserRole+1
ITEM_HEIGHT_ROLE = Qt.UserRole+2
PRIMARY_ITEM_ROLE = Qt.UserRole+3
SECONDARY_ITEM_ROLE = Qt.UserRole+4
DECISION_ITEM_ROLE = Qt.UserRole+5
ITEM_ORDER_ROLE = Qt.UserRole+6
EDITOR_ROLE = Qt.UserRole+7
MOVE_UP_ITEM = Qt.UserRole+8
MOVE_DOWN_ITEM = Qt.UserRole+9
MOVE_ITEM_TARGET = Qt.UserRole+10
EDIT_ITEM = Qt.UserRole+11
# EDITED_DATA_ROLE = Qt.UserRole+12
# MERGE STATES
MERGE_NONE = 0
MERGE_UNDECIDED = 1
MERGE_EDITED = 2
MERGE_ACCEPTED = 3
MERGE_REJECTED = 4
MERGE_MIXED = 5 # used for parent items where children are a mixture of ACCEPTED and REJECTED
MERGE_IGNORE = -1 # USED WHEN BOTH PRIMARY AND SECONDARY DATA IS EMPTY

PAGE_INFO = 0
PAGE_SIGNS = 1
####

class MergeDialog(QDialog):
    close_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(MergeDialog, self).__init__(parent)
        self.setWindowTitle(qApp.instance().translate('MergeDialog', 'Compare two versions'))
        self.primary_proj = ''
        fn =  qApp.instance().pm.current_project_filename
        if fn and qApp.instance().pm.isReadWrite(fn) and not self.setMergeDir(fn):
            self.primary_proj = fn
        self.secondary_proj = ''
        layout = QVBoxLayout()
        self.setLayout(layout)
        glayout = QGridLayout()
        self.primary_lbl = QLabel(self.primary_proj)
        self.secondary_project_btn = QPushButton()
        self.secondary_project_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.secondary_project_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.secondary_project_btn.pressed.connect(self.onChooseProject)
        self.secondary_project_btn.setStyleSheet('text-align: left;')

        self.compare_project_radio = QRadioButton(qApp.instance().translate('MergeDialog', 'Compare with another dictionary'))
        self.compare_zoozl_radio = QRadioButton(qApp.instance().translate('MergeDialog', 'Compare with a .zoozl file'))
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.compare_project_radio)
        radio_layout.addWidget(self.compare_zoozl_radio)
        radio_layout.addStretch()
        self.compare_project_radio.setChecked(True)
        glayout.addWidget(QLabel('(A) Primary version:'), 0, 0)
        glayout.addWidget(self.primary_lbl, 0, 1)
        glayout.addWidget(QLabel('(B) Secondary version:'), 1, 0)
        glayout.addWidget(self.secondary_project_btn, 1, 1)
        glayout.addLayout(radio_layout, 2, 1)
        layout.addLayout(glayout)

        layout.addSpacing(24)
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('MergeDialog', 'Compare'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('MergeDialog', 'Cancel'))
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(qApp.instance().pm.stopInactivityTimer)
        self.btnBox.rejected.connect(self.reject)
        layout.addWidget(self.btnBox)

        self.exclude_exts = ['.user', '.lock', '.inventory']
        qApp.instance().pm.startInactivityTimer(self)

    def leaveEdit(self, _bool): # inactivity timeout will use this
        self.close()

    def closeEvent(self, evt):
        self.close_signal.emit()
        mw = qApp.instance().getMainWindow()  
        qApp.instance().pm.releaseFullProjectLock(mw) 
        qApp.instance().pm.stopInactivityTimer()   

    def setMergeDir(self, filename):
        self.merge_dir = os.path.dirname(filename) + '/merge'
        if os.path.exists(self.merge_dir):
            return True
        return False

    def onChooseProject(self):
        qApp.instance().pm.startInactivityTimer(self)
        mw = qApp.instance().getMainWindow()
        dlg = mw.soosl_file_dlg
        self.close_signal.connect(dlg.close)        
        _type = 'project'
        if self.compare_zoozl_radio.isChecked():
            _type = 'zoozl'
        dlg.setupForMergeComparison(_type)        
        t2 = qApp.instance().translate('MergeDialog', 'Select Secondary Version')
        title = t2
        dlg.setWindowTitle(title)
        qApp.processEvents()
        mw.ensureUsingActiveMonitor(dlg)
        btn = self.sender()
        if dlg.exec_():
            selected_path = dlg.selected_path 
            if qApp.instance().pm.isReadWrite(selected_path):
                self.secondary_proj = selected_path

                primary_id = qApp.instance().pm.getProjectId(self.primary_proj)
                secondary_id = qApp.instance().pm.getProjectId(self.secondary_proj)

                if primary_id != secondary_id:
                    short = qApp.instance().translate('MergeDialog', 'Cannot Merge Projects')
                    long = qApp.instance().translate('MergeDialog', "The Project IDs for these two dictionaries are not the same. They are for two different dictionaries. SooSL cannot compare or merge them.")
                    QMessageBox.warning(self, short, long) 
                elif btn == self.secondary_project_btn:
                    if selected_path != self.primary_proj:
                        btn.setText(self.secondary_proj)
                    else:
                        short = qApp.instance().translate('MergeDialog', 'Same Dictionary')
                        long = qApp.instance().translate('MergeDialog', '<h3>A == A</h3>Same dictionary folder! Cannot compare it with itself.')
                        QMessageBox.warning(self, short, long) 
                elif btn is self.primary_lbl:
                    if self.setMergeDir(selected_path): # merge directory already exists; don't merge again
                        self.completeMergeWarning()
                    else:
                        qApp.instance().pm.openProject(self.primary_proj)
                        mw.project_open.emit(True)
                        btn.setText(self.primary_proj)
            else:
                short = qApp.instance().translate('MergeDialog', 'Read-only dictionary')
                long = qApp.instance().translate('MergeDialog', 'Primary dictionary must be read-write')
                QMessageBox.warning(self, short, long)
        del dlg

        if self.secondary_proj and self.primary_proj:
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)

    def copiedProject(self, project_path):
        project_dir = os.path.dirname(project_path)
        temp_dir = qApp.instance().getTempDir()
        temp_project_path = ''
        if project_path.endswith('.zoozl'):
            name = os.path.splitext(os.path.basename(project_path))[0]
            _dir = f'{temp_dir}/{name}'
            importer = Importer(self)
            temp_project_path = importer.doImport(project_path, _dir, False)
        else:
            temp_project_path = os.path.join(temp_dir, os.path.basename(project_dir), os.path.basename(project_path))
            temp_project_dir = os.path.dirname(temp_project_path)
            try:
                shutil.copytree(project_dir, temp_project_dir)
            except:
                shutil.rmtree(temp_project_dir)
                shutil.copytree(project_dir, temp_project_dir)
        if temp_project_path:
            copied_project = Project(temp_project_path)
            return copied_project
        return None

    def compareProjects(self):
        def get_path(j):
            # for files that have it, use the desktop_path
            return j.get('desktop_path', j.get('path'))
        
        def order(p):
            order = 0
            if p.startswith('/_signs/'):
                order = 1
            elif p.startswith('/_sentences/'):
                order = 2
            elif p.startswith('/_extra_videos/'):
                order = 3
            elif p.startswith('/_extra_pictures/'):
                order = 4
            return order
        
        if not self.setMergeDir(self.primary_proj):
            primary_project = Project(self.primary_proj)
            # copy secondary first so original is not changed/updated
            # open copy
            secondary_project = self.copiedProject(self.secondary_proj)
            ignore = ['.lock', '.user', '.inventory']
            result = filecmp.dircmp(secondary_project.project_dir, primary_project.project_dir)
            primary_only = [f'/{i}' for i in result.right_only if os.path.splitext(i)[1] not in ignore]
            secondary_only = [f'/{i}' for i in result.left_only if os.path.splitext(i)[1] not in ignore]
            changed = [f'/{i}' for i in result.diff_files if os.path.splitext(i)[1] not in ignore]
            for _dir in result.common_dirs:
                base = os.path.basename(_dir)
                s_dir = f'{secondary_project.project_dir}/{_dir}'
                p_dir = f'{primary_project.project_dir}/{_dir}'
                result = filecmp.dircmp(s_dir, p_dir)
                primary_only.extend([f'/{base}/{i}' for i in result.right_only if os.path.splitext(i)[1] not in ignore])
                secondary_only.extend([f'/{base}/{i}' for i in result.left_only if os.path.splitext(i)[1] not in ignore])
                changed.extend([f'/{base}/{i}' for i in result.diff_files if os.path.splitext(i)[1] not in ignore])
            primary_only.sort(key=lambda x: (order(x), x))
            secondary_only.sort(key=lambda x: (order(x), x))
            changed.sort(key=lambda x: (order(x), x))
            # if new_files or deleted_files or changed_files:
            if primary_only or secondary_only or changed:                
                if not os.path.exists(self.merge_dir):
                    os.makedirs(self.merge_dir)
                new_changes_file = '{}/changes.json'.format(self.merge_dir)
                o = {}
                o['primary_only'] = primary_only #new_files # here, new files means files only found in primary project
                o['secondary_only'] = secondary_only #deleted_files # here, deleted files means files only found in secondary project
                o['changed'] = changed #changed_files
                with open(new_changes_file, 'w', encoding='utf-8') as f:
                    json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False, cls=MergeEncoder)
                for l in [secondary_only, changed]:
                    for f in l:
                        src = '{}{}'.format(secondary_project.project_dir, f)
                        if os.path.exists(src): #NOTE: if it doesn't exist, an error and possibly an orphaned file

                            dst = '{}{}'.format(self.merge_dir, f)
                            try:
                                shutil.copy(src, dst)
                            except:
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                shutil.copy(src, dst)
                return True # if there are changes to reconcile
            else:
                short = qApp.instance().translate('MergeDialog', 'Nothing to Merge')
                long = qApp.instance().translate('MergeDialog', '<h3>A == B</h3>No differences. Versions are identical. Nothing to merge.')
                QMessageBox.information(self, short, long)
            return False # if there are no changes to reconcile
        else:
            self.completeMergeWarning()

    def completeMergeWarning(self):
        short = qApp.instance().translate('MergeDialog', 'Complete Previous Merge')
        long =  qApp.instance().translate('MergeDialog', 'There are still changes to be reconciled from a previous merge.')
        QMessageBox.warning(self, short, long)

class MergeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'toJsn'):
            return copy.deepcopy(obj.toJsn())
        return json.JSONEncoder.default(self, obj)
    
class FinalMergeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'toFinalJsn'):
            return copy.deepcopy(obj.toFinalJsn())
        elif hasattr(obj, 'toJsn'):
            return copy.deepcopy(obj.toJsn())
        return json.JSONEncoder.default(self, obj)

class ReconcileChangesDialog(QDialog):
    close_signal = pyqtSignal()

    def __init__(self, parent=None, ignore_removal_check=False):
        super(ReconcileChangesDialog, self).__init__(parent)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)           

        self.ignore_removal_check = ignore_removal_check
        self.allow_reconciliation = True
        #self.overall_merge_count = 0
        self.page = PAGE_INFO
        self.abandoned = False # changed to True if merge abandoned
        # these are the items which could be changed in project and signs
        self.info_data_types = [
            'projectInfoLabel',
            'projectName', 
            'signLanguage', 
            'versionId',
            'projectCreator',
            'projectLogo',
            'projectDescription',
            'languageInfoLabel',
            'writtenLanguages',
            'grammarInfoLabel',
            'grammarCategories',
            'dialectInfoLabel',
            'dialects']
        self.sign_data_types = [
            'signsLabel',
            'signId',
            'signPath',
            #'hashType', ## now storing hash data along with path data: ._data = (path, hash) for signPath, sentencePath types
            'componentCodes',
            'senseOrder',
            'senseId',
            'dialectIds',
            'grammarCategoryId',
            'glossTexts',
            'sentencePath',
            'sentenceId',
            'sentenceTexts',
            'extraMediaFile',
            'extraTexts']
        
        self.project_root_item = None
        self.sign_root_item = None        
        
        primary_project_filename = qApp.instance().pm.project.filename
        self.primary_project = Project(primary_project_filename) # copy of primary to prevent changes to orgianl at this time. ##qApp.instance().pm.project
        self.merge_dir = os.path.dirname(primary_project_filename) + '/merge'
        secondary_project_filename = [f for f in glob.glob("{}/*.json".format(self.merge_dir)) if not f.endswith('changes.json')][0]
        self.secondary_project = Project(secondary_project_filename)
        
        self.merge_progress_jsn = self.getMergeProgressJson()

        self.s_orig_written_languages = copy.deepcopy(self.secondary_project.writtenLanguages)
        self.p_orig_written_languages = copy.deepcopy(self.primary_project.writtenLanguages)
        self.all_written_languages = self.adjustAllLanguageIds(self.secondary_project.writtenLanguages, self.primary_project.writtenLanguages)

        self.s_orig_dialects = copy.deepcopy(self.secondary_project.dialects)
        self.p_orig_dialects = copy.deepcopy(self.primary_project.dialects)
        self.all_dialects = self.adjustAllDialectIds(self.secondary_project.dialects, self.primary_project.dialects)

        self.s_orig_grammar_categories = copy.deepcopy(self.secondary_project.grammar_categories)
        self.p_orig_grammar_categories = copy.deepcopy(self.primary_project.grammar_categories)
        self.all_grammar_categories = self.adjustAllGrammarCategoryIds(self.secondary_project.grammar_categories, self.primary_project.grammar_categories)

        changes_file = '{}/changes.json'.format(self.merge_dir)
        changes_jsn = None
        with open(changes_file, 'r', encoding='utf-8') as f:
            changes_jsn = json.load(f)

        primary_only_files = changes_jsn.get('primary_only')
        secondary_only_files = changes_jsn.get('secondary_only')
        changed_files = changes_jsn.get('changed')

        primary_only_signs = [p for p in primary_only_files if p.startswith('/_signs') and p.endswith('.json')]
        primary_only_sign_ids = [os.path.basename(os.path.splitext(x)[0]) for x in primary_only_signs]

        secondary_only_signs = [p for p in secondary_only_files if p.startswith('/_signs') and p.endswith('.json')]
        secondary_only_sign_ids = [os.path.basename(os.path.splitext(x)[0]) for x in secondary_only_signs] 

        changed_signs = [p for p in changed_files if p.startswith('/_signs') and p.endswith('.json')]
        changed_sign_ids = [int(os.path.basename(os.path.splitext(x)[0])) for x in changed_signs]        

        # layout widgets
        layout = QVBoxLayout()
        btnBox = QDialogButtonBox()

        btn_layout = QGridLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setColumnStretch(0, 46) #space
        btn_layout.setColumnStretch(1, 1)
        btn_layout.setColumnStretch(2, 1)
        btn_layout.setColumnStretch(3, 1)
        btn_layout.setColumnStretch(4, 2) #space
        # 50 % - half way
        btn_layout.setColumnStretch(5, 1)
        btn_layout.setColumnStretch(6, 47) #space
        btn_layout.setColumnStretch(7, 1)

        self.accept_all_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', 'Accept all'))
        pxm = QPixmap(':/merge_accept.png')
        icn = QIcon(pxm.scaledToHeight(self.accept_all_btn.height(), Qt.SmoothTransformation))
        self.accept_all_btn.setIcon(icn)
        self.accept_all_btn.pressed.connect(self.onAllBtnPressed)
        btn_layout.addWidget(self.accept_all_btn, 0, 1)

        self.reject_all_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', 'Reject all'))
        pxm = QPixmap(':/merge_reject.png')
        icn = QIcon(pxm.scaledToHeight(self.reject_all_btn.height(), Qt.SmoothTransformation))
        self.reject_all_btn.setIcon(icn)
        self.reject_all_btn.pressed.connect(self.onAllBtnPressed)
        btn_layout.addWidget(self.reject_all_btn, 0, 2)

        self.clear_all_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', 'Clear all'))
        pxm = QPixmap(':/merge_question.png')
        icn = QIcon(pxm.scaledToHeight(self.clear_all_btn.height(), Qt.SmoothTransformation))
        self.clear_all_btn.setIcon(icn)
        self.clear_all_btn.pressed.connect(self.onAllBtnPressed)
        btn_layout.addWidget(self.clear_all_btn, 0, 3)

        self.collapse_signs_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', 'Collapse signs'))
        # self.collapse_signs_btn.setEnabled(False)
        self.collapse_signs_btn.setVisible(False)
        pxm = QPixmap(':/collapsed.png')
        icn = QIcon(pxm.scaledToHeight(self.collapse_signs_btn.height(), Qt.SmoothTransformation))
        self.collapse_signs_btn.setIcon(icn)
        self.collapse_signs_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.collapse_signs_btn.pressed.connect(self.onCollapseSigns)
        btn_layout.addWidget(self.collapse_signs_btn, 0, 5)

        self.close_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', "Close and finish later"))
        pxm = QPixmap(':/leave_edit.png')
        icn = QIcon(pxm.scaledToHeight(self.close_btn.height(), Qt.SmoothTransformation))
        self.close_btn.setIcon(icn)
        self.close_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.close_btn.pressed.connect(self.onSaveAndCloseMerge)

        self.abandon_merge_btn = QPushButton(qApp.instance().translate('ReconcileChangesDialog', 'Abandon merge'))       
        pxm = QPixmap(':/abandon_merge.png')
        icn = QIcon(pxm.scaledToHeight(self.abandon_merge_btn.height(), Qt.SmoothTransformation))
        self.abandon_merge_btn.setIcon(icn)
        self.abandon_merge_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.abandon_merge_btn.pressed.connect(self.onAbandonMerge)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addStretch()
        hlayout.addWidget(self.close_btn)
        hlayout.addWidget(self.abandon_merge_btn)

        btn_layout.addWidget(btnBox, 0, 7)

        self.next_btn = QPushButton()
        self.next_btn.setText(qApp.instance().translate('ReconcileChangesDialog', 'Next: Reconcile sign differences'))
        self.next_btn.setIcon(QIcon(':/next.png'))
        btnBox.addButton(self.next_btn, QDialogButtonBox.ApplyRole)

        self.complete_merge_btn = QPushButton() 
        self.complete_merge_btn.setText(qApp.instance().translate('ReconcileChangesDialog', 'Complete merge'))
        self.complete_merge_btn.setIcon(QIcon(':/save.png'))
        btnBox.addButton(self.complete_merge_btn, QDialogButtonBox.ApplyRole)

        self.next_btn.setEnabled(False) 
        self.complete_merge_btn.setEnabled(False)
        self.next_btn.pressed.connect(self.onNextBtnPressed)        
        self.complete_merge_btn.pressed.connect(self.saveMergeChanges)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        
        self.sign_ids = changed_sign_ids
        self.sign_ids.extend(primary_only_sign_ids)
        self.sign_ids.extend(secondary_only_sign_ids)
        self.sign_ids = list(set(self.sign_ids))
        self.sign_ids.sort(key=lambda x: int(x))

        self.project_tree = ProjectTreeView(self, self.secondary_project, self.primary_project)
        self.project_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setupHeaders() 
        self.project_tree.expanded.connect(self.onExpanded)
        self.project_tree.collapsed.connect(self.onCollapsed)

        self.populateProjectModel()
        layout.addWidget(self.project_tree)
        layout.addLayout(btn_layout)
        layout.addLayout(hlayout)
        self.setLayout(layout)
        delegate = ProjectTreeItemDelegate(self.project_tree)
        self.project_tree.setItemDelegate(delegate)  

        qApp.instance().pm.startInactivityTimer(self)
        self.installEventFilter(self)

    def eventFilter(self, obj, evt):
        if evt.type() == QEvent.MouseButtonPress and self.project_tree.editor_index:
            self.project_tree.closeEditor()
        return super(ReconcileChangesDialog, self).eventFilter(obj, evt)

    def leaveEdit(self, _bool): # inactivity timeout will use this
        self.onSaveAndCloseMerge()

    def adjustAllLanguageIds(self, s_written_languages, p_written_languages):
        # give all languages, both secodnary and primary, unique ids unless matching names; which should have the same id
        all_languages = copy.deepcopy(p_written_languages)
        merge_languages = copy.deepcopy(s_written_languages)
        lang_names = [l.name for l in all_languages]
        lang_ids = [int(l.id) for l in all_languages]
        for lang in merge_languages:
            if lang.name not in lang_names:
                lang.id = 1
                while lang.id in lang_ids:
                    lang.id += 1
                all_languages.append(lang)
                lang_names.append(lang.name)
                lang_ids.append(lang.id)
        all_languages.sort(key=lambda x: x.name) # for merging, sort in name order
        for lang in all_languages:
            lang.order = all_languages.index(lang) + 1 # for merging, order also by alphabetical name order;
        # apply changes to orginal language lists
        for langs in [s_written_languages, p_written_languages]:
            for lang in langs:
                l = [l for l in all_languages if l.name == lang.name][0]
                lang.id = l.id
                lang.order = l.order
        return all_languages
    
    def adjustAllDialectIds(self, s_dialects, p_dialects):
        all_dialects = copy.deepcopy(p_dialects)
        merge_dialects = copy.deepcopy(s_dialects)
        dialect_names = [d.name for d in all_dialects]
        dialect_ids = [int(d.id) for d in all_dialects]
        for dial in merge_dialects:
            if dial.name not in dialect_names:
                dial.id = 1
                while dial.id in dialect_ids:
                    dial.id += 1                
                all_dialects.append(dial)
                dialect_names.append(dial.name)
                dialect_ids.append(dial.id)
        # apply changes to orginal dialect lists
        for dials in [s_dialects, p_dialects]:
            for dial in dials:
                d = [d for d in all_dialects if d.name == dial.name][0]
                dial.id = d.id
        all_dialects.sort(key=lambda x: x.name) 
        return all_dialects

    def adjustAllGrammarCategoryIds(self, s_grammar_categories, p_grammar_catories):
        all_cats = copy.deepcopy(p_grammar_catories)
        merge_cats = copy.deepcopy(s_grammar_categories)
        cat_names = [c.name for c in all_cats]
        cat_ids = [int(c.id) for c in all_cats]
        for cat in merge_cats:
            if cat.name not in cat_names:
                cat.id = 1
                while cat.id in cat_ids:
                    cat.id += 1                
                all_cats.append(cat)
                cat_names.append(cat.name)
                cat_ids.append(cat.id)
        # apply changes to orginal category lists
        for cats in [s_grammar_categories, p_grammar_catories]:
            for cat in cats:
                c = [c for c in all_cats if c.name == cat.name][0]
                cat.id = c.id  
        all_cats.sort(key=lambda x: x.name) # for merging, sort in name order
        return all_cats

    def closeEvent(self, evt):
        if isinstance(self.sender(), QAction):
            self.close_reopen = 0
        if os.path.exists(self.merge_dir):
            self.saveMergeProgress()        
        super(ReconcileChangesDialog, self).closeEvent(evt) 
        for i in [
            self
            ]:
                i.deleteLater()  
        mw = qApp.instance().getMainWindow()  
        qApp.instance().pm.releaseFullProjectLock(mw) 
        qApp.instance().pm.stopInactivityTimer()   
        #NOTE: memory usage creeps up by about 1 - 2 MB after each open and close

    def onAllBtnPressed(self):
        qApp.setOverrideCursor(Qt.BusyCursor)
        self.project_tree.closeEditor(False)
        btn = self.sender()
        model = self.project_tree.model()
        parent = model.rootItem
        if btn is self.accept_all_btn:
            self.onAcceptAll(parent)
        elif btn is self.reject_all_btn:
            self.onRejectAll(parent)
        elif btn is self.clear_all_btn:
            self.onClearAll(parent)

    def onCollapseSigns(self):
        model = self.project_tree.model()
        for child in self.sign_root_item._children:
            child.expanded = False
            row = child.row()
            index = model.index(row, 0)
            self.project_tree.collapse(index)
        self.project_tree.update()

    def onSaveAndCloseMerge(self):
        self.close()           
        qApp.restoreOverrideCursor()

    def onAbandonMerge(self):
        self.abandoned = True
        self.close_reopen = 0
        self.close()
        shutil.rmtree(self.merge_dir)           
        qApp.restoreOverrideCursor()

    def onAcceptAll(self, parent):
        ignores = [MERGE_NONE, MERGE_IGNORE]
        if parent.merge_state not in ignores:
            parent.merge_state = MERGE_ACCEPTED
        for child in parent._children:
            if child.merge_state not in ignores:
                child.merge_state = MERGE_ACCEPTED
            if child.childCount():
                self.onAcceptAll(child)           
        qApp.restoreOverrideCursor()
        QTimer.singleShot(0, self.project_tree.scheduleDelayedItemsLayout)     
        if self.page == PAGE_INFO:
            self.next_btn.setEnabled(True)
        elif self.page == PAGE_SIGNS:
            self.complete_merge_btn.setEnabled(True)

    def onRejectAll(self, parent):
        ignores = [MERGE_NONE, MERGE_IGNORE]
        if parent.merge_state not in ignores:
            parent.merge_state = MERGE_REJECTED
        for child in parent._children:
            if child.merge_state not in ignores:
                child.merge_state = MERGE_REJECTED
            if child.childCount():
                self.onRejectAll(child)
        qApp.restoreOverrideCursor()
        QTimer.singleShot(0, self.project_tree.scheduleDelayedItemsLayout)
        if self.page == PAGE_INFO:
            self.next_btn.setEnabled(True)
        elif self.page == PAGE_SIGNS:
            self.complete_merge_btn.setEnabled(True)

    def onClearAll(self, parent):
        ignores = [MERGE_NONE, MERGE_IGNORE]
        if parent.merge_state not in ignores:
            parent.merge_state = MERGE_UNDECIDED
        for child in parent._children:
            if child.merge_state not in ignores:
                child.merge_state = MERGE_UNDECIDED
            if child.childCount():
                self.onClearAll(child)          
        qApp.restoreOverrideCursor()
        QTimer.singleShot(0, self.project_tree.scheduleDelayedItemsLayout)
        if self.page == PAGE_INFO:
            self.next_btn.setEnabled(False)
        elif self.page == PAGE_SIGNS:
            self.complete_merge_btn.setEnabled(False)

    def getMergeProgressJson(self):
        # where merge progress data is stored
        filename = '{}/merge_progress.jsn'.format(self.merge_dir)
        jsn = {}
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                try:
                    jsn = json.load(f)
                except:
                    pass # an empty dict is already assigned to jsn in the event of failure (loading empty file?)
        if jsn:
            # convert dicts into their corresponding SooSL object
            for key in jsn.keys():
                value = jsn.get(key)
                # if value.get('merge_state', MERGE_IGNORE) == MERGE_IGNORE:
                #     continue
                data_type = key.split('_', 2)[1]
                s_data = value.get('secondary_data')
                p_data = value.get('primary_data')
                _cls = None
                if data_type == 'writtenLanguages':
                    _cls = WrittenLanguage
                    value['secondary_data'] = _cls(s_data)
                    value['primary_data'] = _cls(p_data)
                elif data_type == 'grammarCategories':
                    _cls = GrammarCategory
                    value['secondary_data'] = _cls(s_data)
                    value['primary_data'] = _cls(p_data)
                elif data_type == 'dialects':
                    _cls = Dialect
                    value['secondary_data'] = _cls(s_data)
                    value['primary_data'] = _cls(p_data)
                elif data_type == 'glossTexts':
                    _cls = GlossText
                    value['secondary_data'] = _cls(s_data, s_data.get('senseId'), s_data.get('signId'), s_data.get('dialectIds'), s_data.get('order'))
                    value['primary_data'] = _cls(p_data, p_data.get('senseId'), p_data.get('signId'), p_data.get('dialectIds'), p_data.get('order'))
                elif data_type == 'sentenceTexts':
                    _cls = SentenceText
                    value['secondary_data'] = _cls(s_data, s_data.get('order', 0))
                    value['primary_data'] = _cls(p_data, p_data.get('order', 0))
                elif data_type == 'extraTexts':
                    _cls = ExtraText
                    value['secondary_data'] = _cls(s_data)
                    value['primary_data'] = _cls(p_data)
                elif data_type == 'extraMediaFile':
                    _cls = ExtraMediaFile
                    value['secondary_data'] = _cls(self.secondary_project, s_data)
                    value['primary_data'] = _cls(self.primary_project, p_data)
        return jsn
    
    def saveMergeProgress(self):
        if self.project_root_item:
            filename = f'{self.merge_dir}/project_items'
            with open(filename, 'wb') as f:
                pickle.dump(self.project_root_item, f, pickle.HIGHEST_PROTOCOL)
        if self.sign_root_item:
            filename = f'{self.merge_dir}/sign_items'
            with open(filename, 'wb') as f:
                pickle.dump(self.sign_root_item, f, pickle.HIGHEST_PROTOCOL)

    # def rememberMergeProgress(self, s_item):
    #     if s_item.data_type in ['notesLabel', 'infoLabel', 'extraMediaLabel', 'signsLabel']:
    #         return
    #     p_item = self.getOtherItem(s_item)

    #     if self.project_tree.hasEmptyText(s_item) and self.project_tree.hasEmptyText(p_item):
    #         s_item.merge_state = MERGE_IGNORE
    #         p_item.merge_state = MERGE_IGNORE
    #     elif self.project_tree.hasEmptyText(p_item) and s_item.merge_state == MERGE_IGNORE:
    #         s_item.merge_state = MERGE_UNDECIDED
    #         p_item.merge_state = MERGE_UNDECIDED 
            
    #     s_data = s_item._data
    #     p_data = p_item._data
    #     if s_item.data_type == 'sentencePath':
    #         s_name, s_hash = s_data
    #         p_name, p_hash = p_data
    #         if s_data:
    #             s_data = (f'/_sentences/{os.path.basename(s_name)}', s_hash)
    #         if p_data:
    #             p_data = (f'/_sentences/{os.path.basename(p_name)}', p_hash)

    #     key = self.getProgressKey(s_item)
    #     d = self.merge_progress_jsn.get(key, {})
    #     d['merge_state'] = s_item.merge_state
    #     d['edited_data'] = s_item.edited_data            
    #     d['secondary_data'] = s_data
    #     d['primary_data'] = p_data
    #     self.merge_progress_jsn[key] = d 

    # #### https://www.qtcentre.org/threads/67972-Get-Row-of-specific-QTreeWidgetItem-in-my-QWidgetTree?p=298352#post298352 ####
    # def _itemRow(self, item): # starting from 0 as first row in project tree
    #     index = item.model().indexFromItem(item)
    #     _row = self.__calculateRow(index)
    #     return _row

    # def __rowsBelowIndex(self, index):
    #     count = 0
    #     model = index.model()
    #     rowCount = model.rowCount(index)
    #     count += rowCount
    #     for r in range(0, rowCount):
    #         count += self.__rowsBelowIndex(model.index(r, 0, index))
    #     return count

    # def __calculateRow(self, index):
    #     count = 0
    #     if index.isValid():
    #         parent = index.parent()
    #         count = index.row() + self.__calculateRow(parent)            
    #         if parent.isValid():
    #             count += 1
    #             r = 0
    #             while r < index.row():
    #                 count += self.__rowsBelowIndex(parent.child(r, 0))
    #                 r += 1
    #     return count      
    
    def resizeEvent(self, evt):
        try:
            self.resizeHeaderSections()
        except:
            pass
        super(ReconcileChangesDialog, self).resizeEvent(evt)

    def setupHeaders(self):
        header = self.project_tree.header()
        header.setStyleSheet('color:blue; font-weight:bold;')
        header.setSectionsMovable(False)
        header.setMinimumSectionSize(5)
        for section in range(header.count()):
            header.setSectionResizeMode(section, QHeaderView.Fixed)

    def resizeHeaderSections(self):
        margins = self.layout().contentsMargins().left() + self.layout().contentsMargins().right()
        header_width = self.width() - margins
        fudge = 100 ##NOTE: reducing total width #manual figure to get rid of vertical slider; not sure why needed?
        fudge2 = 53 ##NOTE: another manual adjustment for col width to help break text evenly???
        total_width = header_width - fudge
        header = self.project_tree.header()
        w = 18
        for col in [DECISION_COL, MOVE_DOWN_COL, MOVE_UP_COL, EDIT_COL]:
            header.resizeSection(col, w)
        middle_col_width = 4*w
        width = (total_width - middle_col_width)/2
        secondary_width = width
        primary_width = width
        secondary_width = (total_width - 4*w)/2 + fudge2
        primary_width = (total_width - 4*w)/2 - fudge2
        header.resizeSection(SECONDARY_COL, secondary_width)
        header.resizeSection(PRIMARY_COL, primary_width)
    
    def __mergeStateForNode(self, node):
        # get the merge state for this node; priority: MERGE_UNDECIDED, MERGE_ACEPTED|MERGE_REJECTED|MERGE_EDITED
        def getMergeState(node, merge_state):
            for idx in range(node.rowCount()):
                child_item = node.child(idx)
                if child_item.hasChildren():
                    merge_state = getMergeState(child_item, merge_state)
                elif child_item.merge_state == MERGE_UNDECIDED:
                    merge_state = MERGE_UNDECIDED
                elif not merge_state == MERGE_UNDECIDED and child_item.merge_state in [MERGE_ACCEPTED, MERGE_REJECTED, MERGE_EDITED]:
                    merge_state = child_item.merge_state
            return merge_state          
        return getMergeState(node, MERGE_NONE)

    def onCollapsed(self, index):
        qApp.instance().pm.startInactivityTimer(self)

    def onExpanded(self, index):
        qApp.instance().pm.startInactivityTimer(self)
        item = index.internalPointer()
        data_type = item.data_type
        if data_type == 'signId':            
            self.project_tree.expandRecursively(index)

    def onNextBtnPressed(self):
        self.next_btn.setEnabled(False)
        qApp.processEvents()
        qApp.instance().pm.startInactivityTimer(self) 
        self.project_root_item.merge_state = MERGE_ACCEPTED
        self.populateSignModel()           
        
    def saveMergeChanges(self):
        if self.updatePrimaryDictionary():
            try:
                shutil.rmtree(self.merge_dir)
            except:
                pass # already removed/ doesn't exist
            self.close()  

    def __getSignMedia(self, sign):
            media_list = []
            # main sign video
            if sign.path:
                media_list.append(sign.path)
            # extra media
            for media in sign.extra_media_files:
                if media.path:
                    base = os.path.basename(media.path)
                    base_dir = os.path.basename(os.path.dirname(media.path))
                    pth = f'/{base_dir}/{base}'
                    media_list.append(pth)
            # sentence videos
            for sense in sign.senses:
                try:
                    for sent in sense.get('sentences', []):
                        pth = sent.get('path', '')
                        if os.path.basename(pth):
                            media_list.append(pth)
                except:
                    for sent in sense.sentences:
                        pth = sent.path
                        if os.path.basename(pth):
                            media_list.append(pth)
            return media_list

    def updatePrimaryDictionary(self):
        # reconciliation is complete, now time to update the primary dictionary with the changes.
        # While developing and testing, create a copy of the final updated dictionary; not the original.
        qApp.setOverrideCursor(Qt.BusyCursor)
        project_file = self.primary_project.filename
        project_dir = self.primary_project.project_dir
        name, ext = os.path.splitext(os.path.basename(project_file))
        results_name = '{}_merge_results'.format(name)
        results_dir = '{}_merge_results'.format(project_dir)
        results_file = '{}/{}{}'.format(results_dir, results_name, ext)

        if os.path.exists(results_dir): # just for testing ??? start fresh everytime
            shutil.rmtree(results_dir)
            os.mkdir(results_dir)
        else:
            os.mkdir(results_dir)
            
        dt = datetime.now(timezone.utc) # time of merge
        timestamp = str(round(qApp.instance().pm.getSooSLDateTime(dt)))# diff in seconds between creation and SooSL 'epoch'
        modified_date_time = dt.isoformat()

        project_node = self.project_root_item
        sign_node = self.sign_root_item
        sign_items = sign_node._children
        sign_items.extend(sign_node._hidden_children)

        if project_node:            
            project_jsn = self.getProjectData(timestamp, modified_date_time, final=True)
            project_logo = project_jsn.pop('projectLogo', '') # remove it from jsn; don't want it listed in merge project file
            dst_project_logo = f'{results_dir}/project_logo.png'
            if project_logo:
                shutil.copy(project_logo, dst_project_logo) # overwrite any existing logo file
            elif os.path.exists(dst_project_logo):
                os.remove(dst_project_logo) # no logo in merged project, so remove any existing logo

            self.primary_project.sortProjectJsn(project_jsn)
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(project_jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
                            
            if os.path.exists(results_file): # create directories and copy over current data 
                for _dir in ['_signs', '_sentences', '_extra_videos', '_extra_pictures']:
                    shutil.copytree(f'{project_dir}/{_dir}', f'{results_dir}/{_dir}')

            def prep(f):
                base = os.path.basename(f)
                base_dir = os.path.basename(os.path.dirname(f))
                return f'/{base_dir}/{base}'

            project_media = []
            for sign_item in sign_items:
                sign = sign_item.p_data 
                sign_data = self.getSignData(sign_item) 
                sign.modified_datetime = modified_date_time # mark all modified
                sign.path = sign_data.get('path', '')  
                sign.hash = sign_data.get('hash', '')
                sign.component_codes = sign_data.get('componentCodes', [])
                sign.senses = sign_data.get('senses', [])
                for sense in sign.senses:
                    sense.get('dialectIds', []).sort()
                    gloss_texts = sense.get('glossTexts', [])
                    gloss_texts.sort(key=lambda x: x.lang_id)
                    sense['glossTexts'] = [t for t in gloss_texts if t.text]
                    sentences = sense.get('sentences', [])
                    for sent in sentences:
                        sent_texts = sent.get('sentenceTexts', [])
                        sent_texts.sort(key=lambda x: x.lang_id)
                        sent['sentenceTexts'] = [t for t in sent_texts if t.text]
                sign.extra_media_files = sign_data.get('extraMediaFiles', [])
                sign.extra_texts = []
                any_extra_texts = []
                try:
                    any_extra_texts = [t.text for t in sign_data.get('extraTexts', []) if t.text]
                except:
                    any_extra_texts = [t.get('text', '') for t in sign_data.get('extraTexts', []) if t.get('text', '')]
                if any_extra_texts:
                    sign.extra_texts = [et for et in sign_data.get('extraTexts', []) if et.text]
                    sign.extra_texts.sort(key=lambda x: int(x.lang_id))

                file_name = f'{results_dir}/_signs/{sign.id}.json'

                if sign_item.merge_state != MERGE_NONE and not os.path.basename(sign.path): # deleted sign
                    if os.path.exists(file_name):
                        os.remove(file_name)
                else:
                    sign_media = self.__getSignMedia(sign)
                    project_media.extend(sign_media)
                    with open(file_name, 'w', encoding='utf-8') as f:
                        json.dump(sign, f, sort_keys=False, indent=4, ensure_ascii=False, cls=FinalMergeEncoder)

            for f in project_media:
                f = prep(f)
                dst_path = f'{results_dir}{f}'
                if not os.path.exists(dst_path):
                    src_pth = f'{self.secondary_project.project_dir}{f}'
                    shutil.copy(src_pth, dst_path)

            # remove deleted media files from project
            all_media = []
            for _dir in ['_signs', '_sentences', '_extra_videos', '_extra_pictures']:
                qdir = QDir(f'{results_dir}/{_dir}')
                qdir.setFilter(QDir.Files)
                paths = [qdir.absoluteFilePath(entry).replace('\\', '/') for entry in qdir.entryList() 
                         if (qApp.instance().pm.isVideo(entry) or qApp.instance().pm.isPicture(entry))]
                paths = list(map(prep, paths))
                all_media.extend(paths)

            for pth in all_media:
                if pth not in project_media:
                    pth = f'{results_dir}{pth}'
                    try:
                        os.remove(pth)
                    except:
                        pass

            qApp.restoreOverrideCursor()
            return True
        else:           
            qApp.restoreOverrideCursor()
            QMessageBox.information(self, 'Merge Failed!', 'No dictionary file created.')
            shutil.rmtree(results_dir)
            return False
    
    def getProjectData(self, timestamp=0, merge_time=0, final=False):
        """
        Get the project data from the model in the form of a json object (dict).
        """
        written_languages = []
        dialects = []
        grammar_categories = []
        jsn = {
            'projectId': self.primary_project.id, 
            'timeStamp': timestamp,
            'creationDateTime': self.primary_project.jsn.get('creationDateTime'),
            'modifiedDateTime': merge_time,
            'sooslVersion': self.primary_project.soosl_version,
            'minSooSLVersion': self.primary_project.jsn.get('minSooSLVersion'),
            'writtenLanguages': written_languages,
            'dialects': dialects,
            'grammarCategories': grammar_categories
            }
        
        def _data(item):
            data = item.data(PRIMARY_COL)
            if item.merge_state == MERGE_EDITED:
                data = item.edited_data
            elif item.merge_state == MERGE_ACCEPTED:
                data = item.data(SECONDARY_COL)
            return data
        
        for item in self.project_root_item._children:  
            if item.data_type in ['languageInfoLabel', 'dialectInfoLabel', 'grammarInfoLabel']:
                for item in item._children:
                    data = _data(item)
                    if data.empty:
                        continue
                    if item.data_type == 'writtenLanguages':
                        if final:
                            lang = data.toFinalJsn()
                            written_languages.append(lang)
                        else:
                            written_languages.append(data.toJsn())
                    elif item.data_type == 'dialects':
                        if final:
                            dialects.append(data.toFinalJsn())
                        else:
                            dialects.append(data.toJsn())
                    elif item.data_type == 'grammarCategories':
                        if final:
                            grammar_categories.append(data.toFinalJsn())
                        else:
                            grammar_categories.append(data.toJsn())
            elif item.data_type != 'projectInfoLabel':
                data = _data(item)
                if data:
                    jsn[item.data_type] = data
        if final:                
            settings = qApp.instance().getSettings()
            lang_orders = []
            for lang in written_languages:
                # get list of existing orders
                user_order = settings.value(f"ProjectSettings/{self.primary_project.json_file}/{lang.get('langName')}/order")
                if user_order:
                    lang_orders.append(int(user_order))
            for lang in written_languages:
                # adjust order to settings; may have changed for merging sake
                user_order = settings.value(f"ProjectSettings/{self.primary_project.json_file}/{lang.get('langName')}/order")
                if user_order: #overide json order with user setting, if any
                    lang['order'] = int(user_order)
                else:
                    new_order = 1
                    while new_order in lang_orders:
                        new_order += 1
                    lang_orders.append(new_order)
                    lang['order'] = new_order
        written_languages.sort(key=lambda x: x.get('langName', x.get('langId')))
        dialects.sort(key=lambda x: x.get('name'))
        grammar_categories.sort(key=lambda x: x.get('name'))
        return jsn
    
    def __itemData(self, item):
        s_data = item.data(SECONDARY_COL)
        p_data = item.data(PRIMARY_COL)
        if item.data_type == 'writtenLanguages': 
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            if isinstance(data, dict):
                data = WrittenLanguage(data)
            data.order = item.row() + 1 #p_item._data.order
        elif item.data_type in ['dialects', 'grammarCategories']:
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            if isinstance(data, dict):
                if item.data_type == 'dialects':
                    data = Dialect(data)
                else:
                    data = GrammarCategory(data)
            data.id = p_data.id
        elif item.data_type in ['glossTexts', 'sentenceTexts', 'extraTexts']:
            data = p_data
            if item.merge_state == MERGE_ACCEPTED:
                data.text = s_data.text
            elif item.merge_state == MERGE_EDITED:
                data.text = item.edited_data.get('text', '')
        elif item.data_type == 'senseId':
            sense_id = p_data[1]
            data = sense_id
        elif item.data_type == 'sentencePath':
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            pth, hash = data
            _base = os.path.basename(pth)
            data = (f'/_sentences/{_base}', hash)
        elif item.data_type == 'signPath':
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            pth, hash = data
            _base = os.path.basename(pth)
            data = (f'/_signs/{_base}', hash)
        elif item.data_type == 'extraMediaFile':
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            if isinstance(data, dict):
                data = ExtraMediaFile(data)
        else:
            data = s_data # assume MERGE_ACCEPTED
            if item.merge_state == MERGE_REJECTED:
                data = p_data
            elif item.merge_state == MERGE_EDITED:
                data = item.edited_data
        return data

    def getSignData(self, sign_item, merge_time=None):
        """ 
        Get sign data from the model in the form of a json object (dict).
        """
        sign_id = self.__itemData(sign_item)
        sign_data = {'id': sign_id}
        if merge_time:
            sign_data['modifiedDateTime'] = merge_time
        sense_items = []
        if sign_item.hasChildren():
            for child_item in sign_item._children:
                if child_item.data_type == 'signPath':
                    item_data = self.__itemData(child_item)
                    pth, hash = item_data
                    pth = pth.replace('\\', '/')
                    project_dir = qApp.instance().pm.project.project_dir
                    if pth.count('/merge/'):
                        project_dir = '{}/merge'.format(project_dir)
                    sign_data["path"] = pth.replace(project_dir, '')
                    sign_data["hash"] = hash
                elif child_item.data_type == 'componentCodes':
                    sign_data["componentCodes"] = self.__itemData(child_item)
                elif child_item.data_type == 'senseId':
                    if 'senses' not in sign_data.keys():
                        sign_data['senses'] = sense_items
                    sense = {}
                    sense_id = self.__itemData(child_item)
                    sense['id'] = sense_id
                    gloss_items = []
                    sense['dialectIds'] = []
                    sense['grammarCategoryId'] = None
                    sense['glossTexts'] = gloss_items
                    sense['sentences'] = []
                    if child_item.hasChildren():
                        for item in child_item._children:
                            if item.data_type == 'dialectIds':
                                dialect_ids = self.__itemData(item)
                                sense['dialectIds'].extend(dialect_ids)
                            elif item.data_type == 'grammarCategoryId':
                                sense['grammarCategoryId'] = self.__itemData(item)
                            elif item.data_type == 'glossTexts':
                                item_data = self.__itemData(item)
                                if item_data:
                                    gloss_items.append(item_data)                                
                            # label is 'Sentences'
                            elif item.data_type == 'sentencePath':
                                sentence_items = sense.get('sentences')
                                if item.hasChildren():
                                    for item1 in item._children:
                                        if item1.data_type == 'sentenceId':
                                            id = self.__itemData(item1)
                                            pth, hash = self.__itemData(item)
                                            if os.path.basename(pth): # won't exist if empty
                                                sentence_texts = []
                                                sent = {'id': id, 'path': pth, 'hash': hash, 'sentenceTexts': sentence_texts}
                                                sentence_items.append(sent)
                                        elif item1.data_type == 'sentenceTexts':
                                            item_data = self.__itemData(item1)
                                            if item_data:
                                                try:
                                                    sentence_texts.append(item_data)
                                                except:
                                                    pass # empty sent and sentence_texts hasn't been added
                        if not sense.get('grammarCategoryId', None) and \
                            not sense.get('dialectIds', None):
                                pass # empty sense, no need to check other attributes
                        else:
                            sense_items.append(sense)

                elif child_item.data_type == 'extraMediaLabel':
                    media = []
                    sign_data['extraMediaFiles'] = media
                    if child_item.hasChildren():
                        for item in child_item._children:
                            if item.data_type == 'extraMediaFile':
                                em = self.__itemData(item)
                                s = 0
                                try:
                                    s = os.path.getsize(em.path)
                                except:
                                    pass # can't find file
                                else:
                                    if s > 0:
                                        media.append(em)

                elif child_item.data_type == 'notesLabel':
                    notes = []
                    sign_data['extraTexts'] = notes
                    if child_item.hasChildren():
                        for item in child_item._children:
                            if item.data_type == 'extraTexts':
                                item_data = self.__itemData(item)
                                if item_data:
                                    notes.append(item_data)
        return sign_data
         
    def sizeHint(self):
        screen = qApp.screenAt(self.pos())
        if screen:
            s = screen.availableSize()
            w = s.width() * 0.8
            h = s.height() * 0.8
            return QSize(int(w), int(h))
        return QSize(600, 600)

    def setProjectItems(self):
        filename = f'{self.merge_dir}/project_items'
        if os.path.exists(filename):
            with open(f'{self.merge_dir}/project_items', 'rb') as f:
                self.project_root_item = pickle.load(f)
        else:
            # self.project_root_item = MergeNode(None, None, None)
            txt = qApp.instance().translate('ReconcileChangesDialog', "Dictionary information")
            self.project_root_item = MergeNode('projectInfoLabel', txt, txt)
            self.project_root_item.merge_state = MERGE_NONE
            # self.project_root_item.addChild(node)
            self.project_root_item.addChild(MergeNode('projectName', self.secondary_project.name, self.primary_project.name))
            self.project_root_item.addChild(MergeNode('signLanguage', self.secondary_project.sign_language, self.primary_project.sign_language))
            self.project_root_item.addChild(MergeNode('versionId', self.secondary_project.version_id, self.primary_project.version_id))
            self.project_root_item.addChild(MergeNode('projectCreator', self.secondary_project.project_creator, self.primary_project.project_creator))
            s_logo = qApp.instance().pm.getProjectLogo(self.secondary_project)
            p_logo = qApp.instance().pm.getProjectLogo(self.primary_project)
            self.project_root_item.addChild(MergeNode('projectLogo', s_logo, p_logo))
            self.project_root_item.addChild(MergeNode('projectDescription', self.secondary_project.description, self.primary_project.description))
            s_written_languages, p_written_languages = self.adjustWrittenLangs(self.secondary_project.writtenLanguages, self.primary_project.writtenLanguages) 
            self.s_grammar_cats, self.p_grammar_cats = self.adjustGrammarCategories(self.secondary_project.grammar_categories, self.primary_project.grammar_categories)
            self.s_dialects, self.p_dialects = self.adjustDialects(self.secondary_project.dialects, self.primary_project.dialects)
            wl_txt = qApp.instance().translate('ReconcileChangesDialog', "Written languages")        
            gc_txt = qApp.instance().translate('ReconcileChangesDialog', "Grammar categories")
            d_txt = qApp.instance().translate('ReconcileChangesDialog', "Dialects")
            node = MergeNode('languageInfoLabel', wl_txt, wl_txt)
            node.merge_state = MERGE_NONE
            self.project_root_item.addChild(node)
            for s_lang, p_lang in zip(s_written_languages, p_written_languages):
                node.addChild(MergeNode('writtenLanguages', s_lang, p_lang))
            node = MergeNode('grammarInfoLabel', gc_txt, gc_txt)
            node.merge_state = MERGE_NONE
            self.project_root_item.addChild(node)
            for s_cat, p_cat in zip(self.s_grammar_cats, self.p_grammar_cats):
                node.addChild(MergeNode('grammarCategories', s_cat, p_cat))
            node = MergeNode('dialectInfoLabel', d_txt, d_txt)
            node.merge_state = MERGE_NONE
            self.project_root_item.addChild(node)
            for s_dialect, p_dialect in zip(self.s_dialects, self.p_dialects):
                node.addChild(MergeNode('dialects', s_dialect, p_dialect)) 
            
        if not self.infoReconciliationComplete():
            self.project_root_item.merge_state == MERGE_UNDECIDED
            self.next_btn.setEnabled(False)
        else:
            self.project_root_item.merge_state == MERGE_ACCEPTED
            self.next_btn.setEnabled(True)

    # def getInitialMergeState(self, item):
    #     return MERGE_ACCEPTED

    def __getFirstGloss(self, sign_pair):
        txt = ''        
        for sign in sign_pair:
            senses = sign.senses
            if senses:
                gloss_texts = senses[0].gloss_texts
                try:
                    gt = [t for t in gloss_texts if t.lang_id == qApp.instance().pm.search_lang_id][0]
                except:
                    txt = ''
                else:
                    txt = gt.text
                if txt:
                    break
        return txt

    def __sortSigns(self, signs_zip):
        signs = tuple(signs_zip) # ((s_sign, p_sign), (s_sign1, p_sign1),..)
        finder = qApp.instance().getMainWindow().finder_list
        sorter = finder.sorter
        c = Collator() # pyuca
        signs = sorted(signs, key=lambda sp: sorter(finder.lstripPunct(self.__getFirstGloss(sp)).lower().split(';')[0].strip(), c))
        # if synonyms separated by ';' - sort by first synonym
        return signs
    
    def sLangName(self, lang_id):
        names = [l.name for l in self.s_orig_written_languages if l.name and l.id == lang_id]
        if names:
            return names[0]
        return ''
        
    def pLangName(self, lang_id):
        names = [l.name for l in self.p_orig_written_languages if l.name and l.id == lang_id]
        if names:
            return names[0]
        return ''
    
    def sGramCatName(self, _id):
        names = [gc.name for gc in self.s_orig_grammar_categories if gc.name and gc.id == _id]
        if names:
            return names[0]
        return ''
    
    def pGramCatName(self, _id):
        names = [gc.name for gc in self.p_orig_grammar_categories if gc.name and gc.id == _id]
        if names:
            return names[0]
        return ''
    
    def sDialectName(self, _id):
        names = [d.name for d in self.s_orig_dialects if d.name and d.id == _id]
        if names:
            return names[0]
        return ''
    
    def pDialectName(self, _id):
        names = [d.name for d in self.p_orig_dialects if d.name and d.id == _id]
        if names:
            return names[0]
        return ''

    def __updateSignTexts(self, data_type, written_languages, texts, s_or_p): 
        langName = self.sLangName
        source_languages = self.secondary_project.writtenLanguages
        if s_or_p == 'p':
            langName = self.pLangName
            source_languages = self.primary_project.writtenLanguages
        for lang in written_languages:
            written_langs = [l for l in source_languages if l.id == lang.get('langId')]
            if written_langs and written_langs[0].name != lang.get('langName'):
                lang['langName'] = written_langs[0].name
        # update language id to final value
        for t in texts:
            try:
                final_lang = [l for l in source_languages if l.name == langName(t.lang_id)][0]
            except: # already updated to new id (I think!)
                pass
            else:
                t.lang_id = final_lang.id
                t.lang_name = final_lang.name
                t.order = final_lang.order
        # add and remove texts as required
        written_names = [l.get('langName') for l in written_languages]
        text_names = [t.lang_name for t in texts]
        for lang in self.all_written_languages:
            lang_name = lang.name
            if lang_name not in text_names and lang_name in written_names: # add
                _lang = [l for l in written_languages if l.get('langName') == lang_name][0]
                text = None 
                jsn = {'langId': _lang.get('langId'), 'langName': _lang.get('langName'), 'text': ''}
                if data_type == 'gloss':
                    text = GlossText(jsn)
                elif data_type == 'sentence':
                    text = SentenceText(jsn)
                elif data_type == 'extra':
                    text = ExtraText(jsn)
                if text:
                    text.order = _lang.get('order')
                    texts.append(text)
            elif lang_name in text_names and lang_name not in written_names: # remove
                text = [t for t in texts if t.lang_name == lang_name][0]
                texts.remove(text)
        # sort texts by order
        texts.sort(key=lambda x: x.order)

    def __updateSignDialects(self, dialects, dialect_ids, s_or_p):
        dialName = self.sDialectName
        if s_or_p == 'p':
            dialName = self.pDialectName
        # remove dialect from sign if dialect was removed from project
        names = [d.get('name') for d in dialects]
        id_names = [dialName(_id) for _id in dialect_ids]
        for dial in self.all_dialects:
            if dial.name in id_names and dial.name not in names: # remove
                _id = [i for i in dialect_ids if dialName(i) == dial.name][0]
                dialect_ids.remove(_id)                
            ## NOTE: code needed to add??? (only if returning to change project data)
        # sort dialects by name
        dialect_ids.sort(key=lambda x: dialName(x))

    def __updateSignGrammarCategory(self, grammar_categories, grammar_category_id, s_or_p):
        catName = self.sGramCatName
        if s_or_p == 'p':
            catName = self.pGramCatName
        # remove category from sign if category was removed from project
        names = [c.get('name') for c in grammar_categories]
        id_name = catName(grammar_category_id)
        cat_id = grammar_category_id
        for cat in self.all_grammar_categories:
            if cat.name == id_name and cat.name not in names: # remove
                cat_id = None
            ## NOTE: code needed to add??? (only if returning to change project data)
        return cat_id
    
    def updateSignsData(self):
        self.project_data = self.getProjectData()
        #pprint(self.project_data, sort_dicts=False)
        written_languages = self.project_data.get('writtenLanguages')        
        dialects = self.project_data.get('dialects')
        grammar_categories = self.project_data.get('grammarCategories')

        # update text lang ids to final project ids
        for sign in self.secondary_project.signs:
            self.__updateSignTexts('extra', written_languages, sign.extra_texts, 's')
            for sense in sign.senses:
                self.__updateSignTexts('gloss', written_languages, sense.gloss_texts, 's')
                self.__updateSignDialects(dialects, sense.dialect_ids, 's')
                sense.grammar_category_id = self.__updateSignGrammarCategory(grammar_categories, sense.grammar_category_id, 's')
                for sent in sense.sentences:
                    self.__updateSignTexts('sentence', written_languages, sent.sentence_texts, 's')

        for sign in self.primary_project.signs:
            sign.extra_texts = [et for et in sign.extra_texts]
            self.__updateSignTexts('extra', written_languages, sign.extra_texts, 'p')
            for sense in sign.senses:
                self.__updateSignTexts('gloss', written_languages, sense.gloss_texts, 'p')
                self.__updateSignDialects(dialects, sense.dialect_ids, 'p')
                sense.grammar_category_id = self.__updateSignGrammarCategory(grammar_categories, sense.grammar_category_id, 'p')
                for sent in sense.sentences:
                    self.__updateSignTexts('sentence', written_languages, sent.sentence_texts, 'p')

    def getSignDisplayText(self, sign):
        senses = [s for s in sign.senses]
        texts = []
        for sense in senses:
            gloss_texts = sense.gloss_texts
            gts = [t for t in gloss_texts if t.lang_id == qApp.instance().pm.search_lang_id]
            if gts:
                gt = gts[0]
                texts.append(gt.text)
        display_text = ''
        if texts and len(texts) > 1:
            display_text = ' | '.join(texts)
        elif texts:
            display_text = texts[0]
        return display_text

    def setSignItems(self, sign_ids=None):
        if not sign_ids:
            sign_ids = self.sign_ids
        # prepare project info 
        secondary_signs, primary_signs = self.adjustSigns(sign_ids) # just changed signs, identified by ids 
        
        self.updateSignsData() # updates all signs (writtenlang, dialect, grammarCat IDs)  
        signs = self.__sortSigns(zip(secondary_signs, primary_signs))
        # [(s_sign, p_sign), (s_sign1, p_sign1),..] 

        filename = f'{self.merge_dir}/sign_items'
        if os.path.exists(filename):
            with open(f'{self.merge_dir}/sign_items', 'rb') as f:
                self.sign_root_item = pickle.load(f)
        else:
            # populate the tree
            txt = qApp.instance().translate('ReconcileChangesDialog', "Signs")
            self.sign_root_item = MergeNode('signsLabel', txt, txt) 
            for s_sign, p_sign in signs:
                sign_node = MergeNode('signId', s_sign, p_sign)
                self.sign_root_item.addChild(sign_node) 
                self.addSignData(sign_node) 
                if sign_node.merge_state == MERGE_NONE:
                    hidden = self.sign_root_item._children.pop() # don't want signs with same/equal data in list
                    self.sign_root_item._hidden_children.append(hidden)
                sign_node.updateSenseMergeStates()
            if not self.signReconciliationComplete():
                self.sign_root_item.merge_state == MERGE_UNDECIDED
            else:
                self.sign_root_item.merge_state == MERGE_ACCEPTED                    
        qApp.restoreOverrideCursor()

    def addSignData(self, sign_item): 
        s_sign = sign_item.data(SECONDARY_COL)
        p_sign = sign_item.data(PRIMARY_COL)
        s_path = s_sign.path
        p_path = p_sign.path
        try:
            s_hash = s_sign.hash
        except:
            s_hash = ''
        try:
            p_hash = p_sign.hash
        except:
            p_hash = ''
        if s_path and not os.path.exists(s_path):
            s_path = s_path.replace('/merge/', '/')
        
        sign_item.addChild(MergeNode('signPath', (s_path, s_hash), (p_path, p_hash))) 

        if s_sign.component_codes or p_sign.component_codes:
            sign_item.addChild(MergeNode('componentCodes', s_sign.component_codes, p_sign.component_codes))

        #s_sense_order_item = None
        sense_order_node = None
        s_sense_orders = [s.s_order for s in s_sign.senses]
        p_sense_orders = [s.p_order for s in p_sign.senses]
        if s_sense_orders != p_sense_orders:            
            # s_sense_order_item = MergeItem(s_sense_orders, 'senseOrder')
            # p_sense_order_item = MergeItem(p_sense_orders, 'senseOrder')
            sense_order_node = MergeNode('senseOrder', s_sense_orders, p_sense_orders)
            sign_item.addChild(sense_order_node)

        if sense_order_node and sense_order_node.merge_state == MERGE_ACCEPTED:
            # sort senses according to secondary order
            s_sign.senses.sort(key=lambda x: int(x.s_order))
            p_sign.senses.sort(key=lambda x: int(x.s_order))

        for s_sense, p_sense in zip(s_sign.senses, p_sign.senses): #'senseId'
            try:
                s_sense_data = (s_sense.sign_id, s_sense.id, s_sense.s_order, s_sense.p_order) 
            except: # empty sense, use other ids
                s_sense_data = (p_sense.sign_id, p_sense.id, p_sense.s_order, p_sense.p_order)            
            try:
                p_sense_data = (p_sense.sign_id, p_sense.id, p_sense.s_order, p_sense.p_order)
            except: # empty sense, use other ids
                p_sense_data = (s_sense.sign_id, s_sense.id, s_sense.s_order, s_sense.p_order)
            sense_node = MergeNode('senseId', s_sense_data, p_sense_data)
            sign_item.addChild(sense_node)
            if sense_order_node:
                sense_node.order_item = sense_order_node

            #updateGrammarCategoryId(s_sense)
            sense_node.addChild(MergeNode('grammarCategoryId', s_sense.grammar_category_id, p_sense.grammar_category_id))

            #updateDialectIds(s_sense.dialect_ids)
            sense_node.addChild(MergeNode('dialectIds', sorted(s_sense.dialect_ids), sorted(p_sense.dialect_ids)))
                
            s_sense.gloss_texts.sort(key=lambda x: int(x.order))
            p_sense.gloss_texts.sort(key=lambda x: int(x.order))
            for s_text, p_text in zip(s_sense.gloss_texts, p_sense.gloss_texts):
                sense_node.addChild(MergeNode('glossTexts', s_text, p_text))

            s_sentences = [s for s in s_sense.sentences]
            p_sentences = [s for s in p_sense.sentences]

            for s_sent, p_sent in zip(s_sentences, p_sentences):
                pth = s_sent.path               
                if not os.path.exists(pth):
                    pth = pth.replace('/merge/', '/')
                sent_path_node = MergeNode('sentencePath', (pth, s_sent.hash), (p_sent.path, p_sent.hash))
                sense_node.addChild(sent_path_node)
                sent_path_node.addChild(MergeNode('sentenceId', s_sent.id, p_sent.id))
                        
                s_sentence_texts = [t for t in s_sent.sentence_texts]
                p_sentence_texts = [t for t in p_sent.sentence_texts]
                for s_text, p_text in zip(s_sentence_texts, p_sentence_texts):
                    sent_path_node.addChild(MergeNode('sentenceTexts', s_text, p_text))

        if [f.path for f in s_sign.extra_media_files if f.path] or [f.path for f in p_sign.extra_media_files if f.path]:
            txt = qApp.instance().translate('ReconcileChangesDialog', "Extra media")
            extra_media_node = MergeNode('extraMediaLabel', txt, txt)
            sign_item.addChild(extra_media_node)
            s_em_items = []
            for em in s_sign.extra_media_files:
                pth = em.path      
                if not os.path.exists(pth):
                    pth = pth.replace('/merge/', '/')
                    em.path = pth
                s_em_items.append(em)
            p_em_items = []
            for em in p_sign.extra_media_files:
                p_em_items.append(em)
            for s, p in zip(s_em_items, p_em_items):
                if s.path or p.path: # no empty rows
                    extra_media_node.addChild(MergeNode('extraMediaFile', s, p))

        if [t for t in s_sign.extra_texts if t.text] or [t for t in p_sign.extra_texts if t.text]:
            txt = qApp.instance().translate('ReconcileChangesDialog', "Notes")
            notes_node = MergeNode('notesLabel', txt, txt)
            sign_item.addChild(notes_node)

            s_extra_texts = [t for t in s_sign.extra_texts]
            p_extra_texts = [t for t in p_sign.extra_texts]
            for s_text, p_text in zip(s_extra_texts, p_extra_texts):
                notes_node.addChild(MergeNode('extraTexts', s_text, p_text))

        sign_item.updateSignMergeState()

    def infoReconciliationComplete(self):  
        merge_states = self.project_root_item.getChildMergeStates(self.project_root_item)
        if MERGE_UNDECIDED in merge_states:
            self.project_root_item.merge_state = MERGE_UNDECIDED
            return False        
        self.project_root_item.merge_state = MERGE_ACCEPTED
        return True

    def signReconciliationComplete(self):
        for i in self.sign_root_item._children:
            if i.merge_state == MERGE_UNDECIDED:
                self.sign_root_item.merge_state = MERGE_UNDECIDED
                return False
        self.sign_root_item.merge_state = MERGE_ACCEPTED
        return True

    def msgDlg(self, title, txt1, txt2):
        info = "<h3 style='color:blue'>{}</h3><p>{}</p>".format(txt1, txt2)            
        msgBox = QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setText(info)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.button(QMessageBox.Yes).setIcon(QIcon(":/thumb_up.png"))
        msgBox.button(QMessageBox.No).setIcon(QIcon(":/thumb_down.png"))
        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ReconcileChangesDialog', "Yes"))
        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ReconcileChangesDialog', "No"))
        return msgBox
    
    def hideEvent(self, evt):
        self.close_signal.emit()
        super(ReconcileChangesDialog, self).hideEvent(evt)
    
    def projectDataDeletionCheck(self): 
        if self.ignore_removal_check:
            return True
                   
        def counter(item):
            project = self.secondary_project
            data = item.data(SECONDARY_COL)
            if item.data(PRIMARY_COL):
                data = item.data(PRIMARY_COL)
                project = self.primary_project
            count_method = project.countSignsSensesGlossesForLanguage
            if item.data_type == 'grammarCategories':
                count_method = project.countSignsSensesForGramCat
            elif item.data_type == 'dialects':
                count_method = project.countSignsSensesForDialect
            return count_method(data.id)[0]
        
        lang_node = None
        cat_node = None
        dialect_node = None
        for item in self.project_root_item._children:
            if item.data_type == 'languageInfoLabel':
                lang_node = item
            elif item.data_type == 'grammarInfoLabel':
                cat_node = item
            elif item.data_type == 'dialectInfoLabel':
                dialect_node = item

        deleted_langs = []
        deleted_cats = []
        deleted_dialects = []
        for node, _list in [(lang_node, deleted_langs), (cat_node, deleted_cats), (dialect_node, deleted_dialects)]:
            if node:
                for item in node._children:
                    s_data = item.data(SECONDARY_COL)   
                    p_data = item.data(PRIMARY_COL)
                    if s_data.empty and not p_data.empty and item.merge_state == MERGE_ACCEPTED: # p lang deleted
                        _list.append(item)
                    elif not s_data.empty and p_data.empty and item.merge_state == MERGE_REJECTED: # s lang not included
                        _list.append(item)  
        checks = []
        if deleted_langs:
            checks.append((deleted_langs, qApp.instance().translate('ReconcileChangesDialog', "Written Languages")))
        if deleted_cats:
            checks.append((deleted_cats, qApp.instance().translate('ReconcileChangesDialog', "Grammar Categories")))
        if deleted_dialects:
            checks.append((deleted_dialects, qApp.instance().translate('ReconcileChangesDialog', "Dialects")))

        value = True
        if checks:
            dlg = OmissionChecksDlg(self, checks, counter)
            dlg.setFocusOnYesButton()
            qApp.instance().pm.startInactivityTimer(self)
            self.close_signal.connect(dlg.close) # in event of inactivity timeout
            dlg.exec_()                
            for item in dlg.items:
                if item.merge_state == MERGE_UNDECIDED:
                    value = False
                    break
            del dlg
        return value

    def populateProjectModel(self):
        self.setProjectItems()
        model = ProjectItemModel(self.project_root_item, self.project_tree)
        self.project_tree.setModel(model)
        for child in model.rootItem._children:
            idx = model.index(child.row(), 0)
            self.project_tree.expandRecursively(idx)     
        self.page = PAGE_INFO 
        self.next_btn.setEnabled(False)
        if self.project_root_item.reconciled:
            self.next_btn.setEnabled(True)                

    def populateSignModel(self):
        if self.projectDataDeletionCheck(): 
            self.next_btn.setVisible(False)
            self.collapse_signs_btn.setVisible(True)
            self.setSignItems()
            model = ProjectItemModel(self.sign_root_item, self.project_tree)
            self.project_tree.setModel(model)
            self.page = PAGE_SIGNS 
            if self.sign_root_item.reconciled:
                self.complete_merge_btn.setEnabled(True) 
        else:
            self.next_btn.setEnabled(False)
            self.project_root_item.merge_state = MERGE_UNDECIDED

    #https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists
    def __flat(self, _list): # [[1],[2],[3]] ==> [1,2,3]
        return [item for sublist in _list for item in sublist]
    
    def showEvent(self, evt):
        qApp.restoreOverrideCursor() 
        super(ReconcileChangesDialog, self).showEvent(evt) 

    def adjustWrittenLangs(self, s_written_langs, p_written_langs):
        s_langs = []
        p_langs = []
        for lang in self.all_written_languages:
            s_lang = None
            try:
                s_lang = [l for l in s_written_langs if l.id == lang.id][0]
            except:
                s_lang = WrittenLanguage({'langId':lang.id, 'langName': '', 'empty': True, 'order': lang.order})
            if s_lang:
                s_langs.append(s_lang)
            p_lang = None
            try:
                p_lang = [l for l in p_written_langs if l.id == lang.id][0]
            except:
                p_lang = WrittenLanguage({'langId':lang.id, 'langName': '', 'empty': True, 'order': lang.order})
            if p_lang:
                p_langs.append(p_lang)
        s_langs.sort(key=lambda x: x.order)
        p_langs.sort(key=lambda x: x.order) 
        return s_langs, p_langs

    def adjustGrammarCategories(self, s_grammar_cats, p_grammar_cats):
        s_cats = []
        p_cats = []
        for cat in self.all_grammar_categories:
            s_cat = None
            try:
                s_cat = [c for c in s_grammar_cats if c.id == cat.id][0]
            except:
                # name included here for ordering purposes; removed later
                s_cat = GrammarCategory({'id': cat.id, 'name': cat.name, 'empty': True})
            if s_cat:
                s_cats.append(s_cat)
            p_cat = None
            try:
                p_cat = [c for c in p_grammar_cats if c.id == cat.id][0]
            except:
                # name included here for ordering purposes; removed later
                p_cat = GrammarCategory({'id': cat.id, 'name': cat.name, 'empty': True})
            if p_cat:
                p_cats.append(p_cat)
        # order by name
        s_cats.sort(key=lambda x: x.name.lower())
        p_cats.sort(key=lambda x: x.name.lower()) 
        # name only used for ordering; empty name should be ''
        for _list in [s_cats, p_cats]:
            for d in _list:
                if d.empty:
                    d.name = ''
        return s_cats, p_cats

    def adjustDialects(self, s_dialects, p_dialects):
        s_dials = []
        p_dials = []
        for dialect in self.all_dialects:
            s_dial = None
            try:
                s_dial = [d for d in s_dialects if d.id == dialect.id][0]
            except:
                # name included here for ordering purposes; removed later
                s_dial = Dialect({'id': dialect.id, 'name': dialect.name, 'abbr': '', 'focal': dialect.focal, 'empty': True})
            if s_dial:
                s_dials.append(s_dial)
            p_dial = None
            try:
                p_dial = [d for d in p_dialects if d.id == dialect.id][0]
            except:
                # name included here for ordering purposes; removed later
                p_dial = Dialect({'id': dialect.id, 'name': dialect.name, 'abbr': '', 'focal': dialect.focal, 'empty': True})
            if p_dial:
                p_dials.append(p_dial)
        # order by name
        s_dials.sort(key=lambda x: x.name.lower())
        p_dials.sort(key=lambda x: x.name.lower()) 
        # name only used for ordering; empty name should be ''
        for _list in [s_dials, p_dials]:
            for d in _list:
                if d.empty:
                    d.name = ''
        # use focal from primary project
        for s, p in zip(s_dials, p_dials):
            s.focal = p.focal
        return s_dials, p_dials

    def adjustSigns(self, sign_ids):
        secondary_signs = []
        primary_signs = []
        for sign_id in sign_ids:
            s_sign = self.secondary_project.getSign(sign_id)
            p_sign = self.primary_project.getSign(sign_id)
            if not s_sign and not p_sign:
                continue
            if not s_sign:
                jsn = {'id': sign_id,
                    'path': '',
                    'hash': '',
                    'componentCodes': [],
                    'senses': [],
                    'extraMediaFiles': [],
                    'extraTexts': [],
                    'empty': True
                    }
                s_sign = Sign(self.secondary_project, jsn)  
                self.secondary_project.signs.append(s_sign) 
            elif not p_sign:
                jsn = {'id': sign_id,                
                    'path': '',
                    'hash': '',
                    'componentCodes': [],
                    'senses': [],
                    'extraMediaFiles': [],
                    'extraTexts': [],
                    'empty': True
                    }
                p_sign = Sign(self.primary_project, jsn)  
                self.primary_project.signs.append(p_sign)
       
            self.sortSenses(s_sign, p_sign)       
            for s_sense, p_sense in zip(s_sign.senses, p_sign.senses):
                s_sents = s_sense.sentences
                p_sents = p_sense.sentences
                self.sortSentences(s_sents, p_sents)
            self.sortExtraMedia(s_sign.extra_media_files, p_sign.extra_media_files)

            secondary_signs.append(s_sign)
            primary_signs.append(p_sign)
        return secondary_signs, primary_signs
    
    def sortSentences(self, s_sentences, p_sentences):
        for s_sent in s_sentences:
            p_sents = [p_sent for p_sent in p_sentences if self.sameSentence(s_sent, p_sent)]
            if not p_sents:
                p = Sentence(self.primary_project, 
                    {'id': s_sent.id, 
                    'path': '',
                    'hash': '',
                    'sentenceTexts': [], 
                    'empty': True})
                p.sentence_texts = []
                p_sentences.append(p) 
                s_sent.order = len(p_sentences)
            else:
                if len(p_sents) > 1: # get closest match; bring highest ration to front of list
                    p_sents.sort(key=lambda x: self.sameSentence(s_sent, x))
                    p_sents.reverse()
                p_sent = p_sents[0]
                s_sent.order = p_sentences.index(p_sent)
        for p_sent in p_sentences:
            order = p_sentences.index(p_sent)
            p_sent.order = order
            s_sents = [s_sent for s_sent in s_sentences if not s_sent.empty and self.sameSentence(s_sent, p_sent)]
            if not s_sents:
                s = Sentence(self.secondary_project, 
                    {'id': p_sent.id, 
                    'path': '',
                    'hash': '',
                    'sentenceTexts': [], 
                    'empty': True})
                s.sentence_texts = []
                s_sentences.append(s)
                s.order = order
            else:
                if len(s_sents) > 1: # get closest match; bring highest ration to front of list
                    s_sents.sort(key=lambda x: self.sameSentence(x, p_sent))
                    s_sents.reverse()
                s = s_sents[0]
                s.order = order                
        s_sentences.sort(key=lambda x: int(x.order))

    def __mediaOrder(self, path):
        if qApp.instance().pm.isVideo(path):
            return 0
        return 1
    
    def sortExtraMedia(self, secondary_files, primary_files):
        for s_media in secondary_files:
            p_medias = [pm for pm in primary_files if pm.id == s_media.id]
            if not p_medias:
                p_media = ExtraMediaFile(self.primary_project, {'id': s_media.id, 'path': s_media.path, 'empty': True})
                primary_files.append(p_media)
        for p_media in primary_files:
            if p_media.empty:
                continue
            s_medias = [sm for sm in secondary_files if sm.id == p_media.id]
            if not s_medias:
                s_media = ExtraMediaFile(self.secondary_project, {'id': p_media.id, 'path': p_media.path, 'empty': True})
                secondary_files.append(s_media)
        secondary_files.sort(key=lambda x: (self.__mediaOrder(x.path), x.id))
        primary_files.sort(key=lambda x: (self.__mediaOrder(x.path), x.id))
        # # sort by video(0) or picture(1), then by id
        # # https://stackoverflow.com/questions/4233476/sort-a-list-by-multiple-attributes

        # only required path in empties for sorting purposes; remove them now
        for sf, pf in zip(secondary_files, primary_files):
            if pf.empty: 
                pf.path = ''
            if sf.empty: 
                sf.path = ''        

    def sortSenses(self, s_sign, p_sign):
        secondary_senses = s_sign.senses
        primary_senses = p_sign.senses
        for sense in secondary_senses:
            sense.gloss_texts.sort(key=lambda x: int(x.lang_id))
            for sent in sense.sentences:
                sent.sentence_texts.sort(key=lambda x: int(x.lang_id))
        for sense in primary_senses:
            sense.gloss_texts.sort(key=lambda x: int(x.lang_id))
            for sent in sense.sentences:
                sent.sentence_texts.sort(key=lambda x: int(x.lang_id))

        self.secondary_project.ignore_duplicate_sense_id_check = True
        self.primary_project.ignore_duplicate_sense_id_check = True
        for s_sense in secondary_senses:
            p_senses = [p_sense for p_sense in primary_senses if self.sameSense(s_sense, p_sense)]
            if not p_senses:
                s_sense_id = int(s_sense.id)
                if s_sense_id in self.primary_project.old_sense_ids:
                    while s_sense_id in self.primary_project.old_sense_ids:
                        s_sense_id += 1
                    self.primary_project.old_sense_ids.append(s_sense_id)
                    s_sense.id = s_sense_id
                jsn = {'id': s_sense_id,
                    'grammarCategoryId': None,
                    'dialectIds': [],
                    'glossTexts': [],
                    'sentences': [],
                    'empty': True
                    }
                p_sense = Sense(self.primary_project, jsn, int(s_sense.sign_id))                   
                primary_senses.append(p_sense) 
                p_order = primary_senses.index(p_sense) + 1
                s_sense.p_order = p_order
                p_sense.p_order = p_order
                s_order = secondary_senses.index(s_sense) + 1
                s_sense.s_order = s_order
                p_sense.s_order = s_order
            else:
                if len(p_senses) > 1: # get closest match; bring highest ratio to front of list
                    p_senses.sort(key=lambda x: self.sameSense(s_sense, x))
                    p_senses.reverse()
                p_sense = p_senses[0]

                s_order = secondary_senses.index(s_sense) + 1
                s_sense.s_order = s_order
                p_sense.s_order = s_order
                p_order = primary_senses.index(p_sense) + 1
                s_sense.p_order = p_order
                p_sense.p_order = p_order
                
        for p_sense in primary_senses:
            if p_sense.empty:
                continue # empty added above
            p_order = primary_senses.index(p_sense) + 1
            p_sense.p_order = p_order
            s_senses = [s_sense for s_sense in secondary_senses if self.sameSense(s_sense, p_sense)]
            if not s_senses:
                jsn = {'id': int(p_sense.id),
                    'grammarCategoryId': None,
                    'dialectIds': [],
                    'glossTexts': [],
                    'sentences': [],
                    'empty': True
                    }
                s_sense = Sense(self.secondary_project, jsn, int(p_sense.sign_id)) 
                s_sense.p_order = p_order
                secondary_senses.append(s_sense)
                s_order = secondary_senses.index(s_sense) + 1
                s_sense.s_order = s_order
                p_sense.s_order = s_order
            else:
                if len(s_senses) > 1: # get closest match; bring highest ration to front of list
                    s_senses.sort(key=lambda x: self.sameSense(x, p_sense))
                    s_senses.reverse()
                s_sense = s_senses[0]
                s_sense.p_order = p_order
                s_order = secondary_senses.index(s_sense) + 1
                s_sense.s_order = s_order
                p_sense.s_order = s_order

        secondary_senses.sort(key=lambda x: int(x.p_order)) # default preserves primary order, but user may alter to secondary order
        # secondary_senses.sort(key=lambda x: int(x.s_order))
        # primary_senses.sort(key=lambda x: int(x.s_order))

        # sorting may have matched up some empty senses, and missed some others
        for s, p in zip_longest(reversed(secondary_senses), reversed(primary_senses)):
            # sorting may have missed adding some empty senses; add them here
            if not s: # missed adding on secondary side
                jsn = {'id': int(p.id),
                    'grammarCategoryId': None,
                    'dialectIds': [],
                    'glossTexts': [],
                    'sentences': [],
                    'empty': True
                    }
                s_sense = Sense(self.secondary_project, jsn, int(p.sign_id))
                secondary_senses.append(s_sense) 
                s_sense.s_order = secondary_senses.index(s_sense) + 1
                s_sense.p_order = p.p_order
            elif not p: # missed adding on primary side
                s_sense_id = s.id # ensure sense id unique on primary side
                if s_sense_id in self.primary_project.old_sense_ids:
                    while s_sense_id in self.primary_project.old_sense_ids:
                        s_sense_id += 1
                    self.primary_project.old_sense_ids.append(s_sense_id)
                    s.id = s_sense_id
                jsn = {'id': int(s.id),
                    'grammarCategoryId': None,
                    'dialectIds': [],
                    'glossTexts': [],
                    'sentences': [],
                    'empty': True
                    }
                p_sense = Sense(self.secondary_project, jsn, int(s.sign_id)) 
                primary_senses.append(p_sense)
                p_sense.s_order = s.s_order
                p_sense.p_order = primary_senses.index(p_sense) + 1
            elif s.empty and p.empty:
                secondary_senses.remove(s)
                primary_senses.remove(p)
        
        self.secondary_project.ignore_duplicate_sense_id_check = False
        self.primary_project.ignore_duplicate_sense_id_check = False        

    def sameSense(self, s_sense, p_sense, precision=0.6):
        # use this test for faster comparison; should avoid the errors from 0.9.3
        if len(str(s_sense.id)) > 5 and len(str(p_sense.id)) > 5 and s_sense.id == p_sense.id:
            return True
        elif len(str(s_sense.id)) > 5 and len(str(p_sense.id)) > 5 and s_sense.id != p_sense.id:
            return False
        
        if s_sense.id != p_sense.id:
            pass_score = 0.0
            score = 0.0
            s_gloss_texts = [t.text for t in s_sense.gloss_texts]
            p_gloss_texts = [t.text for t in p_sense.gloss_texts]
            for s, p in zip(s_gloss_texts, p_gloss_texts):
                if s and p:
                    # allow for synonymns; split by ';' and compare
                    ss = s.split(';')
                    ps = p.split(';') 
                    for _s, _p in zip_longest(ss, ps):
                        if _s and _p:
                            _s = _s.strip()
                            _p = _p.strip()
                            ratio = difflib.SequenceMatcher(None, _s, _p).ratio()
                            pass_score += precision
                            score += ratio
                    if score < pass_score:
                        return False
                    else:
                        return score
        return 1.0
    
    def sameSentence(self, s_sent, p_sent, precision=0.6):
        # let's don't test by id as I've seen at least one error where ids were equal but different sentences
        # use this test first for faster comparison; should avoid the errors from 0.9.3
        if len(str(s_sent.id)) > 5 and len(str(p_sent.id)) > 5 and s_sent.id == p_sent.id:
            return True
        elif len(str(s_sent.id)) > 5 and len(str(p_sent.id)) > 5 and s_sent.id != p_sent.id:
            return False

        # test paths
        if s_sent.path and not os.path.exists(s_sent.path) and os.path.basename(s_sent.path) == os.path.basename(p_sent.path): 
            # only unchanged sent videos copied into merge directory; should be same as p_path; yes!!!
            return True

        # test texts    
        s_sent_texts = [t.text for t in s_sent.sentence_texts]
        p_sent_texts = [t.text for t in p_sent.sentence_texts]
        pass_score = 0.0
        score = 0.0
        for s, p in zip(s_sent_texts, p_sent_texts):
            if s and p: 
                ratio =  difflib.SequenceMatcher(None, s, p).ratio()
                pass_score += precision
                score += ratio
        if score < pass_score:
            return False
        return True    
    
class MergeNode(object):
    def __init__(self, data_type, secondary_data, primary_data, parent=None):
        self.editing = False
        self.data_type = data_type
        # if data_type == 'projectLogo':
        #     # secondary_data = self.findPathById(secondary_data)
        #     # primary_data = self.findPathById(primary_data)
        # elif data_type in ['signPath', 'sentencePath']:
        #     # secondary_data = (self.findPathById(secondary_data[0]), secondary_data[1])
        #     # primary_data = (self.findPathById(primary_data[0]), primary_data[1])
        # elif data_type == 'extraMediaFile':
        #     # secondary_data.path == self.findPathById(secondary_data.path)
        #     # primary_data.path = self.findPathById(primary_data.path)
        self.s_data = secondary_data
        self.p_data = primary_data
        self.edited_data = ''

        self._columncount = 6
        self._children = []
        self._hidden_children = []
        self._parent = parent
        self._row = 0
        self._column = 0

        self.expanded = False
        self.movable = 0
        self.height = 0

        self.sign_data_types = [
            'signsLabel',
            'signId',
            'signPath',
            #'hashType', ## now storing hash data along with path data: ._data = (path, hash) for signPath, sentencePath types
            'componentCodes',
            'senseOrder',
            'senseId',
            'dialectIds',
            'grammarCategoryId',
            'glossTexts',
            'sentencePath',
            'sentenceId',
            'sentenceTexts',
            'extraMediaFile',
            'extraTexts']

        self.merge_state = MERGE_UNDECIDED
        if data_type in self.sign_data_types and data_type != 'signId': # some types want initial states
            if data_type == 'senseId':
                self.merge_state = MERGE_NONE
            elif primary_data and self.sDataEmpty():
                self.merge_state = MERGE_REJECTED
            elif secondary_data and self.pDataEmpty:
                self.merge_state = MERGE_ACCEPTED
            elif self.equalData():
                self.merge_state = MERGE_NONE

    def dataIsEmpty(self, data):
        if ((hasattr(data, 'empty') and data.empty) or \
            (hasattr(data, 'text') and not data.text.strip()) or \
            (hasattr(data, 'path') and not data.path) or \
            (isinstance(data, (list, tuple)) and data and not data[0]) or \
            not data):
                return True
        return False
    
    def sDataEmpty(self):
        return self.dataIsEmpty(self.s_data)
    
    def pDataEmpty(self):
        return self.dataIsEmpty(self.p_data)

    @property
    def reconciled(self):
        if not self.merge_state == MERGE_UNDECIDED:
            return True
        return False

    def data(self, column):
        if column == SECONDARY_COL:
            return self.s_data
        elif column == PRIMARY_COL:
            return self.p_data
        else:
            return ''

    def columnCount(self):
        return self._columncount
    
    def hasChildren(self):
        if self.childCount():
            return True
        return False

    def childCount(self):
        return len(self._children)

    def child(self, row):
        if row >= 0 and row < self.childCount():
            return self._children[row]

    def parent(self):
        return self._parent

    def row(self):
        return self._row
    
    def column(self):
        return self._column

    def addChild(self, child):
        child._parent = self
        child._row = len(self._children)
        self._children.append(child)

    def bumpMergeState(self):
        if self.merge_state > 0:
            #self.merge_count += 1
            if self.merge_state < 4:
                self.merge_state += 1
            else:
                self.merge_state = 1
            if self.merge_state == MERGE_EDITED and not self.edited_data:
                self.bumpMergeState()
            elif self.data_type in self.sign_data_types:
                if self.data_type in ['signId', 'senseId']:
                    self.updateChildrenMergeStates()
                    if self.data_type == 'senseId':
                        self.updateSignMergeState()
                else:
                    self.updateSignMergeState()

    def updateChildrenMergeStates(self):
        state = self.merge_state
        def setChildStates(_item):
            if _item and _item.childCount():
                for child in _item._children:
                    if child.merge_state in [MERGE_ACCEPTED, MERGE_REJECTED, MERGE_EDITED, MERGE_UNDECIDED]:
                            child.merge_state = state
                    if child.childCount():
                        setChildStates(child)
        setChildStates(self)

    def updateSignMergeState(self):
        def setStates(_item):
            merge_states = self.getChildMergeStates(_item)
            if MERGE_UNDECIDED in merge_states:
                _item.merge_state = MERGE_UNDECIDED
            elif len(merge_states) == 1:
                _item.merge_state = merge_states[0]
            elif len(merge_states) > 1:
                _item.merge_state = MERGE_MIXED
            else:
                _item.merge_state = MERGE_NONE
        item = self
        sense_item = None
        while item and item.data_type != 'signId':
            item = item.parent()
            if item and item.data_type == 'senseId':
                sense_item = item
        if sense_item:
            setStates(sense_item)
        if item:
            setStates(item)

    def updateSenseMergeStates(self):
        sense_nodes = [child for child in self._children if child.data_type == 'senseId']
        for node in sense_nodes:
            merge_states = self.getChildMergeStates(node)
            if MERGE_UNDECIDED in merge_states:
                node.merge_state = MERGE_UNDECIDED
            elif len(merge_states) == 1:
                node.merge_state = merge_states[0]
            elif len(merge_states) > 1:
                node.merge_state = MERGE_MIXED
            else:
                node.merge_state = MERGE_NONE

    def getChildMergeStates(self, item):
        merge_states = []
        def addStates(_item):
            for child in _item._children:
                if child.merge_state not in merge_states and \
                    child.data_type not in ['signId', 'extraMediaLabel', 'sentenceId'] and \
                    child.merge_state in [MERGE_ACCEPTED, MERGE_REJECTED, MERGE_EDITED, MERGE_UNDECIDED] and \
                    not child.equalData():
                        merge_states.append(child.merge_state)
                if child.childCount():
                    addStates(child)
        if item and item.childCount():
            addStates(item)
        return merge_states
    
    def equalData(self):
        value = False
        data_type = self.data_type
        s_data = self.s_data
        p_data = self.p_data
        if data_type in ['projectLogo', 'signPath', 'sentencePath', 'extraMediaFile']:
            s_path = ''
            p_path = ''
            if data_type == 'projectLogo':
                s_path = s_data
                p_path = p_data
            elif data_type in ['signPath', 'sentencePath']:
                s_path = s_data[0]
                p_path = p_data[0]
            elif data_type == 'extraMediaFile':
                s_path = s_data.path
                p_path = p_data.path
            if not s_path and not p_path:
                value = True
            elif not s_path or not p_path:
                value = False
            else:
                value = filecmp.cmp(s_path, p_path, shallow=False)
        elif data_type in ['writtenLanguages', 'grammarCategories', 'dialects']: 
            if s_data.empty or p_data.empty:
                value = False
            else:
                value = (s_data.name == p_data.name)
        elif data_type in ['glossTexts', 'sentenceTexts', 'extraTexts']:
            value = (s_data.text.strip() == p_data.text.strip())
        elif data_type in ['componentCodes', 'dialectIds']: # all lists
            value = (s_data == p_data)
        elif data_type in ['senseId', 'grammarCategoryId']:
            data_type, s_data, p_data
            value = (s_data == p_data)
        elif isinstance(s_data, str):
            value = (s_data == p_data)
        elif data_type in ['signId']:
            # return state of children
            value = False
        if value and self.merge_state >= 0:
            self.merge_state = MERGE_NONE
        return value
    
    def findPathById(self, path):
        if os.path.exists(path) or not path:
            return path        
        # difficulty with (e.g. Arabic) filenames; find file by id
        _id = os.path.splitext(path)[0].split('_id')[-1]
        _dir = os.path.dirname(path)
        paths = glob.glob(f"{_dir}/*_id{_id}.*")
        if paths:
            return paths[0].replace('\\', '/')
        return ''
    
class ProjectItemModel(QAbstractItemModel):        
    def __init__(self, root_item, parent=None):
        super(ProjectItemModel, self).__init__(parent)
        self.tree = parent        

        expanded_pxm = QPixmap(':/expanded.png')
        collapsed_pxm = QPixmap(':/collapsed.png') 
        expanded_hover_pxm = QPixmap(':/expanded_hover.png')
        collapsed_hover_pxm = QPixmap(':/collapsed_hover.png') 
        # collapsed icon
        icn_height = QFontMetrics(parent.font()).height()
        self.collapsed_icn = QIcon(collapsed_pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        self.collapsed_icn.addPixmap(collapsed_hover_pxm.scaledToHeight(icn_height, Qt.SmoothTransformation), mode=QIcon.Active)
        # expanded icon
        icn_height = QFontMetrics(parent.font()).height() + 3
        self.expanded_icn = QIcon(expanded_pxm.scaledToHeight(icn_height, Qt.SmoothTransformation)) 
        self.expanded_icn.addPixmap(expanded_hover_pxm.scaledToHeight(icn_height, Qt.SmoothTransformation), mode=QIcon.Active)

        self.mouseover_index = None
        self.rootItem = root_item

    def rowCount(self, index):
        if index.isValid():
            return index.internalPointer().childCount()
        return self.rootItem.childCount()

    def addChild(self, node, _parent):
        if not _parent or not _parent.isValid():
            parent = self.rootItem
        else:
            parent = _parent.internalPointer()
        parent.addChild(node)

    def index(self, row, column, _parent=QModelIndex()):
        if not _parent or not _parent.isValid():
            parent = self.rootItem
        else:
            parent = _parent.internalPointer()

        if not QAbstractItemModel.hasIndex(self, row, column, _parent):
            return QModelIndex()

        child = parent.child(row)
        if child:
            return QAbstractItemModel.createIndex(self, row, column, child)
        else:
            return QModelIndex()

    def parent(self, index):
        if index.isValid():
            p = index.internalPointer().parent()
            if p:
                return QAbstractItemModel.createIndex(self, p.row(), 0, p)
        return QModelIndex()

    def columnCount(self, index):
        return 6
    
    def data(self, index, role):
        if not index.isValid():
            return None
        item = index.internalPointer()
        data_type = item.data_type
        col = index.column()
        if not item.height:
            item.height = QFontMetrics(self.tree.font()).height()

        style_color = QColor('#e0ffff') #lightcyan #Qt.cyan #primary
        if col == SECONDARY_COL:
            style_color = QColor('#ffffe0') #lightyellow #Qt.yellow 

        _data = item.data(index.column())
        if role == Qt.DisplayRole:
            if col == PRIMARY_COL:
                if item.merge_state in [MERGE_ACCEPTED, MERGE_MIXED] and not item.sDataEmpty():
                    _data = item.data(SECONDARY_COL)
                elif item.merge_state == MERGE_EDITED:
                    _data = item.edited_data
            if _data and col in [SECONDARY_COL, PRIMARY_COL]:
                if data_type == 'projectLogo':
                    return os.path.basename(_data)
                elif (data_type in 'projectDescription' and 
                    col == PRIMARY_COL and 
                    item.merge_state in [MERGE_ACCEPTED, MERGE_EDITED]):
                        return '' # will be painted in html
                elif data_type == 'sentencePath':
                    return '' # will be painted in html
                elif data_type == 'signId':
                    if item.expanded:
                        if col == 0 and not self.tree.isExpanded(index):
                            self.tree.expandRecursively(index)
                        return ''
                    else:
                        senses = [s for s in _data.senses]
                        texts = []
                        for sense in senses:
                            #print(sense)
                            gloss_texts = sense.gloss_texts
                            gts = [t for t in gloss_texts if t.lang_id == qApp.instance().pm.search_lang_id]
                            if gts:
                                gt = gts[0]
                                txt = gt.text.strip()
                                if txt:
                                    texts.append(txt)
                        display_text = ''
                        if texts and len(texts) > 1:
                            display_text = ' | '.join(texts)
                        elif texts:
                            display_text = texts[0]
                        return display_text
                elif data_type == 'signPath':
                    pth = os.path.basename(_data[0]) # (path, hash)
                    return pth
                elif data_type == 'senseId': # (sign_id, sense_id, s_order, p_order)
                    order = _data[2]
                    if col == PRIMARY_COL:
                        order = _data[3]
                    txt = qApp.translate('ProjectItemModel', 'Sense')
                    txt = f'{txt} ({order})'
                    return txt
                elif data_type == 'componentCodes':
                    return '' #_data = list of codes; widget added in delegate
                elif data_type == 'dialectIds':
                    project = self.tree.secondary_project
                    if col == PRIMARY_COL:
                        project = self.tree.primary_project
                    return self.tree.dialectStr(_data, project)
                elif data_type == 'grammarCategoryId':
                    return self.tree.getGramCatDisplayText(_data)
                elif data_type in ['glossTexts', 'sentenceTexts', 'extraTexts']:
                    if hasattr(_data, 'text'):
                        return _data.text.strip()
                    return _data.strip()
                elif data_type == 'sentencePath':
                    pth = os.path.basename(_data[0])
                    txt = qApp.translate('ProjectItemModel', 'Example:')
                    txt = f'{txt} {pth}'
                    return txt
                elif data_type == 'extraMediaFile':
                    return os.path.basename(_data.path)
                elif data_type in ['writtenLanguages', 'grammarCategories', 'dialects']:
                    return _data.name
            return _data
        elif role == Qt.DecorationRole: # where icons are set
            icn_height = QFontMetrics(self.tree.font()).height() - 4
            if item.data_type in ['signId']:
                icn_height += 3
            if col == SECONDARY_COL and item.movable == MOVE_ITEM_TARGET:
                return QIcon(QPixmap(':/target.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
            elif (_data and col in [SECONDARY_COL, PRIMARY_COL]) or \
                (col == PRIMARY_COL and item.merge_state == MERGE_ACCEPTED):
                    if data_type == 'signId':        
                        if item.expanded:
                            return self.expanded_icn
                        return self.collapsed_icn
                    elif data_type == 'senseId':
                        return QIcon(QPixmap(':/hand_up.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif data_type == 'dialectIds':
                        return QIcon(QPixmap(':/dialect_small.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif data_type == 'grammarCategoryId':
                        return QIcon(QPixmap(':/gram_cat.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif data_type == 'extraMediaLabel':
                        return QIcon(QPixmap(':/video24.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif data_type == 'notesLabel':
                        return QIcon(QPixmap(':/list.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif data_type in ['signPath', 'sentencePath', 'extraMediaFile', 'projectLogo']:
                        return QIcon(QPixmap(':/play.png').scaledToHeight(icn_height+3, Qt.SmoothTransformation))
            elif col == DECISION_COL:
                if data_type not in ['signsLabel', 'extraMediaLabel', 'notesLabel', 'projectInfoLabel', 'languageInfoLabel', 'grammarInfoLabel', 'dialectInfoLabel']:
                    if hasattr(item, 'editing') and item.editing:
                        return None
                    elif item.equalData():
                        #item.merge_state = MERGE_NONE
                        pxm = QPixmap(':/equals.png')
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif item.merge_state == MERGE_UNDECIDED: # 1
                        pxm = QPixmap(':/merge_question.png') 
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif item.merge_state == MERGE_EDITED: # 2
                        pxm = QPixmap(':/merge_edited.png')
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif item.merge_state == MERGE_ACCEPTED: # 3
                        pxm = QPixmap(':/merge_accept.png')
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif item.merge_state == MERGE_REJECTED: # 4
                        pxm = QPixmap(':/merge_reject.png')  
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
                    elif item.merge_state == MERGE_MIXED:
                        pxm = QPixmap(':/merge_mixed.png')  # default rejected 
                        return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation)) 
            elif col == EDIT_COL:
                if data_type in ['projectName',
                    'signLanguage',
                    'versionId',
                    'projectCreator',
                    'projectDescription', 
                    'glossTexts', 
                    'sentenceTexts', 
                    'extraTexts']:
                    if not item.equalData():
                        return QIcon(QPixmap(':/edit_sign.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
            elif col == MOVE_UP_COL and item.merge_state in [MERGE_UNDECIDED, MERGE_IGNORE]:
                if data_type in ['writtenLanguages', 'grammarCategories', 'dialects']:
                    above = self.emptyItemAbove(item)
                    if above:
                        return QIcon(QPixmap(':/up.png').scaledToHeight(icn_height, Qt.SmoothTransformation)) 
            elif col == MOVE_DOWN_COL and item.merge_state in [MERGE_UNDECIDED, MERGE_IGNORE]:
                if data_type in ['writtenLanguages', 'grammarCategories', 'dialects']:
                    below = self.emptyItemBelow(item)
                    if below:
                        return QIcon(QPixmap(':/down.png').scaledToHeight(icn_height, Qt.SmoothTransformation))
            return None
        elif role == Qt.ToolTipRole:
            if col == DECISION_COL:
                tip = qApp.instance().translate('ReconcileChangesDialog', 'Accept or Reject differences.')
                if item.merge_state == MERGE_UNDECIDED:
                    tip2 = qApp.instance().translate('ReconcileChangesDialog', 'Undecided')
                    tip = '<b>{}</b><br>({})'.format(tip, tip2)
                    return tip
                if item.merge_state == MERGE_ACCEPTED:
                    tip2 = qApp.instance().translate('ReconcileChangesDialog', 'Secondary accepted over Primary')
                    tip = '<b>{}</b><br>({})'.format(tip, tip2)
                    return tip
                elif item.merge_state == MERGE_EDITED:
                    tip2 = qApp.instance().translate('ReconcileChangesDialog', 'Secondary rejected; Primary retained with edits')
                    tip = '<b>{}</b><br>({})'.format(tip, tip2)
                    return tip
                elif item.merge_state == MERGE_REJECTED:
                    tip2 = qApp.instance().translate('ReconcileChangesDialog', 'Secondary rejected; Primary unchanged')
                    tip = '<b>{}</b><br>({})'.format(tip, tip2)
                    return tip
                elif item.merge_state == MERGE_MIXED:
                    tip2 = qApp.instance().translate('ReconcileChangesDialog', 'Secondary and Primary changes')
                    tip = '<b>{}</b><br>({})'.format(tip, tip2)
                    return tip
                else:
                    return ''
            elif col == EDIT_COL:
                if data_type in ['projectDescription', 'glossTexts', 'sentenceTexts', 'extraTexts']:
                    tip = qApp.instance().translate('ReconcileChangesDialog', 'Manually edit Primary text.')
                    return tip                
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignLeft|Qt.AlignTop
        elif role == Qt.FontRole:
            font = self.tree.font()
            if _data and col in [SECONDARY_COL, PRIMARY_COL]:
                if data_type in [
                    'projectInfoLabel', 
                    'languageInfoLabel',
                    'grammarInfoLabel',
                    'dialectInfoLabel',
                    'signsLabel',
                    'signId',
                    'senseOrder',
                    'senseId', 
                    'extraMediaLabel',
                    'notesLabel']:                        
                        font.setBold(True)
                if col == SECONDARY_COL and item.merge_state in [MERGE_REJECTED, MERGE_EDITED]:
                    font.setStrikeOut(True)
                elif col == PRIMARY_COL and item.merge_state == MERGE_ACCEPTED and item.sDataEmpty():
                    font.setStrikeOut(True)
                elif col == SECONDARY_COL and item.movable:
                    font.setItalic(True)
            return font
        elif role == Qt.BackgroundRole:
            if col == SECONDARY_COL and item.movable:
                return QBrush(Qt.blue)
        elif role == Qt.ForegroundRole:
            if col == SECONDARY_COL and item.movable:
                return QBrush(Qt.white)
            if col == SECONDARY_COL and item.merge_state in [MERGE_REJECTED, MERGE_EDITED]:
                return QBrush(Qt.gray)
            elif col == PRIMARY_COL and item.merge_state == MERGE_ACCEPTED and item.sDataEmpty():
                return QBrush(Qt.gray)
            elif col == PRIMARY_COL and item.merge_state in [MERGE_ACCEPTED, MERGE_MIXED]:
                return QBrush(Qt.red)
            elif col == PRIMARY_COL and item.merge_state == MERGE_EDITED:
                return QBrush(Qt.red)
        elif role == Qt.SizeHintRole: 
            _height = QFontMetrics(self.tree.font()).height() + 6 #fm.height()+fm.descent()+6
            _width = self.tree.columnWidth(col) - 32
            _size = QSize(_width, _height)  
            if col in [SECONDARY_COL, PRIMARY_COL]: 
                if self.tree.indexWidget(index): # componentCodes and indexes while editing
                    _size = self.tree.indexWidget(index).sizeHint()
                elif data_type in ['projectName',
                    'signLanguage',
                    'versionId',
                    'projectCreator',
                    'projectDescription',
                    'writtenLanguages',
                    'grammarCategories',
                    'dialects',
                    'sentencePath', 
                    'glossTexts', 
                    'sentenceTexts', 
                    'extraTexts', 
                    'signId']:
                        font = self.tree.font()
                        font.setBold(True)
                        _size = self.getDocSize(index, font, _width)
            return _size
        return None
    
    def emptyItemAbove(self, item):
        # find empty item above an item which requires reconciling
        row = item.row()
        s_data = item.data(SECONDARY_COL)
        p_data = item.data(PRIMARY_COL)
        if row > 0 and not s_data.empty:# and p_data.empty:
            while row > 0:
                row -= 1
                item_above = item.parent().child(row)
                s_data = item_above.data(SECONDARY_COL)
                p_data = item_above.data(PRIMARY_COL)
                if item_above.merge_state in [MERGE_UNDECIDED, MERGE_IGNORE] and s_data.empty:
                    return item_above
        return None

    def emptyItemBelow(self, item):
        # find empty item above an item which requires reconciling
        row = item.row()
        s_data = item.data(SECONDARY_COL)
        p_data = item.data(PRIMARY_COL)
        count = item.parent().childCount() - 1
        if row < count and not s_data.empty:# and p_data.empty:
            while row < count:
                row += 1
                item_below = item.parent().child(row)
                s_data = item_below.data(SECONDARY_COL)
                p_data = item_below.data(PRIMARY_COL)
                if item_below.merge_state in [MERGE_UNDECIDED, MERGE_IGNORE] and s_data.empty:
                    return item_below
        return None
    
    
    
    def getHtmlDisplay(self, index):
        style_color = QColor('#e0ffff') #lightcyan #Qt.cyan #primary
        item = index.internalPointer()
        merge_state = item.merge_state
        data_type = item.data_type
        if data_type == 'projectDescription':
            left_data = item.data(SECONDARY_COL)
            right_data = item.data(PRIMARY_COL)
            if merge_state == MERGE_EDITED:
                left_data = item.edited_data
            text = self.tree.inlineDiff(left_data, right_data)
            text = self.tree.replaceTags(text, style_color) 
            return text.strip()
        elif item.data_type == 'sentencePath':
            text = qApp.instance().translate('ProjectTreeItemDelegate', 'Example:')
            pth = os.path.basename(item.data(PRIMARY_COL)[0])
            if index.column() == SECONDARY_COL or merge_state == MERGE_ACCEPTED:
                pth = os.path.basename(item.data(SECONDARY_COL)[0])
            if index.column() == PRIMARY_COL and merge_state == MERGE_ACCEPTED:
                text = f"<b>{text}</b>&nbsp;&nbsp;<span style='color:red;'>{pth}</span>"
            elif index.column() == SECONDARY_COL and merge_state == MERGE_REJECTED:
                text = f"<b>{text}</b>&nbsp;&nbsp;<span style='color:gray; text-decoration:line-through;'>{pth}</span>" 
            else:
                text = f"<b>{text}</b>&nbsp;&nbsp;{pth}"
            text = f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{text}'
            return text
        else:
            return ''
    
    def getDocSize(self, index, font, _width):
        doc = QTextDocument()
        doc.setDefaultFont(font)
        item = index.internalPointer()
        text = index.data()
        if (index.column() == PRIMARY_COL and 
            item.data_type == 'projectDescription' and 
            item.merge_state == MERGE_ACCEPTED) or \
            item.data_type == 'sentencePath':
                text = self.getHtmlDisplay(index) 
                doc.setHtml(text)
        else:
            doc.setPlainText(text) # display role        
        doc.setTextWidth(_width)
        return doc.size()
    
    # def canFetchMore(self, index):
    #     if not index.isValid():
    #         return False
    #     item = index.internalPointer()
    #     return not item.is_loaded

    # def fetchMore(self, index):
    #     item = index.internalPointer()
    #     item.load_children()

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled
    
    def headerData(self, section, orientation, role): 
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == SECONDARY_COL:
                return qApp.instance().translate('ProjectItemModel', 'Secondary dictionary')
            elif section == PRIMARY_COL:
                return qApp.instance().translate('ProjectItemModel', 'Primary dictionary')
            else:
                return ''
        return None

class ProjectTreeView(QTreeView):
    item_size = pyqtSignal(str, QSize) 
    # drag_started = pyqtSignal(QTreeWidget)
    # drag_stopped = pyqtSignal(QTreeWidget)
    #highlite_move = pyqtSignal(QStandardItem, QStandardItem)

    def __init__(self, parent, secondary_project, primary_project):
        super(ProjectTreeView, self).__init__(parent)
        self.secondary_project = secondary_project
        self.primary_project = primary_project
        self.setItemsExpandable(False)
        self.setWordWrap(True)
        self.setAlternatingRowColors(False) # too confusing!!!
        self.setIndentation(0) #(16)
        self.setRootIsDecorated(True)
        self.setAutoScroll(False)
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.setSelectionMode(self.NoSelection)
        
        # from PyQt5.QtWidgets import QColorDialog    
        # clr = QColorDialog.getColor(QColor(Qt.gray).lighter())
        # #f0f0f6
        self.style_str = """QTreeView{outline:none; border:0;}
            QHeaderView::section{border:0;} 
            QTreeView::branch{border-image:url(none.png);}"""
        # QTreeView::item:selected{outline:none; border: 1px solid #f0f0f6; border-left: none; border-right: none;}
        #https://stackoverflow.com/questions/16018974/qtreeview-remove-decoration-expand-button-for-all-items; 
        self.setStyleSheet(self.style_str)
        
        self.setMouseTracking(True)
        self.mouse_over_item = None
        self.last_mouse_over_item = None
        self.move_target = None
        self.last_row = None
        self.last_column = None

        # self.last_this_item = None
        # self.last_other_item = None
        # self.last_decision_item = None
        # self.empty_text_str = ''
        # self.editing = False
        # self.editing_started = False
        # self.primary_editor = None
        self.editor_index = None
        self.item_media_viewers = []

        self.resizeTimer = QTimer(self)
        self.resizeTimer.timeout.connect(self.resizeFinished)        

    def inlineDiff(self, p_text, s_text):
        ##NOTE: diffs by character
        # matcher = difflib.SequenceMatcher(None, p_text, s_text)
        # def process_tag(tag, i1, i2, j1, j2):
        #     if tag == 'replace':
        #         return f'&remove;{matcher.a[i1:i2]}&/remove;&add;{matcher.b[j1:j2]}&/add;'
        #         #return f'&add;{matcher.b[j1:j2]}&/add;' # just show new characters when there is a replacement???
        #     if tag == 'delete':
        #         return f'&remove;{matcher.a[i1:i2]}&/remove;'
        #     if tag == 'equal':
        #         return matcher.a[i1:i2]
        #     if tag == 'insert':
        #         return f'&add;{matcher.b[j1:j2]}&/add;'
        #     assert False, "Unknown tag %r"%tag
        # txt = ''.join(process_tag(*t) for t in matcher.get_opcodes())

        ##NOTE: diffs by word instead of character, SequenceMatcher can be fed list of words
        ##NOTE: https://stackoverflow.com/questions/39001097/match-changes-by-words-not-by-characters
        a = p_text.split()
        b = s_text.split()
        ##NOTE: diffs by line
        # a = p_text.split('\n')
        # b = s_text.split('\n')
        matcher = difflib.SequenceMatcher(None, a, b)
        def process_tag(tag, i1, i2, j1, j2):
            if tag == 'replace':
                return f" &remove;{' '.join(matcher.a[i1:i2])}&/remove; &add;{' '.join(matcher.b[j1:j2])}&/add; "
            if tag == 'delete':
                return f"&remove;{' '.join(matcher.a[i1:i2])}&/remove;"
            if tag == 'equal':
                return ' '.join(matcher.a[i1:i2])
            if tag == 'insert':
                return f"&add;{' '.join(matcher.b[j1:j2])}&/add;"
            assert False, "Unknown tag %r"%tag
        op_codes = matcher.get_opcodes()
        txt = ''
        for opc in op_codes:
            txt = f"{txt}{''.join(process_tag(*opc))}"
        return txt
    
    def replaceTags(self, txt, style_color):
        txt = txt.replace('<', '&lt;')
        txt = txt.replace('>', '&gt;')
        txt = txt.replace('&lt;', '<br>&lt;')
        txt = txt.replace('<br>&lt;/', '&lt;/')
        txt = txt.replace('&add;', '<strong style="color:red;">').replace('&/add;', '</strong>')
        txt = txt.replace('&remove;', '<span style="color:gray; text-decoration:line-through;">').replace('&/remove;', '</span>')
        txt = txt.strip()
        if txt.startswith('<br>'):
            txt = txt.replace('<br>', '', 1)
        txt = f'<div style="background-color:{style_color.name()};">{txt}</div>'
        return txt

    def onMoveData(self, src_item, dst_item):
        src_data = src_item.data(SECONDARY_COL)
        src_edited_data = src_item.edited_data
        dst_data = dst_item.data(SECONDARY_COL)
        dst_edited_data = dst_item.edited_data
        # swap _data
        dst_data.order = src_item.row() + 1
        dst_data.id = src_item.data(PRIMARY_COL).id
        src_item.s_data = dst_data
        src_item.edited_data = dst_edited_data
        src_data.order = dst_item.row() + 1
        src_data.id = dst_item.data(PRIMARY_COL).id
        dst_item.s_data = src_data
        dst_item.edited_data = src_edited_data
        if not src_item.data(SECONDARY_COL).name and not src_item.data(PRIMARY_COL).name:
            src_item.merge_state = MERGE_IGNORE
        else:
            src_item.merge_state = MERGE_UNDECIDED
        dst_item.merge_state = MERGE_UNDECIDED
        self.leaveEvent() # as mouse leaving move column; 

    def onMoveDataUp(self, item):
        dst_item = self.model().emptyItemAbove(item)
        self.onMoveData(item, dst_item)   

    def onMoveDataDown(self, item):
        dst_item = self.model().emptyItemBelow(item)
        self.onMoveData(item, dst_item)    

    # def keyPressEvent(self, evt):
    #     idx = self.currentIndex()
    #     super(ProjectTreeView, self).keyPressEvent(evt)
    #     new_idx = self.currentIndex()
    #     if new_idx != idx:
    #         item = self.model().itemFromIndex(new_idx)
    #         for i in [item, item.other_item, item.data(DECISION_ITEM_ROLE)]:
    #             if i:
    #                 self.setCurrentIndex(i.index())

        # # I don't see a default key binding (below) which moves between columns of a row, so need to add one.
        # idx = self.currentIndex()
        # row = idx.row()
        # col = idx.column()
        # if evt.key() in [Qt.Key_Right, Qt.Key_Plus] and qApp.instance().keyboardModifiers() == Qt.AltModifier:            
        #     new_col = col + 1
        #     if new_col > PRIMARY_COL:
        #         new_col = PRIMARY_COL
        #     new_idx = self.model().index(row, new_col)
        #     self.setCurrentIndex(new_idx)
        #     new_item = self.model().itemFromIndex(new_idx) 
        # elif evt.key() in [Qt.Key_Left, Qt.Key_Minus]:
        #     new_col = col + -1
        #     if new_col < 0:
        #         new_col = 0
        #     new_idx = self.model().index(row, new_col)
        #     self.setCurrentIndex(new_idx)
        #     new_item = self.model().itemFromIndex(new_idx)

        # """Key Bindings (https://doc.qt.io/qt-5/qtreeview.html#details)

        # QTreeView supports a set of key bindings that enable the user to navigate in the view and interact with the contents of items:
        # Key	Action
        # Up	Moves the cursor to the item in the same column on the previous row. If the parent of the current item has no more rows to navigate to, the cursor moves to the relevant item in the last row of the sibling that precedes the parent.
        # Down	Moves the cursor to the item in the same column on the next row. If the parent of the current item has no more rows to navigate to, the cursor moves to the relevant item in the first row of the sibling that follows the parent.
        # Left	Hides the children of the current item (if present) by collapsing a branch.
        # Minus	Same as Left.
        # Right	Reveals the children of the current item (if present) by expanding a branch.
        # Plus	Same as Right.
        # Asterisk	Expands the current item and all its children (if present).
        # PageUp	Moves the cursor up one page.
        # PageDown	Moves the cursor down one page.
        # Home	Moves the cursor to an item in the same column of the first row of the first top-level item in the model.
        # End	Moves the cursor to an item in the same column of the last row of the last top-level item in the model.
        # F2	In editable models, this opens the current item for editing. The Escape key can be used to cancel the editing process and revert any changes to the data displayed.
        # """ 

    def closeEditor(self, save=True):
        if self.editor_index:
            editor = self.indexWidget(self.editor_index)
            if save:
                editor.saveChanges(editor.toPlainText())
            editor.close()
            self.setIndexWidget(self.editor_index, None)
            viewer_index = self.model().index(self.editor_index.row(), SECONDARY_COL, self.editor_index.parent())
            self.setIndexWidget(viewer_index, None)
            self.editor_index = None            
            QTimer.singleShot(0, self.scheduleDelayedItemsLayout)

    def mouseDoubleClickEvent(self, evt):
        idx = self.indexAt(evt.pos()) 
        item = idx.internalPointer()
        data_type = item.data_type
        if idx.column() == PRIMARY_COL and \
            data_type in [
                'glossTexts', 
                'sentenceTexts', 
                'extraTexts', 
                'projectName', 
                'signLanguage', 
                'versionId', 
                'projectCreator', 
                'projectDescription']:
                    self.editItem(idx)

    def mousePressEvent(self, evt):
        idx = self.indexAt(evt.pos()) 
        item = idx.internalPointer()
        data_type = item.data_type
        # if item:
        #     print(item.data_type, item.merge_state)
        #     print(item.s_data)
        #     print(item.p_data)

        # if and editor open, all we want to do with a mouse press is close it.
        if self.editor_index and self.editor_index.row() != idx.row():
            self.closeEditor()
        else:
            if data_type == 'signId':               
                evt_x = evt.pos().x()
                header = self.header()
                s_left = header.sectionPosition(SECONDARY_COL) + 4
                p_left = header.sectionPosition(PRIMARY_COL) - 10
                w = 32
                if (s_left <= evt_x <= (s_left + w)) or \
                    (p_left <= evt_x <= (p_left + w)):
                        p = QPoint(s_left, evt.pos().y())
                        idx = self.indexAt(p)        
                        if item.expanded:
                            item.expanded = False
                            self.collapse(idx)
                        else:
                            item.expanded = True
                            self.expand(idx)
                        self.scheduleDelayedItemsLayout()
                        self.update()
            elif data_type in ['projectLogo', 'signPath', 'sentencePath', 'extraMediaFile'] and \
                idx.column() in [SECONDARY_COL, PRIMARY_COL]:
                    self.viewMedia(item)

            if idx.column() == DECISION_COL:
                item.bumpMergeState()
                self.update()
                if data_type in self.parent().info_data_types:
                    if self.parent().infoReconciliationComplete():
                        self.model().rootItem.merge_state = MERGE_ACCEPTED
                        self.parent().next_btn.setEnabled(True)
                    else:
                        self.model().rootItem.merge_state = MERGE_UNDECIDED
                        self.parent().next_btn.setEnabled(False)
            elif idx.column() == MOVE_DOWN_COL and idx.data(Qt.DecorationRole): 
                self.onMoveDataDown(item)             
            elif idx.column() == MOVE_UP_COL and idx.data(Qt.DecorationRole): 
                self.onMoveDataUp(item) 
            elif idx.column() == EDIT_COL and idx.data(Qt.DecorationRole):
                if item.editing:
                    self.closeEditor()
                else:
                    self.editItem(idx)        
        super(ProjectTreeView, self).mousePressEvent(evt) 

    def editItem(self, index):
        parent_idx = index.parent()
        item = index.internalPointer()
        editor = ItemTextEditor(item, self)        
        index = self.model().index(item.row(), PRIMARY_COL, parent_idx)
        self.setIndexWidget(index, editor)
        self.editor_index = index        

        txt = item.data(PRIMARY_COL)
        merge_state = item.merge_state
        if merge_state in [MERGE_UNDECIDED, MERGE_REJECTED]:
            pass # go with text as txt
        elif merge_state == MERGE_ACCEPTED:
            txt = item.data(SECONDARY_COL)
        elif merge_state == MERGE_EDITED:
            try:                        
                txt = item.edited_data.get('text', '') # jsn
            except:
                txt = item.edited_data
        if hasattr(txt, 'text'):
            txt = txt.text
        editor.setPlainText(txt)
        editor.setStyleSheet("""ItemTextEditor{background: #e0ffff; border: 1px dashed blue;}""")
        viewer = ItemTextEditor(item, self, editor) 
        viewer.setReadOnly(True)       
        index = self.model().index(item.row(), SECONDARY_COL, parent_idx)
        self.setIndexWidget(index, viewer)
        txt = item.data(SECONDARY_COL)
        if hasattr(txt, 'text'):
            txt = txt.text
        viewer.setPlainText(txt)
        viewer.setStyleSheet("""ItemTextEditor{background: #ffffe0; border-style:hidden;}""")
        QTimer.singleShot(0, self.scheduleDelayedItemsLayout)

    def leaveEvent(self, evt=None):
        if self.mouse_over_item:
            self.mouse_over_item.movable = 0
            self.mouse_over_item = None
        if self.last_mouse_over_item:
            self.last_mouse_over_item.movable = 0
            self.last_mouse_over_item = None
        if self.move_target:
            self.move_target.movable = 0
            self.move_target = None
        self.update()
        super(ProjectTreeView, self).leaveEvent(evt)

    def mouseMoveEvent(self, evt):
        pos = evt.pos()
        index = self.indexAt(pos)
        row = index.row() 
        col = index.column()
        mouse_over_item = index.internalPointer()
        if row != self.last_row or col != self.last_column:
            self.last_row = row
            self.last_column = col
            self.last_mouse_over_item = self.mouse_over_item
            if self.last_mouse_over_item:
                self.last_mouse_over_item.movable = 0
            self.mouse_over_item = mouse_over_item
            if self.move_target:
                self.move_target.movable = 0
            if col == MOVE_DOWN_COL and index.data(Qt.DecorationRole):
                self.mouse_over_item.movable = MOVE_DOWN_ITEM
                self.move_target = self.model().emptyItemBelow(self.mouse_over_item)
                self.move_target.movable = MOVE_ITEM_TARGET
            elif col == MOVE_UP_COL and index.data(Qt.DecorationRole):
                self.mouse_over_item.movable = MOVE_UP_ITEM
                self.move_target = self.model().emptyItemAbove(self.mouse_over_item)
                self.move_target.movable = MOVE_ITEM_TARGET
            self.update()
    def resizeEvent(self, evt):       
        self.resizeTimer.start(600)
        super(ProjectTreeView, self).resizeEvent(evt) 

    def resizeFinished(self):
        self.resizeTimer.stop() 
        self.scheduleDelayedItemsLayout()  
        qApp.processEvents()

    def dialectStr(self, dialect_ids, project):
        if isinstance(dialect_ids, Dialect): # NOTE: used for a single dialect
            dialect_ids = [dialect_ids.id]
        elif isinstance(dialect_ids, int): #NOTE: probably an error???
            dialect_ids = [dialect_ids]
        dialects = []
        if dialect_ids:
            dialects = [d for d in project.dialects if d.id in dialect_ids or str(d.id) in dialect_ids]
        dialect_str = ''
        if dialects:
            dialects = sorted(dialects, key=lambda x:x.name.lower())
            _str = [f'{d.name} ({d.abbr})' for d in dialects]
            dialect_str = ", ".join(_str)
        return dialect_str

    def getGramCatDisplayText(self, gram_cat_id):
        gram_cats = self.parent().project_data.get('grammarCategories')
        names = [gc for gc in gram_cats if gc.get('id') == gram_cat_id]
        name = ''
        if names:
            name = names[0].get('name')
        return name

    def getGlossDisplayText(self, gloss_text):
        txt = ''
        if isinstance(gloss_text, dict):
            jsn = gloss_text
            sense_id = jsn.get('senseId', 0)
            sign_id = jsn.get('signId', 0)
            dialect_ids = jsn.get('dialectIds', None)
            gloss_text = GlossText(jsn, sense_id, sign_id, dialect_ids)
        txt = gloss_text.text
        return txt
    
    def getMediaPaths(self, item):
        s_path = item.data(SECONDARY_COL)
        p_path = item.data(PRIMARY_COL)
        if isinstance(s_path, (list, tuple)): # {path, hash}
            s_path = s_path[0]
        if isinstance(p_path, (list, tuple)): # {path, hash}
            p_path = p_path[0]
        elif item.data_type == 'extraMediaFile':
            s_path = s_path.path
            p_path = p_path.path
        if not os.path.isfile(s_path):
            s_path = ''
        if not os.path.isfile(p_path):
            p_path = ''
        return (s_path, p_path)
    
    def viewMedia(self, item):
        if not self.item_media_viewers:
            s_path, p_path = self.getMediaPaths(item)
            if not s_path and item.merge_state == MERGE_ACCEPTED:
                pass
            else:
                media_viewer = PlayerDialog(s_path, p_path, item, self, self.item_media_viewers)
                self.parent().close_signal.connect(media_viewer.close)
                if media_viewer.exec_():
                    pass
                del media_viewer
            qApp.restoreOverrideCursor() 

    @property
    def empty(self):
        return self.isEmpty()

    def isEmpty(self):
        try:
            if not self._data:
                return True
            elif isinstance(self._data, str):
                if not self._data:
                    return True
                return False
            elif isinstance(self._data, dict):
                return self._data.get('empty', False)
            elif hasattr(self._data, 'empty'):
                return self._data.empty
            elif self.data_type in [None, 'signId', 'signPath', 'senseId', 'sentenceId', 'grammarCategories', 'writtenLanguages', 'dialects']:
                return False
            elif self.data_type in ['dialectIds', 'componentCodes', 'grammarCategoryId']:
                if not self._data:
                    return True
                return False
            elif self.data_type in ['extraMediaLabel']:
                return False
        except:
            return True
        return False

    def isPrimary(self):
        if self.column() == PRIMARY_COL:
            return True
        return False

    def isSecondary(self):
        if self.column() == SECONDARY_COL:
            return True
        return False

    def setActive(self, _bool):
        self.active = _bool

    def getIcon(self):
        if self.merge_state == MERGE_UNDECIDED:
            pxm = QPixmap(':/merge_question.png')
        elif self.merge_state == MERGE_ACCEPTED:
            pxm = QPixmap(':/merge_accept.png')
        elif self.merge_state == MERGE_REJECTED:
            pxm = QPixmap(':/merge_reject.png')
        elif self.merge_state == MERGE_EDITED:
            pxm = QPixmap(':/merge_edited.png')
        else:
            return QIcon()
        return QIcon(pxm.scaledToHeight(self._icn_height, Qt.SmoothTransformation))

    def getEditIcon(self):
        return QIcon(QPixmap(':/edit_sign.png').scaledToHeight(self._icn_height, Qt.SmoothTransformation))

    def getMoveUpIcon(self):
        return QIcon(QPixmap(':/up.png').scaledToHeight(self._icn_height, Qt.SmoothTransformation))

    def getMoveDownIcon(self):
        return QIcon(QPixmap(':/down.png').scaledToHeight(self._icn_height, Qt.SmoothTransformation))

class CompItemDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super(CompItemDelegate, self).__init__(parent)

    def paint(self, painter, option, index):
        painter.save()
        item = self.parent().itemAt(option.rect.center())
        super(CompItemDelegate, self).paint(painter, option, index) 
        rect = option.rect.adjusted(2, 2, -2, -2)
        if hasattr(item, 'added') and item.added:
            pen = QPen(Qt.red, 2)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 3, 3)
        elif hasattr(item, 'removed') and item.removed: 
            pen = QPen(Qt.gray, 2)
            painter.setPen(pen)
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            painter.drawRoundedRect(rect, 3, 3)
        painter.restore()

class ProjectTreeItemDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super(ProjectTreeItemDelegate, self).__init__(parent) 

    def paint(self, painter, option, index): 

        painter.save()
        this_tree = self.parent()
        this_item = index.internalPointer()
        data_type = this_item.data_type
        merge_state = this_item.merge_state

        # NOT using indent from tree, so create some here
        self.doIndents(data_type, option, index)

        # alignment for row column icons
        option.decorationAlignment = Qt.AlignHCenter|Qt.AlignTop
        if index.column() == DECISION_COL and data_type == 'signId':
            option.decorationAlignment = Qt.AlignHCenter|Qt.AlignVCenter

        # hidden rows
        if data_type in ['sentenceId']:
            this_tree.setRowHidden(index.row(), index.parent(), True)
        # elif data_type == 'signId' and merge_state == MERGE_NONE:
        #     this_tree.setRowHidden(index.row(), index.parent(), True)

        # update widget displays
        this_widget = this_tree.indexWidget(index)
        if data_type in ['componentCodes'] and not this_widget: # this item needs a widget
            self.setComponentsWidget(index) 
            # seems best place to add these widgets. they don't get created and displayed until needed and get laid out properly
            this_widget = this_tree.indexWidget(index)
        if this_widget and data_type == 'componentCodes':# and not this_item.empty:
            if index.column() == SECONDARY_COL and this_item.merge_state == MERGE_REJECTED:
                this_widget.setDisabled(True)
            else:
                this_widget.setEnabled(True)
            if index.column() == PRIMARY_COL and this_item.merge_state == MERGE_ACCEPTED:
                #if other_item.empty:
                this_widget.setDisabled(True)
            this_widget.move(option.rect.topLeft()) 
            this_widget.resize(option.rect.size()) 

        # # some items need html painting
        if data_type in ['projectDescription', 'sentencePath']:
            s_text = this_item.data(SECONDARY_COL)
            p_text = this_item.data(PRIMARY_COL)
            if (data_type == 'projectDescription' and 
                index.column() == PRIMARY_COL and 
                merge_state in [MERGE_ACCEPTED, MERGE_EDITED]):
                    text = index.model().getHtmlDisplay(index)
                    self.setHtmlText(text, option, painter)
            elif data_type == 'sentencePath' and index.column() in [SECONDARY_COL, PRIMARY_COL]:
                text = index.model().getHtmlDisplay(index)
                self.setHtmlText(text, option, painter)

        # put in some gridlines
        if index not in this_tree.selectedIndexes():
            painter.save()
            painter.setPen(QColor(Qt.gray).lighter())
            left = QPoint(0, option.rect.bottom())
            right = QPoint(this_tree.width(), option.rect.bottom())
            painter.drawLine(left, right)
            if data_type == 'signId': 
                index_above = this_tree.indexAbove(index)
                item_above = index_above.internalPointer()
                if this_item.data_type == 'signId' and item_above and item_above.data_type != 'signsLabel':
                    if this_item.expanded or item_above.data_type != 'signId':            
                        painter.setPen(QPen(QColor(Qt.gray).lighter(), 6))
                        left = QPoint(0, option.rect.top())
                        right = QPoint(this_tree.width(), option.rect.top())
                        painter.drawLine(left, right)
            painter.restore()

        # border around primary items
        x = this_tree.header().sectionPosition(4) 
        w = this_tree.header().sectionSize(5) + this_tree.header().sectionSize(4) - 1
        h = this_tree.height() - 24
        painter.save()
        painter.setPen(QPen(Qt.blue, 1))
        painter.drawRect(x, 0, w, h)
        painter.restore()
        super(ProjectTreeItemDelegate, self).paint(painter, option, index) 
        painter.restore() 

    def setHtmlText(self, txt, option, painter):
        doc = QTextDocument()
        doc.setHtml(txt)
        doc.setTextWidth(option.rect.width())
        doc.setDefaultFont(option.widget.font())
        doc.setDocumentMargin(1)
        painter.save()
        painter.translate(option.rect.left(), option.rect.top())
        clip = QRectF(0, 0, option.rect.width(), option.rect.height())
        doc.drawContents(painter, clip)
        painter.restore()

    def setComponentsWidget(self, index):
        tree = self.parent()
        item = index.internalPointer()
        codes = item.data(index.column())
        widget = ComponentLocationWidget(codes, tree)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tree.setIndexWidget(index, widget)

    def doIndents(self, data_type, option, index):
        indent = 0
        if index.column() == SECONDARY_COL:
            if data_type in ['signsLabel', 'signId']:
                indent = 2
            elif data_type in \
                ['projectInfoLabel',
                 'languageInfoLabel',
                 'grammarInfoLabel',
                 'dialectInfoLabel',
                 'signPath', 
                 'componentCodes',
                 'senseId',
                 'extraMediaLabel',
                 'notesLabel']:
                indent = 16
            elif data_type in ['projectName',
                'signLanguage',
                'versionId',
                'projectCreator',
                'projectLogo',
                'projectDescription',
                'writtenLanguages',
                'grammarCategories',
                'dialects',
                'glossTexts',
                'grammarCategoryId',
                'dialectIds',
                'sentencePath',
                'extraMediaFile',
                'extraTexts']:
                    indent = 32
            elif data_type in ['sentenceTexts']:
                indent = 48
            if indent:
                option.rect.translate(indent, 0)
                option.rect.adjust(0, 0, -indent, 0) #adjust(int dx1, int dy1, int dx2, int dy2)        
        elif index.column() == PRIMARY_COL:
            if data_type in ['signsLabel', 'signId']:
                indent = -14
            elif data_type in ['projectName',
                'signLanguage',
                'versionId',
                'projectCreator',
                'projectLogo',
                'projectDescription',
                'writtenLanguages',
                'grammarCategories',
                'dialects',
                'glossTexts',
                'grammarCategoryId',
                'dialectIds',
                'sentencePath',
                'extraMediaFile',
                'extraTexts']:
                    indent = 16
            elif data_type in ['sentenceTexts']:
                indent = 32
            if indent:
                option.rect.translate(indent, 0)
                option.rect.adjust(0, 0, -indent, 0) #adjust(int dx1, int dy1, int dx2, int dy2)
        elif index.column() == EDIT_COL: # without these, background painting is broken, due to secondary column indents
            indent = 0
            if data_type in ['signsLabel', 'signId']:
                indent = -14
            elif data_type in ['projectName',
                'signLanguage',
                'versionId',
                'projectDescription',
                'projectCreator',
                'projectLogo',
                'writtenLanguages',
                'grammarCategories',
                'dialects',
                'glossTexts',
                'grammarCategoryId', 
                'dialectIds',
                'sentencePath',
                'extraMediaFile',
                'extraTexts']:
                    indent = 16
            elif data_type in ['sentenceTexts']:
                indent = 32
            if indent:
                option.rect.adjust(0, 0, +indent, 0)

    def setMoveItems(self, src, dst):
        self.move_items.clear()
        if not hasattr(src, 'none'):
            self.move_items = [src, dst]              

    def getSignRect(self, sign_path_item):
        sign_item = sign_path_item.parent()
        first_rect = self.parent().visualRect(sign_path_item.index())
        last_item = sign_item
        if sign_item.hasChildren():
            last_item = sign_item.child(sign_item.rowCount() - 1)
        last_rect = self.parent().visualRect(last_item.index())
        x = first_rect.left() - 2
        y = first_rect.top() - 2
        w = first_rect.width() + 4 # + 48 # 2x24, two centre column widths
        h = last_rect.bottom() - first_rect.bottom() + 2
        rect = QRect(x, y, w, h)    
        return rect

class ItemTextEditor(QTextEdit):
    def __init__(self, item, project_tree, parent=None):
        super(ItemTextEditor, self).__init__(parent)
        self.setAutoFillBackground(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WordWrap)
        self.setUndoRedoEnabled(True)
        self.setMouseTracking(True)
        self.setTabChangesFocus(True)
        self.item = item
        self.item.editing = True
        self.setFont(project_tree.font())
        self.document().contentsChanged.connect(project_tree.scheduleDelayedItemsLayout)

    def closeEvent(self, evt):
        self.item.editing = False

    def saveChanges(self, new_text):
        # commit edited data to item
        merge_state = self.item.merge_state        
        text = self.item.data(PRIMARY_COL) # merge_state == MERGE_UNDECIDED | MERGE_REJECTED
        if merge_state == MERGE_ACCEPTED:
            text = self.item.data(SECONDARY_COL)
        elif merge_state == MERGE_EDITED:
            text = self.item.edited_data
        if new_text != text:
            self.item.edited_data = new_text
            self.item.merge_state = MERGE_EDITED

    def sizeHint(self):
        # doc = self.document()
        # doc_height = (doc.lineCount() * self.fontMetrics().height()) + 2 * doc.documentMargin()
        doc = QTextDocument()
        doc.setDefaultFont(self.font())
        text = self.toPlainText()
        doc.setPlainText(text) # display role        
        doc.setTextWidth(self.width())
        doc_height = doc.size().height()
        return QSize(self.width(), doc_height)      

class PlayerDialog(QDialog):
    def __init__(self, s_path, p_path, item, tree_view, item_media_viewers, flags=Qt.CustomizeWindowHint|Qt.WindowStaysOnTopHint):
        parent = tree_view.parent()
        super(PlayerDialog, self).__init__(parent)
        self.setStyleSheet('QDialog{background-color: white;}')
        self.setWindowTitle(' ')
        self.s_path = s_path
        self.p_path = p_path
        self.item = item
        self.tree_view = tree_view
        self.viewer_list = item_media_viewers
        self.viewer_list.append(self) 
        
        self.s_player = Player(self)
        self.s_player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.p_player = Player(self)
        self.p_player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.players_linked = False
        self.link_btn = QPushButton()
        self.link_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.link_btn.setFlat(True)
        self.link_btn.setIcon(QIcon(':/disconnect.png'))
        self.link_btn.pressed.connect(self.onLinkPlayers)

        self.merge_state_btn = QPushButton()
        self.merge_state_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.merge_state_btn.setFlat(True)
        self.merge_state_btn.setIcon(self.getIcon(item))
        self.merge_state_btn.pressed.connect(self.onMergeStateBtnPressed)

        # main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        self.setLayout(layout)

        # layout to hold buttons vertically between players
        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.addWidget(self.merge_state_btn)
        vlayout.addWidget(self.link_btn)
        if self.s_player.isVideo(s_path):
            self.link_btn.show()
        else:
            self.link_btn.hide()
        
        # layout to hold players, with a central vertical layout to hold buttons
        player_layout = QHBoxLayout()
        player_layout.setContentsMargins(0, 0, 0, 0)
        player_layout.addWidget(self.s_player, stretch=2)
        player_layout.addLayout(vlayout, stretch=1)
        player_layout.addWidget(self.p_player, stretch=2)       
        layout.addLayout(player_layout, 1)

        # layout to hold textual file information below players
        file_info_layout = QHBoxLayout()
        file_info_layout.setContentsMargins(0, 0, 0, 0)
        file_info_layout.setSpacing(32)
        self.s_file_info_lbl = QLabel(self)
        self.p_file_info_lbl = QLabel(self)
        for lbl in [self.s_file_info_lbl, self.p_file_info_lbl]:
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignTop)
            file_info_layout.addWidget(lbl, stretch=1)
        layout.addLayout(file_info_layout)

        # dialog buttons
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
        close_btn = self.btnBox.button(QDialogButtonBox.Ok)
        close_btn.setText(qApp.instance().translate('PlayerDialog', 'Close'))
        self.btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btnBox.accepted.connect(self.close)
        layout.addStretch()
        layout.addWidget(self.btnBox)          

        self.icn_height = self.fontMetrics().height()
        # mark column if media files are equal in name and in hash
        if os.path.basename(s_path) == os.path.basename(p_path) and \
            filecmp.cmp(s_path, p_path, True):
            #qApp.instance().pm.getFreshHash(s_path) == qApp.instance().pm.getFreshHash(p_path):
                pxm = QPixmap(':/equals.png')
                icn = QIcon(pxm.scaledToHeight(self.icn_height, Qt.SmoothTransformation))
                tip = qApp.instance().translate('PlayerDialog', 'same; no differences')
                self.merge_state_btn.setIcon(icn)
                self.merge_state_btn.setToolTip(tip)
                self.merge_state_btn.blockSignals(True)

        if s_path and p_path:            
            self.onLinkPlayers(pause=False)

    def getIcon(self, item):
        icn_height = self.fontMetrics().height()
        if item.equalData():
            pxm = QPixmap(':/equals.png')
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        elif item.merge_state == MERGE_UNDECIDED: # 1
            pxm = QPixmap(':/merge_question.png') 
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        elif item.merge_state == MERGE_EDITED: # 2
            pxm = QPixmap(':/merge_edited.png')
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        elif item.merge_state == MERGE_ACCEPTED: # 3
            pxm = QPixmap(':/merge_accept.png')
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        elif item.merge_state == MERGE_REJECTED: # 4
            pxm = QPixmap(':/merge_reject.png')  
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation))
        elif item.merge_state == MERGE_MIXED:
            pxm = QPixmap(':/merge_mixed.png')  # default rejected 
            return QIcon(pxm.scaledToHeight(icn_height, Qt.SmoothTransformation)) 
        else:
            return QIcon()

    def startPlay(self, s_path, p_path, item):
        self.setWidgetStyles() 
        path = p_path
        if item.merge_state == MERGE_ACCEPTED:
            path = s_path
        self.setFileInfo('secondary') #s_path, self.s_file_info_lbl)
        self.setFileInfo('primary') #path, self.p_file_info_lbl)
        self.s_player.playFile(s_path) 
        self.p_player.playFile(path)
        self.s_player.MediaPlayer.set_position(0)
        self.p_player.MediaPlayer.set_position(0)

    def suggestedSize(self, width=480): # width of dialog
        media_width = (width - 32)/2 # take off 32 for central button layout and cut in half for each media width
        media_height = media_width/self.s_player.current_aspect_ratio # height by aspect ratio
        height = media_height + \
            self.btnBox.height()*3 + \
            max(self.s_file_info_lbl.height(), self.p_file_info_lbl.height())
        return QSize(int(width), int(height))

    def showEvent(self, evt):
        self.startPlay(self.s_path, self.p_path, self.item)        
        # sizes aren't valid until players are loaded and playing
        self.resize(self.suggestedSize())
        qApp.restoreOverrideCursor() 
        super(PlayerDialog, self).showEvent(evt) 

    def closeEvent(self, evt):
        if self in self.viewer_list:
            self.viewer_list.remove(self)
        for player in [self.s_player, self.p_player]:            
            player.current_media = None
            player.next_media = None
            player.MediaPlayer.stop()       
            player.MediaPlayer.release()         
        super(PlayerDialog, self).closeEvent(evt)
        for i in [
            self.s_player,
            self.p_player,
            self
            ]:
                i.deleteLater() 

    def syncPlayers(self, player1, player2):
        player2.MediaPlayer.set_position(player1.MediaPlayer.get_position)

    def setFileInfo(self, _type):
        def _getText(filename):
            txt = ''
            if filename:
                media = None
                t = 'video'
                if self.p_player.isPicture(filename):
                    t = 'picture'
                if t == 'video':
                    media = Video([filename])
                else:
                    media = Picture([filename])

                try:
                    stats = os.stat(filename)
                except:
                    stats = None
                    print("No such file: ", filename)                
                if stats:
                    _dir_label = qApp.instance().translate('PlayerDialog', 'Folder:')
                    name_label = qApp.instance().translate('PlayerDialog', 'Filename:')
                    _dir, name = os.path.split(filename)
                    size_label = qApp.instance().translate('PlayerDialog', 'Dimensions:')
                    size = f'{media.fsize[0]}x{media.fsize[1]}'
                    fsize_label = qApp.instance().translate('PlayerDialog', 'Size:')
                    fsize = f'{int(round(stats.st_size / 1024, 0))} KB'
                    mt_label = qApp.instance().translate('PlayerDialog', 'Modified:')
                    mt = datetime.fromtimestamp(os.path.getmtime(filename)).strftime("%d/%m/%Y %H:%M:%S")
                    mt = f'{mt}'
                    txt = ''
                    if t == 'video':
                        duration_label = qApp.instance().translate('PlayerDialog', 'Duration:')
                        duration = f"{media.duration} {qApp.instance().translate('PlayerDialog', 'seconds')}"
                        fps_label = qApp.instance().translate('PlayerDialog', 'Framerate:')
                        fps = f"{media.fps} {qApp.instance().translate('PlayerDialog', 'frames/second')}"
                        bitrate_label = qApp.instance().translate('PlayerDialog', 'Bitrate:')
                        bitrate = f'{media.bitrate} kbps'     
                        txt = f'<table> \
                                    <tr> \
                                        <td>{name_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td><b>{name}</b></td> \
                                    </tr><tr> \
                                        <td>{_dir_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>({_dir})</td> \
                                    </tr><tr> \
                                        <td>{duration_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{duration}</td> \
                                    </tr><tr> \
                                        <td>{fsize_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{fsize}</td> \
                                    </tr><tr> \
                                        <td>{size_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{size}</td> \
                                    </tr><tr> \
                                        <td>{mt_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{mt}</td> \
                                    </tr><tr> \
                                        <td>{fps_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{fps}</td> \
                                    </tr><tr>setFileInfo \
                                        <td>{bitrate_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{bitrate}</td> \
                                    </tr> \
                                </table>'
                    else:
                        txt = f'<table> \
                                    <tr> \
                                        <td>{name_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td><b>{name}</b></td> \
                                    </tr><tr> \
                                        <td>{_dir_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>({_dir})</td> \
                                    </tr><tr> \
                                        <td>{fsize_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{fsize}</td> \
                                    </tr><tr> \
                                        <td>{size_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{size}</td> \
                                    </tr><tr> \
                                        <td>{mt_label}&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{mt}</td> \
                                    </tr> \
                                </table>'
            return txt 
       
        if _type == 'secondary': 
            txt = _getText(self.s_path)
            self.s_file_info_lbl.setText(txt)
        elif _type == 'primary' and self.item.merge_state == MERGE_ACCEPTED:        
            txt = f'<span style="color:red;">{_getText(self.s_path)}</span>'
            self.p_file_info_lbl.setText(txt)
        else:
            txt = _getText(self.p_path)
            self.p_file_info_lbl.setText(txt)
    
    def resizeEvent(self, evt):
        try:
            h = self.height()
            if not hasattr(self, 'last_height'):
                self.last_height = h
                return            
            if h != self.last_height:
                delta = h - self.last_height
                self.last_height = h
                player_h = self.s_player.height() + delta
                self.s_player.setMaximumHeight(player_h)
                self.p_player.setMaximumHeight(player_h)
                self.merge_state_btn.setMaximumHeight(player_h - 24)
        except:
            pass

    def onMergeStateBtnPressed(self):
        self.item.bumpMergeState() 
        self.parent().project_tree.update()       
        try:
            self.merge_state_btn.setIcon(self.getIcon(self.item))
        except:
            self.merge_state_btn.setIcon(QIcon())
        s_path, p_path = self.tree_view.getMediaPaths(self.item)
        self.startPlay(s_path, p_path, self.item)

    def setWidgetStyles(self):
        if self.item.merge_state == MERGE_ACCEPTED:
            self.s_file_info_lbl.setStyleSheet(None)
            self.s_player.setEnabled(True)
            self.p_player.setEnabled(True)
        elif self.item.merge_state == MERGE_REJECTED:
            self.s_file_info_lbl.setStyleSheet('color: gray;') #  text-decoration: line-through; ## probably want to see details clearly for comparison
            self.s_player.setDisabled(True)
            self.p_player.setEnabled(True)
        else:
            self.s_file_info_lbl.setStyleSheet(None)
            self.s_player.setEnabled(True)
            self.p_player.setEnabled(True)

    def onLinkPlayers(self, pause=True):
        if pause:
            self.s_player.pauseAtStart()
            self.p_player.pauseAtStart()
        if self.players_linked:
            self.players_linked = False
            self.link_btn.setIcon(QIcon(':/disconnect.png'))
            self.s_player.linkControls(self.p_player, False)
            self.p_player.linkControls(self.s_player, False)
        else:
            self.players_linked = True
            self.link_btn.setIcon(QIcon(':/connect.png'))
            self.s_player.linkControls(self.p_player, True)
            self.p_player.linkControls(self.s_player, True)

class ComponentLocationWidget(QWidget):
    def __init__(self, codes, tree_view, parent=None):
        super(ComponentLocationWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tree_view = tree_view
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet("QWidget{border: 0;} QListWidget::item[new='true']{border: 1px solid red;}")

        self.comp_widget = ComponentDropWidget(self)
        self.comp_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.comp_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.comp_widget.setWrapping(True)
        self.comp_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_widget.setItemDelegate(CompItemDelegate(self.comp_widget))
        
        self.location_widget = LocationView(self)
        self.location_widget.setFixedSize(QSize(120, 120))
        self.location_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.comp_widget.locationItemClicked.connect(self.location_widget.onLocationItemClicked)
        
        layout.addWidget(self.comp_widget, stretch=3)
        layout.addWidget(self.location_widget, stretch=1)        
        layout.setAlignment(self.comp_widget, Qt.AlignTop)        
        layout.setAlignment(self.location_widget, Qt.AlignRight|Qt.AlignTop)
        self.setLayout(layout)

        self.setComponents(codes)
        self.codeList = self.comp_widget.codeList        

    def items(self):
        return self.comp_widget.items()

    def setComponents(self, component_codes):
        self.component_codes = component_codes
        self.comp_widget.onModelReset(self)#, include_locations=False)
        _bool = False
        if qApp.instance().pm.get_location_codes(self):
            _bool = True
            self.location_widget.scene.onModelReset(self)
        self.location_widget.setVisible(_bool)

    def onDataReconciled(self, p_item): 
        if p_item.data_type != 'componentCodes':
            return
        s_item = self.tree_view.getSecondaryItem(p_item)
        s_codes = s_item._data
        if isinstance(s_codes, int):
            s_codes = [str(s_codes)]
        if not s_codes:
            s_codes = []
        p_codes = p_item._data
        if isinstance(p_codes, int):
            p_codes = [str(p_codes)]
        if not p_codes:
            p_codes = []
        if p_item.merge_state == MERGE_ACCEPTED:
            codes = s_codes + p_codes
            codes = list(set(codes)) # set all components; diffs will be marked in next step
            self.setComponents(codes)
            self.__markCodeDiffs(s_item, p_item)
        else:
            self.setComponents(p_codes)

    def __markCodeDiffs(self, s_item, p_item):
        new_codes = []
        old_codes = []
        if s_item:
            new_codes = s_item._data # codes from secondary have been accepted over primary
        if p_item:
            old_codes = p_item._data
            widget = self.tree_view.indexWidget(p_item.index())
            if widget:
                comp_list = widget.comp_widget
                for row in range(comp_list.count()):
                    comp = comp_list.item(row)
                    comp.added = False
                    comp.removed = False
                    if comp.code not in old_codes:
                        comp.added = True
                    elif comp.code not in new_codes:
                        comp.removed = True 

class OmissionChecksDlg(QDialog):
    def __init__(self, parent, deletion_checks, counter):
        super(OmissionChecksDlg, self).__init__(parent=parent, flags=Qt.WindowStaysOnTopHint) 
        settings = qApp.instance().getSettings() 
        layout = QVBoxLayout() 
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(7)
        self.setWindowTitle(' ')
        self.items = []

        txt = qApp.instance().translate('OmissionChecksDlg', 'The following will not be included in the merged dictionary:')
        txt = f'<b>{txt}</b><br>'
        layout.addWidget(QLabel(txt))
        #print(deletion_checks)
        for data in deletion_checks:    
            items, title = data
            self.items.extend(items)
            group_box = QGroupBox(f' {title} ')
            # group_box.setStyleSheet("""QGroupBox{font-weight:bold;}""")
            group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            vlayout = QVBoxLayout()
            group_box.setLayout(vlayout)
            layout.addWidget(group_box)
            for item in items:
                data = item.data(SECONDARY_COL)
                if item.data(PRIMARY_COL):
                    data = item.data(PRIMARY_COL)                
                name = data.name
                count = counter(item)
                txt = qApp.instance().translate('OmissionChecksDlg', 'Number of signs affected:')
                txt = f'<span style="color: blue;">{name}</span><br>{txt} <span style="color: blue;">{count}</span>'                
                lbl = QLabel(txt)
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                lbl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
                vlayout.addWidget(lbl)

        layout.addStretch()
        txt = qApp.instance().translate('OmissionChecksDlg', 'Omit these things?')
        yes_txt = qApp.instance().translate('OmissionChecksDlg', '"Yes"  (Omit these things.)')
        no_txt = qApp.instance().translate('OmissionChecksDlg', '"No"  (Go back and make different choices.)')
        txt = f'<br><b>{txt}</b>' #{yes_txt}<br>{no_txt}'
        layout.addWidget(QLabel(txt))        

        self.btnBox = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        self.btnBox.setOrientation(Qt.Vertical)
        self.btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btnBox.button(QDialogButtonBox.Yes).setIcon(QIcon(":/thumb_up.png"))
        self.btnBox.button(QDialogButtonBox.No).setIcon(QIcon(":/thumb_down.png"))
        self.btnBox.button(QDialogButtonBox.Yes).setText(yes_txt)
        self.btnBox.button(QDialogButtonBox.No).setText(no_txt)
        self.btnBox.button(QDialogButtonBox.Yes).setStyleSheet("text-align:left;")
        self.btnBox.button(QDialogButtonBox.No).setStyleSheet("text-align:left;")
        self.btnBox.accepted.connect(self.accept)  
        self.btnBox.rejected.connect(self.reject)
        layout.addWidget(self.btnBox) 
        self.setLayout(layout)

    def setFocusOnYesButton(self):        
        self.btnBox.button(QDialogButtonBox.Yes).setFocus(True)        

    def reject(self):
        for item in self.items:
            item.merge_state = MERGE_UNDECIDED
        super(OmissionChecksDlg, self).reject()


# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()
