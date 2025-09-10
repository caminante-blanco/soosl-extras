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
import unicodedata as UD
from pyuca import Collator
import sys
import re
import itertools
from PyQt5.Qt import QPalette
chain = itertools.chain
from operator import itemgetter

from PyQt5.QtCore import Qt, QVariant, QTimer, QEvent
from PyQt5.QtCore import QSize
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtCore import QAbstractTableModel, QModelIndex

#from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtGui import QFontMetrics

from PyQt5.QtWidgets import QVBoxLayout, QStyle, QWidget, QHBoxLayout
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QTableView
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QAbstractItemView

from project import Sign
from project_manager import ProjectManager

UNKNOWN_GLOSS = '###'

class FinderList(QWidget):
    font_size_change = pyqtSignal()
    loseTabFocus = pyqtSignal()
    has_unglossed_signs = pyqtSignal(bool)
    show_rows = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        super(FinderList, self).__init__(parent)
        self.settings = qApp.instance().getSettings()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dialect_filter = []
        self.dialect_sort = 0
        self.text_filter = None
        self.search_filter = []
        
        self.selected_sign_id = 0
        self.selected_sense = 0
        self.selected_field = 0
               
        self.current_font_size = 12
        self.current_font_family = None           
        self.editing = False
        self.finder_list = FinderTableView(self)
        self.finder_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.finder_list.horizontalHeader().sectionResized.connect(self.onHeaderResized) 
        self.finder_list.horizontalHeader().sectionPressed.connect(self.onHeaderPressed)
        self.search_box = FinderSearchBox(self)
        self.search_box.setEnabled(False)  
        #self.search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)      
        self.search_box.textChanged.connect(self.onFilterByText)
        self.clear_btn = QPushButton(QIcon(':/close.png'), '')
        self.clear_btn.setFlat(True)
        self.clear_btn.setFixedWidth(24)
        self.clear_btn.hide()
        self.search_box.show_clear_btn.connect(self.clear_btn.show)
        self.search_box.hide_clear_btn.connect(self.clear_btn.hide)
        self.clear_btn.pressed.connect(self.search_box.clear)
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(self.search_box)
        hlayout.addWidget(self.clear_btn)
        
        self.dialect_col_width = 80
        
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(3, 1, 1, 1)
        layout.addLayout(hlayout)
        layout.addWidget(self.finder_list)
        
        self.setLayout(layout)
        self.setTabOrder(self.search_box, self.finder_list)
        
    def model(self):
        return self.finder_list.model()

    def defaultSettings(self):
        self.finder_list.defaultSettings()
                
    #@pyqtSlot()      
    def onClearSearch(self):
        self.setSearchFilter([])
        
    def refreshFilter(self):
        pass ##NOTE: needed?

    def onFilterByText(self, text):
        self.text_filter = text
        if not hasattr(self, 'textFilterTimer'):
            self.textFilterTimer = QTimer(self)
            self.textFilterTimer.timeout.connect(self.setupList)
            self.textFilterTimer.start(300)
        else:
            self.textFilterTimer.start(300)
        
    def onSenseChanged(self):
        current_sign = qApp.instance().pm.sign
        lang_id = qApp.instance().pm.search_lang_id
        sense_id = current_sign.current_sense_id
        sense_field = current_sign.current_sense_field
        senses = current_sign.senses
        current_senses = [s for s in senses if s.id == sense_id]
        if current_senses:
            current_sense = current_senses[0]
            gloss_texts = [t.text for t in current_sense.gloss_texts if t.lang_id == lang_id]
            if gloss_texts:
                gloss_text = gloss_texts[0]
                text = [t.strip() for t in gloss_text.split(';')][sense_field]
                if self.text_filter and not text.startswith(self.text_filter): 
                    pass # crash may result from attempt to select gloss not in filtered list
                else:
                    self.selectCurrentGloss()
        
    def onShowFocalDialect(self, _bool):
        self.refreshList()
        
    def refreshList(self):
        self.finder_list.model().dataChanged.emit(QModelIndex(), QModelIndex())
        
    #@pyqtSlot(int, int, int)
    def onHeaderResized(self, a, b, c):
        if hasattr(self, 'finder_list') and self.finder_list:
            header = self.finder_list.horizontalHeader()
            if a == 0:
                qApp.instance().getSettings().setValue('GlossColWidth', c)
        self.update()
                    
    #@pyqtSlot(int)
    def onHeaderPressed(self, section):
        selected_row = 0        
        if section == 0:
            self.sortBySense()
        elif section == 1:
            self.sortByDialect()
        self.refreshList()
        self.finder_list.setupHeader()
        self.finder_list.horizontalHeader().setEnabled(True)
        
        selected_text = [t for t in self.sign_texts if t.get('sense_id', None) and t.get('sense_id') == self.selected_sense and t.get('sense_field', 0) == self.selected_field]
        if selected_text:
            selected_row = self.sign_texts.index(selected_text[0])
        
        idx = self.finder_list.model().index(selected_row, 0)
        self.finder_list.setCurrentIndex(idx)
        self.finder_list.selectRow(idx.row()) 
        self.selectGlossAtIndex(idx) 
        self.update()
            
    def sortBySense(self):
        if self.dialect_sort:
            c = Collator() # pyuca
            it = itemgetter('text')
            self.sign_texts.sort(key=lambda x: c.sort_key(self.lstripPunct(it(x)).lower()))
            self.dialect_sort = 0
        else:
            self.sign_texts.reverse()
        
    def sortByDialect(self):
        if not self.dialect_sort:
            c = Collator() # pyuca
            self.sign_texts.sort(key=lambda x: c.sort_key(qApp.instance().pm.dialectStr(x.get('dialect_ids', [])).lower()))
            self.dialect_sort = 1  
        else:
            self.sign_texts.reverse()       
    
    #@pyqtSlot(int, int)
    def onFontSizeChange(self, lang_id, _int):
        if qApp.instance().pm.search_lang_id == lang_id:
            self.current_font_size = _int
            if self.finder_list:
                self.finder_list.resizeRowsToContents()
            
    def onFontFamilyChange(self, lang_id, family_name):
        if qApp.instance().pm.search_lang_id == lang_id:
            self.current_font_family = family_name
            self.search_box.setFontFamily(family_name)
            if self.finder_list:
                self.finder_list.resizeRowsToContents()
                
    def showEmptyGlosses(self, _bool):
        unglossed = [t for t in self.sign_texts if not t.get('text', '')]
        unglossed_rows = list(map(lambda x: self.sign_texts.index(x), unglossed))
        indexes = self.finder_list.selectedIndexes()
        if indexes:
            selected_row = indexes[0].row()
            if selected_row in unglossed_rows:
                qApp.instance().pm.findSignById(-1, -1, -1)
                self.finder_list.clearSelection()
        for row in unglossed_rows:
            if _bool:
                self.finder_list.showRow(row)
            else:
                self.finder_list.hideRow(row)
                
    def setSearchFilter(self, sign_ids):
        """setup preview listing based on component search from search dialog"""
        self.search_filter = sign_ids 
        self.setupList()   
        if self.search_filter and self.finder_list:
            self.finder_list.setAlternatingRowColors(True)
        elif self.finder_list:
            self.finder_list.setAlternatingRowColors(False)        
        if sign_ids and sign_ids != [-999] and not self.finder_list.model().rowCount():
            short = qApp.instance().translate('FinderList', 'Clear Text Box')
            long = qApp.instance().translate('FinderList', 'Clear text box above finder list to view glosses for this search.')
            qApp.instance().pm.show_info.emit(short, long)
    
    #@pyqtSlot(list)              
    def onSignsFound(self, signs):
        if qApp.instance().searchType == 'gloss' and signs:
            sign = signs[0]
            if sign and sign.new:
                self.enterEditingMode()
        elif qApp.instance().searchType == 'comp':# and signs:
            sign_ids = [s.id for s in signs if s]
            if not sign_ids:
                sign_ids = [-999] # no such sign id so will clear sign list
            self.setSearchFilter(sign_ids)     

#    https://docs.python.org/2/library/itertools.html
    def flatten(self, listOfLists):
        "Flatten one level of nesting"
        return chain.from_iterable(listOfLists)
    
    def lstripPunct(self, _string): #left strip punctuation
        while _string and UD.category(_string[0]).startswith('P'):
            _string = _string[1:]
        return _string

    def lstripNonAlpha(self, _string): #left strip non alphabetic characters
        strings = _string.split(' ', 1) # 2 list items at most
        if len(strings) > 1 and strings[0][0].isnumeric():
            _string = strings[1]
        while _string and not _string[0].isalpha():
            _string = _string[1:]
        return _string
    
    def getSignTextList(self, project=None):
        if not project:
            project = qApp.instance().pm.project
        def splitGlosses(gloss):
            glosses = gloss.get('text', '').split(';')
            if len(glosses) > 1:
                return [{'text': x.strip(), 'dialect_ids': gloss.get('dialect_ids', []), 'sign_id': gloss.get('sign_id', 0), 'sense_id': gloss.get('sense_id'), 'sense_field': glosses.index(x)} for x in glosses]
            gloss['text'] = gloss.get('text', '').strip()
            gloss['sense_id'] = gloss.get('sense_id')
            gloss['sense_field'] = 0
            return [gloss]
        
        if project:
            lang_id = qApp.instance().pm.search_lang_id
            if self.editing:
                # show glosses for current sign only
                signs = [qApp.instance().pm.sign]
                if signs:
                    sign_texts = self.flatten([[splitGlosses({'text': t.text, 'dialect_ids': t.dialect_ids, 'sign_id': t.sign_id, 'sense_id': t.sense_id})
                        for t in self.flatten(map(lambda x: x.gloss_texts, sign.senses)) if t.lang_id == lang_id] for sign in signs if sign])
                    sign_texts = self.flatten(sign_texts)
                    return list(sign_texts)
                return []

            sign_texts = self.flatten([[splitGlosses({'text': t.text, 'dialect_ids': t.dialect_ids, 'sign_id': t.sign_id, 'sense_id': t.sense_id}) 
                for t in self.flatten(map(lambda x: x.gloss_texts, sign.senses)) 
                # apply any dialect filter            
                if not t or t.lang_id == lang_id and set(t.dialect_ids).intersection(set(project.selected_dialect_ids))] for sign in project.signs
                # apply any search (parameters) filter
                if not self.search_filter or self.search_filter and sign.id in self.search_filter
                ])
            sign_texts = self.flatten(sign_texts)
            
            # apply text filter, if any
            if self.text_filter:
                it = itemgetter('text')
                # searching for punctuation or numbers
                if UD.category(self.text_filter[0]).startswith('P') or \
                    self.text_filter[0].isnumeric():
                        sign_texts = [t for t in sign_texts if it(t).lower().startswith(self.text_filter.lower())]
                #ignore punctuation & numbers
                else: 
                    sign_texts = [t for t in sign_texts if self.lstripNonAlpha(self.lstripPunct(it(t))).strip().lower().startswith(self.text_filter.lower())]

            # add in any empties
            sign_texts = list(sign_texts)
            for sign in project.signs:
                for sense in sign.senses:
                    if not sense.gloss_texts:
                        sign_text = {'text': '', 'dialect_ids': sense.dialect_ids, 'sign_id': sign.id, 'sense_id': sense.id, 'sense_field': 0}
                        sign_texts.append(sign_text)                    

            if not sign_texts:
                return []

            c = Collator() # pyuca
            it = itemgetter('text')
            #qApp.instance().logRunning('start sorting')
            sign_texts = sorted(sign_texts, key=lambda st: self.sorter(self.lstripPunct(it(st)).lower(), c))
            #qApp.instance().logRunning('stop sorting')
            #sign_texts = sorted(sign_texts, key=lambda st: self.lstripPunct(it(st)).lower())
            return sign_texts
        return []

    # ## https://stackoverflow.com/questions/64478179/how-to-sort-list-of-string-with-number-by-grammar-and-number-sequence
    def sorter(self, txt, c):
        if not txt:
            return c.sort_key(''), ''

        alpha = []
        num = []
        pad = 10
        # deal with characters before first alphabetic character
        # (prefix before first word)
        prefix = '0'
        txt2 = txt.split()
        if txt2[0][0].isnumeric(): # first char of first split is a number
            prefix = txt2[0]
            txt = ' '.join(txt2[1:])

        l = [i for i in re.split(r'(\d+)', prefix) if i] # split by numbers
        for i in l:
            try:
                dig = int(i) # number
            except ValueError:
                num.append(i) # some characters separating numbers
            else:
                num.append(i.rjust(pad, '0'))

        # now, deal with the main gloss
        l = [i for i in re.split(r'(\d+)', txt) if i]
        for i in l:
            try:
                dig = int(i) # number
            except ValueError:
                alpha.append(i) 
            else:
                num.append(i.rjust(pad, '0'))
        key1 = ''.join(alpha)
        key2 = ''.join(num)
        return c.sort_key(key1), key2
    
    #@pyqtSlot(bool)        
    def onProjectOpen(self, _bool):
        if _bool and qApp.instance().pm.project:
            self.current_font_size = qApp.instance().pm.getSearchFontSize() 
            self.current_font_family = qApp.instance().pm.getSearchFontFamily()
            self.dialect_filter.clear()
            self.search_box.setEnabled(True)
            self.selected_sense = 0
            self.selected_field = 0
            
    def clear(self):
        if self.finder_list:
            self.finder_list.clear()
    
    #@pyqtSlot()      
    def onProjectClosed(self):
        self.clear()
        self.search_box.setEnabled(False)
        self.finder_list.horizontalHeader().setEnabled(False)        
        
#     def getTextAlignment(self, _text):
#         """
#         http://www.pythoncentral.io/encoding-and-decoding-strings-in-python-3-x/
#         """
#         if not _text:
#             return Qt.AlignLeft
#         x = len([None for ch in _text if UD.bidirectional(ch) in ('R', 'AL')])/float(len(_text))
#         if x > 0.5:
#             return Qt.AlignRight
#         else:
#             return Qt.AlignLeft

    # def setupItems(self):
    #     #'if counts differ, adjust row numbers'; might do if different lang list have glosses separated by ';' in sense
    #     # most definitely diff on opening new project
    #     # old_count = self.model().rowCount()
    #     # new_count = len(self.sign_texts)
    #     # if new_count > old_count: #add rows
    #     #     while self.model().rowCount() < new_count:
    #     #         self.model().appendRow([QStandardItem(), QStandardItem()])
    #     # elif new_count < old_count: #remove rows
    #     #     row = old_count
    #     #     while self.model().rowCount() > new_count:
    #     #         self.model().removeRow(row)
    #     #         row -= 1
    #     self.model().clear()
    #     project = qApp.instance().pm.project
    #     if project:
    #         for st in self.sign_texts:
    #             txt = st.get('text', '')
    #             dialect_ids = st.get('dialect_ids', [])
    #             dstr = qApp.instance().pm.dialectStr(dialect_ids)
    #             self.model().appendRow([QStandardItem(txt), QStandardItem(dstr)])
    #     return True 
                       
    def setupList(self):
        if hasattr(self, 'textFilterTimer'):
            self.textFilterTimer.stop()
        self.sign_texts = self.getSignTextList()
        self.finder_list.model().setSearchFlag(self.search_filter)
        self.finder_list.model().resetSignTextList(self.sign_texts)
        self.showEmptyGlossActionTool()
        if len(self.sign_texts) > 1:
            self.finder_list.horizontalHeader().setEnabled(True) 
        else:
            self.finder_list.horizontalHeader().setEnabled(False)
        if len(self.sign_texts) > 0:
            self.selectCurrentGloss()
        
    def selectCurrentGloss(self):
        ## NOTE: not sure why a ProjectManager is calling this when component searching as well as QAction?
        #if not isinstance(self.sender(), ProjectManager):
        if not self.editing: # selecting a gloss may reload the model and reload the InfoPage, which will in turn lose added widgets (Sentence...) during editing
            if qApp.instance().pm.sign:
                self.selected_sense = qApp.instance().pm.sign.current_sense_id
                self.selected_field = qApp.instance().pm.sign.current_sense_field                
            selected_row = 0 #if no current gloss, select first row
            selected_text = [t for t in self.sign_texts if t.get('sense_id', None) and t.get('sense_id') == self.selected_sense and t.get('sense_field', 0) == self.selected_field]
            if selected_text:
                selected_row = self.sign_texts.index(selected_text[0])
            idx = self.finder_list.model().index(selected_row, 0)
            self.finder_list.setCurrentIndex(idx)
            self.finder_list.selectRow(idx.row())
            self.finder_list.scrollTo(idx)
            self.selectGlossAtIndex(idx)
        else:
            self.finder_list.clearSelection()
        
    def showEmptyGlossActionTool(self):
        unglossed = [t for t in self.sign_texts if not t.get('text', '')]
        if self.finder_list and unglossed:
            self.has_unglossed_signs.emit(True)
        else:
            self.has_unglossed_signs.emit(False)
        
    #@pyqtSlot()           
    def onSearchLangChange(self):
        """alter the current language used for the text list
        """
        if qApp.instance().pm.search_lang_id == 0: #new lang, do nothing
            return
        self.search_box.clear()
        font_size = qApp.instance().pm.getSearchFontSize()
        self.current_font_size = font_size
        font_family = qApp.instance().pm.getSearchFontFamily()
        self.current_font_family = font_family
        self.search_box.setFontFamily(font_family)
        self.setupList()
        
    def setupSearchBox(self): 
        if self.search_box.layoutDirection() == Qt.LeftToRight: 
            self.search_box.setStyleSheet("""background-image: url(':/search_small.png');
            background-repeat: no-repeat;
            background-position: center right;
            padding-right: 24px;
            height: 20px""")
        else:
            self.search_box.setStyleSheet("""background-image: url(':/search_small.png');
            background-repeat: no-repeat;
            background-position: center left;
            padding-left: 24px;
            height: 20px""")

    def enterEvent(self, evt):
        self.update()
        super(FinderList, self).enterEvent(evt)
    
    #@pyqtSlot()    
    def enterEditingMode(self):
        if not self.editing:
            self.editing = True
            self.setupList()
            self.setEnabled(False)
            #self.search_text = self.search_box.text()
            #self.search_box.clear()
            self.search_box.hide()
            self.finder_list.horizontalHeader().hide() 
    
    #@pyqtSlot()    
    def leaveEditingMode(self):
        self.setEnabled(True)
        self.editing = False
        self.setupList()
        self.search_box.show()
        self.finder_list.horizontalHeader().show() 
     
    #@pyqtSlot(list)     
    def filterByDialects(self, dialects):
        self.dialect_filter = dialects
        self.setupList()
    
    #@pyqtSlot(QModelIndex)        
    def selectGlossAtIndex(self, idx, reload=False):
        if idx:
            try:
                sign_text = self.sign_texts[idx.row()]
            except:
                pass
            else:
                selected_sign_id = sign_text.get('sign_id')
                selected_sense = sign_text.get('sense_id')
                selected_field = sign_text.get('sense_field')
                if reload or qApp.instance().searching or \
                    selected_sign_id != self.selected_sign_id or \
                    selected_sense != self.selected_sense or \
                    selected_field != self.selected_field:
                        qApp.instance().pm.findSignById(selected_sign_id, selected_sense, selected_field)                        
                        self.selected_sign_id = selected_sign_id
                        self.selected_sense = selected_sense
                        self.selected_field = selected_field
        if qApp.instance().searchType == 'gloss':
            qApp.instance().searching = False
                        
    def amendList(self):
        self.setupList()

class FinderTableModel(QAbstractTableModel):
    def __init__(self, sign_texts=[], parent=None):
        super(FinderTableModel, self).__init__(parent) 
        self.sign_texts = sign_texts
        self.search_flag = False

    def rowCount(self, parent=None):
        if qApp.instance().pm.project:
            return len(self.sign_texts)
        return 0

    def columnCount(self, parent=None):
        return 2

    def data(self, model_index, role=Qt.DisplayRole):
        if qApp.instance().pm.project:
            row = model_index.row()
            col = model_index.column()
            st = self.sign_texts[row]
            if role == Qt.DisplayRole:
                if col == 0:
                    return st.get('text', '')
                elif col == 1:
                    dialect_ids = st.get('dialect_ids', [])
                    return qApp.instance().pm.dialectStr(dialect_ids)
            # elif role == Qt.DecorationRole and col == 0 and self.search_flag:
            #     return QIcon(':/hand_down.png')
        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section == 0:
                return qApp.instance().translate('FinderTableModel', 'Gloss')
            elif section == 1:
                return qApp.instance().translate('FinderTableModel', 'Dialect')
        return QVariant()

    def resetSignTextList(self, sign_texts):
        self.beginResetModel()
        self.sign_texts = sign_texts
        self.endResetModel()

    def setSearchFlag(self, search_list):
        self.search_flag = False
        if search_list:
            self.search_flag = True
            
class FinderTableView(QTableView):
    #itemClicked = pyqtSignal(QStandardItem)
    
    def __init__(self, parent=None):
        super(FinderTableView, self).__init__(parent) 
        settings = qApp.instance().getSettings()
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        highlight_text = self.palette().color(QPalette.HighlightedText).name()
        highlight = self.palette().color(QPalette.Highlight).name()
        style_str = "QTableView::item:selected{color:%s; background-color:%s}" % (highlight_text, highlight)
        self.setStyleSheet(style_str)
        self.setModel(FinderTableModel())
         
        self.setFrameStyle(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setTextElideMode(Qt.ElideMiddle)        
        self.setFocusPolicy(Qt.TabFocus|Qt.ClickFocus)
        self.setSortingEnabled(False)
        self.setItemDelegate(TextItemDelegate(self))
        #self.setColumnWidth(0, int(settings.value('GlossColWidth', 70)))
        self.setLayoutDirection(Qt.LayoutDirectionAuto) 
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollMode(self.ScrollPerItem)
        self.setupHeader()

    def setupHeader(self):
        ## header settings
        self.horizontalHeader().setMinimumSectionSize(10)
        self.horizontalHeader().setEnabled(False)   
        self.horizontalHeader().setCascadingSectionResizes(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive) 
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  
        self.horizontalHeader().setSectionsMovable(False)
        self.horizontalHeader().sectionHandleDoubleClicked.connect(self.onHeaderHandleDoubleClicked)
        self.horizontalHeader().setStyleSheet("""QHeaderView::section {background-color: palette(button); border: 1px solid gray; border-top: none;}
            QHeaderView::section::hover {background-color: aliceblue; border: 1px solid cornflowerblue;}""")
        gloss_width = int(qApp.instance().getSettings().value('GlossColWidth', 0))
        if gloss_width:
            self.horizontalHeader().resizeSection(0, int(gloss_width))
        else:
            self.defaultSettings()

    def defaultSettings(self):
        w = qApp.instance().getMainWindow().width()/6 + 20
        self.horizontalHeader().resizeSection(0, int(w))
        
    def changeEvent(self, evt):
        if evt.type() == QEvent.LanguageChange:
            self.model().headerDataChanged.emit(Qt.Horizontal, 0, 1)
        else:
            QTableView.changeEvent(self, evt)

    def clear(self):
        pass
    
    def mouseReleaseEvent(self, *args, **kwargs):
        try:
            idxs = self.selectedIndexes()[0]
        except:
            pass
        else:
            self.parent().selectGlossAtIndex(idxs)
        self.parent().update()

    def keyPressEvent(self, evt):
        if evt.key() in [Qt.Key_Tab]:
            try:
                self.parent().loseTabFocus.emit()
            except:
                print('finderlist#1039', self.parent())
        else:
            self.parent().update()
            return super(FinderTableView, self).keyPressEvent(evt)
        
    def keyReleaseEvent(self, evt):
        if evt.key() in [Qt.Key_Enter, 
                         Qt.Key_Space, 
                         Qt.Key_Return]:
            try:
                self.parent().selectGlossAtIndex(self.selectedIndexes()[0])
            except:
                pass
        elif evt.key() in [Qt.Key_Tab]:
            pass
        self.parent().update()
        return super(FinderTableView, self).keyReleaseEvent(evt)
    
    def wheelEvent(self, evt):
        # y = evt.angleDelta().y()
        # scrollbar = self.verticalScrollBar()
        # value = scrollbar.value()
        # if y > 0:
        #     scrollbar.setValue(value - 1)
        # elif y < 0:
        #     scrollbar.setValue(value + 1)
        self.parent().update()
        return super(FinderTableView, self).wheelEvent(evt)
    
    #@pyqtSlot(int)    
    def onHeaderHandleDoubleClicked(self, col):
        if col == 0:
            self.resizeColumnToContents(0)
        
    def getMaxTextWidth(self, col=0):
        max_width = 0
        row = 0
        idx = self.model().index(row, col)
        f = QFont(self.parent().font().family(), self.parent().current_font_size)
        fm = QFontMetrics(f)
        while idx:
            text = idx.data()
            w = fm.width(text)
            if w > max_width:
                max_width = w
            row += 1
            idx = self.model().index(row, col)
        return max_width
    
    def getMaxDialectWidth(self):
        dialects = qApp.instance().pm.getAllDialects()
        abbrs = [d.abbr for d in dialects]
        max_width = 0    
        #idx = self.model().index(0, 0)
        f = QFont(self.parent().font().family(), self.parent().current_font_size)
        fm = QFontMetrics(f)
        for abbr in abbrs:
            w = fm.width(abbr)
            if w > max_width:
                max_width = w
        return max_width
    
    def sizeHintForColumn(self, col):
        # on double-click header-handle
        if col == 0:
            w = self.width() - self.getMaxDialectWidth() - 16 #self.getMaxTextWidth(col=1)# - 20
        elif col == 1:
            w = self.getMaxTextWidth(col=1)
        return w   
        
    def sizeHintForRow(self, row):
        size = QTableView.sizeHintForRow(self, row) + 4
        return size
    
    def sizeHint(self):
        return super(FinderTableView, self).sizeHint()

class FinderSearchBox(QLineEdit):
    change_keyboard = pyqtSignal(int)
    show_clear_btn = pyqtSignal()
    hide_clear_btn = pyqtSignal()
    
    def __init__(self, parent=None):
        super(FinderSearchBox, self).__init__(parent)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setPlaceholderText(qApp.instance().translate('FinderSearchBox', "Search")) 
        self.textChanged.connect(self.onTextChanged)
        self.change_keyboard.connect(qApp.instance().changeKeyboard)
        if sys.platform.startswith('darwin'):
            from Cocoa import NSTextInputContext
            
    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            self.setPlaceholderText(qApp.instance().translate('FinderSearchBox', "Search"))
        else:
            QLineEdit.changeEvent(self, evt)
            
    def onTextChanged(self, text):
        #self.setMyStyle()
        if text:
            self.show_clear_btn.emit()
        else:
            self.hide_clear_btn.emit()      
     
    # @pyqtSlot()   
    # def setMyStyle(self):
        # img = ':/search_small.png'
        # if self.text():
        #     img = ':/close.png'
        # if self.layoutDirection() == 0:
        #     self.setStyleSheet("""background-image: url({});
        #     background-repeat: no-repeat;
        #     background-position: center right;
        #     padding-right: 20px;
        #     padding-left: 0px;
        #     height: 20px""".format(img))
        # else:
        #     self.setStyleSheet("""background-image: url({});
        #     background-repeat: no-repeat;
        #     background-position: center left;
        #     padding-right: 20px;
        #     padding-left: 0px;
        #     height: 20px""".format(img)) 

    # def mouseMoveEvent(self, evt):
    #     icon_rect = self.rect()
    #     if self.layoutDirection() == 0:
    #         l = icon_rect.width() - 20
    #         icon_rect.setLeft(l) 
    #     else:
    #         icon_rect.setRight(20)
    #     if icon_rect.contains(evt.pos()):
    #         self.setCursor(QCursor(Qt.ArrowCursor))
    #     else:
    #         self.setCursor(QCursor(Qt.IBeamCursor))
    #     return super(FinderSearchBox, self).mouseMoveEvent(evt)
        
    # def mousePressEvent(self, evt):
    #     icon_rect = self.rect()
    #     if self.layoutDirection() == 0:
    #         l = icon_rect.width() - 20
    #         icon_rect.setLeft(l) 
    #     else:
    #         icon_rect.setRight(20)
    #     if self.text() and icon_rect.contains(evt.pos()):
    #         self.clear()
    #     return super(FinderSearchBox, self).mousePressEvent(evt)  
    
    def focusInEvent(self, evt):
        self.change_keyboard.emit(qApp.instance().pm.search_lang_id)
        # qApp.processEvents()
        super(FinderSearchBox, self).focusInEvent(evt)
        
    def setFontFamily(self, font_family):
        _font = self.font()
        _font.setFamily(font_family)
        self.setFont(_font)
                
class TextItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(TextItemDelegate, self).__init__(parent)
        
    def sizeHint(self, option, index):
        finder_list = self.parent().parent()
        option.font.setPointSize(finder_list.current_font_size)
        option.font.setFamily(finder_list.current_font_family)
        w = 100
        fm = QFontMetrics(option.font)
        h = fm.height()+fm.descent()
        if finder_list.search_filter:
            h = max(h, option.decorationSize.height())
        sz = QSize(int(w), int(h))
        return sz
        
    def paint(self, painter, option, index):
        try:
            painter.save()
            option.state = option.state & (~QStyle.State_HasFocus) #remove any dotted lines around focus items
            finder_list = self.parent().parent()
            lang_id = qApp.instance().pm.search_lang_id
                
            if index.column() == 0: #gloss
                if index.data() == '':
                    rect = option.rect.adjusted(2, 2, -2, -2)                
                    painter.fillRect(rect, Qt.lightGray) 
                if not finder_list.search_filter: 
                    option.font.setPointSize(finder_list.current_font_size)
                    option.font.setFamily(finder_list.current_font_family)
                    if self.parent().selectionModel().isSelected(index):
                        option.font.setBold(True)
                    else:
                        option.font.setBold(False)
                else:  
                    option.font.setPointSize(finder_list.current_font_size - 2)
                    option.font.setFamily(finder_list.current_font_family)
                    option.decorationSize = QSize(24, 24)
                    
            elif index.column() == 1: #dialects
                option.font.setBold(False)
            try:
                super(TextItemDelegate, self).paint(painter, option, index)
            except:
                pass
            painter.restore()   
        except:
            super(TextItemDelegate, self).paint(painter, option, index)


if __name__ == '__main__':
    from mainwindow import main
    main()
