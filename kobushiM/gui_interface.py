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

import argparse
import math
import os
import pathlib
import queue
import sys
import time
import traceback
import webbrowser

import numpy as np
from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ._version import __version__
from . import canvasplot
from . import dialog_multifields
from . import font_window
from . import i18n
from . import mapinterpreter as interp
from . import mapplot
from . import othertrack_window


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


class mainwindow(QtWidgets.QMainWindow):
    def __init__(self, master=None, parser=None, stepdist=25, font=''):
        super().__init__(master)
        self.dmin = None
        self.dmax = None
        self.result = None
        self.mplot = None
        self.profYlim = None
        self.default_track_interval = stepdist
        self.dist_range_sel = 'all'
        self.dist_range_arb_val = 500
        self._measure_marker_ids = {}
        self.measure_pos = None
        self.parser = parser
        self._closing_without_prompt = False

        self.fontctrl = font_window.FontControl(None, self)
        if font != '':
            self.fontctrl.set_fontname(font)

        self._log_queue = queue.Queue()
        self._log_errors = []
        self._log_warnings = []
        self._log_windows = []
        sys.stdout = LogInterceptor(sys.stdout, 'stdout', self._log_queue)
        sys.stderr = LogInterceptor(sys.stderr, 'stderr', self._log_queue)

        self.bg_image_original = None
        self.bg_image_array = None
        self.bg_image_params = {
            'x': 0.0,
            'y': 0.0,
            'width': 5000.0,
            'height': 5000.0,
            'rotation': 0.0,
        }

        self.setWindowTitle('Kobushi trackviewer ver. {:s}'.format(__version__))
        self.resize(1280, 820)
        self.create_widgets()
        self.create_menubar()
        self.bind_keyevent()
        self.subwindow = othertrack_window.SubWindow(None, self)

        self.log_timer = QtCore.QTimer(self)
        self.log_timer.timeout.connect(self.check_log_queue)
        self.log_timer.start(100)

        i18n.on_language_change(self.refresh_ui_text)
        self.refresh_ui_text()

    def _group(self, title):
        group = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        return group, layout

    def _checkbox(self, parent_layout, text, checked, callback):
        checkbox = QtWidgets.QCheckBox(text)
        checkbox.setChecked(checked)
        parent_layout.addWidget(checkbox)
        checkbox.stateChanged.connect(lambda _state: callback())
        return checkbox

    def refresh_ui_text(self):
        self.setWindowTitle(i18n.get('app.title', version=__version__))
        if hasattr(self, 'open_btn'):
            self.open_btn.setText(i18n.get('button.open'))
        if hasattr(self, 'aux_values_control'):
            self.aux_values_control.setTitle(i18n.get('frame.aux_info'))
        if hasattr(self, 'stationpos_chk'):
            self.stationpos_chk.setText(i18n.get('chk.station_pos'))
        if hasattr(self, 'stationlabel_chk'):
            self.stationlabel_chk.setText(i18n.get('chk.station_name'))
        if hasattr(self, 'stationmileage_chk'):
            self.stationmileage_chk.setText(i18n.get('chk.station_mileage'))
        if hasattr(self, 'gradientpos_chk'):
            self.gradientpos_chk.setText(i18n.get('chk.gradient_pos'))
        if hasattr(self, 'gradientval_chk'):
            self.gradientval_chk.setText(i18n.get('chk.gradient_val'))
        if hasattr(self, 'curveval_chk'):
            self.curveval_chk.setText(i18n.get('chk.curve_val'))
        if hasattr(self, 'prof_othert_chk'):
            self.prof_othert_chk.setText(i18n.get('chk.prof_othert'))
        if hasattr(self, 'speedlimit_chk'):
            self.speedlimit_chk.setText(i18n.get('chk.speedlimit'))
        if hasattr(self, 'graph_control'):
            self.graph_control.setTitle(i18n.get('frame.chart_visibility'))
        if hasattr(self, 'show_gradient_graph_chk'):
            self.show_gradient_graph_chk.setText(i18n.get('chk.gradient_graph'))
        if hasattr(self, 'show_curve_graph_chk'):
            self.show_curve_graph_chk.setText(i18n.get('chk.curve_graph'))
        if hasattr(self, 'grid_control'):
            self.grid_control.setTitle(i18n.get('frame.grid'))
        if hasattr(self, 'grid_fixed_rb'):
            self.grid_fixed_rb.setText(i18n.get('grid.fixed'))
        if hasattr(self, 'grid_movable_rb'):
            self.grid_movable_rb.setText(i18n.get('grid.movable'))
        if hasattr(self, 'grid_none_rb'):
            self.grid_none_rb.setText(i18n.get('grid.none'))
        if hasattr(self, 'mode_control'):
            self.mode_control.setTitle(i18n.get('frame.mode'))
        if hasattr(self, 'mode_pan_rb'):
            self.mode_pan_rb.setText(i18n.get('mode.pan'))
        if hasattr(self, 'mode_measure_rb'):
            self.mode_measure_rb.setText(i18n.get('mode.measure'))
        if hasattr(self, 'stationlist_label'):
            self.stationlist_label.setText(i18n.get('label.station_jump'))
        if hasattr(self, 'menu_file'):
            self.menu_file.setTitle(i18n.get('menu.file'))
            self.menu_option.setTitle(i18n.get('menu.options'))
            self.menu_lang.setTitle(i18n.get('menu.lang'))
            self.menu_help.setTitle(i18n.get('menu.help'))
            self.action_open.setText(i18n.get('menu.open'))
            self.action_reload.setText(i18n.get('menu.reload'))
            self.action_save_image.setText(i18n.get('menu.save_image'))
            self.action_save_trackdata.setText(i18n.get('menu.save_trackdata'))
            self.action_exit.setText(i18n.get('menu.exit'))
            self.action_controlpoints.setText(i18n.get('menu.controlpoints'))
            self.action_plotlimit.setText(i18n.get('menu.plotlimit'))
            self.action_font.setText(i18n.get('menu.font'))
            self.action_help_ref.setText(i18n.get('menu.help_ref'))
            self.action_about.setText(i18n.get('menu.about'))
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
        if hasattr(self, 'bgimg_control'):
            self.bgimg_control.setTitle(i18n.get('frame.bgimage'))
        if hasattr(self, 'bgimg_import_btn'):
            self.bgimg_import_btn.setText(i18n.get('button.import_bg'))
        if hasattr(self, 'bgimg_adjust_btn'):
            self.bgimg_adjust_btn.setText(i18n.get('button.adjust_bg'))
        if hasattr(self, 'bgimg_show_chk'):
            self.bgimg_show_chk.setText(i18n.get('chk.bgimg_show'))
        if self.result is not None:
            self.plot_all()

    def create_widgets(self):
        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(3, 3, 3, 3)
        self.setCentralWidget(central)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        central_layout.addWidget(self.main_splitter)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)

        self.file_frame = QtWidgets.QWidget()
        file_layout = QtWidgets.QHBoxLayout(self.file_frame)
        file_layout.setContentsMargins(3, 3, 3, 3)
        self.open_btn = QtWidgets.QPushButton(i18n.get('button.open'))
        self.open_btn.clicked.connect(self.open_mapfile)
        file_layout.addWidget(self.open_btn)
        self.filedir_entry = QtWidgets.QLineEdit()
        file_layout.addWidget(self.filedir_entry, 1)
        self._log_err_btn = QtWidgets.QPushButton('ERR 0')
        self._log_err_btn.setMaximumWidth(70)
        self._log_err_btn.clicked.connect(self._show_error_details)
        file_layout.addWidget(self._log_err_btn)
        self._log_warn_btn = QtWidgets.QPushButton('WARN 0')
        self._log_warn_btn.setMaximumWidth(80)
        self._log_warn_btn.clicked.connect(self._show_warning_details)
        file_layout.addWidget(self._log_warn_btn)
        self._log_last_label = QtWidgets.QLabel('')
        self._log_last_label.setFrameShape(QtWidgets.QFrame.Shape.Panel)
        self._log_last_label.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self._log_last_label.setMinimumWidth(280)
        file_layout.addWidget(self._log_last_label, 1)
        left_layout.addWidget(self.file_frame)

        self.plot_pane = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plane_canvas = canvasplot.PlotCanvas(
            self.plot_pane,
            title=i18n.get('canvas.plan'),
            rotate_enabled=True,
            y_axis_down=True,
            scalebar=True,
        )
        self.profile_pane = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.profile_canvas = canvasplot.PlotCanvas(
            self.profile_pane,
            title=i18n.get('canvas.profile'),
            rotate_enabled=False,
            world_grid=True,
            x_unit=i18n.get('unit.m'),
            y_unit=i18n.get('unit.m'),
            independent_scale=True,
            zoom_x_by_default=True,
        )
        self.radius_canvas = canvasplot.PlotCanvas(
            self.profile_pane,
            title=i18n.get('canvas.radius'),
            rotate_enabled=False,
            world_grid=True,
            x_unit=i18n.get('unit.m'),
            independent_scale=True,
            lock_y_center=True,
            zoom_x_by_default=True,
            enable_lod=False,
        )
        self.profile_pane.addWidget(self.profile_canvas)
        self.profile_pane.addWidget(self.radius_canvas)
        self.profile_pane.setStretchFactor(0, 1)
        self.profile_pane.setStretchFactor(1, 1)
        self.plot_pane.addWidget(self.plane_canvas)
        self.plot_pane.addWidget(self.profile_pane)
        self.plot_pane.setStretchFactor(0, 20)
        self.plot_pane.setStretchFactor(1, 3)
        left_layout.addWidget(self.plot_pane, 1)

        self.setdist_frame = QtWidgets.QWidget()
        setdist_layout = QtWidgets.QHBoxLayout(self.setdist_frame)
        setdist_layout.setContentsMargins(3, 3, 3, 3)
        self.measure_info_label = QtWidgets.QLabel('')
        setdist_layout.addWidget(self.measure_info_label, 1)
        self.stationlist_label = QtWidgets.QLabel(i18n.get('label.station_jump'))
        setdist_layout.addWidget(self.stationlist_label)
        self.stationlist_cb = QtWidgets.QComboBox()
        self.stationlist_cb.setMinimumWidth(180)
        self.stationlist_cb.activated.connect(self.jumptostation)
        setdist_layout.addWidget(self.stationlist_cb)
        left_layout.addWidget(self.setdist_frame)

        control_widget = QtWidgets.QWidget()
        control_layout = QtWidgets.QVBoxLayout(control_widget)
        control_layout.setContentsMargins(6, 6, 6, 6)
        control_layout.setSpacing(6)

        self.mode_control, mode_layout = self._group(i18n.get('frame.mode'))
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_pan_rb = QtWidgets.QRadioButton(i18n.get('mode.pan'))
        self.mode_measure_rb = QtWidgets.QRadioButton(i18n.get('mode.measure'))
        self.mode_pan_rb.setChecked(True)
        self.mode_group.addButton(self.mode_pan_rb)
        self.mode_group.addButton(self.mode_measure_rb)
        mode_layout.addWidget(self.mode_pan_rb)
        mode_layout.addWidget(self.mode_measure_rb)
        self.mode_group.buttonClicked.connect(lambda _button: self.on_mode_change())
        control_layout.addWidget(self.mode_control)

        self.grid_control, grid_layout = self._group(i18n.get('frame.grid'))
        self.grid_group = QtWidgets.QButtonGroup(self)
        self.grid_fixed_rb = QtWidgets.QRadioButton(i18n.get('grid.fixed'))
        self.grid_movable_rb = QtWidgets.QRadioButton(i18n.get('grid.movable'))
        self.grid_none_rb = QtWidgets.QRadioButton(i18n.get('grid.none'))
        self.grid_fixed_rb.setChecked(True)
        for rb in (self.grid_fixed_rb, self.grid_movable_rb, self.grid_none_rb):
            self.grid_group.addButton(rb)
            grid_layout.addWidget(rb)
        self.grid_group.buttonClicked.connect(lambda _button: self.on_grid_mode_change())
        control_layout.addWidget(self.grid_control)

        self.aux_values_control, aux_layout = self._group(i18n.get('frame.aux_info'))
        self.stationpos_chk = self._checkbox(aux_layout, i18n.get('chk.station_pos'), True, self.on_stationpos_toggle)
        self.stationlabel_chk = self._checkbox(aux_layout, i18n.get('chk.station_name'), True, self.plot_all)
        self.stationmileage_chk = self._checkbox(aux_layout, i18n.get('chk.station_mileage'), True, self.plot_all)
        self.curveval_chk = self._checkbox(aux_layout, i18n.get('chk.curve_val'), True, self.plot_all)
        self.speedlimit_chk = self._checkbox(aux_layout, i18n.get('chk.speedlimit'), True, self.plot_all)
        control_layout.addWidget(self.aux_values_control)

        self.graph_control, graph_layout = self._group(i18n.get('frame.chart_visibility'))
        self.show_curve_graph_chk = self._checkbox(graph_layout, i18n.get('chk.curve_graph'), True, self.update_pane_layout)
        self.show_gradient_graph_chk = self._checkbox(graph_layout, i18n.get('chk.gradient_graph'), True, self.update_pane_layout)
        self.gradientpos_chk = self._checkbox(graph_layout, i18n.get('chk.gradient_pos'), True, self.on_gradientpos_toggle)
        self.gradientval_chk = self._checkbox(graph_layout, i18n.get('chk.gradient_val'), True, self.plot_all)
        self.prof_othert_chk = self._checkbox(graph_layout, i18n.get('chk.prof_othert'), False, self.plot_all)
        control_layout.addWidget(self.graph_control)

        self.bgimg_control, bg_layout = self._group(i18n.get('frame.bgimage'))
        self.bgimg_show_chk = self._checkbox(bg_layout, i18n.get('chk.bgimg_show'), True, self.on_bgimg_show_toggle)
        self.bgimg_show_chk.setEnabled(False)
        self.bgimg_import_btn = QtWidgets.QPushButton(i18n.get('button.import_bg'))
        self.bgimg_import_btn.clicked.connect(self.import_bgimg)
        bg_layout.addWidget(self.bgimg_import_btn)
        self.bgimg_adjust_btn = QtWidgets.QPushButton(i18n.get('button.adjust_bg'))
        self.bgimg_adjust_btn.setEnabled(False)
        self.bgimg_adjust_btn.clicked.connect(self.adjust_bgimg)
        bg_layout.addWidget(self.bgimg_adjust_btn)
        control_layout.addWidget(self.bgimg_control)
        control_layout.addStretch(1)

        control_scroll = QtWidgets.QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setWidget(control_widget)
        control_scroll.setMinimumWidth(220)

        self.main_splitter.addWidget(left_widget)
        self.main_splitter.addWidget(control_scroll)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)

    def update_pane_layout(self):
        show_gradient = self.show_gradient_graph_chk.isChecked()
        show_curve = self.show_curve_graph_chk.isChecked()
        self.profile_canvas.setVisible(show_gradient)
        self.radius_canvas.setVisible(show_curve)
        self.profile_pane.setVisible(show_gradient or show_curve)
        QtWidgets.QApplication.processEvents()
        self.plot_all()

    def on_stationpos_toggle(self):
        enabled = self.stationpos_chk.isChecked()
        self.stationlabel_chk.setEnabled(enabled)
        self.stationmileage_chk.setEnabled(enabled)
        self.plot_all()

    def on_gradientpos_toggle(self):
        self.gradientval_chk.setEnabled(self.gradientpos_chk.isChecked())
        self.plot_all()

    def on_bgimg_show_toggle(self):
        self.plot_all()

    def check_log_queue(self):
        try:
            while True:
                source, msg = self._log_queue.get_nowait()
                if source == 'stderr' or 'error' in msg.lower():
                    self._log_errors.append(msg)
                elif 'warning' in msg.lower():
                    self._log_warnings.append(msg)
                self._log_last_label.setText(msg[-100:])
        except queue.Empty:
            pass
        wc = len(self._log_warnings)
        ec = len(self._log_errors)
        self._log_warn_btn.setText('WARN {:d}'.format(wc))
        self._log_err_btn.setText('ERR {:d}'.format(ec))

    def _clear_logs(self):
        self._log_errors.clear()
        self._log_warnings.clear()
        self._log_last_label.setText('')
        self._log_err_btn.setText('ERR 0')
        self._log_warn_btn.setText('WARN 0')

    def _show_error_details(self):
        self._show_log_detail_window('Errors', self._log_errors)

    def _show_warning_details(self):
        self._show_log_detail_window('Warnings', self._log_warnings)

    def _show_log_detail_window(self, title, messages):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(700, 400)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText('\n'.join(messages) if messages else 'No messages')
        layout.addWidget(text)
        self._log_windows.append(dialog)
        dialog.finished.connect(lambda _result, d=dialog: self._log_windows.remove(d) if d in self._log_windows else None)
        dialog.show()

    def on_grid_mode_change(self):
        if self.grid_none_rb.isChecked():
            mode = 'none'
        elif self.grid_movable_rb.isChecked():
            mode = 'movable'
        else:
            mode = 'fixed'
        self.plane_canvas.set_grid_mode(mode)

    def on_mode_change(self):
        measure_mode = self.mode_measure_rb.isChecked()
        for plot_canvas in [self.plane_canvas, self.profile_canvas, self.radius_canvas]:
            plot_canvas.interactive = not measure_mode
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
            self.measure_info_label.setText('')
            self.plot_all(keep_view=True)

    def _clear_measure_marker(self):
        for plot_canvas, ids in list(self._measure_marker_ids.items()):
            for item_id in ids:
                try:
                    plot_canvas.delete(item_id)
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
        ids = [
            c.create_line(sx - 12, sy - 12, sx + 12, sy + 12, fill='#ff3333', width=2),
            c.create_line(sx - 12, sy + 12, sx + 12, sy - 12, fill='#ff3333', width=2),
        ]
        self._measure_marker_ids[c] = ids
        for cv in [self.profile_canvas, self.radius_canvas]:
            sx_v, _ = cv.world_to_screen(distance, 0)
            c2 = cv.canvas
            h = c2.winfo_height()
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
                self.measure_info_label.setText('')

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
                cv.set_center(float(c * x - s * y), float(s * x + c * y))
            else:
                cv.set_center(x=distance)
        self._sync_measure_markers(distance)
        return 'break'

    def update_measure_info(self):
        if self.measure_pos is None or self.mplot is None:
            self.measure_info_label.setText('')
            return
        info = self.mplot.get_track_info_at(self.measure_pos['distance'])
        if info is None:
            self.measure_info_label.setText('')
            return
        speed_text = i18n.get('info.no_limit') if info['speed'] is None else '{:.0f} km/h'.format(info['speed'])
        text = '{m}: {mileage:.0f}m | {e}: {elevation:.1f}m | {g}: {gradient:.1f} | {r}: {radius:.0f}m | {s}: {speed}'.format(
            m=i18n.get('info.mileage'), mileage=info['mileage'],
            e=i18n.get('info.elevation'), elevation=info['elevation'],
            g=i18n.get('info.gradient'), gradient=info['gradient'],
            r=i18n.get('info.radius'), radius=info['radius'],
            s=i18n.get('info.speedlimit'), speed=speed_text)
        self.measure_info_label.setText(text)

    def create_menubar(self):
        menubar = self.menuBar()
        self.menu_file = menubar.addMenu(i18n.get('menu.file'))
        self.menu_option = menubar.addMenu(i18n.get('menu.options'))
        self.menu_lang = menubar.addMenu(i18n.get('menu.lang'))
        self.menu_help = menubar.addMenu(i18n.get('menu.help'))

        self.action_open = QtGui.QAction(i18n.get('menu.open'), self)
        self.action_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.open_mapfile)
        self.menu_file.addAction(self.action_open)

        self.action_reload = QtGui.QAction(i18n.get('menu.reload'), self)
        self.action_reload.setShortcut(QtGui.QKeySequence('F5'))
        self.action_reload.triggered.connect(self.reload_map)
        self.menu_file.addAction(self.action_reload)
        self.menu_file.addSeparator()

        self.action_save_image = QtGui.QAction(i18n.get('menu.save_image'), self)
        self.action_save_image.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.action_save_image.triggered.connect(self.save_plots)
        self.menu_file.addAction(self.action_save_image)

        self.action_save_trackdata = QtGui.QAction(i18n.get('menu.save_trackdata'), self)
        self.action_save_trackdata.triggered.connect(self.save_trackdata)
        self.menu_file.addAction(self.action_save_trackdata)
        self.menu_file.addSeparator()

        self.action_exit = QtGui.QAction(i18n.get('menu.exit'), self)
        self.action_exit.setShortcut(QtGui.QKeySequence('Alt+F4'))
        self.action_exit.triggered.connect(self.ask_quit)
        self.menu_file.addAction(self.action_exit)

        self.action_controlpoints = QtGui.QAction(i18n.get('menu.controlpoints'), self)
        self.action_controlpoints.triggered.connect(self.set_arbcpdist)
        self.menu_option.addAction(self.action_controlpoints)

        self.action_plotlimit = QtGui.QAction(i18n.get('menu.plotlimit'), self)
        self.action_plotlimit.triggered.connect(self.set_plotlimit)
        self.menu_option.addAction(self.action_plotlimit)

        self.action_font = QtGui.QAction(i18n.get('menu.font'), self)
        self.action_font.triggered.connect(self.fontctrl.create_window)
        self.menu_option.addAction(self.action_font)

        for lang_code, lang_name in i18n.SUPPORTED_LANGUAGES.items():
            action = QtGui.QAction(lang_name, self)
            action.triggered.connect(lambda _checked=False, c=lang_code: i18n.set_language(c))
            self.menu_lang.addAction(action)

        self.action_help_ref = QtGui.QAction(i18n.get('menu.help_ref'), self)
        self.action_help_ref.triggered.connect(self.open_webdocument)
        self.menu_help.addAction(self.action_help_ref)

        self.action_about = QtGui.QAction(i18n.get('menu.about'), self)
        self.action_about.triggered.connect(self.aboutwindow)
        self.menu_help.addAction(self.action_about)

    def bind_keyevent(self):
        return None

    def open_mapfile(self, event=None, inputdir=None):
        if inputdir is None:
            inputdir, _ = QtWidgets.QFileDialog.getOpenFileName(self, i18n.get('menu.open'), os.getcwd())
        if inputdir != '':
            self.filedir_entry.setText(inputdir)
            self._clear_logs()
            t_start = time.perf_counter()
            interpreter = interp.ParseMap(None, self.parser)
            self.result = interpreter.load_files(inputdir)

            self.dist_range_sel = 'all'
            if len(self.result.station.position) > 0:
                self.dmin = round(min(self.result.station.position.keys()), -2) - 500
                self.dmax = round(max(self.result.station.position.keys()), -2) + 500
                self.distrange_min = self.dmin
                self.distrange_max = self.dmax
            else:
                self.dmin = round(min(self.result.controlpoints.list_cp), -2) - 500
                self.dmax = round(max(self.result.controlpoints.list_cp), -2) + 500
                self.distrange_min = self.dmin
                self.distrange_max = self.dmax

            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {
                    'current': linecolor_default[color_ix % 10],
                    'default': linecolor_default[color_ix % 10],
                }
                color_ix += 1

            self._set_station_combo_values()
            self.subwindow.set_ottree_value()
            self.profYlim = None
            self.mplot = mapplot.Mapplot(self.result, unitdist_default=self.default_track_interval)
            self.setdist_all()
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            self.print_debugdata()

    def _set_station_combo_values(self):
        stnlist_tmp = []
        for stationkey in self.result.station.stationkey.keys():
            stnlist_tmp.append(stationkey + ', ' + self.result.station.stationkey[stationkey])
        self.stationlist_cb.blockSignals(True)
        self.stationlist_cb.clear()
        self.stationlist_cb.addItems(stnlist_tmp)
        self.stationlist_cb.blockSignals(False)

    def reload_map(self, event=None):
        inputdir = self.filedir_entry.text()
        if inputdir != '':
            tmp_cp_arbdistribution = self.mplot.environment.cp_arbdistribution
            tmp_othertrack_checked = self.subwindow.othertrack_tree.get_checked()
            tmp_othertrack_linecolor = self.result.othertrack_linecolor
            tmp_othertrack_cprange = self.result.othertrack.cp_range

            self._clear_logs()
            t_start = time.perf_counter()
            interpreter = interp.ParseMap(None, self.parser)
            self.result = interpreter.load_files(inputdir)

            if len(self.result.station.position) > 0:
                self.distrange_min = round(min(self.result.station.position.keys()), -2) - 500
                self.distrange_max = round(max(self.result.station.position.keys()), -2) + 500
            else:
                self.distrange_min = round(min(self.result.controlpoints.list_cp), -2) - 500
                self.distrange_max = round(max(self.result.controlpoints.list_cp), -2) + 500

            self.result.othertrack_linecolor = {}
            linecolor_default = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            color_ix = 0
            for key in self.result.othertrack.data.keys():
                self.result.othertrack_linecolor[key] = {
                    'current': linecolor_default[color_ix % 10],
                    'default': linecolor_default[color_ix % 10],
                }
                color_ix += 1

            self.subwindow.set_ottree_value()
            for key in tmp_othertrack_cprange.keys():
                if key in self.result.othertrack.data.keys():
                    self.result.othertrack.cp_range[key] = tmp_othertrack_cprange[key]
                    self.subwindow.othertrack_tree.set(key, '#1', tmp_othertrack_cprange[key]['min'])
                    self.subwindow.othertrack_tree.set(key, '#2', tmp_othertrack_cprange[key]['max'])
                    self.subwindow.othertrack_tree.tag_configure(key, foreground=tmp_othertrack_linecolor[key]['current'])
                    self.result.othertrack_linecolor[key] = tmp_othertrack_linecolor[key]
                    if key in tmp_othertrack_checked:
                        self.subwindow.othertrack_tree._check_ancestor(key)

            self._set_station_combo_values()
            view_state = self.get_view_state()
            self.mplot = mapplot.Mapplot(self.result, cp_arbdistribution=tmp_cp_arbdistribution)
            self.plot_all(keep_view=True)
            self.set_view_state(view_state)
            t_end = time.perf_counter()
            print('Map loaded in {:.2f}s'.format(t_end - t_start))
            self.print_debugdata()

    def draw_planerplot(self):
        data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked(),
        )

        def render(view):
            if self.bgimg_show_chk.isChecked() and self.bg_image_array is not None:
                view.image(
                    self.bg_image_array,
                    self.bg_image_params['x'],
                    self.bg_image_params['y'],
                    self.bg_image_params['width'],
                    self.bg_image_params['height'],
                    self.bg_image_params['rotation'],
                )

            if len(data['owntrack']) > 0:
                if self.curveval_chk.isChecked():
                    for sec in data['curve_sections']:
                        mask = (data['owntrack'][:, 0] >= sec['start']) & (data['owntrack'][:, 0] <= sec['end'])
                        if mask.sum() >= 2:
                            view.line(data['owntrack'][mask][:, 1:3], fill='#888888', width=10)
                    for sec in data['transition_sections']:
                        mask = (data['owntrack'][:, 0] >= sec['start']) & (data['owntrack'][:, 0] <= sec['end'])
                        if mask.sum() >= 2:
                            view.line(data['owntrack'][mask][:, 1:3], fill='#555555', width=8)
                view.line(data['owntrack'][:, 1:3], width=2)

            for track in data['othertracks']:
                if len(track['points']) > 0:
                    view.line(track['points'][:, 1:3], fill=track['color'], width=1)

            if self.stationpos_chk.isChecked():
                for station in data['stations']:
                    x = station['point'][1]
                    y = station['point'][2]
                    view.point(x, y, radius=4)
                    if self.stationlabel_chk.isChecked():
                        view.text(x, y, station['name'], offset=(8, -8), font_size=9)
                    if self.stationmileage_chk.isChecked():
                        view.text(x, y, self.format_mileage(station['mileage']), offset=(8, 8), font_size=8, fill='#ffd84d')

            if self.speedlimit_chk.isChecked():
                for sp in data['speedlimits']:
                    sx, sy = view.world_to_screen(sp['x'], sp['y'])
                    t = sp['theta']
                    wx_perp = sp['x'] - math.sin(t)
                    wy_perp = sp['y'] + math.cos(t)
                    sx_perp, sy_perp = view.world_to_screen(wx_perp, wy_perp)
                    sdx = sx_perp - sx
                    sdy = sy_perp - sy
                    screen_len = math.sqrt(sdx * sdx + sdy * sdy)
                    if screen_len > 0:
                        sdx = sdx / screen_len * 8
                        sdy = sdy / screen_len * 8
                    view.canvas.create_line(sx - sdx, sy - sdy, sx + sdx, sy + sdy, fill='#88ccff', width=1)
                    if sp['speed'] is not None:
                        view.text(sp['x'], sp['y'], str(int(sp['speed'])), offset=(10, -15), font_size=9, fill='#88ccff')
                    else:
                        view.text(sp['x'], sp['y'], 'x', offset=(10, -15), font_size=9, fill='#88ccff')

            if self.curveval_chk.isChecked() and len(data['curve_sections']) > 0:
                for sec in data['curve_sections']:
                    mid_d = (sec['start'] + sec['end']) / 2
                    idx = np.searchsorted(data['owntrack'][:, 0], mid_d)
                    if idx >= len(data['owntrack']):
                        idx = len(data['owntrack']) - 1
                    mx = data['owntrack'][idx][1]
                    my = data['owntrack'][idx][2]
                    view.text(mx, my, str(int(sec['radius'])), offset=(8, -16), font_size=8, fill='#88ff88')

        self.plane_canvas.set_renderer(render, bounds=data['bounds'], keep_view=self.keep_view_on_next_draw)

    def draw_profileplot(self):
        data = self.mplot.profile_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked() if self.prof_othert_chk.isChecked() else None,
            ylim=self.profYlim,
        )

        def render(view):
            if len(data['owntrack']) > 0:
                view.line(data['owntrack'][:, [0, 3]], width=2)
            for track in data['othertracks']:
                if len(track['points']) > 0:
                    view.line(track['points'][:, [0, 3]], fill=track['color'], width=1)

            _, ymin, _, ymax = view._get_visible_world_bounds(margin=0.05)
            if self.stationpos_chk.isChecked():
                for station in data['stations']:
                    x = station['point'][0]
                    z = station['point'][3]
                    view.line(np.array([[x, z], [x, ymax]]), fill='#ffffff', width=1)
                    view.point(x, z, radius=3)
                    if self.stationlabel_chk.isChecked():
                        view.text(x, z, station['name'], offset=(8, -26), font_size=9)
                    if self.stationmileage_chk.isChecked():
                        view.text(x, ymax, self.format_mileage(station['mileage']), offset=(8, 8), font_size=8, fill='#ffd84d')
            if self.gradientpos_chk.isChecked():
                for point in data['gradient_points']:
                    view.line(np.array([[point['x'], point['z']], [point['x'], ymin]]), fill='#ffffff', width=1)
                for label in data['gradient_labels']:
                    if self.gradientval_chk.isChecked():
                        view.text(label['x'], ymin, label['text'], offset=(6, -6), font_size=8, fill='#ffffff', anchor='se')

        if self.show_gradient_graph_chk.isChecked():
            self.profile_canvas.set_renderer(render, bounds=data['bounds'], keep_view=self.keep_view_on_next_draw)

        def render_radius(view):
            if len(data['curve']) > 0:
                view.line(data['curve'], width=2)
            for label in data['radius_labels']:
                view.text(label['x'], label['y'], label['text'], angle=90, offset=(-6, 0), font_size=8)

            _, ymin, _, ymax = view._get_visible_world_bounds(margin=0.05)
            if self.stationpos_chk.isChecked():
                for station in data['stations']:
                    screen_x, _ = view.world_to_screen(station['distance'], 0)
                    if screen_x < 0 or screen_x > view.canvas.winfo_width():
                        continue
                    view.line(np.array([[station['distance'], ymin], [station['distance'], ymax]]), fill='#ffffff', width=1)
                    if self.stationlabel_chk.isChecked():
                        view.text(station['distance'], ymax, station['name'], offset=(8, 8), font_size=9)
                    if self.stationmileage_chk.isChecked():
                        view.text(station['distance'], ymin, self.format_mileage(station['mileage']), offset=(8, -8), font_size=8, fill='#ffd84d', anchor='sw')

        if self.show_curve_graph_chk.isChecked():
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
                print(i, self.result.station.stationkey[self.result.station.position[i]])
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
        if self.result is not None:
            self.dist_range_sel = 'all'
            self.dmin = self.distrange_min
            self.dmax = self.distrange_max
            self.plot_all()

    def setdist_arbitrary(self):
        if self.result is not None:
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
        if self.result is not None:
            self._clear_measure_marker()
            self.keep_view_on_next_draw = keep_view
            self.plane_canvas.set_font(self.fontctrl.get_fontname())
            if self.show_gradient_graph_chk.isChecked() or self.show_curve_graph_chk.isChecked():
                self.profile_canvas.set_font(self.fontctrl.get_fontname())
                self.radius_canvas.set_font(self.fontctrl.get_fontname())
            self.draw_planerplot()
            self.draw_profileplot()
            self.keep_view_on_next_draw = False

    def ask_quit(self, event=None, ask=True):
        if ask:
            self.close()
        else:
            self._closing_without_prompt = True
            QtWidgets.QApplication.quit()

    def closeEvent(self, event):
        if self._closing_without_prompt:
            event.accept()
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            self.windowTitle(),
            i18n.get('dialog.quit'),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            event.accept()
            if hasattr(self, 'subwindow'):
                self.subwindow.close()
        else:
            event.ignore()

    def jumptostation(self, event=None):
        value = self.stationlist_cb.currentText()
        key = value.split(',')[0]
        dist = [k for k, v in self.result.station.position.items() if v == key]
        if len(dist) > 0:
            self.focus_station(dist[0])
        else:
            QtWidgets.QMessageBox.information(self, self.windowTitle(), i18n.get('dialog.station_not_found', value=value))

    def focus_station(self, distance):
        plane_data = self.mplot.plane_data(
            distmin=self.dmin,
            distmax=self.dmax,
            othertrack_list=self.subwindow.othertrack_tree.get_checked(),
        )
        for station in plane_data['stations']:
            if station['distance'] == distance:
                self.plane_canvas.set_center(station['point'][1], station['point'][2])
                break
        self.profile_canvas.set_center(x=distance)
        self.radius_canvas.set_center(x=distance)

    def save_plots(self, event=None):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            i18n.get('menu.save_image'),
            os.getcwd(),
            'PNG (*.png);;{} (*)'.format(i18n.get('filetype.any')),
        )
        if filepath != '':
            filepath = pathlib.Path(filepath)
            self.plane_canvas.export_image(filepath.parent.joinpath(filepath.stem + '_plan.png'))
            self.profile_canvas.export_image(filepath.parent.joinpath(filepath.stem + '_profile.png'))
            self.radius_canvas.export_image(filepath.parent.joinpath(filepath.stem + '_radius.png'))

    def save_trackdata(self, event=None):
        filepath = QtWidgets.QFileDialog.getExistingDirectory(self, i18n.get('menu.save_trackdata'), os.getcwd())
        if filepath != '':
            filepath = pathlib.Path(filepath)
            filename_base = filepath.stem
            output_filename = filepath.joinpath(str(filename_base) + '_owntrack' + '.csv')
            output = self.result.owntrack_pos
            header = 'distance,x,y,z,direction,radius,gradient,interpolate_func,cant,center,gauge'
            np.savetxt(output_filename, output, delimiter=',', header=header, fmt='%.6f')
            for key in self.result.othertrack_pos.keys():
                output_filename = filepath.joinpath(str(filename_base) + '_' + key + '.csv')
                output = self.result.othertrack_pos[key]
                header = 'distance,x,y,z,interpolate_func,cant,center,gauge'
                np.savetxt(output_filename, output, delimiter=',', header=header, fmt='%.6f')

    def set_plotlimit(self, event=None):
        if self.result is not None:
            dialog = dialog_multifields.dialog_multifields(
                self,
                [
                    {'name': 'min', 'type': 'Double', 'label': i18n.get('dialog.plotlimit_min', value=str(self.result.cp_defaultrange[0])), 'default': self.distrange_min},
                    {'name': 'max', 'type': 'Double', 'label': i18n.get('dialog.plotlimit_max', value=str(self.result.cp_defaultrange[1])), 'default': self.distrange_max},
                ],
                message=i18n.get('dialog.set_plotlimit', min=str(min(self.result.controlpoints.list_cp)), max=str(max(self.result.controlpoints.list_cp))),
            )
            if dialog.result == 'OK':
                self.distrange_min = float(dialog.variables['min'].get())
                self.distrange_max = float(dialog.variables['max'].get())
                self.setdist_all()
            elif dialog.result == 'reset':
                self.distrange_min = self.result.cp_defaultrange[0]
                self.distrange_max = self.result.cp_defaultrange[1]
                self.setdist_all()

    def set_arbcpdist(self, event=None):
        if self.result is not None:
            cp_arbdistribution = self.mplot.environment.cp_arbdistribution
            list_cp = self.result.controlpoints.list_cp
            boundary_margin = 500
            equaldist_unit = 25
            cp_arbcp_default = [max(0, round(min(list_cp), -2) - boundary_margin), round(max(list_cp), -2) + boundary_margin, equaldist_unit]
            if cp_arbdistribution is None:
                cp_arbdistribution = cp_arbcp_default
            dialog = dialog_multifields.dialog_multifields(
                self,
                [
                    {'name': 'min', 'type': 'Double', 'label': i18n.get('dialog.cp_min', value=str(cp_arbcp_default[0])), 'default': cp_arbdistribution[0]},
                    {'name': 'max', 'type': 'Double', 'label': i18n.get('dialog.cp_max', value=str(cp_arbcp_default[1])), 'default': cp_arbdistribution[1]},
                    {'name': 'interval', 'type': 'Double', 'label': i18n.get('dialog.cp_interval', value=str(cp_arbcp_default[2])), 'default': cp_arbdistribution[2]},
                ],
                message=i18n.get('dialog.set_controlpoint'),
            )
            if dialog.result == 'OK':
                inputval = [dialog.variables['min'].get(), dialog.variables['max'].get(), dialog.variables['interval'].get()]
                for ix in [0, 1, 2]:
                    self.mplot.environment.cp_arbdistribution[ix] = float(inputval[ix])
                self.reload_map()
            elif dialog.result == 'reset':
                for ix in [0, 1, 2]:
                    self.mplot.environment.cp_arbdistribution = None
                self.reload_map()

    def aboutwindow(self, event=None):
        msg = i18n.get('about.text', version=__version__)
        QtWidgets.QMessageBox.information(self, self.windowTitle(), msg)

    def import_bgimg(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            i18n.get('button.import_bg'),
            os.getcwd(),
            'Image Files (*.png *.jpg *.jpeg);;{} (*)'.format(i18n.get('filetype.any')),
        )
        if not filepath:
            return
        try:
            self.bg_image_original = Image.open(filepath).convert('RGBA')
            self.bg_image_array = np.asarray(self.bg_image_original)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, self.windowTitle(), i18n.get('dialog.bgimg_load_error', error=str(e)))
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

        self.bgimg_adjust_btn.setEnabled(True)
        self.bgimg_show_chk.setEnabled(True)
        if hasattr(self, 'plane_canvas'):
            self.plane_canvas.redraw()

    def adjust_bgimg(self):
        if self.bg_image_original is None:
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(i18n.get('dialog.adjust_bgimg'))
        layout = QtWidgets.QVBoxLayout(dialog)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        fields = [
            ('x', i18n.get('label.bgimg_x')),
            ('y', i18n.get('label.bgimg_y')),
            ('width', i18n.get('label.bgimg_width')),
            ('height', i18n.get('label.bgimg_height')),
            ('rotation', i18n.get('label.bgimg_rotation')),
        ]
        edits = {}
        for key, label_text in fields:
            edit = QtWidgets.QLineEdit(str(self.bg_image_params[key]))
            edits[key] = edit
            form.addRow(label_text, edit)

        button_row = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton(i18n.get('button.ok'))
        cancel_btn = QtWidgets.QPushButton(i18n.get('button.cancel'))
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        align_btn = QtWidgets.QPushButton(i18n.get('button.align_to_station'))
        layout.addWidget(align_btn)

        def on_ok():
            try:
                for key in edits:
                    self.bg_image_params[key] = float(edits[key].text())
                dialog.accept()
                self.plane_canvas.redraw()
            except ValueError:
                QtWidgets.QMessageBox.critical(dialog, dialog.windowTitle(), i18n.get('dialog.invalid_number'))

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        align_btn.clicked.connect(lambda: self._align_to_station_dialog(dialog))
        dialog.exec()

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
        return float(own[idx][1]), float(own[idx][2])

    def _start_align_pick(self, slot, dialog, btn1, btn2):
        self._align_pick_slot = slot
        self._align_dialog = dialog
        self._align_pick_btn1 = btn1
        self._align_pick_btn2 = btn2
        self._align_pick_active = True
        dialog.hide()
        self.plane_canvas.set_cursor('crosshair')
        self.plane_canvas.canvas.unbind('<Double-Button-1>')
        self.plane_canvas.canvas.bind('<Double-Button-1>', self._on_align_canvas_dblclick)

    def _on_align_canvas_dblclick(self, event):
        wx, wy = self.plane_canvas.screen_to_world(event.x, event.y)
        self._cleanup_align_pick()
        slot = self._align_pick_slot
        if slot == 1:
            self._align_pick1 = (wx, wy)
            self._align_pick_btn1.setText(i18n.get('button.pick_on_bg_ok'))
        else:
            self._align_pick2 = (wx, wy)
            self._align_pick_btn2.setText(i18n.get('button.pick_on_bg_ok'))
        self._align_dialog.show()
        self._align_dialog.raise_()
        self._align_dialog.activateWindow()
        return 'break'

    def _cleanup_align_pick(self):
        if hasattr(self, '_align_pick_active') and self._align_pick_active:
            self._align_pick_active = False
            self.plane_canvas.canvas.unbind('<Double-Button-1>')
            self.plane_canvas.canvas.bind('<Double-Button-1>', self.plane_canvas.fit)
        self.plane_canvas.set_cursor('')

    def _align_to_station_dialog(self, parent_dialog):
        if self.result is None or not hasattr(self.result, 'station') or len(self.result.station.position) == 0:
            QtWidgets.QMessageBox.information(parent_dialog, parent_dialog.windowTitle(), i18n.get('dialog.no_station_data'))
            return

        dialog = QtWidgets.QDialog(parent_dialog)
        dialog.setWindowTitle(i18n.get('dialog.align_to_station'))
        main_layout = QtWidgets.QVBoxLayout(dialog)
        station_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(station_layout)

        stnlist = []
        for stnkey in self.result.station.stationkey.keys():
            stnlist.append(stnkey + ', ' + self.result.station.stationkey[stnkey])

        left_box = QtWidgets.QGroupBox(i18n.get('frame.station1'))
        left_layout = QtWidgets.QVBoxLayout(left_box)
        left_layout.addWidget(QtWidgets.QLabel(i18n.get('label.select_station')))
        stn1_cb = QtWidgets.QComboBox()
        stn1_cb.addItems(stnlist)
        left_layout.addWidget(stn1_cb)
        pick1_btn = QtWidgets.QPushButton(i18n.get('button.pick_on_bg'))
        left_layout.addWidget(pick1_btn)
        station_layout.addWidget(left_box)

        right_box = QtWidgets.QGroupBox(i18n.get('frame.station2'))
        right_layout = QtWidgets.QVBoxLayout(right_box)
        right_layout.addWidget(QtWidgets.QLabel(i18n.get('label.select_station')))
        stn2_cb = QtWidgets.QComboBox()
        stn2_cb.addItems(stnlist)
        if len(stnlist) > 1:
            stn2_cb.setCurrentIndex(1)
        right_layout.addWidget(stn2_cb)
        pick2_btn = QtWidgets.QPushButton(i18n.get('button.pick_on_bg'))
        right_layout.addWidget(pick2_btn)
        station_layout.addWidget(right_box)

        self._align_pick1 = None
        self._align_pick2 = None
        pick1_btn.clicked.connect(lambda: self._start_align_pick(1, dialog, pick1_btn, pick2_btn))
        pick2_btn.clicked.connect(lambda: self._start_align_pick(2, dialog, pick1_btn, pick2_btn))

        button_row = QtWidgets.QHBoxLayout()
        apply_btn = QtWidgets.QPushButton(i18n.get('button.apply'))
        ok_btn = QtWidgets.QPushButton(i18n.get('button.ok'))
        cancel_btn = QtWidgets.QPushButton(i18n.get('button.cancel'))
        button_row.addWidget(apply_btn)
        button_row.addWidget(ok_btn)
        button_row.addWidget(cancel_btn)
        main_layout.addLayout(button_row)

        apply_btn.clicked.connect(lambda: self._compute_and_apply_alignment(stn1_cb.currentText(), stn2_cb.currentText(), dialog, close_parent=False))

        def on_ok():
            if self._compute_and_apply_alignment(stn1_cb.currentText(), stn2_cb.currentText(), dialog, close_parent=True):
                dialog.accept()
                parent_dialog.accept()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(lambda: (self._cleanup_align_pick(), dialog.reject()))
        dialog.rejected.connect(self._cleanup_align_pick)
        dialog.exec()

    def _compute_and_apply_alignment(self, stn1_val, stn2_val, dialog, close_parent):
        if self._align_pick1 is None or self._align_pick2 is None:
            QtWidgets.QMessageBox.information(dialog, dialog.windowTitle(), i18n.get('dialog.pick_points_needed'))
            return False
        s1 = self._get_station_world_coords(stn1_val)
        s2 = self._get_station_world_coords(stn2_val)
        if s1 is None or s2 is None:
            QtWidgets.QMessageBox.information(dialog, dialog.windowTitle(), i18n.get('dialog.station_coord_error'))
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
            QtWidgets.QMessageBox.information(dialog, dialog.windowTitle(), i18n.get('dialog.distance_too_short'))
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
            QtWidgets.QMessageBox.information(dialog, dialog.windowTitle(), i18n.get('dialog.pick_points_coincident'))
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
        self.plane_canvas.redraw()
        return True

    def customdialog_test(self, event=None):
        dialog_obj = dialog_multifields.dialog_multifields(
            self,
            [{'name': 'A', 'type': 'str', 'label': 'test A', 'default': 'alpha'},
             {'name': 'B', 'type': 'Double', 'label': 'test B', 'default': 100}],
            'Test Dialog',
        )
        print('Done', dialog_obj.result, dialog_obj.variables['A'].get())

    def open_webdocument(self, event=None):
        webbrowser.open('https://github.com/NewSapporoNingyo/kobushi-trackviewer-modified')


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('filepath', metavar='F', type=str, help='input mapfile', nargs='?')
    argparser.add_argument('-s', '--step', help='distance interval for track calculation', type=float, default=25)
    argparser.add_argument('-f', '--font', help='Font', type=str, default='sans-serif')
    args = argparser.parse_args()

    qt_app = QtWidgets.QApplication(sys.argv)

    def qt_excepthook(exc_type, value, tb):
        message = ''.join(traceback.format_exception(exc_type, value, tb))
        try:
            sys.__stderr__.write(message)
        except Exception:
            pass
        QtWidgets.QMessageBox.critical(None, 'Unhandled exception', message)

    sys.excepthook = qt_excepthook
    window = mainwindow(parser=None, stepdist=args.step, font=args.font)
    window.show()
    if args.filepath is not None:
        window.open_mapfile(inputdir=args.filepath)
    sys.exit(qt_app.exec())
