#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Copyright SIL International 2009 - 2025.

This file is part of SooSL™.

SooSL™ is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

SooSL™ is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with SooSL™.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import glob
import shutil
import sys
import io
import copy
import json
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
import tempfile
from datetime import datetime, timezone, timedelta
from dateutil import tz, parser
import platform
import psutil
import time
from operator import itemgetter
import requests
from pyuca import Collator
from pathlib import Path

from filelock import Timeout, SoftFileLock
# https://filelock.readthedocs.io/en/latest/

import json, stat
from slugify import slugify
import re
import unicodedata
from pprint import pprint

#from components.component_descriptions import ComponentDescriptions
#from components import component_type

from PyQt5.QtSql import QSqlQuery
from PyQt5.QtSql import QSqlDatabase

from PyQt5.QtCore import QObject
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QProcess

from PyQt5.QtWidgets import QMessageBox, QPushButton
from PyQt5.QtWidgets import qApp

from PyQt5.QtGui import QIcon, QMovie, QPixmap
import csaw as csaw
from project import Dialect
from project import Project
from project import ZooZLProject
from project import Sense
from project import GrammarCategory
from project import WrittenLanguage
from project_updater import ProjectUpdater as PU

from media_object import MediaObject
from media_wrappers import PictureWrapper as Picture
from media_wrappers import VideoWrapper as Video
from media_saver import MediaSaver
from importer import Importer, IMPORT_SUFFIX
from exporter import Exporter
from continue_editing_dlg import ContinueEditingDlg
from webproject_upload_dlg import WebProjectUploadDlg
from project_merger import ReconcileChangesDialog, MergeDialog

# class FileDeleteError(Exception):
#     def __init__(self, message):
#         self.message = message

LOCK_EXPIRES = 1800 # seconds (30 min)
## Change value in SooSL.ini for testing
## max_secs = settings.value('lockTimeoutSeconds', LOCK_EXPIRES)
LOCK_UPDATE_INTERVAL = 540000 # mseconds (9 min) # 3 updates before expiry time
USER_UPDATE_INTERVAL = 300 # mseconds (300ms)

class ProjectManager(QObject):
    """an editor class for SooSL dictionary projects
    """
    project_closed = pyqtSignal()
    project_changed = pyqtSignal()
    project_reloaded = pyqtSignal()
    signs_found = pyqtSignal(list)
    show_warning = pyqtSignal(str, str) #dialog
    show_info = pyqtSignal(str, str) #dialog
    show_message = pyqtSignal(str) #status bar
    lang_selection_change = pyqtSignal()
    search_lang_change = pyqtSignal()
    lang_list_changed = pyqtSignal()
    font_size_change = pyqtSignal(int, int)
    font_family_change = pyqtSignal(int, str)
    lang_order_change = pyqtSignal(list)
    dirty = pyqtSignal(bool)
    save_finished = pyqtSignal()
    abort_save = pyqtSignal()
    newSentence = pyqtSignal(tuple)
    newSense = pyqtSignal(Sense)

    save_progress = pyqtSignal(str, int, float, bool)
    def __init__(self, parent=None):
        super(ProjectManager, self).__init__(parent)

        self.fileSystemWatcher = MyPathWatcher()
        self.fileSystemWatcher.projectChanged.connect(self.onProjectChanged)

        #locks
        self.sign_locks = []
        self.project_locks = [] #to keep track of locks acquired during this session
        self.projectLock = None
        self.fullProjectLock = None
        self.projectIDLock = None # required in the rare/improbable case that the same user on the same machine is attempting to
        # upload different projects with the same project ID from different SooSL instances.
        self.userLock = None

        # self.acquired_project_lock = False
        # self.acquired_full_project_lock = False
        # self.acquired_project_id_lock = False

        self.lock_update_timer = QTimer(self)
        self.lock_update_timer.setInterval(LOCK_UPDATE_INTERVAL) #writes username and timestamp to lockfile on timeout.
        self.lock_update_timer.timeout.connect(self.updateLocks)
        self.user_update_timer = QTimer(self)
        self.user_update_timer.setInterval(USER_UPDATE_INTERVAL) #writes username and timestamp to lockfile on timeout.
        self.user_update_timer.timeout.connect(self.updateUserLock)

        self.signs = []
        self.sign = None
        self.sense = None
        self.delete_flag = False
        self.selected_lang_ids = [1]
        self.search_lang_id = 1
        self.editing = False
        self.edit_widget = None

        ##NOTE: deleted files are not removed immediately but saved till dictionary closed
        ## on file delete, its path is added to list; on file add it is removed from this list if present
        ## if not deleted for some reason on dictionary closure, its path is written to a file in the dictionary directory,
        ## and used to populate this list the next time the dictionary is opened.
        self.possible_removals = []
        self.project = None
        self.prev_project_filename = None
        self.known_project_info_dict = {} # key: file_path; value: [read/write?, dictionary title, project id]
        self.tempIds = []
        self.session_id = None

    def removeExpiredLocks(self):
        self.removeExpiredUserLocks()
        self.removeExpiredProjectLocks()
        self.removeExpiredSignLocks()

    def updateLock(self, lock):
        if lock and os.path.exists(lock.lock_file) and self.isMyLock(lock):
            self.writeLockData(lock)

    def updateLocks(self):
        for lock in self.project_locks:
            self.updateLock(lock)
        for lock in self.sign_locks:
            self.updateLock(lock)
        # for lock in [self.projectLock,
        #     self.fullProjectLock,
        #     self.projectIDLock,
        #     *self.sign_locks]:
        #        self.updateLock(lock)

    def updateUserLock(self):
        self.updateLock(self.userLock)

    def removeExpiredProjectLocks(self):
        qdir = QDir(qApp.instance().getWorkingDir())
        qdir.setFilter(QDir.Files)
        project_locks = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock']
        qdir = QDir(self.project.project_dir)
        qdir.setFilter(QDir.Files)
        project_locks.extend([qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock'])
        expired_lock_files = [lf for lf in project_locks if self.lockFileHasExpired(lf)]
        for elf in expired_lock_files:
            try:
                os.remove(elf)
            except:
                try:
                    os.remove(elf)
                except:
                    pass

    def removeExpiredSignLocks(self):
        signs_dir = '{}/_signs'.format(self.project.project_dir)
        qdir = QDir(signs_dir)
        qdir.setFilter(QDir.Files)
        lock_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock']
        if lock_files:
            expired_lock_files = [lf for lf in lock_files if self.lockFileHasExpired(lf)]
            for elf in expired_lock_files:
                try:
                    os.remove(elf)
                except:
                    try:
                        os.remove(elf)
                    except:
                        pass

    def removeExpiredUserLocks(self):
        qdir = QDir(self.project.project_dir)
        qdir.setFilter(QDir.Files)
        lock_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.user']
        if lock_files:
            expired_lock_files = [lf for lf in lock_files if self.userLockFileInactive(lf)]
            for elf in expired_lock_files:
                try:
                    os.remove(elf)
                except:
                    try:
                        os.remove(elf)
                    except:
                        pass

    def writeLockData(self, lock):
        o = {}
        user, pid = self.session_id.rsplit('_', 1)
        o['node'] = platform.node()
        o['username'] = os.path.basename(user)
        o['pid'] = pid
        o['timestamp'] = datetime.now(timezone.utc).timestamp()
        with io.open(lock.lock_file, 'w', encoding='utf-8') as f:
            json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)

    def splitExt(self, file_path):
        try:
            base, ext = os.path.splitext(file_path)
        except:
            return file_path, ''
        else:
            if ext.lower() == '.enc' and file_path.lower().endswith('.sqlite.enc'): #old project
                ext = '.sqlite.enc'
                base = file_path.replace(ext, '')
            return base, ext

    def lowerExt(self, file_path):
        # return file path with extension lower case
        # safe with directories or files without extensions
        base, ext = self.splitExt(file_path)
        file_path = base + ext.lower()
        return file_path

    def getKnownProjectInfo(self, file_path):
        file_path = file_path.replace('\\', '/')
        if not os.path.exists(file_path): #removed from filesystem outside of SooSL while SooSL open
            return []
        p = QDir.cleanPath(file_path)
        p = self.lowerExt(p)
        info = self.known_project_info_dict.get(p, [])
        return info

    def setKnownProjectInfo(self, _path, perm=None, proj_name=None, proj_id=None, proj_version=None, proj_datetime=None):
        """add read/write permission, project name, and project id for a project file
           or directory of project files to a 'known projects' dictionary."""

        included =  ['.json', '.zoozl', '.sqlite', '.sqlite.enc']
        excluded = ['error.log', 'crash.log', 'import_crash.json', 'startup.log', 'running.log']
        paths = None
        _path = _path.replace('\\', '/')
        if os.path.isdir(_path):
            qdir = QDir(_path)
            qdir.setFilter(QDir.Files)
            paths = [qdir.absoluteFilePath(entry) for entry in qdir.entryList()]
        else:
            paths = [_path]
        paths = [p for p in paths if self.splitExt(p)[1].lower() in included and os.path.basename(p).lower() not in excluded]
        for p in paths:
            p = self.lowerExt(p)
            info = self.getKnownProjectInfo(p)
            if not info:
                try:
                    name, _id, _version, _datetime = self.getProjectNameIdVersionDatetime(p)
                except:
                    pass
                else:
                    info = [self.isReadWrite(p), name, _id, _version, _datetime]
            #keyword args take precendence
            if info:
                if perm or perm is False:
                    info[0] = perm
                if proj_name:
                    info[1] = proj_name
                if proj_id:
                    info[2] = proj_id
                if proj_version:
                    info[3] = proj_version
                if proj_datetime:
                    info[4] = proj_datetime
                self.known_project_info_dict[p] = info

    def updateKnownProjectInfoName(self, file_path, new_name):
        """used with project files after a change of project name"""
        self.setKnownProjectInfo(file_path, proj_name=new_name)

    def updateKnownProjectInfoPermission(self, file_path, permission):
        """used with zoozl exports (and project imports) when changing permission"""
        # not often needed with project imports, except when overwriting an existing
        # project with a different read/write permission
        #file_path = file_path.replace('-replace.json', '.json')
        self.setKnownProjectInfo(file_path, perm=permission)

    def updateKnownProjectInfoId(self, file_path, project_id):
        """used with project files after a change of project id"""
        # currently not really needed as id doesn't change, but includee for completeness
        self.setKnownProjectInfo(file_path, proj_id=project_id)

    def updateKnownProjectInfoVersion(self, file_path, project_version):
        """used with project files after a change of project version"""
        self.setKnownProjectInfo(file_path, proj_version=project_version)

    def updateKnownProjectInfoDatetime(self, file_path, project_datetime):
        """used with project files after a change of project datetime"""
        self.setKnownProjectInfo(file_path, proj_datetime=project_datetime)

    def updateImportExportDirectories(self, dirpath):
        _dir = dirpath.replace('\\', '/')
        settings = qApp.instance().getSettings()
        _dirs = settings.value('ImportExportDirectories', [])
        if _dir not in _dirs:
            _dirs.insert(0, _dir)
            self.setKnownProjectInfo(dirpath)
        else: #ensure directory is first in the order
            _dirs = sorted(list(set(_dirs)), key=lambda x: x==_dir, reverse=True)
        settings.setValue('ImportExportDirectories', _dirs)
        settings.sync()

    @property
    def current_project_filename(self):
        if self.project:
            return self.project.filename
        return None

    def onAmended(self):
        _bool = qApp.instance().dirty()
        self.dirty.emit(_bool)

    def onDeleteSign(self, _bool):
        self.delete_flag = _bool

    def ableToEdit(self):
        """a flag used to dictate read-only or read-write status for a project database.
        """
#         if self.current_project_filename == 'new':
#             return True
        return self.__authorizeUser()

    def enterEditingMode(self):
        self.editing = True

    def cleanupNewSign(self):
        # if a new sign has been started but cancelled before anything saved,
        # file in filesystem will be empty; remove
        if self.sign.new:
            sign_file = '{}/_signs/{}.json'.format(self.project.project_dir, self.sign.id)
            if os.path.exists(sign_file): # and not os.path.getsize(sign_file):
                lock_file = '{}/_signs/{}.json.lock'.format(self.project.project_dir, self.sign.id)
                self.releaseSignLock(lock_file)
                os.remove(sign_file)
        self.sign = None

    def leaveEditingMode(self):
        self.inactivity_timer.stop()
        self.editing = False
        try:
            if self.sign.new:
                self.sign = {}
                self.signs = [self.sign]
                self.signs_found.emit(self.signs)
        except:
            self.sign = {}
            self.signs = [self.sign]
            self.signs_found.emit(self.signs)

    def getProjectList(self, _dir=None):
        """get list of dictionary databases which this application knows about
        """
        projects = []
        project_directories = []
        if not _dir: #default; get all dictionaries this app knows about
            project_directories = self.getProjectLocations()
        else: # get projects found in a specific directory
            project_directories = [_dir]
        if not project_directories:
            return []
        project_directories = [x.replace('\\', '/') for x in project_directories]
        project_directories = set(project_directories)
        for _dir in project_directories:
            _dir = QDir(_dir)
            _dir.setFilter(QDir.Dirs|QDir.NoDotAndDotDot)
            project_dirs = _dir.entryList()
            project_dirs = [QDir(_dir.filePath(name)) for name in project_dirs]
            for qdir in project_dirs:
                qdir.setFilter(QDir.Files)
                files = qdir.entryList()
                _projects = [f for f in files if f == '{}.json'.format(qdir.dirName())]
                if not _projects:
                    _projects = [f for f in files if f.endswith('.sqlite')]
                if _projects:
                    _projects = ['{}/{}'.format(qdir.absolutePath(), pth) for pth in _projects]
                    projects.extend(_projects)
        projects = list(set(projects)) #could have duplicates if a dictionary directory is a subdirectory of another
        return projects

    def amendProjectList(self, project_file, remove=False): #adding to list is the default
        project_dir = os.path.dirname(os.path.dirname(project_file)).replace('\\', '/')
        project_dirs = self.getProjectLocations()
        if not remove:
            if project_dir not in project_dirs:
                project_dirs.append(project_dir)
                self.setProjectLocations(project_dirs)
        else: #first check if any other projects are in this directory before removing
            projects = self.getProjectList(project_dir)
            if len(projects) == 0:
                project_dirs.remove(project_dir)
                self.setProjectLocations(project_dirs) ##NOTE: not sure if this is doing anything; REVIEW
            self.removeProjectSettings(project_file)

    def removeProjectSettings(self, project_file):
        project_dir = os.path.dirname(project_file).replace('\\', '/')
        project_dir = project_dir.lstrip('/')
        settings = qApp.instance().getSettings()
        text = 'ProjectSettings/{}'.format(project_dir)
        for key in settings.allKeys():
            if key.startswith(text):
                settings.remove(key)
        settings.sync()

    def getCurrentUILang(self):
        settings = qApp.instance().getSettings()
        lang_name = settings.value('displayLang', 'en English')
        try:
            trans_file, timestamp = qApp.instance().translation_dict.get(lang_name)
        except:
            return 'en'
        lang = os.path.splitext(os.path.basename(trans_file))[0]
        return lang

    def getSelectedLanguages(self):
        return [lang for lang in self.getLangs() if lang[0] in self.selected_lang_ids]

    def getSooSLVersion(self):
        settings = qApp.instance().getSettings()
        soosl_version = settings.value("Version", '0.0.0')
        return soosl_version

    def getProjectSooSLVersion(self):
        if self.project:
            return self.project.soosl_version
        return self.getSooSLVersion()

    def getProjectDirFromImport(self, zoozl):
        anyfile = ZipFile(zoozl, 'r').infolist()[0].filename
        anyfile = anyfile.replace('\\', '/')
        _dir = anyfile.split('/')[0]
        return _dir

    def getProjectFile(self, dir_path):
        if not dir_path:
            return None
        name = os.path.basename(dir_path)
        #project_path = '{}/{}.json'.format(dir_path, name)
        project_path = os.path.join(dir_path, (name + '.json'))
        if not os.path.exists(project_path):
            #project_path = '{}/{}.sqlite'.format(dir_path, name)
            project_path = os.path.join(dir_path, (name + '.sqlite'))
            if not os.path.exists(project_path):
                #project_path = '{}/{}.sqlite.enc'.format(dir_path, name)
                project_path = os.path.join(dir_path, (name + '.sqlite.enc'))
        if os.path.exists(project_path):
            return project_path
        return None

    def getProjectName(self, file_path):
        info = self.getKnownProjectInfo(file_path)
        if info and info[1]:
            return info[1]
        _id = None
        try:
            _id = self.getProjectNameIdVersionDatetime(file_path)[0]
        except:
            return None
        else:
            return _id

    def getProjectId(self, file_path):
        info = self.getKnownProjectInfo(file_path)
        if info and info[2]:
            return info[2]
        _id = None
        try:
            _id = self.getProjectNameIdVersionDatetime(file_path)[1]
        except:
            return None
        else:
            return _id

    def getProjectLogo(self, project=None):
        if not project:
            project = self.project
        logo = f'{project.project_dir}/project_logo.png'
        if os.path.exists(logo):
            return logo
        else:
            return ''

    def saveProjectLogo(self, logo_filename):
        dst = f'{self.project.project_dir}/project_logo.png'
        if logo_filename: # add
            ffmpeg = qApp.instance().getFFmpeg()
            args = ['-stdin', '-y', '-i', logo_filename, dst]
            pxm = QPixmap(logo_filename)
            if pxm.height() > 200:
                args = ['-stdin', '-y', '-i', logo_filename, '-vf', 'scale=200:-2', dst]
            process = QProcess()
            process.start(ffmpeg, args)
            process.waitForFinished(msecs=-1)
        elif os.path.exists(dst): # no filename; remove existing project logo file
            os.remove(dst)

    def getProjectNameIdVersionDatetime(self, filename, fresh=False):
        """Get the name, id, version and modified datetime for a dictionary based on it's database's full pathname.
           Set fresh=True if you want to get the values directly from the file and not the know info dictionary.
        """
        filename = qApp.instance().pm.lowerExt(filename) # ensure any comparisons are case insensitive
        known = self.getKnownProjectInfo(filename)
        if known and not fresh:
            name = known[1]
            _id = known[2]
            _version = None
            try:
                _version = known[3]
            except:
                pass
            _datetime = None
            try:
                _datetime = known[4]
            except:
                pass
            if name  and _id:
                return (name, _id, _version, _datetime)

        if filename and os.path.exists(filename):
            if filename.endswith('.sqlite'):
                name = os.path.splitext(os.path.basename(filename))[0]
                id = self.sooslSlugify(name)
                return (name, id, None, '') #_datetime)
            elif filename.endswith('.sqlite.enc'):
                name = os.path.splitext(os.path.splitext(os.path.basename(filename))[0])[0]
                id = self.sooslSlugify(name)
                return (name, id, None, '') #_datetime)
            elif filename.endswith('.json'):
                with io.open(filename, 'r', encoding='utf-8') as f:
                    try:
                        j = json.load(f)
                    except:
                        return (None, None, None, None)
                    else:
                        name = j.get('projectName', '')
                        id = j.get('projectId', self.sooslSlugify(name))
                        _version = j.get('versionId', '')
                        _datetime = j.get('modifiedDateTime', '')
                        return (name, id, _version, _datetime)
            elif filename.endswith('.zoozl'): #zipped archive
                full_filename = filename
                try:
                    z = ZipFile(filename, 'r')
                except:
                    return ('','','','')
                else:
                    info = z.infolist()#[:10] #10 is random; no need to check entire list; dictionary file(s) will be in the first few items
                    info = [i for i in info if i.filename.count('/') < 2 and
                        ((i.filename.endswith('.json') or i.filename.endswith('.sqlite') or i.filename.endswith('.sqlite.enc')))]
                    try:
                        filename = info[0].filename
                    except:
                        return ('','','','')
                    else:
                        if len(info) > 1: # json and sqlite versions
                            info_json = [i for i in info if i.filename.endswith('.json')]
                            if info_json: ##  NOTE: this assumes only one .json file
                                ## this should be true, but should I check and verify for the true dictionary file?
                                filename = info_json[0].filename
                        tmp_file = os.path.join(qApp.instance().getTempDir(), os.path.basename(filename))
                        with open(tmp_file, 'wb') as f:
                            f.write(z.read(filename))
                        name, id, _version, _datetime = self.getProjectNameIdVersionDatetime(tmp_file)
                        if not id:
                            id = self.sooslSlugify(name)
                        # if not _datetime: #if no datetime recorded (old projects) use datetime from zoozl file itself
                        #     _datetime = datetime.fromtimestamp(os.path.getmtime(full_filename), tz=timezone.utc).isoformat()
                        os.remove(tmp_file)
                        return (name, id, _version, _datetime)
            else:
                return ('','','','')
        else:
                return ('','','','')

    def getScreenSizeForWidget(self, widget):
        _pos = widget.mapToGlobal(widget.rect().center())
        return qApp.screenAt(_pos).availableSize()

    def sooslSlugify(self, text):
        if not text:
            return ''
        try:
            slug = slugify(text)
        except:
            slug = self.linux_slugify(text)
        return slug

    def linux_slugify(self, string):
        """
        python3-slugify is failing for Ubuntu
        let's find the problem
        """
        ## Error: name 'unicode' is not defined
        # return re.sub(r'[-\s]+', '-',
        #         unicode(
        #             re.sub(r'[^\w\s-]', '',
        #                 unicodedata.normalize('NFKD', string)
        #                 .encode('ascii', 'ignore'))
        #             .strip()
        #             .lower()))
        #
        _string = ''
        if string:
            try:
                _string = unicodedata.normalize('NFKD', string)
            except:
                return string
            else:
                _string = _string.encode('ascii', 'ignore').strip().lower().decode('ascii')
                _string = re.sub(r'[^\w\s-]', '', _string)
                _string = re.sub(r'[-\s]+', '-', _string)
        return _string

    def getCurrentProjectName(self):
        if self.project:
            return self.project.name
        return ''

    def getCurrentProjectSignLanguage(self):
        if self.project:
            return self.project.sign_language
        return ''

    def to_local_datetime(self, utc_dt):
        utc_zone = tz.tzutc()
        local_zone = tz.tzlocal()
        utc = utc_dt.replace(tzinfo=utc_zone)
        # Convert time zone
        return utc.astimezone(local_zone)

    def getCurrentDateTimeStr(self, iso_str=None):
        # timestamp of last update/save
        if (self.project and self.project.last_save_datetime) or iso_str:
            dt = ''
            if iso_str:
                _datetime = iso_str.rstrip('Z') #iso string from websoosl ends with 'Z'
            else:
                _datetime = self.project.last_save_datetime
            if hasattr(datetime, 'fromisoformat'): # python3.7
                dt = datetime.fromisoformat(_datetime)
            elif hasattr(parser, 'isoparse'): # dateutil >= 2.7
                dt = parser.isoparse(_datetime)
            else:
                dt = self.fromIsoFormat(_datetime)
            if dt:
                dt = self.to_local_datetime(dt)
                time_str = dt.strftime('%a,  %d %b %Y %H:%M:%S (UTC%z)')
                return time_str
        return ''

    def fromIsoFormat(self, iso_date_time):
        if iso_date_time.endswith('Z'):
            iso_date_time = iso_date_time.replace('Z', '+00:00')
        date_str, time_str = iso_date_time.split('T')
        year, month, day = date_str.split('-')
        pre = '+'
        if time_str.count('+'):
            time_str, utc_offset = time_str.split('+')
        else:
            time_str, utc_offset = time_str.split('-')
            pre = '-'
        hours, minutes, secs = time_str.split(':')
        secs, micro_secs = secs.split('.')
        offset_hours, offset_mins = utc_offset.split(':')
        offset_hours = int(offset_hours)
        if pre == '-':
            offset_hours = -offset_hours
        offset_mins = int(offset_mins)
        time_delta = timedelta(hours = offset_hours, minutes = offset_mins)
        dt = datetime(int(year),
            int(month),
            int(day),
            int(hours),
            int(minutes),
            int(secs),
            int(micro_secs),
            tzinfo = timezone(time_delta))
        ##NOTE: is this timezone calculation correct???
        return dt

    def getCurrentProjectVersionId(self):
        if self.project:
            return self.project.version_id
        return ''

    def getCurrentProjectCreator(self):
        if self.project:
            return self.project.project_creator
        return ''

    def getCurrentProjectDir(self):
        if self.current_project_filename:
            return os.path.dirname(self.current_project_filename)
        return ''

    def setCurrentProject(self, project):
        self.project = project

    def newProject(self, setup_data, db_ext, project_id=None):
        name, location, written_langs, dialects, descript, sign_language, version = setup_data
        #setup directory structure
        ##TODO: check 'name' is not already used; offer to open existing named database???
        if not project_id:
            project_id = qApp.instance().pm.sooslSlugify(name)
        filename = os.path.normpath(os.path.join(location, project_id, "{}.{}".format(project_id, db_ext)))
        setup = self.__setupDirectories(location, project_id, filename)
        if setup: #new directories created
            new_jsn_file = self.newJson(name, filename, written_langs, dialects, descript, sign_language, version, project_id=project_id)
            self.amendProjectList(filename)
            if os.path.exists(filename):
                return filename
            return None
        else: #directories already exist
            return None

    def getSooSLDateTime(self, dt):
        # instead of relying on epoch basis of the timestamp being the same across platforms, use the offset from a
        # specific date (date this code was written).
        return (dt - datetime(2020, 12, 4, tzinfo=timezone.utc)).total_seconds()

    def newJson(self, name, filename, written_langs, _dialects, descript, sign_language, project_version, project_id=None):
        o = {}
        soosl_version = self.getProjectSooSLVersion()
        dt = datetime.now(timezone.utc)
        t = dt.isoformat()
        timestamp = str(round(self.getSooSLDateTime(dt)))# diff in seconds between creation and SooSL 'epoch'
        if not project_id:
            project_id = self.sooslSlugify(name)
            project_id = '{}-{}'.format(project_id, timestamp)
        #NOTE: see top of project.py for some explanations of keys
        o['projectName'] = name
        o['signLanguage'] = sign_language
        o['projectId'] = project_id
        o['timeStamp'] = timestamp
        o['versionId'] = project_version
        o['creationDateTime'] = t
        o['modifiedDateTime'] = t
        o['sooslVersion'] = soosl_version
        o['projectDescription'] = descript
        written_languages = []
        o['writtenLanguages'] = written_languages
        _id = 1
        for lang in written_langs:
            _lang = {}
            written_languages.append(_lang)
            name, order = lang[1:]
            _lang['langId'] = _id
            _lang['langName'] = name
            _lang['order'] = order
            _id += 1
        dialects = []
        o['dialects'] = dialects
        _id = 1
        for d in _dialects:
            dialect = {}
            dialects.append(dialect)
            dialect['id'] = _id
            dialect['name'] = d[1]
            dialect['abbr'] = d[2]
            dialect['focal'] = d[3]
            _id += 1
        # default set of grammar categories for new project
        o['grammarCategories'] = [
            {
                "id": 1,
                "name": "Noun"
            },
            {
                "id": 2,
                "name": "Verb"
            },
            {
                "id": 3,
                "name": "Adj"
            },
            {
                "id": 4,
                "name": "Quant"
            }]
        o['signs'] = []

        with io.open(filename, 'w', encoding='utf-8') as f:
            json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)

        return filename

    def setLanguages(self, langs):
        # id = 0; new language
        # id < 0; deleted
        new = [l for l in langs if isinstance(l, list) and l[0] == 0]
        deleted = [l for l in langs if isinstance(l, list) and l[0] < 0]
        if new or deleted:
            self.lang_list_changed.emit()

    def setSelectedLangIds(self, lang_ids):
        _ids = []
        for _id in lang_ids:
            if isinstance(_id, str):
                _ids.append(abs(self.getLangId(_id)))
            else:
                _ids.append(abs(_id))

        if self.selected_lang_ids != _ids:
            self.selected_lang_ids = _ids
            settings = qApp.instance().getSettings()
            name = self.current_project_filename
            if name and name != 'new':
                settings.setValue('ProjectSettings/{}/selected_lang_ids'.format(name), _ids)
                settings.sync()
                self.lang_selection_change.emit()

    def setSearchLangId(self, lang_id):
        if isinstance(lang_id, str):
            lang_id = self.getLangId(lang_id) #probably new language
        if not lang_id:
            lang_id = 1
        if self.search_lang_id != lang_id:
            self.search_lang_id = int(lang_id)
            settings = qApp.instance().getSettings()
            #name = settings.value("lastOpenedDatabase")
            name = self.current_project_filename
            if name:
                settings.setValue('ProjectSettings/{}/search_lang_id'.format(name), lang_id)
                settings.sync()
                self.search_lang_change.emit()

    def getSearchFontSize(self):
        return self.getFontSizeById(self.search_lang_id)

    def getSearchFontFamily(self):
        lang_name = self.project.getWrittenLanguageName(self.search_lang_id)
        return self.getFontFamily(lang_name)

    def getFontFamily(self, lang_name):
        settings = qApp.instance().getSettings()
        key = 'fontFamily{}'.format(lang_name)
        font_family = settings.value(key, qApp.instance().font().family())
        return font_family

    def getFontSize(self, lang_name):
        settings = qApp.instance().getSettings()
        key = 'fontSize{}'.format(lang_name)
        size = settings.value(key, 12)
        if size:
            return int(size)
        return 12

    def getFontSizeById(self, lang_id):
        if lang_id == 0:
            lang_id = 1 ##NOTE: this is an error, remove after fix
        lang_name = self.project.getWrittenLanguageName(lang_id)
        font_size = self.getFontSize(lang_name)
        return font_size

    def setFontSize(self, lang_name, _int):
        settings = qApp.instance().getSettings()
        settings.setValue('fontSize{}'.format(lang_name), _int)
        settings.sync()

    def setFontFamily(self, lang_name, family_name):
        settings = qApp.instance().getSettings()
        settings.setValue('fontFamily{}'.format(lang_name), family_name)
        settings.sync()

    def setFontSizes(self, font_sizes):
        for key in font_sizes.keys():
            if isinstance(key, str):
                lang_name = key
                lang_id = self.getLangId(key) #self.getFontSize(lang_name)
            else:
                lang_name = self.project.getWrittenLanguageName(key)
                lang_id = key

            font_size = font_sizes.get(key)
            self.setFontSize(lang_name, font_size)
            self.font_size_change.emit(lang_id, font_size)

    def setFontFamilies(self, font_families):
        for key in font_families.keys():
            if isinstance(key, str):
                lang_name = key
                lang_id = self.getLangId(key) #self.getFontSize(lang_name)
            else:
                lang_name = self.project.getWrittenLanguageName(key)
                lang_id = key

            font_family = font_families.get(key)
            self.setFontFamily(lang_name, font_family)
            self.font_family_change.emit(lang_id, font_family)

    def setAutoKeyboard(self, check_state):
        settings = qApp.instance().getSettings()
        settings.setValue('autoKeyboardSwitchState', check_state)
        settings.sync()

    def getProjectFiles(self, project_filename=None):
        if not project_filename:
            project_filename = self.current_project_filename
        proj_dir = os.path.dirname(project_filename)
        files = [f for f in glob.iglob(os.path.join(proj_dir, '**'), recursive=True) \
            if not os.path.isdir(f)]
        return files

    def createInventoryChangeFile(self, old_inventory, new_inventory): # or 'secondary inventory' and 'primary_inventory'
        # ('new_' or 'primary_' 'inventory' is also the inventory for the currently open project in SooSL Desktop.)
        with io.open(old_inventory, 'r', encoding='utf-8') as f:
            old_jsn = json.load(f)
        with io.open(new_inventory, 'r', encoding='utf-8') as f:
            new_jsn = json.load(f)

        proj_dir = os.path.dirname(new_inventory)
        proj_id = new_jsn.get('projectId')
        ## NOTE: need to compare old and new ids; probably only want to compare inventories with identical ids
        changes_file = proj_dir + '/{}-changes.json'.format(proj_id)
        o = {}
        oldname = old_jsn.get('projectName')
        newname = new_jsn.get('projectName')
        if oldname == newname:
            o['projectName'] = oldname
        else:
            o['oldProjectName'] = oldname
            o['newProjectName'] = newname
        o['projectId'] = proj_id
        oldversion = old_jsn.get('versionId')
        newversion = new_jsn.get('versionId')
        if oldversion == newversion:
            o['versionId'] = oldversion
        else:
            o['oldVersionId'] = oldversion
            o['newVersionId'] = newversion
        oldmodtime = old_jsn.get('projectModifiedDateTime')
        newmodtime = new_jsn.get('projectModifiedDateTime')
        if oldmodtime == newmodtime:
            o['projectModifiedDateTime'] = oldmodtime
        else:
            o['oldProjectModifiedDateTime'] = old_jsn.get('projectModifiedDateTime')
            o['newProjectModifiedDateTime'] = new_jsn.get('projectModifiedDateTime')
        o['oldInventoryDateTime'] = old_jsn.get('inventoryDateTime')
        o['newInventoryDateTime'] = new_jsn.get('inventoryDateTime')

        new_files = []
        changed_files = []
        deleted_files = []
        o['newFiles'] = new_files
        o['changedFiles'] = changed_files
        o['deletedFiles'] = deleted_files
        oldfiles = old_jsn.get('files', [])
        newfiles = new_jsn.get('files', [])

        def get_path(j):
            return j.get('path')

        #find new and changed files:
        for nf in newfiles:
            pth = get_path(nf)
            in_old = [f for f in oldfiles if get_path(f) == pth]
            if not in_old:
                new_files.append(nf) # new file
            else:
                old_f = in_old[0]
                if self.hasFileChanged(old_f, nf):
                    changed_files.append(nf) # changed file
        # find deleted files
        for ff in oldfiles:
            pth = get_path(ff)
            in_new = [f for f in newfiles if get_path(f) == pth]
            if not in_new:
                deleted_files.append(ff)

        # check for any manual changes made outside of SooSL.
        # if there are any changed files and project file is not amongst them, then such a change has occurred.
        # making a change in SooSL should always change the timestamp and modified datetime in the project file.
        project_pth = self.project.filename.replace(proj_dir, '')
        all_pths = []
        all_files = new_files + changed_files + deleted_files
        for f in all_files:
            try:
                all_pths.append(get_path(f))
            except:
                all_pths.append(f)
        if all_pths and project_pth not in all_pths:
            print('Manual changes detected.. updating project modifiedDateTime and timestamp...')
            dt = datetime.now(timezone.utc).isoformat()
            self.project.updateProjectTimeStamp(dt)
            self.reloadCurrentProject() # to clear the reload project action in toolbar
            print('Getting new inventory...')
            new_inventory = self.createInventory() # update the inventory file
            with io.open(new_inventory, 'r', encoding='utf-8') as f:
                new_jsn = json.load(f)
                project_file = new_jsn.get('files')[0] # project file should be first in list
                ## NOTE: need to update changed sign JSON also? a little more difficult...
                changed_files.append(project_file)
                o['newInventoryDateTime'] = new_jsn.get('inventoryDateTime')
                o['newProjectModifiedDateTime'] = new_jsn.get('projectModifiedDateTime')
        with io.open(changes_file, 'w', encoding='utf-8') as f:
            json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)
        #os.remove(old_inventory)
        return changes_file

    # def isSignFile(self, filename):
    #     if filename.count('/_signs/') and filename.endswith('.json'):
    #         return True
    #     return False

    def hasFileChanged(self, old_jsn, new_jsn):
        newhash = new_jsn.get('md5')
        oldhash = old_jsn.get('md5')
        if newhash == oldhash:
            return False
        #print(oldhash, newhash, old_jsn, new_jsn)
        return True

    def doesPathExist(self, filepath):
        if os.path.exists(filepath):
            return True
        # in case of string mismatch (some Arabic...),
        # id is also unique within filename, so look for this.
        try:
            _id = re.search(r'_id[0-9]+\.', filepath)[0]
        except:
            pass
        else:
            d = os.path.dirname(filepath)
            if glob.glob(f'{d}/*{_id}*'):
                return True
        return False

    def createInventory(self, project=None, create_changes=False, progress_dlg=None):
        """
        walk through the project creating a list of current files and their hashes.
        """
        then = time.time()
        self.abort_inventory = False
        if not create_changes and isinstance(self.sender(), QPushButton):
            create_changes = True
        if not project and self.project:
            project = self.project
        if project:
            inventory_file = project.project_dir + '/{}.inventory'.format(project.id)
            old_inventory_file = None
            if create_changes:
                old_inventory_file = None
                if os.path.exists(inventory_file):
                    old_inventory_file = project.project_dir + '/{}-old_inventory.json'.format(project.id)
                    shutil.copy(inventory_file, old_inventory_file)
            o = {}
            o['projectName'] = project.name
            o['projectId'] = project.id
            o['versionId'] = project.version_id
            o['projectModifiedDateTime'] = project.last_save_datetime
            o['inventoryDateTime'] = datetime.now(timezone.utc).isoformat()
            project_files = []
            pth = project.filename.replace(project.project_dir, '')
            _md5 = self.getFreshHash(project.filename)
            project_files.append({'path':pth, 'md5':_md5})
            logo = self.getProjectLogo(project)
            if logo:
                _md5 = self.getFreshHash(logo)
                pth = logo.replace(project.project_dir, '')
                project_files.append({'path':pth, 'md5':_md5})

            if progress_dlg:
                progress_dlg.setMaximum(len(project.signs)+1) # extra 1 keeps it from closing; export dialog will take over
            for sign in project.signs:
                if self.abort_inventory:
                    break
                if progress_dlg:
                    qApp.processEvents()
                    if progress_dlg.wasCanceled():
                        return None
                    progress_dlg.setValue(progress_dlg.value() + 1)
                # sign file
                if not os.path.exists(sign.json_file): # sign has been manually removed outside of SooSL
                    print('sign removed?', sign.json_file)
                    continue
                desk_pth = sign.json_file.replace(project.project_dir, '')
                pth = f"/_signs/{sign.id}.json"
                _md5 = self.getFreshHash(sign.json_file)
                d = {'path':pth, 'desktop_path':desk_pth, 'md5':_md5}
                if d not in project_files:
                    project_files.append(d)
                # sign video
                if not os.path.exists(sign.path):
                    print('mia:', os.path.exists(sign.path), self.doesPathExist(sign.path), sign.path)
                if self.doesPathExist(sign.path): # manually removed?
                    pth = sign.path.replace(project.project_dir, '')
                    _md5 = self.getFreshHash(sign.path)
                    d = {'path':pth, 'md5':_md5}
                    if d not in project_files:
                        project_files.append(d)
                for sense in sign.senses:
                    for sentence in sense.sentences:
                        # sentence video
                        if self.doesPathExist(sentence.path): # manually removed?
                            pth = sentence.path.replace(project.project_dir, '')
                            _md5 = self.getFreshHash(sentence.path)
                            d = {'path':pth, 'md5':_md5}
                            if d not in project_files:
                                project_files.append(d)
                for media in sign.extra_media_files:
                    # extra media video or picture
                    if self.doesPathExist(media.path): # manually removed?
                        pth = media.path.replace(project.project_dir, '')
                        _md5 = self.getFreshHash(media.path)
                        d = {'path':pth, 'md5':_md5}
                        if d not in project_files:
                            project_files.append(d)

            if not self.abort_inventory:
                ##NOTE: DON'T be tempted to sort inventory here; it is already ordered grouping files in sign order
                o['files'] = project_files
                with io.open(inventory_file, 'w', encoding='utf-8') as f:
                    json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)
                if create_changes and old_inventory_file:
                    self.createInventoryChangeFile(old_inventory_file, inventory_file)
            else:
                return None

        elapsed_time = time.time() - then
        # print('inventory:', elapsed_time)
        return inventory_file

    def updateWebProject(self):
        if self.project.writePermission:
            mw = qApp.instance().getMainWindow()
            if self.projectChanged():
                mw.reloadProject()
            if self.acquireFullProjectLock() and self.acquireProjectIDLock():
                dlg = WebProjectUploadDlg(mw)
                dlg.exec_()
                self.releaseFullProjectLock(self)
                self.releaseProjectIDLock()
                #self.acquired_project_id_lock = False

        else:
            t1 = qApp.instance().translate('ProjectManager', 'This dictionary is read-only and cannot be uploaded.')
            t2 = qApp.instance().translate('ProjectManager', 'It is locked against any changes.')
            t3 = qApp.instance().translate('ProjectManager', 'Open a read-write version of this dictionary before uploading.')
            txt = '<b style="color:blue;">{}</b><br><br>{}<br>{}'.format(t1, t2, t3)
            self.showWarning(' ', txt)

    def getFullProjectFileForExport(self):
        return self.project.getFullProjectFileForExport()

    def setWritePermission(self, pth, write):
        # https://stackoverflow.com/questions/28492685/change-file-to-read-only-mode-in-python
        if os.path.isfile(pth):
            self.updateKnownProjectInfoPermission(pth, write)
            if not write:
                os.chmod(pth, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
                return False
            os.chmod(pth, stat.S_IWUSR|stat.S_IREAD)
            return True
        elif os.path.isdir(pth):
            qdir = QDir(pth)
            qdir.setFilter(QDir.Files)
            files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList()]
            if not write:
                for f in files:
                    os.chmod(f, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
                return False
            for f in files:
                os.chmod(f, stat.S_IWUSR|stat.S_IREAD)
            return True

    def minSooSLVersionCheck(self, _filename):
        if _filename and not _filename.endswith('.json'):
            return True # okay to open old sqlite projects; will be updated
        try:
            f = open(_filename, 'r', encoding='utf-8')
        except:
            return False
        txt = f.read(1500)
        f.close()
        tmatch = re.search(r'"minSooSLVersion": "(.+)",', txt)
        if tmatch:
            min_version = str(tmatch.group(1))
            soosl_version = self.getSooSLVersion()
            if min_version == soosl_version:
                return True
            try:
                _bool = self.olderThan(min_version, soosl_version)
            except:
                return True #NOTE: some error in versioning, but assume okay to open???
            else:
                if _bool:
                    return True
                # show update SooSL message
                short = qApp.instance().translate('ProjectManager', 'Update SooSL')
                txt1 = qApp.instance().translate('ProjectManager', 'Please update SooSL to open this dictionary.')
                txt2 = qApp.instance().translate('ProjectManager', 'Minimum version required:')
                long = '<center><h3>{}</h3><p>({} SooSL {})</p></center>'.format(txt1, txt2, min_version)
                self.showWarning(short, long)
                return False
        else:
            return True # must be 0.9.0 which didn't have this feature; okay to open
        return True

    def onFileChanged(self, pth):
        print('file changed', pth)

    def startInactivityTimer(self, widget):
        # prevent indefinite locking for sign or project info editing if SooSL instance
        # left unattended
        if not hasattr(self, 'inactivity_timer'):
            settings = qApp.instance().getSettings()
            interval = settings.value('inactivityTimeoutMinutes', 30) # interval in minutes
            interval = int(float(interval) * 60000) # convert to milliseconds
            self.inactivity_timer = QTimer(self)
            self.inactivity_timer.setInterval(interval)
            self.inactivity_timer.timeout.connect(self.onEditTimeout)
        self.edit_widget = widget
        self.inactivity_timer.start()

    def stopInactivityTimer(self):
        if hasattr(self, 'inactivity_timer'):
            self.inactivity_timer.stop()

    def onEditTimeout(self):
        self.inactivity_timer.stop()
        try:
            dlg = ContinueEditingDlg(parent=self.edit_widget)
        except:  # wrapped C/C++ object of type ProjectTreeView has been deleted; inactivity timeout closure on reconciliation widget
            pass
        else:
            if dlg.exec_():
                self.inactivity_timer.start()
            else:
                self.edit_widget.leaveEdit(False)
                title = qApp.instance().translate('ProjectManager', 'SooSL edit timeout')
                txt1 = qApp.instance().translate('ProjectManager', 'Editing in SooSL has closed due to inactivity.')
                txt2 = qApp.instance().translate('ProjectManager', 'Unsaved changes were discarded.')
                if isinstance(self.edit_widget, (MergeDialog, ReconcileChangesDialog)):
                    title = qApp.instance().translate('ProjectManager', 'SooSL reconciliation timeout')
                    txt1 = qApp.instance().translate('ProjectManager', 'Reconciling of versions has stopped due to inactivity.')
                    txt2 = qApp.instance().translate('ProjectManager', 'Current progress has been saved.')
                self.edit_widget = None
                # show message dialog to user explaining why editing was exited.
                widget = qApp.instance().getMainWindow()
                box = QMessageBox(widget)
                box.setWindowTitle(title)
                box.setText('{}\n{}'.format(txt1, txt2))
                box.setIcon(QMessageBox.Information)
                box.exec_()
        self.removeExpiredProjectLocks()
        self.removeExpiredSignLocks()

    def isProjectFullyLocked(self):
        try:
            self.fullProjectLock.acquire()
        except:
            return True
        else:
            self.fullProjectLock.release() # just asking the question here, don't want to keep the lock
            return False

    def setFullProjectLock(self):
        # set full project lock from the beginning if you can
        # to prevent new sign creation while checking individual sign locks
        _return = True
        try:
            self.fullProjectLock.acquire()
        except:
            _return = (self.lockHasExpired(self.fullProjectLock) or self.isMyLock(self.fullProjectLock))
        if _return:
            # find any lock files
            signs_dir = '{}/_signs'.format(self.project.project_dir)
            qdir = QDir(signs_dir)
            qdir.setFilter(QDir.Files)
            lock_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock']
            if self.editing:
                current_sign_lockfile = '{}/_signs/{}.json.lock'.format(self.project.project_dir, self.sign.id)
                lock_files = [lf for lf in lock_files if lf != current_sign_lockfile]
            # attempt to acquire; return False if any are already locked; don't keep acquired sign locks
            for lf in lock_files:
                lock = SoftFileLock(lf, timeout=0)
                try:
                    lock.acquire()
                except:
                    _return = (self.lockHasExpired(lock) or self.isMyLock(lock))
                    if not _return:
                        self.removeFullProjectLock()
                if _return:
                    lock.release()
                    if os.path.exists(lf):
                        try:
                            os.remove(lf)
                        except:
                            pass
        return _return

    def removeFullProjectLock(self):
        self.fullProjectLock.release() # if acquire fails on any sign, full project lock fails
        try:
            self.project_locks.remove(self.fullProjectLock)
        except:
            pass
        if os.path.exists(self.fullProjectLock.lock_file):
            try:
                os.remove(self.fullProjectLock.lock_file)
            except:
                pass

    def acquireFullProjectLock(self, widget=None, ignore_merge_lock=False):
        _return = False
        if self.acquireProjectLock(widget, ignore_merge_lock):
            _return = self.setFullProjectLock()
            if not _return:
                self.releaseProjectLock()
                msg = '{}\n{}'.format(qApp.instance().translate('ProjectManager', 'Signs are being edited by another user.'),
                        qApp.instance().translate('ProjectManager', "Try again later."))
                self.showLockedMessageBox(widget, msg)
        if _return:
            self.writeLockData(self.fullProjectLock)
        if _return:
            self.project_locks.append(self.fullProjectLock)
            self.lock_update_timer.start()
        return _return

    def releaseFullProjectLock(self, object=None):
        self.lock_update_timer.stop()
        self.releaseSignLocks()
        self.removeFullProjectLock()
        self.releaseProjectLock()
        if object:
            if hasattr(object, 'acquired_full_project_lock'):
                object.acquired_full_project_lock = False
            if hasattr(object, 'acquired_project_lock'):
                object.acquired_project_lock = False

    def getLockSession(self, lock):
        if lock and os.path.exists(lock.lock_file):
            return self.getLockSessionFromFile(lock.lock_file)
        return None

    def getLockSessionFromFile(self, lock_file):
        jsn = {}
        with open(lock_file, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
        node = jsn.get('node', '')
        user = jsn.get('username', '')
        pid = jsn.get('pid', '')
        session = f'{node}_{user}_{pid}'
        return session

    def acquireProjectIDLock(self):
        def show_message():
            txt1 = qApp.instance().translate('WebProjectUploadDlg', 'Dictionary was locked against updating by:')
            txt2 = self.getLockSession(self.projectIDLock)
            txt3 = qApp.instance().translate('ProjectManager', "Try again later.")
            msg = f'{txt1}\n{txt2}\n{txt3}'
            self.showLockedMessageBox(qApp.instance().getMainWindow(), msg)
            return False

        # if project is locked for editing, you cannot lock it for uploading
        if self.lockedForEditing():
            return show_message()
        if self.lockedForMerging():
            return False # message shown in above check

        print('Acquire ID lock')

        _return = True # return True if you've acquired the project ID lock
        if self.projectIDLock.is_locked:
            _return = (self.lockHasExpired(self.projectIDLock) or self.isMyLock(self.projectIDLock))
        if _return:
            try:
                self.projectIDLock.acquire()
            except:
                _return = (self.lockHasExpired(self.projectIDLock) or self.isMyLock(self.projectIDLock))
            else:
                _return = True
        if _return:
            self.writeLockData(self.projectIDLock)
            self.project_locks.append(self.projectIDLock)
            self.lock_update_timer.start()
        if not _return:
            show_message()
        return _return

    def releaseProjectIDLock(self):
        self.lock_update_timer.stop()
        try:
            self.project_locks.remove(self.projectIDLock)
        except:
            pass
        lock_file = self.projectIDLock.lock_file
        self.projectIDLock.release()
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except:
                try:
                    os.remove(lock_file)
                except:
                    pass

    def lockHasExpired(self, lock):
        return self.lockFileHasExpired(lock.lock_file)

    def __oldStyleLockDate(self, lock_file):
        lines = []
        with open(lock_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) == 2:
            return lines[1].strip()
        return '1.0' # must be corrupt lock; remove it.

    def userLockFileInactive(self, lock_file, max_secs=3):
        user_date = ''
        try:
            with open(lock_file, 'r', encoding='utf-8') as f:
                jsn = json.load(f)
        except:
            user_date = self.__oldStyleLockDate(lock_file)
        else:
            user_date = jsn.get('timestamp', '1.0')
        if user_date:
            this_date = datetime.now(timezone.utc).timestamp()
            time_diff = float(this_date) - float(user_date)
            if time_diff > max_secs: # hasn't been updated in max_secs - consider it inactive
                return True
        return False

        # with open(lock_file, 'r', encoding='utf-8') as f:
        #     lines = f.readlines()
        # if lines:
        #     try:
        #         session_id, user_date = lines
        #     except:
        #         return False
        #     else:
        #         this_date = datetime.now(timezone.utc).timestamp()
        #         time_diff = float(this_date) - float(user_date)
        #         if time_diff > max_secs: # hasn't been updated in max_secs - consider it inactive
        #             return True
        # else:
        #     return False # empty file; no session id found, don't use

    def lockFileHasExpired(self, lock_file):
        if not os.path.exists(lock_file):
            return True
        settings = qApp.instance().getSettings()
        max_secs = int(settings.value('lockTimeoutSeconds', LOCK_EXPIRES))
        this_date = datetime.now(timezone.utc).timestamp()
        try:
            with open(lock_file, 'r', encoding='utf-8') as f:
                jsn = json.load(f)
        except:
            lock_date = self.__oldStyleLockDate(lock_file)
        else:
            lock_date = jsn.get('timestamp', '1.0')
        try:
            time_diff = float(this_date) - float(lock_date)
            if time_diff > max_secs: # hasn't been updated in max_secs - consider it unlocked
                return True
        except:
            pass # one case where this would happen: open on one computer and no access from another
        return False

    def acquireSignLocks(self, signs=[]):
        project_dir = self.project.project_dir
        if not signs:
            signs = [self.sign]
        for sign in signs: # we want all signs locked or None
            _return = True # return True if you've acquired a sign lock
            if sign is self.sign and self.editing:
                continue # current sign should already be locked
            try:
                sign_id = sign.id
            except:
                sign_id = sign # new sign
            sign_file = '{}/_signs/{}.json'.format(project_dir, sign_id)
            ##https://github.com/benediktschmitt/py-filelock
            signLock = SoftFileLock(sign_file + '.lock', timeout=0)
            if signLock.is_locked:
                _return = (self.lockHasExpired(signLock) or self.isMyLock(signLock))
            if _return:
                try:
                    signLock.acquire()
                except:
                    _return = (self.lockHasExpired(signLock) or self.isMyLock(signLock))
                else:
                    _return = True
            if _return: # and signLock not in self.sign_locks: # obtained lock and not already locked by editing
                self.writeLockData(signLock)
                self.sign_locks.append(signLock)
            else: # if one fails, they all fail
                self.releaseSignLocks()
                break
        if _return:
            self.lock_update_timer.start()
        return _return

    def updateLockPID(self, lock_file, pid):
        with open(lock_file, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
        jsn['pid'] = pid
        with open(lock_file, 'w', encoding='utf-8') as f:
            json.dump(jsn, f, sort_keys=False, indent=4, ensure_ascii=False)

    def isMyLock(self, lock):
        try:
            with open(lock.lock_file, 'r', encoding='utf-8') as f:
                jsn = json.load(f)
        except:
            # old style lock
            try:
                os.remove(lock.lock_file)
            except:
                return False
            else:
                return True # able to remove, so must be dead
        else:
            node = jsn.get('node')
            user = jsn.get('username')
            pid = jsn.get('pid')
            this_user, this_pid = self.session_id.rsplit('_', 1)
            if node == platform.node(): # lock set by this computer
                try:
                    p = psutil.Process(int(pid))
                except:
                    if user == this_user: # same user but in a different crashed process; consider mine to use
                        self.updateLockPID(lock.lock_file, this_pid)
                        return True
                else: # active process; is it mine?
                    session_id = f'{user}_{pid}'
                    if session_id == self.session_id:
                        return True
            # else: # lock set by a remote computer
            #     pass
        return False

    def releaseSignLocks(self, all=False):
        keep_locked = None
        for lock in self.sign_locks:
            lock_file = lock.lock_file
            if self.editing and self.sign and not all:
                pth = '{}/_signs/{}.json.lock'.format(self.project.project_dir, self.sign.id)
                if pth == lock_file:
                    keep_locked = lock
                    continue
            lock.release()
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    try:
                        os.remove(lock_file)
                    except:
                        pass
        if keep_locked:
            self.sign_locks = [keep_locked]
        else:
            self.lock_update_timer.stop()
            self.sign_locks.clear()

    def releaseSignLock(self, lock_file):
        self.lock_update_timer.stop()
        locks = [lock for lock in self.sign_locks if lock.lock_file == lock_file]
        if locks:
            lock = locks[0]
            lock.release()
            self.sign_locks.remove(lock)
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    try:
                        os.remove(lock_file)
                    except:
                        pass

    def acquireProjectLock(self, widget=None, ignore_merge_lock=False):
        if not ignore_merge_lock and self.lockedForMerging(widget):
            return False
        # necessary to send reference to the widget which request the lock;
        # if lock not acquired, this is used as parent to QMessageBox warning
        _return = True # return True if you've acquired the project lock
        try:
            if self.projectLock.is_locked:
                _return = (self.lockHasExpired(self.projectLock) or self.isMyLock(self.projectLock))
        except:
            _return = False
        if _return:
            try:
                self.projectLock.acquire()
            except:
                _return = (self.lockHasExpired(self.projectLock) or self.isMyLock(self.projectLock))
            else:
                _return = True
        if widget and not _return: # no widget means no message required
            # saving a sign updates project json with timestamp, but other provision is made if there is
            # a project lock in place and no warning is required
            t1 = qApp.instance().translate('ProjectManager', 'This dictionary is currently being edited by another user:')
            t2 = self.getLockSession(self.projectLock)
            t3 = qApp.instance().translate('ProjectManager', "Try again later.")
            msg = f'{t1}\n{t2}\n{t3}'
            self.showLockedMessageBox(widget, msg)
        if _return:
            self.writeLockData(self.projectLock)
            self.project_locks.append(self.projectLock)
            self.lock_update_timer.start()
        return _return

    def lockedForEditing(self, widget=None):
        if not widget:
            widget = qApp.instance().getMainWindow()
        if os.path.exists(self.fullProjectLock.lock_file) and self.isMyLock(self.fullProjectLock):
            return False
        if self.isProjectFullyLocked():
            t1 = qApp.instance().translate('ProjectManager', 'This dictionary is currently locked against editing by another user:')
            t2 = self.getLockSession(self.fullProjectLock)
            t3 = qApp.instance().translate('ProjectManager', "Try again later.")
            msg = f'{t1}\n{t2}\n{t3}'
            self.showLockedMessageBox(widget, msg)
            return True
        return False

    def lockedForMerging(self, widget=None):
        if not widget:
            widget = qApp.instance().getMainWindow()
        if os.path.exists(f'{self.project.project_dir}/merge'):
            msg = '{}\n{}'.format(qApp.instance().translate('ProjectManager', 'Another dictionary is currently being merged with this one.'),
                qApp.instance().translate('ProjectManager', "Complete merge before further editing."))
            self.showLockedMessageBox(widget, msg)
            return True
        return False

    def showLockedMessageBox(self, widget, message):
        box = QMessageBox(widget)
        box.setWindowTitle(' ')
        box.setText(message)
        pxm = QPixmap(':/lock16.png').scaledToHeight(32, Qt.SmoothTransformation)
        box.setIconPixmap(pxm)
        box.exec_()

    def releaseProjectLock(self):
        self.lock_update_timer.stop()
        lock_file = self.projectLock.lock_file
        self.projectLock.release()
        try:
            self.project_locks.remove(self.projectLock)
        except:
            pass
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except:
                try:
                    os.remove(lock_file)
                except:
                    pass

    def projectChanged(self):
        if self.projectTimestampChanged() or \
           self.pendingProjectTimestampChange():
                return True
        return False

    def onNetworkLost(self, pth):
        txt1 = qApp.instance().translate('ProjectManager', 'Connection to dictionary lost')
        txt2 = txt1
        if self.project and self.project.filename.startswith(pth):
            txt2 = '<center>{}<br>{}<br>{}</center>'.format(txt1, self.project.name, qApp.instance().translate('ProjectManager', 'This dictionary has been closed.'))
            self.closeProject(network=False)
        self.show_warning.emit(txt1, txt2)

    def projectTimestampChanged(self):
        this_timestamp = self.project.getModifiedTimeStampProject(self.project.last_save_datetime)
        jsn = None
        with io.open(self.current_project_filename, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
        if jsn:
            file_timestamp = jsn.get('timeStamp')
            #if file_timestamp > this_timestamp:
            ## NOTE: might a changed project have an earlier timestamp???
            # importing project, for example, if allowed...
            if file_timestamp != this_timestamp:
                return True
        return False

    def onProjectChanged(self):
        if self.projectTimestampChanged():
            self.project_changed.emit()

    def reloadCurrentProject(self):
        self.project = Project(self.current_project_filename, update_jsn=True)
        self.project_reloaded.emit()
        self.updateKnownProjectInfoDatetime(self.project.filename, self.project.last_save_datetime)

    def openZooZLProject(self, _filename):
        try:
            parent = qApp.instance().startup_widget
        except:
            parent = qApp.instance().getMainWindow()
        if not parent.isVisible():
            parent = qApp.instance().getMainWindow()
        msgBox = QMessageBox(parent)
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<strong>{}</strong>'.format(_filename))
        t1 = qApp.instance().translate('ProjectManager', 'This is a ZOOZL file and needs to be imported.')
        t2 = qApp.instance().translate('ProjectManager', 'Do you want to import it now?')
        msgBox.setInformativeText(f'{t1}<br>{t2}')
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_btn, no_btn = msgBox.buttons()
        yes_btn.setIcon(QIcon(":/thumb_up.png"))
        no_btn.setIcon(QIcon(":/thumb_down.png"))
        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ProjectManager', "Yes"))
        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ProjectManager', "No"))
        msgBox.setDefaultButton(QMessageBox.No)
        if msgBox.exec_() != QMessageBox.Yes:
            return None

        importer = Importer(self)
        importer.importProject(_filename)
        ## NOTE: could SooSL work directly with zoozl files, without the need to extract first???
        ##_project = ZooZLProject(_filename)

    def openProject(self, _filename):
        """open project by 'filename'
        """
        if not _filename:
            return
        qApp.setOverrideCursor(Qt.BusyCursor)
        #qApp.instance().logRunning('open project {}'.format(_filename))
        filename = _filename
        _project = None
        # some test code for launching project at a particular time; checking what happens if several instances of SooSL
        # attempt to opne a project at the same time - so far have seen no problems
        # while time.time() < 1628610427:
        #     self.thread().msleep(1)
        if filename and filename.endswith('.json') and self.minSooSLVersionCheck(filename):
            _project = Project(filename)
        elif filename and os.path.exists(filename):
            if os.path.splitext(filename)[1] == ".enc":
                filename = self.unsecure(_filename, inplace=True)
            ext = os.path.splitext(filename)[1]
            if ext == ".sqlite":
                _copy = '{}-backup'.format(filename)
                if os.path.exists(_copy): #SooSL probably crashed; assume db corrupted
                    shutil.copy(_copy, filename)
                else: #create fresh copy
                    shutil.copy(filename, _copy)
                # update to latest json version (keeping old sqlite for now)
                updater = PU()
                _filename = updater.update(filename)
                if _filename:
                    filename = _filename[1]
                    self.openProject(filename)
                if os.path.exists(_copy):
                    try:
                        os.remove(_copy)
                    except:
                        pass
                qApp.restoreOverrideCursor()
                qApp.processEvents()
                return
        if _project:
            if not _project.jsn:
                qApp.restoreOverrideCursor()
                qApp.processEvents()
                return None # an error occurred while creating project
            if self.project:
                self.closeProject() #close current project
            self.setKnownProjectInfo(_project.filename,
                perm=_project.writePermission,
                proj_name=_project.name,
                proj_id=_project.id,
                proj_version=_project.version_id,
                proj_datetime=_project.last_save_datetime)

            self.amendProjectList(filename)
            self.setCurrentProject(_project)
            self.setPossibleRemovals()
            self.setProjectSettings(_project)
            settings = qApp.instance().getSettings()
            settings.setValue("lastOpenedDatabase", filename)

            if _project.writePermission:
                self.openProjectSession()
                # establish lockfiles
                # https://github.com/benediktschmitt/py-filelock
                #_dir = _project.project_dir
                if not _project.id:
                    _project.id = ''
                # projectIDLock created on user's computer, to guard against uploading of diff projects with same id by same user
                self.projectIDLock = SoftFileLock(f'{qApp.instance().getWorkingDir()}/{_project.id}.lock', timeout=0)
                # other locks created in project dir of open project; user's computer or remote computer
                self.fullProjectLock = SoftFileLock(f'{_project.project_dir}/full_project.lock', timeout=0)
                self.projectLock = SoftFileLock(f'{_project.project_dir}/project.lock', timeout=0)

            changes_file = self.getChangesFile()
            if changes_file:
                self.__applyChanges()
                self.recoverAfterCrash()
                if os.path.exists(changes_file):
                    os.remove(changes_file)

            qApp.processEvents()
            settings.sync()
            self.fileSystemWatcher.addPath(_project.filename)

        else:
            self.projectIDLock = None
            self.fullProjectLock = None
            self.projectLock = None
            self.project_locks.clear()
            self.lock_update_timer.stop()
            self.user_update_timer.stop()

        QTimer.singleShot(200, qApp.restoreOverrideCursor)
        #qApp.instance().logRunning('open project complete')
        return _project

    def openProjectSession(self):
        self.removeExpiredLocks()
        p = psutil.Process()
        user_name = os.path.basename(p.username())
        self.session_id = f'{user_name}_{p.pid}'
        self.setUserLock()
        self.user_update_timer.start()
        #self.updateUnexpiredCrashedSessions()

    # def updateUnexpiredCrashedSessions(self):
    #     user_name, current_pid = self.session_id.rsplit('_', 1)
    #     ## look for any crashed sessions for this user and claim any unexpired locks for the first found for this new session
    #     qdir = QDir(self.project.project_dir)
    #     qdir.setFilter(QDir.Files)
    #     user_lock_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.user']
    #     # expired locks should have been removed above
    #     user_locks = [lf for lf in user_lock_files if os.path.basename(lf).startswith(f'{user_name}_')]
    #     other_locks = []
    #     # project locks
    #     qdir = QDir(qApp.instance().getWorkingDir())
    #     qdir.setFilter(QDir.Files)
    #     project_locks = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock']
    #     qdir = QDir(self.project.project_dir)
    #     qdir.setFilter(QDir.Files)
    #     project_locks.extend([qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock'])
    #     # sign locks
    #     signs_dir = '{}/_signs'.format(self.project.project_dir)
    #     qdir = QDir(signs_dir)
    #     qdir.setFilter(QDir.Files)
    #     sign_locks = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.lock']
    #     other_locks.extend(project_locks)
    #     other_locks.extend(sign_locks)
    #     if user_locks:
    #         print(user_locks)
    #         for ulock in user_locks:
    #             if self.userLockFileInactive(ulock):
    #                 os.remove(ulock)

    #             # _username = os.path.basename(os.path.splitext(ulock)[0])
    #             # _pid = _username.rsplit('_', 1)[-1]
    #             # try:
    #             #     _p = psutil.Process(int(_pid))
    #             # except:
    #             #     os.remove(ulock) # no running process - crashed!

    #                 ## NOTE: remove any other locks set by this user and process???
    #                 ## process crashed before lock expired
    #                 ## update other locks created in crashed process to use new process id
    #                 # old_session_id = f'{user_name}_{_pid}'
    #                 # for olock in other_locks:
    #                 #     lines = []
    #                 #     with open(olock, 'r', encoding='utf-8') as f:
    #                 #         lines = f.readlines()
    #                 #     if len(lines) == 2: # old style lock
    #                 #         session_id = lines[0].strip()
    #                 #         timestamp = lines[1]
    #                 #     else:
    #                 #         s = ''.join(lines)
    #                 #         jsn = json.loads(s)
    #                 #         user = jsn.get('username')
    #                 #         pid = jsn.get('pid')
    #                 #         timestamp = jsn.get('timestamp')
    #                 #         session_id = f'{user}_{pid}'
    #                 #     if session_id == old_session_id:
    #                 #         o = {'username': user_name,
    #                 #              'pid': current_pid,
    #                 #              'timestamp': timestamp}
    #                 #         with open(olock, 'w', encoding='utf-8') as f:
    #                 #             json.dump(o, f, sort_keys=False, indent=4, ensure_ascii=False)

    #     # self.user_update_timer.start()

    def closeProjectSession(self):
        self.user_update_timer.stop()
        # settings = qApp.instance().getSettings()
        # key = 'lastProjectSessionId/{}'.format(self.project.project_dir)
        # settings.remove(key)
        self.session_id = None
        if self.userLock:
            self.userLock.release()
            lock_file = self.userLock.lock_file
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    try:
                        os.remove(lock_file)
                    except:
                        pass
        self.userLock = None

    def setUserLock(self):
        # won't really lock anything, just create a way to know if other users have project open
        user_file = f'{self.project.project_dir}/{self.session_id}.user'
        self.userLock = SoftFileLock(user_file, timeout=0)
        self.writeLockData(self.userLock)

    def getOtherProjectUsers(self, project_filename):
        if os.path.isdir(project_filename):
            project_filename = '{}/{}.json'.format(project_filename, os.path.basename(project_filename))
        users = self.getProjectUsers(project_filename)
        this_user_file = '{}/{}'.format(os.path.dirname(project_filename), self.thisUser())
        if os.path.exists(this_user_file):
            lock = SoftFileLock(this_user_file)
            try:
                lock.acquire()
            except: #this_user_file belongs to another process on this computer; they are in this project, you are not
                pass
            else:
                users = [u for u in users if u != self.thisUser()]
        return users

    def getProjectUsers(self, project_filename):
        users = []
        qdir = QDir(os.path.dirname(project_filename))
        qdir.setFilter(QDir.Files)
        user_lock_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1] == '.user']
        for f in user_lock_files:
            _user = os.path.basename(os.path.splitext(f)[0])
            lock = SoftFileLock(f, timeout=0)
            try:
                lock.acquire()
            except:
                users.append(_user)
            else:
                if _user and _user != self.thisUser():
                    lock.release()
        return users

    def thisUser(self):
        if hasattr(self, 'userLock') and self.userLock:
            user = os.path.basename(os.path.splitext(self.userLock.lock_file)[0])
            return user
        return None

    def setPossibleRemovals(self):
        removals_file = os.path.join(self.project.project_dir, 'files_to_remove.txt')
        if os.path.exists(removals_file):
            with io.open(removals_file, 'r', encoding='utf-8') as f:
                self.possible_removals = f.read().split(',') #first time this is set after opening project; just amend hereafter
            os.remove(removals_file)

    def __updateLastChange(self):
        changes_file = self.getChangesFile()
        if changes_file:
            changes = eval('[{}]'.format(io.open(changes_file, 'r', encoding='utf-8').read()).replace('null', 'None').replace('true', 'True').replace('false', 'False'))
            signs = [change for change in changes if change.__contains__('id')]
            if signs:
                last_sign = signs[-1]
                last_sign['saved'] = True
                with io.open(changes_file, 'w', encoding='utf-8') as f:
                    f.write('')
                with io.open(changes_file, 'a', encoding='utf-8') as f:
                    for change in changes:
                        json.dump(change, f, sort_keys=False, indent=4, ensure_ascii=False)
                        f.write(',\n')

    def getChangesFilePath(self):
        #get path for a possible changes file; may not exist, or use to create one
        wd = qApp.instance().getWorkingDir()
        return '{}/changes-{}'.format(wd, os.path.basename(self.current_project_filename))

    def getChangesFile(self):
        #get path for an existing changes file; return None otherwise
        changes_file = self.getChangesFilePath()
        if os.path.exists(changes_file):
            print('Changes file exists:')
            print(changes_file)
        if os.path.exists(changes_file):
            return changes_file
        return None

    def getSavedMediaLogPath(self):
        #get path for a possible saved media log file; may not exist, or use to create one
        wd = qApp.instance().getWorkingDir()
        return '{}/saved-media-{}'.format(wd, os.path.basename(self.current_project_filename))

    def getSavedMediaLog(self):
        #get path for an existing saved media log file; return None otherwise
        saved_media_log = self.getSavedMediaLogPath()
        if os.path.exists(saved_media_log):
            return saved_media_log
        return None

    def __clearSavedMediaLog(self):
        saved_media_log = self.getSavedMediaLog()
        saved_paths = []
        if saved_media_log:
            with open(saved_media_log, encoding='utf-8') as f:
                saved_paths = f.readlines()
        for pth in saved_paths:
            pth = pth.strip()
            try:
                os.remove(pth)
            except: # try another time, maybe open?
                self.addPossibleRemoval(pth)
        if saved_media_log:
            try:
                os.remove(saved_media_log)
            except: # try another time, maybe open?
                self.addPossibleRemoval(saved_media_log)

    def __applyChanges(self, changes_file=None):
        if not changes_file:
            changes_file = self.getChangesFile()
        if changes_file:
            changes = eval('[{}]'.format(io.open(changes_file, 'r', encoding='utf-8').read()).replace('null', 'None').replace('true', 'True').replace('false', 'False'))
            signs = [change for change in changes if change.__contains__('id')]
            name = [change for change in changes if change.__contains__('projectName')]
            sign_language = [change for change in changes if change.__contains__('signLanguage')]
            project_version = [change for change in changes if change.__contains__('versionId')]
            date_time = [change for change in changes if change.__contains__('modifiedDateTime')]
            descripts = [change for change in changes if change.__contains__('projectDescription')]
            gram_cats = [change for change in changes if change.__contains__('grammarCategories')]
            languages = [change for change in changes if change.__contains__('writtenLanguages')]
            dialects = [change for change in changes if change.__contains__('dialects')]
            if name:
                self.project.name = name[-1].get('projectName', '')
            if sign_language:
                self.project.sign_language = sign_language[-1].get('signLanguage', '')
            if project_version:
                self.project.version_id = project_version[-1].get('versionId')
            if date_time:
                self.project.last_save_datetime = date_time[-1].get('modifiedDateTime')
            if descripts: #apply last change
                self.project.description = descripts[-1].get('projectDescription', '')
            if gram_cats:
                self.project.grammar_categories = [GrammarCategory(gc) for gc in gram_cats[-1].get('grammarCategories', [])]
            if languages:
                self.project.writtenLanguages = [WrittenLanguage(lang) for lang in languages[-1].get('writtenLanguages', [])]
            if dialects:
                self.project.dialects = [Dialect(dialect) for dialect in dialects[-1].get('dialects', [])]

            def show_progress():
                txt = qApp.instance().translate('ProjectManager', 'Applying changes')
                if hasattr(qApp.instance(), 'start_dlg'):
                    progress_dlg = qApp.instance().start_dlg
                    progress_dlg.setProgressText(txt)
                    progress_dlg.setModal(True) #important; will stop mainwindow from showing until changes applied; dlg deleted in the showing of mainwindow
                    qApp.instance().pm.save_progress.connect(progress_dlg.onProgress)
                else:
                    qApp.instance().getMainWindow().setupProgress(txt)

            self.setSaveProgressDuration(signs)
            saved_signs = [sign for sign in signs if sign.get('saved', False)]
            unsaved_signs = [sign for sign in signs if not sign.get('saved', False)]
            for sign in saved_signs:
                self.saveSign(sign, record=False, update_last_change=False)
            # NOTE: can't think of why there would be more than one unsaved sign, and it would be the last in the list
            # either save now or discard change; maybe this change is the one which crashed the program???
            if unsaved_signs:
                msgBox = QMessageBox()
                msgBox.setIcon(QMessageBox.Question)
                msgBox.setTextFormat(Qt.RichText)
                msgBox.setWindowTitle(' ')
                msgBox.setText('<b style="color: blue;">{}</b>'.format(qApp.instance().translate('ProjectManager', "Unsaved Changes")))
                msgBox.setInformativeText(qApp.instance().translate('ProjectManager', "<center><p>SooSL closed unexpectedly and left some changes unsaved.</p><p>Do you want to save those changes now?</p></center>"))
                msgBox.setStandardButtons(QMessageBox.Yes |  QMessageBox.No)
                yes_btn, no_btn = msgBox.buttons()
                yes_btn.setIcon(QIcon(":/thumb_up.png"))
                no_btn.setIcon(QIcon(":/thumb_down.png"))
                msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('ProjectManager', "Save"))
                msgBox.button(QMessageBox.No).setText(qApp.instance().translate('ProjectManager', "Discard"))
                msgBox.setDefaultButton(QMessageBox.Yes)
                if msgBox.exec_() == QMessageBox.Yes:
                    if self.acquireFullProjectLock():
                        show_progress()
                        for sign in unsaved_signs:
                            self.saveSign(sign, record=False, update_last_change=True)
                        self.releaseFullProjectLock(self)
                else:
                    self.__removeUnsavedChanges()
                    self.__clearSavedMediaLog()

    def isSqliteReadWrite(self, file_path):
        db = QSqlDatabase.addDatabase("QSQLITE", file_path)
        db.setDatabaseName(file_path)
        message = None
        if db.open():
            query = QSqlQuery(db)
            query.prepare("""SELECT pass_message FROM project""")
            query.exec_()
            while query.next():
                message = query.value(0)
            db.close()
            QSqlDatabase.removeDatabase(file_path)
        if message and csaw.canReadWrite(message):
            return True
        return False

    def isReadWrite(self, file_path):
        if not file_path:
            return False
        file_path = file_path.replace('\\', '/')
        info = self.getKnownProjectInfo(file_path)
        if info:
            return info[0]
        d = False
        value = False
        if file_path.endswith('.enc'):
            file_path = self.unsecure(file_path, False)
            d = True
        ext = os.path.splitext(file_path)[1]
        if ext == '.json' and os.access(file_path, os.W_OK):
            value = True
        elif ext == '.sqlite':
            value = self.isSqliteReadWrite(file_path)
        elif ext in ['.zoozl']:
            if not os.access(file_path, os.W_OK): #latest version, contains .json file which is read-only
                value = False
            else: #may be a new read-write .json, an old read-write .sqlite or old read-only .sqlite version;
                # need to look inside the archive
                try:
                    z = ZipFile(file_path, 'r')
                except:
                    value = False
                else:
                    info = z.infolist()#[:10] #10 is random; no need to check entire list; project file(s) will be in the first few items
                    info = [i for i in info if (i.filename.endswith('.json') or i.filename.endswith('.sqlite') or i.filename.endswith('.sqlite.enc'))]
                    filename = None
                    info_json = [i for i in info if i.filename.endswith('.json')]
                    if info_json: # .json file found; will be read-write if we are in this clause
                        value = True
                    else: # look for .sqlite or .enc file
                        info_sqlite = [i for i in info if i.filename.endswith('.sqlite')]
                        if info_sqlite:
                            filename = info_sqlite[0].filename
                        else:
                            info_enc = [i for i in info if i.filename.endswith('.enc')]
                            if info_enc:
                                filename = info_enc[0].filename
                    if filename: # if we've found a possible file, let extract it
                        tmp_file = os.path.join(qApp.instance().getTempDir(), os.path.basename(filename))
                        tmp_file = tmp_file.replace('\\', '/')
                        with open(tmp_file, 'wb') as f:
                            f.write(z.read(filename))
                        file_path = tmp_file
                        if tmp_file.endswith('.enc'):
                            file_path = self.unsecure(tmp_file, True)
                        value = self.isSqliteReadWrite(file_path)
                        d = True
        if d:
            os.remove(file_path)
        return value

    def exportProject(self):
        exporter = Exporter(self)
        exporter.exportProject()

    def importProject(self):
        importer = Importer(self)
        importer.importProject()

    def setProjectSettings(self, project):
        settings = qApp.instance().getSettings()
        name = project.filename
        settings.setValue("lastOpenedDatabase", name)
        self.selected_lang_ids = [1]
        self.search_lang_id = 1
        if name:
            selected_lang_ids = settings.value('ProjectSettings/{}/selected_lang_ids'.format(name))
            if not selected_lang_ids:
                selected_lang_ids = project.getWrittenLanguageIds()
            if selected_lang_ids:
                selected_lang_ids = [int(i) for i in selected_lang_ids]
                settings.setValue('ProjectSettings/{}/selected_lang_ids'.format(name), selected_lang_ids)
                self.selected_lang_ids = selected_lang_ids

            search_lang_id = settings.value('ProjectSettings/{}/search_lang_id'.format(name))
            if not search_lang_id:
                search_lang_id = self.getFocalLangID()
            if search_lang_id:
                settings.setValue('ProjectSettings/{}/search_lang_id'.format(name), search_lang_id)
                self.search_lang_id = int(search_lang_id)
            settings.sync()

    def removeDeletedFilesOnClose(self):
        for pr in self.possible_removals:
            pr = pr.replace('\\', '/')
            if os.path.exists(pr):
                fail = False
                if os.path.isdir(pr):
                    try:
                        shutil.rmtree(pr)
                    except:
                        fail = True
                else:
                    try:
                        os.remove(pr)
                    except:
                        fail = True
                if fail:
                    removals_file = os.path.join(self.project.project_dir, 'files_to_remove.txt')
                    with io.open(removals_file, 'a', encoding='utf-8') as f:
                        f.write('{},'.format(pr))
        self.possible_removals.clear()

    def addPossibleRemoval(self, pth):
        if pth:
            pth = pth.replace('\\', '/')
            if pth not in self.possible_removals:
                self.possible_removals.append(pth)

    def removePossibleRemoval(self, pth):
        if pth:
            pth = pth.replace('\\', '/')
            if pth in self.possible_removals:
                self.possible_removals.remove(pth)

    ##NOTE: No longer encrypting by default on close 0.8.7 (161116)
    def closeProject(self, encrypt=False, return_project_pth=False, emit=True, network=True):
        """close currently open project database
        """
        project_filename = self.current_project_filename
        if project_filename and network:
            try:
                self.releaseSignLocks()
            except:
                pass
            try:
                self.releaseProjectLock()
            except:
                pass
            try:
                self.releaseFullProjectLock()
            except:
                pass
            try:
                self.releaseProjectIDLock()
            except:
                pass
            self.fileSystemWatcher.removePath(project_filename)
        if project_filename:
            self.closeProjectSession()
            self.cleanTempDir()
            self.removeDeletedFilesOnClose()
            self.setCurrentProject(None)
            self.sign = {}
            if emit:
                self.project_closed.emit()
            if return_project_pth:
                return project_filename #old project name
        return None

    def amendProjectDialectList(self, _dialects):
        if _dialects:
            self.project.amendProjectDialects(_dialects)

    def amendLanguageList(self, langs):
        if langs:
            self.project.amendLanguageList(langs)

    def amendGramCatsList(self, types):
        if types:
            self.project.amendGramCatsList(types)

    def openLast(self):
        """open the last used project database
        """
        settings = qApp.instance().getSettings()
        last_filename = settings.value("lastOpenedDatabase")

        if last_filename:
            enc = last_filename + '.enc'
            if os.path.exists(enc):
                try:
                    return self.openProject(enc)
                except:
                    return None
            elif os.path.exists(last_filename):
                try:
                    return self.openProject(last_filename)
                except:
                    return None
            else:
                return None

    def  __setupDirectories(self, location, project_id, filename):
        project_dir = os.path.join(location, project_id)
        try:
            os.makedirs(project_dir)
        except:
            if not os.path.exists(filename):
                #database does not exist but directories do, perhaps from aborted/failed attempt
                return True
            else:
                return False ## NOTE: if project_dir already exists; give user choice to open existing database???
        else:
            sign_dir = os.path.join(project_dir, '_signs')
            sent_dir = os.path.join(project_dir, '_sentences')
            ex_picts_dir = os.path.join(project_dir, '_extra_pictures')
            ex_videos_dir = os.path.join(project_dir, '_extra_videos')
            for _dir in [sign_dir, sent_dir, ex_picts_dir, ex_videos_dir]:
                try:
                    os.makedirs(_dir)
                except:
                    pass #shouldn't happen as you will only get here if 'project_dir' doesn't already exist
            return True

    def __authorizeUser(self):
        """authorize user for editing (json)
        """
        if self.project:
            return self.project.writePermission
        return True

    def secure(self, filename, inplace=False):
        _file = csaw.secureFile(filename)
        if inplace:
            try:
                os.remove(filename)
            except:
                pass
        return _file

    def unsecure(self, filename, inplace=False):
        _file = csaw.unsecureFile(filename)
        if inplace:
            os.remove(filename)
        return _file

    def setReadWrite(self, _bool):
        """set read-write/read-only permission for project."""
        self.setWritePermission(self.current_project_filename, _bool)

    def newSign(self, sign_filename, texts):
        self.sign = self.project.getNewSign(sign_filename, texts)
        self.makeNewSignFile(self.sign.id)
        self.signs = [self.sign]
        self.signs_found.emit(self.signs)

    def getTempId(self):
        """ new things need a unique temp id until they are saved
        """
        _id = 'n'
        while _id in self.tempIds:
            _id = '{}n'.format(_id)
        self.tempIds.append(_id)
        return _id

    def extraMediaAdded(self):
        self.onAmended()

    def extraMediaRemoved(self):
        self.onAmended()

    def recordNameChange(self, name):
        self.__recordChanges({'projectName': name})

    def recordSignLanguageChange(self, sign_language):
        self.__recordChanges({'signLanguage': sign_language})

    def recordVersionIdChange(self, version_id):
        self.__recordChanges({'versionId': version_id})

    def recordProjectCreatorChange(self, project_creator):
        self.__recordChanges({'projectCreator': project_creator})

    def recordDateTimeChange(self, date_time):
        self.__recordChanges({'modifiedDateTime': date_time})

    def recordDescriptionChange(self, description):
        self.__recordChanges({'projectDescription': description})

    def recordGramCatChange(self, grammar_categories):
        self.__recordChanges({'grammarCategories': [gc.toJsn() for gc in grammar_categories]})

    def recordLangListChange(self, languages):
        self.__recordChanges({'writtenLanguages': [lang.toJsn() for lang in languages]})

    def recordDialectListChange(self, dialects):
        self.__recordChanges({'dialects': [dialect.toJsn() for dialect in dialects]})

    def recordImportInfo(self, zoozl_file, dest_dir):
        dest_dir = dest_dir.replace('\\', '/')
        import_file = '{}/import_crash.json'.format(qApp.instance().getWorkingDir())
        with io.open(import_file, 'a', encoding='utf-8') as f:
            json.dump({'zoozl': zoozl_file, 'dest': dest_dir}, f, sort_keys=False, indent=4, ensure_ascii=False)
            f.write(',\n')

    def removeImportInfo(self):
        import_file = '{}/import_crash.json'.format(qApp.instance().getWorkingDir())
        try:
            os.remove(import_file)
        except:
            self.addPossibleRemoval(import_file)

    def recordExportInfo(self, project_file, dst_zip, existing_dst_permission):
        dst_zip = dst_zip.replace('\\', '/')
        export_file = '{}/export_crash.json'.format(qApp.instance().getWorkingDir())
        failed_exports = []
        # read from json
        if os.path.exists(export_file):
            with io.open(export_file, 'r', encoding='utf-8') as f:
                j = json.load(f)
                failed_exports = j.get("exports", [])
        failed_exports.append({'project': project_file, 'dest': dst_zip, 'existing_read_write': existing_dst_permission})
        # write to json
        with io.open(export_file, 'w', encoding='utf-8') as f:
            json.dump({'exports': failed_exports}, f, sort_keys=False, indent=4, ensure_ascii=False)

    def removeExportInfo(self):
        export_file = '{}/export_crash.json'.format(qApp.instance().getWorkingDir())
        try:
            os.remove(export_file)
        except:
            self.addPossibleRemoval(export_file)

    def __recordChanges(self, data):
        changes_file = self.getChangesFilePath()
        mode = 'a'
        if not os.path.exists(changes_file):
            mode = 'w'
        with io.open(changes_file, mode, encoding='utf-8') as f:
            json.dump(data, f, sort_keys=False, indent=4, ensure_ascii=False)
            f.write(',\n')

    def __removeUnsavedChanges(self):
        changes_file = self.getChangesFile()
        if changes_file:
            changes = eval('[{}]'.format(io.open(changes_file, 'r', encoding='utf-8').read()).replace('null', 'None').replace('true', 'True').replace('false', 'False'))
            saved_changes = [change for change in changes if not change.__contains__('saved') or change.get('saved', False) is True]
            if saved_changes: #NOTE: will there ever be???
                with io.open(changes_file, 'w', encoding='utf-8') as f:
                    f.write('')
                with io.open(changes_file, 'a', encoding='utf-8') as f:
                    for change in saved_changes:
                        json.dump(change, f, sort_keys=False, indent=4, ensure_ascii=False)
                        f.write(',\n')
            else:
                os.remove(changes_file)

    def isCorruptVideoFile(self, file_path):
        video = Video([file_path])
        if video.isCorrupt():
            return True
        return False

    def isCorruptPictureFile(self, file_path):
        picture = Picture([file_path])
        if picture.isCorrupt():
            return True
        return False

    def appendVideo(self, media_objects, video):
        if video.isCorrupt():
            return
        new_path = video.newPath()
        if os.path.exists(new_path):
            ## NOTE: show dialog and give choice to overwrite?
            if self.isCorruptVideoFile(new_path):
                os.remove(new_path)
        #         media_objects.append(video)
        #     else:
        #         self.removePossibleRemoval(new_path) #NOTE: probably deleted and re-added, don't take chance on deletion
        # else:
        media_objects.append(video)

    def appendPicture(self, media_objects, picture):
        if picture.isCorrupt():
            return
        new_path = picture.newPath()
        if os.path.exists(new_path):
            ## NOTE: show dialog and give choice to overwrite?
            if self.isCorruptPictureFile(new_path):
                os.remove(new_path)
        #         media_objects.append(picture)
        #     else:
        #         self.removePossibleRemoval(new_path) #NOTE: probably deleted and re-added, don't atke chance on deletion
        # else:
        media_objects.append(picture)

    def getMediaPaths(self, sign_list):
        paths = []
        for sign in sign_list:
            try:
                path = sign.get('path')
            except:
                paths.append(sign.path)
            else:
                paths.append(path)
            senses = []
            try:
                pth = sign.get('media_object')[0]
            except:
                pth = sign.media_object[0]
            if pth not in paths: #in the case of a replacement
                paths.append(pth)
            try:
                senses = sign.get('senses', [])
            except:
                senses = sign.senses
            for sense in senses:
                sentences = []
                try:
                    sentences = sense.get('sentences', [])
                except:
                    sentences = sense.sentences
                for sent in sentences:
                    try:
                        path = sent.get('path', [])
                    except:
                        paths.append(sent.path)
                    else:
                        paths.append(path)
                    try:
                        pth = sent.get('media_object')[0]
                    except:
                        pth = sent.media_object[0]
                    if pth not in paths: #in the case of a replacement
                        paths.append(pth)
            extra_media = []
            try:
                extra_media = sign.get('extraMediaFiles', [])
            except:
                extra_media = sign.extra_media_files
            for em in extra_media:
                try:
                    path = em.get('path')
                except:
                    paths.append(em.path)
                else:
                    paths.append(path)
        return paths

    def setSaveProgressDuration(self, sign_list):
        file_durations = []
        try:
            paths = self.getMediaPaths(sign_list)
        except:
            pass
        else:
            for path in paths:
                media = None
                if self.isVideo(path):
                    media = Video([path])
                elif self.isPicture(path):
                    media = Picture([path])
                if media:
                    if not self.isInProject(path) or \
                        (os.path.exists(path) and media.isCorrupt()): # new media \ leftover from crashed save
                            duration = media.duration
                            file_durations.append((path, duration))
        dlg = qApp.instance().getProgressDlg()
        dlg.setFileDurations(file_durations)

    def getNewId(self):
        # use difference between current time and 'SooSL Epoch' in microseconds as unique identifier
        if not hasattr(self, 'old_id'):
            dt = datetime.now(timezone.utc)
            self.old_id = int(str(self.getSooSLDateTime(dt)).replace('.', ''))
        new_id = self.old_id
        while new_id == self.old_id:
            dt = datetime.now(timezone.utc)
            new_id = int(str(self.getSooSLDateTime(dt)).replace('.', ''))
        self.old_id = new_id
        return new_id

    def getNewSignId(self):
        return self.getNewId()

    def getNewSenseId(self):
        return self.getNewId()

    def getNewSentenceId(self):
        return self.getNewId()

    def getNewExtraMediaId(self):
        return self.getNewId()

    def makeNewSignFile(self, sign_id):
        #sign_id = os.path.splitext(os.path.basename(self.joinFilenameId(sign_filename, sign_id)))[0] # 0.9.4
        filename = f'{self.project.project_dir}/_signs/{sign_id}.json'
        with io.open(filename, 'w', encoding='utf-8') as f:
            self.acquireSignLocks([sign_id])
            json.dump({'id': sign_id, 'new': True}, f, sort_keys=False, indent=4, ensure_ascii=False) # give some initial content so its not empty

    def saveSign(self, sign_data, record=True, update_last_change=True):
        #pprint(sign_data)
        #for key, value in sign_data.items(): print(key, '|', value)
        self.abort_flag = False
        # deal with deletions
        sign_data['saved'] = False
        sign_data['modifiedDateTime'] = datetime.now(timezone.utc).isoformat()
        if record:
            self.__recordChanges(sign_data) # record changes about to be made in changes.json

        if sign_data.get('delete', False):
            self.addPossibleRemoval(sign_data.get('path', None))
            extra_media_files = [m.get('path') for m in sign_data.get('extraMediaFiles', [])]
            for emf in extra_media_files:
                self.addPossibleRemoval(emf)
        senses = sign_data.get('senses', [])
        for sense in reversed(senses):
            sentences = sense.get('sentences', [])
            for sent in reversed(sentences):
                if sent.get('delete', False) or sign_data.get('delete', False):
                    self.addPossibleRemoval(sent.get('path', None))
                    sentences.remove(sent)
            if sense.get('delete', False):
                senses.remove(sense)
        if not senses:
            gloss_texts = []
            for lang in self.project.writtenLanguages:
                gloss_texts.append({'langId': lang.id,
                                    'text': ''
                                    })
            senses.append({"id": self.getTempId(),
                           "dialectIds": [self.getFocalDialectId()],
                           "glossTexts": gloss_texts
                           })
        if sign_data.get('delete_extraTexts', False):
            sign_data.get("extraTexts", []).clear()

        media_objects = []
        # update new ids
        if sign_data.get('new', False):
            new_sign_id = self.getNewSignId()
            sign_data['id'] = new_sign_id
            _dir = self.get_root('sign')
            media_object = self.__mediaObject(sign_data, 'sign')
            video = Video(media_object, _dir, new_sign_id)
            self.appendVideo(media_objects, video)
            sign_data['path'] = video.newPath()
            sign_data['hash'] = media_object.getHash()
        else:
            media_object = self.__mediaObject(sign_data, 'sign')
            if media_object and media_object.filename != media_object.orig_filename:
                _dir = self.get_root('sign')
                _id = sign_data.get('id')
                video = Video(media_object, _dir, _id)
                self.appendVideo(media_objects, video)
                sign_data['path'] = video.newPath()
                sign_data['hash'] = media_object.getHash()

        senses = sign_data.get('senses', [])
        old_sense_ids = []
        old_sent_ids = []
        for sense in senses:
            if isinstance(sense.get('id', 'n'), str):
                new_id = self.getNewSenseId()
                old_sense_ids.append(new_id)
                sense['id'] = new_id

            sentences = sense.get('sentences', [])
            for sent in sentences:
                sent_id = sent.get('id', 'n')
                if isinstance(sent_id, str): #new
                    new_id = self.getNewSentenceId()
                    old_sent_ids.append(new_id)
                    sent['id'] = new_id
                    _dir = self.get_root('sent')
                    media_object = self.__mediaObject(sent, 'sent')
                    video = Video(media_object, _dir, new_id)
                    self.appendVideo(media_objects, video)
                    sent['path'] = video.newPath()
                    sent['hash'] = media_object.getHash()
                else:
                    media_object = self.__mediaObject(sent, 'sent')
                    if media_object and media_object.filename != media_object.orig_filename:
                        _dir = self.get_root('sent')
                        _id = sent.get('id')
                        video = Video(media_object, _dir, _id)
                        self.appendVideo(media_objects, video)
                        sent['path'] = video.newPath()
                        sent['hash'] = media_object.getHash()

        extra_media = sign_data.get('extraMediaFiles', [])

        # mark deleted extra media for removal
        extra_media_paths = [i.get('path') for i in extra_media]
        try:
            old_extra_media_paths = [i.path for i in self.sign.extra_media_files]
        except:
            pass # new sign; no self.sign
        else:
            for pth in old_extra_media_paths:
                if pth not in extra_media_paths:
                    self.addPossibleRemoval(pth)

        extra_video_ids = []
        extra_picture_ids = []
        for media in extra_media:
            media_id = media.get('id', 'n')
            media_path = media.get('path')
            new_path = None
            if isinstance(media_id, str):
                new_id = self.getNewExtraMediaId()
                if self.isVideo(media_path):
                    extra_video_ids.append(new_id)
                    _dir = self.get_root('ex_video')
                    media_object = self.__mediaObject(media, 'ex_video')
                    video = Video(media_object, _dir, new_id)
                    self.appendVideo(media_objects, video)
                    new_path = video.newPath()
                else: #picture
                    extra_picture_ids.append(new_id)
                    _dir = self.get_root('ex_picture')
                    media_object = self.__mediaObject(media, 'ex_picture')
                    pict = Picture(media_object, _dir, new_id)
                    self.appendPicture(media_objects, pict)
                    new_path = pict.newPath()
                media['id'] = new_id
                media['path'] = new_path
                media['hash'] = media_object.getHash()

        self.sign_data = sign_data
        media_saver = MediaSaver(media_objects, update_last_change)
        media_saver.finished.connect(self.onSaveFinished)
        media_saver.remove_file.connect(self.addPossibleRemoval)
        media_saver.dont_remove_file.connect(self.removePossibleRemoval)
        self.abort_save.connect(media_saver.abort)
        media_saver.save()

    def __mediaObject(self, data, _type):
        media_object = data.get('media_object', None)
        if media_object and not isinstance(media_object, MediaObject):
            media_object = MediaObject(*media_object)
        if not media_object:
            media_object = MediaObject()
            media_object.filename = data.get('path', '')
        media_object.mediatype = _type
        return media_object

    def sooslOlderThan(self, version):
        soosl_version = self.getSooSLVersion()
        return self.olderThan(soosl_version, version)

    def olderThan(self, version, current_version):
        if version == current_version:
            return False
        pattern = r'[^0-9]' # possible separators between version and build are non-numeric
        # new(?) version
        v1, v2, v3 = version.split('.')
        v1 = int(v1)
        v2 = int(v2)
        micro = re.split(pattern, v3)
        v3 = int(micro[0])
        build = 0
        try:
            build = int(micro[1])
        except:
            pass
        # current version
        cv1, cv2, cv3 = current_version.split('.')
        cv1 = int(cv1)
        cv2 = int(cv2)
        micro = re.split(pattern, cv3)
        cv3 = int(micro[0])
        cbuild = 0
        try:
            cbuild = int(micro[1])
        except:
            pass

        if v1 < cv1:
            return True
        elif v1 == cv1 and v2 < cv2:
            return True
        elif v1 == cv1 and v2 == cv2 and v3 < cv3:
            return True
        elif v1 == cv1 and v2 == cv2 and v3 == cv3 and build < cbuild:
            return True
        else:
            return False

    def updateProjectFile(self):
        if self.project.updateProject():
            changes = self.getChangesFile()
            if changes and os.path.exists(changes):
                os.remove(changes)

    def updateSignFiles(self, gram_cats=[], dialects=[], langs=[]):
        if gram_cats:
            self.project.updateSignFileGramCats(gram_cats)
        if dialects:
            self.project.updateSignFileDialects(dialects)
        if langs:
            self.project.updateSignFileLangs(langs)

    def onSaveFinished(self, update_last_change=True):
        saved_media_log = self.getSavedMediaLog()
        if not self.abort_flag:
            prev_id = None
            try:
                prev_id = self.sign.id
            except:
                pass ## NOTE:probably attempt to save after losing and regaining network access???
            self.sign = self.project.saveSign(self.sign_data)
            self.signs = [self.sign]
            self.signs_found.emit(self.signs)
            if update_last_change:
                self.__updateLastChange()
            delete_id = False
            if self.sign_data.get('delete', False):
                delete_id = self.sign_data.get('id')
            if self.project.updateSignFile(self.sign, delete_id=delete_id):
                if self.acquireProjectLock():
                    self.project.updateProjectTimeStamp(self.project.last_save_datetime)
                    self.updateKnownProjectInfoDatetime(self.project.filename, self.project.last_save_datetime)
                    self.releaseProjectLock()
                else:
                    update_project_time = '{}/update_datetime.txt'.format(self.project.project_dir)
                    with io.open(update_project_time, 'w', encoding='utf-8') as f:
                        f.write(self.project.last_save_datetime)
                    ## If lock cannot be acquired, write a 'timestamp' file to the
                    # project directory which will be read and used to update the project file (if later)
                    # when the other user releases the lock. See project.checkOtherUsersProjectDateTime()

                changes = self.getChangesFile()
                if changes and os.path.exists(changes):
                    os.remove(changes)
                if saved_media_log:
                    os.remove(saved_media_log)
        else:
            if saved_media_log:
                self.__clearSavedMediaLog()

        self.save_finished.emit()
        self.tempIds.clear()
        self.delete_flag = False

    def isInProject(self, filename):
        filename = filename.replace('\\', '/')
        project_dir = self.project.project_dir
        if filename.startswith(project_dir):
            return True
        return False

    def addNewSense(self):
        new_sense = self.project.getNewSense()
        self.newSense.emit(new_sense)

    def addNewSentence(self, filename, gloss_id, texts):
        new_sentence = self.project.getNewSentence(filename, gloss_id, texts)
        self.newSentence.emit((gloss_id, new_sentence))

    def saveAuthorsMessage(self, message):
        self.project.setDescription(message)

    def saveProjectName(self, project_name):
        self.project.setProjectName(project_name)
        self.updateKnownProjectInfoName(self.project.filename, project_name)

    def saveProjectSignLanguage(self, sign_language):
        self.project.setProjectSignLanguage(sign_language)

    def saveProjectVersionId(self, version_id):
        self.project.setProjectVersionId(version_id)
        self.updateKnownProjectInfoVersion(self.project.filename, self.project.version_id)

    def saveProjectCreator(self, project_creator):
        self.project.setProjectCreator(project_creator)

    def saveProjectDateTime(self):
        self.project.setProjectDateTime()
        self.updateKnownProjectInfoDatetime(self.project.filename, self.project.last_save_datetime)

    def checkOtherUsersProjectDateTime(self):
        if self.project:
            self.project.checkOtherUsersProjectDateTime()

    def pendingProjectTimestampChange(self):
        return self.project.checkOtherUsersProjectDateTime(set=False)

    #https://stackoverflow.com/questions/952914/how-to-make-a-flat-list-out-of-list-of-lists
    def __flat(self, _list): # [[1],[2],[3]] ==> [1,2,3]
        return [item for sublist in _list for item in sublist]

    def getOriginalHash(self, filename):
        root, tail = os.path.split(filename)
        if root.endswith('signs'):
            hashes = [sign.hash for sign in self.project.signs if sign.path.endswith('/_signs/{}'.format(tail))]
            if hashes:
                return hashes[0]
            return ''
        elif root.endswith('sentences'):
            senses = self.__flat([sign.senses for sign in self.project.signs])
            sentences = self.__flat([sense.sentences for sense in senses])
            hashes = [sent.hash for sent in sentences if sent.path.endswith('/sentences/{}'.format(tail))]
            if hashes:
                return hashes[0]
            return ''
        elif root.endswith('extra_videos') or root.endswith('extra_pictures'):
            extra_media = self.__flat([sign.extra_media_files for sign in self.project.signs])
            hashes = [media.hash for media in extra_media if media.path.endswith('{}'.format(tail))]
            if hashes:
                return hashes[0]
            return ''

    def getHash(self, filename):
        _dir = os.path.dirname(filename)
        proj_dir = os.path.dirname(self.current_project_filename)
        if _dir.startswith(proj_dir):
            _md5 = self.getOriginalHash(filename)
            return _md5 # we want the hash from the original file which was imported into SooSL;
            # not the hash of an already converted file
        return self.getFreshHash(filename)

    def getFreshHash(self, filename):
        filename = """{}""".format(filename)
        contents = ''
        _md5 = ''
        try:
            if filename.endswith('.json'):
                ## newline characters can differ between OS's
                ## look inside sign files; create hash based on their string data using a consistent newline character;
                ## otherwise, the same file in different OS's may appear different and trigger unnessary web upload
                with open(filename, 'r', encoding='utf-8', newline='\n') as f:
                    jsn = json.load(f)
                    contents = json.dumps(jsn, sort_keys=False, indent=4).encode('utf-8')
                    # contents = json.dumps(jsn, sort_keys=False, indent=4, ensure_ascii=False).encode('utf-8')
                    # # encoding changes made in SooSL 0.9.4, but for web upload and inventory creation,
                    # # this is not necessary and causes compatibility problems with 0.9.3, i.e. Every sign hash in an
                    # 0.9.4 upload inventory would look different to an 0.9.3 inventory and would trigger a full upload
                    # of all signs even when there were no changes.
            else:
                with open(filename, 'rb') as _file:
                    contents = _file.read()
            if contents:
                _md5 = csaw.hashlib.md5(contents).hexdigest()
        except:
            pass
        return str(_md5)

    def fileInProject(self, pth, _type):
        if pth is None:
            pth = ''
        if os.path.exists(pth):
            # pth from within project directories
            if os.path.normpath(pth).startswith(os.path.normpath(self.getCurrentProjectDir())):
                return pth

            return self.getFileByHash(pth, _type) # None returned if no file found
        else:
            return None

    def getFileByHash(self, pth, _type):
        _md5 = self.getHash(pth)
        if _type == 'ex_media':
            if self.isPicture(pth):
                _type = 'ex_picture'
            else:
                _type = 'ex_video'
        types = ['sign', 'sent', 'ex_video', 'ex_picture']
        types.remove(_type)
        types.insert(0, _type)
        _file = ''
        for t in types:
            if t == 'sign':
                _file = self.project.getSignVideoByHash(_md5)
            elif t == 'sent':
                _file = self.project.getSentenceVideoByHash(_md5)
            elif t == 'ex_video':
                _file = self.project.getExVideoByHash(_md5)
            elif t == 'ex_picture':
                _file = self.project.getExPictureByHash(_md5)
            if _file:
                break
        return _file

    @property
    def data_dir(self):
        proj = self.current_project_filename
        if proj:
            return os.path.split(proj)[0]
        else:
            return None

    def getTypeDir(self, _type, pth):
        if _type == 'ex_media':
            if self.isPicture(pth):
                _type = 'ex_picture'
            else:
                _type = 'ex_video'
        return self.get_root(_type)

    def get_root(self, media_type='sign'):
        root = os.path.join(self.data_dir, '_signs')
        if media_type == 'ex_video':
            root = os.path.join(self.data_dir, '_extra_videos')
        elif media_type == 'ex_picture':
            root = os.path.join(self.data_dir, '_extra_pictures')
        elif media_type == 'sent':
            root = os.path.join(self.data_dir, '_sentences')
        elif media_type == 'gloss':
            pass #currently same as 'sign'
        return root

    def __cannotRemoveMessage(self, pth):
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setText("<p><b>{}</b></p><p>{}</p>".format(qApp.instance().translate('ProjectManager', 'Cannot remove file; it is being used'), pth))
        msgBox.setInformativeText(qApp.instance().translate('ProjectManager', "Close other programs which may be using the file and try again."))
        t1 = qApp.instance().translate('ProjectManager', 'Look for:')
        t2 = qApp.instance().translate('ProjectManager', 'Another SooSL window')
        t3 = qApp.instance().translate('ProjectManager', 'Video player or picture viewer')
        msgBox.setDetailedText(
            """{}
            1. {}
            2. {}
            """)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setDefaultButton(QMessageBox.Ok)
        return msgBox.exec_()

    def abortSave(self):
        self.abort_flag = True
        self.abort_save.emit()
        self.__removeUnsavedChanges()

    def amendExVideos(self, new, old, sign_id):
        to_remove = []
        for media in old:
            try:
                new.remove(media) #remove common filenames
            except:
                to_remove.append(media) #if not in new_filenames, then it is meant for removal
        for media in new: #list should now contain only new filenames
            media2 = copy.deepcopy(media)
            media2.rotation = 0
            media2.crop = None
            media2.transcode_crop = None
            try:
                to_remove.remove(media2)
            except:
                name, _id = self.addExVideo(media.filename, sign_id)
                media.filename = name
                media.id = _id
            else:
                self.amendExVideo(media, sign_id)
        for media in to_remove:
            filename = media.filename
            filename_id = media.id
            self.removeExVideo(filename, filename_id, sign_id)
        return new

    def amendExPictures(self, new, old, sign_id):
        to_remove = []
        for media in old:
            try:
                new.remove(media) #remove common filenames
            except:
                to_remove.append(media) #if not in new_filenames, then it is meant for removal
        for media in new: #list should now contain only new filenames
            media2 = copy.deepcopy(media)
            media2.rotation = 0
            media2.crop = None
            media2.transcode_crop = None
            try:
                to_remove.remove(media2)
            except:
                name, _id = self.addExPicture(media.filename, sign_id)
                media.filename = name
                media.id = _id
            else:
                self.amendExPicture(media, sign_id)
        for media in to_remove:
            filename = media.filename
            filename_id = media.id
            self.removeExPicture(filename, filename_id, sign_id)
        return new

    def getDestinationFile(self, filename):
        dst = None
        try:
            dst = self.sign_editor.media_dest_dict.get(filename).pop(0)
        except:
            pass
        return dst

    def setDestinationFile(self, src, dst):
        new_file_paths = self.sign_editor.media_dest_dict.get(src) #need full list if available; can't just use getDestinationFile()
        if not new_file_paths:
            self.sign_editor.media_dest_dict[src] = [dst]
        else:
            new_file_paths.append(dst)

    def getSigns(self):
        """return the list of signs stored by the application
        """
        return self.current_signs

    def getLangId(self, lang_name):
        if self.current_project_filename:
            return self.project.getWrittenLanguageId(lang_name)
        return 1

    def getLangName(self, lang_id):
        if self.current_project_filename:
            return self.project.getWrittenLanguageName(lang_id)
        return ''

    def getProjectLangIds(self):
        langs = self.project.writtenLanguages
        lang_ids = [l.id for l in langs]
        return lang_ids

    def getLangOrder(self):
        return self.getProjectLangIds()

    def getFocalLang(self):
        """return primary written language (lang__id, lang_name)
        """
        return self.project.focalLang()

    def getFocalLangID(self):
        try:
            return int(self.project.focalLangID)
        except:
            return None

    def getDialect(self, _id):
        """return a particular dialect by id
        """
        return [d for d in self.getAllDialects() if d._id == _id][0]

    def getAllDialects(self):
        """return dialects for current project
        """
        return self.project.dialects

    def getFocalDialectId(self):
        focal = [d.id for d in self.getAllDialects() if d.isFocal()]
        if focal:
            return focal[0]

    def getAllGramCats(self):
        return self.project.grammar_categories

    def getAuthorsMessage(self):
        return self.project.description

    def getSelectedDialectIds(self):
        if self.project:
            return self.project.selected_dialect_ids

    def getAllDeprecatedCodes(self):
        app_dir = qApp.instance().getAppDir()
        dtxt = os.path.join(app_dir, 'codes_deprecate.txt')
        if sys.platform.startswith('darwin') and not os.path.exists(dtxt):
            dtxt = os.path.join(os.path.dirname(app_dir), 'Resources', 'codes_deprecate.txt')
        with io.open(dtxt, 'r', encoding='utf-8') as deprecation_file:
            lines = [line for line in deprecation_file.read().splitlines() if not line.startswith('#')]
        deps = []
        for line in lines:
            codes = line.split(',') # may wish to add on same line in future?
            for c in codes:
                deps.append(c)
        return deps

    def setSelectedDialectIds(self, dialect_ids):
        self.project.selected_dialect_ids = dialect_ids

    def getGlossesForSign(self, sign=None):
        if not sign and self.sign:
            sign = self.sign
        if sign:
            return sign.senses
        return []

    def getTextsByMediaFile(self, filename, file_type): #sign, sent, ex_picture, ex_video
        texts = []
        if file_type in ['ex_video', 'ex_picture']:
            return texts

        filename = filename.replace('\\', '/')
        name = os.path.basename(filename)
        _md5 = self.getOriginalHash(filename)

        if file_type == 'sign':
            senses = self.__flat([sign.senses for sign in self.project.signs if (_md5 and sign.hash == _md5) or sign.path.endswith(name)])
            texts = self.__flat([sense.gloss_texts for sense in senses])
            texts = [t for t in texts if t.text]
            return texts
        elif file_type == 'sent':
            senses = self.__flat([sign.senses for sign in self.project.signs])
            sentences = self.__flat([sense.sentences for sense in senses])
            texts = self.__flat([sent.sentence_texts for sent in sentences if (_md5 and sent.hash == _md5) or sent.path.endswith(name)])
            _texts = []
            for t in reversed(texts):
                if not t.text or t.text in _texts:
                    texts.remove(t)
                else:
                    _texts.append(t.text)
            return texts
        return []

    def findSignById(self, sign_id, sense_id, sense_field):
        if not hasattr(self, 'project') or not self.project:
            self.signs_found.emit([])
            return
        qApp.instance().searchType = 'gloss'
        # try:
        #     qApp.processEvents()
        # except:
        #     pass
        # self.signs.clear()
        self.signs = [sign for sign in self.project.signs if sign.id == sign_id]
        if self.signs:
            self.sign = self.signs[0]
            senses = [s for s in self.sign.senses if s.id == sense_id]
            if senses:
                self.sign.current_sense_id = sense_id
                self.sign.current_sense_field = sense_field
            self.signs_found.emit([self.sign])
        else:
            self.signs_found.emit([])

    def sortSigns(self, signs):
        # sort signs inplace according to their text order in finderlist
        finder = qApp.instance().getMainWindow().finder_list
        sign_ids = [s.id for s in signs]
        sign_texts = finder.getSignTextList()
        sign_texts = [t for t in sign_texts if t.get('sign_id') in sign_ids]
        # enough to bring sign first in texts to front of signs list
        first_text = sign_texts[0]
        first_id = first_text.get('sign_id')
        first_sign = [s for s in signs if s.id == first_id][0]
        signs.remove(first_sign)
        first_sign.current_sense_id = 0
        first_sign.current_sense_field = 0
        signs.insert(0, first_sign)

    def findSignsByComponents(self, codes, signal=True):
        if not hasattr(self, 'project') or not self.project:
            self.signs_found.emit([])
            return
        if codes:
            qApp.instance().searchType = 'comp'
        dialect_ids = self.getSelectedDialectIds()
        self.signs = self.project.getSignsByComponent(codes, dialect_ids)
        if self.signs:
            # if current sign is in signs, bring to front of list
            try:
                self.signs.remove(self.sign)
            except:
                self.sortSigns(self.signs)
                self.sign = self.signs[0] # sign not in list
            else:
                self.signs.insert(0, self.sign)
            if signal:
                self.signs_found.emit(self.signs)
        else:
            self.sign = {}
            if signal:
                self.signs_found.emit([])

    def findSignsByFile(self, filename, emit=True):
        qApp.instance().searchType = 'file'
        _md5 = self.getHash(filename)
        signs = []
        if _md5:
            signs = [sign for sign in self.project.signs if sign.hash == _md5] # external file used before
        if not signs:
            name = os.path.basename(filename)
            signs = [sign for sign in self.project.signs if sign.path.endswith(name)] # file exists within project
        if signs:
            self.signs = signs
            self.sign = signs[0]
            if emit:
                self.signs_found.emit(self.signs)
            return True
        else:
            if emit:
                self.show_info.emit(" ", "No signs found")
            return False

    def signCountByCode2(self, code, dialect_ids, signs=[]):
        #dialect_ids = [d.id for d in dialects]
        if self.project:
            return self.project.getSignCountByComponent(code, dialect_ids, signs)

    def signCount2(self):
        if self.project:
            return self.project.getSignCount()

    def dialectStr(self, dialects):
        if dialects and isinstance(dialects[0], int): #list of dialect ids
            dialects = [d for d in self.project.dialects if d.id in dialects]
        dialect_str = ""
        if dialects: #list of dialects
            settings = qApp.instance().getSettings()
            show_focal = settings.value('showFocalDialect', False)
            if isinstance(show_focal, str):
                if show_focal.lower() == 'true':
                    show_focal = True
                else:
                    show_focal = False
            dialects = sorted(dialects, key=lambda x:x.name.lower())
            #dialects = sorted(dialects, key=lambda x:eval(str(x.focal).capitalize()), reverse=True)
            if not show_focal and len(dialects) == 1 and dialects[0].isFocal():
                dialect_str = ""
            else:
                abbr = [d.abbr for d in dialects]
                dialect_str = ", ".join(abbr)
        return dialect_str

    def dialectsFromStr(self, dialect_str):
        dialects = []
        if dialect_str:
            abbrs = [d.strip() for d in dialect_str.split(',')]
            dialects = [d for d in self.getAllDialects() if d.abbr in abbrs]
        return dialects

    def showWarning(self, short, long):
        self.show_warning.emit(short, long)

    def showMessage(self, message):
        self.show_message.emit(message)

    def updateConfiguration(self):
        """update configuration file if required
        """
        settings = qApp.instance().getSettings()
        #remove 'citationVideoDir' from settings; changed to 'signVideoDir' in 0.6.0
        cdv = settings.value('citationVideoDir')
        if cdv:
            settings.setValue('signVideoDir', cdv)
        settings.remove('citationVideoDir')
        #self.current_project name storage altered in 0.6.0
        settings.beginGroup("Databases/LastOpened") #pre 0.6.0 database?
        last = settings.value("filename")
        settings.endGroup()
        if last:
            last = last.replace('\\', '/')
            settings.setValue('lastOpenedDatabase', last)
            settings.sync()
        settings.beginGroup("Databases")
        projects = settings.childKeys()
        settings.endGroup()

        project_files = []
        if projects:
            project_files = [settings.value("Databases/{}".format(p)) for p in projects]
        settings.remove("Databases")
        #name change for default project location
        recent = settings.value('recentDatabases')
        if not recent:
            recent = []
        recent = [db.replace('archives', 'projects') for db in recent]
        project_files.extend(recent)

        last = settings.value('lastOpenedDatabase')
        if last and last.count('archives'):
            last = last.replace('archives', 'projects')
            last = last.replace('\\', '/')
            settings.setValue('lastOpenedDatabase', last)
            settings.sync()
        #font sizes made language specific in 0.8.4
        settings.remove('fontSize')
        settings.remove('ReportError') #removed in 0.8.5

        #0.9.0 change way projects are found; just save directories and search these for project files
        project_directories = list(set([os.path.dirname(os.path.dirname(d)).replace('\\', '/') for d in project_files]))
        if project_directories:
            self.setProjectLocations(project_directories)
        settings.remove('recentDatabases')
        settings.sync()

        #0.9.0 alteration as filename couldn't correctly be used as key on its own; split off first directory and used as first hierarchy
        for key in settings.allKeys():
            if not key.startswith('ProjectSettings') and \
                (key.endswith('selected_lang_ids') or \
                key.endswith('order') or \
                key.endswith('search_lang_id')):
                    if key.endswith('order'):
                        project_file = os.path.dirname(os.path.dirname(key))
                    else:
                        project_file = os.path.split(key)[0]
                    if not os.path.exists(project_file):
                        settings.remove(key)
                    else:
                        value = settings.value(key)
                        new_key = key.replace('\\', '/')
                        settings.setValue('ProjectSettings/{}'.format(new_key), value)
                        settings.remove(key)
        import_export_dir = settings.value('ExportDir', None)
        if import_export_dir:
            settings.remove('ExportDir')
            settings.remove('ImportDir')
            settings.setValue('ImportExportDirectories', [import_export_dir])

        # 0.9.2 (210914)
        # consolidate last opened media directories into one
        d = settings.value('signVideoDir')
        if d:
            settings.setValue('lastMediaDir', d)
        settings.remove('signVideoDir')
        settings.remove('exMediaDir')
        settings.remove('sentenceVideoDir')
        settings.remove('exVideoDir')
        settings.remove('exPictureDir')

        settings.sync()

    def getExportLocations(self):
        settings = qApp.instance().getSettings()
        value = settings.value("ImportExportDirectories", [])
        return list(set(value))
        #NOTE: may expand at some point to remember more than one export directory used

    def getProjectLocations(self):
        """return list of directories where projects are stored"""
        #multiple entries come back as a list, but a single comes back as a string
        settings = qApp.instance().getSettings()
        dirs = settings.value('projectDirectories', [])
        if not dirs:
            dirs = []
        if isinstance(dirs, str):
            dirs = [dirs]
        return list(set(dirs))

    def deleteProject(self, project):
        self.delete_success = False

        def completeDelete():
            project_dir = QDir(os.path.dirname(project))

            possible_exts = ['.json', '.sqlite', '.enc', '.user']
            project_dir.setFilter(QDir.Files)
            project_files = [project_dir.absoluteFilePath(f) for f in project_dir.entryList() if os.path.splitext(f)[1] in possible_exts or \
                (not os.path.splitext(f)[1] and os.path.splitext(f)[0] in possible_exts)] # 2nd case to cover a rare error: filename would equal ext

            #possible_dirs = ['signs', 'sentences', 'extra_videos', 'extra_pictures', 'explanatory_videos', 'explanatory_pictures']
            possible_dirs = ['_signs', '_sentences', '_extra_videos', '_extra_pictures'] # 0.9.2
            project_dir.setFilter(QDir.Dirs|QDir.NoDotAndDotDot)
            media_dirs = [project_dir.absoluteFilePath(d) for d in project_dir.entryList() if d in possible_dirs]

            temp_dir = '{}/{}'.format(qApp.instance().getTempDir(), os.path.basename(project_dir.path()))
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)

            try:
                for _dir in media_dirs:
                    shutil.move(_dir, temp_dir)
                for _file in project_files:
                    shutil.move(_file, temp_dir)
            except:
                print('move failed')
                #if error, move all back to src dir
                # media files
                qtemp = QDir(temp_dir)
                qtemp.setFilter(QDir.Dirs|QDir.NoDotAndDotDot)
                dirs = [qtemp.absoluteFilePath(d) for d in qtemp.entryList()]
                for _dir in dirs:
                    dst = '{}/{}'.format(project_dir.path(), os.path.basename(_dir))
                    if not os.path.exists(dst): #move entire directory
                        shutil.move(_dir, dst)
                    else: #move files into existing directory
                        qdir = QDir(_dir)
                        qdir.setFilter(QDir.Files)
                        files = [qdir.absoluteFilePath(f) for f in qdir.entryList()]
                        for f in files:
                            dst = '{}/{}/{}'.format(project_dir.path(), os.path.basename(_dir), os.path.basename(f)) #project_dir, media_dir, filename
                            if not os.path.exists(dst):
                                shutil.move(f, dst)
                # project files
                qtemp.setFilter(QDir.Files)
                files = [qtemp.absoluteFilePath(f) for f in qtemp.entryList()]
                for f in files:
                    dst = '{}/{}'.format(project_dir.path(), os.path.basename(f))
                    if not os.path.exists(dst):
                        shutil.move(f, dst)
            else:
                self.delete_success = True
                proj_dir_path = project_dir.path()
                if not self.getProjectList(proj_dir_path): # don't remove directory if it contains any other projects
                    # this would be an error condition; this avoids a (rare) possibility of deleting other projects
                    qdir = QDir(proj_dir_path)
                    qdir.setFilter(QDir.NoDotAndDotDot)
                    # let's go a step further and not delete if ANY files/dirs remain in directory
                    if not qdir.entryList():
                        try:
                            shutil.rmtree(proj_dir_path)
                        except:
                            self.thread().msleep(500)
                            try:
                                shutil.rmtree(proj_dir_path)
                            except:
                                self.addPossibleRemoval(proj_dir_path)
                            else:
                                self.amendProjectList(project, remove=True)
                        else:
                            #files removed, now remove entry from listing
                            self.amendProjectList(project, remove=True)

            if os.path.exists(temp_dir):
                for g in glob.glob("{}/*".format(temp_dir)):
                    if g.endswith('.json'): #main project file; make sure its now read-write or removal will fail
                        os.chmod(g, stat.S_IWUSR|stat.S_IREAD) # change back to read-write
                try:
                    shutil.rmtree(temp_dir)
                except:
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        print('cant remove', temp_dir) #no real problem; temp directory deleted on close of SooSL
        try:
            if self.current_project_filename and os.path.samefile(self.current_project_filename, project):
                self.project_closed.connect(completeDelete)
                self.closeProject()
            else:
                completeDelete()
        except:
            msg = '<b>{}</b><br>{}'.format(qApp.instance().translate('ProjectManager', 'Path cannot be found.'), QDir.cleanPath(self.current_project_filename))
            self.showWarning('Path Error', msg)
        try:
            self.project_closed.disconnect(completeDelete)
        except:
            pass
        return self.delete_success

    def setProjectLocations(self, dir_list):
        settings = qApp.instance().getSettings()
        old_list = settings.value('projectDirectories', [])
        if not old_list:
            old_list = []
        if not dir_list:
            dir_list = []
        # prevent duplicates
        dir_list = list(set(dir_list))
        settings.setValue('projectDirectories', dir_list)
        settings.sync()
        for d in dir_list:
            if d not in old_list:
                self.setKnownProjectInfo(d)

    def removeEmptyImportExportDirectories(self):
        settings = qApp.instance().getSettings()
        default_import_export_dirs = qApp.instance().getDefaultImportExportDirs()
         # remove any empty import/export directories from settings
        empties = []
        _dirs = settings.value('ImportExportDirectories', [])
        # remove duplicates
        _dirs = list(set(_dirs))
        for _dir in reversed(_dirs):
            qdir = QDir(_dir)
            qdir.setFilter(QDir.Files)
            zoozl_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if os.path.splitext(entry)[1].lower() == '.zoozl']
            if not zoozl_files:
                _dirs.remove(_dir)
                empties.append(_dir)
        if _dirs:
            settings.setValue('ImportExportDirectories', _dirs)
        else:
            settings.setValue('ImportExportDirectories', default_import_export_dirs)
        settings.sync()
        return empties

    def removeEmptyProjectDirectories(self):
        settings = qApp.instance().getSettings()
        default_projects_dir = qApp.instance().getDefaultProjectsDir()
        # remove any empty dictionary directories from settings
        empties = []
        _dirs = settings.value('projectDirectories')
        if not _dirs:
            _dirs = []
        if isinstance(_dirs, str):
            _dirs = [_dirs]
        # remove duplicates
        _dirs = list(set(_dirs))
        if _dirs:
            for _dir in reversed(_dirs):
                projects = self.getProjectList(_dir)
                if not projects:
                    _dirs.remove(_dir)
                    empties.append(_dir)
        else:
            _dirs = []
        if default_projects_dir not in _dirs:
            _dirs.append(default_projects_dir)
        if default_projects_dir in empties:
            empties.remove(default_projects_dir)
        settings.setValue('projectDirectories', _dirs)
        settings.sync()
        return empties

    # def removeOrphanedMediaFiles(self):
    #     """remove media files which are no longer used by project; through explicit deletion or some program error"""
    #     pass # NOTE: lets don't call this after every close any longer; not such an issue as earlier versions
    #     # Maybe after crashes? or some other tool called by user to clean up the project???
    #     # Certainly not after simply browsing a project!!!

    #     # media_paths = self.getMediaPaths(self.project.signs)
    #     # for d in ['signs', 'sentences', 'extra_pictures', 'extra_videos']:
    #     #     _dir = QDir(os.path.join(self.project.project_dir, d))
    #     #     files = list(map(lambda x: _dir.absoluteFilePath(x), _dir.entryList(filters=QDir.Files)))
    #     #     for f in files: #files in actual project directory
    #     #         if f not in media_paths: #file paths used by project
    #     #             try:
    #     #                 os.remove(f)
    #     #             except:
    #     #                 self.addPossibleRemoval(f)

    def cleanImport(self, crash_log):
        import_file = '{}/import_crash.json'.format(qApp.instance().getWorkingDir())
        #remove failed import directory
        if os.path.exists(import_file):
            failed_import = None
            with io.open(import_file, 'r', encoding='utf-8') as f:
                failed_import = f.read()
            crash_log.write('\nImport crash: {}'.format(failed_import))
            try:
                _dict = eval(failed_import)[0]
            except:
                print('reading failed')
            else:
                dst = _dict.get('dest')
                if os.path.exists(dst):
                    try:
                        shutil.rmtree(dst)
                    except:
                        self.setWritePermission(dst, True)
                        shutil.rmtree(dst)
            os.remove(import_file)

    def cleanExportDir(self, crash_log):
        export_file = '{}/export_crash.json'.format(qApp.instance().getWorkingDir())
        #remove failed export file
        if os.path.exists(export_file):
            failed_export = None
            with io.open(export_file, 'r', encoding='utf-8') as f:
                failed_export = f.read()
            crash_log.write('\nExport crash: {}'.format(failed_export))

            failed_exports = []
            with io.open(export_file, 'r', encoding='utf-8') as f:
                j = json.load(f)
                failed_exports = j.get("exports", [])
            try:
                for export in failed_exports:
                    dst = export.get('dest')
                    read_write = export.get('existing_read_write')
                    if os.path.exists(dst):
                        self.setWritePermission(dst, True)
                        os.remove(dst)
                    # deal with any backup
                    backup = '{}-backup'.format(dst)
                    if os.path.exists(backup):
                        os.rename(backup, dst)
                        self.setWritePermission(dst, read_write)

            except:
                pass
            else:
                self.removeExportInfo()

    def cleanTempDir(self):
        soosl_files = glob.glob('{}/SooSL_*'.format(tempfile.gettempdir()))
        for f in soosl_files:
            try:
                os.remove(f)
            except:
                self.addPossibleRemoval(f)

    def recoverAfterCrash(self):
        # just deal with old/redundant project files here; media files are dealt with in self.removeOrphanedMediaFiles
        # self.possible_removals is already set at this point (onOpenProject), so just amend
        # through self.addPossibleRemoval; files are removed at close (onCloseProject) or on next open (onOpenProject)

        # get a list of the top level project files
        _dir = QDir(self.project.project_dir)
        _dir.setFilter(QDir.Files)
        project_files = list(map(lambda x: _dir.absoluteFilePath(x), _dir.entryList()))
        # backups were only created in the sqlite - json conversion, and deleting them should have been done in the update process
        # see this.openOpject; added here for completeness
        backups = [f for f in project_files if f.endswith('-backup')]
        for b in backups:
            try:
                os.remove(b)
            except:
                self.addPossibleRemoval(b)

    # # as of 0.9.0 updating of projects is done in project.py
    # def updateProject(self):
    #     """update project json and directories between versions, if required
    #     """
    #     # nothing for 0.9.0; this was the first version to use json for project storage
    #     return False

    def checkFilepathLength(self, src, update=False):
        dst = src
        pth = Path(src)
        if len(pth.stem) > 100:
            try:
                name, id = pth.stem.split('_id')
            except:
                new_stem = pth.stem[:82]
            else:
                new_stem = f'{name[:82]}_id{id}'
            dst = f'{pth.parent}/{new_stem}{pth.suffix}'
            # print(src)
            # print(dst)
            # print()
            if update:
                try:
                    shutil.move(src, dst)
                except:
                    return src
        return dst

    def sanitizePath(self, pth):
        if not pth:
            return ''
        # used to clean undesirable characters from filenames (basename)
        head, _name = os.path.split(pth)
        name, ext = os.path.splitext(_name)
        _id = name.split('_id')[-1]
        _id_str = ''
        if _id:
            _id_str = '_id{}'.format(_id)
            name = name.replace(_id_str, '')

        # now that we are down to the part of the path we want to "sanitize"
        for _char in ['_', '-', '.', ',']:
            name = name.replace(_char, ' ') #replace character with space
        name = name.strip() #strip off leading and trailing whitespace
        name = '-'.join(name.split()) #replace internal spaces with single hyphen#
        # NOTE: remove non-printing characters???
        # # remove non-printing characters
        # printable = list(s for s in name if s.isprintable())
        # name = ''.join(printable)
        name = re.sub(r"[\\/\'\"\`<>|{}[\]*?~^+=;:#$%&@]", '', name) # remove characters; same as used in 'validators.py'

        # put the full path back together again and return it
        return QDir.cleanPath('{}/{}{}{}'.format(head, name, _id_str, ext))

    def isVideo(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.video_extensions or \
            (ext == '.gif' and QMovie(filename).frameCount() > 1):
            return True
        return False

    def isPicture(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.picture_extensions and ext != '.gif' or \
            (ext == '.gif' and QMovie(filename).frameCount() == 1):
                return True
        return False

    def splitFilenameId(self, filename):
        root = os.path.splitext(filename)[0]
        _id = None
        if root.find('_id') != -1:
            _id = root.split('_id')[-1] #should only be one '_id', but to be sure, I want the final one
        return (filename, _id)

    def joinFilenameId(self, filename, _id):
        root, ext = os.path.splitext(filename)
        #remove any previously set _id
        if root.find('_id') != -1:
            root = "_id".join(root.split('_id')[:-1]) #I only want to remove final '_id' in the unexpected case there are more than one
        new_filename = "".join([root, '_id{}'.format(_id), ext])
        return new_filename

    # @property
    # def video_filter(self):
    #     return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectManager', "Videos"), " *".join(self.video_extensions), qApp.instance().translate('ProjectManager', 'All files'))

    # @property
    # def picture_filter(self):
    #     return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectManager', 'Pictures'), " *".join(self.picture_extensions), qApp.instance().translate('ProjectManager', 'All files'))

    # @property
    # def media_filter(self):
    #     return "{} (*{});;{} (*.*)".format(qApp.instance().translate('ProjectManager', "Videos or Pictures"), " *".join(self.media_extensions),
    #                                                  qApp.instance().translate('ProjectManager', 'All files'))

    ##TODO: probably only keep the most used extension (and obviously the ones supported by
    ## SooSL (VLC; obscure ones needed by users could be amended to list? in configuration?
    #source: http://www.fileinfo.com/filetypes/
    @property
    def media_extensions(self):
        return self.video_extensions + self.picture_extensions

    @property
    def video_extensions(self):
        return ['.mp4', '.264', '.3g2', '.3gp', '.3gp2', '.3gpp', '.3gpp2', '.3mm',
                '.3p2', '.60d', '.787', '.aaf', '.aep', '.aepx', '.aet',
                '.aetx', '.ajp', '.amv', '.amx', '.arf', '.asf', '.asx', '.avb',
                '.avd', '.avi', '.avs', '.avs', '.axm', '.bdm', '.bdmv', '.bik',
                '.bin', '.bix', '.bmk', '.box', '.bs4', '.bsf', '.byu', '.camproj',
                '.camrec', '.clpi', '.cmmp', '.cmmtpl', '.cmproj', '.cmrec',
                '.cpi', '.cvc', '.d2v', '.d3v', '.dat', '.dav', '.dce', '.dck',
                '.ddat', '.dif', '.dir', '.divx', '.dlx', '.dmb', '.dmsm',
                '.dmsm3d', '.dmss', '.dnc', '.dpg', '.dream', '.dsy', '.dv',
                '.dv-avi', '.dv4', '.dvdmedia', '.dvr-ms', '.dvx', '.dxr', '.dzm',
                '.dzp', '.dzt', '.evo', '.eye', '.f4p', '.f4v', '.fbr', '.fbr',
                '.fbz', '.fcp', '.flc', '.flh', '.fli', '.flv', '.flx', '.gl',
                '.grasp', '.gts', '.gvi', '.gvp', '.h264', '.hdmov', '.hkm', '.ifo',
                '.imovieproj', '.imovieproject', '.iva', '.ivf', '.ivr', '.ivs',
                '.izz', '.izzy', '.jts', '.lsf', '.lsx', '.m15', '.m1pg', '.m1v',
                '.m21', '.m21', '.m2a', '.m2p', '.m2t', '.m2ts', '.m2v', '.m4e',
                '.m4u', '.m4v', '.m75', '.meta', '.mgv', '.mj2', '.mjp', '.mjpg',
                '.mkv', '.mmv', '.mnv', '.mod', '.modd', '.moff', '.moi', '.moov',
                '.mov', '.movie', '.mp21', '.mp21', '.mp2v', '.mp4v',
                '.mpe', '.mpeg', '.mpeg4', '.mpf', '.mpg', '.mpg2', '.mpgindex',
                '.mpl', '.mpls', '.mpsub', '.mpv', '.mpv2', '.mqv', '.msdvd',
                '.msh', '.mswmm', '.mts', '.mtv', '.mvb', '.mvc', '.mvd', '.mve',
                '.mvp', '.mxf', '.mys', '.ncor', '.nsv', '.nuv', '.nvc', '.ogm',
                '.ogv', '.ogx', '.osp', '.par', '.pds', '.pgi', '.piv', '.playlist',
                '.pmf', '.prel', '.pro', '.prproj', '.psh', '.pssd', '.pva', '.pvr',
                '.pxv', '.qt', '.qtch', '.qtl', '.qtm', '.qtz', '.r3d', '.rcproject',
                '.rdb', '.rec', '.rm', '.rmd', '.rmp', '.rms', '.rmvb', '.roq',
                '.rp', '.rts', '.rts', '.rum', '.rv', '.sbk', '.sbt', '.scm',
                '.scm', '.scn', '.sec', '.seq', '.sfvidcap', '.smi', '.smil',
                '.smk', '.sml', '.smv', '.spl', '.srt', '.ssm', '.str', '.stx',
                '.svi', '.swf', '.swi', '.swt', '.tda3mt', '.tivo', '.tix', '.tod',
                '.tp', '.tp0', '.tpd', '.tpr', '.trp', '.ts', '.tvs', '.vc1',
                '.vcpf', '.vcr', '.vcv', '.vdo', '.vdr', '.veg', '.vem', '.vf',
                '.vfw', '.vfz', '.vgz', '.vid', '.viewlet', '.viv', '.vivo', '.vlab',
                '.vob', '.vp3', '.vp6', '.vp7', '.vpj', '.vro', '.vs4', '.vse', '.vsp',
                '.w32', '.wcp', '.webm', '.wlmp', '.wm', '.wmd', '.wmmp', '.wmv',
                '.wmx', '.wp3', '.wpl', '.wtv', '.wvx', '.xfl', '.xvid', '.yuv',
                '.zm1', '.zm2', '.zm3', '.zmv']

    @property
    def picture_extensions(self):
        return ['.png', '.jpeg', '.gif', '.001', '.2bp', '.411', '.8pbs', '.8xi', '.abm', '.acr', '.adc',
                '.afx', '.agif', '.agp', '.aic', '.ais', '.albm', '.apd', '.apm',
                '.apng', '.arr', '.art', '.artwork', '.arw', '.arw', '.asw',
                '.avatar', '.awd', '.awd', '.blkrt', '.blz', '.bm2', '.bmc',
                '.bmf', '.bmp', '.brk', '.brt', '.c4', '.cal', '.cals', '.cam',
                '.can', '.cd5', '.cdc', '.cdg', '.ce', '.cimg', '.cin', '.cit',
                '.cpc', '.cpd', '.cpg', '.cps', '.cpt', '.cpx', '.cr2', '.crw',
                '.csf', '.ct', '.cut', '.dcm', '.dcr', '.dcx', '.ddb', '.dds',
                '.dib', '.djv', '.djvu', '.dng', '.dpx', '.dt2', '.dtw', '.dvl',
                '.ecw', '.erf', '.exr', '.fac', '.face', '.fal', '.fax', '.fbm',
                '.fil', '.fits', '.fpg', '.fpx', '.frm', '.gbr', '.gfb',
                '.gih', '.gim', '.gmbck', '.gp4', '.gpd', '.gro', '.grob', '.gry',
                'heic', '.hdp', '.hdr', '.hf', '.hpi', '.hr', '.hrf', '.ic1', '.ic2', '.ic3',
                '.ica', '.icb', '.icn', '.icon', '.ilbm', '.img', '.imj', '.info',
                '.ink', '.int', '.ipx', '.itc2', '.ithmb', '.ivr', '.j', '.j2c',
                '.j2k', '.jas', '.jb2', '.jbf', '.jbig', '.jbmp', '.jbr', '.jfi',
                '.jfif', '.jia', '.jif', '.jiff', '.jng', '.jp2', '.jpc', '.jpd',
                '.jpe', '.jpf', '.jpg', '.jps', '.jpx', '.jtf', '.jwl',
                '.jxr', '.kdc', '.kdk', '.kfx', '.kic', '.kodak', '.kpg', '.lbm',
                '.mac', '.mat', '.max', '.mbm', '.mcs', '.mef', '.met', '.mic',
                '.mip', '.mix', '.mng', '.mnr', '.mos', '.mpf', '.mrb', '.mrw',
                '.msk', '.msp', '.ncd', '.ncr', '.nct', '.nef', '.neo', '.nrw',
                '.odi', '.omf', '.orf', '.ota', '.otb', '.oti', '.pac', '.pal',
                '.pap', '.pat', '.pbm', '.pc1', '.pc2', '.pc3', '.pcd', '.pcx',
                '.pdd', '.pdn', '.pe4', '.pe4', '.pef', '.pfr', '.pgm', '.pi1',
                '.pi2', '.pi2', '.pi3', '.pi4', '.pi5', '.pi6', '.pic', '.pic',
                '.pic', '.picnc', '.pict', '.pictclipping', '.pix', '.pix', '.pm',
                '.pm3', '.pmg', '.pni', '.pnm', '.pnt', '.pntg', '.pov',
                '.pov', '.pp4', '.pp5', '.ppf', '.ppm', '.prw', '.psb', '.psd',
                '.psf', '.psp', '.pspbrush', '.pspimage', '.ptg', '.ptx', '.ptx',
                '.pvr', '.pwp', '.px', '.pxm', '.pxr', '.pzp', '.qif', '.qti',
                '.qtif', '.raf', '.ras', '.raw', '.rgb', '.rgb', '.ric', '.rif',
                '.riff', '.rix', '.rle', '.rsb', '.rsr', '.rw2', '.s2mv', '.sar',
                '.scg', '.sci', '.scp', '.sct', '.scu', '.sdr', '.sff', '.sfw',
                '.sgi', '.shg', '.sid', '.sig', '.sim', '.skitch', '.sld', '.smp',
                '.spc', '.spe', '.spiff', '.spp', '.spr', '.spu', '.sr', '.sr2',
                '.srf', '.ste', '.sumo', '.sun', '.suniff', '.sup', '.sva', '.svg', '.t2b',
                '.taac', '.tb0', '.tex', '.tg4', '.tga', '.thm', '.thm', '.thumb',
                '.tif', '.tif', '.tiff', '.tjp', '.tn1', '.tn2', '.tn3', '.tny',
                '.tpi', '.trif', '.u', '.ufo', '.urt', '.v', '.vda', '.vff', '.vic',
                '.viff', '.vna', '.vss', '.vst', '.wb1', '.wbc', '.wbd', '.wbm',
                '.wbmp', '.wbz', '.wdp', '.web', '.wi', '.wic', '.wmp', '.wvl',
                '.x3f', '.xbm', '.xcf', '.xpm', '.xwd', '.y', '.yuv', '.zif']

    def get_location_codes(self, sign):
        try:
            return self.get_location_codes_from_list(sign.component_codes)
        except:
            return []

    def get_used_location_codes(self):
        codes = []
        if self.project:
            codes = list(set(self.__flat([self.get_location_codes(sign) for sign in self.project.signs])))
        return codes

    def get_location_codes_from_list(self, codes):
        location_codes = [c for c in codes if (eval("0x{}".format(c)) >= eval("0x500") and \
                          eval("0x{}".format(c)) < eval("0x1000"))]
        return location_codes

    def get_non_location_codes(self, sign):
        """returns non-location codes"""
        return self.get_non_location_codes_from_list(sign.component_codes)

    def get_non_location_codes_from_list(self, codes):
        non_location_codes = [c for c in codes if (eval("0x{}".format(c)) < eval("0x500") or \
                            eval("0x{}".format(c)) >= eval("0x1000"))]
        return non_location_codes

    def importSignsFromProject(self, project_jsn_path):
        qApp.setOverrideCursor(Qt.BusyCursor)
        # currently part of a test suite of tools for testing purposes
        # import signs from another project; may lay some foundations for future merging code...
        import_project = Project(project_jsn_path)
        old_id = 0
        current_proj_dir = qApp.instance().pm.project.project_dir
        import_proj_dir = import_project.project_dir
        # in case of empty project, create the required directories
        sign_dir = os.path.join(current_proj_dir, '_signs')
        sent_dir = os.path.join(current_proj_dir, '_sentences')
        video_dir = os.path.join(current_proj_dir, '_extra_videos')
        picture_dir = os.path.join(current_proj_dir, '_extra_pictures')
        for _dir in [sign_dir, sent_dir, video_dir, picture_dir]:
            if not os.path.exists(_dir):
                os.mkdir(_dir)

        # read, update and import signs
        # assume all new signs; no amends to old sign at the moment
        for sign in import_project.signs:
            sign_jsn = None
            # read orinal sign data into a json object
            with io.open(sign.json_file, 'r', encoding='utf-8') as f:
                sign_jsn = json.load(f)
            # sign info
            new_sign_id = self.getNewSignId()
            while new_sign_id == old_id:
                new_sign_id = self.getNewSignId()
            old_id = new_sign_id
            new_sign_path = self.joinFilenameId(sign_jsn.get('path'), new_sign_id)
            full_new_sign_path = '{}{}'.format(current_proj_dir, new_sign_path)
            sign_jsn['id'] = new_sign_id
            sign_jsn['path'] = new_sign_path
            if os.path.exists(sign.path):
                shutil.copy(sign.path, full_new_sign_path)
            # sense info
            for sense in sign_jsn.get("senses", []):
                new_sense_id = self.getNewSenseId()
                while new_sense_id == old_id:
                    new_sense_id = self.getNewSenseId()
                old_id = new_sense_id
                sense['id'] = new_sense_id
                # sentence info
                for sentence in sense.get("sentences", []):
                    new_sentence_id = self.getNewSentenceId()
                    while new_sentence_id == old_id:
                        new_sentence_id = self.getNewSentenceId()
                    old_id = new_sentence_id
                    old_sentence_path = sentence.get('path')
                    new_sentence_path = self.joinFilenameId(old_sentence_path, new_sentence_id)
                    sentence['id'] = new_sentence_id
                    sentence['path'] = new_sentence_path
                    src = '{}{}'.format(import_proj_dir, old_sentence_path)
                    dst = '{}{}'.format(current_proj_dir, new_sentence_path)
                    if os.path.exists(src):
                        shutil.copy(src, dst)
            # extra media info
            for media in sign_jsn.get("extraMediaFiles", []):
                new_media_id = self.getNewExtraMediaId()
                while new_media_id == old_id:
                    new_media_id = self.getNewExtraMediaId()
                old_id = new_media_id
                old_media_path = media.get('path')
                new_media_path = self.joinFilenameId(old_media_path, new_media_id)
                media['id'] = new_media_id
                media['path'] = new_media_path
                src = '{}{}'.format(import_proj_dir, old_media_path)
                dst = '{}{}'.format(current_proj_dir, new_media_path)
                if os.path.exists(src):
                    shutil.copy(src, dst)

            # write out updated json object to new file in current project
            dst = '{}/_signs/{}.json'.format(current_proj_dir, new_sign_id)
            with io.open(dst, 'w', encoding='utf-8') as f:
                json.dump(sign_jsn, f, sort_keys=False, indent=4, ensure_ascii=False)

        self.reloadCurrentProject()
        qApp.restoreOverrideCursor()

class MyPathWatcher(QObject):
    projectChanged = pyqtSignal()
    fileChanged = pyqtSignal(str)
    directoryChanged = pyqtSignal(str)

    def __init__(self):
        super(MyPathWatcher, self).__init__()
        self.paths = []
        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(5000)
        self.watch_timer.timeout.connect(self.onTimeout)
        self.pth_dict = {}

    def addPath(self, pth):
        if pth not in self.paths:
            self.paths.append(pth)
            if os.path.isdir(pth):
                qdir = QDir(pth)
                qdir.setFilter(QDir.Files)
                paths = [qdir.absoluteFilePath(entry) for entry in qdir.entryList()]
                self.pth_dict[pth] = paths.sort()
            elif os.path.isfile(pth):
                self.pth_dict[pth] = os.path.getmtime(pth)
            if not self.watch_timer.isActive():
                self.watch_timer.start()

    def removePath(self, pth):
        if pth in self.paths:
            self.paths.remove(pth)
            try:
                self.pth_dict.pop(pth)
            except:
                pass
            if not self.paths and self.watch_timer.isActive():
                self.watch_timer.stop()

    def onTimeout(self):
        for pth in self.paths:
            self.checkNetworkAccess(pth)

    def onNetworkLost(self, pth):
        self.removePath(pth)
        qApp.processEvents()
        qApp.instance().pm.onNetworkLost(pth)

    def onNetworkOkay(self, pth):
        if os.path.isfile(pth):
            old_mtime = self.pth_dict.get(pth, 0)
            new_mtime = os.path.getmtime(pth)
            if new_mtime != old_mtime:
                self.pth_dict[pth] = new_mtime
                if pth == qApp.instance().pm.current_project_filename:
                    self.projectChanged.emit()
                else:
                    self.fileChanged.emit(pth)

    def checkNetworkAccess(self, pth):
        target = QDir(pth).canonicalPath()
        if target:
            self.onNetworkOkay(pth)
        else:
            self.onNetworkLost(pth)


# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()