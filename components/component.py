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

import sys, os

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint

from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPainter

from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QLabel

from components import component_type
from components import component_descriptions
    
import code

class Component(QObject):
    def __init__(self, code, parent=None):
        super(Component, self).__init__(parent)
        self.code = code
        
        self.type = component_type.byCode(code) 
        self.dir = qApp.instance().getComponentImagesDir()       
        self.pth = self.get_code_path(self.type, self.code)
        
    @property
    def iconType(self):
        settings = qApp.instance().getSettings()
        return settings.value("componentView/imageType", 'photo')
        
    def getIconPth(self):
        pth = None
        if self.type == 'location':
            return ''
        if self.iconType == 'photo': 
            if os.path.exists(self.__photo_pth()):
                pth = self.__photo_pth()
            elif os.path.exists(self.__drawing_pth()):
                pth = self.__drawing_pth()
            elif os.path.exists(self.__sw_pth()): #if self.iconType ==3 or no photo or drawing pth
                pth = self.__sw_pth()
        elif self.iconType == 'drawing': 
            if os.path.exists(self.__drawing_pth()):
                pth = self.__drawing_pth()
            elif os.path.exists(self.__photo_pth()):
                pth = self.__photo_pth()           
            elif os.path.exists(self.__sw_pth()): #if self.iconType ==3 or no photo or drawing pth
                pth = self.__sw_pth()
        elif self.iconType == 'signwriting': 
            if os.path.exists(self.__sw_pth()): #if self.iconType ==3 or no photo or drawing pth
                pth = self.__sw_pth()
            elif os.path.exists(self.__photo_pth()):
                pth = self.__photo_pth()
            elif os.path.exists(self.__drawing_pth()):
                pth = self.__drawing_pth()
        if not pth:
            return ''
        return pth         
        
    def __sw_pth(self):
        if self.pth:
            pth = os.path.join(self.pth, '{}00.png'.format(self.code))
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}10.png'.format(self.code))
                #pth might not exist; check in any calling methods
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}00.png'.format(self.code))
            return pth
        return ''
    
    def __drawing_pth(self):
        if self.pth:
            pth = os.path.join(self.pth, '{}00_draw.png'.format(self.code))
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}10_draw.png'.format(self.code))            
                #pth might not exist; check in any calling methods
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}00.png'.format(self.code))
            return pth
        return ''
    
    def __photo_pth(self):
        if self.pth:
            pth = os.path.join(self.pth, '{}00.jpg'.format(self.code))
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}10.jpg'.format(self.code))            
                #pth might not exist; check in any calling methods
            if not os.path.exists(pth):
                pth = os.path.join(self.pth, '{}00.png'.format(self.code))
            return pth
        return ''
    
    def photo_help_pths(self):
        if not self.pth:
            return []
        #images = ['a.jpg', 'b.jpg', 'c.jpg']
        images = ['{}00_photo_help.jpg'.format(self.code)]
        return [os.path.join(self.pth, i) for i in images if os.path.exists(os.path.join(self.pth, i))]
    
    def get_code_path(self, _type, code):
        cat_dir = None
        try:
            cat_dir = os.path.join(self.dir, _type)
        except:
            return ''
        else: 
            if os.path.exists(cat_dir):           
                base_dirs = os.listdir(cat_dir)
                base_dirs = [d for d in base_dirs if d != ".DS_Store"]
                dirs = sorted(base_dirs, key=lambda x: eval("0x{}".format(x))) 
                possible_d = '100' #lowest possible base
                for d in dirs:
                    if code == d:
                        return os.path.join(cat_dir, d, code)
                    elif "0x{}".format(code) < "0x{}".format(d):
                        return os.path.join(cat_dir, possible_d, code)
                    elif "0x{}".format(code) > "0x{}".format(d):
                        possible_d = d
                return os.path.join(cat_dir, possible_d, code)
            return ''
    
class ComponentItem(QListWidgetItem):
    def __init__(self, code, parent=None):
        super(ComponentItem, self).__init__(parent)
        self.component = Component(code)
        self.code = self.component.code
        self.resetIcon()
        self.photoHelpPths = self.component.photo_help_pths()

    # def mouseReleaseEvent(self, event):
    #     pass #print('released', event.pos())
    
    @property    
    def iconPth(self):
        return self.component.getIconPth()
        
    def resetIcon(self):
        pth = self.iconPth
        if self.component.type == 'location':
            pth = ':/body24.png' #just a generic location image for now            
        elif pth and not os.path.exists(pth) or \
            not pth:
            pth = ':/question.png'
            self.setText(self.code)            
        pixmap = QPixmap(pth)
        icon = QIcon(pixmap)
        try:
            self.setIcon(icon)
        except:
            self.setPixmap(pixmap)
            
class ComponentItemWidget(QFrame):
    def __init__(self, code, parent=None):
        super(ComponentItemWidget, self).__init__(parent)
        self.component = Component(code)
        self.code = self.component.code
        self.photoHelpPths = self.component.photo_help_pths()
        self.photo_dlg = None
        comp_descriptions = component_descriptions.ComponentDescriptions()
        self.symbol_group_dict = comp_descriptions.symbol_group_dict()    
        
        self.settings = qApp.instance().getSettings()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignCenter)
        pxm = QPixmap(self.iconPth)
        self.imageLabel.setPixmap(pxm)
        pth = ":/folder.png"
        lst = pth.split("\\")
        pth = "/".join(lst)
        self.imageLabel.setStyleSheet("""background-image: url({0}); 
                           background-repeat: no-repeat; 
                           background-position: center center""".format(pth))
        
        self.countLabel = QLabel()
        self.countLabel.setFixedHeight(16)
        self.countLabel.setAlignment(Qt.AlignBottom | Qt.AlignCenter)
        
        layout.addWidget(self.imageLabel)
        layout.addWidget(self.countLabel, 0)
        self.setLayout(layout)        
        
        self.resetIcon()
            
    @property    
    def iconPth(self):
        pth = self.component.getIconPth()
        _type = self.component.type
        if _type == "handshape" and self.component.iconType != "signwriting":
            root = os.path.splitext(pth)[0]
            pth = "{}_folder.png".format(root)
        return pth
    
    @property
    def description(self):
        return "{} ({})".format(self.symbol_group_dict[self.code], qApp.instance().translate('ComponentItemWidget', 'Group'))
        
    def resetIcon(self):
        pxm = QPixmap(self.iconPth)
        self.imageLabel.setPixmap(pxm)
        
    def setCountText(self, sign_count):
        #sign_count represents signs which use this component; since this is a group component,
        # we also need to find the count for all the components in this group
        self.countLabel.setText(sign_count)
                
class ComponentItemList(QListWidget):
    def __init__(self, parent=None):
        super(ComponentItemList, self).__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setFlow(QListView.TopToBottom) 
        self.setStyleSheet('border:0;') 
        self.setSpacing(6)
        w = 46
        h = 65
        size = QSize(w, h)
        self.setIconSize(size)
        self.setMouseTracking(True)
        self.current_code = None
        self.photo_dlg = None
        self.setDragEnabled(True) 
        self.setAcceptDrops(False)
        self.settings = qApp.instance().getSettings()
        comp_descriptions = component_descriptions.ComponentDescriptions()
        self.symbol_dict = comp_descriptions.symbol_dict()
        
    def selectByCode(self, code):
        idx = 0
        item = self.item(idx)
        while item:
            if item.code == code:
                self.setCurrentItem(item)
                return True
            idx += 1
            item = self.item(idx)  
        return False  
        