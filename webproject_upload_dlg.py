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

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QObject

from PyQt5.QtGui import QCursor, QIcon

from PyQt5.QtWidgets import qApp, QDialog
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QGroupBox

import os, sys
import requests
import json
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from datetime import datetime, timezone, timedelta
import keyring
import shutil
import time

#backend_url = "http://localhost:4000/local/"
#backend_url = "https://api-webtest.soosl.net/"
#backend_url = "https://api-web.soosl.net/"

class ProjectVariant(QObject):
   def __init__(self, variant, parent):
      super(ProjectVariant, self).__init__(parent)
      self.project_id = qApp.instance().pm.project.id
      self.locked = False
      self.public_or_private = variant.get('projectVariant')
      self.status = variant.get('status')
      if self.status == 'locked':
         self.locked = True
      self.session_id = variant.get('uploadSessionId', '')
      self.username = self.parent().username
      self.expires_at = ''
      if self.locked:
         session_info = variant.get('sessionInfo', {})
         if 'uploadSessionId' in session_info.keys():
            self.session_id = session_info.get('uploadSessionId', self.session_id) # removed for production security; keep available for testing
         self.username = session_info.get('username')
         self.expires_at = session_info.get('expiresAt')
      self.lastuser = variant.get('lastUpload', {}).get('username', '')
      self.uploadtime = variant.get('lastUpload', {}).get('uploadTime', '')
      if self.uploadtime:
         self.uploadtime = qApp.instance().pm.getCurrentDateTimeStr(self.uploadtime)
      self.upload_count = self.parent().getPublicSessionCount()
      if self.public_or_private == 'private':
         self.upload_count = self.parent().getPrivateSessionCount()
      self.s3_folder = variant.get("s3Folder")
      self.selected = False

class WebProjectUploadDlg(QDialog):
   upload = pyqtSignal(str, str, list)
   response_msg = pyqtSignal(str)
   upload_complete = pyqtSignal()
   auth_response = pyqtSignal(requests.Response, str)

   def __init__(self, parent=None, dialects=None):
      super(WebProjectUploadDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
      txt = qApp.instance().translate('WebProjectUploadDlg', 'Upload Dictionary')
      self.setWindowTitle(txt)
      self.setSizeGripEnabled(True)

      if sys.platform.startswith('win'):
         keyring.core.set_keyring(keyring.core.load_keyring('keyring.backends.Windows.WinVaultKeyring'))
      elif sys.platform.startswith('darwin'):
         keyring.core.set_keyring(keyring.core.load_keyring('keyring.backends.macOS.Keyring'))
      elif sys.platform.startswith('linux'):
         keyring.core.set_keyring(keyring.core.load_keyring('keyring.backends.SecretService.Keyring'))

      self.already_uploaded_files = self.getAlreadyUploadedFiles()

      layout = QVBoxLayout()
      layout.setSpacing(3)
      layout.setContentsMargins(3, 3, 3, 3)

      settings = qApp.instance().getSettings()
      backend = settings.value('lastWebBackend', 'https://api-web.soosl.net/')

      self.remember_credentials = settings.value('rememberWebCresentials', 1)

      username = settings.value('lastWebUsername', '')
      psswrd = ''
      if username:
         qApp.processEvents()
         psswrd = keyring.get_password('websoosl', username)
         qApp.processEvents()

      self.password_field = QLineEdit()
      self.password_field.setEchoMode(QLineEdit.Password)
      self.password_field.setText(psswrd)

      self.username_field = QLineEdit()
      self.username_field.setText(username)
      self.username_field.textChanged.connect(self.onUsernameChanged)

      self.backend_field = QLineEdit()
      self.backend_field.setText(backend)
      self.response_field = QTextBrowser()
      self.response_field.setReadOnly(True)
      self.response_field.setOpenExternalLinks(True)
      self.response_field.setFocusPolicy(Qt.NoFocus)
      self.upload_btn = QPushButton(qApp.instance().translate('WebProjectUploadDlg', 'Upload'))
      self.upload_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
      self.upload_btn.pressed.connect(self.onUpload)

      showhide_box = QCheckBox()
      showhide_box.setCursor(QCursor(Qt.PointingHandCursor))
      showhide_box.clicked.connect(self.onShowHideClicked)
      showhide_box.setToolTip(qApp.instance().translate('WebProjectUploadDlg', "Show password"))
      showhide_box.setMinimumSize(20, 20)
      showhide_box.setStyleSheet("""QCheckBox:indicator:checked{image: url(':/show.png')}
         QCheckBox:indicator:unchecked{image: url(':/hide.png')}"""
         )

      remember_box = QCheckBox()
      if self.remember_credentials:
         remember_box.setChecked(True)
      remember_box.clicked.connect(self.onRememberCredentials)
      remember_box.setMinimumSize(20, 20)

      self.progress_bar = QProgressBar()
      self.progress_bar.setHidden(True)
      self.progress_bar.setMinimum(0)
      self.progress_bar.setTextVisible(True)

      self.settings_widget = QWidget()
      settings_layout = QGridLayout()
      self.settings_widget.setLayout(settings_layout)
      settings_layout.addWidget(QLabel(qApp.instance().translate('WebProjectUploadDlg', 'Upload to:')), 0, 0)
      settings_layout.addWidget(self.backend_field, 0, 2)
      settings_layout.addWidget(QLabel(qApp.instance().translate('WebProjectUploadDlg', 'Username:')), 1, 0)
      settings_layout.addWidget(self.username_field, 1, 2)
      settings_layout.addWidget(QLabel(qApp.instance().translate('WebProjectUploadDlg', 'Password:')), 2, 0)
      settings_layout.addWidget(showhide_box, 2, 1)
      settings_layout.addWidget(self.password_field, 2, 2)
      settings_layout.addWidget(remember_box, 3, 1)
      settings_layout.addWidget(QLabel(qApp.instance().translate('WebProjectUploadDlg', 'Remember username and password')), 3, 2)

      layout.addWidget(self.response_field)
      layout.addWidget(self.progress_bar)
      layout.addWidget(self.settings_widget)

      self.settings_btn = QToolButton()
      self.settings_btn.setIcon(QIcon(':/settings16.png'))
      self.settings_btn.setToolTip(qApp.instance().translate('WebProjectUploadDlg', "Show settings"))
      self.settings_btn.setCheckable(True)
      self.settings_btn.setAutoRaise(True)
      self.settings_btn.setChecked(True)
      self.settings_btn.toggled.connect(self.onShowSettings)

      btnBox = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
      btnBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
      self.ok_btn = btnBox.button(QDialogButtonBox.Ok)
      self.cancel_btn = btnBox.button(QDialogButtonBox.Cancel)
      self.ok_btn.setText(qApp.instance().translate('WebProjectUploadDlg', 'Done'))
      self.cancel_btn.setText(qApp.instance().translate('WebProjectUploadDlg', 'Cancel'))
      self.ok_btn.setDisabled(True)

      self.sign_count_label = QLabel()
      btnBox.accepted.connect(self.accept)
      btnBox.rejected.connect(self.reject)
      hlayout = QHBoxLayout()
      hlayout.addWidget(self.settings_btn)
      hlayout.addWidget(self.sign_count_label)
      hlayout.addWidget(self.upload_btn)
      hlayout.addWidget(btnBox)
      layout.addLayout(hlayout)

      self.setLayout(layout)
      self.uploading = False
      self.incomplete_uploads = False

      self.value = 1
      self.abort = False
      self.uploads = 0
      self.variants = []

      self.public_session = None
      self.private_session = None

      self.response_msg.connect(self.showResponseMessage)
      self.upload_complete.connect(self.onDone)
      self.auth_response.connect(self.handleAuthenticationResponse)

      self.internet_access = True # assume so

      self.private_upload_complete = False
      self.public_upload_complete = False
      # when both are True, upload button can be disabled

   def getAlreadyUploadedFiles(self):
      files = []
      filename = '{}/{}.uploads'.format(self.project_dir, self.project_id)
      if os.path.exists(filename):
         with open(filename, 'r', encoding='utf-8', newline='\n') as f:
            files = json.load(f)
      return files

   def rememberAlreadyUploaded(self):
      filename = '{}/{}.uploads'.format(self.project_dir, self.project_id)
      _str = json.dumps(self.already_uploaded_files, sort_keys=False, indent=4, ensure_ascii=False)
      with open(filename, 'wb') as f:
         f.write(_str.encode('utf-8'))

   def forgetAlreadyUploaded(self):
      self.already_uploaded_files.clear()
      filename = '{}/{}.uploads'.format(self.project_dir, self.project_id)
      if os.path.exists(filename):
         os.remove(filename)

   def rememberFile(self, filename, _hash):
      self.already_uploaded_files.append([filename, _hash])

   def isFileRemembered(self, filename):
      _hash = qApp.instance().pm.getFreshHash(filename)
      if [filename, _hash] in self.already_uploaded_files:
         return True
      return False

   def updateSignCount(self, sign_count):
      if not hasattr(self.sign_count_label, 'count'):
         self.sign_count_label.count = 0
      self.sign_count_label.count += 1
      txt = '{}/{} {}'.format(self.sign_count_label.count, sign_count, qApp.instance().translate('WebProjectUploadDlg', 'signs'))
      self.sign_count_label.setText(txt)

   def abortUpload(self):
      self.abort = True
      qApp.instance().pm.abort_inventory = True
      msg = '<div style="color:blue;"><br>{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Upload aborted.'))
      self.response_msg.emit(msg)
      self.upload_btn.setEnabled(False)

   def keepWebFiles(self, title):
      dlg = QDialog(self, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)
      layout = QVBoxLayout()
      dlg.setLayout(layout)
      dlg.setWindowTitle(' ')

      lbl = QLabel()
      lbl.setStyleSheet('text-align: left')
      lbl.setText('<b style="color:blue;">{}</b><br>'.format(title))
      layout.addWidget(lbl)

      radio_layout = QGridLayout()
      radio1 = QRadioButton()
      txt = qApp.instance().translate('WebProjectUploadDlg', "Keep the files already uploaded.")
      txt2 = qApp.instance().translate('WebProjectUploadDlg', "I will finish uploading within the next 12 hours.")
      msg = '<b>{}</b><br>{}<br>({})'.format(txt, txt2, qApp.instance().translate('WebProjectUploadDlg', 'Other users will not be able to upload during this time period.'))
      lbl = QLabel(msg)
      radio_layout.addWidget(radio1, 0, 0)
      radio_layout.addWidget(lbl, 0, 1)

      radio2 = QRadioButton()
      txt = qApp.instance().translate('WebProjectUploadDlg', "Discard the files already uploaded.")
      txt2 =  qApp.instance().translate('WebProjectUploadDlg', "If I start again, I'll upload everything again.")
      msg = '<b>{}</b><br>{}'.format(txt, txt2)
      lbl = QLabel(msg)
      radio_layout.addWidget(radio2, 1, 0)
      radio_layout.addWidget(lbl, 1, 1)

      radio_layout.setAlignment(radio1, Qt.AlignTop)
      radio_layout.setAlignment(radio2, Qt.AlignTop)

      btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
      btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
      btnBox.button(QDialogButtonBox.Ok).setCursor(QCursor(Qt.PointingHandCursor))
      btnBox.button(QDialogButtonBox.Ok).setText(' {} '.format(qApp.instance().translate('WebProjectUploadDlg', 'Ok')))
      btnBox.accepted.connect(dlg.accept)

      layout.addLayout(radio_layout)
      layout.addStretch()
      layout.addWidget(btnBox)

      radio1.setChecked(True)

      if dlg.exec_():
         if radio1.isChecked():
            self.rememberAlreadyUploaded()
         else:
            self.forgetAlreadyUploaded()
         return radio1.isChecked()
      self.rememberAlreadyUploaded()
      return True

   def updateProgress(self, value=0):
      # call with value == 1 in order to clear and hide progress bar
      if value:
         self.value = value
      if self.value > 1 and not self.progress_bar.isVisible():
         self.progress_bar.show()
      elif self.value <= 1:
         self.progress_bar.hide()
      self.progress_bar.setValue(self.value)
      self.value += 1
      if self.value > 1:
         self.progress_bar.repaint()
      qApp.processEvents()

   def authenticate(self, session_id='', timeout=60):
      text = qApp.instance().translate('WebProjectUploadDlg', 'Authenticating...')
      self.response_msg.emit(text)
      authData = {"username" : self.username, "password" : self.password, "projectId" : self.project_id}
      headers = {'Content-Type': 'application/json', 'Content-MD5': 'ContentMD5'}
      if session_id:
         authData["uploadSessionId"] = session_id
      backend_url = self.backend_field.text()
      try:
         response = requests.post(backend_url + "projects/authenticate-for-update", headers=headers, data=json.dumps(authData, ensure_ascii=False), timeout=timeout)
      except requests.Timeout:
         response = QObject()
         response.status_code = 418
         response.content = '{"message": "request_timed_out"}' #qApp.instance().translate('WebProjectUploadDlg', 'Connection request timed out.')
         self.handleResponseErrors(response)
      except requests.ConnectionError:
         response = QObject()
         response.status_code = 400
         response.content = '{"message": "connection_error"}' #qApp.instance().translate('WebProjectUploadDlg', 'Connection error.')
         self.handleResponseErrors(response)
      else:
         self.auth_response.emit(response, session_id)
      #self.upload_btn.setEnabled(True)

   def reauthenticate(self, variant, timeout=60):
      session_id = variant.session_id
      try:
         self.s3_client.close()
      except:
         del self.s3_client

      text = qApp.instance().translate('WebProjectUploadDlg', 'Re-authenticating...')
      self.response_msg.emit(text)
      authData = {"username" : self.username, "password" : self.password, "projectId" : self.project_id, "uploadSessionId" : session_id}
      headers = {'Content-Type': 'application/json', 'Content-MD5': 'ContentMD5'}
      backend_url = self.backend_field.text()
      try:
         response = requests.post(backend_url + "projects/authenticate-for-update", headers=headers, data=json.dumps(authData, ensure_ascii=False), timeout=timeout)
      except:
         return (None, None)
      else:
         response_data = json.loads(response.content)
         self.s3_client = boto3.client('s3',
            aws_access_key_id=response_data.get("accessKeyId"),
            aws_secret_access_key=response_data.get("secretAccessKey"),
            aws_session_token=response_data.get("sessionToken"),
            region_name=response_data.get("regionName"),
            config=Config(s3={"use_accelerate_endpoint": True})
         )
         bucket = response_data.get("uploadBucket")
         if not self.accelerated_transfer(self.s3_client, bucket):
            del self.s3_client
            self.s3_client = boto3.client('s3',
               aws_access_key_id=response_data.get("accessKeyId"),
               aws_secret_access_key=response_data.get("secretAccessKey"),
               aws_session_token=response_data.get("sessionToken"),
               region_name=response_data.get("regionName"))

      project_variants = response_data.get('projectVariants', [])
      self.variants = [ProjectVariant(v, self) for v in project_variants]
      selected_variant = None
      unselected_variant = None
      for v in self.variants:
         self.setUploadSessionIdAndCount(v, 0)
         if v.session_id == session_id:
            selected_variant = v
         else:
            unselected_variant = v
      if unselected_variant:
         self.unlockDictionary(unselected_variant)
         self.variants.remove(unselected_variant)

      return (self.s3_client, bucket)

   def handleResponseErrors(self, response):
      if (response.status_code == 400):
         _dict = eval(response.content)
         msg = _dict.get('message', '')
         if msg == 'something_went_wrong':
            self.response_msg.emit('something_went_wrong')
            self.response_msg.emit(str(response.content))
         elif msg == 'connection_error':
            self.response_msg.emit('connection_error')
         elif msg == 'update_in_progress':
            self.response_msg.emit('update_in_progress')
         else:
            self.response_msg.emit(msg)

      elif (response.status_code == 401):
         _dict = eval(response.content)
         msg = _dict.get('message', '')
         if msg == 'wrong_username_or_password':
            self.response_msg.emit('wrong_username_or_password')
         else:
            self.response_msg.emit(msg)

      elif (response.status_code == 403):
         _dict = eval(response.content)
         msg = _dict.get('message', '')
         if msg == 'not_authorized':
            self.response_msg.emit('not_authorized')
         elif msg == 'project_is_locked':
            upload_session = _dict.get('uploadSession', {})
            start_time = upload_session.get('startTime', 0)
            start_time = qApp.instance().pm.getCurrentDateTimeStr(start_time)
            username = upload_session.get('username', 'unknown')
            print('upload', username)
            msg = '<div style="color:red;">{} {}<br>{} {}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Dictionary was locked against updating by:'), username, qApp.instance().translate('WebProjectUploadDlg', 'On:'), start_time)
            self.response_msg.emit(msg)
         else:
            self.response_msg.emit(msg)

      elif (response.status_code == 404):
         try:
            _dict = eval(response.content)
         except:
            msg = response.content.decode('utf-8')
         else:
            msg = _dict.get('message', None)
         if msg == 'dictionary_not_found':
            self.response_msg.emit('dictionary_not_found')
         # elif msg == 'session_not_found': # no need to handle this, just recording here as option in case we need it later
         #    pass

      else:
         try:
            _dict = eval(response.content)
         except:
            msg = 'Error: <br><br>{}'.format(response.content.decode('utf-8'))
         else:
            msg = _dict.get('message', qApp.instance().translate('WebProjectUploadDlg', 'Error'))
         self.response_msg.emit(msg)

      qApp.restoreOverrideCursor()
      self.upload_btn.setEnabled(True)

   def __developerUnlockDictionary(self):
      for v in self.variants:
         self.unlockDictionary(v, dev=True)
      self.variants.clear()
      self.response_field.clear()
      self.ok_btn.setDisabled(False)
      self.cancel_btn.setDisabled(True)
      self.upload_btn.setDisabled(False)
      qApp.processEvents()

   def processStoredIds(self):
      """
      A crash on a previous upload attempt will leave project locked.
      Unlock now if no files were actually uploaded.
      """
      public_id = self.getPublicSessionId()
      public_count = self.getPublicSessionCount()
      variant = QObject()
      variant.username = self.username
      session_ids = []
      if public_id and not public_count:
         variant.session_id = public_id
         variant.public_or_private = 'public'
         self.unlockDictionary(variant)
      elif public_id:
         session_ids.append(public_id)
      private_id = self.getPrivateSessionId()
      private_count = self.getPrivateSessionCount()
      if private_id and not private_count:
         variant.session_id = private_id
         variant.public_or_private = 'private'
         self.unlockDictionary(variant)
      elif private_id:
         session_ids.append(private_id)
      if session_ids:
         return session_ids[0]
         #NOTE: "may" be a case where there are both a public and private stored session...
      return ''

   def unlockDictionary(self, variant, dev=False):
      username = variant.username
      session_id = variant.session_id
      if not dev and username != self.username:
         #print('Cannot unlock dictionary locked by another user:', username, self.username)
         return
      backend_url = self.backend_field.text()
      authData = { "projectId" : self.project_id, "uploadSessionId" : session_id}
      headers = {'Content-Type': 'application/json'}
      try:
         response = requests.post(backend_url + "projects/unlock", headers=headers, data=json.dumps(authData, ensure_ascii=False), timeout=60)
      except requests.Timeout:
         response = QObject()
         response.status_code = 418
         response.content = '{"message": "request_timed_out"}' #qApp.instance().translate('WebProjectUploadDlg', 'Connection request timed out.')
         self.handleResponseErrors(response)
      except requests.ConnectionError:
         response = QObject()
         response.status_code = 400
         response.content = '{"message": "connection_error"}' #qApp.instance().translate('WebProjectUploadDlg', 'Connection error.')
         self.handleResponseErrors(response)
      else:
         # The API returns:
         # - 200 in case of success
         # - 404 if the project is not found
         # - 400 if the project is not locked
         if response.status_code == 200:
            self.clearSessionId(username, variant.public_or_private)
            msg = qApp.instance().translate('WebProjectUploadDlg', "Dictionary unlocked.")
            self.response_msg.emit(msg)
            #return response_data
         elif response.status_code == 400:
            msg = qApp.instance().translate('WebProjectUploadDlg', "Dictionary not unlocked.")
            self.response_msg.emit(msg)
         else:
            self.handleResponseErrors(response)
      #return None

   def getTimeTillExpires(self, expires):
      dt_expire = qApp.instance().pm.fromIsoFormat(expires)
      dt_expire = qApp.instance().pm.to_local_datetime(dt_expire)
      dt_now = datetime.now(timezone.utc)
      time_delta = dt_expire - dt_now
      hours, remainder = divmod(time_delta.seconds, 3600)
      minutes, seconds = divmod(remainder, 60)
      expires = '{} {}, {} {}'.format(hours, qApp.instance().translate('WebProjectUploadDlg', 'hours'), minutes, qApp.instance().translate('WebProjectUploadDlg', 'minutes'))
      return expires

   def getUploadTime(self, expires):
      # given the time when a lock expires, return the time when the upload was attempted last
      # (currently locks are on for 12 hours)
      dt_expire = qApp.instance().pm.fromIsoFormat(expires)
      upload_time = dt_expire - timedelta(hours=12)
      upload_time = str(qApp.instance().pm.to_local_datetime(upload_time))
      return qApp.instance().pm.getCurrentDateTimeStr(upload_time)

   def selectVariant(self, variants):
      if len(variants) == 1:
         v = variants[0]
         if v.status == 'locked':
            pass # let's see what the dialog shows...
         elif v.status != 'inventory_not_found':
            v.selected = True
            return (v, None) # don't show choice dialog if only one variant
      qApp.restoreOverrideCursor()
      dlg = QDialog(self, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint)
      dlg.setWindowTitle(qApp.instance().translate('WebProjectUploadDlg', 'Select dictionary variant'))
      value = 0
      btns = []
      layout = QVBoxLayout()
      group = QGroupBox('')
      group.setStyleSheet("""QGroupBox{font-weight:bold;}""")
      glayout = QGridLayout()
      glayout.setContentsMargins(3, 3, 3, 3)
      glayout.setSpacing(6)
      can_upload = False
      #locks = False
      for idx, v in enumerate(variants):
         txt = ''
         txt2 = qApp.instance().translate('WebProjectUploadDlg', 'public')
         if v.public_or_private == 'private':
            txt = '<img src="{}">'.format(':/keys.png')
            txt2 = qApp.instance().translate('WebProjectUploadDlg', 'private')
         lbl = QLabel(txt)
         lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
         lbl.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
         glayout.addWidget(lbl, idx, 0)
         btn = QRadioButton(txt2)
         btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
         if v.status == 'ready':
            can_upload = True
            txt = qApp.instance().translate('WebProjectUploadDlg', 'Last upload by:')
            user = v.lastuser
            if v.upload_count:
               txt = '{} {} {}'.format(qApp.instance().translate('WebProjectUploadDlg', 'Incomplete.'), v.upload_count, qApp.instance().translate('WebProjectUploadDlg', 'files uploaded by:'))
               self.incomplete_uploads = True
               user = v.username # only way to have an upload count is if you were doing the upload and cancelled/crashed
            txt = '{} <b>{}</b><br>{} <b>{}</b>'.format(txt, user, qApp.instance().translate('WebProjectUploadDlg', 'On:'), v.uploadtime)
            glayout.addWidget(QLabel(txt), idx, 2, alignment=Qt.AlignTop)
            #can_upload = True
         elif v.status == 'locked':
            #locks = True
            time_till_expires = self.getTimeTillExpires(v.expires_at)
            if v.username != self.username: # locked by another user
               btn.setEnabled(False)
               txt = '{} <b>{}</b><br>{} <b>{}</b>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Locked by:'), v.username, qApp.instance().translate('WebProjectUploadDlg', 'Current lock expires:'), time_till_expires)
               glayout.addWidget(QLabel(txt), idx, 2, alignment=Qt.AlignTop)
            elif v.username == self.username: # locked by same user in another session on another computer
               btn.setEnabled(False)
               txt = '{} <b>{}</b><br>{} <b>{}</b>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Locked on another computer by:'), v.username, qApp.instance().translate('WebProjectUploadDlg', 'Current lock expires:'), time_till_expires)
               glayout.addWidget(QLabel(txt), idx, 2, alignment=Qt.AlignTop)
         elif v.status == 'inventory_not_found':
            self.response_msg.emit('inventory_not_found') # NOTE: shouldn't this be a response.content == 404 error?
            del dlg
            return None
         elif v.status == 'update_in_progress':
            btn.setEnabled(False)
            txt = '{} <b>{}</b>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Website is being updated by:'), v.username)
            glayout.addWidget(QLabel(txt), idx, 2, alignment=Qt.AlignVCenter)
         btn.idx = idx
         glayout.addWidget(btn, idx, 1)
         btns.append(btn)

      group.setLayout(glayout)
      layout.addWidget(group)

      layout.addStretch()
      btnBox = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
      btnBox.button(QDialogButtonBox.Ok).setText(qApp.instance().translate('WebProjectUploadDlg', 'Upload'))
      if not can_upload:
         btnBox.button(QDialogButtonBox.Ok).setEnabled(False)
         btnBox.button(QDialogButtonBox.Cancel).setFocus(True)
      btnBox.accepted.connect(dlg.accept)
      btnBox.rejected.connect(dlg.reject)
      layout.addWidget(btnBox)

      if btns[0].isEnabled() and btns[0].text() == 'public':
         btns[0].setChecked(True)
      elif len(btns) > 1 and btns[1].isEnabled() and btns[1].text() == 'public':
         btns[1].setChecked(True)
      elif btns[0].isEnabled():
         btns[0].setChecked(True)
      elif len(btns) > 1 and btns[1].isEnabled():
         btns[1].setChecked(True)
      dlg.setLayout(layout)

      if not dlg.exec_():
         msg = qApp.instance().translate('WebProjectUploadDlg', "No dictionary variant selected.")
         self.response_msg.emit(msg)
         return (None, None)
      qApp.setOverrideCursor(Qt.BusyCursor)

      selected_variant = None
      unselected_variant = None
      for btn in btns:
         if btn.isChecked():
            selected_variant = variants[btn.idx]
            selected_variant.selected = True
         else:
            unselected_variant = variants[btn.idx]
            unselected_variant.selected = False
      return (selected_variant, unselected_variant)

   def accelerated_transfer(self, client, bucket):
      try:
         response = client.get_bucket_accelerate_configuration(Bucket=bucket)
      except:
         pass
      else:
         if response.get('Status', None) == 'Enabled':
            return True
      return False

   def isSignFile(self, file_jsn):
      if file_jsn.get('path', '').count('signs/') and file_jsn.get('path', '').endswith('.json'):
         return True
      return False

   def fullPath(self, file_jsn):
      full_path = self.project_dir + file_jsn.get('path', '')
      return full_path

   def uploadVariant(self, variant, response_data):
      desktop_inventory = ''
      web_inventory = ''
      changes_file = ''
      upload_changes_file = ''
      self.internet_access = True # assume so, will change to False in this method if not.
      if not variant.upload_count:
         self.forgetAlreadyUploaded()

      def _return():
         return (desktop_inventory, web_inventory, changes_file, upload_changes_file)

      msg = "{} {} [{}]".format(qApp.instance().translate('WebProjectUploadDlg', 'Ready to upload:'), variant.project_id, variant.public_or_private)
      self.response_msg.emit(msg)
      if variant.session_id:
         userId = response_data.get('userId')
         userEmail = response_data.get('userEmail')
         lastUploadUsername = response_data.get('lastUploadUsername')

         if variant.uploadtime and lastUploadUsername:
            last_upload_str = qApp.instance().pm.getCurrentDateTimeStr(variant.uploadtime)
            msg = '\n{} {}'.format(qApp.instance().translate('WebProjectUploadDlg', 'Last uploaded:'), last_upload_str)
            self.response_msg.emit(msg)
            msg = '{} {}\n'.format(qApp.instance().translate('WebProjectUploadDlg', 'Last uploaded by:'), lastUploadUsername)
            self.response_msg.emit(msg)

         self.s3_client = boto3.client('s3',
            aws_access_key_id=response_data.get("accessKeyId"),
            aws_secret_access_key=response_data.get("secretAccessKey"),
            aws_session_token=response_data.get("sessionToken"),
            region_name=response_data.get("regionName"),
            config=Config(s3={"use_accelerate_endpoint": True}))
         bucket = response_data.get("uploadBucket")
         if not self.accelerated_transfer(self.s3_client, bucket):
            del self.s3_client
            self.s3_client = boto3.client('s3',
               aws_access_key_id=response_data.get("accessKeyId"),
               aws_secret_access_key=response_data.get("secretAccessKey"),
               aws_session_token=response_data.get("sessionToken"),
               region_name=response_data.get("regionName"))

         #read inventory
         # websoosl-upload-dev/1zE65i3XNoon7rlvts5jvOeDSnV/demo-asl-74424/private/demo-asl-74424.inventory
         if not variant.s3_folder:
            self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'No s3 folder found.') + '\n')
            self.response_msg.emit(str(variant))
            qApp.restoreOverrideCursor()
            return _return()
         object_name = '{}{}.inventory'.format(variant.s3_folder, self.project_id)
         if not bucket:
            self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'No bucket found.') + '\n')
            self.response_msg.emit(str(variant))
            qApp.restoreOverrideCursor()
            return _return()
         errors = 0
         self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'Reading web inventory...'))
         try:
            inventory_file = self.s3_client.get_object(Bucket=bucket, Key=object_name)
         except EndpointConnectionError as e:
            self.internet_access = False
            self.updateProgress(1)
            self.abort = True
            txt = qApp.instance().translate('WebProjectUploadDlg', 'No Internet connection.')
            msg = '<div style="color:red;"><br>{}<br><br>{}</div>'.format(txt, str(e))
            self.response_msg.emit(msg)
            self.abortUpload()
            self.rememberAlreadyUploaded()
            errors = 1
         except ClientError as e:
            error = str(e)
            if not self.accelerated_transfer(self.s3_client, bucket):
               del self.s3_client
               self.s3_client = boto3.client('s3',
                  aws_access_key_id=response_data.get("accessKeyId"),
                  aws_secret_access_key=response_data.get("secretAccessKey"),
                  aws_session_token=response_data.get("sessionToken"),
                  region_name=response_data.get("regionName")
                  )
               inventory_file = self.s3_client.get_object(Bucket=bucket, Key=object_name)
            else:
               errors = 1
               self.response_msg.emit(error)
               self.response_msg.emit(str(e.response['ResponseMetadata']['HTTPStatusCode']))

         if not errors:
            inventory_json = json.loads(inventory_file['Body'].read())
            web_inventory =  f'{self.project_dir}/{self.project_id}-web.inventory'
            with open(web_inventory, 'wb') as f:
               _str = json.dumps(inventory_json, sort_keys=False, indent=4, ensure_ascii=False)
               _str = self.webStrToDesktop(_str, True).encode('utf-8')
               f.write(_str)
            self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'Reading desktop inventory...'))
            desktop_inventory = qApp.instance().pm.createInventory()
            self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'Comparing inventories...'))
            if desktop_inventory and web_inventory:
               changes_file = qApp.instance().pm.createInventoryChangeFile(web_inventory, desktop_inventory)
               changes_json = {}
               with open(changes_file, 'r', encoding='utf-8') as f:
                  changes_json = json.load(f)

               old = changes_json.get('oldProjectModifiedDateTime', '0')
               new = changes_json.get('newProjectModifiedDateTime', '0')
               if old > new: #project on web is newer than desktop project
                  msgBox = QMessageBox(self)
                  msgBox.setIcon(QMessageBox.Warning)
                  msgBox.setTextFormat(Qt.RichText)
                  msgBox.setWindowTitle(' ')
                  msgBox.setText('<b>{}</b>'.format(qApp.instance().translate('WebProjectUploadDlg', "The website dictionary is newer than the one that you are uploading.")))
                  msgBox.setInformativeText(qApp.instance().translate('WebProjectUploadDlg', "Overwrite the website dictionary with this older version?"))
                  msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                  yes_btn, no_btn = msgBox.buttons()
                  yes_btn.setIcon(QIcon(":/thumb_up.png"))
                  no_btn.setIcon(QIcon(":/thumb_down.png"))
                  msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('WebProjectUploadDlg', "Yes"))
                  msgBox.button(QMessageBox.No).setText(qApp.instance().translate('WebProjectUploadDlg', "No"))
                  msgBox.setDefaultButton(QMessageBox.Yes)

                  if msgBox.exec_() == QMessageBox.No:
                     self.abortUpload() # set abort flags, no further processing once set
                     self.unlockDictionary(variant)
                     self.accept() #close dialog
               if not self.abort:
                  ## proceed with uploads...
                  ###############################################################
                  new_files_to_upload = changes_json.get('newFiles', [])
                  changed_files_to_upload = changes_json.get('changedFiles', [])
                  files_to_upload = changed_files_to_upload + new_files_to_upload # puts project.json to front
                  files_to_delete = changes_json.get('deletedFiles', [])
                  ################################################################

                  self.progress_bar.setMaximum(len(files_to_upload) + 2)
                  remaining_files_to_upload = []
                  if files_to_upload:
                     file_count = len(files_to_upload)
                     sign_count = len([f for f in files_to_upload if self.isSignFile(f)])
                     remaining_files_to_upload = [f for f in files_to_upload if not self.isFileRemembered(self.fullPath(f))]
                     remaining_file_count = len(remaining_files_to_upload)
                     remaining_sign_count = len([f for f in remaining_files_to_upload if self.isSignFile(f)])

                     self.sign_count_label.count = sign_count - remaining_sign_count
                     self.updateProgress(file_count - remaining_file_count)

                     idx = 0
                     while idx < remaining_file_count:
                        f = remaining_files_to_upload[idx]
                        if self.abort:
                           break
                        self.uploads += 1
                        pth = f.get('path')
                        desk_pth = f.get('desktop_path', '')

                        _dir = '' #main dictionary file
                        if pth.count('signs/'):
                           _dir = 'signs/'
                        elif pth.count('sentences/'):
                           _dir = 'sentences/'
                        elif pth.count('extra_videos/'):
                           _dir = 'extra_videos/'
                        elif pth.count('extra_pictures/'):
                           _dir = 'extra_pictures/'

                        filename = f'{self.project_dir}{pth}'
                        desk_filename = ''
                        if desk_pth:
                           desk_filename = f'{self.project_dir}{desk_pth}'
                        desktop_hash = qApp.instance().pm.getFreshHash(filename)
                        _base = os.path.basename(pth)
                        _filename = None
                        project_file_flag = False
                        if filename == self.project_json_file:
                           project_file_flag = True
                           _base2 = self.project_id + '.json'
                           if _base != _base2: # web upload requires project file in the format of _base2
                              _filename = self.project_dir + '/' + _base2
                              shutil.copyfile(filename, _filename)
                              filename = _filename
                              _base = _base2
                        object_name = variant.s3_folder + _dir + _base
                        query_response = ''
                        try: # check for already existing file
                           query_response = self.s3_client.head_object(Bucket=bucket, Key=object_name)
                        except EndpointConnectionError as e:
                           self.internet_access = False
                           self.updateProgress(1) #hide progress bar
                           txt = qApp.instance().translate('WebProjectUploadDlg', 'No Internet connection.')
                           msg = '<div style="color:red;"><br>{}<br><br>{}</div>'.format(txt, str(e))
                           self.response_msg.emit(msg)
                           self.abortUpload()
                           self.rememberAlreadyUploaded()
                        except ClientError as e: # file not found; go ahead and upload
                           name = filename
                           if desk_filename:
                              name = desk_filename
                           body = open(name, 'rb').read()
                           if filename.lower().endswith('.json'):
                              with open(name, 'r', encoding='utf-8', newline='\n') as f:
                                 jsn = json.load(f)
                                 _str = json.dumps(jsn, sort_keys=False, indent=4, ensure_ascii=False)
                                 body = self.desktopStrToWeb(_str).encode('utf-8')
                           try:
                              if filename.count('/_signs/') and filename.endswith('.json'):
                                 sign_id = self.getSignIdFromPath(name)
                                 fg = self.getSignDisplayText(sign_id, qApp.instance().pm.project)
                                 msg = '<div style="color:blue;">{} - "{}"</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Uploading sign'), fg)
                                 self.response_msg.emit(msg)
                                 self.updateSignCount(sign_count)
                              elif self.project_dir + pth == self.project_json_file:
                                 msg = '<div style="color:blue;">{} - "{}"</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Uploading project file'), self.project_id)
                                 self.response_msg.emit(msg)
                              self.response_msg.emit('    {}'.format(os.path.basename(name)))
                              # https://stackoverflow.com/questions/22403071/text-files-uploaded-to-s3-are-encoded-strangely
                              content_type = "text/plain;charset=utf-8"
                              upload_response = self.s3_client.put_object(
                                 Body=body,
                                 ContentType=content_type,
                                 Bucket=bucket,
                                 Key=object_name,
                                 Metadata={'md5': desktop_hash}
                                 )
                           except EndpointConnectionError as e:
                              self.internet_access = False
                              self.updateProgress(1)
                              self.abort = True
                              txt = qApp.instance().translate('WebProjectUploadDlg', 'No Internet connection.')
                              msg = '<div style="color:red;"><br>{}<br><br>{}</div>'.format(txt, str(e))
                              self.response_msg.emit(msg)
                              self.abortUpload()
                              self.rememberAlreadyUploaded()
                           except ClientError as e:
                              ## credentials timeouted after 1Hr
                              self.s3_client, bucket = self.reauthenticate(variant)
                              retry = 0
                              while (not self.s3_client or not bucket) or retry == 10:
                                 retry += 1
                                 self.thread().msleep(500)
                                 qApp.processEvents()
                              if (not self.s3_client or not bucket):
                                 msg = '<div style="color:red;"> {}.</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Upload failed:'), str(e.response['ResponseMetadata']['HTTPStatusCode']))
                                 self.response_msg.emit(msg)
                                 #self.abortUpload()
                                 self.uploads -= 1 # only case where I need to decrement upload flag
                                 # leave other cases alone as they indicate a file already on the web
                              else: # successfully re-authenticated
                                 continue # continue with same idx
                           else:
                              if project_file_flag:
                                 self.rememberFile(self.project_json_file, desktop_hash)
                              else:
                                 self.rememberFile(filename, desktop_hash)
                              self.setUploadSessionIdAndCount(variant, self.uploads) # start recording session id along with upload count
                        else: # file found; test and only upload again if web file and desktop file differ
                           msg = '{} {}.'.format(qApp.instance().translate('WebProjectUploadDlg', 'File already on server:'), filename)
                           self.response_msg.emit(msg)
                           web_hash = query_response.get('Metadata').get('md5')
                           if web_hash != desktop_hash: # file on website not same as desktop file; old, incomplete or corrupted on server
                              self.response_msg.emit(qApp.instance().translate('WebProjectUploadDlg', 'Differences found, uploading again...'))
                              body = open(filename, 'rb').read()
                              if filename.lower().endswith('.json'):
                                 with open(filename, 'r', encoding='utf-8', newline='\n') as f:
                                    jsn = json.load(f)
                                    _str = json.dumps(jsn, sort_keys=False, indent=4, ensure_ascii=False)
                                    body = self.desktopStrToWeb(_str).encode('utf-8')
                              try:
                                 content_type = "text/plain;charset=utf-8"
                                 upload_response = self.s3_client.put_object(
                                    Body=body,
                                    ContentType=content_type,
                                    Bucket=bucket,
                                    Key=object_name,
                                    Metadata={'md5': desktop_hash}
                                    )
                              except EndpointConnectionError as e:
                                 self.internet_access = False
                                 self.updateProgress(1)
                                 self.abort = True
                                 txt = qApp.instance().translate('WebProjectUploadDlg', 'No Internet connection.')
                                 msg = '<div style="color:red;"><br>{}<br><br>{}</div>'.format(txt, str(e))
                                 self.response_msg.emit(msg)
                                 self.abortUpload()
                                 self.rememberAlreadyUploaded()
                              except ClientError as e:
                                 # don't worry here about reauthentication in event of credential timeout
                                 # that would've been caught already in the last 'ClientError' exception
                                 # no harm in uploading that file again
                                 msg = '<div style="color:red;"> {}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Upload failed:'), str(e.response['ResponseMetadata']['HTTPStatusCode']))
                                 self.response_msg.emit(msg)
                              else:
                                 self.setUploadSessionIdAndCount(variant, self.uploads)
                                 if project_file_flag:
                                    self.rememberFile(self.project_json_file, desktop_hash)
                                 else:
                                    self.rememberFile(filename, desktop_hash)
                           elif filename.count('/_signs/') and filename.endswith('.json'):
                              if not hasattr(self.sign_count_label, 'count'):
                                 self.sign_count_label.count = 0
                              self.sign_count_label.count += 1
                        self.updateProgress()
                        if _filename:
                           os.remove(_filename)

                        idx += 1
                  ################################################################################
                  ################################################################################

                  # if successful, upload the control files
                  if not self.abort and (files_to_delete or remaining_files_to_upload):
                     desktop_project_path = '/' + os.path.basename(self.project_json_file)
                     web_project_path = '/' + self.project_id + '.json'
                     if desktop_project_path != web_project_path:
                        self.webifyList(changed_files_to_upload, desktop_project_path, web_project_path)
                     o = {}
                     o['projectId'] = self.project_id
                     o['userId'] = userId
                     o['uploadTime'] = datetime.now(timezone.utc).isoformat()
                     o['UILang'] = qApp.instance().pm.getCurrentUILang()
                     o['newFiles'] = new_files_to_upload
                     o['changedFiles'] = changed_files_to_upload
                     o['deletedFiles'] = files_to_delete
                     _str = json.dumps(o, sort_keys=False, indent=4, ensure_ascii=False)
                     upload_changes_file = self.project_dir + '/' + self.project_id + '.changes'
                     with open(upload_changes_file, 'wb') as f:
                        f.write(self.desktopStrToWeb(_str).encode('utf-8'))

                     fail = False
                     def uploadControlFile(filename, bucket, fail):
                        object_name = variant.s3_folder + os.path.basename(filename)
                        content = open(filename, 'r', encoding='utf-8').read()
                        if filename == desktop_inventory:
                           content = self.desktopStrToWeb(content, True)
                        body = content.encode('utf-8')
                        try:
                           msg = '{} {}'.format(qApp.instance().translate('WebProjectUploadDlg', 'Uploading control file:'), filename)
                           self.response_msg.emit(msg)
                           content_type = "text/plain;charset=utf-8"
                           upload_response = self.s3_client.put_object(
                              Body=body,
                              ContentType=content_type,
                              Bucket=bucket,
                              Key=object_name
                              )
                        except EndpointConnectionError as e:
                           self.internet_access = False
                           self.updateProgress(1)
                           self.abort = True
                           txt = qApp.instance().translate('WebProjectUploadDlg', 'No Internet connection.')
                           msg = '<div style="color:red;"><br>{}<br><br>{}</div>'.format(txt, str(e))
                           self.response_msg.emit(msg)
                           self.abortUpload()
                           self.rememberAlreadyUploaded()
                        except ClientError as e:
                           ## credentials timeouted after 1Hr
                           self.s3_client, bucket = self.reauthenticate(variant)
                           retry = 0
                           while (not self.s3_client or not bucket) or retry == 10:
                              retry += 1
                              self.thread().msleep(500)
                              qApp.processEvents()
                           if not self.s3_client or bucket:
                              msg = '<div style="color:red;"> {}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Upload failed:'), str(e.response['ResponseMetadata']['HTTPStatusCode']))
                              self.response_msg.emit(msg)
                              fail = True
                           else: # successfully re-authenticated
                              uploadControlFile(filename, bucket, fail)

                        self.updateProgress()
                     uploadControlFile(desktop_inventory, bucket, fail)
                     uploadControlFile(upload_changes_file, bucket, fail)
                     if not fail:
                        self._markCompleteUploads(variant)
                        msg = '<div style="color:blue;"><br>{}<br>{} {}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'All files have now been uploaded.'), qApp.instance().translate('WebProjectUploadDlg', 'When your website is ready to view, you will get an email at:'), userEmail)
                        self.response_msg.emit(msg)
                        self.clearSessionId(variant.username, variant.public_or_private)
                        self.forgetAlreadyUploaded()
                     else:
                        self.rememberAlreadyUploaded()
                  elif not (remaining_files_to_upload or files_to_delete):
                     msg = qApp.instance().translate('WebProjectUploadDlg', 'Nothing to upload.')
                     self.response_msg.emit(msg)
                     self._markCompleteUploads(variant)
                     self.unlockDictionary(variant)
                     self.updateProgress()
                     self.forgetAlreadyUploaded()
      return _return()

   def getSignIdFromPath(self, pth):
        _id = None
        basename = os.path.basename(pth)
        _id, ext = os.path.splitext(basename)
        return _id

   def getSignDisplayText(self, sign_id, project):
        # string together all glosses from sense list
        display_text = ''
        sign = project.getSign(sign_id)
        if sign:
            senses = sign.senses
            if senses:
                gloss_texts = senses[0].gloss_texts
                gts = [t for t in gloss_texts if t.lang_id == qApp.instance().pm.search_lang_id]
                if gts:
                    gt = gts[0]
                    display_text = gt.text
                if len(senses) > 1:
                    for sense in senses[1:]:
                        gloss_texts = sense.gloss_texts
                        gts = [t for t in gloss_texts if t.lang_id == qApp.instance().pm.search_lang_id]
                        if gts:
                            gt = gts[0]
                            display_text = f'{display_text}  |  {gt.text}'
        return display_text

   def _markCompleteUploads(self, variant):
      if variant.public_or_private == 'public':
         self.public_upload_complete = True
         if len(self.variants) == 1:
            self.private_upload_complete = True
      else:
         self.private_upload_complete = True
         if len(self.variants) == 1:
            self.public_upload_complete = True

   def getSession(self, _type):
      backend = self.backend_field.text()
      settings = qApp.instance().getSettings()
      key = 'lastUploadSessionId/{}/{}/{}/{}'.format(self.project_id, backend, self.username, _type)
      value = settings.value(key, '')
      if value:
         return value
      return ''

   def getPublicSessionId(self):
      session = self.getSession('public')
      if session:
         return session.split('_')[0]
      return ''

   def getPrivateSessionId(self):
      session = self.getSession('private')
      if session:
         return session.split('_')[0]
      return ''

   def getPublicSessionCount(self):
      session = self.getSession('public')
      if session:
         return int(session.split('_')[1])
      return 0

   def getPrivateSessionCount(self):
      session = self.getSession('private')
      if session:
         return int(session.split('_')[1])
      return 0

   def doUpload(self, variant, response_data):
      desktop_inventory = ''
      web_inventory = ''
      changes_file = ''
      upload_changes_file = ''
      if variant:
         self.setUploadSessionIdAndCount(variant, 0)
         desktop_inventory, web_inventory, changes_file, upload_changes_file = self.uploadVariant(variant, response_data)
      else: # upload cancelled
         msg = qApp.instance().translate('WebProjectUploadDlg', 'Upload cancelled')
         self.response_msg.emit(msg)
         self.onUploadCancelled()

      #cleanup after upload
      self.upload_complete.emit()
      for _file in [desktop_inventory, web_inventory, changes_file, upload_changes_file]:
         if _file and os.path.exists(_file):
            os.remove(_file)

      return ''

   def onUploadCancelled(self):
      print('variants:', self.variants)
      if self.internet_access:
         for v in self.variants:
            print('selected:', v.selected, v.upload_count)
            if v.selected and (not v.upload_count or not self.keepWebFiles(qApp.instance().translate('WebProjectUploadDlg', 'Cancel Upload'))):
               self.unlockDictionary(v)
            elif not v.selected:
               try:
                  self.unlockDictionary(v)
               except:
                  pass
      qApp.restoreOverrideCursor()

   def setUploadSessionIdAndCount(self, variant, upload_count):
      if not variant.locked and upload_count >= variant.upload_count:
         session_id = '{}_{}'.format(variant.session_id, upload_count)
         backend = self.backend_field.text()
         settings = qApp.instance().getSettings()
         key = 'lastUploadSessionId/{}/{}/{}/{}'.format(self.project_id, backend, self.username, variant.public_or_private)
         settings.setValue(key, session_id)
         settings.sync()
         variant.upload_count = upload_count

   def clearSessionId(self, username, public_or_private):
      backend = self.backend_field.text()
      settings = qApp.instance().getSettings()
      key = 'lastUploadSessionId/{}/{}/{}/{}'.format(self.project_id, backend, username, public_or_private)
      settings.remove(key)
      settings.sync()

   def webifyList(self, _list, desktop_path, web_path):
      for l in _list:
         if l.get('path') == desktop_path:
            l['path'] = web_path
            break #should only be one change and probably first in list

   def webStrToDesktop(self, text, replace_proj_name=False):
      """Convert strings from WebSooSL to desktop format"""
      # Web does not use an initial '_' in its project directory names.
      # Desktop does.
      text = text.replace('/signs/', '/_signs/')
      text = text.replace('/sentences/', '/_sentences/')
      text = text.replace('/extra_videos/', '/_extra_videos/')
      text = text.replace('/extra_pictures/', '/_extra_pictures/')
      if replace_proj_name:
         dsk_path = os.path.basename(self.project_json_file)
         web_path = self.project_id + '.json'
         text = text.replace(web_path, dsk_path)
      return text

   def desktopStrToWeb(self, text, replace_proj_name=False):
      """Convert strings from DesktopSooSL to web format"""
      # Desktop uses an initial '_' in its project directory names to guard against an old, pre 0.9.1 bug
      # Web directories do not want these, so remove them before uploading
      text = text.replace('/_signs/', '/signs/')
      text = text.replace('/_sentences/', '/sentences/')
      text = text.replace('/_extra_videos/', '/extra_videos/')
      text = text.replace('/_extra_pictures/', '/extra_pictures/')
      if replace_proj_name:
         dsk_path = os.path.basename(self.project_json_file)
         web_path = self.project_id + '.json'
         text = text.replace(dsk_path, web_path)
      return text

   def onShowSettings(self, _bool):
      self.settings_widget.setVisible(_bool)

   def showEvent(self, evt):
      super(WebProjectUploadDlg, self).showEvent(evt)
      if not self.backend_field.text():
         self.backend_field.setFocus(True)
      elif not self.username_field.text():
         self.username_field.setFocus(True)
      elif not self.password_field.text():
         self.password_field.setFocus(True)
      else:
         self.upload_btn.setFocus(True)
         self.settings_btn.setChecked(False)
      self.showProjectInfo()

   def showProjectInfo(self):
      _version = self.project_version_id
      if not _version:
         _version = '--'
      if self.project_last_save_datetime:
         _datetime = qApp.instance().pm.getCurrentDateTimeStr(iso_str=self.project_last_save_datetime)
      else:
         _datetime = '--'
      txt = """<table>
                  <tr>
                      <td>{}:</td>
                      <td>&nbsp;&nbsp;&nbsp;<b>{}</b></td>
                  </tr>
                  <tr>
                      <td>{}:</td>
                      <td>&nbsp;&nbsp;&nbsp;{}</td>
                  </tr>
                  <tr>
                      <td>{}:</td>
                      <td>&nbsp;&nbsp;&nbsp;{}</td>
                  </tr>
                  <tr>
                      <td>{}:</td>
                      <td>&nbsp;&nbsp;&nbsp;{}</td>
                  </tr>
               </table>""".format(qApp.instance().translate('WebProjectUploadDlg', 'Title'), self.project_name, qApp.instance().translate('WebProjectUploadDlg', 'Filename'), self.project_json_file, qApp.instance().translate('WebProjectUploadDlg', 'Version'), _version, qApp.instance().translate('WebProjectUploadDlg', 'Modified'), _datetime)
      self.response_field.append(txt)

   def onShowHideClicked(self):
      box = self.sender()
      if box.isChecked():
         self.password_field.setEchoMode(QLineEdit.Normal)
         box.setToolTip(qApp.instance().translate('WebProjectUploadDlg', "Hide password"))
      else:
         self.password_field.setEchoMode(QLineEdit.Password)
         box.setToolTip(qApp.instance().translate('WebProjectUploadDlg', "Show password"))

   def onRememberCredentials(self):
      box = self.sender()
      if box.isChecked():
         self.remember_credentials = 1
      else:
         self.remember_credentials = 0

   def onUsernameChanged(self, username_txt):
      if username_txt:
         try:
            qApp.processEvents()
            psswrd = keyring.get_password('websoosl', username_txt)
            qApp.processEvents()
            self.password_field.setText(psswrd)
         except:
            pass
      else:
         self.password_field.clear()

   def rememberWebCredentials(self):
      settings = qApp.instance().getSettings()
      settings.setValue('rememberWebCredentials', self.remember_credentials)
      if not int(self.remember_credentials):
         try:
            keyring.delete_password('websoosl', self.username)
         except:
            pass
         settings.setValue('lastWebUsername', '')
      else:
         try:
            keyring.set_password('websoosl', self.username, self.password)
         except:
            pass
         else:
            settings.setValue('lastWebUsername', self.username)
            backend = self.backend_field.text()
            settings.setValue('lastWebBackend', backend)
      settings.sync()

   def sizeHint(self):
      _size = QSize(400, 500)
      _pos = self.parent().pos()
      screen = qApp.screenAt(_pos)
      if screen:
         s = screen.availableSize()
         w = s.width() * 0.4
         h = s.height() * 0.5
         _size = QSize(int(w), int(h))
      return _size

   def onDone(self):
      _bool = True
      if self.abort:
         _bool = False
      self.cancel_btn.setDisabled(_bool)
      self.ok_btn.setEnabled(_bool)
      self.upload_btn.setDisabled(True)
      qApp.restoreOverrideCursor()
      self.uploading = False
      self.rememberWebCredentials()

   def reject(self):
      self.abortUpload()
      self.onUploadCancelled()
      super(WebProjectUploadDlg, self).reject()

   def showResponseMessage(self, txt):
      if txt == 'wrong_username_or_password':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'You have entered a wrong username or password.'))
      elif txt == 'not_authorized':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'You are not authorized to update this dictionary.'))
      elif txt == 'dictionary_not_found':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'This dictionary cannot be found.') + '\n' +
             qApp.instance().translate('WebProjectUploadDlg', 'Please contact us if you want us to host your dictionary.'))
      elif txt == 'something_went_wrong':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Something went wrong:'))
      elif txt == 'update_in_progress':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Update still in progress.'))
      elif txt == 'inventory_not_found':
         t1 = qApp.instance().translate('WebProjectUploadDlg', 'Inventory not found.')
         t2 = qApp.instance().translate('WebProjectUploadDlg', 'Please contact us through our website at: <a href="https://soosl.net/contact.html">https://soosl.net/contact.html</a>')
         txt = '<p style="color:red;">{}<br>{}</p>'.format(t1, t2)
      # elif txt == 'Missing Authentication Token':
      #    txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Missing authentication token.'))
      elif txt == 'connection_error':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Connection error.'))
      elif txt == 'request_timed_out':
         txt = '<div style="color:red;">{}</div>'.format(qApp.instance().translate('WebProjectUploadDlg', 'Connection request timed out.'))
      self.response_field.append(txt)
      scroll = self.response_field.verticalScrollBar()
      scroll.setValue(scroll.maximum())

   def getLastUploadSessionId(self):
      public_id = self.getPublicSessionId()
      public_count = self.getPublicSessionCount()
      private_id = self.getPrivateSessionId()
      private_count = self.getPrivateSessionCount()
      upload_session_ids = []
      if public_count:
         return public_id
      elif private_count:
         return private_id
      else:
         return ''

   def clearInvalidId(self, session_id):
      session_ids = [v.session_id for v in self.variants]
      # case where stored session_id has expired
      if session_id and session_ids and session_id not in session_ids:
         public_or_private = None
         if session_id == self.getPublicSessionId():
            public_or_private = 'public'
         elif session_id == self.getPrivateSessionId():
            public_or_private = 'private'
         if public_or_private:
            self.clearSessionId(self.username, public_or_private)
         return True
      return False

   def onUpload(self, reentry=False):
      if not reentry:
         qApp.setOverrideCursor(Qt.BusyCursor)
         qApp.processEvents()
         self.response_field.clear()
         self.progress_bar.hide()
         self.ok_btn.setDisabled(True)
         self.cancel_btn.setDisabled(False)
         self.upload_btn.setDisabled(True)
         self.showResponseMessage(qApp.instance().translate('WebProjectUploadDlg', 'Connecting...'))
         qApp.processEvents()
         self.uploading = True
      session_id = self.processStoredIds()
      self.authenticate(session_id)

   def handleAuthenticationResponse(self, response, session_id):
      if (response.status_code == 200):
         response_data = json.loads(response.content)
         project_variants = response_data.get('projectVariants', [])
         self.variants = [ProjectVariant(v, self) for v in project_variants]
         if self.clearInvalidId(session_id):
            self.onUpload(True) # reenter method with no session_id
         else:
            for v in self.variants:
               self.setUploadSessionIdAndCount(v, 0)
            try:
               selected_variant, unselected_variant = self.selectVariant(self.variants)
            except:
               self.upload_btn.setEnabled(True)
            else:
               if unselected_variant:
                  self.unlockDictionary(unselected_variant)
                  self.variants.remove(unselected_variant)
               if selected_variant:
                  self.doUpload(selected_variant, response_data)
               else:
                  self.upload_btn.setEnabled(True)
      else:
         self.handleResponseErrors(response)

   @property
   def username(self):
      return self.username_field.text()

   @property
   def password(self):
      return self.password_field.text()

   @property
   def project_id(self):
      return qApp.instance().pm.project.id

   @property
   def project_dir(self):
      return qApp.instance().pm.project.project_dir

   @property
   def project_json_file(self):
      return qApp.instance().pm.project.json_file

   @property
   def project_version_id(self):
      return qApp.instance().pm.project.version_id

   @property
   def project_last_save_datetime(self):
      return qApp.instance().pm.project.last_save_datetime

   @property
   def project_name(self):
      return qApp.instance().pm.project.name

   @property
   def project_signs(self):
      return qApp.instance().pm.project.signs


# allows me to start soosl by running this module
if __name__ == '__main__':
   from mainwindow import main
   main()
