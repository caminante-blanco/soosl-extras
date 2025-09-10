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

import os, sys
import re

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QSize

from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QGroupBox
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QToolBar
    
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtGui import QCursor

from components.component import Component, ComponentItem, ComponentItemWidget, ComponentItemList
from components import component_type
from components import component_descriptions
from location_widget import LocationView

class ComponentWidget(QTabWidget):
    enableBack = pyqtSignal(bool)
    item_selected = pyqtSignal(str)
    
    def __init__(self, handshape_actions, parent=None):
        super(ComponentWidget, self).__init__(parent)
        self.setTabPosition(QTabWidget.North)
        self.setStyleSheet("""background: White;""")
        
        #self.pm = None
        self.deprecatedCodesAll = qApp.instance().pm.getAllDeprecatedCodes()
        self.deprecatedCodesInProject = [] # codes to be kept visible throughout program session,
        # even if code count is reduced to 0. (deprecated codes)
        self.editing = False
        self.dialect_filter = []
        self.enable_back = 0 
        settings = qApp.instance().getSettings()
        self.use_photo_help = int(settings.value("photoHelp", 1))
        self.compDir = qApp.instance().getComponentImagesDir()
        
        self.signtypePage = QWidget()
        self.handshapePage = QWidget()
        self.motionPage = QWidget()
        self.faceheadPage = QWidget()
        
        self.signtypePage.cat = "signtype"
        self.handshapePage.cat = "handshape"
        self.motionPage.cat = "changenature_changelocation_changemanner_contact"
        self.faceheadPage.cat = "facehead"
        
        self.setupInitialPage(self.signtypePage)
        self.setupInitialPage(self.handshapePage, handshape_actions) 
        self.setupInitialPage(self.motionPage) 
        self.setupInitialPage(self.faceheadPage)
        
        self.addTab(self.signtypePage, qApp.instance().translate('ComponentWidget', "Sign types")) 
        self.addTab(self.handshapePage, qApp.instance().translate('ComponentWidget', "Handshapes"))
        self.addTab(self.motionPage, qApp.instance().translate('ComponentWidget', "Motion"))
        self.addTab(self.faceheadPage, qApp.instance().translate('ComponentWidget', "Face/head/body"))
        self.setTabToolTip(0, qApp.instance().translate('ComponentWidget', "Sign types"))
        self.setTabToolTip(1, qApp.instance().translate('ComponentWidget', "Handshapes"))
        self.setTabToolTip(2, qApp.instance().translate('ComponentWidget', "Motion"))
        self.setTabToolTip(3, qApp.instance().translate('ComponentWidget', "Face/head/body")) 
        
        comp_descriptions = component_descriptions.ComponentDescriptions()
        self.symbol_dict = comp_descriptions.symbol_dict()
        self.symbol_group_dict = comp_descriptions.symbol_group_dict() 
        
    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            comp_descriptions = component_descriptions.ComponentDescriptions()
            self.symbol_dict = comp_descriptions.symbol_dict()
            self.symbol_group_dict = comp_descriptions.symbol_group_dict() 
            self.resetHandshapeToolTips(self.use_photo_help) #this only resets handshapes
            self.resetSignTypeToolTips()
            #self.resetLocationToolTips()
            self.resetMotionToolTips()
            self.resetFaceHeadToolTips()
            self.setTabText(0, qApp.instance().translate('ComponentWidget', "Sign types"))
            self.setTabText(1, qApp.instance().translate('ComponentWidget', "Handshapes"))
            self.setTabText(2, qApp.instance().translate('ComponentWidget', "Locations"))
            self.setTabText(3, qApp.instance().translate('ComponentWidget', "Motion"))
            self.setTabText(4, qApp.instance().translate('ComponentWidget', "Face/head/body"))
            self.setTabToolTip(0, qApp.instance().translate('ComponentWidget', "Sign types"))
            self.setTabToolTip(1, qApp.instance().translate('ComponentWidget', "Handshapes"))
            self.setTabToolTip(2, qApp.instance().translate('ComponentWidget', "Locations"))
            self.setTabToolTip(3, qApp.instance().translate('ComponentWidget', "Motion"))
            self.setTabToolTip(4, qApp.instance().translate('ComponentWidget', "Face/head/body"))
        else:
            QTabWidget.changeEvent(self, evt)
        
    def addLocationsPage(self, loc_page):
        self.locations_page = loc_page
        self.insertTab(2, loc_page, qApp.instance().translate('ComponentWidget', "Locations"))
        self.setTabToolTip(2, qApp.instance().translate('ComponentWidget', "Locations"))
        icn = QIcon(':/body24.png')
        self.__setTabIcons()
        
    def __setTabIcons(self):
        comp = Component(component_type.signTypeLabelCode())
        pth = comp.getIconPth()  
        icn = QIcon(QPixmap(pth))
        self.setTabIcon(0, icn)
        
        comp = Component(component_type.handshapeLabelCode())
        pth = comp.getIconPth()  
        icn = QIcon(QPixmap(pth))
        self.setTabIcon(1, icn)
        icn = QIcon(':/body24.png')
        self.setTabIcon(2, icn)
        
        comp = Component(component_type.motionLabelCode())
        pth = comp.getIconPth() 
        icn = QIcon(QPixmap(pth))
        self.setTabIcon(3, icn)
        
        comp = Component(component_type.faceheadLabelCode())
        pth = comp.getIconPth() 
        
        icn = QIcon(QPixmap(pth))
        self.setTabIcon(4, icn)         
        
    @property
    def display_order(self):
        """how are components displayed? in frequency of use (sign count) or grouped?
        """
        if not qApp.instance().pm.project:
            return 'count' #'count' requires an open database
        if self.editing:
            return 'group'
        else:
            return 'count' #when not editing only order by frequency of use (sign count)
    
    @property
    def show_count(self):
        """should frequency of use (sign count) labels be shown?
        """
        if not qApp.instance().pm.project:
            return False #'count' requires an open database
        settings = qApp.instance().getSettings()             
        return settings.value("componentView/showCount", True)
    
    ##!!@pyqtSlot(QListWidgetItem)
    def locateSymbol(self, item):
        code = item.code
        page_type = component_type.byCode(code)
        page = None
        if page_type == 'signtype':
            page = self.signtypePage
        elif page_type == 'handshape':
            page = self.handshapePage
        elif page_type in ['changenature', 'changelocation', 'changemanner', 'contact']:
            page = self.motionPage
        elif page_type == 'facehead':
            page = self.faceheadPage
            
        if page:
            self.setCurrentWidget(page)
            if page != self.motionPage:
                if page != self.handshapePage:
                    page.itemList.selectByCode(code)
                else: #self.handshapePage
                    if self.editing:
                        group_code = component_type.handshapeGroupCode(code)
                        codes = self.getBaseCodes(group_code)
                        self.setupList(page, codes, level=2)
                    page.itemList.selectByCode(code)
            else: #self.motionPage
                for l in [page.itemList1, page.itemList2, page.itemList3, page.itemList4]:
                    if l.selectByCode(code):
                        pass
                    else:
                        l.clearSelection()
                        
        if page_type == 'location' and hasattr(self, 'locations_page'):
            self.setCurrentWidget(self.locations_page)
    
    ##!!@pyqtSlot(QModelIndex)                
    def onListSelectionChanged(self, model_index):
        selected_list = self.sender()
        for l in [self.motionPage.itemList1, 
                  self.motionPage.itemList2, 
                  self.motionPage.itemList3, 
                  self.motionPage.itemList4]:
            if l is not selected_list:
                l.clearSelection()
                    
    def setupInitialPage(self, page, actions=None):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if page != self.motionPage:            
            itemList = ComponentItemList()
            itemList.setCursor(QCursor(Qt.PointingHandCursor))    
            setattr(page, 'itemList', itemList) 
            if actions:
                toolbar = QToolBar(page)
                toolbar.addActions(actions)
                if hasattr(toolbar, 'addStretch'):
                    toolbar.addStretch()
                layout.addWidget(toolbar)
                
            group = QGroupBox('')
            vlayout = QHBoxLayout()
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.setSpacing(0) 
            vlayout.addWidget(itemList)
            group.setLayout(vlayout)
            layout.addWidget(group)  
            
            if self.display_order == 'group': #show a display of components which is grouped 
                codes = self.getGroupCodes(page.cat)
                self.setupList(page, codes, level=1)
                page.level = 1
        else:
            itemList1 = ComponentItemList()
            itemList1.setCursor(QCursor(Qt.PointingHandCursor))
            itemList2 = ComponentItemList()
            itemList2.setCursor(QCursor(Qt.PointingHandCursor))
            itemList3 = ComponentItemList()
            itemList3.setCursor(QCursor(Qt.PointingHandCursor))
            itemList4 = ComponentItemList()
            itemList4.setCursor(QCursor(Qt.PointingHandCursor))
            
            setattr(page, 'itemList1', itemList1)
            setattr(page, 'itemList2', itemList2)
            setattr(page, 'itemList3', itemList3)
            setattr(page, 'itemList4', itemList4) 
                        
            itemList1.pressed.connect(self.onListSelectionChanged)
            itemList2.pressed.connect(self.onListSelectionChanged)
            itemList3.pressed.connect(self.onListSelectionChanged)
            itemList4.pressed.connect(self.onListSelectionChanged)
            
            group1 = QGroupBox(qApp.instance().translate('ComponentWidget', 'Nature of change'))
            group1.setStyleSheet("""QGroupBox::title {color:gray;}""")
            vlayout = QHBoxLayout()
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.setSpacing(0) 
            vlayout.addWidget(itemList1)
            group1.setLayout(vlayout)
            layout.addWidget(group1)
                       
            group2 = QGroupBox(qApp.instance().translate('ComponentWidget', 'Change of location details'))
            group2.setStyleSheet("""QGroupBox::title {color:gray;}""")
            vlayout = QHBoxLayout()
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.setSpacing(0) 
            vlayout.addWidget(itemList2)
            group2.setLayout(vlayout)
            layout.addWidget(group2) 
            
            group3 = QGroupBox(qApp.instance().translate('ComponentWidget', 'Manner of change'))
            group3.setStyleSheet("""QGroupBox::title {color:gray;}""")
            vlayout = QHBoxLayout()
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.setSpacing(0)  
            vlayout.addWidget(itemList3)
            group3.setLayout(vlayout)
            layout.addWidget(group3)
            
            group4 = QGroupBox(qApp.instance().translate('ComponentWidget', 'Contact'))
            group4.setStyleSheet("""QGroupBox::title {color:gray;}""")
            vlayout = QHBoxLayout()
            vlayout.setContentsMargins(0, 0, 0, 0)
            vlayout.setSpacing(0)  
            vlayout.addWidget(itemList4)
            group4.setLayout(vlayout)
            layout.addWidget(group4)
            
        page.setLayout(layout)
        
    def __getGroupDescription(self, code):
        return self.symbol_group_dict.get(code)
    
    def __getBaseDescription(self, code):
        return self.symbol_dict.get(code)
    
    ##!!@pyqtSlot(bool)  
    def onShowChangeLocationDetails(self, _bool):
        self.motionPage.itemList2.parent().setVisible(_bool)
    
    ##!!@pyqtSlot(int)                
    def onPageChanged(self, idx=0):
        page = self.currentWidget()
        try:
            level = page.level
        except:
            self.enable_back = 1
            if self.editing:
                self.enableBack.emit(False)
        else:
            if level == 1 or \
                page.cat == 'changenature_changelocation_changemanner_contact' or \
                page.cat == 'facehead' or \
                page.cat == 'signtype':
                    self.enable_back = 0
                    if self.editing:
                        self.enableBack.emit(False)
            else:
                self.enable_back = 1
                if self.editing:
                    self.enableBack.emit(True)
                    
    ##!!@pyqtSlot()                  
    def onProjectClosed(self):
        self.onProjectOpen(False)
    
    ##!!@pyqtSlot(bool)
    def onProjectOpen(self, _bool):
        #database required for sign counts
        if _bool == True and qApp.instance().pm.project:
            #self.pm = qApp.instance().pm
            self.dialect_filter = qApp.instance().pm.project.dialects
            self.deprecatedCodesInProject.clear()
            if self.display_order == 'count': #show a display of only those components which have been used by a sign
                for page in [self.signtypePage,
                         self.handshapePage, 
                         self.motionPage, 
                         self.faceheadPage]:
                    codes = self.getUsedCodes(page.cat)
                    deprecated_codes = [c for c in codes if self.isDeprecated(c)]
                    self.deprecatedCodesInProject.extend(deprecated_codes)
                    self.setupList(page, codes, level=2)
    
    ##!!@pyqtSlot(QListWidgetItem)                                        
    def onItemClicked(self, item):
        itemList = self.sender()
        while True:
            try:
                itemList.itemClicked.disconnect(self.onItemClicked)
            except:
                break
        if self.display_order == 'group':
            codes = None
            if hasattr(item, 'code'): # 1st case never used(>=0.9.2). From some older version?
                codes = self.getBaseCodes(item.code)
            else:
                widget = itemList.itemWidget(item)
                if widget:
                    codes = self.getBaseCodes(widget.code)            
            page = itemList.parent().parent() 
            if codes:
                self.setupList(page, codes, level=2)
    
    ##!!@pyqtSlot(list)      
    def filterByDialects(self, dialects):
        if not dialects or len(dialects) == len(qApp.instance().pm.project.dialects):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects
            
        for page in [self.signtypePage,
                     self.handshapePage, 
                     self.motionPage,
                     self.faceheadPage]:
            if self.display_order == 'count': #show a display of only those components which have been used by a sign                
                codes = self.getUsedCodes(page.cat)
                self.setupList(page, codes, level=2)
                    
            elif self.display_order == 'group': #show a display of components which is grouped
                codes = self.getGroupCodes(page.cat)
                if page.cat == 'facehead':
                    self.setupList(page, codes, level=1)
                    
    def __clearConnections(self, page):
        if page.cat != 'changenature_changelocation_changemanner_contact':
            while True:
                try:
                    page.itemList.itemDoubleClicked.disconnect(self.onItemDoubleClicked)
                except:
                    break
        else:
            for l in [page.itemList1, page.itemList2, page.itemList3, page.itemList4]:
                while True:
                    try:
                        l.itemDoubleClicked.disconnect(self.onItemDoubleClicked)
                    except:
                        break
                
    def __clearLists(self, page):
        if hasattr(page, 'itemList'):
            page.itemList.clear()    
        if hasattr(page, 'itemList1'):
            page.itemList1.clear()    
        if hasattr(page, 'itemList2'):
            page.itemList2.clear()    
        if hasattr(page, 'itemList3'):
            page.itemList3.clear()    
        if hasattr(page, 'itemList4'):
            page.itemList4.clear() 
        
    def setupList(self, page, codes, level=1):
        self.__clearConnections(page)
        self.__clearLists(page)
        
        if page.cat == 'signtype':
            description = self.__getBaseDescription
            page.itemList.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.level = 2
            self.enable_back = 0
            if self.editing:
                codes = self.getBaseCodes('1000')
                self.enableBack.emit(False) 
        elif page.cat == 'facehead':
            description = self.__getBaseDescription
            page.itemList.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.level = 2
            self.enable_back = 0
            if self.editing:
                codes = self.getBaseCodes('2ff')
                self.enableBack.emit(False)
                
        elif page.cat == 'changenature_changelocation_changemanner_contact':
            description = self.__getBaseDescription
            page.itemList1.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.itemList2.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.itemList3.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.itemList4.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.level = 2
            self.enable_back = 0
            if self.editing:
                codes = self.getBaseCodes('1010')
                codes.extend(self.getBaseCodes('1020'))
                codes.extend(self.getBaseCodes('1028'))
                codes.extend(self.getBaseCodes('1030'))
                self.enableBack.emit(False)  
                          
        elif level == 1: #handshape groups
            description = self.__getGroupDescription
            page.itemList.itemClicked.connect(self.onItemClicked)
            
            page.level = 1
            self.enable_back = 0
            if self.editing:
                self.enableBack.emit(False)
        elif level == 2: #handshapes
            description = self.__getBaseDescription           
            page.itemList.itemDoubleClicked.connect(self.onItemDoubleClicked)
            page.level = 2
            self.enable_back = 1
            if self.editing:
                self.enableBack.emit(True)  
        for c in codes:
            ####################################################################
            ##NOTE: this block is intended to keep a deprecated code which was in
            # use at program startup to remain visible even if its count was reduced
            # to 0 during the session. If its count is still 0 at the end of the 
            # session, it will not be available the next time SooSL starts, although
            # the code still remains in the database; may be removed completely at 
            # some future date and release.
#             if c in self.keep_visible or not self.isDeprecated(c):
#                 print('show', c)
#             elif self.isDeprecated(c) and self.signCount(c):
#                 self.keep_visible.append(c)
#             else:
#                 continue
            if self.isDeprecated(c) and c not in self.deprecatedCodesInProject:
                continue
            ####################################################################    
                            
            if level == 1 and page.cat == 'handshape': #not in ['facehead', 'signtype', 'changenature_changelocation_changemanner_contact']:
                item = QListWidgetItem()
                item.setSizeHint(QSize(60, 80))
                #item.code = c
                widget = ComponentItemWidget(c)
                widget.setAttribute(Qt.WA_DeleteOnClose)
                page.itemList.addItem(item)
                page.itemList.setItemWidget(item, widget)
                tip = "{} ({})".format(description(c), qApp.instance().translate('ComponentWidget', 'Group'))
                self.addToolTip(item, tip)
            else:
                item = ComponentItem(c) 
                tip = description(c)
                self.addToolTip(item, tip)
                if component_type.byCode(c) in ['handshape', 'signtype', 'facehead']:
                    page.itemList.addItem(item) 
                elif component_type.byCode(c) == 'changenature':
                    page.itemList1.addItem(item)
                elif component_type.byCode(c) == 'changelocation':
                    page.itemList2.addItem(item)
                elif component_type.byCode(c) == 'changemanner':
                    page.itemList3.addItem(item)
                elif component_type.byCode(c) == 'contact':
                    page.itemList4.addItem(item)
               
        if page.cat != 'changenature_changelocation_changemanner_contact':
            self.showCountList(self.show_count, page.itemList)
        else:
            for l in [page.itemList1, page.itemList2, page.itemList3, page.itemList4]:
                self.showCountList(self.show_count, l) 
    
    ##!!@pyqtSlot(bool)          
    def resetHandshapeToolTips(self, photos):
        self.use_photo_help = photos
        itemList = self.handshapePage.itemList
        idxs = range(itemList.count())
        for idx in idxs:
            item = itemList.item(idx)
            tip = ''
            if hasattr(item, 'code'):
                tip = self.__getBaseDescription(item.code)
            else: # Folder - tooltip  'tip (Group)'
                code = item.listWidget().itemWidget(item).code
                tip = self.__getGroupDescription(code)
                tip = "{} ({})".format(tip, qApp.instance().translate('ComponentWidget', 'Group'))
            self.addToolTip(item, tip)
            
    def resetSignTypeToolTips(self):
        itemList = self.signtypePage.itemList
        idxs = range(itemList.count())
        for idx in idxs:
            item = itemList.item(idx)
            tip = self.__getBaseDescription(item.code)
            self.addToolTip(item, tip)
                
#     def resetLocationToolTips(self):
#         for item in self.locations_page.scene.items():
#             print(item.code, item.descript)
# #         itemList = self.locations_page.itemList
# #         idxs = range(itemList.count())
# #         for idx in idxs:
# #             item = itemList.item(idx)
# #             tip = item.toolTip()
# #             descript = re.findall(r"""<descript>(.+)</descript>""", tip)
# #             if descript:
# #                 tip = descript[0]
# #             #self.addToolTip(item, tip)
                
    def resetMotionToolTips(self):
        itemLists = [self.motionPage.itemList1,
            self.motionPage.itemList2, 
            self.motionPage.itemList3,
            self.motionPage.itemList4]
        for itemList in itemLists:             
            idxs = range(itemList.count())
            for idx in idxs:
                item = itemList.item(idx)
                tip = self.__getBaseDescription(item.code)
                self.addToolTip(item, tip)
                
    def resetFaceHeadToolTips(self):
        itemList = self.faceheadPage.itemList
        idxs = range(itemList.count())
        for idx in idxs:
            item = itemList.item(idx)
            tip = self.__getBaseDescription(item.code)
            self.addToolTip(item, tip)
                
    def addToolTip(self, item, description):
        if self.use_photo_help and hasattr(item, 'photoHelpPths'):
            pths = item.component.photo_help_pths()
            if pths:
                img = pths[0]
                description = """<img src='{}'><br><descript>{}</descript>""".format(img, description) 
        item.setToolTip(description)
        
    def isDeprecated(self, code):     
        if code in self.deprecatedCodesAll:
            return True 
        return False   
    
    ##!!@pyqtSlot(QListWidgetItem)                    
    def onItemDoubleClicked(self, item):
        if item.code:
            self.item_selected.emit(item.code)
            
    def getGroupCodes(self, category_str):
        #group codes relate to directory names        
        categories = category_str.split("_")
        _codes = []
        for category in categories:        
            _dir = os.path.join(self.compDir, category)
            codes = [c for c in os.listdir(_dir) if c != ".DS_Store"]
            codes.sort(key=lambda x: eval("0x{}".format(x)))
            #codes.sort(key=lambda x: self.signCount(x), reverse=True)
            _codes = _codes + codes
        return _codes
    
    def getBaseCodes(self, group_code):
        #base codes relate to directory names in the directories under the group directory
        category = component_type.byCode(group_code)
        _dir = os.path.join(self.compDir, category) #category directory
        _dir = os.path.join(_dir, group_code) #dir containing the base code dirs
        codes = []
        codes = [c for c in os.listdir(_dir) if c != ".DS_Store"]
        if codes:
            codes.sort(key=lambda x: eval("0x{}".format(x)))
        #NOTE: order by frequency also? probably...
        #codes.sort(key=lambda x: self.signCount(x), reverse=True)
        return codes
    
    def getUsedCodes(self, category):
        #get all the codes for a category of component which have been used for notating signs
        codes = []
        group_codes = self.getGroupCodes(category)
        for code in group_codes:
            base_codes = self.getBaseCodes(code)
            base_codes = [c for c in base_codes if self.signCount(c)]
            codes += base_codes
        return codes           
    
    def resetIcons(self):
        """reset component icons on componentViewImageChange
        """
        #handshapes are the only components which have alternate icon views
        #others will be added as they are found
        itemList = self.handshapePage.itemList
        count = itemList.count()
        if count:
            for i in range(count):
                item = itemList.item(i)
                if hasattr(item, "resetIcon"):
                    item.resetIcon()
                else:
                    widget = itemList.itemWidget(item)
                    widget.resetIcon()
        itemList.doItemsLayout()
        self.__setTabIcons()      
        
    def signCount(self, item_code):
        """return count of how many signs use this item
        """
        return qApp.instance().pm.signCountByCode2(item_code, self.dialect_filter)
                        
    def showCountList(self, _bool, itemList):
        """set item count labels for specific item list
        """
        count = itemList.count()
        if count:
            for i in range(count):
                item = itemList.item(i)
                
                if hasattr(item, 'code'): #componentItem; single component
                    if bool:
                        sign_count = self.signCount(item.code)
                        ##page_total += sign_count
                        if sign_count:
                            item.setText(str(sign_count))
                    else:
                        item.setText(None)
                else: #normal listWidgetItem with widget attached; component group
                    widget = itemList.itemWidget(item)
                    if _bool:
                        sign_count = self.signCount(widget.code)
                        base_codes = self.getBaseCodes(widget.code)
                        group_sign_count = 0
                        for code in base_codes:
                            group_sign_count += self.signCount(code)
                        widget.setCountText("{0} [{1}]".format(sign_count, group_sign_count))
                    else:
                        widget.setCountText(None)
            itemList.doItemsLayout()
        """#show/hide total count for category on tab labels                                   
        
        page = itemList.parent()
        stacked = page.parent()
        if stacked:
            tabbed = stacked.parent()
            idx = tabbed.indexOf(page)
            text = tabbed.tabText(idx) #, page_total)
            try:
                i = text.index("[")
            except:
                pass
            else:
                text = text[:(i-1)]
            if bool:
                text = "{0} [{1}]".format(text, page_total)
            tabbed.setTabText(idx, text)"""                
    
    ##!!@pyqtSlot(int)
    ##!!@pyqtSlot()        
    def resetPages(self, _all=0):
        for page in [self.signtypePage,
                     self.handshapePage, 
                     self.motionPage, 
                     self.faceheadPage]:
            if _all or page.isVisible():   
                if self.display_order == 'count': #show a display of only those components which have been used by a sign                
                    codes = self.getUsedCodes(page.cat)
                    self.setupList(page, codes, level=2)
                        
                elif self.display_order == 'group': #show a display of components which is grouped
                    codes = self.getGroupCodes(page.cat) 
                    if page.cat == 'facehead' or page.cat == 'signtype' or page.cat == 'changenature_changelocation_changemanner_contact':
                        level = 2
                    else:                        
                        level = 1
                    self.setupList(page, codes, level)
    
    ##!!@pyqtSlot()    
    def enterEditingMode(self):        
        self.editing = True  
        self.resetPages(1)       
        self.currentChanged.connect(self.onPageChanged)           
    
    ##!!@pyqtSlot()    
    def leaveEditingMode(self):
        self.editing = False
        self.resetPages(1)  
        while True:               
            try:
                self.currentChanged.disconnect(self.onPageChanged)
            except:
                break # not connected
                
