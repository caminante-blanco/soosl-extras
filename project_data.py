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

"""
DESIGN NOTE:
Aim to create a project data structure which can be more easily shared with model/views without convertion to another
data structure.
Also, make it based on Python only so it is not Qt dependent; ie, it could be more easily used with a
different gui toolkit.
"""

class Node(object):
    def __init__(self, data, data_type, parent=None):
        self.data = data
        self.data_type = data_type
        self._children = []
        self._parent = parent

    def parent(self):
        return self._parent
    
    def children(self):
        return self._children
    
    def hasChildren(self):
        if self.childCount():
            return True
        return False

    def childCount(self):
        return len(self._children)

    def addChild(self, child):
        child._parent = self
        child._row = len(self._children)
        self._children.append(child)

    def displayText(self):
        if self.data_type == 'projectRoot':
            return ''
        return ''
    
    def save(self):
        pass

class ProjectNode(Node):
    def __init__(self, project_path):
        super(ProjectNode, self).__init__(project_path, 'projectRoot')

