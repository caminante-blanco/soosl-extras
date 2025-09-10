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

CURRENT_LANG = 1
LAST_DB_UPDATE = '0.8.4' #last version with db changes incompatible with earlier versions of SooSL
OLDEST_UPDATABLE = '0.4.0'

import os
import copy
import re
import sys
import glob
import collections
import io

from PyQt5.QtSql import QSqlQuery
from PyQt5.QtSql import QSqlDatabase

from PyQt5.QtCore import QObject
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QProgressDialog

from dialect import Dialect

class SooSLQuery(QSqlQuery):
    def __init__(self, db):
        super(SooSLQuery, self).__init__(db)
        if db:
            self.setForwardOnly(True)

class SooSLDatabaseManager(QObject):    
    def __init__(self, db=None, parent=None):
        super(SooSLDatabaseManager, self).__init__(parent)
        self.prev_connection_name = None
        self.connection_name = None
        self.db = None
        if db and db.isOpen():
            self.setCurrentDb(db)
        self.databases = []
        
    def setCurrentDb(self, db, connection_name):
        self.db = db
        self.prev_connection_name = self.connection_name
        self.connection_name = connection_name
    
    def compact(self):
        query = SooSLQuery(self.db)
        query.exec_("""VACUUM""")    
    
    def signExists(self, name):
        """determine if a sign file (basename) exists in database. test for just 'root' without 'ext' as the
        extension will probably differ in the database (currently .mp4).
        """
        root = os.path.splitext(name)[0]
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, path FROM citation WHERE path LIKE '{}.{}'""".format(root, '%')) #use the '.' in the search to match full 'root'
        if query.next():
            _id = query.value(0)
            path = query.value(1)
            return (_id, path)
        else:
            return (None, None)  
        
    def sentenceVideoExists(self, name):
        """determine if a sentence file (basename) exists in database. test for just 'root' without 'ext' as the
        extension will probably differ in the database (currently .mp4).
        """
        root = os.path.splitext(name)[0]
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, path FROM sentenceVideo WHERE path LIKE '{}.{}'""".format(root, '%')) #use the '.' in the search to match full 'root'
        if query.next():
            _id = query.value(0)
            path = query.value(1)
            return (_id, path)
        else:
            return (None, None)  
        
    def exVideoExists(self, name):
        """determine if a exVideo file (basename) exists in database. test for just 'root' without 'ext' as the
        extension will probably differ in the database (currently .mp4).
        """
        root = os.path.splitext(name)[0]
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, path FROM exVideo WHERE path LIKE '{}.{}'""".format(root, '%')) #use the '.' in the search to match full 'root'
        if query.next():
            _id = query.value(0)
            path = query.value(1)
            return (_id, path)
        else:
            return (None, None)
        
    def exPictureExists(self, name):
        """determine if a exPicture file (basename) exists in database. test for just 'root' without 'ext' as the
        extension will probably differ in the database (currently .mp4).
        """
        root = os.path.splitext(name)[0]
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, path FROM exPicture WHERE path LIKE '{}.{}'""".format(root, '%')) #use the '.' in the search to match full 'root'
        if query.next():
            _id = query.value(0)
            path = query.value(1)
            return (_id, path)
        else:
            return (None, None)
        
    def exPictureUsageCount(self, file_path):
        name = os.path.basename(file_path)
        _id, pth = self.exPictureExists(name)
        if not _id:
            return 0
        else:
            return self.countExPictures(_id)
    
    def exVideoUsageCount(self, file_path):
        name = os.path.basename(file_path)
        _id, pth = self.exVideoExists(name)
        if not _id:
            return 0
        else:
            return self.countExVideos(_id)
    
    def canAccess(self):
        version = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT version FROM meta""")
        while query.next():
            version = query.value(0)
        if version:
            return True
        return False
    
    def projectFiles(self):
        files = []
        query = SooSLQuery(self.db)
        for media_type, _query in [
           ('signs', """SELECT path FROM citation"""),
           ('sentences', """SELECT path FROM sentenceVideo"""),
           ('extra_videos', """SELECT path FROM exVideo"""),
           ('extra_pictures', """SELECT path FROM exPicture""")
           ]:
            query.exec_(_query)
            while query.next():
                name = query.value(0)
                files.append(os.path.join(media_type, name))  
        return files
                
    def openDb(self, filename, canedit=False):
        """open a database
        """            
        db = QSqlDatabase.addDatabase("QSQLITE", filename) 
        db.setDatabaseName(filename)   
        if not canedit:
            db.setConnectOptions('QSQLITE_OPEN_READONLY')
        if db.open():
            self.setCurrentDb(db, filename)
            if self.canAccess(): # no longer using sqlite for new projects as of 0.8.10 
                query = SooSLQuery(db)
                query.prepare("""PRAGMA locking_mode=EXCLUSIVE""") ##TODO: PLACE DB LOCK BACK ON
                query.exec_()
                return db
            else: #already open in another instance of SooSL, or maybe some other database program with exclusive access
                db.close()
                QSqlDatabase.removeDatabase(filename)
                return None
        else:
            return None
        
    def close(self, connection=None):
        db = self.db
        if connection and connection in QSqlDatabase.connectionNames():
            db = QSqlDatabase.database(connection)
        db_filename = db.databaseName()
        if db.isOpen():
            db.close()
            QSqlDatabase.removeDatabase(db_filename)
        return db_filename
            
    def addType(self, gram_cat):
        query = SooSLQuery(self.db)
        query.prepare("""INSERT INTO type ('name') VALUES (?)""")  
        query.addBindValue(gram_cat)
        query.exec_()
        
    def countExVideos(self, _id):
        count = 0
        if _id:
            query = SooSLQuery(self.db)   
            query.prepare("""SELECT DISTINCT count(exVideo_id) FROM exVideo_gloss WHERE exVideo_id=?""")
            query.addBindValue(_id)
            query.exec_()    
            while query.next():
                count = query.value(0)
        return count
    
    def countSenses(self, _id):
        _id = str(_id)
        if _id:
            query = SooSLQuery(self.db)   
            query.prepare("""SELECT count(citation_id) FROM gloss_citation WHERE citation_id=?""")
            query.addBindValue(_id)
        query.exec_()
        count = 0
        while query.next():
            count = query.value(0)
        return count
    
    def countExPictures(self, _id):
        _id = abs(_id)
        query = SooSLQuery(self.db)   
        query.prepare("""SELECT DISTINCT count(exPicture_id) FROM exPicture_gloss WHERE exPicture_id=?""")
        query.addBindValue(_id)
        query.exec_()
        count = 0
        while query.next():
            count = query.value(0)
        return count
        
    def removeExVideo(self, _id, sign_id, gloss_id, delete_all):
        """remove ex video.
        """  
        if _id:
            query = SooSLQuery(self.db)
            if delete_all:    
                query.exec_("""DELETE FROM exVideo_gloss WHERE exVideo_id={}""".format(_id))
                query.exec_("""DELETE FROM exVideo WHERE id={}""".format(_id))
            else:
                query.prepare("""DELETE FROM exVideo_gloss WHERE exVideo_id=? AND citation_id=? AND gloss_id=?""")
                query.addBindValue(_id)
                query.addBindValue(sign_id)
                query.addBindValue(gloss_id)
                query.exec_()
            
    def removeExPicture(self, _id, sign_id, gloss_id, delete_all):
        """remove ex picture.
        """
        if _id:
            query = SooSLQuery(self.db)
            if delete_all:    
                query.exec_("""DELETE FROM exPicture_gloss WHERE exPicture_id={}""".format(_id))
                query.exec_("""DELETE FROM exPicture WHERE id={}""".format(_id))
            else:
                query.prepare("""DELETE FROM exPicture_gloss WHERE exPicture_id=? AND citation_id=? AND gloss_id=?""")
                query.addBindValue(_id)
                query.addBindValue(sign_id)
                query.addBindValue(gloss_id)
                query.exec_()
            
    def glossCount(self): 
        return len(self.glosses())
    
    def emptyGlosses(self):
        query = SooSLQuery(self.db)
        query.prepare("""SELECT id FROM glossID WHERE id NOT IN (SELECT gloss_id FROM glossText) ORDER BY id""")
        query.exec_()
        gloss_ids = []
        while query.next():
            gloss_ids.append(query.value(0))
        return gloss_ids
    
    def signIds(self):
        """return list of sign ids
        """
        sign_ids = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id FROM citation""")
        while query.next():
            sign_ids.append(query.value(0))
        return sign_ids
                    
    def glosses(self):
        """return list of glosses
        """
        statement = """SELECT gloss_id, text, lang_id FROM glossText ORDER BY gloss_id, lang_id"""
        query = SooSLQuery(self.db)
        query.prepare(statement)
        query.exec_()
        
        texts_empty = collections.OrderedDict()
        languages = self.langs()
        for l in languages:
            texts_empty[l[0]] = ""    
        
        prev_id = None
        glosses = []
        texts = copy.deepcopy(texts_empty)
        gloss_id = None    
        while query.next():
            gloss_id = query.value(0)
            text = query.value(1)
            lang_id = query.value(2)
            
            if gloss_id != prev_id: #new gloss
                if prev_id:
                    glosses.append(texts)
                texts = copy.deepcopy(texts_empty)
                texts[0] = gloss_id
                if text:
                    texts[lang_id] = text
            else:
                if text:
                    texts[lang_id] = text
            prev_id = gloss_id
        if gloss_id:
            glosses.append(texts) #add final gloss
        return glosses
    
    def sentenceTexts(self):
        """return list of sentence texts
        """
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, text, lang_id FROM sentenceText ORDER BY id, lang_id""")
        
        texts_empty = collections.OrderedDict()
        languages = self.langs()
        for l in languages:
            texts_empty[l[0]] = ""
            
        sentences = []
        prev_id = None
        texts = copy.deepcopy(texts_empty)
        text_id = None
        while query.next():
            text_id = query.value(0)
            text = query.value(1)
            lang_id = query.value(2)
            if text_id != prev_id:
                if prev_id:
                    sentences.append(texts)
                texts = copy.deepcopy(texts_empty)
                texts[0] = text_id
                texts[lang_id] = text
            else:
                texts[lang_id] = text
            prev_id = text_id
        if text_id:
            sentences.append(texts)        
        return sentences
    
    def getSentences(self, sign_id, gloss_id):
        """return list of sentences for a citation, gloss combination
        """
        sql = """SELECT sentence_citation.sentence_id, sentenceVideo.id, sentenceVideo.path, sentenceText.id, sentenceText.lang_id, sentenceText.text
            FROM sentence_citation
            LEFT OUTER JOIN sentence ON sentence_citation.sentence_id=sentence.id
            LEFT OUTER JOIN sentenceVideo ON sentence.video_id=sentenceVideo.id
            LEFT OUTER JOIN sentenceText ON sentence.text_id=sentenceText.id
            WHERE sentence_citation.citation_id=?
            AND sentence_citation.gloss_id=?
            ORDER BY sentence_citation.sentence_id, sentenceText.lang_id"""
        
        query = SooSLQuery(self.db)
        query.prepare(sql)
        query.addBindValue(sign_id)
        query.addBindValue(gloss_id)
        query.exec_()
        
        texts_empty = collections.OrderedDict()
        languages = self.langs()
        for l in languages:
            texts_empty[l[0]] = ""
            
        sentences = []
        prev_id = None
        ##dialects = []    
        texts = copy.deepcopy(texts_empty)
        sentence_id = None
        sentence = []
        while query.next():
            sentence_id = query.value(0)
            video_id = query.value(1)
            video_path = query.value(2)
            text_id = query.value(3)
            lang_id = query.value(4)
            text = query.value(5)
            
            if sentence_id != prev_id: #initialize first sentence and on id change
                if prev_id: #id change but not first sentence
                    sentence.append(texts)
                    sentences.append(sentence)
                        
                sentence = [sentence_id, [video_id, video_path]]
                texts = copy.deepcopy(texts_empty)
                if text_id:
                    texts[0] = text_id
                    if text and lang_id:
                        texts[lang_id] = text
            else: #same id so add to texts dictionary
                if text and lang_id:
                    texts[lang_id] = text
            prev_id = sentence_id
        if prev_id: #last text
            sentence.append(texts)
            sentences.append(sentence)
        return sentences
    
    def getTables(self):
        tables = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT name FROM sqlite_master WHERE type='table'""")
        while query.next():
            table = query.value(0)
            tables.append(table)
        return tables
    
    def getCols(self, table_name, _query=None):
        cols = []
        if _query:
            query = _query
        else:
            query = SooSLQuery(self.db)
        query.prepare("""SELECT sql FROM sqlite_master WHERE type="table" AND name=?""")    
        query.addBindValue(table_name)
        query.exec_()
        while query.next():
            sql = query.value(0).replace('CREATE TABLE ', '')
            name, cols = sql.split('(', 1)
            cols = cols.split(',')
            cols = [c.strip('()') for c in cols]
            cols = [c.split()[0].strip('\'"') for c in cols]
        return cols
    
    def getGramCats(self, sign_id, gloss_id):
        types = []
        query = SooSLQuery(self.db)
        query.prepare("""SELECT id, name FROM type WHERE id IN (SELECT type_id FROM gloss_type WHERE citation_id=? AND gloss_id=?)""")
        query.addBindValue(sign_id)
        query.addBindValue(gloss_id)
        query.exec_()
        while query.next():
            _id = query.value(0)
            _name = query.value(1)
            types.append((_id, _name))
        return types
    
    def getAllGramCats(self):
        types = []
        query = SooSLQuery(self.db)
        query.prepare("""SELECT id, name FROM type""")
        query.exec_()
        while query.next():
            _id = query.value(0)
            _name = query.value(1)
            types.append((_id, _name))
        return types
    
    def getAuthorsMessage(self):
        message = None
        query = SooSLQuery(self.db)
        query.prepare("""SELECT author_message FROM project""")
        query.exec_()
        while query.next():
            message = query.value(0)
        return message
    
    def getPassMessage(self):
        message = None
        query = SooSLQuery(self.db)
        query.prepare("""SELECT pass_message FROM project""")
        query.exec_()
        while query.next():
            message = query.value(0)
        return message
    
    def savePassMessage(self, message):
        rowid = None
        query = SooSLQuery(self.db)
        query.prepare("""SELECT rowid FROM project""")
        query.exec_()
        while query.next():
            rowid = query.value(0)
        if rowid:
            query.prepare("""UPDATE project SET pass_message=?""")
            query.addBindValue(message)
            query.exec_()
        else:
            query.prepare("""INSERT INTO project ('pass_message') VALUES (?)""")
            query.addBindValue(message)
            query.exec_()
    
    def hasPass(self):
        message = None
        query = SooSLQuery(self.db)
        query.prepare("""SELECT pass_message FROM project""")
        query.exec_()
        while query.next():
            message = query.value(0)
        if message:
            return True
        return False    
    
    def linkGramCat(self, type_id, sign_id, gloss_id):
        query = SooSLQuery(self.db)
        query.prepare("""SELECT rowid FROM gloss_type WHERE citation_id=? AND gloss_id=?""")
        query.addBindValue(sign_id)
        query.addBindValue(gloss_id)
        query.exec_()
        _id = None
        while query.next():
            _id = query.value(0)
        if not _id:
            query.prepare("""INSERT INTO gloss_type ('citation_id', 'gloss_id', 'type_id') VALUES (?, ?, ?)""")
            query.addBindValue(sign_id)
            query.addBindValue(gloss_id)
            query.addBindValue(type_id)
        else:
            query.prepare("""UPDATE gloss_type SET type_id=? WHERE rowid=?""")
            query.addBindValue(type_id)
            query.addBindValue(_id)
        query.exec_()
    
    def getVersion(self):
        _version = '0.0.0'
        query = SooSLQuery(self.db)
        query.exec_("""SELECT version FROM meta""")
        while query.next():
            _version = query.value(0)
        return _version
    
    def getCompatibleVersion(self):
        compatible_version = LAST_DB_UPDATE
        query = SooSLQuery(self.db)
        query.exec_("""SELECT compatible_version FROM meta""")
        while query.next():
            compatible_version = query.value(0)
        return compatible_version
        
    def getLayoutDirection(self, lang_id):
        layout = 0 # default right to left
        query = SooSLQuery(self.db)
        query.exec_("""SELECT layout FROM writtenLanguage WHERE id='{}'""".format(lang_id))
        while query.next():
            layout = query.value(0)
        return layout
    
    def setLangOrder(self, lang_ids): 
        query = SooSLQuery(self.db)
        _count = 1
        for _id in lang_ids:
            focal = False
            if _count == 1:
                focal = True
            query.prepare("""UPDATE "writtenLanguage" SET "focal"=?, "order"=? WHERE "id"=?""")
            query.addBindValue(focal)
            query.addBindValue(_count)
            query.addBindValue(_id)
            query.exec_()
            _count += 1           
    
    def setVersion(self, version_str, compatible_str):    
        query = SooSLQuery(self.db)
        count = 0
        query.exec_("""SELECT count(version) FROM meta""")
        while query.next():
            count = query.value(0)
        if count:
            query.exec_("""UPDATE meta SET version='{}', compatible_version='{}'""".format(version_str, compatible_str))
        else:
            query.exec_("""INSERT INTO meta ('version', 'compatible_version') VALUES ('{}','{}')""".format(version_str, compatible_str))
    
    def allDialects(self):
        """return list of all dialects
        """
        dialects = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT * FROM dialect ORDER BY focal DESC""")
        while query.next():
            _id = query.value(0)
            name = query.value(1)
            abbrv = query.value(2)
            focal = query.value(3)
            dialects.append(Dialect(_id, name, abbrv, focal))
        return dialects
    
    def allTypes(self):
        """return list of all sign types
        """
        types = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT * FROM type ORDER BY name""")
        while query.next():
            _id = query.value(0)
            name = query.value(1)
            types.append((_id, name))
        return types
    
    def getSignDialects(self, sign_id):
        dialects = []
        glosses = self.getGlosses(sign_id)
        gloss_ids = [g.get(0) for g in glosses]
        for _id in gloss_ids:
            dialect_ids = [d._id for d in dialects]
            gloss_dialects = self.getGlossDialects(sign_id, _id)
            for g in gloss_dialects:
                if g._id not in dialect_ids:
                    dialects.append(g)
    
        #if no dialects, assume the 'focal' dialect
        if not dialects:
            dialects = [self.getFocalDialect()]
        return dialects
    
    def getFocalDialect(self):
        all_dialects = self.allDialects()
        if all_dialects:
            dialects = [d for d in all_dialects if d.isFocal]
            if dialects:
                return dialects[0]
            return all_dialects[0]
        return None
       
    def getGlossDialects(self, sign_id, gloss_id):
        dialects = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT DISTINCT id, name, abbrv, focal FROM dialect JOIN gloss_dialect ON dialect.id=gloss_dialect.dialect_id
            WHERE citation_id='{}' AND gloss_id='{}'""".format(sign_id, gloss_id))
        while query.next():
            dialect_id = query.value(0)
            name = query.value(1)
            abbrv = query.value(2)
            focal = query.value(3)
            dialects.append(Dialect(dialect_id, name, abbrv, focal))
        #if no dialects, assume the 'focal' dialect
        if not dialects:
            dialects = [self.getFocalDialect()]
        return dialects
    
    def getAllGlossDialects(self, gloss_id):
        dialects = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT DISTINCT id, name, abbrv, focal FROM dialect JOIN gloss_dialect ON dialect.id=gloss_dialect.dialect_id
            WHERE gloss_id='{}'""".format(gloss_id))
        while query.next():
            dialect_id = query.value(0)
            name = query.value(1)
            abbrv = query.value(2)
            focal = query.value(3)
            dialects.append(Dialect(dialect_id, name, abbrv, focal))
        #if no dialects, assume the 'focal' dialect
        if not dialects:
            dialects = [self.getFocalDialect()]
        return dialects
            
    def linkDialect(self, dialect_id, sign_id, gloss_id): #, sentence_id):
        query = SooSLQuery(self.db)
        if sign_id and gloss_id: # and not sentence_id:
            query.exec_("""INSERT INTO gloss_dialect ('citation_id', 'gloss_id', 'dialect_id')
                VALUES ('{}', '{}', '{}')""".format(sign_id, gloss_id, dialect_id))
            
    def langs(self):
        """return list of languages
        """
        languages = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT * FROM 'writtenLanguage'""")# ORDER BY order""")
        while query.next():
            _id = query.value(0)
            name = query.value(1)
            order = query.value(4)
            languages.append((_id, name, order))
        return languages
    
    def langName(self, lang_id):
        """return language by id
        """
        if self.db:
            query = SooSLQuery(self.db)
            statement = """SELECT name FROM writtenLanguage WHERE id=?"""
            query.prepare(statement)
            query.addBindValue(lang_id)
            query.exec_()
            name = ''
            while query.next():
                name = query.value(0)
            return name
        return None
    
    def types(self):
        """return list of sign types (part-of-speech or grammatical category)
        """
        gram_cats = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT * FROM type ORDER BY id""")
        while query.next():
            _id = query.value(0)
            name = query.value(1)
            gram_cats.append((_id, name))
        return gram_cats
    
    def focalLang(self):
        """primary written language
        """
        lang = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id, name FROM writtenLanguage WHERE "order"=1""")
        while query.next():
            _id = query.value(0)
            name = query.value(1)
            lang = (_id, name)            
        
        return lang
    
    def langCount(self):
        return len(self.langs())
    
    def signsByGloss(self, gloss_id, dialects=[]):
        """return list of signs for a particular gloss _id
        """
        signs = []
        query = SooSLQuery(self.db)
        ##if not dialects:
        statement = """SELECT DISTINCT citation.id FROM citation
            JOIN gloss_citation ON citation.id=gloss_citation.citation_id
            WHERE gloss_citation.gloss_id=?"""
        query.prepare(statement)
        query.addBindValue(gloss_id)
        query.exec_()
        while query.next():
            sign_id = query.value(0)
            sign_dialects = self.getSignDialects(sign_id)
            sign_dialect_ids = [sd._id for sd in sign_dialects]
            if set.intersection(set(sign_dialect_ids), set(dialects)):
                signs.append(sign_id)
        return signs
    
    def getTextsByMediaFile(self, filename, file_type):
        texts = []
        if file_type in ['ex_video', 'ex_picture']:
            return texts
        
        name = os.path.basename(filename)
        _hash = self.getOriginalHash(filename)
        
        if file_type == 'sign':
            # get gloss texts for this sign
            query = SooSLQuery(self.db)
            statement = """SELECT gloss_id FROM gloss_citation WHERE gloss_citation.citation_id IN 
                (SELECT id FROM citation WHERE path='{}')""".format(name)
            if _hash:
                statement = """SELECT gloss_id FROM gloss_citation WHERE gloss_citation.citation_id IN 
                    (SELECT id FROM citation WHERE hash='{}')""".format(_hash)
            query.prepare(statement)    
            query.exec_()
            while query.next():
                query2 = SooSLQuery(self.db)
                query2.exec_("""SELECT DISTINCT lang_id, text FROM glossText WHERE glossText.gloss_id='{}'""".format(query.value(0))) 
                d = collections.OrderedDict()
                while query2.next():
                    lang_id = query2.value(0)
                    text = query2.value(1)
                    d[lang_id] = text
                if d not in texts:
                    texts.append(d)
        elif file_type == 'sent':
            # get sentence texts for this sentence
            query = SooSLQuery(self.db)
            statement = """SELECT text_id FROM sentence WHERE video_id IN 
                (SELECT id FROM sentenceVideo WHERE path='{}')""".format(name)
            if _hash:
                statement = """SELECT text_id FROM sentence WHERE video_id IN 
                    (SELECT id FROM sentenceVideo WHERE hash='{}')""".format(_hash)
            query.prepare(statement)   
            query.exec_()
            while query.next():
                d = collections.OrderedDict()
                query2 = SooSLQuery(self.db)
                query2.exec_("""SELECT DISTINCT lang_id, text FROM sentenceText WHERE sentenceText.id='{}'""".format(query.value(0)))
                while query2.next():
                    lang_id = query2.value(0)
                    text = query2.value(1)
                    d[lang_id] = text
                if d not in texts:
                    texts.append(d)
        return texts
    
    def getComponents(self, sign_id):
        """return list of component codes for a particular sign id
        """
        if not sign_id or not int(sign_id):
            return []
        codes = []
        query = SooSLQuery(self.db)
        query.exec_("""SELECT code FROM component JOIN component_citation ON component.id=component_id
            WHERE citation_id={} ORDER BY code""".format(sign_id))
        while query.next():
            code = query.value(0)
            codes.append(code)
        return codes
    
    def getSignVideo(self, sign_id):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM citation WHERE id={}""".format(sign_id))
        while query.next():
            pth = query.value(0)
        return pth
    
    def getSignVideoByHash(self, _hash):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM citation WHERE hash='{}'""".format(_hash))
        if query.next():
            pth = query.value(0)
        return pth
    
    def getSentenceVideoByHash(self, _hash):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM sentenceVideo WHERE hash='{}'""".format(_hash))
        if query.next():
            pth = query.value(0)
        return pth
    
    def getExVideo(self, video_id):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM exVideo WHERE id={}""".format(video_id))
        while query.next():
            pth = query.value(0)
        return pth
    
    def getExVideoByHash(self, _hash):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM exVideo WHERE hash='{}'""".format(_hash))
        if query.next():
            pth = query.value(0)
        return pth
    
    def getExVideos(self, sign_id, gloss_id):
        videos = [] #collections.OrderedDict()
        query = SooSLQuery(self.db)
        if gloss_id:
            query.exec_("""SELECT id, path FROM exVideo JOIN exVideo_gloss ON id=exVideo_id
                WHERE citation_id={} AND gloss_id={} ORDER BY exVideo_gloss.rowid""".format(sign_id, gloss_id))
        else:
            query.exec_("""SELECT id, path FROM exVideo JOIN exVideo_gloss ON id=exVideo_id
                WHERE citation_id={} ORDER BY exVideo_gloss.rowid""".format(sign_id))
        while query.next():
            _id = query.value(0)
            pth = query.value(1)
            videos.append([pth, _id])
        return videos
    
    def getExPictures(self, sign_id, gloss_id):
        pictures = [] 
        query = SooSLQuery(self.db)
        if gloss_id:
            query.exec_("""SELECT id, path FROM exPicture JOIN exPicture_gloss ON id=exPicture_id
                WHERE citation_id={} AND gloss_id={} ORDER BY exPicture_gloss.rowid""".format(sign_id, gloss_id))
        else:
            query.exec_("""SELECT id, path FROM exPicture JOIN exPicture_gloss ON id=exPicture_id
                WHERE citation_id={} ORDER BY exPicture_gloss.rowid""".format(sign_id))
        while query.next():
            _id = query.value(0)
            pth = query.value(1)
            pictures.append([pth, _id])
        return pictures
    
    def getExPicture(self, pict_id):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM exPicture WHERE id={}""".format(pict_id))
        while query.next():
            pth = query.value(0)
        return pth
    
    def getExPictureByHash(self, _hash):
        pth = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT path FROM exPicture WHERE hash='{}'""".format(_hash))
        if query.next():
            pth = query.value(0)
        return pth
    
    def getExTexts(self, sign_id):
        texts = collections.OrderedDict()
        if not sign_id or not int(sign_id):
            return texts
        query = SooSLQuery(self.db)
        query.prepare("""SELECT lang_id, text FROM exText WHERE id IN (SELECT id FROM exTextID WHERE sign_id=?)""")
        query.addBindValue(sign_id)
        query.exec_()
        while query.next():
            texts[query.value(0)] = query.value(1)
        return texts
    
    def getGlosses(self, sign_id):
        ## NOTE: more accurately named as 'getSenses'?
        """return list of glosses for a particular sign id
        """
        if not sign_id or not int(sign_id):
            return []    
        
        sign_id = str(sign_id)
        statement = """SELECT gloss_citation.gloss_id, lang_id, text FROM gloss_citation
            LEFT OUTER JOIN  glossText ON gloss_citation.gloss_id=glossText.gloss_id
            WHERE gloss_citation.citation_id=?
            ORDER BY gloss_citation.rowid, glossText.lang_id"""
        query = SooSLQuery(self.db)
        query.prepare(statement)
        query.addBindValue(sign_id)
        query.exec_()  
        
        prev_id = None
        gloss = collections.OrderedDict()
        glosses = []
        gloss_id = None    
        while query.next():
            gloss_id = query.value(0)
            lang_id = query.value(1)
            text = query.value(2)
              
            if gloss_id != prev_id: #new gloss
                if prev_id:
                    glosses.append(gloss)
                gloss = collections.OrderedDict()
                gloss[0] = gloss_id
                if text:
                    gloss[lang_id] = text
            else:
                if text:
                    gloss[lang_id] = text
            prev_id = gloss_id
        if gloss_id:
            glosses.append(gloss) #add final gloss
        glosses = [d.copy() for d in glosses]
        return glosses
    
    def removeGloss(self, gloss_id, sign_id, remove_sign=False):
        """remove gloss references, particularly when amending a sign entry with a previously unknown gloss.
        this leaves the actual gloss texts in the database; decision must be taken elsewhere if and when to delete.
        """
        tables = ["gloss_citation",
                  "exText_gloss",
                  "exPicture_gloss",
                  "exVideo_gloss",
                  "gloss_dialect",
                  "gloss_type",
                  "sentence_citation",
                  "gloss_type"
                  "exTextID"] 
        gloss_id = str(gloss_id)
        sign_id = str(sign_id)   
        query = SooSLQuery(self.db)    
        for table in tables:
            query.exec_("""DELETE FROM {} WHERE gloss_id={} AND citation_id={}""".format(table, gloss_id, sign_id))
         
        if not remove_sign:   #if not removing the entire sign, this is required 
            count = self.countSenses(sign_id)
            if count == 0:
                self.addGloss({}, sign_id)
            
    def removeGlossText(self, gloss_id):
        """remove gloss text if not required by other entries.
        """
        gloss_id = str(gloss_id)
        query = SooSLQuery(self.db)   
        query.prepare("""SELECT count(gloss_id) FROM gloss_citation WHERE gloss_id=?""")
        query.addBindValue(gloss_id)
        query.exec_()
        count = 0
        while query.next():
            count = query.value(0)
        if count == 0:
            query.exec_("""DELETE FROM glossText WHERE gloss_id={}""".format(gloss_id))
            query.exec_("""DELETE FROM glossID WHERE id={}""".format(gloss_id))
        
    def removeSentence(self, sign_id, gloss_id, sentence_id):
        """remove sentence references
        """    
        tables = ["sentence_citation"]         
        query = SooSLQuery(self.db)    
        for table in tables:
            query.exec_("""DELETE FROM {} WHERE citation_id={} AND gloss_id={} AND sentence_id={}""".format(table, sign_id, gloss_id, sentence_id))
         
        query.exec_("""SELECT text_id, video_id FROM sentence WHERE ID={}""".format(sentence_id))
        while query.next():
            text_id = query.value(0)
            video_id = query.value(1)
        # do any other signs use this sentence?
        query.exec_("""SELECT count(sentence_id) FROM sentence_citation WHERE sentence_id={}""".format(sentence_id))  
        count = -1
        while query.next():
            count = query.value(0)
        if count == 0:
            query.exec_("""DELETE FROM sentence WHERE id={}""".format(sentence_id))
            self.removeSentenceText(text_id)
            self.removeSentenceVideo(video_id)
            
    def findOldUnglossedSigns(self):
        """ for 0.8.4 and earlier """
        query = SooSLQuery(self.db)
        query.prepare("""SELECT gloss_id FROM glossText WHERE text LIKE ?""")
        query.addBindValue('###%')
        query.exec_()
        glosses = []
        while query.next():
            glosses.append(query.value(0))#ids of 'UNKNOWN' glosses
        signs = []
        _ids = [d._id for d in self.allDialects()]
        for gloss in glosses:
            signs.append((gloss, self.signsByGloss(gloss, _ids)))
        return signs        
    
    def findUnglossedSigns(self, dialects):
        """ for later than 0.8.4"""
        query = SooSLQuery(self.db)
        query.prepare("""SELECT id FROM glossID WHERE id NOT IN (SELECT gloss_id FROM glossText)""")
        query.exec_()
        signs = []
        dialect_ids = [d._id for d in dialects]
        while query.next():
            sign_ids = self.signsByGloss(query.value(0), dialect_ids)
            for _id in sign_ids:
                if _id not in signs:
                    signs.append(_id)
        return signs
        
    def addGloss(self, gloss_dict, sign_id):
        #gloss_dict ==> {0:gloss_id, lang_id: text}
        query = SooSLQuery(self.db)   
        gloss_id = gloss_dict.get(0)
        if not gloss_id or isinstance(gloss_id, str): #new gloss text
            query.exec_("""INSERT INTO glossID DEFAULT VALUES""")
            gloss_id = query.lastInsertId()
        query.prepare("""INSERT INTO gloss_citation ('gloss_id', 'citation_id') VALUES (?, ?)""")
        query.addBindValue(gloss_id)
        query.addBindValue(sign_id)
        query.exec_()
         
        ## NOTE: allow duplicate glosses, particularly when a duplicate gloss can have a different dialect, although this isn't enforced (yet)   
        lang_ids = [_id for _id in gloss_dict.keys() if int(_id) > 0]
        for lang_id in lang_ids:
            text = gloss_dict.get(lang_id).strip()
            if text:
                query.prepare("""INSERT INTO glossText ('gloss_id', 'lang_id', 'text') VALUES (?, ?, ?)""")
                query.addBindValue(gloss_id)
                query.addBindValue(lang_id)
                query.addBindValue(text)
                query.exec_()
        return gloss_id
    
    def amendGloss(self, new_dict, old_dict, sign_id):
        gloss_keys = sorted(new_dict.keys())
        lang_ids = [key for key in gloss_keys if int(key) > 0]
        new_id = new_dict.get(0)
         
        for lang_id in lang_ids:       
            if new_dict.get(lang_id) != old_dict.get(lang_id):
                new_gloss = new_dict.get(lang_id)     
                query = SooSLQuery(self.db)
                text = new_gloss.strip()
                query.exec_("""SELECT text FROM glossText WHERE gloss_id={} AND lang_id={}""".format(new_id, lang_id))
                if query.next():
                    if text:
                        query.prepare("""UPDATE glossText SET text=?
                        WHERE gloss_id=? AND lang_id=?""")
                        query.addBindValue(text)
                        query.addBindValue(new_id)
                        query.addBindValue(lang_id)
                        query.exec_()
                    else: #if text has been reduced to nothing, remove it
                        query.prepare("""DELETE FROM glossText WHERE gloss_id=? AND lang_id=?""")
                        query.addBindValue(new_id)
                        query.addBindValue(lang_id)
                        query.exec_()
                else:
                    query.prepare("""INSERT INTO glossText ('gloss_id', 'lang_id', 'text') VALUES (?, ?, ?)""")
                    query.addBindValue(new_id)
                    query.addBindValue(lang_id)
                    query.addBindValue(text)
                    query.exec_()           
                     
        return new_id
        
    def addSentenceVideo(self, video, _hash):
        name = os.path.basename(video)
        query = SooSLQuery(self.db)
        if _hash:
            query.exec_("""INSERT INTO sentenceVideo ('path', 'hash') VALUES ("{}", "{}")""".format(name, _hash))
        else:
            query.exec_("""INSERT INTO sentenceVideo ('path') VALUES ("{}")""".format(name))
             
        return query.lastInsertId()
    
    def amendSentence(self, video, orig_video, texts, orig_texts, sign_id,  gloss_id, sentence_id, response=2, hash=None): 
        query = SooSLQuery(self.db)
        if video:
            pth = os.path.basename(video)
            if video != orig_video and not orig_video:
                video_id = self.addSentenceVideo(pth)
                query.exec_("""UPDATE sentence SET video_id={} WHERE id={}""".format(video_id, sentence_id))
            elif orig_video: # replace old video
                orig_pth = os.path.basename(orig_video)
                orig_id = None
                query.exec_("""SELECT id FROM sentenceVideo WHERE path='{}'""".format(orig_pth))
                if query.next():
                    orig_id = query.value(0)
                if response == 2: # amend for all sentences which used original video
                    self.updateSentenceVideo(video, orig_id, hash)
                elif not response or response == 1: # amend for this sentence only
                    self.__amendSentenceVideo(video, sentence_id, hash)
             
        if texts and texts != orig_texts:
            _id = texts.get(0)
            #no original texts
            orig_id = orig_texts.get(0)
            if not orig_id:
                if _id is None:
                    texts_id = self.addSentenceText(texts)
                else:
                    texts_id = _id
                query.exec_("""UPDATE sentence SET text_id={} WHERE id={}""".format(texts_id, sentence_id))
             
            else:
                if _id == orig_id: #amend original texts
                    self.amendSentenceText(_id, texts)
                else: #amend texts with existing text
                    query.exec_("""UPDATE sentence SET text_id={} WHERE id={}""".format(_id, sentence_id))
                    
    def __amendSentenceVideo(self, video, sent_id, _hash):
        query = SooSLQuery(self.db)
        video_id = self.addSentenceVideo(video, _hash)
        new_video = self.parent().joinFilenameId(video, video_id)
        os.replace(video, new_video)
        self.updateSentenceVideo(new_video, video_id, _hash)
        query.exec_("""UPDATE sentence SET video_id={} WHERE id={}""".format(video_id, sent_id))
    
    def updateSentenceVideo(self, new_video, sentence_video_id, _hash):
        pth = os.path.basename(new_video)
        query = SooSLQuery(self.db)
        query.exec_("""UPDATE sentenceVideo SET path="{}", hash="{}" WHERE id={}""".format(pth, _hash, sentence_video_id))
    
    def removeSentenceVideo(self, video_id):
        """remove sentence video if not required by other entries.
        """
        query = SooSLQuery(self.db)   
        query.prepare("""SELECT count(id) FROM sentence WHERE video_id=?""")
        query.addBindValue(video_id)
        query.exec_()
        while query.next():
            count = query.value(0)
        if not count:
            query.exec_("""DELETE FROM sentenceVideo WHERE id={}""".format(video_id))
            
    def addSentenceText(self, texts):
        query = SooSLQuery(self.db)
        text_id = texts.pop(0, None) #existing sentence?
        lang_ids = list(texts.keys())
         
        if not text_id: #new sentence text
            query.exec_("""INSERT INTO sentenceTextID DEFAULT VALUES""")
            text_id = query.lastInsertId() 
                  
        for lang_id in lang_ids:
            text = texts.get(lang_id).strip()
            if text:
                query.exec_("""INSERT INTO sentenceText ('id', 'lang_id', 'text') VALUES ("{}", "{}", "{}")""".format(text_id, lang_id, text))
        return text_id
    
    def amendSentenceText(self, text_id, texts):
        _id = text_id
        query = SooSLQuery(self.db)
        lang_ids = [k for k in texts.keys() if k and k > 0]
        for lang_id in lang_ids:
            text = texts.get(lang_id).strip()
            query.exec_("""SELECT text FROM sentenceText WHERE id={} AND lang_id={}""".format(_id, lang_id))
            if query.next():
                if not text:
                    query.prepare("""DELETE FROM sentenceText WHERE id=? AND lang_id=?""")
                    query.addBindValue(_id)
                    query.addBindValue(lang_id)
                else:
                    query.prepare("""UPDATE sentenceText SET text=? WHERE id=? AND lang_id=?""")
                    query.addBindValue(text)
                    query.addBindValue(_id)
                    query.addBindValue(lang_id)
                query.exec_()
            else:
                query.prepare("""INSERT INTO sentenceText ('id', 'lang_id', 'text') VALUES (?, ?, ?)""")
                query.addBindValue(_id)
                query.addBindValue(lang_id)
                query.addBindValue(text)
                query.exec_()
    
    def removeSentenceText(self, text_id):
        """remove sentence text if not required by other entries.
        """
        query = SooSLQuery(self.db)   
        query.prepare("""SELECT count(id) FROM sentence WHERE text_id=?""")
        query.addBindValue(text_id)
        query.exec_()
        while query.next():
            count = query.value(0)
        if not count:
            query.exec_("""DELETE FROM sentenceText WHERE id={}""".format(text_id))
            query.exec_("""DELETE FROM sentenceTextID WHERE id={}""".format(text_id))
        
    def addSentence(self, video, texts, sign_id, gloss_id, _hash):
        query = SooSLQuery(self.db)
        video_id = None
        text_id = None
        if video: 
            video_id = self.sentenceVideoId(video)
            if not video_id:
                video_id = self.addSentenceVideo(video, _hash)
                new_video = self.parent().joinFilenameId(video, video_id)
                os.replace(video, new_video)
                self.updateSentenceVideo(new_video, video_id, _hash)
        if texts:
            text_id = self.addSentenceText(texts)
        query.exec_("""INSERT INTO sentence ('video_id', 'text_id')
            VALUES ("{}", "{}")""".format(video_id, text_id))
        sentence_id = query.lastInsertId()
        query.exec_("""INSERT INTO sentence_citation ('citation_id', 'gloss_id', 'sentence_id')
            VALUES ("{}","{}","{}")""".format(sign_id, gloss_id, sentence_id))
        return sentence_id

    def getComponentId(self, code):
        component_id = 0
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id FROM component WHERE code='{}'""".format(code))
        while query.next():
            component_id = query.value(0)
        return component_id   
    
    def addComponent(self, code, sign_id):
        """insert a component code into the database
        """
        _id = self.getComponentId(code)
        query = SooSLQuery(self.db)
        if not _id:
            query.exec_("""INSERT INTO component ('code') VALUES ('{}')""".format(code))
            _id = query.lastInsertId()
        query.exec_("""INSERT INTO component_citation ('component_id', 'citation_id')
                       VALUES ('{}', '{}')""".format(_id, sign_id))        
    
    def removeComponent(self, code, sign_id):
        """remove a component code from database
        """
        code_id = self.getComponentId(code)
        if not code_id:
            return
        else:
            query = SooSLQuery(self.db)
            query.exec_("""SELECT rowid FROM component_citation WHERE (component_id='{}' AND citation_id='{}')""".format(code_id, sign_id))
            while query.next():
                row_id = query.value(0)
                query.exec_("""DELETE FROM component_citation WHERE (rowid='{}')""".format(row_id))
                break #we only want to delete one result per method call if more than one exists
        if not self.signCountByComponent(code):
            query.exec_("""DELETE FROM component WHERE (id='{}')""".format(code_id))

    def getOriginalHash(self, filename):
        query = SooSLQuery(self.db)
        root, tail = os.path.split(filename)
        if root.endswith('signs') or root.endswith('citations'):
            query.prepare("""SELECT hash FROM citation WHERE path=?""")
        elif root.endswith('sentences'):
            query.prepare("""SELECT hash FROM sentenceVideo WHERE path=?""")
        elif root.endswith('extra_videos') or root.endswith('explanatory_videos'):
            query.prepare("""SELECT hash FROM exVideo WHERE path=?""")
        elif root.endswith('extra_pictures') or root.endswith('explanatory_pictures'):
            query.prepare("""SELECT hash FROM exPicture WHERE path=?""")
        query.addBindValue(tail)
        _hash = None
        query.exec_()
        if query.next():
            _hash = query.value(0)
        return _hash        
            
    def signsByHash(self, _hash): 
        """return list of signs for a sign video-file hash
        """
        if not _hash:
            return 
        signs = [] 
        query = SooSLQuery(self.db)
        query_str = """SELECT id FROM citation WHERE hash='{}'""".format(_hash)         
        query.prepare(query_str)
        query.exec_()
        while query.next():
            signs.append(query.value(0))
        return signs  
    
    def signsByName(self, filename):
        if not filename:
            return
        name = os.path.basename(filename)
        signs = [] 
        query = SooSLQuery(self.db)
        query_str = """SELECT id FROM citation WHERE path='{}'""".format(name)         
        query.prepare(query_str)
        query.exec_()
        while query.next():
            signs.append(query.value(0))
        return signs     
            
    def signsByComponent(self, codes, dialects=[]):
        """return list of signs for a list of components
        """
        if not dialects:
            dialects = []
        if not codes:
            return
        code_set = set(codes)
        signs = []
        query = SooSLQuery(self.db)
        if isinstance(code_set, set) and len(code_set) > 1:
            codes = tuple(code_set)
            query_str = """SELECT citation.id, citation.path FROM citation
                WHERE citation.id IN
                (SELECT citation_id FROM component_citation WHERE component_id IN
                (SELECT id FROM component WHERE code IN {}))""".format(codes)
        elif isinstance(code_set, set) and len(code_set) == 1:
            code = list(code_set)[0]
            query_str = """SELECT citation.id, citation.path FROM citation
                WHERE citation.id IN
                (SELECT citation_id FROM component_citation WHERE component_id IN
                (SELECT id FROM component WHERE code='{}'))""".format(code)
        else:
            print('expecting set of codes, length >= 1')
            return
        query.prepare(query_str)
        query.exec_()
        glosses = []
        components = []
        #code_set = set(codes)
        while query.next():
            _id = query.value(0)
            components = self.getComponents(_id)
            add = True
            for c in code_set:
                #if sign doesn't have this component or has fewer of this component than we are searching for, then don't
                #add it to the list of signs to return; the following logic covers both of these cases
                #print("c {}".format(c))
                if codes.count(c) > components.count(c):
                    add = False
                sign_dialects = []
                if dialects:
                    sign_dialects = self.getSignDialects(_id)
                    sign_dialect_ids = [d._id for d in sign_dialects]
                    if not set.intersection(set(sign_dialect_ids), set(dialects)):
                        add = False
            if add:
                video_path = query.value(1)
                sign = (_id, video_path)           
                signs.append(sign)    
        return signs
    
    def signCountByComponent(self, code, dialect_ids=None):
        query = SooSLQuery(self.db)
        if not dialect_ids: #no dialect filtering
            query.exec_("""SELECT count(DISTINCT component_citation.citation_id) FROM component_citation JOIN component ON component_citation.component_id=component.id
                WHERE component.code='{0}'""".format(code))
            count = 0
            while query.next():
                count = query.value(0)
        else:
            query.exec_("""SELECT DISTINCT component_citation.citation_id FROM component_citation JOIN component ON component_citation.component_id=component.id
                WHERE component.code='{}'""".format(code))
            count = 0
            while query.next():
                sign_id = query.value(0)
                sign_dialects = self.getSignDialects(sign_id)
                sign_dialect_ids = [d._id for d in sign_dialects]
                if set.intersection(set(sign_dialect_ids), set(dialect_ids)):
                    count += 1
        return count
    
    def signCount(self):
        query = SooSLQuery(self.db)
        query.exec_("""SELECT count(citation.id) FROM citation""")
        count = 0
        while query.next():
            count = query.value(0)
        return count  
    
    def countSignsSensesForDialect(self, dialect_id):
        query = SooSLQuery(self.db)
        query.prepare("""SELECT count(DISTINCT citation_id), count(DISTINCT gloss_id) from gloss_dialect WHERE dialect_id=?""")
        query.addBindValue(dialect_id)
        query.exec_()
        sign_count, sense_count = (0, 0)
        while query.next():
            sign_count = query.value(0)
            sense_count = query.value(1)
        return (sign_count, sense_count) 
    
    def countSignsSensesForLanguage(self, lang_id):
        sign_count, sense_count = (0, 0)
        query = SooSLQuery(self.db) 
        query.prepare("""SELECT count(DISTINCT sign_id) FROM
            (SELECT citation_id AS sign_id FROM gloss_citation WHERE gloss_id IN (SELECT gloss_id FROM glossText WHERE lang_id=?)
            UNION
            SELECT citation_id AS sign_id FROM sentence_citation WHERE sentence_id IN (SELECT id FROM sentenceText WHERE lang_id=?)
            UNION
            SELECT sign_id FROM exTextID WHERE id IN (SELECT id FROM exText WHERE lang_id=?))""")
        query.addBindValue(lang_id)
        query.addBindValue(lang_id)
        query.addBindValue(lang_id)
        query.exec_()
        while query.next():
            sign_count = query.value(0)
        query.prepare("""SELECT count(DISTINCT gloss_id) FROM glossText WHERE lang_id=?""")
        query.addBindValue(lang_id)
        query.exec_()
        while query.next():
            sense_count = query.value(0)
        return (sign_count, sense_count)                
    
    def signCountByVideo(self, video_path):
        """return count of signs which use this sign
        """
        if isinstance(video_path, list):
            video_path = video_path[1]
        pth = None
        try:
            pth = os.path.basename(video_path)
        except:
            pass
        count = -1 #
        sign_id = None
        query = SooSLQuery(self.db)
        query.exec_("""SELECT id FROM citation WHERE path='{}'""".format(pth))
        while query.next():
            sign_id = query.value(0)
        if sign_id: #if not found, path has been amended and count returns -1 to indicate this
            count = 0
            query.exec_("""SELECT count(citation_id) FROM gloss_citation WHERE citation_id='{}'""".format(sign_id))
            while query.next():
                count = query.value(0)       
        return count
    
    def __getIdFromPath(self, pth):
        """path and database filenames should match. If they have been changed (by user?) in the filesystem, they probably still
        contain a unique id in the name which can be used to link with the database entries and keep them in sync. This should
        prevent any update code deleting file thinking its orphaned"""
        _id = None
        root, file_name = os.path.split(pth)
        if file_name.count('_id'):
            _id = file_name.split('_id')[-1].split('.')[0]
        return _id
    
    def orphanedFile(self, pth, _type='signs'):
        _id = None #no id found means file pth doesn't exist in db; therefore, it is orphaned and should return 'True'
        query = SooSLQuery(self.db)
        if _type == 'signs':
            query.exec_("""SELECT id FROM citation WHERE path='{}'""".format(os.path.basename(pth)))
        elif _type == 'sentences':
            query.exec_("""SELECT id FROM sentenceVideo WHERE path='{}'""".format(os.path.basename(pth)))
        elif _type == 'extra_videos':
            query.exec_("""SELECT id FROM exVideo WHERE path='{}'""".format(os.path.basename(pth)))  
        elif _type == 'extra_pictures':
            query.exec_("""SELECT id FROM exPicture WHERE path='{}'""".format(os.path.basename(pth))) 
            
        while query.next():
            _id = query.value(0)
            
        if _id:
            return False
        else: #no id for this file in database; could it be a damaged file path? check for id in name and match if possible
            _id = self.__getIdFromPath(pth)
            if not _id: #old path before id added? probably this has been updated already, but otherwise would indicate orphan
                return True
            else:
                db_pth = None
                if _type == 'signs':
                    db_pth = self.getSignVideo(_id)
                elif _type == 'sentences':
                    db_pth = self.sentenceVideoPath(_id)
                elif _type == 'extra_videos':
                    db_pth = self.getExVideo(_id) 
                elif _type == 'extra_pictures':    
                    db_pth = self.getExPicture(_id)
                if db_pth:
                    #db_pth is the one we want
                    return False #not really an orphaned file, just different name but same id
                    #NOTE: see this problem running a Japanese dictionary on an English machine
        return True
    
    def signCountByID(self, sign_id):
        """return count of signs which use this sign
        """
        ##NOTE: more accurate to say 'count of senses' for this sign (video) ??? see 'countSenses'
        query = SooSLQuery(self.db)
        count = -1 #
        if sign_id: #if not found, path has been amended and count returns -1 to indicate this
            count = 0
            query.prepare("""SELECT count(citation_id) FROM (SELECT DISTINCT gloss_id, citation_id FROM gloss_citation WHERE citation_id=?)""")
            query.addBindValue(sign_id)
            query.exec_()
            while query.next():
                count = query.value(0)
        return count
    
    def signCountByLanguage(self, lang_id):
        """return count of signs which use this written language
        """
        query = SooSLQuery(self.db)
        count = 0
        query.prepare("""SELECT count(sign_id) FROM
            (SELECT DISTINCT citation_id AS sign_id FROM gloss_citation WHERE gloss_id IN (SELECT gloss_id FROM glossText WHERE lang_id=?)
            UNION
            SELECT DISTINCT citation_id AS sign_id FROM sentence_citation WHERE sentence_id IN (SELECT id FROM sentenceText WHERE lang_id=?)
            UNION
            SELECT DISTINCT sign_id FROM exTextID WHERE id IN (SELECT id FROM exText WHERE lang_id=?))""")
        query.addBindValue(lang_id)
        query.addBindValue(lang_id)
        query.addBindValue(lang_id)
        query.exec_()
        while query.next():
            count = query.value(0)
        return count
    
    def senseCountByDialect(self, dialect_id):
        """return count of senses which use this dialect; could be greater than a
        sign count as sign could have more than one sense using the same dialect.
        """
        query = SooSLQuery(self.db)
        count = 0
        query.prepare("""SELECT count(id) FROM glossID WHERE id IN
            (SELECT DISTINCT gloss_id FROM gloss_dialect WHERE dialect_id=?)
            """)
        query.addBindValue(dialect_id)
        query.exec_()
        while query.next():
            count = query.value(0)
        return count
    
    def signCountByGramCat(self, type_id):
        """return count of signs which use this sign type
        """
        query = SooSLQuery(self.db)
        count = 0
        query.prepare("""SELECT count(sign_id) FROM
            (SELECT DISTINCT citation_id AS sign_id FROM gloss_type WHERE type_id=?)
            """)
        query.addBindValue(type_id)
        query.exec_()
        while query.next():
            count = query.value(0)
        return count
    
    def countSignsSensesForGramCat(self, type_id):
        """return count of signs and senses which use this sign type
        """
        query = SooSLQuery(self.db)
        sign_count, sense_count = (0, 0)
        query.prepare("""SELECT count(DISTINCT citation_id), count(DISTINCT gloss_id) FROM
            gloss_type WHERE type_id=?""")
        query.addBindValue(type_id)
        query.exec_()
        while query.next():
            sign_count = query.value(0)
            sense_count = query.value(1)
        return (sign_count, sense_count)
    
    def sentenceVideoPath(self, sent_id):
        query = SooSLQuery(self.db)
        query.prepare("""SELECT video_id FROM sentence WHERE id=?""")
        query.addBindValue(sent_id)
        query.exec_()
        video_id = None
        while query.next():
            video_id = query.value(0)
        if not video_id:
            return None
        else:
            query.prepare("""SELECT path FROM sentenceVideo WHERE id=?""")
            query.addBindValue(video_id)
            query.exec_()
            pth = None
            while query.next():
                pth = query.value(0)
            return pth 
            
    def sentenceVideoId(self, video_path):
        """returns id of video which uses this path
        """
        if video_path:
            pth = os.path.basename(video_path)
        else:
            return None
        query = SooSLQuery(self.db)   
        query.prepare("""SELECT id FROM sentenceVideo WHERE path=?""")
        query.addBindValue(pth)
        query.exec_()
        video_id = None
        while query.next():
            video_id = query.value(0)
        return video_id
    
    def sentenceVideoUsageCount(self, video_path):
        """returns the number of times this video is used by sign sentences
        """
        video_id = self.sentenceVideoId(video_path)
        count = 1
        if video_id:
            query = SooSLQuery(self.db)
            #assume record exists until proven otherwise
            query.prepare("""SELECT count(id) FROM sentence WHERE video_id=?""")
            query.addBindValue(video_id)
            query.exec_()
            while query.next():
                count = query.value(0)
        else:
            count = 0 
        return count
        
    def countFiles2Delete(self):
        query = SooSLQuery(self.db)
        query.exec_("""SELECT count(path) FROM files2Delete""")
        count = 0
        while query.next():
            count = query.value(0)
        return count
        
    def dropFilesToDelete(self):
        if not self.countFiles2Delete():
            query = SooSLQuery(self.db)
            query.exec_("""DROP TABLE IF EXISTS files2Delete""")
            return True
        return False
    
    def olderThan(self, version, current_version):
        if version == current_version:
            return False
        pattern = r'(\D+)'
        v1, v2, v3 = version.split('.')
        v1 = int(v1)
        v2 = int(v2)
        try:
            v3 = int(v3)
        except:
            micro = re.split(pattern, v3)
            v3 = int(micro[0])
            sep = micro[1]
            build = int(micro[2])
        else:
            sep = None
            build = 0
        cv1, cv2, cv3 = current_version.split('.')
        cv1 = int(cv1)
        cv2 = int(cv2)
        try:
            cv3 = int(cv3)
        except:
            micro = re.split(pattern, cv3)
            cv3 = int(micro[0])
            sep = micro[1]
            cbuild = int(micro[2])
        else:
            sep = None
            cbuild = 0
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
        
    def projectOlderThan(self, version):
        current_version = self.getVersion() #of database
         
        return self.olderThan(current_version, version)
        
    def sooslOlderThan(self, version):
        settings = qApp.instance().getSettings()
        soosl_version = settings.value("Version", '0.0.0')
        return self.olderThan(soosl_version, version)
    
    def embedID(self, _id, pth):
        if os.path.exists(pth):
            query = SooSLQuery(self.db)
            root, filename = os.path.split(pth)
            name, ext = os.path.splitext(filename)
            new_name = '{}_id{}{}'.format(name, _id, ext)
            new_pth = os.path.join(root, new_name)
            #amend database
            if root.endswith('signs') or root.endswith('citations'):
                query.prepare("""UPDATE citation SET path=? WHERE id=?""")
            elif root.endswith('sentences'):
                query.prepare("""UPDATE sentenceVideo SET path=? WHERE id=?""")
            elif root.endswith('extra_videos') or root.endswith('explanatory_videos'):
                query.prepare("""UPDATE exVideo SET path=? WHERE id=?""")
            elif root.endswith('extra_pictures') or root.endswith('explanatory_pictures'):
                query.prepare("""UPDATE exPicture SET path=? WHERE id=?""")
            query.addBindValue(new_name) 
            query.addBindValue(_id)  
            if query.exec_():
                try:
                    os.rename(pth, new_pth)
                except:
                    query.addBindValue(filename) 
                    query.addBindValue(_id) 
                    query.exec_()
                        
    def getGlossCount(self):
        return len(self.glosses())
                        
    def getUpdateSteps(self, _query=None):
        if _query:
            query = _query
        else:
            query = SooSLQuery(self.db)
        steps = 5
        if self.projectOlderThan('0.6.0'):
            steps += 1
        if self.projectOlderThan('0.6.2'):
            steps += 1
        if self.projectOlderThan('0.6.7'):
            steps += 1
        if self.projectOlderThan('0.7.4'):
            steps += 1
        if self.projectOlderThan('0.8.0'):
            steps += 1
        if self.projectOlderThan('0.8.3'):
            steps += 1
        if self.projectOlderThan('0.8.4'):
            steps += 1
        if self.projectOlderThan('0.8.6'):
            query.exec_("""SELECT count(id) FROM citation""")
            while query.next():
                steps += query.value(0)
            query.exec_("""SELECT count(id) FROM sentenceVideo""")
            while query.next():
                steps += query.value(0)
            query.exec_("""SELECT count(id) FROM exVideo""")
            while query.next():
                steps += query.value(0)
            query.exec_("""SELECT count(id) FROM exPicture""")
            while query.next():
                steps += query.value(0)
            if 'order' not in self.getCols('writtenLanguage', query):
                query.exec_("""SELECT count(id) FROM writtenLanguage""")
                while query.next():
                    steps += query.value(0) * 2
        if self.projectOlderThan('0.8.7'):
            query.exec_("""SELECT count(citation_id) FROM gloss_citation WHERE citation_id NOT IN
                        (SELECT citation_id FROM gloss_dialect WHERE gloss_dialect.gloss_id = gloss_citation.gloss_id AND
                         gloss_dialect.citation_id = gloss_citation.citation_id)""")
            while query.next():
                _steps = query.value(0)
                steps += _steps
            query.exec_("""SELECT count(id) FROM component""")
            while query.next():
                _steps = query.value(0)
                steps += _steps
        return steps
    
    def updateProgress(self, progress, text=None):
        if progress:
            try:
                if progress.wasCanceled():
                    progress.close()
                    del progress
                    return False
            except:
                pass
            update_progress = progress.value() + 1
            try:
                progress.parent().setProgressValue(update_progress)
            except:
                progress.setValue(update_progress)
            if text:
                try:
                    progress.setLabelText(text)
                except:
                    progress.parent().setProgressText(text)
        qApp.processEvents()
        return True
    
        
    def updateDB(self, message):
        settings = qApp.instance().getSettings()
        soosl_version = settings.value("Version")
        compatible_version = self.getCompatibleVersion()
        
        ## last version with db changes was 0.6.3.
        ## attempt to update newer database with incompatible software
        #last_db_update = '0.8.4'   
        if self.sooslOlderThan(compatible_version):
            return False 
        elif self.projectOlderThan(OLDEST_UPDATABLE):
            return False
        
        progress = None
        _max = self.getUpdateSteps() + self.getGlossCount()
        if _max > 10:            
            if hasattr(qApp.instance(), 'start_dlg'):
                progress = qApp.instance().start_dlg.progress_bar
            else:
                try:
                    progress = QProgressDialog(qApp.instance().getMainWindow())
                except:
                    progress = QProgressDialog(qApp.instance().start_dlg.progress_bar)
                setattr(qApp.instance(), 'progress_dlg', progress)
                progress.setWindowTitle(' ')
                if not int(settings.value('Testing', 0)): progress.setWindowModality(Qt.WindowModal)##NOTE: allows crash testing while testing
                progress.setCancelButton(None)
                progress.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
                progress.setMinimum(0)
                progress.setLabelText(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'))
                progress.forceShow()  
            progress.setMaximum(_max)
        query = SooSLQuery(self.db)
        #update to 0.6.0
        if self.projectOlderThan('0.6.0'): 
            self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.6.0'))
            
            query.exec_("""DROP TABLE IF EXISTS citation_type""")
            query.exec_("""DROP TABLE IF EXISTS sentence_type""")
            query.exec_("""DROP TABLE IF EXISTS exPicture_sentence""")
            query.exec_("""DROP TABLE IF EXISTS exVideo_sentence""")
        
            query.exec_("""DROP TABLE IF EXISTS type""") #may exist with incorrect values; hasn't yet been used in practise
            if 'citation_id' in self.getCols('exTextID'):
                query.exec_("""DROP TABLE IF EXISTS exTextID""") #may exist with incorrect columns; hasn't yet been used in practise
            
            query.exec_("""CREATE TABLE IF NOT EXISTS "exText" ("id" INTEGER NOT NULL, "lang_id" INTEGER NOT NULL,"text" TEXT NOT NULL, PRIMARY KEY ("id", "lang_id"))""")
            query.exec_("""CREATE TABLE IF NOT EXISTS "exTextID" ("id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "sign_id" INTEGER NOT NULL)""")
            query.exec_("""CREATE TABLE IF NOT EXISTS "type" (id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL, name TEXT UNIQUE)""")
            
            if not self.types():
                for t in ["Noun", "Verb", "Adj", "Quant"]:
                    self.addType(t)
        if self.projectOlderThan('0.6.2'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.6.2')): return (False, 1)
            #remove dominant hand location codes
            for code in ['500', '508', '510', '518']:
                code_id = self.getComponentId(code)
                if code_id:
                    query.exec_("""DELETE FROM component WHERE (id='{}')""".format(code_id))
                    query.exec_("""DELETE FROM component_citation WHERE (component_id='{}')""".format(code_id))
            #if any signs use old finger and palm locations for the non-dominant hand, replace with the signle new non-dom hand location
            sign_ids = []
            for code in ['504', '514']:
                signs = self.signsByComponent([code])
                _ids = [sign[0] for sign in signs]
                for _id in _ids:
                    self.removeComponent(code, _id) #remove component
                    if _id not in sign_ids: #only a small chance of duplication, but I want to make sure and not add new hand code twice in later step
                        sign_ids.append(_id)
            for sign_id in sign_ids:            
                self.addComponent('500', sign_id)
        if self.projectOlderThan('0.6.7'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.6.7')): return (False, 1)
            #adding project info and authorization to edit - added v0.6.7
            query.exec_("""CREATE TABLE IF NOT EXISTS "project" ("pass_message" TEXT, "author_message" TEXT)""")
        
        if self.projectOlderThan('0.7.4'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.7.4')): return (False, 1)
            # bug in Mac Version where location codes emitted as long numeric strings, instead of 3 character strings
            # representing hex code.
            comps = []
            query.exec_("""SELECT id FROM component WHERE length(code) > 3""")
            while query.next():
                comps.append(query.value(0))
            if comps:
                ids = tuple(comps)
                if len(ids) > 1:
                    str1 = """DELETE FROM component WHERE id IN {}""".format(ids)
                    str2 = """DELETE FROM component_citation WHERE component_id IN {}""".format(ids)
                else:
                    str1 = """DELETE FROM component WHERE id={}""".format(ids[0])
                    str2 = """DELETE FROM component_citation WHERE component_id={}""".format(ids[0])
                query.prepare(str1)
                query.exec_()
                query.prepare(str2)
                query.exec_()
        
        if self.projectOlderThan('0.8.0'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.8.0')): return (False, 1)
            # remove redundant 'heel' components
            for codes in [('14d', '14c'),
                          ('14f', '14e'),
                          ('151', '150'),
                          ('15c', '15b'),
                          ('15e', '15d'),
                          ('1f6', '1f5'),
                          ('204', '203'),
                          # one location on wrist & hand
                          ('504', '500'),
                          ('528', '520')]:
                sign_ids = []
                old, new = codes
                signs = self.signsByComponent([old])
                if signs:
                    _ids = [sign[0] for sign in signs]
                    for _id in _ids:
                        self.removeComponent(old, _id) #remove component
                        if _id not in sign_ids: #only a small chance of duplication, but I want to make sure and not add new hand code twice in later step
                            sign_ids.append(_id)
                    for sign_id in sign_ids:            
                        self.addComponent(new, sign_id)
        
        if self.projectOlderThan('0.8.3'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.8.3')): return (False, 1)
            self.savePassMessage(message) #older databases were all read-write
        
        if self.projectOlderThan('0.8.4'): 
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.8.4')): 
                return (False, 1)          
            #0.8.4
            signs = self.findOldUnglossedSigns()
            for sign in signs:
                unknown_id, sign_ids = sign #UNKNOWN gloss id
                for sign_id in sign_ids:
                    sentences = self.getSentences(sign_id, unknown_id)
                    _types = self.getGramCats(sign_id, unknown_id)
                    dialects = self.getSignDialects(sign_id)        
                    new_id = self.addGloss({0:0}, sign_id)
                    for sent in sentences:
                        _id, video, texts = sent
                        video_file = video[1]
                        sent_dir = self.parent().sign_model.get_root('sent')
                        video_file = os.path.join(sent_dir, video_file)
                        self.addSentence(video_file, texts, sign_id, new_id, None) 
                    for t in _types:
                        self.linkGramCat(t[0], sign_id, new_id)                
                    for d in dialects:
                        self.linkDialect(d._id, sign_id, new_id)             
                    self.removeGloss(unknown_id, sign_id)
                    self.removeGlossText(unknown_id) 
        ##added in 0.7.4, removed in 0.8.5
        #query.exec_("""ALTER TABLE "writtenLanguage" ADD COLUMN "layout" INTEGER NOT NULL DEFAULT 0""")
        # all citations have a gloss even if it is 'UNKNOWN' (###), and sentences are linked to a gloss of a particular
        # dialect, so the only dialect link table required is gloss_dialect. Remove the others.
        query.exec_("""DROP TABLE IF EXISTS citation_dialect""")
        query.exec_("""DROP TABLE IF EXISTS sentence_dialect""")
        #added in 0.7.6
        query.exec_("""DROP TRIGGER IF EXISTS sign_type_delete""")
        #update version string; possibly should be the last step in the update process as other steps may depend on it
        query.exec_("""CREATE TABLE IF NOT EXISTS "meta" ("version" TEXT NOT NULL )""")
        #added in 0.8.4
        query.exec_("""ALTER TABLE "meta" ADD COLUMN "compatible_version" TEXT NOT NULL DEFAULT '0.8.4'""")
        if self.projectOlderThan('0.8.5'):
            if not self.updateProgress(progress, '{} {}'.format('Applying updates', '0.8.5')): 
                return (False, 1)
            #added in 0.8.5
            if 'order' not in self.getCols('writtenLanguage'):
                query.exec_("""ALTER TABLE "writtenLanguage" ADD COLUMN "order" INTEGER NOT NULL DEFAULT 1""")
                lang_ids = []
                query.exec_("""SELECT id, name, focal FROM writtenLanguage ORDER BY name""")
                while query.next():
                    if not self.updateProgress(progress): return (False, 1)
                    _id = query.value(0)
                    focal = query.value(2)
                    if focal == 'true':
                        lang_ids.insert(0, _id)
                    else:
                        lang_ids.append(_id)
                                  
                _count = 1
                for _id in lang_ids:
                    focal = False
                    if _count == 1:
                        focal = True
                    query.prepare("""UPDATE "writtenLanguage" SET "focal"=?, "order"=? WHERE "id"=?""")
                    query.addBindValue(focal)
                    query.addBindValue(_count)
                    query.addBindValue(_id)
                    query.exec_()
                    _count += 1  
                    if not self.updateProgress(progress): return (False, 1)    
            
    #         deleting sign hasn't fully cleaned up the database
    #         No problems caused but unnecessary data in database needed to be removed
    #         Add code here to remove entries referencing deleted citation/sign_ids
            query.exec_("""SELECT exVideo_id, citation_id, gloss_id FROM exVideo_gloss WHERE exVideo_gloss.citation_id NOT IN (SELECT id FROM citation)""")
            while query.next():
                _id = query.value(0)
                sign_id = query.value(0)
                gloss_id = query.value(0)
                if _id:
                    count = self.countExVideos(_id)
                    if count <= 1: #video not used by other signs; full delete from database
                        self.removeExVideo(_id, sign_id, gloss_id, delete_all=True)
                    else:
                        self.removeExVideo(_id, sign_id, gloss_id, delete_all=False)
            if not self.updateProgress(progress): return (False, 1)
                        
            query.exec_("""SELECT exPicture_id, citation_id, gloss_id FROM exPicture_gloss WHERE exPicture_gloss.citation_id NOT IN (SELECT id FROM citation)""")
            while query.next():
                _id = query.value(0)
                sign_id = query.value(0)
                gloss_id = query.value(0)
                if _id:
                    count = self.countExPictures(_id)
                    if count <= 1: #video not used by other signs; full delete from database
                        self.removeExPicture(_id, sign_id, gloss_id, delete_all=True)
                    else:
                        self.removeExPicture(_id, sign_id, gloss_id, delete_all=False)
            if not self.updateProgress(progress): return (False, 1)
                        
            query.exec_("""SELECT id, video_id, text_id FROM sentence WHERE sentence.id NOT IN (SELECT sentence_id FROM sentence_citation)""")
            while query.next():
                sent_id = query.value(0)
                sent_video_id = query.value(1)
                sent_text_id = query.value(2)
                if sent_id:
                    query2 = SooSLQuery(self.db) 
                    query2.exec_("""DELETE FROM sentence WHERE id={}""".format(sent_id))
                    self.removeSentenceText(sent_text_id)
                    self.removeSentenceVideo(sent_video_id)
            if not self.updateProgress(progress): 
                return (False, 1)
                    
            query.exec_("""SELECT gloss_id, citation_id FROM gloss_citation WHERE gloss_citation.citation_id NOT IN (SELECT id FROM citation)""")
            while query.next():
                gloss_id = query.value(0)
                sign_id = query.value(1)
                if sign_id:
                    self.removeGloss(gloss_id, sign_id, remove_sign=True)
                    self.removeGlossText(gloss_id) 
            if not self.updateProgress(progress): 
                return (False, 1)
                    
            query.exec_("""DELETE FROM component WHERE component.id NOT IN (SELECT component_id FROM component_citation)""")
            query.exec_("""DELETE FROM exText WHERE id IN (SELECT id FROM exTextID WHERE sign_id NOT IN (SELECT id FROM citation))""")
            query.exec_("""DELETE FROM exTextID WHERE id IN (SELECT id FROM exTextID WHERE sign_id NOT IN (SELECT id FROM citation))""")       
            
            ##NOTE: cleanup video/picture entries where there is no related media in the file system
            project_dir = os.path.dirname(self.db.databaseName())
            for _types, _query in [
                (('citations', 'signs'), """SELECT id, path FROM citation"""),
                (('sentences', 'sentences'), """SELECT id, path FROM sentenceVideo"""),
                (('explanatory_videos', 'extra_videos'), """SELECT id, path FROM exVideo"""),
                (('explanatory_pictures', 'extra_pictures'), """SELECT id, path FROM exPicture""")
                ]:                
                    query.exec_(_query)
                    while query.next():
                        if not self.updateProgress(progress): 
                            return (False, 1)
                        
                        _id = query.value(0)
                        _type = _types[0]
                        _dir = os.path.join(project_dir, _type)
                        if not os.path.exists(_dir):
                            _type = _types[1]
                            _dir = os.path.join(project_dir, _type)
                        pth = os.path.join(_dir, query.value(1))
                        if os.path.exists(pth):
                            # all is fine!
                            if not pth.count('_id{}.'.format(_id)): #update to new naming policy
                                self.embedID(_id, pth)
                        else:
                            pth_id = self.__getIdFromPath(pth) #should be the same as _id, but want to use if not
                            matching_pths = None
                            if pth_id: #old naming policy
                                matching_pths = glob.glob('{}{}*_id{}.*'.format(_dir, os.sep, _id))
                            if not pth_id or not matching_pths:
                                query2 = SooSLQuery(self.db)
                                if _type == 'signs':
                                    query2.exec_("""DELETE FROM citation WHERE id={}""".format(_id))
                                elif _type == 'sentences':
                                    query2.exec_("""DELETE FROM sentenceVideo WHERE id={}""".format(_id))
                                elif _type == 'extra_videos':
                                    query2.exec_("""DELETE FROM exVideo WHERE id={}""".format(_id))
                                elif _type == 'extra_pictures':
                                    query2.exec_("""DELETE FROM exPicture WHERE id={}""".format(_id))
                                    
        if self.projectOlderThan('0.8.7'):
            if not self.updateProgress(progress, '{} ({})'.format(qApp.instance().translate('SooSLDatabaseManager', 'Updating dictionary'), '0.8.7')): 
                return (False, 1)
        # find signs linked to the current focal dialect and really link them
        # previously assumed focal dialect if dialect not found; now wish to add definite value into db to avoid confusion 
            query.exec_("""SELECT citation_id, gloss_id FROM gloss_citation WHERE citation_id NOT IN
                        (SELECT citation_id FROM gloss_dialect WHERE gloss_dialect.gloss_id = gloss_citation.gloss_id AND
                         gloss_dialect.citation_id = gloss_citation.citation_id)""")
            focal_id = self.getFocalDialect()._id
            while query.next():
                if not self.updateProgress(progress): return (False, 1)
                sign_id = query.value(0)
                gloss_id = query.value(1)
                self.linkDialect(focal_id, sign_id, gloss_id)
                
            # add column for original file hashes to identify attempts to import already used videos/pictures 
            for table in ['citation', 'sentenceVideo', 'exVideo', 'exPicture']:
                query_str = """ALTER TABLE "{}" ADD COLUMN "hash" TEXT""".format(table) 
                query.prepare(query_str) 
                query.exec_() 
                
        # update component codes for new movement notation 
        app_dir = qApp.instance().getAppDir()
        ccc = os.path.join(app_dir, 'codes_convert.txt')
        if sys.platform.startswith('darwin'):
            if not os.path.exists(ccc):
                ccc = os.path.join(os.path.dirname(app_dir), 'Resources', 'codes_convert.txt')
        with io.open(ccc, 'r', encoding='utf-8') as conversion_file:
            lines = [line for line in conversion_file.read().splitlines() if not line.startswith('#')]
        to_delete = []
        convert_dict = collections.OrderedDict()
        for line in lines:
            old, new = line.split(',', 1)
            if old == new:
                continue 
            if new == '000':
                to_delete.append(old)
                continue  
            convert_dict[old] = new.split(',')
        component_ids = []
        query.exec_("""SELECT * FROM component""")
        query2 = SooSLQuery(self.db)
        query2.prepare("""SELECT citation_id FROM component_citation WHERE component_id=?""")
        while query.next():
            if not self.updateProgress(progress): return (False, 1)
            comp_id = query.value(0)
            component_ids.append(comp_id)
            sign_ids = []
            query2.addBindValue(comp_id) #find signs
            query2.exec_()
            while query2.next():
                sign_ids.append(query2.value(0))
                
            old_code = query.value(1)
            new_codes = convert_dict.get(old_code)
            if new_codes:
                new_code = new_codes[0]
                self.convertCompCode(old_code, new_code, sign_ids)
                qApp.processEvents()
                
                more_codes = new_codes[1:]
                if more_codes and sign_ids:
                    for code in more_codes:
                        for sign_id in sign_ids:
                            self.addComponent(code, sign_id)
                            
        if to_delete: 
            for code in to_delete:
                query.prepare("""SELECT id FROM component WHERE code=?""")
                query.addBindValue(code)
                query.exec_()
                _id = None
                while query.next():
                    _id = query.value(0)
                if _id:
                    query.prepare("""DELETE FROM component WHERE code=?""")
                    query.addBindValue(code)
                    query.exec_() 
                    query.prepare("""DELETE FROM component_citation WHERE component_id=?""")
                    query.addBindValue(_id)
                    query.exec_()
                          
            #purge duplicate entries - no longer required with new 'sign types'
            for _id in component_ids:
                query.prepare("""SELECT rowid, component_id, citation_id FROM component_citation WHERE component_id=?""")
                query.addBindValue(_id)
                query.exec_()
                sign_comps = []
                while query.next():
                    row = query.value(0)
                    sign_id = query.value(1)
                    comp_id = query.value(2)
                    sign_comp = (sign_id, comp_id)
                    if sign_comp in sign_comps:
                        query2.prepare("""DELETE FROM component_citation WHERE rowid=?""")
                        query2.addBindValue(row)
                        query2.exec_()
                    else:
                        sign_comps.append(sign_comp)       
        
        if self.projectOlderThan(soosl_version):
            if not self.updateProgress(progress): 
                return (False, 1)      
            self.setVersion(soosl_version, LAST_DB_UPDATE)
            
        try:
            progress.close()
        except:
            pass
        return True
    
    def convertCompCode(self, old_code, new_code, sign_ids):
        query = SooSLQuery(self.db) 
        query.prepare("""SELECT id FROM component WHERE code=?""") #find comp id
        query2 = SooSLQuery(self.db) 
        query2.prepare("""UPDATE component SET code=? WHERE id=?""")
        query3 = SooSLQuery(self.db) 
        query3.prepare("""UPDATE component_citation SET component_id=? WHERE citation_id=? AND component_id=?""")
        
        #determine if the new code already exists
        new_comp_id = None
        query.addBindValue(new_code)
        query.exec_()
        while query.next():
            new_comp_id = query.value(0)
            
        old_comp_id = None
        query.addBindValue(old_code)
        query.exec_()
        while query.next():
            old_comp_id = query.value(0)    
            
        if not new_comp_id: #if new doesn't already exist, update old to new            
            if old_comp_id: #something wrong if this isn't true!
                query2.addBindValue(new_code)
                query2.addBindValue(old_comp_id)
                query2.exec_()
                qApp.processEvents()
        else: #update existing signs to use new comp_id value
            for sign_id in sign_ids:
                query3.addBindValue(new_comp_id)
                query3.addBindValue(sign_id)
                query3.addBindValue(old_comp_id)
                query3.exec_()
                qApp.processEvents() 
            #old component with old comp id no longer needed               
            query.prepare("""DELETE FROM component WHERE id=?""")
            query.addBindValue(old_comp_id)
            query.exec_()
