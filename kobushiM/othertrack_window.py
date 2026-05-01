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

import tkinter as tk
from tkinter import ttk
import tkinter.simpledialog as simpledialog
import tkinter.colorchooser as colorchooser
from ttkwidgets import CheckboxTreeview
from . import i18n

class SubWindow(ttk.Frame):
    def __init__(self, master, mainwindow):
        self.mainwindow = mainwindow
        self.parent = master
        super().__init__(master, padding='3 3 3 3')
        
        self.mainwindow.tk.eval("""
            ttk::style map Treeview \
            -foreground {disabled SystemGrayText \
                         selected SystemHighlightText} \
            -background {disabled SystemButtonFace \
                         selected SystemHighlight}
        """)
        
        self.master.title(i18n.get('window.othertracks'))
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.grid(column=0, row=0,sticky=(tk.N, tk.W, tk.E, tk.S))
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        self.create_widgets()
        self.master.geometry('+1100+0')
    def create_widgets(self):
        self.frame = ttk.Frame(self, padding=0)
        self.frame.grid(sticky=(tk.N, tk.W, tk.E, tk.S))
        self.frame.columnconfigure(0,weight=1)
        self.frame.rowconfigure(0,weight=1)
        self.othertrack_tree = CheckboxTreeview(self.frame, show='tree headings', columns=['mindist', 'maxdist', 'linecolor'],selectmode='browse')
        self.othertrack_tree.bind("<ButtonRelease>", self.click_tracklist)
        self.othertrack_tree.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.othertrack_tree.column('#0', width=200)
        self.othertrack_tree.column('mindist', width=100)
        self.othertrack_tree.column('maxdist', width=100)
        self.othertrack_tree.column('linecolor', width=50)
        self.othertrack_tree.heading('#0', text=i18n.get('tree.track_key'))
        self.othertrack_tree.heading('mindist', text=i18n.get('tree.from'))
        self.othertrack_tree.heading('maxdist', text=i18n.get('tree.to'))
        self.othertrack_tree.heading('linecolor', text=i18n.get('tree.color'))
        
        self.ottree_scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.othertrack_tree.yview)
        self.ottree_scrollbar.grid(column=1, row=0, sticky=(tk.N, tk.S, tk.E))
        self.othertrack_tree.configure(yscrollcommand=self.ottree_scrollbar.set)

    def refresh_ui_text(self):
        self.master.title(i18n.get('window.othertracks'))
        self.othertrack_tree.heading('#0', text=i18n.get('tree.track_key'))
        self.othertrack_tree.heading('mindist', text=i18n.get('tree.from'))
        self.othertrack_tree.heading('maxdist', text=i18n.get('tree.to'))
        self.othertrack_tree.heading('linecolor', text=i18n.get('tree.color'))

    def click_tracklist(self, event=None):
        columnlabel = { '#0': i18n.get('label.check'), '#1': i18n.get('tree.from'), '#2': i18n.get('tree.to'), '#3': i18n.get('tree.color')}
        if event != None:
            if getattr(event, 'widget').identify("element", event.x, event.y) == 'text':
                clicked_column = self.othertrack_tree.identify_column(event.x)
                clicked_track = self.othertrack_tree.identify_row(event.y)
                if clicked_track == '\\':
                    clicked_track = ''
                if clicked_column in ['#1','#2','#3'] and clicked_track != 'root':
                    if clicked_column == '#3':
                        inputdata = colorchooser.askcolor(
                            color=self.mainwindow.result.othertrack_linecolor[clicked_track]['current'],
                            title=i18n.get('dialog.color_title', trackkey=clicked_track, color=self.mainwindow.result.othertrack_linecolor[clicked_track]['default']))
                        if inputdata[1] != None:
                            self.mainwindow.result.othertrack_linecolor[clicked_track]['current'] = inputdata[1]
                            self.othertrack_tree.tag_configure(clicked_track,foreground=self.mainwindow.result.othertrack_linecolor[clicked_track]['current'])
                    else:
                        if clicked_column == '#1':
                            defaultval = min(self.mainwindow.result.othertrack.data[clicked_track], key=lambda x: x['distance'])['distance']
                        elif clicked_column == '#2':
                            defaultval = max(self.mainwindow.result.othertrack.data[clicked_track], key=lambda x: x['distance'])['distance']
                        inputdata = simpledialog.askfloat(
                            i18n.get('dialog.distance_title', trackkey=clicked_track),
                            i18n.get('dialog.distance_prompt', label=columnlabel[clicked_column], value=str(defaultval)))
                        if inputdata != None:
                            if clicked_column == '#1':
                                self.mainwindow.result.othertrack.cp_range[clicked_track]['min'] = inputdata
                            elif clicked_column == '#2':
                                self.mainwindow.result.othertrack.cp_range[clicked_track]['max'] = inputdata
                            self.othertrack_tree.set(clicked_track,clicked_column,inputdata)
        self.mainwindow.plot_all()
    def set_ottree_value(self):
        if self.othertrack_tree.exists('root'):
            self.othertrack_tree.delete('root')
        self.othertrack_tree.insert("", "end", 'root', text='root', open=True)
        colorix = 0
        for i in self.mainwindow.result.othertrack.data.keys():
            self.othertrack_tree.insert("root", "end", '\\' if i=='' else i, text=i, values=(min(self.mainwindow.result.othertrack.data[i], key=lambda x: x['distance'])['distance'],max(self.mainwindow.result.othertrack.data[i], key=lambda x: x['distance'])['distance'], '■■■'),tags=(i,))
            # trackkey == '' (空文字列)の場合はidをバックスラッシュに置き換える。（他軌道ツリーのroot要素と重複するため）
            self.othertrack_tree.tag_configure(i,foreground=self.mainwindow.result.othertrack_linecolor[i]['current'])
        #self.subwindow.othertrack_tree.see('root')
        #self.othertrack_tree.configure(yscrollcommand=self.ottree_scrollbar.set)
