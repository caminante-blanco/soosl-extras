# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import pyuca
pyuca_dir = os.path.dirname(pyuca.__file__)
		
added_files = [
    ('.\\soosl.ico', '.'),
	('.\\soosl_uninstall.ico', '.'),
	('.\\codes_convert.txt', '.'),
	('.\\codes_deprecate.txt', '.'),
	(os.path.join(pyuca_dir, 'allkeys-8.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-9.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-10.0.0.txt'), 'pyuca'),
	('.\\docs\\help\\en', 'docs\\help\\en'),
	('.\\docs\\COPYING', 'docs'),
	('.\\docs\\README', 'docs'),
	('.\\docs\\RELEASE_NOTES', 'docs'),
	('.\\components\\facehead', 'components\\facehead'),
	('.\\components\\handshape', 'components\\handshape'),
	('.\\components\\changenature', 'components\\changenature'),
    ('.\\components\\changelocation', 'components\\changelocation'),
    ('.\\components\\changemanner', 'components\\changemanner'),
    ('.\\components\\signtype', 'components\\signtype'),
    ('.\\components\\contact', 'components\\contact'),
    ('.\\translations', 'translations'),
    ('.\\plugins', 'plugins'),
    ('.\\docs\\VLC', 'docs\\VLC'),
    ('.\\libvlc.dll', '.'),
    ('.\\libvlccore.dll', '.'),
    ('.\\ffmpeg_win32\\soosl_ffmpeg.exe', 'ffmpeg_win32'),
    ('.\\ffmpeg_win32\\COPYING.txt', 'docs\\FFmpeg'),
    ('.\\ffmpeg_win32\\SOOSL_README.txt', 'docs\\FFmpeg'), 
    ('.\\windows7\\api-ms-win*', '.')
	]

excludes = [
    'PyQt5.QtBluetooth', 
    'PyQt5.QtDesigner', 
    'PyQt5.QtHelp', 
    'PyQt5.QtLocation', 
    'PyQt5.QtOpenGL', 
    'PyQt5.QtMultimedia', 
    'PyQt5.QtMultimediaWidgets', 
    'PyQt5.QtPositioning', 
    'PyQt5.QtPositioningQuick', 
    'PyQt5.QtQml', 
    'PyQt5.QtQmlModels', 
    'PyQt5.QtQmlWorkerScript', 
    'PyQt5.QtQuick', 
    'PyQt5.QtQuickControls2', 
    'PyQt5.QtQuickParticles', 
    'PyQt5.QtQuickShapes', 
    'PyQt5.QtQuickTemplates2', 
    'PyQt5.QtQuickTest', 
    'PyQt5.QtQuickWidgets', 
    'PyQt5.QtWebChannel', 
    'PyQt5.QtWebSockets', 
    'PyQt5.QtTest', 
    'PyQt5.QtXml', 
    'PyQt5.QtXmlPatterns', 
    'PyQt5.QtSensors', 
    'PyQt5.QtNfc', 
    'PyQt5.QtSerialPort'
    ]

a = Analysis(['SooSL.py'],
             pathex=['C:\\Users\\tim_g\\soosl-desktop'],
             binaries=[],
             datas=added_files,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=excludes,
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='SooSL_094',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='.\\soosl.ico',
          version='.\\version.rc')

excluded_binaries = [
    'Qt5Qml.dll', 
    'Qt5Quick.dll', 
    'Qt5WebSockets.dll', 
    'Qt5Sensors.dll', 
    'opengl32sw.dll', 
    'libvlc.dylib',
    'libvlccore.dylib',
    'PyQt5\\Qt\\plugins\\sqldrivers\\qsqlmysql.dll', 
    'PyQt5\\Qt\\plugins\\sqldrivers\\qsqlodbc.dll', 
    'PyQt5\\Qt\\plugins\\sqldrivers\\qsqlpsql.dll'
    ]
    
excluded_data = [
    # remove dvd access, requires libdvdcss.dll, which must be contained within the .exe???
    #'plugins\\access\\libdvdnav_plugin.dll',
    #'plugins\\access\\libdvdread_plugin.dll',
    #'plugins\\.gitignore',
    'plugins\\plugins.dat'
    ]

a.binaries = TOC([x for x in a.binaries if x[0] not in excluded_binaries])
a.datas = TOC([x for x in a.datas if x[0] not in excluded_data
    and not x[0].startswith('PyQt5/Qt/translations')])

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='SooSL')
