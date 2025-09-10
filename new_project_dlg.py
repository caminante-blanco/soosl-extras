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

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import QSortFilterProxyModel

from PyQt5.QtGui import QPalette, QFontDatabase
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPainter

from PyQt5.QtWidgets import QRadioButton, QFrame, QSpinBox, QCheckBox, QGridLayout, QLayout,\
    QStackedWidget, QTextBrowser
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QFontComboBox
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QAction, QToolButton

# NOTE: a validator isn't really needed as initial project name will be "slugified" into a project id and filename
# removing or replacing invalid characters in the process; see: project_manager.sooslSlugify()
#from validators import FileNameValidator
if sys.platform.startswith('linux'):
    from keyboard_combo import KeyboardComboBox

class EditDialectsDlg(QDialog):
    showFocalDialect = pyqtSignal(bool)
    
    def __init__(self, parent=None, dialects=None):
        super(EditDialectsDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
        able_to_edit = qApp.instance().pm.ableToEdit()
        self.acquired_project_lock = False
        self.acquired_full_project_lock = False
        self.setWindowTitle(qApp.instance().translate('EditDialectsDlg', 'Dialects'))
        
        self.layout = QVBoxLayout()
        self.layout.setSpacing(3)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        
        self.whatDialectsWidget = DialectsWidget(self, edit=False) 
        self.whatDialectsWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.whatDialectsWidget.showFocalDialect.connect(self.showFocalDialect)       
        self.layout.addWidget(self.whatDialectsWidget)
        
        dialects = sorted(dialects, key=lambda d: d.name.lower()) #sort alphabetically by name
        
        for d in dialects:
            self.whatDialectsWidget.onAddDialect(dialect = d)
        
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)        
        self.btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('EditDialectsDlg', 'Ok'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditDialectsDlg', 'Cancel'))
        if not able_to_edit:
            self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditDialectsDlg', 'Close'))
        self.OKBtn = self.btnBox.button(QDialogButtonBox.Ok)
        self.CancelBtn = self.btnBox.button(QDialogButtonBox.Cancel)
        self.OKBtn.setEnabled(False) 
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)

        hlayout = QHBoxLayout()
        hlayout.addStretch()
        if able_to_edit:
            self.edit_btn = QPushButton(qApp.instance().translate('EditDialectsDlg', 'Edit'))
            self.edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.edit_btn.clicked.connect(self.onEdit)
            self.edit_btn.setToolTip(qApp.instance().translate('EditDialectsDlg', 'Add, remove or rename dialects.'))
            hlayout.addWidget(self.edit_btn)
        hlayout.addWidget(self.btnBox)
        self.layout.addLayout(hlayout)        
        self.setLayout(self.layout)

    def refreshDialects(self):
        old_dialects = self.dialects
        mw = qApp.instance().getMainWindow()
        mw.reloadProject(force=True)
        _new_dialects = sorted(qApp.instance().pm.project.dialects, key=lambda d: d.name.lower()) #sort alphabetically by name
        new_dialects = [[d.id, d.name, d.abbr, d.focal] for d in _new_dialects]
        if new_dialects != old_dialects:
            box = QMessageBox(self)
            box.setWindowTitle(' ')
            txt1 = qApp.instance().translate('EditDialectsDlg', 'Dialects have been edited by another user.')
            txt2 = qApp.instance().translate('EditDialectsDlg', 'Your display may show changes.')
            msg = '{}\n{}'.format(txt1, txt2)
            box.setText(msg)
            box.setIcon(QMessageBox.Information)
            box.exec_()
            table = self.whatDialectsWidget.dialectTable
            table.clearContents()
            table.setRowCount(0)
            for d in _new_dialects:
                self.whatDialectsWidget.onAddDialect(dialect = d)

    def onEdit(self):
        if not self.acquired_full_project_lock and not self.acquired_project_lock:
            self.acquired_full_project_lock = qApp.instance().pm.acquireFullProjectLock(self) # deletion column
        if self.acquired_full_project_lock:
            if qApp.instance().pm.projectChanged():
                self.refreshDialects()
            self.edit = True
            self.edit_btn.setEnabled(False)
            self.edit_btn.setToolTip(None)
            self.setWindowTitle(qApp.instance().translate('EditDialectsDlg', 'Edit Dialects'))
            self.whatDialectsWidget.setupEditing()
            self.whatDialectsWidget.adjustSize()
            self.adjustSize()
            self.whatDialectsWidget.saveReady.connect(self.onSaveReady)
            qApp.instance().pm.startInactivityTimer(self)
        
    @property
    def dialects(self):
        return self.whatDialectsWidget.dialects
    
    def hideEvent(self, evt):
        qApp.processEvents()
        super(EditDialectsDlg, self).hideEvent(evt) 
        qApp.instance().pm.stopInactivityTimer()

    def leaveEdit(self, check_dirty=False):
        # if self.acquired_project_lock:
        #     qApp.instance().pm.releaseProjectLock()
        if self.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock()  
        self.reject()
    
    ##!!@pyqtSlot(bool)
    def onSaveReady(self, _bool):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.OKBtn.setEnabled(_bool)
        if _bool:
            self.OKBtn.setFocus(True)
        else:
            self.whatDialectsWidget.addDialectBtn.setFocus(True)

class EditWrittenLanguageSettingsDlg(QDialog):
    def __init__(self, parent=None, languages=None, edit=True):
        super(EditWrittenLanguageSettingsDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
        self.acquired_project_lock = False
        self.acquired_full_project_lock = False
        self.save_order_to_file = False # determines if data should be updated in json files or simply in user settings
        self.setHidden(True)
        #self.all_langs_added = False 
        self.lang_count = len(languages)
        self.setWindowTitle(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Written Language Settings'))
        
        self.layout = QVBoxLayout()
        self.layout.setSpacing(3)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        self.scrollArea = QScrollArea()
        self.scrollArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.whatLanguagesWidget = LanguagesWidget(parent=self, langs=languages, edit=edit)
        self.whatLanguagesWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
        self.scrollArea.setWidget(self.whatLanguagesWidget) 
        self.scrollArea.setWidgetResizable(True) 
        self.layout.addWidget(self.scrollArea)
        
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Ok'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Cancel'))
        self.OKBtn = self.btnBox.button(QDialogButtonBox.Ok)
        self.CancelBtn = self.btnBox.button(QDialogButtonBox.Cancel)
        self.OKBtn.setEnabled(False) 
        self.OKBtn.clicked.connect(self.onOK)
        self.CancelBtn.clicked.connect(self.onCancel)
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        self.layout.addLayout(hlayout)
        hlayout.addStretch()
        if qApp.instance().pm.ableToEdit():
            self.edit_btn = QPushButton(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Edit'))
            self.edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.edit_btn.clicked.connect(self.onEdit)
            self.edit_btn.setToolTip(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Add, remove, or rename languages.'))
            hlayout.addWidget(self.edit_btn)
        hlayout.addWidget(self.btnBox)
        
        self.setLayout(self.layout)
        if edit:
            self.whatLanguagesWidget.addLanguageBtn.setFocus(True)
        self.whatLanguagesWidget.saveReady.connect(self.onSaveReady)
        if hasattr(self.whatLanguagesWidget, 'addLanguageBtn'):
            self.whatLanguagesWidget.addLanguageBtn.clicked.connect(self.scrollLangWidget)

    def refreshWrittenLangs(self):
        old_langs = self.gloss_languages
        mw = qApp.instance().getMainWindow()
        mw.reloadProject(force=True)
        _new_langs = qApp.instance().pm.project.writtenLanguages
        new_langs = [[l.id, l.name, l.order] for l in _new_langs]
        if new_langs != old_langs:
            box = QMessageBox(self)
            box.setWindowTitle(' ')
            txt1 = qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Written languages have been edited by another user.')
            txt2 = qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Your display may show changes.')
            msg = '{}\n{}'.format(txt1, txt2)
            box.setText(msg)
            box.setIcon(QMessageBox.Information)
            box.exec_()

            self.whatLanguagesWidget.close()
            del self.whatLanguagesWidget
            langs = [l.id for l in _new_langs]
            self.whatLanguagesWidget = LanguagesWidget(self, langs, True)
            self.scrollArea.setWidget(self.whatLanguagesWidget)
            self.whatLanguagesWidget.addLanguageBtn.setFocus(True)
            self.whatLanguagesWidget.saveReady.connect(self.onSaveReady)
            self.whatLanguagesWidget.addLanguageBtn.clicked.connect(self.scrollLangWidget)

    def onEdit(self):
        if not self.acquired_full_project_lock and not self.acquired_project_lock:
            self.acquired_full_project_lock = qApp.instance().pm.acquireFullProjectLock(self) # deletion column
        if self.acquired_full_project_lock:
            if qApp.instance().pm.projectChanged():
                self.refreshWrittenLangs()
            self.whatLanguagesWidget.setupEditing()
            self.edit = True
            self.edit_btn.setDisabled(True)
            self.edit_btn.setToolTip(None)    
            self.scrollArea.ensureWidgetVisible(self.whatLanguagesWidget.addLanguageBtn)
            self.setWindowTitle(qApp.instance().translate('EditWrittenLanguageSettingsDlg', 'Edit Written Language Settings'))
            qApp.instance().pm.startInactivityTimer(self)
        
    def sizeHint(self):
        s = QSize(1280, 800)
        try:
            s = qApp.screenAt(self.pos()).availableSize()
        except:
            pass
        max_width = s.width() * 0.90
        max_height = s.height() * 0.90 
        min_height = 200           

        w = self.whatLanguagesWidget.width() + 64
        if w > max_width:
            w = max_width
        h = self.lang_count * 24 + 200
        if h < min_height:
            h = min_height
        elif h > max_height:
            h = max_height
        return QSize(int(w), int(h))

    def hideEvent(self, evt):
        qApp.instance().pm.stopInactivityTimer()
        qApp.processEvents()
        super(EditWrittenLanguageSettingsDlg, self).hideEvent(evt)  

    def leaveEdit(self, check_dirty=False):
        # if self.acquired_project_lock:
        #     qApp.instance().pm.releaseProjectLock()
        if self.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock()  
        self.reject()

    ##!!@pyqtSlot()
    def onOK(self):
        qApp.instance().resetKeyboard()
        QTimer.singleShot(0, self.accept)
    
    ##!!@pyqtSlot()    
    def onCancel(self):
        qApp.instance().resetKeyboard()
        QTimer.singleShot(0, self.reject)
    
    ##!!@pyqtSlot()
    def scrollLangWidget(self):
        scroller = self.scrollArea.verticalScrollBar()
        value = scroller.value()
        scroller.setValue(value + 100) #scroll to bottom
        
    @property
    def gloss_languages(self):
        return self.whatLanguagesWidget.gloss_languages
    
    def getSelectedLangIds(self):
        return self.whatLanguagesWidget.getSelectedLangIds()
    
    def getSearchLangId(self):
        return self.whatLanguagesWidget.getSearchLangId()
    
    def getFontSizes(self):
        return self.whatLanguagesWidget.getFontSizes()
    
    def getFontFamilies(self):
        return self.whatLanguagesWidget.getFontFamilies()
    
    def getOrigFontSizes(self):
        return self.whatLanguagesWidget.getOrigFontSizes()
    
    def getOrigFontFamilies(self):
        return self.whatLanguagesWidget.getOrigFontFamilies()
    
    def getOrigSearchLangId(self):
        return self.whatLanguagesWidget.getOrigSearchLangId()
    
    def getOrigSelectedLangIds(self):
        return self.whatLanguagesWidget.getOrigSelectedLangIds()
    
    def getLangOrder(self):
        return self.whatLanguagesWidget.getLangOrder()
    
    def getKeyboardLayouts(self):
        return self.whatLanguagesWidget.getKeyboardLayouts()
    
    def getOrigKeyboardLayouts(self):
        return self.whatLanguagesWidget.getOrigKeyboardLayouts()
    
    def useAutoKeyboard(self):
        return self.whatLanguagesWidget.useAutoKeyboard()
    
    ##!!@pyqtSlot(bool)
    def onSaveReady(self, _bool):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.OKBtn.setEnabled(_bool)
            
class NewProjectDlg(QDialog):
    """Dialog used when creating a new dictionary."""
    
    def __init__(self, parent=None):
        super(NewProjectDlg, self).__init__(parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint) #|Qt.WindowStaysOnTopHint)
        #self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(qApp.instance().translate('NewProjectDlg', "Create New Dictionary"))
        
        self.layout = QVBoxLayout()
        self.layout.setSizeConstraint(QLayout.SetFixedSize)
        self.layout.setSpacing(3)
        self.layout.setContentsMargins(3, 3, 3, 3)        
        self.notebook = QTabWidget()
        self.notebook.setTabPosition(QTabWidget.South)
         
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('NewProjectDlg', 'Ok'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('NewProjectDlg', 'Cancel'))
        self.OKBtn = self.btnBox.button(QDialogButtonBox.Ok)
        self.CancelBtn = self.btnBox.button(QDialogButtonBox.Cancel)
        self.OKBtn.setFocusPolicy(Qt.StrongFocus)
        self.CancelBtn.setFocusPolicy(Qt.StrongFocus)       
        self.OKBtn.setDisabled(True)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)
         
        text = "<p><i><strong>{}</strong><br>{}</i></p>".format(qApp.instance().translate('NewProjectDlg', "Click 'Ok' to create your new dictionary."),
            qApp.instance().translate('NewProjectDlg', 'View and change details by clicking on the tabs above.'))
        self.readyToCreateLbl = QLabel(text)
        self.readyToCreateLbl.hide()
         
        #setup WhatProject? page        
        self.whatProjectWidget = ProjectWidget(self)
        self.notebook.addTab(self.whatProjectWidget, qApp.instance().translate('NewProjectDlg', "Dictionary details"))
        self.notebook.setTabIcon(0, QIcon(":/new_project.png"))
         
        #setup WhatDialect? widget
        self.whatDialectsWidget = DialectsWidget(self, is_new=True)
         
        self.notebook.addTab(self.whatDialectsWidget, qApp.instance().translate('NewProjectDlg', "Which dialect(s)?"))
        self.notebook.setTabIcon(1, QIcon(":/edit_dialects.png"))
        self.notebook.setTabEnabled(1, False)
         
        #setup WhatLanguage? widget
        self.whatLanguagesWidget = LanguagesWidget(parent=self, is_new=True)
                     
        self.notebook.addTab(self.whatLanguagesWidget, qApp.instance().translate('NewProjectDlg', "Which written language(s)?"))
        self.notebook.setTabIcon(2, QIcon(":/edit_langs.png"))
        self.notebook.setTabEnabled(2, False)
         
        self.layout.addSpacing(20)       
        self.layout.addWidget(self.notebook) 
             
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(3, 3, 3, 3)
        hlayout.setSpacing(6)
        hlayout.addSpacing(10)
        hlayout.addWidget(self.readyToCreateLbl) 
        hlayout.addStretch() 
        hlayout.addWidget(self.btnBox)
        self.layout.addLayout(hlayout)
         
        self.setLayout(self.layout)
        self.setMinimumSize(500, 250)
        
        self.notebook.currentChanged.connect(self.onPageChanged) 
        self.whatProjectWidget.setInitialFocus()
        
        self.readyToSaveTimer = QTimer(self)
        self.readyToSaveTimer.timeout.connect(self.onReadyToSave)
        self.readyToSaveTimer.start(500)

    @property
    def language_name(self):
        return self.whatProjectWidget.language_name
        
    @property
    def project_name(self):
        return self.whatProjectWidget.project_name
    
    @property
    def project_version(self):
        return self.whatProjectWidget.project_version
    
    @property
    def project_location(self): 
        return self.whatProjectWidget.location
    
    @property
    def dialects(self):
        return self.whatDialectsWidget.dialects
    
    @property
    def gloss_languages(self):
        return self.whatLanguagesWidget.gloss_languages
    
    @property
    def project_descript(self):
        return self.whatProjectWidget.about_project           

    ### some methods for populating fields, mainly used when merging; see 'project_merger.py'.###
    def setupForMerging(self):
        self.readyToSaveTimer.timeout.disconnect(self.onReadyToSave)
        self.readyToSaveTimer.stop()
        self.setWindowTitle(qApp.instance().translate('NewProjectDlg', 'Create Merged Dictionary'))
        self.notebook.setTabEnabled(1, True)
        self.notebook.setTabEnabled(2, True)
        self.OKBtn.setEnabled(True)
        self.whatProjectWidget.dialectNextBtn.hide()
        self.whatDialectsWidget.langNextBtn.hide()
        self.whatDialectsWidget.clear()
        self.whatLanguagesWidget.clear()
        
    def setSignLanguage(self, text):
        self.whatProjectWidget.language_name_edit.setText(text)

    def setName(self, text):
        self.whatProjectWidget.project_name_edit.setText(text)

    def setVersion(self, text):
        self.whatProjectWidget.project_version_edit.setText(text)

    def setDescription(self, text):
        widget = self.whatProjectWidget
        editor = widget.project_description_edit
        editor.setPlainText(text)
        
    def setDialects(self, dialects):
        widget = self.whatDialectsWidget
        for d in dialects:
            widget.onAddDialect(d)

    def setWrittenLanguages(self, languages):
        widget = self.whatLanguagesWidget
        for l in languages:
            widget.onAddLanguage(l)
    #############################################################################################
    
    ##!!@pyqtSlot(int)    
    def onPageChanged(self, idx):
        if idx == 0: #initial dictionary page
            self.whatProjectWidget.setInitialFocus()
        elif idx == 1: #dialects page
            self.whatDialectsWidget.setInitialFocus()            
        elif idx == 2: #languages page
            self.whatLanguagesWidget.setInitialFocus()  
            
    def onPageReady(self, _bool):  
        pass
    
    ##!!@pyqtSlot()    
    def onNextBtnClicked(self):
        btn = self.sender()
        btn.hide() #page is now enabled and can be changed by tab
        if btn.parent() is self.whatProjectWidget:           
            self.notebook.setTabEnabled(1, True)     
            self.notebook.setCurrentWidget(self.whatDialectsWidget)
        elif btn.parent() is self.whatDialectsWidget:
            self.notebook.setTabEnabled(2, True)  
            self.notebook.setCurrentWidget(self.whatLanguagesWidget)
    
    ##!!@pyqtSlot()        
    def onReadyToSave(self):
        _bool = False
        if self.whatProjectWidget.isDirty() and \
            self.whatDialectsWidget.isDirty() and \
            self.whatLanguagesWidget.isDirty():
                _bool = True
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(_bool)
        if _bool:
            self.readyToCreateLbl.show()
        else:
            self.readyToCreateLbl.hide()
            
    def getSelectedLangIds(self):
        return self.whatLanguagesWidget.getSelectedLangIds()
        
    def getSearchLangId(self):
        return self.whatLanguagesWidget.getSearchLangId()
        
    def getFontSizes(self):
        return self.whatLanguagesWidget.getFontSizes()
    
    def getFontFamilies(self):
        return self.whatLanguagesWidget.getFontFamilies()
        
    def getLangOrder(self):
        return self.whatLanguagesWidget.getLangOrder() 
    
    def getKeyboardLayouts(self):
        return self.whatLanguagesWidget.getKeyboardLayouts()

class FileFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(FileFilterProxyModel, self).__init__(parent)
  
    def filterAcceptsRow(self, source_row, srcidx):
        model = self.sourceModel()
        index0 = model.index(source_row, 0, srcidx)
        fpth = model.filePath(index0)
        if os.path.isdir(fpth) and not qApp.instance().pm.getProjectFile(fpth): #self.isProjectDir(fpth): # prevent import into an existing dictionary!!!!
            return True
        return False
           
class ProjectWidget(QWidget):
    def __init__(self, parent=None):
        super(ProjectWidget, self).__init__(parent)
        self.project_name = '' 
        self.language_name = '' 
        self.project_version = ''      
        #self.location = os.path.normpath(os.path.join(QDir.homePath(), "SooSL", "projects"))        
        self.location = qApp.instance().getDefaultProjectsDir()
        layout = QVBoxLayout()
        
        self.project_name_edit = QLineEdit()
        # validator = FileNameValidator(self)
        # self.project_name_edit.setValidator(validator)
        # validator.invalidChar.connect(self.onInvalidProjectChar)
        # validator.invalidName.connect(self.onInvalidProjectName)
        self.project_name_edit.textChanged.connect(self.onProjectNameChanged)
        
        self.project_version_edit = QLineEdit()
        self.project_version_edit.textChanged.connect(self.onProjectVersionChanged)
        
        self.language_name_edit = QLineEdit()
        self.language_name_edit.textChanged.connect(self.onLanguageNameChanged)
        
        self.exist_proj_label = QLabel("<i>{}</i>".format(qApp.instance().translate('ProjectWidget', 'Existing dictionary title')))
        self.exist_proj_label.setStyleSheet("color: red")
        self.exist_proj_label.hide()
        
        self.invalid_char_label = QLabel()
        self.invalid_char_label.setStyleSheet("color: red")
        self.invalid_char_label.setWordWrap(True)
        self.invalid_char_label.hide()
        
        self.invalid_project_name_label = QLabel()
        self.invalid_project_name_label.setStyleSheet("color: red")
        self.invalid_project_name_label.hide()
        
        label = QLabel("<b>{}</b>".format(qApp.instance().translate('ProjectWidget', "SIGN LANGUAGE WHAT?")))
        label.setStyleSheet("color: blue")
        layout.addWidget(label)
        layout.addWidget(self.language_name_edit)
        
        label = QLabel("<b>{}</b>".format(qApp.instance().translate('ProjectWidget', "DICTIONARY TITLE WHAT?")))
        label.setStyleSheet("color: blue")
        layout.addWidget(label)
        layout.addWidget(self.project_name_edit)
        
        label = QLabel("<b>{} </b>({})".format(qApp.instance().translate('ProjectWidget', "DICTIONARY VERSION WHAT?"), qApp.instance().translate('ProjectWidget', 'optional')))
        label.setStyleSheet("color: blue")
        layout.addWidget(label)
        layout.addWidget(self.project_version_edit)
        
        layout.addWidget(self.exist_proj_label)
        layout.addWidget(self.invalid_char_label)
        layout.addWidget(self.invalid_project_name_label)
        layout.addSpacing(7)
        
        label = QLabel("<b>{}</b>".format(qApp.instance().translate('ProjectWidget', "STORE DICTIONARY WHERE?")))
        label.setStyleSheet("color: blue")
        layout.addWidget(label)

        self.change_loc_label = QLabel(self.location)
        #layout.addWidget(self.change_loc_label)

        changeAction = QAction(QIcon(':/open_file.png'), 
            qApp.instance().translate('ProjectWidget', 'Change'), self, 
            toolTip=qApp.instance().translate('ProjectWidget', 'Change dictionary location'), 
            triggered=self.onLocationBtnClicked)

        self.change_loc_btn = QToolButton()
        self.change_loc_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.change_loc_btn.setDefaultAction(changeAction)
        self.change_loc_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.change_loc_btn.setCursor(QCursor(Qt.PointingHandCursor))

        layout.addWidget(self.change_loc_label)
        layout.addWidget(self.change_loc_btn)
        layout.addSpacing(7)
        
        label = QLabel("<b>{}</b> ({})".format(qApp.instance().translate('ProjectWidget', 'ABOUT DICTIONARY?'), qApp.instance().translate('ProjectWidget', 'optional')))
        label.setStyleSheet("color: blue")
        hlayout = QHBoxLayout()
        hlayout.addWidget(label)
        layout.addLayout(hlayout)
        self.preview_btn = QPushButton(qApp.instance().translate('ProjectWidget', 'Preview HTML'))
        self.preview_btn.setToolTip('{}\n{}'.format(qApp.instance().translate('ProjectWidget', 'You may use HTML tags to style your description.'), qApp.instance().translate('ProjectWidget', 'Click here to change between editing and viewing HTML style.')))
        self.preview_btn.clicked.connect(self.onPreviewHtml)
        self.preview_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.preview_btn.setEnabled(False)
        hlayout.addWidget(self.preview_btn)
        hlayout.addStretch()
        
        self.description_stack = QStackedWidget()   
        self.project_description_edit = QTextEdit()
        self.project_description_edit.setToolTip(qApp.instance().translate('ProjectWidget', "Write a short description of your dictionary."))
        self.project_description_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.project_description_edit.setAcceptRichText(False)
        self.project_description_edit.setReadOnly(False)
        self.project_description_edit.setTabChangesFocus(True)
        self.project_description_edit.setDisabled(True)
        self.project_description_edit.textChanged.connect(self.setPreview)
        self.description_stack.addWidget(self.project_description_edit)
        self.project_description_preview = QTextBrowser()
        self.project_description_preview.setOpenExternalLinks(True)
        self.project_description_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.project_description_preview.setAcceptRichText(True)
        self.project_description_preview.setReadOnly(True)
        self.project_description_preview.setFocusPolicy(Qt.NoFocus)
        self.description_stack.addWidget(self.project_description_preview)
        self.description_stack.setCurrentWidget(self.project_description_edit)
        layout.addWidget(self.description_stack)
        
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(3, 3, 3, 3)
        hlayout.setSpacing(6)
        label = QLabel()
        label = QLabel("<i>{}<br>{}</i>".format(qApp.instance().translate('ProjectWidget', 'You can change <strong>About Dictionary?</strong> information later.'), 
            qApp.instance().translate('ProjectWidget', "See other items under the blue tools icon.")))
        hlayout.addWidget(label)
        label = QLabel()
        label.setPixmap(QPixmap(':/tools.png'))
        hlayout.addWidget(label)
        hlayout.addStretch()
        
        self.dialectNextBtn = QPushButton("{} -->".format(qApp.instance().translate('ProjectWidget', 'Next')))
        self.dialectNextBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.dialectNextBtn.setToolTip(qApp.instance().translate('ProjectWidget', "Next - Which dialect(s)?"))
        self.dialectNextBtn.setEnabled(False)
        self.dialectNextBtn.clicked.connect(self.parent().onNextBtnClicked)
        hlayout.addWidget(self.dialectNextBtn)
        layout.addLayout(hlayout)
        self.setLayout(layout)
        
        self.valid_project_name = False
        self.valid_language_name = False
        
        self.readyToSaveTimer = QTimer(self)
        self.readyToSaveTimer.timeout.connect(self.onReadyToSave)
        self.readyToSaveTimer.start(200)
        
        for w in [self.language_name_edit, self.project_name_edit, self.project_version_edit, self.change_loc_btn, self.project_description_edit, self.dialectNextBtn]:
            w.setFocusPolicy(Qt.StrongFocus)
            
    def currentText(self):
        return self.project_description_edit.toPlainText().strip()
            
    def setPreview(self):
        current_text = self.currentText()
        if current_text and current_text.count('<') and current_text.count('>'):
            self.preview_btn.setEnabled(True)
            br = '<br style="line-height: 50%;">'
            message = current_text.replace('\n\n', br)
            message = message.replace('\n', '')
            self.project_description_preview.setHtml(message)
            self.preview_btn.setEnabled(True)
        else:
            self.preview_btn.setEnabled(False)
            self.project_description_preview.setText(current_text)
            self.preview_btn.setEnabled(False)
            
    def onPreviewHtml(self):
        if self.description_stack.currentWidget() is self.project_description_edit:
            self.description_stack.setCurrentWidget(self.project_description_preview)
            self.sender().setText(qApp.instance().translate('ProjectWidget', 'Edit'))
        else:
            self.description_stack.setCurrentWidget(self.project_description_edit)
            self.sender().setText(qApp.instance().translate('ProjectWidget', 'Preview HTML'))
        
    @property
    def about_project(self):
        return self.currentText() #self.project_description_edit.toPlainText() # 5.11.3 # 5.14.1 toMarkdown(self.project_description_edit.document().MarkdownNoHTML)
    
    #@property
    def isDirty(self):
        #print('dirty', self.valid_language_name, self.valid_project_name)
        #project_path = os.path.join(self.location, self.project_name)
        if self.valid_project_name and self.valid_language_name:
            return True
        return False
    
    ##!!@pyqtSlot(str)
    def onInvalidProjectChar(self, char):
        if not char:
            self.invalid_char_label.hide()
        else:
            text = "<p>{} '{}'.</p>".format(qApp.instance().translate('ProjectWidget', 'Invalid character'), char)
            if char in ['\\', '/']:
                add_text = "<p style='color:Black'>{}</p>".format(qApp.instance().translate('ProjectWidget', """If you want a new directory for your dictionary,
                    you can make one below with 'STORE DICTIONARY WHERE?'"""))
                text = '{}{}'.format(text, add_text)
            self.invalid_char_label.setText(text)
            self.invalid_char_label.show()
     
    ##!!@pyqtSlot(str)       
    def onInvalidProjectName(self, name):
        if name:
            self.project_name_edit.setStyleSheet("color:Red")
            self.valid_project_name = False
            text = "<p style='color:Red'>{} - <STRONG>{}</STRONG></p>".format(qApp.instance().translate('ProjectWidget', 'Reserved filename'), name)
            self.invalid_project_name_label.setText(text)
            self.invalid_project_name_label.show()  
        else:
            self.project_name_edit.setStyleSheet(None)
            #self.valid_project_name = True
            self.invalid_project_name_label.hide() 
    
    ##!!@pyqtSlot()    
    def onReadyToSave(self):
        _bool = self.isDirty()
        #self.change_loc_btn.setEnabled(_bool)
        self.dialectNextBtn.setEnabled(_bool) 
        self.project_description_edit.setEnabled(_bool)        
        
    def setInitialFocus(self):        
        self.language_name_edit.setFocus()
                
    def onLocationBtnClicked(self): 
        mw = qApp.instance().getMainWindow()
        dlg = mw.soosl_file_dlg
        dlg.setupForChangeProjectLocation()
        # dlg.show()
        # dlg.raise_() 
        qApp.processEvents()
        if dlg.exec_():
            self.location = dlg.selected_path.replace('\\', '/')
            self.change_loc_label.setText(self.location)
        # dictionary name hasn't changed, but directory location may have, possibly changing validity
        # of dictionary name, so retest using the same method   
        self.onProjectNameChanged(self.project_name)

    def onFullFileDlgBtn(self):
        dlg = QFileDialog(None, qApp.instance().translate('ProjectWidget', "Choose Dictionary Location"))
        dlg.setFileMode(QFileDialog.Directory)
        if dlg.exec_():
            paths = dlg.selectedFiles()
            if paths:
                pth = paths[0]
                import_dlg = self.sender().parent()
                import_dlg.setDirectory(pth)
                name_edit = import_dlg.findChild(QWidget, 'fileNameEdit')
                name_edit.setText(pth)
        del dlg
        ### BUG: This seems to raise an error report about fatal Windows errors, but no crash???
        ### just clear report for now so it doesn't flag up when SooSL starts
        qApp.instance().clearCrashReport()
                
    def onLanguageNameChanged(self, name):  
        if not name or name.strip() == '':
            self.language_name_edit.setText('')
            self.valid_language_name = False
        else:
            self.language_name = str(name) 
            self.valid_language_name = True     
    
    ##!!@pyqtSlot(str)    
    def onProjectNameChanged(self, name):
        if not name or name.strip() == '':
            self.project_name = ''
            self.project_name_edit.setText('')
            self.valid_project_name = False
        else:
            self.project_name = str(name)
            slug = qApp.instance().pm.sooslSlugify(name) #
            project_dir = os.path.join(self.location, slug)
            if name and not os.path.exists(project_dir): 
                self.valid_project_name = True
                self.exist_proj_label.hide() 
                self.dialectNextBtn.setEnabled(True)            
            else: 
                self.valid_project_name = False
                if name:
                    self.exist_proj_label.show() 
                    self.dialectNextBtn.setEnabled(False)  
                    
    def onProjectVersionChanged(self, version): 
        self.project_version = str(version.strip())

# NAME_COL = 0
# ABBR_COL = 1
# FOCAL_COL = 2
# SIGN_COUNT_COL = 3
# SENSE_COUNT_COL = 4
# REMOVE_COL = 5
# ID_COL = 6

class DialectsWidget(QWidget):
    saveReady = pyqtSignal(bool)
    showFocalDialect = pyqtSignal(bool)
    close_signal = pyqtSignal()
      
    def __init__(self, parent=None, edit=False, is_new=False):
        super(DialectsWidget, self).__init__(parent=parent)
        self.focal_item = None
        self.edit = edit
        self.new = True
        self.new_project = is_new

        self.able_to_edit = qApp.instance().pm.ableToEdit()
        layout = QVBoxLayout()
        
        label = QLabel("<b>{}</b>".format(qApp.instance().translate('DialectsWidget', 'SIGN VARIETIES WHICH?')))        
        label.setStyleSheet("color: blue")
        layout.addWidget(label)
        
        self.dialectTable = QTableWidget()
        self.dialectTable.setTabKeyNavigation(True) 
        self.dialectTable.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 
        self.dialectTable.setShowGrid(False)
        self.dialectTable.verticalHeader().hide()
        self.dialectTable.setColumnCount(7)
        self.dialectTable.setColumnHidden(6, True)
        self.dialectTable.setHorizontalHeaderLabels([qApp.instance().translate('DialectsWidget', "Name"), qApp.instance().translate('DialectsWidget', "Abbreviation"), "", qApp.instance().translate('DialectsWidget', 'Signs'), qApp.instance().translate('DialectsWidget', 'Senses'), ""])
        self.dialectTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.dialectTable.horizontalHeader().setStretchLastSection(False)
        self.dialectTable.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.dialectTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.dialectTable.setItemDelegate(DialectItemDelegate(self.dialectTable))        
        self.dialectTable.itemChanged.connect(self.onDialectItemChanged)
        self.dialectTable.itemSelectionChanged.connect(self.onCellChange)
        self.dialectTable.itemClicked.connect(self.onItemClicked)
        if is_new: #not edit and isinstance(self.parent(), NewProjectDlg):
            self.onAddDialect()
        layout.addWidget(self.dialectTable)
        
        if not is_new: #edit:    
            self.showFocalBtn = QCheckBox(self)
            self.showFocalBtn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.showFocalBtn.setText(qApp.instance().translate('DialectsWidget', 'Show focal abbreviation?'))
            layout.addWidget(self.showFocalBtn)
            settings = qApp.instance().getSettings()
            self.show_focal = settings.value('showFocalDialect', False)
            if isinstance(self.show_focal, str):
                if self.show_focal.lower() == 'true':
                    self.show_focal = True
                else:
                    self.show_focal = False
            if self.show_focal:
                self.showFocalBtn.setChecked(True)
                 
            self.showFocalBtn.toggled.connect(self.onShowFocalDialect)
            self.showFocalBtn.toggled.connect(self.onToggled)
        
        hlayout = QHBoxLayout()
        if is_new: #not edit:
            hlayout.setContentsMargins(3, 3, 3, 3)
            hlayout.setSpacing(6)
            label = QLabel()
            label = QLabel("<i>{}<br>{}</i>".format(qApp.instance().translate('DialectsWidget', '<strong>Dialects</strong> can be added or edited later.'), 
                                                    qApp.instance().translate('DialectsWidget', "See 'Edit dialects' under the blue tools icon.")))
            hlayout.addWidget(label)
            label = QLabel()
            label.setPixmap(QPixmap(':/tools.png'))
            hlayout.addWidget(label)
            
        hlayout.addStretch()
        self.addDialectBtn = QPushButton(QIcon(":/add.png"), "")
        self.addDialectBtn.setFocusPolicy(Qt.StrongFocus)
        self.addDialectBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.addDialectBtn.setToolTip(qApp.instance().translate('DialectsWidget', "More Dialects? Click here to add one more"))
        self.addDialectBtn.setEnabled(False)
        if isinstance(self.parent(), EditDialectsDlg):
            self.addDialectBtn.setVisible(False)
        self.addDialectBtn.clicked.connect(self.onAddDialect)
        hlayout.addWidget(self.addDialectBtn)        
        if is_new: #not edit and isinstance(self.parent(), NewProjectDlg):
            self.langNextBtn = QPushButton("{} -->".format(qApp.instance().translate('DialectsWidget', 'Next')))
            self.langNextBtn.setFocusPolicy(Qt.StrongFocus)
            self.langNextBtn.setCursor(QCursor(Qt.PointingHandCursor))
            self.langNextBtn.setToolTip(qApp.instance().translate('DialectsWidget', "Next - Which written language(s)?"))
            self.langNextBtn.setEnabled(False)
            self.langNextBtn.clicked.connect(self.parent().onNextBtnClicked)
            hlayout.addWidget(self.langNextBtn)        
        layout.addLayout(hlayout)
        self.setLayout(layout) 
        
        self.inFirstCell = False
        self.inLastCell = False
        
        if not is_new:
            QTimer.singleShot(0, self.dialectTable.scrollToTop)
        else:
            self.dialectTable.horizontalHeader().setStretchLastSection(True)
        #some columns should not be shown if dictionary is 'read-only'
        if not is_new: #self.new_project and not self.able_to_edit:
            self.dialectTable.setColumnHidden(5, True)
            self.addDialectBtn.setHidden(True)

    def clear(self):
        self.dialectTable.clearContents()
        self.dialectTable.setRowCount(0)

    def setupEditing(self):
        self.edit = True
        self.addDialectBtn.setVisible(True)
        self.addDialectBtn.setEnabled(True)
        self.addDialectBtn.setFocus(True)
        self.dialectTable.setColumnHidden(5, False)
        self.dialectTable.horizontalHeader().setStretchLastSection(True)
        for row in range(self.dialectTable.rowCount()):
            name_item = self.dialectTable.item(row, 0)
            name_item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable)
            abbr_item = self.dialectTable.item(row, 1)
            abbr_item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable)
            focal = self.dialectTable.cellWidget(row, 2)
            focal.setEnabled(True)
        self.adjustSize()
            
    def onShowFocalDialect(self):
        toggle = self.sender()
        settings = qApp.instance().getSettings()
        settings.setValue('showFocalDialect', toggle.isChecked())
        settings.sync()
        self.showFocalDialect.emit(toggle.isChecked())
        qApp.processEvents()
        
    @property
    def dialects(self):
        return self.getDialects()
        
    def setInitialFocus(self):
        self.dialectTable.setTabKeyNavigation(True)
        row = self.dialectTable.rowCount() - 1
        item = self.dialectTable.item(row, 0)
        if item:
            self.dialectTable.setCurrentItem(item)
            item.setSelected(True)
        self.dialectTable.setFocus()
        if row == 0 and item:
            self.dialectTable.editItem(item)
            line_edit = self.dialectTable.cellWidget(row, 0)
            line_edit.setFocus()
            
    def onDeleteOld(self):
        pass
    
    ##!!@pyqtSlot(bool)
    def onToggled(self, _bool):
        self.saveReady.emit(self.isDirty())
    
    def onRemoveNew(self):        
        btn = self.sender()
        self.dialectTable.hideRow(btn.row)
        if not self.dialectTable.rowCount():
            self.addDialectBtn.setEnabled(True)
            
    def __undeletedCount(self):
        count = 0
        for row in range(self.dialectTable.rowCount()):
            if self.dialectTable.item(row, 5).data(Qt.UserRole) == 1:
                count += 1
        return count 
    
    ##!!@pyqtSlot(QTableWidgetItem)
    def onItemClicked(self, item):
        if item.column() == 5: # deletion column
            row = item.row()
            nameItem = self.dialectTable.item(row, 0)
            abbrItem = self.dialectTable.item(row, 1)
            focalRadio = self.dialectTable.cellWidget(row, 2)
            
            if item.data(Qt.UserRole) == 1 and self.__undeletedCount() == 1:
                QMessageBox.warning(self, 
                qApp.instance().translate('DialectsWidget', "Cannot Delete Last Dialect"),
                "<STRONG>{}</STRONG>".format(qApp.instance().translate('DialectsWidget', 'At least one dialect is required')))
                return
            if focalRadio.isChecked():
                QMessageBox.warning(self, 
                qApp.instance().translate('DialectsWidget', "Cannot Delete Focal Dialect"),
                "<STRONG>{}</STRONG>".format(qApp.instance().translate('DialectsWidget', 'Set another focal dialect before deleting this one.')))
                return 
            if not nameItem.data(Qt.UserRole) and not abbrItem.data(Qt.UserRole):
                    self.dialectTable.removeRow(row)
                    self.addDialectBtn.setEnabled(True)
            elif item.data(Qt.UserRole) == 1:
                sign_count = int(self.dialectTable.item(row, 3).text())
                if sign_count:
                    name = nameItem.text() #dialect[1].upper()
                    sign_txt = qApp.instance().translate('DialectsWidget', '1 Sign uses this dialect.')
                    txt1 = qApp.instance().translate('DialectsWidget', 'This will be changed to the focal dialect.')
                    if sign_count > 1:
                        sign_txt = "<span style='color:blue;'>{}</span> {}".format(sign_count, qApp.instance().translate('DialectsWidget', 'Signs use this dialect:'))
                        txt1 = qApp.instance().translate('DialectsWidget', 'These will be changed to the focal dialect:')
                    text = "<b>{} <span style='color:blue;'>{}</span></b><br><br>{} <span style='color:blue;'>{}</span>".format(sign_txt, name, txt1, self.getFocalDialect()) #new_focal[1])
                    msgBox = QMessageBox(self)
                    self.close_signal.connect(msgBox.close)
                    msgBox.setIcon(QMessageBox.Warning)
                    msgBox.setTextFormat(Qt.RichText)
                    msgBox.setWindowTitle(qApp.instance().translate('DialectsWidget', "Delete Dialect"))
                    msgBox.setText(text)
                    msgBox.setInformativeText(qApp.instance().translate('DialectsWidget', "Is this what you want to do?"))
                    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    yes_btn, no_btn = msgBox.buttons()
                    yes_btn.setIcon(QIcon(":/thumb_up.png"))
                    no_btn.setIcon(QIcon(":/thumb_down.png"))
                    msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('DialectsWidget', "Yes"))
                    msgBox.button(QMessageBox.No).setText(qApp.instance().translate('DialectsWidget', "No"))
                    msgBox.setDefaultButton(QMessageBox.No)
                    if msgBox.exec_() == QMessageBox.Yes: #remove this dialect
                        item.setData(Qt.UserRole, -1)
                        item.setIcon(QIcon(":/trash24_red.png"))
                        item.setToolTip(qApp.instance().translate('DialectsWidget', "Click to keep this dialect"))
                        focalRadio = QRadioButton() #QTableWidgetItem("")
                        focalRadio.setEnabled(False)
                        self.dialectTable.setCellWidget(row, 2, focalRadio)
                        for i in [nameItem, abbrItem]:#, focalItem]:
                            #i.setFlags(Qt.ItemIsEnabled)
                            i.setFlags(Qt.NoItemFlags)
                        self.markForDelete(row, True)
                else:
                    item.setData(Qt.UserRole, -1)
                    item.setIcon(QIcon(":/trash24_red.png"))
                    item.setToolTip(qApp.instance().translate('DialectsWidget', "Click to keep this dialect"))
                    focalRadio = QRadioButton() #QTableWidgetItem("")
                    focalRadio.setEnabled(False)
                    self.dialectTable.setCellWidget(row, 2, focalRadio)
                    for i in [nameItem, abbrItem]:#, focalItem]:
                        #i.setFlags(Qt.ItemIsEnabled)
                        i.setFlags(Qt.NoItemFlags)
                    self.markForDelete(row, True)
            else:
                item.setData(Qt.UserRole, 1)
                item.setIcon(QIcon(":/trash20.png"))
                item.setToolTip(qApp.instance().translate('DialectsWidget', "Click to delete this dialect"))
                nameItem.setFlags(Qt.ItemIsEditable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                abbrItem.setFlags(Qt.ItemIsEditable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                focalRadio.setChecked(False)
                focalRadio.setEnabled(True)
                self.markForDelete(row, False)
        
            self.dialectTable.hideRow(row)
            self.dialectTable.showRow(row)
            self.onReadyToSave()           
        
        if not self.dialectTable.rowCount():
            self.addDialectBtn.setEnabled(True) 
    
    ##!!@pyqtSlot()    
    def onCellChange(self):        
        try:
            index = self.dialectTable.selectedIndexes()[0]
        except: #this occurs when focus has moved out of table items; no selected indexes
            self.inFirstCell = False
            self.inLastCell = False
            def setnav():
                self.dialectTable.setTabKeyNavigation(True)                
                self.addDialectBtn.setFocus(True)
            QTimer.singleShot(0, setnav)
        else:
            maxrow = self.dialectTable.rowCount() - 1
            maxcol = self.dialectTable.columnCount() - 2
            if index.row() == maxrow and index.column() == 5:
                self.inLastCell = True
            else:
                self.inLastCell = False
            if index.row() == 0 and index.column() == 0:
                self.inFirstCell = True
            else:
                self.inFirstCell = False
                
    #@property
    def isDirty(self): # True = unsaved data
        if self.edit and self.show_focal != self.showFocalBtn.isChecked():
            return True
        row_count = self.dialectTable.rowCount()
        try:
            for row in range(row_count):
                name = self.dialectTable.item(row, 0).text()
                abbr = self.dialectTable.item(row, 1).text()
                old_name = self.dialectTable.item(row, 0).data(Qt.UserRole)
                old_abbr = self.dialectTable.item(row, 1).data(Qt.UserRole)
                focal = self.dialectTable.cellWidget(row, 2).isChecked()
                remove = self.dialectTable.item(row, 5).data(Qt.UserRole)
                # name and abbreviation required for each dialect
                if not name or not abbr:
                    if row_count > 1 and not name and not abbr: # ignore blank row
                        pass
                elif name != old_name:
                    return True
                elif abbr != old_abbr:
                    return True
                elif focal and self.dialectTable.property('orig_focal_row') != row:
                    return True
                elif remove < 0:
                    return True
        except:
            pass
        return False
    
    def onReadyToSave(self):
        _bool = self.isDirty()
        if not self.edit and self.new_project:
            self.langNextBtn.setEnabled(_bool)
        count = self.dialectTable.rowCount()
        if count:
            last_row = count - 1
            nameItem = self.dialectTable.item(last_row, 0)
            abbrItem = self.dialectTable.item(last_row, 1)
            name = nameItem.text()
            abbr = abbrItem.text()
            if name and abbr:
                self.addDialectBtn.setEnabled(True)
            else:
                self.addDialectBtn.setEnabled(False)
        self.saveReady.emit(_bool)
    
    ##!!@pyqtSlot(QTableWidgetItem)        
    def onDialectItemChanged(self, item):
        try:
            self.dialectTable.itemChanged.disconnect(self.onDialectItemChanged)
        except:
            pass

        row = item.row()
        try:
            name = self.dialectTable.item(row, 0).text()
            abbr = self.dialectTable.item(row, 1).text()
        except:
            pass
        else:
            if not self.new and item.checkState() == Qt.Checked and (not name or not abbr):
                item.setCheckState(Qt.Unchecked)
                QMessageBox.warning(self, 
                    qApp.instance().translate('DialectsWidget', "Name or abbreviation missing"),
                    qApp.instance().translate('DialectsWidget', """<STRONG>Name</STRONG> and <STRONG>abbreviation</STRONG> are both required"""))
                if not name:
                    self.dialectTable.editItem(self.dialectTable.item(row, 0))
                    self.dialectTable.setCurrentItem(self.dialectTable.item(row, 0))
                elif not abbr:
                    self.dialectTable.editItem(self.dialectTable.item(row, 1))
                    self.dialectTable.setCurrentItem(self.dialectTable.item(row, 1))
                self.dialectTable.itemChanged.connect(self.onDialectItemChanged)
                return
        
        col = item.column()
        if col == 2:
            try:
                state = item.checkState()
            except:
                pass
            else:
                if state == Qt.Checked:
                    if self.focal_item:
                        try:
                            self.focal_item.setCheckState(Qt.Unchecked)
                        except:
                            pass
                        else:
                            self.focal_item.setData(Qt.UserRole, False)
                            self.focal_item.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                            self.focal_item.setText("")
                    self.focal_item = item
                    self.focal_item.setData(Qt.UserRole, True)    
                    item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                    item.setText(qApp.instance().translate('DialectsWidget', "Focal"))
                else:
                    item.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                    item.setText("")
                    item.setData(Qt.UserRole, False)
        self.dialectTable.itemChanged.connect(self.onDialectItemChanged) 
        try:
            self.onReadyToSave()  
        except:
            pass                  
    
    ##!!@pyqtSlot()
    ##!!@pyqtSlot(Dialect)                
    def onAddDialect(self, dialect=None):
        if hasattr(self, 'addDialectBtn'):
            self.addDialectBtn.setEnabled(False)
        table = self.dialectTable  
        table.setTabKeyNavigation(True)      
        model = table.model()
        row = model.rowCount()
        table.insertRow(row)
        
        if dialect:
            _id = QTableWidgetItem(str(dialect.id))
            name = QTableWidgetItem(dialect.name)
            name.setData(Qt.UserRole, dialect.name)
            abbr = QTableWidgetItem(dialect.abbr)
            abbr.setData(Qt.UserRole, dialect.abbr)
            try:
                sign_count, sense_count = qApp.instance().pm.project.countSignsSensesForDialect(dialect.id)
            except:
                sign_count, sense_count = 0, 0
            sign_count_item = QTableWidgetItem(str(sign_count))
            sense_count_item = QTableWidgetItem(str(sense_count))
        else:
            _id = QTableWidgetItem("0")
            name = QTableWidgetItem("")
            abbr = QTableWidgetItem("")
            sign_count_item = QTableWidgetItem("0")
            sense_count_item = QTableWidgetItem("0")
            
        focal = QRadioButton("", table)
        sign_count_item.setTextAlignment(Qt.AlignCenter)
        sign_count_item.setFlags(Qt.NoItemFlags)
        sense_count_item.setTextAlignment(Qt.AlignCenter)
        sense_count_item.setFlags(Qt.NoItemFlags)
        name.setToolTip(qApp.instance().translate('DialectsWidget', "Double-click to edit name"))
        abbr.setToolTip(qApp.instance().translate('DialectsWidget', "Double-click to edit abbreviation"))
        
        remove = QTableWidgetItem()
        icn = QIcon(":/trash20.png")
        remove.setIcon(icn)
        remove.setData(Qt.UserRole, 1)
        remove.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
        remove.setToolTip(qApp.instance().translate('DialectsWidget', "Click to delete dialect"))
        remove.setTextAlignment(Qt.AlignCenter)
        if (row == 0 and not dialect) or \
            dialect and isinstance(dialect.focal, str) and dialect.focal.lower() == 'true' or \
            dialect and isinstance(dialect.focal, int) and dialect.focal:
                focal.setChecked(Qt.Checked)
                focal.setText(qApp.instance().translate('DialectsWidget', "Focal"))
                table.setProperty('orig_focal_row', row)
        focal.toggled.connect(self.onToggled)
        if dialect and not self.new_project:# and not self.able_to_edit:
            name.setFlags(Qt.NoItemFlags) #Qt.ItemIsEnabled|Qt.ItemIsSelectable)
            abbr.setFlags(Qt.NoItemFlags) #Qt.ItemIsEnabled|Qt.ItemIsSelectable)
            focal.setDisabled(True)
        
        table.setItem(row, 0, name)
        table.setItem(row, 1, abbr)
        table.setCellWidget(row, 2, focal)
        table.setItem(row, 3, sign_count_item)
        table.setItem(row, 4, sense_count_item)
        table.setItem(row, 5, remove)
        table.setItem(row, 6, _id)
        
        index = model.index(row, 0)
        table.setCurrentIndex(index)
        if not dialect:
            table.editItem(name)
            table.scrollToBottom()
        self.new = False 
        
    def event(self, evt):
        if evt.type() == QEvent.ShortcutOverride: 
            if evt.key() == Qt.Key_Tab:
                if self.inLastCell:
                    self.dialectTable.setTabKeyNavigation(False)
                    self.dialectTable.setCurrentItem(None)
            elif evt.key() == Qt.Key_Backtab:
                if self.inFirstCell:
                    self.dialectTable.setTabKeyNavigation(False)
                    self.dialectTable.setCurrentItem(None)
            elif evt.key() == Qt.Key_Space:
                try:
                    item = self.dialectTable.selectedItems()[0]
                except:
                    pass
                else:
                    if item.column() == 5: # REMOVE item
                        self.onItemClicked(item) 
            return False
        elif evt.type() == QEvent.Hide:
            qApp.processEvents()
            self.close_signal.emit()
            return super(DialectsWidget, self).event(evt)
        else:
            return super(DialectsWidget, self).event(evt)
        
    def sizeHint(self):
        w = self.dialectTable.horizontalHeader().length() + 40
        if w > self.parent().width():
            w = self.parent().width()
        h = self.dialectTable.verticalHeader().length() + 150
        if h < 250:
            h = 250
        elif h > 450:
            h = 450
        return QSize(int(w), int(h))
        
    def showEvent(self, evt):
        name = self.dialectTable.item(0, 0)
        if name and not name.text():
            self.dialectTable.closePersistentEditor(name)
            self.addDialectBtn.setEnabled(False)
            self.dialectTable.setCurrentItem(name)
            def _edit():
                self.dialectTable.editItem(name) 
            QTimer.singleShot(0, _edit)
        
    def getDialects(self):
        dialects = []
        rows = range(self.dialectTable.rowCount())
        for row in rows:
            name = self.dialectTable.item(row, 0).text()
            if name:
                _id = int(self.dialectTable.item(row, 6).text())
                abbr = self.dialectTable.item(row, 1).text()
                focal = self.dialectTable.cellWidget(row, 2).isChecked()
                dialects.append([_id, name, abbr, focal])
        return dialects
    
    def getFocalDialect(self):
        dialects = self.getDialects()
        return [d[1] for d in dialects if d[3]][0]
    
    def markForDelete(self, row, _bool):
        idItem = self.dialectTable.item(row, 6)
        _id = abs(int(idItem.text()))
        if _bool:
            _id = -_id
        idItem.setText("{}".format(_id))
        
SEARCH_COL = 0
SHOWHIDE_COL = 1
NAME_COL = 2
FONT_SIZE_COL = 3
FONT_FAMILY_COL = 4
KEYBOARD_COL = 5
KEYBOARD_LBL_COL = 6
MOVEDOWN_COL = 7
MOVEUP_COL = 8
SIGN_COUNT_COL = 9
SENSE_COUNT_COL = 10
GLOSS_COUNT_COL = 11
REMOVE_COL = 12
COL_COUNT = 13
if sys.platform.startswith('linux'):
    MOVEDOWN_COL = 6
    MOVEUP_COL = 7
    SIGN_COUNT_COL = 8
    SENSE_COUNT_COL = 9
    GLOSS_COUNT_COL = 10
    REMOVE_COL = 11
    COL_COUNT = 12
#HEADERS = [" "," ","Name       "," ","Sample Text"," "," "," "," ", " "]

class LanguagesWidget(QWidget):
    saveReady = pyqtSignal(bool)
    close_signal = pyqtSignal()
     
    def __init__(self, parent=None, langs=None, edit=True, is_new=False):
        super(LanguagesWidget, self).__init__(parent=parent)
        if not qApp.instance().pm.ableToEdit():
            edit = False      
        self.edit = edit
        self.selected_row = 1
        self.selected_color = self.palette().highlight().color()
        self.selected_text_color = self.palette().highlightedText().color()
        self.__selected_lang_ids = []
        self.__orig_selected_lang_ids = qApp.instance().pm.selected_lang_ids
        settings = qApp.instance().getSettings()
        self.search_lang_id = 1
        self.search_row = None
        self.new = is_new
        if not self.new:
            name = qApp.instance().pm.current_project_filename
            self.search_lang_id = settings.value('ProjectSettings/{}/search_lang_id'.format(name), 1)
            if self.search_lang_id:
                self.search_lang_id = int(self.search_lang_id)
            
        self.orig_font_dict = {}  
        self.orig_font_family_dict = {}
        self.orig_keyboard_dict = {} 
        layout = QVBoxLayout()
        
        layout.setContentsMargins(4, 3, 3, 3)
        text = '<b>{}</b>'.format(qApp.instance().translate('LanguagesWidget', 'WRITTEN LANGUAGES WHICH?'))
        if not is_new:
            text = '<b>{}</b>'.format(qApp.instance().translate('LanguagesWidget', 'WRITTEN LANGUAGE SETTINGS WHAT?'))
        label = QLabel(text)
        label.setStyleSheet("color: blue;")
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(label)
                  
        self.languageLayout = QGridLayout()
        self.languageLayout.setContentsMargins(2, 2, 2, 2)
        
        name_lbl = QLabel(qApp.instance().translate('LanguagesWidget', 'Language name'))
        name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        name_lbl.setStyleSheet("color: blue")
        self.languageLayout.addWidget(name_lbl, 0, NAME_COL) 
        
        font_lbl = QLabel(qApp.instance().translate('LanguagesWidget', 'Font'))
        font_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        font_lbl.setStyleSheet("color: blue")
        self.languageLayout.addWidget(font_lbl, 0, FONT_FAMILY_COL)
        #if self.edit and qApp.instance().pm.ableToEdit():
        txt = qApp.instance().translate('LanguagesWidget', 'Sample text / keyboard')
        if sys.platform.startswith('linux'):
            txt = qApp.instance().translate('LanguagesWidget', 'Keyboard')
        sample_lbl = QLabel(txt)
        sample_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) 
        sample_lbl.setStyleSheet("color: blue")
        self.languageLayout.addWidget(sample_lbl, 0, KEYBOARD_COL, 1, 2) 
        if not self.new:
            for t in [
                (qApp.instance().translate('LanguagesWidget', 'Signs'), SIGN_COUNT_COL),
                (qApp.instance().translate('LanguagesWidget', 'Senses'), SENSE_COUNT_COL),
                (qApp.instance().translate('LanguagesWidget', 'Glosses'), GLOSS_COUNT_COL)
                ]:
                    txt, col = t
                    count_lbl = QLabel(txt)
                    count_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) 
                    count_lbl.setStyleSheet("color: blue")
                    self.languageLayout.addWidget(count_lbl, 0, col, 1, 1) 
        layout.addLayout(self.languageLayout) 
        keyboard_state = int(settings.value('autoKeyboardSwitchState', Qt.Checked))
        self.keyboardSwitchBox = QCheckBox(qApp.instance().translate('LanguagesWidget', 'Use automatic keyboard switching'))
        self.keyboardSwitchBox.setCheckState(keyboard_state)
        self.keyboardSwitchBox.stateChanged.connect(self.onKeyboardSwitchChanged)
        layout.addWidget(self.keyboardSwitchBox) 
        
        layout.addStretch()     
                  
        hlayout = QHBoxLayout()
        if self.new:           
            hlayout.setContentsMargins(3, 3, 3, 3)
            hlayout.setSpacing(6)
            #label = QLabel()
            label = QLabel("<i>{}<br>{}</i>".format(qApp.instance().translate('LanguagesWidget', '<strong>Languages</strong> can be added or edited later.'), 
                                                    qApp.instance().translate('LanguagesWidget', "See 'Edit written languages' under the blue tools icon.")))
            hlayout.addWidget(label)
            label = QLabel()
            label.setPixmap(QPixmap(':/tools.png'))
            hlayout.addWidget(label)
        #if self.new or (edit and qApp.instance().pm.ableToEdit()):
        self.addLanguageBtn = QPushButton(QIcon(":/add.png"), "")
        self.addLanguageBtn.setFocusPolicy(Qt.StrongFocus)
        self.addLanguageBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.addLanguageBtn.setToolTip(qApp.instance().translate('LanguagesWidget', "More Languages? Click here to add one more"))
        if not self.new:
            self.addLanguageBtn.setVisible(False)
        self.addLanguageBtn.clicked.connect(self.addNewLanguage)
        hlayout.addStretch()
        hlayout.addWidget(self.addLanguageBtn)
        layout.addLayout(hlayout)
        self.setLayout(layout) 
        if self.new:
            self.onAddLanguage()
        qApp.instance().focusChanged.connect(self.onFocusChanged)
        if langs:
            for l in langs:
                self.onAddLanguage(l)
            self.resetTabOrder() 
        self.onKeyboardSwitchChanged(keyboard_state)

    def hideEvent(self, evt):
        self.close_signal.emit()
        super(LanguagesWidget, self).hideEvent(evt)

    def setupEditing(self):
        self.edit = True
        self.addLanguageBtn.show()
        rowcount = self.languageLayout.rowCount()
        for row in range(1, rowcount): # row 0 is for column labels
            item = self.languageLayout.itemAtPosition(row, NAME_COL)
            if item:
                widget = item.widget()
                widget.setReadOnly(False)
                widget.setFrame(QFrame.StyledPanel)
                widget.setStyleSheet(None)
                # if row != rowcount - 1: #last row
                #     self.languageLayout.itemAtPosition(row, MOVEDOWN_COL).widget().show()
                # if row != 1: #first row
                #     self.languageLayout.itemAtPosition(row, MOVEUP_COL).widget().show()
                self.languageLayout.itemAtPosition(row, REMOVE_COL).widget().show()
        self.adjustSize()
            
    def onKeyboardSwitchChanged(self, state): 
        rows = self.languageLayout.rowCount()
        cols = [KEYBOARD_COL]
        if not sys.platform.startswith('linux'): 
            cols.append(KEYBOARD_LBL_COL)
        for row in range(rows): 
            for col in cols:
                item = self.languageLayout.itemAtPosition(row, col) 
                if item:
                    widget = item.widget()        
                    if state == Qt.Checked:
                        widget.setEnabled(True)
                    else:
                        widget.setEnabled(False)
        try:
            self.saveReady.emit(self.isDirty())  
        except:
            print('onKeyboardSwitchChanged error', state)     
                    
    def useAutoKeyboard(self):
        return self.keyboardSwitchBox.checkState()
     
    ##!!@pyqtSlot()   
    def addNewLanguage(self):
        self.onAddLanguage()
        self.saveReady.emit(False) #not ready until language text added
        
    def getFontDict(self):
        fdict = {}
        rows = range(1, self.languageLayout.rowCount())
        for row in rows:
            key_item = self.languageLayout.itemAtPosition(row, NAME_COL)
            value_item = self.languageLayout.itemAtPosition(row, FONT_SIZE_COL) 
            if key_item:
                name_edit = key_item.widget()
                font_spinner = value_item.widget() 
                lang_id = int(name_edit.id)
                if lang_id == 0: #new
                    lang_id = name_edit.text()
                elif lang_id < 0:
                    lang_id = None
                if lang_id:
                    fdict[lang_id] = font_spinner.value()
        return fdict  
    
    def getFontFamilyDict(self):
        kdict = {}
        rows = range(1, self.languageLayout.rowCount())
        for row in rows:
            key_item = self.languageLayout.itemAtPosition(row, FONT_FAMILY_COL)
            if key_item:
                font_family_combo = key_item.widget()
                family_name = font_family_combo.currentText()
                lang_id = int(font_family_combo.id)
                if lang_id == 0: #new
                    name_item = self.languageLayout.itemAtPosition(row, NAME_COL)
                    if name_item:
                        name_edit = name_item.widget()
                        lang_id = name_edit.text()
                    else:
                        lang_id = None
                elif lang_id < 0:
                    lang_id = None
                if lang_id:
                    kdict[lang_id] = family_name
        return kdict
                    
    def getKeyboardDict(self):
        kdict = {}
        rows = range(1, self.languageLayout.rowCount())
        for row in rows:
            key_item = self.languageLayout.itemAtPosition(row, NAME_COL)
            value_item = self.languageLayout.itemAtPosition(row, KEYBOARD_COL)
            if key_item:
                name_edit = key_item.widget()
                sample_edit = value_item.widget()
                lang_id = int(name_edit.id)
                if lang_id == 0: #new
                    lang_id = name_edit.text()
                elif lang_id < 0:
                    lang_id = None
                if lang_id and hasattr(sample_edit, 'keyboard'):
                    kdict[lang_id] = sample_edit.keyboard
        return kdict
    
    def __refresh_hack(self):
        old = self.size()
        new = self.size() + QSize(1, 1)
        self.resize(new)
        self.resize(old)
    
    ##!!@pyqtSlot(str)    
    def onSetKeyboard(self, sample_text):       
        """use the entry of sample text to set keyboard layout for language"""
        self.__refresh_hack()
        if sample_text:
            widget = self.sender()
            lang_id = self.sender().id
            if sys.platform.startswith('linux'):
                sample_text = sample_text.rstrip(']')
                lang, name = sample_text.split('[')
                keyboard = qApp.instance().getKeyboardByName(lang, name)
                keyboard = '{}[{}]'.format(lang, keyboard)
            else:
                keyboard = qApp.instance().getKeyboard()
                keyboard_name = qApp.instance().getKeyboardName(keyboard)
            if sys.platform.startswith('darwin'):
                keyboard_name = keyboard_name.split('.')[-1]
            widget.keyboard = keyboard
            item_pos = self.languageLayout.getItemPosition(self.languageLayout.indexOf(widget))
            row = item_pos[0]
            if not sys.platform.startswith('linux'):
                keyboard_lbl = self.languageLayout.itemAtPosition(row, KEYBOARD_LBL_COL).widget()
                keyboard_lbl.setText(keyboard_name)
            if widget.keyboard != self.orig_keyboard_dict.get(lang_id):
                style_str = """color: red"""
            else:
                style_str = """color: #585858"""
            if not sys.platform.startswith('linux'):
                keyboard_lbl.setStyleSheet(style_str)
            else:
                style_str = 'QComboBox{' + style_str + '}'
                keyboard_combo = self.languageLayout.itemAtPosition(row, KEYBOARD_COL).widget()
                keyboard_combo.setStyleSheet(style_str)
            ##NOTE: if text is cleared, return to original keyboard
            self.onReadyToSave() 
                    
    def onAddLanguage(self, lang=None):   
        layout = self.languageLayout    
        row = layout.rowCount() 
        _id = 0
        _name = ''
        if lang:
            if hasattr(lang, 'id'):
                _id = lang.id
                _name = lang.name
            else:
                _id = lang
                _name = qApp.instance().pm.project.getWrittenLanguageName(_id) #lang[1]                  
        
        if not self.new:
            # COLUMN 0
            search_btn = QRadioButton()
            search_btn.setCursor(QCursor(Qt.PointingHandCursor))
            search_btn.clicked.connect(self.onSearchLangChange)
            search_btn.setStyleSheet("""QRadioButton:indicator:checked:enabled{image: url(':/search_small.png')}
                                        QRadioButton:indicator:checked:disabled{image: url(':/search_disabled.png')}""")
            search_btn.setToolTip(qApp.instance().translate('LanguagesWidget', "Choose language for gloss list"))
            search_btn.setMinimumSize(20, 20)
            search_btn.id = _id
            if _id not in qApp.instance().pm.selected_lang_ids and _id != 0:
                search_btn.setChecked(False) #not likely
                search_btn.setHidden(True)
            else:
                search_btn.setHidden(False)
                if _id == self.search_lang_id: # or row == 1: #self.getSearchLangId():
                    search_btn.setChecked(True)                
            layout.addWidget(search_btn, row, SEARCH_COL)
            
            # COLUMN 1
            showhide_box = QCheckBox()
            showhide_box.setCursor(QCursor(Qt.PointingHandCursor))
            showhide_box.clicked.connect(self.onShowHideClicked)
            showhide_box.setToolTip(qApp.instance().translate('LanguagesWidget', "Show or hide language"))
            showhide_box.setMinimumSize(20, 20)
            showhide_box.id = _id
            showhide_box.setStyleSheet("""QCheckBox:indicator:checked:enabled{image: url(':/show.png')} 
                                          QCheckBox:indicator:unchecked:enabled{image: url(':/hide.png')}
                                          QCheckBox:indicator:checked:disabled{image: url(':/show_disabled.png')} 
                                          QCheckBox:indicator:unchecked:disabled{image: url(':/hide_disabled.png')}""")
            if _id in qApp.instance().pm.selected_lang_ids or _id == 0:
                showhide_box.setCheckState(Qt.Checked)
                showhide_box.orig_check_state = Qt.Checked
                self.__selected_lang_ids.append(_id)
            else:
                showhide_box.setCheckState(Qt.Unchecked)
                showhide_box.orig_check_state = Qt.Unchecked
            layout.addWidget(showhide_box, row, SHOWHIDE_COL) 
        # COLUMN 2    
        name_edit = QLineEdit()      
        name_edit.id = _id
        name_edit.setText(_name)
        name_edit.orig_text = _name
        name_edit.textEdited.connect(self.onNameEdited)
        if (self.edit and qApp.instance().pm.ableToEdit()) or self.new:
            name_edit.setReadOnly(False)
            name_edit.setFrame(QFrame.StyledPanel)
        else:
            name_edit.setReadOnly(True)
            name_edit.setFrame(QFrame.NoFrame)
            color = self.palette().window().color().name()
            style_str = 'QLineEdit{background: bcolor;}'
            style_str = style_str.replace('bcolor', color)
            name_edit.setStyleSheet(style_str)
        layout.addWidget(name_edit, row, NAME_COL)             
                  
        if not self.new: 
            # COLUMN 3   
            font_spinner = QSpinBox()
            font_spinner.setCursor(QCursor(Qt.PointingHandCursor))
            font_spinner.id = _id
            font_spinner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            font_spinner.setMaximumWidth(125)
            font_spinner.setToolTip(qApp.instance().translate('LanguagesWidget', "Change font size"))
            font_spinner.setMinimum(6)
            font_spinner.setMaximum(32)
            font_size = self.getFontSize(_name)
            if _id != 0:
                self.orig_font_dict[_id] = font_size
            font_spinner.setValue(font_size)
            font_spinner.valueChanged.connect(self.onFontSizeChanged)
            layout.addWidget(font_spinner, row, FONT_SIZE_COL)
        # COLUMN 4
        font_family_combo = QFontComboBox()
        font_family_combo.setMaximumWidth(250)
        font_family_combo.id = _id
        font_family = qApp.instance().font().family()
        if isinstance(_id, int) and _id > 0:
            font_family = self.getFontFamily(_name)
        font_family_combo.setCurrentText(font_family)
        font_family_combo.setStyleSheet('QComboBox{font-family:' + font_family + ';}')
        self.orig_font_family_dict[_id] = font_family
        font_family_combo.currentFontChanged.connect(self.onCurrentFontChanged)
        layout.addWidget(font_family_combo, row, FONT_FAMILY_COL) 
        #if self.edit and qApp.instance().pm.ableToEdit():    
        # COLUMN 5
        sample_edit = QLineEdit()
        if not sys.platform.startswith('linux'):
            tip1 = qApp.instance().translate('LanguagesWidget', "Change to the keyboard layout to be used with this language, and then type a few characters into this field.")
            tip2 = qApp.instance().translate('LanguagesWidget', "When you need to type with this language in SooSL, the keyboard will automatically change for you.") 
            sample_edit.setToolTip("<p>{}<br><br>{}".format(tip1, tip2))
            sample_edit.setReadOnly(False)
            sample_edit.setMinimumWidth(32)
            sample_edit.setMaximumWidth(80)
            sample_edit.id = _id
            sample_edit.textEdited.connect(self.onSetKeyboard)
        elif sys.platform.startswith('linux'):
            sample_edit = KeyboardComboBox()
            sample_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tip1 = qApp.instance().translate('LanguagesWidget', "Click to set the keyboard layout to be used with this language.")
            tip2 = qApp.instance().translate('LanguagesWidget', "When you need to type with this language in SooSL, the keyboard will automatically change for you.") 
            sample_edit.setToolTip("<p>{}<br><br>{}".format(tip1, tip2))
            sample_edit.id = _id
            keyboard = None
            if isinstance(_id, int) and _id > 0:
                keyboard = qApp.instance().getKeyboard(_id)
            else: #new language
                keyboard = qApp.instance().getKeyboard()
            keyboard = keyboard.rstrip(']')
            try:
                lang, keyboard = keyboard.split('[')
            except:
                sample_edit.setCurrentText(None)
            else:
                keyboard_name = qApp.instance().getKeyboardName(keyboard)
                text = '{}[{}]'.format(lang, keyboard_name)
                sample_edit.setCurrentText(text)
            sample_edit.current_keyboard_changed.connect(self.onSetKeyboard)
        if font_family_combo and not sys.platform.startswith('linux'):
            font_family_combo.currentFontChanged.connect(sample_edit.setFont)
        if isinstance(_id, int) and _id > 0:
            keyboard = qApp.instance().getKeyboard(_id)
            sample_edit.keyboard = keyboard
            self.orig_keyboard_dict[_id] = keyboard
        layout.addWidget(sample_edit, row, KEYBOARD_COL)
        
        # COLUMN 6
        if not sys.platform.startswith('linux'):
            keyboard_lbl = QLabel()
            keyboard_lbl.setToolTip("<p>{}</p>".format(qApp.instance().translate('LanguagesWidget', "This is the keyboard layout currently set for this language.")))
            keyboard_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            keyboard_lbl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
            keyboard_lbl.setContentsMargins(3, 0, 0, 0)
            keyboard_lbl.setProperty('selected', 'false')
            keyboard_lbl.setStyleSheet("""QLabel[selected='false']{color: #585858} QLabel[selected='true']{color: %s}""" % self.selected_text_color.name())
            
            if isinstance(_id, int) and _id > 0:
                keyboard = qApp.instance().getKeyboard(_id)
                keyboard_name = qApp.instance().getKeyboardName(keyboard)
                if sys.platform.startswith('darwin'):
                    keyboard_name = keyboard_name.split('.')[-1]
                keyboard_lbl.setText(keyboard_name)
                
            layout.addWidget(keyboard_lbl, row, KEYBOARD_LBL_COL) 
        if not self.new:
            # COLUMN 7
            movedown_btn = QPushButton()
            movedown_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            movedown_btn.setCursor(QCursor(Qt.PointingHandCursor))
            movedown_btn.setFlat(True)
            movedown_btn.setStyleSheet("""QPushButton:enabled{background-image: url(':/down.png');
                        background-repeat: no-repeat;
                        background-position: center right;
                        border: 0px}
                        QPushButton:disabled{background-image: url(':/down_disabled.png');
                        background-repeat: no-repeat;
                        background-position: center right;
                        border: 0px}
                        """)
            movedown_btn.setToolTip(qApp.instance().translate('LanguagesWidget', 'Move down'))
            movedown_btn.hide()
            movedown_btn.clicked.connect(self.moveRow)            
            layout.addWidget(movedown_btn, row, MOVEDOWN_COL)
        
            # COLUMN 8
            moveup_btn = QPushButton()
            moveup_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            moveup_btn.setCursor(QCursor(Qt.PointingHandCursor)) 
            moveup_btn.setFlat(True)
            moveup_btn.setStyleSheet("""QPushButton:enabled{background-image: url(':/up.png');
                        background-repeat: no-repeat;
                        background-position: center left;
                        border: 0px}
                        QPushButton:disabled{background-image: url(':/up_disabled.png');
                        background-repeat: no-repeat;
                        background-position: center left;
                        border: 0px}
                        """)
            moveup_btn.setToolTip(qApp.instance().translate('LanguagesWidget', 'Move up'))
            moveup_btn.clicked.connect(self.moveRow)
            # moveup_btn.hide()
            # movedown_btn.hide()
            layout.addWidget(moveup_btn, row, MOVEUP_COL)

            # Count columns
            sign_count, sense_count, gloss_count = 0, 0, 0
            if not self.new: # new dictionary, no counts yet
                try:
                    sign_count, sense_count, gloss_count = qApp.instance().pm.project.countSignsSensesGlossesForLanguage(_id)
                except:
                    pass           
            # COLUMN 9, 10, 11
            for t in [
                (str(sign_count), SIGN_COUNT_COL),
                (str(sense_count), SENSE_COUNT_COL),
                (str(gloss_count), GLOSS_COUNT_COL)
                ]:
                    txt, col = t
                    count_lbl = QLabel()
                    lbl = layout.itemAtPosition(0, col).widget()
                    fm = self.fontMetrics()
                    w = fm.width(lbl.text())
                    count_lbl.setMinimumWidth(w)
                    count_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    count_lbl.setAlignment(Qt.AlignHCenter)
                    count_lbl.setContentsMargins(3, 0, 0, 0)
                    count_lbl.setProperty('selected', 'false')
                    count_lbl.setStyleSheet("""QLabel[selected='false']{color: #585858} QLabel[selected='true']{color: white}""")
                    count_lbl.setText(txt)
                    layout.addWidget(count_lbl, row, col)
                  
            #if self.edit and qApp.instance().pm.ableToEdit():    
            # COLUMN 12
            remove_btn = QPushButton() 
            if not self.edit:
                remove_btn.hide()
            remove_btn.setCheckable(True)
            remove_btn.toggled.connect(self.onRemoveLanguage)
            remove_btn.id = _id       
            remove_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            remove_btn.setCursor(QCursor(Qt.PointingHandCursor))
            remove_btn.setFlat(True)
            remove_btn.setFocusPolicy(Qt.NoFocus)
            remove_btn.setToolTip(qApp.instance().translate('LanguagesWidget', "Delete this written language"))
            icon = QIcon(':/trash20.png')
            icon.addFile(':/trash24_red.png', state=QIcon.On)
            remove_btn.setIcon(icon)
            remove_btn.setIconSize(QSize(16, 16))
            remove_btn.setMinimumSize(16, 16)
            layout.addWidget(remove_btn, row, REMOVE_COL) 
                
            if row == 1:
                moveup_btn.hide()
                movedown_btn.hide()
                self.setLabelsSelected(self.selected_row)
            else:
                item = layout.itemAtPosition(row - 1, MOVEDOWN_COL)
                if item:
                    last_movedown_btn = item.widget()
                    last_movedown_btn.show()
                    moveup_btn.show()
        
        if not lang:
            if hasattr(self, 'addLanguageBtn'):
                self.addLanguageBtn.setEnabled(False)
            name_edit.setFocus()
        else:
            if hasattr(self, 'addLanguageBtn'):
                self.addLanguageBtn.setEnabled(True)
                self.addLanguageBtn.setFocus() 
                  
        qApp.processEvents()        
        if self.edit and not _name:
            self.enableRow(row, False)
        
    def enableRow(self, row, _bool=True):
        cols = [SEARCH_COL, SHOWHIDE_COL, FONT_SIZE_COL, FONT_FAMILY_COL, KEYBOARD_COL, 
                MOVEDOWN_COL, MOVEUP_COL, SIGN_COUNT_COL, SENSE_COUNT_COL, GLOSS_COUNT_COL, REMOVE_COL]
        if not sys.platform.startswith('linux'):
            cols.append(KEYBOARD_LBL_COL)
        for col in cols:
            item = self.languageLayout.itemAtPosition(row, col)
            if item:
                widget = item.widget()
                if (widget.isEnabled() and _bool is False) or \
                    (_bool is True and not widget.isEnabled()):
                    if row != 1 and col == REMOVE_COL and widget.id == 0: #keep remove button enabled for a new row
                        _bool = True
                    widget.setEnabled(_bool)
                    self.resetTabOrder()
    
    ##!!@pyqtSlot()    
    def onRemoveLanguage(self):
        btn = self.sender()
        lang_id = btn.id
        _bool = False
        if btn.isChecked():
            _bool = True
        if lang_id == 0 and _bool: #newly added language
            self.removeNewLang(btn)
        elif lang_id > 0:
            self.markLangForDelete(btn, _bool)
        self.onReadyToSave() 
            
    def removeNewLang(self, widget):
        if not self.new and self.getLangName(widget) == self.getSearchLangId(): #id is name in case of new language
            self.blockSignals(True)
            widget.setChecked(False)
            self.blockSignals(False)
            QMessageBox.warning(self, 
            qApp.instance().translate('LanguagesWidget', "Cannot delete language"),
            "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'Select another search language first')))
            return
        idx = self.languageLayout.indexOf(widget) #index of last column
        self.removeRow(idx)

    def clear(self):
        rowcount = self.languageLayout.rowCount()
        colcount = self.languageLayout.columnCount()
        for row in range(1, rowcount):
            for col in range(colcount):
                item = self.languageLayout.itemAtPosition(row, col)
                if item:
                    idx = self.languageLayout.indexOf(item)
                    _item = self.languageLayout.takeAt(idx)
                    widget = _item.widget()
                    if widget:
                        widget.blockSignals(True)
                        widget.close()
                    del _item
        
    def removeRow(self, idx):        
        row2remove = self.languageLayout.getItemPosition(idx)[0]
        row_count = self.languageLayout.rowCount()
        widgets = []
        row = 0
        col = 0
        while row < row_count:
            item = self.languageLayout.itemAtPosition(row, col)
            widget = None
            if item:
                widget = item.widget()
                self.languageLayout.removeWidget(widget)
            if row != row2remove:     
                widgets.append(widget)
            elif widget:
                widget.close()
            col += 1
            if col == COL_COUNT:
                col = 0
                row += 1
        self.layout().removeItem(self.languageLayout)        
        del self.languageLayout
        
        self.languageLayout = QGridLayout()
        self.languageLayout.setContentsMargins(2, 2, 2, 2)
        self.layout().insertLayout(1, self.languageLayout)    
        
        row = 0
        col = 0
        for widget in widgets:
            if widget:
                if row == 0 and col == KEYBOARD_COL:
                    self.languageLayout.addWidget(widget, row, col, 1, 2)
                else:
                    self.languageLayout.addWidget(widget, row, col)
                if row == 1 and col == MOVEUP_COL:
                    widget.hide()
                elif row == 1 and col == MOVEDOWN_COL:
                    widget.show()
                elif row == row_count - 2 and col == MOVEUP_COL:
                    widget.show()
                elif row == row_count - 2 and col == MOVEDOWN_COL:
                    widget.hide()            
            
            col += 1
            if col == COL_COUNT:
                row += 1
                col = 0
            
        self.addLanguageBtn.setEnabled(True)
        self.adjustSize()
    
    def markLangForDelete(self, widget, _bool):
        def uncheck():
            self.blockSignals(True)
            widget.setChecked(False)
            self.blockSignals(False)
        if _bool:
            undeleted = [lang for lang in self.getLanguages() if isinstance(lang[0], int) \
                         and lang[0] > 0 or isinstance(lang[0], str)]            
            selected_ids = self.getSelectedLangIds()
            warning_title = qApp.instance().translate('LanguagesWidget', "Cannot delete language")
            if len(undeleted) <=1: #cannot delete all languages
                uncheck()
                QMessageBox.warning(self, 
                warning_title,
                "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'At least one language is required.')))
                return
            elif len(selected_ids) == 1 and widget.id == selected_ids[0]:
                uncheck()
                #NOTE: animate show/hide buttons???
                QMessageBox.warning(self, 
                warning_title,
                "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'At least one language must be visible.')))
                return
            elif widget.id == self.getSearchLangId():
                uncheck()
                #NOTE: animated search buttons???
                QMessageBox.warning(self, 
                warning_title,
                "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'Select another search language first.')))
                return
            #count how many signs use this language for glosses
            count = self.getLangSignCount(widget) 
            if count:
                name = self.getLangName(widget)
                msgBox = QMessageBox(self)
                self.close_signal.connect(msgBox.close) # in event of inactivity timeout
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setTextFormat(Qt.RichText)
                msgBox.setWindowTitle(qApp.instance().translate('LanguagesWidget', "Remove Language"))
                msgBox.setText("<b>{} <span style='color:blue;'>{}</span><br>{} <span style='color:blue;'>{}</span></b>".format(qApp.instance().translate('LanguagesWidget', 'Language name:'), \
                    name, qApp.instance().translate('LanguagesWidget', 'Number of signs affected:'), count))
                msgBox.setInformativeText(qApp.instance().translate('LanguagesWidget', "Remove this language?"))
                msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                yes_btn, no_btn = msgBox.buttons()
                yes_btn.setIcon(QIcon(":/thumb_up.png"))
                no_btn.setIcon(QIcon(":/thumb_down.png"))
                msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('LanguagesWidget', "Yes"))
                msgBox.button(QMessageBox.No).setText(qApp.instance().translate('LanguagesWidget', "No"))
                msgBox.setDefaultButton(QMessageBox.No)
                if msgBox.exec_() == QMessageBox.No: #don't remove this language
                    widget.setChecked(False)
                    return
            
        idx = self.languageLayout.indexOf(widget)
        row = self.languageLayout.getItemPosition(idx)[0]
        _id = abs(widget.id)
        
        if _bool and _id in self.__selected_lang_ids:
            self.__selected_lang_ids.remove(_id)
        else:
            checkbox = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL).widget()
            if checkbox.isChecked():
                self.__selected_lang_ids.append(_id)
        if _bool:
            _id = -_id
        for col in [SEARCH_COL, SHOWHIDE_COL, NAME_COL]:
            self.languageLayout.itemAtPosition(row, col).widget().id = _id
        self.setDeleteStyles(row, _bool)
        hide_btn = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL).widget()
        hide_btn.setChecked(not _bool)
        qApp.instance().pm.setSelectedLangIds(self.getSelectedLangIds())
        
    def setDeleteStyles(self, row, _bool):
        for col in [SEARCH_COL,
                    SHOWHIDE_COL,
                    FONT_SIZE_COL,
                    FONT_FAMILY_COL
                    #MOVEDOWN_COL,
                    #MOVEUP_COL
                    ]:
            item = self.languageLayout.itemAtPosition(row, col)
            if item:
                item.widget().setDisabled(_bool)
                
        lang_name_widget = self.languageLayout.itemAtPosition(row, NAME_COL).widget()
        keyboard_name_widget = self.languageLayout.itemAtPosition(row, KEYBOARD_COL).widget()
        sign_count_widget = self.languageLayout.itemAtPosition(row, SIGN_COUNT_COL).widget()
        sense_count_widget = self.languageLayout.itemAtPosition(row, SENSE_COUNT_COL).widget()
        gloss_count_widget = self.languageLayout.itemAtPosition(row, GLOSS_COUNT_COL).widget()
        col = KEYBOARD_LBL_COL
        if sys.platform.startswith('linux'):
            col = KEYBOARD_COL
        keyboard_widget = self.languageLayout.itemAtPosition(row, col).widget()
        
        for widget in [lang_name_widget, keyboard_name_widget, keyboard_widget]:
            if _bool:
                widget.setStyleSheet("color:red; text-decoration:line-through;")
                if not sys.platform.startswith('linux'):
                    try:
                        widget.setReadOnly(True)
                    except:
                        widget.setDisabled(True)
                else:
                    widget.setDisabled(True)
            else:
                widget.setStyleSheet(None)
                if not sys.platform.startswith('linux'):
                    try:
                        widget.setReadOnly(False)
                    except:
                        widget.setDisabled(False)
                else:
                    widget.setDisabled(False)
                
        for widget in [sign_count_widget, sense_count_widget, gloss_count_widget]:
            if _bool:
                widget.setStyleSheet("color:red; text-decoration:line-through;")
            else:
                widget.setStyleSheet("color:#585858;")
    
    ###!!@pyqtSlot(QLineEdit, QLineEdit) 
    ##NOTE: adding decorator prevents new dictionary being created; I think because first widget can be none, howto add NoneType in decorator?
    def onFocusChanged(self, widget, widget2):
        if widget and widget2:
            self.setRowSelected(widget2)
            if widget2 and hasattr(widget2, 'id'):
                idx = self.languageLayout.indexOf(widget2)
                item_pos = self.languageLayout.getItemPosition(idx)
                col = item_pos[1]
                if col == KEYBOARD_COL:
                    qApp.instance().changeKeyboard(widget2.id)
                else:
                    qApp.instance().changeKeyboard()
        
    def setRowSelected(self, widget_or_int):
        row = 1
        if isinstance(widget_or_int, int):
            row = widget_or_int
        else:
            idx = self.languageLayout.indexOf(widget_or_int)
            if not idx or idx < 0:
                return
            item_pos = self.languageLayout.getItemPosition(idx)
            if item_pos:
                row = item_pos[0]
        if 0 < row < self.languageLayout.rowCount() and row != self.selected_row:
            self.selected_row = row
            self.setLabelsSelected(row)
            QTimer.singleShot(0, self.repaint)
            
    def setLabelsSelected(self, selected_row):
        """set any labels in row with text 'selected'"""
        for row in range(1, self.languageLayout.rowCount()):
            _bool = 'false'
            if row == selected_row:
                _bool = 'true'
            keyboard = self.languageLayout.itemAtPosition(row, KEYBOARD_LBL_COL)
            if keyboard:
                keyboard_lbl = keyboard.widget()
                keyboard_lbl.setProperty('selected', _bool)
                keyboard_lbl.style().unpolish(keyboard_lbl)
                keyboard_lbl.style().polish(keyboard_lbl)
            for col in [SIGN_COUNT_COL, SENSE_COUNT_COL, GLOSS_COUNT_COL]:
                item = self.languageLayout.itemAtPosition(row, col)
                if item:
                    count_lbl = item.widget()
                    count_lbl.setProperty('selected', _bool)
                    count_lbl.style().unpolish(count_lbl)
                    count_lbl.style().polish(count_lbl)
            
    def setInitialFocus(self):
        item = self.languageLayout.itemAtPosition(1, NAME_COL)
        if item:
            item.widget().setFocus()
            
    def __getSelectedRect(self):
        item = self.languageLayout.itemAtPosition(self.selected_row, NAME_COL)
        if item:
            widget = item.widget() # widest widget from row
            return QRect(0, widget.pos().y()-2, self.width(), widget.height()+4)
        return None
    
    def __getHeaderRect(self):
        item = self.languageLayout.itemAtPosition(0, NAME_COL)
        if item:
            widget = item.widget() # widest widget from row
            if widget.isVisible():
                return QRect(0, widget.pos().y()-4, self.width(), widget.height()+8)
        return None
        
    def paintEvent(self, evt):
        p = QPainter(self)
        rect = self.__getSelectedRect()
        if rect:
            p.fillRect(rect, self.selected_color)
        header_rect = self.__getHeaderRect()
        if header_rect:
            p.fillRect(header_rect, self.palette().midlight().color())
    
    ##!!@pyqtSlot()    
    def moveRow(self):
        if self.languageLayout.rowCount() == 2:
            return # nowhere to move just one language row!
        row_id = self.getLangId(self.sender())
        idx = self.languageLayout.indexOf(self.sender())
        row, column = self.languageLayout.getItemPosition(idx)[:2]
        widget = None
        widget_new = None
        
        if column == MOVEDOWN_COL:
            new_row = row + 1
        elif column == MOVEUP_COL:
            new_row = row - 1
               
        if not self.new:
            columns = [SEARCH_COL, SHOWHIDE_COL, NAME_COL, FONT_SIZE_COL, FONT_FAMILY_COL, KEYBOARD_COL, 
                SIGN_COUNT_COL, SENSE_COUNT_COL, GLOSS_COUNT_COL, REMOVE_COL]
            if not qApp.instance().pm.ableToEdit():
                columns = [SEARCH_COL, SHOWHIDE_COL, NAME_COL, FONT_SIZE_COL, FONT_FAMILY_COL, 
                    SIGN_COUNT_COL, SENSE_COUNT_COL, GLOSS_COUNT_COL]
        else:
            columns = [NAME_COL, FONT_FAMILY_COL, KEYBOARD_COL, SIGN_COUNT_COL, SENSE_COUNT_COL, GLOSS_COUNT_COL, REMOVE_COL]
            
        if not sys.platform.startswith('linux') and qApp.instance().pm.ableToEdit():
            columns.append(KEYBOARD_LBL_COL)
        
        for col in columns:
            item = self.languageLayout.itemAtPosition(row, col)
            if item:
                widget = item.widget()
                self.languageLayout.removeWidget(widget)
            item = self.languageLayout.itemAtPosition(new_row, col)
            if item:
                widget_new = item.widget()
                self.languageLayout.removeWidget(widget_new)
            
            if widget:                
                self.languageLayout.addWidget(widget, new_row, col)
            if widget_new:
                self.languageLayout.addWidget(widget_new, row, col)
        
        self.resetTabOrder()
        if row_id > 0:
            qApp.instance().pm.lang_order_change.emit(self.getLangOrder())
        self.onReadyToSave()
        
        self.setRowSelected(new_row)
        btn = self.languageLayout.itemAtPosition(new_row, NAME_COL).widget()
        btn.setFocus()      
    
    def getFontSize(self, lang_name):
        return qApp.instance().pm.getFontSize(lang_name)
    
    def getFontSizes(self):
        return self.getFontDict()
    
    def getFontFamily(self, lang_name):
        family = qApp.instance().pm.getFontFamily(lang_name)
        if family:
            return family
        return qApp.instance().font().family()
    
    def getFontFamilies(self):
        return self.getFontFamilyDict()
    
    def getKeyboardLayouts(self):
        return self.getKeyboardDict()
    
    def getOrigKeyboardLayouts(self):
        return self.orig_keyboard_dict        
    
    def getLangId(self, widget):
        idx = self.languageLayout.indexOf(widget)
        row = self.languageLayout.getItemPosition(idx)[0]
        return self.languageLayout.itemAtPosition(row, NAME_COL).widget().id
    
    def getLangName(self, widget):
        idx = self.languageLayout.indexOf(widget)
        row = self.languageLayout.getItemPosition(idx)[0]
        return self.languageLayout.itemAtPosition(row, NAME_COL).widget().text()
    
    def getLangSignCount(self, widget):
        idx = self.languageLayout.indexOf(widget)
        row = self.languageLayout.getItemPosition(idx)[0]
        # only want to return the sign count if the gloss count is 0
        if int(self.languageLayout.itemAtPosition(row, GLOSS_COUNT_COL).widget().text()):
            return int(self.languageLayout.itemAtPosition(row, SIGN_COUNT_COL).widget().text())
        return 0
        
    def getOrigLangName(self, widget):
        idx = self.languageLayout.indexOf(widget)
        row = self.languageLayout.getItemPosition(idx)[0]
        return self.languageLayout.itemAtPosition(row, NAME_COL).widget().orig_text
    
    def getOrigSelectedLangIds(self):
        return self.__orig_selected_lang_ids
    
    def getOrigFontSizes(self):
        return self.orig_font_dict
    
    def getOrigFontFamilies(self):
        return self.orig_font_family_dict
    
    def getOrigSearchLangId(self):
        return self.search_lang_id
    
    ##!!@pyqtSlot()
    def onSearchLangChange(self):
        if self.languageLayout.rowCount() == 1:
            radio = self.sender()
            radio.blockSignals(True)
            radio.setChecked(True)
            radio.blockSignals(False)
        else: 
            _id = self.sender().id
            qApp.instance().pm.setSearchLangId(_id)
            self.onReadyToSave()
            
    def __hideSearchBtn(self, widget, _bool):
        idx = self.languageLayout.indexOf(self.sender())
        row = self.languageLayout.getItemPosition(idx)[0]
        item = self.languageLayout.itemAtPosition(row, SEARCH_COL)
        if item:
            item.widget().setHidden(_bool)
        
    def __selectedCount(self):
        count = 0
        for row in range(1, self.languageLayout.rowCount()):
            item = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL)
            if item and item.widget().isChecked() and \
               item.widget().id >= 0 :
                count += 1
        return count 
     
    ##!!@pyqtSlot()       
    def onShowHideClicked(self):
        checkbox = self.sender()
        lang_id = checkbox.id 
        warning_title = qApp.instance().translate('LanguagesWidget', "Cannot hide language")       
        if not checkbox.isChecked() and self.__selectedCount() == 0:
            self.blockSignals(True)
            checkbox.setChecked(True)
            self.blockSignals(False)
            QMessageBox.warning(self, 
            warning_title,
            "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'At least one language must be displayed.')))                 
            return
        elif lang_id == self.getSearchLangId() or \
            self.getLangName(checkbox) == self.getSearchLangId():
            self.blockSignals(True)
            checkbox.setChecked(True)
            self.blockSignals(False)
            #NOTE: animated search buttons???
            QMessageBox.warning(self, 
            warning_title,
            "<STRONG>{}</STRONG>".format(qApp.instance().translate('LanguagesWidget', 'Select another search language first.')))
            return
        
        if checkbox.isChecked():
            self.__selected_lang_ids.append(lang_id)
            self.__hideSearchBtn(checkbox, False)  
        elif not checkbox.isChecked() and lang_id in self.__selected_lang_ids:
            self.__selected_lang_ids.remove(lang_id)
            self.__hideSearchBtn(checkbox, True)
        qApp.instance().pm.setSelectedLangIds(self.getSelectedLangIds())
        self.onReadyToSave()
        self.resetTabOrder()
     
    ##!!@pyqtSlot(str)   
    def onNameEdited(self, text):        
        editor = self.sender()
        if text:
            if text != editor.orig_text:
                editor.setStyleSheet("""color:red""")
            else:
                editor.setStyleSheet("""color:{}""".format(QPalette.Text))
            self.setRowSelected(editor)            
            idx = self.languageLayout.indexOf(editor)
            row = self.languageLayout.getItemPosition(idx)[0]
            self.enableRow(row)
        else:
            idx = self.languageLayout.indexOf(editor)
            row = self.languageLayout.getItemPosition(idx)[0]
            self.enableRow(row, False)
        
        self.onReadyToSave()
    
    ##!!@pyqtSlot(int)    
    def onFontSizeChanged(self, _int):
        spinner = self.sender()
        lang_id = spinner.id
        if lang_id == 0:
            lang_id = self.getOrigLangName(spinner)
        if _int != self.orig_font_dict.get(lang_id):
            spinner.setStyleSheet("""color:red""")
        else:
            spinner.setStyleSheet("""color:{}""".format(QPalette.Text)) 
        self.onReadyToSave()
        qApp.instance().pm.font_size_change.emit(lang_id, _int)
        
    def onCurrentFontChanged(self, _font):
        self.__refresh_hack()
        #for now, only interested in font family change
        combo = self.sender()
        lang_id = combo.id
        family = _font.family()
        if family != self.orig_font_family_dict.get(lang_id):
            combo.setStyleSheet('QComboBox{color:red; font-family:' + family + ';}')
        else:
            combo.setStyleSheet('QComboBox{' + 'color:{}; font-family:'.format(QPalette.Text) + family + ';}')  
        self.onReadyToSave()
        qApp.instance().pm.font_family_change.emit(lang_id, family)
            
    def onReadyToSave(self):
        row = 1
        while self.languageLayout.itemAtPosition(row, NAME_COL):
            name = self.languageLayout.itemAtPosition(row, NAME_COL).widget().text()
            row += 1
            if not name:
                if hasattr(self, 'addLanguageBtn'):
                    self.addLanguageBtn.setEnabled(False)
                self.saveReady.emit(False) #override .isDirty if an empty text field is found
                return
        if hasattr(self, 'addLanguageBtn'):
            self.addLanguageBtn.setEnabled(True)
        try:
            self.saveReady.emit(self.isDirty())
        except:
            print('onReadyToSave error')
            self.saveReady.emit(False) #occurring when choosing current language, so should be false
        
    #@property
    def isDirty(self):
        settings = qApp.instance().getSettings()
        if self.useAutoKeyboard() != int(settings.value('autoKeyboardSwitchState', Qt.Checked)):
            return True
        
        for row in range(1, self.languageLayout.rowCount()):
            widget = self.languageLayout.itemAtPosition(row, NAME_COL).widget()
            if widget.id < 0: #marked for deletion
                return True
            name = widget.text()
            old_name = widget.orig_text
            if not self.new:
                check_state = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL).widget().checkState()
                old_check_state = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL).widget().orig_check_state                        
            
            # at least one language required
            if not name:
                return False #
            elif name and name != old_name:
                return True
            elif not self.new and check_state != old_check_state:
                return True
            
        if not self.new:
            if self.getSearchLangId() != self.search_lang_id:
                return True
            elif self.getLangOrder() != qApp.instance().pm.getLangOrder():
                return True
            
            font_dict = self.getFontDict()
            for key in font_dict:
                new_font = font_dict.get(key)
                old_font = self.orig_font_dict.get(key)
                if new_font != old_font:
                    return True
                
            font_family_dict = self.getFontFamilyDict()
            for key in font_family_dict:
                new_family = font_family_dict.get(key)
                old_family = self.orig_font_family_dict.get(key)
                if new_family != old_family:
                    return True                
                
            if qApp.instance().pm.ableToEdit():
                keyboard_dict = self.getKeyboardDict()
                for key in keyboard_dict:
                    new_keyboard = keyboard_dict.get(key)
                    old_keyboard = self.orig_keyboard_dict.get(key)
                    #print('kb', old_keyboard, new_keyboard)
                    if old_keyboard != new_keyboard:
                        return True
        return False
    
    @property
    def gloss_languages(self):
        return self.getLanguages()
    
    def getLanguages(self):
        langs = []
        rows = range(1, self.languageLayout.rowCount())
        for row in rows:
            item = self.languageLayout.itemAtPosition(row, NAME_COL)
            if item:
                widget = item.widget()
                name = widget.text()
                order = row
                if name:
                    _id = widget.id 
                    langs.append([_id, name, order]) 
        return langs
    
    def getSearchLangId(self):
        first_id = 1
        if not self.new:
            radio = None
            for row in range(1, self.languageLayout.rowCount()):
                item = self.languageLayout.itemAtPosition(row, SEARCH_COL)
                if item:
                    radio = item.widget()
                    _id = radio.id
                    
                    # set first available id; this will be returned if nothing else found 
                    # id < 0 is marked for deletion and doesn't count as available
                    if not first_id and _id > 0:
                        first_id = _id
                    elif not first_id and _id == 0:
                        first_id = self.languageLayout.itemAtPosition(row, NAME_COL).widget().text()
                               
                    if radio.isChecked():
                        if _id < 0: #marked for deletion
                            pass
                        elif _id == 0: #new; return name instead
                            return self.languageLayout.itemAtPosition(row, NAME_COL).widget().text()
                        else:
                            return _id                        
        else:
            item = self.languageLayout.itemAtPosition(1, NAME_COL)
            if item:
                return item.widget().text()
        return first_id
                
    def getSelectedLangIds(self): #this way maintains display order
        ids = []
        if not self.new:
            for row in range(1, self.languageLayout.rowCount()):
                checkbox = self.languageLayout.itemAtPosition(row, SHOWHIDE_COL).widget() 
                if checkbox.isChecked():
                    _id = checkbox.id
                    if _id != 0:
                        ids.append(_id)
                    else:
                        item = self.languageLayout.itemAtPosition(row, NAME_COL)
                        if item:
                            ids.append(item.widget().text())                        
        else:
            for row in range(1, self.languageLayout.rowCount()):
                item = self.languageLayout.itemAtPosition(row, NAME_COL)
                if item:
                    ids.append(item.widget().text())
        return ids
    
    def getLangOrder(self):
        ids = []
        for lang in self.getLanguages():
            _id, name = lang[:2]
            try:
                if int(_id) != 0:
                    ids.append(int(_id))
                else:
                    ids.append(name)
            except:
                ids.append(name)
        return ids 
    
    def resetTabOrder(self):
        widgets = []
        columns = [SEARCH_COL, SHOWHIDE_COL, NAME_COL, FONT_SIZE_COL, FONT_FAMILY_COL, KEYBOARD_COL, MOVEDOWN_COL, MOVEUP_COL]
        if not sys.platform.startswith('linux'):
            columns.append(KEYBOARD_LBL_COL)
        for row in range(1, self.languageLayout.rowCount()):
            for col in columns:
                item = self.languageLayout.itemAtPosition(row, col)
                if item and item.widget().isEnabled():
                    widgets.append(item.widget())
        if hasattr(self, 'addLanguageBtn'):
            widgets.append(self.addLanguageBtn)
                 
        count = len(widgets)
        for i in range(count - 1):
            w1 = widgets[i]
            w2 = widgets[i + 1]
            self.setTabOrder(w1, w2) 
                        
class DialectItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(DialectItemDelegate, self).__init__(parent)
        
    def paint(self, painter, option, index):
        painter.save()
        row = index.row()
        col = index.column()
        
        if col in [0, 1]:
            text = index.data()
            if text:
                text = text.strip()
                if self.isMarkedDeleted(row):
                    option.font.setStrikeOut(True)
                    option.palette.setColor(QPalette.Text, Qt.red)
                elif text != index.data(Qt.UserRole):
                    option.palette.setColor(QPalette.Text, Qt.red)
            else:
                text = ''
            if text == '':
                rect = option.rect.adjusted(2, 2, -2, -2)                
                painter.fillRect(rect, QColor("pink"))
                painter.setPen(QColor("blue")) 
                painter.drawRect(rect)
                rect = option.rect.adjusted(10, 10, -10, -10)  
                painter.drawText(rect.bottomLeft(), qApp.instance().translate('DialectItemDelegate', "Required"))
                  
        elif col == 2 and self.isMarkedDeleted(row):
            painter.restore()
            return 
        
        elif col == 2: 
            radio = self.parent().cellWidget(row, col)
            if radio:
                if not self.isFocal(row) and radio.isChecked():
                    radio.setStyleSheet('color:red')
                else:
                    radio.setStyleSheet(None)
                if radio.isChecked():
                    radio.setText(qApp.instance().translate('DialectItemDelegate', 'Focal'))
                    radio.setToolTip(None)
                else:
                    radio.setText('')
                    radio.setToolTip(qApp.instance().translate('DialectItemDelegate', "Make this dialect focal"))
                
        elif col in [3, 4]:
            if self.isMarkedDeleted(row):
                option.font.setStrikeOut(True)
                option.palette.setColor(QPalette.Text, Qt.red)
        
        super(DialectItemDelegate, self).paint(painter, option, index)
        painter.restore() 
        
    def isMarkedDeleted(self, row):
        table = self.parent()
        deleteItem = table.item(row, 5)
        if deleteItem and deleteItem.data(Qt.UserRole) == -1:
            return True
        return False  
    
    def isFocal(self, row):
        table = self.parent()
        if table.property('orig_focal_row') == row:
            return True
        return False
    
class ItemLabel(QLabel):       
    def __init__(self, item, text, parent=None):  
        super(ItemLabel, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 
        self.item = item
        super(ItemLabel, self).setText(text)
        
    def mousePressEvent(self, evt):
        table = self.item.tableWidget()
        table.itemClicked.emit(self.item)
        super(ItemLabel, self).mousePressEvent(evt)
    
class ItemBtn(QPushButton):       
    def __init__(self, item, col, parent=None):  
        super(ItemBtn, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFlat(True)
        self.item = item
        self.col = col
        self.clicked.connect(self.onMouseClicked)
    
    ##!!@pyqtSlot()
    def onMouseClicked(self):
        tree = self.item.treeWidget()
        tree.itemClicked.emit(self.item, self.col)     
    