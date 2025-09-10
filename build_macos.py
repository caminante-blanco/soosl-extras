#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A script to assist in building the final MacOS bundle4
"""

import os, sys
import shutil
import subprocess

from mainwindow import __version__, __build__

def createReleaseNotes(version):
    docs_dir = './docs'
    changelog_path = os.path.join(docs_dir, "CHANGELOG")
    changelog_lines = []
    with open(changelog_path, encoding='utf-8') as f:
        lines = f.readlines()
    append_ = False
    for l in lines:
        if l.startswith('## [') and not l.startswith('## [{}'.format(version)):
            append_ = False
        if append_ or l.startswith('## [{}'.format(version)):
            append_ = True
            changelog_lines.append(l)
    text = ''.join(changelog_lines)
    release_notes_path = os.path.join(docs_dir, "RELEASE_NOTES")
    with open(release_notes_path, 'w', encoding='utf-8') as f:
        f.write(text)
# createReleaseNotes(__version__)

f = open('macos.spec', encoding='utf-8')
orig_text = f.read()
f.close()
text = orig_text.replace('__VERSION__', __version__)
text = text.replace('__BUILD__', __build__)
f = open('macos.spec', 'w', encoding='utf-8')
f.write(text)
f.close()

__build_dir__ = os.path.abspath('build')
print(__build_dir__)
if os.path.exists(__build_dir__):
    shutil.rmtree(__build_dir__)

__dist_dir__ = os.path.abspath('dist/SooSL')
print(__dist_dir__)
if os.path.exists(__dist_dir__):
    shutil.rmtree(__dist_dir__)

subprocess.call(['pyinstaller', 'macos.spec', '--noconfirm'])

f = open('macos.spec', 'w', encoding='utf-8')
f.write(orig_text)
f.close()

app = './dist/SooSL.app'
if os.path.exists(app) and os.path.exists('./PkgInfo'):
    shutil.copy('./PkgInfo', app + '/Contents/PkgInfo')
# if os.path.exists(app):
    # shutil.rmtree(app + '/Contents/Frameworks')
    # os.remove(app + '/Contents/MacOS/include')
    # os.remove(app + '/Contents/MacOS/lib')
    # shutil.rmtree(app + '/Contents/Resources/include')
    # shutil.rmtree(app + '/Contents/Resources/lib')
# if os.path.exists(app) and os.path.exists('/Applications/App Wrapper 4.app'):
#     # This command is specific to a local developer machine and will fail in CI.
#     # It is used for code signing and notarization, which needs to be handled
#     # differently in an automated build environment.
#     os.system('/Users/Shared/awhelper /Users/timothygrove/soosl\-desktop/dist/SooSL.app')
