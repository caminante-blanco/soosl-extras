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
#Video Player adapted from:
    # Qt example for VLC Python bindings
    # Copyright (C) 2009-2010 the VideoLAN team
    #
    # This program is free software; you can redistribute it and/or modify
    # it under the terms of the GNU General Public License as published by
    # the Free Software Foundation; either version 2 of the License, or
    # (at your option) any later version.
    #
    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.
    #
    # You should have received a copy of the GNU General Public License
    # along with this program; if not, write to the Free Software
    # Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.
    #

import sys
import os
import glob
import tempfile
import copy

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QFile

from PyQt5.QtGui import QPalette, QMovie, QTransform
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QColor
from PyQt5.QtGui import QPainter

from PyQt5.QtWidgets import QLabel, QHBoxLayout, QStackedWidget, QSpinBox,\
    QGroupBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QPushButton, QRadioButton
from PyQt5.QtWidgets import QSlider
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QDialog
# if sys.platform == "darwin": # for MacOS
#     from PyQt5.QtWidgets import QMacCocoaViewContainer 

from info_page import InfoPage
from media_object import MediaObject
from media_wrappers import VideoWrapper, PictureWrapper
from extra_media_selector import ExtraMediaSelector
from search_dialog import SearchDlg

class LoadTimer(QTimer):
    def __init__(self, parent=None):
        super(LoadTimer, self).__init__(parent)
        # self.interval = 1 # msec
        # self.duration = 200
        # self.timer = QTimer()
        # self.timer.timeout.connect(self.onTimeout)

    def start(self):
        super(LoadTimer, self).start(1)
        qApp.processEvents()
        QTimer.singleShot(200, self.stop)

    # def stop(self):
    #     self.timer.stop()
    #     super(LoadTimer, self).stop()
    #     qApp.processEvents()

    # def onTimeout(self):
    #     self.stop()
    #     qApp.processEvents()

class QPushButtonElidedText(QPushButton):
    def __init__(self, parent=None):
        super(QPushButtonElidedText, self).__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
    def paintEvent(self, evt):
        icon_width = self.height()
        text_width = self.width() - icon_width
        text_rect = QRect(self.rect().left(), self.rect().top(), text_width, self.height()) 
        icon_rect = QRect(self.rect().right() - icon_width, self.rect().top()+2, icon_width-4, self.height()-4)
        icon_size = QSize(icon_width-4, icon_width-4)
        p = QPainter(self)
        text = p.fontMetrics().elidedText(self.text(), Qt.ElideLeft, text_width)
        p.drawText(text_rect, Qt.AlignLeft|Qt.AlignVCenter, text)
        p.drawPixmap(icon_rect, self.icon().pixmap(icon_size))

class MediaWidget(QLabel):
    def __init__(self, parent):
        super(MediaWidget, self).__init__(parent)
        self.player = parent
        self.setStyleSheet('background-color: white')
        self.setMinimumSize(0, 0)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.player.media_stack)
        layout.setStretchFactor(self.player.media_stack, 1)
        self.setLayout(layout)

    def sizeHint(self):
        if not self.player.current_media:
            return QSize(0, 0)
        else:
            w = self.player.width()
            h = self.player.height()
            if self.player.playerControls.isVisible():
                h = h - self.player.playerControls.height()
            return QSize(int(w), int(h))
        
    # def onStop(self):
    #     self.resize(0, 0)
    #     # w, h = self.width(), self.height()
    #     # self.layout().setContentsMargins(w//2, h//2, w//2, h//2)
        
    # def resizeEvent(self, evt):
    #     super(MediaWidget, self).resizeEvent(evt)
    #     if self.player.media_stack.currentWidget() is self.player.MediaFrame:
    #         self.setWhiteBorders()

    def setWhiteBorders(self):
        if self.player.media_stack.currentWidget() is self.player.MediaFrame:
            w, h = self.width(), self.height()
            try:
                media_widget_aspect = w/h
            except:
                media_widget_aspect = 0
            player_aspect = self.player.current_aspect_ratio
            if not self.player.current_media or not media_widget_aspect:
                w = int(w/2)
                h = int(h/2)
                self.layout().setContentsMargins(w, h, w, h)
            elif media_widget_aspect > player_aspect: #left, right margins
                player_width = player_aspect*h
                border = w - player_width
                b = int(border/2)
                self.layout().setContentsMargins(b, 0, b, 0)
            elif media_widget_aspect < player_aspect: #top, bottm margins
                player_height = w/player_aspect
                border = h - player_height
                b = int(border/2)
                self.layout().setContentsMargins(0, b, 0, b)
            else:
                self.layout().setContentsMargins(0, 0, 0, 0)
        else:
            self.layout().setContentsMargins(0, 0, 0, 0)

class Player(QWidget):
    """A simple Media Player using VLC and Qt
    """
    #media_size_change = pyqtSignal(tuple)
    amendCurrentVideo = pyqtSignal(MediaObject, int, object) #'object' caters for 'list' or 'dict' NOTE:should create
    # overloaded signal/slot or change calling methods
    cropping = pyqtSignal(bool)
    scaling_set = pyqtSignal()
    
    def __init__(self, folder_btn=True, parent=None):
        super(Player, self).__init__(parent)
#         self.pe = qApp.instance().pe
        self.linked_player = None
        self.editing = False
        self.load_flag = True
        self.deleted_sentences = []
        self.current_media = None        
        self.next_media = None
        # self.current_media_size = [0, 0] #size of current video 
        self.current_aspect_ratio = 1.8
        self.current_scale = None
        
        self.idx = 1
        self.dialect_filter = []
        self.PlaybackRate = 1
        """Set up the user interface, signals & slots
        """
        # In this widget, the video will be drawn
        self.MediaFrame = QLabel(self)
        self.MediaFrame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.MediaFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.MediaFrame.setAttribute(Qt.WA_NativeWindow)
        self.MediaFrame.setStyleSheet("QLabel{background-color: white;}")
        #self.MediaFrame.setMinimumSize(10, 10)
        
        self.PictureFrame = QLabel(self)
        self.PictureFrame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.PictureFrame.setStyleSheet("QLabel{background-color: white;}")
        self.PictureFrame.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        #self.PictureFrame.setMinimumSize(10, 10)
        
        self.media_stack = QStackedWidget(self)
        self.media_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.media_stack.addWidget(self.MediaFrame)
        self.media_stack.addWidget(self.PictureFrame)
        
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.valueChanged.connect(self.onSeek)
        self.seek_slider.sliderPressed.connect(self.onSliderPressed)
        
        self.editColor = Qt.red
        if folder_btn:
            self.AddEditMediaBtn = QPushButtonElidedText()
            self.AddEditMediaBtn.setFocusPolicy(Qt.NoFocus)
            self.AddEditMediaBtn.setMinimumWidth(20)
            h = self.AddEditMediaBtn.fontMetrics().height()
            self.AddEditMediaBtn.setMaximumHeight(h*2)
            self.AddEditMediaBtn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            p = self.AddEditMediaBtn.palette()
            self.btnTextColor = p.color(QPalette.ButtonText)
            self.AddEditMediaBtn.hide() #only visible for editing
            self.AddEditMediaBtn.clicked.connect(self.changeCurrentMedia)
            self.AddEditMediaBtn.setIcon(QIcon(':/open_file.png'))

        self.media_widget = MediaWidget(self)
        self.media_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.VBoxLayout = QVBoxLayout()
        self.VBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.VBoxLayout.setSpacing(0)
        # self.VBoxLayout.addWidget(self.media_stack)
        self.VBoxLayout.addWidget(self.media_widget)
        
        self.setupPlayerContols()
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(1, 1, 1, 1)
        hlayout.setSpacing(3)
        hlayout.addWidget(self.playerControls)
        hlayout.addWidget(self.seek_slider)
        self.VBoxLayout.addLayout(hlayout)    
        if folder_btn:
            self.VBoxLayout.addWidget(self.AddEditMediaBtn)
        self.setLayout(self.VBoxLayout)
        ###############################       
        #self.win_id = self.MediaFrame.winId()
        #print('vw', int(self.win_id))
        self.pause_at_start = False
        self.last_pos = 0.0
        
        self.vlcInstance = self.getInstance()
        self.load_timer = LoadTimer(self)
        self.load_timer.timeout.connect(self.onLoadTimerTimeout)        
#         self.setInstance() 
        self.MediaPlayer = self.newPlayer()

    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            self.rate_spinner.setToolTip(qApp.instance().translate('Player', "Playback rate"))
            f = None
            if self.current_media: 
                f = self.current_media.filename
            self.setBtnDisplay(f)
        else:
            QWidget.changeEvent(self, evt)
        
    @property
    def rotation(self):
        try:
            return self.current_media.rotation
        except:
            return 0
    
    @property
    def crop(self):
        if hasattr(self.current_media, 'crop'):
            return self.current_media.crop
        return None 
    
    @property
    def deleted(self):
        if qApp.instance().pm.sign_model.delete_flag or \
            hasattr(self, 'deleted_media') and \
            self.current_media and \
            self.current_media.filename in self.deleted_media:
                return True
        return False
    
    def resizeEvent(self, evt):
        super(Player, self).resizeEvent(evt)
        if self.media_stack.currentWidget() is self.PictureFrame and self.current_media:
            self.loadPicture(self.current_media.filename)
        try:
            self.setScale()
        except:
            pass
        else:
            self.media_widget.setWhiteBorders()
        if hasattr(self, 'deleted_overlay'):
            self.deleted_overlay.setGeometry(self.geometry())
        
    def setupPlayer(self, player):
        event_manager = player.event_manager()
        event_manager.event_attach(qApp.instance().vlc.EventType.MediaPlayerPaused, self.onPlayerPaused)
        event_manager.event_attach(qApp.instance().vlc.EventType.MediaPlayerPlaying, self.onPlayerPlaying)
        event_manager.event_attach(qApp.instance().vlc.EventType.MediaPlayerPositionChanged, self.onPlayerPosChanged)
        event_manager.event_attach(qApp.instance().vlc.EventType.MediaPlayerOpening, self.onPlayerOpening)
  
        player.set_rate(self.PlaybackRate)
        
    def connectToWindow(self, player):
        # the media player has to be 'connected' to the QFrame
        # (otherwise a video would be displayed in it's own window)
        # this is platform specific!
        # you have to give the id of the QFrame (or similar object) to
        # vlc_osx, different platforms have different functions for this
        win_id = self.MediaFrame.winId()
        
        if sys.platform.startswith("linux"): #linux2": # for Linux using the X Server
            _id = int(win_id)
            player.set_xwindow(_id)
        elif sys.platform.startswith("win32"): # for Windows
            player.set_hwnd(win_id)
        elif sys.platform.startswith("darwin"): # for MacOS
            #self.MediaPlayer.set_agl(self.win_id)
#             _id = self.MediaFrame.winId()
            _id = int(win_id)
            player.set_nsobject(_id)
        
    def getInstance(self):
        args = ["--verbose=-1",
                "--ignore-config",
                "--play-and-pause",
                "--no-video-title-show",
                "--quiet"
                ]
        if sys.platform.startswith('darwin'): 
            args.insert(0, "--no-autoscale")  # scaling only appears to be a problem on macos    
            args.insert(3, "--vout=macosx")
        elif sys.platform.startswith('linux'):
            args.insert(3, "--vout=gl")
            
        #filters = "--video-filter=swscale{mode=2}"
        # filters = None
        # if self.crop and self.rotation:
        #     filters = '--video-filter=croppadd:transform'
        # elif self.crop:
        #     filters = '--video-filter=croppadd'
        # elif self.rotation:
        #     filters = '--video-filter=transform'
        # if filters:   
        #     args.append(filters)
        
        # if self.crop:
        #     right, bottom, left, top = self.crop
        #     croptop = top
        #     cropbottom = bottom #self.current_media_size[1] - bottom
        #     cropleft = left
        #     cropright = right #self.current_media_size[0] - right
        #     args.extend(["--croppadd-croptop={}".format(croptop),
        #                  "--croppadd-cropbottom={}".format(cropbottom),
        #                  "--croppadd-cropleft={}".format(cropleft),
        #                  "--croppadd-cropright={}".format(cropright)
        #                  ])
        # if self.rotation:
        #     args.append("--transform-type={}".format((self.rotation * 90)))
        
        return qApp.instance().vlc.Instance(*args)
        
    # def newPlayer(self, media_filename):
    #     self.load_flag = True
    #     if hasattr(self, 'MediaPlayer'): 
    #         self.MediaPlayer.stop()       
    #         self.MediaPlayer.release()
    #         del self.MediaPlayer
        
    #     media = self.vlcInstance.media_new(media_filename)
    #     media.parse()
    #     player = self.vlcInstance.media_player_new()
    #     player.set_media(media)
    #     self.setupPlayer(player)
    #     self.connectToWindow(player)
    #     return player

    def linkControls(self, other_player, _bool): 
        if _bool:             
            self.linked_player = other_player      
            self.playBtn.clicked.connect(other_player.onPlayPauseBtn) 
            self.seek_slider.valueChanged.connect(other_player.seek_slider.setValue)
            self.seek_slider.sliderPressed.connect(other_player.onSliderPressed)
            self.rate_spinner.valueChanged.connect(other_player.rate_spinner.setValue)
        else:         
            self.linked_player = None
            self.playBtn.clicked.disconnect(other_player.onPlayPauseBtn)
            self.seek_slider.valueChanged.disconnect(other_player.seek_slider.setValue)
            self.seek_slider.sliderPressed.disconnect(other_player.onSliderPressed)
            self.rate_spinner.valueChanged.disconnect(other_player.rate_spinner.setValue)

    def newPlayer(self):
        self.load_flag = True
        player = self.vlcInstance.media_player_new()
        self.setupPlayer(player)
        self.connectToWindow(player)
        return player
        
    def onDeleteSign(self, _bool):
        self.onVideoDelete(_bool)
        if _bool:
            color = QColor(self.editColor).name()
            if hasattr(self, 'AddEditMediaBtn'):
                self.AddEditMediaBtn.setStyleSheet("""color: {}; text-decoration: line-through;""".format(color))
        else:
            if hasattr(self, 'AddEditMediaBtn'):
                self.AddEditMediaBtn.setStyleSheet(None)
            self.repaint()
        qApp.processEvents()
        
    def onVideoDelete(self, _bool):
        if self.current_media: 
            self.setDeletedOverlay(_bool)              
            if _bool:
                self.setDeletedView()
            else:
                self.setNormalView()
                
    def setDeletedOverlay(self, _bool):
        if hasattr(self, 'deleted_overlay') and not _bool:
            self.deleted_overlay.close()
            del self.deleted_overlay
        elif hasattr(self, 'deleted_overlay') and _bool:
            self.deleted_overlay.show()
        elif _bool:            
            self.deleted_overlay = QDialog(self)
            self.deleted_overlay.setWindowOpacity(0.4)
            self.deleted_overlay.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.deleted_overlay.setGeometry(self.geometry())
            self.deleted_overlay.setStyleSheet("""background-color: rgba(255, 0, 0, 180)""")
            self.deleted_overlay.show()
            self.deleted_overlay.raise_()
                
    def setDeletedView(self):
        self.pauseAtStart() 
            
    def setNormalView(self):
        if hasattr(self, 'AddEditMediaBtn'):
            self.AddEditMediaBtn.setStyleSheet("""color: Black""")
        # if hasattr(self, 'deleted_overlay'):
        #     self.deleted_overlay.close()
    
    ##!!@pyqtSlot()      
    def onProjectClosed(self):
        #self.play_timer.stop()
        self.editing = False
        self.deleted_sentences.clear()
        self.current_media = None
        self.next_media = None
        # self.current_media_size = [0, 0] #size of current video
        self.current_aspect_ratio = 1.8
        self.idx = 1
        self.dialect_filter = []
        self.enablePlayControls(False)
        self.hidePlayerControls()
        self.Stop()
        
    def pauseAtStart(self):
        # might not exist if network connection lost for networked project
        if hasattr(self, "MediaPlayer") and self.MediaPlayer.is_playing() and \
            (not self.current_media or os.path.exists(self.current_media.filename)):
                self.seek_slider.blockSignals(True)
                self.MediaPlayer.pause()    
                self.MediaPlayer.set_position(0.2)
                self.seek_slider.setValue(0)            
                self.seek_slider.blockSignals(False)
        
    def onModelReset(self, sign):
        self.first_load = 1
        if sign and sign.path:
            media = sign.media_object
            if hasattr(sign, 'selected_video'):
                media = sign.selected_video
            if media:
                self.next_media = media
            else:
                self.next_media = None
            self.onLoadMediaFile(media)
        else:
            self.next_media = None
            self.Stop()
            
        if self.editing:
            self.deleted_sentences.clear()
        self.setNormalView()
        
    def onLoadTimerTimeout(self):
        if self.next_media != self.current_media:
            self.load(self.next_media, start=True)
        try:
            s = self.getScale()                    
        except:
            s = None 
        else: 
            if s and self.media_stack.currentWidget() is self.MediaFrame:
                self.MediaPlayer.video_set_scale(s)
        self.media_widget.setWhiteBorders()
        qApp.processEvents()

    def hidePlayerControls(self):
        for widget in [
            self.playBtn,
            self.rate_spinner,
            self.seek_slider
            ]:
                widget.hide()
                
    def showPlayerControls(self):
        for widget in [
            self.playBtn,
            self.rate_spinner,
            self.seek_slider
            ]:
                widget.show()
            
    def setupPlayerContols(self):
        self.playerControls = QWidget(self)
        controlsLayout = QHBoxLayout()
        controlsLayout.setContentsMargins(0, 0, 0, 0)
        controlsLayout.setSpacing(3)
        self.playerControls.setLayout(controlsLayout)
        self.playerControls.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.playBtn = QPushButton()
        self.playBtn.setFocusPolicy(Qt.NoFocus)
        self.playBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.playBtn.setFlat(True)
        self.playBtn.setIcon(QIcon(':/play.png'))
        self.playBtn.setIconSize(QSize(16, 16))
        controlsLayout.addWidget(self.playBtn)
        self.playBtn.clicked.connect(self.onPlayPauseBtn)
        
        self.rate_spinner = RateSpinBox()
        self.rate_spinner.setFocusPolicy(Qt.NoFocus)
        self.rate_spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rate_spinner.setMaximumWidth(72)
        self.rate_spinner.setMinimum(1)
        self.rate_spinner.setMaximum(4)
        self.rate_spinner.setValue(4)   #setSliderPosition(5)
        self.rate_spinner.setToolTip(qApp.instance().translate('Player', "Playback rate"))
        controlsLayout.addWidget(self.rate_spinner)
        self.rate_spinner.valueChanged.connect(self.setRate)
        self.enablePlayControls(False)
        self.hidePlayerControls()
    
    ##!!@pyqtSlot()     
    def onSliderPressed(self):
        if hasattr(self, "MediaPlayer") and self.MediaPlayer.is_playing():
            self.MediaPlayer.pause()
        if hasattr(self, 'movie') and self.movie.state() == QMovie.Running:
            self.movie.setPaused(True)
        
    def onPlayerPosChanged(self, evt):
        pos = round(self.MediaPlayer.get_position()*100)
        if self.seek_slider:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(pos)
            self.seek_slider.blockSignals(False) 
     
    ##!!@pyqtSlot()    
    def onSeek(self):
        slider = self.sender()
        if hasattr(self, 'movie'):
            try:
                self.movie.jumpToFrame(slider.value())
            except:
                pass
            if qApp.hasPendingEvents():
                qApp.processEvents()
            self.setPxm(self.movie.currentPixmap())
        else:
            try:
                value = float(slider.value()/100)
            except:
                pass
            else:
                self.MediaPlayer.set_position(value)
                self.last_pos = value
                
    ##!!@pyqtSlot()         
    def onPlayPauseBtn(self):
        self.pause_at_start = False
        self.playPause()
        if self.linked_player: #sync players
            player1 = self.MediaPlayer
            player2 = self.linked_player.MediaPlayer
            pos1 = player1.get_position()           
            pos2 = player2.get_position()
            if pos1 != pos2:
                pos = min(pos1, pos2)
                player1.set_position(pos)
                player2.set_position(pos)
        
    def Pause(self):
        if hasattr(self, "MediaPlayer") and self.MediaPlayer.is_playing():
            self.MediaPlayer.pause()

    def playPause(self):
        """Toggle play/pause status
        """ 
        if self.current_media and self.isVideo(self.current_media.filename) and not self.current_media.isGif():                           
            qApp.processEvents()
            if str(self.MediaPlayer.get_state()) == 'State.Ended' or \
                (hasattr(self, 'last_pos') and self.MediaPlayer.get_position() > 0.85): #0.94): # at end
                self.last_pos = 0.0
                _reload = False
                if self.sender() is self.playBtn or self.linked_player:
                    _reload = True
                self.load(self.current_media, start=True, reload=_reload)
                return           
            if self.MediaPlayer.is_playing():
                self.MediaPlayer.pause()
            else:
                self.MediaPlayer.set_rate(self.PlaybackRate)
                # try:
                #     self.setScale()
                # except:
                #     pass
                self.MediaPlayer.play()
                #self.MediaFrame.repaint()
                
        elif hasattr(self, 'movie'):
            state = self.movie.state()
            if state == QMovie.Running:
                self.movie.setPaused(True)
            elif state == QMovie.Paused:
                self.movie.setPaused(False)
            else:
                self.movie.start()
                                            
        #if qApp.hasPendingEvents():
            #qApp.processEvents()
            
    def Stop(self):
        """Stop player
        """ 
        try:
            self.MediaPlayer.stop()
        except:
            pass
        #self.media_widget.resize(0, 0)
        self.media_stack.hide()
        self.PictureFrame.clear()
        self.current_media = None
        self.seek_slider.setValue(0)
        self.seek_slider.setDisabled(True)
        self.playBtn.setIcon(QIcon(':/play.png'))
        self.playBtn.setDisabled(True)

    def getScale(self):
        if not sys.platform.startswith('darwin'):
            return 0 # 0 autoscales, which only appears to be a problem on macos
        self.MediaPlayer.get_media().parse()
        video_width, video_height = self.MediaPlayer.video_get_size(0)
        if not video_height: # will lead to division by 0 error
            return 0
        display_width, display_height = self.width(), self.height() - self.playerControls.height() -4 # fudge factor!
        video_aspect = video_width/video_height
        display_aspect = display_width/display_height
        s = 1
        try:
            if display_aspect > video_aspect: # scale by height
                s = display_height/video_height
            else: # scale by width
                s = display_width/video_width
        except:
            pass
        s = s * qApp.instance().primaryScreen().devicePixelRatio()
        return s
            
    def setScale(self):
        try:
            if self.first_load:
                self.first_load = 0
                #self.scaling_set.emit()
                qApp.processEvents() #events need to be cleared for proper scaling only on first load.
                # self.MediaPlayer.video_set_scale(0) # this just reinstates auto-scaling, which started our problem...
        except:
            #pass
            self.first_load = 0
            qApp.processEvents()
        self.MediaPlayer.video_set_scale(self.getScale())
    
    ##!!@pyqtSlot()         
    def changeCurrentMedia(self):
        mw = qApp.instance().getMainWindow()
        if not self.current_media:
            self.current_media = MediaObject(qApp.instance().pm.sign.media_object.filename, qApp.instance().pm.sign.media_object.mediatype)
        filename, response, associated_texts = mw.changeCurrentMedia(self.current_media.orig_filename, self.current_media.mediatype)
        if filename and response: # no response means change was cancelled
            if self.current_media:
                media = copy.deepcopy(self.current_media)
                media.filename = filename 
                media.append('replace') # just to be sure that the media object is different in some way from the current media in the event
                # that everthing else is the same; such as the case when using an already used video of the same name as the one 
                # you are replacing; can happen! The replacement video may not reload in the player window otherwise.
                media.hash = qApp.instance().pm.getHash(filename)
                self.next_media = media
                self.onLoadMediaFile(media)
                if not associated_texts:
                    associated_texts = {}
                self.amendCurrentVideo.emit(media, response, associated_texts)
    
    ##!!@pyqtSlot(MediaObject)            
    def onLoadMediaFile(self, media_object):        
        if isinstance(self.sender(), (InfoPage, ExtraMediaSelector)):
            self.load_timer.start()
        if media_object:
            self.next_media = media_object
        else:
            self.next_media = None
                
    def disable(self):
        self.load_flag = False
         
    def enable(self):
        self.load_flag = True
        
    def __getIdFromPath(self, pth):
        """path and database filenames should match. If they have been changed (by user?) in the filesystem, they probably still
        contain a unique id in the name which can be used to link with the database entries and keep them in sync. This should
        prevent any update code deleting file thinking its orphaned"""
        _id = None
        if pth.count('_id'):
            root, file_name = os.path.split(pth)
            _id = file_name.split('_id')[-1].split('.')[0]
        return _id
    
    def __getMatchingFilename(self, pth):
        """if a database filename and a filesystem filename differ but still contain
        the same unique id number, then consider them a match"""
        _id = self.__getIdFromPath(pth)
        if _id:
            _dir = os.path.dirname(pth)
            _files = glob.glob('{}{}*_id{}.*'.format(_dir, os.sep, _id))
            if _files:
                return _files[0].replace('\\', '/')
        return None
    
    def isVideo(self, filename):
        if filename:
            return qApp.instance().pm.isVideo(filename)
        return None
    
    def isPicture(self, filename):
        if filename:
            return qApp.instance().pm.isPicture(filename)
        return None
    
    def closeEvent(self, evt):
        self.MediaPlayer.set_media(None)
        self.setDeletedOverlay(False)
        super(Player, self).closeEvent(evt)
        
    def scaledMovieSize(self, movie):
        w, h = QPixmap(movie).width(), QPixmap(movie).height()
        scale = float(w/h)
        new_height = self.PictureFrame.height()
        new_width = new_height * scale
        if new_width > self.PictureFrame.width():
            new_width = self.PictureFrame.width()
            new_height = new_width/scale
        return QSize(int(new_width), int(new_height))
    
    def setPlayerSize(self):
        fh = self.media_stack.height()
        fw = self.media_stack.width()
        sz = QSize(int(fh*self.current_aspect_ratio), int(fh))
        if sz.width() > fw:
            sz = QSize(int(fw), int(fw/self.current_aspect_ratio))
        self.media_widget.resize(sz)
    
    def setPxm(self, pxm):
        if self.rotation:
            trans = QTransform()
            trans.rotate(90 * self.rotation) 
            pxm = pxm.transformed(trans)
        fh = self.PictureFrame.height()
        fw = self.PictureFrame.width()
        pxm = pxm.scaledToHeight(fh, mode=Qt.SmoothTransformation)
        if pxm.width() > fw:
            pxm = pxm.scaledToWidth(fw, mode=Qt.SmoothTransformation)
        self.PictureFrame.setPixmap(pxm)
        
    def setPlayerPxm(self, pxm):
        fh = self.MediaFrame.height()
        fw = self.MediaFrame.width()
        pxm = pxm.scaledToHeight(fh, mode=Qt.SmoothTransformation)
        if pxm.width() > fw:
            pxm = pxm.scaledToWidth(fw, mode=Qt.SmoothTransformation)
        self.MediaFrame.setPixmap(pxm)
        
    def loadPicture(self, filename):
        if filename:
            self.PictureFrame.resize(self.size())
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.svg':
                self.loadSVG(filename)
            else:
                self.setPxm(QPixmap(filename)) 
            
    def loadSVG(self, filename):
        if filename:         
            pxm = QPixmap(filename)
            self.setPxm(pxm)
                
    def loadAnimatedGif(self, filename):
        if filename:
            ##!!@pyqtSlot(int)  
            def onFrameChanged(frame_int):
                self.setPxm(self.movie.currentPixmap())
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(frame_int)
                self.seek_slider.blockSignals(False)
                if frame_int == self.movie.frameCount() - 1:
                    self.movie.stop()
                    
            self.movie = QMovie(filename)
            self.movie.setCacheMode(QMovie.CacheAll)
            self.seek_slider.setRange(0, self.movie.frameCount() - 1)
            self.seek_slider.setEnabled(True)
            self.playBtn.setEnabled(True) 
            self.showPlayerControls()  
            self.movie.frameChanged.connect(onFrameChanged)
            sz = self.scaledMovieSize(filename)
            self.movie.setScaledSize(sz)           
            self.movie.start()   # self.playPause starts movie 
            
    #@property
    def dirty(self):
        if self.current_media and self.current_media.filename != self.current_media.orig_filename:
            return True
        return False 
    
    def playFile(self, filename):
        media = MediaObject(filename)
        self.current_media = None
        self.next_media = media
        self.load_timer.start()
        # self.onLoadMediaFile(media)
        #self.load(media, True, True)
        
    def load(self, media_object, start=False, reload=False):
        _bool = False # only load if _bool is True
        if reload:
            _bool = True
        else:
            try:
                _bool = (media_object.filename != self.current_media.filename)
            except:
                _bool = True # media_object or self.current_media is None
            else:
                if not _bool and media_object: # in case a sign or sentence changed its video:
                    _bool = (media_object.filename != media_object.orig_filename)

        if media_object:
            self.current_media = media_object
        if not _bool:
            return
 
        if hasattr(self, 'movie'):
            self.movie.stop()
            del self.movie
        filename = None
        
        if media_object: 
            filename = media_object.filename
        if filename and not os.path.exists(filename):
            filename = self.__getMatchingFilename(filename)
        if not self.load_flag:
            return
        if filename:  
            self.setCurrentAspectRatio(media_object)          
            media_name = filename           
            if self.isPicture(filename):
                self.media_stack.setCurrentWidget(self.PictureFrame)
                if self.PictureFrame.testAttribute(Qt.WA_NoSystemBackground):               
                    self.PictureFrame.setAttribute(Qt.WA_NoSystemBackground, False)
                self.enablePlayControls(False)
                self.hidePlayerControls()
                #self.setPlayerSize()
                self.loadPicture(filename)
                #self.media_widget.setWhiteBorders()
            else:
                ext = os.path.splitext(filename)[1].lower()
                self.enablePlayControls(True)
                self.showPlayerControls()
                qApp.processEvents()
                if ext == '.gif':
                    #self.MediaPlayer.set_mrl('')
                    self.MediaPlayer.set_media(None)
                    self.media_stack.setCurrentWidget(self.PictureFrame)
                    if not self.PictureFrame.testAttribute(Qt.WA_NoSystemBackground):
                        self.PictureFrame.setAttribute(Qt.WA_NoSystemBackground)
                    self.loadAnimatedGif(filename)
                else: 
                    #self.setPlayerSize()
                    #self.MediaFrame.hide()
                    # self.MediaPlayer = self.newPlayer()
                    self.MediaPlayer.set_mrl(media_name)  
                    self.MediaPlayer.get_media().parse() 
                    self.MediaPlayer.video_set_scale(self.getScale())
                    self.media_widget.setWhiteBorders()    
                    self.seek_slider.setRange(0, 100)
                    self.media_stack.setCurrentWidget(self.MediaFrame)
                if start:
                    #self.setScale() 
                    #self.media_widget.setWhiteBorders()
                    self.MediaPlayer.play()
                    #self.MediaFrame.show()
        else:   
            self.PictureFrame.clear()
            self.current_media = None
            self.enablePlayControls(False)
            self.seek_slider.setEnabled(False)
            self.playBtn.setEnabled(False)
        
        if hasattr(self, 'AddEditMediaBtn') and self.AddEditMediaBtn.isVisible():
            self.setBtnDisplay(filename)

        self.media_stack.show()

    def setCurrentAspectRatio(self, media_object):
        filename = media_object.filename
        m = None
        if self.isPicture(filename):
            m = PictureWrapper(media_object)
        elif self.isVideo(filename):
            m = VideoWrapper(media_object)  
        old_aspect = self.current_aspect_ratio
        if m:
            w, h = m.fsize
            self.current_aspect_ratio = 1.8 # prevent division by zero error
            if h:
                self.current_aspect_ratio = w/h 
        else:
            self.current_aspect_ratio = 1.8
        if self.current_aspect_ratio != old_aspect:
            self.media_widget.adjustSize()
            
    def __isNewSign(self):
        if not qApp.instance().pm.sign.id:
            return True #shouldn't happen, but... default and clear should now set sign_id = 0 instead of None 18/04/13
        sign_id = int(qApp.instance().pm.sign.id)
        if sign_id == 0:
            return True
        return False
            
    def __isNewSentence(self, filename):
        for sense in qApp.instance().pm.sign.senses:
            for sent in sense.sentences:
                if filename == sent.path:
                    return False
        return True
                
    def setBtnDisplay(self, filename=None):              
        text = filename
        tool = qApp.instance().translate('Player', "Click to change video")
        if not filename or not qApp.instance().pm.doesPathExist(filename):
            text = "<< {} >>".format(qApp.instance().translate('Player', "Add video"))
            tool = qApp.instance().translate('Player', "Click to add video")
            if filename:
                text = "<< {} {} >>".format(qApp.instance().translate('Player', "Missing video:"), os.path.basename(filename))
                tool = "{} {}<br><br>{}".format(qApp.instance().translate('Player', "Missing video:"), filename, qApp.instance().translate('Player', "Click to find and add video"))
            if hasattr(self, 'AddEditMediaBtn'):
                self.AddEditMediaBtn.setStyleSheet("""color: {}""".format(QColor(self.editColor).name()))
        elif self.current_media and self.current_media.mediatype == 'sign':
            orig_filename = None
            if qApp.instance().pm.sign and qApp.instance().pm.sign.media_object:
                orig_filename = qApp.instance().pm.sign.media_object.orig_filename
            if filename != orig_filename or self.__isNewSign():
                if hasattr(self, 'AddEditMediaBtn'):
                    self.AddEditMediaBtn.setStyleSheet("""color: {}""".format(QColor(self.editColor).name()))
            else:
                if hasattr(self, 'AddEditMediaBtn'):
                    self.AddEditMediaBtn.setStyleSheet("""color: {}""".format(QColor(self.btnTextColor).name()))
        elif self.current_media and self.current_media.mediatype == 'sent':
            if filename in self.deleted_sentences:
                if hasattr(self, 'AddEditMediaBtn'):
                    self.AddEditMediaBtn.setStyleSheet("""color: {}; text-decoration: line-through;""".format(QColor(self.editColor).name()))
            elif self.current_media.orig_filename != self.current_media.filename or \
                self.__isNewSign() or \
                self.__isNewSentence(filename):
                if hasattr(self, 'AddEditMediaBtn'):
                    self.AddEditMediaBtn.setStyleSheet("""color: {}""".format(QColor(self.editColor).name()))
            else:
                if hasattr(self, 'AddEditMediaBtn'):
                    self.AddEditMediaBtn.setStyleSheet("""color: {}""".format(QColor(self.btnTextColor).name()))
            
        if hasattr(self, 'AddEditMediaBtn'):
            self.AddEditMediaBtn.setText(text)
            self.AddEditMediaBtn.setToolTip(tool)
        
    def enablePlayControls(self, _bool):
        alist = ['playBtn', 'rate_spinner', 'seek_slider']
        for a in alist:
            if hasattr(self, a): 
                getattr(self, a).setEnabled(_bool)
                       
    def onPlayerPaused(self, evt):
        self.playBtn.setIcon(QIcon(':/play.png'))
        self.last_pos = self.MediaPlayer.get_position()
        self.onLoadTimerTimeout()
                
    def onPlayerPlaying(self, evt):
        self.playBtn.setIcon(QIcon(':/pause.png'))
        if self.pause_at_start:
            self.pauseAtStart()
            
    def onPlayerOpening(self, evt):
        self.onLoadTimerTimeout()
            
    ##!!@pyqtSlot()    
    def enterEditingMode(self):
        self.editing = True
        self.deleted_sentences = []
        self.pauseAtStart()
        if hasattr(self, 'AddEditMediaBtn'):
            self.AddEditMediaBtn.show()
        if hasattr(self.current_media, 'filename'):
            self.setBtnDisplay(self.current_media.filename)
        else:
            self.setBtnDisplay(qApp.instance().pm.sign.media_object.filename)
        self.media_widget.setWhiteBorders()
    
    ##!!@pyqtSlot()
    def leaveEditingMode(self):
        self.editing = False
        self.pauseAtStart()
        self.pause_at_start = False
        self.setEnabled(True)
        
        self.deleted_sentences = []
        if hasattr(self, 'AddEditMediaBtn'):
            self.AddEditMediaBtn.hide()
            self.AddEditMediaBtn.setText("<< {} >>".format(qApp.instance().translate('Player', 'Add video')))
            self.AddEditMediaBtn.setStyleSheet(None)
            self.AddEditMediaBtn.repaint()
        try:
            self.MediaFrame.clear()
            self.PictureFrame.clear()
        except:
            pass
        self.setDeletedOverlay(False)
        QTimer.singleShot(0, self.media_widget.setWhiteBorders)
    
    ##!!@pyqtSlot(int)     
    def setRate(self, Rate):
        """Set the play-back rate
        """
        if Rate == 1:
            rate = 0.25
        elif Rate == 2:
            rate = 0.5
        elif Rate == 3:
            rate = 0.75
        elif Rate == 4:
            rate = 1
        self.PlaybackRate = rate
        self.MediaPlayer.set_rate(rate)
        if self.MediaPlayer.is_playing():
            self.MediaPlayer.set_rate(rate)

class RateSpinBox(QSpinBox):   
    def __init__(self, parent=None):
        super(RateSpinBox, self).__init__(parent)
        self.setWrapping(True)
        
    def textFromValue(self, value):
        rate = 0
        if value == 1:
            rate = 0.25
        elif value == 2:
            rate = 0.5
        elif value == 3:
            rate = 0.75
        elif value == 4:
            rate = 1
        return ("%s x" % rate)
            
if __name__ == '__main__':
    from mainwindow import main
    main()