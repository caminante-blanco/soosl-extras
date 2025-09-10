# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['launcher.py'],
             pathex=['.'],
             binaries=[],
             datas=[
                 ('components', 'components'),
                 ('icons', 'icons'),
                 ('translations', 'translations'),
                 ('text_unidecode', 'text_unidecode'),
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
          a.binaries,
          a.zipfiles,
          a.datas,
          name='SooSL',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='icons/hicolor/36x36/soosl.png',
          version='version.rc')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='SooSL')
