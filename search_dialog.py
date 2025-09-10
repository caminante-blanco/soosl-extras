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
import sys, copy, time

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QTimer

from PyQt5.QtGui import QIcon, QKeySequence

from PyQt5.QtWidgets import QPushButton, QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QMessageBox

from components.component_drop_widget import ClearParametersButton, ComponentDropWidget
from components.component_widget import ComponentWidget
from location_widget import LocationView
from media_saver import MediaSaver

class SearchComponentWidget(ComponentWidget):
    def __init__(self, handshape_actions, parent=None):        
        super(SearchComponentWidget, self).__init__(handshape_actions, parent=parent)

    def filterByDialects(self, dialects):
        current_codes = self.parent().comps
        project = qApp.instance().pm.project
        if not dialects or (project and len(dialects) == len(project.dialects)):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects
            
        for page in [self.signtypePage,
                     self.handshapePage, 
                     self.motionPage,
                     self.faceheadPage]:
            codes = self.getUsedCodes(page.cat)
            if current_codes:
                codes = [c for c in codes if c in current_codes]
            self.setupList(page, codes, level=2)
        self.parent().filterByDialects()
    
class SearchDlg(QWidget):
    """Dialog used for searching"""
    
    search_signs = pyqtSignal(list)
    compview_order_change = pyqtSignal()
    photo_help_changed = pyqtSignal(bool)
    project_open = pyqtSignal(bool)
    project_closed = pyqtSignal()
    clear_search = pyqtSignal()
    
    def __init__(self, parent=None):        
        super(SearchDlg, self).__init__(parent=parent)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout()        
        
        self.already_cleared = True
        self.last_signs = []
        
        # add search and clear buttons; let's put them at the top since they were at the top, in the toolbar of the mainwindow
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)

        self.comp_search_list = ComponentDropWidget()
        self.comp_search_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.comp_search_list.setWrapping(True)
        self.comp_search_list.setEditable(True)
        self.comp_search_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_search_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comp_search_list.list_changed.connect(self.onCompListChanged)
        self.comp_search_list.installEventFilter(self)
        hlayout.addWidget(self.comp_search_list)
        
        self.clear_btn = ClearParametersButton(self.comp_search_list, self)
        self.clear_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.clear_btn.setToolTip(qApp.instance().translate('SearchDlg', 'Click to remove all search parameters, or \
            <br>Drag and drop a single parameter onto this icon to remove it.\
            <br>Right-click on a parameter also removes it.'))
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.onClear)
        hlayout.addWidget(self.clear_btn)
        #hlayout.setAlignment(self.clear_btn, Qt.AlignLeft)
        #hlayout.addStretch()        
        layout.addLayout(hlayout)        
        #layout.addWidget(self.comp_search_list)
        
        self.comp_widget = SearchComponentWidget(None, self)
        self.comp_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.project_open.connect(self.comp_widget.onProjectOpen)
        self.project_closed.connect(self.comp_widget.onProjectClosed)
        
        self.location_widget = LocationView(searching=True)
        self.project_open.connect(self.location_widget.onProjectOpen)
        self.project_closed.connect(self.location_widget.onProjectClosed)
        self.comp_widget.addLocationsPage(self.location_widget)
        layout.addWidget(self.comp_widget)
        
        self.setLayout(layout)  

        self.comp_search_list.list_changed.connect(self.onSearch)

        #self.location_widget.scene.enterEditingMode()
        self.location_widget.scene.item_selected.connect(self.onSearch)
        
        self.location_widget.scene.item_selected.connect(self.comp_search_list.onAddLocationItem)
        self.comp_widget.item_selected.connect(self.comp_search_list.onItemSelected)
        self.comp_search_list.itemDoubleClicked.connect(self.comp_widget.locateSymbol)
        self.comp_search_list.show_change_location_details.connect(self.comp_widget.onShowChangeLocationDetails)
        self.comp_search_list.location_removed.connect(self.location_widget.scene.deselectItem)
        self.comp_search_list.locationItemClicked.connect(self.location_widget.onLocationItemClicked)   
        
        self.used_location_comps = [] #qApp.instance().pm.get_used_location_codes()
        self.comps = []
        self.signs_found = []
        
    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.clear_btn.setToolTip(qApp.instance().translate('SearchDlg', 'Click to remove all search parameters, or \
                <br>Drag and drop a single parameter onto this icon to remove it.\
                <br>"Right-click" on a parameter also removes it.'))
        else:
            QWidget.changeEvent(self, evt)
        
    def eventFilter(self, obj, evt):
        if not obj.count() and not self.already_cleared:
            self.already_cleared = True 
            self.clear_search.emit()
            self.clear_btn.setEnabled(False)
        elif obj.count() and self.already_cleared:
            self.already_cleared = False
            self.clear_btn.setEnabled(True)
        return QWidget.eventFilter(self, obj, evt)
    
    def onCompListChanged(self):
        if not len(self.comp_search_list.codeList):
            self.clear_btn.setEnabled(False)
            self.location_widget.clearLocations()
            self.comps.clear()
            self.signs_found.clear()
            #self.onSignsFound(self.signs_found)
            self.comp_widget.filterByDialects(self.comp_widget.dialect_filter)
            self.clear_search.emit()
        else:
            self.clear_btn.setEnabled(True)
            self.showOnlyUsedComponents(self.comp_search_list.codeList)

    def filterByDialects(self):
        self.showOnlyUsedComponents(self.comps) #all components for signs found
        
    def showEvent(self, evt):
        self.used_location_comps = qApp.instance().pm.get_used_location_codes()
        self.showOnlyUsedComponents(self.comps)
        super(SearchDlg, self).showEvent(evt) 
    
    ##!!@pyqtSlot(list)     
    def onSignsFound(self, signs):
        if self.last_signs != signs:
            self.last_signs = signs
            if qApp.instance().searchType != 'comp' or not self.isVisible():
                return
            project = qApp.instance().pm.project
            if not project:
                return
            if qApp.instance().editing:
                self.updateComponents()
            self.signs_found = [s for s in signs if s]
            if self.signs_found:
                comps = []
                for sign in self.signs_found:
                    _comps = project.getComponents(sign.id)
                    comps.extend(_comps)
                self.showOnlyUsedComponents(comps)
            elif self.comp_search_list.codeList:
                mw = qApp.instance().getMainWindow()
                box = QMessageBox(mw)
                box.setWindowTitle(' ')
                txt = qApp.instance().translate('EditProjectInfoDlg', 'Your current search can find no more signs.')
                txt2 = qApp.instance().translate('EditProjectInfoDlg', 'Clear the search field to continue.')
                msg = f'{txt}\n\n{txt2}'
                box.setText(msg)
                box.setIcon(QMessageBox.Information)
                box.exec_()
                #QTimer.singleShot(0, self.onClear)
            
    ##!!@pyqtSlot() 
    def onSearch(self):    
        if (not qApp.instance().closing and 
            not qApp.instance().pm.editing and 
            isinstance(self.sender(), (ComponentDropWidget, MediaSaver))):
                self.search_signs.emit(self.comp_search_list.codeList)
        # if qApp.instance().editing:
        #     print('search disabled during edit???')
            # codes = self.comp_search_list.codeList
            # qApp.instance().pm.findSignsByComponents(codes, signal=False)
            # self.onSignsFound(qApp.instance().pm.signs)
            # # saving but not leaving edit, asks again to save when i leave???

    def resetIcons(self):
        self.comp_search_list.resetIcons()
        self.comp_widget.resetIcons()
        
    def updateComponents(self):
        """used when component(s) have been added/removed from a sign"""
        self.comp_widget.resetPages(1)
        
    def getShortcutString(self, key_sequence):
        try:
            _str = [q.toString(QKeySequence.NativeText) for q in QKeySequence.keyBindings(key_sequence)][0]
        except:
            return ""
        else:
            return _str 
    
    ##!!@pyqtSlot(bool)    
    def onProjectOpen(self, _bool):
        self.used_location_comps = qApp.instance().pm.get_used_location_codes()
        self.showOnlyUsedComponents()
        self.project_open.emit(_bool)
     
    ##!!@pyqtSlot()     
    def onProjectClosed(self):
        self.used_location_comps = []
        self.project_closed.emit()
    
    ##!!@pyqtSlot() 
    def onClear(self):
        self.clear_btn.setEnabled(False)
        self.comp_search_list.clearComponents()
        
    def showOnlyUsedComponents(self, comps=[]):
        #once a search filter is applied, show only those components that are used in the list of filtered signs
        self.comps = comps
        comp_set = None
        if comps:
            comp_set = list(set(comps))
        idx = 0
        widget = self.comp_widget.widget(idx)
        item_lists = []
        loc_items = []
        while widget:
            if isinstance(widget, LocationView):
                loc_items = widget.scene.items()
                item_lists.append(loc_items)
            else:
                if widget is not self.comp_widget.motionPage:
                    item_lists.append(widget.itemList)
                else:
                    item_lists.extend([widget.itemList1, widget.itemList2, widget.itemList3, widget.itemList4])       
            idx += 1
            widget = self.comp_widget.widget(idx)
        items = []
        for l in item_lists:
            if isinstance(l, list): #location items
                items.extend(l)
                self.location_widget.scene.update()
            else:
                i = 0
                item = l.item(i)
                while item:                    
                    items.append(item)
                    i += 1
                    item = l.item(i) 
                if not comp_set:
                    self.comp_widget.showCountList(True, l) 
        for item in items:
            if comp_set:
                if item.code != '0' and item.code in comp_set:
                    if hasattr(item, 'listWidget'):
                        count = str(comps.count(item.code))
                        item.setText(count) #, item.text())
                    try:
                        item.setHidden(False) #item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    except:
                        item.setVisible(True)
                elif item.code != '0':
                    try:
                        item.setHidden(True) #item.setFlags(item.flags() ^ Qt.ItemIsEnabled) 
                    except:
                        item.setVisible(False)
            else:
                if item in loc_items and item.code != '0' and item.code not in self.used_location_comps:
                    try:
                        item.setHidden(True) #item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    except:
                        item.setVisible(False) 
                else:
                    try:
                        item.setHidden(False) #item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    except:
                        item.setVisible(True) 

            
class MyAction(QAction):
    set_visible = pyqtSignal(bool)
    def __init__(self, *args, **kwargs):
        super(MyAction, self).__init__(*args, **kwargs)
        
    def setVisible(self, _bool):
        super(MyAction, self).setVisible(_bool)
        qApp.processEvents()
        self.set_visible.emit(_bool)     
                

if __name__ == '__main__':
    from mainwindow import main
    main()
