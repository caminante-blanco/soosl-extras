#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtCore import pyqtSignal, Qt, QSortFilterProxyModel, QRect
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtGui import QStandardItem, QStandardItemModel

import linux_keyboard

class KeyboardComboBox(QComboBox):
    current_keyboard_changed = pyqtSignal(str)
    
    def __init__(self, *args):
        super().__init__(*args)
        self.currentIndexChanged.connect(self.onCurrentIndexChanged)
        self.current_lang = None #'English'
        self.current_item = None #source item
        self.orig_text = None
        
        kbd = linux_keyboard.Keyboard()
        model = QStandardItemModel()
        languages = list(kbd.kbdict.keys())
        languages.sort()
        for language in languages: 
            keyboards = list(kbd.kbdict.get(language))
            keyboards.sort()
            language_item = QStandardItem(language)
            language_item.setForeground(Qt.blue)
            f = language_item.font()
            f.setBold(True)
            language_item.setFont(f)
            language_item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
            language_item.lang = None
            model.appendRow([language_item])
            for _, keyboard_name in keyboards:                  
                keyboard_item = QStandardItem('    {}'.format(keyboard_name)) 
                keyboard_item.lang = language
                model.appendRow([keyboard_item])
                
        proxy_model = KeyboardSortFilterProxyModel(self)
        proxy_model.setSourceModel(model)
        self.setModel(proxy_model)
                
        self.view().activated.connect(self.onActivated)
        self.view().pressed.connect(self.view().activated)
        
    def onPressed(self, idx):
        pass
        
    def onActivated(self, idx): # responds on Double-click and Enter
        src_idx = self.model().mapToSource(idx)
        item = self.model().sourceModel().itemFromIndex(src_idx)
        self.current_item = item
        if item:
            if not item.lang:
                self.current_lang = item.text()
            else:
                self.current_lang = item.lang
        self.model().invalidateFilter()
        
    def setCurrentText(self, text):
        if text:
            self.orig_text = text
            text = text.rstrip(']')
            try:
                language, keyboard_name = text.split('[')
            except:
                self.setCurrentIndex(-1)
            else:
                self.current_lang = language
                self.model().invalidateFilter()
                items = self.model().sourceModel().findItems('    {}'.format(keyboard_name))
                for item in items:
                    if item.lang == language: #need to find item as some languages use same keyboard name
                        idx = self.model().mapFromSource(item.index())
                        self.setCurrentIndex(idx.row()) 
        else:
            self.setCurrentIndex(-1)                  

    def onCurrentIndexChanged(self, row):
        idx = self.model().index(row, 0)
        src_idx = self.model().mapToSource(idx)
        item = self.model().sourceModel().itemFromIndex(src_idx)
        if item:
            lang = item.lang
            if not lang: #language item
                pass
            else: #keybaord item
                keyboard = item.text().strip()
                keyboard_name = '{}[{}]'.format(lang, keyboard)
                self.current_keyboard_changed.emit(keyboard_name)
        
    def showPopup(self):
        super().showPopup()
        popup = self.view().parent()
        #popup.installEventFilter(self)
        w = self.width()
        combo = popup.parent()
        pos = self.parent().mapToGlobal(combo.pos())
        x, y = pos.x(), pos.y()
        h = 400
        popup.setGeometry(x, y, w, h)
        
    def hidePopup(self):
        popup = self.view().parent()
        mouse_pos = self.mapToGlobal(self.cursor().pos())
        popup_pos = self.mapToGlobal(popup.pos())
        popup_rect = QRect(popup_pos, popup.size())
        if self.current_item and self.current_item.lang:
            super().hidePopup()
            return
        if not popup_rect.contains(mouse_pos):
            super().hidePopup()
            self.setCurrentText(self.orig_text)
               
class KeyboardSortFilterProxyModel(QSortFilterProxyModel): 
    def __init__(self, parent=None):
        super(KeyboardSortFilterProxyModel, self).__init__(parent)
         
    def filterAcceptsRow(self, src_row, src_parent):
        idx = self.sourceModel().index(src_row, 0, src_parent)
        item = self.sourceModel().itemFromIndex(idx)
        if item.lang != self.parent().current_lang and item.lang is not None:
                return False
        return True        
     