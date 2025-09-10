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

import os

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtProperty

class MediaObject(list):
    def __init__(self, _filename=None, _mediatype=None, _crop=None, _transcode_crop=None, _rotation=0, _id=0, _hash='', _orig_filename=None):
        super(MediaObject, self).__init__()
        if _filename:
            _filename = _filename.replace('\\', '/')
        if not _orig_filename:
            _orig_filename = _filename
        else:
            _orig_filename = _orig_filename.replace('\\', '/')
        self.extend([_filename, _mediatype, _crop, _transcode_crop, _rotation, _id, _hash, _orig_filename])

    def clear(self):
        super(MediaObject, self).clear()
        self.extend([None, None, None, None, 0, 0, '', '', None])

    @pyqtProperty(str)
    def orig_filename(self):
        return self[7]

    @pyqtProperty(str)
    def filename(self):
        return self[0]

    @filename.setter
    def filename(self, value):
        self[0] = value.replace('\\', '/')

    @pyqtProperty(str)
    def mediatype(self):
        return self[1]

    @mediatype.setter
    def mediatype(self, value):
        self[1] = value

    @pyqtProperty(tuple)
    def crop(self):
        return self[2]

    @crop.setter
    def crop(self, value):
        self[2] = value

    @pyqtProperty(tuple)
    def transcode_crop(self):
        return self[3]

    @transcode_crop.setter
    def transcode_crop(self, value):
        self[3] = value

    @pyqtProperty(int)
    def rotation(self):
        return self[4]

    @rotation.setter
    def rotation(self, value):
        self[4] = value

    @pyqtProperty(int)
    def id(self):
        return self[5]

    @id.setter
    def id(self, value):
        self[5] = value

    ##NOTE: appears to be some conflict not allowing this to be a property named 'hash'; just returned 0 when self[6] returned expected hash string
    #@pyqtProperty(str)
    def getHash(self):
        return self[6]

    @id.setter
    def hash(self, value):
        self[6] = str(value)

    def isGif(self):
        ext = os.path.splitext(self.filename)[1].lower()
        if ext == '.gif':
            return True
        return False
