'''
    Copyright 2021-2024 konawasabi

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
'''

from PyQt6 import QtGui, QtWidgets


class FontControl:
    def __init__(self, master, mainwindow):
        self.mainwindow = mainwindow
        self.parent = master
        self.fontname = QtWidgets.QApplication.font().family()

    def create_window(self, event=None):
        current = QtGui.QFont(self.fontname)
        font, ok = QtWidgets.QFontDialog.getFont(current, self.mainwindow)
        if ok:
            self.fontname = font.family()
            self.mainwindow.plot_all()

    def refresh_ui_text(self):
        return None

    def closewindow(self):
        return None

    def ok_close(self):
        self.mainwindow.plot_all()

    def set_fontname(self, font):
        if font:
            self.fontname = font

    def get_fontname(self):
        return self.fontname
