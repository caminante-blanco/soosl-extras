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
import shutil
import json
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import io
import copy
import stat
import glob
from datetime import datetime, timezone
from dateutil import parser
#from collections import OrderedDict
# As of Python version 3.7, dictionaries are ordered; don't need above import using 3.8

from PyQt5.QtCore import QDir, QObject, Qt
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QProgressDialog

from media_object import MediaObject

from pprint import pprint        

MIN_SOOSL_VERSION = '0.9.4' # oldest version of SooSL that can open this json project.
# (doesn't affect old sqlite projects as they will be updated to latest json version.)

# lists of attributes used as keys in self.jsn including version in which they were added
# these lists are mainly for documentation, but can also be used to enforce an order on the json file output (see self.updateProject)
# NOTE: If an attribute name is changed or added, make sure code in self.updateProject() is also modified
# NOTE: Also, modify project_manager.newJson()
project_attributes = [
    'projectName', #0.9.0
    'signLanguage', #0.9.0
    'projectId', #0.9.0
    'timeStamp', #0.9.1; seconds since December 4, 2020 UTC, the SooSL "epoch" when this was first added
    'versionId', #0.9.1; a string identifying the version of this project
    'creationDateTime', #0.9.1; date and time of project creation, UTC, ISO 8601 format
    'modifiedDateTime', #0.9.1; date and time of last modification, UTC, ISO 8601 format
    'sooslVersion', # 0.9.0; version of SooSL which created this project
    # as of 0.9.1 the version which last modified this project file.
    'minSooSLVersion', # oldest version of SooSL that can open this project.
    'projectCreator', # new in 0.9.4
    'projectDescription', #0.9.0
    'writtenLanguages', #0.9.0
    'dialects', #0.9.0
    'grammarCategories', #0.9.0
    'signs' #0.9.0
    ]

written_language_attributes = [
    'langId', #0.9.0
    'langName', #0.9.0
    'order' #0.9.0
    ]

dialect_attributes = [
    'id', #0.9.0
    'name', #0.9.0
    'abbr', #0.9.0
    'focal', #0.9.0
    ]

grammar_category_attributes = [
    'id', #0.9.0
    'name', #0.9.0
    ]

sign_attributes = [
    'id', #0.9.0
    'modifiedDateTime', #0.9.1
    'path', #0.9.0; path to video file
    'hash', #0.9.0; hash of original video to identify reuse of video
    'componentCodes', #0.9.0
    'senses', #0.9.0
    'extraMediaFiles', #0.9.0
    'extraTexts', #0.9.0
    ]

sense_attributes = [
    'id', #0.9.0
    'dialectIds', #0.9.0
    'grammarCategoryId', #0.9.0
    'glossTexts', #0.9.0
    'sentences' #0.9.0
    ]

sentence_attributes = [
    'id', #0.9.0
    'path', #0.9.0
    'hash', #0.9.0; hash of original video to identify reuse of video
    'sentenceTexts' #0.9.0
    ]

gloss_text_attributes = [
    'langId', #0.9.0
    'text' #0.9.0
    ]

sentence_text_attributes = [
    'langId', #0.9.0
    'text' #0.9.0
    ]

extra_text_attributes = [
    'langId', #0.9.0
    'text' #0.9.0
    ]

extra_media_file_attributes = [
    'id', #0.9.0
    'path', #0.9.0
    'hash' #0.9.0; hash of original video to identify reuse of video
    ]

## FULL PROJECT STRUCTURE:
# projectName
#     signLanguage
#     projectId
#     timeStamp
#     versionId'
#     creationDateTime
#     modifiedDateTime
#     sooslVersion
#     minSooSLVersion
#     projectCreator    
#     projectDescription
#     writtenLanguages
#         langId
#         langName
#         order
#     dialects
#         id
#         name
#         abbr
#         focal
#     grammarCategories
#         id
#         name
#     signs
#         id
#         modifiedDateTime
#         path
#         hash
#         componentCodes
#         senses
#             id
#             dialectIds
#             grammarCategoryId
#             glossTexts
#                 langId
#                 text
#             sentences
#                 id
#                 path
#                 hash
#                 sentenceTexts
#                     langId
#                     text
#         extraMediaFiles
#            id
#            path
#            hash
#         extraTexts
#            langId
#            text

def findPathById(path):
    if not path or os.path.exists(path) or os.path.exists(path.replace('/merge/', '/')):
        return path 
    #print('No:', path)       
    # difficulty with (e.g. Arabic) filenames; find file by id
    _id = os.path.splitext(path)[0].split('_id')[-1]
    _dir = os.path.dirname(path)
    paths = glob.glob(f"{_dir}/*_id{_id}.*")
    if paths:
        #print('Yes:', paths[0].replace('\\', '/'))
        return paths[0].replace('\\', '/')
    return ''

class ZooZLProject(QObject):
    def __init__(self, zoozl_file, canedit=False, update_jsn=True):
        super(ZooZLProject, self).__init__()

        names = []
        with ZipFile(zoozl_file) as archive:
            names = archive.namelist()
        for name in names:
            print(name)

class Project(QObject):
    def __init__(self, json_file, canedit=False, update_jsn=True):
        super(Project, self).__init__()
        self.json_file = json_file.replace('\\', '/')
        self.project_updates = False
        self.old_sense_ids = []
        try:
            mw = qApp.instance().getMainWindow()
        except:
            mw = None
        self.progress = QProgressDialog(parent=mw, flags=Qt.WindowTitleHint)
        self.progress.setCancelButton(None)
        self.progress.setWindowTitle('Opening Dictionary')
        self.progress.setMinimum(0)
        txt = qApp.instance().translate('Project', 'Opening dictionary...')
        self.progress.setLabelText(f"<b>{txt}</b><br><p style='color:blue; text-align:left;'>{json_file}</p>") 
        #self.progress.forceShow()
        self.progress.setValue(0)
        qApp.processEvents()

        writable_location = self.isWritableLocation(json_file)
        if not writable_location:
            update_jsn = False
        self.jsn = self.getJsn(update=update_jsn) #False when simply refreshing project

        self.sense_ids_changed = False
        self.ignore_duplicate_sense_id_check = False
        if self.jsn:
            self.writePermission = qApp.instance().pm.isReadWrite(json_file)
            if not writable_location:
                self.writePermission = False
                title = ' ' #qApp.instance().translate('Project', 'Read-only permission')
                t2 = qApp.instance().translate('Project', 'SooSL cannot get read-write permission for this dictionary:')
                t3 = qApp.instance().translate('Project', 'SooSL will open this dictionary as read-only.')
                t4 = qApp.instance().translate('Project', 'You will not be able to edit it.')
                msg = f'<b>{t2}</b><br><br><span style="color:blue;">{self.json_file}</span><br><br>{t3}<br>{t4}<br><br>'
                t5 = qApp.instance().translate('Project', 'Maybe the file, folder or network share is read-only?')
                if sys.platform.startswith("win") and qApp.instance().win32ControlledFolderAccessEnabled():
                    protected_folders = qApp.instance().win32ProtectedFolders()
                    for folder in protected_folders:
                        try:
                            if os.path.commonpath([folder, self.json_file]):
                                a = qApp.instance().translate('Project', "You have 'Controlled folder access' enabled and this folder is protected.")
                                b = qApp.instance().translate('Project', "Allow SooSL through 'Controlled folder access' in 'Settings' to avoid further errors.")                                
                                c = qApp.instance().translate('Project',  "Then close and restart SooSL.")
                                t5 = f'{a}<br>{b} ({sys.executable})<br><br><b>{c}</b>'
                                break
                        except ValueError:
                            pass # ValueError: Paths don't have the same drive
                            # this is okay as folder compared will defo not be in the protected folder path
                msg = f'{msg}{t5}<br>'   
                qApp.instance().pm.show_warning.emit(title, msg)
            self.soosl_version = self.jsn.get('sooslVersion') # version of SooSL which last updated project
            self.sign_language = self.jsn.get('signLanguage', '')
            self.name = self.jsn.get('projectName')
            self.id = self.jsn.get('projectId')
            self.version_id = self.jsn.get('versionId', '')
            self.last_save_datetime = self.jsn.get('modifiedDateTime', '')
            self.project_creator = self.jsn.get('projectCreator', '')
            self.description = self.jsn.get('projectDescription', '')
            
            dialects = self.jsn.get('dialects')
            if not dialects: dialects = []
            self.dialects = [Dialect(d) for d in dialects]
            self.selected_dialect_ids = [d.id for d in self.dialects]
            
            grammar_categories = self.jsn.get('grammarCategories')
            if not grammar_categories: grammar_categories = []
            self.grammar_categories = [GrammarCategory(gc) for gc in grammar_categories]
            self.grammar_categories = sorted(self.grammar_categories, key=lambda x:x.name)
            
            writtenLanguages = self.jsn.get('writtenLanguages')
            if writtenLanguages:
                settings = qApp.instance().getSettings()
                for wl in writtenLanguages:
                    user_order = settings.value(f"ProjectSettings/{json_file}/{wl.get('langName')}/order")
                    if user_order: #overide json order with user setting, if any
                        wl['order'] = int(user_order)
                writtenLanguages.sort(key=lambda x:int(x.get('order')), reverse=False) # put primary at front, based on 'order'
            else: 
                writtenLanguages = []
            self.writtenLanguages = [WrittenLanguage(wl) for wl in writtenLanguages]

            # lang_ids = [l.id for l in self.writtenLanguages]            
            # qApp.instance().pm.lang_order_change.emit(lang_ids) 
            
            signs = self.jsn.get('signs')
            if not signs: 
                signs = [] 
            project_dir = os.path.dirname(self.json_file)
            self.signs = []
            if writable_location: # won't be able to make following updates if not
                for sign_data in signs:
                    # test for errors in signs              
                    if sign_data.get('new') or \
                        sign_data.get('path', '') in ['', '/']: # process any error conditions; remove
                            sign_id = sign_data.get('id') 
                            if sign_id:
                                sign_dir = f'{project_dir}/_signs'
                                _dir = QDir(sign_dir)
                                _dir.setFilter(QDir.Files)
                                entries = [f for f in _dir.entryList() if f.lower().endswith('.json')]
                                sign_paths = [x for x in list(map(lambda x: _dir.absoluteFilePath(x), entries)) if x.endswith(f'{sign_id}.json')]
                                if sign_paths:
                                    sign_path = sign_paths[0]
                                    lock_path = f'{sign_path}.lock' 
                                    if os.path.exists(lock_path):
                                        os.remove(lock_path)
                                    if os.path.exists(sign_path):
                                        os.remove(sign_path)
                    else: 
                        sign = Sign(self, sign_data)
                        updated = False
                        if self.sense_ids_changed: # updates to sign need to be written to sign file on disk
                            self.updateSignFile(sign)
                            self.sense_ids_changed = False
                            updated = True
                        ### Updates in 0.9.4 to cleanup empty glossText, sentenceText and extraText in files ###
                        elif sign.extra_texts and [t.get('text', '') for t in sign_data.get('extraTexts', []) if not t.get('text', '')]:
                            self.updateSignFile(sign)
                            updated = True
                        elif sign.extra_media_files and sorted(sign.extra_media_files, key=lambda x: (self.__mediaOrder(x.path), x.id)) != sign.extra_media_files:
                            # sort by video(0) or picture(1), then by id
                            # https://stackoverflow.com/questions/4233476/sort-a-list-by-multiple-attributes
                            self.updateSignFile(sign)
                            updated = True
                        if not updated:
                            for sense in sign_data.get('senses', []):
                                if sense.get('glossTexts', []) and [t.get('text', '') for t in sense.get('glossTexts', []) if not t.get('text', '')]:
                                    self.updateSignFile(sign) 
                                    updated = True
                                    break
                                elif sorted([t.get('langId') for t in sense.get('glossTexts', [])]) != [t.get('langId') for t in sense.get('glossTexts', [])]:
                                    self.updateSignFile(sign)
                                    updated = True
                                    break
                                elif sorted(sense.get('dialectIds', [])) != sense.get('dialectIds', []):
                                    self.updateSignFile(sign)
                                    updated = True
                                    break
                        ##########################################################################################
                        self.signs.append(sign)
                self.signs.sort(key = lambda x: int(x.id))

                if self.project_updates:
                    self.updateProject()
            else: # sign data won't have been added or updated before
                self.addSignData(self.jsn)
                signs = self.jsn.get('signs', [])
                for sign_data in signs:
                    sign = Sign(self, sign_data)
                    self.signs.append(sign)
                self.signs.sort(key = lambda x: int(x.id))
        self.progress.close()

    def __mediaOrder(self, path):
        if qApp.instance().pm.isVideo(path):
            return 0
        return 1

    def needsMergeReconciled(self):
        if os.path.exists(self.merge_dir):
            return True
        return False
                
    def isWritableLocation(self, json_file):
        _dir = os.path.dirname(json_file)
        test_dir = f'{_dir}/test'
        try:
            os.mkdir(test_dir)
        except:
            if os.path.exists(test_dir):
                self.thread().msleep(200)
                try:
                    os.rmdir(test_dir)
                except:
                    qApp.instance().pm.addPossibleRemoval(test_dir)
                return True # written on some previous attempt
            else:
                return False # cannot write to this location
        else:
            # lets try to write a file also
            test = f'{test_dir}/test.txt'
            try:                
                with open(test, 'w') as f:
                    f.write('test text')
            except:
                try:
                    os.rmdir(test_dir)
                except:
                    qApp.instance().pm.addPossibleRemoval(test_dir)
                return False
            else:
                try:
                    os.remove(test)
                except:
                    qApp.instance().pm.addPossibleRemoval(test)
                try:
                    os.rmdir(test_dir)
                except:
                    qApp.instance().pm.addPossibleRemoval(test_dir)
                return True

    @property
    def filename(self):
        return self.json_file
        
    @property
    def project_dir(self):
        proj_dir = os.path.dirname(self.json_file).replace('\\', '/')
        return proj_dir

    @property
    def merge_dir(self):
        return f'{self.project_dir}/merge'
    
    def attributeOrder(self, attribute, attribute_list):
        # The order is the index of the attribute in the list of attributes
        try:
            order = attribute_list.index(attribute) + 1 # indexes are zero based, so bump it up by 1; not strictly necessary
        except:
            # unknown parameter; just place at the start
            return 0
        else:
            return order    

    def sortDictInplace(self, _dict, attributes):
        sorted_items = sorted(_dict.items(), key=lambda x:self.attributeOrder(x[0], attributes))
        _dict.clear()
        _dict.update(sorted_items)

    def sortSignJsn(self, sign_jsn):
        # sorts sign attributes inplace
        # attributes are sorted according to their position (index) in their attribute list
        if sign_attributes != list(sign_jsn.keys()):
            self.sortDictInplace(sign_jsn, sign_attributes)
            senses = sign_jsn.get('senses', [])
            for sense in senses:
                self.sortDictInplace(sense, sense_attributes)
                gloss_texts = sense.get('glossTexts', [])
                for text in gloss_texts:
                    self.sortDictInplace(text, gloss_text_attributes)
                sentences = sense.get('sentences', [])
                for sentence in sentences:
                    self.sortDictInplace(sentence, sentence_attributes)
                    sentence_texts = sentence.get('sentenceTexts', [])
                    for text in sentence_texts:
                        self.sortDictInplace(text, sentence_text_attributes)
            extra_media = sign_jsn.get('extraMediaFiles', [])
            for media in extra_media:
                self.sortDictInplace(media, extra_media_file_attributes)
            extra_texts = sign_jsn.get('extraTexts', [])
            for text in extra_texts:
                self.sortDictInplace(text, extra_text_attributes)

    def sortProjectJsn(self, project_jsn):
        # sorts project attributes inplace
        # attributes are sorted according to their position (index) in their attribute list
        self.sortDictInplace(project_jsn, project_attributes)
        written_langs = project_jsn.get('writtenLanguages', [])
        for lang in written_langs:
            self.sortDictInplace(lang, written_language_attributes)
        dialects = project_jsn.get('dialects', [])
        for dialect in dialects:
            self.sortDictInplace(dialect, dialect_attributes)
        categories = project_jsn.get('grammarCategories', [])
        for cat in categories:
            self.sortDictInplace(cat, grammar_category_attributes)
        signs = project_jsn.get('signs', [])
        for sign in signs: # if there are signs with the project file, sort them also
            self.sortSignJsn(sign)       

    def getFullProjectFileForExport(self):
        ## exporting requires a project file which includes project data plus all sign data;
        ## paths and attributes should also be revertered to compatibility with 0.9.0;
        ## 0.9.0 was the first SooSL version to use JSON file format for projects
        proj_name = os.path.basename(self.filename)
        tmp_dir = qApp.instance().getTempDir()
        tmp_proj_pth = os.path.join(tmp_dir, proj_name)
        f = io.open(tmp_proj_pth, 'w', encoding='utf-8')
        f.close()
        # write json out to file 
        jsn = copy.deepcopy(self.jsn)
        self.sortProjectJsn(jsn)
        jsn = self.__getCompatibleJsn(jsn)
        write = True
        f =  io.open(tmp_proj_pth, 'w', encoding='utf-8')
        json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False) 
        f.flush()
        f.close()
        return tmp_proj_pth

    def __getCompatibleJsn(self, jsn):
        ## change file paths, etc, to maintain compatibility with 0.9.0/0.9.1 preferred
        jsn['minSooSLVersion'] = '0.9.1'
        jsn['sooslVersion'] = '0.9.1_210201'
        signs = jsn.get('signs', [])
        jsn['signs'] = list(map(lambda s:self.revertPathsInSign(s), signs))
        return jsn
        
    def updateProject(self):
        """ this is run after a save operation to update the project and related project json files"""
        # just updating project info with this; sign data will be updated in a different method
        if self.writePermission:
            # construct json from current project attributes
            project_dir = os.path.dirname(self.json_file).replace('\\', '/').lstrip('./')
            project_dir = f'/{project_dir}'
            
            # 0.9.1 introduces some additional fields which are overwritten when opened with 0.9.0.
            # can't do much about that, but starting with the original json object should help prevent alterations 
            # in future versions being lost when opened with earlier ones; > 0.9.1
            #o = self.jsn
            self.jsn['signLanguage'] = self.sign_language
            self.jsn['projectName'] = self.name
            self.jsn['projectId'] = self.id
            self.jsn['versionId'] = self.version_id
            self.jsn['modifiedDateTime'] = self.last_save_datetime
            self.jsn['timeStamp'] = self.getModifiedTimeStampProject()
            self.jsn['projectCreator'] = self.project_creator # 0.9.4
            self.jsn['projectDescription'] = self.description
            
            #print('Before Update', [l.name for l in self.writtenLanguages])
            self.jsn['writtenLanguages'] = []
            self.writtenLanguages.sort(key=lambda x:x.name)
            for l in self.writtenLanguages:
                self.jsn['writtenLanguages'].append({'langId':l.id, 'langName':l.name, 'order':l.order})
                #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                # a new attribute key added would be lost if project is edited by older software which doesn't include it.
            #print('After Update', [l.name for l in self.writtenLanguages])
            
            self.jsn['dialects'] = []
            self.dialects.sort(key=lambda x:x.name)
            for d in self.dialects:
                self.jsn['dialects'].append({'id':d.id, 'name':d.name, 'abbr':d.abbr,  'focal':d.focal})
                #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                # a new attribute key added would be lost if project is edited by older software which doesn't include it.
                
            self.jsn['grammarCategories'] = []
            self.grammar_categories.sort(key=lambda x:x.name)
            for c in self.grammar_categories:
                self.jsn['grammarCategories'].append({'id':c.id, 'name':c.name})
                #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                # a new attribute key added would be lost if project is edited by older software which doesn't include it.
                    
            # write json out to file
            signs = None
            try:
                signs = self.jsn.pop('signs') #just writing out project info
            except:
                pass # already updated and removed from main project file            
            self.sortProjectJsn(self.jsn)
            write = True
            if not os.access(self.json_file, os.W_OK):
                os.chmod(self.json_file, stat.S_IWUSR|stat.S_IREAD)
                write = False
            with io.open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
            if not write:
                os.chmod(self.json_file, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH) 

            if signs:
                self.jsn['signs'] = signs #add back in
                
        return True

    def updateProjectTimeStamp(self, datetime):
        jsn = {}
        with io.open(self.json_file, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
        project_timestamp = jsn.get('timeStamp', None)
        this_timestamp = self.getModifiedTimeStampProject(datetime)
        ##NOTE: timestamps are strings and need to be converted before comparison
        if not project_timestamp or float(this_timestamp) > float(project_timestamp):
            jsn['timeStamp'] = this_timestamp
            jsn['modifiedDateTime'] = datetime
            with io.open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)

    def updateSignDateTime(self, sign, datetime):
        jsn = {}
        with io.open(sign.path, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
            jsn['modifiedDateTime'] = datetime
        if jsn:
            with io.open(sign.path, 'w', encoding='utf-8') as f:
                json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
            sign.modified_datetime = datetime

    def updateSignFileGramCats(self, grammar_categories):
        gram_cat_ids = [gc[0] for gc in grammar_categories if gc[0] > 0]
        signs_dir = f'{self.project_dir}/_signs'
        qdir = QDir(signs_dir)
        qdir.setFilter(QDir.Files)
        sign_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1].lower() == '.json'] 
        for sign_file in sign_files:
            jsn = None
            update = False
            with io.open(sign_file, encoding='utf-8') as f:
                try:
                    jsn = json.load(f)
                except:
                    print(f'empty file: {f} Delete???')
            if jsn:
                senses = jsn.get('senses', [])
                for sense in senses:
                    id = sense.get('grammarCategoryId')
                    if id and id not in gram_cat_ids:
                        update = True
                        jsn['modifiedDateTime'] = self.last_save_datetime
                        sense['grammarCategoryId'] = None
            if update:
                try:
                    with io.open(sign_file, 'w', encoding='utf-8') as f:
                        json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
                except TimeoutError:
                    short = qApp.instance().translate('Project', 'Network access to dictionary lost.')
                    long = qApp.instance().translate('Project', 'Please close dictionary and try again later.')
                    qApp.instance().pm.show_warning.emit(short, long)
                    #json.dump(_sign, f, sort_keys=False, indent=4, ensure_ascii=False)

    def updateSignFileDialects(self, dialects):
        remove_ids = [abs(d[0]) for d in dialects if d[0] < 0] #to remove
        signs_dir = f'{self.project_dir}/_signs'
        qdir = QDir(signs_dir)
        qdir.setFilter(QDir.Files)
        sign_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1].lower() == '.json'] 
        for sign_file in sign_files:
            jsn = None
            update = False
            with io.open(sign_file, encoding='utf-8') as f:
                try:
                    jsn = json.load(f)
                except:
                    print(f'empty file: {f} Delete???')
            if jsn:
                senses = jsn.get('senses', [])
                for sense in senses:
                    ids = sense.get('dialectIds')
                    new_ids = copy.deepcopy(ids)
                    for id in remove_ids:
                        if id in new_ids:
                            new_ids.remove(id)
                    if ids != new_ids:
                        update = True
                        jsn['modifiedDateTime'] = self.last_save_datetime
                        sense['dialectIds'] = new_ids
            if update:
                try:
                    with io.open(sign_file, 'w', encoding='utf-8') as f:
                        json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
                except TimeoutError:
                    short = qApp.instance().translate('Project', 'Network access to dictionary lost.')
                    long = qApp.instance().translate('Project', 'Please close dictionary and try again later.')
                    qApp.instance().pm.show_warning.emit(short, long)

    def updateSignFileLangs(self, langs):
        remove_ids = [abs(l[0]) for l in langs if l[0] < 0] #to remove
        signs_dir = f'{self.project_dir}/_signs'
        qdir = QDir(signs_dir)
        qdir.setFilter(QDir.Files)
        sign_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1].lower() == '.json'] 
        for sign_file in sign_files:
            with io.open(sign_file, encoding='utf-8') as f:
                try:
                    jsn = json.load(f)
                except:
                    print(f'empty file: {f} Delete???')
            if jsn:
                # modified time
                modify_datetime = False
                #jsn['modifiedDateTime'] = self.last_save_datetime

                # modified extra texts
                extra_texts = jsn.get('extraTexts', [])
                new_extra_texts = [et for et in extra_texts if et.get('langId') not in remove_ids]
                jsn['extraTexts'] = new_extra_texts
                if extra_texts != new_extra_texts:
                    modify_datetime = True
                # modified gloss texts & sentence texts
                senses = jsn.get('senses', [])
                for sense in senses:
                    # gloss texts
                    gloss_texts = sense.get('glossTexts', [])
                    new_gloss_texts = [gt for gt in gloss_texts if gt.get('langId') not in remove_ids]
                    sense['glossTexts'] = new_gloss_texts
                    if gloss_texts != new_gloss_texts:
                        modify_datetime = True
                    # sentence texts
                    sentences = sense.get('sentences', [])
                    for sentence in sentences:
                        sent_texts = sentence.get('sentenceTexts', [])
                        new_sent_texts = [s for s in sent_texts if s.get('langId') not in remove_ids]
                        sentence['sentenceTexts'] = new_sent_texts
                        if sent_texts != new_sent_texts:
                            modify_datetime = True
                if modify_datetime:
                    jsn['modifiedDateTime'] = self.last_save_datetime
            # write changes to file
            try:
                with io.open(sign_file, 'w', encoding='utf-8') as f:
                    json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
            except TimeoutError:
                short = qApp.instance().translate('Project', 'Network access to dictionary lost.')
                long = qApp.instance().translate('Project', 'Please close dictionary and try again later.')
                qApp.instance().pm.show_warning.emit(short, long)

    def updateSignFile(self, sign, delete_id=None):
        old_signs = []
        if not sign and delete_id:
            try:
                old_signs = [s for s in self.jsn['signs'] if s.get('id') == delete_id]
            except:
                pass # probably new dictionary without any signs yet
        else:
            try:
                old_signs = [s for s in self.jsn['signs'] if s.get('id') == sign.id]
            except:
                pass # probably new dictionary without any signs yet
        _sign = {} #new sign?
        if old_signs: # existing sign updated or removed
            _sign = old_signs[0]
            if delete_id:
                self.jsn['signs'].remove(_sign)

        elif not delete_id: # new sign
            try:
                self.jsn['signs'].append(_sign)
            except:
                self.jsn['signs'] = [_sign] # first sign in new dictionary

        if not delete_id:
            if 'new' in _sign.keys():
                _sign.pop('new') #

            _sign['id'] = sign.id
            _sign['modifiedDateTime'] = sign.modified_datetime
            # pth = sign.path ##NOTE: this probably is only the case for testing MEGA dictionary with paths in the local filesystem?
            # ##NOTE: a real dictionary would have all files in the dictionary directory? following check may not be needed...
            # #if pth.startswith(project_dir): 
            pth = f'/_signs/{os.path.basename(sign.path)}'
            old_sign_video = _sign.get('path', pth) # if none set, let them be equal
            _sign['path'] = pth
            _sign['hash'] = sign.hash
            _sign['componentCodes'] = sign.component_codes
            _sign['senses'] = []
            for sense in sign.senses:
                _sense = {}
                _sign['senses'].append(_sense)
                _sense['id'] = sense.id
                sense.dialect_ids.sort(key=lambda x: int(x))
                _sense['dialectIds'] = sense.dialect_ids
                _sense['grammarCategoryId'] = sense.grammar_category_id
                _sense['glossTexts'] = []
                any_gloss_texts = [gt.text for gt in sense.gloss_texts if gt.text]
                if any_gloss_texts:
                    sense.gloss_texts.sort(key=lambda x: int(x.lang_id))
                    for gloss_text in sense.gloss_texts:
                        if gloss_text.text:
                            _sense['glossTexts'].append({'langId':gloss_text.lang_id, 'text':gloss_text.text})
                        #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                        # a new attribute key added would be lost if dictionary is edited by older software which doesn't include it.
                _sense['sentences'] = []
                for sentence in sense.sentences:
                    _sentence = {}
                    _sense['sentences'].append(_sentence)
                    _sentence['id'] = sentence.id
                    pth = f'/_sentences/{os.path.basename(sentence.path)}'
                    _sentence['path'] = pth
                    _sentence['hash'] = sentence.hash
                    _sentence['sentenceTexts'] = []
                    any_sentence_texts = [st.text for st in sentence.sentence_texts if st.text]
                    if any_sentence_texts:
                        sentence.sentence_texts.sort(key=lambda x: int(x.lang_id))
                        for text in sentence.sentence_texts:
                            if text.text:
                                _sentence['sentenceTexts'].append({'langId':text.lang_id, 'text':text.text})
                            #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                            # a new attribute key added would be lost if dictionary is edited by older software which doesn't include it.
            _sign['extraMediaFiles'] = []
            sign.extra_media_files.sort(key=lambda x: (self.__mediaOrder(x.path), x.id))
            # sort by video(0) or picture(1), then by id
            # https://stackoverflow.com/questions/4233476/sort-a-list-by-multiple-attributes
            for emf in sign.extra_media_files:
                pth = emf.path
                if emf.media_object.mediatype == 'ex_video':
                    pth = f'/_extra_videos/{os.path.basename(pth)}'
                else:
                    pth = f'/_extra_pictures/{os.path.basename(pth)}'
                _sign['extraMediaFiles'].append({'id':emf.id, 'path':pth, 'hash':emf.hash})
                #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                # a new attribute key added would be lost if dictionary is edited by older software which doesn't include it.
            _sign['extraTexts'] = []
            any_extra_texts = [et.text for et in sign.extra_texts if et.text]
            if any_extra_texts:
                sign.extra_texts.sort(key=lambda x: int(x.lang_id))
                for et in sign.extra_texts:
                    if et.text:
                        _sign['extraTexts'].append({'langId':et.lang_id, 'text':et.text})
                    #NOTE: use full list of attribute keys, even deprecated ones, to ensure no loss of data between versions.
                    # a new attribute key added would be lost if dictionary is edited by older software which doesn't include it.

        # update sign json file
        signs_dir = f'{self.project_dir}/_signs'
        if not os.path.exists(signs_dir):
            os.mkdir(signs_dir)

        sign_video = _sign.get('path')
        _id = os.path.splitext(os.path.basename(sign_video))[0] # 0.9.4
        _id = _id.split('_id')[-1] # reverting 0.9.4 change
        sign_pth =  f'{signs_dir}/{_id}.json'
        old_sign_pth = sign_pth # if not assigned next, let it be the same
        old_sign_video = _sign.get('path', old_sign_pth) # if none set, let them be equal
        if old_sign_video != sign_video: # editing changed sign video file
            old_id = os.path.splitext(os.path.basename(old_sign_video))[0]
            old_sign_pth =  f'{signs_dir}/{old_id}.json'

        if delete_id:
            if sign_pth and os.path.exists(sign_pth):
                os.remove(sign_pth)
                lock_path = f'{sign_pth}.lock'
                if os.path.exists(lock_path):
                    qApp.instance().pm.releaseSignLock(lock_path)  
        else:
            try:
                with io.open(sign_pth, 'w', encoding='utf-8') as f:
                    json.dump(_sign, f, sort_keys=False, indent=4, ensure_ascii=False)
            except TimeoutError:
                short = qApp.instance().translate('Project', 'Network access to dictionary lost.')
                long = qApp.instance().translate('Project', 'Please close dictionary and try again later.')
                qApp.instance().pm.show_warning.emit(short, long)
            else:
                if sign_pth != old_sign_pth: ## editing changed sign video file; new sign json file with new name; remove old file 
                    qApp.instance().pm.acquireSignLocks([_id])
                    qApp.instance().pm.releaseSignLock(f'{old_sign_pth}.lock')
                    os.remove(old_sign_pth)
                    old_video = f'{self.project_dir}{old_sign_video}'
                    qApp.instance().pm.addPossibleRemoval(old_video)

        return True
        
    def getJsn(self, update=True): 
        jsn = None
        try:  
            with io.open(self.json_file, 'r', encoding='utf-8') as f:
                jsn = json.load(f)
        except:
            return None
        else:
            if update:
                pass
                jsn = self.updateJsn(jsn)
        return jsn
    
    def showCannotOpenErrorMsg(self):
        txt1 = qApp.instance().translate('Project', 'Cannot open dictionary')
        a = qApp.instance().translate('Project', 'This dictionary cannot be opened now.')
        b = qApp.instance().translate('Project', 'It may already be open with a version of SooSL older than 0.9.2.')
        c = qApp.instance().translate('Project', 'Please try again later.')
        txt2 = f"<b>{a}</b><br>{b}<br>{c}"        
        qApp.instance().pm.show_warning.emit(txt1, txt2)
        
    def updateJsn(self, jsn):
        """update with any name changes or other modifications"""
        try:
            date_time = jsn.pop('dateTime') # changed to 'timeStamp' 0.9.1
        except:
            pass
        else:
            jsn['timeStamp'] = date_time

        old_version = jsn.get('sooslVersion', '0.0.0')
        old_min_version = jsn.get('minSooSLVersion', '0.0.0')
        
        if jsn.get('signs', None):
            # if jsn contains sign data, split out signs into individual JSON files; old project or zoozl import
            jsn = self.splitProjectSignData(jsn)
        ## 0.9.2
        if qApp.instance().pm.olderThan(old_version, qApp.instance().pm.getSooSLVersion()):
            jsn['sooslVersion'] = qApp.instance().pm.getSooSLVersion() # record current/latest version which has modified dictionary
            self.project_updates = True
        if qApp.instance().pm.olderThan(old_min_version, MIN_SOOSL_VERSION):
            jsn['minSooSLVersion'] = MIN_SOOSL_VERSION # oldest SooSL version that can open this dictionary
            self.project_updates = True

        # prevent versions < 0.9.2 from deleting sign media and data by renaming directories.
        # this was possible by code which mistakenly deleted files which appeared to be 'orphaned' and not used by the dictionary
        # due to errors in identifying correct file paths.
        project_dir = os.path.dirname(self.json_file)
        old_sign_dir = f'{project_dir}/signs'
        new_sign_dir = f'{project_dir}/_signs'
        old_sentence_dir = f'{project_dir}/sentences'
        new_sentence_dir = f'{project_dir}/_sentences'
        old_extra_video_dir = f'{project_dir}/extra_videos'
        new_extra_video_dir = f'{project_dir}/_extra_videos'
        old_extra_picture_dir = f'{project_dir}/extra_pictures'
        new_extra_picture_dir = f'{project_dir}/_extra_pictures'

        # create new directories
        for _dir in [new_sign_dir, new_sentence_dir, new_extra_video_dir, new_extra_picture_dir]:
            if not os.path.exists(_dir):
                os.mkdir(_dir)

        error = False
        for _dirs in [(old_sign_dir, new_sign_dir), (old_sentence_dir, new_sentence_dir),
            (old_extra_video_dir, new_extra_video_dir), (old_extra_picture_dir, new_extra_picture_dir)]:
                src, dst = _dirs
                qdir = QDir(src)
                qdir.setFilter(QDir.Files)
                paths = [qdir.absoluteFilePath(entry) for entry in qdir.entryList()]
                for pth in paths:
                    try:
                        shutil.move(pth, dst)
                    except:
                        error = True
                if not error and os.path.exists(src):
                    try:
                        shutil.rmtree(src)
                    except:
                        pass #error = True
        if error:
            self.showCannotOpenErrorMsg()
            return None
        if qApp.instance().pm.olderThan(old_version, '0.9.2'):
            self.sanitizeFilenames(new_sign_dir)        

        # self.updateSignJsn094(new_sign_dir) 
        # self.revertSignJsn094Change(new_sign_dir)
        jsn = self.addSignData(jsn)
        
        # ## 0.9.4 ###########################################
        if qApp.instance().pm.olderThan(old_version, '0.9.4'):
            self.lengthCheckFilenames(new_sign_dir)

        creation_dt = jsn.get('creationDateTime')
        if not creation_dt:
            jsn['creationDateTime'] = ''
            self.project_updates = True
        keys = list(jsn.keys())
        ## NOTE: yes! we want to keep them; from 0.9.4 we must be able to preserve any unknown future changes
        # for key in keys: # remove unwanted attributes in jsn
        #     if key not in project_attributes:
        #         jsn.pop(key)  
        if keys != project_attributes:
            self.sortProjectJsn(jsn)
            self.project_updates = True
        # ##################################################### 
        return jsn
    
    # def updateSignJsn094(self, sign_dir):
    #     # update sign.json filenames to match media.mp4 filenames 
    #     qApp.setOverrideCursor(Qt.BusyCursor)
    #     _dir = QDir(sign_dir)
    #     _dir.setFilter(QDir.Files)
    #     entries = [f for f in _dir.entryList() if f.lower().endswith('.json')]
    #     sign_files = list(map(lambda x: _dir.absoluteFilePath(x), entries))
    #     for sign_file in sign_files:
    #         jsn = None
    #         with io.open(sign_file, 'r', encoding='utf-8') as f:
    #             jsn = json.load(f)
    #         if jsn:
    #             _pth = jsn.get('path')
    #             if _pth:
    #                 new_id = os.path.splitext(os.path.basename(_pth))[0]
    #                 new_sign_file = f'{self.project_dir}/_signs/{new_id}.json'
    #                 if sign_file != new_sign_file:
    #                     shutil.move(sign_file, new_sign_file)
    #     qApp.restoreOverrideCursor()

    # def revertSignJsn094Change(self, sign_dir):
    #     # NOTE: just needed for development to revert change for 0.9.4
    #     # update sign.json filenames to match media.mp4 filenames 
    #     print('REMOVE revertSignJsn094Change BEFORE DEPLOYMENT')
    #     qApp.setOverrideCursor(Qt.BusyCursor)
    #     _dir = QDir(sign_dir)
    #     _dir.setFilter(QDir.Files)
    #     entries = [f for f in _dir.entryList() if f.lower().endswith('.json')]
    #     sign_files = list(map(lambda x: _dir.absoluteFilePath(x), entries))
    #     for sign_file in sign_files:
    #         jsn = None
    #         with io.open(sign_file, 'r', encoding='utf-8') as f:
    #             jsn = json.load(f)
    #         if jsn:
    #             _pth = jsn.get('path')
    #             if _pth:
    #                 new_id = os.path.splitext(os.path.basename(_pth))[0]
    #                 new_id = new_id.split('_id')[-1] # revert change
    #                 new_sign_file = f'{self.project_dir}/_signs/{new_id}.json'
    #                 if sign_file != new_sign_file:

    #                     shutil.move(sign_file, new_sign_file)
    #     qApp.restoreOverrideCursor()

    def lengthCheckFilenames(self, sign_dir):
        pass

    def sanitizeFilenames(self, sign_dir):
        proj_dir = os.path.dirname(sign_dir)
        def sanitizeJsn(dict):
            pth = dict.get('path', '')
            new_pth = qApp.instance().pm.sanitizePath(pth)
            if pth != new_pth:
                dict['path'] = new_pth

        sent_dir = os.path.join(proj_dir, '_sentences')
        extra_video_dir = os.path.join(proj_dir, '_extra_videos')
        extra_picture_dir = os.path.join(proj_dir, '_extra_pictures')

        txt = qApp.instance().translate('Project', 'Updating sign files...')
        self.progress.setLabelText(f"<b>{txt}</b>") 

        for _dir in [sign_dir, sent_dir, extra_video_dir, extra_picture_dir]:
            qdir = QDir(_dir) #sign directory will contain all the sign json files including media file paths
            qdir.setFilter(QDir.Files)
            count = len(qdir.entryList())
            self.progress.setMaximum(self.progress.maximum()+count)
            for entry in qdir.entryList():
                self.progress.setValue(self.progress.value()+1)
                qApp.processEvents()
                if entry.endswith('.lock'):
                    continue
                pth = qdir.absoluteFilePath(entry)
                if not pth.lower().endswith('.json'): # sanitize media files
                    new_pth = qApp.instance().pm.sanitizePath(pth)
                    if pth != new_pth:
                        try:
                            shutil.move(pth, new_pth)
                        except:
                            pass
                else: # santize sign json files
                    try:
                        with io.open(pth, 'r', encoding='utf-8') as f:
                            jsn = json.load(f)
                    except:
                        pass
                    else:
                        sanitizeJsn(jsn)
                        senses = jsn.get('senses', [])
                        for sense in senses:
                            sentences = sense.get('sentences', [])
                            for sent in sentences:
                                sanitizeJsn(sent)
                        extra_media = jsn.get('extraMediaFiles', [])
                        for extra in extra_media:
                            sanitizeJsn(extra)
                        # write amend sign file
                        with io.open(pth, 'w', encoding='utf-8') as f:
                            json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)

    def addSignData(self, jsn):
        project_dir = os.path.dirname(self.json_file)
        sign_dir = f'{project_dir}/_signs'
        _dir = QDir(sign_dir)
        _dir.setFilter(QDir.Files)
        entries = [f for f in _dir.entryList() if f.lower().endswith('.json')]
        sign_files = list(map(lambda x: _dir.absoluteFilePath(x), entries))
        sign_data = [] 

        count = len(sign_files) 
        self.progress.setMaximum(self.progress.maximum() + count)
        txt = qApp.instance().translate('Project', 'Getting signs...')
        self.progress.setLabelText(f"<b>{txt}</b>") 

        for sf in sign_files:
            self.progress.setValue(self.progress.value()+1) 
            qApp.processEvents() 

            txt = open(sf, 'r', encoding='utf-8').read()
            if txt: #NOTE: dummy sign, indicating full dictionary lock may not contain text
                try:
                    sign = json.loads(txt)
                except:
                    pass
                else:
                    if list(sign.keys()) != sign_attributes:
                        self.sortSignJsn(sign)
                        with io.open(sf, 'w', encoding='utf-8') as f:
                            json.dump(sign, f, sort_keys=False, indent=4, ensure_ascii=False)
                    # if len(str(sign.get('id'))) < 5: # update ids to new style based on timestamp
                    #     sign = self.updateIdsInSign(sign, sf)
                    sign_data.append(sign)
        jsn['signs'] = sign_data
        return jsn

    def updatePathsInSign(self, sign):
        # 0.9.2 change of media paths
        pth = sign.get('path', '')
        pth = pth.replace('/signs/', '/_signs/')
        sign['path'] = pth
        senses = sign.get('senses', [])
        for sense in senses:
            sentences = sense.get('sentences', [])
            for sent in sentences:
                pth = sent.get('path')
                pth = pth.replace('/sentences/', '/_sentences/')
                sent['path'] = pth
        extra_media_files = sign.get('extraMediaFiles', [])
        for emf in extra_media_files:
            pth = emf.get('path')
            if pth.count('/extra_videos/'):
                pth = pth.replace('/extra_videos/', '/_extra_videos/')
            elif pth.count('/extra_pictures/'):
                pth = pth.replace('/extra_pictures/', '/_extra_pictures/')
            emf['path'] = pth
        return sign

    def revertPathsInSign(self, sign):
        # change of media paths from 0.9.2 to compatibility with 0.9.0
        pth = sign.get('path', '')
        pth = pth.replace('/_signs/', '/signs/')
        sign['path'] = pth
        senses = sign.get('senses', [])
        for sense in senses:
            sentences = sense.get('sentences', [])
            for sent in sentences:
                pth = sent.get('path')
                pth = pth.replace('/_sentences/', '/sentences/')
                sent['path'] = pth
        extra_media_files = sign.get('extraMediaFiles', [])
        for emf in extra_media_files:
            pth = emf.get('path')
            if pth.count('/_extra_videos/'):
                pth = pth.replace('/_extra_videos/', '/extra_videos/')
            elif pth.count('/_extra_pictures/'):
                pth = pth.replace('/_extra_pictures/', '/extra_pictures/')
            emf['path'] = pth
        return sign

    def splitProjectSignData(self, jsn):
        # introduced in 0.9.2 to split single JSON file into a dictionary info json file
        # and individual json files for each sign
        project_dir = os.path.dirname(self.json_file)
        signs = jsn.pop('signs')
        self.progress.setValue(self.progress.value()+1)
        qApp.processEvents()
        for sign in signs:
            sign = self.updatePathsInSign(sign)
            id = sign.get('id')
            signs_dir = f'{project_dir}/signs' # don't update to '/_signs' here; will be done later in a directory rename
            if not os.path.exists(signs_dir):
                os.mkdir(signs_dir)
            pth = f'{signs_dir}/{id}.json'
            with io.open(pth, 'w', encoding='utf-8') as f:
                json.dump(sign, f, sort_keys=False, indent=4, ensure_ascii=False)
        write = True
        if not os.access(self.json_file, os.W_OK):
            os.chmod(self.json_file, stat.S_IWUSR|stat.S_IREAD)
            write = False
        with io.open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
        if not write:
            os.chmod(self.json_file, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
        #jsn['signs'] = signs # signs are added back in later; this doubled it
        return jsn
        
    def setDescription(self, descript):
        self.description = descript
        qApp.instance().pm.recordDescriptionChange(descript)
        
    def setProjectName(self, name):
        self.name = name
        qApp.instance().pm.recordNameChange(name)
        
    def setProjectSignLanguage(self, sign_language):
        self.sign_language = sign_language
        qApp.instance().pm.recordSignLanguageChange(sign_language)
        
    def setProjectVersionId(self, version_id):
        self.version_id = version_id
        qApp.instance().pm.recordVersionIdChange(version_id)
        
    def setProjectDateTime(self):
        self.last_save_datetime = datetime.now(timezone.utc).isoformat()
        qApp.instance().pm.recordDateTimeChange(self.last_save_datetime)

    def setProjectCreator(self, project_creator):
        self.project_creator = project_creator
        qApp.instance().pm.recordProjectCreatorChange(project_creator)

    def checkOtherUsersProjectDateTime(self, set=True):
        other_users_datetime = f'{self.project_dir}/update_datetime.txt'
        if os.path.exists(other_users_datetime):
            users_dt = open(other_users_datetime, encoding='utf-8').read().strip()
            users_timestamp = self.getModifiedTimeStampProject(users_dt)
            #project_dt = self.jsn.get('modifiedDateTime')
            project_timestamp = self.jsn.get('timeStamp')
            if set:
                if float(users_timestamp) > float(project_timestamp):
                    try:  
                        with io.open(self.json_file, 'r', encoding='utf-8') as f:
                            jsn = json.load(f)
                    except:
                        pass
                    else: 
                        jsn['timeStamp'] = users_timestamp
                        jsn['modifiedDateTime'] = users_dt
                        with io.open(self.filename, 'w', encoding='utf-8') as f:
                            json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)
                os.remove(other_users_datetime)
            elif float(users_timestamp) > float(project_timestamp):
                return True
            return False
        
    def getModifiedTimeStampProject(self, _dt=None):
        if not _dt:
            _dt = self.last_save_datetime
        if _dt:
            dt = ''
            if hasattr(datetime, 'fromisoformat'):
                dt = datetime.fromisoformat(_dt)
            elif hasattr(parser, 'isoparse'):
                dt = parser.isoparse(_dt)
            else:
                dt = qApp.instance().pm.fromIsoFormat(self.last_save_datetime)
            return str(round(qApp.instance().pm.getSooSLDateTime(dt))) # round this to seconds.
        return ''  
    
    def amendGramCatsList(self, cats):
        remove_ids = [abs(c[0]) for c in cats if c[0] < 0]
        self.grammar_categories = [gc for gc in self.grammar_categories if gc.id not in remove_ids]
        for gc in self.grammar_categories:
            cat = [c for c in cats if c[0] == gc.id][0]
            gc.id = cat[0]
            gc.name = cat[1]
        
        if remove_ids: # amend signs which use these categories
            for sign in self.signs:
                for sense in sign.senses:
                    if sense.grammar_category_id in remove_ids:
                        sense.grammar_category_id = None
                        
        new = [c for c in cats if c[0] == 0]
        if new:
            all_ids = [gc.id for gc in self.grammar_categories]
            new_id = 1
            for n in new:
                while new_id in all_ids:
                    new_id += 1
                all_ids.append(new_id)
                new_cat = GrammarCategory({'id':new_id, 'name':n[1]})
                self.grammar_categories.append(new_cat) 
                
        qApp.instance().pm.recordGramCatChange(self.grammar_categories) 
        
    def amendLanguageList(self, langs):
        remove_ids = [abs(l[0]) for l in langs if l[0] < 0]
        self.writtenLanguages = [wl for wl in self.writtenLanguages if wl.id not in remove_ids]
        for lang in self.writtenLanguages:
            _lang = [l for l in langs if l[0] == lang.id][0]
            lang.name = _lang[1]
            lang.order = _lang[2]
            
        if remove_ids: #delete texts which use these languages
            for sign in self.signs:
                sign.extra_texts = [et for et in sign.extra_texts if et.lang_id not in remove_ids]
                for sense in sign.senses:
                    sense.gloss_texts = [gt for gt in sense.gloss_texts if gt.lang_id not in remove_ids]
                    for sent in sense.sentences:
                        sent.sentence_texts = [st for st in sent.sentence_texts if st.lang_id not in remove_ids]
            
        new = [l for l in langs if l[0] == 0]
        if new:
            all_ids = [l.id for l in self.writtenLanguages]
            new_id = 1
            for n in new:
                while new_id in all_ids:
                    new_id += 1
                all_ids.append(new_id)
                new_lang = WrittenLanguage({'langId':new_id, 'langName':n[1], 'order':n[2]})
                self.writtenLanguages.append(new_lang)
                
        settings = qApp.instance().getSettings()
        # remove old order settings for project
        start_text = f'ProjectSettings/{self.json_file}'
        for key in settings.allKeys():
            if key.startswith(start_text) and key.endswith('order'):
                settings.remove(key)
        # add new order settings
        for wl in self.writtenLanguages:
            settings.setValue(f'ProjectSettings/{self.json_file}/{wl.name}/order', wl.order)
        settings.sync()    
        qApp.instance().pm.recordLangListChange(self.writtenLanguages)
        self.writtenLanguages = sorted(self.writtenLanguages, key=lambda x: x.order) 
     
    def amendProjectDialects(self, dialects):
        removed_ids = [abs(d[0]) for d in dialects if d[0] < 0]
        new_dialects = [d for d in dialects if d[0] == 0]
        if new_dialects:
            dialect_ids = [d.id for d in self.dialects]
            new_dialect_id = 1
            for nd in new_dialects:
                while new_dialect_id in dialect_ids:
                    new_dialect_id +=1
                nd[0] = new_dialect_id
                dialect_ids.append(new_dialect_id)
                self.selected_dialect_ids.append(new_dialect_id)
        # if any signs use removed dialects, then update them to use the focal dialect
        if removed_ids:
            focal_id = [d[0] for d in dialects if d[3]][0]
            for sign in self.signs:
                for sense in sign.senses:
                    for _id in removed_ids:
                        if _id in sense.dialect_ids: 
                            sense.dialect_ids.remove(_id)
                            if focal_id not in sense.dialect_ids:
                                sense.dialect_ids.append(focal_id)    
        dialects = [{'id':d[0], 'name':d[1], 'abbr':d[2], 'focal':d[3]} for d in dialects if not d[0] < 0]
        self.dialects = [Dialect(d) for d in dialects]
        qApp.instance().pm.recordDialectListChange(self.dialects) 
        
    def countSignsSensesForDialect(self, dialect_id):
        sign_count = 0
        sense_count = 0
        for sign in self.signs:
            senses = [sense for sense in sign.senses if dialect_id in sense.dialect_ids]
            count = len(senses)
            if count:
                sign_count += 1
                sense_count += count
        return sign_count, sense_count
    
    def countSignsSensesGlossesForLanguage(self, lang_id=0):
        sign_count = 0
        sense_count = 0
        gloss_count = 0
        for sign in self.signs:
            senses = sign.senses
            count = len(senses)
            if count:
                sign_count += 1
                sense_count += count
                for sense in senses:
                    texts = self.__flat([list(map(lambda x:x.strip(), gt.text.split(';'))) for gt in sense.gloss_texts if gt.text and gt.lang_id == lang_id])
                    if texts:
                        gloss_count += len(texts)
        return sign_count, sense_count, gloss_count

    #https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists
    def __flat(self, _list): # [[1],[2],[3]] ==> [1,2,3]
        return [item for sublist in _list for item in sublist] 

    def countSignsSensesForProject(self):
        # not interested if text is added for a language or not
        sign_count = 0
        sense_count = 0
        for sign in self.signs:
            senses = sign.senses
            count = len(senses)
            if count:
                sign_count += 1
                sense_count += count
        return sign_count, sense_count
    
    def countSignsSensesForGramCat(self, cat_id):
        sign_count = 0
        sense_count = 0
        for sign in self.signs:
            senses = [sense for sense in sign.senses if sense.grammar_category_id == int(cat_id)]
            count = len(senses)
            if count:
                sign_count += 1
                sense_count += count
        return sign_count, sense_count
        
    def getSignCount(self):
        return len(self.signs)
    
    def getComponents(self, sign_id):
        """return list of component codes for a particular sign id
        """
        if not sign_id: return []
        signs = [sign for sign in self.signs if sign.id == sign_id]
        if signs: return signs[0].component_codes
    
    def getSignsByComponent(self, codes, dialect_ids, signs=[]):
        if isinstance(codes, (str, int)):
            codes = [codes]
        _signs = signs
        if not signs:
            _signs = self.signs
        if dialect_ids:
            signs = [sign for sign in _signs if (set(codes).issubset(set(sign.component_codes)) and 
                [sense for sense in sign.senses if all(i in dialect_ids for i in sense.dialect_ids)])]
        else:
            signs = [sign for sign in _signs if set(codes).issubset(set(sign.component_codes))]
        return signs
    
    def getSignCountByComponent(self, code, dialect_ids, signs=[]):
        return len(self.getSignsByComponent(code, dialect_ids, signs))
        
    def getDialectById(self, _id):
        dialects = [d.id for d in self.dialects if d.id == _id]
        if dialects:
            return dialects[0]
        
    def getGrammarCategoryName(self, _id):
        cats = [gc.name for gc in self.grammar_categories if gc.id == _id]
        if cats:
            return cats[0]
        
    def getWrittenLanguageId(self, lang_name):
        _id = [wl.id for wl in self.writtenLanguages if wl.name == lang_name]
        if _id:
            return _id[0] 
        return 0 #new lang
        
    def getWrittenLanguageName(self, _id):
        langs = [wl.name for wl in self.writtenLanguages if wl.id == _id]
        if langs:
            return langs[0]
        
    def getWrittenLanguageOrder(self, _id):
        langs = [wl.order for wl in self.writtenLanguages if wl.id == _id]
        if langs:
            return langs[0]
        
    def getWrittenLanguageIds(self):
        try:
            self.writtenLanguages.sort(key=lambda x:int(x.order))
        except:
            pass #old dictionary
        return [wl.id for wl in self.writtenLanguages]
        
    def getAllGlosses(self):
        empty = []
        gloss_texts = []
        signs = self.signs
        for sign in signs:
            senses = sign.senses
            for sense in senses:
                texts = sense.gloss_texts
                if not texts:
                    empty.append([sign.id, sense.id])
                for text in texts:
                    gloss_texts.append([sign.id, text])
        return (gloss_texts, empty)
    
    def getSignsByGloss(self, sense_id, dialect_ids):
        #https://thispointer.com/python-check-if-a-list-contains-all-the-elements-of-another-list/
        signs = [sign for sign in self.signs if [sense for sense in sign.senses if (sense.id == sense_id and all(i in dialect_ids for i in sense.dialect_ids))]]
        for sign in signs: sign.current_sense_id = sense_id
        return signs
    
    def getAllGlossDialects(self, sign_id, sense_id):
        dialect_ids =  [sense.dialect_ids for sense in self.getSenses(sign_id) if sense.id == sense_id]
        if dialect_ids:
            return [d for d in self.dialects if d.id in dialect_ids[0]]
        return []
    
    def getFocalDialect(self):
        try:
            return [dialect for dialect in self.dialects if dialect.isFocal()][0]
        except:
            return self.dialects[0]
    
    def getSenses(self, sign_id):
        sign = self.getSign(sign_id)
        if sign: return sign.senses
        return []
    
    def getGrammarCategory(self, sign_id, sense_id):
        cat_id =  [sense.grammar_category_id for sense in self.getSenses(sign_id) if sense.id == sense_id]
        if cat_id: cat_id = cat_id[0]
        cat = [cat for cat in self.grammar_categories if cat.id == cat_id]
        if cat: return cat[0]
        return None
    
    def getSentences(self, sign_id, sense_id):
        sentences = [sense.sentences for sense in self.getSenses(sign_id) if sense.id == sense_id]
        if sentences: return sentences[0]
        return []
    
    def getNewSign(self, filename, gloss_texts):
        _hash = qApp.instance().pm.getHash(filename)
        sign = Sign(self, {'id': qApp.instance().pm.getNewSignId(), 'path': filename, 'hash': _hash, 'new': True})
        sign.senses = [Sense(self, {"id": qApp.instance().pm.getTempId()})]
        if gloss_texts:
            print('do something with gloss_texts')
        else:
            sense = sign.senses[0]
            sense.gloss_texts = [GlossText(sense_id=sense.id)]
        return sign
    
    def getNewSense(self):
        sense = Sense(self, {"id": qApp.instance().pm.getTempId()})
        sense.grammar_category_id = None
        sense.dialect_ids = []
        sense.gloss_texts = []
        sense.sentences = []
        return sense
    
    def getNewSentence(self, filename, gloss_id, texts):
        sent = Sentence(self, {'id': qApp.instance().pm.getTempId(), 'path': filename})
        sent.hash = qApp.instance().pm.getHash(filename)
        #sent.path = filename
        sent.media_object = MediaObject(_filename=filename, _mediatype='sent', _hash=sent.hash)
        if not texts:
            texts = []
        sent.sentence_texts = copy.deepcopy(texts)
        return sent
    
    def getSign(self, sign_id):
        try:
            signs = [sign for sign in self.signs if sign and str(sign.id) == str(sign_id)]
        except:
            signs = []
            print('error: ', sign_id)        
        if signs: return signs[0]
        return None
    
    def getSignVideoByHash(self, _hash):
        for sign in self.signs:
            if sign.hash == _hash:
                return sign.path
        return None
    
    def getSentenceVideoByHash(self, _hash):
        for sign in self.signs:
            for sense in sign.senses:
                for sent in sense.sentences:
                    if sent.hash == _hash:
                        return sent.path
        return None
    
    def getExVideoByHash(self, _hash):
        return self.__getExMediaByHash(_hash)
    
    def getExPictureByHash(self, _hash):
        return self.__getExMediaByHash(_hash)
    
    def __getExMediaByHash(self, _hash):
        for sign in self.signs:
            for emf in sign.extra_media_files:
                if emf.hash == _hash:
                    return emf.path
        return None
    
    def saveSign(self, sign_data):
        self.ignore_duplicate_sense_id_check = True
        sign_data['complete'] = True
        self.last_save_datetime = datetime.now(timezone.utc).isoformat()
        sign_data['modifiedDateTime'] = self.last_save_datetime
        new_sign = {}
        sign_id = sign_data.get('id')
        if not sign_data.get('delete', False):
            new_sign = Sign(self, sign_data) 
        try:
            old_sign = [s for s in self.signs if s.id == sign_id][0]
        except:
            pass
        else:
            self.signs.remove(old_sign)
        if new_sign:
            self.signs.append(new_sign)
        self.ignore_duplicate_sense_id_check = False
        return new_sign

class Dialect():
    def __init__(self, jsn):
        self.id = jsn.get('id', 0)
        self.abbr = jsn.get('abbr', '')
        self.focal = jsn.get('focal', False)
        self.name = jsn.get('name', '')
        self.empty = jsn.get('empty', False)
        # self.merge_state = jsn.get('merge_state', 0)
        # self.edited_data = jsn.get('edited_data', '')
        
    def toJsn(self):
        return {
            'id': self.id, 
            'name': self.name,
            'abbr': self.abbr, 
            'focal': self.focal,
            'empty': self.empty
            }#, 'merge_state': self.merge_state, 'edited_data': self.edited_data}
    
    def toFinalJsn(self):
        return {
            'id': self.id, 
            'name': self.name,
            'abbr': self.abbr, 
            'focal': self.focal
            }

    def toList(self):
        return [self.id, self.abbr, self.focal, self.name]#, self.merge_state, self.edited_data]
        
    def isFocal(self):
        return self.focal

class GrammarCategory():
    def __init__(self, jsn={}):
        self.id = jsn.get('id', 0)
        self.name = jsn.get('name', '')
        self.empty = jsn.get('empty', False)
        # self.merge_state = jsn.get('merge_state', 0)
        # self.edited_data = jsn.get('edited_data', '')
        
    def toJsn(self):
        return {
            'id': self.id, 
            'name': self.name,
            'empty': self.empty
            }#, 'merge_state': self.merge_state, 'edited_data': self.edited_data}
    
    def toFinalJsn(self):
        return {
            'id': self.id, 
            'name': self.name
            }
                            
class WrittenLanguage():
    def __init__(self, jsn):
        self.name = jsn.get('langName', '')
        self.id = int(jsn.get('langId', 0))
        self.order = int(jsn.get('order', 0))
        self.empty = jsn.get('empty', False)
        # self.merge_state = jsn.get('merge_state', 0)
        # self.edited_data = jsn.get('edited_data', '')
        
    def toJsn(self):
        return {
            'langName': self.name, 
            'langId': self.id, 
            'order': self.order, 
            'empty': self.empty
            }#, 'merge_state': self.merge_state, 'edited_data': self.edited_data}
    
    def toFinalJsn(self):
        return { 
            'langName': self.name, 
            'langId': self.id, 
            'order': self.order
            }

    def toList(self):
        return [self.name, self.id, self.order, self.empty]#, self.merge_state, self.edited_data]

class Sign():
    def __init__(self, project, jsn=None):
        self.setup(project, jsn)

    def setup(self, project, jsn):        
        lang_ids = [l.id for l in project.writtenLanguages]
        self.project_directory = project.project_dir
        if jsn is None:
            jsn = {}
        self.id = self.getId(jsn)
        self.new = jsn.get('new', False)
        self.modified_datetime = jsn.get('modifiedDateTime', '')
        pth = jsn.get('path', '')
        self.path = pth
        if self.path and not os.path.exists(self.path): #path after saved
            project_dir = project.project_dir.lstrip('.')
            self.path = f'{project_dir}{pth}'.replace('\\', '/')
        self.path = findPathById(self.path)        
        self.path = qApp.instance().pm.checkFilepathLength(self.path, True)
        # if not os.path.exists(self.path):
        #     print('Where is:', self.path)
        self.hash = jsn.get('hash', '')
        orig_filename = None
        if self.new:
            orig_filename = 'None' # just so _orig_filename in MediaObject isn't same as filename; see class MediaObject
        self.media_object = MediaObject(_filename=self.path, _mediatype='sign', _hash=self.hash, _orig_filename=orig_filename)
        
        self.component_codes = jsn.get('componentCodes', [])

        senses = jsn.get('senses', [])
        self.senses = [Sense(project, sense, sign_id=self.id) for sense in senses]
        self.current_sense = None
        self.current_sense_id = None
        self.current_sense_field = None
        if self.senses: 
            self.current_sense = self.senses[0]
            self.current_sense_id = self.current_sense.id
            self.current_sense_field = 0
        
        extra_texts = jsn.get('extraTexts', [])
        any_extra_texts = [et.get('text', '') for et in extra_texts if et.get('text', '')]
        if not any_extra_texts:
            self.extra_texts = []
        else:
            for lang_id in lang_ids:
                lang_name = project.getWrittenLanguageName(lang_id) # useful for merging 0.9.4
                texts = [t for t in extra_texts if t.get('langId', '') == lang_id]
                if not texts:
                    extra_texts.append({'langId': lang_id, 'langName': lang_name, 'text': ''})
                else:
                    extra_texts[0]['langName'] = lang_name
            self.extra_texts = [ExtraText(et) for et in extra_texts]
        
        extra_media = jsn.get('extraMediaFiles', [])
        self.extra_media_files = [ExtraMediaFile(project, em) for em in extra_media]
        self.empty = jsn.get('empty', False)

        self.jsn = jsn

    def toJsn(self):
        return {
            'id': self.id,
            'modifiedDateTime': self.modified_datetime,
            'path': f'/_signs/{os.path.basename(self.path)}',
            'hash': self.hash,
            'componentCodes': self.component_codes,
            'senses': self.senses,
            'extraMediaFiles': self.extra_media_files,
            'extraTexts': self.extra_texts,
            'empty': self.empty
            }
    
    def toFinalJsn(self):
        return {
            'id': self.id,
            'modifiedDateTime': self.modified_datetime,
            'path': f'/_signs/{os.path.basename(self.path)}',
            'hash': self.hash,
            'componentCodes': self.component_codes,
            'senses': self.senses,
            'extraMediaFiles': self.extra_media_files,
            'extraTexts': self.extra_texts
            }

    def getId(self, jsn):
        _id = jsn.get('id', 0)
        return _id

    @property
    def json_file(self):
        _dir = self.project_directory
        if not _dir:
            _dir = qApp.instance().pm.project.project_dir
        _id = os.path.splitext(os.path.basename(self.path))[0] # 0.9.4
        _id = _id.split('_id')[-1] # revert 0.9.4 change
        return f'{_dir}/_signs/{_id}.json' 
        
    def resetMedia(self):
        if self.media_object.filename != self.path:
            self.media_object.filename = self.path
        for sense in self.senses:
            for sent in sense.sentences:
                if sent.media_object.filename != sent.path:
                    sent.media_object.filename = sent.path
## NOTE: shouldn't need to reset extra media in this way (yet)
## these are  simply deleted and a new one added in the event of a change
#         for ex in self.extra_media_files:
#             if ex.media_object.filename != ex.path:
#                     ex.media_object.filename = ex.path
        
class Sense():
    def __init__(self, project, jsn=None, sign_id=0):
        lang_ids = [l.id for l in project.writtenLanguages]
        if jsn is None:
            jsn = {}
        self.sign_id = sign_id
        self.id = jsn.get('id', self.getId(project, jsn))
        self.grammar_category_id = jsn.get('grammarCategoryId', None)
        self.dialect_ids = jsn.get('dialectIds', [])
        
        gloss_texts = jsn.get('glossTexts', [])
        any_gloss_texts = [t.get('text', '') for t in gloss_texts if t.get('text', '')]
        if not any_gloss_texts:
            self.gloss_texts = []
        else:
            # check if there is a text for each language; if not, add an "empty" text for that language.
            for lang_id in lang_ids:
                lang_name = project.getWrittenLanguageName(lang_id) # useful for merging 0.9.4
                texts = [gt for gt in gloss_texts if gt.get('langId', '') == lang_id]
                if not texts:
                    gloss_texts.append({'langId': lang_id, 'langName': lang_name, 'text': ''})
                else:
                    texts[0]['langName'] = lang_name
            self.gloss_texts = [GlossText(gt, self.id, sign_id=sign_id, dialect_ids=self.dialect_ids) for gt in gloss_texts]
        sentences = jsn.get('sentences', [])
        self.sentences = [Sentence(project, s) for s in sentences]
        self.empty = False
        if jsn:
            self.empty = jsn.get('empty', False)

    def toJsn(self):
        return {
            'id': self.id,
            'dialectIds': self.dialect_ids,
            'grammarCategoryId': self.grammar_category_id,
            'glossTexts': self.gloss_texts,
            'sentences': self.sentences,
            'empty:': self.empty
            }
    
    def toFinalJsn(self):
        return {
            'id': self.id,
            'dialectIds': self.dialect_ids,
            'grammarCategoryId': self.grammar_category_id,
            'glossTexts': self.gloss_texts,
            'sentences': self.sentences
            }

    def getId(self, project, jsn):
        _id = jsn.get('id', 0)
        if _id not in project.old_sense_ids:
            project.old_sense_ids.append(_id)
            return _id
        elif _id and project.ignore_duplicate_sense_id_check:
            return _id
        else: # _id already exists (error in 0.9.1); get new one
            try:
                new_id = qApp.instance().pm.getNewSenseId()
            except:
                new_id = f'{_id}n'
                # NOTE: don't really need brand new datetime here, just increment by 1 (1ms)
                while new_id in project.old_sense_ids:
                    try:
                        new_id += 1
                    except:
                        new_id = f'{new_id}n' # 'n' is appended each time: idn, idnn, idnnn...
                project.old_sense_ids.append(new_id)
            project.sense_ids_changed = True
            jsn['id'] = new_id
            return new_id
        
class GlossText():
    def __init__(self, jsn=None, sense_id=0, sign_id=0, dialect_ids=None, order=0):
        if not jsn:
            jsn = {}
        if dialect_ids is None:
            dialect_ids = []
        self.sense_id = sense_id
        self.lang_id = jsn.get('langId', 0)
        self.lang_name = jsn.get('langName', '')
        self.text = jsn.get('text', '')
        self.sign_id = sign_id #not for export; helpful for creating finder list
        self.dialect_ids = dialect_ids #not for export; helpful for creating finder list
        self.empty = jsn.get('empty', False)
        self.order = order

    def setOrder(self, _order):
        self.order = _order

    def toJsn(self):
        return {'langId': self.lang_id,
            'langName': self.lang_name,
            'text': self.text,
            'signId': self.sign_id,
            'senseId': self.sense_id,
            'dialectIds': self.dialect_ids,
            'empty': self.empty
            }
    
    def toFinalJsn(self):
        return {'langId': self.lang_id,
            'text': self.text
            }
        
class Sentence():
    def __init__(self, project, jsn):
        lang_ids = [l.id for l in project.writtenLanguages]
        self.id = self.getId(jsn)
        pth = jsn.get('path', '')
        self.path = pth
        if self.path and not os.path.exists(self.path): #path after saved
            project_dir = project.project_dir.lstrip('.')
            self.path = f'{project_dir}{pth}'.replace('\\', '/')
        self.path = findPathById(self.path)        
        self.path = qApp.instance().pm.checkFilepathLength(self.path, True)
        self.hash = jsn.get('hash', '')
        self.media_object = MediaObject(_filename=self.path, _mediatype='sent', _hash=self.hash)
        
        sentence_texts = jsn.get('sentenceTexts', [])
        for lang_id in lang_ids:
            lang_name = project.getWrittenLanguageName(lang_id) # useful for merging 0.9.4
            texts = [t for t in sentence_texts if t.get('langId', '') == lang_id]
            if not texts:
                sentence_texts.append({'langId': lang_id, 'langName': lang_name, 'text': ''})
            else:
                sentence_texts[0]['langName'] = lang_name
        self.sentence_texts = [SentenceText(st) for st in sentence_texts]
        self.empty = jsn.get('empty', False)

    def toJsn(self):
        return {
            'id': self.id,
            'path': self.path,
            'hash': self.hash,
            'sentenceTexts': self.sentence_texts,
            'empty': self.empty
            }
    
    def toFinalJsn(self):
        return {
            'id': self.id,
            'path': self.path,
            'hash': self.hash,
            'sentenceTexts': self.sentence_texts
            }

    def getId(self, jsn):
        _id = jsn.get('id', 0)
        return _id

class SentenceText():
    def __init__(self, jsn=None, order=0):
        if not jsn:
            jsn = {}
        self.lang_id = 0
        self.lang_name = ''
        self.text = ''
        self.empty = True
        self.order = order
        if jsn:
            self.lang_id = jsn.get('langId', 0)
            self.lang_name = jsn.get('langName', '')
            self.text = jsn.get('text', '')
            self.empty = jsn.get('empty', False)
            self.order = jsn.get('order', order)

    def toJsn(self):
        return {'langId': self.lang_id,
            'langName': self.lang_name,
            'text': self.text,
            'empty': self.empty
            }
    
    def toFinalJsn(self):
        return {'langId': self.lang_id,
            'text': self.text
            }

class ExtraText():
    def __init__(self, jsn=None, order=0):
        if not jsn:
            jsn = {}
        self.lang_id = 0
        self.lang_name = ''
        self.text = ''
        self.empty = True
        self.order = order
        if jsn:
            self.lang_id = jsn.get('langId', 0)
            self.lang_name = jsn.get('langName', '')
            self.text = jsn.get('text', '')
            self.empty = jsn.get('empty', False)
            self.order = order

    def toJsn(self):
        return {'langId': self.lang_id,
            'langName': self.lang_name,
            'text': self.text,
            'empty': self.empty
            }
    
    def toFinalJsn(self):
        return {'langId': self.lang_id,
            'text': self.text
            }

class ExtraMediaFile():
    def __init__(self, project, jsn=None):
        if not jsn:
            jsn = {}
        self.id = self.getId(jsn)
        pth = jsn.get('path', '')
        self.path = pth
        if self.path and not os.path.exists(self.path): #path after saved
            project_dir = project.project_dir.lstrip('.')
            self.path = f'{project_dir}{pth}'.replace('\\', '/')
        self.path = findPathById(self.path)
        self.path = qApp.instance().pm.checkFilepathLength(self.path, True) 
        self.hash = jsn.get('hash', '')
        
        _type = 'ex_video'
        if qApp.instance().pm.isPicture(self.path):
            _type = 'ex_picture'
            
        self.media_object = MediaObject(_filename=self.path, _mediatype=_type, _hash=self.hash)
        self.empty = jsn.get('empty', False)

    def getId(self, jsn):
        _id = jsn.get('id', 0)
        return _id
    
    def toJsn(self):
        path = ''
        if self.path:
            path = self.path.replace('\\', '/')
            parts = path.split('/')
            path = f'/{parts[-2]}/{parts[-1]}'
        return {            
            'id': self.id,
            'path': path,
            'hash': self.hash,
            'empty': self.empty,
            }
        
    def toFinalJsn(self):
        path = ''
        if self.path:
            path = self.path.replace('\\', '/')
            parts = path.split('/')
            path = f'/{parts[-2]}/{parts[-1]}'
        return {            
            'id': self.id,
            'path': path,
            'hash': self.hash
            }
    
# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()   