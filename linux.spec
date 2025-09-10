# -*- mode: python -*-

block_cipher = None

import os
import pyuca
pyuca_dir = os.path.dirname(pyuca.__file__)

extra_files = [
    ('codes_convert.txt', './'),
    ('codes_deprecate.txt', './'),
    (os.path.join(pyuca_dir, 'allkeys-8.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-9.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-10.0.0.txt'), 'pyuca'),
    ('docs/help/en', 'docs/help/en'),
    ('docs/COPYING', 'docs'),
    ('docs/README', 'docs'),
    ('docs/RELEASE_NOTES', 'docs'),
    ('components/facehead', 'components/facehead'),
    ('components/handshape', 'components/handshape'),
    ('components/changenature', 'components/changenature'),
    ('components/changelocation', 'components/changelocation'),
    ('components/changemanner', 'components/changemanner'),
    ('components/signtype', 'components/signtype'),
    ('components/contact', 'components/contact'),
    ('translations', 'translations'),
    #('/usr/lib/x86_64-linux-gnu/vlc/plugins', 'plugins'),
    #('ffmpeg_linux/soosl_ffmpeg', 'ffmpeg_linux'),
    #('ffmpeg_linux/COPYING.txt', 'docs/ffmpeg_linux'),
    #('ffmpeg_linux/SOOSL_README.txt', 'docs/ffmpeg_linux')
    ]

excludes = [
    'QtBluetooth', 
    'QtDesigner', 
    'QtHelp', 
    'QtLocation', 
    'QtOpenGL', 
    'QtMultimedia', 
    'QtMultimediaWidgets', 
    'QtPositioning', 
    'QtPositioningQuick', 
    'QtQml', 
    'QtQmlModels', 
    'QtQmlWorkerScript', 
    'QtQuick', 
    'QtQuickControls2', 
    'QtQuickParticles', 
    'QtQuickShapes', 
    'QtQuickTemplates2', 
    'QtQuickTest', 
    'QtQuickWidgets', 
    'QtWebChannel', 
    'QtWebSockets', 
    'QtTest', 
    'QtXml', 
    'QtXmlPatterns', 
    'QtSensors', 
    'QtNfc', 
    'QtSerialPort']
    
a = Analysis(['launcher.py'],
    binaries=[],
    datas=extra_files,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
    cipher=block_cipher)

exe = EXE(pyz,
    a.scripts,
    exclude_binaries=True,
    name='soosl',
    debug=False,
    strip=True,
    upx=False,
    console=False)  

#from pprint import pprint
#print('Binaries')
#pprint(a.binaries)
#print()
# print('Datas')
# pprint(a.datas)

excluded_binaries = []
excluded_datas = []
excluded_strings = [
    'QtBluetooth', 
    'QtDesigner', 
    'QtHelp', 
    'QtLocation', 
    'QtOpenGL', 
    'QtMultimedia', 
    'QtQml', 
    'QtWebSockets', 
    'QtTest', 
    'QtXml', 
    'QtSensors', 
    'QtNfc', 
    'QtSerialPort',
    'QtWebSockets', 
    'QtQuick',
    'QtPositioning', 
    'QtWebEngine', 
    'QtWebChannel',
    'QtTextToSpeech',
    'QtWebEngine',  
    'Qt5Bluetooth', 
    'Qt5Designer', 
    'Qt5Help', 
    'Qt5Location', 
    'Qt5OpenGL', 
    'Qt5Multimedia', 
    'Qt5Qml', 
    'Qt5WebSockets', 
    'Qt5Test', 
    'Qt5Xml', 
    'Qt5Sensors', 
    'Qt5Nfc', 
    'Qt5SerialPort',
    'Qt5WebSockets', 
    'Qt5Quick',
    'Qt5Positioning', 
    'Qt5WebEngine', 
    'Qt5WebChannel',
    'Qt5TextToSpeech',
    'Qt5WebEngine',  
    'libqsqlmysql',
    'libqsqlodbc', 
    'libqsqlpsql', 
    'libqtposition',
    'libvlc',
    'Qt/translations'
    ]
for e in excluded_strings:
    for b in a.binaries:
        if b[0].count(e):
            excluded_binaries.append(b)
    for d in a.datas:
        if d[0].count(e):
            excluded_datas.append(d)

a.binaries = TOC([x for x in a.binaries if x not in excluded_binaries])    
a.datas = TOC([x for x in a.datas if x not in excluded_datas])        

coll = COLLECT(exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='soosl')

print(exe.contents_directory)
