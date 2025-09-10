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

from PyQt5.QtWidgets import QDialog, QPushButton, QSizePolicy
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QTreeWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import qApp

from PyQt5.QtCore import Qt, QSize, QEvent

from PyQt5.QtGui import QPalette

class DialectDlg(QDialog):
    """Dialog used for choosing dialects."""

    def __init__(self, parent, dialects, selected_dialect_ids, title, message, editing=True):
        super(DialectDlg, self).__init__(parent=parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet('QDialog {border: 1px solid blue;}')
        self.editing = editing
        self.dialects = sorted(dialects, key=lambda x:x.name.lower()) # all dialects
        self.orig_selected_dialects = [d for d in self.dialects if d.id in selected_dialect_ids]
        self.selected_dialect_ids = selected_dialect_ids

        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(6, 6, 6, 6)

        if message:
            messageLabel = QLabel()
            messageLabel.setText(message)
            layout.addWidget(messageLabel)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.dialectList = QTreeWidget(self)
        self.dialectList.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dialectList.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.dialectList.setHeaderHidden(True)
        self.dialectList.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dialectList.setColumnCount(3)
        self.dialectList.setUniformRowHeights(True)
        self.dialectList.setIndentation(0)
        self.dialectList.setStyleSheet("""QTreeWidget {border: 0;}""")
        self.dialectList.setSelectionMode(QAbstractItemView.MultiSelection)
        self.dialectList.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dialectList.setWordWrap(True)
        if hasattr(self.parent(), 'orig_dialects'):
            orig_dialects = self.parent().orig_dialects
            self.dialectList.setItemDelegate(TextItemDelegate(self.dialects, self.dialectList))
        else:
            self.dialectList.setItemDelegate(TextItemDelegate(self.orig_selected_dialects, self.dialectList))

        self.dialectList.itemPressed.connect(self.onItemPressed)
        self.dialectList.installEventFilter(self)

        self.btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('DialectDlg', 'Ok'))
        self.btnBox.button(QDialogButtonBox.Cancel).setText(qApp.instance().translate('DialectDlg', 'Cancel'))
        self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)
        self.blockSignals(True)
        for dn in self.dialects:
            item = QTreeWidgetItem()
            item.setTextAlignment(1, Qt.AlignLeft)
            item.setTextAlignment(2, Qt.AlignLeft)
            self.dialectList.addTopLevelItem(item)

            text = dn.name
            if dn.isFocal():
                text = "{} ({})".format(text, qApp.instance().translate('DialectDlg', 'Focal'))
            widget = QCheckBox()
            widget.i = item
            self.dialectList.setItemWidget(item, 0, widget)
            item.setText(1, ' {} '.format(dn.abbr))
            item.setText(2, text)
            item.id = dn.id
            if dn.id in selected_dialect_ids:
                self.dialectList.itemWidget(item, 0).setChecked(True)
                item.setSelected(True)
            widget.stateChanged.connect(self.onChecked)
        self.blockSignals(False)
        layout.addWidget(self.dialectList)

        if not self.editing:
            self.select_btn = QPushButton(qApp.instance().translate('DialectDlg', "Select all"))
            self.select_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.select_btn.clicked.connect(self.onSelectAll)
            self.clear_btn = QPushButton(qApp.instance().translate('DialectDlg', "Clear"))
            self.clear_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.clear_btn.clicked.connect(self.onClear)
            layout.addWidget(self.select_btn)
            layout.addWidget(self.clear_btn)

        layout.addWidget(self.btnBox)
        self.setLayout(layout)
        self.dialectList.resizeColumnToContents(0)
        self.dialectList.resizeColumnToContents(1)
        self.dialectList.resizeColumnToContents(2)
        self.btnBox.button(QDialogButtonBox.Cancel).setFocus(True)

    def eventFilter(self, obj, evt):
        if evt.type() == QEvent.KeyRelease:
            return True
        return QDialog.eventFilter(self, obj, evt)

    def hideEvent(self, evt):
        qApp.processEvents()
        super(DialectDlg, self).hideEvent(evt)

    ##!!@pyqtSlot()
    def onClear(self):
        count = self.dialectList.topLevelItemCount()
        for i in range(count):
            item = self.dialectList.topLevelItem(i)
            try:
                self.dialectList.itemWidget(item, 0).setChecked(False)
            except:
                pass
        self.repaint()

    ##!!@pyqtSlot()
    def onSelectAll(self):
        count = self.dialectList.topLevelItemCount()
        for i in range(count):
            item = self.dialectList.topLevelItem(i)
            try:
                self.dialectList.itemWidget(item, 0).setChecked(True)
            except:
                pass
        self.repaint()

    def sizeHint(self):
        width = self.dialectList.header().length() + 32
        #idx = self.dialectList.model().index(0, 0)
        h = 22 #self.dialectList.rowHeight(idx) + 7
        count = self.dialectList.topLevelItemCount() + 1
        height = h * count + self.btnBox.button(QDialogButtonBox.Ok).height()
        if not self.editing:
            height = height + self.select_btn.height() + self.clear_btn.height()
        return QSize(int(width), int(height))

    #@property
    def selected_dialects(self):
        _ids = self.selected_dialect_ids
        _dialects = [d for d in self.dialects if d.id in _ids]
        return _dialects

    def onItemPressed(self, item):
        checkbox = self.dialectList.itemWidget(item, 0)
        checkbox.setChecked(item.isSelected())

#     def onItemActivated(self, item, col):
#         print(item, col)

    ##!!@pyqtSlot(int)
    def onChecked(self, _int):
        checkbox = self.sender()
        item = checkbox.i
        if _int > 0:
            item.setSelected(True)
            self.selected_dialect_ids.append(item.id)
        else:
            item.setSelected(False)
            self.selected_dialect_ids.remove(item.id)

        orig_ids = sorted([d.id for d in self.orig_selected_dialects])
        new_ids = sorted(self.selected_dialect_ids)

        if new_ids and new_ids != orig_ids:
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(True)
            self.btnBox.button(QDialogButtonBox.Ok).setFocus(True)
        else:
            self.btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.btnBox.button(QDialogButtonBox.Cancel).setFocus(True)

class TextItemDelegate(QStyledItemDelegate):
    def __init__(self, orig_dialects, parent=None):
        super(TextItemDelegate, self).__init__(parent)
        self.orig_names = [d.name for d in orig_dialects]

    def paint(self, painter, option, index):
        painter.save()
        if index.column() == 1:
            option.font.setBold(True)
        else:
            option.font.setBold(False)
        item = self.parent().topLevelItem(index.row())
        text = item.text(2)
        fcl = qApp.instance().translate('TextItemDelegate', 'Focal')
        if text.endswith('({})'.format(fcl)):
            text = text.replace('({})'.format(fcl), '').strip()
            option.font.setBold(True)
            option.palette.setColor(QPalette.Text, Qt.blue)
            option.font.setBold(True)
        # if text in self.orig_names:
        #     option.font.setBold(True)
        #     #option.palette.setColor(QPalette.Text, Qt.blue)
        # else:
        #     option.font.setBold(False)
        #     #option.palette.setColor(QPalette.Text, Qt.black)

        super(TextItemDelegate, self).paint(painter, option, index)
        painter.restore()
