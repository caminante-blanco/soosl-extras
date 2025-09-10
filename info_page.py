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
import copy

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QRect
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QEvent

from PyQt5.QtGui import QPalette, QTextCursor
from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPainter
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QTextOption
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QPen

from PyQt5.QtWidgets import QWidget, QStackedWidget, QLayout, QGridLayout, QAction
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QPushButton

from dialect_dlg import DialectDlg
from media_object import MediaObject
from project import Sign

def isOdd(num):
    if num % 2 == 1:
        return True
    return False

class InfoPage(QWidget):
    """Widget for displaying information for a Sign.
    (mostly textual, but also links to extra media)
    """
    amended = pyqtSignal()
    enterEdit = pyqtSignal(bool)
    loadMediaFile = pyqtSignal(MediaObject, str)
    deleteSign = pyqtSignal(bool)
    add_sentence = pyqtSignal(str)
    gloss_changed = pyqtSignal(list)
    filter_dialects = pyqtSignal(list)
    showFocalDialect = pyqtSignal(bool)
    gramCatsAmended = pyqtSignal()
    sense_changed = pyqtSignal()
    repaint_widgets = pyqtSignal()

    def __init__(self, parent=None):
        super(InfoPage, self).__init__(parent)

        if sys.platform.startswith('darwin'):
            self.SENSE_BKG = self.palette().highlight().color()
            self.SELECTED_BKG = QColor(Qt.blue).lighter(136)
            self.SELECTED_TEXT_CLR = QColor(Qt.white)
        else:
            self.SENSE_BKG = self.palette().highlight().color().lighter()
            self.SELECTED_BKG = self.palette().highlight().color()
            self.SELECTED_TEXT_CLR = self.palette().highlightedText().color()

        self.SENTENCE_BKG = self.palette().mid().color().lighter()
        self.SENTENCE_ALT_BKG = self.palette().midlight().color().lighter()

        self.DELETE_CLR = QColor(Qt.red).lighter()

        self.TEXT_CLR = self.palette().text().color()

        self.edit = False
        self.lang_id = 1
        self.current_font_size = self.fontInfo().pointSize()
        self.current_editor = None
        self.current_idx = 0
        self.current_sign = None
        self.current_sign_id = None ##NOTE: needed? or just self.current_sign?
        self.selected_widget = None
        self.add_sentence_here = 1
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout()
        layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        layout.setContentsMargins(2, 2, 20, 100)
        layout.setSpacing(2)
        self.setLayout(layout)
        self.amended.connect(qApp.instance().pm.onAmended)
        if sys.platform.startswith('win32'):
            key1 = QKeySequence(Qt.ControlModifier + Qt.Key_Up)
            key2 = QKeySequence(Qt.ControlModifier + Qt.Key_Down)
            self.dragSenseUpAction = QAction(self, shortcut=key1, triggered=self.onMoveSenseUp)
            self.dragSenseDownAction = QAction(self, shortcut=key2, triggered=self.onMoveSenseDown)
            self.addAction(self.dragSenseUpAction)
            self.addAction(self.dragSenseDownAction)

        self.setAcceptDrops(True)
        self.gloss_drop_zones = None
        self.drag_widget = None

        qApp.instance().pm.lang_list_changed.connect(self.onLangListChanged)
        self.repaint_widgets.connect(self.onRepaint)
        #self.maximized = -1

    # def updateWidgets(self):
    #     idx = 0
    #     while self.layout().itemAt(idx):
    #         widget = self.layout().itemAt(idx).widget()
    #         if widget:
    #             try:
    #                 widget.layout().invalidate()
    #             except:
    #                 pass
    #         idx += 1

    # def resizeEvent(self, evt):
    #     self.layout().invalidate()
    #     super(InfoPage, self).resizeEvent(evt)

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def onLangListChanged(self):
        self.onModelReset(qApp.instance().pm.sign, True)

    #@property
    def dirty(self): # page contains unsaved data
        if not self.edit:
            return False
        if self.current_sign_id == 0:
            return True
        idx = 0
        sense_order = 1
        item = self.layout().itemAt(idx)
        while item:
            widget = item.widget()
            if isinstance(widget, SenseWidget):
                if widget.amend_flag or \
                    widget.delete_flag or \
                    widget.gram_cat_widget.amend_flag or \
                    widget.dialect_widget.amend_flag or \
                    sense_order != widget.sense_order:
                        return True
                sense_order += 1
            elif isinstance(widget, (SentenceWidget, ExtraTextWidget)):
                if isinstance(widget, SentenceWidget) and isinstance(widget.sentence.id, str):
                    return True
                if widget.amend_flag or \
                    widget.delete_flag:
                    return True
            idx += 1
            item = self.layout().itemAt(idx)
        return False

    def getSignData(self):
        sign_data = {'id': self.current_sign_id}
        if qApp.instance().pm.delete_flag:
            sign_data['delete'] = True
        senses = []
        sign_data["senses"] = senses
        idx = 0
        item = self.layout().itemAt(idx)
        sense = None
        while item:
            widget = item.widget()
            if isinstance(widget, SenseWidget):
                if "path" not in sign_data.keys():
                    sign_data["path"] = widget.video.filename
                    sign_data["media_object"] = widget.video
                    sign_data["hash"] = widget.hash
                sense = {"id": widget.sense_id}
                senses.append(sense)
                if widget.gram_cat_widget.gram_cat:
                    sense["grammarCategoryId"] = widget.gram_cat_widget.gram_cat.id
                sense["dialectIds"] = [d.id for d in widget.dialect_widget.dialects]
                sense["glossTexts"] = [{"langId":e.lang_id, "text":e.text()} for e in widget.editors]
                if widget.delete_flag:
                    sense['delete'] = True
                sense["sentences"] = []
            elif isinstance(widget, SentenceWidget):
                sentence = {"id": widget.sentence.id}
                sense.get("sentences").append(sentence)
                sentence["path"] = widget.sentence.path
                sentence["media_object"] = widget.sentence.media_object
                sentence["hash"] = widget.sentence.hash
                sentence["sentenceTexts"] = [{"langId":e.lang_id, "text":e.text()} for e in widget.editors]
                if widget.delete_flag:
                    sentence['delete'] = True
            elif isinstance(widget, ExtraTextWidget):
                sign_data["extraTexts"] = [{"langId":e.lang_id, "text":e.text()} for e in widget.editors]
                if widget.delete_flag:
                    sign_data['delete_extraTexts'] = True
            idx += 1
            item = self.layout().itemAt(idx)
        return sign_data

    def onMoveSenseUp(self):
        """move up sense order"""
        #find previous drop zone
        if self.edit:
            widget = self.selected_widget
            if widget and isinstance(widget, SenseWidget):
                gloss_id = widget.gloss_id
                idx = self.layout().indexOf(widget)
                zones = self.setupDropZones(idx, gloss_id)
                drop_zone = None
                for zone in zones:
                    zone_idx = self.layout().indexOf(zone)
                    if  zone_idx < idx:
                        drop_zone = zone
                    elif zone_idx > idx:
                        break
                if drop_zone:
                    self.moveSense(widget, drop_zone)
                    self.amended.emit()

    def onMoveSenseDown(self):
        """move down sense order"""
        if self.edit:
            #find next drop zone
            widget = self.selected_widget
            if widget and isinstance(widget, SenseWidget):
                gloss_id = widget.gloss_id
                idx = self.layout().indexOf(widget)
                zones = self.setupDropZones(idx, gloss_id)
                drop_zone = None
                for zone in zones:
                    zone_idx = self.layout().indexOf(zone)
                    if  zone_idx > idx:
                        drop_zone = zone
                        break
                if drop_zone:
                    self.moveSense(widget, drop_zone)
                    self.amended.emit()

    def mouseMoveEvent(self, evt):
        """when dragging with the mouse"""
        if self.edit and self.drag_widget and hasattr(self, 'drop_stack'):
            self.checkScroll()
            x = self.layout().contentsMargins().left()
            y = evt.globalPos().y() + self.drop_stack.property('y_offset')
            new_pos = QPoint(x, y)
            self.drop_stack.move(new_pos)
            self.checkDropZones(y)

            c_pos = self.drop_stack.property('cursor_pos')
            dy = c_pos.y() - evt.globalPos().y()
            cx, cy = c_pos.x(), c_pos.y() - dy
            self.drop_stack.setProperty('cursor_pos', QPoint(cx, cy))
            #anchor cursor to drag handle
            self.cursor().setPos(self.drop_stack.property('cursor_pos'))

    ##!!@pyqtSlot(QWidget)
    def setDragWidget(self, widget):
        self.drag_widget = widget
        if widget: #start drag
            self.setupDrag(widget)
            if not hasattr(self, 'dragTimer'):
                self.dragTimer = QTimer(self)
                self.dragTimer.timeout.connect(self.repaint_widgets)
                self.dragTimer.start(10)
            else:
                self.dragTimer.start(10)
        else: #end drag
            if hasattr(self, 'drop_stack'):
                self.drop_stack.close()
            if hasattr(self, 'drop_zone') and self.drop_zone:
                self.moveSense(self.drop_stack.property('widget'), self.drop_zone)
            self.dragTimer.stop()
            del self.dragTimer

    @property
    def current_gloss_id(self):
        return self.selected_widget.gloss_id

    def clear(self):
        item = self.layout().takeAt(0)
        while item:
            widget = item.widget()
            if widget:
                widget.blockSignals(True)
                widget.close()
            del item
            item = self.layout().takeAt(0)

    def setCurrentEditor(self, editor):
        if self.current_editor is not editor:
            self.current_editor = editor
            if editor:
                self.current_idx = self.layout().indexOf(editor.parent())
            else:
                self.current_idx = 0

    def setupDropZones(self, _idx, gloss_id):
        """locate areas where Senses can be dragged to and 'dropped'; valid
        for a given gloss_id"""
        #find next 'sense' separator; a QLabel
        zones = []
        idx = 0
        item = self.layout().itemAt(idx)
        while item:
            widget = item.widget()
            if widget and \
                idx != _idx - 1 and \
                isinstance(widget, QLabel) and \
                widget.gloss_id != gloss_id:
                    zones.append(widget)
            idx += 1
            item = self.layout().itemAt(idx)
        if len(zones) >= 1:
            self.gloss_drop_zones = zones
        else:
            self.gloss_drop_zones = None
        return zones

    def isDragNearZone(self, y, zone):
        BORDER = 15 #margin along top and bottom of drag label which won't trigger drop indicator
        x = self.drop_stack.pos().x() - 5 # add a little extra width to ensure lbl wider than zone
        width = self.drop_stack.width() + 5
        y = self.drop_stack.pos().y() + BORDER
        height = self.drop_stack.height() - 2*BORDER
        rect = QRect(x, y, width, height)
        zone_rect = QRect(zone.pos(), zone.size())

        if rect.contains(zone_rect):
            return True
        return False

    def setPixmapBorder(self, pxm):
        painter = QPainter(pxm)
        painter.setCompositionMode(painter.CompositionMode_SourceOver)
        painter.setPen(QPen(QColor('purple'), 7, Qt.SolidLine))
        painter.drawRect(pxm.rect())
        painter.end()
        return pxm

    def setPixmapNoBorder(self, pxm):
        painter = QPainter(pxm)
        painter.setCompositionMode(painter.CompositionMode_DestinationIn)
        painter.fillRect(pxm.rect(), QColor(0, 0, 0, 170))
        painter.end()
        return pxm

    def getSenseIds(self):
        _ids = []
        idx = 0
        item = self.layout().itemAt(idx)
        widget = None
        while item:
            widget = item.widget()
            if isinstance(widget, SenseWidget):
                _ids.append(widget.gloss_id)
            idx += 1
            item = self.layout().itemAt(idx)
        return _ids

    def moveSense(self, src_widget, drop_zone):
        widgets = self.getSenseWidgets(src_widget)
        self.layout().removeWidget(src_widget)
        for widget in widgets:
            self.layout().removeWidget(widget)
        drop_idx = self.layout().indexOf(drop_zone) + 1
        for widget in reversed(widgets):
            self.layout().insertWidget(drop_idx, widget)
        self.layout().insertWidget(drop_idx, src_widget)
        self.resetTabOrder()

        _ids = self.getSenseIds()
        self.setOrderLabelStyles()
        self.amended.emit()
        QTimer.singleShot(200, self.ensureSelectedVisible)

    def setOrderLabelStyles(self):
        i = 0
        sense_widgets = []
        item = self.layout().itemAt(i)
        while item:
            widget = item.widget()
            if widget and isinstance(widget, SenseWidget):
                sense_widgets.append(widget)
            i += 1
            item = self.layout().itemAt(i)
        for widget in sense_widgets:
            idx = sense_widgets.index(widget)
            order = int(widget.sense_order_label.text().strip())
            if order == idx + 1 and not widget.isNew():
                widget.sense_order_label.setStyleSheet(None)
            else:
                widget.sense_order_label.setStyleSheet("""color:red; font-weight:bold;""")

    def getSenseWidgets(self, sense_widget):
        """get widgets under sense_widget associated with a sense"""
        widgets = []
        idx = self.layout().indexOf(sense_widget) + 1
        item = self.layout().itemAt(idx)
        widget = None
        while item:
            widget = item.widget()
            if isinstance(widget, (SenseWidget, ExtraTextWidget)):
                break
            elif widget:
                widgets.append(widget)
            idx += 1
            item = self.layout().itemAt(idx)
        return widgets

    def checkScroll(self):
        if hasattr(self, 'drop_stack'):
            scroller = self.parent().parent().verticalScrollBar()
            scroll_value = scroller.value()
            if self.drop_stack.pos().y() <= self.visibleRegion().boundingRect().top() + 5:
                scroller.setValue(scroll_value - 10)
            if self.drop_stack.pos().y() + self.drop_stack.height() >= self.visibleRegion().boundingRect().bottom() - 5:
                scroller.setValue(scroll_value + 10)

    def checkDropZones(self, y):
        for zone in self.gloss_drop_zones:
            if self.isDragNearZone(y, zone):
                if not zone.gloss_id:
                    zone.show()
                self.drop_stack.setCurrentIndex(1)
                self.drop_zone = zone
                break
            else: # drag not near to a 'drop-zone'
                if not zone.gloss_id:
                    zone.hide()
                self.drop_stack.setCurrentIndex(0)
                self.drop_zone = None

    def setupDrag(self, widget, start_pos=None):
        gloss_id = widget.gloss_id
        idx = self.layout().indexOf(widget)
        if not start_pos:
            start_pos = self.cursor().pos()
        if self.setupDropZones(idx, gloss_id):
            self.drop_zone = None
            self.drop_stack = QStackedWidget(self)
            self.drop_stack.setWindowOpacity(30)
            self.drop_stack.setAttribute(Qt.WA_DeleteOnClose)
            self.drop_stack.setWindowFlags(Qt.WindowStaysOnTopHint)
            self.drop_stack.resize(widget.size())
            self.drop_stack.setProperty('y_offset', widget.pos().y() - start_pos.y())
            self.drop_stack.setProperty('x_offset', widget.pos().x() - start_pos.x())
            self.drop_stack.setProperty('widget', widget)
            self.drop_stack.setCursor(QCursor(Qt.ClosedHandCursor))
            cursor_pos = widget.sense_drag_handle.geometry().center()
            cursor_pos = widget.mapToGlobal(cursor_pos)
            self.drop_stack.setProperty('cursor_pos', cursor_pos)

            for pxm in [self.setPixmapNoBorder(widget.grab()),
                        self.setPixmapBorder(widget.grab())]:
                lbl = QLabel(self)
                lbl.setPixmap(pxm)
                self.drop_stack.addWidget(lbl)
            # shift the Pixmap so that it coincides with the cursor position
            #pos = start_pos - widget.pos()
            #self.last_y = start_pos.y()
            x = self.layout().contentsMargins().left()
            y = self.cursor().pos().y() + self.drop_stack.property('y_offset')
            pos = QPoint(x, y)
            self.drop_stack.move(pos)
            self.drop_stack.show()

    def hideSentences(self, _bool):
        idx = 0
        item = self.layout().itemAt(idx)
        while item:
            widget = item.widget()
            if widget and isinstance(widget, (SentenceWidget, SentenceAddButton)):
                if _bool:
                    widget.hide()
                else:
                    widget.show()
            idx += 1
            item = self.layout().itemAt(idx)

    ##!!@pyqtSlot(list)
    def filterByDialects(self, dialect_list):
        pass #self.filter_dialects.emit(dialect_list)
        # TODO: Ask the question!
        # NOTE: Not sure how to handle this. Should glosses/senses be hidden if they don't
        # match the dialect filter? or is it useful information to know all dialects that
        # a sign uses

    def getSentenceAddBtn(self, gloss_id):
        btn = SentenceAddButton(self)
        btn.setFlat(True)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setIcon(QIcon(':/add_sentence.png'))
        btn.setIconSize(QSize(20, 20))
        btn.gloss_id = gloss_id
        btn.clicked.connect(self.onAddSentence)
        self.add_sentence_buttons.append(btn)
        return btn

    def getLine(self, gloss_id):
        lbl = QLabel(self)
        lbl.setAttribute(Qt.WA_DeleteOnClose)
        lbl.setFocusPolicy(Qt.NoFocus)
        lbl.gloss_id = gloss_id
        lbl.setMaximumHeight(2)
        lbl.setStyleSheet("""background-color:lightgray""")
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if not gloss_id:
            lbl.hide()
        return lbl

    def __justChangeSense(self, sign):
        # Just changing sense, not sign
        sense_id = sign.current_sense_id
        idx = 0
        item = self.layout().itemAt(idx)
        selected_widget = None
        while item:
            widget = item.widget()
            if isinstance(widget, SenseWidget) and widget.sense_id == sense_id:
                selected_idx = idx
                if widget.sense_id != self.selected_widget.sense_id: #would be deselected on alternate clicks
                    selected_widget = widget
            idx += 1
            item = self.layout().itemAt(idx)
        return selected_widget

    def onMWSizeChange(self, _bool):
        # NOTE: aides layout on max min change
        self.layout().invalidate()
        if self.current_sign:
            self.onModelReset(self.current_sign, True)

    ##!!@pyqtSlot(Sign)
    def onModelReset(self, sign, full=False):
        self.current_editor = None
        selected_widget = None
        selected_idx = 1
        # if sign hasn't changed, but moving between searching and editing, need to know which index was selected and then reselect after model reset
        # defaults to first index (row)
        sign_id = -1
        current_sign_id = -1
        if sign:
            try:
                sign_id = sign.id
            except:
                sign_id = sign.get('id')
        if self.current_sign:
            try:
                current_sign_id = self.current_sign.id
            except:
                current_sign_id = self.current_sign.get('id')
        if self.selected_widget and sign and sign_id == current_sign_id:
            try:
                selected_idx = self.layout().indexOf(self.selected_widget)
            except:
                selected_idx = 1
            self.current_idx = selected_idx
            try:
                if isinstance(self.selected_widget, SenseWidget) and not self.edit:
                    selected_widget = self.__justChangeSense(sign)
                elif self.selected_widget and hasattr(self.selected_widget, '_selected'):
                    selected_widget = self.selected_widget
            except:
                pass
        #let's try to prevent unecessary reloading and flickering of gui
        if full or \
            (self.edit and self.dirty()) or \
            self.signHasChanged(sign, self.current_sign):
                self.clear()
                if sign:
                    self.current_sign_id = sign_id

                    selected_widget = None
                    self.add_sentence_buttons = []

                    line = self.getLine(None) # an initial hidden line to mark first 'drop zone'.
                    self.layout().addWidget(line)

                    sense_list = sign.senses #qApp.instance().pm.project.getSenses(sign_id)
                    self.sense_count = 1
                    for sense in sense_list:
                        dialects = qApp.instance().pm.project.getAllGlossDialects(sign_id, sense.id)
                        if not dialects:
                            dialects.append(qApp.instance().pm.project.getFocalDialect())
                        gram_cat = qApp.instance().pm.project.getGrammarCategory(sign_id, sense.id)
                        sentences = qApp.instance().pm.project.getSentences(sign_id, sense.id)
                        sense_widget = SenseWidget(sense, dialects, gram_cat, sign.media_object, sign.hash, self)
                        sense_widget.setBackground(self.SENSE_BKG)
                        sense_widget.setSenseOrder(self.sense_count)
                        self.sense_count += 1
                        sense_widget.onEnterEdit(self.edit)
                        self.enterEdit.connect(sense_widget.onEnterEdit)
                        self.deleteSign.connect(sense_widget.onSignDelete)
                        sense_widget.amended.connect(qApp.instance().pm.onAmended)

                        sense_widget._selected.connect(self.onWidgetSelected)
                        sense_widget.gloss_changed.connect(self.gloss_changed)
                        sense_widget.sense_drag_handle.drag_widget.connect(self.setDragWidget)
                        self.filter_dialects.connect(sense_widget.filterByDialects)

                        self.layout().addWidget(sense_widget)
                        # when searching, set the current index for the correct sense
                        if not self.edit and isinstance(self.selected_widget, SenseWidget) and sense_widget.sense_id == sign.current_sense_id:
                            selected_idx = self.layout().indexOf(sense_widget)
                        if sentences:
                            count = 0
                            for sent in sentences:
                                sent_widget = SentenceWidget(sent, sense.id, self)
                                self.deleteSign.connect(sent_widget.onDelete)
                                sense_widget.deleted.connect(sent_widget.onDelete)
                                if isOdd(count):
                                    sent_widget.setBackground(self.SENTENCE_BKG)
                                    sent_widget.setProperty('isOdd', True)
                                else:
                                    sent_widget.setBackground(self.SENTENCE_ALT_BKG)
                                    sent_widget.setProperty('isOdd', False)
                                #sent_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                                sent_widget.onEnterEdit(self.edit)
                                self.enterEdit.connect(sent_widget.onEnterEdit)
                                count += 1
                                try:
                                    sense_widget.deleted.connect(sent_widget.onGlossDelete)
                                except:
                                    pass
                                else:
                                    self.layout().addWidget(sent_widget)
                                    sent_widget.amended.connect(qApp.instance().pm.onAmended)
                                    sent_widget._selected.connect(self.onWidgetSelected)

                        add_button = self.getSentenceAddBtn(sense.id)
                        try:
                            sense_widget.deleted.connect(add_button.setHidden)
                        except:
                            pass
                        if not self.edit:
                            add_button.hide()
                        self.layout().addWidget(add_button)

                        line = self.getLine(sense.id)
                        self.layout().addWidget(line)

                    self.layout().addSpacing(20)

                    extra_text_widget = ExtraTextWidget(sign.extra_texts, self)

                    #extra_text_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    extra_text_widget.amended.connect(qApp.instance().pm.onAmended)
                    extra_text_widget._selected.connect(self.onWidgetSelected)
                    extra_text_widget.onEnterEdit(self.edit)
                    self.enterEdit.connect(extra_text_widget.onEnterEdit)
                    self.deleteSign.connect(extra_text_widget.onSignDelete)
                    #self.font_size_change.connect(extra_text_widget.onFontSizeChange)
                    self.layout().addWidget(extra_text_widget)

                    self.layout().addStretch()
                    selected = self.layout().itemAt(selected_idx)
                    if selected:
                        selected_widget = selected.widget()
        try: #occurred while rapidly scrolling and selecting words in the gloss list
            self.current_sign = copy.deepcopy(sign)
        except:
            pass
        try:
            if selected_widget and hasattr(selected_widget, '_selected'): #add sentence button has no _selected
                selected_widget._selected.emit()
        except:
            pass # wrapped C/C++ object deleted

    def signHasChanged(self, new_sign, old_sign):
        #return True #NOTE: work on this to prevent umwanted reloads/flicker

        if not new_sign and old_sign:
            return True
        elif new_sign and not old_sign:
            return True
        elif not new_sign and not old_sign:
            return False
        elif new_sign.id != old_sign.id:
            return True

        return False

    ##!!@pyqtSlot(dict)
    def onNewSense(self, sense):
        _id = sense.id
        gram_cats = sense.grammar_category_id
        dialects = sense.dialect_ids
        if not dialects:
            dialects.append(qApp.instance().pm.project.getFocalDialect())
        sense_widget = SenseWidget(sense, dialects, gram_cats, qApp.instance().pm.sign.media_object, '', self)
        self.enterEdit.connect(sense_widget.onEnterEdit)
        sense_widget.onEnterEdit(True)
        self.deleteSign.connect(sense_widget.onDelete)
        sense_widget.amended.connect(qApp.instance().pm.onAmended)
        sense_widget._selected.connect(self.onWidgetSelected)
        sense_widget.sense_drag_handle.drag_widget.connect(self.setDragWidget)
        row = self.layout().count() - 3
        self.layout().insertWidget(row, sense_widget)

        add_button = self.getSentenceAddBtn(_id)
        self.layout().insertWidget(row + 1, add_button)
        line = self.getLine(_id)
        self.layout().insertWidget(row + 2, line)
        sense_widget._selected.emit()
        if sense_widget.editor:
            sense_widget.editor.setFocus()
        sense_widget.setSenseOrder(self.sense_count)
        sense_widget.sense_order_label.setStyleSheet("""color:red; font-weight:bold;""")
        self.sense_count += 1
        self.ensureSenseVisible(sense_widget)

    def ensureSenseVisible(self, sense_widget):
        y = 0
        i = 0
        item = self.layout().itemAt(i)
        while item:
            widget = item.widget()
            if widget and widget is sense_widget:
                break
            if widget:
                y = y + widget.height()
            i += 1
            item = self.layout().itemAt(i)
        scroller = self.parent().parent().verticalScrollBar()
        scroller.setValue(y)

    ##!!@pyqtSlot()
    def onAddSentence(self):
        btn = self.sender()
        gloss_id = btn.gloss_id
        self.add_sentence_here = self.layout().indexOf(btn)
        self.add_sentence.emit(str(gloss_id))
        self.amended.emit()
        qApp.processEvents()

    ##!!@pyqtSlot(tuple)
    def onNewSentence(self, sent_tuple):
        gloss_id, sent = sent_tuple
        sent_widget = SentenceWidget(sent, gloss_id, self)
        sent_widget.amended.connect(qApp.instance().pm.onAmended)
        sent_widget._selected.connect(self.onWidgetSelected)
        self.enterEdit.connect(sent_widget.onEnterEdit)
        sent_widget.onEnterEdit(True)
        self.deleteSign.connect(sent_widget.onDelete)
        self.layout().insertWidget(self.add_sentence_here, sent_widget)
        self.resetTabOrder()
        if sys.platform.startswith('darwin'):
            qApp.processEvents()
        if sent_widget.editor:
            sent_widget.editor.setFocus()

    def resetTabOrder(self):
        i = 0
        item = self.layout().itemAt(i)
        widgets = []
        while item:
            try:
                widget = item.widget()
            except:
                pass
            else:
                if widget:
                    if isinstance(widget, SenseWidget):
                        widgets.append(widget.gram_cat_widget.gram_cats_combo)
                        widgets.append(widget.dialect_widget.dialect_combo)
                        for editor in widget.editors:
                            widgets.append(editor)
                    elif isinstance(widget, SentenceWidget):
                        for editor in widget.editors:
                            widgets.append(editor)
                    elif isinstance(widget, SentenceAddButton):
                        widgets.append(widget)
                    elif isinstance(widget, ExtraTextWidget):
                        pass
            i += 1
            item = self.layout().itemAt(i)
        count = len(widgets)
        for i in range(count - 1):
            w1 = widgets[i]
            j = i + 1
            w2 = widgets[j]
            self.setTabOrder(w1, w2)

    ##!!@pyqtSlot()
    def onProjectClosed(self):
        self.clear()

    ##!!@pyqtSlot(bool)
    def onProjectOpen(self, _bool):
        pass

    def ensureSelectedVisible(self):
        scroll_area = self.parent().parent()
        try:
            scroll_area.ensureWidgetVisible(self.selected_widget)
        except:
            pass ## ERROR: wrapped C/C object of type SenseWidget has been deleted

    ###!!@pyqtSlot()
    ##NOTE: marking this as slot causes it to fire everytime text is typed in an editor, but not when it is not. why?
    def onWidgetSelected(self):
        widget = self.sender()
        if widget and isinstance(widget, (SenseWidget, SentenceWidget)):
            old_widget = self.selected_widget
            if widget and widget is not self.selected_widget:
                try: #
                    self.selected_widget.setSelected(False)
                except:
                    pass #None or already deleted
                self.selected_widget = widget
                if hasattr(self.selected_widget, 'setSelected'):
                    try:
                        self.selected_widget.setSelected(True)
                    except:
                        pass
                self.ensureSelectedVisible()
                if old_widget: # old widget should be none on when first loading sign; prevents loading sign video again
                    # as it is loaded elsewhere
                    video = self.selected_widget.video
                    _type = self.selected_widget.video_type
                    try:
                        qApp.instance().pm.sign.selected_video = video
                    except:
                        pass
                    else:
                        if qApp.instance().pm.sign.current_sense_id != self.selected_widget.sense_id:
                            qApp.instance().pm.sign.current_sense_id = self.selected_widget.sense_id
                            try:
                                if hasattr(self.selected_widget, 'sense_field'):
                                    qApp.instance().pm.sign.current_sense_field = self.selected_widget.sense_field
                                if isinstance(self.selected_widget, SentenceWidget):
                                    qApp.instance().pm.sign.current_sense_field = 0
                            except:
                                pass
                            else:
                                self.sense_changed.emit()
                    try:
                        self.loadMediaFile.emit(video, _type)
                    except:
                        self.loadMediaFile.emit(None, None)
        qApp.processEvents()

    def onSenseFieldChanged(self):
        if isinstance(self.selected_widget, SenseWidget) and qApp.instance().pm.sign:
            qApp.instance().pm.sign.current_sense_field = self.selected_widget.sense_field
            qApp.instance().pm.sign.current_sense_id = self.selected_widget.sense_id
            self.sense_changed.emit()

    def onAmendProjectDialects(self, _bool):
        if isinstance(_bool, str): #Windows seems to treat bools as strings in settings; 'sometimes' at least
            if _bool.lower() == 'true':
                _bool = True
            else:
                _bool = False
        self.showFocalDialect.emit(_bool)

    def onAmendProjectGramCats(self):
        self.gramCatsAmended.emit()

    ##!!@pyqtSlot()
    def enterEditingMode(self):
        self.edit = True
        try:
            for btn in self.add_sentence_buttons:
                btn.show()
        except:
            pass
        ## NOTE: should this next line exist???
        idx = 1
        try:
            idx = self.layout().indexOf(self.selected_widget)
        except:
            pass
        self.enterEdit.emit(True)

    ##!!@pyqtSlot()
    def leaveEditingMode(self):
        self.blockSignals(True)
        if qApp.instance().pm.sign:
            qApp.instance().pm.sign.resetMedia()
        self.edit = False
        #self.onModelReset(qApp.instance().pm.sign)
        self.blockSignals(False)
        try:
            for btn in self.add_sentence_buttons:
                btn.hide()
        except:
            pass
        self.enterEdit.emit(False)
        if not self.isEnabled():
            self.setEnabled(True)
        self.onMWSizeChange(True)
        QTimer.singleShot(200, qApp.instance().resetKeyboard)

    ##!!@pyqtSlot(bool)
    def onDeleteSign(self, _bool):
        self.deleteSign.emit(_bool)
        self.setDisabled(_bool)

    ##!!@pyqtSlot(MediaObject, int)
    def onCurrentVideoAmended(self, media, response, associated_texts):
        widget = self.selected_widget
        if hasattr(media, 'widget'):
            widget = media.widget
        widget.setTexts(associated_texts)
        widget.setVideo(media)
        self.amended.emit()
        # def delay_return():
        #     return
        QTimer.singleShot(200, self.amended.emit)

class SenseWidget(QWidget):
    amended = pyqtSignal()
    deleted = pyqtSignal(bool)
    _selected = pyqtSignal()
    gloss_changed = pyqtSignal(list)
    sense_field_changed = pyqtSignal()
    #repaint_widgets = pyqtSignal()

    def __init__(self, sense, dialects, gram_cat, media_object, video_hash, parent):
        super(SenseWidget, self).__init__(parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAutoFillBackground(True)
        self.video = media_object
        self.hash = video_hash
        self.video_type = 'sign'
        self.edit = parent.edit
        self.setProperty('selected', False)
        self.delete_flag = False
        self.gloss_texts = copy.deepcopy(sense.gloss_texts)
        self.editors = []
        self.editor = None
        self.sense_order = 0
        self.sense_id = sense.id
        self.sense_field = 0
        self.amend_flag = False
        self.setAcceptDrops(False)

        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(3)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        #self.header_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        self.sense_order_label = QLabel()
        self.sense_order_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        pxm_h = 28
        self.normal_pxm = QPixmap(':/hand_up.png').scaledToHeight(pxm_h, Qt.SmoothTransformation)
        self.selected_pxm = QPixmap(':/hand_down.png').scaledToHeight(pxm_h, Qt.SmoothTransformation)
        self.icon_label = QLabel(self)
        self.icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.icon_label.setPixmap(self.normal_pxm)
        #self.icon_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.icon_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to select this sense and show its video"))
        self.gram_cat_widget = GramCatWidget(gram_cat, self)
        self.parent().gramCatsAmended.connect(self.gram_cat_widget.onGramCatsAmended)
        self.gram_cat_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.dialect_widget = DialectWidget(dialects, self)
        self.parent().showFocalDialect.connect(self.dialect_widget.onAmendProjectDialects)
        self.dialect_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.remove_label = QLabel(self)
        self.remove_label.setFixedSize(QSize(24, 24))
        self.remove_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.remove_pxm = QPixmap(':/trash20.png')
        self.remove_label.setPixmap(self.remove_pxm)
        self.header_layout.addWidget(self.icon_label)
        self.header_layout.addWidget(self.sense_order_label)
        self.header_layout.addWidget(self.gram_cat_widget)
        self.header_layout.addWidget(self.dialect_widget)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.remove_label)

        self.gloss_layout = QHBoxLayout()
        self.gloss_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.gloss_layout.setSpacing(3)
        self.gloss_layout.setContentsMargins(0, 0, 0, 0)

        self.sense_drag_handle = SenseDragHandle(self)
        self.sense_drag_handle.setMaximumSize(QSize(2, 48))
        self.sense_drag_handle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sense_drag_handle.setCursor(QCursor(Qt.ArrowCursor))

        self.editor_layout = QGridLayout()
        self.editor_layout.setContentsMargins(0,0,0,0)
        self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        self.gloss_layout.addWidget(self.sense_drag_handle)
        self.gloss_layout.addLayout(self.editor_layout)
        self.gloss_layout.setAlignment(self.icon_label, Qt.AlignTop|Qt.AlignLeft)
        self.gloss_layout.setAlignment(self.editor_layout, Qt.AlignTop)

        layout= QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)
        layout.addLayout(self.header_layout)
        layout.addLayout(self.gloss_layout)
        self.setLayout(layout)

        self.__setupRows()
        if self.editors:
            self.editor = self.editors[0]
        self.setStyles()
        qApp.processEvents()

        self.deleted.connect(self.gram_cat_widget.onDelete)
        self.deleted.connect(self.dialect_widget.onDelete)
        self.sense_field_changed.connect(self.parent().onSenseFieldChanged)

        qApp.instance().pm.lang_selection_change.connect(self.onLangSelectionChange)
        qApp.instance().pm.font_size_change.connect(self.onFontSizeChange)
        qApp.instance().pm.font_family_change.connect(self.onFontFamilyChange)
        qApp.instance().pm.lang_order_change.connect(self.onLangOrderChange)
        self.parent().repaint_widgets.connect(self.onRepaint)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    def updateToolTips(self):
        self.icon_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to select this sense and show its video"))
        if self.edit:
            self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to delete sense"))
            key1 = QKeySequence(Qt.CTRL + Qt.Key_Up)
            key2 = QKeySequence(Qt.CTRL + Qt.Key_Down)
            shortcut = '{} {} | {}'.format(qApp.instance().translate('SenseWidget', 'Keyboard:'), key1.toString(QKeySequence.NativeText), key2.toString(QKeySequence.NativeText))
            self.sense_drag_handle.setToolTip('{}\n{}'.format(qApp.instance().translate('SenseWidget', 'Click and drag to change sense order'), shortcut))
            if self.delete_flag:
                self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to keep sense"))
            else:
                self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to delete sense"))

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def __setupRows(self):
        langs = qApp.instance().pm.project.writtenLanguages
        langs.sort(key=lambda x: int(x.order))
        row = 0
        for lang in langs:
            lang_id = lang.id
            lang_name = lang.name
            editor = self.__getEditor(lang_id)
            lbl = self.__getEditorLabel(lang_id, lang_name)

            self.editor_layout.addWidget(editor, row, 0)
            self.editor_layout.addWidget(lbl, row, 1)
            row += 1

            self.editors.append(editor)
            font_size = qApp.instance().pm.getFontSizeById(lang_id)
            self.onFontSizeChange(lang_id, font_size)
            font_family = qApp.instance().pm.getFontFamily(lang_name)
            self.onFontFamilyChange(lang_id, font_family)

    def __getEditor(self, lang_id):
        text = ''
        try:
            text = [t.text for t in self.gloss_texts if t.lang_id == lang_id][0].strip()
        except:
            pass
        editor = MyMultilineEdit(self, text, lang_id)
        if editor.lang_id not in qApp.instance().pm.selected_lang_ids:
            editor.hide()
        editor.setOrigText(text)
        editor.setReadOnly(True)
        editor.setFrame(False)
        editor.textChanged.connect(self.onTextChanged)
        return editor

    def __getEditorLabel(self, lang_id, lang_name):
        lbl = QLabel(lang_name, self)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        lbl.setContentsMargins(5, 0, 5, 0)
        lbl.lang_id = lang_id
        lbl.hide()
        return lbl

    def setBackground(self, bkg_color):
        p = self.palette()
        p.setColor(QPalette.Base, bkg_color)
        self.setPalette(p)
        if bkg_color == self.parent().SELECTED_BKG and not self.edit:
            frg_color = self.parent().SELECTED_TEXT_CLR
        elif bkg_color == self.parent().DELETE_CLR:
            frg_color = self.parent().DELETE_CLR
        else:
            frg_color = self.parent().TEXT_CLR

        for editor in self.editors:
            try:
                p = editor.palette()
            except:
                pass
            else:
                p.setColor(QPalette.Base, bkg_color)
                if not editor.property('amend'):
                    p.setColor(QPalette.Text, frg_color)
                if not self.edit and not editor.text().strip(): # == '???':
                    p.setColor(QPalette.Text, Qt.gray)
                editor.setPalette(p)

    ##!!@pyqtSlot(list)
    def onLangOrderChange(self, lang_ids):
        widgets = []
        row = 0
        try:
            while row < self.editor_layout.rowCount():
                editor = self.editor_layout.itemAtPosition(row, 0).widget()
                lang_lbl = self.editor_layout.itemAtPosition(row, 1).widget()
                self.editor_layout.removeWidget(editor)
                self.editor_layout.removeWidget(lang_lbl)
                if editor.lang_id not in lang_ids:
                    editor.close()
                    lang_lbl.close()
                else:
                    widgets.append(editor)
                    widgets.append(lang_lbl)
                row += 1
        except:
            pass
        else:
            self.gloss_layout.removeItem(self.editor_layout)
            del self.editor_layout

            self.editor_layout = QGridLayout()
            self.editor_layout.setContentsMargins(0,0,0,0)
            self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
            self.gloss_layout.insertLayout(1, self.editor_layout)

            row = 0
            lang_ids = [l for l in lang_ids if (isinstance(l, int) and l > 0) or isinstance(l, str)]
            for _id in lang_ids:
                if isinstance(_id, int):
                    try:
                        editor, lang_lbl = [e for e in widgets if e.lang_id == _id]
                    except:
                        print('no editor', _id)
                        editor, lang_lbl = [None, None]
                elif isinstance(_id, str): #new lang
                    name = _id
                    _id = qApp.instance().pm.getLangId(name)
                    editor = self.__getEditor(_id)
                    self.editors.append(editor)
                    lang_lbl = self.__getEditorLabel(_id, name)
                if editor:
                    self.editor_layout.addWidget(editor, row, 0)
                    self.editor_layout.addWidget(lang_lbl, row, 1)
                    row += 1
            self.setStyles()
            qApp.processEvents()
            self.adjustSize()

    ##!!@pyqtSlot()
    def onLangSelectionChange(self):
        if not self.edit:
            for editor in self.editors:
                try:
                    if editor.lang_id in qApp.instance().pm.selected_lang_ids and editor.text():
                        editor.show()
                    else:
                        editor.hide()
                except:
                    pass

    def resetTabOrder(self):
        self.setTabOrder(self.gram_cat_widget, self.dialect_widget)
        if self.editors:
            self.setTabOrder(self.dialect_widget, self.editors[0])
            l = len(self.editors)
            if l > 1:
                for idx in range(l):
                    if idx != len(self.editors) - 1:
                        self.setTabOrder(self.editors[idx], self.editors[idx+1])

    ##!!@pyqtSlot(list)
    def filterByDialects(self, filter_dialects):
        if filter_dialects:
            dialect_abbrs = [d.abbr for d in self.dialect_widget.dialects]
            filter_abbrs = [d.abbr for d in filter_dialects]
            inter = set.intersection(set(dialect_abbrs), set(filter_abbrs))
            if inter:
                self.dialect_widget.filterByDialects(filter_dialects)
                try:
                    self.show()
                except: #already delected
                    pass
            else:
                try:
                    self.hide()
                except: #already delected
                    pass

    def setVideo(self, media_object):
        if self.video:
            self.video.filename = media_object.filename #os.path.normpath(filename)

    def setSenseOrder(self, _int):
        self.sense_order = _int
        self.sense_order_label.setText(' {} '.format(_int))

    def isNew(self):
        try:
            int(self.gloss_id)
        except:
            return True # if new, id is string 'n..'
        else:
            return False # integer id will pass this test

    @property
    def gloss_id(self):
        return self.sense_id

    def __setEditor(self):
        idx = 0
        item = self.editor_layout.itemAt(idx)
        while item:
            widget = item.widget()
            pos = self.mapFromGlobal(self.cursor().pos())
            rect = widget.rect().translated(widget.pos())
            if isinstance(widget, QLabel) and rect.contains(pos):
                lang_id = widget.lang_id
                self.editor = [e for e in self.editors if e.lang_id == lang_id][0]
                break
            idx += 1
            item = self.editor_layout.itemAt(idx)
        self.parent().setCurrentEditor(self.editor)
        if self.editor:
            self.editor.setFocus()

    def mousePressEvent(self, evt):
        rect = self.remove_label.rect().translated(self.remove_label.pos())
        if self.edit and rect.contains(evt.pos()):
            self.setFocus()
            self.onDelete(not self.delete_flag)
            self.deleted.emit(self.delete_flag)
        elif not self.delete_flag:# and self.icon_label.underMouse():
            self._selected.emit()
            self.__setEditor()
            rect = self.sense_drag_handle.rect().translated(self.sense_drag_handle.pos())
            if rect.contains(evt.pos()):
                self.sense_drag_handle.setCursor(QCursor(Qt.ClosedHandCursor))
        super(SenseWidget, self).mousePressEvent(evt)

    def mouseReleaseEvent(self, evt):
        self.sense_drag_handle.setCursor(QCursor(Qt.OpenHandCursor))
        return QWidget.mouseReleaseEvent(self, evt)

    def setTexts(self, text_dict):
        print('Not currently amending texts for Sense Widget')
        pass
#         for key in text_dict.keys():
#             lang_id = key
#             text = text_dict.get(lang_id)
#             editor = self.__getEditor(lang_id)
#             editor.setText(text)

    ##!!@pyqtSlot()
    def onTextChanged(self):
        editor = self.sender()
        if not self.property('selected'):
            self._selected.emit()
        text = editor.toPlainText()
        gloss_texts = [gt for gt in self.gloss_texts if gt.lang_id == editor.lang_id]
        if not text and not editor.orig_text:
            if gloss_texts:
                self.gloss_texts.remove(gloss_texts[0])
        else:
            if gloss_texts:
                gloss_text = gloss_texts[0]
                gloss_text.text = text

        if text != editor.orig_text:
            self.amend_flag = True
            editor.setProperty('amend', True)
        else:
            self.amend_flag = False
            editor.setProperty('amend', False)

        self.setStyles()
        qApp.processEvents()
        self.parent().setCurrentEditor(editor)
        self.amended.emit()

    ##!!@pyqtSlot(bool)
    def onEnterEdit(self, _bool):
        self.edit = _bool
        try:
            self.remove_label.setVisible(_bool)
        except:
            pass # remove label already deleted
        else:
            if _bool:
                cursor = QCursor(Qt.PointingHandCursor)
                self.remove_label.setCursor(cursor)
                self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to delete sense"))
        try:
            self.gram_cat_widget.onEnterEdit(_bool)
        except:
            pass
        try:
            self.dialect_widget.onEnterEdit(_bool)
        except:
            pass

        if not _bool: #normal search mode
            self.sense_drag_handle.setCursor(QCursor(Qt.ArrowCursor))
            self.sense_drag_handle.setToolTip(None)
            self.sense_drag_handle.setStyleSheet(None)
            self.sense_drag_handle.setMaximumSize(QSize(2, 48))
            #self.onEditingFinished()
            self.delete_flag = False
            self.amend_flag = False

            idx = 0
            try:
                item = self.editor_layout.itemAt(idx)
            except:
                pass
            else:
                while item:
                    widget = item.widget()
                    widget.show()
                    if isinstance(widget, MyMultilineEdit):
                        if widget.hasFocus():
                            widget.parent().setFocus()
                        widget.setFrame(False)
                        widget.setReadOnly(True)
                        if widget.lang_id not in qApp.instance().pm.selected_lang_ids:
                            widget.hide()
                        # if not widget.text():
                        #     widget.blockSignals(True)
                        #     widget.setText('???')
                        #     widget.setOrigText('???')
                        #     widget.blockSignals(False)
                    elif isinstance(widget, QLabel):
                        widget.hide()
                    idx += 1
                    item = self.editor_layout.itemAt(idx)

        else: #editing mode
            lang_ids = [l.id for l in qApp.instance().pm.project.writtenLanguages]
            self.sense_drag_handle.setCursor(QCursor(Qt.OpenHandCursor))
            key1 = QKeySequence(Qt.CTRL + Qt.Key_Up)
            key2 = QKeySequence(Qt.CTRL + Qt.Key_Down)
            shortcut = '{} {} | {}'.format(qApp.instance().translate('SenseWidget', 'Keyboard:'), key1.toString(QKeySequence.NativeText), key2.toString(QKeySequence.NativeText))
            self.sense_drag_handle.setToolTip('{}\n{}'.format(qApp.instance().translate('SenseWidget', 'Click and drag to change sense order'), shortcut))
            self.sense_drag_handle.setStyleSheet("QLabel {background:purple; color:white;}")
            self.sense_drag_handle.setMaximumSize(QSize(20, 48))
            idx = 0
            try:
                item = self.editor_layout.itemAt(idx)
            except:
                pass
            else:
                while item:
                    widget = item.widget()
                    widget.show()
                    if isinstance(widget, MyMultilineEdit):
                        widget.setFrame(True)
                        widget.setReadOnly(False)
                        # if widget.text() == '???':
                        #     widget.blockSignals(True)
                        #     widget.setText('')
                        #     widget.setOrigText('')
                        #     widget.blockSignals(False)
                    idx += 1
                    item = self.editor_layout.itemAt(idx)
        self.setStyles()

    def setSelected(self, _bool=True):
        if self.sender() == self and not self.sender().property('selected'):
            self.setProperty('selected', True)
            self.gram_cat_widget.setStyleSheet('QLabel{color: white;}')
            self.dialect_widget.setStyleSheet('QLabel{color: white;}')
            self.gloss_changed.emit(self.gloss_texts)
        elif self.sender() != self:
            self.setProperty('selected', False)
            self.gram_cat_widget.setStyleSheet(None)
            self.dialect_widget.setStyleSheet(None)
            self.sense_field = 0
        self.setStyles()
        qApp.processEvents()

    ##!!@pyqtSlot(bool)
    def onSignDelete(self, _bool):
        self.remove_label.setHidden(_bool)
        self.onDelete(_bool)

    ##!!@pyqtSlot(bool)
    def onDelete(self, _bool):
        self.delete_flag = _bool
        for editor in self.editors:
            try:
                if editor.hasFocus():
                    self.setFocus()
                editor.setDisabled(_bool)
                editor.setProperty('disabled', _bool)
            except:
                pass
        self.setStyles()
        self.amended.emit()
        qApp.processEvents()

    ##!!@pyqtSlot(int, int)
    ##!!@pyqtSlot(str, int)
    def onFontSizeChange(self, lang_id, _int):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass # editor deleted
                else:
                    font.setPointSize(_int + 1)
                    font.setBold(True)
                    editor.setFont(font)

    def onFontFamilyChange(self, lang_id, family_name):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                font = None
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass
                else:
                    font.setFamily(family_name)
                    editor.setFont(font)

    def setStyles(self):
        dcolor = self.parent().DELETE_CLR
        if self.property('selected'):
            bcolor = self.parent().SELECTED_BKG
        else:
            bcolor = self.parent().SENSE_BKG
        tcolor = self.parent().TEXT_CLR

        style_str = None
        style_str = """QTextEdit[disabled='true']{color: dcolor; text-decoration: line-through;}
                        QTextEdit[readOnly='true']{background: bcolor;}
                        QTextEdit[readOnly='true']:focus{background: bcolor; selection-color: black; selection-background-color: yellow;}
                        QTextEdit[readOnly='false']{background: white;}
                        QTextEdit[readOnly='false']:focus{border: 2px solid blue;}
                        QTextEdit[amend='true']{color: red;}"""

        style_str = style_str.replace('dcolor', dcolor.name())
        style_str = style_str.replace('bcolor', bcolor.name())
        self.setStyleSheet(style_str)

        if self.delete_flag:
            self.remove_label.setStyleSheet("""background: {}""".format(dcolor.name()))
            self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to keep sense"))
            self.setBackground(self.parent().DELETE_CLR)
        else:
            self.remove_label.setStyleSheet(None)
            self.remove_label.setToolTip(qApp.instance().translate('SenseWidget', "Click to delete sense"))

            self.setBackground(bcolor)
        self.repaint()

class SenseDragHandle(QLabel):
    drag_widget = pyqtSignal(SenseWidget)

    def __init__(self, parent):
        super(SenseDragHandle, self).__init__(parent)

    def mousePressEvent(self, evt):
        if self.parent().edit:
            self.drag_widget.emit(self.parent())
        return QLabel.mousePressEvent(self, evt)

    def mouseReleaseEvent(self, evt):
        if self.parent().edit:
            self.drag_widget.emit(None)
        return QLabel.mouseReleaseEvent(self, evt)

class SentenceWidget(QWidget):
    amended = pyqtSignal()
    _selected = pyqtSignal()
    #repaint_widgets = pyqtSignal()

    def __init__(self, sentence, sense_id, parent):
        super(SentenceWidget, self).__init__(parent)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAutoFillBackground(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_type = 'sent'
        self.edit = parent.edit
        self.setProperty('selected', False)
        self.delete_flag = False
        self.amend_flag = False
        self.sentence = sentence
        self.sense_id = sense_id
        self.texts = self.sentence.sentence_texts #copy.deepcopy(self.sentence.sentence_texts)
        self.sentence_layout = QHBoxLayout()
        self.sentence_layout.setSpacing(2)
        self.sentence_layout.setContentsMargins(8, 2, 0, 2)
        self.normal_pxm = QPixmap(':/sentence_up.png')
        self.selected_pxm = QPixmap(':/sentence_down.png')
        self.icon_label = QLabel(self)
        self.icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.icon_label.setPixmap(self.normal_pxm)
        self.icon_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to select this sentence and show its video"))
        self.editors = []
        self.editor = None
        self.editor_layout = QGridLayout()
        self.editor_layout.setContentsMargins(0,0,0,0)
        self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        self.remove_label = QLabel(self)
        self.remove_label.setFixedSize(QSize(24, 24))
        self.remove_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.remove_pxm = QPixmap(':/trash20.png')
        self.remove_label.setPixmap(self.remove_pxm)

        self.sentence_layout.addWidget(self.icon_label)
        self.sentence_layout.addLayout(self.editor_layout)
        self.sentence_layout.addWidget(self.remove_label)
        self.sentence_layout.setAlignment(self.icon_label, Qt.AlignTop|Qt.AlignLeft)
        self.sentence_layout.setAlignment(self.remove_label, Qt.AlignTop)
        self.sentence_layout.setAlignment(self.editor_layout, Qt.AlignTop)
        self.setLayout(self.sentence_layout)

        langs = qApp.instance().pm.project.writtenLanguages
        row = 0
        sent_id = sentence.id
        for lang in langs:
            lang_id = lang.id
            lang_name = lang.name
            editor = self.__getEditor(lang_id)
            _bool = False
            if isinstance(sent_id, str) and sent_id.startswith('n'):
                _bool = True
            editor.setProperty('amend', _bool)
            self.editors.append(editor)

            lbl = self.__getEditorLabel(lang_id, lang_name)

            self.editor_layout.addWidget(editor, row, 0)
            self.editor_layout.addWidget(lbl, row, 1)
            row += 1

            font_size = qApp.instance().pm.getFontSizeById(lang_id)
            self.onFontSizeChange(lang_id, font_size)
            font_family = qApp.instance().pm.getFontFamily(lang_name)
            self.onFontFamilyChange(lang_id, font_family)
        if self.editors:
            self.editor = self.editors[0]

        qApp.instance().pm.lang_selection_change.connect(self.onLangSelectionChange)
        qApp.instance().pm.font_size_change.connect(self.onFontSizeChange)
        qApp.instance().pm.font_family_change.connect(self.onFontFamilyChange)
        qApp.instance().pm.lang_order_change.connect(self.onLangOrderChange)
        self.parent().repaint_widgets.connect(self.onRepaint)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    # def resizeEvent(self, evt):
    #     self.layout().invalidate()
    #     super(SentenceWidget, self).resizeEvent(evt)

    def updateToolTips(self):
        self.icon_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to select this sentence and show its video"))
        if self.edit:
            if self.delete_flag:
                self.remove_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to keep sentence"))
            else:
                self.remove_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to delete sentence"))

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def __getEditor(self, lang_id):
        text = ''
        try:
            text = [t.text for t in self.texts if t.lang_id == lang_id][0].strip()
        except:
            pass
        editor = MyMultilineEdit(self, text, lang_id)

        if not text or editor.lang_id not in qApp.instance().pm.selected_lang_ids:
            editor.hide()
        editor.setOrigText(text)
        editor.setReadOnly(True)
        editor.setFrame(False)
        editor.setFocusPolicy(Qt.StrongFocus)
        editor.textChanged.connect(self.onTextChanged)
        return editor

    def __getEditorLabel(self, lang_id, lang_name):
        lbl = QLabel(lang_name, self)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        lbl.setContentsMargins(5, 0, 5, 0)
        lbl.lang_id = lang_id
        lbl.hide()
        return lbl

    def setBackground(self, bkg_color):
        p = self.palette()
        p.setColor(QPalette.Base, bkg_color)
        self.setPalette(p)
        if bkg_color == self.parent().SELECTED_BKG and not self.edit:
            frg_color = self.parent().SELECTED_TEXT_CLR
        elif bkg_color == self.parent().DELETE_CLR:
            frg_color = self.parent().DELETE_CLR
        else:
            frg_color = self.parent().TEXT_CLR

        for editor in self.editors:
            try:
                p = editor.palette()
                p.setColor(QPalette.Base, bkg_color)
                if not editor.property('amend'):
                    p.setColor(QPalette.Text, frg_color)
                if not self.edit and not editor.text(): # == '???':
                    p.setColor(QPalette.Text, Qt.gray)
                editor.setPalette(p)
            except:
                pass

    ##!!@pyqtSlot(list)
    def onLangOrderChange(self, lang_ids):
        widgets = []
        row = 0
        while row < self.editor_layout.rowCount():
            editor = self.editor_layout.itemAtPosition(row, 0).widget()
            lang_lbl = self.editor_layout.itemAtPosition(row, 1).widget()
            self.editor_layout.removeWidget(editor)
            self.editor_layout.removeWidget(lang_lbl)
            if editor.lang_id not in lang_ids:
                editor.close()
                lang_lbl.close()
            else:
                widgets.append(editor)
                widgets.append(lang_lbl)
            row += 1

        self.sentence_layout.removeItem(self.editor_layout)
        del self.editor_layout

        self.editor_layout = QGridLayout()
        self.editor_layout.setContentsMargins(0,0,0,0)
        self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.sentence_layout.insertLayout(1, self.editor_layout)

        row = 0
        lang_ids = [l for l in lang_ids if (isinstance(l, int) and l > 0) or isinstance(l, str)]
        for _id in lang_ids:
            if isinstance(_id, int):
                try:
                    editor, lang_lbl = [e for e in widgets if e.lang_id == _id]
                except:
                    editor, lang_lbl = [None, None]
            elif isinstance(_id, str): #new lang
                name = _id
                _id = qApp.instance().pm.getLangId(name)
                editor = self.__getEditor(_id)
                self.editors.append(editor)
                lang_lbl = self.__getEditorLabel(_id, name)
            if editor:
                self.editor_layout.addWidget(editor, row, 0)
                self.editor_layout.addWidget(lang_lbl, row, 1)
                row += 1
        self.setStyles()
        qApp.processEvents()
        self.adjustSize()

    ##!!@pyqtSlot()
    def onLangSelectionChange(self):
        if not self.edit:
            for editor in self.editors:
                try:
                    if editor.lang_id in qApp.instance().pm.selected_lang_ids and editor.text():
                        editor.show()
                    else:
                        editor.hide()
                except:
                    pass

    ##!!@pyqtSlot()
    def onTextChanged(self):
        editor = self.sender()
        if not self.property('selected'):
            self._selected.emit()
        #case when editing an unglossed sign, but adding nothing new;
        #just leaving edit adds and empty entry in dictionary {0:65, 1:''}, need to remove any empty entry
        text = editor.toPlainText()
        sent_id = self.sentence.id
        if text != editor.orig_text or \
            isinstance(sent_id, str) and sent_id.startswith('n'): #new sentence
            self.amend_flag = True
            editor.setProperty('amend', True)
        else:
            self.amend_flag = False
            editor.setProperty('amend', False)
        self.setStyles()
        qApp.processEvents()
        self.parent().setCurrentEditor(editor)
        self.amended.emit()

    @property
    def video(self):
        return self.sentence.media_object

    def setVideo(self, media): #, response=2):
        ##response determines how updates are handled; '2' for everywhere file is used; '1' for just once
        self.video.filename = media.filename

    def setTexts(self, text_dict):
        if isinstance(text_dict, list): #probably is; NOTE: maybe change this method if this is what always happens...
            td = {}
            for text in text_dict:
                td[text.lang_id] = text.text
            text_dict = td
        for key in text_dict.keys():
            lang_id = key
            text = text_dict.get(lang_id)
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                editor = editors[0]
                editor.setText(text)

    def __setEditor(self):
        idx = 0
        item = self.editor_layout.itemAt(idx)
        while item:
            widget = item.widget()
            pos = self.mapFromGlobal(self.cursor().pos())
            rect = widget.rect().translated(widget.pos())
            if isinstance(widget, QLabel) and rect.contains(pos):
                lang_id = widget.lang_id
                self.editor = [e for e in self.editors if e.lang_id == lang_id][0]
                break
            idx += 1
            item = self.editor_layout.itemAt(idx)
        self.parent().setCurrentEditor(self.editor)
        if self.editor:
            self.editor.setFocus()

    def mousePressEvent(self, evt):
        rect = self.remove_label.rect().translated(self.remove_label.pos())
        if self.edit and rect.contains(evt.pos()):
            self.setFocus()
            self.onDelete(not self.delete_flag)
        elif not self.delete_flag:
            self._selected.emit()
            self.__setEditor()
        super(SentenceWidget, self).mousePressEvent(evt)

    ##!!@pyqtSlot(bool)
    def onEnterEdit(self, _bool):
        self.edit = _bool
        try:
            self.remove_label.setVisible(_bool)
        except:
            pass
        else:
            if _bool:
                self.remove_label.setCursor(QCursor(Qt.PointingHandCursor))
                self.remove_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to delete sentence"))
        if not _bool: #leaving edit
            self.delete_flag = False
            self.amend_flag = False

            idx = 0
            item = self.editor_layout.itemAt(idx)
            while item:
                widget = item.widget()
                widget.show()
                if isinstance(widget, MyMultilineEdit):
                    widget.setFrame(False)
                    widget.setReadOnly(True)
                    widget.setProperty('readOnly', True)
                    if widget.lang_id not in qApp.instance().pm.selected_lang_ids:
                        widget.hide()
                    # if not widget.toPlainText():
                    #     widget.blockSignals(True)
                    #     widget.setText('???')
                    #     widget.setOrigText('???')
                    #     widget.blockSignals(False)
                elif isinstance(widget, QLabel):
                    widget.hide()
                idx += 1
                item = self.editor_layout.itemAt(idx)
        else: #editing mode
            idx = 0
            item = self.editor_layout.itemAt(idx)
            while item:
                widget = item.widget()
                widget.show()
                if isinstance(widget, MyMultilineEdit):
                    widget.setFrame(True)
                    widget.setReadOnly(False)
                    widget.setProperty('readOnly', False)
                    # if widget.toPlainText() == '???':
                    #     widget.blockSignals(True)
                    #     widget.setText('')
                    #     widget.setOrigText('')
                    #     widget.blockSignals(False)
                idx += 1
                item = self.editor_layout.itemAt(idx)
        self.setStyles()
        qApp.processEvents()

    ##!!@pyqtSlot(bool)
    def onGlossDelete(self, _bool):
        self.remove_label.setHidden(_bool)
        self.onDelete(_bool)

    ##!!@pyqtSlot(bool)
    def onDelete(self, _bool):
        self.delete_flag = _bool
        for editor in self.editors:
            try:
                if editor.hasFocus():
                    self.setFocus()
                editor.setProperty('disabled', _bool)
                editor.setDisabled(_bool)
            except:
                pass
        self.setStyles()
        qApp.processEvents()
        self.amended.emit()

    ##!!@pyqtSlot(int, int)
    ##!!@pyqtSlot(str, int)
    def onFontSizeChange(self, lang_id, _int):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                font = None
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass
                else:
                    font.setPointSize(_int)
                    editor.setFont(font)

    def onFontFamilyChange(self, lang_id, family_name):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                font = None
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass
                else:
                    font.setFamily(family_name)
                    editor.setFont(font)

    def setStyles(self):
        dcolor = self.parent().DELETE_CLR
        if self.property('selected'):
            bcolor = self.parent().SELECTED_BKG
        elif self.property('isOdd'):
            bcolor = self.parent().SENTENCE_BKG
        else:
            bcolor = self.parent().SENTENCE_ALT_BKG
        tcolor = self.parent().TEXT_CLR

        style_str = None
        style_str = """QTextEdit[disabled='true']{color: dcolor; text-decoration: line-through;}
                        QTextEdit[readOnly='true']{background: bcolor;}
                        QTextEdit[readOnly='true']:focus{background: bcolor; selection-color: black; selection-background-color: yellow;}
                        QTextEdit[readOnly='false']{background: white;}
                        QTextEdit[readOnly='false']:focus{border: 2px solid blue;}
                        QTextEdit[amend='true']{color: red;}"""
        style_str = style_str.replace('dcolor', dcolor.name())
        style_str = style_str.replace('bcolor', bcolor.name())
        self.setStyleSheet(style_str)

        if self.delete_flag:
            self.remove_label.setStyleSheet("""background: {}""".format(dcolor.name()))
            self.remove_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to keep sentence"))
            self.setBackground(self.parent().DELETE_CLR)
        else:
            self.remove_label.setStyleSheet(None)
            self.remove_label.setToolTip(qApp.instance().translate('SentenceWidget', "Click to delete sentence"))

            self.setBackground(bcolor)
        self.repaint()

    def setSelected(self, _bool=True):
        #NOTE: see def onModelReset #489
        try:
            if self.sender() == self and not self.sender().property('selected'):
                self.setProperty('selected', True)
            elif self.sender() != self:
                self.setProperty('selected', False)
        except:
            pass
        else:
            self.setStyles()
        qApp.processEvents()

class ExtraTextWidget(QWidget):
    amended = pyqtSignal()
    deleted = pyqtSignal(bool)
    _selected = pyqtSignal()
    #repaint_widgets = pyqtSignal()

    def __init__(self, texts, parent):
        super(ExtraTextWidget, self).__init__(parent)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.edit = parent.edit
        self.delete_flag = False
        self.amend_flag = False
        self.setProperty('selected', False)
        self.texts = texts #copy.deepcopy(texts)
        self.text_layout = QHBoxLayout()
        self.text_layout.setSpacing(3)
        self.text_layout.setContentsMargins(0, 0, 0, 0)
        pxm_h = 28
        self.normal_pxm = QPixmap(":/text_file.png").scaledToHeight(pxm_h, Qt.SmoothTransformation)
        self.selected_pxm = self.normal_pxm
        self.icon_label = QLabel(self)
        self.icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.icon_label.setPixmap(self.normal_pxm)
        self.editors = []
        self.editor = None
        self.editor_layout = QGridLayout()
        self.editor_layout.setContentsMargins(0,0,0,0)
        self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        self.remove_label = QLabel(self)
        self.remove_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.remove_pxm = QPixmap(':/trash20.png')
        self.remove_label.setPixmap(self.remove_pxm)
        self.remove_label.setCursor(QCursor(Qt.PointingHandCursor))
        if not self.edit:
            self.remove_label.hide()

        self.text_layout.addWidget(self.icon_label)
        self.text_layout.addLayout(self.editor_layout)
        self.text_layout.addWidget(self.remove_label)
        self.text_layout.setAlignment(self.icon_label, Qt.AlignTop|Qt.AlignLeft)
        self.text_layout.setAlignment(self.editor, Qt.AlignTop)
        self.text_layout.setAlignment(self.remove_label, Qt.AlignTop)
        self.setLayout(self.text_layout)

        langs = qApp.instance().pm.project.writtenLanguages
        row = 0
        for lang in langs:
            lang_id = lang.id
            lang_name = lang.name
            editor = self.__getEditor(lang_id)
            self.editors.append(editor)

            lbl = self.__getEditorLabel(lang_id, lang_name)

            self.editor_layout.addWidget(editor, row, 0)
            self.editor_layout.addWidget(lbl, row, 1)
            row += 1

            font_size = qApp.instance().pm.getFontSizeById(lang_id)
            self.onFontSizeChange(lang_id, font_size)
            font_family = qApp.instance().pm.getFontFamily(lang_name)
            self.onFontFamilyChange(lang_id, font_family)
        if self.editors:
            self.editor = self.editors[0]

        qApp.instance().pm.lang_selection_change.connect(self.onLangSelectionChange)
        qApp.instance().pm.font_size_change.connect(self.onFontSizeChange)
        qApp.instance().pm.font_family_change.connect(self.onFontFamilyChange)
        qApp.instance().pm.lang_order_change.connect(self.onLangOrderChange)
        self.parent().repaint_widgets.connect(self.onRepaint)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    def updateToolTips(self):
        if self.edit:
            if self.delete_flag:
                self.remove_label.setToolTip(qApp.instance().translate('ExtraTextWidget', "Click to keep extra text"))
            else:
                self.remove_label.setToolTip(qApp.instance().translate('ExtraTextWidget', "Click to delete extra text"))

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def __getEditor(self, lang_id):
        text = ''
        texts = [text.text for text in self.texts if text.lang_id == lang_id]
        if texts:
            text = texts[0].strip()
        editor = MyMultilineEdit(self, text, lang_id)
        if not text: # == '???':
            p = editor.palette()
            p.setColor(QPalette.Text, Qt.gray)
            editor.setPalette(p)

        if editor.lang_id not in qApp.instance().pm.selected_lang_ids:
            editor.hide()
        editor.setOrigText(text)
        editor.setReadOnly(True)
        editor.setFrame(False)
        editor.setFocusPolicy(Qt.StrongFocus)
        editor.textChanged.connect(self.onTextChanged)
        return editor

    def __getEditorLabel(self, lang_id, lang_name):
        lbl = QLabel(lang_name, self)
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        lbl.setContentsMargins(5, 0, 5, 0)
        lbl.lang_id = lang_id
        lbl.hide()
        return lbl

    ##!!@pyqtSlot(list)
    def onLangOrderChange(self, lang_ids):
        widgets = []
        row = 0
        while row < self.editor_layout.rowCount():
            editor = self.editor_layout.itemAtPosition(row, 0).widget()
            lang_lbl = self.editor_layout.itemAtPosition(row, 1).widget()
            self.editor_layout.removeWidget(editor)
            self.editor_layout.removeWidget(lang_lbl)
            if editor.lang_id not in lang_ids:
                editor.close()
                lang_lbl.close()
            else:
                widgets.append(editor)
                widgets.append(lang_lbl)
            row += 1

        self.text_layout.removeItem(self.editor_layout)
        del self.editor_layout

        self.editor_layout = QGridLayout()
        self.editor_layout.setContentsMargins(0,0,0,0)
        self.editor_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.text_layout.insertLayout(1, self.editor_layout)

        row = 0
        lang_ids = [l for l in lang_ids if (isinstance(l, int) and l > 0) or isinstance(l, str)]
        for _id in lang_ids:
            if isinstance(_id, int):
                try:
                    editor, lang_lbl = [e for e in widgets if e.lang_id == _id]
                except:
                    editor, lang_lbl = [None, None]
            elif isinstance(_id, str): #new lang
                name = _id
                _id = qApp.instance().pm.getLangId(name)
                editor = self.__getEditor(_id)
                self.editors.append(editor)
                lang_lbl = self.__getEditorLabel(_id, name)
            if editor:
                self.editor_layout.addWidget(editor, row, 0)
                self.editor_layout.addWidget(lang_lbl, row, 1)
                row += 1
        self.setStyles()
        qApp.processEvents()
        self.adjustSize()

    ##!!@pyqtSlot()
    def onLangSelectionChange(self):
        if not self.edit:
            for editor in self.editors:
                try:
                    if editor.lang_id in qApp.instance().pm.selected_lang_ids and editor.text():
                        editor.show()
                    else:
                        editor.hide()
                except:
                    pass

    ##!!@pyqtSlot()
    def onTextChanged(self):
        editor = self.sender()
        if not self.property('selected'):
            self._selected.emit()
        #case when editing an unglossed sign, but adding nothing new;
        #just leaving edit adds and empty entry in dictionary {0:65, 1:''}, need to remove any empty entry
        text = editor.toPlainText()

        if text != editor.orig_text:
            self.amend_flag = True
            editor.setProperty('amend', True)
        else:
            self.amend_flag = False
            editor.setProperty('amend', False)
        self.setStyles()
        qApp.processEvents()

        self.parent().setCurrentEditor(editor)
        self.amended.emit()

    def __setEditor(self):
        idx = 0
        item = self.editor_layout.itemAt(idx)
        while item:
            widget = item.widget()
            pos = self.mapFromGlobal(self.cursor().pos())
            rect = widget.rect().translated(widget.pos())
            if isinstance(widget, QLabel) and rect.contains(pos):
                lang_id = widget.lang_id
                self.editor = [e for e in self.editors if e.lang_id == lang_id][0]
                break
            idx += 1
            item = self.editor_layout.itemAt(idx)
        self.parent().setCurrentEditor(self.editor)
        if self.editor:
            self.editor.setFocus()

    def mousePressEvent(self, evt):
        rect = self.remove_label.rect().translated(self.remove_label.pos())
        if self.edit and rect.contains(evt.pos()):
            self.setFocus()
            self.onDelete(not self.delete_flag)
        elif not self.delete_flag:
            self._selected.emit()
            self.__setEditor()
        super(ExtraTextWidget, self).mousePressEvent(evt)

    ##!!@pyqtSlot(bool)
    def onEnterEdit(self, _bool):
        texts = [t for t in self.texts if t.text.strip()] # texts may be just spaces; one dictionary used this to not show '???' before this fix.
        if _bool or texts:
            self.show()
        else:
            self.hide()
        self.edit = _bool
        try:
            self.remove_label.setVisible(_bool)
        except:
            pass
        else:
            if not _bool:
                self.delete_flag = False
                self.amend_flag = False

                idx = 0
                try:
                    item = self.editor_layout.itemAt(idx)
                except:
                    pass
                else:
                    while item:
                        widget = item.widget()
                        widget.show()
                        if isinstance(widget, MyMultilineEdit):
                            if widget.hasFocus():
                                widget.parent().setFocus()
                            widget.setFrame(False)
                            widget.setReadOnly(True)
                            widget.setFocusPolicy(Qt.StrongFocus)
                            if widget.lang_id not in qApp.instance().pm.selected_lang_ids:
                                widget.hide()
                            # if not widget.toPlainText():
                            #     widget.blockSignals(True)
                            #     widget.setText('???')
                            #     widget.setOrigText('???')
                            #     widget.blockSignals(False)
                        elif isinstance(widget, QLabel):
                            widget.hide()
                        idx += 1
                        item = self.editor_layout.itemAt(idx)
            else: #editing mode
                idx = 0
                try:
                    item = self.editor_layout.itemAt(idx)
                except:
                    pass
                else:
                    while item:
                        widget = item.widget()
                        widget.show()
                        if isinstance(widget, MyMultilineEdit):
                            widget.setFrame(True)
                            widget.setReadOnly(False)
                            widget.setFocusPolicy(Qt.StrongFocus)
                            # if widget.toPlainText() == '???':
                            #     widget.blockSignals(True)
                            #     widget.setText('')
                            #     widget.setOrigText('')
                            #     widget.blockSignals(False)
                        idx += 1
                        item = self.editor_layout.itemAt(idx)
            self.__hideOrShowRemoveLabel()
            self.setStyles()
            qApp.processEvents()

    def __hideOrShowRemoveLabel(self):
        if hasattr(self, 'remove_label'):
            if not self.edit:
                self.remove_label.setVisible(False)
            else:
                _bool = False
                for editor in self.editors:
                    try:
                        if editor.text():
                            _bool = True
                            break
                    except:
                        pass
# # #                   -----------------------------------------------------------------------------------------
# # #                   <class 'RuntimeError'>:
# # #                   wrapped C/C   object of type MyMultilineEdit has been deleted
# # #                   ------------------------------------------------------------------------------------------
# # #                     File "SooSL-0.8.8/SooSL-0.8.8/info_page.py", line 2188, in onEnterEdit
# # #                       self.__hideOrShowRemoveLabel()
# # #                     File "SooSL-0.8.8/SooSL-0.8.8/info_page.py", line 2198, in __hideOrShowRemoveLabel
# # #                       if editor.text():
# # #                     File "SooSL-0.8.8/SooSL-0.8.8/info_page.py", line 2720, in text
                self.remove_label.setVisible(_bool)

    ##!!@pyqtSlot(bool)
    def onSignDelete(self, _bool):
        try:
            self.remove_label.setHidden(_bool)
        except:
            pass
        else:
            self.onDelete(_bool)

    def onDelete(self, _bool):
        self.delete_flag = _bool
        for editor in self.editors:
            try:
                if editor.hasFocus():
                    self.setFocus()
                editor.setProperty('disabled', _bool)
                editor.setDisabled(_bool)
            except:
                pass
        self.setStyles()
        qApp.processEvents()
        self.amended.emit()

    ##!!@pyqtSlot(int, int)
    ##!!@pyqtSlot(str, int)
    def onFontSizeChange(self, lang_id, _int):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass
                else:
                    font.setPointSize(_int)
                    editor.setFont(font)

    def onFontFamilyChange(self, lang_id, family_name):
        if isinstance(lang_id, str): # new lang
            pass
        else:
            editors = [e for e in self.editors if e.lang_id == lang_id]
            if editors:
                font = None
                editor = editors[0]
                try:
                    font = editor.font()
                except:
                    pass
                else:
                    font.setFamily(family_name)
                    editor.setFont(font)

    def setSelected(self, _bool=True):
        if self.editor and self.sender() == self and not self.editor.hasFocus():
            self.editor.setFocus(True)

        if self.sender() == self and not self.sender().property('selected'):
            self.setProperty('selected', True)
        elif self.sender() != self:
            self.setProperty('selected', False)
        self.setStyles()
        qApp.processEvents()

    def setStyles(self):
        try:
            dcolor = self.parent().DELETE_CLR
        except:
            pass
        else:
            style_str = None
            style_str = """QTextEdit[disabled='true']{color: dcolor; text-decoration: line-through;}
                            QTextEdit[readOnly='true']:focus{selection-color: black; selection-background-color: yellow;}
                            QTextEdit[readOnly='false']{background: white;}
                            QTextEdit[readOnly='false']:focus{border: 2px solid blue;}
                            QTextEdit[amend='true']{color: red;}"""
            style_str = style_str.replace('dcolor', dcolor.name())
            self.setStyleSheet(style_str)

            if self.delete_flag:
                self.remove_label.setStyleSheet("""background: {}""".format(dcolor.name()))
                self.remove_label.setToolTip(qApp.instance().translate('ExtraTextWidget', "Click to keep extra text"))
            else:
                self.remove_label.setStyleSheet(None)
                self.remove_label.setToolTip(qApp.instance().translate('ExtraTextWidget', "Click to delete extra text"))
        self.repaint()

class GramCatWidget(QWidget):
    editingFinished = pyqtSignal()

    def __init__(self, gram_cat, parent):
        super(GramCatWidget, self).__init__(parent)
        self.gram_cat = gram_cat
        self.amend_flag = False
        self.delete_flag = False
        self.editing = False

        layout = QHBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        self.gram_cat_label = QLabel(self)
        self.gram_cat_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pxm = QPixmap(':/gram_cat.png')
        self.gram_cat_label.setPixmap(pxm)
        self.gram_cat_text_label = QLabel(self)
        self.gram_cat_text_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        text = ''
        if gram_cat:
            text = gram_cat.name
        self.gram_cat_text_label.setText('{}   '.format(text))
        self.orig_text = text
        if text or parent.edit:
            self.gram_cat_label.show()
            self.gram_cat_text_label.show()
        else:
            self.gram_cat_label.hide()
            self.gram_cat_text_label.hide()
        self.gram_cats_combo = GramCatsCombo(self)
        self.gram_cats_combo.setItemDelegate(GramCatItemDelegate(self.gram_cat, self.gram_cats_combo))
        self.gram_cats_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        all_types = sorted(qApp.instance().pm.project.grammar_categories, key=lambda x:x.name.lower())

        for t in all_types:
            name = t.name
            self.gram_cats_combo.addItem(name, userData=name)
        idx = self.gram_cats_combo.findText(self.orig_text)
        self.gram_cats_combo.setCurrentIndex(idx)
        self.gram_cats_combo.setEditable(False)
        self.gram_cats_combo.hide()
        self.gram_cats_combo.currentIndexChanged.connect(self.onGramCatChanged)

        layout.addWidget(self.gram_cat_label)
        layout.addWidget(self.gram_cat_text_label)
        layout.addWidget(self.gram_cats_combo)
        self.setLayout(layout)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    def updateToolTips(self):
        if self.editing:
            self.setToolTip(qApp.instance().translate('GramCatWidget', 'Click to edit grammar categories'))

    def onGramCatsAmended(self):
        """called when amending from the Grammar category tool; a project level change"""
        self.gram_cats_combo.currentIndexChanged.disconnect(self.onGramCatChanged)
        all_types = sorted(qApp.instance().pm.project.grammar_categories, key=lambda x:x.name.lower())
        current_id = None
        current_name = None
        if self.gram_cat:
            current_id = self.gram_cat.id
        self.gram_cats_combo.clear()
        self.gram_cat = None
        for t in all_types:
            id = t.id
            name = t.name
            if current_id and id == current_id:
                current_name = name
                self.gram_cat = t
            self.gram_cats_combo.addItem(name, userData=name)
        old_name = self.gram_cat_text_label.text().strip()
        if current_name:
            idx = self.gram_cats_combo.findText(current_name)
            self.gram_cats_combo.setCurrentIndex(idx)
            if old_name != current_name:
                self.gram_cat_text_label.setText('{}   '.format(current_name))
        else:
            self.gram_cats_combo.setCurrentIndex(-1)
            self.gram_cat_label.clear()
            self.gram_cat_text_label.clear()
            self.gram_cat_label.hide()
            if not self.editing:
                self.gram_cat_text_label.hide()
        self.gram_cats_combo.currentIndexChanged.connect(self.onGramCatChanged)

    ##!!@pyqtSlot(int)
    def onGramCatChanged(self, idx):
        if idx > -1:
            all_types = sorted(qApp.instance().pm.project.grammar_categories, key=lambda x:x.name.lower())
            self.gram_cat = all_types[idx]
            new_text = self.gram_cats_combo.currentText()
            self.gram_cat_text_label.setText('{}   '.format(new_text))
            if new_text != self.orig_text:
                self.amend_flag = True
            else:
                self.amend_flag = False
            self.setStyles()
            qApp.processEvents()
            self.parent().amended.emit()

    def onEnterEdit(self, _bool):
        self.editing = _bool
        self.gram_cats_combo.setVisible(_bool)
        self.gram_cat_text_label.setHidden(_bool) # holds the text
        if not self.gram_cat_text_label.text().strip():
            self.gram_cat_label.setVisible(_bool)
        if not _bool: #leaving
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.setToolTip(None)
            self.delete_flag = False
            self.amend_flag = False
        else: # entering
            self.setCursor(QCursor(Qt.PointingHandCursor))
            self.setToolTip(qApp.instance().translate('GramCatWidget', 'Click to edit grammar categories'))

    ##!!@pyqtSlot(bool)
    def onDelete(self, _bool):
        self.delete_flag = _bool
        self.setDisabled(_bool)

    def onEditingFinished(self):
        self.gram_cats_combo.hide()
        self.gram_cat_text_label.show()

    def onGramCatsCombo(self):
#         self.parent()._selected.emit()
        self.parent().parent().setCurrentEditor(self)

    def setStyles(self):
        if self.gram_cats_combo.hasFocus():
            if self.delete_flag:
                self.gram_cats_combo.setStyleSheet("""border: 1px solid red; color: red; text-decoration: line-through""")
            elif self.amend_flag:
                self.gram_cats_combo.setStyleSheet("""border: 1px solid red; color: red""")
            else:
                self.gram_cats_combo.setStyleSheet("""border: 1px solid blue""")
        else:
            if self.delete_flag:
                self.gram_cats_combo.setStyleSheet("""color: red; text-decoration: line-through""")
            elif self.amend_flag:
                self.gram_cats_combo.setStyleSheet("""color: red""")
            else:
                self.gram_cats_combo.setStyleSheet(None)
        self.repaint()

class GramCatsCombo(QComboBox):
    def __init__(self, parent=None):
        super(GramCatsCombo, self).__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.currentIndexChanged.connect(self.onCurrentIndexChanged)

    def focusInEvent(self, evt):
        self.parent().parent()._selected.emit()
        super(GramCatsCombo, self).focusInEvent(evt)

    def showPopup(self):
        self.parent().onGramCatsCombo()
        super(GramCatsCombo, self).showPopup()

    ##!!@pyqtSlot(int)
    def onCurrentIndexChanged(self, idx):
        text = self.itemText(idx)
        fm = self.fontMetrics()
        width = fm.width(text) + 30
        self.setMinimumWidth(width)

class DialectCombo(QComboBox):
    def __init__(self, parent=None):
        super(DialectCombo, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

    def setText(self, text):
        self.clear()
        self.addItem(text, userData=None)
        fm = self.fontMetrics()
        width = fm.width(text) + 30
        self.setMinimumWidth(width)

    def showPopup(self):
        self.parent().onDialectCombo()

    def focusInEvent(self, evt):
        self.parent().parent()._selected.emit()
        super(DialectCombo, self).focusInEvent(evt)

class DialectWidget(QWidget):
    editingFinished = pyqtSignal()

    def __init__(self, dialects, parent):
        super(DialectWidget, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.editing = False
        self.dialects = dialects
        self.orig_dialects = []
        for d in dialects:
            self.orig_dialects.append(d)
        if dialects:
            self.dialects = dialects
        self.amend_flag = False
        self.delete_flag = False

        layout = QHBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        self.dialect_label = QLabel(self)
        self.dialect_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pxm = QPixmap(':/dialect_small.png')
        self.dialect_label.setPixmap(pxm)
        self.dialect_text_label = QLabel(self)
        self.dialect_text_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.orig_str = text = qApp.instance().pm.dialectStr(dialects)
        self.dialect_text_label.setText('{}   '.format(text))

        self.dialect_combo = DialectCombo(self)
        self.dialect_combo.setText(text)

        if text:
            if not self.editing:
                self.dialect_text_label.show()
        else:
            self.dialect_text_label.hide()
        if parent.edit:
            self.dialect_combo.show()
        else:
            self.dialect_combo.hide()

        layout.addWidget(self.dialect_label)
        layout.addWidget(self.dialect_text_label)
        layout.addWidget(self.dialect_combo)
        self.setLayout(layout)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    def updateToolTips(self):
        if self.editing:
            self.setToolTip(qApp.instance().translate('DialectWidget', 'Click to edit dialects'))

    def onDialectCombo(self):
#         self.parent()._selected.emit()
        self.parent().parent().setCurrentEditor(self)
        self.edit()

    ##!!@pyqtSlot(list)
    def filterByDialects(self, filter_dialects):
        if filter_dialects:
            abbrs = [d.abbr for d in self.dialects]
            filter_abbrs = [d.abbr for d in filter_dialects]
            inter = set.intersection(set(abbrs), set(filter_abbrs))
            dialects = [d for d in self.dialects if d.abbr in inter]
        else: #all dialects - no filtering
            dialects = self.dialects
        text = qApp.instance().pm.dialectStr(dialects)
        self.dialect_text_label.setText('{}   '.format(text))

    def edit(self):
        _all = qApp.instance().pm.project.dialects
        try:
            selected = [d.abbr for d in self.dialects]
        except:
            selected = ['']
        if len(selected) == 1 and selected[0] == '':
            selected = [qApp.instance().pm.project.getFocalDialect()]
        else:
            selected = [d for d in _all if d.abbr in selected]
        selected_ids = [d.id for d in selected]
        dlg = DialectDlg(self, _all, selected_ids, None, None)
        dlg.setWindowTitle(" ")
        def _move():
            pos = self.dialect_combo.pos() - QPoint((dlg.width() - self.dialect_combo.width()), - self.dialect_combo.height())
            pos = self.mapToGlobal(pos)
            dlg.move(pos)
        QTimer.singleShot(0, _move)
        qApp.processEvents()

        if dlg.exec_():
            dialects = dlg.selected_dialects()
            dialect_str = qApp.instance().pm.dialectStr(dialects)
            self.dialect_text_label.setText(dialect_str)
            self.dialect_combo.setText(dialect_str)
            self.dialects.clear()
            for d in dialects:
                self.dialects.append(d)

            if dialect_str != self.orig_str:
                self.amend_flag = True
            else:
                self.amend_flag = False
            self.setStyles()
            qApp.processEvents()
            self.parent().amended.emit()
        del dlg

    def onEnterEdit(self, _bool):
        self.editing = _bool
        self.dialect_combo.setVisible(_bool)
        self.dialect_text_label.setHidden(_bool) # holds the text
        if not self.dialect_text_label.text().strip():
            self.dialect_label.setVisible(_bool)
        if not _bool: #leaving
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.setToolTip(None)
            self.delete_flag = False
            self.amend_flag = False
        else: # entering
            self.setCursor(QCursor(Qt.PointingHandCursor))
            self.setToolTip(qApp.instance().translate('DialectWidget', 'Click to edit dialects'))

    ##!!@pyqtSlot(bool)
    def onAmendProjectDialects(self, _bool):
        # amend dialects for this widget after amending project dialects
        # this includes amending the choice to show or hid focal dialect, indicated by '_bool'
        focal_id = qApp.instance().pm.project.getFocalDialect().id
        all_ids = [d.id for d in qApp.instance().pm.project.dialects]

        # amend dialects
        dialect_ids = []
        for d in self.dialects:
            if d.id not in all_ids: #dialect deleted, replace with focal
                dialect_ids.append(focal_id)
            else:
                dialect_ids.append(d.id)
        dialect_ids = list(set(dialect_ids)) #in case more than one dicalect deleted, remove any duplicate focals
        self.dialects = [d for d in qApp.instance().pm.project.dialects if d.id in dialect_ids]

        # show/hide focal dialect, if used for this senses
        dialects = self.dialects
        if not _bool and focal_id in dialect_ids:
            dialects = [d for d in self.dialects if d.id != focal_id]
        text = qApp.instance().pm.dialectStr(dialects)

        old_text = self.dialect_text_label.text()
        new_text = '{}   '.format(text)
        self.dialect_text_label.setText(new_text)
        if self.dialect_combo.currentText().strip() == old_text.strip():
            idx = self.dialect_combo.currentIndex()
            self.dialect_combo.setItemText(idx, new_text)
        if text:
            self.dialect_label.show()
            if not self.editing:
                self.dialect_text_label.show()
        else:
            if not self.editing:
                self.dialect_label.hide()
            self.dialect_text_label.hide()

    ##!!@pyqtSlot(bool)
    def onDelete(self, _bool):
        self.delete_flag = _bool
        self.setStyles()
        qApp.processEvents()
        self.setDisabled(_bool)

    def setStyles(self):
        if self.dialect_combo.hasFocus():
            if self.delete_flag:
                self.dialect_combo.setStyleSheet("""border: 1px solid red; color: red; text-decoration: line-through""")
            elif self.amend_flag:
                self.dialect_combo.setStyleSheet("""border: 1px solid red; color: red""")
            else:
                self.dialect_combo.setStyleSheet("""border: 1px solid blue""")
        else:
            if self.delete_flag:
                self.dialect_combo.setStyleSheet("""color: red; text-decoration: line-through""")
            elif self.amend_flag:
                self.dialect_combo.setStyleSheet("""color: red""")
            else:
                self.dialect_combo.setStyleSheet(None)
        self.repaint()

class MyMultilineEdit(QTextEdit):
    change_keyboard = pyqtSignal(int)

    def __init__(self, parent, text, lang_id=None):
        super(MyMultilineEdit, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lang_id = lang_id
        if not lang_id:
            self.lang_id = 1
        self.orig_text = ''
        self.setReadOnly(True)
        self.setTabChangesFocus(True)
        self.setWordWrapMode(QTextOption.WordWrap)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setText(text)
        self.setAcceptDrops(False)
        self.ctrl_down = False
        self.change_keyboard.connect(qApp.instance().changeKeyboard)
        parent = self.parent()
        try:
            self.parent().parent().repaint_widgets.connect(self.onRepaint)
        except:
            pass

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def text(self):
        return self.toPlainText()

    def setOrigText(self, text):
        self.orig_text = text

    def setText(self, text):
        super(MyMultilineEdit, self).setText(text)
        def adjust_size():
            try:
                self.adjustSize()
            except:
                pass # wrapped C/C++ object deleted
        QTimer.singleShot(200, adjust_size)

    def showEvent(self, evt):
        self.sizeHint()
        super(MyMultilineEdit, self).showEvent(evt)

    def sizeHint(self):
        w = int(self.width())
        h = int(self.document().size().height())
        try:
            if self.parent().edit:
                h = h + 30
        except:
            pass
        #self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        return QSize(w, h)

    def resizeEvent(self, evt):
        self.adjustSize()
        super(MyMultilineEdit, self).resizeEvent(evt)

    def setFrame(self, _bool):
        #changes when entering/leaving edit mode
        if _bool:
            self.setFrameStyle(QFrame.StyledPanel)
        else:
            self.setFrameStyle(QFrame.NoFrame)
        QTimer.singleShot(200, self.repaint)

    def keyReleaseEvent(self, evt):
        if (sys.platform.startswith('darwin') or \
            sys.platform.startswith('linux')) and \
            isinstance(self.parent(), SenseWidget) and \
            self.parent().edit:
            if evt.key() == Qt.Key_Control:
                self.ctrl_down = False
        super(MyMultilineEdit, self).keyReleaseEvent(evt)

    def keyPressEvent(self, evt):
        if (sys.platform.startswith('darwin') or \
            sys.platform.startswith('linux')) and \
            isinstance(self.parent(), SenseWidget) and \
            self.parent().edit:
            if evt.key() == Qt.Key_Control:
                self.ctrl_down = True
            if evt.key() == Qt.Key_Up and self.ctrl_down:
                self.parent().parent().onMoveSenseUp()
            if evt.key() == Qt.Key_Down and self.ctrl_down:
                self.parent().parent().onMoveSenseDown()
        super(MyMultilineEdit, self).keyPressEvent(evt)

    def focusInEvent(self, evt):
        try:
            self.parent().editor = self
            if hasattr(self.parent(), '_selected'):
                self.parent()._selected.emit()
            if hasattr(self, 'deselect'):
                QTimer.singleShot(200, self.deselect)
            try:
                self.parent().parent().setCurrentEditor(self)
            except:
                pass #NO
            if self.parent().edit:
                self.change_keyboard.emit(self.lang_id)
        except:
            pass
        try:
            super(MyMultilineEdit, self).focusInEvent(evt)
        except:
            pass
#
    def focusOutEvent(self, evt):
        cursor = QTextCursor(self.document())  # Create a cursor on the document
        cursor.clearSelection() # Clear the selection
        self.setTextCursor(cursor) # Set the new cursor
        if sys.platform.startswith('linux'):
            self.change_keyboard.emit(None)
        super(MyMultilineEdit, self).focusOutEvent(evt)

    def mouseReleaseEvent(self, evt):
        if isinstance(self.parent(), SenseWidget) and \
            self.lang_id == qApp.instance().pm.search_lang_id:
                self.findField(evt.pos())
        return QTextEdit.mouseReleaseEvent(self, evt)

    def findField(self, pos):
        doc = self.document()
        text = doc.toRawText()
        fields = text.split(';')
        field = 0
        if len(fields) > 1:
            x = pos.x()
            fm = self.fontMetrics()
            doc_length = fm.width(text)
            if x <= doc_length:
                text = '{};'.format(fields[0])
                if x <= fm.width(text):
                    field = 0
                else:
                    for _field in fields[1:]:
                        text = '{}{};'.format(text, _field)
                        field += 1
                        if x <= fm.width(text):
                            break
        if self.parent().sense_field != field:
            self.parent().sense_field = field
        self.parent().sense_field_changed.emit()

class SentenceAddButton(QPushButton):
    def __init__(self, parent=None):
        super(SentenceAddButton, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.parent().repaint_widgets.connect(self.onRepaint)
        self.setToolTip(qApp.instance().translate('SentenceAddButton', "Click to add sentence"))

    def onRepaint(self):
        self.repaint()
        qApp.processEvents()

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QWidget.changeEvent(self, evt)

    def updateToolTips(self):
        self.setToolTip(qApp.instance().translate('SentenceAddButton', "Click to add sentence"))

class GramCatItemDelegate(QStyledItemDelegate):
    def __init__(self, orig_gram_cat, parent=None):
        super(GramCatItemDelegate, self).__init__(parent)
        if orig_gram_cat:
            self.orig_gram_cat = orig_gram_cat.name
        else:
            self.orig_gram_cat = None

    def paint(self, painter, option, index):
        painter.save()
        if index.data(Qt.DisplayRole) == self.orig_gram_cat:
            option.font.setBold(True)
            option.palette.setColor(QPalette.Text, Qt.blue)
        else:
            option.font.setBold(False)
            option.palette.setColor(QPalette.Text, Qt.black)

        super(GramCatItemDelegate, self).paint(painter, option, index)
        painter.restore()


# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()
