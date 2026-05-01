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
import sys
import pathlib
import os
import webbrowser
import argparse

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
import tkinter.simpledialog as simpledialog
import tkinter.font as font

import numpy as np

from ._version import __version__
from . import mapinterpreter as interp
from . import mapplot
from . import canvasplot
from . import dialog_multifields
from . import othertrack_window
from . import font_window
from . import i18n

# http://centerwave-callout.com/tkinter内で起きた例外をどうキャッチするか？/
class Catcher: # tkinter内で起きた例外をキャッチする
    def __init__(self, func, subst, widget):
        self.func = func
        self.subst = subst
        self.widget = widget
    
    def __call__(self, *args):
        try:
            if self.subst:
               args = self.subst(*args)
            return self.func(*args)
        except Exception as e:
            if not __debug__: # デバッグモード(-O)なら素通し。pdbが起動する
                raise e
            else:
                print(e) # 通常モードならダイアログ表示
                tk.messagebox.showinfo(message=e)

class mainwindow(ttk.Frame):
    def __init__(self, master, parser, stepdist = 25, font = ''):
        self.dmin = None
        self.dmax = None
        self.result = None
        self.profYlim = None
        self.default_track_interval = stepdist
        
        super().__init__(master, padding='3 3 3 3')
        self.master.title('Kobushi trackviewer ver. {:s}'.format(__version__))
        self.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        
        master.protocol('WM_DELETE_WINDOW', self.ask_quit)
        
        self.fontctrl = font_window.FontControl(None,self)
        if font != '':
            self.fontctrl.set_fontname(font)
        
        self.create_widgets()
        self.create_menubar()
        self.bind_keyevent()
        self.subwindow = othertrack_window.SubWindow(tk.Toplevel(master), self)
        
        self.parser = parser

        i18n.on_language_change(self.refresh_ui_text)
        self.refresh_ui_text()

    def refresh_ui_text(self):
        self.master.title(i18n.get('app.title', version=__version__))
        if hasattr(self, 'open_btn'):
            self.open_btn.config(text=i18n.get('button.open'))
        if hasattr(self, 'aux_val_label'):
            self.aux_val_label.config(text=i18n.get('frame.aux_info'))
        if hasattr(self, 'stationpos_chk'):
            self.stationpos_chk.config(text=i18n.get('chk.station_pos'))
        if hasattr(self, 'stationlabel_chk'):
            self.stationlabel_chk.config(text=i18n.get('chk.station_name'))
        if hasattr(self, 'stationmileage_chk'):
            self.stationmileage_chk.config(text=i18n.get('chk.station_mileage'))
        if hasattr(self, 'gradientpos_chk'):
            self.gradientpos_chk.config(text=i18n.get('chk.gradient_pos'))
        if hasattr(self, 'gradientval_chk'):
            self.gradientval_chk.config(text=i18n.get('chk.gradient_val'))
        if hasattr(self, 'curveval_chk'):
            self.curveval_chk.config(text=i18n.get('chk.curve_val'))
        if hasattr(self, 'prof_othert_chk'):
            self.prof_othert_chk.config(text=i18n.get('chk.prof_othert'))
        if hasattr(self, 'graph_control_label'):
            self.graph_control_label.config(text=i18n.get('frame.chart_visibility'))
        if hasattr(self, 'show_gradient_graph_chk'):
            self.show_gradient_graph_chk.config(text=i18n.get('chk.gradient_graph'))
        if hasattr(self, 'show_curve_graph_chk'):
            self.show_curve_graph_chk.config(text=i18n.get('chk.curve_graph'))
        if hasattr(self, 'stationlist_label'):
            self.stationlist_label.config(text=i18n.get('label.station_jump'))
        if hasattr(self, 'menubar'):
            self.menubar.entryconfig(0, label=i18n.get('menu.file'))
            self.menubar.entryconfig(1, label=i18n.get('menu.options'))
            self.menubar.entryconfig(2, label=i18n.get('menu.lang'))
            self.menubar.entryconfig(3, label=i18n.get('menu.help'))
            self.menu_file.entryconfig(0, label=i18n.get('menu.open'))
            self.menu_file.entryconfig(1, label=i18n.get('menu.reload'))
            self.menu_file.entryconfig(3, label=i18n.get('menu.save_image'))
            self.menu_file.entryconfig(4, label=i18n.get('menu.save_trackdata'))
            self.menu_file.entryconfig(6, label=i18n.get('menu.exit'))
            self.menu_option.entryconfig(0, label=i18n.get('menu.controlpoints'))
            self.menu_option.entryconfig(1, label=i18n.get('menu.plotlimit'))
            self.menu_option.entryconfig(2, label=i18n.get('menu.font'))
            self.menu_help.entryconfig(0, label=i18n.get('menu.help_ref'))
            self.menu_help.entryconfig(1, label=i18n.get('menu.about'))
        if hasattr(self, 'profile_canvas'):
            self.profile_canvas.title = i18n.get('canvas.profile')
        if hasattr(self, 'radius_canvas'):
            self.radius_canvas.title = i18n.get('canvas.radius')
        if hasattr(self, 'plane_canvas'):
            self.plane_canvas.title = i18n.get('canvas.plan')
        if hasattr(self, 'subwindow'):
            self.subwindow.refresh_ui_text()
        if hasattr(self, 'fontctrl'):
            self.fontctrl.refresh_ui_text()
        if self.result is not None:
            self.plot_all()

    def create_widgets(self):
        self.control_frame = ttk.Frame(self, padding='3 3 3 3')
        self.control_frame.grid(column=1, row=1, sticky=(tk.S))
        
        font_title = font.Font(weight='bold',size=10)
        
        self.aux_values_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.aux_values_control.grid(column=0, row=0, sticky=(tk.S, tk.W, tk.E))
        self.aux_val_label = ttk.Label(self.aux_values_control, text=i18n.get('frame.aux_info'), font = font_title)
        self.aux_val_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.stationpos_val = tk.BooleanVar(value=True)
        self.stationpos_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_pos'),onvalue=True, offvalue=False, variable=self.stationpos_val, command=self.plot_all)
        self.stationpos_chk.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.stationlabel_val = tk.BooleanVar(value=True)
        self.stationlabel_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_name'),onvalue=True, offvalue=False, variable=self.stationlabel_val, command=self.plot_all)
        self.stationlabel_chk.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
        self.stationmileage_val = tk.BooleanVar(value=True)
        self.stationmileage_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_mileage'),onvalue=True, offvalue=False, variable=self.stationmileage_val, command=self.plot_all)
        self.stationmileage_chk.grid(column=0, row=3, sticky=(tk.N, tk.W, tk.E))
        self.gradientpos_val = tk.BooleanVar(value=True)
        self.gradientpos_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.gradient_pos'),onvalue=True, offvalue=False, variable=self.gradientpos_val, command=self.plot_all)
        self.gradientpos_chk.grid(column=0, row=4, sticky=(tk.N, tk.W, tk.E))
        self.gradientval_val = tk.BooleanVar(value=True)
        self.gradientval_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.gradient_val'),onvalue=True, offvalue=False, variable=self.gradientval_val, command=self.plot_all)
        self.gradientval_chk.grid(column=0, row=5, sticky=(tk.N, tk.W, tk.E))
        self.curveval_val = tk.BooleanVar(value=True)
        self.curveval_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.curve_val'),onvalue=True, offvalue=False, variable=self.curveval_val, command=self.plot_all)
        self.curveval_chk.grid(column=0, row=6, sticky=(tk.N, tk.W, tk.E))
        self.prof_othert_val = tk.BooleanVar(value=False)
        self.prof_othert_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.prof_othert'),onvalue=True, offvalue=False, variable=self.prof_othert_val, command=self.plot_all)
        self.prof_othert_chk.grid(column=0, row=7, sticky=(tk.N, tk.W, tk.E))

        self.graph_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.graph_control.grid(column=0, row=1, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))
        self.graph_control_label = ttk.Label(self.graph_control, text=i18n.get('frame.chart_visibility'), font=font_title)
        self.graph_control_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.show_gradient_graph_val = tk.BooleanVar(value=True)
        self.show_gradient_graph_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.gradient_graph'),
            onvalue=True, offvalue=False, variable=self.show_gradient_graph_val,
            command=self.update_pane_layout)
        self.show_gradient_graph_chk.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.show_curve_graph_val = tk.BooleanVar(value=True)
        self.show_curve_graph_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.curve_graph'),
            onvalue=True, offvalue=False, variable=self.show_curve_graph_val,
            command=self.update_pane_layout)
        self.show_curve_graph_chk.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
        
        self.dist_range_sel = tk.StringVar(value='all')
        self.dist_range_arb_val = tk.DoubleVar(value=500)
        
        self.file_frame = ttk.Frame(self, padding='3 3 3 3')
        self.file_frame.grid(column=0, row=0, sticky=(tk.N, tk.W))
        self.open_btn = ttk.Button(self.file_frame, text=i18n.get('button.open'), command=self.open_mapfile)
        self.open_btn.grid(column=0, row=0, sticky=(tk.W))
        self.filedir_entry_val = tk.StringVar()
        self.filedir_entry = ttk.Entry(self.file_frame, width=75, textvariable=self.filedir_entry_val)
        self.filedir_entry.grid(column=1, row=0, sticky=(tk.W, tk.E))
        
        self.setdist_frame = ttk.Frame(self, padding='3 3 3 3')
        self.setdist_frame.grid(column=0, row=2, sticky=(tk.S, tk.W, tk.E))

        self.stationlist_frame = ttk.Frame(self.setdist_frame, padding='0 0 0 0')
        self.stationlist_frame.grid(column=0, row=0, sticky=(tk.E))
        self.stationlist_label = ttk.Label(self.stationlist_frame, text=i18n.get('label.station_jump'), font = font_title)
        self.stationlist_label.grid(column=0, row=0, sticky=(tk.W))
        self.stationlist_val = tk.StringVar()
        self.stationlist_cb = ttk.Combobox(self.stationlist_frame, textvariable=self.stationlist_val, width = 20, state='readonly')
        self.stationlist_cb.grid(column=1, row=0, sticky=(tk.W, tk.E))
        self.stationlist_cb.bind('<<ComboboxSelected>>', self.jumptostation)
        
        self.setdist_frame.columnconfigure(0, weight=1)
        self.setdist_frame.rowconfigure(0, weight=1)
        
        self.canvas_frame = ttk.Frame(self, padding='3 3 3 3')
        self.canvas_frame.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E, tk.S))
        
        self.plot_pane = ttk.PanedWindow(self.canvas_frame, orient=tk.VERTICAL)
        self.plot_pane.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.plane_canvas = canvasplot.PlotCanvas(self.plot_pane, title=i18n.get('canvas.plan'), rotate_enabled=True, y_axis_down=True, scalebar=True)
        self.profile_pane = ttk.PanedWindow(self.plot_pane, orient=tk.HORIZONTAL)
        self.profile_canvas = canvasplot.PlotCanvas(
            self.profile_pane, title=i18n.get('canvas.profile'), rotate_enabled=False,
            world_grid=True, x_unit=i18n.get('unit.m'), y_unit=i18n.get('unit.m'), independent_scale=True, zoom_x_by_default=True)
        self.radius_canvas = canvasplot.PlotCanvas(
            self.profile_pane, title=i18n.get('canvas.radius'), rotate_enabled=False,
            world_grid=True, x_unit=i18n.get('unit.m'), independent_scale=True, lock_y_center=True, zoom_x_by_default=True)
        self.profile_pane.add(self.profile_canvas, weight=1)
        self.profile_pane.add(self.radius_canvas, weight=1)
        self.plot_pane.add(self.plane_canvas, weight=20)
        self.plot_pane.add(self.profile_pane, weight=1)
        
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_frame.rowconfigure(0, weight=1)
        
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)
    def update_pane_layout(self):
        show_gradient = self.show_gradient_graph_val.get()
        show_curve = self.show_curve_graph_val.get()

        if show_gradient:
            try:
                self.profile_pane.add(self.profile_canvas, weight=1)
            except tk.TclError:
                pass
        else:
            try:
                self.profile_pane.forget(self.profile_canvas)
            except tk.TclError:
                pass

        if show_curve:
            try:
                self.profile_pane.add(self.radius_canvas, weight=1)
            except tk.TclError:
                pass
        else:
            try:
                self.profile_pane.forget(self.radius_canvas)
            except tk.TclError:
                pass

        if show_gradient or show_curve:
            try:
                self.plot_pane.add(self.profile_pane, weight=3)
            except tk.TclError:
                pass
        else:
            try:
                self.plot_pane.forget(self.profile_pane)
            except tk.TclError:
                pass

        self.master.update_idletasks()
        self.plot_all()
    def create_menubar(self):
        self.master.option_add('*tearOff', False)
        
        self.menubar = tk.Menu(self.master)
        
        self.menu_file = tk.Menu(self.menubar)
        self.menu_option = tk.Menu(self.menubar)
        self.menu_lang = tk.Menu(self.menubar)
        self.menu_help = tk.Menu(self.menubar)
        
        self.menubar.add_cascade(menu=self.menu_file, label=i18n.get('menu.file'))
        self.menubar.add_cascade(menu=self.menu_option, label=i18n.get('menu.options'))
        self.menubar.add_cascade(menu=self.menu_lang, label=i18n.get('menu.lang'))
        self.menubar.add_cascade(menu=self.menu_help, label=i18n.get('menu.help'))
        
        self.menu_file.add_command(label=i18n.get('menu.open'), command=self.open_mapfile, accelerator='Control+O')
        self.menu_file.add_command(label=i18n.get('menu.reload'), command=self.reload_map, accelerator='F5')
        self.menu_file.add_separator()
        self.menu_file.add_command(label=i18n.get('menu.save_image'), command=self.save_plots, accelerator='Control+S')
        self.menu_file.add_command(label=i18n.get('menu.save_trackdata'), command=self.save_trackdata)
        self.menu_file.add_separator()
        self.menu_file.add_command(label=i18n.get('menu.exit'), command=self.ask_quit, accelerator='Alt+F4')
        
        self.menu_option.add_command(label=i18n.get('menu.controlpoints'), command=self.set_arbcpdist)
        self.menu_option.add_command(label=i18n.get('menu.plotlimit'), command=self.set_plotlimit)
        self.menu_option.add_command(label=i18n.get('menu.font'), command=self.fontctrl.create_window)
        
        for lang_code, lang_name in i18n.SUPPORTED_LANGUAGES.items():
            self.menu_lang.add_command(label=lang_name, command=lambda c=lang_code: i18n.set_language(c))
        
        self.menu_help.add_command(label=i18n.get('menu.help_ref'), command=self.open_webdocument)
        self.menu_help.add_command(label=i18n.get('menu.about'), command=self.aboutwindow)
        
        self.master['menu'] = self.menubar
    def bind_keyevent(self):
        self.bind_all("<Control-o>", self.open_mapfile)
        self.bind_all("<Control-s>", self.save_plots)
        self.bind_all("<F5>", self.reload_map)
        self.bind_all("<Alt-F4>", self.ask_quit)
    def open_mapfile(self, event=None,inputdir=None):
        inputdir = filedialog.askopenfilename() if inputdir is None else inputdir
        if inputdir != '':
            self.filedir_entry_val.set(inputdir)
            
            interpreter = interp.ParseMap(None,self.parser)
            self.result = interpreter.load_files(inputdir)
            
            self.dist_range_sel.set('all')
            if(len(self.result.station.position) > 0):
                self.dmin = round(min(self.result.station.position.keys()),-2) - 500
                self.dmax = round(max(self.result.station.position.keys()),-2) + 500
                self.distrange_min = self.dmin
                self.distrange_max = self.dmax
            else:
                self.dmin = round(min(self.result.controlpoints.list_cp),-2) - 500
                self.dmax = round(max(self.result.controlpoints.list_cp),-2) + 500
                self.distrange_min = self.dmin
                self.distrange_max = self.dmax
                
            '''
            self.distrange_min/max: 対象のマップで表示可能な距離程の最大最小値を示す
            self.dmin/dmax : 実際に画面にプロットする距離程の範囲を示す
            '''
                
            # 他軌道のラインカラーを設定
            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {'current':linecolor_default[color_ix%10], 'default':linecolor_default[color_ix%10]}
                color_ix += 1
                
            # 駅ジャンプメニュー更新
            stnlist_tmp = []
            self.stationlist_cb['values'] = ()
            for stationkey in self.result.station.stationkey.keys():
                stnlist_tmp.append(stationkey+', '+self.result.station.stationkey[stationkey])
                #self.menu_station.add_command(label=stationkey+', '+self.result.station.stationkey[stationkey], command=lambda: print(stationkey))
            self.stationlist_cb['values'] = tuple(stnlist_tmp)
                
            self.subwindow.set_ottree_value()
            
            self.profYlim = None
            
            self.mplot = mapplot.Mapplot(self.result, unitdist_default=self.default_track_interval)
            self.setdist_all()
            
            self.print_debugdata()
    def reload_map(self, event=None):
        inputdir = self.filedir_entry_val.get()
        if inputdir != '':
            # マップ描画設定の退避
            tmp_cp_arbdistribution   = self.mplot.environment.cp_arbdistribution
            tmp_othertrack_checked   = self.subwindow.othertrack_tree.get_checked()
            tmp_othertrack_linecolor = self.result.othertrack_linecolor
            tmp_othertrack_cprange   = self.result.othertrack.cp_range
            
            interpreter = interp.ParseMap(None,self.parser)
            self.result = interpreter.load_files(inputdir)
            
            
            if(len(self.result.station.position) > 0):
                self.distrange_min = round(min(self.result.station.position.keys()),-2) - 500
                self.distrange_max = round(max(self.result.station.position.keys()),-2) + 500
            else:
                self.distrange_min = round(min(self.result.controlpoints.list_cp),-2) - 500
                self.distrange_max = round(max(self.result.controlpoints.list_cp),-2) + 500

            '''
            self.distrange_min/max: 対象のマップで表示可能な距離程の最大最小値を示す
            self.dmin/dmax : 実際に画面にプロットする距離程の範囲を示す
            '''
                
            # 他軌道のラインカラーを設定
            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {'current':linecolor_default[color_ix%10], 'default':linecolor_default[color_ix%10]}
                color_ix += 1
                
            self.subwindow.set_ottree_value()
            
            # 他軌道の描画情報を復帰
            for key in tmp_othertrack_cprange.keys():
                if key in self.result.othertrack.data.keys():
                    self.result.othertrack.cp_range[key] = tmp_othertrack_cprange[key]
                    self.subwindow.othertrack_tree.set(key,'#1',tmp_othertrack_cprange[key]['min'])
                    self.subwindow.othertrack_tree.set(key,'#2',tmp_othertrack_cprange[key]['max'])
                    self.subwindow.othertrack_tree.tag_configure(key,foreground=tmp_othertrack_linecolor[key]['current'])
                    self.result.othertrack_linecolor[key] = tmp_othertrack_linecolor[key]
                    if key in tmp_othertrack_checked:
                        self.subwindow.othertrack_tree._check_ancestor(key)
                    
                
            # 駅ジャンプメニュー更新
            stnlist_tmp = []
            self.stationlist_cb['values'] = ()
            for stationkey in self.result.station.stationkey.keys():
                stnlist_tmp.append(stationkey+', '+self.result.station.stationkey[stationkey])
                #self.menu_station.add_command(label=stationkey+', '+self.result.station.stationkey[stationkey], command=lambda: print(stationkey))
            self.stationlist_cb['values'] = tuple(stnlist_tmp)
            
            view_state = self.get_view_state()
            self.mplot = mapplot.Mapplot(self.result,cp_arbdistribution = tmp_cp_arbdistribution)
            self.plot_all(keep_view=True)
            self.set_view_state(view_state)
            
            self.print_debugdata()
    def draw_planerplot(self):
        data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked())

        def render(view):
            if len(data['owntrack']) > 0:
                view.line(data['owntrack'][:, 1:3], width=2)
            for track in data['othertracks']:
                if len(track['points']) > 0:
                    view.line(track['points'][:, 1:3], fill=track['color'], width=1)
            if self.stationpos_val.get():
                for station in data['stations']:
                    x = station['point'][1]
                    y = station['point'][2]
                    view.point(x, y, radius=4)
                    if self.stationlabel_val.get():
                        view.text(x, y, station['name'], offset=(8, -8), font_size=9)
                    if self.stationmileage_val.get():
                        view.text(x, y, self.format_mileage(station['mileage']), offset=(8, 8), font_size=8, fill='#ffd84d')

        self.plane_canvas.set_renderer(render, bounds=data['bounds'], keep_view=self.keep_view_on_next_draw)
    def draw_profileplot(self):
        data = self.mplot.profile_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked() if self.prof_othert_val.get() else None,
            ylim=self.profYlim)

        def render(view):
            if len(data['owntrack']) > 0:
                view.line(data['owntrack'][:, [0, 3]], width=2)
            for track in data['othertracks']:
                if len(track['points']) > 0:
                    view.line(track['points'][:, [0, 3]], fill=track['color'], width=1)

            canvas = view.canvas
            height = max(1, canvas.winfo_height())

            for station in data['stations']:
                x = station['point'][0]
                z = station['point'][3]
                screen_x, screen_z = view.world_to_screen(x, z)
                canvas.create_line(screen_x, screen_z, screen_x, 0, fill='#ffffff', width=1)
                view.point(x, z, radius=3)
                if self.stationlabel_val.get():
                    view.text(x, z, station['name'], offset=(8, -26), font_size=9)
                if self.stationmileage_val.get():
                    screen_x, _ = view.world_to_screen(x, 0)
                    canvas.create_text(screen_x + 8, 8, anchor='nw',
                        text=self.format_mileage(station['mileage']),
                        fill='#ffd84d', font=(view.font_family, 8))
            if self.gradientpos_val.get():
                for point in data['gradient_points']:
                    screen_x, screen_z = view.world_to_screen(point['x'], point['z'])
                    canvas.create_line(screen_x, screen_z, screen_x, height, fill='#ffffff', width=1)
                for label in data['gradient_labels']:
                    if self.gradientval_val.get():
                        screen_x, _ = view.world_to_screen(label['x'], 0)
                        canvas.create_text(screen_x + 6, height - 6, anchor='se',
                            text=label['text'], fill='#ffffff',
                            font=(view.font_family, 8))

        if self.show_gradient_graph_val.get():
            self.profile_canvas.set_renderer(render, bounds=data['bounds'], keep_view=self.keep_view_on_next_draw)

        def render_radius(view):
            if len(data['curve']) > 0:
                view.line(data['curve'], width=2)
            if self.curveval_val.get():
                for label in data['radius_labels']:
                    view.text(label['x'], label['y'], label['text'], angle=90, offset=(-6, 0), font_size=8)

            if self.stationpos_val.get():
                canvas = view.canvas
                width = max(1, canvas.winfo_width())
                height = max(1, canvas.winfo_height())
                for station in data['stations']:
                    screen_x, _ = view.world_to_screen(station['distance'], 0)
                    if screen_x < 0 or screen_x > width:
                        continue
                    canvas.create_line(screen_x, 0, screen_x, height, fill='#ffffff', width=1)
                    if self.stationlabel_val.get():
                        canvas.create_text(screen_x + 8, 8, anchor='nw',
                            text=station['name'], fill='#ffffff',
                            font=(view.font_family, 9))
                    if self.stationmileage_val.get():
                        canvas.create_text(screen_x + 8, height - 8, anchor='sw',
                            text=self.format_mileage(station['mileage']),
                            fill='#ffd84d', font=(view.font_family, 8))

        if self.show_curve_graph_val.get():
            self.radius_canvas.set_renderer(render_radius, bounds=data['radius_bounds'], keep_view=self.keep_view_on_next_draw)
    def print_debugdata(self):
        if not __debug__:
            print('own_track data')
            for i in self.result.own_track.data:
                print(i)
            print('controlpoints list')
            for i in self.result.controlpoints.list_cp:
                print(i)
            print('own_track position')
            for i in self.result.owntrack_pos:
                print(i)
            print('station list')
            for i in self.result.station.position:
                print(i,self.result.station.stationkey[self.result.station.position[i]])
            print('othertrack data')
            for i in self.result.othertrack.data.keys():
                print(i)
                for j in self.result.othertrack.data[i]:
                    print(j)
            print('Track keys:')
            print(self.result.othertrack.data.keys())
            print('othertrack position')
            for i in self.result.othertrack.data.keys():
                print(i)
                for j in self.result.othertrack_pos[i]:
                    print(j)
    def setdist_all(self):
        if self.result != None:
            self.dist_range_sel.set('all')
            self.dmin = self.distrange_min
            self.dmax = self.distrange_max
            self.plot_all()
    def setdist_arbitrary(self):
        if self.result != None:
            self.setdist_all()
    def format_mileage(self, value):
        return i18n.get('mileage.format').format(value)
    def get_view_state(self):
        return {
            'plane': self.plane_canvas.get_view_state(),
            'profile': self.profile_canvas.get_view_state(),
            'radius': self.radius_canvas.get_view_state(),
        }
    def set_view_state(self, state):
        self.plane_canvas.set_view_state(state['plane'])
        self.profile_canvas.set_view_state(state['profile'])
        self.radius_canvas.set_view_state(state['radius'])
    def plot_all(self, keep_view=False):
        if(self.result != None):
            self.keep_view_on_next_draw = keep_view
            self.plane_canvas.set_font(self.fontctrl.get_fontname())
            if self.show_gradient_graph_val.get() or self.show_curve_graph_val.get():
                self.profile_canvas.set_font(self.fontctrl.get_fontname())
                self.radius_canvas.set_font(self.fontctrl.get_fontname())
            self.draw_planerplot()
            self.draw_profileplot()
            self.keep_view_on_next_draw = False
    def ask_quit(self, event=None, ask=True):
        if ask:
            if tk.messagebox.askyesno(message=i18n.get('dialog.quit')):
                self.quit()
        else:
            self.quit()
    def jumptostation(self, event=None):
        value = self.stationlist_cb.get()
        key = value.split(',')[0]
        dist = [k for k, v in self.result.station.position.items() if v == key]
        if len(dist)>0:
            self.focus_station(dist[0])
        else:
            tk.messagebox.showinfo(message=i18n.get('dialog.station_not_found', value=value))
    def focus_station(self, distance):
        plane_data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked())
        for station in plane_data['stations']:
            if station['distance'] == distance:
                self.plane_canvas.center = [station['point'][1], station['point'][2]]
                self.plane_canvas.redraw()
                break
        self.profile_canvas.center[0] = distance
        self.profile_canvas.redraw()
        self.radius_canvas.center[0] = distance
        self.radius_canvas.redraw()
    def save_plots(self, event=None):
        filepath = filedialog.asksaveasfilename(filetypes=[(i18n.get('filetype.ps'),'*.ps'), (i18n.get('filetype.any'),'*')], defaultextension='.ps')
        if filepath != '':
            filepath = pathlib.Path(filepath)
            self.plane_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_plan.ps')), colormode='color')
            self.profile_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_profile.ps')), colormode='color')
            self.radius_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_radius.ps')), colormode='color')
    def save_trackdata(self, event=None):
        filepath = filedialog.askdirectory(initialdir='./')
        if filepath != '':
            filepath = pathlib.Path(filepath)
            filename_base = filepath.stem
            
            output_filename = filepath.joinpath(str(filename_base)+'_owntrack'+'.csv')
            output = self.result.owntrack_pos
            header = 'distance,x,y,z,direction,radius,gradient,interpolate_func,cant,center,gauge'
            np.savetxt(output_filename, output, delimiter=',',header=header,fmt='%.6f')
            
            for key in self.result.othertrack_pos.keys():
                output_filename = filepath.joinpath(str(filename_base)+'_'+key+'.csv')
                output = self.result.othertrack_pos[key]
                header = 'distance,x,y,z,interpolate_func,cant,center,gauge'
                np.savetxt(output_filename, output, delimiter=',',header=header,fmt='%.6f')
    def set_plotlimit(self, event=None):
        if self.result != None:
            dialog = dialog_multifields.dialog_multifields(self,\
                                            [{'name':'min', 'type':'Double', 'label':i18n.get('dialog.plotlimit_min', value=str(self.result.cp_defaultrange[0])), 'default':self.distrange_min},\
                                            {'name':'max', 'type':'Double', 'label':i18n.get('dialog.plotlimit_max', value=str(self.result.cp_defaultrange[1])), 'default':self.distrange_max}],
                                            message =i18n.get('dialog.set_plotlimit', min=str(min(self.result.controlpoints.list_cp)), max=str(max(self.result.controlpoints.list_cp))))
            if dialog.result == 'OK':
                self.distrange_min = float(dialog.variables['min'].get())
                self.distrange_max = float(dialog.variables['max'].get())
                self.setdist_all()
            elif dialog.result == 'reset':
                self.distrange_min = self.result.cp_defaultrange[0]
                self.distrange_max = self.result.cp_defaultrange[1]
                self.setdist_all()
    def set_arbcpdist(self, event = None):
        if self.result != None:
            cp_arbdistribution = self.mplot.environment.cp_arbdistribution
            cp_arb_default = self.mplot.environment.cp_arbdistribution_default
            list_cp = self.result.controlpoints.list_cp
            boundary_margin = 500
            equaldist_unit = 25
            cp_arbcp_default = [max(0, round(min(list_cp),-2) - boundary_margin),round(max(list_cp),-2) + boundary_margin,equaldist_unit]
            
            dialog = dialog_multifields.dialog_multifields(self,\
                                            [{'name':'min', 'type':'Double', 'label':i18n.get('dialog.cp_min', value=str(cp_arbcp_default[0])), 'default':cp_arbdistribution[0]},\
                                            {'name':'max', 'type':'Double', 'label':i18n.get('dialog.cp_max', value=str(cp_arbcp_default[1])), 'default':cp_arbdistribution[1]},\
                                            {'name':'interval', 'type':'Double', 'label':i18n.get('dialog.cp_interval', value=str(cp_arbcp_default[2])), 'default':cp_arbdistribution[2]}],
                                            message =i18n.get('dialog.set_controlpoint'))
            if dialog.result == 'OK':
                inputval = [dialog.variables['min'].get(),dialog.variables['max'].get(),dialog.variables['interval'].get()]
                for ix in [0,1,2]:
                    self.mplot.environment.cp_arbdistribution[ix] = float(inputval[ix])
                self.reload_map()
            elif dialog.result == 'reset':
                for ix in [0,1,2]:
                    self.mplot.environment.cp_arbdistribution = None
                self.reload_map()
    def aboutwindow(self, event=None):
        msg = i18n.get('about.text', version=__version__)
        tk.messagebox.showinfo(message=msg)
    def customdialog_test(self, event=None):
        dialog_obj = dialog_multifields.dialog_multifields(self,\
                                        [{'name':'A', 'type':'str', 'label':'test A', 'default':'alpha'},\
                                        {'name':'B', 'type':'Double', 'label':'test B', 'default':100}],\
                                        'Test Dialog')
        print('Done', dialog_obj.result, dialog_obj.variables['A'].get())
    def open_webdocument(self, event=None):
        webbrowser.open('https://github.com/konawasabi/kobushi-trackviewer/blob/master/reference.md')
#if __name__ == '__main__':
def main():
    if not __debug__:
        # エラーが発生した場合、デバッガを起動 https://gist.github.com/podhmo/5964702e7471ccaba969105468291efa
        def info(type, value, tb):
            if hasattr(sys, "ps1") or not sys.stderr.isatty():
                # You are in interactive mode or don't have a tty-like
                # device, so call the default hook
                sys.__excepthook__(type, value, tb)
            else:
                import traceback, pdb

                # You are NOT in interactive mode; print the exception...
                traceback.print_exception(type, value, tb)
                # ...then start the debugger in post-mortem mode
                pdb.pm()
        #import sys
        sys.excepthook = info
        print('Debug mode')

    argparser = argparse.ArgumentParser()
    argparser.add_argument('filepath', metavar='F', type=str, help='input mapfile', nargs='?')
    argparser.add_argument('-s', '--step', help='distance interval for track calculation', type=float, default=25)
    argparser.add_argument('-f', '--font', help='Font', type=str, default = 'sans-serif')
    args = argparser.parse_args()
       
    tk.CallWrapper = Catcher
    root = tk.Tk()
    app = mainwindow(master=root, parser = None, stepdist = args.step, font=args.font)

    if args.filepath is not None:
        app.open_mapfile(inputdir=args.filepath)
    app.mainloop()
