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

import sys
import os
import copy
import shutil
from zipfile import ZipFile
import io
import stat

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QStandardPaths
#from PyQt5.QtCore import QAbstractProxyModel, QModelIndex, QAbstractItemModel
from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5.QtCore import QByteArray

from PyQt5.QtSql import QSqlDatabase

from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QCursor

from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QProgressDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtWidgets import QFileSystemModel
from PyQt5.QtWidgets import QHBoxLayout

from import_project_dlg import ImportProjectDlg
from database import OLDEST_UPDATABLE
from database import SooSLQuery
from database import SooSLDatabaseManager
from project import Project
#from project_file_dialogs import SooSLFileDialog, ProjectProxyModel

ARCHIVE_EXT = "zoozl"
DB_EXT = "sqlite"
DB_EXT_2 = "json"
ORIG_SUFFIX = '-orig'
IMPORT_SUFFIX = '-import'

class Importer(QObject):

    def __init__(self, parent=None):
        super(Importer, self).__init__(parent)
        self.mw = qApp.instance().getMainWindow()

    def replaceDiffPerm(self, src_perm, dst_perm):
        """ warn user if replacing a dictionary with a different read/write permission"""
        if src_perm == dst_perm:
            return True # method not really needed here as the permissions are the same
        message = qApp.instance().translate('Importer', 'You are replacing a dictionary that cannot be edited<br> with a dictionary that can be edited.') #assume read-write import
        if not src_perm: #read-only import
            message = qApp.instance().translate('Importer', 'You are replacing a dictionary that can be edited<br> with a dictionary that cannot be edited.')
        message = "<p style:'color:blue'>{}</p>".format(message)

        mw = qApp.instance().getMainWindow()
        msgBox = QMessageBox(mw)
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setWindowTitle('{} - {}'.format(qApp.instance().translate('Importer', 'Import Dictionary'), qApp.instance().translate('Importer', 'Different permissions')))
        msgBox.setText(message)
        msgBox.setInformativeText(qApp.instance().translate('Importer', "Is this what you want to do?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_btn, no_btn = msgBox.buttons()
        yes_btn.setIcon(QIcon(":/thumb_up.png"))
        no_btn.setIcon(QIcon(":/thumb_down.png"))
        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('Importer', "Yes"))
        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('Importer', "No"))
        msgBox.setDefaultButton(QMessageBox.No)
        if msgBox.exec_() == QMessageBox.Yes:
            return True
        return False

    def importProject(self, zoozl_file=None):
        """For importing zip archived database of the following structure:

        project_name [dir] --|
                                |---- signs [dir] ##was 'citations'
                                |---- extra_pictures [dir]
                                |---- extra_videos [dir]
                                |---- sentences [dir]
                                |---- project_name [database file]
                                |---- project_logo [image file]
        """
        #step 1: choose dictionary to import
        if not zoozl_file:
            zoozl_file = self.getFilename() #SooSL zip archive; .zoozl

        if zoozl_file:
            qApp.instance().pm.setKnownProjectInfo(zoozl_file)
            dlg = ImportProjectDlg(zoozl_file, self.mw)
            project_dir = None
            if dlg.exec_():
                #project_id = qApp.instance().pm.getProjectNameIdVersionDatetime(zoozl_file)[1]
                new_name = dlg.project_name
                archive_dir = dlg.location #destination parent directory
                project_path = dlg.project_path
                full_project_path = '{}/{}'.format(archive_dir, project_path) #full path to
                project_dir = os.path.dirname(full_project_path)
                if os.path.exists(full_project_path):
                    src_perm = qApp.instance().pm.isReadWrite(zoozl_file)
                    dst_perm = qApp.instance().pm.isReadWrite(full_project_path)
                    if src_perm == dst_perm or self.replaceDiffPerm(src_perm, dst_perm):
                        project_dir = '{}{}'.format(os.path.dirname(full_project_path), IMPORT_SUFFIX)
                    else:
                        del dlg
                        return
                    qApp.instance().pm.closeProject()
            else:
                if dlg.back:
                    self.importProject()
                return
            del dlg

            self.project_dir = project_dir
            if self.project_dir and self.project_dir.endswith(IMPORT_SUFFIX):
                old_dir = self.project_dir.replace(IMPORT_SUFFIX, '')
                orig_dir = self.project_dir.replace(IMPORT_SUFFIX, ORIG_SUFFIX)
                qApp.instance().pm.setWritePermission(old_dir, True) #incase overwriting a read-only dictionary
                try:
                    shutil.move(old_dir, orig_dir)
                except:
                    shutil.rmtree(orig_dir)
                    self.showCannotOverwriteMessage(old_dir)
                else:
                    self.doImport(zoozl_file, self.project_dir)
            elif self.project_dir:
                self.doImport(zoozl_file, self.project_dir)
            qApp.instance().pm.removeImportInfo() # if this completed, then no crash
        qApp.restoreOverrideCursor()

    def doImport(self, zoozl_file, import_dir, open_project=True):
        zoozl_file = zoozl_file.replace('\\', '/')
        z = ZipFile(zoozl_file)
        names = z.namelist()
        #display progress dialog
        progress = QProgressDialog(parent=self.mw, flags=Qt.WindowTitleHint)
        progress.setWindowTitle('Import Dictionary')
        progress.setCancelButton(QPushButton(QIcon(":/close.png"), "Cancel"))
        qApp.instance().error_signal.connect(progress.cancel)
        progress.setMinimum(0)
        _max = len(names)
        progress.setMaximum(_max)
        value = 0
        #progress.forceShow()
        progress.setLabelText("<b>{}</b><br><p style='color:blue; text-align:left;'>{}</p>".format(zoozl_file, qApp.instance().translate('Importer', 'Importing dictionary...')))
        # progress settings
        count = _max
        interval = 10
        next_update = 10
        # to be used in case of crash recovery
        qApp.instance().pm.recordImportInfo(zoozl_file, import_dir)
        names = list(set(names)) # removes duplicates
        def name_order(_name):
            if _name.count('/') == 1: # brings project and inventory files to the front
                return 0
            elif _name.count('signs') or _name.count('citations'):
                return 1
            elif _name.count('sentences'):
                return 2
            else:
                return 3
        names.sort(key=lambda x:(name_order(x), x))
        for name in names:
            # show progress
            qApp.processEvents()
            if progress.wasCanceled():
                break
            if value == next_update or value == count:
                progress.setValue(value)
                next_update += interval
            value += 1
            # extraction
            _name = name.split('/', 1)[1] # remove first folder name - this will come from import_dir
            if not _name.count('/') and not _name.startswith('project_logo'): # project and inventory file
                ext = os.path.splitext(_name)[1]
                if ext == '.json': # project file
                    base = os.path.basename(import_dir).replace(IMPORT_SUFFIX, '')
                    _name = f'{base}{ext}'
            dst = f'{import_dir}/{_name}'
            _dir = os.path.dirname(dst)
            if not os.path.exists(_dir):
                os.makedirs(_dir)
            if os.path.basename(dst): # file
                source = z.open(name)
                try:
                    target = open(dst, "wb")
                except:
                    pass
                    # target.close()
                    # source.close()
                else:
                    shutil.copyfileobj(source, target)
                    target.close()
                    source.close()
            elif not os.path.exists(dst): # directory
                os.makedirs(dst)
        if open_project:
            project_to_open = self.getProjectToOpen(import_dir, z.filename)
            if not self.progressCanceled(progress, import_dir):
                # extraction complete; close progress dlg and any currently open project
                progress.setLabelText(qApp.instance().translate('Importer', 'Closing current dictionary...'))
                progress.setCancelButton(None)
                qApp.processEvents()
                progress.close()
                self.onImportSuccess(project_to_open, z.filename)
            else:
                self.onImportFailure(import_dir)
        elif not self.progressCanceled(progress, import_dir):
            progress.close()
            project_to_open = self.getProjectToOpen(import_dir, z.filename)
            return project_to_open
        else:
            return None

    def getProjectToOpen(self, project_dir, z_filename):
        if project_dir.endswith(IMPORT_SUFFIX): # in the case of overwriting existing project
            _dir = project_dir.replace(IMPORT_SUFFIX, '')
            os.rename(project_dir, _dir)
            project_dir = _dir
            _dir = f'{_dir}{ORIG_SUFFIX}'
            if os.path.exists(_dir):
                qApp.instance().pm.setWritePermission(_dir, True) #incase overwriting a read-only dictionary
                shutil.rmtree(_dir)
        name = os.path.basename(project_dir)
        project_to_open = f'{project_dir}/{name}.json'
        return project_to_open

    def onImportSuccess(self, project_to_open, z_filename):
        qApp.instance().pm.setWritePermission(project_to_open, qApp.instance().pm.isReadWrite(z_filename))
        qApp.instance().pm.updateKnownProjectInfoPermission(project_to_open, qApp.instance().pm.isReadWrite(z_filename))
        project = qApp.instance().pm.openProject(project_to_open)
        self.mw.project_open.emit(True)
        QMessageBox.information(self.mw, qApp.instance().translate('Importer', "Import complete"), "<center><p style='color:blue'>{}</p></center>".format(qApp.instance().translate('Importer', "Import complete")))

    def onImportFailure(self, project_dir):
        qApp.instance().pm.setWritePermission(project_dir, True) #NOTE: overwriting a read-only dictionary
        shutil.rmtree(project_dir)
        if project_dir.endswith(IMPORT_SUFFIX):
            orig_dir = project_dir.replace(IMPORT_SUFFIX, ORIG_SUFFIX)
            if os.path.exists(orig_dir):
                _dir = orig_dir.replace(ORIG_SUFFIX, '')
                os.rename(orig_dir, _dir)
        QMessageBox.information(self.mw, qApp.instance().translate('Importer', "Import failed"), "<center><p style='color:blue'>{}</p></center>".format(qApp.instance().translate('Importer', "Import failed")))
        # open old project?

    def showCannotOverwriteMessage(self, project_filename):
        msg1 = qApp.instance().translate('Importer', 'Cannot overwrite dictionary')
        msg2 = ''
        users = qApp.instance().pm.getOtherProjectUsers(project_filename)
        if users:
            msg2 = qApp.instance().translate('Importer', 'This dictionary is open by other users:') + '<ol>'
            for u in users:
                msg2 += '<li>{}</li>'.format(u)
            msg2 += '</ol>'
        else:
            msg2 = qApp.instance().translate('Importer', 'Media files from this dictionary may be open by other programs.')
        qApp.instance().pm.showWarning(' ', '<b>{}</b><br><br>{}'.format(msg1, msg2))

    def progressCanceled(self, progress, project_dir):
        if progress.wasCanceled():
            progress.close()
            QMessageBox.information(self.mw, qApp.instance().translate('Importer', "Import cancelled"), "<center><p style='color:red'>{}</p></center>".format(qApp.instance().translate('Importer', "Import cancelled")))
            return True
        return False

    def isValidArchive(self, filename):
        z = None
        try:
            z = ZipFile(filename)
        except:
            return False
        db = None
        for name in z.namelist():
            if name.endswith(".{}".format(DB_EXT)) or name.endswith(".{}".format(DB_EXT_2)) or name.endswith(".enc"):
                db = name.split("/")[1]
        if not db:
            return False
        return True

    def getFilename(self):
        valid_archive = False
        while not valid_archive:
            dlg = self.mw.soosl_file_dlg
            dlg.setupForImporting()
            # dlg.show()
            # dlg.raise_()
            qApp.processEvents()
            self.mw.ensureUsingActiveMonitor(dlg)
            filename = None
            if dlg.exec_():
                filename = dlg.selected_path #selectedFiles()[0]
            if not filename:
                break
            if self.isValidArchive(filename):
                valid_archive = True
            else:
                warning = QMessageBox.warning(self.mw,
                    qApp.instance().translate('Importer', "Invalid archive"),
                    "<STRONG>{}</STRONG> - {}".format(filename, qApp.instance().translate('Importer', 'Not a SooSL archive')))

        return filename

    def getIdFromPath(self, pth):
        """path and database filenames should match. If they have been changed (by user?) in the filesystem, they probably still
        contain a unique id in the name which can be used to link with the database entries and keep them in sync. This should
        prevent any update code deleting file thinking its orphaned"""
        _id = None
        root, file_name = os.path.split(pth)
        if file_name.count('_id'):
            _id = file_name.split('_id')[-1].split('.')[0]
        return _id

    def isSameType(self, pth1, pth2):
        type1 = os.path.basename(os.path.split(pth1)[0])
        type2 = os.path.basename(os.path.split(pth2)[0])
        if type1 == type2:
            return True
        return False

    def getJSONMembers(self, filename):
        project = Project(filename, update_jsn=False) #don't want to update jsn here as it will be updated on opening; NOTE: or do I???
        sign_members = [os.path.join('signs', os.path.split(s.path)[1]) for s in project.signs]

        sentence_members = []
        sign_ids = [s.id for s in project.signs]
        for sign_id in sign_ids:
            sense_ids = [s.id for s in project.getSenses(sign_id)]
            for sense_id in sense_ids:
                sentence_members.extend([os.path.join('sentences', os.path.split(s.path)[1]) for s in project.getSentences(sign_id, sense_id)])
        sentence_members = list(set(sentence_members)) # remove any duplicates

        extra_video_members = []
        extra_picture_members = []
        for sign in project.signs:
            extra_video_members.extend([os.path.join('extra_videos', os.path.split(em.path)[1]) for em in sign.extra_media_files if os.path.split(em.path)[0].endswith('extra_videos')])
            extra_picture_members.extend([os.path.join('extra_pictures', os.path.split(em.path)[1]) for em in sign.extra_media_files if os.path.split(em.path)[0].endswith('extra_pictures')])
        extra_video_members = list(set(extra_video_members))
        extra_picture_members = list(set(extra_picture_members))

        members = sign_members + sentence_members + extra_video_members + extra_picture_members
        return members

    def getDBMembers(self, filename):
        """return list of media filepaths contained in a database (db)"""
        enc = False
        db_filename = filename
        if db_filename:
            if os.path.splitext(db_filename)[1] == ".enc":
                enc = True
                db_filename = qApp.instance().pm.unsecure(filename, inplace=True)

        members = []
        dbm = SooSLDatabaseManager(parent=self)
        if dbm.openDb(db_filename):
            query = SooSLQuery(dbm.db)

            #check version
            version = '0.0.0'
            query.exec_("""SELECT version FROM meta""")
            while query.next():
                version = query.value(0)
            if not dbm.projectOlderThan(OLDEST_UPDATABLE):
                for media_type, _query in [
                   ('signs', """SELECT path FROM citation"""),
                   ('sentences', """SELECT path FROM sentenceVideo"""),
                   ('extra_videos', """SELECT path FROM exVideo"""),
                   ('extra_pictures', """SELECT path FROM exPicture""")
                   ]:
                    query.exec_(_query)
                    while query.next():
                        name = query.value(0)
                        members.append(os.path.join(media_type, name))
            dbm.close()
        if enc:
            qApp.instance().pm.secure(db_filename, inplace=True)
        return members

    def getSourceTargetPairs(self, members, db_members):
        """match up members based on embedded id and return as a list of tuple pairs"""
        pairs = []
        for db in db_members:
            _id = self.getIdFromPath(db)
            n = None
            if _id:
                try:
                    n = [m for m in members if m.count('_id{}.'.format(_id)) and self.isSameType(db, m)][0]
                except:
                    pass
                pairs.append((n, db))
            else:
                try:
                    n = [m for m in members if os.path.basename(m) == os.path.basename(db) and self.isSameType(db, m)][0]
                except:
                    pass
                pairs.append((n, db))
        return pairs

if __name__ == '__main__':
    from mainwindow import main
    main()
