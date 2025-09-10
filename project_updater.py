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
from PyQt5.Qt import QTextDocument

""" This module takes old sqlite based projects (<0.9.0), updates them and converts to current json format.
"""

import os
import glob
import shutil
import sys
import io
import copy

import re, codecs, json, stat
from components.component_descriptions import ComponentDescriptions

from PyQt5.QtCore import QObject
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QSize

from PyQt5.QtWidgets import QMessageBox, QProgressBar, QProgressDialog, QInputDialog
from PyQt5.QtWidgets import qApp

from PyQt5.QtGui import QIcon, QMovie#, QTextDocument

from database import SooSLDatabaseManager
from database import OLDEST_UPDATABLE
import csaw as csaw
from signmodel_updater import SignModelUpdater as SignModel
from dialect import Dialect
from project import Project

class ProjectUpdater(QObject):
    """an editor class for SooSL dictionary projects
    """
    #abort_save = pyqtSignal()
    project_closed = pyqtSignal()
    signs_found = pyqtSignal(list)
    show_warning = pyqtSignal(str, str) #dialog
    show_info = pyqtSignal(str, str) #dialog
    show_message = pyqtSignal(str) #status bar
    lang_selection_change = pyqtSignal()
    search_lang_change = pyqtSignal()
    #focal_dialect_changed = pyqtSignal(int)
    font_size_change = pyqtSignal(int, int)
    font_family_change = pyqtSignal(int, str)
    lang_order_change = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super(ProjectUpdater, self).__init__(parent)
        
        self.sign_model = SignModel(parent=self)
        self.signs = []
        self.selected_dialects = []
        self.selected_lang_ids = [1]
        self.search_lang_id = 1
        self.files_2_delete = []
#         self.dbm = SooSLDatabaseManager(parent=self)
        self.project = None
        self.prev_project_filename = None
        self.current_project_filename = None
        self.current_project_rw = False
    
    def ableToEdit(self):
        """a flag used to dictate read-only or read-write status for a project database.
        """
        return self.__authorizeUser()
    
    @property
    def passProtected(self):
        """This means that a project requires a password to unlock it for editing.
        """
        return self.dbm.hasPass()
    
    def getSelectedLanguages(self):
        return [lang for lang in self.getLangs() if lang[0] in self.selected_lang_ids]
    
    def sooslOlderThan(self, version_string):
        return self.dbm.sooslOlderThan(version_string)
    
    def getProjectVersion(self):
        return self.dbm.getVersion()
    
    def getSignLanguage(self):
        dlg = SignLanguageRequestDialog(self.current_project_filename)
        if dlg.exec_() and dlg.textValue():
            return dlg.textValue()
        self.getSignLanguage()
    
    def getProjectSooSLVersion(self):
        if self.project:
            return self.project.soosl_version
        return '0.0.0'
    
    def getCurrentProjectName(self):
        if self.project:
            return self.project.name
        return ''
    
    def getCurrentProjectDir(self):
        if self.current_project_filename:
            return os.path.dirname(self.current_project_filename)
        return ''
    
    def setCurrentProject(self, project):
        self.project = project
    
    def setCurrentProjectFilename(self, filename): 
        self.prev_project_filename = self.current_project_filename
        self.current_project_filename = filename     
    
#     def newProject(self, setup_data, db_ext):
#         name, location, written_langs, dialects, descript = setup_data
#         #setup directory structure
#         ##TODO: check 'name' is not already used; offer to open existing named database???
#         filename = os.path.normpath(os.path.join(location, name, "{}.{}".format(name, db_ext))) 
#         setup = self.__setupDirectories(location, name, filename)
#         if setup: #new directories created
#             self.current_project_rw = True
#             #self.search_lang_id = self.getFocalLangID()  
#             mw = qApp.instance().getMainWindow()
#             progress = QProgressDialog(mw)
#             progress.setWindowTitle(' ')
#             settings = qApp.instance().getSettings()
#             if not int(settings.value('Testing', 0)): progress.setWindowModality(Qt.WindowModal)##NOTE: allows crash testing while testing
#             progress.setCancelButton(None)
#             progress.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
#             progress.setLabelText('<h3 style="color:blue;">{}</h3><p>{}</p>'.format(qApp.instance().translate('ProjectUpdater', "Creating New Dictionary..."), qApp.instance().translate('ProjectUpdater', "Please wait...")))
#             progress.setMinimum(0)
#             progress.setMaximum(0)
#             ##NOTE: hide bar until I can figure where to signal setValue from
#             bar = QProgressBar()
#             progress.setBar(bar)
#             bar.hide()
#             progress.forceShow()   
#             qApp.processEvents()
#             
#             try:
#                 self.dbm.close()
#             except:
#                 pass
#             else:
#                 self.project_closed.emit()
#                 
#             new_db = self.dbm.new(filename, written_langs, dialects, descript)
#             self.setReadWrite(True) 
#             #self.setSelectedLangIds(self.getLangIds())
#             self.setCurrentProjectFilename(filename)
#             self.setProjectSettings()
#             progress.close() 
#                       
#             return new_db
#         else: #directories already exist
#             return None
        
    def setSelectedLangIds(self, lang_ids):
        _ids = []
        for _id in lang_ids:
            if isinstance(_id, str):
                _ids.append(abs(self.getLangId(_id)))
            else:
                _ids.append(abs(_id))
                
        if self.selected_lang_ids != _ids:
            self.selected_lang_ids = _ids
            settings = qApp.instance().getSettings()
            #name = settings.value("lastOpenedDatabase")
            name = self.current_project_filename
            if name and name != 'new':
                settings.setValue('ProjectSettings/{}/selected_lang_ids'.format(name), _ids)
                settings.sync()
                self.lang_selection_change.emit()
            
    def setSearchLangId(self, lang_id):
        if isinstance(lang_id, str):
            lang_id = self.getLangId(lang_id) #probably new language
        if self.search_lang_id != lang_id:
            self.search_lang_id = int(lang_id)
            settings = qApp.instance().getSettings()
            #name = settings.value("lastOpenedDatabase")
            name = self.current_project_filename
            if name and name != 'new':
                settings.setValue('ProjectSettings/{}/search_lang_id'.format(name), lang_id)
                settings.sync()
                self.search_lang_change.emit()
            
    def setLangOrder(self, lang_ids):
        self.dbm.setLangOrder(lang_ids)
        self.lang_order_change.emit(lang_ids)
            
    def getSearchFontSize(self):
        return self.getFontSizeById(self.search_lang_id)
    
    def getSearchFontFamily(self):
        lang_name = self.project.getWrittenLanguageName(self.search_lang_id)
        return self.getFontFamily(lang_name)
           
    def getFontFamily(self, lang_name):
        settings = qApp.instance().getSettings()
        key = 'fontFamily{}'.format(lang_name)
        font_family = settings.value(key, qApp.instance().font().family())
        return font_family
            
    def getFontSize(self, lang_name):        
        settings = qApp.instance().getSettings()
        key = 'fontSize{}'.format(lang_name)
        size = settings.value(key, 12)
        if size:
            return int(size)
        return 12
    
    def getFontSizeById(self, lang_id):
        if lang_id == 0:
            lang_id = 1 ##NOTE: this is an error, remove after fix
        lang_name = self.project.getWrittenLanguageName(lang_id)
        font_size = self.getFontSize(lang_name)
        return font_size 
    
    def setFontSize(self, lang_name, _int):
        settings = qApp.instance().getSettings()
        settings.setValue('fontSize{}'.format(lang_name), _int)
        settings.sync()
        
    def setFontFamily(self, lang_name, family_name):
        settings = qApp.instance().getSettings()
        settings.setValue('fontFamily{}'.format(lang_name), family_name)
        settings.sync()
            
    def setFontSizes(self, font_sizes):
        for key in font_sizes.keys():
            if isinstance(key, str):
                lang_name = key
                lang_id = self.getLangId(key) #self.getFontSize(lang_name)
            else:
                lang_name = self.project.getWrittenLanguageName(key)
                lang_id = key
                
            font_size = font_sizes.get(key)                
            self.setFontSize(lang_name, font_size)
            self.font_size_change.emit(lang_id, font_size)
            
    def setFontFamilies(self, font_families):
        for key in font_families.keys():
            if isinstance(key, str):
                lang_name = key
                lang_id = self.getLangId(key) #self.getFontSize(lang_name)
            else:
                lang_name = self.project.getWrittenLanguageName(key)
                lang_id = key
                
            font_family = font_families.get(key)                
            self.setFontFamily(lang_name, font_family)
            self.font_family_change.emit(lang_id, font_family)
            
    def setAutoKeyboard(self, check_state):
        settings = qApp.instance().getSettings()
        settings.setValue('autoKeyboardSwitchState', check_state)
        settings.sync()  
    
    def getProjectFiles(self):
        proj_dir = os.path.dirname(self.current_project_filename)
        files = [f for f in glob.iglob(os.path.join(proj_dir, '**'), recursive=True) if not os.path.isdir(f)]
        return files
    
    def __setWritePermission(self, filename, write):
        # https://stackoverflow.com/questions/28492685/change-file-to-read-only-mode-in-python
        if not write:
            os.chmod(filename, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH) 
            return False
        os.chmod(filename, stat.S_IWUSR|stat.S_IREAD)
        return True
    
    def backupCurrentProject(self):        
        _copy = '{}-backup'.format(self.current_project_filename)
        shutil.copy(self.current_project_filename, _copy)
    
    def setProjectSettings(self):
        settings = qApp.instance().getSettings()
        name = self.current_project_filename
        settings.setValue("lastOpenedDatabase", name)
        #self.__addToOpenProjects(name)
        self.selected_lang_ids = [1]
        self.search_lang_id = 1
        if name:
            selected_lang_ids = settings.value('ProjectSettings/{}/selected_lang_ids'.format(name))
            if not selected_lang_ids:
                selected_lang_ids = self.project.getWrittenLanguageIds()
            if selected_lang_ids:
                selected_lang_ids = [int(i) for i in selected_lang_ids]
                settings.setValue('ProjectSettings/{}/selected_lang_ids'.format(name), selected_lang_ids)
                settings.sync()
                self.selected_lang_ids = selected_lang_ids
                
            search_lang_id = settings.value('ProjectSettings/{}/search_lang_id'.format(name))
            if not search_lang_id:
                search_lang_id = self.getFocalLangID()
            if search_lang_id:
                settings.setValue('ProjectSettings/{}/search_lang_id'.format(name), search_lang_id)
                settings.sync()
                self.search_lang_id = int(search_lang_id) 
    
    ##NOTE: No longer encrypting by default on close 0.8.7 (161116)
    def closeProject(self, encrypt=False, value=False, emit=True):
        """close currently open project database
        """
        if self.current_project_filename:
            _copy = '{}-backup'.format(self.current_project_filename)
            if os.path.exists(_copy):
                try:
                    os.remove(_copy)
                except:
                    self.__setWritePermission(_copy, True) # importing/updating a read-only database
                    try:
                        os.remove(_copy)
                    except:
                        pass
            settings = qApp.instance().getSettings()
            settings.setValue("lastOpenedDatabase", self.current_project_filename)
            self.setCurrentProjectFilename(None)
            if hasattr(self, 'dbm') and not self.dbm.dropFilesToDelete(): #table couldn't be dropped because files are listed in it
                files = self.dbm.files2Delete()
                for f in files:
                    _type = os.path.split(os.path.split(f)[0])[1]
                    count = 0
                    if _type == 'signs':
                        count = self.dbm.signCountByVideo(f)
                    elif _type == 'sentences':
                        count = self.dbm.sentenceVideoUsageCount(f)
                    elif _type == 'extra_videos':
                        count = self.dbm.exPictureUsageCount(f)
                    elif _type == 'extra_pictures':
                        count = self.dbm.exVideoUsageCount(f)
                     
                    #if file is not in use by the database, try to delete it.
                    if count <= 0:
                        try:
                            os.remove(f)
                        except:
                            if os.path.exists(f):
                                pass #file in use; JUST LEAVE IT ALONE AND TRY AGAIN NEXT TIME!!!?
                            else:
                                self.dbm.removeFile2Delete(f) #doesn't exist and shouldn't be in this table
                        else: #if successful, remove it from this list
                            self.dbm.removeFile2Delete(f)
                    #if file is in use by the database it is not available for deletion, remove it from this list
                    elif count > 0:
                        self.dbm.removeFile2Delete(f)
                ##database.dropFilesToDelete() #try again, but doesn't really matter... it will drop eventually
             
            old_db_filename = self.current_project_filename
            if hasattr(self, 'dbm'):           
                self.dbm.compact()
                old_db_filename = self.dbm.close()
                #old_db_name = os.path.splitext(os.path.basename(old_db_filename))[0]  
             
            self.sign_model.load(None, None)
            if qApp.hasPendingEvents():
                qApp.processEvents()
               
            if emit:
                self.project_closed.emit()
               
            if value == True:
                return old_db_filename
        return None
    
    def amendDialectList(self, _dialects):
        if _dialects:
            toAdd = []
            toRemove = []
            toAmend = []
            for d in _dialects:
                _id = int(d[0])
                if _id:
                    if _id < 0: #delete
                        toRemove.append(d) 
                    else: #amend
                        toAmend.append(d)
                else: #new
                    toAdd.append(d)
            self.showMessage(qApp.instance().translate('ProjectUpdater', "Amending Dialects... Please wait..."))
            old_focal = self.dbm.getFocalDialect()._id
            new_focal = [d for d in _dialects if d[3]][0][0]            
            
            if toAdd:
                self.dbm.addDialects(toAdd)
                self.selectDialects(toAdd)  #when first added, dialects should appear as selected in dialect filter dialog            
                        
            if new_focal != old_focal:
                if not new_focal: # newly added dialect with id 0
                    new_focal = self.getFocalDialect()._id
                    
            if toAmend: 
                self.dbm.amendDialects(toAmend)
                              
            if toRemove:
                #if self.deletionAllowed():
                for dialect in toRemove:
                    i = abs(dialect[0])
                    sign_count = self.dbm.countSignsSensesForDialect(i)[0]
                    if sign_count:
                        name = dialect[1].upper()
                        focal = self.dbm.getFocalDialect().name
                        sign_txt = qApp.instance().translate('ProjectUpdater', '1 Sign uses this dialect.')
                        txt1 = qApp.instance().translate('ProjectUpdater', 'This will be changed to the focal dialect.')
                        if sign_count > 1:
                            sign_txt = "<span style='color:blue;'>{}</span> {}".format(sign_count, qApp.instance().translate('ProjectUpdater', 'Signs use this dialect:'))
                            txt1 = qApp.instance().translate('ProjectUpdater', 'These will be changed to the focal dialect:')
                        text = "<b>{} <span style='color:blue;'>{}</span></b><br><br>{} <span style='color:blue;'>{}</span>".format(sign_txt, name, txt1, focal)
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Warning)
                        msgBox.setTextFormat(Qt.RichText)
                        msgBox.setWindowTitle(qApp.instance().translate('ProjectUpdater', "Delete Dialect"))
                        msgBox.setText(text)
                        msgBox.setInformativeText(qApp.instance().translate('ProjectUpdater', "Is this what you want to do?"))
                        msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                        yes_btn, no_btn = msgBox.buttons()
                        yes_btn.setIcon(QIcon(":/thumb_up.png"))
                        no_btn.setIcon(QIcon(":/thumb_down.png"))
                        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ProjectUpdater', "Yes"))
                        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ProjectUpdater', "No"))
                        msgBox.setDefaultButton(QMessageBox.No)
                        if msgBox.exec_() == QMessageBox.No: #don't remove this dialect
                            toRemove = [d for d in toRemove if abs(d[0]) != i]
                if toRemove:
                    self.dbm.removeDialects(toRemove)
                    self.selectDialects(toRemove) 
            
    def amendLanguageList(self, langs):
        toAdd = []
        toRemove = []
        toAmend = []        
        all_langs = [list(l) for l in self.getLangs()]
        for l in langs:
            try:
                _id = int(l[0])
            except:
                toAdd.append(l)
            else:
                if _id:
                    if _id < 0:
                        toRemove.append(l) 
                    elif l not in all_langs:
                        toAmend.append(l)
                else:
                    toAdd.append(l)
        self.showMessage(qApp.instance().translate('ProjectUpdater', "Amending text settings... "))
        
        if toAdd:
            self.dbm.addLanguages(toAdd)
        if toRemove:
#             if self.deletionAllowed():
            for lang in toRemove:
                i = abs(lang[0])
                # give user choice about removing language if the language is used
                count = self.signCountByLang(i)
                if count:
                    name = lang[1].upper()
                    msgBox = QMessageBox()
                    msgBox.setIcon(QMessageBox.Warning)
                    msgBox.setTextFormat(Qt.RichText)
                    msgBox.setWindowTitle(qApp.instance().translate('ProjectUpdater', "Remove Language"))
                    msgBox.setText("<b>{} <span style='color:blue;'>{}</span><br>{} <span style='color:blue;'>{}</span></b>".format(qApp.instance().translate('ProjectUpdater', 'Language name:'), \
                        name, qApp.instance().translate('ProjectUpdater', 'Number of signs affected:'), count))
                    msgBox.setInformativeText(qApp.instance().translate('ProjectUpdater', "Remove this language?"))
                    msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                    yes_btn, no_btn = msgBox.buttons()
                    yes_btn.setIcon(QIcon(":/thumb_up.png"))
                    no_btn.setIcon(QIcon(":/thumb_down.png"))
                    msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ProjectUpdater', "Yes"))
                    msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ProjectUpdater', "No"))
                    msgBox.setDefaultButton(QMessageBox.No)
                    if msgBox.exec_() == QMessageBox.No: #don't remove this language
                        toRemove = [l for l in toRemove if abs(l[0]) != i]
                        l[0] = abs(l[0]) #this should mark this lang as not deleted for the purpose of other functions
                        
            if toRemove:
                self.dbm.removeLanguages(toRemove) 
        if toAmend: 
            self.dbm.amendLanguages(toAmend)
            
    def amendGramCatsList(self, types):
        toAdd = []
        toRemove = []
        toAmend = []
        for t in types:
            _id = int(t[0])
            if _id:
                if _id < 0:
                    toRemove.append(t) 
                else:
                    toAmend.append(t)
            else:
                toAdd.append(t)
        self.showMessage(qApp.instance().translate('ProjectUpdater', "Amending grammatical categories... Please wait..."))
        
        if toAdd:
            self.dbm.addGramCats(toAdd)
        if toRemove:
            for _type in toRemove:
                i = abs(_type[0])
                count = self.dbm.signCountByGramCat(i)
                if count:
                    name = _type[1].upper()
                    msgBox = QMessageBox()
                    msgBox.setIcon(QMessageBox.Warning)
                    msgBox.setTextFormat(Qt.RichText)
                    msgBox.setWindowTitle(qApp.instance().translate('ProjectUpdater', "Delete Grammatical Category"))
                    t1 = qApp.instance().translate('ProjectUpdater', 'Sign(s) use this grammar category:')
                    t2 = qApp.instance().translate('ProjectUpdater', 'It will be removed from these signs if you continue.')
                    text = "<b><span style='color:blue;'>{}</span> {} <span style='color:blue;'> {}</span></b><br><br>{}".format(count, t1, name, t2)
                    msgBox.setText(text)
                    msgBox.setInformativeText(qApp.instance().translate('ProjectUpdater', "Is this what you want to do?"))
                    msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                    yes_btn, no_btn = msgBox.buttons()
                    yes_btn.setIcon(QIcon(":/thumb_up.png"))
                    no_btn.setIcon(QIcon(":/thumb_down.png"))
                    msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ProjectUpdater', "Yes"))
                    msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ProjectUpdater', "No"))
                    msgBox.setDefaultButton(QMessageBox.No)
                    if msgBox.exec_() == QMessageBox.No: #don't remove this language
                        toRemove = [t for t in toRemove if abs(t[0]) != i]
            if toRemove:
                self.dbm.removeGramCats(toRemove)
        if toAmend:
            self.dbm.amendGramCats(toAmend)
    
#     def openLast(self):        
#         """open the last used project database
#         """ 
#         settings = qApp.instance().getSettings()
#         last_filename = settings.value("lastOpenedDatabase")
#         
#         if last_filename:
#             enc = last_filename + '.enc'
#             if os.path.exists(enc):
#                 try:
#                     return self.openProject(enc)
#                 except:
#                     return None
#             elif os.path.exists(last_filename):
#                 try:
#                     return self.openProject(last_filename)
#                 except:
#                     return None                
#             else:
#                 return None
        
#     def  __setupDirectories(self, location, name, filename):
#         project_dir = os.path.join(location, name)
#         try:
#             os.makedirs(project_dir)
#         except:
#             if not os.path.exists(filename):
#                 #database does not exist but directories do, perhaps from aborted/failed attempt
#                 return True
#             else:
#                 return False ## NOTE: if project_dir already exists; give user choice to open existing database???
#         else:
#             sign_dir = os.path.join(project_dir, "signs")
#             sent_dir = os.path.join(project_dir, "sentences")
#             ex_picts_dir = os.path.join(project_dir, "extra_pictures")
#             ex_videos_dir = os.path.join(project_dir, "extra_videos")
#             for _dir in [sign_dir, sent_dir, ex_picts_dir, ex_videos_dir]:
#                 try:
#                     os.makedirs(_dir)
#                 except:
#                     pass #shouldn't happen as you will only get here if 'project_dir' doesn't already exist
#             return True
        
    def __authorizeUser(self):
        """authorize user for editing (sqlite)
        """
        if csaw.canReadWrite(self.dbm.getPassMessage()):
            return True
        return False
    
    def secure(self, filename, inplace=False):
        _file = csaw.secureFile(filename)
        if inplace:
            try:
                os.remove(filename)
            except:
                pass
        return _file
    
    def unsecure(self, filename, inplace=False):
        _file = csaw.unsecureFile(filename)
        if inplace:
            os.remove(filename)
        return _file
    
    def setReadWrite(self, _bool):
        """set read-write/read-only permission for project."""  
        self.__setWritePermission(self.current_project_filename, _bool)
        self.current_project_rw = _bool
    
    def newSign(self, sign_filename, texts):
        self.sign_model.loadNew(sign_filename, texts)
        
    def addGramCat(self, type_id):
        """add a sign type (part-of-speech) to the project's database
        """
        self.dbm.addType(type_id)
        
    def saveAuthorsMessage(self, message):
        self.dbm.saveAuthorsMessage(message)
        
    def addDialects(self, dialects, sign_id, gloss_id): 
        for d in dialects:
            self.dbm.linkDialect(d._id, sign_id, gloss_id) 
    
    def removeDialects(self, dialects, sign_id, gloss_id):
        for d in dialects:
            self.dbm.unlinkDialect(d._id, sign_id, gloss_id) 
            
    def amendDialects(self, old_dialects, new_dialects, sign_id, gloss_id):
        fd = self.getFocalDialect()
        if not new_dialects:
            new_dialects = [fd]
        if not old_dialects:
            old_dialects = []
        old_dialect_ids = [d._id for d in old_dialects]
        new_dialect_ids = [d._id for d in new_dialects]
        
        remove = [] #dialects to remove
        add = [] #dialects to add
        for d in old_dialects:
            if d._id not in new_dialect_ids:
                remove.append(d)            
        for d in new_dialects:
            if d._id not in old_dialect_ids:
                add.append(d)
            
        if add:
            self.addDialects(add, sign_id, gloss_id) 
        if remove:
            self.removeDialects(remove, sign_id, gloss_id) 
            
    def addSignVideo(self, video):
        video_file = self.getDestinationFile(video)
        if not video_file or not os.path.exists(video_file):
            return None  
        
        _hash = self.getHash(video)
        if not _hash:
            _dir = os.path.normpath(os.path.dirname(video))
            proj_dir = os.path.normpath(os.path.dirname(self.current_project_filename))
            if _dir.startswith(proj_dir):
                _hash = self.dbm.updateEmptyHash(video)
        self.showMessage("{} - {}".format(qApp.instance().translate('ProjectUpdater', 'Adding sign video'), video)) 
        
        sign_id =  self.dbm.addSign(video_file, _hash) #returns sign id
        new_file_name = self.joinFilenameId(video_file, sign_id)
        os.replace(video_file, new_file_name)
        self.dbm.updateSign(new_file_name, sign_id, _hash)
        if new_file_name in self.files_2_delete:
            self.files_2_delete.remove(new_file_name)
            self.dbm.removeFile2Delete(new_file_name)
        return sign_id
    
    def changeSignVideo(self, sign_id, old_video, new_video):
        _hash = self.getHash(new_video)
        video_file = self.getDestinationFile(new_video)
        if not video_file:
            video_file = self.getDestinationFile(os.path.normpath(new_video)) 
        self.dbm.updateSign(video_file, sign_id, _hash)
        if self.signExists(old_video)[0] is None:
            self.files_2_delete.append(old_video)  
        if video_file in self.files_2_delete:
            self.files_2_delete.remove(video_file)
            self.dbm.removeFile2Delete(video_file)
            
    def reorderSenses(self, sign_id, sense_ids): 
        self.dbm.reorderSenses(sign_id, sense_ids) 
            
    def addGloss(self, gloss_dict, sign_id):
        #gloss_dict ==> {lang_id: text}
        gloss_id = self.dbm.addGloss(gloss_dict, sign_id)
        return gloss_id
    
    def amendGloss(self, new_dict, old_dict, sign_id):
        #new_dict, old_dict, self.sign_id
        return self.dbm.amendGloss(new_dict, old_dict, sign_id)
        
    def removeGloss(self, gloss_dict, sign_id):
        gloss_id = abs(gloss_dict.get(0))
        self.dbm.removeGloss(gloss_id, sign_id)
        self.dbm.removeGlossText(gloss_id)
        
    def addSentence(self, media_obj, texts, sign_id, gloss_id):
        video = media_obj.filename
        _hash = self.getHash(video)
        if not _hash:
            _dir = os.path.normpath(os.path.dirname(video))
            proj_dir = os.path.normpath(os.path.dirname(self.current_project_filename))
            if _dir.startswith(proj_dir):
                _hash = self.dbm.updateEmptyHash(video)
        
        video_file = None
        if video:
            video_file = self.getDestinationFile(video)
            if not video_file:
                video_file = self.getDestinationFile(os.path.normpath(video))
            if not video_file:
                video_file = video # not really new, just moving existing file
        return self.dbm.addSentence(video_file, texts, sign_id, gloss_id, _hash)
    
    def amendSentence(self, _new_video, orig_video, new_texts, orig_texts, sign_id, gloss_id, sentence_id, response):
        # response can be either '1' for 'once' or '2' for 'all'; determining if video amendment will be for just this sentence or
        # all sentences which use this video
        self.showMessage(qApp.instance().translate('ProjectUpdater', "Amending sentence...")) #{}".format(idx))
        new_video = None
        _hash = None
        try:      
            if _new_video != orig_video:
                new_video = self.getDestinationFile(_new_video)
                _hash = self.getHash(_new_video)
                if not new_video:
                    new_video = self.getDestinationFile(os.path.normpath(_new_video))
                if not new_video:
                    new_video = _new_video 
        except:
            pass
        self.dbm.amendSentence(new_video, orig_video, new_texts, orig_texts, sign_id, gloss_id, sentence_id, response, _hash)   
        
        if self.sentenceVideoExists(orig_video)[0] is None:
            self.files_2_delete.append(orig_video)
        if new_video in self.files_2_delete:
            self.files_2_delete.remove(new_video)
            self.dbm.removeFile2Delete(new_video)  
        
    def clearFiles2DeleteList(self):
        self.files_2_delete.clear()
        
    def removeUnusedFiles(self):
        """remove files which are no longer required; any references to them have been removed from project database.
        If file cannot be removed now, due to it's use by another program perhaps, a reference to it is kept in a database
        table, and another attempt will be made at the program close.
        """
        for pth in self.files_2_delete:
            if isinstance(pth, list):
                pth = pth[1]
            if pth and os.path.exists(pth):
                try:
                    os.remove(pth)
                except:
                    self.dbm.addFile2Delete(pth)
        self.clearFiles2DeleteList()
        
    def removeSentenceVideo(self, video, _id):
        self.dbm.removeSentenceVideo(video, _id)
    
    def signFileIsUsed(self, file_name):
        return self.dbm.signCountByVideo(file_name)
    
    def sentenceFileIsUsed(self, file_name):
        """return number of times this video is used for sentences
        """
        return self.dbm.sentenceVideoUsageCount(file_name)
    
    def extraVideoIsUsed(self, file_name):
        return self.dbm.exVideoUsageCount(file_name)
    
    def extraPictureIsUsed(self, file_name):
        return self.dbm.exPictureUsageCount(file_name)
    
    def getHash(self, filename):
        #NOTE: SELF.DBM.SIGNSBYNAME ?
        _dir = os.path.normpath(os.path.dirname(filename))
        proj_dir = os.path.normpath(os.path.dirname(self.current_project_filename))
        if _dir.startswith(proj_dir):
            return self.dbm.getOriginalHash(filename) # we want the hash from the original file which was imported into SooSL;
            # not the hash of an already converted file
        with open(filename, 'rb') as _file:
            _hash = csaw.hashlib.md5(_file.read()).hexdigest()
        return str(_hash)
    
    def fileInProject(self, pth, _type):
        if pth is None:
            pth = ''
        if os.path.exists(pth):
            # pth from within project directories
            if os.path.normpath(pth).startswith(os.path.normpath(self.getCurrentProjectDir())):
                return pth
            
            return self.getFileByHash(pth, _type) # None returned if no file found
        else:
            return None
    
    def getFileByHash(self, pth, _type):
        _hash = self.getHash(pth)
        if _type == 'ex_media':            
            if self.isPicture(pth):
                _type = 'ex_picture'
            else:
                _type = 'ex_video'
        types = ['sign', 'sent', 'ex_video', 'ex_picture']  
        types.remove(_type)
        types.insert(0, _type)
        _file = ''
        for t in types:         
            if t == 'sign':
                _file = self.dbm.getSignVideoByHash(_hash)
            elif t == 'sent':
                _file = self.dbm.getSentenceVideoByHash(_hash)
            elif t == 'ex_video':
                _file = self.dbm.getExVideoByHash(_hash)
            elif t == 'ex_picture':
                _file = self.dbm.getExPictureByHash(_hash) 
            if _file:
                break
        return _file
    
    def getTypeDir(self, _type, pth):        
        if _type == 'ex_media':
            if self.isPicture(pth):
                _type = 'ex_picture'
            else:
                _type = 'ex_video'
        return self.sign_model.get_root(_type)
        
    def __cannotRemoveMessage(self, pth):
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setText("<p><b>{}</b></p><p>{}</p>".format(qApp.instance().translate('ProjectUpdater', 'Cannot remove file; it is being used'), pth))
        msgBox.setInformativeText(qApp.instance().translate('ProjectUpdater', "Close other programs which may be using the file and try again."))
        t1 = qApp.instance().translate('ProjectUpdater', 'Look for:')
        t2 = qApp.instance().translate('ProjectUpdater', 'Another SooSL window')
        t3 = qApp.instance().translate('ProjectUpdater', 'Video player or picture viewer')
        msgBox.setDetailedText(
            """{}
            1. {}
            2. {}
            """)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setDefaultButton(QMessageBox.Ok)                            
        return msgBox.exec_()        
        
    def removeSign(self, sign_id, gloss_id):
        count = self.dbm.signCountByID(sign_id)
        if count > 1: #can just remove database entries as video is required by other entries
            self.dbm.removeGloss(gloss_id, sign_id, remove_sign=True)
            self.dbm.removeGlossText(gloss_id)
        elif count <= 1: #video only required for this gloss; let's try removing video
            video = self.sign_model.sign_video
            if video:
                pth = video[0][0]
                self.files_2_delete.append(pth)
            self.dbm.removeGloss(gloss_id, sign_id, remove_sign=True)
            self.dbm.removeGlossText(gloss_id) 
            self.dbm.removeSign(sign_id)

    def removeSentence(self, sign_id, gloss_id, sent_id):
        pth = self.dbm.sentenceVideoPath(sent_id)
        count = self.dbm.sentenceVideoUsageCount(pth)
        if count and count > 1: #can just remove database entries as video is required by other entries
            self.dbm.removeSentence(sign_id, gloss_id, sent_id)
        elif not count or count <= 1 and self.ableToEdit(): #video only required for this sentence; let's try removing video
            try:
                full_path = os.path.join(self.sign_model.get_root('sent'), pth)
                self.files_2_delete.append(full_path)
            except:
                pass
            self.dbm.removeSentence(sign_id, gloss_id, sent_id)
                        
    def abortSave(self):
        self.sign_model.abortSave()
            
    def addAmendDialects(self, new_str, old_str, gloss_id, sign_id):
        old = self.dialectsFromStr(old_str)
        new = self.dialectsFromStr(new_str)
        if not old: #new sign
            #dialects, sign_id, gloss_id, sentence_id
            self.addDialects(new, sign_id, gloss_id) #, None)
        else:
            self.amendDialects(old, new, sign_id, gloss_id) #, None)
            #old_dialects, new_dialects, sign_id, gloss_id, sentence_id
            #self.emit(SIGNAL("dialectsAmended"))
            
    def amendGramCats(self, gram_cats, sign_id, gloss_id):
        type_ids = [t[0] for t in self.getAllGramCats() if t in gram_cats]
        for _id in type_ids:
            self.dbm.linkGramCat(_id, sign_id, gloss_id)
            
    def amendComponents(self, new, old, sign_id):
        to_remove = []
        for c in old:
            try:
                new.remove(c)
            except ValueError: #not in new, so needs to be removed
                to_remove.append(c)
        for c in new: #add anything remaining
            self.dbm.addComponent(c, sign_id)
        for c in to_remove:
            self.dbm.removeComponent(c, sign_id)
            
    def amendExVideo(self, media, sign_id):
        pass
                
    def amendExVideos(self, new, old, sign_id):
        to_remove = []
        for media in old:
            try:
                new.remove(media) #remove common filenames
            except:
                to_remove.append(media) #if not in new_filenames, then it is meant for removal
        for media in new: #list should now contain only new filenames
            media2 = copy.deepcopy(media)
            media2.rotation = 0
            media2.crop = None
            media2.transcode_crop = None
            try:
                to_remove.remove(media2)
            except:
                name, _id = self.addExVideo(media.filename, sign_id)
                media.filename = name
                media.id = _id
            else:
                self.amendExVideo(media, sign_id)
        for media in to_remove:
            filename = media.filename
            filename_id = media.id
            self.removeExVideo(filename, filename_id, sign_id)
        return new
            
    def amendExPicture(self, media, sign_id):
        pass       
    
    def amendExPictures(self, new, old, sign_id):
        to_remove = []
        for media in old:
            try:
                new.remove(media) #remove common filenames
            except:
                to_remove.append(media) #if not in new_filenames, then it is meant for removal
        for media in new: #list should now contain only new filenames
            media2 = copy.deepcopy(media)
            media2.rotation = 0
            media2.crop = None
            media2.transcode_crop = None
            try:
                to_remove.remove(media2)
            except:
                name, _id = self.addExPicture(media.filename, sign_id)
                media.filename = name
                media.id = _id
            else:
                self.amendExPicture(media, sign_id)
        for media in to_remove:
            filename = media.filename
            filename_id = media.id
            self.removeExPicture(filename, filename_id, sign_id)
        return new

    def getDestinationFile(self, filename):
        dst = None
        try:
            dst = self.sign_model.media_dest_dict.get(filename).pop(0)
        except:
            pass
        return dst
    
    def setDestinationFile(self, src, dst):
        # a single source media file could potentially be used for more than one destination file                
        new_file_paths = self.sign_model.media_dest_dict.get(src) #need full list if available; can't just use getDestinationFile()
        if not new_file_paths:          
            self.sign_model.media_dest_dict[src] = [dst]
        else:
            new_file_paths.append(dst)
                
    def addExVideo(self, filename, sign_id, gloss_id=None):
        _hash = self.getHash(filename)
        if not _hash:
            _dir = os.path.normpath(os.path.dirname(filename))
            proj_dir = os.path.normpath(os.path.dirname(self.current_project_filename))
            if _dir.startswith(proj_dir):
                _hash = self.dbm.updateEmptyHash(filename)
        video_file = self.getDestinationFile(filename)
        if not video_file:
            video_file = self.getDestinationFile(os.path.normpath(filename))
        if not video_file:
            video_file = filename #not a new file, just moving old one
        _id = self.dbm.addExVideo(video_file, sign_id, gloss_id, _hash)
        return (video_file, _id)
            
    def removeExVideo(self, filename, filename_id, sign_id, gloss_id=0):
        count = self.dbm.countExVideos(filename_id)
        if count <= 1: #video not used by other signs; full delete from database and file system
            self.dbm.removeExVideo(filename_id, sign_id, gloss_id, delete_all=True)
            if self.ableToEdit:
                src_dir = self.sign_model.get_root('ex_video')
                pth = os.path.join(src_dir, filename)
                self.files_2_delete.append(pth)           
        else:
            self.dbm.removeExVideo(filename_id, sign_id, gloss_id, delete_all=False)
            
    def addExPicture(self, filename, sign_id, gloss_id=None):
        _hash = self.getHash(filename)
        if not _hash:
            _dir = os.path.normpath(os.path.dirname(filename))
            proj_dir = os.path.normpath(os.path.dirname(self.current_project_filename))
            if _dir.startswith(proj_dir):
                _hash = self.dbm.updateEmptyHash(filename)
        picture_file = self.getDestinationFile(filename)
        if not picture_file:
            picture_file = self.getDestinationFile(os.path.normpath(filename))
        if not picture_file:
            picture_file = filename #not really a new picture, just moving old one to new sign
        _id = self.dbm.addExPicture(picture_file, sign_id, gloss_id, _hash)
        return (picture_file, _id)
            
    def removeExPicture(self, filename, filename_id, sign_id, gloss_id=0):
        count = self.dbm.countExPictures(filename_id)
        if count <= 1: #picture not used by other signs; full delete from database and file system
            self.dbm.removeExPicture(filename_id, sign_id, gloss_id, delete_all=True)
            if self.ableToEdit:
                src_dir = self.sign_model.get_root('ex_picture')
                pth = os.path.join(src_dir, filename)
                self.files_2_delete.append(pth)          
        else:
            self.dbm.removeExPicture(filename_id, sign_id, gloss_id, delete_all=False)
            
    def addAmendExText(self, new_dict, old_dict, sign_id):
        self.dbm.addAmendExText(new_dict, old_dict, sign_id)
    
    def removeExText(self, sign_id, lang_id):
        self.dbm.removeExText(sign_id, lang_id)
       
    def removeSignVideos(self):
        """remove sign videos if no longer required
        """
        for vp in self.sign_videos_2_remove:
            count = self.dbm.signCountByVideo(vp)
            if  count == -1 and self.ableToEdit: #sign video amended, just remove old video
                self.files_2_delete.append(vp)
            elif count == 0 and self.ableToEdit:
                self.files_2_delete.append(vp)
                self.dbm.removeSign(vp)
        
    def removeSentenceVideos(self):
        """remove sentence videos if no longer required
        """
        for vp in self.sentence_videos_2_remove:
            count = self.dbm.sentenceVideoUsageCount(vp)
            if not count and self.ableToEdit:
                self.files_2_delete.append(vp)
        
    def getSigns(self):
        """return the list of signs stored by the application
        """
        return self.current_signs
    
    def getGramCats(self, sign_id, gloss_id):
        """return a list of sign types for a particular sign
        """
        return self.dbm.getGramCats(sign_id, gloss_id)
    
    def getLangs(self):
        """return languages used for current project
        """
        langs = self.dbm.langs()
        try:
            langs = sorted(langs, key=lambda x:int(x[2]), reverse=False) # put primary at front, based on 'order'
        except:
            try:
                langs = sorted(langs, key=lambda x:x[2], reverse=True) # based on 'focal'
            except:
                pass
        return langs
    
    def getLangById(self, lang_id):
        lang = [l for l in self.getLangs() if l[0] == lang_id]
        if lang:
            return lang[0]
        else:
            return None
    
    def getLangId(self, lang_name):
        _ids = [l[0] for l in self.getLangs() if l[1] == lang_name]
        if _ids:
            return _ids[0]
        else:
            return 1
    
    def getLangName(self, lang_id):
        if self.current_project_filename:
            return self.dbm.name(lang_id)
        return ''
    
    def getLangIds(self):
        langs = self.getLangs()
        return [l[0] for l in langs]
    
    def getProjectLangIds(self):
        langs = self.project.writtenLanguages
        return [l.id for l in langs]
    
    def getProjectLangIds(self):
        langs = self.project.writtenLanguages
        lang_ids = [l.id for l in langs]
        return lang_ids
    
    def getLangOrder(self):
        return self.getLangIds()
    
    def getFocalLang(self):
        """return primary written language (lang__id, lang_name)
        """
        return self.project.focalLang()

    def getFocalLangID(self):
        try:
            return int(self.project.focalLangID)
        except:
            return None
    
    def getDialect(self, _id):
        """return a particular dialect by id
        """
        return [d for d in self.getAllDialects() if d._id == _id][0]
    
    def getAllDialects(self):
        """return dialects for current project
        """
        try:
            return self.dbm.allDialects()
        except:
            return self.project.dialects
    
    def getAllGramCats(self):
        return self.dbm.getAllGramCats()
    
    def getAuthorsMessage(self):
        return '<h3>{}</h3>'.format(self.dbm.getAuthorsMessage())
    
    def getSignDialects(self, sign_id):
        """return all dialects for a given sign
        """
        return self.dbm.getSignDialects(sign_id)
    
    def getFocalDialect(self):
        return self.dbm.getFocalDialect()
    
    def setFocalDialect(self, _id):
        self.dbm.setFocalDialect(_id)
    
    def getGlossDialects(self, sign_id, gloss_id):
        """return dialects for a given sign, gloss
        """
        return self.dbm.getGlossDialects(sign_id, gloss_id)
    
    def getAllGlossDialects(self, gloss_id):
        """return all dialects for a given gloss
        """
        return self.dbm.getAllGlossDialects(gloss_id)
    
    def getExVideos(self, sign_id, gloss_id):
        """return extra videos for a given sign, gloss
        """
        return self.dbm.getExVideos(sign_id, gloss_id)
    
    def getExPictures(self, sign_id, gloss_id):
        """return extra pictures for a given sign, gloss
        """
        return self.dbm.getExPictures(sign_id, gloss_id)
    
    def getExTexts(self, sign_id):
        """return extra text for a given sign, gloss
        """
        return self.dbm.getExTexts(sign_id) 
    
    def getComponents(self, sign_id):
        return self.dbm.getComponents(sign_id)   

    def getSentenceVideoId(self, video_path):
        return self.dbm.sentenceVideoId(video_path)
    
    def getSelectedDialects(self):
        selected = self.selected_dialects
        if not selected:
            selected = self.project.dialects
        return selected
    
    def getAllDeprecatedCodes(self):
        app_dir = qApp.instance().getAppDir()
        dtxt = os.path.join(app_dir, 'codes_deprecate.txt')
        if sys.platform.startswith('darwin'):
            if not os.path.exists(dtxt):
                ccc = os.path.join(os.path.dirname(app_dir), 'Resources', 'codes_deprecate.txt')
        with io.open(dtxt, 'r', encoding='utf-8') as deprecation_file:
            lines = [line for line in deprecation_file.read().splitlines() if not line.startswith('#')]
        deps = []
        for line in lines:
            codes = line.split(',') # may wish to add on same line in future?
            for c in codes:
                deps.append(c)
        return deps
        
    def selectDialects(self, _dialects):
        all_d = self.getAllDialects()
        for d in _dialects:
            _id = int(d[0])
            if _id >= 0:
                if _id == 0:
                    dialect = [a for a in all_d if a.name == d[1]][0]
                else:
                    dialect = Dialect(*d)
                self.selected_dialects.append(dialect)
            else:
                _id = abs(_id)
                self.selected_dialects = [d for d in self.selected_dialects if d._id != _id]
                                            
    def setSelectedDialects(self, dialects):
        self.selected_dialects = dialects
        
    def getEmptyGlosses(self):
        return self.dbm.emptyGlosses()
    
    def getAllGlosses(self):
        """return list of all glosses in current project
        """
        return self.dbm.glosses()
    
    def getGlossesForSign(self, sign_id):
        return self.dbm.getGlosses(sign_id)    
    
    def getAllSentences(self):
        """return list of all sentences (texts) in current project
        """
        return self.dbm.sentenceTexts()
    
    def hasUnglossedSigns(self):
        dialects = self.getSelectedDialects()
        if self.dbm.findUnglossedSigns(dialects):
            return True
        return False
    
    def findUnglossedSigns(self):
        dialects = self.getSelectedDialects()
        self.signs = self.dbm.findUnglossedSigns(dialects)
        if self.signs:
            sign_id = self.signs[0]
            self.sign_model.load(sign_id, None)
        else:
            self.sign_model.load(None, None)
        self.signs_found.emit(self.signs)
        
    def getTextsByMediaFile(self, filename, file_type):
        text_dict = self.dbm.getTextsByMediaFile(filename, file_type)
        return text_dict
    
    def signCountByGloss(self, gloss_id):
        return len(self.dbm.signsByGloss(gloss_id))
    
    def signCountByLang(self, lang_id):
        return self.dbm.signCountByLanguage(lang_id)
    
    def findSignsByGloss(self, gloss_id):
        qApp.instance().searchType = 'gloss'
        dialects = self.getSelectedDialects()
        dialect_ids = []
        if dialects:
            dialect_ids = [d.id for d in dialects]
            
        if isinstance(gloss_id, int):
            self.signs = self.project.getSignsByGloss(gloss_id, dialect_ids)
            
        elif isinstance(gloss_id, list): #list of gloss ids
            self.signs = []
            for _id in gloss_id:
                signs = self.project.getSignsByGloss(_id, dialect_ids)
                self.signs = self.signs + signs
            self.signs = list(set(self.signs)) #remove any duplicates 
        self.signs_found.emit(self.signs)
        
    def findSignsByComponents(self, codes, signal=True):
        qApp.instance().searchType = 'comp'
        qApp.processEvents()
        dialects = self.getSelectedDialects()
        dialect_ids = []
        if dialects:
            dialect_ids = [d.id for d in dialects]
        self.signs = self.project.getSignsByComponent(codes, dialect_ids)
        if self.signs:
            if signal:
                self.signs_found.emit(self.signs)
        else:
            if signal:
                self.signs_found.emit([])
            
    def findSignsByFile(self, filename):
        qApp.instance().searchType = 'file' #'gloss'
        _hash = self.getHash(filename)
        signs = self.dbm.signsByHash(_hash) # external file used before 
        if not signs: 
            signs = self.dbm.signsByName(filename) # file exists within project                     
        if signs:
            self.signs = signs
            self.signs_found.emit(self.signs) 
            return True
        else:
            txt = qApp.instance().translate('ProjectUpdater', "No signs found")
            self.show_info.emit(" ", txt)
            return False     
            
    def senseCountByDialect(self, _id):
        return self.dbm.senseCountByDialect(_id)
        
    def signCountByCode(self, code, dialects):
        dialect_ids = [d.id for d in dialects]
        return self.dbm.signCountByComponent(code, dialect_ids)
    
    def signCountByCode2(self, code, dialects):
        dialect_ids = [d.id for d in dialects]
        return self.project.getSignCountByComponent(code, dialect_ids)
    
    def signCount(self):
        return self.dbm.signCount()
    
    def signCount2(self):
        return self.project.getSignCount()
    
    def countSignsSensesForDialect(self, dialect_id):
        return self.dbm.countSignsSensesForDialect(dialect_id)
    
    def countSignsSensesForLanguage(self, lang_id):   
        return self.dbm.countSignsSensesForLanguage(lang_id) 
    
    def countSignsSensesForGramCat(self, type_id):
        return self.dbm.countSignsSensesForGramCat(type_id)
        
    def signExists(self, filename):
        """returns (_id, path) for a sign if a filename already exists in the project; (None, None) if not
        """
        name = os.path.basename(filename)
        return self.dbm.signExists(name)
    
    def sentenceVideoExists(self, filename):
        """returns (_id, path) for a sentenceVideo if a filename already exists in the project; (None, None) if not
        """
        name = os.path.basename(filename)
        return self.dbm.sentenceVideoExists(name)
    
    def exVideoExists(self, filename):
        """returns (_id, path) for a exVideo if a filename already exists in the project; _id=1 if not
        """
        name = os.path.basename(filename)
        return self.dbm.exVideoExists(name)
    
    def exPictureExists(self, filename):
        """returns (_id, path) for a exPicture if a filename already exists in the project; _id=1 if not
        """
        name = os.path.basename(filename)
        return self.dbm.exPictureExists(name)
    
    def dialectStr(self, dialects):
        dialect_str = ""
        if dialects: #list of dialects
            settings = qApp.instance().getSettings()
            show_focal = settings.value('showFocalDialect', False)
            if isinstance(show_focal, str):
                if show_focal.lower() == 'true':
                    show_focal = True
                else:
                    show_focal = False
            dialects = sorted(dialects, key=lambda x:x.name.lower())
            #dialects = sorted(dialects, key=lambda x:eval(str(x.focal).capitalize()), reverse=True)
            if not show_focal and len(dialects) == 1 and dialects[0].isFocal():
                dialect_str = ""
            else:                          
                abbr = [d.abbr for d in dialects]
                dialect_str = ", ".join(abbr)
        return dialect_str  
    
    def dialectsFromStr(self, dialect_str): 
        dialects = []
        if dialect_str:
            abbrs = [d.strip() for d in dialect_str.split(',')]
            dialects = [d for d in self.getAllDialects() if d.abbr in abbrs]
        return dialects
        
    def showWarning(self, short, long):
        self.show_warning.emit(short, long) 
        
    def showMessage(self, message):  
        self.show_message.emit(message)  
        
    def repairAfterCrash(self, project_dir):
        """repair media after a crash during save operation; if required"""
        pths = []
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                if file.endswith('.old'):
                    pths.append(os.path.join(root, file)) 
        for p in pths:
            new = os.path.splitext(p)[0]
            if os.path.exists(new):
                try:
                    os.remove(new)
                except:
                    pass
                else:
                    os.rename(p, new)
            else:
                os.rename(p, new)
    
    def updateProject(self): 
        """update project database and directories between versions, if required
        """ 
        update = self.dbm.updateDB(csaw.getPermission(True))
        if isinstance(update, tuple) and not update[0]: # update was canceled
            #self.dbm.close()
            return (False, 3)
        elif not update: #attempt to update/open new database with older software
            if self.dbm.projectOlderThan(OLDEST_UPDATABLE): #NOTE: CANNOT UPDATE, POSSIBLY MORE RECENT NUMBER REQUIRED???
                short = qApp.instance().translate('ProjectUpdater', 'Cannot update project')
                long = '<b>{}</b><p>{}</p>'.format(qApp.instance().translate('ProjectUpdater', 'Your project is too old to be opened in  SooSL, but we may still be able to help.'),
                    qApp.instance().translate('ProjectUpdater', 'Please contact us at contact@soosl.net.'))
                self.closeProject()
                self.showWarning(short, long)
                return (False, 1)
            else:
                short = qApp.instance().translate('ProjectUpdater', 'Update SooSL')
                long = '<h3>{}<br></h3>'.format(qApp.instance().translate('ProjectUpdater', 'Please update to a new version of SooSL to open this project.'))
                self.closeProject()
                self.showWarning(short, long)
                return (False, 2)
        else:
            # database now updated to latest version
            project_dir = os.path.dirname(self.dbm.db.databaseName())
            self.repairAfterCrash(project_dir)        
        
            ## update directories for version 0.6.0
                                          
            #make any directories which did not exist in the zip archive on import
            #also, names were changed in v0.6.0, so a tuple represents (old, new)   
            for d in [('citations', 'signs'), 
                      ('explanatory_pictures', 'extra_pictures'),
                      ('explanatory_videos', 'extra_videos'),
                       'sentences']:
                if isinstance(d, tuple):
                    old, new = d
                    old_dir = os.path.join(project_dir, old)
                    new_dir = os.path.join(project_dir, new)
                    if os.path.exists(old_dir):                            
                        os.rename(old_dir, new_dir)
                    elif not os.path.exists(new_dir):
                        os.makedirs(new_dir) 
                else:
                    _dir = os.path.join(project_dir, d)
                    if not os.path.exists(_dir):
                        os.makedirs(_dir)
                        
            #if self.dbm.projectOlderThan('0.8.8'):
            # remove any video/picture files which haven't been removed when signs were deleted
            db_media = self.getProjectFiles()
            if db_media: 
                sign_videos = glob.glob('{}/*'.format(os.path.join(project_dir, 'signs')))
                for video in sign_videos:                        
                    if self.dbm.orphanedFile(video, 'signs'):
                        try:
                            os.remove(video)
                        except:
                            self.dbm.addFile2Delete(video)
                sent_videos = glob.glob('{}/*'.format(os.path.join(project_dir, 'sentences')))
                for video in sent_videos:
                    if self.dbm.orphanedFile(video, 'sentences'):
                        try:
                            os.remove(video)
                        except:
                            self.dbm.addFile2Delete(video)
                ex_videos = glob.glob('{}/*'.format(os.path.join(project_dir, 'extra_videos')))
                for video in ex_videos:
                    if self.dbm.orphanedFile(video, 'extra_videos'):
                        try:
                            os.remove(video)
                        except:
                            self.dbm.addFile2Delete(video)
                ex_picts = glob.glob('{}/*'.format(os.path.join(project_dir, 'extra_pictures')))
                for pict in ex_picts:
                    if self.dbm.orphanedFile(pict, 'extra_pictures'):
                        try:
                            os.remove(pict)
                        except:
                            self.dbm.addFile2Delete(pict)
            return True
        return False
    
    def isVideo(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.video_extensions or \
            (ext == '.gif' and QMovie(filename).frameCount() > 1):
            return True
        return False
        
    def isPicture(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.picture_extensions and ext != '.gif' or \
            (ext == '.gif' and QMovie(filename).frameCount() == 1):
                return True
        return False
    
    def splitFilenameId(self, filename):
        root = os.path.splitext(filename)[0]
        _id = None
        if root.find('_id') != -1:
            _id = root.split('_id')[-1] #should only be one '_id', but to be sure, I want the final one
        return (filename, _id)
        
    def joinFilenameId(self, filename, _id):
        root, ext = os.path.splitext(filename)
        #remove any previously set _id
        if root.find('_id') != -1:
            root = "_id".join(root.split('_id')[:-1]) #I only want to remove final '_id' in the unexpected case there are more than one
        new_filename = "".join([root, '_id{}'.format(_id), ext])
        return new_filename 
    
    def update(self, _filename):
        self.dbm = SooSLDatabaseManager(parent=self)
        _project = self.dbm.openDb(_filename, canedit=True) #fully open initially to allow updating if necessary
        self.current_project_filename = _filename
        self.updateProject()
        authorized = self.__authorizeUser()
        filename = ''
        if _project:
            filename = self.exportProject2Json(_filename)
            if filename:
                _bool = self.__setWritePermission(filename, authorized)
        del self.dbm
        if filename:
            _project = Project(filename) 
            return (_project, filename)
        else:
            return
        
    def stripHtml(self, text):
        #text = text.replace('</p>', '\\n\\n')
        text = text.replace('p, li { white-space: pre-wrap; }', '')
        text = re.sub('<!DOCTYPE[^<]*?>', '', text)
        text = re.sub('<html[^<]*?>', '', text)
        text = re.sub('</html[^<]*?>', '', text)
        text = re.sub('<head[^<]*?>', '', text)
        text = re.sub('</head[^<]*?>', '', text)
        text = re.sub('<meta[^<]*?>', '', text)
        text = re.sub('<style[^<]*?>', '', text)
        text = re.sub('</style[^<]*?>', '', text)
        text = re.sub('<body[^<]*?>', '', text)
        text = re.sub('</body[^<]*?>', '', text)
        text = re.sub('<span[^<]*?>', '', text)
        text = re.sub('</span[^<]*?>', '', text)
        text = re.sub('<br[^<]*?>', '', text)
        text = re.sub('<p[^<]*?>', '', text)
        text = re.sub('</p[^<]*?>', '\n', text)
        text = text.strip()
        return text #QTextDocument(self.dbm.getAuthorsMessage()).toMarkdown(QTextDocument.MarkdownNoHTML)
    
    def exportProject2Json(self, _filename):
        self.current_project_filename = _filename
        pth = qApp.instance().pm.lowerExt(_filename)
        if pth and pth.endswith('.sqlite') and os.path.exists(pth):
                DB_PATH = pth
                JSON_PATH = pth.replace('.sqlite', '.json')
        else:
            return  
        descriptions = ComponentDescriptions()
        descriptions = descriptions.symbol_dict()
        
        soosl_version = self.getProjectVersion()
        sign_language = ''
        if self.__authorizeUser(): # only ask to update this if read/write database
            sign_language = self.getSignLanguage()
        project_name, project_id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(DB_PATH)
        project_description = self.stripHtml(self.dbm.getAuthorsMessage())
         
        o = {}
        o['sooslVersion'] = soosl_version
        o['signLanguage'] = sign_language
        o['projectName'] = project_name
        o['projectId'] = project_id
        o['projectDescription'] = project_description
         
        written_languages = []
        o['writtenLanguages'] = written_languages
        _written_languages = self.getLangs()
        for lang in _written_languages:
            _lang = {}
            written_languages.append(_lang)
            lang_id, name, order = lang
            if not order:
                order = lang_id
            _lang['langId'] = lang_id
            _lang['langName'] = name
            _lang['order'] = order
          
        dialects = []
        o['dialects'] = dialects
        _dialects = self.getAllDialects()
        for d in _dialects: 
            dialect = {}
            dialects.append(dialect)
            dialect['id'] = d._id
            dialect['abbr'] = d.abbr
            _bool = True
            if d.focal == 'false' or str(d.focal) == '0':
                _bool = False
            dialect['focal'] = _bool
            dialect['name'] = d.name
            
        grammar_categories = []
        o['grammarCategories'] = grammar_categories
        gram_cats = self.getAllGramCats()
        for gc in gram_cats:
            _gc = {}
            grammar_categories.append(_gc)
            _gc['id'] = gc[0]
            _gc['name'] = gc[1]
           
        signs = []
        o['signs'] = signs
           
        sign_ids = self.dbm.signIds()
        for sign_id in sign_ids:
            sign = {}
            signs.append(sign)
            self.sign_model.load(sign_id, None, reset_model=False)
            _filename = self.sign_model.sign_video[0].filename
            media = os.path.basename(_filename)
            _hash = self.dbm.getOriginalHash(_filename)
            sign['id'] = sign_id
            sign['path'] = '/signs/{}'.format(media)
            sign['hash'] = _hash
            component_codes = []
            sign['componentCodes'] = component_codes            
            for c in self.sign_model.component_list:
                component_codes.append(c)
   
            senses = []
            sign['senses'] = senses
            for _sense in self.sign_model.gloss_list:
                sense = {}
                senses.append(sense)
                sense_id = _sense.get(0)
                sense['id'] = sense_id
                dialect_ids = []
                sense['dialectIds'] = dialect_ids                
                _dialects = self.sign_model.dialect_dict.get(sense_id)
                for d in _dialects: 
                    dialect_ids.append(d._id)
                
                gc = self.sign_model.gram_cat_dict.get(sense_id, None) #grammar category
                sense['grammarCategoryId'] = None
                if gc:
                    sense['grammarCategoryId'] = gc[0][0]
                    
                gloss_texts = []
                sense['glossTexts'] = gloss_texts 
                values = list(_sense.values())[1:]
                for v in values:
                    if v:              
                        for lang in _written_languages:
                            gloss_text = {}
                            gloss_texts.append(gloss_text)
                            lang_id, name, order = lang
                            text = _sense.get(lang_id)
                            gloss_text['langId'] = lang_id
                            if not text:
                                text = ''
                            gloss_text['text'] = text
                        break
                   
                sentences = []
                sense['sentences'] = sentences
                _sentences = self.sign_model.sentence_dict.get(sense_id)
                for sent in _sentences:
                    sentence = {}
                    sentences.append(sentence)
                    _filename = sent[1][1].filename
                    _hash = self.dbm.getOriginalHash(_filename)
                    media = os.path.basename(_filename)
                    sent_id = sent[1][0]
                    sentence['id'] = sent_id
                    sentence['path'] = '/sentences/{}'.format(media)
                    sentence['hash'] = _hash
                    text_dict = sent[2]
                    sentence_texts = []
                    sentence['sentenceTexts'] = sentence_texts
                    for lang in _written_languages:
                        sent_text = {}
                        sentence_texts.append(sent_text)
                        lang_id, name, order = lang
                        text = text_dict.get(lang_id)
                        sent_text['langId'] = lang_id
                        if not text:
                            text = ''
                        sent_text['text'] = text 
                           
            extra_media = []
            sign['extraMediaFiles'] = extra_media
            for media in self.sign_model.extra_videos:
                ex_media = {}
                extra_media.append(ex_media)
                dir = 'extra_videos'
                ex_media['id'] = media.id
                _path = '/{}/{}'.format(dir, os.path.basename(media.filename))
                ex_media['path'] = _path
                ex_media['hash'] = self.dbm.getOriginalHash(_path)
            for media in self.sign_model.extra_pictures:
                ex_media = {}
                extra_media.append(ex_media)
                dir = 'extra_pictures'
                ex_media['id'] = media.id
                _path = '/{}/{}'.format(dir, os.path.basename(media.filename))
                ex_media['path'] = _path
                ex_media['hash'] = self.dbm.getOriginalHash(_path)
            extra_texts = []  
            sign['extraTexts'] = extra_texts
            values = list(self.sign_model.extra_text_dict.values())
            for v in values:
                if v:
                    for lang in _written_languages:
                        extra_text = {}
                        extra_texts.append(extra_text)
                        lang_id, name, order = lang
                        _extra_text = self.sign_model.extra_text_dict.get(lang_id)
                        extra_text['langId'] = lang_id
                        if not _extra_text:
                            _extra_text = ''
                        extra_text['text'] = _extra_text
                break 
        
        self.closeProject(emit=False) #close project or filename/directory cannot be updated (renamed)
        if project_name != project_id:
            try:
                JSON_PATH = self.__updateFilename(JSON_PATH, project_id, project_name)
            except:
                return  
        with codecs.open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)
            
        return JSON_PATH
    
    def __updateFilename(self, filename, project_id, project_name):
        """ With version 0.9.0 filename is based on a slugified version of the project name,
        instead of the project name itself; this converts the old style to the new. """
        #rename project directory
        old_dir = os.path.dirname(filename).replace('\\', '/')
        base_dir = os.path.dirname(old_dir).replace('\\', '/')
        new_dir = '{0}/{1}'.format(base_dir, project_id)
        new_filename = '{0}/{1}.json'.format(new_dir, project_id)
        if os.path.exists(new_filename): #case when copying on import
            orig_id = project_id
            count = 2
            while os.path.exists(new_filename):
                project_id = '{}-{}'.format(orig_id, count)
                new_dir = '{0}/{1}'.format(base_dir, project_id)
                new_filename = '{0}/{1}.json'.format(new_dir, project_id)
                count += 1
        ## all this just to force Windows to change a capitalized directory to lower case
        if project_id == project_name.lower():
            count = 1
            new_dir = '{0}/{1}-{2}'.format(base_dir, project_id, count)
            while os.path.exists(new_dir): #just in case we've renamed it to another existing directory
                count += 1
                new_dir = '{0}/{1}-{2}'.format(base_dir, project_id, count)
            #new_filename = '{0}/{1}-{2}.json'.format(new_dir, project_id, count)
        os.rename(old_dir, new_dir)
        os.rename(new_dir, os.path.dirname(new_filename))
        return new_filename
        
    @property
    def video_filter(self):
        return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectUpdater', "Videos"), " *".join(self.video_extensions), qApp.instance().translate('ProjectUpdater', 'All files'))
    
    @property
    def picture_filter(self):
        return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectUpdater', 'Pictures'), " *".join(self.picture_extensions), qApp.instance().translate('ProjectUpdater', 'All files'))
    
    @property
    def media_filter(self):
        return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectUpdater', "Videos or Pictures"), " *".join(self.media_extensions), 
                                                     qApp.instance().translate('ProjectUpdater', 'All files'))
            
    ##TODO: probably only keep the most used extension (and obviously the ones supported by
    ## SooSL (VLC; obscure ones needed by users could be amended to list? in configuration?    
    #source: http://www.fileinfo.com/filetypes/
    @property
    def media_extensions(self):
        return self.video_extensions + self.picture_extensions
    
    
    @property
    def video_extensions(self):
        return ['.264', '.3g2', '.3gp', '.3gp2', '.3gpp', '.3gpp2', '.3mm',
                '.3p2', '.60d', '.787', '.aaf', '.aep', '.aepx', '.aet', 
                '.aetx', '.ajp', '.amv', '.amx', '.arf', '.asf', '.asx', '.avb', 
                '.avd', '.avi', '.avs', '.avs', '.axm', '.bdm', '.bdmv', '.bik', 
                '.bin', '.bix', '.bmk', '.box', '.bs4', '.bsf', '.byu', '.camproj', 
                '.camrec', '.clpi', '.cmmp', '.cmmtpl', '.cmproj', '.cmrec', 
                '.cpi', '.cvc', '.d2v', '.d3v', '.dat', '.dav', '.dce', '.dck', 
                '.ddat', '.dif', '.dir', '.divx', '.dlx', '.dmb', '.dmsm', 
                '.dmsm3d', '.dmss', '.dnc', '.dpg', '.dream', '.dsy', '.dv', 
                '.dv-avi', '.dv4', '.dvdmedia', '.dvr-ms', '.dvx', '.dxr', '.dzm', 
                '.dzp', '.dzt', '.evo', '.eye', '.f4p', '.f4v', '.fbr', '.fbr', 
                '.fbz', '.fcp', '.flc', '.flh', '.fli', '.flv', '.flx', '.gl', 
                '.grasp', '.gts', '.gvi', '.gvp', '.h264', '.hdmov', '.hkm', '.ifo', 
                '.imovieproj', '.imovieproject', '.iva', '.ivf', '.ivr', '.ivs', 
                '.izz', '.izzy', '.jts', '.lsf', '.lsx', '.m15', '.m1pg', '.m1v', 
                '.m21', '.m21', '.m2a', '.m2p', '.m2t', '.m2ts', '.m2v', '.m4e', 
                '.m4u', '.m4v', '.m75', '.meta', '.mgv', '.mj2', '.mjp', '.mjpg', 
                '.mkv', '.mmv', '.mnv', '.mod', '.modd', '.moff', '.moi', '.moov', 
                '.mov', '.movie', '.mp21', '.mp21', '.mp2v', '.mp4', '.mp4v', 
                '.mpe', '.mpeg', '.mpeg4', '.mpf', '.mpg', '.mpg2', '.mpgindex', 
                '.mpl', '.mpls', '.mpsub', '.mpv', '.mpv2', '.mqv', '.msdvd', 
                '.msh', '.mswmm', '.mts', '.mtv', '.mvb', '.mvc', '.mvd', '.mve', 
                '.mvp', '.mxf', '.mys', '.ncor', '.nsv', '.nuv', '.nvc', '.ogm', 
                '.ogv', '.ogx', '.osp', '.par', '.pds', '.pgi', '.piv', '.playlist', 
                '.pmf', '.prel', '.pro', '.prproj', '.psh', '.pssd', '.pva', '.pvr', 
                '.pxv', '.qt', '.qtch', '.qtl', '.qtm', '.qtz', '.r3d', '.rcproject', 
                '.rdb', '.rec', '.rm', '.rmd', '.rmp', '.rms', '.rmvb', '.roq', 
                '.rp', '.rts', '.rts', '.rum', '.rv', '.sbk', '.sbt', '.scm', 
                '.scm', '.scn', '.sec', '.seq', '.sfvidcap', '.smi', '.smil', 
                '.smk', '.sml', '.smv', '.spl', '.srt', '.ssm', '.str', '.stx', 
                '.svi', '.swf', '.swi', '.swt', '.tda3mt', '.tivo', '.tix', '.tod', 
                '.tp', '.tp0', '.tpd', '.tpr', '.trp', '.ts', '.tvs', '.vc1', 
                '.vcpf', '.vcr', '.vcv', '.vdo', '.vdr', '.veg', '.vem', '.vf', 
                '.vfw', '.vfz', '.vgz', '.vid', '.viewlet', '.viv', '.vivo', '.vlab', 
                '.vob', '.vp3', '.vp6', '.vp7', '.vpj', '.vro', '.vs4', '.vse', '.vsp', 
                '.w32', '.wcp', '.webm', '.wlmp', '.wm', '.wmd', '.wmmp', '.wmv', 
                '.wmx', '.wp3', '.wpl', '.wtv', '.wvx', '.xfl', '.xvid', '.yuv', 
                '.zm1', '.zm2', '.zm3', '.zmv']
    
    @property            
    def picture_extensions(self):
        return ['.001', '.2bp', '.411', '.8pbs', '.8xi', '.abm', '.acr', '.adc', 
                '.afx', '.agif', '.agp', '.aic', '.ais', '.albm', '.apd', '.apm', 
                '.apng', '.arr', '.art', '.artwork', '.arw', '.arw', '.asw', 
                '.avatar', '.awd', '.awd', '.blkrt', '.blz', '.bm2', '.bmc', 
                '.bmf', '.bmp', '.brk', '.brt', '.c4', '.cal', '.cals', '.cam', 
                '.can', '.cd5', '.cdc', '.cdg', '.ce', '.cimg', '.cin', '.cit', 
                '.cpc', '.cpd', '.cpg', '.cps', '.cpt', '.cpx', '.cr2', '.crw', 
                '.csf', '.ct', '.cut', '.dcm', '.dcr', '.dcx', '.ddb', '.dds', 
                '.dib', '.djv', '.djvu', '.dng', '.dpx', '.dt2', '.dtw', '.dvl', 
                '.ecw', '.erf', '.exr', '.fac', '.face', '.fal', '.fax', '.fbm', 
                '.fil', '.fits', '.fpg', '.fpx', '.frm', '.gbr', '.gfb', '.gif', 
                '.gih', '.gim', '.gmbck', '.gp4', '.gpd', '.gro', '.grob', '.gry', 
                '.hdp', '.hdr', '.hf', '.hpi', '.hr', '.hrf', '.ic1', '.ic2', '.ic3', 
                '.ica', '.icb', '.icn', '.icon', '.ilbm', '.img', '.imj', '.info', 
                '.ink', '.int', '.ipx', '.itc2', '.ithmb', '.ivr', '.j', '.j2c', 
                '.j2k', '.jas', '.jb2', '.jbf', '.jbig', '.jbmp', '.jbr', '.jfi', 
                '.jfif', '.jia', '.jif', '.jiff', '.jng', '.jp2', '.jpc', '.jpd', 
                '.jpe', '.jpeg', '.jpf', '.jpg', '.jps', '.jpx', '.jtf', '.jwl', 
                '.jxr', '.kdc', '.kdk', '.kfx', '.kic', '.kodak', '.kpg', '.lbm', 
                '.mac', '.mat', '.max', '.mbm', '.mcs', '.mef', '.met', '.mic', 
                '.mip', '.mix', '.mng', '.mnr', '.mos', '.mpf', '.mrb', '.mrw', 
                '.msk', '.msp', '.ncd', '.ncr', '.nct', '.nef', '.neo', '.nrw', 
                '.odi', '.omf', '.orf', '.ota', '.otb', '.oti', '.pac', '.pal', 
                '.pap', '.pat', '.pbm', '.pc1', '.pc2', '.pc3', '.pcd', '.pcx', 
                '.pdd', '.pdn', '.pe4', '.pe4', '.pef', '.pfr', '.pgm', '.pi1', 
                '.pi2', '.pi2', '.pi3', '.pi4', '.pi5', '.pi6', '.pic', '.pic', 
                '.pic', '.picnc', '.pict', '.pictclipping', '.pix', '.pix', '.pm', 
                '.pm3', '.pmg', '.png', '.pni', '.pnm', '.pnt', '.pntg', '.pov', 
                '.pov', '.pp4', '.pp5', '.ppf', '.ppm', '.prw', '.psb', '.psd', 
                '.psf', '.psp', '.pspbrush', '.pspimage', '.ptg', '.ptx', '.ptx', 
                '.pvr', '.pwp', '.px', '.pxm', '.pxr', '.pzp', '.qif', '.qti', 
                '.qtif', '.raf', '.ras', '.raw', '.rgb', '.rgb', '.ric', '.rif', 
                '.riff', '.rix', '.rle', '.rsb', '.rsr', '.rw2', '.s2mv', '.sar', 
                '.scg', '.sci', '.scp', '.sct', '.scu', '.sdr', '.sff', '.sfw', 
                '.sgi', '.shg', '.sid', '.sig', '.sim', '.skitch', '.sld', '.smp', 
                '.spc', '.spe', '.spiff', '.spp', '.spr', '.spu', '.sr', '.sr2', 
                '.srf', '.ste', '.sumo', '.sun', '.suniff', '.sup', '.sva', '.svg', '.t2b', 
                '.taac', '.tb0', '.tex', '.tg4', '.tga', '.thm', '.thm', '.thumb', 
                '.tif', '.tif', '.tiff', '.tjp', '.tn1', '.tn2', '.tn3', '.tny', 
                '.tpi', '.trif', '.u', '.ufo', '.urt', '.v', '.vda', '.vff', '.vic', 
                '.viff', '.vna', '.vss', '.vst', '.wb1', '.wbc', '.wbd', '.wbm', 
                '.wbmp', '.wbz', '.wdp', '.web', '.wi', '.wic', '.wmp', '.wvl', 
                '.x3f', '.xbm', '.xcf', '.xpm', '.xwd', '.y', '.yuv', '.zif']
        
    def get_location_codes(self, sign):
        codes = sign.component_codes
        location_codes = [c for c in codes if (eval("0x{}".format(c)) >= eval("0x500") and \
                          eval("0x{}".format(c)) < eval("0x1000"))]
        return location_codes
    
    def get_non_location_codes(self, sign):
        """returns non-location codes"""
        codes = sign.component_codes
        non_location_codes = [c for c in codes if (eval("0x{}".format(c)) < eval("0x500") or \
                            eval("0x{}".format(c)) >= eval("0x1000"))]
        return non_location_codes
    
class SignLanguageRequestDialog(QInputDialog):
    def __init__(self, project_filename):
        _parent = qApp.instance().getMainWindow()
        super(SignLanguageRequestDialog, self).__init__(parent=_parent)
        flags = self.windowFlags() & (~Qt.WindowContextHelpButtonHint)
        self.setWindowFlags(flags)
        self.setStyleSheet('QLabel{color:blue;}')
        self.setLabelText(qApp.instance().translate('SignLanguageRequestDialog', "SIGN LANGUAGE WHAT?"))
        self.setWindowTitle(qApp.instance().pm.getProjectNameIdVersionDatetime(project_filename)[0])
        
    def sizeHint(self):
        fm = self.fontMetrics()
        title = self.windowTitle()
        w = fm.width(title) + 150
        h = self.height()
        return QSize(int(w), int(h))

# if __name__ == '__main__': # just start SooSL
#     from mainwindow import main
#     main()
