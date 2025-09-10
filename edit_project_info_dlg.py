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

import os, re, glob, shutil

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize

from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QTextDocument

from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QTextEdit, QTextBrowser
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QPushButton

from media_wrappers import PictureWrapper as Picture

class EditProjectInfoDlg(QDialog):
    def __init__(self, parent=None):
        super(EditProjectInfoDlg, self).__init__(parent=parent)
        txt = qApp.instance().translate('EditProjectInfoDlg', "Dictionary Information")
        self.acquired_project_lock = False
        self.setWindowTitle(txt)
        self.project_logo_filename = qApp.instance().pm.getProjectLogo()

        self.main_widget = QWidget(self)
        self.main_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(3,3,3,3)
        self.main_widget.setLayout(layout)
        
        self.header = QLabel()
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.source_edit = QTextEdit(self)
        self.source_edit.setAutoFormatting(QTextEdit.AutoNone)
        self.source_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.source_edit.setAcceptRichText(False)
        self.source_edit.setReadOnly(False)
        self.source_edit.setTabChangesFocus(True)
        # self.source_edit.textChanged.connect(self.onTextChanged)
        self.source_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.html_preview_edit = QTextBrowser(self)
        self.html_preview_edit.setOpenExternalLinks(True)
        self.html_preview_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.html_preview_edit.setReadOnly(True) 
        self.html_preview_edit.setFocusPolicy(Qt.NoFocus) 
        self.html_preview_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.html_preview_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.pm = qApp.instance().pm
        self.new_name = self.pm.getCurrentProjectName()
        self.new_sign_language = self.pm.getCurrentProjectSignLanguage()
        self.new_version_id = self.pm.getCurrentProjectVersionId() 
        self.new_project_creator = self.pm.getCurrentProjectCreator()        
        
        layout.addWidget(self.header)
        # show timestamp
        self.timestamp_lbl = QLabel()
        self.timestamp_lbl.hide()
        self.timestamp_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.timestamp_lbl.setMinimumHeight(22)
        self.setTimestamp()
        # show sign and sense counts
        self.count_lbl = QLabel()
        self.count_lbl.hide()
        self.setCounts()

        self.project_folder_lbl = QLabel()
        self.project_folder_lbl.hide()
        self.setProjectFolder(self.pm.project.json_file)

        self.project_id_lbl = QLabel()
        self.project_id_lbl.hide()
        self.setProjectId(self.pm.project.id)

        self.setHeaderMessage(self.project_logo_filename, self.new_name, self.new_sign_language, self.new_version_id, self.new_project_creator)

        # project logo
        self.add_logo_btn = QPushButton(qApp.instance().translate('EditProjectInfoDlg', 'Add dictionary logo (optional)'))
        self.add_logo_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_logo_btn.pressed.connect(self.onAddProjectLogo)
        self.add_logo_btn.hide()
        self.remove_logo_btn = QPushButton(qApp.instance().translate('EditProjectInfoDlg', 'Remove dictionary logo'))
        self.remove_logo_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.remove_logo_btn.pressed.connect(self.onRemoveProjectLogo)
        self.remove_logo_btn.hide()

        self.dictionary_logo_lbl = QLabel('<b>{}</b>'.format(qApp.instance().translate('EditProjectInfoDlg', 'Dictionary logo (optional):')))
        layout.addWidget(self.dictionary_logo_lbl)
        self.dictionary_logo_lbl.hide()

        self.project_logo_lbl = QLabel()
        self.project_logo_lbl.setVisible(False)
        layout.addWidget(self.project_logo_lbl)
        project_logo = self.pm.getProjectLogo(self.pm.project)
        if project_logo:
            pxm = QPixmap(project_logo)            
            if pxm.height() > 200:
                self.project_logo_lbl.setPixmap(pxm.scaledToHeight(200, Qt.SmoothTransformation))
            else:
                self.project_logo_lbl.setPixmap(pxm)
            #self.project_logo_lbl.setVisible(True)
            self.add_logo_btn.setText(qApp.instance().translate('EditProjectInfoDlg', 'Change dictionary logo'))        
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.add_logo_btn)
        hlayout.addWidget(self.remove_logo_btn)
        hlayout.addStretch()
        layout.addLayout(hlayout)

        #change name
        self.change_name_lbl = QLabel('<b>{}</b>'.format(qApp.instance().translate('EditProjectInfoDlg', 'Dictionary title:')))
        self.change_name_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.change_name_lbl.setMinimumHeight(22)
        layout.addWidget(self.change_name_lbl)
        self.change_name_lbl.hide()
        self.change_name_edit = QLineEdit()
        layout.addWidget(self.change_name_edit)
        #self.new_name = self.pm.getCurrentProjectName()
        self.change_name_edit.setText(self.new_name)
        self.change_name_edit.textChanged.connect(self.onNameChanged)
        self.change_name_edit.hide()
        #change sign language
        self.change_lang_lbl = QLabel('<b>{}</b>'.format(qApp.instance().translate('EditProjectInfoDlg', 'Sign language:')))
        self.change_lang_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.change_lang_lbl.setMinimumHeight(22)
        layout.addWidget(self.change_lang_lbl)
        self.change_lang_lbl.hide()
        self.change_lang_edit = QLineEdit()
        layout.addWidget(self.change_lang_edit)
        layout.addWidget(self.count_lbl)
        #self.new_sign_language = self.pm.getCurrentProjectSignLanguage()
        self.change_lang_edit.setText(self.new_sign_language)
        self.change_lang_edit.textChanged.connect(self.onSignLanguageChanged)
        self.change_lang_edit.hide()
        
        self.change_version_lbl = QLabel('<b>{}</b>'.format(qApp.instance().translate('EditProjectInfoDlg', 'Version:')))
        self.change_version_lbl.setAlignment(Qt.AlignLeft|Qt.AlignBottom)
        self.change_version_lbl.setMinimumHeight(22)
        layout.addWidget(self.change_version_lbl)
        self.change_version_lbl.hide()
        self.change_version_edit = QLineEdit()
        layout.addWidget(self.change_version_edit)
        layout.addWidget(self.timestamp_lbl)
        layout.addWidget(self.project_folder_lbl)
        layout.addWidget(self.project_id_lbl)
        #layout.addWidget(self.project_creator_lbl)

        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary created by:')
        self.change_creator_lbl = QLabel(f'<b>{t1}</b>')
        self.change_creator_lbl.hide()
        self.change_creator_edit = QLineEdit()
        self.change_creator_edit.setText(self.new_project_creator)
        self.change_creator_edit.textChanged.connect(self.onSignCreatorChanged)
        self.change_creator_edit.hide()
        layout.addSpacing(6)
        layout.addWidget(self.change_creator_lbl)
        layout.addWidget(self.change_creator_edit)        

        #self.new_version_id = self.pm.getCurrentProjectVersionId()
        self.change_version_edit.setText(self.new_version_id)
        self.change_version_edit.textChanged.connect(self.onVersionIdChanged)
        self.change_version_edit.hide()
        
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Description:')
        self.change_description_lbl = QLabel(f'<b>{t1}</b>')
        self.change_description_lbl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.change_description_lbl.setMinimumHeight(22)
        self.change_description_lbl.hide()
        
        self.preview_edit_btn = QPushButton(qApp.instance().translate('EditProjectInfoDlg', 'Edit'))
        self.preview_edit_btn.setToolTip('{}\n{}'.format(qApp.instance().translate('EditProjectInfoDlg', 'You may use HTML tags to style your description.'), qApp.instance().translate('EditProjectInfoDlg', 'Click here to change between editing and viewing HTML style.')))
        self.preview_edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.preview_edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.preview_edit_btn.pressed.connect(self.togglePreviewEditSource)
        self.preview_edit_btn.hide()
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.change_description_lbl)
        hlayout.addWidget(self.preview_edit_btn)
        hlayout.addStretch()
        layout.addSpacing(6)
        layout.addLayout(hlayout)
        layout.addWidget(self.source_edit)
        layout.addWidget(self.html_preview_edit)
        self.html_preview_edit.show()
        self.source_edit.hide()
        hlayout = QHBoxLayout()

        # display read/write permission
        image = ':/lock16.png'
        txt = qApp.instance().translate('EditProjectInfoDlg', 'Read-only')
        if self.pm.project.writePermission:
            image = ':/lock_open16.png'
            txt = qApp.instance().translate('EditProjectInfoDlg', 'Read-write')
        txt =  "<img src='{}'>  {}".format(image, txt)
        perm_label = QLabel(txt)
        perm_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        hlayout.addWidget(perm_label)
        hlayout.addStretch()

        self.displayBtnBox = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        self.displayBtnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.displayBtnBox.button(QDialogButtonBox.Save).setText(qApp.instance().translate('EditProjectInfoDlg', 'Save'))
        self.displayBtnBox.button(QDialogButtonBox.Save).pressed.connect(self.accept)
        self.displayBtnBox.button(QDialogButtonBox.Save).setDisabled(True)
        self.displayBtnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditProjectInfoDlg', 'Close'))
        self.displayBtnBox.button(QDialogButtonBox.Cancel).pressed.connect(self.reject)
        self.edit_btn = QPushButton(qApp.instance().translate('EditProjectInfoDlg', 'Edit'))
        self.edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.edit_btn.pressed.connect(self.onEdit)
        hlayout.addWidget(self.edit_btn)
        if not (self.pm.project and self.pm.project.writePermission): 
            self.edit_btn.hide()
            self.displayBtnBox.button(QDialogButtonBox.Save).hide()
            self.displayBtnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditProjectInfoDlg', 'Close'))
            
        hlayout.addWidget(self.displayBtnBox)
        
        self.source_edit.textChanged.connect(self.onMessageChanged) 
        self.source_edit.setFocus() 
        
        self.message = self.getBodyMessage()
        if self.message:
            self.source_edit.setPlainText(self.message)
            self.displayFormatting()

        # main layout
        mlayout = QVBoxLayout()
        mlayout.setSpacing(3)
        mlayout.setContentsMargins(0,0,0,0)

        scroll = QScrollArea(self)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setWidget(self.main_widget)
        mlayout.addWidget(scroll)
        mlayout.addLayout(hlayout)
        self.setLayout(mlayout)

    def onRemoveProjectLogo(self):
        self.project_logo_lbl.setPixmap(QPixmap())
        self.project_folder_lbl.setVisible(False)            
        self.onProjectLogoChange("")
        self.remove_logo_btn.setDisabled(True)

    def onAddProjectLogo(self):
        mw = qApp.instance().getMainWindow()
        filename, texts, case = mw.getMediaFile('logo')
        if filename:
            pxm = QPixmap(filename)
            if pxm.height() > 200:
                self.project_logo_lbl.setPixmap(pxm.scaledToHeight(200, Qt.SmoothTransformation))
            else:
                self.project_logo_lbl.setPixmap(pxm)
            self.project_logo_lbl.setVisible(True)
            self.onProjectLogoChange(filename)
            self.remove_logo_btn.setEnabled(True)

    def setProjectFolder(self, project_file):
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary folder:')
        t2 = os.path.dirname(project_file)
        self.project_folder_lbl.setText(f'<p>{t1} <b>{t2}/</b></p>')

    def setProjectId(self, project_id):
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary project ID (generated automatically):')
        self.project_id_lbl.setText(f'<p>{t1} <b>{project_id}</b></p>')

    def setProjectCreator(self, project_creator):
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary created by:')
        self.project_creator_lbl.setText(f'<p>{t1} <b>{project_creator}</b></p>')

    def setTimestamp(self):
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Last update:')
        t2 = self.pm.getCurrentDateTimeStr()
        self.timestamp_lbl.setText(f'<p>{t1} <b>{t2}</b></p>')

    def setCounts(self):
        sign_count, sense_count = qApp.instance().pm.project.countSignsSensesForProject()
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'signs in dictionary')
        t2 = qApp.instance().translate('EditProjectInfoDlg', 'senses')
        self.count_lbl.setText(f'<p><b>{sign_count} {t1} ({sense_count} {t2})</b></p>')
         
    def togglePreviewEditSource(self):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        if self.source_edit.isVisible():
            self.html_preview_edit.show()
            self.source_edit.hide()
            self.preview_edit_btn.setText(qApp.instance().translate('EditProjectInfoDlg', 'Edit'))
        else:
            self.source_edit.show()
            self.html_preview_edit.hide()
            self.preview_edit_btn.setText(qApp.instance().translate('EditProjectInfoDlg', 'Preview HTML'))
        self.setSize()

    def refreshProjectInfo(self):
        mw = qApp.instance().getMainWindow()
        mw.reloadProject(force=True)

        old_project_name = self.new_name
        old_sign_language = self.new_sign_language
        old_version_id = self.new_version_id
        new_project_name = self.pm.getCurrentProjectName()
        new_sign_language = self.pm.getCurrentProjectSignLanguage()
        new_version_id = self.pm.getCurrentProjectVersionId()
        old_message = self.currentMessage()
        new_message = self.getBodyMessage()

        box = QMessageBox(self)
        box.setWindowTitle(' ')
        txt1 = qApp.instance().translate('EditProjectInfoDlg', 'This dictionary has been edited by another user.')
        txt2 = qApp.instance().translate('EditProjectInfoDlg', 'Your display may show changes.')
        msg = '{}\n{}'.format(txt1, txt2)
        box.setText(msg)
        box.setIcon(QMessageBox.Information)
        box.exec_()

        self.setTimestamp() # if dictionary has changed, at the very least the timestamp will have changed
        self.setCounts()

        if old_project_name != new_project_name:
            self.new_name = new_project_name
            self.change_name_edit.setText(self.new_name)
        if old_sign_language != new_sign_language:
            self.new_sign_language = new_sign_language
            self.change_lang_edit.setText(self.new_sign_language)
        if old_version_id != new_version_id:
            self.new_version_id = new_version_id
            self.change_version_edit.setText(self.new_version_id)
        if old_message != new_message:
            self.message = new_message
            if self.message:
                self.source_edit.setPlainText(self.message)
                self.displayFormatting()
            else:
                self.source_edit.clear()

    def onEdit(self):
        self.acquired_project_lock = qApp.instance().pm.acquireProjectLock(self)
        if self.acquired_project_lock:
            if qApp.instance().pm.projectChanged():
                self.refreshProjectInfo()
            self.setupEditing() 
            qApp.instance().pm.startInactivityTimer(self) 

    def hideEvent(self, evt):
        super(EditProjectInfoDlg, self).hideEvent(evt) 
        qApp.instance().pm.stopInactivityTimer()

    def leaveEdit(self, check_dirty=False):
        if self.acquired_project_lock:
            qApp.instance().pm.releaseProjectLock()
        self.reject()          
        
    def setupEditing(self):
        self.setWindowTitle(qApp.instance().translate('EditProjectInfoDlg', "Edit Dictionary Information"))
        self.edit_btn.setEnabled(False)
        self.header.hide()
        for widget in [
            self.timestamp_lbl,
            self.count_lbl,
            self.project_folder_lbl,
            self.project_id_lbl,
            self.change_creator_lbl,
            self.change_creator_edit,
            self.add_logo_btn,
            self.remove_logo_btn,
            self.change_name_lbl,
            self.change_name_edit,
            self.change_lang_lbl,
            self.change_lang_edit,
            self.change_version_lbl,
            self.change_version_edit,
            self.preview_edit_btn,
            self.change_description_lbl,            
            self.project_logo_lbl,
            self.dictionary_logo_lbl]:
                widget.show()
        for widget in [
            self.timestamp_lbl,
            self.project_folder_lbl,
            self.project_id_lbl,
            self.count_lbl]:
                widget.setDisabled(True)
        if not self.pm.getProjectLogo(self.pm.project):
            self.remove_logo_btn.setDisabled(True)
        self.source_edit.show()
        self.html_preview_edit.hide()
        self.preview_edit_btn.setText(qApp.instance().translate('EditProjectInfoDlg', 'Preview HTML'))
        self.edit_btn.setDisabled(True)
        self.setSize()
        #self.resize(self.sizeHint()) 
        
    def displayFormatting(self):
        current_text = self.currentMessage()
        if current_text and current_text.count('<') and current_text.count('>'):
            br = '<br style="line-height: 50%;">'
            message = current_text.replace('\n\n', br)
            message = message.replace('\n', '')
            self.html_preview_edit.setHtml(message)
            self.preview_edit_btn.setEnabled(True)
        else:
            self.html_preview_edit.setText(current_text)
            self.preview_edit_btn.setEnabled(False)
        
    def setHeaderMessage(self, project_logo, project_name, sign_language, version_id, project_creator):
        # Dictionary title
        name_text = project_name
        if project_name != self.pm.getCurrentProjectName():
            name_text = f'<span style="color: red;">{project_name}</span>'
        logo = ':/about_project.png'
        if project_logo:
            logo = project_logo
        name_text = f'<h2 style="vertical-align:middle"><img src="{logo}"><br><br>{name_text}</h2>'

        # Sign language
        lang_text = sign_language
        if sign_language != self.pm.getCurrentProjectSignLanguage():
            lang_text = f'<span style="color: red;">{sign_language}</span>'
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Sign language:')
        lang_text = f"{t1} <b>{lang_text}</b>"

        # Sign (Sense) count
        count_text = self.count_lbl.text().replace('<p>', '').replace('</p>', '')

        # Version
        version_text = version_id
        if version_id != self.pm.getCurrentProjectVersionId():
            version_text = '<span style="color: red;">{}</span>'.format(version_id)
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary version:')
        version_text = f"{t1} <b>{version_text}</b>"

        # Last update
        update_text = self.timestamp_lbl.text().replace('<p>', '').replace('</p>', '')

        # Dictionary folder
        proj_folder = self.project_folder_lbl.text().replace('<p>', '').replace('</p>', '')

        # Dictionary id
        id_text = self.project_id_lbl.text().replace('<p>', '').replace('</p>', '')

        # Dictionary creator
        creator_text = project_creator
        if creator_text != self.pm.getCurrentProjectCreator():
            creator_text = f'<span style="color: red;">{creator_text}</span>'
        t1 = qApp.instance().translate('EditProjectInfoDlg', 'Dictionary created by:')
        creator_text = f"{t1} <b>{creator_text}</b>"
            
        message = f"{name_text}<p>{lang_text}<br>{count_text}<br><br>{version_text}<br>{update_text}<br>{proj_folder}<br>{id_text}<br><br>{creator_text}</p>"
        self.header.setText(message)
    
    def getBodyMessage(self):
        message = self.pm.getAuthorsMessage()
        return message

    def sizeHint(self):
        s = QSize(1280, 800)
        try:
            s = qApp.screenAt(self.pos()).availableSize()
        except:
            pass
        max_width = s.width() * 0.40
        max_height = s.height() * 0.60 

        w = max_width
        h = max_height
        return QSize(int(w), int(h))      

    def resizeEvent(self, evt):
        self.setSize()

    def showEvent(self, evt):
        super(EditProjectInfoDlg, self).showEvent(evt)
        self.setSize()
    
    def setSize(self):        
        w = self.size().width() - 24
        doc = QTextDocument() 
        txt = self.source_edit.toPlainText()
        doc.setPlainText(txt)
        doc.setTextWidth(w)        
        h = doc.size().height() + 64
        count = self.main_widget.layout().count()
        while count >= 0:
            try:
                widget = self.main_widget.layout().itemAt(count).widget()
            except:
                pass
            else:
                if isinstance(widget, (QLabel, QLineEdit)) and widget.isVisible():
                    h = h + widget.height()
                elif widget is None:
                    h = h + 32 # an hlayout
            count = count - 1
        self.main_widget.setFixedSize(int(w), int(h))
                
    def currentMessage(self):
        return self.source_edit.toPlainText()
    
    ##!!@pyqtSlot()
    def onMessageChanged(self):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.displayFormatting()
        if self.source_edit.toPlainText() != self.message:
            self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
        else:
            if self.new_name == self.pm.getCurrentProjectName() and \
                self.new_sign_language == self.pm.getCurrentProjectSignLanguage() and \
                self.new_version_id == self.pm.getCurrentProjectVersionId() and \
                self.new_project_creator == self.pm.getCurrentProjectCreator():
                    self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(False)
            else:
                self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
    
    def onNameChanged(self, text):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.new_name = text
        if text and text != self.pm.getCurrentProjectName() or \
            self.source_edit.toPlainText() != self.message or \
            self.new_sign_language != self.pm.getCurrentProjectSignLanguage() or \
            self.new_version_id != self.pm.getCurrentProjectVersionId() or \
            self.new_project_creator != self.pm.getCurrentProjectCreator():
                self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
        else:
            self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(False)
            
    def onSignLanguageChanged(self, text):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.new_sign_language = text
        if text and text != self.pm.getCurrentProjectSignLanguage() or \
            self.source_edit.toPlainText() != self.message or \
            self.new_name != self.pm.getCurrentProjectName() or \
            self.new_version_id != self.pm.getCurrentProjectVersionId() or \
            self.new_project_creator != self.pm.getCurrentProjectCreator():
                self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
        else:
            self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(False)
            
    def onVersionIdChanged(self, text):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.new_version_id = text
        if text and text != self.pm.getCurrentProjectVersionId() or \
            self.source_edit.toPlainText() != self.message or \
            self.new_name != self.pm.getCurrentProjectName() or \
            self.new_sign_language != self.pm.getCurrentProjectSignLanguage() or \
            self.new_project_creator != self.pm.getCurrentProjectCreator():
                self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
        else:
            self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(False)

    def onSignCreatorChanged(self, text):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.new_project_creator = text
        if text and text != self.pm.getCurrentProjectCreator() or \
            self.source_edit.toPlainText() != self.message or \
            self.new_name != self.pm.getCurrentProjectName() or \
            self.new_version_id != self.pm.getCurrentProjectVersionId() or \
            self.new_sign_language != self.pm.getCurrentProjectSignLanguage():
                self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)
        else:
            self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(False)

    def onProjectLogoChange(self, logo_file):
        self.project_logo_filename = logo_file
        self.displayBtnBox.button(QDialogButtonBox.Save).setEnabled(True)

# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()      
        