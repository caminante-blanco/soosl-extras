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
import pyuca
import sys

__version__ = "0.9.4"
__build__ = "250802" #ymmdd

""" Main Window for the SooSL program """

import os
import subprocess
#import chardet
import io
import json
import copy
import webbrowser
import re
import psutil
from pprint import pprint

if sys.platform.startswith('win'):
    import six
    import packaging
    import packaging.version
    import packaging.specifiers
    import packaging.requirements
    import win32api
    from winreg import *
    from ctypes import windll
    user32 = windll.user32
elif sys.platform.startswith('darwin'):
    from Cocoa import NSTextInputContext
    from Cocoa import NSHelpManager
    from Cocoa import NSBundle
    from Cocoa import CFBundleGetMainBundle
    from Cocoa import CFBundleGetValueForInfoDictionaryKey
elif sys.platform.startswith('linux'):
    import linux_keyboard

import platform
import shutil
import glob
from zipfile import ZipFile
import tempfile
import ssl
import urllib.parse as parse
from urllib.request import Request, urlopen
from pathlib import Path

import time
from datetime import datetime
import traceback
import faulthandler
#from hanging_threads import start_monitoring

if sys.platform.startswith("win"):
	from win32event import CreateMutex

from PyQt5.QtCore import qInstallMessageHandler
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QByteArray, QRect
from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty
from PyQt5.QtCore import QSettings
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QUrl
from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import QTranslator
from PyQt5.QtCore import QPoint

from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QDesktopServices

from PyQt5.QtWidgets import QDialog, QCheckBox, QFileIconProvider, QComboBox,\
    QHBoxLayout, QDockWidget, QListWidget, QGridLayout
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QErrorMessage
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QRadioButton

from project_manager import ProjectManager as PM
from messagebox import ErrorMessageBox
from messagebox import FeedbackBox

import qrc_resources #NOTE: ONLY NEED TO IMPORT ONCE HERE

from finder_list import FinderList
from video_widget_vlc import Player
from location_widget import LocationView

from extra_media_selector import ExtraMediaSelector
from transcode_settings_widget import TranscodeSettingsWidget
from search_dialog import SearchDlg

from startup_widget import StartupWidget
from new_project_dlg import NewProjectDlg
from new_project_dlg import EditWrittenLanguageSettingsDlg
from new_project_dlg import EditDialectsDlg
from gram_cat_dlg import EditGramCatDlg

from project_file_dialogs import SooSLFileDialog
from project_file_dialogs import ExportProjectDlg

from dialect_dlg import DialectDlg
from edit_project_info_dlg import EditProjectInfoDlg
from save_changes_dlg import SaveChangesDlg
from update_dlg import UpdateDlg
from progress_dlg import ProgressDlg
from existing_media_dlg import ExistingMediaDlg

from components.component_drop_widget import ComponentDropWidget, ClearParametersButton
from components.component_widget import ComponentWidget
from info_page import InfoPage
from soosl_info import SooSLInfoPage
from media_wrappers import VideoWrapper as Video
from media_wrappers import PictureWrapper as Picture
from about_soosl_dlg import AboutSooSLDlg

from project import Project
from project_merger import MergeDialog, ReconcileChangesDialog#, ReconcileProjectChangesDialog

ARCHIVE_EXT = "zoozl"
DB_EXT = "json"

class MainWindow(QMainWindow):
    edit_enable = pyqtSignal()
    edit_disable = pyqtSignal()
    project_open = pyqtSignal(bool)
    compview_order_change = pyqtSignal()
    filter_dialects = pyqtSignal(list)
    delete_sign = pyqtSignal(bool)
    photo_help_changed = pyqtSignal(bool)
    mw_size_change = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        if sys.platform == 'darwin':
            ## NOTE: App was freezing on Max/Min before I set these flags explicitly
            self.setWindowFlags(Qt.Window|Qt.WindowMinMaxButtonsHint|Qt.WindowCloseButtonHint)

        if hasattr(self, 'closing') and self.closing:
            return

        self.last_sign = None
        self.editing = False
        self.acquired_full_project_lock = False
        self.acquired_project_lock = False

        self.leave_edit_flag = False
        self.save_complete = True
        self.current_video_size = QSize()
        self.showLeftWidget = False
        self.dialect_filter = []
        self.lang_id = 1

        self.progress_dlg = None
        self.finder_widget = QWidget()
        self.componentInfoWidget = QWidget()

        self.createActions()
        self.initialActions()
        self.createToolbars()
        self.createStatusbar()

        if sys.platform.startswith("darwin"):
            self.setUnifiedTitleAndToolBarOnMac(False)

        #qApp.instance().logStartup('setting up file dialogs')
        self.setupFileDialogs()

        self.splitterMain = QSplitter(self) #main splitter
        self.splitterMain.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitterMain.setOpaqueResize(True)
        self.setCentralWidget(self.splitterMain)

        #qApp.instance().logStartup('setting up gloss list')
        self.finder_list = FinderList()
        self.finder_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        #qApp.instance().logStartup('setting up video player')
        self.player = Player(self)
        self.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        #qApp.instance().logStartup('setting up extra media player')
        self.exMediaWidget = Player(False, self)
        self.exMediaWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.exMediaSelector = ExtraMediaSelector(self)
        self.exMediaSelector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.exMediaSelector.loadMediaFile.connect(self.exMediaWidget.onLoadMediaFile)
        self.exMediaSelector.deletedOverlay.connect(self.exMediaWidget.setDeletedOverlay)
        exMediaPlayer = QWidget(self)
        exMediaPlayer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        exMediaPlayer.setMinimumHeight(20)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.exMediaWidget)
        layout.addWidget(self.exMediaSelector)
        exMediaPlayer.setLayout(layout)
        layout.setStretchFactor(self.player, 1)

        self.locationWidget = LocationView()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.finder_toolbar)
        layout.addWidget(self.finder_list)
        self.finder_widget.setLayout(layout)

        #create the widget which holds the player widgets in a vertical splitter
        self.splitterMediaPlayers = QSplitter(Qt.Vertical, self)
        self.splitterMediaPlayers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitterMediaPlayers.setOpaqueResize(True)
        self.splitterMediaPlayers.addWidget(self.player)
        self.splitterMediaPlayers.addWidget(exMediaPlayer)

        #qApp.instance().logStartup('setting up sign parameter widget')
        handshape_actions = [self.compViewOrderChangeAction]
        self.componentWidget = ComponentWidget(handshape_actions)
        self.componentWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.componentWidget.setHidden(True)

        #qApp.instance().logStartup('setting up sign info page')
        self.infoPage = InfoPage()
        self.infoPage.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scrollArea = QScrollArea()
        self.scrollArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scrollArea.setBackgroundRole(QPalette.Base)
        self.scrollArea.setWidget(self.infoPage)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFocusPolicy(Qt.NoFocus)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.compInfoStack = QStackedWidget()
        self.componentWidget.addLocationsPage(self.locationWidget)
        self.componentWidget.setCurrentWidget(self.locationWidget)
        self.componentWidget.tabBar().setVisible(False)

        self.compInfoStack.addWidget(self.componentWidget)
        self.compInfoStack.addWidget(self.scrollArea)

        self.componentsList = ComponentDropWidget(self)
        self.locationWidget.scene.item_selected.connect(self.componentsList.onAddLocationItem)
        self.componentsList.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.componentsList.setWrapping(True)
        self.componentsList.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.componentsList.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.componentsList.setDragDropMode(QListWidget.DragOnly)
        self.componentsList.setSelectionMode(QListWidget.SingleSelection)
        self.componentsList.setStyleSheet("""border-style:hidden""")
        self.clearParamBtn = ClearParametersButton(self.componentsList, self)
        self.clearParamBtn.setIcon(QIcon(':/trash20.png'))
        self.clearParamBtn.setToolTip(qApp.instance().translate('MainWindow', 'Click to remove all indexing parameters, or \
            \nDrag and drop a single parameter onto this icon to remove it.\
            \n"Right-click" on a parameter also removes it.'))

        vlayout = QVBoxLayout()
        vlayout.setContentsMargins(3, 3, 3, 3)
        vlayout.setSpacing(7)
        vlayout.addWidget(self.componentInfoToolbar)
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.addWidget(self.componentsList)
        hlayout.addWidget(self.clearParamBtn)
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.compInfoStack)
        self.componentInfoWidget.setLayout(vlayout)

        self.splitterMain.addWidget(self.finder_widget)
        self.splitterMain.addWidget(self.splitterMediaPlayers)
        self.splitterMain.addWidget(self.componentInfoWidget)
        qApp.processEvents()

        settings = qApp.instance().getSettings()
        self.last_filename = settings.value("lastOpenedDatabase")
        enc = "{}.enc".format(self.last_filename)
        if self.last_filename and not os.path.exists(self.last_filename) and not os.path.exists(enc):
            self.last_filename = None

        #qApp.instance().logStartup('setting up search dialog')
        self.search_dlg = SearchDlg(self)
        self.search_dock = QDockWidget(self)
        self.search_dock.installEventFilter(self)
        self.search_dock.setWindowTitle(self.search_dlg.windowTitle())
        self.search_dock.setHidden(True)
        self.search_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.search_dock.setAllowedAreas(Qt.NoDockWidgetArea)
        self.search_dock.setFloating(True)
        self.search_dock.setWidget(self.search_dlg)
        self.search_filter_on = False # parameter search, which affects finder list

        self.setConnections()
        self.setSizePolicies()
        self.switchCompInfo(self.scrollArea)

        if qApp.hasPendingEvents():
            qApp.processEvents()
        #qApp.instance().logStartup('completed creation of main window')

        self.set_title()
        self.mw_size_change.connect(self.infoPage.onMWSizeChange)

    def setupFileDialogs(self):
        settings = qApp.instance().getSettings()
        archive_dirs = settings.value('ImportExportDirectories')
        pm = qApp.instance().pm
        #qApp.instance().logStartup('looking for dictionaries')
        project_list = pm.getProjectList()
        for proj in project_list:
            #qApp.instance().logStartup('{}\n{}'.format('setting project info for:', proj))
            pm.setKnownProjectInfo(proj)
        for dir in archive_dirs:
            #qApp.instance().logStartup('{}\n{}'.format('setting archive info for:', dir))
            pm.setKnownProjectInfo(dir)

        #qApp.instance().logStartup('creating SooSL file dialog')
        self.soosl_file_dlg = SooSLFileDialog(self)
        self.soosl_file_dlg.setupForOpenProject() # most likely first setup needed
        #qApp.instance().logStartup('creating Export dictionary dialog')
        self.export_dlg = ExportProjectDlg(self)

    # def onPlayTimerTimeout(self):
    #     qApp.processEvents()

    #@property
    def dirty(self): #returns True if sign data needs saving
        if not self.editing:
            return False
        if self.infoPage.dirty() or \
            self.componentsList.dirty() or \
            self.locationWidget.dirty() or \
            self.exMediaWidget.dirty() or \
            self.player.dirty() or \
            self.exMediaSelector.dirty():
                return True
        return False

    def onCrop(self, _bool):
        player = self.sender()
        widgets = [self.compInfoStack,
                   self.leaveEditAction,
                   self.switchCompInfoAction,
                   self.addSenseAction,
                   self.deleteSignAction,
                   self.helpAction]
        if player is not self.player:
            widgets.append(self.player)
        else:
            widgets.append(self.exMediaWidget)
        for widget in widgets:
            if _bool:
                widget.setEnabled(False)
            else:
                widget.setEnabled(True)

    def eventFilter(self, obj, evt):
        if evt.type() == QEvent.Close and hasattr(self, 'search_dock') and obj is self.search_dock:
            settings = qApp.instance().getSettings()
            geom = self.search_dock.saveGeometry()
            settings.setValue("MainWindow/SearchDock/Geometry", geom)
            settings.setValue("MainWindow/SearchDock/Visible", 0)
            settings.sync()
            if self.scrollArea.isVisible():
                self.handshapeViewGroup.hide()
                self.photoHelpAction.setVisible(False)
            return True
        elif (evt.type() == QEvent.Resize or evt.type() == QEvent.Move) \
            and hasattr(self, 'search_dock') and obj is self.search_dock \
            and self.search_dock.isVisible():
                settings = qApp.instance().getSettings()
                geom = self.search_dock.saveGeometry()
                settings.setValue("MainWindow/SearchDock/Geometry", geom)
                size = self.search_dock.size()
                settings.setValue("MainWindow/SearchDock/Size", size)
                settings.sync()
                return True
        elif evt.type() == QEvent.Close and hasattr(self, 'transcode_settings_dock') and obj is self.transcode_settings_dock and self.transcode_settings_dock.isVisible():
            settings = qApp.instance().getSettings()
            settings.setValue("MainWindow/TranscodeSettingsDock/Geometry", self.transcode_settings_dock.saveGeometry())
            settings.setValue("MainWindow/TranscodeSettingsDock/Visible", 0)
            settings.sync()
            return True #QDockWidget.event(self.transcode_settings_dock, evt)
        elif evt.type() == QEvent.Move and hasattr(self, 'transcode_settings_dock') and obj is self.transcode_settings_dock:
            return True
        # else:
        #     return False

        return super(MainWindow, self).eventFilter(obj, evt)

    def resizeEvent(self, evt):
        self.mw_size_change.emit(self.isMaximized())
        super(MainWindow, self).resizeEvent(evt)

    def showEvent(self, evt):
        qApp.restoreOverrideCursor()
        qApp.processEvents()
        super(MainWindow, self).showEvent(evt)

    def initialProjectSelection(self, project_file):
        if project_file and not qApp.instance().pm.minSooSLVersionCheck(project_file):
            return #self.initialProjectSelection(startup_widget)
        if project_file == 'NO DICTIONARY':
            qApp.instance().completeStartup()
            self.startWithNoProject()
        elif project_file:
            msg = '{}<br>{}'.format(qApp.instance().translate('MainWindow', 'opening dictionary file:'), os.path.basename(project_file))
            if project_file.endswith('.zoozl'):
                if not qApp.instance().pm.openZooZLProject(project_file):
                    self.sender().showProjectControls()
                    self.sender().selectProject()
            else:
                qApp.instance().startupMessage(msg)
                qApp.setOverrideCursor(Qt.BusyCursor)
                project = qApp.instance().pm.openProject(project_file) #if converting from an old sqlite project, this will show the updated details
                if project:
                    self.set_status(project.json_file)
                    self.set_title(project.name)
                    self.project_open.emit(True)

    def startWithNoProject(self):
        frame = QFrame(self)
        frame.setWindowFlags(Qt.Popup)
        frame.setWindowTitle(" ")
        frame.setLineWidth(3)
        frame.setMidLineWidth(3)
        frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
        frame.setAttribute(Qt.WA_NoSystemBackground, False)
        t1 = qApp.instance().translate('MainWindow', 'There is no dictionary open.')
        t2 = qApp.instance().translate('MainWindow', 'What can you do now?')
        t3 = qApp.instance().translate('MainWindow', 'Use the tools menu (on right):')
        t4 = qApp.instance().translate('MainWindow', "<I><B style='color:blue;'>Open</I></B> a dictionary that you've already imported or started")
        t5 = qApp.instance().translate('MainWindow', 'Start a <I><B style="color:blue;">new</I></B> dictionary')
        t6 = qApp.instance().translate('MainWindow', '<I><B style="color:blue;">Import</I></B> a dictionary from a .zoozl file')
        t7 = qApp.instance().translate('MainWindow', 'The tools menu can be shown anytime.')
        t8 = qApp.instance().translate('MainWindow', 'Click on the blue wrench icon (top right).')
        msg = """
            <B style="color:blue;">{}</B><br>
            {}<br><br>
            {}<br><br>
            &nbsp;&nbsp;- {}<br>
            &nbsp;&nbsp;- {}<br>
            &nbsp;&nbsp;- {}<br><br>
            <table>
                <tr>
                    <td>
                        {}<br>{}
                    </td>
                    <td>
                        <img src=':/tools.png'>
                    </td>
                </tr>
            </table>
            """.format(t1, t2, t3, t4, t5, t6, t7, t8)
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        menu = self.tools() # if no dictionary open, show tools menu
        menu.aboutToHide.connect(frame.close)
        menu.setFocusPolicy(Qt.StrongFocus)
        menu.setAttribute(Qt.WA_TranslucentBackground, False) # seems to be required, at least in MX Linux, to keep an opaque background
        # for the menu

        icn = QIcon(':/help.png')
        tool_tip = qApp.instance().translate('MainWindow', 'Help for getting started with SooSL')
        settings = qApp.instance().getSettings()
        if settings.value('helpSource', 'local') == 'online':
            icn = QIcon(':/help_online.png')
            # tool_tip = qApp.instance().translate('MainWindow', 'Help for getting started with SooSL (online)')
        btnLayout = QHBoxLayout()
        help_btn = QPushButton(icn, qApp.instance().translate('MainWindow', 'Help (Getting started)'))
        help_btn.setFocusPolicy(Qt.StrongFocus)
        help_btn.setToolTip(tool_tip)
        help_btn.pressed.connect(frame.close)
        def _help():
            self.helpSooSL(topic='GetstartedwithSooSLDesktopD', context_id=1)
        help_btn.pressed.connect(_help)
        btnLayout.addStretch()
        btnLayout.addWidget(help_btn)
        btnLayout.addStretch()

        #pxm = self.style().standardPixmap(QStyle.SP_MessageBoxInformation).scaledToHeight(32, Qt.SmoothTransformation)
        info_label = QLabel(self)
        info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        info_label.setPixmap(QPixmap(':/info.png'))

        #populate layouts
        hlayout = QHBoxLayout() # vlayout | line | menu
        hlayout.setSpacing(12)
        vlayout = QVBoxLayout() # lbl | buttons
        vlayout.addWidget(lbl)
        vlayout.addLayout(btnLayout)
        hlayout.addWidget(info_label)
        hlayout.addLayout(vlayout)
        hlayout.addWidget(menu)
        frame.setLayout(hlayout)

        # show and position widget
        frame.show()
        pos = self.mapToGlobal(self.rect().topRight())
        pos = pos - QPoint(frame.width(), -self.componentInfoToolbar.height())
        frame.move(pos)
        frame.raise_()
        menu.setFocus(True)
        menu.setActiveAction(self.openProjectAction)

    def show_docks(self):
        settings = qApp.instance().getSettings()
        if int(settings.value("MainWindow/SearchDock/Visible", 0)):
            self.showSearchDlg()
            self.handshapeViewGroup.show()
            qApp.processEvents()
        else:
            self.handshapeViewGroup.hide()
        if int(settings.value("MainWindow/TranscodeSettingsDock/Visible", 0)) and \
            int(settings.value('Testing', 0)):
            self.showTranscodeSettings()
            qApp.processEvents()

    def onScreenCountChanged(self, new_count):
        self.ensureUsingActiveMonitor(self)
        self.ensureUsingActiveMonitor(self.search_dock)
        if hasattr(self, 'transcode_settings_dock'):
            self.ensureUsingActiveMonitor(self.transcode_settings_dock)

    def ensureUsingActiveMonitor(self, widget=None):
        if not widget:
            widget = self
        if qApp.hasPendingEvents():
            qApp.processEvents()
        screen_number = qApp.desktop().screenNumber(widget)
        if  screen_number > qApp.desktop().screenCount() - 1 or \
            screen_number < 0:
                frameGm = widget.frameGeometry()
                screen = qApp.desktop().primaryScreen()
                centerPoint = qApp.desktop().screenGeometry(screen).center()
                frameGm.moveCenter(centerPoint)
                widget.move(frameGm.topLeft())

    def set_title(self, name=None):
        title = f"SooSL™ {qApp.instance().getLongVersion()}"
        if name:
            db_ext = ".{}".format(DB_EXT)
            name = os.path.basename(name)
            _slice = -len(db_ext)
            if name[_slice:] == db_ext:
                name = str(name[:_slice])
            title = "{} - {}".format(name, title)
        self.setWindowTitle(title)

    def set_status(self, filename):
        if filename:
            filename = filename.replace('\\', '/')
            if os.path.splitext(filename)[1] == '.enc':
                filename = filename[:-4]
            image = ':/lock16.png'
            tip = qApp.instance().translate('MainWindow', 'This dictionary cannot be edited.')
            if qApp.instance().pm.ableToEdit():
                image = ':/lock_open16.png'
                tip = qApp.instance().translate('MainWindow', 'This dictionary can be edited.')
            #NOTE: don't show lock image until password protection implemented
            #txt = "<img src='{}'>  {}/  [v{}]".format(image, os.path.dirname(filename), qApp.instance().pm.getProjectSooSLVersion())
            txt =  "<img src='{}'>  {}/&nbsp;&nbsp;".format(image, os.path.dirname(filename))
            ##NOTE: removed verrsion from status in 0.9.3; originally meant to indicate which version created the dictionary
            self.database_lbl.setText(txt)
            self.database_lbl.setToolTip(tip)
        else:
            self.database_lbl.setText("  ")
            self.database_lbl.setToolTip('')

    # def __handshapeView(self):
    #     settings = qApp.instance().getSettings()
    #     image_type = settings.value("componentView/imageType", "photo")
    #     img = ':/sw_symbol.png' #default type "photo"
    #     if image_type == "signwriting":
    #         img = ':/sw_photo.png'
    #     return img

    def resetGui(self):
        self.defaultSettings(_max=False)

    def defaultSettings(self, _max=True):
        if _max:
            self.showMaximized()
        w = self.width()
        h = self.height()
        self.splitterMain.moveSplitter(int(2*w/3), 2)
        if not self.current_video_size:
            self.splitterMediaPlayers.moveSplitter(int(0.5*h), 1)
        self.splitterMain.moveSplitter(int(w/4), 1)
        self.finder_list.defaultSettings()
        self.infoPage.adjustSize()

    def setSizePolicies(self):
        self.splitterMain.setChildrenCollapsible(False)
        self.splitterMediaPlayers.setChildrenCollapsible(False)

        _min, _max = 20, 700
        self.finder_list.setMinimumWidth(_min)
        self.finder_list.setMaximumWidth(_max)
        self.finder_list.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.finder_widget.setMinimumWidth(_min)
        self.finder_widget.setMaximumWidth(_max)
        self.finder_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.player.setMinimumHeight(28)
        self.componentsList.setFixedHeight(70)
        self.componentInfoWidget.setMinimumWidth(_min)

#     def openWithProject(self, project=None):
#         if project and project != 'NO DICTIONARY':
#             _project = qApp.instance().pm.openProject(project)
#
# #             project = qApp.instance().pm.project #if converting from an old sqlite project, this will show the updated details
# #             if project: #NOTE: also in showEvent; startup seems to like/need it to load video properly
# #                 self.project_open.emit(True)
# #             self.set_status(project.json_file)
# #             self.set_title(project.name)
#         else:
#             self.set_title(None)
#             self.set_status(None)

    #@pyqtSlot(bool)
    def onModelDirty(self, _bool):
        self.saveSignAction.setEnabled(_bool)

    #@pyqtSlot()
    def abortSave(self):
        """cleanup after an aborted save"""
        self.kill_ffmpeg()
        qApp.instance().pm.abortSave()
        self.setEnabled(True)
        self.saveSignAction.setEnabled(True)

    def setStates(self):
        qApp.processEvents()
        settings = qApp.instance().getSettings()
        settings.setValue("MainWindow/Geometry", self.saveGeometry())
        screen_pos = self.mapToGlobal(self.rect().center())
        settings.setValue("MainWindow/ScreenPos", screen_pos)
        settings.setValue("MainWindow/State", self.saveState())
        settings.setValue("MainWindow/Splitter/State", self.splitterMain.saveState())
        settings.setValue("MainWindow/Splitter_2/State", self.splitterMediaPlayers.saveState())
        settings.sync()

    def restoreSettings(self):
        settings = qApp.instance().getSettings()
        first_run = settings.value("FirstRun", 1) #first time programm is run
        if not int(first_run):
            main_geometry = settings.value("MainWindow/Geometry", QByteArray())
            self.restoreGeometry(main_geometry)
            main_state = settings.value("MainWindow/State", QByteArray())
            self.restoreState(main_state)
            splitter_state = settings.value("MainWindow/Splitter/State", QByteArray())
            self.splitterMain.restoreState(splitter_state)
            splitter_2_state = settings.value("MainWindow/Splitter_2/State", QByteArray())
            self.splitterMediaPlayers.restoreState(splitter_2_state)

    def kill_ffmpeg(self):
        try:
            if sys.platform.startswith('win'):
                #os.system('taskkill /f /im soosl_ffmpeg.exe')
                #https://stackoverflow.com/questions/7006238/how-do-i-hide-the-console-when-i-use-os-system-or-subprocess-call
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                #si.wShowWindow = subprocess.SW_HIDE # default
                subprocess.call('taskkill /f /im soosl_ffmpeg.exe', startupinfo=si)
            elif sys.platform.startswith('darwin'):
                os.system('killall -9 soosl_ffmpeg')
        except:
            pass

    def closeEvent(self, evt):
        qApp.instance().closing = True
        if self.editing:
            if hasattr(self, 'dirty') and self.dirty():
                self.leaveEdit()
                while not self.save_complete:
                    self.thread().msleep(20)
                    qApp.processEvents()
            else:
                try:
                    qApp.instance().pm.releaseSignLocks(all=True)
                except:
                    pass
        elif not self.save_complete:
            self.abortSave()

        qApp.instance().pm.closeProject(emit=False)
        self.stopVideo()

        self.setStates()

        settings = qApp.instance().getSettings()
        search_bool = settings.value("MainWindow/SearchDock/Visible", 0)
        transcode_bool = settings.value("MainWindow/TranscodeSettingsDock/Visible", 0)

        if hasattr(self, 'transcode_settings_dock'):
            try:
                self.transcode_settings_dock.close()
            except:
                pass
            else:
                del self.transcode_settings_dock

        if hasattr(self, 'transcodeSettingsDlg'):
            try:
                self.transcodeSettingsDlg.close()
            except:
                pass
            else:
                del self.transcodeSettingsDlg

        if hasattr(self, 'search_dock'):
            try:
                self.search_dock.close()
            except:
                pass
            else:
                del self.search_dock

        if hasattr(self, 'search_dlg'):
            try:
                self.search_dlg.close()
            except:
                pass
            else:
                del self.search_dlg

        settings.setValue("MainWindow/SearchDock/Visible", search_bool)
        settings.setValue("MainWindow/TranscodeSettingsDock/Visible", transcode_bool)
        settings.sync()

        qApp.processEvents()
        if not sys.platform.startswith('linux'):
            self.kill_ffmpeg()
        if sys.platform.startswith('win') and hasattr(self, 'help_proc'):
            self.help_proc.kill()

        try:
            qApp.instance().resetKeyboard()
        except:
            pass

    #@pyqtSlot(str)
    def onShowMessage(self, message):
        if message:
            self.database_lbl.hide()
            self.statusBar().setStyleSheet('color:red;')
            self.statusBar().showMessage(message)
        else:
            self.statusBar().setStyleSheet(None)
            self.database_lbl.show()
            self.statusBar().clearMessage()
        qApp.processEvents()

    #@pyqtSlot(str, str)
    def onShowWarning(self, short, long):
        center_on = self
        if hasattr(qApp.instance(), 'startup_widget') and qApp.instance().startup_widget.isVisible():
            center_on = qApp.instance().startup_widget
        QMessageBox.warning(center_on, short, long)

    #@pyqtSlot(str, str)
    def onShowInfo(self, short, long):
        if hasattr(self, 'search_dlg') and self.search_dlg.isVisible():
            QMessageBox.information(self.search_dlg, short, long)
        else:
            QMessageBox.information(self, short, long)

    def createActions(self):
        settings = qApp.instance().getSettings()

        self.searchSignsAction = QAction(QIcon(':/search.png'), "",
            self, toolTip=qApp.instance().translate('MainWindow', "Search for signs"), triggered=self.showSearchDlg)
        self.searchSignsAction.setDisabled(True)

        self.switchFinderPreviewAction  = QAction(QIcon(':/filter.png'), "",
            self, toolTip='', triggered=self.switchFinderPreview)
        self.switchFinderPreviewAction.setDisabled(True)

        self.filterDialectsAction = QAction(QIcon(':/dialect.png'), "",
            self, toolTip=qApp.instance().translate('MainWindow', "View signs by dialect"), triggered=self.filterDialects)
        self.filterDialectsAction.setDisabled(True)

        #for right toolbar
        icon = QIcon(':/lamp_off.png')
        icon.addFile(':/lamp_on.png', state=QIcon.On)
        self.photoHelpAction = QAction(icon, "",
            self, triggered=self.photoHelp)
        self.photoHelpAction.setCheckable(True)
        value = int(settings.value("photoHelp", 1))
        self.photoHelpAction.setChecked(value)
        self.photoHelpAction.setDisabled(True)
        self.photoHelpAction.setVisible(False)

        self.handshapePhotoViewAction = QAction(QIcon(':/sw_photo.png'), "",
            self, toolTip=qApp.instance().translate('MainWindow', 'Switch to Photo handshapes'), triggered=self.handshapeViewChange)
        self.handshapeSymbolViewAction = QAction(QIcon(':/sw_symbol.png'), "",
            self, toolTip=qApp.instance().translate('MainWindow', 'Switch to SignWriting handshapes'), triggered=self.handshapeViewChange)
        _type = settings.value("componentView/imageType")
        if _type == "signwriting":
            self.handshapePhotoViewAction.setDisabled(False)
            self.handshapeSymbolViewAction.setDisabled(True)
            self.handshapeSymbolViewAction.setToolTip('')
        else:
            self.handshapePhotoViewAction.setDisabled(True)
            self.handshapeSymbolViewAction.setDisabled(False)
            self.handshapePhotoViewAction.setToolTip('')

        key = QKeySequence(Qt.CTRL + Qt.Key_Right)
        shortcut_str = key.toString(QKeySequence.NativeText)
        self.switchCompAction = QAction(QIcon(':/components.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'Show parameters'), shortcut_str), triggered=self.switchCompInfo,
            shortcut=key)
        self.switchCompAction.setDisabled(True)

        key = QKeySequence(Qt.CTRL + Qt.Key_Right)
        shortcut_str = key.toString(QKeySequence.NativeText)
        self.switchInfoAction = QAction(QIcon(':/form.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'Show sign information'), shortcut_str), triggered=self.switchCompInfo,
            shortcut=key)
        self.switchInfoAction.setDisabled(True)

        shortcut_str = self.getShortcutString(QKeySequence.Open)
        self.editSignAction = QAction(QIcon(':/edit_sign.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'Open editor for sign'), shortcut_str), triggered=self.editSign,
            shortcut=QKeySequence.Open)
        self.editSignAction.setDisabled(True)

        shortcut_str = self.getShortcutString(QKeySequence.New)
        self.newSignAction = QAction(QIcon(':/new_sign.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'New sign'), shortcut_str), triggered=self.newSign,
            shortcut=QKeySequence.New)
        self.newSignAction.setDisabled(True)

        shortcut_str = self.getShortcutString(QKeySequence.WhatsThis)
        self.toolsAction = QAction(QIcon(':/tools.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', "Tools for dictionary tasks"), shortcut_str), triggered=self.openTools,
            shortcut=QKeySequence.WhatsThis)

        shortcut_str = self.getShortcutString(QKeySequence.Save)
        self.saveSignAction = QAction(QIcon(':/save.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'Save changes to sign'), shortcut_str), triggered=self.saveSign,
            shortcut=QKeySequence.Save)

        icon = QIcon(':/trash24.png')
        icon.addFile(':/trash24_red.png', state=QIcon.On)
        self.deleteSignAction = QAction(icon, "",
            self, toolTip=qApp.instance().translate('MainWindow', "Delete sign entry"), triggered=self.deleteSign)
        self.deleteSignAction.setCheckable(True)

        shortcut_str = self.getShortcutString(QKeySequence.Close)
        self.leaveEditAction = QAction(QIcon(':/leave_edit.png'), "",
            self, toolTip="{}   {}".format(qApp.instance().translate('MainWindow', 'Close editor'), shortcut_str), triggered=self.leaveEdit,
            shortcut=QKeySequence.Close)

        self.addSenseAction = QAction(QIcon(':/add_gloss.png'), "",
            self, toolTip=qApp.instance().translate('MainWindow', 'Add a new gloss or sense'), triggered=self.onAddSense)

        self.compViewOrderChangeAction = QAction(self, triggered=self.compViewOrderChange)
        self.setCompViewOrderAction(onSetup=True)

        self.newProjectAction = QAction(QIcon(':/new_project.png'), qApp.instance().translate('MainWindow', "New dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "Create a new dictionary"), triggered=self.createProject)

        self.openProjectAction = QAction(QIcon(':/open_file.png'), qApp.instance().translate('MainWindow', "Open dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "Open an existing dictionary"), triggered=self.openProject)

        self.importProjectAction = QAction(QIcon(':/import_project.png'), qApp.instance().translate('MainWindow', "Import dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "Import dictionary from a .zoozl file\n (opens as new dictionary)"), triggered=self.importProject)

        self.exportProjectAction = QAction(QIcon(':/export_project.png'), qApp.instance().translate('MainWindow', "Export dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "Export this dictionary as a .zoozl file"), triggered=self.exportProject)

        delete_icon = QIcon(':/delete_project.png')
        self.deleteProjectsAction = QAction(delete_icon, qApp.instance().translate('MainWindow', "Delete dictionaries"),
            self, toolTip=qApp.instance().translate('MainWindow', "Delete dictionaries"), triggered=self.deleteProjects)

        merge_icon = QIcon(':/merge.png')
        self.compareDictionariesAction = QAction(merge_icon, qApp.instance().translate('MainWindow', "Compare two versions"),
            self, #toolTip=qApp.instance().translate('MainWindow', "Merge a second"),
            triggered=self.compareProjects)

        reconcile_icon = QIcon(':/reconcile.png')
        self.reconcileMergeAction = QAction(reconcile_icon, qApp.instance().translate('MainWindow', "Reconcile/merge versions"),
            self, #toolTip=qApp.instance().translate('MainWindow', "Merge a second"),
            triggered=self.onReconcileMerge)
        self.reconcileMergeAction.setEnabled(False)

        update_icon = QIcon(':/cycle.png')
        self.reloadProjectAction = QAction(update_icon, qApp.instance().translate('MainWindow', "Reload dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "The current dictionary has been changed by another user - Please reload"),
            triggered=self.reloadProject)
        self.reloadProjectAction.setVisible(False)

        icn = QIcon(':/help.png')
        shortcut_str = self.getShortcutString(QKeySequence.HelpContents)
        tool_tip = "{}    {}".format(qApp.instance().translate('MainWindow', 'Read the Help documents'), shortcut_str)
        self.helpAction = QAction(icn, qApp.instance().translate('MainWindow', "Help"),
            self, toolTip=tool_tip, triggered=self.onHelpSooSL, shortcut=QKeySequence.HelpContents)

        self.aboutSooSLAction = QAction(QIcon(':/about_soosl.png'), qApp.instance().translate('MainWindow', "About SooSL"),
            self, toolTip=qApp.instance().translate('MainWindow', "Read about SooSL"), triggered=self.aboutSooSL)

        self.aboutProjectAction = QAction(QIcon(':/about_project.png'), qApp.instance().translate('MainWindow', "About dictionary"),
            self, toolTip=qApp.instance().translate('MainWindow', "Read about the current dictionary"), triggered=self.onEditProjectInfo)

        self.editLangsAction = QAction(QIcon(':/edit_langs.png'), qApp.instance().translate('MainWindow', "Written languages"),
            self, toolTip=qApp.instance().translate('MainWindow', "Edit settings used for recording glosses, sentences and comments"), triggered=self.onEditTextSettings)

        self.editDialectsAction = QAction(QIcon(':/edit_dialects.png'), qApp.instance().translate('MainWindow', "Dialects"),
            self, toolTip=qApp.instance().translate('MainWindow', "Edit sign dialects"), triggered=self.onEditProjectDialects)

        self.editGramCatsAction = QAction(QIcon(':/edit_gram_cat.png'), qApp.instance().translate('MainWindow', "Grammar categories"),
            self, toolTip=qApp.instance().translate('MainWindow', "Edit grammar categories"), triggered=self.onEditGramCats)

#         self.editProjectInfoAction = QAction(QIcon(':/edit_passwords.png'), qApp.instance().translate('MainWindow', "Edit dictionary info"),
#             self, toolTip=qApp.instance().translate('MainWindow', "Edit dictionary information"), triggered=self.onEditProjectInfo)

        self.updateSooSLAction = QAction(QIcon(':/soosl_update.png'), qApp.instance().translate('MainWindow', "Update SooSL"),
            self, toolTip=qApp.instance().translate('MainWindow', "Check for program updates"), triggered=self.onUpdateSooSL)

        self.sendFeedbackAction = QAction(QIcon(':/mail.png'), qApp.instance().translate('MainWindow', "Send feedback"),
            self, toolTip=qApp.instance().translate('MainWindow', "Contact us about SooSL"), triggered=self.onSendFeedback)

        self.reportErrorAction = QAction(QIcon(':/mail_error.png'), qApp.instance().translate('MainWindow', "Send error report"),
            self, toolTip=qApp.instance().translate('MainWindow', "Contact us about errors in SooSL"), triggered=self.onReportError)

        try:
            if not qApp.instance().unreported_errors():
                self.reportErrorAction.setVisible(False)
        except:
            self.reportErrorAction.setVisible(False)

#         self.showHideNoGlossAction = QAction(QIcon(':/show.png'), qApp.instance().translate('MainWindow', "Hide empty gloss (???)"),
#             self, toolTip=qApp.instance().translate('MainWindow', "Hide or show ??? in place of empty gloss text"), triggered=self.onShowHideNoGloss)

        self.closeSooSLAction = QAction(QIcon(':/exit.png'), qApp.instance().translate('MainWindow', "Close SooSL"),
            self, toolTip=qApp.instance().translate('MainWindow', "Close and Exit SooSL"), triggered=self.onCloseSooSL)

        self.uploadToWebAction = QAction(QIcon(':/globe.png'),
            qApp.instance().translate('MainWindow', "Upload dictionary"),
            self,
            toolTip=qApp.instance().translate('MainWindow', "Upload this dictionary to the Web"),
            triggered=qApp.instance().pm.updateWebProject)
        self.uploadToWebAction.setVisible(False)

        ## create some actions for testing/devvelopment purposes
        #self.compareProjectsAction = QAction("Merge dictionaries", self, toolTip="Merge dictionary projects into one project", triggered=self.compareProjects)
        self.snapShotAction = QAction("Snapshot", self, toolTip="Create a snapshot of the current project in '~/SooSL/snapshots'", triggered=self.takeSnapShot)
        self.importSignsAction = QAction("Import signs", self, toolTip="Import signs from another project", triggered=self.onImportSigns)
        self.createInventoryAction = QAction("Create inventory", self, toolTip="", triggered=qApp.instance().pm.createInventory)
        self.transcodeSettingsAction = QAction("Transcode settings", self, toolTip="", triggered=self.showTranscodeSettings)
        self.crashTestAction = QAction("Crash test", self, toolTip="", triggered=self.crashTest)
        self.errorTestAction = QAction("Error test", self, toolTip="", triggered=self.errorTest)
        self.transcodeAgainAction = QAction("Transcode videos again!", self, toolTip="", triggered=self.transcodeAgain)

    def transcodeAgain(self):
        # from pyffmpeg import FFmpeg, FFprobe
        # ff = FFmpeg()
        qApp.setOverrideCursor(Qt.BusyCursor)
        for root, dirs, files in os.walk(qApp.instance().pm.project.project_dir):
            if files:
                for file in files:
                    if os.path.splitext(file)[1] == '.mp4':
                        full_pth = os.path.join(root, file)
                        full_pth = full_pth.replace('\\', '/')
                        full_pth = """{}""".format(full_pth)
                        #fp = FFprobe(full_pth)
                        #print(fp.file_name)
                        video = Video([full_pth])
                        # differrence in max_height is really the only attribute that will tell me if a video has already been transcoded or not;
                        # max_fps will usually be 0, and a large video's bitrate will probably be under the max_bitrate anyway.
                        if int(video.fheight) > video.get_settings(['max_height']):
                            src_path, dst_path = video.transcodeAgain()
                            shutil.move(dst_path, full_pth)
                            os.remove(src_path)
        qApp.restoreOverrideCursor()
        box = QMessageBox(self)
        box.setWindowTitle(' ')
        box.setText('Transcode complete!')
        box.setIcon(QMessageBox.Information)
        box.exec_()

    def initialActions(self):
        #initial states
        for action in [self.saveSignAction,
                       self.leaveEditAction,
                       self.deleteSignAction,
                       self.compViewOrderChangeAction, #blue 'back' arrow
                       self.addSenseAction]:
            action.setVisible(False)

    def onCloseSooSL(self):
        self.close()

#     def onShowHideNoGloss(self):
#         settings = qApp.instance().getSettings()
#         value = settings.value('showHideNoGloss', 1)
#         if int(value) == 1:
#             settings.setValue('showHideNoGloss', 0)
#         else:
#             settings.setValue('showHideNoGloss', 1)
#         settings.sync()
#         self.finder_list.refreshFilter()

    def getShortcutString(self, key_sequence):
        try:
            _str = [q.toString(QKeySequence.NativeText) for q in QKeySequence.keyBindings(key_sequence)][0]
        except:
            return ""
        else:
            return _str

    def setConnections(self):
        self.edit_enable.connect(qApp.instance().pm.enterEditingMode)
        self.edit_disable.connect(qApp.instance().pm.leaveEditingMode)
        self.edit_enable.connect(self.enterEditingMode)
        self.edit_disable.connect(self.leaveEditingMode)

        self.project_open.connect(self.finder_list.onProjectOpen)
        self.project_open.connect(self.locationWidget.onProjectOpen)
        self.project_open.connect(self.componentWidget.onProjectOpen)
        self.project_open.connect(self.search_dlg.onProjectOpen)
        self.project_open.connect(self.onProjectOpen)
        #self.project_open.connect(self.infoPage.onProjectOpen)

        qApp.instance().pm.project_closed.connect(self.exMediaWidget.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.exMediaSelector.onProjectClosed)

        qApp.instance().pm.project_closed.connect(self.player.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.finder_list.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.locationWidget.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.componentWidget.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.search_dlg.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.infoPage.onProjectClosed)
        qApp.instance().pm.project_closed.connect(self.onProjectClosed)

        qApp.instance().pm.project_changed.connect(self.onProjectChanged)

        qApp.instance().pm.search_lang_change.connect(self.finder_list.onSearchLangChange)
        qApp.instance().pm.font_size_change.connect(self.finder_list.onFontSizeChange)
        qApp.instance().pm.font_family_change.connect(self.finder_list.onFontFamilyChange)
        qApp.instance().pm.project_reloaded.connect(self.finder_list.setupList)
        qApp.instance().pm.project_reloaded.connect(self.updateSignCount)

        qApp.instance().pm.signs_found.connect(self.search_dlg.onSignsFound)
        qApp.instance().pm.signs_found.connect(self.finder_list.onSignsFound)
        qApp.instance().pm.signs_found.connect(self.onSignsFound)

        self.componentWidget.item_selected.connect(self.componentsList.onItemSelected)
        self.componentsList.show_change_location_details.connect(self.componentWidget.onShowChangeLocationDetails)
        self.componentsList.itemDoubleClicked.connect(self.switchToComponents)
        self.componentsList.location_removed.connect(self.locationWidget.onLocationRemoved)
        self.componentsList.locationItemClicked.connect(self.locationWidget.onLocationItemClicked)

        self.compview_order_change.connect(self.componentWidget.resetPages)

        self.infoPage.loadMediaFile.connect(self.player.onLoadMediaFile)
        qApp.instance().pm.show_message.connect(self.onShowMessage)
        qApp.instance().pm.show_warning.connect(self.onShowWarning)
        qApp.instance().pm.show_info.connect(self.onShowInfo)

        # self.player.scaling_set.connect(self.onPlayerScalingSet)
        # self.exMediaWidget.scaling_set.connect(self.onPlayerScalingSet)

        self.filter_dialects.connect(self.finder_list.filterByDialects)
        self.filter_dialects.connect(self.componentWidget.filterByDialects)
        self.filter_dialects.connect(self.locationWidget.filterByDialects)

        self.filter_dialects.connect(self.search_dlg.comp_widget.filterByDialects)
        self.filter_dialects.connect(self.search_dlg.location_widget.filterByDialects)
        self.filter_dialects.connect(self.search_dlg.comp_search_list.filterByDialects)

        self.filter_dialects.connect(self.infoPage.filterByDialects)
        self.filter_dialects.connect(self.componentsList.filterByDialects)
        self.filter_dialects.connect(self.filterByDialects)

        self.splitterMain.splitterMoved.connect(self.onMainSplitterMoved)

        qApp.instance().pm.dirty.connect(self.onModelDirty)

        self.delete_sign.connect(qApp.instance().pm.onDeleteSign)
        self.delete_sign.connect(self.infoPage.onDeleteSign)
        self.delete_sign.connect(self.componentsList.onDeleteSign)
        self.delete_sign.connect(self.locationWidget.onDeleteSign)

        self.delete_sign.connect(self.search_dlg.comp_search_list.onDeleteSign)
        self.delete_sign.connect(self.search_dlg.location_widget.onDeleteSign)

        self.delete_sign.connect(self.exMediaWidget.onDeleteSign)
        self.delete_sign.connect(self.player.onDeleteSign)

        self.player.amendCurrentVideo.connect(self.infoPage.onCurrentVideoAmended)
        qApp.instance().pm.save_finished.connect(self.onSaveFinished)
        #qApp.instance().pm.save_finished.connect(self.search_dlg.updateComponents)
        self.infoPage.add_sentence.connect(self.onAddSentence)
        self.infoPage.sense_changed.connect(self.finder_list.onSenseChanged)
        qApp.instance().pm.newSentence.connect(self.infoPage.onNewSentence)
        qApp.instance().pm.newSense.connect(self.infoPage.onNewSense)

        self.finder_list.loseTabFocus.connect(self.infoPage.setFocus)
        self.finder_list.has_unglossed_signs.connect(self.showEmptyGlossesBtn.setVisible)

        self.photo_help_changed.connect(self.componentWidget.resetHandshapeToolTips)
        self.photo_help_changed.connect(self.componentsList.resetHandshapeToolTips)
        self.photo_help_changed.connect(self.search_dlg.comp_widget.resetHandshapeToolTips)
        self.photo_help_changed.connect(self.search_dlg.comp_search_list.resetHandshapeToolTips)

        self.search_dlg.clear_search.connect(self.clearSearch)
        self.search_dlg.clear_search.connect(self.finder_list.onClearSearch)
        self.search_dlg.clear_search.connect(self.onClearSearch)
        self.search_dlg.search_signs.connect(self.finder_list.search_box.clear)
        self.search_dlg.search_signs.connect(self.searchSigns)
        # self.finder_list.search_box.textChanged.connect(self.search_dlg.onClear)
        # self.finder_list.search_box.textChanged.connect(self.search_dlg.hide)

        qApp.desktop().screenCountChanged.connect(self.onScreenCountChanged)

        self.clearParamBtn.clicked.connect(self.locationWidget.clearLocations)
        self.clearParamBtn.clicked.connect(self.componentsList.clearComponents)

    def onClearSearch(self):
        self.switchFinderPreviewAction.setDisabled(True)
        self.switchFinderPreviewAction.setIcon(QIcon(':/filter.png'))
        self.switchFinderPreviewAction.setToolTip(None)
        self.searchSignsAction.setIcon(QIcon(':/search.png'))

    def createToolbars(self):
        self.showEmptyGlossesBtn = QPushButton(self)
        self.showEmptyGlossesBtn.setFlat(True)
        self.showEmptyGlossesBtn.setStyleSheet('QPushButton{color:blue; font:22px;}')
        self.showEmptyGlossesBtn.setText('###')
        self.showEmptyGlossesBtn.setToolTip(qApp.instance().translate('MainWindow', 'Show unglossed signs'))
        self.showEmptyGlossesBtn.setCheckable(True)
        self.showEmptyGlossesBtn.setVisible(False)
        self.showEmptyGlossesBtn.setChecked(True)
        self.showEmptyGlossesBtn.toggled.connect(self.showEmptyGlosses)

        empty_widget = QWidget()
        empty_widget.setSizePolicy(QSizePolicy.Expanding, -1)
        self.finder_toolbar = MyMacToolBar(self)
        self.finder_toolbar.addSpacing(7)
        self.finder_toolbar.addAction(self.searchSignsAction)
        self.finder_toolbar.addAction(self.switchFinderPreviewAction)
        self.finder_toolbar.addWidget(empty_widget)
        self.finder_toolbar.addWidget(self.showEmptyGlossesBtn)
        self.finder_toolbar.addAction(self.filterDialectsAction)

        self.componentInfoToolbar = MyMacToolBar(self)
        self.componentInfoToolbar.addAction(self.reloadProjectAction)
        self.componentInfoToolbar.addAction(self.newSignAction)
        self.componentInfoToolbar.addAction(self.editSignAction)
        self.componentInfoToolbar.addAction(self.saveSignAction)
        self.componentInfoToolbar.addAction(self.leaveEditAction)
        self.componentInfoToolbar.addSeparator()

        #self.componentInfoToolbar.addSeparator()
        action_group = [self.switchInfoAction, self.switchCompAction]
        switchInfoCompGroup = self.componentInfoToolbar.addActionGroupBox(action_group)
        #self.componentInfoToolbar.addSeparator()

        self.componentInfoToolbar.addAction(self.photoHelpAction)

        action_group = [self.handshapePhotoViewAction, self.handshapeSymbolViewAction]
        self.handshapeViewGroup = self.componentInfoToolbar.addActionGroupBox(action_group)

        self.componentInfoToolbar.addAction(self.addSenseAction)

        empty_widget = QWidget()
        empty_widget.setSizePolicy(QSizePolicy.Expanding, -1)
        self.componentInfoToolbar.addWidget(empty_widget)

        self.componentInfoToolbar.addAction(self.deleteSignAction)
        empty_widget = QWidget()
        empty_widget.setMaximumSize(24, 24)
        empty_widget.setSizePolicy(QSizePolicy.Expanding, -1)
        self.componentInfoToolbar.addWidget(empty_widget)
        self.componentInfoToolbar.addAction(self.helpAction)
        self.componentInfoToolbar.addAction(self.toolsAction)

    def toggle(self):
        pass

    def createStatusbar(self):
        status = self.statusBar()

        self.message_lbl = QLabel()
        status.addWidget(self.message_lbl)

        self.dialect_lbl = QLabel() #QLabel('   {}   '.format(qApp.instance().translate('MainWindow', 'All dialects')))
        status.addWidget(self.dialect_lbl)

        self.database_lbl = QLabel()
        status.addWidget(self.database_lbl)

        self.testing_tools_btn = QToolButton()
        testingToolsAction = QAction(QIcon(':/tools.png'), "Testing tools",
            self, toolTip="Tools for testing tasks", triggered=self.testTools)
        self.testing_tools_btn.setDefaultAction(testingToolsAction)
        self.testing_tools_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # self.inventory_tool_btn = QPushButton('Create inventory')
        # self.inventory_tool_btn.setStyleSheet('color:Red')
        # self.inventory_tool_btn.setFocusPolicy(Qt.NoFocus)
        # self.inventory_tool_btn.clicked.connect(qApp.instance().pm.createInventory)

        # self.transcode_settings_btn = QPushButton('Transcode settings')
        # self.transcode_settings_btn.setIcon(QIcon(':/transcode24.png'))
        # self.transcode_settings_btn.setStyleSheet('color:Red')
        # self.transcode_settings_btn.setFocusPolicy(Qt.NoFocus)
        # self.transcode_settings_btn.clicked.connect(self.showTranscodeSettings)
        # self.error_btn = QPushButton('Error test')
        # self.error_btn.setStyleSheet('color:Red')
        # self.error_btn.setFocusPolicy(Qt.NoFocus)
        # self.error_btn.clicked.connect(self.errorTest)
        # self.crash_btn = QPushButton('Crash test')
        # self.crash_btn.setStyleSheet('color:Red')
        # self.crash_btn.clicked.connect(self.crashTest)
        # self.crash_btn.setFocusPolicy(Qt.NoFocus)
        status.addPermanentWidget(self.testing_tools_btn)
        # status.addPermanentWidget(self.inventory_tool_btn)
        # status.addPermanentWidget(self.transcode_settings_btn)
        # status.addPermanentWidget(self.error_btn)
        # status.addPermanentWidget(self.crash_btn)
        testing = qApp.instance().getSettings().value('Testing', '0')
        _bool = False
        if str(testing) != '0':
            _bool = True
        self.setUpTesting(_bool)

        self.trans_combo = QComboBox(self)
        self.trans_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self.trans_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.trans_combo.setToolTip(qApp.instance().translate('MainWindow', 'Change display language'))
        for name in sorted(qApp.instance().translation_dict.keys()):
            self.trans_combo.addItem(name)
        settings = qApp.instance().getSettings()
        display_lang = settings.value('displayLang', 'English')
        self.trans_combo.setCurrentText(display_lang)
        self.trans_combo.currentTextChanged.connect(self.onDisplayLangChange)
        status.addPermanentWidget(self.trans_combo)

        self.reset_btn = QPushButton(QIcon(':/reset_gui.png'), qApp.instance().translate('MainWindow', "Reset display"))
        self.reset_btn.setFlat(True)
        self.reset_btn.setFocusPolicy(Qt.NoFocus)
        self.reset_btn.clicked.connect(self.resetGui)
        status.addPermanentWidget(self.reset_btn)

    def onDisplayLangChange(self, lang):
        settings = qApp.instance().getSettings()
        settings.setValue('displayLang', lang)
        qApp.instance().setupTranslators(lang)

    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            self.reset_btn.setText(qApp.instance().translate('MainWindow', "Reset display"))
            settings = qApp.instance().getSettings()
            display_lang = settings.value('displayLang', 'English')
            self.trans_combo.setCurrentText(display_lang)
            self.trans_combo.setToolTip(qApp.instance().translate('MainWindow', 'Change display language'))
            self.updateSignCount()
            self.filterByDialects(self.dialect_filter)
            title = None
            filename = None
            if qApp.instance().pm.project:
                title = qApp.instance().pm.project.name
                filename = qApp.instance().pm.project.filename
            self.set_title(title)
            self.set_status(filename)

            if self.finder_list.search_filter:
                self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Remove search filter'))
            elif hasattr(self, 'search_filter') and self.search_filter:
                self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Apply search filter'))


            if self.showEmptyGlossesBtn.isChecked():
                tip = qApp.instance().translate('MainWindow', 'Hide unglossed signs')
            else:
                tip = qApp.instance().translate('MainWindow', 'Show unglossed signs')
            self.showEmptyGlossesBtn.setToolTip(tip)

            self.filterDialectsAction.setToolTip(qApp.instance().translate('MainWindow', "View signs by dialect"))
            self.searchSignsAction.setToolTip(qApp.instance().translate('MainWindow', "Search for signs"))

            # tooltip = qApp.instance().translate('MainWindow', 'Switch to SignWriting handshapes')
            # settings = qApp.instance().getSettings()
            # _type = settings.value("componentView/imageType")
            # if _type == "signwriting":
            #     tooltip = qApp.instance().translate('MainWindow', 'Switch to Photo handshapes')
            # self.handshapePhotoViewAction.setToolTip(tooltip)

            settings = qApp.instance().getSettings()
            _type = settings.value("componentView/imageType")
            if _type == "signwriting":
                self.handshapePhotoViewAction.setToolTip(qApp.instance().translate('MainWindow', 'Switch to Photo handshapes'))
                self.handshapeSymbolViewAction.setToolTip(qApp.instance().translate('MainWindow', ''))
            else:
                self.handshapePhotoViewAction.setToolTip('')
                self.handshapeSymbolViewAction.setToolTip(qApp.instance().translate('MainWindow', 'Switch to SignWriting handshapes'))

            widget = self.compInfoStack.currentWidget()
            key = QKeySequence(Qt.CTRL + Qt.Key_Right)
            shortcut_str = key.toString(QKeySequence.NativeText)
            if widget is self.scrollArea:
                self.switchCompAction.setToolTip('{}   {}'.format(qApp.instance().translate('MainWindow', 'Show parameters'), shortcut_str))
            elif widget is self.componentWidget:
                self.switchCompAction.setToolTip('{}   {}'.format(qApp.instance().translate('MainWindow', 'Show sign information'), shortcut_str))

            tip = qApp.instance().translate('MainWindow', 'Show Photos when pointer over handshape')
            if self.photoHelpAction.isChecked():
                tip = qApp.instance().translate('MainWindow', 'Hide Photos when pointer over handshape')
            self.photoHelpAction.setToolTip(tip)

            shortcut_str = self.getShortcutString(QKeySequence.Open)
            self.editSignAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'Open editor for sign'), shortcut_str))

            shortcut_str = self.getShortcutString(QKeySequence.New)
            self.newSignAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'New sign'), shortcut_str))

            shortcut_str = self.getShortcutString(QKeySequence.WhatsThis)
            self.toolsAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', "Tools for dictionary tasks"), shortcut_str))

            shortcut_str = self.getShortcutString(QKeySequence.Save)
            self.saveSignAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'Save changes to sign'), shortcut_str))

            self.deleteSignAction.setToolTip(qApp.instance().translate('MainWindow', "Delete sign entry"))

            shortcut_str = self.getShortcutString(QKeySequence.Close)
            self.leaveEditAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'Close editor'), shortcut_str))

            self.addSenseAction.setToolTip(qApp.instance().translate('MainWindow', 'Add new gloss or sense'))

            shortcut_str = self.getShortcutString(QKeySequence.HelpContents)
            self.helpAction.setToolTip("{}    {}".format(qApp.instance().translate('MainWindow', 'Help with SooSL'), shortcut_str))

            self.newProjectAction.setToolTip(qApp.instance().translate('MainWindow', "Create new dictionary"))
            self.newProjectAction.setText(qApp.instance().translate('MainWindow', "New dictionary"))
            self.openProjectAction.setToolTip(qApp.instance().translate('MainWindow', "Open existing dictionary"))
            self.openProjectAction.setText(qApp.instance().translate('MainWindow', "Open dictionary"))
            self.importProjectAction.setToolTip('{} (.zoozl)'.format(qApp.instance().translate('MainWindow', "Import dictionary archive")))
            self.importProjectAction.setText(qApp.instance().translate('MainWindow', "Import dictionary"))
            self.exportProjectAction.setToolTip('{} (.zoozl)'.format(qApp.instance().translate('MainWindow', "Export dictionary archive")))
            self.exportProjectAction.setText(qApp.instance().translate('MainWindow', "Export dictionary"))
            self.deleteProjectsAction.setToolTip(qApp.instance().translate('MainWindow', "Delete dictionaries"))
            self.deleteProjectsAction.setText(qApp.instance().translate('MainWindow', "Delete dictionaries"))

            self.aboutSooSLAction.setToolTip(qApp.instance().translate('MainWindow', "All About SooSL"))
            self.aboutSooSLAction.setText(qApp.instance().translate('MainWindow', "About SooSL"))
            self.aboutProjectAction.setToolTip(qApp.instance().translate('MainWindow', "All About This Dictionary"))
            self.aboutProjectAction.setText(qApp.instance().translate('MainWindow', "About dictionary"))
            self.editLangsAction.setToolTip(qApp.instance().translate('MainWindow', "Edit settings used for recording glosses, sentences and comments"))
            self.editLangsAction.setText(qApp.instance().translate('MainWindow', "Written languages"))
            self.editDialectsAction.setToolTip(qApp.instance().translate('MainWindow', "Edit sign dialects"))
            self.editDialectsAction.setText(qApp.instance().translate('MainWindow', "Dialects"))
            self.editGramCatsAction.setToolTip(qApp.instance().translate('MainWindow', "Edit grammar categories"))
            self.editGramCatsAction.setText(qApp.instance().translate('MainWindow', "Grammar categories"))
            self.updateSooSLAction.setToolTip(qApp.instance().translate('MainWindow', "Check for program updates"))
            self.updateSooSLAction.setText(qApp.instance().translate('MainWindow', "Update SooSL"))
            self.sendFeedbackAction.setToolTip(qApp.instance().translate('MainWindow', "Contact us about SooSL"))
            self.sendFeedbackAction.setText(qApp.instance().translate('MainWindow', "Send feedback"))
            self.reportErrorAction.setToolTip(qApp.instance().translate('MainWindow', "Contact us about errors in SooSL"))
            self.reportErrorAction.setText(qApp.instance().translate('MainWindow', "Send error report"))
            self.closeSooSLAction.setToolTip(qApp.instance().translate('MainWindow', "Close and Exit SooSL"))
            self.closeSooSLAction.setText(qApp.instance().translate('MainWindow', "Close SooSL"))
            self.helpAction.setText(qApp.instance().translate('MainWindow', "Read the Help documents"))
            self.uploadToWebAction.setText(qApp.instance().translate('MainWindow', "Upload dictionary"))
            self.uploadToWebAction.setToolTip(qApp.instance().translate('MainWindow', "Upload this dictionary to the Web"))

            self.search_dock.setWindowTitle(qApp.instance().translate('MainWindow', 'Search for Signs'))
            self.clearParamBtn.setToolTip(qApp.instance().translate('MainWindow', 'Click to remove all indexing parameters, or \
                <br>Drag and drop a single parameter onto this icon to remove it.\
                <br>Right-click on a parameter also removes it.'))
        else:
            QMainWindow.changeEvent(self, evt)

    def showMessage(self, message, time=0):
        message = "{}  ".format(message)
        prev = self.message_lbl.text()
        self.message_lbl.setText(message)
        def reset():
            self.message_lbl.setText(prev)
        if time:
            QTimer.singleShot(time, reset)

    def filterDialects(self):
        try:
            btn = [w for w in self.sender().associatedWidgets() if isinstance(w, QToolButton)][0]
        except:
            pass
        else:
            dialects = qApp.instance().pm.project.dialects
            selected_dialect_ids = copy.deepcopy(qApp.instance().pm.getSelectedDialectIds())
            dlg = DialectDlg(self, dialects, selected_dialect_ids, None, None, editing=False)
            pos = self.mapToGlobal(btn.pos())
            def _move():
                dlg.move(pos)
            QTimer.singleShot(0, _move)

            if dlg.exec_():
                selected = dlg.selected_dialect_ids
                qApp.instance().pm.setSelectedDialectIds(selected)
                self._filterDialects(selected)
            del dlg

    def _filterDialects(self, dialects):
        all_dialects = qApp.instance().pm.getAllDialects()
        if len(dialects) == len(all_dialects):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects
        self.filter_dialects.emit(self.dialect_filter)

    #@pyqtSlot(list)
    def filterByDialects(self, dialects):
        text = qApp.instance().translate('MainWindow', 'All dialects')
        img = ':/dialect.png'
        if not dialects or len(dialects) == len(qApp.instance().pm.getAllDialects()):
            self.dialect_filter = []
        else:
            self.dialect_filter = dialects
            _str = qApp.instance().pm.dialectStr(dialects)
            if not _str:
                _str = qApp.instance().translate('MainWindow', 'focal')
            text = "{} {}".format(qApp.instance().translate('MainWindow', 'Dialects:'), _str)
            img = ':/dialect_filtered.png'
        self.dialect_lbl.setText("  {}  ".format(text))
        self.filterDialectsAction.setIcon(QIcon(img))

    def showEmptyGlosses(self, _bool):
        self.finder_list.showEmptyGlosses(_bool)
        if _bool:
            tip = qApp.instance().translate('MainWindow', 'Hide unglossed signs')
        else:
            tip = qApp.instance().translate('MainWindow', 'Show unglossed signs')
        self.showEmptyGlossesBtn.setToolTip(tip)

    def switchFinderPreview(self):
        if self.finder_list.search_filter:
            self.search_filter = copy.deepcopy(self.finder_list.search_filter)
            self.finder_list.setSearchFilter([])
            self.search_filter_on = False
            self.switchFinderPreviewAction.setIcon(QIcon(':/filter.png'))
            self.searchSignsAction.setIcon(QIcon(':/search.png'))
            self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Apply search filter'))
        elif hasattr(self, 'search_filter') and self.search_filter:
            self.finder_list.setSearchFilter(self.search_filter)
            self.search_filter_on = True
            self.switchFinderPreviewAction.setIcon(QIcon(':/filter_on.png'))
            self.searchSignsAction.setIcon(QIcon(':/search_on.png'))
            self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Remove search filter'))
        qApp.processEvents()

    #@pyqtSlot()
    def switchToComponents(self):
        self.switchCompInfo(self.componentWidget)

    def switchCompInfo(self, widget=None):
        current_widget = self.compInfoStack.currentWidget()
        key = QKeySequence(Qt.CTRL + Qt.Key_Right)
        shortcut_str = key.toString(QKeySequence.NativeText)
        widgets = [self.scrollArea, self.componentWidget]
        if widget not in widgets: #triggered from toolbar
            widget = widgets[0]
            if current_widget is widgets[0]:
                widget = widgets[1] # opposite of current widget

        #if current_widget is not widget:
        self.compInfoStack.setCurrentWidget(widget)
        if widget is self.scrollArea:
            self.switchCompAction.setDisabled(False)
            self.switchCompAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'Show parameters'), shortcut_str))
            self.switchInfoAction.setEnabled(False)
            self.switchInfoAction.setToolTip('')
            if self.search_dock.isHidden():
                self.handshapeViewGroup.hide()
                self.photoHelpAction.setVisible(False)
            self.componentsList.setVisible(False)
            self.clearParamBtn.setVisible(False)
            if self.editing:
                self.addSenseAction.setVisible(True)
                self.onEnableBack(False)
        elif widget is self.componentWidget:
            self.switchCompAction.setDisabled(True)
            self.switchCompAction.setToolTip('')
            self.switchInfoAction.setEnabled(True)
            self.switchInfoAction.setToolTip("{}   {}".format(qApp.instance().translate('MainWindow', 'Show sign information'), shortcut_str))
            self.handshapeViewGroup.show()
            self.photoHelpAction.setVisible(True)
            self.photoHelp()
            self.componentsList.setVisible(True)
            if self.editing:
                self.addSenseAction.setVisible(False)
                self.clearParamBtn.setVisible(True)
                self.onEnableBack(True)
            else:
                self.clearParamBtn.setVisible(False)
        else:
            print('invalid widget to switch to:', widget) # an error message for developers only

    #@pyqtSlot()
    def clearSearch(self):
#         self.onSignsFound(None)
        if hasattr(self, 'search_filter'):
            self.search_filter = None

    def photoHelp(self):
        settings = qApp.instance().getSettings()
        tip = qApp.instance().translate('MainWindow', 'Show Photos when pointer over handshape')
        if self.photoHelpAction.isChecked():
            tip = qApp.instance().translate('MainWindow', 'Hide Photos when pointer over handshape')
            settings.setValue("photoHelp", 1)
        else:
            settings.setValue("photoHelp", 0)
        settings.sync()
        self.photoHelpAction.setToolTip(tip)
        self.photo_help_changed.emit(self.photoHelpAction.isChecked())

    #@pyqtSlot()
    def crashTest(self):
        faulthandler._sigsegv()

    #@pyqtSlot()
    def errorTest(self):
        p = 5/0

    def onHelpSooSL(self):
        self.helpSooSL(topic='AboutSooSLT', context_id=0)

    def helpSooSL(self, topic='AboutSooSLT', anchor=None, context_id=0):
        soosl_help = qApp.instance().getHelpFile()
        # https://doc.qt.io/archives/qtforpython-5/PySide2/QtGui/QDesktopServices.html#more
        # NOTE: develop context help further???
        if sys.platform.startswith('darwin'):
            soosl_help = f'file://{soosl_help}'
            webbrowser.open(soosl_help)
        elif sys.platform.startswith('win'):
            webbrowser.open(soosl_help)
        else:
            url = QUrl(soosl_help)
            QDesktopServices.openUrl(url)

        # if sys.platform.startswith('darwin'):
        #     # # helpManager = NSHelpManager.new()
        #     # # bundle = CFBundleGetMainBundle()
        #     # # print('Bundle?', bundle)
        #     # # help_book_name = CFBundleGetValueForInfoDictionaryKey(bundle, 'CFBundleHelpBookFolder')
        #     # # print('Help?', help_book_name)
        #     # soosl_help = None
        #     # if getattr(sys, 'frozen', False):
        #     #     exec_dir = os.path.realpath(os.path.dirname(sys.executable))
        #     #     soosl_help = exec_dir.replace('MacOS', 'Resources/SooSL.help')
        #     # elif __file__:
        #     #     print('Test Help files in App directory')
        #     #     # pth = '/Users/timothygrove/soosl-desktop/SooSL.aw4/SooSL.help'
        #     #     soosl_help = '/Applications/SooSL.app/Contents/Resources/SooSL.help'
        #     if soosl_help.startswith('http'):
        #         webbrowser.open(soosl_help)
        #     elif soosl_help:
        #         if topic:
        #             # helpManager.openHelpAnchor_inBook_(topic, 'SooSL.help')
        #             os.system(f"open {soosl_help}")
        #     #https://developer.apple.com/forums/thread/667260
        #     # In order to do less typing I set the working directory to the Resources directory in the help bundle, using the chdir pathname command.
        #     # I use the command: hiutil -Cf English.lproj/SooSL.helpindex English.lproj
        #     # This creates a SooSL.helpindex file in the English.lproj folder. As per the documentation the other html files are in a sub directory.
        #     # To be sure that I'm not looking at a cached version of the application's help I use the terminal command:
        #     # rm -rf ~/Library/Caches/com.apple.help*
        #     # The name of the help.helpindex file is in the help bundle's info.plist file in the HPDBookIndexPath dictionary

        #     #https://stackoverflow.com/questions/60366788/how-to-generate-working-indexes-for-macos-help-on-mojave-and-catalina
        #     #https://eclecticlight.co/2017/03/16/using-html-from-tinderbox-7-to-make-a-help-book/

        #     #hiutil -I corespotlight -Caf English.cshelpindex SooSL.help -vvv
        #     #hiutil -I lsm -Caf English.helpindex SooSL.help -vvv
        #     # https://marioaguzman.wordpress.com/2020/09/12/auth/amp/

        # elif sys.platform.startswith('win'):
        #     print('help:', soosl_help)
        #     #webbrowser.open(soosl_help)
        #     # https://doc.qt.io/archives/qtforpython-5/PySide2/QtGui/QDesktopServices.html#more
        #     url = QUrl(soosl_help)
        #     QDesktopServices.openUrl(url)
        #     # if hasattr(self, 'help_proc'):
        #     #     self.help_proc.kill()

        #     # if topic:
        #     #     soosl_help = f'{soosl_help}::{topic}.htm'
        #     # if anchor:
        #     #     soosl_help = f'{soosl_help}#{anchor}'

        #     # try:
        #     #     self.help_proc = subprocess.Popen(['hh.exe', soosl_help])
        #     # except:
        #     #     pass

        # elif sys.platform.startswith('linux'):
        #     # https://doc.qt.io/archives/qtforpython-5/PySide2/QtGui/QDesktopServices.html#more
        #     url = QUrl(soosl_help)
        #     QDesktopServices.openUrl(url)
        #     # try:
        #     #     app = 'xchm'
        #     #     context = '--contextid={}'.format(context_id)
        #     #     subprocess.Popen([app, soosl_help, context])
        #     # except:
        #     #     try:
        #     #         app = '/usr/bin/kchmviewer'
        #     #         if not topic:
        #     #             topic = 'AboutSooSLT'
        #     #         page = '{}.htm'.format(topic)
        #     #         subprocess.Popen([app, soosl_help, '-showPage', page])
        #     #     except:
        #     #         try:
        #     #             app = 'chmsee'
        #     #             subprocess.Popen([app, soosl_help])
        #     #         except:
        #     #             pass

    ##!!@pyqtSlot(list)
    def searchSigns(self, codes):
        qApp.instance().searching = True
        if codes:
            #self.stopVideo()
            qApp.instance().pm.findSignsByComponents(codes)
            self.switchFinderPreviewAction.setEnabled(True)
            self.switchFinderPreviewAction.setIcon(QIcon(':/filter_on.png'))
            self.searchSignsAction.setIcon(QIcon(':/search_on.png'))
            self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Remove search filter'))

    def aboutSooSL(self):
        dlg = AboutSooSLDlg(__version__, __build__, self)
        dlg.exec_()
        del dlg

    def handshapeViewChange(self):
        settings = qApp.instance().getSettings()
        _type = settings.value("componentView/imageType")
        new_type = "signwriting"
        if _type == "signwriting":
            new_type = "photo"
            self.handshapePhotoViewAction.setEnabled(False)
            self.handshapePhotoViewAction.setToolTip('')
            self.handshapeSymbolViewAction.setEnabled(True)
            self.handshapeSymbolViewAction.setToolTip(qApp.instance().translate('MainWindow', 'Switch to SignWriting handshapes'))
        else:
            self.handshapePhotoViewAction.setEnabled(True)
            self.handshapePhotoViewAction.setToolTip(qApp.instance().translate('MainWindow', 'Switch to Photo handshapes'))
            self.handshapeSymbolViewAction.setEnabled(False)
            self.handshapeSymbolViewAction.setToolTip(qApp.instance().translate('MainWindow', ''))
        settings.setValue("componentView/imageType", new_type)
        settings.sync()
        self.componentsList.resetIcons()
        self.componentWidget.resetIcons()
        self.search_dlg.resetIcons()

    def editSign(self):
        sign = qApp.instance().pm.sign
        if sign and not qApp.instance().pm.lockedForEditing(self) and not qApp.instance().pm.lockedForMerging(self):
            sign_file = sign.json_file # 0.9.4
            _id = os.path.splitext(os.path.basename(sign_file))[0] # 0.9.4
            if qApp.instance().pm.acquireSignLocks([_id]):
                sign_id = self.finder_list.selected_sign_id
                self.reloadProject() #make sure working with latest data
                #sign_file = '{}/_signs/{}.json'.format(qApp.instance().pm.project.project_dir, sign_id) # 0.9.3

                if os.path.exists(sign_file): #won't exist if deleted by another user
                    self.edit_enable.emit()
                    self.deleteSignAction.setEnabled(True)
            else:
                msg = '{}\n{}'.format(qApp.instance().translate('MainWindow', "This sign is locked for editing by another user."),
                    qApp.instance().translate('MainWindow', "Try again later."))
                qApp.instance().pm.showLockedMessageBox(self, msg)

    def newSign(self):
        if not qApp.instance().pm.lockedForEditing(self) and not qApp.instance().pm.lockedForMerging(self):
            #user must choose a video to start a new sign
            if qApp.instance().pm.current_project_filename:
                self.pauseVideo()
                filename, texts, case = self.getMediaFile('sign')

                #case 1: do nothing
                #case 2: view existing
                #case 3: use existing
                #case 4: use original
    #             if not case:
    #                 case = 1
                if filename and case in [3, 4]:
                    self.reloadProject()
                    qApp.instance().pm.newSign(filename, texts)

    def openTools(self):
        if qApp.instance().pm.project:
            QTimer.singleShot(0, self.tools)
        else:
            self.startWithNoProject()

    def tools(self):
        #self.pauseVideo() # NOTE: causes problems if network connection lost to networked dictionary
        menu = ToolsMenu(self)
        menu.setToolTipsVisible(True)
        if not self.editing:
            actions = [
                       self.openProjectAction,
                       self.aboutProjectAction,
                       None,
                       self.newProjectAction,
                       self.importProjectAction,
                       self.exportProjectAction,
                       self.uploadToWebAction,
                       self.deleteProjectsAction,
                       None,
                    ##NOTE: hide merging for this versions
                    #    self.compareDictionariesAction,
                    #    self.reconcileMergeAction,
                    #    None,
                       self.editLangsAction,
                       self.editGramCatsAction,
                       self.editDialectsAction,
                       None,
                       self.aboutSooSLAction,
                       self.helpAction,
                       self.sendFeedbackAction,
                       self.reportErrorAction,
                       None,
                       self.closeSooSLAction]
            if not sys.platform.startswith('linux'):
                #actions.insert(14, None)
                actions.insert(16, self.updateSooSLAction)
                #actions.insert(14, None)
            for action in actions:
                if action:
                    menu.addAction(action)
                else:
                    menu.addSeparator()
            try:
                if qApp.instance().unreported_errors():
                    self.reportErrorAction.setVisible(True)
                else:
                    self.reportErrorAction.setVisible(False)
            except:
                self.reportErrorAction.setVisible(False)

            self.aboutProjectAction.setEnabled(True)

            if not qApp.instance().pm.current_project_filename:
                self.editLangsAction.setVisible(False)
                self.aboutProjectAction.setVisible(False)
                self.exportProjectAction.setVisible(False)
                self.editDialectsAction.setVisible(False)
                self.editGramCatsAction.setVisible(False)
                ##NOTE: hide merging for this versions
                # self.compareDictionariesAction.setVisible(False)
                # self.reconcileMergeAction.setVisible(False)
                ##NOTE: hide merging for this versions
                # self.compareDictionariesAction.setEnabled(True)
                # self.reconcileMergeAction.setEnabled(False)
            else:
                self.editLangsAction.setVisible(True)
                self.aboutProjectAction.setVisible(True)
                if qApp.instance().pm.ableToEdit():
                    self.exportProjectAction.setVisible(True)
                self.editDialectsAction.setVisible(True)
                self.editGramCatsAction.setVisible(True)
                ##NOTE: hide merging for this versions
                # self.compareDictionariesAction.setVisible(True)
                # self.reconcileMergeAction.setVisible(True)
                # if qApp.instance().pm.project.needsMergeReconciled():
                #     self.compareDictionariesAction.setEnabled(False)
                #     self.reconcileMergeAction.setEnabled(True)
                # else:
                #     self.compareDictionariesAction.setEnabled(True)
                #     self.reconcileMergeAction.setEnabled(False)
                # if not qApp.instance().pm.ableToEdit():
                #     self.compareDictionariesAction.setVisible(False)
                #     self.reconcileMergeAction.setVisible(False)
            if not qApp.instance().pm.getProjectList():
                self.deleteProjectsAction.setEnabled(False)
            else:
                self.deleteProjectsAction.setEnabled(True)
        else:
            for action in [
                self.editGramCatsAction,
                self.editDialectsAction,
                None,
                self.sendFeedbackAction,
                None,
                self.closeSooSLAction
                ]:
                    if action:
                        menu.addAction(action)
                    else:
                        menu.addSeparator()

        qApp.processEvents()
        pos = self.mapToGlobal(self.rect().topRight())
        pos = pos - QPoint(180, -self.componentInfoToolbar.height())
        #qApp.processEvents()
        menu.setActiveAction(self.openProjectAction)
        if qApp.instance().pm.project: # triggered from tools action; # don't popup here if called by self.startWithNoProject()
            menu.popup(pos)
        return menu

    def testTools(self):
        menu = ToolsMenu(self)
        menu.setToolTipsVisible(True)
        actions = [
            self.snapShotAction,
            self.importSignsAction,
            self.createInventoryAction,
            self.transcodeSettingsAction,
            self.crashTestAction,
            self.errorTestAction,
            self.transcodeAgainAction,
            self.compareDictionariesAction,
            self.reconcileMergeAction
            ]
        for action in actions:
            if action:
                menu.addAction(action)
            else:
                menu.addSeparator()

        pos = self.cursor().pos()
        menu.popup(pos)

    def onImportSigns(self): # a testing tool
        # get project filename to import from
        self.soosl_file_dlg.setupForOpenProject()
        # self.soosl_file_dlg.show()
        # self.soosl_file_dlg.raise_()
        qApp.processEvents()
        self.ensureUsingActiveMonitor(self.soosl_file_dlg)
        project_filename = None
        if self.soosl_file_dlg.exec_():
            project_filename = self.soosl_file_dlg.selected_path
            if not qApp.instance().pm.minSooSLVersionCheck(project_filename):
                return
            qApp.instance().pm.importSignsFromProject(project_filename)

    def createProject(self):
        dlg = NewProjectDlg(self)
        if dlg.exec_():
            qApp.setOverrideCursor(Qt.BusyCursor)
            setup_data = (dlg.project_name, dlg.project_location, dlg.gloss_languages, dlg.dialects, dlg.project_descript, dlg.language_name, dlg.project_version)
            new_project_filename = qApp.instance().pm.newProject(setup_data, DB_EXT)
            if new_project_filename:
                qApp.instance().pm.openProject(new_project_filename)
                self.project_open.emit(True)
                qApp.restoreOverrideCursor()
                qApp.instance().pm.setSearchLangId(dlg.getSearchLangId())
                keyboards = dlg.getKeyboardLayouts()
                qApp.instance().setKeyboardLayouts(keyboards)
                font_families = dlg.getFontFamilies()
                qApp.instance().pm.setFontFamilies(font_families)
                self.newSignAction.setEnabled(True)
                del dlg
            else:
                qApp.restoreOverrideCursor()
                message = '{} ({})'.format(dlg.project_name, dlg.project_location)
                self.onShowWarning(qApp.instance().translate('MainWindow', "Duplicate Name"), "{} - <STRONG>{}</STRONG>".format(qApp.instance().translate('MainWindow', 'Dictionary already exists'), message))
                del dlg
                self.createProject()
        else:
            del dlg

    def readWriteProject(self, _bool):
        qApp.instance().pm.setReadWrite(_bool)

    def setGuiReadWrite(self, _bool):
        for action in [self.editSignAction,
                       self.newSignAction,
                       self.exportProjectAction,
                       self.editDialectsAction,
                       self.editGramCatsAction
                       ]:
            action.setVisible(_bool)

    def importProject(self):
        #self.stopVideo(True)
        qApp.processEvents()
        qApp.instance().pm.importProject()

    def exportProject(self):
        qApp.processEvents()
        if qApp.instance().pm.projectChanged():
            self.reloadProject()
        qApp.instance().pm.exportProject()

    def reloadProject(self, force=False, other_user=True):
        if force or \
        self.reloadProjectAction.isVisible() or \
        qApp.instance().pm.projectTimestampChanged() or \
        qApp.instance().pm.pendingProjectTimestampChange():
            self.reloadProjectAction.setVisible(False)
            sign_id = self.finder_list.selected_sign_id
            sense = self.finder_list.selected_sense
            field = self.finder_list.selected_field

            ## Fix to Albert's dropbox error??? 24/05/2022
            sign_time1 = ''
            try:
                sign_time1 = qApp.instance().pm.sign.modified_datetime
            except:
                pass
            ###############################################

            qApp.instance().pm.reloadCurrentProject()
            self.statusBar().showMessage(qApp.instance().translate('MainWindow', 'Dictionary reloaded'), 3000)
            self.finder_list.setupList()
            self.finder_list.repaint()
            self.updateSignCount()

            deleted = False
            sign_file = qApp.instance().pm.sign.path #current sign
            if os.path.exists(sign_file):
                qApp.instance().pm.findSignById(sign_id, sense, field)
            else:
                deleted = True

            ## Fix to Albert's dropbox error??? 24/05/2022
            sign_time2 = ''
            try:
                sign_time2 = qApp.instance().pm.sign.modified_datetime
            except:
                pass
            ###############################################

            if other_user and (deleted or (sign_time1 != sign_time2)):
                parent = self
                widget = qApp.instance().activeModalWidget()
                if widget:
                    parent = widget
                box = QMessageBox(parent)
                box.setWindowTitle(' ')
                txt1 = qApp.instance().translate('MainWindow', 'The current sign has been edited by another user.')
                if deleted:
                    txt1 = qApp.instance().translate('MainWindow', 'The current sign has been deleted by another user.')
                box.setText(txt1)
                box.setIcon(QMessageBox.Information)
                box.exec_()

    def openProject(self):
        self.soosl_file_dlg.setupForOpenProject()
        qApp.processEvents()
        self.ensureUsingActiveMonitor(self.soosl_file_dlg)
        if self.soosl_file_dlg.exec_():
            project_filename = self.soosl_file_dlg.selected_path
            if project_filename.endswith('.zoozl'):
                return qApp.instance().pm.openZooZLProject(project_filename)
            if not qApp.instance().pm.minSooSLVersionCheck(project_filename):
                return self.openProject()
            qApp.setOverrideCursor(Qt.BusyCursor)
            encrypted_file = project_filename + ".enc"
            if not os.path.exists(project_filename) and not os.path.exists(encrypted_file):
                qApp.restoreOverrideCursor()
                parent = self
                if self.search_dlg.isVisible():
                    parent = self.search_dlg
                warning = QMessageBox.warning(parent, qApp.instance().translate('MainWindow', "File not found"),
                    "{} - <STRONG>{}</STRONG>".format(qApp.instance().translate('MainWindow', 'Cannot find'), project_filename))
                return

            if os.path.exists(encrypted_file):
                project_filename = encrypted_file

            def completeOpen():
                db = qApp.instance().pm.openProject(project_filename)
                self.project_open.emit(True)
                qApp.restoreOverrideCursor()
            if qApp.instance().pm.current_project_filename:
                qApp.instance().pm.project_closed.connect(completeOpen)
                self.stopVideo()
                qApp.instance().pm.closeProject()
            else:
                completeOpen()
            try:
                qApp.instance().pm.project_closed.disconnect(completeOpen)
            except:
                pass
        qApp.restoreOverrideCursor()

    def deletionAllowed(self):
        #only allow deletion if code is entered '54321'
        ok = True
        correct = False
        count = 1
        while not correct:
            dlg = MyInputDialog(self)
            dlg.setWindowTitle(' ')
            dlg.setInputMode(QInputDialog.TextInput)
            text = '<b>{}</b>'.format(qApp.instance().translate('MainWindow', "Password for deletion (see help file):"))
            if count > 1:
                text2 = '<I style="color:red">{}</I>'.format(qApp.instance().translate('MainWindow', 'Incorrect password'))
                text = '{}<br>{}'.format(text, text2)
            dlg.setLabelText(text)
            ok = dlg.exec_()
            code = dlg.textValue()
            try:
                del dlg
            except:
                pass
            if ok and code == '54321':
                return True
            elif ok and code.lower() == 'testingon':
                self.setUpTesting()
                return False
            elif ok and code.lower() == 'testingoff':
                self.setUpTesting(False)
                return False
            elif ok: #code incorrect
                count += 1
            else:
                return False

    def setUpTesting(self, _bool=True):
        self.testing_tools_btn.setVisible(_bool)
        #self.inventory_tool_btn.setVisible(_bool)
        # self.transcode_settings_btn.setVisible(_bool)
        # self.error_btn.setVisible(_bool)
        # self.crash_btn.setVisible(_bool)
        settings = qApp.instance().getSettings()
        if _bool:
            settings.setValue('Testing', '1')
            if not hasattr(self, 'transcodeSettingsDlg'):
                self.transcodeSettingsDlg = TranscodeSettingsWidget(self)
                qApp.instance().transcode_stats.connect(self.transcodeSettingsDlg.showStats)
                self.transcode_settings_dock = QDockWidget(self)
                self.transcode_settings_dock.installEventFilter(self)
                self.transcode_settings_dock.setWindowTitle(self.transcodeSettingsDlg.windowTitle())
                self.transcode_settings_dock.setHidden(True)
                self.transcode_settings_dock.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
                self.transcode_settings_dock.setAllowedAreas(Qt.NoDockWidgetArea)
                self.transcode_settings_dock.setFloating(True)
                self.transcode_settings_dock.setWidget(self.transcodeSettingsDlg)
        else:
            settings.setValue('Testing', '0')
            try:
                self.transcode_settings_dock.close()
            except:
                pass
            else:
                del self.transcode_settings_dock
        settings.sync()

    def deleteProjects(self):
        if self.deletionAllowed():
            dlg = self.soosl_file_dlg
            dlg.setupForDeleting()
            # dlg.show()
            # dlg.raise_()
            qApp.processEvents()
            self.ensureUsingActiveMonitor(dlg)
            if dlg.exec_():
                self.stopVideo()
                projects = dlg.projects()
                project_dict = {}
                for project in projects:
                    project_name, filename = project
                    project_name = '<STRONG><span style="color:blue;">{}</span></STRONG><br>{}'.format(project_name, filename)
                    project_dict[project_name] = filename
                project_names = list(project_dict.keys())
                text = qApp.instance().translate('MainWindow', 'Delete the following dictionaries?')
                project_names = sorted(project_names)
                project_str = ("<li>".join(project_names))
                warning = "<h3 style='color:Red'>{}</h3><ol><li>{}</ol>".format(text, project_str)

                msgBox = QMessageBox(self)
                msgBox.setWindowTitle(qApp.instance().translate('MainWindow', "Delete Dictionary"))
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setText(warning)
                msgBox.setTextFormat(Qt.RichText)
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msgBox.setDefaultButton(QMessageBox.No)
                msgBox.button(QMessageBox.Yes).setIcon(QIcon(":/thumb_up.png"))
                msgBox.button(QMessageBox.No).setIcon(QIcon(":/thumb_down.png"))
                msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('MainWindow', "Yes"))
                msgBox.button(QMessageBox.No).setText(qApp.instance().translate('MainWindow', "No"))
                ret = msgBox.exec_()
                if ret == QMessageBox.Yes:
                    #qApp.instance().pm.deleteProjects(projects)
                    qApp.setOverrideCursor(Qt.BusyCursor)
                    for project in projects:
                        project_name, filename = project
                        success = qApp.instance().pm.deleteProject(filename)
                        if success: # deletion success
                            settings = qApp.instance().getSettings()
                            if project == settings.value("lastOpenedDatabase", None):
                                settings.setValue("lastOpenedDatabase", None)
                                settings.sync()
                                self.project_open.emit(False)
                                self.set_title(None)
                                self.set_status(None)
                                self.showMessage('')
                            qApp.restoreOverrideCursor()
                            QMessageBox.information(self, qApp.instance().translate('MainWindow', "Deletion complete"), "<center><p style='color:blue'>{}</p><p>{}</p></center>".format(qApp.instance().translate('MainWindow', "Deletion complete"), project_name))
                        else: # deletion failure
                            qApp.restoreOverrideCursor()
                            qApp.instance().processEvents()
                            self.showCannotDeleteMessage(project_name, filename)
            else:
                return

    def showCannotDeleteMessage(self, project_name, project_filename):
        msg1 = qApp.instance().translate('MainWindow', 'Cannot delete dictionary')
        msg2 = ''
        users = qApp.instance().pm.getOtherProjectUsers(project_filename)
        if users:
            msg2 = qApp.instance().translate('MainWindow', 'This dictionary is open by other users:') + '<ol>'
            for u in users:
                msg2 += '<li>{}</li>'.format(u)
            msg2 += '</ol>'
        else:
            msg2 = qApp.instance().translate('MainWindow', 'Media files from this dictionary may be open by other programs.')
        qApp.instance().pm.showWarning(' ', '<b>{}</b><br><br><b>{}</b><br>{}<br><br>{}'.format(msg1, project_name, project_filename, msg2))

    def onAddSense(self):
        self.switchCompInfo(self.scrollArea)
        qApp.instance().pm.addNewSense()

    def pauseVideo(self):
        self.player.pauseAtStart()
        self.exMediaWidget.pauseAtStart()

    def stopVideo(self):
        self.exMediaWidget.Stop()
        self.player.Stop()

    #@pyqtSlot(str)
    def onAddSentence(self, gloss_id):
        self.pauseVideo()
        filename, texts, case = self.getMediaFile('sent')
        #case 1: do nothing
        #case 2: view existing
        #case 3: use existing
        #case 4: use original
        if case == 1 or not filename:
            return
        qApp.instance().pm.addNewSentence(filename, gloss_id, texts)

    def onProjectOpen(self, _bool):
        self.reloadProjectAction.setVisible(False)
        sign_count = self.updateSignCount()
        if _bool and qApp.instance().pm.project:
            selected = qApp.instance().pm.project.selected_dialect_ids
            self.filter_dialects.emit(selected)
            self.dialect_lbl.setText("  {}  ".format(qApp.instance().translate('MainWindow', 'All dialects')))
            self.setGuiReadWrite(qApp.instance().pm.ableToEdit())
            self.set_status(qApp.instance().pm.current_project_filename)
            self.set_title(qApp.instance().pm.project.name)
            self.newSignAction.setDisabled(False)
            if qApp.instance().pm.sign:
                self.editSignAction.setEnabled(True)
            else:
                self.editSignAction.setEnabled(False)

            self.switchFinderPreviewAction.setDisabled(True)
            self.filterDialectsAction.setDisabled(False)
            if sign_count:
                self.searchSignsAction.setEnabled(True)
            else:
                self.searchSignsAction.setEnabled(False)
            self.photoHelpAction.setDisabled(False)
            self.showEmptyGlossesBtn.setEnabled(True)
            self.showEmptyGlossesBtn.setChecked(True)
            self.finder_list.setFocus(True)
            self.uploadToWebAction.setVisible(True)
            if not self.isVisible():
                qApp.instance().completeStartup()
            if qApp.instance().pm.project.needsMergeReconciled():
                self.reconcileMergeAction.setEnabled(True)
        else:
            self.newSignAction.setDisabled(True)
            self.editSignAction.setDisabled(True)
            self.filterDialectsAction.setDisabled(True)
            self.searchSignsAction.setDisabled(True)
            self.photoHelpAction.setDisabled(True)
            self.showEmptyGlossesBtn.setEnabled(False)
            self.uploadToWebAction.setVisible(False)
            self.reconcileMergeAction.setEnabled(False)

    def onProjectClosed(self):
        #self.stopVideo()
        self.locationWidget.clearLocations()
        self.componentsList.clearComponents()
        self.infoPage.clear()
        self.clearSearch()
        if hasattr(self, 'search_dlg'):
            self.search_dlg.onClear()
        self.switchCompInfo(self.scrollArea)
        self.switchFinderPreviewAction.setDisabled(True)
        self.filterDialectsAction.setDisabled(True)
        self.searchSignsAction.setDisabled(True)
        self.photoHelpAction.setDisabled(True)
        #self.handshapePhotoViewAction.setDisabled(True)
        self.showEmptyGlossesBtn.setEnabled(False)
        self.saveSignAction.setEnabled(False)
        self.editSignAction.setEnabled(False)
        self.statusBar().clearMessage()
        self.uploadToWebAction.setVisible(False)

        self.set_title(None)
        self.set_status(None)
        self.showMessage('')
        self.dialect_lbl.clear()

    def onProjectChanged(self):
        self.reloadProjectAction.setVisible(True)
        self.componentInfoToolbar.repaint()

    def changeCurrentMedia(self, orig_filename, mediatype):
        filename, texts, case = self.getMediaFile(mediatype, change=True)
        #case 1: do nothing
        #case 2: view existing
        #case 3: use existing
        #case 4: use original
        if not filename or case == 1:
            return (None, None, None)

        response = 2 # default response; change for all ==> applies to signs/sentences
        _texts = None
        if mediatype == 'sent':
            _texts = texts
        return (filename, response, _texts)

    def getDirTextFilter(self, media_type):
        _type = media_type
        if not _type:
            _type = self.infoPage.selected_widget.video_type
        if not _type:
            _type = 'sign'
        dir_name = None
        text = ''
        if _type == 'sign':
            dir_name = 'lastMediaDir' #"signVideoDir"
            text = qApp.instance().translate('MainWindow', 'Choose video file for a sign')
        elif _type == 'sent':
            dir_name = 'lastMediaDir' #"sentenceVideoDir"
            text = qApp.instance().translate('MainWindow', 'Choose video file for a sentence')
        elif _type == 'ex_media':
            dir_name = 'lastMediaDir' #"exMediaDir"
            text = qApp.instance().translate('MainWindow', 'Choose video or picture file')
        elif _type == 'ex_video':
            dir_name = 'lastMediaDir' #"exVideoDir"
            text = qApp.instance().translate('MainWindow', 'Choose video file')
        elif _type == 'ex_picture':
            dir_name = 'lastMediaDir' #"exPictureDir"
            text = qApp.instance().translate('MainWindow', 'Choose a picture file')
        elif _type == 'logo':
            dir_name = 'lastMediaDir'
            text = qApp.instance().translate('MainWindow', 'Choose a picture file')
        return (dir_name, text)

    def fileCheck(self, filename, file_type):
        if not filename:
            return False
        elif file_type == 'ex_media':
            if qApp.instance().pm.isPicture(filename):
                file_type = 'ex_picture'
            else:
                file_type = 'ex_video'

        def showWarning(text):
            warning = MyMessageBox(QMessageBox.Warning,
                qApp.instance().translate('MainWindow', "File error"),
                """<strong>{}</strong>""".format(text))
            warning.exec_()
        if file_type == 'ex_picture' and not qApp.instance().pm.isPicture(filename):
            text = qApp.instance().translate('MainWindow', "Use only picture files for extra pictures")
            showWarning(text)
            return False
        elif file_type == 'sign' and not qApp.instance().pm.isVideo(filename):
            text = qApp.instance().translate('MainWindow', "Use only video files for signs")
            showWarning(text)
            return False
        elif file_type == 'sent' and not qApp.instance().pm.isVideo(filename):
            text = qApp.instance().translate('MainWindow', "Use only video files for sentences")
            showWarning(text)
            return False
        elif file_type == 'ex_video' and not (qApp.instance().pm.isVideo(filename) or qApp.instance().pm.isPicture(filename)):
            text = qApp.instance().translate('MainWindow', "Use only video files for extra videos")
            showWarning(text)
            return False
        elif (file_type == 'ex_picture' and Picture([filename]).isCorrupt()) or \
            (file_type in ['ex_video', 'sent', 'sign'] and Video([filename]).isCorrupt()):
            text = qApp.instance().translate('MainWindow', 'File is corrupt')
            showWarning(text)
            return False
        elif file_type == 'logo' and not qApp.instance().pm.isPicture(filename):
            text = qApp.instance().translate('MainWindow', "Use only picture files for project logos")
            showWarning(text)
            return False
        elif file_type == 'logo' and Picture([filename]).isCorrupt():
            text = qApp.instance().translate('MainWindow', 'File is corrupt')
            showWarning(text)
            return False
        return True

    def getMediaFilename(self, text, media_dir, file_type):
        filename = None
        dlg = self.soosl_file_dlg
        if file_type in ['sign', 'sent']:
            dlg.setupForVideoFiles(text, media_dir)
        elif file_type == 'logo':
            dlg.setupForProjectLogo(text, media_dir)
        else:
            dlg.setupForAllMedia(text, media_dir)
        # dlg.show()
        # dlg.raise_()
        qApp.processEvents()
        if self.editing:
            self.edit_disable.connect(dlg.close)
        if dlg.exec_():
            filename = dlg.selected_path
        dlg.close()
        return filename

    def existingFileCheck(self, filename, file_type):
        #reusing existing file?
        texts = None
        #case 1: do nothing
        #case 2: view existing
        #case 3: use existing
        #case 4: use original
        case = 4 # this would be the default case if no existing file found
        existing_name = qApp.instance().pm.fileInProject(filename, file_type)
        if existing_name:
            existing_file = os.path.join(qApp.instance().pm.getTypeDir(file_type, filename), existing_name)
            existing_media_dlg = ExistingMediaDlg(self, filename, existing_file, file_type)
            #existing_media_dlg.setModal(True)
            existing_media_dlg.view_signs_for_file.connect(self.onViewSignsForFile)
            existing_media_dlg.exec_()
            pos = existing_media_dlg.pos()
            case = existing_media_dlg.case
            if case == 2:
                #existing_media_dlg.hide()
                existing_media_dlg.setModal(False)
                self.existing_file_dock = QDockWidget(self)
                self.existing_file_dock.setHidden(True)
                self.existing_file_dock.setFeatures(QDockWidget.DockWidgetFloatable)
                self.existing_file_dock.setAllowedAreas(Qt.NoDockWidgetArea)
                self.existing_file_dock.setFloating(True)
                self.existing_file_dock.setWidget(existing_media_dlg)
                self.existing_file_dock.setWindowTitle(existing_media_dlg.windowTitle())
                self.existing_file_dock.move(pos)

                while case == 2:
                    existing_media_dlg.show()
                    self.existing_file_dock.show()
                    qApp.processEvents()
                    case = existing_media_dlg.case

            self.setEnabled(True)
            try:
                existing_media_dlg.close()
            except:
                pass
            try:
                self.existing_file_dock.close()
            except:
                pass

            #self.finder_list.setSignFilter(None)
            if case:
                texts = existing_media_dlg.selected_texts
            else:
                return (None, None, None)
        if case == 3:
            filename = existing_file
        return (filename, texts, case)

    def compareProjects(self):
        if not self.compareDictionariesAction.isEnabled():
            return ##NOTE: This shouldn't be triggered when the action is disabled, but it is???

        #if not self.acquired_full_project_lock and not self.acquired_project_lock:
        self.acquired_full_project_lock = qApp.instance().pm.acquireFullProjectLock(self)
        if self.acquired_full_project_lock:
            dlg = MergeDialog(self)
            qApp.processEvents()
            self.ensureUsingActiveMonitor(dlg)
            if dlg.exec_():
                qApp.setOverrideCursor(Qt.BusyCursor)
                if dlg.compareProjects():
                    qApp.restoreOverrideCursor()
                    txt1 = qApp.instance().translate('MainWindow', 'There are differences.')
                    txt2 = qApp.instance().translate('MainWindow', 'Reconcile now?')
                    info = "<h3>B != A</h3>{}&nbsp;{}".format(txt1, txt2)
                    msgBox = QMessageBox(self)
                    dlg.close_signal.connect(msgBox.close)
                    msgBox.setWindowTitle(qApp.instance().translate('MainWindow', "Reconcile Dictionary Differences?"))
                    msgBox.setIcon(QMessageBox.Information)
                    msgBox.setText(info)
                    msgBox.setTextFormat(Qt.RichText)
                    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msgBox.setDefaultButton(QMessageBox.No)
                    msgBox.button(QMessageBox.Yes).setIcon(QIcon(":/thumb_up.png"))
                    msgBox.button(QMessageBox.No).setIcon(QIcon(":/thumb_down.png"))
                    msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('MainWindow', "Yes"))
                    msgBox.button(QMessageBox.No).setText(qApp.instance().translate('MainWindow', "No"))
                    ret = msgBox.exec_()
                    if ret != QMessageBox.Yes:
                        qApp.instance().pm.releaseFullProjectLock(self)
                        qApp.instance().pm.stopInactivityTimer()
                    else: # reconcile changes
                        self.onReconcileMerge()
                        self.reconcileMergeAction.setEnabled(True)
                qApp.restoreOverrideCursor()
            else:
                qApp.instance().pm.releaseFullProjectLock(self)

    def onReconcileMerge(self, ignore_removal_check=False):
        if qApp.instance().pm.project:
            _dir =  qApp.instance().pm.project.merge_dir
            if os.path.exists(_dir):
                if not self.acquired_full_project_lock and not self.acquired_project_lock:
                    self.acquired_full_project_lock = qApp.instance().pm.acquireFullProjectLock(self, ignore_merge_lock=True)
                if self.acquired_full_project_lock:
                    dlg = ReconcileChangesDialog(self, ignore_removal_check)
                    dlg.exec_()
                    # if dlg.close_reopen:
                    #     qApp.setOverrideCursor(Qt.BusyCursor)
                    #     self.onReconcileMerge(ignore_removal_check=True)
                    if not os.path.exists(_dir) and not dlg.abandoned:
                        QMessageBox.information(self, qApp.instance().translate('MainWindow', "Merge Complete"), """<center><h3 style='color:blue;'>{}</h3></center>""".format(qApp.instance().translate('MainWindow', 'Merge and reconciliation completed.')))
                        self.reconcileMergeAction.setEnabled(False)

    def takeSnapShot(self):
        snapshot_dir = '{}/snapshots'.format(qApp.instance().getWorkingDir())
        now = int(time.time())
        project_file = qApp.instance().pm.current_project_filename
        project_dir = os.path.dirname(project_file)
        root, ext = os.path.splitext( os.path.basename(project_file))

        snapshot_dir = '{}/{}-{}'.format(snapshot_dir, root, now)
        new_project_dir = '{}/{}'.format(snapshot_dir, root)

        inventory = qApp.instance().pm.createInventory()
        jsn = None
        with open(inventory, 'r', encoding='utf-8') as f:
            jsn = json.load(f)
        os.remove(inventory)
        files = jsn.get('files', [])
        for f in files:
            pth = f.get('desktop_path', f.get('path'))
            old_pth = f'{project_dir}{pth}'
            new_pth = f'{new_project_dir}{pth}'
            try:
                shutil.copy(old_pth, new_pth)
            except:
                os.makedirs(os.path.dirname(new_pth), exist_ok=True)
                shutil.copy(old_pth, new_pth)

    def getMediaFile(self, file_type, change=False):
        """get a media file
        """
        dir_name, text = self.getDirTextFilter(file_type)
        settings = qApp.instance().getSettings()
        media_dir = settings.value(dir_name, QStandardPaths.writableLocation(QStandardPaths.MoviesLocation))
        if not isinstance(media_dir, (str, QDir)): #just in case an int got into the config through earlier bug
            media_dir = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
        filename = self.getMediaFilename(text, media_dir, file_type)
        if not self.fileCheck(filename, file_type):
            return (None, None, None)
        texts = None
        case = None
        if file_type != 'logo':
            # remember choice of directory
            settings.setValue(dir_name, os.path.dirname(filename))
            settings.sync()
            filename, texts, case = self.existingFileCheck(filename, file_type)
        return (filename, texts, case)

    def onViewSignsForFile(self, filename):
        qApp.instance().pm.findSignsByFile(filename)
        #NOTE: need to find unglossed sign as well

    def updateSignCount(self):
        message = ''
        count = qApp.instance().pm.signCount2()
        if not count:
            count = 0
        message = "  {} {}  ".format(count, qApp.instance().translate('MainWindow', 'Signs in dictionary'))
        self.showMessage(message)
        return count

    #@pyqtSlot()
    def onSaveFinished(self):
        self.setDisabled(False)
        self.exMediaWidget.setNormalView()
        self.save_complete = True
        self.statusBar().showMessage(qApp.instance().translate('MainWindow', "Sign saved"), 3000)
        self.finder_list.amendList()

        self.deleteSignAction.setEnabled(True)

        if self.deleteSignAction.isChecked():
            self.deleteSignAction.blockSignals(True)
            self.deleteSignAction.setChecked(False)
            self.deleteSignAction.blockSignals(False)
            self.edit_disable.emit()
            self.switchCompInfo(self.scrollArea)
        elif self.leave_edit_flag:
            self.edit_disable.emit()
        #ensure that one and only one connection is made to self.player.onLoadMedia
        #will be disconnected after saving a sign deletion
        while True:
            try:
                self.infoPage.loadMediaFile.disconnect(self.player.onLoadMediaFile)
            except:
                break
        self.infoPage.loadMediaFile.connect(self.player.onLoadMediaFile)
        try:
            self.progress_dlg.close()
        except:
            pass #already closed
        self.progress_dlg = None
        qApp.processEvents()
        if hasattr(self, 'search_dlg'):
            self.search_dlg.onSearch()

    def setupProgress(self, title=None):
        self.progress_dlg = qApp.instance().getProgressDlg(title)

    def getSignData(self):
        sign_data = self.infoPage.getSignData()
        components = self.componentsList.getSignData()
        components.get("componentCodes", []).extend(self.locationWidget.getSignData().get("componentCodes", []))
        sign_data.update(components)
        sign_data.update(self.exMediaSelector.getSignData())
        return sign_data

    def saveSign(self, show=False):
        qApp.instance().pm.startInactivityTimer(self)
        self.pauseVideo()
        qApp.processEvents()
        self.save_complete = False
        sign = qApp.instance().pm.sign
        if self.dirty():
            self.setDisabled(True)
            dlg = None
            if show or qApp.instance().pm.delete_flag: #only confirm save if deleting sign
                dlg = SaveChangesDlg(qApp.instance().pm.delete_flag, parent=self)
                self.edit_disable.connect(dlg.close)
            if not dlg or (dlg and dlg.exec_()):
                if qApp.instance().pm.delete_flag:
                    self.stopVideo()
                self.setupProgress(title=(qApp.instance().translate('MainWindow', 'Saving sign...')))
                self.saveSignAction.setEnabled(False)
                sign_data = self.getSignData()
                qApp.instance().pm.setSaveProgressDuration([sign_data])
                qApp.instance().pm.saveSign(sign_data)
            else: # save cancelled
                qApp.instance().pm.cleanupNewSign()
                self.save_complete = True
                if not qApp.instance().closing:
                    self.setEnabled(True)
                    if qApp.instance().pm.delete_flag:
                        self.deleteSignAction.setChecked(False)
                        self.deleteSign() #reverse delete settings
                self.edit_disable.emit()
        else:
            self.save_complete = True

    def leaveEdit(self, check_dirty=True):
        ##NOTE: unsure why the leave editing tool action is sending in check_dirty=False
        if isinstance(self.sender(), QAction):
            check_dirty = True
        if self.infoPage.current_editor:
            try:
                self.infoPage.current_editor.clearFocus()
            except:
                pass
        self.leave_edit_flag = True
        if check_dirty and hasattr(self, 'dirty') and self.dirty():
            self.saveSign(show=True)
        else:
            self.edit_disable.emit()
        self.setDisabled(False)
        if self.search_filter_on:
            codes = self.search_dlg.comp_search_list.codeList
            if codes:
                self.searchSigns(codes)
        try:
            qApp.instance().pm.releaseSignLocks(all=True)
        except:
            pass

    def deleteSign(self):
        btn = self.deleteSignAction
        self.switchCompInfo(self.scrollArea)
        self.addSenseAction.setVisible(True)
        _bool = False
        if btn.isChecked():
            _bool = True

        for action in [self.addSenseAction]: #, self.switchCompInfoAction]:
            action.setDisabled(_bool)
        self.delete_sign.emit(_bool)
        QTimer.singleShot(200, self.saveSign)

    def compViewOrderChange(self):
        self.setCompViewOrderAction()
        self.compview_order_change.emit()

    def setCompViewOrderAction(self, onSetup=False):
        png = 'back.png'
        shortcut_str = self.getShortcutString(QKeySequence.Back)
        _help = "{}   {}".format(qApp.instance().translate('MainWindow', 'Show parameter folders'), shortcut_str)
        self.compViewOrderChangeAction.setIcon(QIcon(":/{}".format(png)))
        self.compViewOrderChangeAction.setToolTip(_help)
        self.compViewOrderChangeAction.setShortcut(QKeySequence.Back)

    #@pyqtSlot()
    def enterEditingMode(self):
        self.editing = True
        self.search_dock.setEnabled(False)
        self.search_dlg.setEnabled(False)
        self.leave_edit_flag = False
        # y = self.player.AddEditMediaBtn.height()
        # sizes = self.splitterMediaPlayers.sizes()
        # size = sizes[0]
        # self.splitterMediaPlayers.moveSplitter(size+32, 1)

        self.componentWidget.setCurrentIndex(0)
        self.componentWidget.tabBar().setVisible(True)
        self.componentWidget.enableBack.connect(self.onEnableBack)
        self.componentsList.itemDoubleClicked.connect(self.componentWidget.locateSymbol)
        #NOTE: all dialects available when editing; no filter
#         self.filter_dialects.emit([])

        self.setStyleSheet('QStatusBar {background: red;} QStatusBar QLabel, QStatusBar QPushButton {color: white;}') #E6E6FF #PaleGoldenRod, khaki
        for action in [self.saveSignAction,
                       self.leaveEditAction,
                       self.deleteSignAction
                       ]:
            action.setVisible(True)
        if self.componentWidget.isVisible():
            self.addSenseAction.setVisible(False)
        else:
            self.addSenseAction.setVisible(True)
        if self.componentsList.isVisible():
            self.clearParamBtn.setVisible(True)
        self.deleteSignAction.setToolTip(qApp.instance().translate('MainWindow', "Delete sign entry"))
        for action in [self.editSignAction,
                       self.newSignAction,
                       self.switchFinderPreviewAction,
                       self.filterDialectsAction
                       ]:
            action.setVisible(False)
        self.searchSignsAction.setDisabled(True)
        # self.switchCompAction.setDisabled(False)
        # self.switchInfoAction.setDisabled(False)
        self.componentsList.setStyleSheet("""QListView{border-style:inset;}""")

        self.finder_toolbar.setVisible(False)
        text = self.database_lbl.text().strip()
        text = '{} {}'.format(qApp.instance().translate('MainWindow', 'EDITING:'), text)
        self.database_lbl.setText('  {}  '.format(text))

        title = self.windowTitle()
        title = '{} {}'.format(qApp.instance().translate('MainWindow', 'EDITING:'), title)
        self.setWindowTitle(title)
        self.componentInfoWidget.setVisible(True)

        self.saveSignAction.setEnabled(False)
        self.deleteSignAction.setEnabled(True)
        self.exMediaWidget.adjustSize()
        self.player.adjustSize()
        qApp.instance().pm.startInactivityTimer(self)
        self.otherEnterEditingMode()
        QTimer.singleShot(0, self.update)

    def otherEnterEditingMode(self):
        self.player.enterEditingMode()
        self.infoPage.enterEditingMode()
        self.finder_list.enterEditingMode()
        self.componentsList.enterEditingMode()
        self.locationWidget.enterEditingMode()
        self.componentWidget.enterEditingMode()
        self.exMediaWidget.enterEditingMode()
        self.exMediaSelector.enterEditingMode()

    #@pyqtSlot()
    def leaveEditingMode(self):
        qApp.instance().pm.stopInactivityTimer()

        title = self.windowTitle()
        title = title.replace(qApp.instance().translate('MainWindow', 'EDITING:'), '').strip()
        self.setWindowTitle(title)

        text = self.database_lbl.text()
        text = text.replace(qApp.instance().translate('MainWindow', 'EDITING:'), '').strip()
        self.database_lbl.setText('  {}  '.format(text))

        self.setStyleSheet(None)
        self.finder_widget.show()
        self.finder_toolbar.setVisible(True)
        for action in [self.saveSignAction,
                       self.leaveEditAction,
                       self.deleteSignAction,
                       self.compViewOrderChangeAction,
                       self.addSenseAction
                       ]:
            action.setVisible(False)
        for action in [self.editSignAction,
                       self.newSignAction,
                       self.switchFinderPreviewAction,
                       self.filterDialectsAction]:
            action.setVisible(True)
        for action in [self.addSenseAction
                       #self.switchCompInfoAction
                       ]:
            action.setDisabled(False)

        #sign_count = qApp.instance().pm.signCount2() #
        sign_count = self.updateSignCount()
        if sign_count:
            self.searchSignsAction.setEnabled(True)
        else:
            self.searchSignsAction.setEnabled(False)

        if qApp.instance().pm.sign and sign_count:
            self.editSignAction.setEnabled(True)
        else:
            self.editSignAction.setEnabled(False)

        if self.deleteSignAction.isChecked():
            self.deleteSignAction.blockSignals(True)
            self.deleteSignAction.setChecked(False)
            self.deleteSignAction.blockSignals(False)

        self.componentWidget.setCurrentWidget(self.locationWidget)
        self.componentWidget.tabBar().setVisible(False)
        self.componentsList.setStyleSheet("""QListView{border-style:hidden;}""")
        try:
            self.componentsList.itemDoubleClicked.disconnect(self.componentWidget.locateSymbol)
        except:
            pass
        if self.componentsList.isVisible():
            self.clearParamBtn.setVisible(False)

        self.player.enable()
        self.setEnabled(True)
        self.save_complete = True
        # self.refreshSearchFilter()
        self.otherLeaveEditingMode()
        self.search_dock.setEnabled(True)
        self.search_dlg.setEnabled(True)
        self.search_dlg.comp_search_list.setEnabled(True)
        self.editing = False

    def otherLeaveEditingMode(self):
        self.player.leaveEditingMode()
        self.infoPage.leaveEditingMode()
        self.finder_list.leaveEditingMode()
        self.componentsList.leaveEditingMode()
        self.locationWidget.leaveEditingMode()
        self.componentWidget.leaveEditingMode()
        self.exMediaWidget.leaveEditingMode()
        self.exMediaSelector.leaveEditingMode()

    # def refreshSearchFilter(self):
    #     if hasattr(self, 'search_dlg'):
    #         # print('refresh')
    #         self.search_dlg.onSearch()

    #@pyqtSlot(list)
    def onSignsFound(self, signs):
        if not signs:
            self.stopVideo()
            self.switchFinderPreviewAction.setEnabled(False)
            self.switchFinderPreviewAction.setIcon(QIcon(':/filter.png'))
            self.searchSignsAction.setIcon(QIcon(':/search.png'))
            self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Apply search filter'))
            self.onModelReset({})
        else:
            sign = signs[0]
            if self.last_sign != sign:
                self.last_sign = sign
                if self.finder_list.search_filter:
                    self.switchFinderPreviewAction.setEnabled(True)
                    self.switchFinderPreviewAction.setIcon(QIcon(':/filter_on.png'))
                    self.searchSignsAction.setIcon(QIcon(':/search_on.png'))
                    self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Remove search filter'))
                else:
                    self.switchFinderPreviewAction.setIcon(QIcon(':/filter.png'))
                    self.searchSignsAction.setIcon(QIcon(':/search.png'))
                    self.switchFinderPreviewAction.setToolTip(qApp.instance().translate('MainWindow', 'Apply search filter'))

                self.onModelReset(sign)

                try:
                    if signs and sign.new:
                        self.edit_enable.emit()
                except:
                    pass

                def finish():
                    self.locationWidget.setEnabled(True)
                    try:
                        if signs and sign.new:
                            self.saveSignAction.setEnabled(True)
                            self.deleteSignAction.setEnabled(False)
                    except:
                        pass
                    qApp.processEvents()
                QTimer.singleShot(0, finish)

    #@pyqtSlot()
    def showTranscodeSettings(self):
        if not self.transcode_settings_dock.isVisible():
            settings = qApp.instance().getSettings()
            self.transcode_settings_dock.restoreGeometry(settings.value("MainWindow/TranscodeSettingsDock/Geometry", QByteArray()))
            settings.setValue("MainWindow/TranscodeSettingsDock/Visible", 1)
            self.ensureUsingActiveMonitor(self.transcode_settings_dock)
        self.transcode_settings_dock.show()
        self.transcode_settings_dock.activateWindow()
        self.transcode_settings_dock.show()

    #@pyqtSlot()
    def showSearchDlg(self):
        if not self.search_dlg.isVisible():
            settings = qApp.instance().getSettings()
            default = QSize(600, 400)
            size = settings.value("MainWindow/SearchDock/Size", default)
            geom = settings.value("MainWindow/SearchDock/Geometry", QByteArray())
            self.search_dock.restoreGeometry(geom)
            settings.setValue("MainWindow/SearchDock/Visible", 1)
            self.ensureUsingActiveMonitor(self.search_dock)
            self.handshapeViewGroup.setVisible(True)
            self.photoHelpAction.setVisible(True)
            self.search_dock.show()
            self.search_dlg.show()
            self.search_dock.resize(size)
            self.search_dock.setWindowTitle(qApp.instance().translate('MainWindow', 'Search for Signs'))
            #self.switchFinderPreview()

    #@pyqtSlot()
    def onModelReset(self, sign):
        self.player.load_timer.stop()
        #self.player.Stop()
        self.last_sign = sign
        self.exMediaWidget.onModelReset(None)
        self.exMediaSelector.onModelReset(sign)
        self.infoPage.blockSignals(True) # prevents infoPage from loading media also when first loading sign on reset
        self.infoPage.onModelReset(sign, True)
        self.infoPage.blockSignals(False) # prevents infoPage from loading media also when first loading sign on reset
        self.locationWidget.scene.onModelReset(sign)
        self.componentsList.onModelReset(sign)
        if sign:
            if not sign.new:
                self.editSignAction.setEnabled(True)
            current_widget = self.compInfoStack.currentWidget()
            if current_widget is self.componentWidget:
                self.switchCompAction.setEnabled(False)
                self.switchCompAction.setToolTip('')
                self.switchInfoAction.setEnabled(True)
            else:
                self.switchCompAction.setEnabled(True)
                self.switchInfoAction.setEnabled(False)
                self.switchInfoAction.setToolTip('')
        else:
            self.editSignAction.setDisabled(True)
            self.switchCompAction.setEnabled(False)
            self.switchCompAction.setToolTip('')
            self.switchInfoAction.setEnabled(False)
            self.switchInfoAction.setToolTip('')
        self.player.onModelReset(sign)
        self.player.load_timer.start()

    def onEditTextSettings(self):
        if qApp.instance().pm.projectChanged():
            self.reloadProject()

        _langs = qApp.instance().pm.project.getWrittenLanguageIds() # list of ids
        name = qApp.instance().pm.project.getWrittenLanguageName
        order = qApp.instance().pm.project.getWrittenLanguageOrder
        old_langs = sorted([[_id, name(_id), int(order(_id))] for _id in _langs], key=lambda x: x[0])
        self.finder_list.setFocus()
        able_to_edit = qApp.instance().pm.ableToEdit()

        dlg = EditWrittenLanguageSettingsDlg(languages=_langs, edit=False)
        dlg.resize(dlg.sizeHint())
        if dlg.exec_():
            _langs = dlg.gloss_languages # [id, name, order]
            if _langs:
                self.reloadProject()
                qApp.instance().pm.amendLanguageList(_langs) # update user settings
                if not dlg.save_order_to_file: # revert order to original before writing to file
                    for ol in old_langs:
                        _id = ol[0]
                        _order = ol[2]
                        l = [l for l in _langs if l[0] == _id]
                        if l:
                            l[0][2] = _order
                new_langs = sorted(_langs, key=lambda x: x[0])
                if old_langs != new_langs:
                    qApp.instance().pm.saveProjectDateTime()
                    qApp.instance().pm.updateSignFiles(langs=_langs)

                    qApp.instance().pm.updateProjectFile()
            qApp.instance().pm.setSearchLangId(dlg.getSearchLangId())
            qApp.instance().pm.setSelectedLangIds(dlg.getSelectedLangIds())
            qApp.instance().pm.setLanguages(dlg.gloss_languages)
            qApp.instance().pm.setFontSizes(dlg.getFontSizes())
            qApp.instance().pm.setFontFamilies(dlg.getFontFamilies())
            qApp.instance().pm.setAutoKeyboard(dlg.useAutoKeyboard())
            if able_to_edit:
                keyboards = dlg.getKeyboardLayouts()
                qApp.instance().setKeyboardLayouts(keyboards)
        else:
            qApp.instance().pm.setSearchLangId(dlg.getOrigSearchLangId())
            qApp.instance().pm.setSelectedLangIds(dlg.getOrigSelectedLangIds())
            qApp.instance().pm.setFontSizes(dlg.getOrigFontSizes())
            qApp.instance().pm.setFontFamilies(dlg.getOrigFontFamilies())
            qApp.instance().pm.lang_order_change.emit(qApp.instance().pm.getProjectLangIds())
            qApp.instance().pm.setLanguages(_langs)
        if dlg.acquired_project_lock:
            qApp.instance().pm.checkOtherUsersProjectDateTime()
            qApp.instance().pm.releaseProjectLock()
        if dlg.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock()
        if qApp.instance().pm.edit_widget is dlg:
            qApp.instance().pm.edit_widget = None

        del dlg
        qApp.instance().resetKeyboard()

    def onEditProjectDialects(self):
        #NOTE: available during sign editing
        settings = qApp.instance().getSettings()
        show_focal = settings.value('showFocalDialect', False)
        if qApp.instance().pm.projectChanged():
            self.reloadProject()
        _dialects = qApp.instance().pm.getAllDialects()
        dlg = EditDialectsDlg(None, _dialects)
        dlg.showFocalDialect.connect(self.finder_list.onShowFocalDialect)
        dlg.showFocalDialect.connect(self.infoPage.onAmendProjectDialects)
        if not _dialects:
            dlg.setWindowTitle(qApp.instance().translate('MainWindow', "Add Dialects"))
        if self.editing: # whether or not any dialects are edited, I want any inactivity warning dialogs
            # to rise above this dialog and I want it to close also if SooSL is inactive
            qApp.instance().pm.edit_widget = dlg
        if dlg.exec_():
            qApp.setOverrideCursor(Qt.BusyCursor)
            _dialects = dlg.dialects
            if _dialects:
                self.reloadProject()
                qApp.instance().pm.amendProjectDialectList(_dialects)
                qApp.instance().pm.saveProjectDateTime()
                qApp.instance().pm.updateSignFiles(dialects=_dialects)
                qApp.instance().pm.updateProjectFile()
            qApp.restoreOverrideCursor()
            show_focal = settings.value('showFocalDialect', False)
        # inactivity timer should carry on if sign is being edited
        if self.editing:
            qApp.instance().pm.startInactivityTimer(self)
        if dlg.acquired_project_lock:
            qApp.instance().pm.checkOtherUsersProjectDateTime()
            qApp.instance().pm.releaseProjectLock()
        if dlg.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock()
        if qApp.instance().pm.edit_widget is dlg:
            qApp.instance().pm.edit_widget = None # NOTE: may have already cleared, but to be sure...
        del dlg
        self.onAmendProjectDialects(show_focal)

    #@pyqtSlot(bool)
    def onAmendProjectDialects(self, _bool):
        self.infoPage.onAmendProjectDialects(_bool)
        self.finder_list.refreshList()

    def onEditGramCats(self):
        #NOTE: available during sign editing
        if qApp.instance().pm.projectChanged():
            self.reloadProject()
        all_types = sorted(qApp.instance().pm.project.grammar_categories, key=lambda x:x.name.lower())
        #qApp.processEvents()
        dlg = EditGramCatDlg(None, all_types)
        if self.editing: # whether or not any gram cats are edited, I want any inactivity warning dialogs
            # to rise above this dialog and I want it to close also if SooSL is inactive
            qApp.instance().pm.edit_widget = dlg
        if dlg.exec_():
            types = dlg.gram_cats
            if types:
                self.reloadProject()
                qApp.setOverrideCursor(Qt.BusyCursor)
                qApp.instance().pm.amendGramCatsList(types)
                qApp.instance().pm.saveProjectDateTime()
                qApp.instance().pm.updateSignFiles(gram_cats=types)
                qApp.instance().pm.updateProjectFile()
                qApp.restoreOverrideCursor()
        # inactivity timer should carry on if sign is being edited
        if self.editing:
            qApp.instance().pm.startInactivityTimer(self)
        self.infoPage.onAmendProjectGramCats()
        if dlg.acquired_project_lock:
            qApp.instance().pm.checkOtherUsersProjectDateTime()
            qApp.instance().pm.releaseProjectLock()
        if dlg.acquired_full_project_lock:
            qApp.instance().pm.releaseFullProjectLock()
        if qApp.instance().pm.edit_widget is dlg: #NOTE: may have cleared already, but to be sure
            qApp.instance().pm.edit_widget = None
        del dlg

    def onEditProjectInfo(self):
        message = None
        if qApp.instance().pm.projectChanged():
            self.reloadProject()
        dlg = EditProjectInfoDlg()
        if dlg.exec_():
            message = dlg.currentMessage()
            project_name = dlg.new_name
            sign_language = dlg.new_sign_language
            version_id = dlg.new_version_id
            project_creator = dlg.new_project_creator
            logo_file = dlg.project_logo_filename
            qApp.instance().pm.saveAuthorsMessage(message)
            qApp.instance().pm.saveProjectName(project_name)
            qApp.instance().pm.saveProjectSignLanguage(sign_language)
            qApp.instance().pm.saveProjectVersionId(version_id)
            qApp.instance().pm.saveProjectCreator(project_creator)
            qApp.instance().pm.saveProjectLogo(logo_file)
            qApp.instance().pm.saveProjectDateTime()
            qApp.instance().pm.updateProjectFile()
            self.set_title(project_name)
        # else:
        #     # remove any added
        #     proj_dir = qApp.instance().pm.project.project_dir
        #     logos = glob.glob(f'{proj_dir}/project_logo.*')
        #     new_logo = None
        #     if logos:
        #         new_logo = logos[0].replace('\\', '/')
        #     logos = glob.glob(f'{proj_dir}/old_project_logo.*')
        #     old_logo = None
        #     if logos:
        #         old_logo = logos[0].replace('\\', '/')
        #     if old_logo:
        #         shutil.move(old_logo, new_logo)
        #     else:
        #         os.remove(new_logo)
        if dlg.acquired_project_lock:
            qApp.instance().pm.checkOtherUsersProjectDateTime()
            qApp.instance().pm.releaseProjectLock()
        del dlg

    #@pyqtSlot(bool)
    def onEnableBack(self, _bool):
        if _bool and self.componentWidget.enable_back:
            self.compViewOrderChangeAction.setVisible(True)
        else:
            self.compViewOrderChangeAction.setVisible(False)

    #@pyqtSlot(int, int)
    def onMainSplitterMoved(self, y, idx):
        if self.current_video_size and (idx == 1 or idx == 2):
            width, height = self.current_video_size
            try:
                aspect = float(height/width)
            except:
                pass
            else:
                controls_height = self.player.height() - self.player.MediaFrame.height()
                new_height = aspect * self.player.width() + controls_height
                self.splitterMediaPlayers.moveSplitter(int(new_height), 1)

    def onUpdateSooSL(self):
        #version info should return version number of latest version available
        version_info = qApp.instance().checkForUpdates()
        if version_info == 1: # no available updates; latest version installed
            QMessageBox.information(self, qApp.instance().translate('MainWindow', "Update notice"), """<center><p>{}</p></center>""".format(qApp.instance().translate('MainWindow', 'No updates available.')))
        elif version_info == -1: # error connecting to website
            QMessageBox.information(self, qApp.instance().translate('MainWindow', "Update notice"), """<center><p>{}</p></center>""".format(qApp.instance().translate('MainWindow', "SooSL cannot connect to soosl.net to check for a new version. Most likely you don't have an internet connection, but something else may be blocking the connection.")))
        else:
            dlg = UpdateDlg(None, version_info)
            if dlg.exec_():
                if not qApp.instance().update_success:
                    QMessageBox.information(self, qApp.instance().translate('MainWindow', "Update failed"), "<center><p style='color:red'>{}</p> \
                    <p>{}</p></center>".format(qApp.instance().translate('MainWindow', "Update failed"), qApp.instance().translate('MainWindow', 'Please try again or download from www.soosl.net')))
            else:
                qApp.instance().update_abort = True

    def onSendFeedback(self):
        messagebox = FeedbackBox(self)
        pxm = QPixmap(':/mail.png').scaledToHeight(32, Qt.SmoothTransformation)
        messagebox.setIconPixmap(pxm)
        messagebox.setText("<h3>{}</h3>".format(qApp.instance().translate('MainWindow', 'Feedback for SooSL')))
        messagebox.setInformativeText('<p>{}</p><p>{} <span style="color: blue;">contact@soosl.net</span>'.format(qApp.instance().translate('MainWindow', 'Please send us your feedback on using SooSL; any problems, questions or suggestions.'), \
            qApp.instance().translate('MainWindow', 'Alternatively, use your own email client to send feedback to:')))
        messagebox.setDetailedText(qApp.instance().getUserSystemInfo())
        f = qApp.instance().getFeedbackFile()
        if f:
            with open(f, 'r', encoding='utf-8') as f:
                messagebox.setUserText(f.read())
        messagebox.exec_()

    def onReportError(self):
        if qApp.instance().checkForAccess():
            messagebox = ErrorMessageBox('report', parent=self)
            pxm = QPixmap(':/mail_error.png').scaledToHeight(32, Qt.SmoothTransformation)
            messagebox.setIconPixmap(pxm)
            messagebox.setText("<h3>{}</h3>".format(qApp.instance().translate('MainWindow', 'Report error in SooSL')))
            messagebox.setInformativeText("<p>{}</p>".format(qApp.instance().translate('MainWindow', "Please tell us how you were using SooSL when this error happened.")))
            messages = qApp.instance().getErrorMessages()
            messagebox.setErrorMessages(messages)

            #messagebox.exec_()
            try:
                if not messagebox.exec_() or messagebox.send_complete: # discarding reports or send reports successful: remove files
                    error_log_files = qApp.instance().getOldErrorLogFiles()
                    for f in error_log_files:
                        os.remove(f)
            except:
                pass # no internet
        else:
            error = QErrorMessage(self)
            error.setWindowTitle(qApp.instance().translate('MainWindow', 'Report Error'))
            t1 = qApp.instance().translate('MainWindow', 'No Internet access or SooSL website unavailable')
            t2 = qApp.instance().translate('MainWindow', 'Please connect to the Internet and try again')
            error.showMessage("<p style='color:Red'><b>{}</b></p><p>{}</p>".format(t1, t2))
            self.hideCheckbox(error)
            error.exec_()

    def hideCheckbox(self, widget):
        i = 0
        while True:
            try:
                item = widget.layout().itemAt(i)
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

class MyFileIconProvider(QFileIconProvider):
    def __init__(self):
        super(MyFileIconProvider, self).__init__()
        self.project_dir = None
        filename = qApp.instance().pm.current_project_filename
        if filename:
            self.project_dir = os.path.dirname(filename)

    def icon(self, file_info):
        try:
            if hasattr(file_info, 'filePath') and \
                self.project_dir and \
                os.path.normpath(self.project_dir) == os.path.normpath(file_info.filePath()):
                    icn = QIcon(':/soosl.ico')
                    return icn
            else:
                return super(MyFileIconProvider, self).icon(file_info)
        except:
            return super(MyFileIconProvider, self).icon(file_info)

class MyMessageBox(QMessageBox):
    def __init__(self, _icon, _str, _str2):
        super(MyMessageBox, self).__init__(_icon, _str, _str2)

    def hideEvent(self, evt):
        qApp.processEvents()
        super(MyMessageBox, self).hideEvent(evt)

class ToolsMenu(QMenu):
    def __init__(self, parent):
        super(ToolsMenu, self).__init__(parent)
        self.installEventFilter(self)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

    def eventFilter(self, obj, evt):
        if evt.type() == QEvent.MouseButtonPress:
            action = obj.activeAction()
            if action:
                obj.close()
                action.triggered.emit()
                return True
        elif evt.type() == QEvent.KeyPress \
            and (evt.key() == Qt.Key_Enter \
            or evt.key() == Qt.Key_Space \
            or evt.key() == Qt.Key_Return):
                action = obj.activeAction()
                if action:
                    action.triggered.emit()
                    obj.close()
                    return True
        return super(ToolsMenu, self).eventFilter(obj, evt)

class MyInputDialog(QInputDialog):
    def __init__(self, parent=None):
        super(MyInputDialog, self).__init__(parent=parent, flags=Qt.WindowTitleHint|Qt.WindowSystemMenuHint|Qt.WindowStaysOnTopHint)

    def hideEvent(self, evt):
        qApp.processEvents()
        super(MyInputDialog, self).hideEvent(evt)

class MyMacToolBar(QWidget):
    def __init__(self, parent=None):
        super(MyMacToolBar, self).__init__(parent)
        ##NOTE: for some reason, at least in PyQt5.7.1, the usual QToolbar appears 'doubled' in the frozen app for macOS,
        # so a need for this custom one based on QWidget.
        self.setFixedHeight(36)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
        self.widget_list = []

    # def __setMinWidth(self):
    #     w = sum([w.width() for w in self.widget_list])
    #     self.setMinimumWidth(w)

    def showHideButtons(self):
        for widget in self.widget_list:
            if hasattr(widget, 'defaultAction'):
                action = widget.defaultAction()
                if widget.isVisible() != action.isVisible():
                    widget.setVisible(action.isVisible())

    def paintEvent(self, evt):
        super(MyMacToolBar, self).paintEvent(evt)
        self.showHideButtons()

    def addStretch(self):
        self.layout.addStretch()

    def addSpacing(self, _int):
        self.layout.addSpacing(_int)

    def addAction(self, action, for_group=False):
        btn = QToolButton(self)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setFixedSize(28, 28)
        btn.setIconSize(QSize(28, 28))
        btn.setStyleSheet("""border: none;""")
        btn.setDefaultAction(action)
        self.widget_list.append(btn)
        #self.__setMinWidth()
        if for_group:
            return btn
        self.layout.addWidget(btn)

    def addActionGroupBox(self, actions):
        def _width(action): # QAction|QPushButton
            try:
                return action.width()
            except:
                return 28
        w = sum([_width(a) for a in actions])
        group_box = QGroupBox('')
        group_box.setMinimumWidth(w)
        #group_box.setStyleSheet("QGroupBox{background: qlineargradient( x1:0 y1:0, x2:1 y2:0, stop:0 white, stop:1 gray); border: 2px solid lightgray; border-width: 2px; border-radius: 9px;}")
        group_box.setStyleSheet("QGroupBox{background-color: white; border: 2px solid lightgray; border-width: 2px; border-radius: 9px;}")
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(2, 2, 2, 2)
        hlayout.setSpacing(0)
        for action in actions:
            if isinstance(action, QPushButton):
                btn = action
            else:
                btn = self.addAction(action, True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            hlayout.addWidget(btn)
            hlayout.setAlignment(btn, Qt.AlignLeft | Qt.AlignBottom)
        group_box.setLayout(hlayout)
        self.layout.addWidget(group_box)
        return group_box

    def addWidget(self, widget):
        self.layout.addWidget(widget)

    def addSeparator(self):
        s = QLabel()
        s.setFixedSize(QSize(2, 32))
        s.setStyleSheet("""background-color: lightgray""")
        self.layout.addWidget(s)
        self.widget_list.append(s)
        #self.__setMinWidth()

    ## NOTE: is following needed? don't recall it's reason and cannot see it doing anything?
    def resizeEvent(self, evt):
        w = 2
        for widget in self.widget_list:
            w = w + 2 + widget.width()
            if w < self.width():
                if not widget.isVisible():
                    widget.setVisible(True)
            else:
                if widget.isVisible():
                    widget.setVisible(False)
        return super(MyMacToolBar, self).resizeEvent(evt)

class MyApp(QApplication):
    update_progress = pyqtSignal(int)
    transcode_stats = pyqtSignal(str, str)
    error_signal = pyqtSignal()

    def __init__(self, argv):
        # help for high res displays
        # https://stackoverflow.com/questions/45949661/scale-qt-applications-nicely-with-4k-moniters
        _bool = True
        if sys.platform.startswith('win32'):
            _bool = False
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            self.setAttribute(Qt.AA_EnableHighDpiScaling, _bool)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            self.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        if hasattr(Qt, 'AA_DisableWindowContextHelpButton'):
            self.setAttribute(Qt.AA_DisableWindowContextHelpButton)
        super(MyApp, self).__init__(argv)
        #self.aboutToQuit.connect(self.deleteLater)

        access_check = 0
        if sys.platform.startswith('win32'):
            try:
                access_check = self.win32ControlledFolderAccessCheck()
            except:
                pass

        if sys.platform.startswith('win32') and access_check > 1:
            self.closing = True
            sys.exit()
        else:
            try:
                import vlc
            except:
                import vlc_new as vlc
            if sys.platform.startswith('linux'):
                #plugin_path = "/usr/lib64/vlc/plugins"
                #plugin_path = f'{self.getAppDir()}/plugins'
                #os.environ["VLC_PLUGIN_PATH"] = plugin_path
                os.environ["CRYPTOGRAPHY_OPENSSL_NO_LEGACY"] = "1"
            self.vlc = vlc
            self.startup_time = 0
            self.running_time = 0 # NOTE: for my own testing purposes

            self.closing = False
            self.searchType = 'gloss'
            self._searching = False

            self.setOrganizationName("SIL International")
            self.setOrganizationDomain("sil.org")
            self.setApplicationName("SooSL")
            self.setWindowIcon(QIcon(":/soosl.ico"))

            self.setLayoutDirection(Qt.LayoutDirectionAuto)
            if sys.platform.startswith('darwin'):
                self.ic = NSTextInputContext.currentInputContext()
                if not self.ic:
                    self.ic = NSTextInputContext.new()
            self.startupKeyboard = self.getKeyboard()

            if sys.platform.startswith("win"):
                self.mutexname = "SooSLMutex"
                self.mutex = CreateMutex(None, False, self.mutexname)

    # #     setup some initial directories
            working_dir = self.getWorkingDir()
            temp_dir = self.getTempDir()
            default_projects_dir = self.getDefaultProjectsDir()
            default_import_export_dirs = self.getDefaultImportExportDirs()
            default_media_dir = QDir.homePath()
            old_translations_dir = self.getTranslationsDir()
            new_translations_dir = self.getNewerTranslationDir()

            settings = self.getSettings()

            if sys.platform.startswith('darwin'):
                new_plist = settings.fileName()
                old_plist = os.path.join(os.path.dirname(new_plist), "com.sil-international.SooSL.plist")
                #/Users/<username>/Library/Preferences/com.sil-international.SooSL.plist
                # change of plist in v0.8.3 with addition of setOrganizationDomain("sil.org")
                if os.path.exists(old_plist):
                    old_settings = QSettings(old_plist, QSettings.NativeFormat)
                    keys = old_settings.allKeys()
                    for key in keys:
                        settings.setValue(key, old_settings.value(key))
                    os.remove(old_plist)

            settings.setFallbacksEnabled(False)
            if not os.path.exists(working_dir):
                try:
                    os.makedirs(working_dir)
                except:
                    pass

            if not os.path.exists(temp_dir):
                try:
                    os.makedirs(temp_dir)
                except:
                    pass
            else: # couldn't be removed at close of previous run
                for f in glob.glob("{}/*".format(temp_dir)):
                    try:
                        os.remove(f)
                    except:
                        pass

            if not os.path.exists(default_projects_dir):
                try:
                    os.mkdir(default_projects_dir)
                except:
                    pass

            if not os.path.exists(default_import_export_dirs[0]):
                try:
                    os.mkdir(default_import_export_dirs[0])
                except:
                    pass

            if not os.path.exists(new_translations_dir):
                os.mkdir(new_translations_dir)
                # if os.path.exists(old_translations_dir):
                #     shutil.copytree(old_translations_dir, new_translations_dir)
                #     # try:
                #     #     os.remove(old_translations_dir)
                #     # except:
                #     #     pass
                # else:
                #     os.mkdir(new_translations_dir)

            #settings.setValue("componentView/photoHelp", 1)
            settings.setValue("Version", "{}_{}".format(__version__, __build__))
            settings.setValue("Website", "https://soosl.net")

    #         ## ONE-FILE SETUP???
    #         # if SooSL is "one-file" installation, deal with any setup issues
    #         old_meipass = settings.value('meipass', None)
    #         # if SooSL crashed or aborted, old temp install may still exist
    #         if old_meipass and os.path.exists(old_meipass):
    #             shutil.rmtree(old_meipass)
    #         if hasattr(sys, '_MEIPASS'):
    #             meipass_dir = sys._MEIPASS
    #             pyuca_dir = os.path.join(self.getAppDir(), 'pyuca')
    #             new_pyuca_dir = '{}/{}'.format(meipass_dir, 'pyuca')
    #             try:
    #                 shutil.copytree(pyuca_dir, new_pyuca_dir)
    #             except: # a meipass directory exists on a onedir installation
    #                 pass
    #             else:
    #                 settings.setValue('meipass', meipass_dir)

            # In the case of editing, leaving SooSL unattended while in editing mode could block other networked
            # users from editing; close editing after a period of inactivity to unlock sign and/or dictionary files.
            # 30 minutes seems a good default, but this can be edited manually in the SooSL.ini file, particularly
            # during development and testing. The value here is in minutes; SooSL will convert this to milliseconds
            # for timer use.
            if not settings.value('inactivityTimeoutMinutes', None):
                settings.setValue('inactivityTimeoutMinutes', 30) # minutes
            if not settings.value('inactivityCountdownSeconds', None):
                settings.setValue('inactivityCountdownSeconds', 60) # seconds

            self.setupErrorReporting()

            self.pm = PM()
            try:
                self.pm.removeEmptyImportExportDirectories()
            except:
                pass
            try:
                self.pm.removeEmptyProjectDirectories()
            except:
                pass

            self.pm.updateConfiguration()  #update /Users/<<user>>/Library/Preferences/com.sil-international.SooSL.plist before it may be needed
            try:
                self.pm.cleanTempDir() #remove any tempfiles created by SooSL
            except:
                pass
            try:
                self.pm.cleanExportDir(self.crash_log) #recover from any crashed exports
            except:
                pass
            try:
                self.pm.cleanImport(self.crash_log) #recover from any crashed imports
            except:
                pass

            #self.pm.setupKnownProjectInfo() ##NOTE: into a thread for quicker startup???
            self.update_success = True
            self.update_abort = False

            settings.sync()
            self.translation_dict = self.getTranslationDict()

    def startupMessage(self, text=''):
        msg = self.translate('MyApp', 'SooSL starting... please wait...') + '<br>' + text
        self.startup_widget.showMessage(msg)

    def completeStartup(self):
        mw = self.getMainWindow()
        mw.show()
        settings = self.getSettings()
        first_run = settings.value("FirstRun", 1)
        if int(first_run):
            settings.setValue("FirstRun", 0)
            settings.sync()
            mw.defaultSettings(True)
        QTimer.singleShot(200, mw.show_docks)
        #QTimer.singleShot(200, self.finishStartupLog)
        QTimer.singleShot(200, self.startup_widget.close)

    def win32ControlledFolderAccessCheck(self):
        if sys.platform.startswith("win") and self.win32ControlledFolderAccessEnabled():
            protected_folders = self.win32ProtectedFolders()
            working_folder = self.getWorkingDir()
            msg = ''
            for folder in protected_folders:
                try:
                    # if os.path.commonpath([folder, working_folder]):
                    #     a = qApp.instance().translate('MyApp', "You have 'Controlled folder access' enabled and SooSL needs access to this folder:")
                    #     b = qApp.instance().translate('MyApp', "Allow SooSL through 'Controlled folder access' in 'Settings' to avoid further errors.")
                    #     c = qApp.instance().translate('MyApp', "Application path:")
                    #     msg = f'<b>{a}</b> <span style="color: blue;">{working_folder}</span><br><br>{b} {c} <span style="color: blue;">{sys.executable}</span><br>'
                    #     break
                    ## Alternate message:
                    if os.path.commonpath([folder, working_folder]):
                        a = qApp.instance().translate('MyApp', "You have 'Controlled folder access' enabled on your computer.")
                        b = qApp.instance().translate('MyApp', "SooSL needs access to this folder:")
                        c = qApp.instance().translate('MyApp', "Allow SooSL through 'Controlled folder access' in 'Settings' to avoid further errors.")
                        d = qApp.instance().translate('MyApp', "Application path:")
                        e = qApp.instance().translate('MyApp',  "Then close and restart SooSL.")
                        msg = f'<b>{a}</b><br>{b} <span style="color: blue;">{working_folder}</span><br><br>{c} {d} <span style="color: blue;">{sys.executable}</span><br><br><b>{e}</b>'
                        break
                except ValueError:
                    pass # ValueError: Paths don't have the same drive
                    # this is okay as folder compared will defo not be in the protected folder path
            if msg:
                msg2 = qApp.instance().translate('MyApp', "Continue starting SooSL?")
                msgBox = QMessageBox()
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setWindowIcon(QIcon(':/soosl.ico'))
                msgBox.setTextFormat(Qt.RichText)
                title = qApp.instance().translate('MyApp', "Starting SooSL...")
                msgBox.setWindowTitle(title)
                msgBox.setText(msg)
                msgBox.setInformativeText(msg2)
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                yes_btn, no_btn = msgBox.buttons()
                yes_btn.setIcon(QIcon(":/thumb_up.png"))
                no_btn.setIcon(QIcon(":/thumb_down.png"))
                msgBox.button(QMessageBox.Yes).setText(qApp.instance().translate('Exporter', "Yes"))
                msgBox.button(QMessageBox.No).setText(qApp.instance().translate('Exporter', "No"))
                msgBox.setDefaultButton(QMessageBox.No)
                if msgBox.exec_() == QMessageBox.Yes:
                    return 1 # continue opening SooSL
                return 2 # close SooSL
        return 0

    # def logStartup(self, text):
    #     if self.startup_time < 0:
    #         return
    #     if hasattr(self, 'startup_widget'):
    #         now = time.time()
    #         if self.startup_time == 0:
    #             self.last_time = now
    #             self.startup_time = now
    #         elapsed_time = now - self.last_time
    #         self.last_time = now
    #         self.startupMessage(text)
    #         if text:
    #             with open(self.startup_log, 'a', encoding='utf-8') as f:
    #                 f.write('{} ms\n{} '.format(int(elapsed_time * 1000), text))

    # def logRunning(self, text=None):
    #     running_log = os.path.join(self.getWorkingDir(), 'running.log')
    #     if not os.path.exists(running_log):
    #         open(running_log, 'w', encoding='utf-8').close()
    #     now = time.time()
    #     if not text:
    #         self.running_time = now
    #         self.last_time = now
    #     else:
    #         if self.running_time == 0:
    #             self.last_time = now
    #             self.running_time = now
    #         elapsed_time = now - self.last_time
    #         self.last_time = now
    #         with open(running_log, 'a', encoding='utf-8') as f:
    #             msec = int(elapsed_time * 1000)
    #             msg = '{} ms\n{} '.format(msec, text)
    #             f.write(msg)

    def finishStartupLog(self):
        with open(self.startup_log, 'a', encoding='utf-8') as f:
            f.write('\n\nTotal startup time: {} ms'.format(int((time.time() - self.startup_time) * 1000)))
        self.startup_time = -1

    @pyqtProperty(bool)
    def searching(self):
        return self._searching

    @searching.setter
    def searching(self, value):
        self._searching = value

    @property
    def editing(self):
        mw = self.getMainWindow()
        return mw.editing

    #@property
    def dirty(self): # return True if unsaved sign edits
        mw = self.getMainWindow()
        return mw.dirty()

    def getTranslationDict(self):
        trans_dict = {}
        ## get translation files shipped with installation
        old_dir = self.getTranslationsDir()
        ## get newer translation files already downloaded from website
        new_dir = self.getNewerTranslationDir()
        translator = QTranslator(self)
        for d in [old_dir, new_dir]:
            qm_files = glob.glob(f'{d}/*.qm')
            for f in qm_files:
                translator.load(f)
                lang = os.path.splitext(os.path.basename(f))[0]
                display_name = translator.translate('LanguageSettings', 'language_display_name')
                if display_name == 'language_display_name':
                    display_name = lang # if no name
                else:
                    display_name = f'{lang}  {display_name}'
                f = f.replace('\\', '/')
                timestamp = round(os.path.getmtime(f))
                if d == new_dir and trans_dict.get(display_name, []):
                    old_timestamp = trans_dict.get(display_name)[1]
                    if old_timestamp >= timestamp: # could happen with new release; remove older downloaded translation.
                        os.remove(f)
                        continue
                trans_dict[display_name] = [f, timestamp]
        del translator
        # get newer translation files from website
        web_names = self.getWebTranslationNames()
        for key in web_names.keys():
            if key not in trans_dict.keys() or \
                web_names.get(key)[1] > trans_dict.get(key)[1]:
                    trans_dict[key] = web_names.get(key)
        return trans_dict

    def getAppDir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
#             try:
#                 return sys._MEIPASS # pyinstaller onefile build
#             except:
#                 return os.path.dirname(sys.executable)
        elif __file__:
            return os.path.dirname(__file__)
        else:
            return None

    def getFFmpeg(self):
        app_path = self.getAppDir()
        if sys.platform.startswith('win32'):
#             if not getattr(sys, 'frozen', False):
#                 return 'C:\\Users\\Samuel\\ffmpeg-3.3.1-win32-static\\soosl_ffmpeg.exe'
#                 #return 'C:\\Users\\Samuel\\ffmpeg-3.3.2-win32-static\\soosl_ffmpeg.exe'
            return os.path.join(app_path, 'ffmpeg_win32', 'soosl_ffmpeg.exe')
        elif sys.platform.startswith('darwin'):
            if not getattr(sys, 'frozen', False):
                return os.path.join('/', app_path, 'ffmpeg_macos', 'soosl_ffmpeg')
            return os.path.join(app_path, 'ffmpeg_macos', 'soosl_ffmpeg')
        elif sys.platform.startswith('linux'):
            return 'ffmpeg'
            ##return os.path.join(app_path, 'ffmpeg_linux', 'soosl_ffmpeg')
        else:
            return None

    def getHelpFile(self):
        qApp.setOverrideCursor(Qt.BusyCursor)
        soosl_hlp = f'{self.getDocsDir()}/help/en/index.html'
        new_soosl_hlp = f'{self.getWorkingDir()}/docs/help/en/index.html'
        timestamp = 1.0
        if os.path.exists(soosl_hlp):
            timestamp = round(os.path.getmtime(soosl_hlp))

        if os.path.exists(new_soosl_hlp) and round(os.path.getmtime(new_soosl_hlp)) > timestamp:
            soosl_hlp = new_soosl_hlp  # newer than installed version
            timestamp = round(os.path.getmtime(soosl_hlp))
        elif os.path.exists(new_soosl_hlp): # older than installed version
            help_dir = f'{self.getWorkingDir()}/docs/help/'
            try:
                shutil.rmtree(help_dir) # could happen with a new release installation
            except:
                pass #print('removal failed', new_soosl_hlp)
        # # soosl_hlp now points to the newest help file on system, and timestamp is from this file
        # # check for updated version on website
        #web_help = "https://soosl."

        response = None
        response = self.checkForAccess('help')
        if response:
            web_timestamp = response.info()["Last-Modified"]
            if not web_timestamp:
                web_timestamp = response.info()["Date"]
            web_timestamp = int(datetime.strptime(web_timestamp, "%a, %d %b %Y %H:%M:%S %Z").timestamp())
            if web_timestamp > timestamp:
                #NOTE: message dialog about new help files available ???
                #NOTE: progress dialog required?
                new_dir = os.path.dirname(new_soosl_hlp)
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir)
                response.close()
                # help file download comes as zip archive
                help_zip = f'help/{os.path.basename(os.path.dirname(response.url))}.zip'
                response = self.checkForAccess(help_zip)
                if response:
                    dst_dir = os.path.dirname(os.path.dirname(new_soosl_hlp))
                    tmp_file = f'{qApp.instance().getTempDir()}/help.zip'
                    with open(tmp_file, 'wb') as f:
                        f.write(response.read())
                        archive = ZipFile(tmp_file)
                        archive.extractall(dst_dir)
                        archive.close()
                    os.utime(new_soosl_hlp, (web_timestamp, web_timestamp))
                    qApp.restoreOverrideCursor()
                return new_soosl_hlp

            #for testing, lower current timestamp on help file; comment out test below.
            # print('REMOVE BEFORE RELEASE!!!')
            # try:
            #     os.utime(soosl_hlp, (web_timestamp-1000, web_timestamp-1000))
            # except:
            #     pass

            # test 3746 above; comment out the above test.
            # soosl_hlp = f'{self.getDocsDir()}/help/en/index.html'
            # os.utime(soosl_hlp, (web_timestamp+1000, web_timestamp+1000))

        qApp.restoreOverrideCursor()
        return soosl_hlp

        #NOTE: file is unblocked; following not required but nice to know about...
        # https://stackoverflow.com/questions/20886450/unblock-a-file-in-windows-from-a-python-script
        # try:
        #     os.remove(your_file_path + ':Zone.Identifier')
        # except FileNotFoundError:
        #     # The ADS did not exist, it was already unblocked or
        #     # was never blocked in the first place
        #     pass

    def getDocsDir(self):
        app_dir = self.getAppDir()
        if getattr(sys, 'frozen', False) and sys.platform.startswith('darwin'):
            pth = os.path.join(os.path.dirname(app_dir), "Resources", "docs") #osx app bundle
            pth = pth.replace('\\', '/')
            return pth
        else:
            _dir = os.path.join(app_dir, "docs") #win32 and development
            if sys.platform.startswith('linux') and not os.path.exists(_dir):
                _dir = '/usr/share/soosl/docs'
            return _dir.replace('\\', '/')

    def getTranslationsDir(self):
        app_dir = self.getAppDir()
        if getattr(sys, 'frozen', False) and sys.platform.startswith('darwin'):
            return os.path.join(os.path.dirname(app_dir), "Resources", "translations") #osx app bundle
        else:
            return os.path.join(app_dir, "translations") #win32 and development

    def getNewerTranslationDir(self):
        pth = f'{self.getWorkingDir()}{"/translations"}'
        return pth

    def getNewerHelpDir(self):
        pth = f'{self.getWorkingDir()}{"/help"}'
        return pth

    def getWorkingDir(self):
        pth = os.path.join(QDir.homePath(), "SooSL").replace('\\', '/')
        return pth

    def getTempDir(self):
        _dir = '{}/{}'.format(self.getWorkingDir(), "temp")
        if not os.path.exists(_dir):
            try:
                os.makedirs(_dir)
            except:
                pass
        return _dir

    def getLastProject(self):
        settings = self.getSettings()
        return settings.value("lastOpenedDatabase", None)

    def getLastProjectDir(self):
        last_project = self.getLastProject()
        if last_project:
            return os.path.dirname(os.path.dirname(last_project))
        return ''

    def getDefaultProjectsDir(self):
        return '{}/{}'.format(self.getWorkingDir(), "projects")

    def getDefaultImportExportDirs(self):
        return ['{}/{}'.format(self.getWorkingDir(), "exports")]

    def getComponentImagesDir(self):
        app_dir = self.getAppDir()
        if getattr(sys, 'frozen', False) and sys.platform.startswith('darwin'):
            _dir = os.path.join(os.path.dirname(app_dir), "Resources", "components") #osx app bundle
        else:
            _dir = os.path.join(app_dir, "components") #win32 and development
        return _dir

    def getShortVersion(self):
        return __version__ #self.splitVersion()[0]

    def getLongVersion(self):
        return '{} ({})'.format(__version__, __build__)

    def getProgressDlg(self, title=None):
        progress_dlg = None
        if hasattr(self, 'start_dlg'):
            progress_dlg = self.start_dlg
            return progress_dlg
        mw = self.getMainWindow()
        if mw and mw.progress_dlg: #return existing progress dialog; called during save operation
            progress_dlg = mw.progress_dlg
        elif mw: #return new progress dialog; created at start of save operation
            progress_dlg = ProgressDlg(mw)
            mw.progress_dlg = progress_dlg
            progress_dlg.canceled.connect(mw.abortSave)
            self.pm.save_progress.connect(progress_dlg.onProgress)
        if title:
            progress_dlg.setProgressText(title)
        return progress_dlg

    #@property
    def unreported_errors(self):
        count = len(self.getCrashedCrashLogFiles())
        count = count + len(self.getOldErrorLogFiles())
        if os.path.exists(self.error_log) and os.path.getsize(self.error_log):
            count += 1
        return count

    def setupErrorReporting(self):
        p = psutil.Process()
        user_name = os.path.basename(p.username())
        session_id = f'{user_name}_{p.pid}'
        error_filename = os.path.join(self.getWorkingDir(), f'error-{session_id}.log')
        crash_filename = os.path.join(self.getWorkingDir(), f'crash-{session_id}.log')
        #self.startup_log = os.path.join(self.getWorkingDir(), 'startup.log')
        # with open(error_filename, 'w', encoding='utf-8') as f:
        #     pass # just create file
        self.error_log = error_filename # error log doesn't need to stay open
        try: # crash log needs to remain open
            self.crash_log = open(crash_filename, 'a+', encoding='utf-8')
        except:
            pass
        else:
            try:
                faulthandler.enable(file=self.crash_log, all_threads=True)
            except:
                pass
        #open(self.startup_log, 'w').close()

        #faulthandler.dump_traceback_later(1, True, file=sys.stderr, exit=False)

        #https://pypi.org/project/hanging-threads/
        #monitoring_thread = start_monitoring(seconds_frozen=10, test_interval=100) - default values
        ## NOTE: hnaging threads for testing only? include?
        #self.monitoring_thread = start_monitoring()

    def resetErrorLog(self, file_name=''):
        if not file_name:
            file_name = self.error_log
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write('')
            f.flush()

    def logErrorMessages(self, error_messages):
        # o = []
        # if os.path.exists(self.error_log) and os.path.getsize(self.error_log):
        #     with open(self.error_log, 'r', encoding='utf-8') as f:
        #         o = json.load(f)
        # error_times = []
        # for error in error_messages: # rare case, but prevent duplicates when saving with no internet after send attempt from tools
        #     error_time = error.get('error_message', '')[:20]
        #     print(error_time, error_times)
        #     if error_time not in error_times:
        #         error_times.append(error_time)
        #         o.append(error)
        #     else:
        #         existing_idx = error_times.index(error_time)
        #         existing_error = o[existing_idx]
        #         old_comments = existing_error.get('user_comments')
        #         new_comments = error.get("user_comments")
        #         print('update?', old_comments, ' --> ', new_comments)
        #         if new_comments != old_comments:
        #             existing_error['user_comments'] = new_comments

        with open(self.error_log, 'w', encoding='utf-8') as f:
            json.dump(error_messages, f, sort_keys=False, indent=4, ensure_ascii=False)

    def getErrorMsg(self):
        msg = ''
        with open(self.error_log, encoding='utf-8') as f:
            msg = f.read()
        #self.resetErrorLog(self.error_log)
        return msg

    def getFeedbackMsg(self):
        msg = ''
        with open(self.getFeedbackFile(), 'r', encoding='utf-8') as f:
            msg = f.read()
            msg = '{}\n{}'.format(self.getUserSystemInfo(), msg)
        return msg

    def getErrorMessages(self):
        messages = []
        files = self.getOldErrorLogFiles()
        current_file = self.error_log
        if os.path.exists(current_file) and os.path.getsize(current_file):
            files.append(current_file)
        files.sort(key=lambda x: os.path.getmtime(x))
        files.reverse() # latest file first
        times = []
        for file in files:
            with open(file, 'r', encoding='utf-8') as f:
                _messages = json.load(f)
                _messages.reverse() # latest message first
                for _msg in _messages:
                    time = _msg.get('error_message')
                    user = _msg.get('user_comments')
                    if time not in times: # only keep newest with latest user comments
                        times.append(time)
                        messages.append(_msg)
        return messages

    def getCrashReport(self, crash_log_files):
        report = ''
        for file in crash_log_files:
            with open(file, 'r', encoding='utf-8') as f:
                report = f'{report}\n{f.read()}'
                time_str = datetime.fromtimestamp(os.path.getmtime(file)).strftime("%Y-%m-%d, %H:%M:%S")
                report = f"{time_str}\n{report}"
        return report

    def clearCrashReport(self):
        name = self.crash_log.name
        self.crash_log.close()
        self.crash_log = open(name, 'w+', encoding='utf-8')
        self.crash_log.close()
        self.crash_log = open(name, 'a+', encoding='utf-8')

    def removeLogs(self):
        error_filename = self.error_log
        crash_filename = self.crash_log.name
        self.crash_log.close()
        if os.path.exists(error_filename) and not os.path.getsize(error_filename):
            os.remove(error_filename)
        if os.path.exists(crash_filename) and not os.path.getsize(crash_filename):
            os.remove(crash_filename)

    def getCrashedCrashLogFiles(self):
        # get crash log files for SooSL process crashes
        qdir = QDir(self.getWorkingDir())
        qdir.setFilter(QDir.Files)
        current_entry = os.path.basename(self.crash_log.name) # still alive and not crashed - yet!!!
        log_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if entry.startswith('crash-') and entry != current_entry]
        # log_files = [lf for lf in log_files]# if os.path.getsize(lf)]
        # remove empty files
        _log_files = copy.deepcopy(log_files)
        for lf in _log_files:
            if not os.path.getsize(lf):
                try: # an extra test to prove it really isn't active and owned by another process
                    os.remove(lf)
                except:
                    pass
                log_files.remove(lf) # still want to remove it from list if 0 size

        log_files.sort(key=lambda x: os.path.getmtime(x))
        return log_files

    def getOldErrorLogFiles(self):
        qdir = QDir(self.getWorkingDir())
        qdir.setFilter(QDir.Files)
        current_entry = os.path.basename(self.error_log) # current log and not yet written to
        log_files = [qdir.absoluteFilePath(entry) for entry in qdir.entryList() if entry.startswith('error-') and entry != current_entry]
        # remove empty files
        _log_files = copy.deepcopy(log_files)
        for lf in _log_files:
            if not os.path.getsize(lf):
                try:
                    os.remove(lf)
                except:
                    pass
                log_files.remove(lf)
        log_files.sort(key=lambda x: os.path.getmtime(x))
        return log_files

    def errorLastRun(self, crash_log_files=[], error_log_files=[], feedback_log_file=''):
        settings = self.getSettings()
        crash_report = ''
        if crash_log_files:
            crash_report = self.getCrashReport(crash_log_files)
        if crash_report:
            settings.setValue('ErrorRemind', 1)
            messagebox = ErrorMessageBox('error', parent=self)
            messagebox.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
            messagebox.setIcon(QMessageBox.Warning)
            messagebox.setText("<h3>{}</h3>".format(qApp.instance().translate('MyApp', 'Fatal error in SooSL the last time it was run')))
            messagebox.setInformativeText("<p>{}</p><p>{}</p>".format(qApp.instance().translate('MyApp', "The last time SooSL was running, an error occurred that caused it to crash (close unexpectedly). We don't know how it happened!"), \
                qApp.instance().translate('MyApp', 'Would you help us please with more information? What were you doing or trying to do just before it crashed?')))
            # if not getattr(sys, 'frozen', False): # running from source as developer; I want to see messages in event that SooSL is unresponsive
            #     print('crash', crash_report)
            messagebox.setDetailedText(crash_report)
            try:
                if not messagebox.exec_() or messagebox.send_complete: # discarding reports or send reports successful: remove files
                    for f in crash_log_files: os.remove(f)
            except: # no internet connection (maybe)
                pass
            if not self.checkForAccess(): # no internet connection (definitely!)
                for f in crash_log_files:
                    # error_log_files.append(f)
                    # if saved, crash message will be added to error log, so clear for removal
                    crashed = open(f, 'w+', encoding='utf-8')
                    crashed.close()

        if settings.value('ErrorRemind') and error_log_files:
            errorMsg = QErrorMessage()
            errorMsg.setWindowTitle(qApp.instance().translate('MyApp', 'Report Error'))
            errorMsg.setMinimumSize(480, 180)
            msg1 = qApp.instance().translate('MyApp', 'You have an error report waiting to be sent.')
            msg2 = qApp.instance().translate('MyApp', "Please send us your report by clicking on the blue tool icon.")
            msg3 = qApp.instance().translate('MyApp', "Then click on 'Send Error Report'.")
            errorMsg.showMessage("<h3 style='color:Blue'>{}</h3> \
               <p>{} <img src=':/tools.png' align='middle'></p> \
               <p>{} <img src=':/mail_error.png' align='middle'></p>".format(msg1, msg2, msg3))
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
                            checkbox.setText(qApp.instance().translate('MyApp', 'Remind me when SooSL starts'))
                        i += 1
                    else:
                        break
            errorMsg.exec_()
            if checkbox.isChecked():
                settings.setValue('ErrorRemind', 1)
            else:
                settings.setValue('ErrorRemind', None)

        if settings.value('ErrorRemind') and feedback_log_file:
            errorMsg = QErrorMessage()
            errorMsg.setWindowTitle(qApp.instance().translate('MyApp', 'Send Feedback'))
            errorMsg.setMinimumSize(480, 180)
            msg1 = qApp.instance().translate('MyApp', 'You have a feedback report waiting to be sent.')
            msg2 = qApp.instance().translate('MyApp', "Please send us your report by clicking on the blue tool icon.")
            msg3 = qApp.instance().translate('MyApp', "Then click on 'Send feedback'.")
            errorMsg.showMessage("<h3 style='color:Blue'>{}</h3> \
               <p>{} <img src=':/tools.png' align='middle'></p> \
               <p>{} <img src=':/mail_error.png' align='middle'></p>".format(msg1, msg2, msg3))
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
                            checkbox.setText(qApp.instance().translate('MyApp', 'Remind me when SooSL starts'))
                        i += 1
                    else:
                        break
            errorMsg.exec_()
            if checkbox.isChecked():
                settings.setValue('ErrorRemind', 1)
            else:
                settings.setValue('ErrorRemind', None)
        settings.sync()

    def getUserSystemInfo(self):
        p = psutil.Process()
        info = "\n".join([
            f"SooSL {__version__} ({__build__})",
            f'Username: {p.username()}',
            f'Platform: {platform.platform()}',
            f'Version: {platform.version()}',
            f'Processor: {platform.processor()}\n\n'
            ])
        return info

    # def getLogFile(self):
    #     settings = self.getSettings()
    #     return settings.value('LogFile')

    def getFeedbackFile(self, new=False):
        feedback_file = os.path.join(self.getWorkingDir(), 'feedback.log')
        if new:
            return feedback_file
        elif os.path.exists(feedback_file):
            return feedback_file
        else:
            return ''

    def win32ProtectedFolders(self):
        protected_folders = []
        key_to_read = 'SOFTWARE\\Microsoft\\Windows Defender\\Windows Defender Exploit Guard\\Controlled Folder Access\\ProtectedFolders'
        # https://stackoverflow.com/questions/30932831/winreg-openkey-throws-filenotfound-error-for-existing-registry-keys
        try:
            key = OpenKey(HKEY_LOCAL_MACHINE, key_to_read)
        except:  # FileNotFoundError or OSError?:
            bitness = platform.architecture()[0]
            if bitness == '32bit':
                other_view_flag = KEY_WOW64_64KEY
            elif bitness == '64bit':
                other_view_flag = KEY_WOW64_32KEY
            try:
                key = OpenKey(HKEY_LOCAL_MACHINE, key_to_read, access=KEY_READ | other_view_flag)
            except:  # FileNotFoundError or OSError?:
                '''
                We really could not find the key in both views.
                '''
            else:
                row_count = QueryInfoKey(key)[1]
                for row in range(row_count):
                    protected_folders.append(str(EnumValue(key, row)[0]))
        return protected_folders

    def win32ControlledFolderAccessEnabled(self):
        key_to_read = 'SOFTWARE\\Microsoft\\Windows Defender\\Windows Defender Exploit Guard\\Controlled Folder Access'
        # https://stackoverflow.com/questions/30932831/winreg-openkey-throws-filenotfound-error-for-existing-registry-keys
        # https://www.topbug.net/blog/2020/10/03/catching-filenotfounderror-watch-out/
        try:
            key = OpenKey(HKEY_LOCAL_MACHINE, key_to_read)
        except:  # FileNotFoundError or OSError?:
            bitness = platform.architecture()[0]
            if bitness == '32bit':
                other_view_flag = KEY_WOW64_64KEY
            elif bitness == '64bit':
                other_view_flag = KEY_WOW64_32KEY
            try:
                key = OpenKey(HKEY_LOCAL_MACHINE, key_to_read, access=KEY_READ | other_view_flag)
            except:  # FileNotFoundError or OSError?:
                '''
                We really could not find the key in both views.
                '''
                return 0
            else:
                return QueryValueEx(key, 'EnableControlledFolderAccess')[0]
        else:
            return QueryValueEx(key, 'EnableControlledFolderAccess')[0]

    def getKeyboardName(self, keyboard_id):
        if sys.platform.startswith('win32'):
            hklm = ConnectRegistry(None,  HKEY_LOCAL_MACHINE)
            path = f"SYSTEM\\CurrentControlSet\\Control\\Keyboard Layouts{keyboard_id}"
            try:
                key = OpenKey(hklm, path)
            except:
                return None
            else:
                txt = QueryValueEx(key, "Layout Text")
                if txt:
                    txt = txt[0]
                CloseKey(key)
                return txt
        elif sys.platform.startswith('darwin'):
            return keyboard_id
        elif sys.platform.startswith('linux'):
            try:
                kbd = linux_keyboard.Keyboard()
            except:
                pass
            else:
                return kbd.engine_name(keyboard_id)

    #linux only
    def getAllKeyboardNames(self):
        if not sys.platform.startswith('linux'):
            return
        try:
            kbd = linux_keyboard.Keyboard()
        except:
            pass
        else:
            return kbd.all_engine_names()

    #linux only
    def getKeyboardByName(self, lang, name):
        if not sys.platform.startswith('linux'):
            return
        try:
            kbd = linux_keyboard.Keyboard()
        except:
            pass
        else:
            return kbd.engine_by_name(lang, name)

    def getKeyboard(self, lang_id=None):
        if sys.platform.startswith('win'):
            if not lang_id:
                return win32api.GetKeyboardLayoutName()
            else:
                lang_name = self.pm.getLangName(lang_id)
                settings = self.getSettings()
                key = "{}/{}".format('Keyboards', lang_name)
                value = settings.value(key)
                try:
                    value = value.value()
                except:
                    pass
                try:
                    value = value.value()
                except:
                    pass
                if not value:
                    value = self.startupKeyboard
                return value
        elif sys.platform.startswith('darwin'):
            if not lang_id:
                ic = self.__getIC()
                new_keyboard = ic.selectedKeyboardInputSource()
                return new_keyboard
            else:
                lang_name = self.pm.getLangName(lang_id)
                settings = self.getSettings()
                key = "{}/{}".format('Keyboards', lang_name)
                value = settings.value(key)
                try:
                    value = value.value()
                except:
                    pass
                if not value:
                    value = self.startupKeyboard
                return value
        elif sys.platform.startswith('linux'):
            if not lang_id:
                try:
                    kbd = linux_keyboard.Keyboard()
                except:
                    pass
                else:
                    return kbd.current_keyboard
            else:
                lang_name = self.pm.getLangName(lang_id)
                settings = self.getSettings()
                key = "{}/{}".format('Keyboards', lang_name)
                value = settings.value(key)
                if not value:
                    value = self.startupKeyboard
                return value

    def __getIC(self):
        return self.ic

    def setKeyboardLayouts(self, keyboard_dict):
        for lang_id in keyboard_dict.keys():
            self.__setKeyboardValue(lang_id, keyboard_dict.get(lang_id))

    def __setKeyboardValue(self, lang_id, keyboard):
        settings = self.getSettings()
        #=======================================================================
        # if sys.platform.startswith('win'):
        #=======================================================================
        if isinstance(lang_id, int):
            lang_name = self.pm.getLangName(lang_id)
        else:
            lang_name = lang_id
        key = "{}/{}".format('Keyboards', lang_name)
        settings.setValue(key, str(keyboard))
        settings.sync()

    #@pyqtSlot(int)
    def changeKeyboard(self, lang_id=None):
        settings = self.getSettings()
        if int(settings.value('autoKeyboardSwitchState', Qt.Checked)) != Qt.Checked:
            return

        if hasattr(self, 'mw') and self.mw and self.focusWidget() is self.mw.finder_list.search_box and not lang_id:
            pass #NOTE: this gets to calls from a search_box, sencond call 'None'; why???
        else:
            if lang_id:
                lang_name = self.pm.getLangName(lang_id)
                settings = self.getSettings()
                key = "{}/{}".format('Keyboards', lang_name)
                value = settings.value(key)
                try:
                    value = value.value()
                except:
                    pass
                if not value:
                    value = self.startupKeyboard
            else:
                value = self.startupKeyboard
            if sys.platform.startswith('win'):
                try:
                    win32api.LoadKeyboardLayout(value, 2|1)
                except:
                    pass
            elif sys.platform.startswith('darwin'):
                ic = self.__getIC()
                ic.setValue_forKey_(value, 'selectedKeyboardInputSource')
            elif sys.platform.startswith('linux'):
                try:
                    kbd = linux_keyboard.Keyboard()
                except:
                    pass
                else:
                    keyboard = None
                    value = value.rstrip(']')
                    try:
                        _, keyboard = value.split('[')
                    except:
                        keyboard = value
                    kbd.set_engine(keyboard)

    def resetKeyboard(self):
        if hasattr(self, 'mw') and self.mw and self.focusWidget() is self.mw.finder_list.search_box:
            self.changeKeyboard(self.pm.search_lang_id)
        else:
            self.changeKeyboard()

    def saveFeedback(self, txt):
        with open(self.getFeedbackFile(new=True), 'w', encoding='utf-8') as f:
            f.write(txt)

    def removeFeedback(self):
        try:
            os.remove(self.getFeedbackFile())
        except:
            pass

    def getSettings(self):
        if sys.platform.startswith('darwin'):
            settings = QSettings()
        else:
            settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "SIL", "SooSL")
        #settings.setIniCodec("UTF-8") ## not backwards compatible with < 0.9.4
        return settings

    def getTranscodeSettings(self, values):
        current_settings = []
        settings = self.getSettings()
        settings.sync()
        testing = self.getSettings().value('Testing', '0')
        if str(testing) == '1':
            size = settings.value('Transcoding/current_size', 'medium')
            for v in values:
                if v == 'size':
                    current_settings.append(size)
                elif v == 'crf':
                    current_settings.append(settings.value('Transcoding/{}/crf'.format(size), 23))
                elif v == 'preset':
                    current_settings.append(settings.value('Transcoding/{}/preset'.format(size), 'medium'))
                elif v == 'max_height':
                    current_settings.append(int(settings.value('Transcoding/{}/max_height'.format(size), "576")))
                elif v == 'max_bitrate':
                    current_settings.append(int(settings.value('Transcoding/{}/max_bitrate'.format(size), 50000)))
                elif v == 'max_fps':
                    current_settings.append(settings.value('Transcoding/{}/max_fps'.format(size), '0'))
        else:
            for v in values:
                if v == 'size':
                    current_settings.append('medium')
                elif v == 'crf':
                    current_settings.append(23)
                elif v == 'preset':
                    current_settings.append('medium')
                elif v == 'max_height':
                    current_settings.append(576)
                elif v == 'max_bitrate':
                    current_settings.append(50000)
                elif v == 'max_fps':
                    current_settings.append('0')

        if len(current_settings) == 1:
            return current_settings[0]
        return current_settings

    def cancelUpdate(self):
        self.update_abort = True

    def onUpdateComplete(self, _bool):
        self.update_success = _bool

    def update(self, filename):
        #print(filename)
        filename = os.path.basename(filename)
        self.update_abort = False

        dst_dir = os.path.join(self.getWorkingDir(), "updates")
        os.makedirs(dst_dir, exist_ok=True)

        dst = os.path.join(dst_dir, filename)
        dst_file = io.open(dst, "wb")
        site = f"https://soosl.net/download_update_files.php?f={filename}"
        response = None
        try:
            response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
        except:
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
            except:
                self.update_abort = True
                try:
                    dst_file.close()
                except:
                    pass
        if response:
            cl = response.info()["Content-Length"]
            file_size = 1024*8
            if cl:
                file_size = int(cl)
            block_size = 1024*8
            if block_size > file_size:
                block_size = file_size
            max_blocks = int(file_size / block_size)
            count = 0
            while not self.update_abort and count <= max_blocks:
                block = response.read(block_size)
                dst_file.write(block)
                count += 1
                percent = int(count * 100 / max_blocks)
                self.update_progress.emit(percent)
                qApp.processEvents()
            dst_file.close()
            response.close()

        if self.update_abort:
            if os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
            return

        name = os.path.basename(dst)
        ext = os.path.splitext(name)[1]
        if ext.lower() == '.zip': #versions before 0.8.6 expected zipfiles
            archive = ZipFile(dst)
            name = archive.namelist()[0]
            if sys.platform.startswith("win"):
                archive.extract(name, dst_dir)
            elif sys.platform.startswith("darwin"):
                archive.extractall(dst_dir)
            archive.close()

        updater = os.path.join(dst_dir, name)
        if not os.path.exists(updater):
            self.onUpdateComplete(False)
            return

        if sys.platform.startswith("win"):
            del self.mutex #just to be sure

        try:
            if sys.platform.startswith("win"):
                #os.system("start {}".format(updater))
                #https://stackoverflow.com/questions/7006238/how-do-i-hide-the-console-when-i-use-os-system-or-subprocess-call
                si = subprocess.STARTUPINFO()
                #si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE # default
                subprocess.Popen([updater], startupinfo=si)
            elif sys.platform.startswith("darwin"):
                os.system("open {}".format(updater))
            elif sys.platform.startswith("linux"):
                try:
                    os.system("ubuntu-software --local-filename='{}'".format(updater))
                except:
                    os.system("gnome-software --local-filename='{}'".format(updater))
        except:
            if sys.platform.startswith("win"):
                self.mutexname = "SooSLMutex"
                self.mutex = CreateMutex(None, False, self.mutexname)
            self.onUpdateComplete(False)
            return
        else:
            self.onUpdateComplete(True)
            QTimer.singleShot(0, self.quit)
        return

    def updateMac(self, macos_dir, update_dir):
        def getFiles(folder):
            file_list = []
            for root, dirs, files in os.walk(folder):
                if files:
                    for file in files:
                        full_pth = os.path.join(root, file)
                        file_list.append(full_pth)
            return file_list

        dst_app = os.path.dirname(os.path.dirname(macos_dir))
        files = getFiles(update_dir)
        for file in files:
            dst_file = dst_app + file.split('.update')[1]
            shutil.copy(file, dst_file)
        os.system("{}/Contents/MacOS/soosl".format(dst_app))

    def checkForAccess(self, page=None):
        settings = self.getSettings()
        top_level_url = settings.value("Website")
        site = top_level_url
        response = None
        if page:
            site = f"{site}/{page}"
        HEADERS = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = urlopen(Request(url=site, headers=HEADERS), timeout=5)
        except:
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                response = urlopen(Request(url=site, headers=HEADERS), timeout=5)
            except:
                return None
        return response

    def getWebTranslationNames(self):
        site = f"https://soosl.net/translations.php"
        response = None
        try:
            response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
        except:
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
            except:
                pass
        if response:
            names = response.read().decode('utf-8')
            jsn = json.loads(names)
            return jsn
        return {}

    def updateTranslationFile(self, lang, pth, timestamp):
        trans_dir = self.getNewerTranslationDir()
        ## JIRA SOOS-299
        response = self.checkForAccess()
        if response:
            src = os.path.basename(pth)
            dst = f'{trans_dir}/{src}'
            with open(dst, 'wb') as f:
                site = f"https://soosl.net/download_translation.php?f={src}"
                response = None
                try:
                    response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
                except:
                    ssl._create_default_https_context = ssl._create_unverified_context
                    try:
                        response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
                    except:
                        pass
                if response:
                    f.write(response.read())
                    response.close()
                    os.utime(dst, (timestamp, timestamp))
                    self.translation_dict[lang] = [dst, timestamp]
                    return dst
        return pth

            ##NOTE: for timestamp comparisons to work properly, make sure any initial uploads of current .qm files to the website
            ## at release maintain their timestamps.
            ## Maybe they don't need to be uploaded?
            ## Maybe just clear translations folder on website at release time?
            ## In FileZilla, this can be achieved through: 'Transfer >> preserve timestamps...'
            ## Alternatively, upload files to website and download again to include in release. In this way, the released versions
            ## will be slightly newer than the website versions.

    def checkForUpdates(self):
        response = self.checkForAccess() # no response means error trying to connect to website
        current_version = f'{__version__}_{__build__}'
        if response:
            os = sys.platform
            os_long_name = platform.platform()
            machine = platform.machine()
            #print(platform.uname())
            site = f"https://soosl.net/update_soosl.php?os={os}&os_long_name={os_long_name}&machine={machine}&version={current_version}"
            response = None
            try:
                response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
            except:
                ssl._create_default_https_context = ssl._create_unverified_context
                try:
                    response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
                except:
                    return -1
            if response:
                files = response.read().decode('utf-8').split(',') # return 2 files separated by comma: "update_file,release_note_file"
                if files and len(files) > 1:
                    path = Path(files[0])
                    stem = path.stem
                    file_build = int(re.findall(r"(\d{6})", stem)[0])
                    file_version = stem.split(str(file_build))[0]
                    file_version = re.findall(r"\d+", file_version)
                    file_version = '.'.join(file_version)
                    file_version = f'{file_version}_{file_build}'
                    if self.pm.olderThan(current_version, file_version): # update available
                        release_notes_path = Path(files[1])
                        site = f"https://soosl.net/download_update_files.php?f={release_notes_path.name}"
                        response = None
                        try:
                            response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
                        except:
                            ssl._create_default_https_context = ssl._create_unverified_context
                            try:
                                response = urlopen(Request(url=site, headers={'User-Agent': 'Mozilla/5.0'}), timeout=4)
                            except:
                                return -1
                        if response:
                            release_note_str = response.read().decode('utf-8')
                            update_file = files[0]
                            return [update_file, release_note_str]
                    else:
                        return 1 # same version and build
                else:
                    return 1
        else:
            return -1 # no access for some reason

    def removeTempDir(self):
        tempDir = self.instance().getTempDir()
        if tempDir and os.path.exists(tempDir):
            try:
                shutil.rmtree(tempDir)
            except:
                # some process is still using one of this directories files; just try again
                try:
                    shutil.rmtree(tempDir)
                except:
                    return False # some process is still using one of this directories files
                else:
                    return True
            else:
                return True
            # no real problem; another attempt will be made at startup or close of SooSL

    def getMainWindow(self):
        mw = None
        widgets = [w for w in self.allWidgets() if isinstance(w, MainWindow)]
        if widgets:
            mw = widgets[0]
        return mw

#     ##https://www.scrygroup.com/tutorial/2018-02-06/python-excepthook-logging/
#     def handle_unhandled_exception(self, exc_type, exc_value, exc_traceback):
#         """Handler for unhandled exceptions that will write to the logs"""
#         if issubclass(exc_type, KeyboardInterrupt):
#             # call the default excepthook saved at __excepthook__
#             sys.__excepthook__(exc_type, exc_value, exc_traceback)
#             return
#         self.logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    def excepthook(self, excType, excValue, tracebackobj):
        """
        Global function to catch unhandled exceptions.

        @param excType exception type
        @param excValue exception value
        @param tracebackobj traceback object
        """
        if issubclass(excType, KeyboardInterrupt): ##https://www.scrygroup.com/tutorial/2018-02-06/python-excepthook-logging/
            # call the default excepthook saved at __excepthook__
            sys.__excepthook__(excType, excValue, tracebackobj)
            return
        msg = ''
        if tracebackobj:
            separator = '-' * 90
            timeString = time.strftime("%Y-%m-%d, %H:%M:%S")
            tbinfofile = io.StringIO()
            traceback.print_tb(tracebackobj, None, tbinfofile)
            tbinfofile.seek(0)
            tbinfo = tbinfofile.read()

            errmsg = f'{excType}: \n{excValue}'
            sections = [timeString, separator, errmsg, separator, tbinfo]
            msg = '\n'.join(sections)
        settings = self.getSettings()
        settings.setValue('ErrorRemind', 1)
        settings.sync()

        def _message():
            messagebox = ErrorMessageBox('error', parent=self)
            messagebox.setIcon(QMessageBox.Critical)
            messagebox.setText("<h3>{}</h3>".format(qApp.instance().translate('MyApp', 'Error in SooSL')))
            messagebox.setInformativeText("<p>{}</p><p>{}</p>".format(qApp.instance().translate('MyApp', "An error occurred in SooSL and we don't know how it happened!"), \
                qApp.instance().translate('MyApp', 'Would you help us please with more information? What were you doing or trying to do when the error happened?')))
            if not getattr(sys, 'frozen', False): # running from source as developer; I want to see messages in event that SooSL is unresponsive
                print(msg)
            messagebox.setDetailedText(msg)
            messagebox.exec_()
            self.error_signal.emit()

        dialogs = [w for w in self.allWidgets() if isinstance(w, QDialog)]
        for d in dialogs:
            d.setModal(False) #don't want modal dialogs blocking error dialog
        if issubclass(excType, (PermissionError, FileNotFoundError, OSError)):
            path_not_found = str(excValue).split(':', 1)[1].strip().replace('\\', '/').lstrip("'").rstrip("'")
            title = ' ' #qApp.instance().translate('MyApp', 'Folder not found')
            t1 = qApp.instance().translate('MyApp', 'SooSL cannot perform the requested task.')
            t2 = qApp.instance().translate('MyApp', 'SooSL cannot open the following folder or file:')
            msg = f'<b>{t1}</b><br><br>{t2}<br><span style="color:blue;">{path_not_found}</span><br><br>'
            t3 = qApp.instance().translate('MyApp', 'Maybe the file, folder or network share is read-only?')
            if sys.platform.startswith("win") and self.win32ControlledFolderAccessEnabled():
                protected_folders = self.win32ProtectedFolders()
                for folder in protected_folders:
                    try:
                        if os.path.commonpath([folder, path_not_found]):
                            a = qApp.instance().translate('MyApp', "You have 'Controlled folder access (CFA)' enabled and this folder is protected.")
                            b = qApp.instance().translate('MyApp', "Allow SooSL through 'Controlled folder access' in 'Settings' to avoid further errors.")
                            c = qApp.instance().translate('MyApp',  "Then close and restart SooSL.")
                            t3 = f'{a}<br>{b} ({sys.executable})<br><br><b>{c}</b>'
                            break
                    except ValueError:
                        pass # ValueError: Paths don't have the same drive
                        # this is okay as folder compared will defo not be in the protected folder path
            msg = f'{msg}{t3}<br>'
            QMessageBox.warning(None, title, msg)
        else:
            _message()
        if hasattr(self, 'mw'):
            self.mw.setEnabled(True)

        qApp.restoreOverrideCursor()

    def setupTranslators(self, lang):
        try:
            pth, timestamp = self.translation_dict.get(lang)
        except:
            pass
        else:
            if hasattr(self, 'translator'):
                try:
                    self.removeTranslator(self.translator)
                except:
                    pass
                else:
                    del self.translator

            self.translator = QTranslator(self)
            if not os.path.exists(pth): # probably a translation file on the website; need to download it.
                pth = self.updateTranslationFile(lang, pth, timestamp)
            self.translator.load(pth)
            self.installTranslator(self.translator)

def main():

    # if distributed version, disable Qt messages
    if getattr(sys, 'frozen', False):
        def qt_message_handler(mode, context, message):
            if message:
                pass

        qInstallMessageHandler(qt_message_handler) #may want to see messages during development, but when deployed
#     #os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

    if sys.platform.startswith('darwin'):
        sys.argv.extend(['-graphicssystem', 'raster'])
    elif sys.platform.startswith('win32'):
        sys.argv.extend(["Appname", "--platform", "windows:dpiawareness=0"])

    app = qApp.instance()
    # # https://stackoverflow.com/questions/24041259/python-kernel-crashes-after-closing-an-pyqt4-gui-application
    if not app:
        app = MyApp(sys.argv)

    #app.logStartup()
## commandline interface (cli) - just experimenting for now
#     if sys.platform == 'darwin' and len(sys.argv) > 3 or \
#         sys.platform == 'win32' and len(sys.argv) > 1:
#             from cli import processArgs
#             processArgs(sys.argv)
#
    if not app.closing:
        sys.excepthook = app.excepthook
        #sys.excepthook = app.handle_unhandled_exception
        app.startup_widget = StartupWidget(__version__, __build__)
        app.startup_widget.show()
        # center startup_widget
        settings = qApp.instance().getSettings()
        main_screen = None
        main_screen_pos = settings.value("MainWindow/ScreenPos", None)
        if main_screen_pos:
            main_screen = qApp.screenAt(main_screen_pos)
        if not main_screen:
            main_screen = qApp.instance().primaryScreen()
        frameGm = app.startup_widget.frameGeometry()
        centerPoint = main_screen.geometry().center()
        frameGm.moveCenter(centerPoint)
        app.startup_widget.move(frameGm.topLeft())

        crash_log_files = app.getCrashedCrashLogFiles()
        error_log_files = app.getOldErrorLogFiles()
        feedback_log_file = app.getFeedbackFile()
        if crash_log_files or error_log_files or feedback_log_file:
            app.errorLastRun(crash_log_files, error_log_files, feedback_log_file)
        # try:
        #     if app.unreported_errors():
        #         app.errorLastRun()
        # except:
        #     pass

        def _mainWindow():
            mw = MainWindow()
            if not mw.isVisible():
                update_dir = os.path.join(qApp.instance().getWorkingDir(), "updates")
                try:
                    if os.path.exists(update_dir):
                        shutil.rmtree(update_dir)
                except:
                    pass

            mw.restoreSettings()
            mw.ensureUsingActiveMonitor(qApp.instance().startup_widget)
            mw.ensureUsingActiveMonitor() # in case of using multiple screens
            return mw

        #app.logStartup('checking website for updates')
        update_files = None
        #if not sys.platform.startswith('linux'):
        update_files = app.checkForUpdates()
        if update_files and update_files not in [1, -1]: #no internet or other error
            dlg = UpdateDlg(None, update_files)
            if dlg.exec_() and app.update_success:
                sys.exit()
            else:
                app.update_abort = True
        #app.logStartup('setting up mainWindow')
        mw = _mainWindow()
        app.startup_widget.trans_combo.currentTextChanged.connect(mw.onDisplayLangChange)
        app.startup_widget.startup.connect(mw.initialProjectSelection)
        app.startup_widget.showProjectControls()

        #sys.exit(app.exec_())
        # # https://stackoverflow.com/questions/24041259/python-kernel-crashes-after-closing-an-pyqt4-gui-application
        #app.aboutToQuit.connect(app.error_log.close)
        app.aboutToQuit.connect(app.removeTempDir)
        app.aboutToQuit.connect(app.clearCrashReport)
        app.aboutToQuit.connect(app.removeLogs)

    app.exec_()

# allows me to start soosl by running this module
if __name__ == '__main__':
    main()
