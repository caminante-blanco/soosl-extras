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

"""function to find component type for a given code"""

def byCode(code):
    _type = None
    code = eval("0x{}".format(code))
    if 256 <= code < 517:
        _type = 'handshape'
    elif 767 <= code <= 880:
        _type = 'facehead'
    elif 1280 <= code <= 4095: # see location_widget.py; range here for reference only
        _type = 'location'
    elif 4096 <= code <= 4111:
        _type = 'signtype'
    elif 4112 <= code <= 4127:
        _type = 'changenature' # movements - nature of change
    elif 4128 <= code <= 4135:
        _type = 'changelocation' #movements - change of location details
    elif 4136 <= code <= 4143:
        _type = 'changemanner' #movements - manner of change
    elif 4144 <= code <= 4159:
        _type = 'contact'

    else:
        _type = 'none_type'
    return _type

def possibleCatCodes(category): #not all codes in range are used
    if category == 'handshape':
        return [i for i in list(range(256, 517))]
    elif category == 'facehead':
        return [i for i in list(range(767, 880))]
    elif category == 'signtype':
        return [i for i in list(range(4096, 4112))]
    elif category == 'changenature':
        return [i for i in list(range(4112, 4128))]
    elif category == 'changelocation':
        return [i for i in list(range(4128, 4136))]
    elif category == 'changemanner':
        return [i for i in list(range(4136, 4144))]
    elif category == 'contact':
        return [i for i in list(range(4144, 4160))]
# reference only; see location_widget.py
    elif category == 'location':
        return [i for i in list(range(1280, 4095))]
    else:
        return []

def sortOrder(code):
    _type = byCode(code)
    if _type == 'signtype': #4 character codes
        return eval("0x1{}".format(code))
    elif _type == 'handshape': #3 character codes
        return eval("0x20{}".format(code))
    elif _type == 'location': #3 location codes
        return eval("0x30{}".format(code))
    elif _type in ['changenature', 'changelocation', 'changemanner', 'contact']: #4 character codes
        return eval("0x4{}".format(code))
    elif _type == 'facehead': #3 character codes
        return eval("0x50{}".format(code))
    else:
        return eval("0x60fff") # place any errors at end of list

def changeLocationCode():
    return '1012'

def signTypeLabelCode():
    return '1003'

def handshapeLabelCode():
    return '14c'

def motionLabelCode():
    return '1010'

def faceheadLabelCode():
    return '32a'

def  handshapeGroupCode(code):
    dec = eval('0x{}'.format(code))
    if dec < 270:
        return '100'
    elif dec < 286:
        return '10e'
    elif dec < 324:
        return '11e'
    elif dec < 390:
        return '14c'
    elif dec < 420:
        return '186'
    elif dec < 442:
        return '1a4'
    elif dec < 461:
        return '1ba'
    elif dec < 501:
        return '1cd'
    elif dec < 517:
        return '1f5'
