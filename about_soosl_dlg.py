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
import os
import sys
import re

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSize
#from PyQt5.QtCore import QEvent

from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QSizePolicy, QVBoxLayout, QGridLayout
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtWidgets import qApp
from PyQt5.QtWidgets import QTextBrowser


class AboutSooSLDlg(QDialog):

    def __init__(self, version, build, parent=None):
        super(AboutSooSLDlg, self).__init__(parent=parent, flags=Qt.WindowTitleHint |
                                            Qt.WindowSystemMenuHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet('QDialog{background: white;}')
        #self.installEventFilter(self)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.logo_lbl = QLabel()
        self.logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # https://stackoverflow.com/questions/7010611/how-can-i-crop-an-image-in-qt
        pxm = QPixmap(':/soosl_logo.png')
        r = pxm.rect().adjusted(4, 4, -4, -60)
        pxm = pxm.copy(r)
        h = int(pxm.height() * 0.8)
        pxm = pxm.scaledToHeight(h, Qt.SmoothTransformation)
        self.logo_lbl.setPixmap(pxm)
        layout.addWidget(self.logo_lbl, 0, 0)

        title = f"{qApp.instance().translate('AboutSooSLDlg', 'About')} - SooSL™"
        self.setWindowTitle(qApp.instance().translate('AboutSooSLDlg', title))

        icn = QIcon(':/help.png')
        about_txt = qApp.instance().translate('AboutSooSLDlg', "Help")
        terms_txt = qApp.instance().translate('AboutSooSLDlg', "Terms of Use")
        priv_txt = qApp.instance().translate('AboutSooSLDlg', "Privacy Policy")
        lic_txt = qApp.instance().translate('AboutSooSLDlg', "Licensing")
        settings = qApp.instance().getSettings()
        help_source = settings.value('helpSource', 'local')        
        if help_source == 'online':
            icn = QIcon(':/help_online.png')
        #     about_txt = qApp.instance().translate('AboutSooSLDlg', "Help (online)")
        #     terms_txt = qApp.instance().translate('AboutSooSLDlg', "Terms of Use (online)")
        #     priv_txt = qApp.instance().translate('AboutSooSLDlg', "Privacy Policy (online)")
        #     lic_txt = qApp.instance().translate('AboutSooSLDlg', "Licensing (online)")
        about_action = QAction(icn, about_txt, self, triggered=self.showAboutSooSL)        
        terms_action = QAction(icn, terms_txt, self, triggered=self.showTermsOfUse)
        privacy_action = QAction(icn, priv_txt, self, triggered=self.showPrivacyStatement)
        license_action = QAction(icn, lic_txt, self, triggered=self.showLicensing)
        notes_action = QAction(QIcon(':/text_file.png'), qApp.instance().translate(
            'AboutSooSLDlg', "Release Notes"), self, triggered=self.showReleaseNotes)

        vlayout = QVBoxLayout()
        vlayout.setSpacing(3)
        vlayout.setContentsMargins(3, 3, 3, 3)
        about_btn = QToolButton()
        about_btn.setDefaultAction(about_action)
        terms_btn = QToolButton()
        terms_btn.setDefaultAction(terms_action)
        privacy_btn = QToolButton()
        privacy_btn.setDefaultAction(privacy_action)
        license_btn = QToolButton()
        license_btn.setDefaultAction(license_action)
        notes_btn = QToolButton()
        notes_btn.setDefaultAction(notes_action)
        for btn in [about_btn, terms_btn, privacy_btn, license_btn, notes_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            vlayout.addWidget(btn)
        vlayout.addStretch()
        layout.addLayout(vlayout, 0, 1, 2, 1)
        #layout.addWidget(QLabel(title), 1, 0)

        btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
        close_btn = btnBox.button(QDialogButtonBox.Ok)
        close_btn.setText(qApp.instance().translate('AboutSooSLDlg', 'Close'))
        btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btnBox.button(QDialogButtonBox.Ok).setCursor(
            QCursor(Qt.PointingHandCursor))
        btnBox.accepted.connect(self.accept)
        vlayout.addWidget(btnBox)

        text = ' SooSL™ {} ({})'.format(version, build)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(lbl, 1, 0)

        self.setLayout(layout)

    # def eventFilter(self, obj, evt):
    #     # trying to turn off tool tips - just repeats text already there
    #     if evt.type() == QEvent.ToolTip:
    #         print('tooltip', obj.text())
    #         return True
    #     return super(AboutSooSLDlg, self).eventFilter(obj, evt)

    def resizeEvent(self, evt):
        self.setFixedSize(self.size())
        super(AboutSooSLDlg, self).resizeEvent(evt)

    def showAboutSooSL(self):
        mw = qApp.instance().getMainWindow()
        mw.helpSooSL(topic='AboutSooSLT', context_id=0)
        self.accept()

    def showTermsOfUse(self):
        mw = qApp.instance().getMainWindow()
        mw.helpSooSL(topic='Termsofuse', context_id=10)
        self.accept()

    def showPrivacyStatement(self):
        mw = qApp.instance().getMainWindow()
        mw.helpSooSL(topic='Privacypolicy', context_id=20)
        self.accept()

    def showLicensing(self):
        mw = qApp.instance().getMainWindow()
        mw.helpSooSL(topic='License', context_id=50)
        self.accept()

    def showReleaseNotes(self):
        dlg = ReleaseNotesDlg(self)
        dlg.exec_()
        self.accept()

class ReleaseNotesDlg(QDialog):

    def __init__(self, parent=None):
        super(ReleaseNotesDlg, self).__init__(parent=parent,
                                              flags=Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowStaysOnTopHint)
        version = qApp.instance().pm.getSooSLVersion().split('_')[0]
        notes = self.getReleaseNotes(version)
        self.setWindowTitle(
            '{} - SooSL™ {}'.format(qApp.instance().translate('ReleaseNotesDlg', 'Release Notes'), version))
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tb.setReadOnly(True)
        tb.setHtml(notes)
        layout.addWidget(tb)

        btnBox = QDialogButtonBox(QDialogButtonBox.Ok)
        btnBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btnBox.button(QDialogButtonBox.Ok).setCursor(
            QCursor(Qt.PointingHandCursor))
        btnBox.accepted.connect(self.accept)
        layout.addWidget(btnBox)

        self.setLayout(layout)

    def getReleaseNotes(self, version):
        docs_dir = qApp.instance().getDocsDir()
        release_path = os.path.join(docs_dir, "RELEASE_NOTES")
        if os.path.exists(release_path):
            release_lines = self.getReleaseLines(release_path, version)
            release_lines.insert(0, '<body>')
            release_lines.insert(0, '<html>')
            release_lines.append('<br><br>')
            txt = qApp.instance().translate('ReleaseNotesDlg', """See website <a href="https://soosl.net/older_software_and_sources.html#Changes">
                https://soosl.net/older_software_and_sources.html#Changes</a> to see release notes for earlier versions.""")
            release_lines.append(f'<p>{txt}</p>')
            release_lines.append('</body>')
            release_lines.append('</html>')
            in_list = False
            added_txt = qApp.instance().translate('ReleaseNotesDlg', 'Added')
            added_txt = f'<p style="color:blue;"><STRONG>{added_txt}</STRONG></p>'
            fixed_txt = qApp.instance().translate('ReleaseNotesDlg', 'Fixed')
            fixed_txt = f'<p style="color:blue;"><STRONG>{fixed_txt}</STRONG></p>'
            changed_txt = qApp.instance().translate('ReleaseNotesDlg', 'Changed')
            changed_txt = f'<p style="color:blue;"><STRONG>{changed_txt}</STRONG></p>'
            for idx, l in enumerate(release_lines):
                l = l.lstrip()
                if not in_list and l.startswith('<li>'):
                    release_lines.insert(idx, '<ul>')
                    in_list = True
                elif in_list and l.startswith('Added'):
                    release_lines[idx] = added_txt
                    release_lines.insert(idx, '</ul>')
                    in_list = False
                elif l.startswith('Added'):
                    release_lines[idx] = added_txt
                elif in_list and l.startswith('Fixed'):
                    release_lines[idx] = fixed_txt
                    release_lines.insert(idx, '</ul>')
                    in_list = False
                elif l.startswith('Fixed'):
                    release_lines[idx] = fixed_txt
                elif in_list and l.startswith('Changed'):
                    release_lines[idx] = changed_txt
                    release_lines.insert(idx, '</ul>')
                    in_list = False
                elif l.startswith('Changed'):
                    release_lines[idx] = changed_txt
                elif in_list and (l.startswith('#') or l.startswith('<p>') or l.startswith('</body>')):
                    release_lines.insert(idx, '</ul>')
                    in_list = False

            html = '\n'.join(release_lines)
            return html
        return '<h3>{}</h3>'.format(qApp.instance().translate('ReleaseNotesDlg', 'Release notes not found.'))

    def getReleaseLines(self, release_path, version):
        release_lines = []
        with open(release_path, encoding='UTF-8') as f:
            lines = f.readlines()
        append_ = False
        for l in lines:
            if l.startswith('## [') and not l.startswith('## [{}'.format(version)):
                append_ = False
            if append_ or l.startswith('## [{}'.format(version)):
                append_ = True
                release_lines.append(l)

        for idx, l in enumerate(release_lines):
            l = l.strip()
            if l.startswith('###'):
                l = l.lstrip('# ')
            elif l.startswith('##'):
                version, release_date = l.split('-', 1)
                version = re.findall('[0-9]+', version) # find the numbers; single digits for version numbers, 6 digit build number
                build = version[-1]
                version_txt = qApp.instance().translate('ReleaseNotesDlg', "Version:")
                release_txt = qApp.instance().translate('ReleaseNotesDlg', "Release date:")
                version = '.'.join(version[:-1]) # Join together version numbers, excluding build number
                l = f"""<p><STRONG><span style='color:blue'>{version_txt} </span>SooSL&trade; {version} ({build})&nbsp;&nbsp;&nbsp;&nbsp;
                    <span style='color:blue'>{release_txt} </span>{release_date}</STRONG></p>"""
            elif l.startswith('-'):
                l = '<li>{}</li>'.format(l.lstrip('- '))
            release_lines[idx] = l
        return release_lines

    # def getLinuxReleaseLines(self, release_path, version):
    #     release_lines = []
    #     p = subprocess.Popen(['zcat', release_path], stdout=subprocess.PIPE)
    #     lines = p.communicate()[0].decode('utf-8').splitlines()
    #     append_ = False
    #     for l in lines:
    #         if l.startswith('soosl (') and l.startswith('soosl ({}'.format(version)):
    #             append_ = True
    #             l = re.search(r'soosl \(.+\)', l)[0]
    #         elif l.startswith('soosl ('):
    #             append_ = False
    #         if append_:
    #             release_lines.append(l)

    #     title_idx = 0
    #     for idx, l in enumerate(release_lines):
    #         l = l.strip()
    #         if l.startswith('soosl ('):
    #             title_idx = idx
    #             l = '<p><b>{}</b></p>'.format(l.replace('soosl', '').replace('(', '[').replace(')', ']'))
    #             release_lines[idx] = l
    #         elif l.startswith('--'):
    #             l = release_lines.pop(idx)
    #             l = l.lstrip('- ')
    #             title = release_lines[title_idx]
    #             release_lines[title_idx] = title + l + '<br><br>'
    #         elif l.startswith('-'):
    #             l = '<li>{}</li>'.format(l.lstrip('- '))
    #             release_lines[idx] = l
    #         elif l.startswith('*'):
    #             l = l.lstrip('*')
    #             release_lines[idx] = l
    #     return release_lines

    def sizeHint(self):
        w = int(self.parent().width() * 1.5)
        h = int(self.parent().width() * 1.5)
        return QSize(int(w), int(h))


if __name__ == '__main__':
    import sys
    from mainwindow import MyApp
    app = MyApp(sys.argv)

    dlg = AboutSooSLDlg('0.9.3', '220306')
    if dlg.exec_():
        sys.exit()

    sys.exit(app.exec_())
