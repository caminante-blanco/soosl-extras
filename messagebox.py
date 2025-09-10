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
import urllib.request
import urllib.parse as parse
from urllib.request import Request, urlopen
import ssl
import json
import copy

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSlot

from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap

from PyQt5.QtWidgets import qApp, QProgressDialog, QGridLayout, QDialogButtonBox,\
    QScrollArea
from PyQt5.QtWidgets import QDialog, QMessageBox, QLayout
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QErrorMessage

class MessageBox(QDialog):

    def __init__(self, _type=None, parent=None):
        #_type = 'error' | 'feedback' | 'report'
        super(MessageBox, self).__init__(parent)
        self._type = _type
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

    def setupGui(self, title, _style, text, btn_text, _icon, website_access):
        self.setWindowTitle(title)
        layout = QGridLayout()
        layout.setSizeConstraint(QLayout.SetFixedSize)
        self.icon_lbl = QLabel()
        self.icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.text_lbl = QLabel()
        self.text_lbl.setStyleSheet(_style)
        self.inform_text_lbl = QLabel()

        layout.addWidget(self.icon_lbl, 0, 0, 1, 2)
        layout.addWidget(self.text_lbl, 0, 1)
        layout.addWidget(self.inform_text_lbl, 1, 1)

        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        #self.text_edit.setMinimumSize(420, 50)
        #self.text_edit.setMaximumSize(500, 100)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

        lbl1 = QLabel('<b>{}</b><br>({})'.format(text, qApp.instance().translate("MessageBox", 'optional')))
        lbl1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        lbl1.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        layout.addWidget(lbl1, 2, 0)
        layout.addWidget(self.text_edit, 2, 1)
        text = "Some untranslated text."

        self.line_edit = QLineEdit()
        self.line_edit.textEdited.connect(self.verifyEmail)
        #self.line_edit.setMinimumWidth(100)
        self.line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        settings = qApp.instance().getSettings()
        self.user_email = settings.value('UserEmail', '')
        if self.user_email:
            self.line_edit.setText(self.user_email)

        email = qApp.instance().translate("MessageBox", 'Your email:')
        opt = qApp.instance().translate("MessageBox", 'optional')
        lbl2 = QLabel('<b>{}</b><br>({})'.format(email, opt))
        lbl2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lbl2.setAlignment(Qt.AlignLeft|Qt.AlignTop)

        layout.addWidget(lbl2, 3, 0)
        layout.addWidget(self.line_edit, 3, 1)

        if hasattr(self, 'error_messages'):
            hlayout = QHBoxLayout()
            hlayout.setSpacing(1)
            hlayout.setContentsMargins(3, 3, 3, 3)

            self.next_btn = QPushButton()
            self.next_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
            self.next_btn.setIcon(QIcon(':/next.png'))
            self.next_btn.clicked.connect(self.setNextMessage)
            self.next_btn.hide()
            self.next_btn.setFlat(True)

            self.error_lbl = QLabel()
            self.error_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
            self.error_lbl.hide()

            hlayout.addWidget(self.next_btn)
            hlayout.addWidget(self.error_lbl)

            layout.addLayout(hlayout, 4, 0)

        send_btn = QPushButton(btn_text)
        if not website_access:
            send_btn.setIcon(QIcon(':/save.png'))
        else:
            send_btn.setIcon(QIcon(_icon))

        text = qApp.instance().translate("MessageBox", 'Show info...')
        info_button = QPushButton(text)
        info_button.clicked.connect(self.onInfoBtnClicked)

        text = qApp.instance().translate("MessageBox", 'Cancel and discard all messages')
        cancel_btn = QPushButton(text)
        cancel_btn.setIcon(QIcon(':/delete16.png'))

        btns = QDialogButtonBox()
        btns.addButton(cancel_btn, QDialogButtonBox.RejectRole)
        btns.addButton(info_button, QDialogButtonBox.ActionRole)
        btns.addButton(send_btn, QDialogButtonBox.AcceptRole)

        btns.accepted.connect(self.onAccepted)
        btns.rejected.connect(self.onRejected)

        if not website_access:
            msg0 = qApp.instance().translate("MessageBox", 'No Internet access or SooSL website unavailable')
            msg1 = qApp.instance().translate("MessageBox", "Choose 'Save' (below) to save your message and try again later")
            msg2 = qApp.instance().translate("MessageBox", "<STRONG>How?</STRONG> Click on the following icons")
            lbl = QLabel("""<p style='color:Red'><b>{}</b></p><p>{}</p>
               <p>{}&nbsp;&nbsp;&nbsp;&nbsp;
               <img src=':/tools.png' align='middle'>&nbsp;&nbsp;
               <img src='{}' align='middle'> ({})</p>""".format(msg0, msg1, msg2, _icon, title), self)

            layout.addWidget(lbl, 4, 1)
            layout.addWidget(btns, 5, 1)
        else:
            layout.addWidget(btns, 4, 1)

        self.detailed_text_lbl = QLabel()
        self.detailed_text_lbl.setHidden(True)
        self.detailed_text_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.detailed_text_lbl.setContentsMargins(3, 3, 3, 3)
        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(QPalette.Base)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setWidget(self.detailed_text_lbl)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setHidden(True)
        self.scroll_area.setMaximumHeight(200)
        layout.addWidget(self.scroll_area, 6, 1, 1, 2)

        self.msg = ''
        if self.user_email and self.verifyEmail(self.user_email):
            self.text_edit.setFocus()

        self.setLayout(layout)

    ##!!@pyqtSlot()
    def onInfoBtnClicked(self):
        btn = self.sender()
        if self.scroll_area.isHidden():
            self.scroll_area.setHidden(False)
            btn.setText(qApp.instance().translate("MessageBox", 'Hide info'))
        else:
            self.scroll_area.setHidden(True)
            btn.setText(qApp.instance().translate("MessageBox", 'Show info...'))

    def setDetailedText(self, msg, errors=[]):
        self.msg = msg
        txt = copy.deepcopy(msg)
        if not errors:
            txt = f"{txt}\n\n{qApp.instance().getUserSystemInfo()}"
        self.detailed_text_lbl.setText(txt)

    def setIconPixmap(self, pxm):
        self.icon_lbl.setPixmap(pxm)

    def setIcon(self, _icon):
        if _icon == QMessageBox.Critical: #red
            pxm = QPixmap(':/error.png')
        else: #yellow
            pxm = QPixmap(':/warning.png')
        self.setIconPixmap(pxm)

    def setText(self, _text):
        self.text_lbl.setText(_text)

    def setInformativeText(self, _text):
        self.inform_text_lbl.setText(_text)

    def setUserText(self, txt):
        self.text_edit.setText(txt)

    def getUserComments(self):
        return self.text_edit.toPlainText()

    ##!!@pyqtSlot()
    def onAccepted(self):
        if self.accept_task == 'send':
            self.sendReport()
        elif self.accept_task == 'save':
            self.saveReport()
        if self.verifyEmail(self.line_edit.text()):
            settings = qApp.instance().getSettings()
            settings.setValue('UserEmail', self.line_edit.text())
            settings.sync()
        self.accept()

    ##!!@pyqtSlot(str)
    def verifyEmail(self, text):
        try:
            atpos = text.index("@")
        except:
            atpos = 0
        try:
            dotpos = text[::-1].index(".") #check for last dot
        except:
            dotpos = 0
        else:
            dotpos = len(text) - dotpos #because it was reversed text
        if (atpos < 1 or
            dotpos < atpos + 2 or
            dotpos + 1 >= len(text)):
            return False
        else:
            return True

    def hideEvent(self, evt):
        qApp.processEvents()
        super(MessageBox, self).hideEvent(evt)

class ErrorMessageBox(MessageBox):
    def __init__(self, _type, parent=None):
        #_type = 'error' | 'report'
        super(ErrorMessageBox, self).__init__(parent)
        self.error_messages = []
        self.internet = True #assume true to start
        self.idx = 0

        _icon = ':/mail_error.png'
        text = qApp.instance().translate("ErrorMessageBox", 'Description:')
        btn_text = 'Save'
        website_access = qApp.instance().checkForAccess()
        self.accept_task = 'save'
        if website_access:
            btn_text = qApp.instance().translate("ErrorMessageBox", 'Send error report')
            self.accept_task = 'send'
        if _type == 'error':
            title = qApp.instance().translate("ErrorMessageBox", "SooSL Error")
            _style = """color:Red"""
        elif _type == 'report':
            title = qApp.instance().translate("ErrorMessageBox", "SooSL Error Report")
            _style = """color:Blue"""

        self.setupGui(title, _style, text, btn_text, _icon, website_access)
        self.setSizeGripEnabled(False)
        #self.text_edit.textChanged.connect(self.onUserCommentsChanged)

    def onAccepted(self):
        self.updateUserComments()
        super(ErrorMessageBox, self).onAccepted()

    def setErrorMessages(self, messages):
        if len(messages) >= 1:
            self.error_messages = messages
            self.message_count = len(self.error_messages)
            if self.message_count > 1:
                self.next_btn.show()
                self.error_lbl.show()
            self.idx = 0
            self.__setMessage(0)

    def __setMessage(self, idx):
        message = self.error_messages[idx]
        self.error_lbl.setText(f'<p>{qApp.instance().translate("ErrorMessageBox", "Errors")}<br>({idx+1} - {self.message_count})</p>')
        self.text_edit.setText(message.get('user_comments', ''))
        dt = f"{message.get('error_message', '')}\n\n{message.get('system_info', '')}"
        self.setDetailedText(dt)

    ##!!@pyqtSlot()
    def setNextMessage(self):
        self.updateUserComments()
        self.idx += 1
        if self.idx == self.message_count:
            self.idx = 0
        self.__setMessage(self.idx)

    def updateUserComments(self):
        if self.error_messages:
            self.error_messages[self.idx]['user_comments'] = self.getUserComments()

    def saveErrors(self):
        if not self.error_messages:
            jsn = {'user_comments': self.getUserComments(),
                   'error_message': self.msg,
                   'system_info': qApp.instance().getUserSystemInfo()
                   }
            self.error_messages.append(jsn)
            qApp.instance().clearCrashReport()
        qApp.instance().logErrorMessages(self.error_messages)

    def setDetailedText(self, msg):
        # following on my own machines???
        if sys.platform.startswith("win"):
            msg = msg.replace("C:\\Users\\Timothy\\workspace\\", "")
        elif sys.platform.startswith("darwin"):
            msg = msg.replace("/Users/timothygrove/Documents/workspace/", "")
        elif sys.platform.startswith("linux"):
            msg = msg.replace("/home/timothy/Desktop/", "")
        super(ErrorMessageBox, self).setDetailedText(msg, self.error_messages)

    def getMessageToSend(self):
        #the complete error report including crash reports should now be contained in the error.log
        #read it from the file and format it for sending
        message = 'ERROR but cannot get message from SooSL!'
        if self.error_messages:
            message = json.dumps(self.error_messages, sort_keys=False, indent=4, ensure_ascii=False)
        else:
            message = qApp.instance().getErrorMsg()
        return message

    def saveReport(self):
        self.updateUserComments()
        self.saveErrors()

    ##!!@pyqtSlot()
    def onSendFinished(self):
        self.send_complete = True

    def timerEvent(self, evt):
        access = qApp.instance().checkForAccess()
        if not access:
            self.internet = False
            _id = evt.timerId()
            self.killTimer(_id)
        else:
            self.internet = True

    def sendReport(self):
        self.send_complete = False
        self.updateUserComments()
        self.saveErrors()
        message = self.getMessageToSend()

        user_email = self.line_edit.text()
        if not self.verifyEmail(user_email):
            user_email = 'contact@soosl.net'
        params = {'user_email': user_email, 'user_message': message}

        settings = qApp.instance().getSettings()
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        top_level_url = settings.value("Website")
        usr = settings.value("Usr")
        psw = settings.value("Psw")
        password_mgr.add_password(None, top_level_url, usr, psw)
        handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        opener = urllib.request.build_opener(handler)
        urllib.request.install_opener(opener)
        qApp.setOverrideCursor(Qt.BusyCursor)
        qApp.instance().pm.showMessage(qApp.instance().translate("ErrorMessageBox", "Sending error report, please wait..."))

        sendprogress = QProgressDialog(self)
        if not int(settings.value('Testing', 0)): sendprogress.setWindowModality(Qt.WindowModal)##NOTE: allows crash testing while testing
        sendprogress.setWindowTitle(' ')
        sendprogress.setLabelText("<p style='color:blue'>{}</p>".format(qApp.instance().translate("ErrorMessageBox", "Sending error report, please wait...")))
        self.progress_cancel_btn = QPushButton(QIcon(':/close.png'), qApp.instance().translate("ErrorMessageBox", "Cancel"))
        sendprogress.setCancelButton(self.progress_cancel_btn)
        sendprogress.setMinimum(0)
        sendprogress.setMaximum(0)
        sendprogress.setAutoReset(True)

        self.send_thread = SendReportThread(self, "https://soosl.net/error_report.php", params)
        # print('TESTING ONLY')
        # self.send_thread = SendReportThread(self, "https://soosl.net/error_test.php", params)
        self.send_thread.finished.connect(self.onSendFinished)
        sendprogress.canceled.connect(self.send_thread.cancel)

        self.send_thread.start()
        sent_flag = False
        while True:
            if not self.send_complete:
                sendprogress.forceShow()
                qApp.processEvents()
            else:
                sent_flag = self.send_thread.success
                qApp.processEvents()
                break

        mw = qApp.instance().getMainWindow()
        if not sent_flag:
            self.setHidden(True)
            qApp.restoreOverrideCursor()
            errorMsg = QErrorMessage(mw)
            errorMsg.setMinimumSize(500, 200)
            #errorMsg.setResizable(True)
            if sendprogress.wasCanceled():
                title = qApp.instance().translate("ErrorMessageBox", 'Sending Cancelled')
                errorMsg.setWindowTitle(title)
            else:
                title = qApp.instance().translate("ErrorMessageBox", 'No Internet connection or SooSL website unavailable')
                errorMsg.setWindowTitle('No Internet')

            msg1 = qApp.instance().translate("ErrorMessageBox", 'Your message has been saved - Try again when you are connected to the Internet')
            msg2 = qApp.instance().translate("ErrorMessageBox", "Click on the blue tool icon")
            msg3 = qApp.instance().translate("ErrorMessageBox", "Choose 'Send error report'")
            errorMsg.showMessage("<h3 style='color:red'>{}</h3> \
                <p>{}<br><br> \
                {} <img src=':/tools.png' align='middle'><br> \
                {} <img src=':/mail_error.png' align='middle'></p>".format(title, msg1, msg2, msg3))
            i=0
            checkbox = None
            while True:
                try:
                    item = errorMsg.layout().itemAt(i)
                except:
                    break
                else:
                    if item:
                        if isinstance(item.widget(), QCheckBox):
                            checkbox = item.widget()
                            checkbox.hide()
                        i += 1
                    else:
                        break
            sendprogress.close()
            errorMsg.exec_()
            qApp.instance().pm.showMessage('')
            return -1 # no internet connection available
        else:
            sendprogress.close()
            try:
                os.remove(qApp.instance().error_log)
            except:
                qApp.instance().resetErrorLog()
            qApp.restoreOverrideCursor()
            QMessageBox.information(self, ' ', "<center><h3 style='color:blue'>{}</h3></center>".format(qApp.instance().translate("ErrorMessageBox", 'Send successful!')))

        qApp.instance().pm.showMessage('')
        try:
            qApp.instance().clearCrashReport() #crash report may be cleared because it will have been sent or added to the error log.
        except:
            pass
        try:
            self.close()
        except:
            pass #already closed

    ##!!@pyqtSlot()
    def onRejected(self):
        try:
            qApp.instance().resetErrorLog()
        except:
            pass
        try:
            qApp.instance().clearCrashReport()
        except:
            pass
        super(ErrorMessageBox, self).reject()

class FeedbackBox(MessageBox):
    def __init__(self, parent=None):
        super(FeedbackBox, self).__init__(parent)

        self.internet = True #assume true to start
        self.send_thread = SendReportThread(self)
        self.send_thread.finished.connect(self.onSendFinished)

        title = qApp.instance().translate("FeedbackBox", "SooSL feedback")
        _style = """color:Blue"""
        text = qApp.instance().translate("FeedbackBox", 'Feedback:')
        _icon = ':/mail.png'
        btn_text = qApp.instance().translate("FeedbackBox", 'Save')
        website_access = qApp.instance().checkForAccess()
        self.accept_task = 'save'
        if website_access:
            btn_text = qApp.instance().translate("FeedbackBox", 'Send feedback')
            self.accept_task = 'send'

        self.setupGui(title, _style, text, btn_text, _icon, website_access)
        self.setSizeGripEnabled(False)

    def getFeedbackToSend(self):
        feedback = qApp.instance().getFeedbackMsg()
        return feedback

    def saveReport(self):
        qApp.instance().saveFeedback(self.text_edit.toPlainText())

    ##!!@pyqtSlot()
    def onSendFinished(self):
        self.send_complete = True

    def sendReport(self):
        self.send_complete = False
        qApp.instance().saveFeedback(self.text_edit.toPlainText())
        message = self.getFeedbackToSend()

        user_email = self.line_edit.text()
        if not self.verifyEmail(user_email):
            user_email = 'contact@soosl.net'

        params = {'user_email': user_email, 'user_message': message}

#         settings = qApp.instance().getSettings()
#         password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
#         top_level_url = settings.value("Website")
#         usr = settings.value("Usr")
#         psw = settings.value("Psw")
#         password_mgr.add_password(None, top_level_url, usr, psw)
#         handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
#         opener = urllib.request.build_opener(handler)
#         urllib.request.install_opener(opener)
        qApp.setOverrideCursor(Qt.BusyCursor)

        sendprogress = QProgressDialog(self)
        sendprogress.setLabelText("<p style='color:blue'>{}</p>".format(qApp.instance().translate("FeedbackBox", 'Sending feedback, please wait...')))
        self.progress_cancel_btn = QPushButton(QIcon(':/close.png'), qApp.instance().translate("FeedbackBox", "Cancel"))
        sendprogress.setCancelButton(self.progress_cancel_btn)
        sendprogress.setMinimum(0)
        sendprogress.setMaximum(0)
        sendprogress.setAutoReset(True)
        self.send_thread.setUrl("https://soosl.net/feedback.php")
        self.send_thread.setParams(params)
        sendprogress.canceled.connect(self.send_thread.cancel)

        self.send_thread.start()

        sent_flag = False
        while True:
            if not self.send_complete:
                sendprogress.forceShow()
                qApp.processEvents()
            else:
                sent_flag = self.send_thread.success
                qApp.processEvents()
                break

        if not sent_flag:
            self.setHidden(True)
            qApp.restoreOverrideCursor()
            mw = qApp.instance().getMainWindow()
            errorMsg = QErrorMessage(mw)
            errorMsg.setWindowTitle(qApp.instance().translate("FeedbackBox", 'No Internet'))
            errorMsg.setMinimumSize(500, 200)
            if sendprogress.wasCanceled():
                title = qApp.instance().translate("FeedbackBox", 'Sending Cancelled')
                errorMsg.setWindowTitle(title)
            else:
                title = qApp.instance().translate("FeedbackBox", 'No Internet Connection or SooSL Website Unavailable')
                errorMsg.setWindowTitle(qApp.instance().translate("FeedbackBox", 'No Internet'))

            msg1 = qApp.instance().translate("FeedbackBox", 'Your message has been saved - Try again when you are connected to the Internet')
            msg2 = qApp.instance().translate("FeedbackBox", "Click on the blue tool icon")
            msg3 = qApp.instance().translate("FeedbackBox", "Choose 'Send feedback'")
            errorMsg.showMessage("<h3 style='color:red'>{}</h3> \
                <p>{}<br><br> \
                {} <img src=':/tools.png' align='middle'><br> \
                {} <img src=':/mail.png' align='middle'></p>".format(title, msg1, msg2, msg3))
            i=0
            checkbox = None
            while True:
                try:
                    item = errorMsg.layout().itemAt(i)
                except:
                    break
                else:
                    if item:
                        if isinstance(item.widget(), QCheckBox):
                            checkbox = item.widget()
                            checkbox.hide()
                        i += 1
                    else:
                        break

            sendprogress.close()
            errorMsg.exec_()
            return -1 # no internet connection available
        else:
            sendprogress.close()
            qApp.instance().removeFeedback()
            qApp.restoreOverrideCursor()
            QMessageBox.information(self, ' ', "<center><h3 style='color:blue'>{}</h3></center>".format(qApp.instance().translate("FeedbackBox", 'Send successful!')))
        try:
            self.close()
        except:
            pass #already closed

    def onRejected(self):
        qApp.instance().removeFeedback()
        super(FeedbackBox, self).reject()

    def timerEvent(self, evt):
        access = qApp.instance().checkForAccess()
        if not access:
            self.internet = False
            _id = evt.timerId()
            self.killTimer(_id)
        else:
            self.internet = True

class SendReportThread(QThread):

    def __init__(self, parent=None, url=None, params=None):
        super(SendReportThread, self).__init__(parent)

        self.url = url
        self.params = params
        self.completed = False
        self.success = False
        self.canceled = False

    def setUrl(self, url):
        self.url = url

    def setParams(self, params):
        self.params = params

    ##!!@pyqtSlot()
    def cancel(self):
        self.completed = True
        self.canceled = True
        self.terminate()

    def run(self):
        #user_message = self.params.get('user_message')
        #MAX_MESSAGE_SIZE = 20000 #JUST FOR SAFETY TO PREVENT SOMEONE THROWING A WHOLE BOOK AT US!
        MAX_LENGTH = 2000
        HALF_MAX = 1000
        message = self.params.get('user_message', 'no message')
        # if len(message) > MAX_LENGTH:
        #     part1 = message[:HALF_MAX]
        #     part2 = message[(len(message) - HALF_MAX):]
        #     message = part1 + '\n\n[.....]\n\n' + part2
        # ## BUG:
        # ## Just restrict message size for now; trying to send multiple messages causes error
        # ## LARGE MESSAGES don't send and trigger 'No Internet' warning -not helpful!!!

        self.completed = False
        self.success = False
        self.params['user_message'] = message
        self.params = parse.urlencode(self.params)
        self.params = parse.unquote_to_bytes(self.params)

        try:
            urlopen(Request(self.url, headers={'User-Agent': 'Mozilla/5.0'}), self.params, 40)
        except:
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                urlopen(Request(self.url, headers={'User-Agent': 'Mozilla/5.0'}), self.params, 40)
            except:
                self.internet = False
                self.success = False
        else:
            self.success = True

        self.completed = True
        return

    def __del__(self):
        if not self.completed:
            try:
                self.wait()
            except:
                pass

# allows me to start soosl by running this module
if __name__ == '__main__':
    from mainwindow import main
    main()
