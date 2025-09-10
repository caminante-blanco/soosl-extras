# -*- mode: python -*-

block_cipher = None

import os
import pyuca
import text_unidecode

#following dirs not automatically pulled in by pyinstaller
pyuca_dir = os.path.dirname(pyuca.__file__)
text_unidecode_dir = os.path.dirname(text_unidecode.__file__)

extra_files = [
    ('codes_convert.txt', '.'),
    ('codes_deprecate.txt', '.'),
    (os.path.join(pyuca_dir, 'allkeys-8.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-9.0.0.txt'), 'pyuca'),
    (os.path.join(pyuca_dir, 'allkeys-10.0.0.txt'), 'pyuca'),
    (os.path.join(text_unidecode_dir, 'data.bin'), 'text_unidecode'),
    ('docs/VLC', 'docs/VLC'),
    ('docs/help/en', 'docs/help/en'),
    ('ffmpeg_macos/COPYING.txt', 'docs/ffmpeg_macos'),
    ('ffmpeg_macos/SOOSL_README.txt', 'docs/ffmpeg_macos'),
    #('docs/SooSL.help', 'SooSL.help'),
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
    ('VLC', 'VLC'),
    ('ffmpeg_macos/soosl_ffmpeg', 'ffmpeg_macos')
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
    'PyQt5.QtSerialPort']
    
excluded_binaries = [
    'QtWebSockets.so',
    'QtWebSockets', 
    'QtWebEngine.so', 
    'QtWebEngineCore.so', 
    'QtWebEngineWidgets.so', 
    'PyQt5/Qt/plugins/sqldrivers/libqsqlmysql.dylib',
    'PyQt5/Qt/plugins/sqldrivers/libqsqlodbc.dylib', 
    'PyQt5/Qt/plugins/sqldrivers/libqsqlpsql.dylib', 
    'PyQt5/Qt/plugins/position/libqtposition_cl.dylib', 
    'PyQt5/Qt/plugins/position/libqtposition_serialnmea.dylib',
    'PyQt5/Qt/plugins/position/libqtposition_positionpoll.dylib', 
    'PyQt5/Qt/plugins/position/libqtposition_geoclue.dylib', 
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtWebEngineCore', 
    'PyQt5.QtWebEngine', 
    'PyQt5.QtQuick3D',
    'QtPositioning', 
    'QtWebEngineWidgets', 
    'QtWebChannel', 
    'QtWebEngineCore', 
    'QtWebEngine',
    'sip'
    ]
    
excluded_data = [
    'VLC/plugins/libavcapture_plugin.dylib',
    'VLC/plugins/libqtsound_plugin.dylib',
    'VLC/plugins/libqtcapture_plugin.dylib',
    'VLC/plugins/libvda_plugin.dylib',
    # remove dvd access, requires libdvdcss.dll, which must be contained within the executable???
    'VLC/plugins/libdvdnav_plugin.dylib',
    'VLC/plugins/libdvdread_plugin.dylib',
    'VLC/plugins/.gitignore',
    'VLC/plugins/plugins.dat'
    ]

a = Analysis(['SooSL.py'],
    pathex=[],
    binaries=[],
    datas=extra_files,
    hiddenimports=['PyQt5.QtDBus', 'unidecode'],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher
    )
             
pyz = PYZ(a.pure, a.zipped_data,
    cipher=block_cipher,    )
             
exe = EXE(pyz,
    a.scripts,
    exclude_binaries=True,
    name='SooSL',
    debug=False,
    strip=False,
    upx=False,
    console=False)
         
a.binaries = TOC([x for x in a.binaries if x[0] not in excluded_binaries 
    and not x[0].startswith('QtQuick') 
    and not x[0].startswith('QtQml')])
    
a.datas = TOC([x for x in a.datas if x[0] not in excluded_data
    and not x[0].startswith('PyQt5/Qt/translations')])
    
coll = COLLECT(exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='SooSL')
    
app = BUNDLE(coll,
    name='SooSL.app',
    icon='soosl.icns',
    #bundle_identifier='org.sil.twg.SooSL',
    info_plist={
        'LSApplicationCategoryType': 'Education',
        'LSMinimumSystemVersion': '13.0',
        'NSHumanReadableCopyright': '© Copyright SIL International 2009 - 2025.',
        'NSHighResolutionCapable': 'No',
		'CFBundleDevelopmentRegion': 'English', 
		'CFBundleName': 'SooSL', 
		#'CFBundleHelpBookName': 'SooSL', 
		#'CFBundleHelpBookFolder': 'SooSL.help',
		'CFBundleShortVersionString': '__VERSION__',
		'CFBundleVersion': '__BUILD__',
		'CFBundleExecutable': 'SooSL',
		'CFBundleSignature': 'soos',
		'CFBundleIdentifier': 'org.sil.twg.SooSL'
		}
	)

