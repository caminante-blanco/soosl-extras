#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A script to assist in building .deb files
"""
#xenial = {'revision':'xenial1', 'distribution':'xenial', 'num': 1} # 16.04 LTS Xenial Xerus
#bionic = {'revision':'bionic1', 'distribution':'bionic', 'num': 2} # 18.04 LTS Bionic Beaver
focal = {'revision':'focal1', 'distribution':'focal', 'num': 5} # 20.04 LTS Focal Fossa
jammy = {'revision':'jammy1', 'distribution':'jammy', 'num': 6} # 22.04 LTS Jammy Jellyfish
#kinetic = {'revision':'kinetic1', 'distribution':'kinetic', 'num': 5}
noble = {'revision':'noble1', 'distribution':'noble', 'num': 7} #24.04 LTS Noble Numbat
debian = {'revision':'', 'distribution':'trixie', 'num': 13}

build_flavours = [debian] #, [debian, xenial, bionic, focal, jammy, kinetic, noble]
deploy = False

import os, sys
import shutil
import subprocess
import tarfile
import glob
from datetime import datetime, timezone

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

install_file = './Debian/debian_template/install'
with open(install_file, 'w', encoding='utf-8') as f:
    for line in [
        "bin/soosl usr/bin",
        "icons/hicolor/36x36/soosl.png usr/share/icons/hicolor/36x36",
        "applications/SooSL.desktop usr/share/applications"
        ]:
            f.write(line + '\n')
source_folder = './linux_dist/SooSL/soosl'
with open(install_file, 'a+') as f:
    for root, dirs, files in os.walk(source_folder):
        if files:
            for file in files:
                src = os.path.join(root, file)
                if src.count('egg-info'):
                    continue
                dst = os.path.dirname(src)
                dst = dst.replace('./linux_dist/SooSL/', 'opt/')
                src = src.lstrip('./')
                f.write(f'{src} {dst}\n')


for flavour in build_flavours:
    num = flavour.get('num')
    version = '{}.{}'.format(__version__, __build__)
    # if num > 0:
    #     version = '{}.{}'.format(version, num)
    createReleaseNotes(__version__)

    # install file is important as it lists all of the required source files and
    # their destinations in the install system.
    # NOTE: needs to amended with any source file changes.
    # use it here to get a list of source files.

    f = open(install_file, encoding='utf-8')
    lines = f.readlines()
    f.close()

    file_list = ['./' + l.split(' ')[0] for l in lines]
    # from pprint import pprint
    # pprint(file_list)
    # break

    if os.path.exists('./Debian/dist/'):
        shutil.rmtree('./Debian/dist/')

    # update changelog template
    header_str = 'soosl (SOOSLVERSION) SOOSLDISTRIB; urgency=medium'
    dt = datetime.now(timezone.utc)
    time_str = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    footer_str = ' -- Timothy Ward Grove (SooSL Developer) <tim_grove@sil.org>  {}'.format(time_str)

    changelog_template_pth = './Debian/debian_template/changelog'
    changelog_template_pth_copy = './Debian/debian_template/changelog_copy'
    if os.path.exists(changelog_template_pth):
        os.remove(changelog_template_pth)
    shutil.copy(changelog_template_pth_copy, changelog_template_pth)
    changelog_contents = ''
    with open(changelog_template_pth, encoding='utf-8') as f:
        changelog_contents = f.read()
    if not changelog_contents.count('soosl ({})'.format(__version__)):
        pth = './docs/CHANGELOG'
        with open(pth, encoding='utf-8') as f:
            lines = f.readlines()
        record = False
        change_lines = []
        for l in lines:
            l = l.strip()
            if l.startswith('## [{}]'.format(version)):
                record = True
                continue
            elif l.startswith('## ['):
                if record == True:
                    break
                record = False
            if record == True:
                change_lines.append(l)
        change_str = '\n'.join(change_lines).strip()
        change_str = change_str.replace('###', '  *')
        change_str = change_str.replace('-', '   -')

        changelog_str = '{}\n\n{}\n\n{}'.format(header_str, change_str, footer_str)
        changelog_contents = '{}\n\n{}'.format(changelog_str, changelog_contents)
        with open(changelog_template_pth, 'w', encoding='utf-8') as f:
            f.write(changelog_contents)

#for flavour in build_flavours: #see top of this file:
    # create a distribution directory
    rev = flavour.get('revision')
    _version = '{}'.format(version)
    sep = '-'
    # '-' treats revision as a package revision
    # '+' treats revision as part of version, requiring a source file archive
    if rev:
        _version = '{}{}{}'.format(version, sep, rev)

    debian_dist = './Debian/dist/soosl-{}'.format(_version)

    if not os.path.exists(debian_dist):
        os.makedirs(debian_dist)

    # copy some directories to distribution directory
    shutil.copytree('./Debian/debian_template', debian_dist + '/debian')
    shutil.copytree('./Debian/icons', debian_dist + '/icons')
    shutil.copytree('./Debian/applications', debian_dist + '/applications')
    shutil.copytree('./Debian/bin', debian_dist + '/bin')

    # copy in source files
    for f in file_list:
        if os.path.exists(f): # non-existant files have already been copied in above steps
            dir, file_name = os.path.split(f)
            if dir == '.':
                value = shutil.copy2(f, debian_dist)
            else:
                dst_dir = os.path.join(debian_dist, dir.lstrip('./'))
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)
                shutil.copy(f, dst_dir)

    # amend files
    pth = os.path.join(debian_dist, 'debian', 'files')
    with open(pth, encoding='utf-8') as f:
        contents = f.read()
    contents = contents.replace('SOOSLVERSION', _version)
    with open(pth, 'w', encoding='utf-8') as f:
        f.write(contents)

    # amend changelog
    pth = os.path.join(debian_dist, 'debian', 'changelog')
    with open(pth, encoding='utf-8') as f:
        changelog_contents = f.read()
    _distrib = flavour.get('distribution')
    changelog_contents = changelog_contents.replace('SOOSLDISTRIB', _distrib)
    changelog_contents = changelog_contents.replace('SOOSLVERSION', _version)
    with open(pth, 'w', encoding='utf-8') as f:
        f.write(changelog_contents)

    # update origianal template
    changelog_template_pth = './Debian/debian_template/changelog'
    changelog_contents = ''
    with open(changelog_template_pth, encoding='utf-8') as f:
        changelog_contents = f.read()
        changelog_contents = changelog_contents.replace('SOOSLVERSION', _version)
    if changelog_contents:
        with open(changelog_template_pth, 'w', encoding='utf-8') as f:
            f.write(changelog_contents)

    # create source file archives
    current_dir = os.getcwd()
    os.chdir(debian_dist)
    debian_archive = 'soosl_{}.orig.tar.xz'.format(_version)
    # if sep == '+': # archive required for each flavour as '+' treated as different version
    debian_archive = 'soosl_{}.orig.tar.xz'.format(version)
    debian_archive_dst = '../{}'.format(debian_archive)
    if not os.path.exists(debian_archive_dst):
        with tarfile.open(debian_archive, 'w:xz') as tf:
            for f in file_list:
                try:
                    tf.add(f)
                except:
                    print('not found', f)
        shutil.move(debian_archive, debian_archive_dst)

    # https://alioth-lists-archive.debian.net/pipermail/devscripts-devel/2014-May/002256.html
    # Issue: newer dkpg-deb uses xv compression on control file within .deb which currently prevents
    # upload to repo; this workaround forces it to use gzip compression.
    # I added this alias:
    # alias debuild="debuild --preserve-envvar PATH"
    # and modified dpkg-deb wrapper /usr/local/bin/dpkg-deb:
    # #!/bin/bash
    # /usr/bin/dpkg-deb -Zgzip $@

    # # create deb
    subprocess.call(['debuild', '-sa']) # '-sa' forces inclusion of full source

    os.chdir(current_dir)
    shutil.rmtree(debian_dist)

if deploy:
    import deploy_debian

## deployment statements
# dput -U pso:debian/buster soosl_0.9.1-210206_amd64.changes
# dput -U pso:ubuntu/xenial soosl_0.9.1-210206ubuntu1_amd64.changes
# dput -U pso:ubuntu/bionic soosl_0.9.1-210206ubuntu2_amd64.changes
# dput -U pso:ubuntu/focal soosl_0.9.1-210206ubuntu3_amd64.changes
