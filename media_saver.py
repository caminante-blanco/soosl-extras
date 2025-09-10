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

"""Used with new json dictionary format (>=0.9.0).
"""

import sys, os

from PyQt5.QtWidgets import qApp
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal

class MediaSaver(QObject):
    finished = pyqtSignal(bool)
    remove_file = pyqtSignal(str)
    dont_remove_file = pyqtSignal(str)

    def __init__(self, media_objects, update_last_change=False, parent=None):
        super(MediaSaver, self).__init__(parent)
        self.completed = False
        self.media_objects = media_objects
        self.abort_flag = False
        self.update_last_change = update_last_change
        self.media_log = qApp.instance().pm.getSavedMediaLogPath()
        with open(self.media_log, 'w', encoding='utf-8') as f:
            f.write('')

    ##!!@pyqtSlot(int, float, str, bool)
    def onProgress(self, progress, duration, file_pth, complete):
        if duration:
            qApp.instance().pm.save_progress.emit(file_pth, progress, duration, complete)

    def abort(self):
        self.abort_flag = True
        for obj in self.media_objects:
            new_path = obj.newPath()
            if os.path.exists(new_path):
                self.remove_file.emit(new_path)

        self.media_objects.clear()
        self.completed = True
        self.finished.emit(False)

    def logMediaSavePaths(self, filename):
        with open(self.media_log, 'a', encoding='utf-8') as f:
            f.write(filename + '\n')

    def save(self):
        #populate progress dialog
        for obj in self.media_objects:
            obj.progress.connect(self.onProgress)
            new_path = obj.newPath()
            self.dont_remove_file.emit(new_path)
            self.logMediaSavePaths(new_path)

        for obj in self.media_objects:
            if self.abort_flag:
                return

            obj.save2dir()

            while not obj.complete:
                if qApp.hasPendingEvents():
                    qApp.processEvents()
                self.thread().msleep(100)

        if qApp.hasPendingEvents():
            qApp.processEvents()
        self.media_objects.clear()
        self.completed = True
        self.finished.emit(self.update_last_change)
