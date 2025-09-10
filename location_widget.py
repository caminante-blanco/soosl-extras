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
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import QRectF
from PyQt5.QtCore import QPointF
from PyQt5.QtCore import QTimer

from PyQt5.QtGui import QColor
#from PyQt5.QtGui import QCursor
#from PyQt5.QtGui import QFontMetrics
from PyQt5.QtGui import QBrush
from PyQt5.QtGui import QPolygonF
from PyQt5.QtGui import QPen
from PyQt5.QtGui import QPixmap

from PyQt5.QtWidgets import qApp
#from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtWidgets import QGraphicsPolygonItem
from PyQt5.QtWidgets import QGraphicsEllipseItem
#from PyQt5.QtWidgets import QStackedWidget

from PyQt5.QtSvg import QGraphicsSvgItem

class LocationView(QGraphicsView):
    def __init__(self, parent=None, searching=False):
        super(LocationView, self).__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.scene = LocationScene(self, searching)
        if searching:
            self.setEditable(True)
        self.setScene(self.scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scene.add_head.connect(self.onAddHead)
        self.scene.remove_head.connect(self.onRemoveHead)
        self.setStyleSheet("""background: White""")

    def onLocationRemoved(self, code):
        self.scene.deselectItem(code)
        self.scene.item_selected.emit(code, False)

    def onLocationItemClicked(self, code):
        # when a location item is clicked in a connected component_drop_widget list;
        # used to highlight item in location widget
        self.scene.highLiteItem(code)

    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.updateToolTips()
        else:
            QGraphicsView.changeEvent(self, evt)

    def updateToolTips(self):
        for item in self.scene.items():
            if item.code != '0':
                tooltip = self.scene.getTooltip(item.code)
                item.setToolTip(tooltip)

    def getSignData(self):
        return {"componentCodes": self.getSelectedCodes()}

    #@property
    def dirty(self):
        orig_codes = qApp.instance().pm.get_location_codes(qApp.instance().pm.sign)
        orig_codes.sort()
        selected = self.getSelectedCodes()
        selected.sort()
        if orig_codes != selected:
            return True
        return False

    ##!!@pyqtSlot(list)
    def filterByDialects(self, dialects):
        self.scene.filterByDialects(dialects)

    def getSelectedCodes(self):
        return self.scene.getSelectedCodes()

    def resizeEvent(self, event):
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    ##!!@pyqtSlot()
    def onAddHead(self):
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    ##!!@pyqtSlot()
    def onRemoveHead(self):
        self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    ##!!@pyqtSlot(bool)
    def onProjectOpen(self, _bool):
        self.scene.onProjectOpen(_bool)

    ##!!@pyqtSlot()
    def onProjectClosed(self):
        self.scene.clearOnClose()
        if qApp.hasPendingEvents():
            qApp.processEvents()

    ##!!@pyqtSlot(bool)
    def onDeleteSign(self, _bool):
        self.setDisabled(_bool)
        color = QColor(Qt.white)
        if _bool:
            self.setStyleSheet("""background: {}""".format(color))
        else:
            self.setStyleSheet(None)

    ##!!@pyqtSlot()
    def enterEditingMode(self):
        self.scene.enterEditingMode()
        self.updateToolTips() # any hidden items now shown won't have been updated by any language change

    ##!!@pyqtSlot()
    def leaveEditingMode(self):
        self.scene.leaveEditingMode()
        self.setStyleSheet(None)
        self.setEnabled(True)

    def setEditable(self, _bool):
        self.scene.setEditable(_bool)

    def clearLocations(self):
        """unselect all visible locations
        """
        if qApp.hasPendingEvents():
            qApp.processEvents()
        self.scene.clear()
        if qApp.hasPendingEvents():
            qApp.processEvents()

    def showCount(self, bool):
        pass

    def paintItem(self, painter, item):
        c = item.count()
        code = item.code
        search = self.scene.searching
        edit = self.scene.editing
        normal = (not search and not edit)
        item.show()
        text = ''
        if c and not normal:
            text = str(c)
        font = painter.font()
        font.setPixelSize(6)
        painter.setFont(font)
        text_color = QColor(Qt.blue)
        if item.brush() == item.select_brush:
            text_color = QColor(Qt.white)
        adjustments = [-5.0, 0.0, 5.0, 0.0] #[x1, y1, x2, y2] #make rect a little wider to accommodate larger counts
        # ellipses
        if code == '540': #outer elbow
            text_color = QColor(Qt.blue) #count located outside of ellipse
            adjustments = [-6.0, 10.0, 4.0, 10.0]
        elif code == '568': #shoulder; strong side
            adjustments = [-4.0, 0.0, -2.0, 0.0]
        elif code == '560': #shoulder; weak side
            adjustments = [3.0, 0.0, 6.0, 0.0]
        elif code == '680': #back of head
            adjustments = [-5.0, 0.0, 5.0, -83.0]
        elif code == '600': #lips
            adjustments = [-5.0, -1.0, 5.0, -21.0]
        # polygons
        elif code in ['650', '658']: #eyebrows
            text_color = QColor(Qt.blue) # count set outside of polygon, with a white background
            adjustments = [0.0, -8.0, 0.0, -8.0]
        elif code == '548': #upper arm
            adjustments = [-7.0, 4.0, 4.0, 4.0]
        elif code == '530': #lower arm
            adjustments = [-10.0, -10.0, 2.0, -10.0]
        elif code == '618': #nose
            adjustments = [-5.0, 5.0, 5.0, 5.0]
        elif code in ['5c2', '5c4']: #sides of neck
            adjustments = [-5.0, 3.0, 5.0, 3.0]
        rectf = item.boundingRect().adjusted(*adjustments)
        painter.setPen(text_color)
        painter.drawText(rectf, Qt.AlignCenter, text)
        # elif code != '0':
        #     item.hide()

class SVG(QGraphicsSvgItem):
    def __init__(self, filename):
        super(SVG, self).__init__(filename)
        self.descript = "SVG"
        self.code = '0'
        self.selected = True #keep selected always so item is included in selected list

    def setSelected(self, bool):
        pass #nothing to do - always selected - see __init__ above

class Ellipse(QGraphicsEllipseItem):
    def __init__(self, code, descript, rectF, posF=QPointF(0, 0)):
        super(Ellipse, self).__init__(rectF, None)
        self.code = code
        self.descript = descript
        self.normal_brush = None
        self.hover_brush = None
        self.select_brush = None
        self.selected = False
        self.setOpacity(1.0)
        self.setPos(posF)
        self.setAcceptHoverEvents(True)
        tooltip = self.descript
        self.setToolTip(tooltip)
        self.setPen(QPen(QColor("grey")))

    def paint(self, painter, option, widget):
        super(Ellipse, self).paint(painter, option, widget)
        widget.parent().paintItem(painter, self)

    def count(self):
        """return count of how many signs use this item
        """
        if self.scene():
            return self.scene().signCount(self.code)
        return 0

    def setSelected(self, bool, deselect_brush=None):
        if not deselect_brush:
            deselect_brush = self.normal_brush
        if bool:
            self.selected = True
            try:
                self.setBrush(self.select_brush)
            except:
                pass
        else:
            self.selected = False
            try:
                self.setBrush(deselect_brush)
            except:
                pass

    def mousePressEvent(self, event):
        if self.select_brush and self.hover_brush: #'blank' won't have these
            if event.button() == 1 and not self.selected:
                if self.descript == 'Head':
                    self.scene().addHeadItems()
                self.setSelected(True)
                if self.code:
                    self.scene().item_selected.emit(self.code, True)
            elif event.button() == 2 and self.selected: #right button
                if self.descript == 'Head':
                    self.scene().removeHeadItems()
                self.setSelected(False, self.hover_brush) #mouse should still be 'hovering' over item
                if self.code:
                    self.scene().item_selected.emit(self.code, False)

    def hoverEnterEvent(self, event):
        if (self.selected or
            (self.code == '0' and self.descript != 'Head')):
            pass
        else:
            self.setBrush(self.hover_brush)

    def hoverLeaveEvent(self, event):
        if (self.selected or
            (self.code == '0' and self.descript != 'Head')):
            pass
        else:
            self.setBrush(self.normal_brush)

class Polygon(QGraphicsPolygonItem):
    def __init__(self, code, descript, qpolygonF, posF=QPointF(0, 0)):
        QGraphicsPolygonItem.__init__(self, qpolygonF, None)
        self.code = code
        self.descript = descript
        self.normal_brush = None
        self.hover_brush = None
        self.select_brush = None
        self.selected = False
        self.setOpacity(1.0)
        self.setPos(posF)
        self.setAcceptHoverEvents(True)
        self.setToolTip(self.descript)
        self.setPen(QPen(QColor("grey")))

    def paint(self, painter, option, widget):
        super(Polygon, self).paint(painter, option, widget)
        widget.parent().paintItem(painter, self)

    def count(self):
        """return count of how many signs use this item
        """
        if self.scene():
            return self.scene().signCount(self.code)
        return 0

    def setSelected(self, bool, deselect_brush=None):
        if not deselect_brush:
            deselect_brush = self.normal_brush
        if bool:
            self.selected = True
            try:
                self.setBrush(self.select_brush)
            except:
                pass #may not have a select brush as in the case of descript = 'Blank'
        else:
            self.selected = False
            self.setBrush(deselect_brush)

    def mousePressEvent(self, event):
        if self.select_brush and self.hover_brush: #'blank' won't have these
                if event.button() == 1 and not self.selected:
                    self.setSelected(True)
                    if self.code:
                        self.scene().item_selected.emit(self.code, True)
                elif event.button() == 2 and self.selected: #right button
                    self.setSelected(False, self.hover_brush) #mouse still hovering over item
                    if self.code:
                        self.scene().item_selected.emit(self.code, False)

    def hoverEnterEvent(self, event):
        if not self.selected and self.code != '0':
            self.setBrush(self.hover_brush)

    def hoverLeaveEvent(self, event):
        if not self.selected and self.code != '0':
            self.setBrush(self.normal_brush)

class LocationScene(QGraphicsScene):
    item_selected = pyqtSignal(str, bool)
    add_head = pyqtSignal()
    remove_head = pyqtSignal()

    def __init__(self, parent=None, searching=False):
        self.pm = qApp.instance().pm #Sign Collection
        self.dialect_filter = []
        #brush for normal painting
        self.brush = QBrush(QColor("light grey"))
        #brushes for hovering
        self.hover_brush_spatial = QBrush(QColor("cyan"))
        self.hover_brush_contact = QBrush(QColor("pink"))
        #brushes for selection
        self.select_brush_spatial = QBrush(QColor("blue"))
        self.select_brush_contact = QBrush(QColor("red"))

        super(LocationScene, self).__init__(parent)
        behind_body = [loc for loc in self.__body_locations if 'behind' in loc[1]]
        front_body = [loc for loc in self.__body_locations if 'behind' not in loc[1]]
        behind_head = [loc for loc in self.__head_locations if 'behind' in loc[1]]
        front_head = [loc for loc in self.__head_locations if 'behind' not in loc[1]]

        #create body items
        self.behind_body_items = self.getItems(behind_body)
        self.body_svg = SVG(":/body.svg")
        self.front_body_items = self.getItems(front_body)
        self.body_items = self.behind_body_items + [self.body_svg] + self.front_body_items

        #create head items
        self.behind_head_items = self.getItems(behind_head)
        self.head_svg = SVG(":/head.svg")
        self.front_head_items = self.getItems(front_head)
        self.head_items = self.behind_head_items + [self.head_svg] + self.front_head_items
        self.editing = False
        self.editable = False
        self.searching = searching
        if searching:
            self.editable = True
        self.dialect_filters = []

        self.addItem(self.body_svg)
        #self.code_locations() #only used in development to assign codes to items

        self.item_selected.connect(self.onItemSelected)

        self.search_codes = []
        self.highlited_item = None
        self.highlite_brush = QBrush(QColor("yellow"))
        self.highlited_item_old_brush = QBrush()

    def highLiteItem(self, code):
        if code:
            items = []
            items.extend(self.front_head_items)
            items.extend(self.behind_head_items)
            items.extend(self.front_body_items)
            items.extend(self.behind_body_items)
            items = [item for item in items if item.code == code]
            if items:
                item = items[0]
                if self.highlited_item:
                    self.highlited_item.setBrush(self.highlited_item_old_brush)
                self.highlited_item = item
                self.highlited_item_old_brush = item.brush()
                self.highlited_item.setBrush(self.highlite_brush)
        else:
            if self.highlited_item:
                self.highlited_item.setBrush(self.highlited_item_old_brush)
            self.highlited_item = None
            self.highlited_item_old_brush = QBrush()


    def setEditable(self, _bool):
        self.editable = _bool

    def mousePressEvent(self, *args, **kwargs):
        if self.editable:
            return QGraphicsScene.mousePressEvent(self, *args, **kwargs)

    def mouseReleaseEvent(self, *args, **kwargs):
        if self.editable:
            return QGraphicsScene.mouseReleaseEvent(self, *args, **kwargs)

    def mouseDoubleClickEvent(self, *args, **kwargs):
        if self.editable:
            return QGraphicsScene.mouseDoubleClickEvent(self, *args, **kwargs)

    def filterByDialects(self, dialects):
        if not dialects or len(dialects) == len(self.pm.getAllDialects()):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects
        self.setupScene()

    def signCount(self, code):
        """return count of how many signs use this item
        """
        try:
            parent = self.parent().parent().parent().parent()
        except:
            pass
        else:
            if type(parent).__name__ == 'SearchDlg':
                return self.pm.signCountByCode2(code, self.dialect_filter, parent.signs_found)
        return self.pm.signCountByCode2(code, self.dialect_filter)

    def onProjectOpen(self, _bool):
        pass # when dictionary opens, scene will be setup when model resets on first sign load

    def setupScene(self):
        self.removeItems()
        self.addBodyItems()
        self.addHeadItems()

    ##!!@pyqtSlot(str)
    def deselectItem(self, code):
        items = self.body_items + self.head_items
        for item in items:
            if item.code == code:
                item.setSelected(False)
                if item is self.highlited_item:
                    self.highlited_item = None
                    self.highlited_item_old_brush = QBrush()
                break

    #!!@pyqtSlot(str, bool)
    def onItemSelected(self, code, _bool):
        if not self.searching:
            sign = qApp.instance().pm.sign
            if self.editable and sign:
                orig_codes = qApp.instance().pm.get_location_codes(sign)
                orig_codes.sort()
                selected = self.parent().getSelectedCodes()
                selected.sort()
                qApp.instance().pm.onAmended()

    def getSelectedCodes(self):
        items = self.body_items + self.head_items
        codes = [item.code for item in items if item.selected and not item.code == '0']
        return codes

    def clear(self):
        """unselect all items
        """
        if self.editable:
            items = self.body_items + self.head_items
            for item in items:
                try:
                    item.setBrush(item.normal_brush)
                except:
                    pass
                if item.selected:
                    item.setSelected(False)
                    #if editing, need to also amend sign's 'component_amends' list
                    #the following signal should do this
                    if item.code != '0':
                        self.item_selected.emit(item.code, False)

        self.highlited_item = None
        self.highlited_item_old_brush = QBrush()

    def clearOnClose(self):
        """unselect all items
        """
        items = self.body_items + self.head_items
        for item in items:
            try:
                item.setBrush(item.normal_brush)
            except:
                pass
            if item.selected:
                item.setSelected(False)
                #if editing, need to also amend sign's 'component_amends' list
                #the following signal should do this
                if item.code != '0':
                    self.item_selected.emit(item.code, False)

    def removeItems(self):
        """remove items from scene, but do not destroy
        """
        for item in self.items():
            self.removeItem(item)

    def getItems(self, locations):
        items = []
        for loc in locations:
            code, strings, data, pos = loc
            descript = strings[0]
            pos = QPointF(*pos)
            if 'ellipse' in strings:
                data = [data[0][0], data[0][1], data[1][0], data[1][1]]
                item = Ellipse(code, descript, QRectF(*data), pos)
            elif 'circle' in strings:
                tpl, d = data
                data = [tpl[0], tpl[1], d, d]
                item = Ellipse(code, descript, QRectF(*data), pos)
            elif 'polygon' in strings:
                data = [QPointF(i[0], i[1]) for i in data]
                item = Polygon(code, descript, QPolygonF(data), pos)
            elif 'rectangle' in strings:
                xy, wh = data
                x, y = xy
                w, h = wh
                data = [QPointF(x, y), QPointF(x + w, y), QPointF(x + w, y + h), QPointF(x, y + h)]
                item = Polygon(code, descript, QPolygonF(data), pos)

            if 'blank' in strings:
                item.normal_brush = QBrush(QColor("grey"))
                item.setBrush(item.normal_brush)
                item.setToolTip("")
            else:
                #descript = strings[0]
                #item.setToolTip(descript)
                if 'contact' in strings:
                    item.normal_brush = self.brush
                    item.setBrush(item.normal_brush)
                    item.hover_brush = self.hover_brush_contact
                    item.select_brush = self.select_brush_contact
                elif 'spatial' in strings:
                    item.normal_brush = self.brush
                    item.setBrush(item.normal_brush)
                    item.hover_brush = self.hover_brush_spatial
                    item.select_brush = self.select_brush_spatial

            items.append(item)
        return items

    def enterEditingMode(self):
        if not self.editing:
            self.editing = True
            self.editable = True
            self.onModelReset(self.pm.sign)

    def leaveEditingMode(self):
        if self.editing:
            self.editing = False
            self.editable = False
            self.onModelReset(self.pm.sign)

    def onModelReset(self, sign):
        self.removeItems()
        if not sign:
            # self.selectHeadItems([]) #if no head codes, this will de-select all head items
            # self.selectBodyItems([], include_head=True)
            # self.addBodyItems()
            # self.addHeadItems()
            return
        codes = self.pm.get_location_codes(sign)
        body_codes = [c for c in codes if eval("0x{}".format(c)) < eval("0x5f8")] #see bottom of page for codes
        head_codes = [c for c in codes if eval("0x{}".format(c)) >= eval("0x5f8")] #see bottom of page for codes
        self.selectHeadItems(head_codes) #if no head codes, this will de-select all head items
        self.selectBodyItems(body_codes, include_head=True)
        self.addHeadItems()
        self.addBodyItems()

    def addBodyItems(self):
        self.__addItems(self.body_items)

    def addHeadItems(self):
        self.__addItems(self.head_items)
        self.add_head.emit()
        descriptions = [i.descript for i in self.head_items]
        selected = [i.descript for i in self.head_items if i.selected]

    def __addItems(self, items):
        descriptions = [i.descript for i in items]
        for item in items:
            count = self.signCount(item.code)
            comp_codes = []
            sign = qApp.instance().pm.sign
            if sign:
                try:
                    comp_codes = sign.component_codes
                except:
                    comp_codes = sign.get('componentCodes', [])
            if not self.editing and self.dialect_filter and not count:
                if (item.descript == 'SVG' or
                    item.descript == 'Head' or
                    (item.descript == 'L_Blank' and 'Lips' in descriptions) or
                    (item.descript == 'L_Blank' and 'Tongue' in descriptions)):
                        self.addItem(item)
            elif (item.selected or
                self.editing or
                self.searching or
                item.descript == 'Head' or
                (item.descript == 'L_Blank' and 'Lips' in descriptions) or
                (item.descript == 'L_Blank' and 'Tongue' in descriptions) or
                (not self.editing and item.code in comp_codes)):
                self.addItem(item)

    def removeHeadItems(self):
        for item in self.head_items:
            self.removeItem(item)
            if item.selected:
                item.setSelected(False)
                if eval(item.code):
                    self.item_selected.emit(item.code, False)
        self.remove_head.emit()

    def selectBodyItems(self, body_item_codes, include_head=False):
        items = self.behind_body_items + [self.body_svg] + self.front_body_items
        for item in items:
            if (item.code in body_item_codes or
               (item.descript == 'Head' and include_head) or
               item.descript == 'SVG'):
                item.setSelected(True)
            else:
                item.setSelected(False)

    def selectHeadItems(self, head_codes):
        items = self.behind_head_items + [self.head_svg] + self.front_head_items
        for item in items:
            if (item.code in head_codes or
               item.descript == 'SVG' or
               (item.descript == 'L_Blank' and '600' in head_codes) or #Lips blank
               (item.descript == 'BOH_Blank' and '680' in head_codes)): #Back-of-Head blank
                item.setSelected(True)
            else:
                item.setSelected(False)

    def location_codes(self):
        codes = []
        all_locations = self.__body_locations + self.__head_locations
        for loc in all_locations:
            code, strings, data, position = loc
            descript = strings[0]
            if code != '0':
                codes.append(code)
        return codes

    def getTooltip(self, code):
        if code != '0':
            locations = [l for l in self.__body_locations if l[0] == code]
            if not locations:
                locations = [l for l in self.__head_locations if l[0] == code]
            if locations:
                return locations[0][1][0]
        return ''

    @property
    def __body_locations(self):
        return [

        ('500', [qApp.instance().translate('LocationScene', 'Weak hand'), 'contact', 'circle'],
        [(25, -225), 30],
        [180.7, 460.2]),

        ('520', [qApp.instance().translate('LocationScene', 'Wrist'), 'contact', 'circle'],
        [(200, -208), 12],
        [1.0, 434.0]),

        ('530', [qApp.instance().translate('LocationScene', 'Lower arm'), 'contact', 'polygon'],
        [(170, -198), (185, -201), (198, -172), (190, -169)],
        [7.0, 396.0]),

        ('538', [qApp.instance().translate('LocationScene', 'Inner elbow'), 'contact', 'circle'],
        [(172, -156), 16],
        [-1.0, 334.0]),

        ('540', [qApp.instance().translate('LocationScene', 'Outer elbow'), 'contact', 'circle', 'behind'],
        [(163, -166), 11],
        [-3.0, 354]),

        ('548', [qApp.instance().translate('LocationScene', 'Upper arm'), 'contact', 'polygon'],
        [(154, -130), (162, -161), (172, -112), (159, -108)],
        [9.0, 286.0]),

        ('550', [qApp.instance().translate('LocationScene', 'Armpit, weak side'), 'contact', 'ellipse'],
        [(143, -130), (12, 18)],
        [9.0, 267.0]),

        ('558', [qApp.instance().translate('LocationScene', 'Armpit, strong side'), 'contact', 'ellipse'],
        [(0.0, 0.0), (12, 18)],
        [75.0, 138.0]),

        ('560', [qApp.instance().translate('LocationScene', 'Shoulder, weak side'), 'contact', 'circle'],
        [(154, -99), 23],
        [-8.0, 211.0]),

        ('568', [qApp.instance().translate('LocationScene', 'Shoulder, strong side'), 'contact', 'circle'],
        [(0.0, 0.0), 23],
        [67.0, 113.0]),

        ('570', [qApp.instance().translate('LocationScene', 'Top of shoulder, weak side'), 'contact', 'ellipse'],
        [(124, -88), (30, 8)],
        [13.0, 190.0]),

        ('578', [qApp.instance().translate('LocationScene', 'Top of shoulder, strong side'), 'contact', 'ellipse'],
        [(0.0, 0.0), (30, 8)],
        [67.0, 103.0]),

        ('580', [qApp.instance().translate('LocationScene', 'Above shoulder, weak side'), 'spatial', 'ellipse'],
        [(130, -78), (28, 8)],
        [9.0, 168.0]),

        ('588', [qApp.instance().translate('LocationScene', 'Above shoulder, strong side'), 'spatial', 'ellipse'],
        [(0.0, 0.0), (28, 8)],
        [66.0, 91.0]),

        ('590', [qApp.instance().translate('LocationScene', 'Hip, weak side'), 'contact', 'ellipse'],
        [(0, 0), (12, 45)],
        [147.0, 205.0]),

        ('598', [qApp.instance().translate('LocationScene', 'Hip, strong side'), 'contact', 'ellipse'],
        [(0, 0), (12, 45)],
        [81.0, 205.0]),

        ('5a0', [qApp.instance().translate('LocationScene', 'Lower torso'), 'contact', 'polygon'],
        [(83, -124), (80, -168), (147, -168), (144, -124)],
        [6.0, 321.0]),

        ('5a8', [qApp.instance().translate('LocationScene', 'Chest, strong side'), 'contact', 'polygon'],
        [(75, -123), (99, -123), (99, -83), (80, -83)],
        [7.0, 234.0]),

        ('5b0', [qApp.instance().translate('LocationScene', 'Chest (center)'), 'contact', 'polygon'],
        [(101, -123), (124, -123), (124, -83), (101, -83)],
        [7.0, 234.0]),

        ('5b8', [qApp.instance().translate('LocationScene', 'Chest, weak side'), 'contact', 'polygon'],
        [(126, -123), (150, -123), (145, -83), (126, -83)],
        [7.0, 234.0]),

        ('5c0', [qApp.instance().translate('LocationScene', 'Neck'), 'contact', 'rectangle'],
        #[(99, -81), (25, 10)],
        [(102, -81), (18, 10)],
        [7.0, 177.0]),

        ('5c2', [qApp.instance().translate('LocationScene', 'Side of neck, strong side'), 'contact', 'rectangle'],
        [(94, -83), (6, 12)],
        [7.0, 177.0]),
#
        ('5c4', [qApp.instance().translate('LocationScene', 'Side of neck, weak side'), 'contact', 'rectangle'],
        [(122, -83), (6, 12)],
        [7.0, 177.0]),

        ('5c8', [qApp.instance().translate('LocationScene', 'Low side of head, weak side'), 'spatial', 'ellipse'],
        [(140, -66), (10, 30)],
        [7.0, 123.0]),

        ('5d0', [qApp.instance().translate('LocationScene', 'Low side of head, strong side'), 'spatial', 'ellipse'],
        [(0.0, 0.0), (10, 30)],
        [77.0, 58.0]),

        ('5d8', [qApp.instance().translate('LocationScene', 'High side of head, weak side'), 'spatial', 'ellipse'],
        [(140, -34), (10, 30)],
        [7.0, 56.0]),

        ('5e0', [qApp.instance().translate('LocationScene', 'High side of head, strong side'), 'spatial', 'ellipse'],
        [(0.0, 0.0), (10, 30)],
        [77.0, 23.0]),

        ('5e8', [qApp.instance().translate('LocationScene', 'Above head'), 'spatial', 'ellipse'],
        [(86, 7), (48, 8)],
        [7.0, 9.0]),

        ('5f0', [qApp.instance().translate('LocationScene', 'Above front of head'), 'spatial', 'ellipse'],
        [(86, -1), (48, 8)],
        [7.0, 8.0]),

        ('5f4', [qApp.instance().translate('LocationScene', 'In front of head'), 'spatial', 'ellipse'],
        [(88, -63), (46, 60)], #(91, -63), (40, 55)]
        [6.0, 91.86])

        ]

    @property
    def __head_locations(self):
        return [

        ('5f8', [qApp.instance().translate('LocationScene', 'Chin'), 'contact', 'ellipse'],
        [(103, 33), (28, 15)],
        [144.0, 108.0]),

        ('600', [qApp.instance().translate('LocationScene', 'Lips'), 'contact', 'ellipse'],
        [(93.5, 51), (48, 26)],
        [146.0, 60.0]),

        ('0', ['L_Blank', 'blank', 'ellipse'],
        [(95, 55), (44, 16)],
        [147.0, 61.0]),

        ('608', [qApp.instance().translate('LocationScene', 'Teeth'), 'contact', 'polygon'],
        [(96, 66.3), (104, 62.85), (109, 62.06), (109, 66.3), (109, 62.06), (114, 61.65), (116.5, 61.6), (116.5, 66.3), (116.5, 61.6), (119, 61.75), (124, 62.06), (124, 66.3), (124, 62.06), (129, 62.95), (137, 66.3)],
        [147.0, 55.0]),

        ('610', [qApp.instance().translate('LocationScene', 'Tongue'), 'contact', 'ellipse'],
        [(104, 55), (28, 8)],
        [146.0, 70.0]),

        ('618', [qApp.instance().translate('LocationScene', 'Nose'), 'contact', 'polygon'],
        [(106, 115), (112, 95), (118, 95), (124, 115)],
        [145.0, -13.0]),

        ('620', [qApp.instance().translate('LocationScene', 'Cheek, weak side'), 'contact', 'circle'],
        [(144, 95), 25],
        [134.0, -7.0]),

        ('628', [qApp.instance().translate('LocationScene', 'Cheek, strong side'), 'contact', 'circle'],
        [(0.0, 0.0), 25],
        [220.0, 89.0]),

        ('630', [qApp.instance().translate('LocationScene', 'Ear, weak side'), 'contact', 'ellipse'],
        [(52, 91), (11, 20)],
        [259.0, -6.0]),

        ('638', [qApp.instance().translate('LocationScene', 'Ear, strong side'), 'contact', 'ellipse'],
        [(0.0, 0.0), (11, 20)],
        [203.0, 87.0]),

        ('640', [qApp.instance().translate('LocationScene', 'Eye, weak side'), 'contact', 'ellipse'],
        [(85.5, 114), (16, 11)],
        [187.0, -44.0]),

        ('648', [qApp.instance().translate('LocationScene', 'Eye, strong side'), 'contact', 'ellipse'],
        [(85.5, 114), (16, 11)],
        [146.0, -45.0]),

        ('650', [qApp.instance().translate('LocationScene', 'Eyebrow, weak side'), 'contact', 'polygon'],
        [(77, 131), (96, 131), (110, 138), (81, 134)],
        [190.0, -73.0]),

        ('658', [qApp.instance().translate('LocationScene', 'Eyebrow, strong side'), 'contact', 'polygon'],
        [(77, 138), (89, 135), (108, 134), (106, 131), (93, 130), (82, 133)],
        [147.0, -73.0]),

        ('660', [qApp.instance().translate('LocationScene', 'Temple, weak side'), 'contact', 'ellipse'],
        [(0.0, 0.0), (10, 30)],
        [302.0, 27.0]),

        ('668', [qApp.instance().translate('LocationScene', 'Temple, strong side'), 'contact', 'ellipse'],
        [(64, 148), (10, 30)],
        [147.0, -122.0]),

        ('670', [qApp.instance().translate('LocationScene', 'Forehead'), 'contact', 'ellipse'],
        [(79, 152), (75, 27)],
        [145.0, -131.0]),

        ('678', [qApp.instance().translate('LocationScene', 'Top of head'), 'contact', 'ellipse'],
        [(79, 178), (75, 12)],
        [144.0, -171.0]),

        ('680', [qApp.instance().translate('LocationScene', 'Back of head'), 'contact', 'ellipse', 'behind'],
        [(15, 135), (136, 96)],
        [178.0, -141.0]),

        #('682', ['Hair', ????
        ##NOTE: Implement Hair location

        ('688', [qApp.instance().translate('LocationScene', 'Jaw middle, weak side'), 'contact', 'circle'],
        [(144, 135), 15],
        [135.4, 0.0]),

        ('690', [qApp.instance().translate('LocationScene', 'Jaw middle, strong side'), 'contact', 'circle'],
        [(2.5, 42.0), 15],
        [226.9, 94.1]),

        ('698', [qApp.instance().translate('LocationScene', 'Jaw back, weak side'), 'contact', 'circle'],
        [(52, 91), 13],
        [243.6, 32.2]),

        ('6a0', [qApp.instance().translate('LocationScene', 'Jaw back, strong side'), 'contact', 'circle'],
        [(0.0, 0.0), 13],
        [216.6, 123.8]),

        ##NOTE: currently (0.8.7 03/10/2016) greatest location code could be 'fff'

        #a blank is required over the back of head region to block events, otherwise the back region
        #receives hover events when hovering over front of head; the head svg 'could' block these also,
        #but then the head svg would block events to the body svg
        ('0', ['BOH_Blank', 'blank', 'polygon', 'behind'],
        [(15, 135), (124, 135), (124, 90), (115, 75), (95, 65), (40, 65), (21, 76), (15, 95)],
        [192.9661016949152, -55.932203389830505])

        ]
