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
#Import standard library modules (sys, pathlib, os, time, queue, webbrowser, argparse, math)
#標準ライブラリモジュール（sys, pathlib, os, time, queue, webbrowser, argparse, math）をインポート
#导入标准库模块（sys, pathlib, os, time, queue, webbrowser, argparse, math）
import sys
import pathlib
import os
import time
import queue
import webbrowser
import argparse
import math

#Import tkinter GUI framework components 
#tkinter GUIフレームワークのコンポーネントをインポート
#导入tkinter GUI框架组件
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
import tkinter.simpledialog as simpledialog
import tkinter.font as font

#Import scientific computing and image processing libraries
#科学計算・画像処理ライブラリをインポート
#导入科学计算和图像处理库
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageTk

# Import internal project modules (version, map interpreter, plotting, dialogs, subwindows, font control, multi-language)
#内部プロジェクトモジュール（バージョン、マップ解釈、プロット、ダイアログ、サブウィンドウ、フォント制御、多言語）をインポート
#导入内部项目模块（版本、地图解释器、绘图、对话框、子窗口、字体控制、国际化）
from ._version import __version__
from . import mapinterpreter as interp
from . import mapplot
from . import canvasplot
from . import dialog_multifields
from . import othertrack_window
from . import font_window
from . import i18n

# Catcher class — wraps tkinter callbacks to catch exceptions that occur inside tkinter event handlers; reference: http://centerwave-callout.com/tkinter内で起きた例外をどうキャッチするか？/    
# Catcherクラス — tkinterのイベントハンドラ内で発生した例外をキャッチするためのラッパー；参考: http://centerwave-callout.com/tkinter内で起きた例外をどうキャッチするか？/   
# Catcher类 — 包装tkinter回调以捕获tkinter事件处理程序中发生的异常；参考: http://centerwave-callout.com/tkinter内で起きた例外をどうキャッチするか？/
# Catches exceptions raised inside tkinter callbacks / tkinterのコールバック内で発生した例外をキャッチする / 捕获tkinter回调中引发的异常
class Catcher:
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
            # In debug mode (-O), let the exception propagate so pdb can start /  デバッグモード(-O)なら素通し。pdbが起動する / 调试模式(-O)下让异常穿透以便pdb启动
            if not __debug__:
                raise e
            else:
                # In normal mode, show exception in a message dialog /  通常モードならダイアログ表示 / 普通模式下在对话框中显示异常
                print(e)
                tk.messagebox.showinfo(message=e)

# LogInterceptor class — redirects stdout/stderr to a queue so log messages can be displayed in the GUI    
#LogInterceptorクラス — 標準出力/標準エラーをキューにリダイレクトし、ログメッセージをGUIに表示できるようにする   
#LogInterceptor类 — 将stdout/stderr重定向到队列以便在GUI中显示日志消息
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

#mainwindow class — the primary application window containing all track visualization canvases and controls   
#mainwindowクラス — 全ての線路可視化キャンバスと操作コントロールを含むメインアプリケーションウィンドウ  
#mainwindow类 — 包含所有轨道可视化画布和控件的主应用程序窗口
class mainwindow(ttk.Frame):
    #Constructor — initializes the main window, sets up widgets, menus, key bindings, background image support, log interception, and i18n
    #コンストラクタ — メインウィンドウを初期化し、ウィジェット、メニュー、キーバインド、背景画像サポート、ログ傍受、国際化を設定する  
    #构造函数 — 初始化主窗口，设置控件、菜单、按键绑定、背景图像支持、日志拦截和国际化
    def __init__(self, master, parser, stepdist = 25, font = ''):
        self.dmin = None
        self.dmax = None
        self.result = None
        self.profYlim = None
        self.default_track_interval = stepdist
        self.bgimg_show_val = tk.BooleanVar(value=True)
        
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
        self.bg_image_thumbnail = None
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

    # Refreshes all UI text labels when the language is changed / 言語変更時にすべてのUIテキストラベルを更新する / 语言切换时刷新所有UI文本标签
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
        if hasattr(self, 'bgimg_label'):
            self.bgimg_label.config(text=i18n.get('frame.bgimage'))
        if hasattr(self, 'bgimg_import_btn'):
            self.bgimg_import_btn.config(text=i18n.get('button.import_bg'))
        if hasattr(self, 'bgimg_adjust_btn'):
            self.bgimg_adjust_btn.config(text=i18n.get('button.adjust_bg'))
        if hasattr(self, 'bgimg_show_chk'):
            self.bgimg_show_chk.config(text=i18n.get('chk.bgimg_show'))
        if self.result is not None:
            self.plot_all()

    #Creates all control widgets — mode selection, grid settings, graph visibility, auxiliary info checkboxes, file path entry, canvas paned windows, station jump, background image controls    
    #すべての操作ウィジェットを作成 — モード選択、グリッド設定、グラフ表示切替、補助情報チェックボックス、ファイルパス入力、キャンバスペインウィンドウ、駅ジャンプ、背景画像コントロール  
    #创建所有控件 — 模式选择、网格设置、图表可见性、辅助信息复选框、文件路径输入、画布分栏窗口、车站跳转、背景图像控件
    def create_widgets(self):
        self.control_frame = ttk.Frame(self, padding='3 3 3 3')
        self.control_frame.grid(column=1, row=1, sticky=(tk.S))
        
        font_title = font.Font(weight='bold',size=10)
        
        # Auxiliary info panel — checkboxes for station position, station name, station mileage, curve value, speed limit display  / 補助情報パネル — 駅位置、駅名、駅キロ程、曲線値、速度制限表示のチェックボックス / 辅助信息面板 — 车站位置、车站名称、车站里程、曲线值、速度限制显示的复选框
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

        # Graph visibility panel — checkboxes for showing/hiding curve graph, gradient graph, gradient position markers, gradient values, other track profile /  グラフ表示パネル — 曲線グラフ、勾配グラフ、勾配位置マーカー、勾配値、他軌道プロファイルの表示/非表示チェックボックス / 图表可见性面板 — 显示/隐藏曲线图、坡度图、坡度位置标记、坡度值、其他轨道剖面的复选框
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

        # Grid control panel — radio buttons for fixed grid, movable grid, or no grid on the plane canvas /  グリッドコントロールパネル — 平面キャンバス上の固定グリッド、可動グリッド、グリッドなしのラジオボタン / 网格控制面板 — 平面画布上固定网格、可移动网格、无网格的单选按钮
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

        # Mode control panel — radio buttons for pan mode (interactive navigation) and measure mode (distance measurement)  / モードコントロールパネル — パンモード（インタラクティブナビゲーション）と計測モード（距離計測）のラジオボタン / 模式控制面板 — 平移模式（交互导航）和测量模式（距离测量）的单选按钮
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
        
        # File frame — contains open button, file path entry, error/warning indicators, and last log message label  / ファイルフレーム — 開くボタン、ファイルパス入力、エラー/警告インジケータ、最終ログメッセージラベルを含む / 文件框架 — 包含打开按钮、文件路径输入、错误/警告指示器和最后一条日志消息标签
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
        
        # Distance/measurement info and station jump frame / 距離/計測情報と駅ジャンプフレーム / 距离/测量信息和车站跳转框架
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
        
        # Canvas frame — contains the paned windows for plane, profile, and radius canvases / キャンバスフレーム — 平面、プロファイル、半径キャンバスのペインウィンドウを含む / 画布框架 — 包含平面、剖面和半径画布的分栏窗口
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

        # Background image control panel — import, adjust, and show/hide background image / 背景画像コントロールパネル — 背景画像のインポート、調整、表示/非表示 / 背景图像控制面板 — 导入、调整和显示/隐藏背景图像
        self.bgimg_control = ttk.Frame(self.control_frame, padding='3 3 3 3', borderwidth=1, relief='ridge')
        self.bgimg_control.grid(column=0, row=10, sticky=(tk.S, tk.W, tk.E), pady=(6, 0))

        self.bgimg_label = ttk.Label(self.bgimg_control, text=i18n.get('frame.bgimage'), font=font_title)
        self.bgimg_label.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E))

        self.bgimg_show_chk = ttk.Checkbutton(self.bgimg_control, text=i18n.get('chk.bgimg_show'), variable=self.bgimg_show_val, command=self.on_bgimg_show_toggle, state=tk.DISABLED)
        self.bgimg_show_chk.grid(column=0, row=1, sticky=(tk.N, tk.W, tk.E))

        self.bgimg_import_btn = ttk.Button(self.bgimg_control, text=i18n.get('button.import_bg'), command=self.import_bgimg)
        self.bgimg_import_btn.grid(column=0, row=2, sticky=(tk.N, tk.W, tk.E))

        self.bgimg_adjust_btn = ttk.Button(self.bgimg_control, text=i18n.get('button.adjust_bg'), command=self.adjust_bgimg, state=tk.DISABLED)
        self.bgimg_adjust_btn.grid(column=0, row=3, sticky=(tk.N, tk.W, tk.E))

    # Updates the pane layout — shows or hides individual canvas panes based on graph visibility checkboxes /  ペインレイアウトを更新 — グラフ表示チェックボックスに基づいて各キャンバスペインを表示/非表示にする / 更新分栏布局 — 根据图表可见性复选框显示或隐藏各个画布分栏
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

    # Toggles station position display sub-items — enables/disables station name and mileage checkboxes based on station position checkbox    駅位置表示のサブ項目を切り替え — 駅位置チェックボックスに応じて駅名・キロ程チェックボックスを有効/無効にする   切换车站位置显示子项 — 根据车站位置复选框启用/禁用车站名称和里程复选框
    def on_stationpos_toggle(self):
        if self.stationpos_val.get():
            self.stationlabel_chk.config(state='normal')
            self.stationmileage_chk.config(state='normal')
        else:
            self.stationlabel_chk.config(state='disabled')
            self.stationmileage_chk.config(state='disabled')
        self.plot_all()

    # Toggles gradient position display sub-items — enables/disables gradient value checkbox based on gradient position checkbox    勾配位置表示のサブ項目を切り替え — 勾配位置チェックボックスに応じて勾配値チェックボックスを有効/無効にする   切换坡度位置显示子项 — 根据坡度位置复选框启用/禁用坡度值复选框
    def on_gradientpos_toggle(self):
        if self.gradientpos_val.get():
            self.gradientval_chk.config(state='normal')
        else:
            self.gradientval_chk.config(state='disabled')
        self.plot_all()

    # Toggles background image visibility and triggers a redraw    背景画像の表示/非表示を切り替えて再描画を実行する   切换背景图像的显示/隐藏并触发重绘
    def on_bgimg_show_toggle(self):
        self.plot_all()

    # Periodic log queue checker — polls the log queue every 100ms, categorizes messages as errors or warnings, updates button labels    定期的なログキューチェック — 100msごとにログキューをポーリングし、メッセージをエラーまたは警告に分類し、ボタンラベルを更新する   定期日志队列检查 — 每100毫秒轮询日志队列，将消息分类为错误或警告，更新按钮标签
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

    # Clears all accumulated error and warning logs and resets the indicator buttons    蓄積されたエラーと警告ログをすべてクリアし、インジケータボタンをリセットする   清除所有累积的错误和警告日志并重置指示器按钮
    def _clear_logs(self):
        self._log_errors.clear()
        self._log_warnings.clear()
        self._log_last_msg.set('')
        self._log_err_btn.config(text='🐛 0')
        self._log_warn_btn.config(text='⚠ 0')

    # Opens a detail window showing all captured error messages    キャプチャされたすべてのエラーメッセージを表示する詳細ウィンドウを開く   打开一个显示所有捕获错误消息的详细信息窗口
    def _show_error_details(self):
        self._show_log_detail_window('Errors', self._log_errors)

    # Opens a detail window showing all captured warning messages    キャプチャされたすべての警告メッセージを表示する詳細ウィンドウを開く   打开一个显示所有捕获警告消息的详细信息窗口
    def _show_warning_details(self):
        self._show_log_detail_window('Warnings', self._log_warnings)

    # Creates a popup window with a scrollable text area to display log messages    ログメッセージを表示するスクロール可能なテキストエリアを持つポップアップウィンドウを作成する   创建一个带有可滚动文本区域的弹出窗口以显示日志消息
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

    # Applies the selected grid mode (fixed/movable/none) to the plane canvas    選択されたグリッドモード（固定/可動/なし）を平面キャンバスに適用する   将选定的网格模式（固定/可移动/无）应用于平面画布
    def on_grid_mode_change(self):
        self.plane_canvas.set_grid_mode(self.grid_mode_val.get())

    # Switches between pan mode and measure mode — in measure mode, binds mouse motion/double-click events for distance measurement across all canvases    パンモードと計測モードを切り替え — 計測モードでは、全キャンバスにマウス移動/ダブルクリックイベントをバインドして距離計測を行う   在平移模式和测量模式之间切换 — 测量模式下在所有画布上绑定鼠标移动/双击事件以进行距离测量
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

    # Removes all measure marker graphics from all canvases    すべてのキャンバスから計測マーカーグラフィックを削除する   从所有画布中移除所有测量标记图形
    def _clear_measure_marker(self):
        for canvas, ids in list(self._measure_marker_ids.items()):
            for item_id in ids:
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
        self._measure_marker_ids = {}

    # Synchronizes measure marker positions — draws a crosshair on the plane canvas and vertical lines on profile/radius canvases at the given distance    計測マーカーの位置を同期 — 指定された距離で平面キャンバスにクロスヘア、プロファイル/半径キャンバスに垂直線を描画する   同步测量标记位置 — 在给定距离处，在平面画布上绘制十字准线，在剖面/半径画布上绘制垂直线
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

    # Handles mouse motion on the plane canvas in measure mode — finds nearest track point within 30px and updates measure markers    計測モードで平面キャンバス上のマウス移動を処理 — 30px以内の最近傍軌道点を見つけて計測マーカーを更新する   在测量模式下处理平面画布上的鼠标移动 — 查找30像素内最近的轨道点并更新测量标记
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

    # Handles mouse motion on the profile canvas in measure mode — updates measure position based on the X world coordinate of the mouse    計測モードでプロファイルキャンバス上のマウス移動を処理 — マウスのXワールド座標に基づいて計測位置を更新する   在测量模式下处理剖面画布上的鼠标移动 — 根据鼠标的X世界坐标更新测量位置
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

    # Handles mouse motion on the radius canvas in measure mode — similar to profile motion, updates measure position based on X coordinate    計測モードで半径キャンバス上のマウス移動を処理 — プロファイルと同様に、X座標に基づいて計測位置を更新する   在测量模式下处理半径画布上的鼠标移动 — 与剖面类似，根据X坐标更新测量位置
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

    # Handles double-click in measure mode — re-centers all canvases on the measured position    計測モードでのダブルクリックを処理 — すべてのキャンバスを計測位置に再センタリングする   处理测量模式下的双击 — 将所有画布重新居中到测量位置
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

    # Updates the measure info label with mileage, elevation, gradient, radius, and speed limit at the current measure position    現在の計測位置におけるキロ程、標高、勾配、半径、速度制限を計測情報ラベルに更新する   更新测量信息标签，显示当前测量位置的里程、高程、坡度、半径和速度限制
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

    # Creates the menu bar — File (open, reload, save image, save track data, exit), Options (control points, plot limit, font), Language (i18n), Help (reference, about)    メニューバーを作成 — ファイル（開く、再読込、画像保存、線路データ保存、終了）、オプション（制御点、プロット範囲、フォント）、言語（国際化）、ヘルプ（リファレンス、バージョン情報）   创建菜单栏 — 文件（打开、重新加载、保存图像、保存轨道数据、退出）、选项（控制点、绘图范围、字体）、语言（国际化）、帮助（参考、关于）
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

    # Binds keyboard shortcuts — Ctrl+O (open), Ctrl+S (save), F5 (reload), Alt+F4 (quit)    キーボードショートカットをバインド — Ctrl+O（開く）、Ctrl+S（保存）、F5（再読込）、Alt+F4（終了）   绑定键盘快捷键 — Ctrl+O（打开）、Ctrl+S（保存）、F5（重新加载）、Alt+F4（退出）
    def bind_keyevent(self):
        self.bind_all("<Control-o>", self.open_mapfile)
        self.bind_all("<Control-s>", self.save_plots)
        self.bind_all("<F5>", self.reload_map)
        self.bind_all("<Alt-F4>", self.ask_quit)

    # Opens a map file via file dialog, parses it, initializes track data, sets up station list, other tracks, and triggers plotting    ファイルダイアログでマップファイルを開き、解析し、線路データを初期化し、駅リスト・他軌道を設定してプロットを実行する   通过文件对话框打开地图文件，解析它，初始化轨道数据，设置车站列表和其他轨道，并触发绘图
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
                
            # self.distrange_min/max — the maximum/minimum displayable distance range for the target map    self.distrange_min/max — 対象のマップで表示可能な距離程の最大最小値を示す   self.distrange_min/max — 目标地图中可显示距离范围的最大/最小值
            # self.dmin/dmax — the actual distance range currently plotted on screen    self.dmin/dmax — 実際に画面にプロットする距離程の範囲を示す   self.dmin/dmax — 实际在屏幕上绘制的距离范围
                
            # Assign default line colors to other tracks    他軌道のラインカラーを設定   为其他轨道分配默认线条颜色
            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {'current':linecolor_default[color_ix%10], 'default':linecolor_default[color_ix%10]}
                color_ix += 1
                
            # Update station jump combo box    駅ジャンプメニュー更新   更新车站跳转下拉框
            stnlist_tmp = []
            self.stationlist_cb['values'] = ()
            for stationkey in self.result.station.stationkey.keys():
                stnlist_tmp.append(stationkey+', '+self.result.station.stationkey[stationkey])
            self.stationlist_cb['values'] = tuple(stnlist_tmp)
                
            self.subwindow.set_ottree_value()
            
            self.profYlim = None
            
            self.mplot = mapplot.Mapplot(self.result, unitdist_default=self.default_track_interval)
            self.setdist_all()
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            
            self.print_debugdata()

    # Reloads the current map file — preserves view state, other track settings, and control point distribution; re-parses and re-renders    現在のマップファイルを再読み込み — ビュー状態、他軌道設定、制御点分布を保持し、再解析・再描画する   重新加载当前地图文件 — 保留视图状态、其他轨道设置和控制点分布，重新解析并重新渲染
    def reload_map(self, event=None):
        inputdir = self.filedir_entry_val.get()
        if inputdir != '':
            # Save current map drawing settings for restoration after reload    マップ描画設定の退避   保存当前地图绘制设置以便重新加载后恢复
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

            # self.distrange_min/max — the maximum/minimum displayable distance range for the target map    self.distrange_min/max — 対象のマップで表示可能な距離程の最大最小値を示す   self.distrange_min/max — 目标地图中可显示距离范围的最大/最小值
            # self.dmin/dmax — the actual distance range currently plotted on screen    self.dmin/dmax — 実際に画面にプロットする距離程の範囲を示す   self.dmin/dmax — 实际在屏幕上绘制的距离范围
                
            # Assign default line colors to other tracks    他軌道のラインカラーを設定   为其他轨道分配默认线条颜色
            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {'current':linecolor_default[color_ix%10], 'default':linecolor_default[color_ix%10]}
                color_ix += 1
                
            self.subwindow.set_ottree_value()
            
            # Restore other track drawing settings from saved state    他軌道の描画情報を復帰   从保存状态恢复其他轨道绘图设置
            for key in tmp_othertrack_cprange.keys():
                if key in self.result.othertrack.data.keys():
                    self.result.othertrack.cp_range[key] = tmp_othertrack_cprange[key]
                    self.subwindow.othertrack_tree.set(key,'#1',tmp_othertrack_cprange[key]['min'])
                    self.subwindow.othertrack_tree.set(key,'#2',tmp_othertrack_cprange[key]['max'])
                    self.subwindow.othertrack_tree.tag_configure(key,foreground=tmp_othertrack_linecolor[key]['current'])
                    self.result.othertrack_linecolor[key] = tmp_othertrack_linecolor[key]
                    if key in tmp_othertrack_checked:
                        self.subwindow.othertrack_tree._check_ancestor(key)
                    
                
            # Update station jump combo box    駅ジャンプメニュー更新   更新车站跳转下拉框
            stnlist_tmp = []
            self.stationlist_cb['values'] = ()
            for stationkey in self.result.station.stationkey.keys():
                stnlist_tmp.append(stationkey+', '+self.result.station.stationkey[stationkey])
            self.stationlist_cb['values'] = tuple(stnlist_tmp)
            
            view_state = self.get_view_state()
            self.mplot = mapplot.Mapplot(self.result,cp_arbdistribution = tmp_cp_arbdistribution)
            self.plot_all(keep_view=True)
            self.set_view_state(view_state)
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            
            self.print_debugdata()

    # Renders the plan (2D top-down) view — draws own track, other tracks, stations, speed limits, curve sections, and optional background image    平面（2Dトップダウン）ビューを描画 — 自軌道、他軌道、駅、速度制限、曲線区間、オプションの背景画像を描画する   渲染平面（2D俯视）视图 — 绘制自身轨道、其他轨道、车站、速度限制、曲线区间和可选的背景图像
    def draw_planerplot(self):
        data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked())

        def render(view):
            # Draw background image if enabled — crop and transform the image to match the current viewport    背景画像が有効な場合に描画 — 画像を現在のビューポートに合わせて切り抜き・変形する   如果启用则绘制背景图像 — 裁剪并变换图像以匹配当前视口
            if self.bgimg_show_val.get() and hasattr(self, 'bg_image_original') and self.bg_image_original is not None:
                vp = view.get_view_params()

                margin = 0.5
                vis_xmin, vis_ymin, vis_xmax, vis_ymax = view._get_visible_world_bounds(margin=margin)

                bg_x = self.bg_image_params['x']
                bg_y = self.bg_image_params['y']
                bg_w = self.bg_image_params['width']
                bg_h = self.bg_image_params['height']
                bg_rot = self.bg_image_params['rotation']

                vis_cx, vis_cy = (vis_xmin + vis_xmax) / 2.0, (vis_ymin + vis_ymax) / 2.0
                vis_radius = math.hypot(vis_xmax - vis_xmin, vis_ymax - vis_ymin) / 2.0
                bg_radius = math.hypot(bg_w, bg_h) / 2.0
                if math.hypot(bg_x - vis_cx, bg_y - vis_cy) > (bg_radius + vis_radius):
                    return

                orig_w, orig_h = self.bg_image_original.size

                rad = math.radians(bg_rot)
                cos_r, sin_r = math.cos(rad), math.sin(rad)

                corners_world = [
                    (vis_xmin, vis_ymin), (vis_xmax, vis_ymin),
                    (vis_xmin, vis_ymax), (vis_xmax, vis_ymax)
                ]
                corners_img = []
                for wx, wy in corners_world:
                    dx = wx - bg_x
                    dy = wy - bg_y
                    local_x = dx * cos_r + dy * sin_r
                    local_y = -dx * sin_r + dy * cos_r
                    px = (local_x / bg_w) * orig_w + orig_w / 2.0
                    py = (local_y / bg_h) * orig_h + orig_h / 2.0
                    corners_img.append((px, py))

                crop_xmin = max(0, int(min(p[0] for p in corners_img)))
                crop_xmax = min(orig_w, int(max(p[0] for p in corners_img)))
                crop_ymin = max(0, int(min(p[1] for p in corners_img)))
                crop_ymax = min(orig_h, int(max(p[1] for p in corners_img)))

                if crop_xmax <= crop_xmin or crop_ymax <= crop_ymin:
                    return

                crop_w = crop_xmax - crop_xmin
                crop_h = crop_ymax - crop_ymin

                px_w = int(bg_w * vp['sx_scale'])
                px_h = int(bg_h * vp['sy_scale'])
                target_px_w = int(crop_w / orig_w * px_w)
                target_px_h = int(crop_h / orig_h * px_h)

                if target_px_w <= 0 or target_px_h <= 0:
                    return

                if target_px_w > 15000 or target_px_h > 15000:
                    return

                try:
                    if hasattr(Image, "Resampling"):
                        modes = {'high': Image.Resampling.LANCZOS, 'low': Image.Resampling.NEAREST}
                    else:
                        modes = {'high': Image.LANCZOS, 'low': Image.NEAREST}

                    interacting = view.is_interacting() and self.bg_image_thumbnail is not None
                    if interacting:
                        src_img = self.bg_image_thumbnail
                        resample_mode = modes['low']
                        thumb_w, thumb_h = src_img.size
                        sx_t = thumb_w / orig_w
                        sy_t = thumb_h / orig_h
                        tcrop_xmin = max(0, int(crop_xmin * sx_t))
                        tcrop_xmax = min(thumb_w, int(crop_xmax * sx_t))
                        tcrop_ymin = max(0, int(crop_ymin * sy_t))
                        tcrop_ymax = min(thumb_h, int(crop_ymax * sy_t))
                        if tcrop_xmax <= tcrop_xmin or tcrop_ymax <= tcrop_ymin:
                            return
                        cropped_img = src_img.crop((tcrop_xmin, tcrop_ymin, tcrop_xmax, tcrop_ymax))
                    else:
                        cropped_img = self.bg_image_original.crop((crop_xmin, crop_ymin, crop_xmax, crop_ymax))
                        resample_mode = modes['high']

                    resized_img = cropped_img.resize((target_px_w, target_px_h), resample_mode)

                    view_rot_deg = math.degrees(vp['rotation'])
                    total_rot_ccw = -bg_rot - view_rot_deg
                    rotated_img = resized_img.rotate(total_rot_ccw, expand=True)

                    offset_x_px = (crop_xmin + crop_xmax) / 2.0 - orig_w / 2.0
                    offset_y_px = (crop_ymin + crop_ymax) / 2.0 - orig_h / 2.0
                    offset_local_x = (offset_x_px / orig_w) * bg_w
                    offset_local_y = (offset_y_px / orig_h) * bg_h

                    offset_w_x = offset_local_x * cos_r - offset_local_y * sin_r
                    offset_w_y = offset_local_x * sin_r + offset_local_y * cos_r

                    crop_center_w_x = bg_x + offset_w_x
                    crop_center_w_y = bg_y + offset_w_y

                    cx, cy = view.world_to_screen(crop_center_w_x, crop_center_w_y)

                    self.bg_image_tk = ImageTk.PhotoImage(rotated_img)
                    img_id = view.canvas.create_image(cx, cy, image=self.bg_image_tk, anchor=tk.CENTER, tags=('bgimage',))
                    view.canvas.tag_lower(img_id)
                except Exception:
                    pass

            # Draw own track — highlight curve sections with thicker colored lines, draw transition sections, then the main track line    自軌道を描画 — 曲線区間を太い色付き線で強調し、緩和曲線区間を描画、その後メインの軌道線を描画する   绘制自身轨道 — 用较粗的彩色线条高亮曲线区间，绘制缓和曲线区间，然后绘制主轨道线
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
            # Draw other tracks using parallel threads for coordinate transformation    他軌道を座標変換に並列スレッドを使用して描画する   使用并行线程进行坐标变换来绘制其他轨道
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
            # Draw station markers — points, labels, and mileage on the plan view    駅マーカーを描画 — 平面図上に点、ラベル、キロ程を表示する   绘制车站标记 — 在平面视图上显示点、标签和里程
            if self.stationpos_val.get():
                for station in data['stations']:
                    x = station['point'][1]
                    y = station['point'][2]
                    view.point(x, y, radius=4)
                    if self.stationlabel_val.get():
                        view.text(x, y, station['name'], offset=(8, -8), font_size=9)
                    if self.stationmileage_val.get():
                        view.text(x, y, self.format_mileage(station['mileage']), offset=(8, 8), font_size=8, fill='#ffd84d')

            # Draw speed limit markers — perpendicular tick marks at each speed limit post on the plan view    速度制限マーカーを描画 — 平面図上の各速度制限標識に垂直な目盛り線を表示する   绘制速度限制标记 — 在平面视图上的每个速度限制标识处绘制垂直标记线
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

            # Draw curve radius labels at the midpoint of each curve section    各曲線区間の中点に曲線半径ラベルを描画する   在每个曲线区间的中点绘制曲线半径标签
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

    # Renders the profile (elevation) view and the radius (curvature) view — draws own track profile, other tracks, stations, gradient markers, and curve radius graph    プロファイル（標高）ビューと半径（曲率）ビューを描画 — 自軌道プロファイル、他軌道、駅、勾配マーカー、曲線半径グラフを描画する   渲染剖面（高程）视图和半径（曲率）视图 — 绘制自身轨道剖面、其他轨道、车站、坡度标记和曲线半径图
    def draw_profileplot(self):
        data = self.mplot.profile_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked() if self.prof_othert_val.get() else None,
            ylim=self.profYlim)

        def render(view):
            # Draw own track profile line (distance vs elevation)    自軌道プロファイル線（距離対標高）を描画する   绘制自身轨道剖面线（距离-高程）
            if len(data['owntrack']) > 0:
                view.line(data['owntrack'][:, [0, 3]], width=2)
            # Draw other track profiles using parallel threads    他軌道プロファイルを並列スレッドで描画する   使用并行线程绘制其他轨道剖面
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

            # Draw station positions as vertical lines with labels and mileage on the profile canvas    プロファイルキャンバスに駅位置を垂直線とラベル・キロ程で描画する   在剖面画布上以垂直线、标签和里程绘制车站位置
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
            # Draw gradient change points as vertical lines and gradient value labels on the profile canvas    プロファイルキャンバスに勾配変化点を垂直線と勾配値ラベルで描画する   在剖面画布上以垂直线和坡度值标签绘制坡度变化点
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

        # Render the radius (curvature) graph — draw curve radius vs distance with labels, plus station markers    半径（曲率）グラフを描画 — 距離に対する曲線半径をラベルと駅マーカー付きで描画する   渲染半径（曲率）图 — 绘制曲线半径-距离图及标签，外加车站标记
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

    # Prints debug data to console — outputs own track, control points, station list, and other track data; only active in non-optimized mode    デバッグデータをコンソールに出力 — 自軌道、制御点、駅リスト、他軌道データを出力；非最適化モードでのみ有効   将调试数据打印到控制台 — 输出自身轨道、控制点、车站列表和其他轨道数据；仅在非优化模式下有效
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

    # Sets the distance range to "all" (the full map extent) and triggers a redraw    距離範囲を「全範囲」（マップ全体）に設定して再描画を実行する   将距离范围设置为“全部”（完整地图范围）并触发重绘
    def setdist_all(self):
        if self.result != None:
            self.dist_range_sel.set('all')
            self.dmin = self.distrange_min
            self.dmax = self.distrange_max
            self.plot_all()

    # Placeholder for setting an arbitrary distance range (currently falls back to setdist_all)    任意の距離範囲を設定するためのプレースホルダ（現在はsetdist_allにフォールバック）   设置任意距离范围的占位符（目前回退到setdist_all）
    def setdist_arbitrary(self):
        if self.result != None:
            self.setdist_all()

    # Formats a mileage value using the i18n mileage format string    i18nのキロ程書式文字列を使用してキロ程値をフォーマットする   使用i18n里程格式字符串格式化里程值
    def format_mileage(self, value):
        return i18n.get('mileage.format').format(value)

    # Captures the current view state (center, zoom, rotation) of all three canvases for later restoration    後で復元するために、3つのキャンバスすべての現在のビュー状態（中心、ズーム、回転）をキャプチャする   捕获所有三个画布的当前视图状态（中心、缩放、旋转）以便后续恢复
    def get_view_state(self):
        return {
            'plane': self.plane_canvas.get_view_state(),
            'profile': self.profile_canvas.get_view_state(),
            'radius': self.radius_canvas.get_view_state(),
        }

    # Restores a previously captured view state to all three canvases    以前にキャプチャしたビュー状態を3つのキャンバスすべてに復元する   将之前捕获的视图状态恢复到所有三个画布
    def set_view_state(self, state):
        self.plane_canvas.set_view_state(state['plane'])
        self.profile_canvas.set_view_state(state['profile'])
        self.radius_canvas.set_view_state(state['radius'])

    # Triggers a full redraw of all canvases — clears measure markers, sets fonts, and calls both plan and profile renderers    全キャンバスの完全再描画を実行 — 計測マーカーをクリアし、フォントを設定し、平面とプロファイルのレンダラを呼び出す   触发所有画布的完全重绘 — 清除测量标记，设置字体，调用平面和剖面渲染器
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

    # Quit confirmation dialog — asks the user whether to exit, then quits the application    終了確認ダイアログ — ユーザーに終了するか確認し、アプリケーションを終了する   退出确认对话框 — 询问用户是否退出，然后退出应用程序
    def ask_quit(self, event=None, ask=True):
        if ask:
            if tk.messagebox.askyesno(message=i18n.get('dialog.quit')):
                self.quit()
        else:
            self.quit()

    # Jumps to a station selected from the combobox — centers all canvases on the station's position    コンボボックスで選択された駅にジャンプ — すべてのキャンバスを駅の位置にセンタリングする   跳转到下拉框中选择的车站 — 将所有画布居中到车站位置
    def jumptostation(self, event=None):
        value = self.stationlist_cb.get()
        key = value.split(',')[0]
        dist = [k for k, v in self.result.station.position.items() if v == key]
        if len(dist)>0:
            self.focus_station(dist[0])
        else:
            tk.messagebox.showinfo(message=i18n.get('dialog.station_not_found', value=value))

    # Centers all canvases on a specific distance — finds the station's plan coordinates and re-centers plane, profile, and radius views    特定の距離にすべてのキャンバスをセンタリング — 駅の平面座標を見つけて、平面・プロファイル・半径ビューを再センタリングする   将所有画布居中到特定距离 — 查找车站的平面坐标并重新居中平面、剖面和半径视图
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

    # Saves all three canvases as PostScript (.ps) files    3つのキャンバスすべてをPostScript（.ps）ファイルとして保存する   将所有三个画布保存为PostScript（.ps）文件
    def save_plots(self, event=None):
        filepath = filedialog.asksaveasfilename(filetypes=[(i18n.get('filetype.ps'),'*.ps'), (i18n.get('filetype.any'),'*')], defaultextension='.ps')
        if filepath != '':
            filepath = pathlib.Path(filepath)
            self.plane_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_plan.ps')), colormode='color')
            self.profile_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_profile.ps')), colormode='color')
            self.radius_canvas.canvas.postscript(file=str(filepath.parent.joinpath(filepath.stem + '_radius.ps')), colormode='color')

    # Exports own track and other track position data as CSV files    自軌道および他軌道の位置データをCSVファイルとしてエクスポートする   将自身轨道和其他轨道的位置数据导出为CSV文件
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

    # Opens a dialog to set the plot range (min/max distance) for the track view    線路ビューのプロット範囲（最小/最大距離）を設定するダイアログを開く   打开对话框设置轨道视图的绘图范围（最小/最大距离）
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

    # Opens a dialog to set control point distribution parameters (min, max, interval) and reloads the map    制御点分布パラメータ（最小、最大、間隔）を設定するダイアログを開き、マップを再読み込みする   打开对话框设置控制点分布参数（最小值、最大值、间距）并重新加载地图
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

    # Shows the About dialog with version and project information    バージョン情報とプロジェクト情報を含む「このアプリについて」ダイアログを表示する   显示包含版本和项目信息的“关于”对话框
    def aboutwindow(self, event=None):
        msg = i18n.get('about.text', version=__version__)
        tk.messagebox.showinfo(message=msg)

    # Imports a background image — opens a file dialog, loads the image, creates a thumbnail, initializes placement parameters    背景画像をインポート — ファイルダイアログを開き、画像を読み込み、サムネイルを作成し、配置パラメータを初期化する   导入背景图像 — 打开文件对话框，加载图像，创建缩略图，初始化放置参数
    def import_bgimg(self):
        filepath = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if not filepath:
            return
        try:
            self.bg_image_original = Image.open(filepath)
        except Exception as e:
            tk.messagebox.showerror(message=i18n.get('dialog.bgimg_load_error', error=str(e)))
            return

        thumb_max = 1024
        ow, oh = self.bg_image_original.size
        if max(ow, oh) > thumb_max:
            ratio = thumb_max / max(ow, oh)
            self.bg_image_thumbnail = self.bg_image_original.resize(
                (int(ow * ratio), int(oh * ratio)),
                Image.LANCZOS)
        else:
            self.bg_image_thumbnail = self.bg_image_original.copy()

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
        self.bgimg_show_chk.config(state=tk.NORMAL)
        if hasattr(self, 'plane_canvas'):
            self.plane_canvas.redraw()

    # Opens a dialog to adjust the background image parameters — position (x, y), size (width, height), and rotation    背景画像のパラメータを調整するダイアログを開く — 位置（x, y）、サイズ（幅、高さ）、回転   打开对话框调整背景图像参数 — 位置（x, y）、大小（宽度、高度）、旋转
    def adjust_bgimg(self):
        if self.bg_image_original is None:
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(i18n.get('dialog.adjust_bgimg'))
        dialog.transient(self.master)

        frame = ttk.Frame(dialog, padding='10 10 10 10')
        frame.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        var_x = tk.DoubleVar(value=self.bg_image_params['x'])
        var_y = tk.DoubleVar(value=self.bg_image_params['y'])
        var_width = tk.DoubleVar(value=self.bg_image_params['width'])
        var_height = tk.DoubleVar(value=self.bg_image_params['height'])
        var_rotation = tk.DoubleVar(value=self.bg_image_params['rotation'])

        fields = [
            (i18n.get('label.bgimg_x'), var_x),
            (i18n.get('label.bgimg_y'), var_y),
            (i18n.get('label.bgimg_width'), var_width),
            (i18n.get('label.bgimg_height'), var_height),
            (i18n.get('label.bgimg_rotation'), var_rotation),
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
                tk.messagebox.showerror(message=i18n.get('dialog.invalid_number'), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(column=0, row=len(fields), columnspan=2, pady=(10, 0))

        ttk.Button(btn_frame, text=i18n.get('button.ok'), command=on_ok).grid(column=0, row=0, padx=(0, 8))
        ttk.Button(btn_frame, text=i18n.get('button.cancel'), command=dialog.destroy).grid(column=1, row=0)

        ttk.Separator(frame, orient='horizontal').grid(column=0, row=len(fields)+1, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        ttk.Button(frame, text=i18n.get('button.align_to_station'), command=lambda: self._align_to_station_dialog(dialog)).grid(column=0, row=len(fields)+2, columnspan=2, pady=(8, 0))

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        var_x_entry = frame.grid_slaves(row=0, column=1)[0]
        var_x_entry.focus_set()
        dialog.wait_window()

    # Retrieves the world coordinates (x, y) of a station given its combo box value (e.g., "key, name")    コンボボックスの値（例："キー, 名前"）から駅のワールド座標（x, y）を取得する   根据下拉框值（例如 "key, name"）获取车站的世界坐标（x, y）
    def _get_station_world_coords(self, station_value):
        key = station_value.split(',')[0]
        distances = [k for k, v in self.result.station.position.items() if v == key]
        if not distances:
            return None
        dist = distances[0]
        own = self.result.owntrack_pos
        idx = np.searchsorted(own[:, 0], dist)
        if idx >= len(own):
            idx = len(own) - 1
        return (float(own[idx][1]), float(own[idx][2]))

    # Starts the interactive pick mode on the plane canvas for background image alignment — user double-clicks to pick a reference point    背景画像の位置合わせのため、平面キャンバス上でインタラクティブなピックモードを開始 — ユーザーがダブルクリックで参照点を選択する   在平面画布上启动背景图像对齐的交互式拾取模式 — 用户双击选择参考点
    def _start_align_pick(self, slot, dialog, btn1, btn2):
        self._align_pick_slot = slot
        self._align_dialog = dialog
        self._align_pick_btn1 = btn1
        self._align_pick_btn2 = btn2
        self._align_pick_active = True

        dialog.withdraw()

        self.plane_canvas.set_cursor('crosshair')
        self.plane_canvas.canvas.bind('<Double-Button-1>', lambda e: self._on_align_canvas_dblclick(e))

    # Handles double-click on the plane canvas during alignment pick mode — captures the world coordinate and updates the corresponding pick button    位置合わせピックモード中に平面キャンバスでダブルクリックされた場合の処理 — ワールド座標をキャプチャし、対応するピックボタンを更新する   在对齐拾取模式下处理平面画布上的双击 — 捕获世界坐标并更新相应的拾取按钮
    def _on_align_canvas_dblclick(self, event):
        wx, wy = self.plane_canvas.screen_to_world(event.x, event.y)

        self._cleanup_align_pick()

        slot = self._align_pick_slot
        if slot == 1:
            self._align_pick1 = (wx, wy)
            self._align_pick_btn1.config(text=i18n.get('button.pick_on_bg_ok'))
        else:
            self._align_pick2 = (wx, wy)
            self._align_pick_btn2.config(text=i18n.get('button.pick_on_bg_ok'))

        self._align_dialog.deiconify()
        self._align_dialog.lift()

    # Cleans up the alignment pick mode — restores default canvas behavior and cursor    位置合わせピックモードをクリーンアップ — デフォルトのキャンバス動作とカーソルを復元する   清理对齐拾取模式 — 恢复默认画布行为和光标
    def _cleanup_align_pick(self):
        if hasattr(self, '_align_pick_active') and self._align_pick_active:
            self._align_pick_active = False
            self.plane_canvas.canvas.bind('<Double-Button-1>', self.plane_canvas.fit)
        self.plane_canvas.set_cursor('')

    # Opens a dialog to align the background image to two known stations — user selects two stations and picks corresponding points on the background    背景画像を2つの既知の駅に合わせるダイアログを開く — ユーザーが2つの駅を選択し、背景上の対応点をピックする   打开对话框将背景图像与两个已知车站对齐 — 用户选择两个车站并在背景上拾取对应点
    def _align_to_station_dialog(self, parent_dialog):
        if self.result is None or not hasattr(self.result, 'station') or len(self.result.station.position) == 0:
            tk.messagebox.showinfo(message=i18n.get('dialog.no_station_data'), parent=parent_dialog)
            return

        dialog = tk.Toplevel(self.master)
        dialog.title(i18n.get('dialog.align_to_station'))
        dialog.transient(parent_dialog)

        stnlist = []
        for stnkey in self.result.station.stationkey.keys():
            stnlist.append(stnkey + ', ' + self.result.station.stationkey[stnkey])

        main_frame = ttk.Frame(dialog, padding='10 10 10 10')
        main_frame.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        left_frame = ttk.LabelFrame(main_frame, text=i18n.get('frame.station1'), padding='8 8 8 8')
        left_frame.grid(column=0, row=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(0, 5))

        ttk.Label(left_frame, text=i18n.get('label.select_station')).grid(column=0, row=0, sticky=tk.W, pady=(0, 4))
        stn1_cb = ttk.Combobox(left_frame, values=stnlist, state='readonly', width=22)
        stn1_cb.grid(column=0, row=1, sticky=(tk.W, tk.E), pady=(0, 8))
        if stnlist:
            stn1_cb.set(stnlist[0])

        pick1_btn = ttk.Button(left_frame, text=i18n.get('button.pick_on_bg'), command=lambda: self._start_align_pick(1, dialog, pick1_btn, pick2_btn))
        pick1_btn.grid(column=0, row=2, sticky=(tk.W, tk.E))

        right_frame = ttk.LabelFrame(main_frame, text=i18n.get('frame.station2'), padding='8 8 8 8')
        right_frame.grid(column=1, row=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=(5, 0))

        ttk.Label(right_frame, text=i18n.get('label.select_station')).grid(column=0, row=0, sticky=tk.W, pady=(0, 4))
        stn2_cb = ttk.Combobox(right_frame, values=stnlist, state='readonly', width=22)
        stn2_cb.grid(column=0, row=1, sticky=(tk.W, tk.E), pady=(0, 8))
        if len(stnlist) > 1:
            stn2_cb.set(stnlist[1])
        elif stnlist:
            stn2_cb.set(stnlist[0])

        pick2_btn = ttk.Button(right_frame, text=i18n.get('button.pick_on_bg'), command=lambda: self._start_align_pick(2, dialog, pick1_btn, pick2_btn))
        pick2_btn.grid(column=0, row=2, sticky=(tk.W, tk.E))

        self._align_pick1 = None
        self._align_pick2 = None

        def on_apply():
            self._compute_and_apply_alignment(stn1_cb.get(), stn2_cb.get(), dialog, close_parent=False)

        def on_ok():
            if self._compute_and_apply_alignment(stn1_cb.get(), stn2_cb.get(), dialog, close_parent=True):
                dialog.destroy()
                parent_dialog.destroy()

        def on_cancel():
            self._cleanup_align_pick()
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(column=0, row=1, columnspan=2, pady=(12, 0))

        ttk.Button(btn_frame, text=i18n.get('button.apply'), command=on_apply).grid(column=0, row=0, padx=(0, 6))
        ttk.Button(btn_frame, text=i18n.get('button.ok'), command=on_ok).grid(column=1, row=0, padx=(0, 6))
        ttk.Button(btn_frame, text=i18n.get('button.cancel'), command=on_cancel).grid(column=2, row=0)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        dialog.protocol('WM_DELETE_WINDOW', on_cancel)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        dialog.wait_window()

    # Computes the background image alignment transformation — using two station reference points and their corresponding picks, calculates scale, rotation, and offset    背景画像の位置合わせ変換を計算 — 2つの駅参照点とそれに対応するピック点を使用して、スケール、回転、オフセットを計算する   计算背景图像对齐变换 — 使用两个车站参考点及其对应的拾取点，计算缩放、旋转和偏移
    def _compute_and_apply_alignment(self, stn1_val, stn2_val, dialog, close_parent):
        if self._align_pick1 is None or self._align_pick2 is None:
            tk.messagebox.showinfo(message=i18n.get('dialog.pick_points_needed'), parent=dialog)
            return False

        s1 = self._get_station_world_coords(stn1_val)
        s2 = self._get_station_world_coords(stn2_val)

        if s1 is None or s2 is None:
            tk.messagebox.showinfo(message=i18n.get('dialog.station_coord_error'), parent=dialog)
            return False

        p1 = self._align_pick1
        p2 = self._align_pick2

        dsx = s2[0] - s1[0]
        dsy = s2[1] - s1[1]
        dpx = p2[0] - p1[0]
        dpy = p2[1] - p1[1]

        ds_dist = math.sqrt(dsx * dsx + dsy * dsy)
        dp_dist = math.sqrt(dpx * dpx + dpy * dpy)

        if ds_dist < 1e-6 or dp_dist < 1e-6:
            tk.messagebox.showinfo(message=i18n.get('dialog.distance_too_short'), parent=dialog)
            return False

        brot_rad = math.radians(self.bg_image_params['rotation'])
        bx = self.bg_image_params['x']
        by = self.bg_image_params['y']

        dp1x = p1[0] - bx
        dp1y = p1[1] - by
        u1 = dp1x * math.cos(brot_rad) + dp1y * math.sin(brot_rad)
        v1 = -dp1x * math.sin(brot_rad) + dp1y * math.cos(brot_rad)

        dp2x = p2[0] - bx
        dp2y = p2[1] - by
        u2 = dp2x * math.cos(brot_rad) + dp2y * math.sin(brot_rad)
        v2 = -dp2x * math.sin(brot_rad) + dp2y * math.cos(brot_rad)

        du = u2 - u1
        dv = v2 - v1
        duv_dist = math.sqrt(du * du + dv * dv)

        if duv_dist < 1e-6:
            tk.messagebox.showinfo(message=i18n.get('dialog.pick_points_coincident'), parent=dialog)
            return False

        scale_factor = ds_dist / duv_dist

        angle_duv = math.atan2(dv, du)
        angle_ds = math.atan2(dsy, dsx)
        new_brot_rad = angle_ds - angle_duv
        new_brot_deg = math.degrees(new_brot_rad) % 360.0

        cos_brot = math.cos(new_brot_rad)
        sin_brot = math.sin(new_brot_rad)
        sx_u1 = scale_factor * (u1 * cos_brot - v1 * sin_brot)
        sy_u1 = scale_factor * (u1 * sin_brot + v1 * cos_brot)
        new_bx = s1[0] - sx_u1
        new_by = s1[1] - sy_u1

        self.bg_image_params['x'] = new_bx
        self.bg_image_params['y'] = new_by
        self.bg_image_params['width'] = self.bg_image_params['width'] * scale_factor
        self.bg_image_params['height'] = self.bg_image_params['height'] * scale_factor
        self.bg_image_params['rotation'] = new_brot_deg

        if hasattr(self, 'plane_canvas'):
            self.plane_canvas.redraw()

        return True

    # Test method for the custom multi-field dialog — opens a sample dialog and prints the result    カスタム複数項目ダイアログのテストメソッド — サンプルダイアログを開いて結果を表示する   自定义多字段对话框的测试方法 — 打开示例对话框并输出结果
    def customdialog_test(self, event=None):
        dialog_obj = dialog_multifields.dialog_multifields(self,\
                                        [{'name':'A', 'type':'str', 'label':'test A', 'default':'alpha'},\
                                        {'name':'B', 'type':'Double', 'label':'test B', 'default':100}],\
                                        'Test Dialog')
        print('Done', dialog_obj.result, dialog_obj.variables['A'].get())

    # Opens the project's GitHub documentation page in the default web browser    プロジェクトのGitHubドキュメントページをデフォルトのWebブラウザで開く   在默认浏览器中打开项目的GitHub文档页面
    def open_webdocument(self, event=None):
        webbrowser.open('https://github.com/NewSapporoNingyo/kobushi-trackviewer-modified')

# Application entry point — parses command-line arguments, sets up the tkinter exception handler, creates the main window, and optionally opens a map file
#アプリケーションのエントリポイント — コマンドライン引数を解析し、tkinterの例外ハンドラを設定し、メインウィンドウを作成し、マップファイルを開く
#应用程序入口 — 解析命令行参数，设置tkinter异常处理器，创建主窗口，并可选择打开地图文件
#if __name__ == '__main__':
def main():
    # In debug mode, install a custom exception hook that launches the pdb debugger on unhandled exceptions    デバッグモードの場合、未処理の例外でpdbデバッガを起動するカスタム例外フックをインストール // 参考: https://gist.github.com/podhmo/5964702e7471ccaba969105468291efa   在调试模式下安装自定义异常钩子，在未处理异常时启动pdb调试器 // 参考: https://gist.github.com/podhmo/5964702e7471ccaba969105468291efa
    if not __debug__:
        def info(type, value, tb):
            if hasattr(sys, "ps1") or not sys.stderr.isatty():
                # In interactive mode or without a tty, use the default exception hook    対話モードまたはttyがない場合はデフォルトの例外フックを使用   在交互模式或无tty时使用默认异常钩子
                sys.__excepthook__(type, value, tb)
            else:
                import traceback, pdb

                # Print the exception traceback and start the debugger in post-mortem mode    例外のトレースバックを表示し、post-mortemモードでデバッガを起動   打印异常回溯并在事后分析模式下启动调试器
                traceback.print_exception(type, value, tb)
                pdb.pm()
        sys.excepthook = info
        print('Debug mode')

    # Parse command-line arguments for file path, track calculation interval, and font    ファイルパス、線路計算間隔、フォントのコマンドライン引数を解析する   解析命令行参数以获取文件路径、轨道计算间隔和字体
    argparser = argparse.ArgumentParser()
    argparser.add_argument('filepath', metavar='F', type=str, help='input mapfile', nargs='?')
    argparser.add_argument('-s', '--step', help='distance interval for track calculation', type=float, default=25)
    argparser.add_argument('-f', '--font', help='Font', type=str, default = 'sans-serif')
    args = argparser.parse_args()
       
    # Install the Catcher wrapper for tkinter callbacks, create the root window and the main application instance    tkinterコールバック用のCatcherラッパーをインストールし、ルートウィンドウとメインアプリケーションインスタンスを作成する   安装tkinter回调的Catcher包装器，创建根窗口和主应用程序实例
    tk.CallWrapper = Catcher
    root = tk.Tk()
    app = mainwindow(master=root, parser = None, stepdist = args.step, font=args.font)

    if args.filepath is not None:
        app.open_mapfile(inputdir=args.filepath)
    app.mainloop()