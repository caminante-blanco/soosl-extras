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

from PyQt5.QtWidgets import qApp
from PyQt5.QtGui import QValidator
from PyQt5.QtCore import pyqtSignal
import re
import os

class FileNameValidator(QValidator):
    invalidChar = pyqtSignal(str, bool)
    intermedChar = pyqtSignal(str)
    invalidName = pyqtSignal(str)
    validChar = pyqtSignal()

    def __init__(self, parent):
        super(FileNameValidator, self).__init__(parent)

    def validate(self, text, pos):
        value = (QValidator.Acceptable, text, pos)
        if text:
            if text[0] in [' ', '_', '-', '.', ',']:
                value = (QValidator.Invalid, text, pos)
                self.invalidChar.emit(qApp.instance().translate('FileNameValidator', 'Filename must start with a letter or a number.'), False)
            elif re.search(r" ", text): # do not allow space
                value = (QValidator.Invalid, text, pos)
                self.invalidChar.emit(qApp.instance().translate('FileNameValidator', 'Use "-" or "_" instead of blank space.'), False)
            # deal with fullstop and extensions #######################################################
            elif text[pos-1] == '.' and text.count('.') > 1: # multiple fullstops invalid
                value = (QValidator.Invalid, text, pos)
                self.invalidChar.emit(qApp.instance().translate('FileNameValidator', '"." can only be used once in the extension ".zoozl".'), False)
            elif text[-1] == '.':
                value = (QValidator.Intermediate, text, pos)
                self.intermedChar.emit(qApp.instance().translate('FileNameValidator', 'Use extension ".zoozl" or no extension.'))
            # elif text.count('.') and os.path.splitext(text)[1].lower() == '.zoozl':
            #     # valid
            #     self.invalidChar.emit('', False)
            elif text.count('.') and os.path.splitext(text)[1].lower() != '.zoozl':
                xt = os.path.splitext(text)[1]
                message = '{} <b style="color:red;">"{}"</b>. {}'.format(qApp.instance().translate('FileNameValidator', 'Invalid extension'), xt, qApp.instance().translate('FileNameValidator', 'Use extension ".zoozl" or no extension.'))
                value = (QValidator.Intermediate, text, pos)
                self.intermedChar.emit(message)
            #############################################################################################
            elif text[pos-1] in ['_', '-']: # valid characters, but prevent repetition
                char = text[pos-1]
                if text[pos-2] in ['_', '-']: #check before
                    value = (QValidator.Invalid, text, pos)
                    self.invalidChar.emit(qApp.instance().translate('FileNameValidator', 'Follow this character with a letter or a number.'), False)
                elif len(text) > pos and text[pos] in ['_', '-']: #check after
                    value = (QValidator.Invalid, text, pos)
                    self.invalidChar.emit(qApp.instance().translate('FileNameValidator', 'Follow this character with a letter or a number.'), True)
                elif len(text) > pos and text[pos] not in ['_', '-', '.']: #check after
                    pass #valid
                else:
                    value = (QValidator.Intermediate, text, pos)
                    self.intermedChar.emit(qApp.instance().translate('FileNameValidator', 'Follow this character with a letter or a number.'))
            elif re.search(r"[\\/\'\"\`<>|{}[\]*?~^+=;:#$%&@]", text):
                    #https://blog.josephscott.org/2007/02/12/things-that-shouldnt-be-in-file-names-for-1000-alex/
                    value = (QValidator.Invalid, text, pos)
                    char = text[pos-1]
                    self.invalidChar.emit('"{}" {}'.format(char, qApp.instance().translate('FileNameValidator', 'Do not use this character.')), False)
            # # ## invalidate non-printing characters
            # #elif list(s for s in text if not s.isprintable()):
            # elif not text.isprintable():
            #     value = (QValidator.Invalid, text, pos)
            #     char = list(s for s in text if not s.isprintable())[0]
            #     self.invalidChar.emit('{}: {}'.format(char, qApp.instance().translate('FileNameValidator', 'Do not use non-printing characters.')), False)
            #https://kizu514.com/blog/forbidden-file-names-on-windows-10/
            elif os.path.splitext(text)[0].upper() in [
                                'CON',
                                'PRN',
                                'AUX',
                                'CLOCK$',
                                'NUL',
                                'COM1',
                                'COM2',
                                'COM3',
                                'COM4',
                                'COM5',
                                'COM6',
                                'COM7',
                                'COM8',
                                'COM9',
                                'COM0',
                                'LPT1',
                                'LPT2',
                                'LPT3',
                                'LPT4',
                                'LPT5',
                                'LPT6',
                                'LPT7',
                                'LPT8',
                                'LPT9',
                                'LPT0'
                                ]:
                value = (QValidator.Intermediate, text, pos)
                #self.invalidName.emit('{}: {}'.format(os.path.basename(text), qApp.instance().translate('FileNameValidator', 'Do not use reserved filename.')))
                self.intermedChar.emit('{}: {}'.format(os.path.basename(text), qApp.instance().translate('FileNameValidator', 'Do not use reserved filename.')))
            else:
                self.invalidChar.emit('', False)
                self.invalidName.emit('')
        self.validChar.emit()
        return value

class FolderNameValidator(QValidator):
    invalidChar = pyqtSignal(str, bool)
    intermedChar = pyqtSignal(str)
    invalidName = pyqtSignal(str)
    validChar = pyqtSignal()

    def __init__(self, parent):
        super(FolderNameValidator, self).__init__(parent)

    def validate(self, text, pos):
        value = (QValidator.Acceptable, text, pos)
        if text:
            if text[0] in [' ', '_', '-', '.', ',']:
                value = (QValidator.Invalid, text, pos)
                self.invalidChar.emit(qApp.instance().translate('FolderNameValidator', 'Folder must start with a letter or a number.'), False)
            elif re.search(r" ", text): # do not allow space
                value = (QValidator.Invalid, text, pos)
                self.invalidChar.emit(qApp.instance().translate('FolderNameValidator', 'Use "-" or "_" instead of blank space.'), False)
            # # deal with fullstop and extensions #######################################################
            # elif text[pos-1] == '.' and text.count('.') > 1: # multiple fullstops invalid
            #     value = (QValidator.Invalid, text, pos)
            #     self.invalidChar.emit(qApp.instance().translate('FolderNameValidator', '"." can only be used once in the extension ".zoozl".'), False)
            # elif text[-1] == '.':
            #     value = (QValidator.Intermediate, text, pos)
            #     self.intermedChar.emit(qApp.instance().translate('FolderNameValidator', 'Use extension ".zoozl" or no extension.'))
            # elif text.count('.') and os.path.splitext(text)[1] != '.zoozl':
            #     xt = os.path.splitext(text)[1]
            #     message = '{} <b style="color:red;">"{}"</b>. {}'.format(qApp.instance().translate('FolderNameValidator', 'Invalid extension'), xt, qApp.instance().translate('FolderNameValidator', 'Use extension ".zoozl" or no extension.'))
            #     value = (QValidator.Intermediate, text, pos)
            #     self.intermedChar.emit(message)
            # #############################################################################################
            elif text[pos-1] in ['_', '-']: # valid characters, but prevent repetition
                char = text[pos-1]
                if text[pos-2] in ['_', '-']: #check before
                    value = (QValidator.Invalid, text, pos)
                    self.invalidChar.emit(qApp.instance().translate('FolderNameValidator', 'Follow this character with a letter or a number.'), False)
                elif len(text) > pos and text[pos] in ['_', '-']: #check after
                    value = (QValidator.Invalid, text, pos)
                    self.invalidChar.emit(qApp.instance().translate('FolderNameValidator', 'Follow this character with a letter or a number.'), True)
                elif len(text) > pos and text[pos] not in ['_', '-', '.']: #check after
                    pass #valid
                else:
                    value = (QValidator.Intermediate, text, pos)
                    self.intermedChar.emit(qApp.instance().translate('FolderNameValidator', 'Follow this character with a letter or a number.'))
            elif re.search(r"[\\/\'\"\`<>|{}[\]*?~^+=;:#$%&@.]", text):
                    #https://blog.josephscott.org/2007/02/12/things-that-shouldnt-be-in-file-names-for-1000-alex/
                    value = (QValidator.Invalid, text, pos)
                    char = text[pos-1]
                    self.invalidChar.emit('"{}" {}'.format(char, qApp.instance().translate('FolderNameValidator', 'Do not use this character.')), False)
            # # ## invalidate non-printing characters
            # #elif list(s for s in text if not s.isprintable()):
            # elif not text.isprintable():
            #     value = (QValidator.Invalid, text, pos)
            #     char = list(s for s in text if not s.isprintable())[0]
            #     self.invalidChar.emit('{}: {}'.format(char, qApp.instance().translate('FolderNameValidator', 'Do not use non-printing characters.')), False)
            #https://kizu514.com/blog/forbidden-file-names-on-windows-10/
            elif os.path.splitext(text)[0].upper() in [
                                'CON',
                                'PRN',
                                'AUX',
                                'CLOCK$',
                                'NUL',
                                'COM1',
                                'COM2',
                                'COM3',
                                'COM4',
                                'COM5',
                                'COM6',
                                'COM7',
                                'COM8',
                                'COM9',
                                'COM0',
                                'LPT1',
                                'LPT2',
                                'LPT3',
                                'LPT4',
                                'LPT5',
                                'LPT6',
                                'LPT7',
                                'LPT8',
                                'LPT9',
                                'LPT0'
                                ]:
                value = (QValidator.Intermediate, text, pos)
                #self.invalidName.emit('{}: {}'.format(os.path.basename(text), qApp.instance().translate('FolderNameValidator', 'Do not use reserved filename.')))
                self.intermedChar.emit('{}: {}'.format(os.path.basename(text), qApp.instance().translate('FolderNameValidator', 'Do not use reserved filename.')))
            else:
                self.invalidChar.emit('', False)
                self.invalidName.emit('')
        self.validChar.emit()
        return value
