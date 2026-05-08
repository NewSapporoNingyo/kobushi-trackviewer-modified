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
import time
import queue
import webbrowser
import argparse
import math

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
import tkinter.simpledialog as simpledialog
import tkinter.font as font

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageTk

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

class LogInterceptor:
    def __init__(self, original, source, log_queue):
        self.original = original
        self.source = source
        self.queue = log_queue

    def write(self, msg):
        if msg:
            if self.original is not None and hasattr(self.original, 'write'):
                try:
                    self.original.write(msg)
                except Exception:
                    pass
            
            stripped = msg.rstrip('\n\r')
            if stripped:
                self.queue.put((self.source, stripped))

    def flush(self):
        if self.original is not None and hasattr(self.original, 'flush'):
            try:
                self.original.flush()
            except Exception:
                pass

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
        self._measure_marker_ids = {}

        self._log_queue = queue.Queue()
        self._log_errors = []
        self._log_warnings = []
        sys.stdout = LogInterceptor(sys.stdout, 'stdout', self._log_queue)
        sys.stderr = LogInterceptor(sys.stderr, 'stderr', self._log_queue)

        self.bg_image_original = None
        self.bg_image_tk = None
        self.bg_image_params = {
            'x': 0.0,
            'y': 0.0,
            'width': 5000.0,
            'height': 5000.0,
            'rotation': 0.0
        }

        i18n.on_language_change(self.refresh_ui_text)
        self.refresh_ui_text()
        self.after(100, self.check_log_queue)

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
        if hasattr(self, 'speedlimit_chk'):
            self.speedlimit_chk.config(text=i18n.get('chk.speedlimit'))
        if hasattr(self, 'graph_control_label'):
            self.graph_control_label.config(text=i18n.get('frame.chart_visibility'))
        if hasattr(self, 'show_gradient_graph_chk'):
            self.show_gradient_graph_chk.config(text=i18n.get('chk.gradient_graph'))
        if hasattr(self, 'show_curve_graph_chk'):
            self.show_curve_graph_chk.config(text=i18n.get('chk.curve_graph'))
        if hasattr(self, 'grid_control_label'):
            self.grid_control_label.config(text=i18n.get('frame.grid'))
        if hasattr(self, 'grid_fixed_rb'):
            self.grid_fixed_rb.config(text=i18n.get('grid.fixed'))
        if hasattr(self, 'grid_movable_rb'):
            self.grid_movable_rb.config(text=i18n.get('grid.movable'))
        if hasattr(self, 'grid_none_rb'):
            self.grid_none_rb.config(text=i18n.get('grid.none'))
        if hasattr(self, 'mode_control_label'):
            self.mode_control_label.config(text=i18n.get('frame.mode'))
        if hasattr(self, 'mode_pan_rb'):
            self.mode_pan_rb.config(text=i18n.get('mode.pan'))
        if hasattr(self, 'mode_measure_rb'):
            self.mode_measure_rb.config(text=i18n.get('mode.measure'))
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
        self.aux_values_control.grid(column=0, row=2, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))
        self.aux_val_label = ttk.Label(self.aux_values_control, text=i18n.get('frame.aux_info'), font = font_title)
        self.aux_val_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.stationpos_val = tk.BooleanVar(value=True)
        self.stationpos_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_pos'),onvalue=True, offvalue=False, variable=self.stationpos_val, command=self.on_stationpos_toggle)
        self.stationpos_chk.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.stationlabel_val = tk.BooleanVar(value=True)
        self.stationlabel_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_name'),onvalue=True, offvalue=False, variable=self.stationlabel_val, command=self.plot_all)
        self.stationlabel_chk.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
        self.stationmileage_val = tk.BooleanVar(value=True)
        self.stationmileage_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.station_mileage'),onvalue=True, offvalue=False, variable=self.stationmileage_val, command=self.plot_all)
        self.stationmileage_chk.grid(column=0, row=3, sticky=(tk.N, tk.W, tk.E))
        self.gradientpos_val = tk.BooleanVar(value=True)
        self.gradientval_val = tk.BooleanVar(value=True)
        self.curveval_val = tk.BooleanVar(value=True)
        self.curveval_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.curve_val'),onvalue=True, offvalue=False, variable=self.curveval_val, command=self.plot_all)
        self.curveval_chk.grid(column=0, row=4, sticky=(tk.N, tk.W, tk.E))
        self.prof_othert_val = tk.BooleanVar(value=False)
        self.speedlimit_val = tk.BooleanVar(value=True)
        self.speedlimit_chk = ttk.Checkbutton(self.aux_values_control, text=i18n.get('chk.speedlimit'),onvalue=True, offvalue=False, variable=self.speedlimit_val, command=self.plot_all)
        self.speedlimit_chk.grid(column=0, row=5, sticky=(tk.N, tk.W, tk.E))

        self.graph_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.graph_control.grid(column=0, row=3, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))
        self.graph_control_label = ttk.Label(self.graph_control, text=i18n.get('frame.chart_visibility'), font=font_title)
        self.graph_control_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.show_curve_graph_val = tk.BooleanVar(value=True)
        self.show_curve_graph_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.curve_graph'),
            onvalue=True, offvalue=False, variable=self.show_curve_graph_val,
            command=self.update_pane_layout)
        self.show_curve_graph_chk.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.show_gradient_graph_val = tk.BooleanVar(value=True)
        self.show_gradient_graph_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.gradient_graph'),
            onvalue=True, offvalue=False, variable=self.show_gradient_graph_val,
            command=self.update_pane_layout)
        self.show_gradient_graph_chk.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
        self.gradientpos_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.gradient_pos'),
            onvalue=True, offvalue=False, variable=self.gradientpos_val, command=self.on_gradientpos_toggle)
        self.gradientpos_chk.grid(column=0, row=3, sticky=(tk.N, tk.W, tk.E))
        self.gradientval_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.gradient_val'),
            onvalue=True, offvalue=False, variable=self.gradientval_val, command=self.plot_all)
        self.gradientval_chk.grid(column=0, row=4, sticky=(tk.N, tk.W, tk.E))
        self.prof_othert_chk = ttk.Checkbutton(self.graph_control, text=i18n.get('chk.prof_othert'),
            onvalue=True, offvalue=False, variable=self.prof_othert_val, command=self.plot_all)
        self.prof_othert_chk.grid(column=0, row=5, sticky=(tk.N, tk.W, tk.E))

        self.grid_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.grid_control.grid(column=0, row=1, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))
        self.grid_control_label = ttk.Label(self.grid_control, text=i18n.get('frame.grid'), font=font_title)
        self.grid_control_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.grid_mode_val = tk.StringVar(value='fixed')
        self.grid_fixed_rb = ttk.Radiobutton(self.grid_control, text=i18n.get('grid.fixed'),
            variable=self.grid_mode_val, value='fixed', command=self.on_grid_mode_change)
        self.grid_fixed_rb.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.grid_movable_rb = ttk.Radiobutton(self.grid_control, text=i18n.get('grid.movable'),
            variable=self.grid_mode_val, value='movable', command=self.on_grid_mode_change)
        self.grid_movable_rb.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
        self.grid_none_rb = ttk.Radiobutton(self.grid_control, text=i18n.get('grid.none'),
            variable=self.grid_mode_val, value='none', command=self.on_grid_mode_change)
        self.grid_none_rb.grid(column=0, row=3, sticky=(tk.N, tk.W, tk.E))

        self.mode_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.mode_control.grid(column=0, row=0, sticky=(tk.S, tk.W, tk.E))
        self.mode_control_label = ttk.Label(self.mode_control, text=i18n.get('frame.mode'), font=font_title)
        self.mode_control_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))
        self.mode_val = tk.StringVar(value='pan')
        self.mode_pan_rb = ttk.Radiobutton(self.mode_control, text=i18n.get('mode.pan'),
            variable=self.mode_val, value='pan', command=self.on_mode_change)
        self.mode_pan_rb.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))
        self.mode_measure_rb = ttk.Radiobutton(self.mode_control, text=i18n.get('mode.measure'),
            variable=self.mode_val, value='measure', command=self.on_mode_change)
        self.mode_measure_rb.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))

        self.measure_pos = None
        
        self.dist_range_sel = tk.StringVar(value='all')
        self.dist_range_arb_val = tk.DoubleVar(value=500)
        
        self.file_frame = ttk.Frame(self, padding='3 3 3 3')
        self.file_frame.grid(column=0, row=0, sticky=(tk.N, tk.W))
        self.open_btn = ttk.Button(self.file_frame, text=i18n.get('button.open'), command=self.open_mapfile)
        self.open_btn.grid(column=0, row=0, sticky=(tk.W))
        self.filedir_entry_val = tk.StringVar()
        self.filedir_entry = ttk.Entry(self.file_frame, width=75, textvariable=self.filedir_entry_val)
        self.filedir_entry.grid(column=1, row=0, sticky=(tk.W, tk.E))
        self._log_err_btn = ttk.Button(self.file_frame, text='🐛 0', width=7, command=self._show_error_details)
        self._log_err_btn.grid(column=2, row=0, sticky=(tk.W), padx=(2, 0))
        self._log_warn_btn = ttk.Button(self.file_frame, text='⚠ 0', width=7, command=self._show_warning_details)
        self._log_warn_btn.grid(column=3, row=0, sticky=(tk.W), padx=(2, 0))
        self._log_last_msg = tk.StringVar(value='')
        self._log_last_label = ttk.Label(self.file_frame, textvariable=self._log_last_msg, width=50, anchor=tk.W, relief=tk.SUNKEN, padding=(4, 1))
        self._log_last_label.grid(column=4, row=0, sticky=(tk.W, tk.E), padx=(4, 0))
        self.file_frame.columnconfigure(4, weight=1)
        
        self.setdist_frame = ttk.Frame(self, padding='3 3 3 3')
        self.setdist_frame.grid(column=0, row=2, sticky=(tk.S, tk.W, tk.E))

        self.measure_info_label = ttk.Label(self.setdist_frame, text='', font=font_title)
        self.measure_info_label.grid(column=0, row=0, sticky=(tk.W), padx=(6, 0), pady=(2, 6))

        self.stationlist_frame = ttk.Frame(self.setdist_frame, padding='0 0 0 0')
        self.stationlist_frame.grid(column=1, row=0, sticky=(tk.E))
        self.stationlist_label = ttk.Label(self.stationlist_frame, text=i18n.get('label.station_jump'), font = font_title)
        self.stationlist_label.grid(column=0, row=0, sticky=(tk.W))
        self.stationlist_val = tk.StringVar()
        self.stationlist_cb = ttk.Combobox(self.stationlist_frame, textvariable=self.stationlist_val, width = 20, state='readonly')
        self.stationlist_cb.grid(column=1, row=0, sticky=(tk.W, tk.E))
        self.stationlist_cb.bind('<<ComboboxSelected>>', self.jumptostation)

        self.setdist_frame.columnconfigure(0, weight=1)
        self.setdist_frame.columnconfigure(1, weight=0)
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
            world_grid=True, x_unit=i18n.get('unit.m'), independent_scale=True, lock_y_center=True, zoom_x_by_default=True,
            enable_lod=False)
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

        self.bgimg_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.bgimg_control.grid(column=0, row=10, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))

        self.bgimg_label = ttk.Label(self.bgimg_control, text="背景图片", font=font_title)
        self.bgimg_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))

        self.bgimg_import_btn = ttk.Button(self.bgimg_control, text="导入", command=self.import_bgimg)
        self.bgimg_import_btn.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))

        self.bgimg_adjust_btn = ttk.Button(self.bgimg_control, text="调整", command=self.adjust_bgimg, state=tk.DISABLED)
        self.bgimg_adjust_btn.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))
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
    def on_stationpos_toggle(self):
        if self.stationpos_val.get():
            self.stationlabel_chk.config(state='normal')
            self.stationmileage_chk.config(state='normal')
        else:
            self.stationlabel_chk.config(state='disabled')
            self.stationmileage_chk.config(state='disabled')
        self.plot_all()
    def on_gradientpos_toggle(self):
        if self.gradientpos_val.get():
            self.gradientval_chk.config(state='normal')
        else:
            self.gradientval_chk.config(state='disabled')
        self.plot_all()
    def check_log_queue(self):
        try:
            while True:
                source, msg = self._log_queue.get_nowait()
                if source == 'stderr' or 'error' in msg.lower():
                    self._log_errors.append(msg)
                elif 'warning' in msg.lower():
                    self._log_warnings.append(msg)
                self._log_last_msg.set(msg[-100:])
        except queue.Empty:
            pass
        wc = len(self._log_warnings)
        ec = len(self._log_errors)
        if wc > 0:
            self._log_warn_btn.config(text='⚠ {:d}'.format(wc))
        if ec > 0:
            self._log_err_btn.config(text='🐛 {:d}'.format(ec))
        self.after(100, self.check_log_queue)

    def _clear_logs(self):
        self._log_errors.clear()
        self._log_warnings.clear()
        self._log_last_msg.set('')
        self._log_err_btn.config(text='🐛 0')
        self._log_warn_btn.config(text='⚠ 0')

    def _show_error_details(self):
        self._show_log_detail_window('Errors', self._log_errors)

    def _show_warning_details(self):
        self._show_log_detail_window('Warnings', self._log_warnings)

    def _show_log_detail_window(self, title, messages):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry('700x400')
        win.transient(self)
        frame = ttk.Frame(win, padding='3 3 3 3')
        frame.pack(fill=tk.BOTH, expand=True)
        text = tk.Text(frame, wrap=tk.WORD, font=('Consolas', 9))
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        if messages:
            for msg in messages:
                text.insert(tk.END, msg + '\n')
        else:
            text.insert(tk.END, 'No messages')
        text.config(state=tk.DISABLED)

    def on_grid_mode_change(self):
        self.plane_canvas.set_grid_mode(self.grid_mode_val.get())
    def on_mode_change(self):
        measure_mode = self.mode_val.get() == 'measure'
        for canvas in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
            canvas.interactive = not measure_mode
        if measure_mode:
            self._measure_marker_ids = {}
            self.plane_canvas.canvas.bind('<Motion>', self.on_plan_motion)
            self.profile_canvas.canvas.bind('<Motion>', self.on_profile_motion)
            self.radius_canvas.canvas.bind('<Motion>', self.on_radius_motion)
            for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
                cv.canvas.unbind('<Double-Button-1>')
                cv.canvas.bind('<Double-Button-1>', self.on_measure_double_click)
        else:
            self.plane_canvas.canvas.unbind('<Motion>')
            self.profile_canvas.canvas.unbind('<Motion>')
            self.radius_canvas.canvas.unbind('<Motion>')
            for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
                cv.canvas.unbind('<Double-Button-1>')
                cv.canvas.bind('<Double-Button-1>', cv.fit)
            self.plane_canvas.set_cursor('')
            self.profile_canvas.set_cursor('')
            self.radius_canvas.set_cursor('')
            self._clear_measure_marker()
            self.measure_pos = None
            self.measure_info_label.config(text='')
            self.plot_all(keep_view=True)
    def _clear_measure_marker(self):
        for canvas, ids in list(self._measure_marker_ids.items()):
            for item_id in ids:
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
        self._measure_marker_ids = {}

    def _sync_measure_markers(self, distance):
        self._clear_measure_marker()
        own = self.result.owntrack_pos
        if len(own) == 0 or distance < own[0][0] or distance > own[-1][0]:
            return
        idx = np.searchsorted(own[:, 0], distance)
        if idx >= len(own):
            idx = len(own) - 1
        track_x = own[idx][1]
        track_y = own[idx][2]
        sx, sy = self.plane_canvas.world_to_screen(track_x, track_y)
        c = self.plane_canvas.canvas
        ids = []
        ids.append(c.create_line(sx - 12, sy - 12, sx + 12, sy + 12, fill='#ff3333', width=2))
        ids.append(c.create_line(sx - 12, sy + 12, sx + 12, sy - 12, fill='#ff3333', width=2))
        self._measure_marker_ids[c] = ids
        for cv in [self.profile_canvas, self.radius_canvas]:
            sx_v, _ = cv.world_to_screen(distance, 0)
            c2 = cv.canvas
            h = max(1, c2.winfo_height())
            self._measure_marker_ids[c2] = [c2.create_line(sx_v, 0, sx_v, h, fill='#ff3333', width=1)]

    def on_plan_motion(self, event):
        if self.result is None:
            return
        v = self.plane_canvas
        wx, wy = v.screen_to_world(event.x, event.y)
        owntrack = self.result.owntrack_pos
        if len(owntrack) == 0:
            return
        dists = np.sqrt((owntrack[:, 1] - wx) ** 2 + (owntrack[:, 2] - wy) ** 2)
        min_idx = np.argmin(dists)
        track_x = owntrack[min_idx][1]
        track_y = owntrack[min_idx][2]
        sx_p, sy_p = v.world_to_screen(track_x, track_y)
        screen_dist = np.sqrt((sx_p - event.x) ** 2 + (sy_p - event.y) ** 2)
        if screen_dist <= 30:
            for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
                cv.set_cursor('crosshair')
            distance = owntrack[min_idx][0]
            self.measure_pos = {'distance': distance}
            self._sync_measure_markers(distance)
            self.update_measure_info()
        else:
            self.plane_canvas.set_cursor('')
            self.profile_canvas.set_cursor('')
            self.radius_canvas.set_cursor('')
            if self.measure_pos is not None:
                self.measure_pos = None
                self._clear_measure_marker()
                self.measure_info_label.config(text='')

    def on_profile_motion(self, event):
        if self.result is None:
            return
        v = self.profile_canvas
        wx, _ = v.screen_to_world(event.x, event.y)
        own = self.result.owntrack_pos
        if len(own) == 0 or wx < own[0][0] or wx > own[-1][0]:
            return
        for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
            cv.set_cursor('crosshair')
        self.measure_pos = {'distance': wx}
        self._sync_measure_markers(wx)
        self.update_measure_info()

    def on_radius_motion(self, event):
        if self.result is None:
            return
        v = self.radius_canvas
        wx, _ = v.screen_to_world(event.x, event.y)
        own = self.result.owntrack_pos
        if len(own) == 0 or wx < own[0][0] or wx > own[-1][0]:
            return
        for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
            cv.set_cursor('crosshair')
        self.measure_pos = {'distance': wx}
        self._sync_measure_markers(wx)
        self.update_measure_info()
    def on_measure_double_click(self, event):
        if self.measure_pos is None or self.result is None:
            return 'break'
        distance = self.measure_pos['distance']
        own = self.result.owntrack_pos
        if len(own) == 0 or distance < own[0][0] or distance > own[-1][0]:
            return 'break'
        idx = np.searchsorted(own[:, 0], distance)
        if idx >= len(own):
            idx = len(own) - 1
        clicked = event.widget
        for cv in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
            if cv.canvas is clicked:
                continue
            if cv is self.plane_canvas:
                x, y = own[idx][1], own[idx][2]
                angle = self.mplot.origin_angle
                c, s = np.cos(-angle), np.sin(-angle)
                cv.center = [float(c * x - s * y), float(s * x + c * y)]
            else:
                cv.center[0] = distance
            cv.redraw()
        self._sync_measure_markers(distance)
        return 'break'
    def update_measure_info(self):
        if self.measure_pos is None or self.mplot is None:
            self.measure_info_label.config(text='')
            return
        info = self.mplot.get_track_info_at(self.measure_pos['distance'])
        if info is None:
            self.measure_info_label.config(text='')
            return
        speed_text = i18n.get('info.no_limit') if info['speed'] is None else '{:.0f} km/h'.format(info['speed'])
        text = '{m}: {mileage:.0f}m | {e}: {elevation:.1f}m | {g}: {gradient:.1f}‰ | {r}: {radius:.0f}m | {s}: {speed}'.format(
            m=i18n.get('info.mileage'), mileage=info['mileage'],
            e=i18n.get('info.elevation'), elevation=info['elevation'],
            g=i18n.get('info.gradient'), gradient=info['gradient'],
            r=i18n.get('info.radius'), radius=info['radius'],
            s=i18n.get('info.speedlimit'), speed=speed_text)
        self.measure_info_label.config(text=text)
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
            
            self._clear_logs()
            t_start = time.perf_counter()
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
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            
            self.print_debugdata()
    def reload_map(self, event=None):
        inputdir = self.filedir_entry_val.get()
        if inputdir != '':
            # マップ描画設定の退避
            tmp_cp_arbdistribution   = self.mplot.environment.cp_arbdistribution
            tmp_othertrack_checked   = self.subwindow.othertrack_tree.get_checked()
            tmp_othertrack_linecolor = self.result.othertrack_linecolor
            tmp_othertrack_cprange   = self.result.othertrack.cp_range
            
            self._clear_logs()
            t_start = time.perf_counter()
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
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            
            self.print_debugdata()
    def draw_planerplot(self):
        data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked())

        def render(view):
            if hasattr(self, 'bg_image_original') and self.bg_image_original is not None:
                vp = view.get_view_params()
                cx, cy = view.world_to_screen(self.bg_image_params['x'], self.bg_image_params['y'])

                px_w = int(self.bg_image_params['width'] * vp['sx_scale'])
                px_h = int(self.bg_image_params['height'] * vp['sy_scale'])

                if 0 < px_w < 15000 and 0 < px_h < 15000:
                    try:
                        resample_mode = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                        resized_img = self.bg_image_original.resize((px_w, px_h), resample_mode)

                        view_rot_deg = math.degrees(vp['rotation'])
                        total_rot_ccw = -self.bg_image_params['rotation'] - view_rot_deg
                        rotated_img = resized_img.rotate(total_rot_ccw, expand=True)

                        self.bg_image_tk = ImageTk.PhotoImage(rotated_img)
                        view.canvas.create_image(cx, cy, image=self.bg_image_tk, anchor=tk.CENTER)
                    except Exception:
                        pass

            if len(data['owntrack']) > 0:
                if self.curveval_val.get():
                    for sec in data['curve_sections']:
                        mask = (data['owntrack'][:, 0] >= sec['start']) & (data['owntrack'][:, 0] <= sec['end'])
                        if mask.sum() >= 2:
                            view.line(data['owntrack'][mask][:, 1:3], fill='#888888', width=10)
                    for sec in data['transition_sections']:
                        mask = (data['owntrack'][:, 0] >= sec['start']) & (data['owntrack'][:, 0] <= sec['end'])
                        if mask.sum() >= 2:
                            view.line(data['owntrack'][mask][:, 1:3], fill='#555555', width=8)
                view.line(data['owntrack'][:, 1:3], width=2)
            other_track_tasks = [(t, t['points'][:, 1:3]) for t in data['othertracks'] if len(t['points']) > 0]
            if other_track_tasks:
                vp = view.get_view_params()
                tasks = []
                with ThreadPoolExecutor(max_workers=min(len(other_track_tasks), 8)) as executor:
                    for track, pts in other_track_tasks:
                        tasks.append((track, executor.submit(
                            canvasplot.PlotCanvas._world_to_screen_static, pts, vp)))
                for track, future in tasks:
                    coords = future.result()
                    if coords:
                        view.line_screen(coords, fill=track['color'], width=1)
            if self.stationpos_val.get():
                for station in data['stations']:
                    x = station['point'][1]
                    y = station['point'][2]
                    view.point(x, y, radius=4)
                    if self.stationlabel_val.get():
                        view.text(x, y, station['name'], offset=(8, -8), font_size=9)
                    if self.stationmileage_val.get():
                        view.text(x, y, self.format_mileage(station['mileage']), offset=(8, 8), font_size=8, fill='#ffd84d')

            if self.speedlimit_val.get():
                import math as _math
                canvas = view.canvas
                for sp in data['speedlimits']:
                    sx, sy = view.world_to_screen(sp['x'], sp['y'])
                    t = sp['theta']
                    wx_perp = sp['x'] - _math.sin(t)
                    wy_perp = sp['y'] + _math.cos(t)
                    sx_perp, sy_perp = view.world_to_screen(wx_perp, wy_perp)
                    sdx = sx_perp - sx
                    sdy = sy_perp - sy
                    screen_len = _math.sqrt(sdx * sdx + sdy * sdy)
                    if screen_len > 0:
                        sdx = sdx / screen_len * 8
                        sdy = sdy / screen_len * 8
                    canvas.create_line(sx - sdx, sy - sdy, sx + sdx, sy + sdy,
                                       fill='#88ccff', width=1)
                    if sp['speed'] is not None:
                        view.text(sp['x'], sp['y'],
                                  str(int(sp['speed'])),
                                  offset=(10, -15), font_size=9, fill='#88ccff')
                    else:
                        view.text(sp['x'], sp['y'], 'x',
                                  offset=(10, -15), font_size=9, fill='#88ccff')

            if self.curveval_val.get() and len(data['curve_sections']) > 0:
                for sec in data['curve_sections']:
                    mid_d = (sec['start'] + sec['end']) / 2
                    idx = np.searchsorted(data['owntrack'][:, 0], mid_d)
                    if idx >= len(data['owntrack']):
                        idx = len(data['owntrack']) - 1
                    mx = data['owntrack'][idx][1]
                    my = data['owntrack'][idx][2]
                    view.text(mx, my, str(int(sec['radius'])),
                              offset=(8, -16), font_size=8, fill='#88ff88')

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
            other_track_tasks = [(t, t['points'][:, [0, 3]]) for t in data['othertracks'] if len(t['points']) > 0]
            if other_track_tasks:
                vp = view.get_view_params()
                tasks = []
                with ThreadPoolExecutor(max_workers=min(len(other_track_tasks), 8)) as executor:
                    for track, pts in other_track_tasks:
                        tasks.append((track, executor.submit(
                            canvasplot.PlotCanvas._world_to_screen_static, pts, vp)))
                for track, future in tasks:
                    coords = future.result()
                    if coords:
                        view.line_screen(coords, fill=track['color'], width=1)

            canvas = view.canvas
            height = max(1, canvas.winfo_height())

            if self.stationpos_val.get():
                for station in data['stations']:
                    x = station['point'][0]
                    z = station['point'][3]
                    screen_x, screen_z = view.world_to_screen(x, z)
                    canvas.create_line(screen_x, screen_z, screen_x, -100, fill='#ffffff', width=1)
                    view.point(x, z, radius=3)
                    if self.stationlabel_val.get():
                        view.text(x, z, station['name'], offset=(8, -26), font_size=9)
                    if self.stationmileage_val.get():
                        screen_x, _ = view.world_to_screen(x, 0)
                        canvas.create_text(screen_x + 8, 8, anchor='nw',
                            text=self.format_mileage(station['mileage']),
                            fill='#ffd84d', font=(view.font_family, 8), tags=('fixed_y',))
            if self.gradientpos_val.get():
                for point in data['gradient_points']:
                    screen_x, screen_z = view.world_to_screen(point['x'], point['z'])
                    canvas.create_line(screen_x, screen_z, screen_x, height + 100, fill='#ffffff', width=1)
                for label in data['gradient_labels']:
                    if self.gradientval_val.get():
                        screen_x, _ = view.world_to_screen(label['x'], 0)
                        canvas.create_text(screen_x + 6, height - 6, anchor='se',
                            text=label['text'], fill='#ffffff',
                            font=(view.font_family, 8), tags=('fixed_y',))

        if self.show_gradient_graph_val.get():
            self.profile_canvas.set_renderer(render, bounds=data['bounds'], keep_view=self.keep_view_on_next_draw)

        def render_radius(view):
            if len(data['curve']) > 0:
                view.line(data['curve'], width=2)
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
    def plot_all(self, keep_view=True):
        if(self.result != None):
            self._clear_measure_marker()
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
    def import_bgimg(self):
        filepath = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if not filepath:
            return
        try:
            self.bg_image_original = Image.open(filepath)
        except Exception as e:
            tk.messagebox.showerror(message=f"无法加载图片: {e}")
            return

        start_x, start_y = 0.0, 0.0
        if self.result is not None and hasattr(self.result, 'environment') and len(self.result.environment.owntrack_pos) > 0:
            start_x = float(self.result.environment.owntrack_pos[0][1])
            start_y = float(self.result.environment.owntrack_pos[0][2])

        img_w, img_h = self.bg_image_original.size
        self.bg_image_params['x'] = start_x
        self.bg_image_params['y'] = start_y
        self.bg_image_params['width'] = 5000.0
        self.bg_image_params['height'] = 5000.0 * (img_h / img_w)
        self.bg_image_params['rotation'] = 0.0

        self.bgimg_adjust_btn.config(state=tk.NORMAL)
        if hasattr(self, 'plane_canvas'):
            self.plane_canvas.redraw()

    def adjust_bgimg(self):
        if self.bg_image_original is None:
            return

        dialog = tk.Toplevel(self.master)
        dialog.title("调整背景图片")
        dialog.transient(self.master)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding='10 10 10 10')
        frame.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        var_x = tk.DoubleVar(value=self.bg_image_params['x'])
        var_y = tk.DoubleVar(value=self.bg_image_params['y'])
        var_width = tk.DoubleVar(value=self.bg_image_params['width'])
        var_height = tk.DoubleVar(value=self.bg_image_params['height'])
        var_rotation = tk.DoubleVar(value=self.bg_image_params['rotation'])

        fields = [
            ("X (m)", var_x),
            ("Y (m)", var_y),
            ("宽度 (m)", var_width),
            ("高度 (m)", var_height),
            ("旋转角度 (°)", var_rotation),
        ]

        for i, (label_text, var) in enumerate(fields):
            ttk.Label(frame, text=label_text).grid(column=0, row=i, sticky=tk.W, padx=(0, 8), pady=2)
            ttk.Entry(frame, textvariable=var, width=20).grid(column=1, row=i, sticky=(tk.W, tk.E), pady=2)

        def on_ok():
            try:
                self.bg_image_params['x'] = var_x.get()
                self.bg_image_params['y'] = var_y.get()
                self.bg_image_params['width'] = var_width.get()
                self.bg_image_params['height'] = var_height.get()
                self.bg_image_params['rotation'] = var_rotation.get()
                dialog.destroy()
                if hasattr(self, 'plane_canvas'):
                    self.plane_canvas.redraw()
            except ValueError:
                tk.messagebox.showerror(message="输入值无效，请输入数字", parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(column=0, row=len(fields), columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text="确定", command=on_ok).grid(column=0, row=0, padx=(0, 8))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).grid(column=1, row=0)

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        var_x_entry = frame.grid_slaves(row=0, column=1)[0]
        var_x_entry.focus_set()
        dialog.wait_window()
    def customdialog_test(self, event=None):
        dialog_obj = dialog_multifields.dialog_multifields(self,\
                                        [{'name':'A', 'type':'str', 'label':'test A', 'default':'alpha'},\
                                        {'name':'B', 'type':'Double', 'label':'test B', 'default':100}],\
                                        'Test Dialog')
        print('Done', dialog_obj.result, dialog_obj.variables['A'].get())
    def open_webdocument(self, event=None):
        webbrowser.open('https://github.com/NewSapporoNingyo/kobushi-trackviewer-modified')
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
