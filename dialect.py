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

from PyQt5.QtCore import QObject

class Dialect(QObject):
    """a class to model a dialect
    """
    
    def __init__(self, _id, name, abbr, focal, parent=None):
        super(Dialect, self).__init__(parent)
        self._id = _id
        self.name = name
        self.abbr = abbr
        self.focal = focal
        
    @property
    def isFocal(self):
        try:
            if self.focal == 1 or \
                isinstance(self.focal, str) and self.focal.lower() == 'true' or \
                isinstance(self.focal, bool) and self.focal == True:
                return 1
            else:
                return 0
        except:
            return 0
        
    def setFocal(self, _bool=True):
        if _bool:
            self.focal = 'true'
        else:
            self.focal = 'false'
