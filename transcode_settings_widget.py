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
# import os
import sys
import io

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot

from PyQt5.QtWidgets import QPushButton, QSpinBox, QComboBox,\
    QTextEdit, QHBoxLayout, QFileDialog, QRadioButton, QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import qApp
from media_wrappers import VideoWrapper as Video
from media_object import MediaObject

class TranscodeSettingsWidget(QWidget):
    """Dialog used for setting transcoding options"""

    def __init__(self, get_settings, parent=None):
        super(TranscodeSettingsWidget, self).__init__(parent=parent)
        self.setWindowTitle('Transcode Settings')
        #self.setModal(False)
        flags = self.windowFlags()
        self.setWindowFlags(flags | Qt.Tool)# | Qt.WindowStaysOnTopHint)

        current_size, \
        crf_value, \
        preset_value, \
        frame_height_value, \
        max_bitrate_value, \
        max_framerate_value = self.get_settings(['size', 'crf', 'preset', 'max_height', 'max_bitrate', 'max_fps'])

        layout = QVBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)

        hlayout = QHBoxLayout()
        btn_super = QRadioButton('Super')
        btn_large = QRadioButton('Large')
        btn_medium = QRadioButton('Medium')
        btn_small = QRadioButton('Small')
        for btn in [btn_super, btn_large, btn_medium, btn_small]:
            hlayout.addWidget(btn)
            if btn.text().lower() == current_size:
                btn.setChecked(True)
            btn.clicked.connect(self.onSizeChanged)
        layout.addLayout(hlayout)

        self.super_label = QLabel('Copy original file')
        layout.addWidget(self.super_label)

        hlayout = QHBoxLayout()
        self.crf_control = QSpinBox()
        self.crf_control.setFixedWidth(90)
        self.crf_control.setRange(0, 51)
        self.crf_control.setValue(int(crf_value))
        self.crf_control.valueChanged.connect(self.onCRFChanged)
        hlayout.addWidget(self.crf_control)
        hlayout.addWidget(QLabel('CRF (Constant rate factor)'))
        layout.addLayout(hlayout)

        text = """<p>The range of the scale is 0-51: where 0 is lossless, 23 is default, and 51 is worst possible.
        A "sane" range is probably 18-28, with 18 considered to be visually lossless or nearly so.
        Increasing the CRF value +6 is roughly half the bitrate while -6 is roughly twice the bitrate.</p>"""
        self.crf_control.setToolTip(text)

        hlayout = QHBoxLayout()
        self.preset_control = QComboBox()
        self.preset_control.setFixedWidth(90)
        self.preset_control.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_control.setCurrentText(preset_value)
        self.preset_control.currentTextChanged.connect(self.onPresetChanged)
        hlayout.addWidget(self.preset_control)
        hlayout.addWidget(QLabel('Preset'))
        layout.addLayout(hlayout)

        text = """<p>A preset is a collection of options that will provide a certain encoding speed to compression ratio.
        A slower preset will provide better compression (compression is quality per filesize).
        The general guideline is to use the slowest preset that you have patience for.</p>"""
        self.preset_control.setToolTip(text)

        hlayout = QHBoxLayout()
        self.frame_height_control = QComboBox()
        self.frame_height_control.setFixedWidth(90)
        self.frame_height_control.addItems(["192", "240", "288", "336", "384", "432", "480", "576", "640", "720", "1080"])
        self.frame_height_control.setCurrentText('{}'.format(frame_height_value))
        self.frame_height_control.currentTextChanged.connect(self.onFrameHeightChanged)
        hlayout.addWidget(self.frame_height_control)
        hlayout.addWidget(QLabel('Maximum frame height (pixels)'))
        layout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        self.max_bitrate_control = QSpinBox()
        self.max_bitrate_control.setFixedWidth(90)
        self.max_bitrate_control.setRange(500, 50000)
        self.max_bitrate_control.setSingleStep(500)
        self.max_bitrate_control.setValue(int(max_bitrate_value))
        self.max_bitrate_control.valueChanged.connect(self.onBitrateChanged)
        hlayout.addWidget(self.max_bitrate_control)
        hlayout.addWidget(QLabel('Maximum bitrate (kbits/s)'))
        layout.addLayout(hlayout)

        hlayout = QHBoxLayout()
        self.max_framerate_control = QSpinBox()
        self.max_framerate_control.setFixedWidth(90)
        self.max_framerate_control.setRange(0, 100)
        self.max_framerate_control.setValue(int(max_framerate_value.rstrip('v').rstrip('c')))
        #self.max_framerate_control.setValue(int(max_framerate_value))
        self.max_framerate_control.valueChanged.connect(self.onFramerateChanged)
        #hlayout.addSpacing(7)
#         hlayout.addWidget(self.max_framerate_control)
#         hlayout.addStretch()
        hlayout.addWidget(self.max_framerate_control)
        hlayout.addWidget(QLabel('Frame rate (f/s)'))
        layout.addLayout(hlayout)

        self.max_framerate_control.setToolTip('Set a constant frame rate. Set to 0 if you wish to keep original frame rate.')

        max_framerate_value = str(max_framerate_value)


        self.stats_edit = QTextEdit()
        self.stats_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.stats_edit.setWordWrap(True)
        layout.addWidget(self.stats_edit)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(7)
        btn = QPushButton('Clear log')
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn2 = QPushButton('Export log to file')
        btn2.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn2.clicked.connect(self.onExportLog)
        hlayout.addWidget(btn)
        hlayout.addWidget(btn2)
        hlayout.addStretch()
        layout.addLayout(hlayout)

        btn.clicked.connect(self.stats_edit.clear)

        #layout.addStretch()
        self.setLayout(layout)

        if current_size == 'super':
            self.showOptions(False)
            self.super_label.setHidden(False)
        else:
            self.showOptions(True)
            self.super_label.setHidden(True)
            crf, preset, height, bitrate, fps = self.get_settings(['crf', 'preset', 'max_height', 'max_bitrate', 'max_fps'])
            self.crf_control.setValue(int(crf))
            self.preset_control.setCurrentText(preset)
            self.frame_height_control.setCurrentText('{}'.format(height))
            self.max_bitrate_control.setValue(int(bitrate))

    def get_settings(self, values):
        return qApp.instance().getTranscodeSettings(values)

    ##!!@pyqtSlot()
    def onSizeChanged(self):
        btn = self.sender()
        current_size = btn.text().lower()
        settings = qApp.instance().getSettings()
        settings.setValue('Transcoding/current_size', current_size)
        settings.sync()
        if current_size == 'super':
            self.showOptions(False)
            self.super_label.setHidden(False)
        else:
            self.showOptions(True)
            self.super_label.setHidden(True)
            crf, preset, height, bitrate, fps = self.get_settings(['crf', 'preset', 'max_height', 'max_bitrate', 'max_fps'])
            self.crf_control.setValue(int(crf))
            self.preset_control.setCurrentText(preset)
            self.frame_height_control.setCurrentText('{}'.format(height))
            self.max_bitrate_control.setValue(int(bitrate))

            #fps = str(fps)
#             if fps.startswith('0'):
#                 self.btn_unset.setChecked(True)
#                 self.max_framerate_control.setDisabled(True)
#                 self.max_framerate_box.setTitle('Framerate (fps)')
#             elif fps.endswith('v'):
#                 self.btn_vrate.setChecked(True)
#                 self.max_framerate_control.setDisabled(False)
#                 self.max_framerate_box.setTitle('Maximum framerate (fps)')
#             elif fps.endswith('c'):
#                 self.btn_crate.setChecked(True)
#                 self.max_framerate_control.setDisabled(False)
#                 self.max_framerate_box.setTitle('Framerate (fps)')

            #self.max_framerate_control.setValue(int(fps.rstrip('c').rstrip('v')))
            self.max_framerate_control.setValue(int(fps))

    def showOptions(self, _bool):
        layout = self.layout()
        for child in layout.children():
            count = child.count()
            for idx in range(count):
                w = child.itemAt(idx).widget()
                if w and not isinstance(w, (QPushButton, QRadioButton)):
                    w.setVisible(_bool)

    ##!!@pyqtSlot(str)
    def onFrameHeightChanged(self, height_value):
        settings = qApp.instance().getSettings()
        current_size = self.get_settings(['size'])
        settings.setValue('Transcoding/{}/max_height'.format(current_size), height_value)
        settings.sync()

    ##!!@pyqtSlot(int)
    def onBitrateChanged(self, bitrate_value):
        settings = qApp.instance().getSettings()
        current_size = self.get_settings(['size'])
        settings.setValue('Transcoding/{}/max_bitrate'.format(current_size), bitrate_value)
        settings.sync()

    ##!!@pyqtSlot(int)
    def onFramerateChanged(self, fps_value):
        settings = qApp.instance().getSettings()
        current_size = self.get_settings(['size'])
#         if self.btn_crate.isChecked():
#             fps_value = '{}c'.format(fps_value)
#         elif self.btn_vrate.isChecked():
#             fps_value = '{}v'.format(fps_value)
#         elif self.btn_unset.isChecked():
#             fps_value = '0'
        settings.setValue('Transcoding/{}/max_fps'.format(current_size), fps_value)
        settings.sync()

#     def onFpsBtnClicked(self):
#         current_size, max_fps = self.get_settings(['size', 'max_fps'])
#         settings = qApp.instance().getSettings()
#         if self.btn_unset.isChecked():
#             max_fps = '0'
#             self.max_framerate_control.setDisabled(True)
#             self.max_framerate_box.setTitle('Framerate (fps)')
#         elif self.btn_vrate.isChecked():
#             max_fps = '{}v'.format(max_fps.rstrip('c'))
#             self.max_framerate_control.setDisabled(False)
#             self.max_framerate_box.setTitle('Maximum framerate (fps)')
#         elif self.btn_crate.isChecked():
#             max_fps = '{}c'.format(max_fps.rstrip('v'))
#             self.max_framerate_control.setDisabled(False)
#             self.max_framerate_box.setTitle('Framerate (fps)')
#         settings.setValue('Transcoding/{}/max_fps'.format(current_size), max_fps)
#         settings.sync()

    ##!!@pyqtSlot(int)
    def onCRFChanged(self, crf_value):
        settings = qApp.instance().getSettings()
        current_size = self.get_settings(['size'])
        settings.setValue('Transcoding/{}/crf'.format(current_size), crf_value)
        settings.sync()

    ##!!@pyqtSlot(str)
    def onPresetChanged(self, preset_text):
        settings = qApp.instance().getSettings()
        current_size = self.get_settings(['size'])
        settings.setValue('Transcoding/{}/preset'.format(current_size), preset_text)
        settings.sync()

    ##!!@pyqtSlot(str, str)
    def showStats(self, src_file, dst_file):
        video = Video(MediaObject(src_file, None))

        src_file_size = video.info_dict.get('size', '???')
        src_width = video.info_dict.get('fwidth', '???')
        src_height = video.info_dict.get('fheight', '???')
        src_duration = video.info_dict.get('duration', '???')
        src_bitrate = video.info_dict.get('bitrate', '???')
        src_fps = video.info_dict.get('fps', '???')

        video = Video(MediaObject(dst_file, None))

        dst_file_size = video.info_dict.get('size', '???')
        dst_width = video.info_dict.get('fwidth', '???')
        dst_height = video.info_dict.get('fheight', '???')
        dst_duration = video.info_dict.get('duration', '???')
        dst_bitrate = video.info_dict.get('bitrate', '???')
        dst_fps = video.info_dict.get('fps', '???')

        percent_change = '???'
        try:
            percent_change = round(dst_file_size/src_file_size*100, 1)
        except:
            pass

        current_size, crf_value, preset_value, height, bitrate, fps = self.get_settings(['size', 'crf', 'preset', 'max_height', 'max_bitrate', 'max_fps'])
        if current_size == 'super':
            crf_value, preset_value = None, None
        if str(fps).startswith('0'):
            fps = 'unset'

        first_line = """<p><b>{}</b><br>{} (crf={}, preset={}, max height={}, max bitrate={}, fps={})</p>""".format(src_file, current_size.capitalize(), crf_value, preset_value, height, bitrate, fps)
        if current_size == 'super':
            first_line = """<p><b>{}</b><br>Super (Copy of original file)</p>""".format(src_file)

        text = """{}
        <table width="400">
        <tr><td>&nbsp;</td><td><b>Before</b></td><td><b>After</b></td></tr>
        <tr><td>File size:</td><td>{} KB</td><td>{} KB</td></tr>
        <tr><td>Percent of original size:</td>&nbsp;<td></td><td>{} %</td></tr>
        <tr><td>Video size:</td><td>{} x {}</td><td>{} x {}</td></tr>
        <tr><td>Duration (h:m:s):</td><td>{}</td><td>{}</td></tr>
        <tr><td>Average bitrate:</td><td>{} kbits/s</td><td>{} kbits/s</td></tr>
        <tr><td>Framerate (fps):</td><td>{}</td><td>{}</td></tr>
        </table>
        """.format(first_line,
                   int(round(src_file_size/1000, 0)), int(round(dst_file_size/1000, 0)),
                   percent_change,
                   src_width, src_height, dst_width, dst_height,
                   src_duration, dst_duration,
                   #self.__format_duration(src_duration), self.__format_duration(dst_duration), #VLC transcoding
                   src_bitrate, dst_bitrate,
                   src_fps, dst_fps
                   )

        old_text = self.stats_edit.toHtml()
        if old_text:
            text = '{}{}'.format(text, old_text)
        self.stats_edit.setHtml(text)

    ##!!@pyqtSlot()
    def onExportLog(self):
        html = self.stats_edit.toHtml()
        filenames = QFileDialog.getSaveFileName(self, "Export Transcoding Statistics", "", "Html Files (*.html)")
        if filenames:
            with io.open(filenames[0], 'w', encoding='utf-8') as f:
                f.write(html)

#     def __format_duration(self, time_ms): #for VLC transcoding
#         if isinstance(time_ms, str) and time_ms == '???':
#             return time_ms
#         hours, minutes, secs = 0, 0, 0
#         secs = time_ms/1000
#         minutes = secs//60
#         secs = secs - 60*minutes
#         if minutes:
#             hours = minutes//60
#             minutes = minutes - 60*hours
#         return '{}:{}:{}'.format(int(hours), int(minutes), round(secs, 3))
