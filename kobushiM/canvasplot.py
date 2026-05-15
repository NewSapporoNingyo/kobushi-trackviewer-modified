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

import math
import numpy as np

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import pyqtgraph.exporters


pg.setConfigOptions(antialias=True, imageAxisOrder='row-major')


class _CanvasEvent:
    def __init__(self, qevent, widget):
        pos = qevent.position()
        self.x = float(pos.x())
        self.y = float(pos.y())
        self.widget = widget


class _CanvasCompat:
    """Small Tk Canvas compatibility layer for code that draws screen overlays."""

    def __init__(self, owner):
        self.owner = owner
        self._overlay_items = {}

    def bind(self, event_name, callback):
        self.owner._canvas_bindings[event_name] = callback
        self.owner.viewport().setMouseTracking('<Motion>' in self.owner._canvas_bindings)

    def unbind(self, event_name):
        self.owner._canvas_bindings.pop(event_name, None)
        self.owner.viewport().setMouseTracking('<Motion>' in self.owner._canvas_bindings)

    def winfo_width(self):
        return max(1, self.owner.viewport().width())

    def winfo_height(self):
        return max(1, self.owner.viewport().height())

    def config(self, **kwargs):
        if 'cursor' in kwargs:
            self.owner.set_cursor(kwargs['cursor'])

    configure = config

    def _screen_to_scene(self, x, y):
        return self.owner.mapToScene(QtCore.QPoint(int(round(x)), int(round(y))))

    def _register_overlay(self, item):
        item.setZValue(100000)
        self.owner.scene().addItem(item)
        item_id = id(item)
        self._overlay_items[item_id] = item
        return item_id

    def create_line(self, *coords, fill=None, width=1, **kwargs):
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)):
            coords = tuple(coords[0])
        if len(coords) < 4:
            return None
        path = QtGui.QPainterPath(self._screen_to_scene(coords[0], coords[1]))
        for ix in range(2, len(coords) - 1, 2):
            path.lineTo(self._screen_to_scene(coords[ix], coords[ix + 1]))
        item = QtWidgets.QGraphicsPathItem(path)
        pen = QtGui.QPen(pg.mkColor(fill or self.owner.line_color))
        pen.setWidthF(float(width))
        pen.setCosmetic(True)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        item.setPen(pen)
        return self._register_overlay(item)

    def create_text(self, x, y, text='', fill=None, font=None, anchor='nw', **kwargs):
        item = QtWidgets.QGraphicsSimpleTextItem(str(text))
        qfont = QtGui.QFont(self.owner.font_family, 9)
        if isinstance(font, (list, tuple)):
            if len(font) > 0:
                qfont.setFamily(str(font[0]))
            if len(font) > 1:
                try:
                    qfont.setPointSize(int(font[1]))
                except Exception:
                    pass
            if len(font) > 2 and 'bold' in str(font[2]).lower():
                qfont.setBold(True)
        item.setFont(qfont)
        item.setBrush(QtGui.QBrush(pg.mkColor(fill or self.owner.text_color)))
        pos = self._screen_to_scene(x, y)
        item.setPos(pos)
        rect = item.boundingRect()
        dx = 0.0
        dy = 0.0
        anchor = anchor or 'nw'
        if 'e' in anchor:
            dx = -rect.width()
        elif 'w' not in anchor:
            dx = -rect.width() / 2.0
        if 's' in anchor:
            dy = -rect.height()
        elif 'n' not in anchor:
            dy = -rect.height() / 2.0
        item.moveBy(dx, dy)
        return self._register_overlay(item)

    def create_oval(self, x1, y1, x2, y2, outline=None, fill=None, width=1, **kwargs):
        p1 = self._screen_to_scene(x1, y1)
        p2 = self._screen_to_scene(x2, y2)
        rect = QtCore.QRectF(p1, p2).normalized()
        item = QtWidgets.QGraphicsEllipseItem(rect)
        pen = QtGui.QPen(pg.mkColor(outline or self.owner.line_color))
        pen.setWidthF(float(width))
        pen.setCosmetic(True)
        item.setPen(pen)
        if fill:
            item.setBrush(QtGui.QBrush(pg.mkColor(fill)))
        return self._register_overlay(item)

    def create_image(self, *args, **kwargs):
        return None

    def move(self, *args, **kwargs):
        return None

    def tag_lower(self, *args, **kwargs):
        return None

    def delete(self, item_id):
        if item_id == 'all':
            self.clear_overlays()
            return
        item = self._overlay_items.pop(item_id, None)
        if item is not None and item.scene() is not None:
            item.scene().removeItem(item)

    def clear_overlays(self):
        for item in list(self._overlay_items.values()):
            if item.scene() is not None:
                item.scene().removeItem(item)
        self._overlay_items.clear()

    def postscript(self, file=None, **kwargs):
        if file:
            self.owner.export_image(file)


class _TrackViewBox(pg.ViewBox):
    def __init__(self, *args, **kwargs):
        self.owner = None
        super().__init__(*args, **kwargs)

    def mouseDragEvent(self, ev, axis=None):
        owner = self.owner
        if owner is not None and not owner.interactive:
            ev.ignore()
            return
        if (
            owner is not None
            and owner.rotate_enabled
            and ev.button() == QtCore.Qt.MouseButton.RightButton
        ):
            center = self.sceneBoundingRect().center()
            p0 = ev.lastScenePos()
            p1 = ev.scenePos()
            
            # 记录旋转前视口中心对应的世界坐标
            wc_x, wc_y = owner._display_to_world_point(owner.center[0], owner.center[1])
            
            a0 = math.atan2(p0.y() - center.y(), p0.x() - center.x())
            a1 = math.atan2(p1.y() - center.y(), p1.x() - center.x())
            owner.rotation += a1 - a0
            
            # 【修改这里】：将计算新坐标和移动视口的操作推迟到 redraw 中执行
            # 保证视口范围的变化和内容重绘绝对同步，消除旋转时的画面偏移错觉
            owner._pending_rotation_center = (wc_x, wc_y)
            
            # 使用定时器延迟重绘，彻底解决旋转时阻塞 UI 造成的卡顿问题
            owner._redraw_timer.start(15)
            ev.accept()
            return
        super().mouseDragEvent(ev, axis=axis)


class PlotCanvas(pg.PlotWidget):
    def __init__(
        self,
        master=None,
        title='',
        rotate_enabled=True,
        y_axis_down=False,
        world_grid=False,
        x_unit='',
        y_unit='',
        independent_scale=False,
        scalebar=False,
        lock_y_center=False,
        zoom_x_by_default=False,
        enable_lod=True,
    ):
        self._viewbox = _TrackViewBox()
        super().__init__(parent=master, viewBox=self._viewbox, background='#000000')
        self._viewbox.owner = self

        self.title = title
        self.rotate_enabled = rotate_enabled
        self.y_axis_down = y_axis_down
        self.world_grid = world_grid
        self.x_unit = x_unit
        self.y_unit = y_unit
        self.independent_scale = independent_scale
        self.scalebar = scalebar
        self.lock_y_center = lock_y_center
        self.zoom_x_by_default = zoom_x_by_default
        self.enable_lod = enable_lod
        self.grid_mode = 'fixed'
        self._interactive = True
        self._view_fitted = False
        self.background = '#000000'
        self.grid_color = '#333333'
        self.line_color = '#ffffff'
        self.text_color = '#ffffff'
        self.font_family = 'Sans Serif'
        self.center = [0.0, 0.0]
        self._pending_rotation_center = None  # 【新增】：用于暂存旋转期间的中心点
        self.scale = 1.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0
        self.bounds = None
        self.renderer = None
        self._in_redraw = False
        self._canvas_bindings = {}
        self.canvas = _CanvasCompat(self)

        self.plotItem.hideButtons()
        self.plotItem.setMenuEnabled(False)
        self.getViewBox().invertY(self.y_axis_down)
        # 防止平面图（非独立缩放的画布）在调整窗口大小时被拉伸
        if not self.independent_scale:
            self.getViewBox().setAspectLocked(True)
        self._apply_mouse_enabled()
        self._set_axis_labels()
        self.canvas.bind('<Double-Button-1>', self.fit)

        self._redraw_timer = QtCore.QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.timeout.connect(self.redraw)
        self._viewbox.sigRangeChanged.connect(self._on_range_changed)
        self.viewport().installEventFilter(self)

    @property
    def interactive(self):
        return self._interactive

    @interactive.setter
    def interactive(self, value):
        self._interactive = bool(value)
        self._apply_mouse_enabled()

    def _apply_mouse_enabled(self):
        if hasattr(self, '_viewbox'):
            self._viewbox.setMouseEnabled(
                x=self._interactive,
                y=self._interactive and not self.lock_y_center,
            )

    def _set_axis_labels(self):
        if self.x_unit:
            self.setLabel('bottom', units=self.x_unit)
        if self.y_unit:
            self.setLabel('left', units=self.y_unit)
            
        # 【新增】：隐藏坐标轴的轴线，只保留刻度文字，并让其紧贴画布边缘
        for ax_name in ['left', 'bottom']:
            ax = self.getAxis(ax_name)
            # 将坐标轴主线和外延刻度线颜色设为透明（隐藏）
            ax.setPen(pg.mkPen(None))
            # 确保刻度的文字颜色正常显示
            ax.setTextPen(pg.mkColor(self.text_color))
            # 刻度线长度设为 0，并将刻度文字向内偏移贴近边缘 (2像素)
            ax.setStyle(tickLength=0, tickTextOffset=2)

    def eventFilter(self, obj, event):
        if obj is self.viewport():
            event_type = event.type()
            if event_type == QtCore.QEvent.Type.MouseMove:
                callback = self._canvas_bindings.get('<Motion>')
                if callback is not None:
                    callback(_CanvasEvent(event, self.canvas))
            elif event_type == QtCore.QEvent.Type.MouseButtonDblClick:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    callback = self._canvas_bindings.get('<Double-Button-1>')
                    if callback is not None:
                        result = callback(_CanvasEvent(event, self.canvas))
                        return result == 'break'
        return super().eventFilter(obj, event)

    def set_renderer(self, renderer, bounds=None, keep_view=True):
        self.renderer = renderer
        if bounds is not None:
            self.bounds = bounds
        if not keep_view or not self._view_fitted:
            self.fit()
        else:
            self.redraw()

    def fit(self, event=None):
        if not self.interactive and event is not None:
            return
        if self.bounds is not None:
            xmin, ymin, xmax, ymax = self.bounds
            if self.lock_y_center:
                half = max(abs(ymin), abs(ymax), 1.0)
                ymin, ymax = -half, half
            if abs(xmax - xmin) < 1e-9:
                xmax = xmin + 1.0
            if abs(ymax - ymin) < 1e-9:
                ymax = ymin + 1.0
            self._viewbox.setRange(xRange=(xmin, xmax), yRange=(ymin, ymax), padding=0.06)
            self._sync_view_metrics()
        self._view_fitted = True
        self.redraw()

    def reset_rotation(self):
        self.rotation = 0.0
        self.redraw()

    def set_font(self, family):
        self.font_family = family or 'Sans Serif'
        self.redraw()

    def get_view_state(self):
        return {
            'center': self.center.copy(),
            'scale': self.scale,
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'rotation': self.rotation,
            'view_range': self.viewRange(),
        }

    def set_view_state(self, state):
        if state is None:
            return
        self.center = state.get('center', self.center).copy()
        self.scale = state.get('scale', self.scale)
        self.scale_x = state.get('scale_x', self.scale_x)
        self.scale_y = state.get('scale_y', self.scale_y)
        self.rotation = state.get('rotation', self.rotation)
        view_range = state.get('view_range')
        if view_range is not None:
            self._viewbox.setRange(xRange=view_range[0], yRange=view_range[1], padding=0)
        self._view_fitted = True
        self.redraw()

    def set_center(self, x=None, y=None):
        xr, yr = self.viewRange()
        xspan = max(abs(xr[1] - xr[0]), 1e-9)
        yspan = max(abs(yr[1] - yr[0]), 1e-9)
        
        # 传入的通常为世界坐标，需转为显示坐标
        if x is not None and y is not None:
            cx, cy = self._world_to_display_point(x, y)
        elif x is not None:
            _, curr_wy = self._display_to_world_point(self.center[0], self.center[1])
            cx, cy = self._world_to_display_point(x, curr_wy)
        elif y is not None:
            curr_wx, _ = self._display_to_world_point(self.center[0], self.center[1])
            cx, cy = self._world_to_display_point(curr_wx, y)
        else:
            cx, cy = self.center[0], self.center[1]

        if self.lock_y_center:
            cy = 0.0
            
        self._viewbox.setRange(
            xRange=(cx - xspan / 2.0, cx + xspan / 2.0),
            yRange=(cy - yspan / 2.0, cy + yspan / 2.0),
            padding=0,
        )
        self._sync_view_metrics()
        self.redraw()

    def set_grid_mode(self, mode):
        self.grid_mode = mode
        self.redraw()

    def redraw(self):
        # 【新增】：在执行重绘前，先同步处理被挂起的视口旋转位移
        if getattr(self, '_pending_rotation_center', None) is not None:
            wc_x, wc_y = self._pending_rotation_center
            self._pending_rotation_center = None
            nd_x, nd_y = self._world_to_display_point(wc_x, wc_y)
            xr, yr = self.viewRange()
            xspan = max(abs(xr[1] - xr[0]), 1e-9)
            yspan = max(abs(yr[1] - yr[0]), 1e-9)
            self._viewbox.setRange(
                xRange=(nd_x - xspan / 2.0, nd_x + xspan / 2.0),
                yRange=(nd_y - yspan / 2.0, nd_y + yspan / 2.0),
                padding=0,
            )
            self._sync_view_metrics()

        if self._in_redraw:
            return
        self._in_redraw = True
        try:
            self._redraw_timer.stop()
            self.getPlotItem().clear()
            self.canvas.clear_overlays()
            self.showGrid(x=self.grid_mode != 'none', y=self.grid_mode != 'none', alpha=0.3)
            self.getPlotItem().setTitle(self.title, color=self.text_color, size='9pt')
            if self.renderer is not None:
                self.renderer(self)
            if self.scalebar:
                self._draw_scalebar()
        finally:
            self._in_redraw = False

    def _sync_view_metrics(self):
        xr, yr = self.viewRange()
        xmin, xmax = min(xr), max(xr)
        ymin, ymax = min(yr), max(yr)
        self.center = [(xmin + xmax) / 2.0, (ymin + ymax) / 2.0]
        if self.lock_y_center:
            self.center[1] = 0.0
        dx = max(xmax - xmin, 1e-9)
        dy = max(ymax - ymin, 1e-9)
        self.scale_x = max(1, self.canvas.winfo_width()) / dx
        self.scale_y = max(1, self.canvas.winfo_height()) / dy
        self.scale = min(self.scale_x, self.scale_y)

    def _on_range_changed(self, *args):
        self._sync_view_metrics()
        if not self._in_redraw and self.renderer is not None:
            self._redraw_timer.start(35)

    def _scales(self):
        if self.independent_scale:
            return self.scale_x, self.scale_y
        return self.scale, self.scale

    def _world_to_display_point(self, x, y):
        if self.rotation == 0:
            return float(x), float(y)
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        return c * float(x) - s * float(y), s * float(x) + c * float(y)

    def _display_to_world_point(self, x, y):
        if self.rotation == 0:
            return float(x), float(y)
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        # 逆旋转变换
        return c * float(x) + s * float(y), -s * float(x) + c * float(y)

    def _world_to_display_batch(self, points_np):
        pts = np.asarray(points_np, dtype=np.float64)
        if pts.size == 0 or self.rotation == 0:
            return pts
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        out = pts.copy()
        out[:, 0] = c * pts[:, 0] - s * pts[:, 1]
        out[:, 1] = s * pts[:, 0] + c * pts[:, 1]
        return out

    def world_to_screen(self, x, y):
        dx, dy = self._world_to_display_point(x, y)
        scene_pos = self._viewbox.mapViewToScene(QtCore.QPointF(dx, dy))
        view_pos = self.mapFromScene(scene_pos)
        return float(view_pos.x()), float(view_pos.y())

    def screen_to_world_delta(self, dx, dy):
        cx = self.canvas.winfo_width() / 2.0
        cy = self.canvas.winfo_height() / 2.0
        x0, y0 = self.screen_to_world(cx, cy)
        x1, y1 = self.screen_to_world(cx + dx, cy + dy)
        return x0 - x1, y1 - y0

    def screen_to_world(self, sx, sy):
        scene_pos = self.mapToScene(QtCore.QPoint(int(round(sx)), int(round(sy))))
        view_pos = self._viewbox.mapSceneToView(scene_pos)
        return self._display_to_world_point(view_pos.x(), view_pos.y())

    def _get_visible_world_bounds(self, margin=0.35):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        corners = [
            self.screen_to_world(0, 0),
            self.screen_to_world(width, 0),
            self.screen_to_world(0, height),
            self.screen_to_world(width, height),
        ]
        xmin = min(p[0] for p in corners)
        xmax = max(p[0] for p in corners)
        ymin = min(p[1] for p in corners)
        ymax = max(p[1] for p in corners)
        pad_x = max(xmax - xmin, 1e-6) * margin
        pad_y = max(ymax - ymin, 1e-6) * margin
        return xmin - pad_x, ymin - pad_y, xmax + pad_x, ymax + pad_y

    def _get_lod_stride(self):
        if not self.enable_lod:
            return 1
        sx_scale, sy_scale = self._scales()
        effective_scale = min(sx_scale, sy_scale)
        if effective_scale >= 0.5:
            return 1
        if effective_scale >= 0.1:
            return 2
        if effective_scale >= 0.01:
            return 5
        return 10

    def line(self, points, fill=None, width=1, tags=None):
        pts = np.asarray(points, dtype=np.float64)
        if pts.size == 0 or len(pts) < 2:
            return None
        pts = pts.reshape((-1, 2))
        pts = self._world_to_display_batch(pts)
        pen = pg.mkPen(pg.mkColor(fill or self.line_color), width=width)
        item = pg.PlotDataItem(pts[:, 0], pts[:, 1], pen=pen, connect='finite')
        self.plotItem.addItem(item)
        return item

    def line_screen(self, coords, fill=None, width=1):
        return self.canvas.create_line(*coords, fill=fill or self.line_color, width=width)

    def get_view_params(self):
        sx_scale, sy_scale = self._scales()
        return {
            'width': self.canvas.winfo_width(),
            'height': self.canvas.winfo_height(),
            'center': self.center.copy(),
            'rotation': self.rotation,
            'sx_scale': sx_scale,
            'sy_scale': sy_scale,
            'y_axis_down': self.y_axis_down,
        }

    @staticmethod
    def _world_to_screen_static(points, vp):
        pts = np.asarray(points)
        if pts.size == 0 or len(pts) < 2:
            return []
        width = vp['width']
        height = vp['height']
        cx = vp['center'][0]
        cy = vp['center'][1]
        c = math.cos(vp['rotation'])
        s = math.sin(vp['rotation'])
        screen_y_sign = 1 if vp['y_axis_down'] else -1
        sx_scale = vp['sx_scale']
        sy_scale = vp['sy_scale']
        
        # 绕绝对原点旋转
        rx = c * pts[:, 0] - s * pts[:, 1]
        ry = s * pts[:, 0] + c * pts[:, 1]
        
        # 再偏移相机中心
        dx = rx - cx
        dy = ry - cy
        
        sx = width / 2 + dx * sx_scale
        sy = height / 2 + screen_y_sign * dy * sy_scale
        coords = np.empty(sx.size + sy.size, dtype=np.float64)
        coords[0::2] = sx
        coords[1::2] = sy
        return coords.tolist()

    def point(self, x, y, radius=3, outline=None, fill=None):
        dx, dy = self._world_to_display_point(x, y)
        item = pg.ScatterPlotItem(
            [dx],
            [dy],
            size=radius * 2,
            pen=pg.mkPen(pg.mkColor(outline or self.line_color), width=1),
            brush=pg.mkBrush(pg.mkColor(fill or self.background)),
        )
        self.plotItem.addItem(item)
        return item

    def text(self, x, y, text, anchor='nw', angle=0, offset=(6, -6), font_size=9, fill=None):
        sx, sy = self.world_to_screen(x, y)
        wx, wy = self.screen_to_world(sx + offset[0], sy + offset[1])
        dx, dy = self._world_to_display_point(wx, wy)
        anchor_map = {
            'nw': (0, 0),
            'n': (0.5, 0),
            'ne': (1, 0),
            'w': (0, 0.5),
            'center': (0.5, 0.5),
            'e': (1, 0.5),
            'sw': (0, 1),
            's': (0.5, 1),
            'se': (1, 1),
        }
        item = pg.TextItem(
            text=str(text),
            color=pg.mkColor(fill or self.text_color),
            anchor=anchor_map.get(anchor, (0, 0)),
            angle=angle,
        )
        qfont = QtGui.QFont(self.font_family, int(font_size))
        try:
            item.setFont(qfont)
        except AttributeError:
            item.textItem.setFont(qfont)
        item.setPos(dx, dy)
        self.plotItem.addItem(item)
        return item

    def image(self, image_array, x, y, width, height, rotation=0.0, opacity=1.0):
        arr = np.ascontiguousarray(image_array)
        if arr.size == 0:
            return None
        item = pg.ImageItem(arr)
        item.setOpacity(opacity)
        item.setZValue(-1000)
        img_h, img_w = arr.shape[:2]
        transform = QtGui.QTransform()
        transform.translate(float(x), float(y))
        transform.rotate(float(rotation))
        transform.scale(float(width) / max(1, img_w), float(height) / max(1, img_h))
        transform.translate(-img_w / 2.0, -img_h / 2.0)
        item.setTransform(transform)
        self.plotItem.addItem(item)
        return item

    def _grid_step(self, span):
        raw = max(span / 8, 1e-9)
        magnitude = 10 ** math.floor(math.log10(raw))
        for factor in [1, 2, 5, 10]:
            step = factor * magnitude
            if raw <= step:
                return step
        return 10 * magnitude

    def _format_scalebar_label(self, length):
        if length >= 1000:
            km = length / 1000
            if abs(km - round(km)) < 1e-9:
                return '{:.0f}km'.format(km)
            return '{:.1f}km'.format(km).rstrip('0').rstrip('.')
        if abs(length - round(length)) < 1e-9:
            return '{:.0f}m'.format(length)
        return '{:.1f}m'.format(length).rstrip('0').rstrip('.')

    def _friendly_scalebar_length(self, raw_length):
        if raw_length <= 0:
            return 1
        magnitude = 10 ** math.floor(math.log10(raw_length))
        candidates = []
        for exp_offset in [-1, 0, 1, 2]:
            base = magnitude * (10 ** exp_offset)
            for factor in [1, 2, 3, 5]:
                candidates.append(factor * base)
        candidates = sorted(value for value in candidates if value > 0)
        return min(candidates, key=lambda value: abs(value - raw_length))

    def _draw_scalebar(self):
        sx_scale, _ = self._scales()
        if sx_scale <= 0:
            return
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        target_px = min(max(width * 0.18, 90), 180)
        length = self._friendly_scalebar_length(target_px / sx_scale)
        bar_px = length * sx_scale
        margin = 24
        x2 = width - margin
        x1 = x2 - bar_px
        y = height - margin
        tick = 10
        self.canvas.create_line(x1, y - tick, x1, y, x2, y, x2, y - tick, fill=self.text_color, width=2)
        self.canvas.create_text(
            (x1 + x2) / 2,
            y - tick - 4,
            text=self._format_scalebar_label(length),
            fill=self.text_color,
            font=(self.font_family, 9),
            anchor='s',
        )

    def set_cursor(self, name):
        if name == 'crosshair':
            self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        elif name:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        else:
            self.unsetCursor()

    def export_image(self, filepath):
        exporter = pyqtgraph.exporters.ImageExporter(self.getPlotItem())
        exporter.export(str(filepath))
