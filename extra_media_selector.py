3
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

import os, sys

from media_object import MediaObject

""" Classes associated with extra materials associated with a sign;
video, still pictures & text """

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import pyqtSignal

from PyQt5.QtGui import QPainter
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import qApp, QWidget, QListWidget, QListWidgetItem,\
    QVBoxLayout
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QHBoxLayout
from project import ExtraMediaFile

class QLabelElidedText(QLabel):
    def __init__(self, parent=None):
        super(QLabelElidedText, self).__init__(parent)
        self.setMinimumWidth(20)

    def paintEvent(self, evt):
        p = QPainter(self)
        text = p.fontMetrics().elidedText(self.text(), Qt.ElideLeft, self.width())
        p.drawText(self.rect(), Qt.AlignCenter, text)

class ExtraMediaSelector(QWidget):
    loadMediaFile = pyqtSignal(MediaObject)
    deletedOverlay = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(ExtraMediaSelector, self).__init__(parent)
        self.setMinimumWidth(20)
        self.new_extra_videos = []
        self.new_extra_pictures = []
        self.deleted_media = []
        self.new_media = []
        self.current_media = None
        self.editing = False

        self.media_list = QListWidget(self)
        self.media_list.setFocusPolicy(Qt.NoFocus)
        self.media_list.setViewMode(QListWidget.IconMode)
        self.media_list.setResizeMode(QListWidget.Adjust)
        self.media_list.setSelectionMode(QListWidget.SingleSelection)
        self.media_list.setWrapping(True)
        self.media_list.setFlow(QListWidget.LeftToRight)
        self.media_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.media_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.media_list.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.media_list.setFixedHeight(20)
        self.media_list.setIconSize(QSize(18, 18))
        self.media_list.setStyleSheet("""QListView{border:0; background:palette(button)}""")
        self.media_list.itemClicked.connect(self.onMediaItemClicked)

        self.file_label = QLabelElidedText()
        self.file_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.file_label.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        self.file_label.hide()
        self.VBoxLayout = QVBoxLayout()
        self.VBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.VBoxLayout.setSpacing(0)
        self.VBoxLayout.insertWidget(2, self.file_label)

        self.addVideoBtn = QPushButton()
        self.addVideoBtn.setFlat(True)
        self.addVideoBtn.hide()
        self.addVideoBtn.setIcon(QIcon(':/add.png'))
        self.addVideoBtn.setToolTip(qApp.instance().translate('ExtraMediaSelector', 'Add media'))
        self.addVideoBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.trashBtn = QToolButton()
        self.trashBtn.setIcon(QIcon(':/trash20.png'))
        self.trashBtn.setToolTip(qApp.instance().translate('ExtraMediaSelector', "Delete media"))
        self.trashBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.trashBtn.setCheckable(True)
        self.trashBtn.setAutoRaise(True)
        self.trashBtn.hide()

        self.ctrl_layout = QHBoxLayout()
        self.ctrl_layout.setSizeConstraint(QHBoxLayout.SetNoConstraint)
        self.ctrl_layout.setContentsMargins(2, 2, 2, 2)
        self.ctrl_layout.setSpacing(0)
        self.ctrl_layout.addWidget(self.media_list, stretch=100)
        self.ctrl_layout.setAlignment(self.media_list, Qt.AlignLeft)

#         self.setupCropWidget()
        self.ctrl_layout.addStretch()

        self.ctrl_layout.addWidget(self.addVideoBtn, stretch=0)
        self.ctrl_layout.setAlignment(self.addVideoBtn, Qt.AlignRight | Qt.AlignTop)
        self.ctrl_layout.addWidget(self.trashBtn, stretch=0)
        self.ctrl_layout.setAlignment(self.trashBtn, Qt.AlignRight | Qt.AlignTop)
        self.addVideoBtn.clicked.connect(self.onAddNewMedia)
        self.trashBtn.toggled.connect(self.onMediaDelete)

        self.VBoxLayout.addLayout(self.ctrl_layout)
        self.setLayout(self.VBoxLayout)

        self.sign_id = None

    def changeEvent(self, evt):
        """Updates gui when gui language changed"""
        if evt.type() == QEvent.LanguageChange:
            self.addVideoBtn.setToolTip(qApp.instance().translate('ExtraMediaSelector', 'Add media'))
            t = qApp.instance().translate('ExtraMediaSelector', "Delete media")
            if self.trashBtn.isChecked():
                t = qApp.instance().translate('ExtraMediaSelector', "Keep media")
            self.trashBtn.setToolTip(t)
        else:
            QWidget.changeEvent(self, evt)

    def __resetList(self):
        pass

    @property
    def media_count(self):
        return self.video_count + self.picture_count

    @property
    def video_count(self):
        return len(self.new_extra_videos)

    @property
    def picture_count(self):
        return len(self.new_extra_pictures)

#     def Stop(self, really_stop=False):
#         """Stop player
#         """
# #         image = '{}/{}'.format(qApp.instance().getWorkingDir(), 'stop.png')
# #         if not os.path.exists(image):
# #             QFile(':/stop.png').copy(image)
# # #         video = '{}/{}'.format(qApp.instance().getWorkingDir(), 'stop.mp4')
# # #         self.load(MediaObject(video))
# #         self.load(MediaObject(image))
#         qApp.processEvents()
#
#         #BUG: avoid stopping for now; often actually stopping causes deadlock; see vlc.py, class MediaReadCb(ctypes.c_void_p)
#         if really_stop:
#             self.MediaPlayer.stop()
#             self.initializePlayer()

    def setDeletedView(self):
        self.file_label.setStyleSheet("""color: red; text-decoration: line-through""")
        text = qApp.instance().translate('ExtraMediaSelector', "Keep media")
        self.trashBtn.setStyleSheet("""background: Red""")
        self.trashBtn.setToolTip(text)
        if not self.trashBtn.isChecked():
            self.trashBtn.blockSignals(True)
            self.trashBtn.setChecked(True)
            self.trashBtn.blockSignals(False)
        self.deletedOverlay.emit(True)

    def setNormalView(self):
        self.file_label.setStyleSheet(None)
        text = qApp.instance().translate('ExtraMediaSelector', "Delete media")
        self.trashBtn.setStyleSheet(None)
        self.trashBtn.setToolTip(text)
        if self.trashBtn.isChecked():
            self.trashBtn.blockSignals(True)
            self.trashBtn.setChecked(False)
            self.trashBtn.blockSignals(False)

        self.deletedOverlay.emit(False)
        self.repaint()

    def setNewView(self):
        self.file_label.setStyleSheet("""color: red""")
        if self.trashBtn.isChecked():
            self.trashBtn.blockSignals(True)
            self.trashBtn.setChecked(False)
            self.trashBtn.setStyleSheet(None)
            self.trashBtn.blockSignals(False)

        self.deletedOverlay.emit(False)
        self.repaint()

    ##!!@pyqtSlot(bool)
    def onMediaDelete(self, _bool):
        if self.current_media:
            current_path = self.current_media.filename
            if _bool:
                self.deleted_media.append(current_path)
                qApp.instance().pm.extraMediaRemoved()
                self.setDeletedView()
                idx = 0
                while True:
                    item = self.media_list.item(idx)
                    if item:
                        if item.media.path == self.current_media.filename:
                            media_icon = QIcon()
                            if self.isVideo(self.current_media.filename):
                                media_icon.addFile(':/video24_deleted.png', mode=QIcon.Normal)
                                media_icon.addFile(':/video24_selected_deleted.png', mode=QIcon.Selected)
                            else:
                                media_icon.addFile(':/picture24_deleted.png', mode=QIcon.Normal)
                                media_icon.addFile(':/picture24_selected_deleted.png', mode=QIcon.Selected)
                            item.setIcon(media_icon)
                        idx += 1
                    else:
                        break
            else:
                if current_path in self.deleted_media:
                    self.deleted_media.remove(current_path)
                qApp.instance().pm.extraMediaAdded()
                self.setNormalView()
                idx = 0
                while True:
                    item = self.media_list.item(idx)
                    if item:
                        if item.media.media_object.filename == self.current_media.filename:
                            media_icon = QIcon()
                            if self.isVideo(self.current_media.filename):
                                media_icon.addFile(':/video24.png', mode=QIcon.Normal)
                                media_icon.addFile(':/video24_selected.png', mode=QIcon.Selected)
                            else:
                                media_icon.addFile(':/picture24.png', mode=QIcon.Normal)
                                media_icon.addFile(':/picture24_selected.png', mode=QIcon.Selected)
                            item.setIcon(media_icon)
                        idx += 1
                    else:
                        break

            self.deletedOverlay.emit(_bool)

    def onDeleteSign(self, _bool):
        self.setDisabled(_bool)
        self.onMediaDelete(_bool)
        if not _bool:
            self.deleted_media = []
#             self.repaint()

    #@pyqtSlot(QListWidgetItem)
    def onMediaItemClicked(self, item):
        # current_media_filename = None
        # if self.current_media:
        #     current_media_filename = self.current_media.filename
        # item_media_path = item.media.path
        # if not self.current_media or item_media_path != current_media_filename:
        #     #self.seek_slider.setValue(0)

        self.media_list.setCurrentItem(item)
        media = item.media
        self.current_media = media.media_object

        filename = media.path
        self.file_label.setText(filename)

        if filename in self.deleted_media:
            self.setDeletedView()
        elif filename in self.new_media:
            self.setNewView()
        else:
            self.setNormalView()

        self.loadMediaFile.emit(media.media_object)

    def isVideo(self, filename):
        if filename:
            return qApp.instance().pm.isVideo(filename)
        return None

    def isPicture(self, filename):
        if filename:
            return qApp.instance().pm.isPicture(filename)
        return None

    def clearMediaList(self):
        item = self.media_list.takeItem(0)
        while item:
            del item
            item = self.media_list.takeItem(0)

    def setupMediaList(self, new_extra_videos, new_extra_pictures):
        for ev in new_extra_videos:
            item = QListWidgetItem(self.media_list)
            media_icon = QIcon()
            media_icon.addFile(':/video24.png', mode=QIcon.Normal)
            media_icon.addFile(':/video24_selected.png', mode=QIcon.Selected)
            item.setIcon(media_icon)
            item.media = ev
            self.media_list.addItem(item)
        for ep in new_extra_pictures:
            item = QListWidgetItem(self.media_list)
            media_icon = QIcon()
            media_icon.addFile(':/picture24.png', mode=QIcon.Normal)
            media_icon.addFile(':/picture24_selected.png', mode=QIcon.Selected)
            item.setIcon(media_icon)
            item.media = ep
            self.media_list.addItem(item)
        self.adjustListSize()
#         self.repaint()

    def resizeEvent(self, evt):
#         if self.media_stack.currentWidget() is self.MediaFrame and self.current_media:
#             self.MediaFrame.repaint()
        super(ExtraMediaSelector, self).resizeEvent(evt)
        self.adjustListSize()

    def adjustListSize(self):
        d = 30
        if self.editing:
            d = 90
        w = self.ctrl_layout.contentsRect().width() - d
        if w > 0:
            self.media_list.setMinimumWidth(w)
            grid_w = 20
            grid_h = 20
            self.media_list.setGridSize(QSize(grid_w, grid_h))
            col_count = self.media_list.width()//grid_w
            row_count = self.media_list.count()//col_count + 1
            new_height = row_count*grid_h
            if new_height != self.media_list.height():
                self.media_list.setFixedHeight(new_height)
            self.media_list.setMinimumWidth(20)

    def clear(self):
        #self.load(None)
        self.file_label.setText(None)
#         self.seek_slider.setValue(0)

    ##!!@pyqtSlot()
    def onProjectClosed(self):
        self.clearMediaList()
        self.editing = False
        self.current_path = None
        self.current_media_type = None
        if self.current_media:
            self.current_media.clear()
        if self.deleted_media:
            self.deleted_media.clear()
        self.sign_id = None
        self.media_index = None
        self.media_size = None #size of current video
        self.dialect_filter = []
        #self.enablePlayControls(False)
        #self.hidePlayerControls()

    def media(self):
        return self.new_extra_videos + self.new_extra_pictures

    def media_filenames(self):
        mf = [m.path for m in self.media()]
        mf.sort()
        return mf

    ##!!@pyqtSlot()
    def onAddNewMedia(self):
        """Open a media file in a MediaPlayer
        """
        mw = qApp.instance().getMainWindow()
        mw.pauseVideo()
        qApp.processEvents()
        filename, texts, case = mw.getMediaFile('ex_media')
        #case 1: do nothing
        #case 2: view existing
        #case 3: use existing
        #case 4: use original
#         if not case:
#             case = 1
        if filename and case in [3, 4]:
            if filename not in self.media_filenames():
                self.new_media.append(filename)
                self.file_label.setText(filename)
                _hash = qApp.instance().pm.getHash(filename)
                project = qApp.instance().pm.project
                media = ExtraMediaFile('', {'id': qApp.instance().pm.getTempId(), 'path': filename, 'hash': _hash})
                media_icon = QIcon()
                media_icon.addFile(':/video24.png', mode=QIcon.Normal)
                media_icon.addFile(':/video24_selected.png', mode=QIcon.Selected)
                if qApp.instance().pm.isPicture(filename):
                    media_icon = QIcon()
                    media_icon.addFile(':/picture24.png', mode=QIcon.Normal)
                    media_icon.addFile(':/picture24_selected.png', mode=QIcon.Selected)
                    media.mediatype = 'ex_picture'
                    self.new_extra_pictures.append(media)
                else:
                    media.mediatype = 'ex_video'
                    self.new_extra_videos.append(media)
                qApp.instance().pm.extraMediaAdded()
                self.trashBtn.setEnabled(True)
                self.setNewView()
                new_item = QListWidgetItem()
                new_item.setIcon(media_icon)
                new_item.media = media
                if media.mediatype == 'ex_picture':
                    self.media_list.addItem(new_item)
                else: # find index of first picture, which is the end of the videos and insert video
                    idx = 0
                    while True:
                        item = self.media_list.item(idx)
                        if not item or item.media.media_object.mediatype == 'ex_picture':
                            break
                        idx += 1
                    self.media_list.insertItem(idx, new_item)
#                     if not self.playBtn.isVisible():
#                         self.playBtn.setVisible(True)
                self.adjustListSize()
                self.onMediaItemClicked(new_item)
            else:
                short = qApp.instance().translate('ExtraMediaSelector', 'Duplicate file')
                long = '<strong>{}</strong><br><br>{}'.format(filename, qApp.instance().translate('ExtraMediaSelector', 'Media file already added to this sign'))
                if filename in self.deleted_media:
                    long = '{}<br>{}'.format(long, qApp.instance().translate('ExtraMediaSelector', 'Media file marked for deletion'))
                qApp.instance().pm.showWarning(short, long)

    def hideEvent(self, evt):
        self.sign_id = None
        super(ExtraMediaSelector, self).hideEvent(evt)

    def onModelReset(self, sign):
        current_media_file = None
        if self.media_list and self.media_list.currentItem():
            current_media_file = self.media_list.currentItem().media.path
        self.clearMediaList()
        self.file_label.setText(None)
        self.new_extra_videos.clear()
        self.new_extra_pictures.clear()
        self.deleted_media.clear()
        extra_media_files = []
        if sign:
            self.sign_id = sign.id
            extra_media_files = [em for em in sign.extra_media_files if os.path.exists(em.path)]
            self.new_extra_videos = [em for em in extra_media_files if qApp.instance().pm.isVideo(em.path)]
            self.new_extra_pictures = [em for em in extra_media_files if qApp.instance().pm.isPicture(em.path)]

        self.setupMediaList(self.new_extra_videos, self.new_extra_pictures)
        self.setNormalView()

    def getSignData(self):
        return {"extraMediaFiles": [{"id":m.id, "path":m.path, "hash":m.hash, "media_object":m.media_object} for m in self.media() if m.path not in self.deleted_media]}

    #@property
    def dirty(self):
        orig_media_filenames = [f.path for f in qApp.instance().pm.sign.extra_media_files]
        orig_media_filenames.sort()
        if self.deleted_media or \
            self.media_filenames() != orig_media_filenames:
            return True
        return False

    def setTrashBtnStyle(self, _bool):
        #True ==> checked; False ==> unchecked
        self.trashBtn.blockSignals(True)
        if _bool:
            self.trashBtn.setStyleSheet("""QToolButton {background: red}""")
            self.trashBtn.setChecked(True)
        else:
            self.trashBtn.setStyleSheet(None)
            self.trashBtn.setChecked(False)
        self.trashBtn.blockSignals(False)

    ##!!@pyqtSlot()
    def enterEditingMode(self):
        self.editing = True
        #self.pauseAtStart()
        self.new_media.clear()
        self.deleted_media.clear()
        self.addVideoBtn.show()
        self.trashBtn.show()
        self.file_label.show()
        self.adjustListSize()
        if hasattr(self, 'movie'):
            self.movie.start()

    ##!!@pyqtSlot()
    def leaveEditingMode(self):
        #qApp.processEvents()
        self.editing = False
#         self.pauseAtStart()
#         self.pause_at_start = False
        self.setEnabled(True)
        self.addVideoBtn.hide()
        self.trashBtn.hide()
        self.file_label.hide()
        self.setTrashBtnStyle(False)
        self.current_media = None
        self.deleted_media.clear()

if __name__ == '__main__':
    from mainwindow import main
    main()
