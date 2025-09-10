#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A script to assist with deploying linux distributions
"""

import os, sys
import shutil
import subprocess
import glob

current_dir = os.getcwd()
os.chdir('./Debian/dist')

changes = glob.glob('*.changes')
for change in changes:
    #repo = 'pso:ubuntu/focal'
    repo = 'pso:debian/trixie'
    if change.count('jammy'):
        repo = 'pso:ubuntu/jammy'
    elif change.count('noble'):
        repo = 'pso:ubuntu/noble'
    elif change.count('focal'):
        repo = 'pso:ubuntu/focal'
    subprocess.call(['dput', '-U', repo, change]) # F=fuller upload logs

os.chdir(current_dir)

## deployment statements
# dput -U pso:debian/buster soosl_0.9.1-210206_amd64.changes
# dput -U pso:ubuntu/xenial soosl_0.9.1-210206ubuntu1_amd64.changes
# dput -U pso:ubuntu/bionic soosl_0.9.1-210206ubuntu2_amd64.changes
# dput -U pso:ubuntu/focal soosl_0.9.1-210206ubuntu3_amd64.changes
