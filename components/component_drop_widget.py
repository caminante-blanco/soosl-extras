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

import sys, re

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QSize

from PyQt5.QtGui import QColor, QPixmap, QIcon

from PyQt5.QtWidgets import qApp, QMessageBox
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QPushButton

from components.component import ComponentItem
from components import component_descriptions
from components import component_type

class ComponentDropWidget(QListWidget):
    show_change_location_details = pyqtSignal(bool)
    list_changed = pyqtSignal()
    location_removed = pyqtSignal(str)
    locationItemClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super(ComponentDropWidget, self).__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.pm = qApp.instance().pm
        self.deprecatedCodesAll = self.pm.getAllDeprecatedCodes()
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setFlow(QListView.LeftToRight)
        size = QSize(46, 65)
        self.setSpacing(6)
        self.setIconSize(size)
        self.setMinimumHeight(70)
        self.codeList = []
        self.dialect_filter = []
        self.editing = False
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.settings = qApp.instance().getSettings()
        self.setStyleSheet("""background: white""")

        comp_descriptions = component_descriptions.ComponentDescriptions()
        self.symbol_dict = comp_descriptions.symbol_dict()
        settings = qApp.instance().getSettings()
        self.use_photo_help = int(settings.value("photoHelp", 1))
        self.editable = False

        self.list_changed.connect(qApp.instance().pm.onAmended)
        self.itemClicked.connect(self.onItemClicked)

    def onItemClicked(self, item):
        code = item.code
        location_codes = qApp.instance().pm.get_location_codes_from_list(self.codeList)
        if code in location_codes:
            self.locationItemClicked.emit(code)
        else:
            self.locationItemClicked.emit('')

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange and self.count():
            comp_descriptions = component_descriptions.ComponentDescriptions()
            self.symbol_dict = comp_descriptions.symbol_dict()
            for row in range(self.count()):
                item = self.item(row)
                if item.component.type == 'location':
                    self.addToolTip(item, qApp.instance().translate('ComponentDropWidget', 'Highlight location (yellow) by clicking'))
                else:
                    self.addToolTip(item, self.description(item.code))
        else:
            QListWidget.changeEvent(self, evt)

    def setEditable(self, _bool):
        self.editable = _bool

    def description(self, code):
        return self.symbol_dict.get(code, '')

    ##!!@pyqtSlot(str)
    def onItemSelected(self, code):
        if self.editable:
            self.addComponent(code)

    def mouseReleaseEvent(self, event):
        if self.editable:
            row = self.currentRow()
            if row > -1 and event.button() == Qt.RightButton:
                item = self.takeItem(row)
                self.removeComponentItem(item)
        return super(ComponentDropWidget, self).mouseReleaseEvent(event)

    def dropEvent(self, event):
        if self.editable and event.source() is not self:
            row = self.row(self.itemAt(event.pos()))
            try:
                code = event.source().currentItem().code
            except:
                pass
            else:
                self.addComponent(code, row)

    def removeComponent(self, code):
        try:
            self.codeList.remove(code)
        except:
            pass
        else:
            project = self.pm.project
            if code == component_type.changeLocationCode():
                self.show_change_location_details.emit(False)
                self.__removeChangeLocationDetails()
            #del item
            self.list_changed.emit()
            self.adjustListSize()

    def addComponent(self, code, row=-1):
        item = ComponentItem(code)
        if code in self.codeList:
            title = ' '
            message = '<strong style="color:blue;">{}</strong>'.format(qApp.instance().translate('ComponentDropWidget', 'This parameter has already been added'))
            if component_type.byCode(code) == 'handshape':
                message = '{}<br><br>{}'.format(message, qApp.instance().translate('ComponentDropWidget', 'Use a Sign type parameter to indicate a two handed sign.'))
            mbox = QMessageBox(QMessageBox.Information, title, message, parent=self)
            mbox.setIconPixmap(QPixmap(item.iconPth))
            mbox.exec_()
            del item
            return

        if code in self.deprecatedCodesAll:
            title = ' '
            message = qApp.instance().translate('ComponentDropWidget', 'This parameter may be removed in a future release')
            message2 = qApp.instance().translate('ComponentDropWidget', 'Please tell us if it is important to your project.')
            mbox = QMessageBox(QMessageBox.Information, title, '<strong style="color:blue;">{}</strong><br><br>{}'.format(message, message2), parent=self)
            mbox.setIconPixmap(QPixmap(item.iconPth))
            mbox.exec_()

        if code == component_type.changeLocationCode():
            self.show_change_location_details.emit(True)

        if item.component.type == 'location':
            tip = qApp.instance().translate('ComponentDropWidget', 'Highlight location (yellow) by clicking')
            self.addToolTip(item, tip)
        else:
            self.addToolTip(item, self.description(code))
        self.codeList.append(code)
        self.codeList.sort(key=lambda x: component_type.sortOrder(x))
        row = self.codeList.index(code)
        self.insertItem(row, item)

        self.list_changed.emit()
        self.adjustListSize()

    ##!!@pyqtSlot(bool)
    def resetHandshapeToolTips(self, photos):
        #only handshapes need to be reset
        self.use_photo_help = photos
        idxs = range(self.count())
        for idx in idxs:
            item = self.item(idx)
            tip = item.toolTip()
            descript = re.findall("""<descript>(.+)</descript>""", tip)
            if descript:
                tip = descript[0]
            self.addToolTip(item, tip)

    def addToolTip(self, item, description):
        if self.use_photo_help and hasattr(item, 'photoHelpPths'):
            pths = item.component.photo_help_pths()
            if pths:
                img = pths[0]
                description = f"<img src='{img}'><br><descript>{description}</descript>"
        item.setToolTip(description)

    def removeComponentItem(self, item):
        try:
            self.codeList.remove(item.code)
        except:
            pass
        else:
            if item.code == component_type.changeLocationCode():
                if self.editing:
                    self.show_change_location_details.emit(False)
                self.__removeChangeLocationDetails()
            self.takeItem(self.row(item))
            if item.component.type == 'location':
                self.location_removed.emit(item.code)
            del item
            self.list_changed.emit()
            self.adjustListSize()

    def clearComponents(self):
        """used by external modules for clearing list
        """
        self.clear()
        # project = self.pm.project
        # if project and self.editing:
        #     for code in self.codeList:
        #         project.removeComponent(code)
        self.codeList = []
        # if qApp.hasPendingEvents():
        #     qApp.processEvents()
        self.list_changed.emit()
        self.adjustListSize()
        #QTimer.singleShot(200, self.clear)

    ##!!@pyqtSlot(bool)
    def onDeleteSign(self, _bool):
        """mark gui for delete/undelete"""
        self.setDisabled(_bool)
        color = QColor(Qt.white)
        if _bool:

            self.setStyleSheet("""background: {}""".format(color))
        else:
            self.setStyleSheet(None)

    def __removeChangeLocationDetails(self):
        count = self.count()
        if count:
            for row in reversed(range(count)):
                item = self.item(row)
                if component_type.byCode(item.code) == 'changelocation':
                    item = self.takeItem(row)
                    self.removeComponentItem(item)

    def __checkForChangeLocation(self, codes):
        _bool = False
        for c in codes:
            if c == component_type.changeLocationCode():
                _bool = True
                break
        self.show_change_location_details.emit(_bool)

    def onModelReset(self, sign):
        self.clear()
        if sign:
            codes = self.pm.get_non_location_codes(sign)
            self.codeList = codes
            location_codes = []
            #if self.editing:
            location_codes = self.pm.get_location_codes(sign)
            codes.extend(location_codes)
            codes = sorted(codes, key=lambda x: component_type.sortOrder(x))
            if self.editing:
                self.__checkForChangeLocation(codes)
            else:
                self.show_change_location_details.emit(True)
            for code in codes:
                item = ComponentItem(code, self)
                tip = self.description(code)
                if code in location_codes:
                    tip = qApp.instance().translate('ComponentDropWidget', 'Highlight location (yellow) by clicking')
                item.setToolTip(tip)

            self.adjustListSize()

    def getSignData(self):
        ## the location parameters are really on used in this widget for display and editing purposes;
        ## remove them before returning data
        comp_codes = qApp.instance().pm.get_non_location_codes_from_list(self.codeList)
        return {"componentCodes": comp_codes}

    #@property
    def dirty(self):
        orig_codes = []
        try:
            #print('try', qApp.instance().pm.sign.id)
            orig_codes = qApp.instance().pm.sign.component_codes
        except:
            try:
                orig_codes = qApp.instance().pm.sign.get('componentCodes', [])
            except:
                pass # probably no sign after deletion
        # print(sorted(orig_codes))
        # print(sorted(self.codeList))
        if sorted(orig_codes) != sorted(self.codeList):
            return True
        return False

    ##!!@pyqtSlot(list)
    def filterByDialects(self, dialects):
        if not dialects or len(dialects) == len(self.pm.getAllDialects()):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects

    ##!!@pyqtSlot()
    def enterEditingMode(self):
        self.setAcceptDrops(True)
        if not self.editing:
            self.editing = True
            self.editable = True
            self.setEnabled(True)
            self.onModelReset(self.pm.sign)

    ##!!@pyqtSlot()
    def leaveEditingMode(self):
        self.setAcceptDrops(False)
        self.editing = False
        self.editable = False
        self.setStyleSheet(None)
        self.setEnabled(True)

    def resetIcons(self):
        """reset component icons on componentViewImageChange
        """
        count = self.count()
        if count:
            for i in range(count):
                self.item(i).resetIcon()
        self.doItemsLayout()
        self.adjustListSize()

    def adjustListSize(self):
        grid_w = 0
        idx = 0
        while True:
            w = self.sizeHintForColumn(idx)
            if w == -1:
                break
            else:
                grid_w = max(w, grid_w)
            idx += 1

        grid_h = 0
        idx = 0
        while True:
            h = self.sizeHintForRow(idx)
            if h == -1:
                break
            else:
                grid_h = max(h, grid_h)
            idx += 1
        grid_h = grid_h + 12
        self.setGridSize(QSize(grid_w, grid_h))
        if grid_w:
            col_count = self.width()//grid_w
            try:
                row_count = self.count()//col_count + 1
            except:
                row_count = self.count()
            item_count = self.count()
            new_height = row_count*grid_h
            if new_height != self.height() and \
                item_count+col_count != col_count*row_count: #condition when row is full; don't change height until item for next line added
                self.setFixedHeight(new_height)

    def resizeEvent(self, *args, **kwargs):
        QListWidget.resizeEvent(self, *args, **kwargs)
        self.adjustListSize()

    def onAddLocationItem(self, code, _bool):
        if _bool:
            self.addComponent(code)
        else:
            idx = 0
            item = self.item(idx)
            while item:
                if item.code == code:
                    self.removeComponentItem(item)
                    break
                idx += 1
                item = self.item(idx)

class ClearParametersButton(QPushButton):
    def __init__(self, parameter_list, parent):
        icn = QIcon(':/clear_search.png')
        super(ClearParametersButton, self).__init__(icn, '', parent)
        self.setAcceptDrops(True)
        self.setFlat(True)
        self.setMinimumHeight(24)
        self.setIconSize(QSize(24, 24))
        self.parameter_list = parameter_list

    def dropEvent(self, evt):
        source = evt.source()
        if source is self.parameter_list:
            item = source.currentItem()
            source.removeComponentItem(item)

    def dragEnterEvent(self, evt):
        source = evt.source()
        if source is self.parameter_list:
            evt.accept()
