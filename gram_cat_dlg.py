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

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QEvent

from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QCursor

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QMessageBox

NAME_COL = 0
SIGN_COUNT_COL = 1
SENSE_COUNT_COL = 2
REMOVE_COL = 3
ID_COL = 4

class GramCatWidget(QWidget):
    saveReady = pyqtSignal(bool) 
    close_signal = pyqtSignal()
     
    def __init__(self, parent=None, edit=False):
        super(GramCatWidget, self).__init__(parent=parent)
        self.edit = edit 
        self.able_to_edit = qApp.instance().pm.ableToEdit() 
        
        layout = QVBoxLayout()
        
        label = QLabel(qApp.instance().translate('GramCatWidget', "GRAMMAR CATEGORIES WHICH?"))
        label.setStyleSheet("color: blue")
        layout.addWidget(label)
        
        self.typeTable = QTableWidget()
        self.typeTable.itemChanged.connect(self.onGramCatItemChanged)
        self.typeTable.setTabKeyNavigation(True)
        self.typeTable.itemSelectionChanged.connect(self.onCellChange)
        self.typeTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.typeTable.setShowGrid(False)
        self.typeTable.horizontalHeader().setStretchLastSection(True)
        self.typeTable.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.typeTable.verticalHeader().hide()
        self.typeTable.setColumnCount(5)
        self.typeTable.setColumnHidden(ID_COL, True) #id column
        self.typeTable.setHorizontalHeaderLabels(["{}".format(qApp.instance().translate('GramCatWidget', 'Name')), qApp.instance().translate('GramCatWidget', 'Signs'), qApp.instance().translate('GramCatWidget', 'Senses'), "", ""])
        self.typeTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.typeTable.itemClicked.connect(self.onItemClicked)
        self.typeTable.setItemDelegate(GramCatItemDelegate(self.typeTable))
        layout.addWidget(self.typeTable)
        
        hlayout = QHBoxLayout()
        self.addGramCatBtn = QPushButton(QIcon(":/add.png"), "")
        self.addGramCatBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.addGramCatBtn.setToolTip(qApp.instance().translate('GramCatWidget', "More grammar categories? Click here to add one more"))
        self.addGramCatBtn.setEnabled(False)
        self.addGramCatBtn.clicked.connect(self.onAddGramCat)
        hlayout.addStretch()
        hlayout.addWidget(self.addGramCatBtn)
        layout.addLayout(hlayout)
        
        self.setLayout(layout) 
        
        self.inFirstCell = False
        self.inLastCell = False
        # if not edit:
        #     self.onAddGramCat()
            
        QTimer.singleShot(0, self.typeTable.scrollToTop)
        #if not self.able_to_edit:
        self.typeTable.horizontalHeader().setStretchLastSection(False)
        self.typeTable.setColumnHidden(REMOVE_COL, True)
        self.addGramCatBtn.setHidden(True)

    def setupEditing(self):
        #if not self.able_to_edit:
        self.typeTable.horizontalHeader().setStretchLastSection(True)
        self.typeTable.setColumnHidden(REMOVE_COL, False)
        for row in range(self.typeTable.rowCount()):
            name_item = self.typeTable.item(row, 0)
            name_item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable)

        self.addGramCatBtn.setHidden(False)
        
    def __undeletedCount(self):
        count = 0
        for row in range(self.typeTable.rowCount()):
            if self.typeTable.item(row, REMOVE_COL).data(Qt.UserRole) == 1:
                count += 1
        return count
        
    @property
    def gram_cats(self):
        return self.getGramCat()
        
    def setInitialFocus(self):
        self.typeTable.setFocus()
        self.typeTable.setTabKeyNavigation(True)
        row = self.typeTable.rowCount() - 1
        item = self.typeTable.item(row, NAME_COL)
        self.typeTable.setCurrentItem(item)
        item.setSelected(True)
        if row == 0 and not item.text():
            self.typeTable.editItem(item)

    def reloadProject(self):
        mw = qApp.instance().getMainWindow()
        mw.reloadProject()
    
    ##!!@pyqtSlot(QTableWidgetItem)   
    def onItemClicked(self, item):
        col = item.column()
        row = item.row()
        if col == REMOVE_COL:
            nameItem = self.typeTable.item(row, NAME_COL)
            if not nameItem.data(Qt.UserRole):
                self.typeTable.removeRow(row)
                self.onReadyToSave()
                #self.addGramCatBtn.setEnabled(True)
            elif item.data(Qt.UserRole) == 1:
                item.setData(Qt.UserRole, -1)
                item.setIcon(QIcon(":/trash24_red.png"))
                count = int(self.typeTable.item(row, SIGN_COUNT_COL).text())
                if count:
                    name = nameItem.text()
                    msgBox = QMessageBox(self)
                    self.close_signal.connect(msgBox.close)
                    msgBox.setIcon(QMessageBox.Warning)
                    msgBox.setTextFormat(Qt.RichText)
                    msgBox.setWindowTitle(qApp.instance().translate('GramCatWidget', "Delete Grammatical Category"))
                    t1 = qApp.instance().translate('GramCatWidget', 'Sign(s) use this grammar category:')
                    t2 = qApp.instance().translate('GramCatWidget', 'It will be removed from these signs if you continue.')
                    text = "<b><span style='color:blue;'>{}</span> {} <span style='color:blue;'> {}</span></b><br><br>{}".format(count, t1, name, t2)
                    msgBox.setText(text)
                    msgBox.setInformativeText(qApp.instance().translate('GramCatWidget', "Is this what you want to do?"))
                    msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                    yes_btn, no_btn = msgBox.buttons()
                    yes_btn.setIcon(QIcon(":/thumb_up.png"))
                    no_btn.setIcon(QIcon(":/thumb_down.png"))
                    msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('GramCatWidget', "Yes"))
                    msgBox.button(QMessageBox.No).setText(qApp.instance().translate('GramCatWidget', "No"))
                    msgBox.setDefaultButton(QMessageBox.No)
                    if msgBox.exec_() == QMessageBox.Yes: #remove this language
                        item.setToolTip(qApp.instance().translate('GramCatWidget', "Click to keep this grammar category"))
                        nameItem.setFlags(Qt.NoItemFlags)
                        self.markForDelete(row, True)
                    else:
                        item.setData(Qt.UserRole, 1)
                        item.setIcon(QIcon(":/trash20.png"))
                        item.setToolTip(qApp.instance().translate('GramCatWidget', "Click to delete this grammar category"))
                        nameItem.setFlags(Qt.ItemIsEditable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                        self.markForDelete(row, False)
                else:
                    item.setToolTip(qApp.instance().translate('GramCatWidget', "Click to keep this grammar category"))
                    nameItem.setFlags(Qt.NoItemFlags)
                    self.markForDelete(row, True)
            else:
                item.setData(Qt.UserRole, 1)
                item.setIcon(QIcon(":/trash20.png"))
                item.setToolTip(qApp.instance().translate('GramCatWidget', "Click to delete this grammar category"))
                nameItem.setFlags(Qt.ItemIsEditable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                self.markForDelete(row, False)
            
            self.typeTable.hideRow(row)
            self.typeTable.showRow(row)
        
        if not self.typeTable.rowCount():
            self.addGramCatBtn.setEnabled(True)
            
    def markForDelete(self, row, _bool):
        idItem = self.typeTable.item(row, ID_COL)
        _id = abs(int(idItem.text()))
        if _bool:
            _id = -_id
        idItem.setText("{}".format(_id))
        
    def isMarkedDeleted(self, row):
        deleteItem = self.typeTable.item(row, REMOVE_COL)
        if deleteItem.data(Qt.UserRole) == -1:
            return True
        return False 
                
    def onDeleteOld(self):
        pass
    
    def onRemoveNew(self):
        btn = self.sender()
        self.typeTable.removeRow(btn.row)
    
    ##!!@pyqtSlot()   
    def onCellChange(self):
        maxrow = self.typeTable.rowCount() - 1
        try:
            index = self.typeTable.selectedIndexes()[0]
        except:
            self.inLastCell = False
            self.inFirstCell = False            
            def setnav():
                self.typeTable.setTabKeyNavigation(True)
                self.addGramCatBtn.setFocus(True)
            QTimer.singleShot(0, setnav)
        else:
            if index.row() == maxrow and index.column() == SENSE_COUNT_COL:
                self.inLastCell = True
            else:
                self.inLastCell = False
            if index.row() == 0 and index.column() == 0:
                self.inFirstCell = True
            else:
                self.inFirstCell = False
    
    ##!!@pyqtSlot(QTableWidgetItem)        
    def onGramCatItemChanged(self, item):
        try:
            self.onReadyToSave()  
        except:
            pass
    
    ##!!@pyqtSlot(tuple)  
    ##!!@pyqtSlot(bool)             
    def onAddGramCat(self, _type=None):
        table = self.typeTable  
        table.setTabKeyNavigation(True)
        model = table.model()
        row = model.rowCount()
        table.insertRow(row)        
        id_txt = '0'
        if _type:
            id_txt = str(_type.id)
            _id = QTableWidgetItem(id_txt)
            name = QTableWidgetItem(_type.name)
            name.setData(Qt.UserRole, _type.name)
        else:
            _id = QTableWidgetItem(id_txt)
            name = QTableWidgetItem("")
            name.setData(Qt.UserRole, "") 
            #name.setFlags(Qt.ItemIsEditable|Qt.ItemIsEnabled|Qt.ItemIsSelectable)
            table.scrollToBottom()
        
        sign_count, sense_count = (0, 0)   
        if _type:
            sign_count, sense_count = qApp.instance().pm.project.countSignsSensesForGramCat(id_txt)
        for t in [(str(sign_count), SIGN_COUNT_COL), (str(sense_count), SENSE_COUNT_COL)]:
            text, col = t
            count = QTableWidgetItem()
            count.setTextAlignment(Qt.AlignCenter)
            count.setFlags(Qt.NoItemFlags)
            count.setText(text) 
            table.setItem(row, col, count)        
        
        remove = QTableWidgetItem()
        remove.setIcon(QIcon(":/trash20.png"))
        remove.setData(Qt.UserRole, 1)
        remove.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
        remove.setToolTip(qApp.instance().translate('GramCatWidget', "Click to delete this grammar category"))  
        
        #if not self.able_to_edit:
        #name.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable) 
        if _type: # existing type, not a new added one
            name.setFlags(Qt.NoItemFlags)                   
                    
        table.setItem(row, NAME_COL, name)
        table.setItem(row, REMOVE_COL, remove)
        table.setItem(row, ID_COL, _id)
        
        index = model.index(row, NAME_COL)
        table.setCurrentIndex(index)    
        if not _type:
            self.addGramCatBtn.setEnabled(False)
            self.typeTable.setCurrentItem(name)
            def _edit():
                self.typeTable.editItem(name) 
            QTimer.singleShot(0, _edit) 
        else:
            self.addGramCatBtn.setEnabled(True)
            self.addGramCatBtn.setFocus()
        
    def event(self, evt):
        if evt.type() == QEvent.ShortcutOverride: 
            if evt.key() == Qt.Key_Tab:
                if self.inLastCell:
                    self.typeTable.setTabKeyNavigation(False)
                    self.typeTable.setCurrentItem(None) 
            elif evt.key() == Qt.Key_Backtab:
                if self.inFirstCell:
                    self.typeTable.setTabKeyNavigation(False)
            elif evt.key() == Qt.Key_Space:
                try:
                    item = self.typeTable.selectedItems()[0]
                except:
                    pass
                else:
                    if item.column() in [1]:
                        self.onItemClicked(item)             
            return False
        elif evt.type() == QEvent.Hide:
            self.close_signal.emit()
            return super(GramCatWidget, self).event(evt)
        else:
            return super(GramCatWidget, self).event(evt)
        
    def getGramCat(self):
        types = []
        rows = range(self.typeTable.rowCount())
        for row in rows:
            name = self.typeTable.item(row, NAME_COL).text()
            if name:
                _id = int(self.typeTable.item(row, ID_COL).text())
                types.append([_id, name])
        return types
            
    @property
    def isDirty(self):
        row_count = self.typeTable.rowCount()
        for row in range(row_count):
            name = self.typeTable.item(row, NAME_COL).text()
            old_name = self.typeTable.item(row, NAME_COL).data(Qt.UserRole)
            remove = self.typeTable.item(row, REMOVE_COL).data(Qt.UserRole)
            if name and name != old_name:
                return True
            elif remove < 0:
                return True
        return False
    
    def onReadyToSave(self):
        _bool = self.isDirty
        count = self.typeTable.rowCount()
        if count:
            last_row = count - 1
            name = self.typeTable.item(last_row, NAME_COL).text()
            if name:
                self.addGramCatBtn.setEnabled(True)
            else:
                self.addGramCatBtn.setEnabled(False)
        self.saveReady.emit(_bool)

class EditGramCatDlg(QDialog):
    def __init__(self, parent=None, types=None):
        super(EditGramCatDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
        able_to_edit = qApp.instance().pm.ableToEdit()
        self.acquired_project_lock = False
        self.acquired_full_project_lock = False
        txt = qApp.instance().translate('EditGramCatDlg', 'Grammar Categories')
        self.setWindowTitle(txt)
        
        self.layout = QVBoxLayout()
        self.layout.setSpacing(3)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        self.whatGramCatWidget = GramCatWidget(self, edit=False)        
        self.layout.addWidget(self.whatGramCatWidget)
        
        if not types:
            self.whatGramCatWidget.onAddGramCat() 
        else:
            for t in types:
                self.whatGramCatWidget.onAddGramCat(_type=t)
        
        self.btnBox = None
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        if able_to_edit:
            hlayout.addStretch()
            self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('EditGramCatDlg', 'Cancel'))
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.btnBox.accepted.connect(self.accept)
            self.btnBox.rejected.connect(self.reject)
            self.edit_btn = QPushButton(qApp.instance().translate('EditGramCatDlg', 'Edit'))
            self.edit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.edit_btn.clicked.connect(self.onEdit)
            self.edit_btn.setToolTip(qApp.instance().translate('EditGramCatDlg', 'Add, remove or rename grammar categories.'))
            hlayout.addWidget(self.edit_btn)
        else:
            self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
            self.btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('EditGramCatDlg', 'Ok'))
            self.btnBox.accepted.connect(self.reject)

        hlayout.addWidget(self.btnBox)
        self.layout.addLayout(hlayout)
        
        self.setLayout(self.layout)

    def sizeHint(self):
        w = self.whatGramCatWidget.typeTable.horizontalHeader().length() + 50
        if w > self.whatGramCatWidget.width():
            w = self.whatGramCatWidget.width()
        h = self.whatGramCatWidget.typeTable.verticalHeader().length() + 150
        return QSize(int(w), int(h))

    def hideEvent(self, evt):
        super(EditGramCatDlg, self).hideEvent(evt)
        qApp.instance().pm.stopInactivityTimer()

    def leaveEdit(self, check_dirty=False):
        # if self.acquired_project_lock:
        #     qApp.instance().pm.releaseProjectLock()
        if self.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock() 
        self.reject()

    def refreshGramCats(self):
        old_gram_cats = self.gram_cats
        mw = qApp.instance().getMainWindow()
        mw.reloadProject(force=True)
        _new_gram_cats = qApp.instance().pm.project.grammar_categories #already sorted
        new_gram_cats = [[gc.id, gc.name] for gc in _new_gram_cats]
        if new_gram_cats != old_gram_cats:
            box = QMessageBox(self)
            box.setWindowTitle(' ')
            txt1 = qApp.instance().translate('EditGramCatDlg', 'Grammar categories have been edited by another user.')
            txt2 = qApp.instance().translate('EditGramCatDlg', 'Your display may show changes.')
            msg = '{}\n{}'.format(txt1, txt2)
            box.setText(msg)
            box.setIcon(QMessageBox.Information)
            box.exec_()

            table = self.whatGramCatWidget.typeTable
            table.clearContents()
            table.setRowCount(0)
            for gc in _new_gram_cats:
                self.whatGramCatWidget.onAddGramCat(gc)

    def onEdit(self):
        if not self.acquired_full_project_lock and not self.acquired_project_lock:
            self.acquired_full_project_lock = qApp.instance().pm.acquireFullProjectLock(self) # deletion column
            if self.acquired_full_project_lock:
                if qApp.instance().pm.projectChanged():
                    self.refreshGramCats()
                self.edit_btn.setDisabled(True)
                self.edit_btn.setToolTip(None)
                self.whatGramCatWidget.setupEditing()
                self.whatGramCatWidget.addGramCatBtn.setFocus(True)
                self.whatGramCatWidget.saveReady.connect(self.onSaveReady)
                self.setWindowTitle(qApp.instance().translate('EditGramCatDlg', 'Edit Grammar Categories'))
                qApp.instance().pm.startInactivityTimer(self)
        
    @property
    def gram_cats(self):
        return self.whatGramCatWidget.gram_cats
    
    ##!!@pyqtSlot(bool)
    def onSaveReady(self, _bool):
        if self.acquired_project_lock: # means we are editing
            qApp.instance().pm.startInactivityTimer(self)
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(_bool)
        
class GramCatItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(GramCatItemDelegate, self).__init__(parent)
        
    def paint(self, painter, option, index):
        painter.save()
        row = index.row()
        col = index.column()
        
        if col == 0:
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
                painter.drawText(rect.bottomLeft(), "required")
                
        elif col in [1, 2]:            
            if self.isMarkedDeleted(row):
                option.font.setStrikeOut(True)
                option.palette.setColor(QPalette.Text, Qt.red) 
        
        super(GramCatItemDelegate, self).paint(painter, option, index)
        painter.restore() 
        
    def isMarkedDeleted(self, row):
        table = self.parent()
        deleteItem = table.item(row, REMOVE_COL)
        if deleteItem.data(Qt.UserRole) == -1:
            return True
        return False           
