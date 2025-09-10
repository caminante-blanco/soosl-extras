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

"""This module is used within project_updater to update and convert old sqlite projects to json format.
"""

import sys, os
import copy

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QFileInfo
from PyQt5.QtCore import QTimer

from PyQt5.QtWidgets import qApp

from media_object import MediaObject
from media_wrappers import PictureWrapper as Picture
from media_wrappers import VideoWrapper as Video

class SignModelUpdater(QObject):
    """a class to model a single sign
    """
    modelReset = pyqtSignal()
    dirty = pyqtSignal(bool)
    newGloss = pyqtSignal(dict)
    newSentence = pyqtSignal(tuple)
    save_progress = pyqtSignal(str, int, float, bool)
    save_finished = pyqtSignal()
    
    def __init__(self, sign_id=None, gloss_id=None, sign_filename=None, parent=None):
        super(SignModelUpdater, self).__init__(parent)
        self.edit = False
        #self.lang_id = 1
        self.delete_flag = False        
        self.abort_flag = False
        self.sign_id = None
        self.gloss_id = None
        self.old_sign_id = None
        self.old_gloss_id = None
        self.media_dest_dict = {}
        self.sign_id = sign_id
        self.gloss_id = gloss_id
        self.tempIds = []
        self.sign_video = []
        
        self.load(sign_id, gloss_id, sign_filename)
        
    def getTempID(self):
        """ new things need a unique temp id until they are saved
        """
        #gloss_ids = [gloss.get(0) for gloss in self.new_gloss_list]
        _id = 'n'
        while _id in self.tempIds:
            _id = '{}n'.format(_id)
        self.tempIds.append(_id)
        return _id  
    
    @property
    def data_dir(self):
        db = self.parent().current_project_filename
        if db:
            return os.path.split(db)[0]
        else:
            return None
        
    def loadNew(self, sign_filename, texts):
        self.old_sign_id = self.sign_id
        self.old_gloss_id = self.gloss_id
        self.clear()
        gloss_id = self.getTempID()
        self.load(0, gloss_id, sign_filename, texts)
        
    def load(self, sign_id, gloss_id, sign_filename=None, texts=None, reload=False, reset_model=True):
        """ An existing sign will have sign_id and gloss_id, and its video will be found using these.
        A new sign will require a video filename and sign_id=0, gloss_id=0.
        """ 
        if not hasattr(self, 'data_dir') or not self.data_dir:
            return
        self.sign_id = sign_id
        self.gloss_id = gloss_id
        
        if not hasattr(self, 'sign_video'):
            self.sign_video = []
        else:
            self.sign_video.clear()
        
        if not reload:
            if not sign_id and not sign_filename:
                self.clear()
                if reset_model:
                    self.modelReset.emit()
                if qApp.hasPendingEvents():
                    qApp.processEvents() 
                return 
            
        if sign_id: #existing sign      
            try:
                sign_video = os.path.join(self.data_dir, 'signs', self.parent().dbm.getSignVideo(sign_id))
            except: ##NOTE: no sign video, deleted??
                self.sign_id = None
                self.gloss_id = None
                self.clear()
                if reset_model:
                    self.modelReset.emit()
                if qApp.hasPendingEvents():
                    qApp.processEvents()            
                return
            else:
                self.sign_video.clear()
                media = MediaObject(sign_video, 'sign')
                self.sign_video.append(media)
                 
        else: #new sign
            self.sign_video.clear()
            if sign_filename:
                media = MediaObject(sign_filename, 'sign')
                self.sign_video.append(media)
        
        self.gloss_list = self.parent().getGlossesForSign(sign_id) #list of glosses
        # a 'gloss' is: {0:gloss_id, lang1:text, lang2:text2, ...}
        self.sentence_dict = {} # dictionary of sentences with gloss_ids as keys
        # a 'sentence' is: [sent_id, [video_id, video_name], {0:text_id, lang1:text, lang2:text2, ..}]
        self.dialect_dict = {} # dictionary of dialect lists with gloss_ids as keys
        self.new_dialect_dict = {} # couldn't create a deepcopy of dialect_dict for some reason, see others below
        # a 'dialect' is [id, name, abbr, focal=bool]
        self.gram_cat_dict = {} # dictionary of sign type lists with gloss_ids as keys
        # a 'sign type' (part-of-speech) is a tuple of (id, name)
        self.extra_text_dict = {} # dictionary of extra texts with lang_ids as keys
        
        self.extra_videos = self.parent().getExVideos(sign_id, None)
        self.extra_pictures = self.parent().getExPictures(sign_id, None)        
        ex_video_dir = self.get_root('ex_video')
        self.extra_videos = [MediaObject(os.path.join(ex_video_dir, ev[0]), 'ex_video', _id=ev[1]) for ev in self.extra_videos]
        ex_picture_dir = self.get_root('ex_picture')
        self.extra_pictures = [MediaObject(os.path.join(ex_picture_dir, ep[0]), 'ex_picture', _id=ep[1]) for ep in self.extra_pictures]
        
        for gloss in self.gloss_list:
            gloss_id = gloss.get(0)
            self.sentence_dict[gloss_id] = self.parent().dbm.getSentences(sign_id, gloss_id)
            dialects = self.parent().getGlossDialects(sign_id, gloss_id)
            self.dialect_dict[gloss_id] = dialects
            new_dialects = []
            for d in dialects:
                new_dialects.append(d)
            self.new_dialect_dict[gloss_id] = new_dialects
            self.gram_cat_dict[gloss_id] = self.parent().dbm.getGramCats(sign_id, gloss_id)
        for gloss in self.gloss_list:
            gloss_id = gloss.get(0)            
            sentences = self.sentence_dict.get(gloss_id)
            if sentences:
                for sent in sentences:
                    sent_id, video, sent_texts = sent
                    filename = video[1]
                    pth = None
                    if filename:
                        pth = os.path.join(self.data_dir, 'sentences', filename)
                        video[1] = MediaObject(pth, 'sent')
        self.component_list = self.parent().getComponents(sign_id)        
        self.extra_text_dict = self.parent().getExTexts(sign_id)  
        for lang_id in self.parent().getLangIds():
            if not self.extra_text_dict.get(lang_id):
                self.extra_text_dict[lang_id] = ''  
                                 
        self.new_sign_video = copy.deepcopy(self.sign_video)
        self.new_gloss_list = copy.deepcopy(self.gloss_list)
        self.new_component_list = copy.deepcopy(self.component_list)
        
        self.new_sentence_dict = copy.deepcopy(self.sentence_dict)
        
        self.new_gram_cat_dict = copy.deepcopy(self.gram_cat_dict)
        self.new_extra_text_dict = copy.deepcopy(self.extra_text_dict)
        
        self.new_extra_videos = copy.deepcopy(self.extra_videos)
        self.new_extra_pictures = copy.deepcopy(self.extra_pictures)
        if not self.gloss_list and isinstance(self.gloss_id, str): # this would be the case with a new sign
            if texts:
                texts[0] = self.gloss_id
                self.new_gloss_list.append(texts)
            else:
                self.new_gloss_list.append({0:self.gloss_id}) #, self.lang_id:''}]
            self.new_dialect_dict[self.gloss_id] = []
            self.new_gram_cat_dict[self.gloss_id] = []
            
        if not self.gloss_id:
            try:
                self.gloss_id = self.new_gloss_list[0].get(0)
            except:
                self.gloss_id = None
        if reset_model:
            QTimer.singleShot(0, self.modelReset.emit)
    
    ##!!@pyqtSlot()   
    def onAmended(self):
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    #@property
    def _dirty(self):  
        if self.delete_flag and self.sign_id == 0:
            return False
        new_comps = self.new_component_list.copy()
        new_comps.sort()
        old_comps = self.component_list.copy()
        old_comps.sort()
        new_extra_videos = copy.deepcopy(self.new_extra_videos)
        new_extra_videos.sort(key=lambda x: x.filename)
        old_extra_videos = copy.deepcopy(self.extra_videos)
        old_extra_videos.sort(key=lambda x: x.filename)
        new_extra_pictures = copy.deepcopy(self.new_extra_pictures)
        new_extra_pictures.sort(key=lambda x: x.filename)
        old_extra_pictures = copy.deepcopy(self.extra_pictures)
        old_extra_pictures.sort(key=lambda x: x.filename)
        if self.delete_flag or \
            self.sign_id == 0 or \
            self.sign_video[0].filename != self.sign_video[0].orig_filename or \
            self.new_sign_video[0] != self.sign_video[0] or \
            self.new_gloss_list != self.gloss_list or \
            new_comps != old_comps or \
            self.new_sentence_dict != self.sentence_dict  or \
            not self.__compareDialectDicts() or \
            self.new_gram_cat_dict != self.gram_cat_dict or \
            self.new_extra_text_dict != self.extra_text_dict or \
            new_extra_videos != old_extra_videos or \
            new_extra_pictures != old_extra_pictures: 
                return True
        return False
    
    def __compareDialectDicts(self):
        dict1, dict2 = self.new_dialect_dict, self.dialect_dict
        if len(dict1) != len(dict2):
            return False
        keys1 = list(dict1.keys())
        keys1.sort()
        keys2 = list(dict2.keys())
        keys2.sort()
        if keys1 != keys2:
            return False
        for key in keys1:
            dialects1 = dict1.get(key)
            dialects2 = dict2.get(key)
            if self.parent().dialectStr(dialects1) != self.parent().dialectStr(dialects2):
                return False
        return True  

    def clear(self):
        self.sign_id = None
        self.gloss_id = None
        for container in [
            'sign_video',
            'gloss_list',
            'component_list',
            'sentence_dict',
            'dialect_dict',
            'gram_cat_dict',
            'extra_text_dict',
            'extra_videos',
            'extra_pictures',
            'new_sign_video',
            'new_gloss_list',
            'new_component_list',
            'new_sentence_dict',
            'new_dialect_dict',
            'new_gram_cat_dict',
            'new_extra_text_dict',
            'new_extra_videos',
            'new_extra_pictures'
            ]:
                if hasattr(self, container):
                    getattr(self, container).clear()
    
    ##!!@pyqtSlot()    
    def enterEditingMode(self):
        self.edit = True
     
    ##!!@pyqtSlot()   
    def leaveEditingMode(self):        
        self.edit = False
        self.tempIds.clear()
        self.reload()
    
    ##!!@pyqtSlot()     
    def saveMediaFinished(self):
        if not self.abort_flag:
            #self.saveData()
            QTimer.singleShot(0, self.saveData)
        else:
            self.finishSave()
            self.cleanupAfterAbort()                        
        try:
            del self.saver 
        except:
            pass #already deleted                   

    def saveMedia(self):
        self.saver = MediaSaver(self)
        self.saver.finished.connect(self.saveMediaFinished)
        self.saver.save()
    
    def save(self):
        self.parent().clearFiles2DeleteList()
        self.new_id = False
        self.abort_flag = False
        if self._dirty():
            if self.delete_flag:
                self.parent().amendComponents([], self.component_list, self.sign_id)
                for lang_id in self.extra_text_dict.keys():
                    self.parent().removeExText(self.sign_id, lang_id)
                for media in self.extra_videos:
                    file_id = media.id
                    filename = media.filename
                    self.parent().removeExVideo(filename, file_id, self.sign_id)
                for media in self.extra_pictures:
                    file_id = media.id
                    filename = media.filename
                    self.parent().removeExPicture(filename, file_id, self.sign_id)
                for gloss in self.gloss_list:
                    gloss_id = gloss.get(0)
                    sents = self.sentence_dict.get(gloss_id)
                    if sents:
                        for sent in sents:
                            sent_id = sent[0]
                            self.parent().removeSentence(self.sign_id, gloss_id, sent_id)
                    #self.parent().removeGloss(gloss, self.sign_id)
                    self.parent().removeSign(self.sign_id, gloss_id)
                self.delete_flag = False
                self.parent().removeUnusedFiles()    
                self.dirty.emit(False)
                self.save_finished.emit()
            else:
                self.saveMedia()
        
    def saveData(self):
        if self.sign_video[0].filename != self.sign_video[0].orig_filename:
            if self.sign_id != 0: #add new sign video but change it one or more times before saving. once saved, there will be a sign id
                self.old_sign_id = self.sign_id
                video = self.sign_video[0].filename
                old_video = self.sign_video[0].orig_filename
                self.parent().changeSignVideo(self.sign_id, old_video, video)
                
        if self.sign_id == 0:
            video = self.sign_video[0].filename
            self.sign_id = self.parent().addSignVideo(video)    
        
        if not self.sign_id:
            self.save_finished.emit()
            return 
             
        if self.new_gloss_list != self.gloss_list:
            reorder = False
            for gloss in self.new_gloss_list:
                gloss_id = gloss.get(0)
                if isinstance(gloss_id, int) and gloss_id < 1 and not self.new_id: #delete
                    self.parent().removeGloss(gloss, self.sign_id)
                elif isinstance(gloss_id, str) and gloss_id.startswith('-'): #delete new - nothing happens
                    self.new_gloss_list.remove(gloss)
                elif isinstance(gloss_id, str): #new
                    _id = self.parent().addGloss(gloss, self.sign_id)
                    if self.new_sentence_dict.get(gloss_id):
                        sent = self.new_sentence_dict.pop(gloss_id)
                        self.new_sentence_dict[_id] = sent
                    if self.new_dialect_dict.get(gloss_id):
                        dialect = self.new_dialect_dict.pop(gloss_id)
                        self.new_dialect_dict[_id] = dialect                            
                    if self.new_gram_cat_dict.get(gloss_id):
                        _type = self.new_gram_cat_dict.pop(gloss_id)
                        self.new_gram_cat_dict[_id] = _type
                    gloss[0] = _id
                     
                else: #amend
                    new = gloss
                    try:
                        old = [gloss for gloss in self.gloss_list if gloss.get(0) == gloss_id][0]
                    except:
                        old = None
                    self.parent().amendGloss(new, old, self.sign_id) 
                    if new in self.gloss_list and self.gloss_list.index(new) != self.new_gloss_list.index(new):
                        reorder = True
                        
            if reorder:
                gloss_ids = [i.get(0) for i in self.new_gloss_list if int(i.get(0)) > 0]
                self.parent().reorderSenses(self.sign_id, gloss_ids)                                                           
        if self.new_component_list != self.component_list:
            self.parent().amendComponents(self.new_component_list, self.component_list, self.sign_id)
             
        if self.new_sentence_dict != self.sentence_dict:
            gloss_ids = self.new_sentence_dict.keys()
            for gloss_id in gloss_ids:
                new = self.new_sentence_dict.get(gloss_id)
                old = self.sentence_dict.get(gloss_id)
                if new != old:
                    for sent in new:
                        _id, video, texts = sent
                        media = video[1]                  
                        if isinstance(_id, int) and _id < 0: #delete
                            sent_id = abs(_id)
                            self.parent().removeSentence(self.sign_id, gloss_id, sent_id)
                        elif isinstance(_id, str) and _id.startswith('-'):
                            pass
                        elif isinstance(_id, str): #new
                            self.parent().addSentence(media, texts, self.sign_id, gloss_id)
                        else: #amend/update an existing sentence    
                            sentence_id = sent[0]
                            old_sent = [s for s in old if s[0] == sentence_id][0]
                            new_video_id = sent[1][0]
                            new_video = sent[1][1]
                            response = None
                            if len(sent[1]) > 2:
                                response = sent[1][2]
                            #response determines how to handle a replacement; 'all'==2, 'once'==1
                            orig_video_id, orig_video = old_sent[1]
                            new_texts = sent[2]
                            orig_texts = old_sent[2]
                            if new_video.filename != orig_video.filename or new_texts != orig_texts:
                                self.parent().amendSentence(new_video.filename, orig_video.filename, new_texts, orig_texts, self.sign_id, gloss_id, sentence_id, response)
        
        if not self.__compareDialectDicts():
            gloss_ids = self.new_dialect_dict.keys()
            for _id in gloss_ids:
                new = self.new_dialect_dict.get(_id)
                new_str = self.parent().dialectStr(new)
                old = self.dialect_dict.get(_id)
                old_str = self.parent().dialectStr(old)
                if  new_str != old_str:
                    self.parent().addAmendDialects(new_str, old_str, _id, self.sign_id)
        
        if self.new_gram_cat_dict != self.gram_cat_dict:
            gloss_ids = self.new_gram_cat_dict.keys()
            for _id in gloss_ids:
                new = self.new_gram_cat_dict.get(_id)
                old = self.gram_cat_dict.get(_id)
                if new != old:
                    self.parent().amendGramCats(new, self.sign_id, _id)                            
                 
        if self.new_extra_text_dict != self.extra_text_dict:                    
            if self.new_extra_text_dict.get(0) == -1: #deletion
                keys = list(self.new_extra_text_dict.keys())
                lang_ids = [k for k in keys if k > 0]
                for _id in lang_ids:
                    self.parent().removeExText(self.sign_id, _id)
            else:
                self.parent().addAmendExText(self.new_extra_text_dict, self.extra_text_dict, self.sign_id)
        
        if self.new_extra_videos != self.extra_videos:
            self.parent().amendExVideos(self.new_extra_videos, self.extra_videos, self.sign_id)                   
        
        if self.new_extra_pictures != self.extra_pictures:
            self.parent().amendExPictures(self.new_extra_pictures, self.extra_pictures, self.sign_id)
            
        self.finishSave()
    
    def finishSave(self):
        self.parent().backupCurrentProject()            
        #keep glosses in original order when reloading
        if not self.abort_flag:
            if not self.gloss_id or isinstance(self.gloss_id, str):
                try:
                    self.gloss_id = self.new_gloss_list[0].get(0)
                except:
                    self.gloss_id = None
            self.load(self.sign_id, self.gloss_id)
            
            #self.crop_dict.clear()
            #self.rotation_dict.clear()      
            self.delete_flag = False
            self.parent().removeUnusedFiles()
            self.save_finished.emit()
            self.dirty.emit(False)
            self.tempIds.clear()
        else:
            self.dirty.emit(True)
        
    def reload(self):
        self.load(self.sign_id, self.gloss_id, reload=True)
        
    def loadLast(self):
        if self.sign_id == 0: #new sign
            self.load(self.old_sign_id, self.old_gloss_id)
        elif self.sign_id:
            self.reload()
        
    def abortSave(self):
        self.abort_flag = True
        if hasattr(self, 'saver'):
            self.saver.abort()
        
    def cleanupAfterAbort(self): 
        #files = list(self.media_dest_dict.values())
        files = []
        for v in self.media_dest_dict.values(): # values are lists of file(s)
            files.extend(v)        
        
        for f in self.parent().files_2_delete:
            if f.endswith('.old'):
                self.parent().files_2_delete.remove(f) 
        
        for f in files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    self.parent().files_2_delete.append(f)
                else:
                    old = '{}.old'.format(f)
                    if os.path.exists(old):
                        os.rename(old, f)                        
        #NOTE: this is getting called twice on abort for some reason
        # 'till I find out why, clearing the media_dest_dict should prevent this 
        # doing any damage !!! 
        # NOTE: fixed above, but won't hurt to leave this code in just in case... 
        # finished signal emitted when FFmpeg process killed, so no need to explicitly signal finish a second time    
        self.media_dest_dict.clear()
        try:
            self.saver.media_objects.clear()
        except:
            pass
        
    def addComponent(self, code):
        self.new_component_list.append(code)
        self.new_component_list.sort(key=lambda x: eval("0x{}".format(x)))
        _bool = self._dirty()
        self.dirty.emit(_bool)
    
    def removeComponent(self, code):
        self.new_component_list.remove(code) 
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def removeExtraMedia(self, media):
        filename = media.filename
        if self.parent().isVideo(filename):
            self.removeExtraVideo(media)
        elif self.parent().isPicture(filename):
            self.removeExtraPicture(media)
        else:
            self.removeExtraVideo(media) #if some unknown file extension used, assume video
            
    def extraMediaAdded(self):
        _bool = self._dirty()
        self.dirty.emit(_bool)
    
    def addExtraMedia(self, media):
        filename = media.filename
        if self.parent().isVideo(filename):
            self.addExtraVideo(media)
        elif self.parent().isPicture(filename):
            self.addExtraPicture(media)
        else:
            self.addExtraVideo(media) #if some unknown file extension used, assume video
        
    def addExtraVideo(self, media):
        self.new_extra_videos.append(media)
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def removeExtraVideo(self, media):
        for ex_media in self.new_extra_videos:
            if media == ex_media:
                self.new_extra_videos.remove(ex_media)
                break        
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def addExtraPicture(self, media):
        self.new_extra_pictures.append(media)
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def removeExtraPicture(self, media): #filename as full path
        for ex_media in self.new_extra_pictures:
            if media == ex_media:
                self.new_extra_pictures.remove(ex_media)
                break        
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def reorderSenses(self, ids):
        self.new_gloss_list.sort(key=lambda x: ids.index(x.get(0)))
        _bool = self._dirty()
        self.dirty.emit(_bool) 
        
    def addRotation(self):
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def removeRotation(self): 
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def addCrop(self):
        _bool = self._dirty()
        self.dirty.emit(_bool)
        
    def removeCrop(self):
        _bool = self._dirty()
        self.dirty.emit(_bool)     
        
    def addNewGloss(self):
#         if self.sign_id is None:
#             self.sign_id = 0
        gloss_id = self.getTempID()
        new_gloss = {0:gloss_id}
        self.new_gloss_list.append(new_gloss)
        self.new_dialect_dict[gloss_id] = []
        self.new_gram_cat_dict[gloss_id] = []
        _bool = self._dirty()
        self.dirty.emit(_bool)
        self.newGloss.emit(new_gloss)
    
    def addNewSentence(self, filename, gloss_id, texts):
        gloss_id = gloss_id
        sent_id = self.getTempID()
        video_id = self.getTempID()
        media = MediaObject(filename, 'sent')
        new_sentence = [sent_id, [video_id, media], {}]
        if texts:
            new_sentence[2] = texts
        sentences = self.new_sentence_dict.get(gloss_id)
        if not sentences:
            sentences = []
        sentences.append(new_sentence)
        self.new_sentence_dict[gloss_id] = sentences
        _bool = self._dirty()
        self.dirty.emit(_bool)
        self.newSentence.emit((gloss_id, new_sentence))
        
    def __get_codes(self):
        if not hasattr(self, 'new_component_list'):
            self.new_component_list = []
        return self.new_component_list
        
    def get_location_codes(self):
        codes = self.__get_codes()
        location_codes = [c for c in codes if (eval("0x{}".format(c)) >= eval("0x500") and \
                          eval("0x{}".format(c)) < eval("0x1000"))]
        return location_codes
    
    def get_non_location_codes(self):
        """returns non-location codes"""
        codes = self.__get_codes()
        non_location_codes = [c for c in codes if (eval("0x{}".format(c)) < eval("0x500") or \
                            eval("0x{}".format(c)) >= eval("0x1000"))]
        return non_location_codes
    
    def get_extra_videos(self):
        return self.new_extra_video_dict
        
    def get_extra_pictures(self):
        return self.new_extra_picture_dict
    
    def get_primary_gloss(self):
        try:
            pm = self.new_gloss_list[0]
        except:
            return None
        else:
            return pm
    
    def get_primary_dialects(self):
        return self.new_dialect_dict.get(0)
    
    ##!!@pyqtSlot(bool)              
    def onDeleteSign(self, _bool):
        self.delete_flag = _bool               
        
    def get_root(self, media_type='sign'):
        root = os.path.join(self.data_dir, 'signs')
        if media_type == 'ex_video':
            root = os.path.join(self.data_dir, 'extra_videos')
        elif media_type == 'ex_picture':
            root = os.path.join(self.data_dir, 'extra_pictures')
        elif media_type == 'sent':
            root = os.path.join(self.data_dir, 'sentences')
        elif media_type == 'gloss':
            pass #currently same as 'sign'
        return root  
    
    def getSavePath(self, file, media_type):
        _dir = self.get_root(media_type)
        video = QFileInfo(file)
        name = video.baseName()
        if media_type == 'ex_picture':
            new_file = os.path.join(_dir, video.fileName()) #os.path.normpath(os.path.join(_dir, video.fileName()))
        else:
            new_ext = ".mp4"
            settings = qApp.instance().getSettings()
            size = settings.value('Transcoding/current_size', 'medium')
            if size == 'super':
                #new_ext = '.mkv'
                new_ext = os.path.splitext(file)[1]
            
            new_file = os.path.join(_dir, """{}{}""".format(name, new_ext)) #os.path.normpath(os.path.join(_dir, """{}{}""".format(name, new_ext)))
        return new_file
    
class MediaSaver(QObject):
    finished = pyqtSignal()
    
    def __init__(self, parent=None):
        super(MediaSaver, self).__init__(parent)
        
        self.completed = False        
        self.parent().media_dest_dict.clear()
        self.media_objects = []
        _dir = self.parent().get_root('sign')
        video = None
        if (self.parent().sign_video[0].filename != self.parent().sign_video[0].orig_filename) or \
            self.parent().sign_id == 0:
            video = self.parent().sign_video[0]  
                      
        if video:
            _id = self.parent().sign_id            
            video_obj = Video(video, _dir, _id)
            #new_media.append(video)
            self.media_objects.append(video_obj)
            
        _dir = self.parent().get_root('sent')   
        for key in self.parent().new_sentence_dict:
            sents = self.parent().new_sentence_dict.get(key)
            orig_sents = self.parent().sentence_dict.get(key)
            for s in sents:
                sent_id = s[0] 
                if isinstance(sent_id, str) and sent_id.startswith('-'):
                    sents.remove(s)  
                    continue 
                sent_video = s[1]                
                video_id, video = sent_video[:2]
                #video = video.replace('\\', '/')
                if isinstance(video_id, str):# new
                    video_obj = Video(video, _dir, video_id)
                    #new_media.append(video)
                    self.media_objects.append(video_obj)
                elif isinstance(video_id, int): #existing       
                    orig_video = None
                    try:
                        orig_video = [sent for sent in orig_sents if sent[1][0]==video_id][0][1][1]
                    except:
                        pass
                    if orig_video and orig_video != video or \
                        video.filename != video.orig_filename: 
                        video_obj = Video(video, _dir, video_id)
                        #new_media.append(video)
                        self.media_objects.append(video_obj)
                        
        _dir = self.parent().get_root('ex_video')          
        for video in self.parent().new_extra_videos:
            if video.id == 0 or \
                isinstance(video.id, str) or \
                video.rotation or \
                video.crop:
                    video_obj = Video(video, _dir, video.id)
                    #new_media.append(video)               
                    self.media_objects.append(video_obj)
        
        _dir = self.parent().get_root('ex_picture')     
        for picture in self.parent().new_extra_pictures:
            if picture.id == 0 or \
                isinstance(picture.id, str) or \
                picture.rotation or \
                picture.crop:
                    picture_obj = Picture(picture, _dir, picture.id)
                    #new_media.append(picture)
                    self.media_objects.append(picture_obj)
    
    ##!!@pyqtSlot(int, float, str, bool)             
    def onProgress(self, progress, duration, file_pth, complete):
        if duration:
            self.parent().save_progress.emit(file_pth, progress, duration, complete)
        
    def abort(self):
        for obj in self.media_objects:
            obj.abort_save.emit()
            
        if qApp.hasPendingEvents():
            qApp.processEvents()
            
        self.completed = True                
        self.finished.emit()
        
    def save(self): 
        #populate progress dialog 
        for obj in self.media_objects:
            obj.progress.connect(self.onProgress)
            self.onProgress(0, obj.duration, obj.media_object.filename, False)
                 
        for obj in self.media_objects:
            obj.save2dir() 
            self.parent().parent().setDestinationFile(obj.media_object.filename, obj.new_file_path)
            
            while not obj.complete:
                if qApp.hasPendingEvents():
                    qApp.processEvents()
                self.thread().msleep(100)        
        
        if qApp.hasPendingEvents():
            qApp.processEvents()
            
        self.completed = True                
        self.finished.emit()
    
