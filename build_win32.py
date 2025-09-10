#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A script to assist in building the final Win32 application
"""
#deploy = False
deploy = False
deploy_at_home = False

import os
import shutil
import subprocess
import re

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
createReleaseNotes(__version__)

def createVersionRC(version, build):
    MAJOR, MINOR, MICRO = version.split('.')
    version_rc = f"""
        # UTF-8
        # For more details about fixed file info 'ffi' see:
        # http://msdn.microsoft.com/en-us/library/ms646997.aspx
        VSVersionInfo(
        ffi=FixedFileInfo(
        # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
        # Set not needed items to zero 0.
        filevers=({MAJOR}, {MINOR}, {MICRO}, 0),
        prodvers=({MAJOR}, {MINOR}, {MICRO}, 0),
        # Contains a bitmask that specifies the valid bits 'flags'r
        mask=0x3f,
        # Contains a bitmask that specifies the Boolean attributes of the file.
        flags=0x0,
        # The operating system for which this file was designed.
        # 0x4 - NT and there is no need to change it.
        OS=0x4,
        # The general type of file.
        # 0x1 - the file is an application.
        fileType=0x1,
        # The function of the file.
        # 0x0 - the function is not defined for this fileType
        subtype=0x0,
        # Creation date and time stamp.
        date=(0, 0)
        ),
        kids=[
        StringFileInfo(
        [
        StringTable(
            u'040904B0',
            [StringStruct(u'CompanyName', u'SIL International'),
            StringStruct(u'FileDescription', u'Sign language dictionary software'),
            StringStruct(u'FileVersion', u'{MAJOR}.{MINOR}.{MICRO}.{build}'),
            StringStruct(u'InternalName', u'SooSL™'),
            StringStruct(u'LegalCopyright', u'Copyright (c) SIL International'),
            StringStruct(u'OriginalFilename', u'SooSL_{MAJOR}{MINOR}{MICRO}.exe'),
            StringStruct(u'ProductName', u'SooSL™'),
            StringStruct(u'ProductVersion', u'{MAJOR}.{MINOR}.{MICRO} ({build})')])
        ]), 
        VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
        ]
        )
        """
    version_rc = version_rc.strip()
    version_rc = version_rc.replace('    ', '')
    with open('./version.rc', 'w', encoding='utf-8') as f:
        f.write(version_rc)
createVersionRC(__version__, __build__)

__build_dir__ = os.path.abspath('./build')
if os.path.exists(__build_dir__):
    shutil.rmtree(__build_dir__)

__dist_dir__ = os.path.abspath('./dist/SooSL/')
if os.path.exists(__dist_dir__):
    shutil.rmtree(__dist_dir__)

__output_dir__ = os.path.abspath('./InnoSetup')
__copyright__ = '2009 - 2025'
__exe_name__ = 'SooSL_{}.exe'.format(__version__.replace('.', ''))

subprocess.call(['pyinstaller', 'win32.spec', '--noconfirm', '--onefile'])

if deploy:
    # update InnoSetup script
    iss = './InnoSetup/soosl.iss'
    f = open(iss, encoding='utf-8')
    old_iss = f.read()
    f.close()

    version_str = re.findall('#define MyAppVersion ".+"', old_iss)[0]
    new_version_str = '#define MyAppVersion "{}"'.format(__version__)

    build_str = re.findall('#define MyBuildNumber ".+"', old_iss)[0]
    new_build_str = '#define MyBuildNumber "{}"'.format(__build__)

    build_dir = re.findall('#define MyBuildDir ".+"', old_iss)[0]
    new_build_dir = '#define MyBuildDir "{}"'.format(__dist_dir__)

    lang_dir = re.findall('#define MyLangDir ".+"', old_iss)[0]
    new_lang_dir = '#define MyLangDir "{}"'.format(__dist_dir__)

    exe_name = re.findall('#define MyAppExeName ".+"', old_iss)[0]
    new_exe_name = '#define MyAppExeName "{}"'.format(__exe_name__)

    output_dir = re.findall('OutputDir=.+', old_iss)[0]
    new_output_dir = 'OutputDir={}'.format(__output_dir__)

    copyright_str = re.findall('VersionInfoCopyright=.+', old_iss)[0]
    new_copyright_str = 'VersionInfoCopyright={}'.format(__copyright__)

    product_version = re.findall('VersionInfoProductVersion=.+', old_iss)[0]
    new_product_version = 'VersionInfoProductVersion={}'.format(__version__)

    new_iss = old_iss.replace(version_str, new_version_str)
    new_iss = new_iss.replace(build_str, new_build_str)
    new_iss = new_iss.replace(build_dir, new_build_dir)
    new_iss = new_iss.replace(lang_dir, new_lang_dir)
    new_iss = new_iss.replace(output_dir, new_output_dir)
    new_iss = new_iss.replace(copyright_str, new_copyright_str)
    new_iss = new_iss.replace(product_version, new_product_version)
    new_iss = new_iss.replace(exe_name, new_exe_name)

    f = open(iss, 'w', encoding='utf-8')
    f.write(new_iss)
    f.close()

    if deploy_at_home:
        # build InnoSetup installer
        # InnoSetup path must be added environment variables (path) for the following to work
        iss = os.path.abspath(iss)
        print(iss)
        subprocess.call(['iscc', iss])
        print('complete')