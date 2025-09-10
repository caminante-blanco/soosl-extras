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
from PyQt5.QtCore import QProcess
from PyQt5.QtWidgets import qApp

class Keyboard(QObject):
    
    def __init__(self, parent=None):
        super(Keyboard, self).__init__(parent)
        self.kbdict = {}
        p = QProcess(self)
        p.setProgram('ibus')
        p.setArguments(['list-engine'])
        p.start()
        p.waitForFinished(msecs=-1)

        result = p.readAll().data().decode('utf-8')
        lines = result.splitlines()
        if not len(lines) > 1:
            p.setProgram('ibus-daemon')
            p.setArguments(['&'])
            p.start()
            p.waitForFinished(msecs=-1)
            p.setProgram('ibus')
            p.setArguments(['list-engine'])
            p.start()
            p.waitForFinished(msecs=-1)
            result = p.readAll().data().decode('utf-8')
        lines = result.splitlines()

        if not len(lines) > 1:
            qApp.instance().pe.setAutoKeyboard(0)
        else:
            lang_name = None #language name; key for self.kbdict
            for line in lines:
                if line:
                    if not line.startswith(' '): #language name line, no space at start; 'language: lang_name'
                        lang_name = line.strip().split(': ')[1]
                    else: #keyboard engine line, 2 spaces at start; '  engine - engine_name'
                        try:
                            engine, engine_name = line.strip().split(' - ') 
                        except:
                            pass #print('error: engine line:', line)
                        else:
                            engines = self.kbdict.get(lang_name, None)
                            if not engines:
                                self.kbdict[lang_name] = [(engine, engine_name)]
                            else:
                                engines.append((engine, engine_name))
                
    @property
    def current_keyboard(self):
        p = QProcess(self)
        p.setProgram('ibus')
        p.setArguments(['engine'])
        p.start()
        p.waitForFinished(msecs=-1)
        result = p.readAll().data()
        result = result.decode('utf-8').strip()
        print(result)
        return result
    
    @property
    def current_keyboard_name(self):
        return self.engine_name(self.current_keyboard)
    
    def engine_name(self, engine):
        for value in self.kbdict.values():
            for eng, eng_name in value:
                if engine == eng:
                    return eng_name
        return None
    
    def engine_by_name(self, lang, name):
        engines = self.kbdict.get(lang)
        if engines:
            for engine in engines:
                eng, eng_name = engine
                if name == eng_name:
                    return eng
        return None
    
    def all_engine_names(self):
        all = []
        for value in self.kbdict.values():
            for eng, eng_name in value:
                all.append(eng_name) 
        all.sort()
        return all
    
    def set_engine(self, engine):
        if engine:
            p = QProcess(self)
            p.setProgram('ibus')
            p.setArguments(['engine', engine])
            p.start()
            p.waitForFinished(msecs=-1)        
        
# if __name__ == '__main__':
#     kbd = Keyboard()
#     for k in kbd.kbdict.keys():
#         engines = kbd.kbdict.get(k)
#         for e in engines:
#             print('{} - {}'.format(k, e))
            