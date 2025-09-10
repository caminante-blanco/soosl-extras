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
along with SooSL™.  If not, see <http://www.gnu.org/licenses/>."""

import os
import sys
import re
import time
import shutil
import tempfile
#from pyffmpeg import FFmpeg

from PyQt5.QtCore import pyqtSignal, Qt, QByteArray
from PyQt5.QtCore import QFileInfo
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QProcess
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QPixmap, QImage, QMovie
from PyQt5.QtWidgets import qApp

from media_object import MediaObject
        
class FFmpegThread(QThread):
    read_output = pyqtSignal(QByteArray)
     
    def __init__(self, parent, args):
        super(FFmpegThread, self).__init__(parent)      
        self.ffmpeg = qApp.instance().getFFmpeg()
        self.args = args
        self.complete = False
        self.success = False   
        qApp.processEvents()     
         
    def run(self):  
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.onReadyReadOutput)
        #print(self.args)           
        self.process.start(self.ffmpeg, self.args)       
        self.process.waitForFinished(msecs=-1)
        if self.process.exitStatus() == QProcess.NormalExit:
            self.success = True        
        self.complete = True
        return
    
    ##!!@pyqtSlot()
    def onReadyReadOutput(self):
        output = self.process.readAllStandardOutput()
        if output:
            self.read_output.emit(output)
         
    def __del__(self):
        if not self.complete:
            self.wait()  
            
class VideoWrapper(QObject):
    """this class is provided as a wrapper around a video file in order to expose information about the 
    video (framesize, duration, fps, crop_geometry, ..). Also, a method is provided for importing a video
    into the appropriate SooSL directory applying any required cropping, scaling and transcoding to .mp4
    
    Info on the web:
    http://trac.ffmpeg.org/wiki/Encode/H.264
    http://slhck.info/video-encoding.html (summary of encoder settings)
    
    """
    abort_save = pyqtSignal()    
    progress = pyqtSignal(int, float, str, bool)
    
    def __init__(self, media_object, destination_dir=None, _id=None, parent=None):
        super(VideoWrapper, self).__init__(parent)
        self.media_object = media_object
        if not isinstance(media_object, MediaObject):
            self.media_object = MediaObject(*media_object)
        self.new_file_path = None
        self._dir = destination_dir
        self._id = _id
        self.info_dict = {}
        self.set_info(self.media_object.filename)
        self.complete = False
        self.success = False
        qApp.processEvents()
               
    @property
    def crop(self):
        _crop = self.media_object.transcode_crop
        if _crop:
            out_w, out_h, x, y = _crop
            return "crop={}:{}:{}:{}".format(out_w, out_h, x, y)
        return "crop={}:{}:0:0".format(self.get_info('fwidth'), self.get_info('fheight'))
    
    @property
    def rotation(self):
        _rot = self.media_object.rotation
        if _rot == 1:
            return "transpose=1"
        elif _rot == 2:
            return "transpose=1,transpose=1"
        elif _rot == 3:
            return "transpose=1,transpose=1,transpose=1"
        else:
            return None
    
    @property
    def scale(self):       
        max_height = self.get_settings(['max_height'])
        w, h = self.fsize           
        if w and h and h > max_height:
            return 'scale=-2:trunc({}/2)*2'.format(max_height)
        else:
            return 'scale=-2:trunc(ih/2)*2'
    
    @property
    def fwidth(self):
        _fwidth = self.get_info('fwidth')
        if not _fwidth:
            _fwidth = 0
        return _fwidth
    
    @property
    def fheight(self):
        _fheight = self.get_info('fheight')
        if not _fheight:
            _fheight = 0
        return _fheight
    
    @property
    def fsize(self):
        return (int(self.fwidth), int(self.fheight))
    
    @property
    def fps(self):
        return self.get_info('fps')
    
    @property
    def bitrate(self):
        return self.get_info('bitrate')
    
    @property
    def duration(self):
        d = self.get_info('duration')
        if isinstance(d, str) and d.count(':'):
            return self.__toSecs(d)
        return d # duration for animated gif already in seconds
    
    def isCorrupt(self):
        ## NOTE: what else would make a video corrupt???
        pth = self.media_object.filename
        if not self.duration: 
            return True
        return False
    
    def get_info(self, key=None): 
        if key:
            return self.info_dict.get(key)
        else:
            return self.info_dict
                
    def set_info(self, media_file):
        args = []
        if sys.platform.startswith('win'):
            args = [#'-r', '25', 
                    '-i', media_file,
                    '-loglevel', 'verbose', 
                    #'-vf', 'cropdetect',
                    '-frames', '10',
                    '-f', 'null', 'out.null']
        elif sys.platform.startswith('darwin'):
            args = ['-stdin',
                    #'-r', '25',
                    '-loglevel', 'verbose', 
                    '-i', media_file,
                    #'-vf', 'cropdetect',  
                    '-vframes', '10',
                    '-f', 'rawvideo', '-y', '/dev/null']
        elif sys.platform.startswith('linux'): #same as os x? let's find out ...
            args = ['-stdin',
                    #'-r', '25',
                    '-loglevel', 'verbose', 
                    '-i', media_file,
                    #'-vf', 'cropdetect',  
                    '-vframes', '10',
                    '-f', 'rawvideo', '-y', '/dev/null']
            
        ffmpeg = FFmpegThread(self, args)
        ffmpeg.read_output.connect(self.readVideoInfo)
        ffmpeg.start()
        ffmpeg.wait()
        
        qApp.processEvents()
        
        self.info_dict['filename'] = media_file
        self.info_dict['size'] = QFileInfo(media_file).size()
                
        duration = self.info_dict.get('duration')
        if duration:
            if duration != 'N/A':
                h, m, s = duration.split(':')
                duration = 0
                if int(h) or int(m) or float(s): # 00:00:00
                    duration = (int(h)*60*60) + (int(m)*60) + float(s)
                    duration = duration*1000
            else: # animated gif
                fps = float(self.info_dict.get('fps'))
                frames = QMovie(media_file).frameCount()
                duration = float(frames/fps)
                self.info_dict['duration'] = duration
            if duration:
                _bytes = self.info_dict.get('size')
                bitrate = round(_bytes*8/duration) #kbps
                self.info_dict['bitrate'] = bitrate #average bitrate

    def get_settings(self, values):
        return qApp.instance().getTranscodeSettings(values)

    def __makeOld(self, pth):
        dst = '{}.old'.format(pth)
        #shutil.copy2(self.new_file_path, dst)
        with open(dst, 'wb') as old_video:
            with open(pth, 'rb') as new_video:
                old_video.write(new_video.read())
            
        qApp.instance().pm.possible_removals.append(dst)
        
    def path(self):
        return self.media_object.filename
        
    def newPath(self):
        new_path = self.media_object.filename #this should only remain unchanged if there is no id or dir given, in the case
        # where rotation and crop changes are made to an existing file in the dictionary
        #video = QFileInfo(self.media_object.filename)
        if self._dir:
            basename = os.path.basename(self.media_object.filename)
            name, old_ext = os.path.splitext(qApp.instance().pm.joinFilenameId(basename, self._id))
            new_ext = ".mp4"
            if self.get_settings(['size']) == 'super':
                #new_ext = '.mkv'
                new_ext = old_ext
            new_path = os.path.join(self._dir, """{}{}""".format(name, new_ext))
            #new_path = new_path.replace('\\', '/')
            new_path = qApp.instance().pm.sanitizePath(new_path)
            new_path = qApp.instance().pm.checkFilepathLength(new_path)        
        return new_path
    
    def transcodeAgain(self):
        filter1 = self.crop
        filter2 = self.scale
        filter3 = self.rotation
        
        filters = "{}".format(filter1)
        if filter2:
            filters = "{},{}".format(filters, filter2)
        if filter3:
            filters = "{},{}".format(filters, filter3)
                
        crf_value, preset_value, max_bitrate, max_fps = self.get_settings(['crf', 'preset', 'max_bitrate', 'max_fps'])
        buff = 2*int(max_bitrate)
         
        file_name = self.media_object.filename
        ext = os.path.splitext(file_name)[1]  
        src_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='SooSL_') #removed at close of dictionary
        dst_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='SooSL_') #removed at close of dictionary
        # in event of crash, removed at restart of program
        src_temp_file = open(src_temp_file.name, 'w+b')
        with open(file_name, 'rb') as src:
            src_temp_file.write(src.read()) 
             
        src_path = src_temp_file.name
        src_path = src_path.replace('\\', '/')
        dst_path = dst_temp_file.name
        dst_path = dst_path.replace('\\', '/')

        args = ['-stdin',
                '-y']
        
        # if a valid frame rate is reported, use it, otherwise enforce fps=25 to correctly transcode videos
        # this should override any other fps options; only time I've seen this is with some old .wmv files 
        try:
            float(self.fps) # invalid rate probably reported as '1k'
        except:
            filters = '{},fps=fps=25'.format(filters)
        else:
            max_fps = str(self.get_settings(['max_fps']))
            if max_fps.startswith('0'):
                pass #just let ffmpeg worry about the frame rate; the recommended option!!!
            else:
                filters = '{},fps=fps={}'.format(filters, max_fps)
        args = args + [
            '-i', src_path,
            '-c:v', 'libx264', '-crf', '{}'.format(crf_value), '-preset', '{}'.format(preset_value),
            '-pix_fmt', 'yuv420p',
            '-bufsize', '{}k'.format(buff),
            '-maxrate', '{}k'.format(max_bitrate),
            '-an',
            '-vf', filters,
            dst_path
            ]
        ffmpeg = qApp.instance().getFFmpeg()
        process = QProcess()
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.start(ffmpeg, args)       
        process.waitForFinished(msecs=-1)        
        qApp.instance().transcode_stats.emit(src_path, dst_path)
        return (src_path, dst_path)
        
    def save2dir(self):
        """save (copy) file into a directory, encoding, cropping and resizing as required. Mostly used when saving a sign and importing
        a video file into the appropriate dictionary directory. 
        """
        new_file_path = self.newPath()
        _dir = os.path.dirname(new_file_path)
        if not os.path.exists(_dir): 
            os.mkdir(_dir)
        if os.path.exists(new_file_path):
            self.__makeOld(new_file_path)
        if self._dir and not self.rotation and self.crop.endswith(':0:0'):
            # if file_path originates from within dictionary directories, (and doesn't require rotation or cropping)
            # then it has already been transcoded/resized and we only wish to copy it
            proj_dir = qApp.instance().pm.getCurrentProjectDir()
            if os.path.normpath(self.media_object.filename).startswith(os.path.normpath(proj_dir)):
                self.__copy2dir(self.media_object.filename, new_file_path)
                return
            
        filter1 = self.crop
        filter2 = self.scale
        filter3 = self.rotation
        
        filters = "{}".format(filter1)
        if filter2:
            filters = "{},{}".format(filters, filter2)
        if filter3:
            filters = "{},{}".format(filters, filter3)
                
        current_size, crf_value, preset_value, max_bitrate, max_fps = self.get_settings(['size', 'crf', 'preset', 'max_bitrate', 'max_fps'])
        buff = 2*int(max_bitrate)
        
        if current_size == 'super': #copy same file
            self.__copy2dir(self.media_object.filename, self.new_file_path)
            qApp.instance().transcode_stats.emit(self.media_object.filename, new_file_path)
            return
         
        #print(self.file_path, self.new_file_path) #NOTE: Maybe the following only needs to be applied when old and new file
        # names are the same???      
        # I've been ending up with damaged files when cropping and rotating files already existing in a dictionary,
        # so copy them to temporary file before transcoding. Seems a good idea to do this anyway for all files to
        # prevent any possible transcoding damage for whatever reason...  
        file_name = self.media_object.filename
        ext = os.path.splitext(file_name)[1]  
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='SooSL_') #removed at close of dictionary
        # in event of crash, removed at restart of program
        temp_file = open(temp_file.name, 'w+b')
        with open(file_name, 'rb') as src:
            temp_file.write(src.read()) 
             
        src_path = temp_file.name        
        src_path = src_path.replace('\\', '/')

        temp_file_2 = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='SooSL_')
        self.new_file_path = temp_file_2.name
        self.new_file_path = self.new_file_path.replace('\\', '/')
        
        args = ['-stdin',
                '-y']
        
        # if a valid frame rate is reported, use it, otherwise enforce fps=25 to correctly transcode videos
        # this should override any other fps options; only time I've seen this is with some old .wmv files 
        try:
            float(self.fps) # invalid rate probably reported as '1k'
        except:
            filters = '{},fps=fps=25'.format(filters)
        else:
            max_fps = str(self.get_settings(['max_fps']))
            if max_fps.startswith('0'):
                pass #just let ffmpeg worry about the frame rate; the recommended option!!!
            else:
                filters = '{},fps=fps={}'.format(filters, max_fps)
#                 elif max_fps and max_fps.endswith('c'): #constant frame rate
#                     fps = max_fps.rstrip('c')
#                     #args.extend([''-r', fps'])
#                     filters = '{},fps=fps={}'.format(filters, fps)
#                 elif max_fps and max_fps.endswith('v'): #variable frame rate
#                     fps = max_fps.rstrip('v')
#                     args.extend(['-vsync', '2']) #https://superuser.com/questions/908295/ffmpeg-libx264-how-to-specify-a-variable-frame-rate-but-with-a-maximum 
#                     filters = '{},fps=fps={}'.format(filters, fps)    
        args = args + [
            '-i', src_path,
            '-c:v', 'libx264', '-crf', '{}'.format(crf_value), '-preset', '{}'.format(preset_value),
            '-pix_fmt', 'yuv420p',
            '-bufsize', '{}k'.format(buff),
            '-maxrate', '{}k'.format(max_bitrate),
            '-an',
            '-vf', filters,
            self.new_file_path
            ]              
        self.save(args)
        
    def __copy2dir(self, old_file, new_file):
        try:
            shutil.copyfile(old_file, new_file)
        except:
            print('filename already exists; error or feature???')
        self.current_progress = 100
        self.complete = True
        self.progress.emit(self.duration, self.duration, self.media_object.filename, self.complete)
        if os.path.exists(new_file):
            self.success = True
    
    def save(self, args):
        self.complete = False
        self.success = False         
        saver = FFmpegThread(self, args)
        saver.read_output.connect(self.onReadyRead)
        saver.finished.connect(self.onSaveFinished)
        saver.start()
    
    ##!!@pyqtSlot()    
    def onSaveFinished(self):
        self.success = self.sender().success
        if not self.success and self._id:
            if os.path.exists(self.new_file_path): #process stopped/crashed part-way
                os.unlink(self.new_file_path)
            if self.success == False: #still use and copy original file
                name = "{}_id{}".format(os.path.split(self.media_object.filename)[1], self._id)
                new_file = os.path.join(self._dir, name)
                new_file = new_file.replace('\\', '/')
                shutil.copyfile(self.media_object.filename, new_file)
                self.new_file_path = new_file
                print('transcode failed')
                print('copy file as is')
                print(self.media_object.filename, new_file)
                print()
            elif self.success == 0: #aborted save
                pass ##NOTE: although it doesn't seem to get this far on aborted save 
        elif self.success and self._id:
            new_file_path = self.newPath() # true path
            shutil.move(self.new_file_path, new_file_path) #self.new_file_path is just temorary at this point
            self.new_file_path = new_file_path
           
        self.complete = True
        self.progress.emit(100, 100, self.media_object.filename, True)        
        qApp.instance().transcode_stats.emit(self.media_object.filename, self.new_file_path)
    
    ##!!@pyqtSlot(QByteArray)
    def onReadyRead(self, output):
        if output:
            lines = output.split('\n')
            for line in lines:
                line = str(line.simplified()).lstrip("b'").rstrip("'")
                time = re.search(r'time=(\S+) ', ascii(line))
                if time:
                    time_string = time.groups()[0]
                    self.onProgress(time_string) 
        qApp.processEvents()
            
    def onProgress(self, time_string):
        secs = self.__toSecs(time_string)
        if secs:
            _progress = int(secs)
            self.progress.emit(_progress, self.duration, self.media_object.filename, self.complete)
             
    def __toSecs(self, time_string):
        if time_string:
            try:
                h, m, s = time_string.split(':')
            except:
                return 0
            else:
                try:
                    seconds = float(h)*360 + float(m)*60 + float(s)
                except:
                    return 0
                else:
                    return seconds  
        else:
            return 0
    
    ##!!@pyqtSlot(QByteArray)
    def readVideoInfo(self, output):
        if output:
            lines = output.split('\n')
            for line in lines:
                line = str(line.simplified()).lstrip("b'").rstrip("'") 
                if line.startswith("Duration"):
                    try:
                        self.info_dict['duration'] = re.findall(r"Duration: (.[^,]+)", line)[0]
                    except:
                        self.info_dict['duration'] = '0:0:0'
#                     try:
#                         self.info_dict['bitrate'] = re.findall(r"bitrate: (.+) kb", line)[0]
#                     except:
#                         self.info_dict['bitrate'] = 0
                elif (line.startswith("Stream") and line.count('fps')):# or line.count('tbc')):
                    try:
                        size = re.findall(r", (\d+x\d+)", line)[0]
                    except:
                        pass
                    else:
                        self.info_dict['fwidth'], self.info_dict['fheight'] = size.split('x')
                    fps = re.findall(r", (\S+)(?=( fps| tbc))", line)[0][0]
                    try:
                        float(fps)
                    except:
                        fps = '???' # unknown; probably reported as '1k'
                    self.info_dict['fps'] = fps
                elif line.count("crop="):
                    cropdetect = re.findall("crop=.+", line)[0]
                    if cropdetect:
                        self.info_dict['crop'] = cropdetect  
                        
#PICTURE_WIDTH = 600

class PictureWrapper(QObject):
    """this class is provided as a wrapper around a picture file in order to expose information about the 
    picture (size, ..). Also, a method is provided for importing a video
    into the appropriate SooSL directory applying any required scaling.
    """
    abort_save = pyqtSignal()    
    progress = pyqtSignal(int, float, str, bool)
    
    def __init__(self, media_object, destination_dir=None, _id=None, parent=None):
        super(PictureWrapper, self).__init__(parent) 
        self.media_object = media_object
        if not isinstance(media_object, MediaObject):
            # media_object is simple list
            self.media_object = MediaObject(*media_object)
        self.new_file_path = None
        self._dir = destination_dir
        self._id = _id
        self.current_progress = 0
        self.duration = 2 # just a nominal figure in seconds
        
        self.complete = False
        self.success = False

    def __makeOld(self, pth):
        dst = '{}.old'.format(pth)
        with open(dst, 'wb') as old_video:
            with open(pth, 'rb') as new_video:
                old_video.write(new_video.read())
            
        qApp.instance().pm.files_2_delete.append(dst)
        
    def isCorrupt(self):
        ##NOTE: what would make an image file corrupt???
        pth = self.media_object.filename
        if pth.lower().endswith('svg'):
            return False
        if QImage(pth) == QImage(): #image not loaded; equal to null QImage
            return True
        return False
        
    def unsupportedFormat(self, filename): #currently no support for writing
        unsupported = ['.svg']
        ext = os.path.splitext(filename)[1].lower()
        if ext in unsupported:
            return True
        return False
    
    def newPath(self):
        _file = qApp.instance().pm.joinFilenameId(self.media_object.filename, self._id)
        new_name = os.path.basename(_file)
        new_path = os.path.join(self._dir, new_name)
        #new_path = new_path.replace('\\', '/')
        
        #see save2dir
        _dir = os.path.dirname(self.media_object.filename) #os.path.normpath(os.path.dirname(self.media_object.filename))
        proj_dir = os.path.dirname(qApp.instance().pm.current_project_filename)
        current_size = self.get_settings(['size'])   
        if current_size == 'super' or self.unsupportedFormat(self.media_object.filename): #copy same file
            pass
        elif _dir.startswith(proj_dir) and not self.rotation: 
            if not self._dir.endswith('signs') and _dir == self._dir: # both original and destination are of the same type, but not sign type
                new_path = self.media_object.filename 
        new_path = qApp.instance().pm.sanitizePath(new_path)         
        new_path = qApp.instance().pm.checkFilepathLength(new_path)
        return new_path
        
    def save2dir(self):
        """save (copy) file into a directory, rescaling as required. Mostly used when saving a sign and importing
        a picture file into the appropriate dictionary directory. 
        """
        self.new_file_path = self.newPath()
        _dir = os.path.dirname(self.new_file_path)
        if not os.path.exists(_dir): 
            os.mkdir(_dir)
        if os.path.exists(self.new_file_path):
            self.__makeOld(self.new_file_path)
        
        # if file_path originates from within dictionary directories, then it has already been transcoded/resized
        # and we only wish to copy it
        _dir = os.path.dirname(self.media_object.filename) #os.path.normpath(os.path.dirname(self.media_object.filename))
        proj_dir = os.path.dirname(qApp.instance().pm.current_project_filename) #os.path.normpath(os.path.dirname(qApp.instance().pm.current_project_filename))
        current_size = self.get_settings(['size'])   
        if current_size == 'super' or self.unsupportedFormat(self.media_object.filename): #copy same file
            self.__copy2dir(self.media_object.filename, self.new_file_path)
        elif _dir.startswith(proj_dir) and not self.rotation: 
            if not self._dir.endswith('signs') and _dir == self._dir: # both original and destination are of the same type, but not sign type
                self.new_file_path = self.media_object.filename # next steps will find and use id of existing video instead of path
                self.success = True
            else:
                shutil.copyfile(self.media_object.filename, self.new_file_path)
        else:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file = open(temp_file.name, 'w+b')
            with open(self.media_object.filename, 'rb') as src:
                temp_file.write(src.read()) 
                   
            file_path = temp_file.name
    
            filters = self.scale
            if self.rotation:
                filters = '{},{}'.format(filters, self.rotation)
            print('filters', filters) 
            args = ['-stdin', '-y', '-i', file_path] 
            args = args + ['-vf', filters]
#             if self.rotation:
#                 args.append('-vf')
#                 args.append(self.rotation)
            args.append(self.new_file_path) #'bgra', '-pix_fmt', 'rgba', 
            
            self.complete = False
            self.success = False         
            saver = FFmpegThread(self, args)
            saver.finished.connect(self.onSaveFinished)
            saver.start()  
        
    @property
    def fsize(self):
        pxm = QPixmap(self.media_object.filename)
        return (pxm.width(), pxm.height())
        
    @property
    def scale(self):       
        max_height = self.get_settings(['max_height'])
        w, h = self.fsize           
        if w and h and h > max_height:
            return 'scale=-2:trunc({}/2)*2:flags=lanczos'.format(max_height)
        else:
            return 'scale=-2:trunc(ih/2)*2:flags=lanczos'
            #return 'scale=trunc(iw/2)*2:trunc(ih/2)*2'        
        
    @property
    def rotation(self):
        _rot = self.media_object.rotation
        if _rot == 1:
            return "transpose=1"
        elif _rot == 2:
            return "transpose=1,transpose=1"
        elif _rot == 3:
            return "transpose=1,transpose=1,transpose=1"
        else:
            return None
        
    def get_settings(self, values):
        return qApp.instance().getTranscodeSettings(values)
        
    def onReadyRead(self, output):
        if output:
            lines = output.split('\n')
            for line in lines:
                line = str(line.simplified()).lstrip("b'").rstrip("'")
                time = re.search(r'time=(\S+) ', ascii(line))
                if time:
                    time_string = time.groups()[0]
                    self.onProgress(time_string) 
        qApp.processEvents()
        
    def onProgress(self, time_string):
        secs = self.__toSecs(time_string)
        if secs:
            _progress = int(secs)
            self.progress.emit(_progress, self.duration, self.media_object.filename, self.complete)
             
    def __toSecs(self, time_string):
        if time_string:
            try:
                h, m, s = time_string.split(':')
            except:
                return 0
            else:
                try:
                    seconds = float(h)*360 + float(m)*60 + float(s)
                except:
                    return 0
                else:
                    return seconds  
        else:
            return 0
        
    def __copy2dir(self, old_file, new_file):
        _dir = os.path.dirname(new_file)
        shutil.copyfile(old_file, new_file)
        self.current_progress = 100
        self.complete = True
        self.progress.emit(0.5, 0.5, self.media_object.filename, self.complete)
        if os.path.exists(new_file):
            self.success = True
        
    def onFirstPassFinished(self):
        self.complete = True
    
    ##!!@pyqtSlot()    
    def onSaveFinished(self):
        old_file = self.sender().args[3]
        new_file = self.sender().args[-1]
        if not os.path.exists(new_file):
            img = QPixmap(old_file)
            max_height = self.get_settings(['max_height'])
            w, h = img.width(), img.height()          
            if w and h and h > max_height:
                img = img.scaledToHeight(max_height, Qt.SmoothTransformation)
            img.save(new_file)
        if os.path.exists(new_file):
            self.success = True
                
        if not self.success and self._id:
            if os.path.exists(self.new_file_path): #process stopped/crashed part-way
                os.unlink(self.new_file_path)
            if self.success == False: 
                name = "{}_id{}".format(os.path.split(self.media_object.filename)[1], self._id)
                new_file = os.path.join(self._dir, name)
                
                shutil.copyfile(self.media_object.filename, new_file)
                self.new_file_path = new_file
            elif self.success == 0: #aborted save
                pass ##NOTE: although it doesn't seem to get this far on aborted save        
        self.complete = True
        self.progress.emit(100, 100, self.media_object.filename, True)
    
