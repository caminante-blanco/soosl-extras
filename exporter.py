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

import sys, os, stat
import shutil
import glob
import json
from zipfile import ZipFile, ZIP_DEFLATED

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QDir

from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QProgressDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QPushButton

ARCHIVE_EXT = "zoozl"

class Exporter(QObject):   
     
    def __init__(self, parent=None):
        super(Exporter, self).__init__(parent)
        self.pm = qApp.instance().pm

    def replaceZoozl(self, filename):
        mw = qApp.instance().getMainWindow()
        msgBox = QMessageBox(mw)
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setTextFormat(Qt.RichText)
        title = '{} - {}'.format(qApp.instance().translate('Exporter', 'Export Dictionary'), qApp.instance().translate('Exporter', 'Replace existing file'))
        msgBox.setWindowTitle(title)
        msgBox.setText('<strong>{}</strong>'.format(filename))
        msgBox.setInformativeText('{}<br>{}'.format(qApp.instance().translate('Exporter', 'This file already exists.'), qApp.instance().translate('Exporter', 'Do you want to replace it?')))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_btn, no_btn = msgBox.buttons()
        yes_btn.setIcon(QIcon(":/thumb_up.png"))
        no_btn.setIcon(QIcon(":/thumb_down.png"))
        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('Exporter', "Yes"))
        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('Exporter', "No"))
        msgBox.setDefaultButton(QMessageBox.No)
        if msgBox.exec_() == QMessageBox.Yes:
            return True
        return False
        
    def replaceDiffPerm(self, src_perm, dst_perm):
        """ warn user if replacing a dictionary with a different read/write permission"""
        if src_perm == dst_perm:
            return True # method not really needed here as the permissions are the same
        message = qApp.instance().translate('Exporter', 'You are replacing a dictionary that cannot be edited<br> with a dictionary that can be edited.') #assume read-write export
        if not src_perm: #read-only export
            message = qApp.instance().translate('Exporter', 'You are replacing a dictionary that can be edited<br> with a dictionary that cannot be edited.')
        
        mw = qApp.instance().getMainWindow()
        msgBox = QMessageBox(mw)
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setTextFormat(Qt.RichText)
        msgBox.setWindowTitle('{} - {}'.format(qApp.instance().translate('Exporter', 'Export Dictionary'), qApp.instance().translate('Exporter', 'Different permissions')))
        msgBox.setText(message)
        msgBox.setInformativeText(qApp.instance().translate('Exporter', "Is this what you want to do?"))
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_btn, no_btn = msgBox.buttons()
        yes_btn.setIcon(QIcon(":/thumb_up.png"))
        no_btn.setIcon(QIcon(":/thumb_down.png"))
        msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('Exporter', "Yes"))
        msgBox.button(QMessageBox.No).setText(qApp.instance().translate('Exporter', "No"))
        msgBox.setDefaultButton(QMessageBox.No)
        if msgBox.exec_() == QMessageBox.Yes:
            return True
        return False

    def exportProject(self):
        """For exporting a dictionary archive (zoozl - zipfile) to a local folder, USB stick or a network folder.
        """  
        mw = qApp.instance().getMainWindow()
        project_file = self.pm.current_project_filename
        if not project_file:
            short = qApp.instance().translate('Exporter', 'No open dictionary')
            long = qApp.instance().translate('Exporter', 'First, open the dictionary you want to export')
            mw.onShowWarning(short, long)
        else:
            project_dir = os.path.dirname(project_file) 
            project_name, project_id, _version, _datetime  = qApp.instance().pm.getProjectNameIdVersionDatetime(project_file)       
            #show dialog for choosing export location directory
            _base = os.path.basename(project_dir)
            suggested_filename = '{}.{}'.format(_base, ARCHIVE_EXT)
            dlg = mw.export_dlg
            dlg.setSuggestedFilename(suggested_filename)
            qApp.processEvents()
            mw.ensureUsingActiveMonitor(dlg)
            #get filename for exported dictionary from dialog
            filename = None
            if dlg.exec_():
                filename = QDir.cleanPath(dlg.selected_path)
                dst_rw = True #if we are overwriting a existing file, we need to know if that file is read-write or not in case of export crash
                if filename:
                    current_dir = os.path.dirname(filename)
                    qApp.instance().pm.updateImportExportDirectories(current_dir)
                    ## make sure not overwriting a different dictionary!!!
                    if os.path.exists(filename):
                        if not qApp.instance().pm.isReadWrite(filename):
                            dst_rw = False
                        #if we are overwriting a existing file, we need to know if that file is read-write or not in case of export crash
                        dst, id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(filename)
                        src, id2, _version2, _datetime2 = qApp.instance().pm.getProjectNameIdVersionDatetime(project_file)
                        if id != id2:
                            message = '<center><h3 style="color: Red;">{}</h3><p>{} --> {}</p></center>'.format(qApp.instance().translate('Exporter', 'Cannot overwrite different dictionary'), src, dst)
                            mw.onShowWarning(' ', message)
                            self.exportProject()
                            return
                        src_perm = dlg.read_write_flag #qApp.instance().pm.isReadWrite(project_file)
                        dst_perm = qApp.instance().pm.isReadWrite(filename)
                        if src_perm != dst_perm and not self.replaceDiffPerm(src_perm, dst_perm):
                            self.exportProject()
                            return
                        elif not self.replaceZoozl(filename):
                            self.exportProject()
                            return
                read_write = dlg.read_write_flag  
                if not filename:
                    mw.onShowWarning('<strong>{}</strong>'.format(qApp.instance().translate('Exporter', 'No filename')))
                    self.exportProject()
                    return
                
                # #display progress dialog
                progress = QProgressDialog(mw)
                progress.setWindowTitle(qApp.instance().translate('Exporter', 'Export dictionary'))
                progress.setLabelText("<p><b>{}</b><br>{}</p><p style='color:blue; text-align:left;'>{}</p>".format(project_name, os.path.basename(project_file), qApp.instance().translate('Exporter', 'Preparing file inventory...')))
                progress.setCancelButton(QPushButton(QIcon(':/close.png'), qApp.instance().translate('Exporter', "Cancel")))
                progress.setMinimum(0)
                #progress.forceShow()                
                # get inventory
                inventory_file = self.pm.createInventory(progress_dlg=progress)
                inventory_json = {}
                with open(inventory_file, 'r', encoding='utf-8') as f:
                    inventory_json = json.load(f)
                inventory_files = inventory_json.get('files', [])
                inventory_files = [f.get('desktop_path', f.get('path')) for f in inventory_files]
                inventory_files.append(inventory_file.replace(project_dir, ''))
                inventory_files = set(inventory_files)        
                progress.setMaximum(progress.maximum() + len(inventory_files))                

                dst_zip = filename
                if os.path.splitext(dst_zip)[1].lower() != '.{}'.format(ARCHIVE_EXT):
                    dst_zip = "{}.{}".format(dst_zip, ARCHIVE_EXT)
                backup = '{}-backup'.format(dst_zip)

                if not progress.wasCanceled(): # could be canceled during inventory taking
                    progress.setLabelText("<p><b>{}</b><br>{}</p><p style='color:blue; text-align:left;'>{}</p>".format(project_name, os.path.basename(project_file), qApp.instance().translate('Exporter', 'Exporting dictionary...')))
                    #create empty destination/export zip file
                    project_filename = os.path.splitext(os.path.basename(dst_zip))[0]  
                    qApp.instance().pm.recordExportInfo(project_file, dst_zip, dst_rw) #record info at start in case of crash
    #               if dst_zip already exists (if we are overwriting), then make a copy in case we cancel the export and need to recover it 
                    if os.path.exists(dst_zip):
                        qApp.instance().pm.showMessage(qApp.instance().translate('Exporter', 'Backing up archive - please wait...'))
                        shutil.copyfile(dst_zip, backup)
                        qApp.instance().pm.showMessage('')
                    qApp.instance().pm.setWritePermission(dst_zip, True)
                    try:
                        z = ZipFile(dst_zip, "w", ZIP_DEFLATED)
                    except:
                        progress.cancel()
                        if os.path.exists(backup):
                            shutil.copyfile(backup, dst_zip)
                    else: 
                        count = 1
                        for fn in inventory_files: 
                            progress.setValue(progress.value() + 1)
                            absfn = f'{project_dir}{fn}'
                            absfn = qApp.instance().pm.lowerExt(absfn)
                            #print(os.path.exists(absfn), count, absfn)
                            count += 1
                            if not os.path.exists(absfn): #NOTE: what case does this handle???
                                try:
                                    _id = absfn.split('_id')[1].split('.')[0]
                                except:
                                    pass #???
                                else:
                                    system_pth = glob.glob('{}/*_id{}.*'.format(os.path.dirname(absfn), _id))
                                    if system_pth:
                                        absfn = system_pth[0]
                                    else:
                                        continue
                            zfn = absfn[len(project_dir)+len(os.sep):] #XXX: relative path
                            name = os.path.join(project_filename, zfn)
                            z.write(absfn, name)
                            qApp.processEvents()
                            if progress.wasCanceled():
                                break
                        z.close()
                        if not read_write:
                            qApp.instance().pm.setWritePermission(dst_zip, False)
                if progress.wasCanceled():  
                    message = QMessageBox.information(mw, qApp.instance().translate('Exporter', "Export cancelled"), "<center><p style='color:red'>{}</p></center>".format(qApp.instance().translate('Exporter', "Export cancelled"))) 
                    if os.path.exists(dst_zip):
                        try:
                            os.remove(dst_zip)
                        except: #read-only dictionary; won't delete until read-write permission set
                            qApp.instance().pm.setWritePermission(dst_zip, True)
                            os.remove(dst_zip)
                    if os.path.exists(backup):
                        qApp.instance().pm.showMessage(qApp.instance().translate('Exporter', 'Restoring backup of archive - please wait...'))
                        shutil.copyfile(backup, dst_zip) 
                        qApp.instance().pm.showMessage('')
                        qApp.instance().pm.setWritePermission(dst_zip, dst_rw) 
                else:
                    #progress.setValue(progress.value() + 1)
                    progress.close()
                    message = QMessageBox.information(mw, qApp.instance().translate('Exporter', "Dictionary exported"), "<center><p style='color:blue'>{}</p></center>".format(qApp.instance().translate('Exporter', 'Export successful')))
                    if os.path.exists(dst_zip):
                        qApp.instance().pm.setKnownProjectInfo(dst_zip)
                        name, _id, _version, _datetime = qApp.instance().pm.getProjectNameIdVersionDatetime(project_file, True)
                        qApp.instance().pm.updateKnownProjectInfoName(dst_zip, name)
                        qApp.instance().pm.updateKnownProjectInfoPermission(dst_zip, read_write)
                        qApp.instance().pm.updateKnownProjectInfoVersion(dst_zip, _version)
                        qApp.instance().pm.updateKnownProjectInfoDatetime(dst_zip, _datetime)
                        if os.path.exists(backup):
                            os.remove(backup) 
                    else: 
                        progress.close()
                        message = QMessageBox.warning(mw, qApp.instance().translate('Exporter', "Export failed"), "<center><p style='color:red'>{}</p></center>".format(qApp.instance().translate('Exporter', "Export failed")))
                        if os.path.exists(backup):
                            qApp.instance().pm.showMessage(qApp.instance().translate('Exporter', 'Restoring backup of archive - please wait...'))
                            shutil.copyfile(backup, dst_zip)
                            qApp.instance().pm.showMessage('')
                            qApp.instance().pm.setWritePermission(dst_zip, dst_rw)
                if os.path.exists(backup):
                    try:
                        os.remove(backup)
                    except:
                        qApp.instance().pm.addPossibleRemoval(backup)
            qApp.instance().pm.removeExportInfo() #export finished cleanly so remove this info

# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()
