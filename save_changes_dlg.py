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


from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import qApp

from PyQt5.QtGui import QPixmap

class SaveChangesDlg(QDialog):
    """Dialog asks user to save or discard changes to a sign before moving on."""
    
    def __init__(self, delete=False, parent=None):        
        super(SaveChangesDlg, self).__init__(parent=parent)  
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(' ')
            
        layout = QVBoxLayout()
        text = QLabel()
        if not delete:
            text.setText('<center><h3>{}</h3></center>'.format(qApp.instance().translate('SaveChangesDlg', 'Save changes'))) 
        else:  
            text.setStyleSheet("""color: red""")   
            text.setText("<center><h3>{}</h3><p>{}</p></center>".format(qApp.instance().translate('SaveChangesDlg', 'Save changes'), qApp.instance().translate('SaveChangesDlg', 'This will delete a Sign from your dictionary.'))) 
        question = QLabel()
        px = QPixmap(":/question.png")    
        question.setPixmap(px)   
        self.btnBox = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        self.btnBox.button(QDialogButtonBox.Yes).setText(qApp.instance().translate('SaveChangesDlg', 'Yes'))
        self.btnBox.button(QDialogButtonBox.No).setText(qApp.instance().translate('SaveChangesDlg', 'No'))
        
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)

        layout.addWidget(text)
        layout.addWidget(question)
        layout.addWidget(self.btnBox)
        
        layout.setAlignment(question, Qt.AlignHCenter)
        layout.setAlignment(self.btnBox, Qt.AlignHCenter)
        
        self.setLayout(layout)      
        self.btnBox.button(QDialogButtonBox.Yes).setFocus()
    
    
