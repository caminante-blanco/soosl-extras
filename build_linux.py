#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A script to assist in building a standalone linux application
"""


import os
import shutil
import subprocess

from mainwindow import __version__, __build__

# def createReleaseNotes(version):
#     docs_dir = './docs'
#     changelog_path = os.path.join(docs_dir, "CHANGELOG")
#     changelog_lines = []
#     with open(changelog_path, encoding='utf-8') as f:
#         lines = f.readlines()
#     append_ = False
#     for l in lines:
#         if l.startswith('## [') and not l.startswith('## [{}'.format(version)):
#             append_ = False
#         if append_ or l.startswith('## [{}'.format(version)):
#             append_ = True
#             changelog_lines.append(l)
#     text = ''.join(changelog_lines)
#     release_notes_path = os.path.join(docs_dir, "RELEASE_NOTES")
#     with open(release_notes_path, 'w', encoding='utf-8') as f:
#         f.write(text)
# createReleaseNotes(__version__)

__build_dir__ = os.path.abspath('./linux_build')
if os.path.exists(__build_dir__):
    shutil.rmtree(__build_dir__)

__dist_dir__ = os.path.abspath('./linux_dist/SooSL/')
if os.path.exists(__dist_dir__):
    shutil.rmtree(__dist_dir__)

subprocess.call(['pyinstaller', 'linux.spec', f'--workpath={__build_dir__}', f'--distpath={__dist_dir__}'])

# move some things out of internal to soosl folder
src_folder = f'{__dist_dir__}/soosl/_internal'
dst_folder = f'{__dist_dir__}/soosl/'
for pth in ['codes_convert.txt',
        'codes_deprecate.txt',
        'components',
        'docs',
        #'plugins',
        #'ffmpeg_linux',
        # 'libvlc.so.5',
        # 'libvlccore.so.9',
        # 'libvlc_pulse.so.0',
        # 'libvlc_vdpau.so.0',
        # 'libvlc_xcb_events.so.0'
        ]:
    try:
        shutil.move(f'{src_folder}/{pth}', dst_folder)
    except:
         pass
# remove some things that didn't get cleaned up before
for pth in [f'{src_folder}/PyQt5/Qt5/qml',
    f'{src_folder}/PyQt5/Qt5/translations']:
        try:
             shutil.rmtree(pth)
        except:
             pass
