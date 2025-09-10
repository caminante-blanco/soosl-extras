# -*- mode: python ; coding: utf-8 -*-

# A good practice is to let PyInstaller discover the python dependencies automatically
# by just specifying the entry-point script. We will specify the data files
# that are not automatically included.

block_cipher = None

a = Analysis(['launcher.py'],
             pathex=['.'],
             binaries=[],
             datas=[
                 ('components', 'components'),
                 ('icons', 'icons'),
                 ('translations', 'translations'),
                 ('text_unidecode', 'text_unidecode'),
                 ('PkgInfo', '.'),
                 ('soosl.py', '.'),
                 ('mainwindow.py', '.'),
                 ('csaw.py', '.')
             ],
             hiddenimports=['pkg_resources.py2_warn'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
          name='SooSL',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='icons/hicolor/36x36/soosl.png')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='SooSL')

app = BUNDLE(coll,
             name='SooSL.app',
             icon='icons/hicolor/36x36/soosl.png',
             bundle_identifier=None,
             info_plist={
                 'NSHighResolutionCapable': 'True'
             })
