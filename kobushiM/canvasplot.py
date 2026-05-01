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
import tkinter as tk
from tkinter import ttk


class PlotCanvas(ttk.Frame):
    def __init__(self, master, title='', rotate_enabled=True, y_axis_down=False, world_grid=False, x_unit='', y_unit='', independent_scale=False, scalebar=False, lock_y_center=False, zoom_x_by_default=False):
        super().__init__(master, padding=0)
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
        self.background = '#000000'
        self.grid_color = '#333333'
        self.line_color = '#ffffff'
        self.text_color = '#ffffff'
        self.font_family = 'TkDefaultFont'
        self.center = [0.0, 0.0]
        self.scale = 1.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0
        self.bounds = None
        self.renderer = None
        self._last_drag = None
        self._last_rotate = None

        self.canvas = tk.Canvas(self, bg=self.background, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas.bind('<Configure>', self._on_resize)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Shift-MouseWheel>', self._on_shift_mousewheel)
        self.canvas.bind('<Control-MouseWheel>', self._on_control_mousewheel)
        self.canvas.bind('<ButtonPress-1>', self._start_pan)
        self.canvas.bind('<B1-Motion>', self._pan)
        self.canvas.bind('<ButtonPress-3>', self._start_rotate)
        self.canvas.bind('<B3-Motion>', self._rotate_drag)
        self.canvas.bind('<Double-Button-1>', self.fit)

    def set_renderer(self, renderer, bounds=None, keep_view=True):
        self.renderer = renderer
        if bounds is not None:
            self.bounds = bounds
        if not keep_view or self.scale <= 1.0:
            self.fit()
        else:
            self.redraw()

    def fit(self, event=None):
        if self.bounds is not None:
            xmin, ymin, xmax, ymax = self.bounds
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            dx = max(xmax - xmin, 1e-6)
            dy = max(ymax - ymin, 1e-6)
            self.center = [(xmin + xmax) / 2, (ymin + ymax) / 2]
            self.scale = min(width / dx, height / dy) * 0.88
            self.scale_x = width / dx * 0.88
            self.scale_y = height / dy * 0.88
        self.redraw()

    def reset_rotation(self):
        self.rotation = 0.0
        self.redraw()

    def set_font(self, family):
        self.font_family = family
        self.redraw()

    def get_view_state(self):
        return {
            'center': self.center.copy(),
            'scale': self.scale,
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'rotation': self.rotation,
        }

    def set_view_state(self, state):
        if state is None:
            return
        self.center = state['center'].copy()
        self.scale = state['scale']
        self.scale_x = state['scale_x']
        self.scale_y = state['scale_y']
        self.rotation = state['rotation']
        if self.lock_y_center:
            self.center[1] = 0
        self.redraw()

    def redraw(self):
        self.canvas.delete('all')
        self._draw_grid()
        if self.title:
            self.canvas.create_text(
                8, 8, anchor='nw', text=self.title,
                fill=self.text_color, font=(self.font_family, 9, 'bold'))
        if self.renderer is not None:
            self.renderer(self)
        if self.scalebar:
            self._draw_scalebar()

    def world_to_screen(self, x, y):
        dx = x - self.center[0]
        dy = y - self.center[1]
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        rx = c * dx - s * dy
        ry = s * dx + c * dy
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        screen_y_sign = 1 if self.y_axis_down else -1
        sx_scale, sy_scale = self._scales()
        return width / 2 + rx * sx_scale, height / 2 + screen_y_sign * ry * sy_scale

    def screen_to_world_delta(self, dx, dy):
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        screen_y_sign = 1 if self.y_axis_down else -1
        sx_scale, sy_scale = self._scales()
        wx = -(c * dx / sx_scale + screen_y_sign * s * dy / sy_scale)
        wy = (s * dx / sx_scale - screen_y_sign * c * dy / sy_scale)
        return wx, wy

    def screen_to_world(self, sx, sy):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        sx_scale, sy_scale = self._scales()
        rx = (sx - width / 2) / sx_scale
        screen_y_sign = 1 if self.y_axis_down else -1
        ry = (sy - height / 2) / (screen_y_sign * sy_scale)
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        x = c * rx + s * ry + self.center[0]
        y = -s * rx + c * ry + self.center[1]
        return x, y

    def _scales(self):
        if self.independent_scale:
            return self.scale_x, self.scale_y
        return self.scale, self.scale

    def line(self, points, fill=None, width=1):
        coords = []
        for x, y in points:
            sx, sy = self.world_to_screen(x, y)
            coords.extend([sx, sy])
        if len(coords) >= 4:
            self.canvas.create_line(
                *coords, fill=fill or self.line_color, width=width,
                capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def point(self, x, y, radius=3, outline=None, fill=None):
        sx, sy = self.world_to_screen(x, y)
        self.canvas.create_oval(
            sx - radius, sy - radius, sx + radius, sy + radius,
            outline=outline or self.line_color, fill=fill or self.background)

    def text(self, x, y, text, anchor='nw', angle=0, offset=(6, -6), font_size=9, fill=None):
        sx, sy = self.world_to_screen(x, y)
        kwargs = {
            'anchor': anchor,
            'text': text,
            'fill': fill or self.text_color,
            'font': (self.font_family, font_size),
        }
        try:
            kwargs['angle'] = angle
            self.canvas.create_text(sx + offset[0], sy + offset[1], **kwargs)
        except tk.TclError:
            kwargs.pop('angle', None)
            self.canvas.create_text(sx + offset[0], sy + offset[1], **kwargs)

    def _draw_grid(self):
        if self.world_grid:
            self._draw_world_grid()
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        spacing = 80
        for x in range(0, width + spacing, spacing):
            self.canvas.create_line(x, 0, x, height, fill=self.grid_color)
        for y in range(0, height + spacing, spacing):
            self.canvas.create_line(0, y, width, y, fill=self.grid_color)

    def _draw_world_grid(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        corners = [
            self.screen_to_world(0, 0),
            self.screen_to_world(width, 0),
            self.screen_to_world(0, height),
            self.screen_to_world(width, height),
        ]
        xmin = min(point[0] for point in corners)
        xmax = max(point[0] for point in corners)
        ymin = min(point[1] for point in corners)
        ymax = max(point[1] for point in corners)
        xstep = self._grid_step(xmax - xmin)
        ystep = self._grid_step(ymax - ymin)
        x0 = math.floor(xmin / xstep) * xstep
        y0 = math.floor(ymin / ystep) * ystep
        x = x0
        while x <= xmax + xstep:
            p1 = self.world_to_screen(x, ymin)
            p2 = self.world_to_screen(x, ymax)
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=self.grid_color)
            if p1[0] >= -60 and p1[0] <= width + 60:
                self.canvas.create_text(
                    p1[0] + 3, height - 16, anchor='sw',
                    text=self._format_grid_label(x, self.x_unit),
                    fill='#888888', font=(self.font_family, 8))
            x += xstep
        y = y0
        while y <= ymax + ystep:
            p1 = self.world_to_screen(xmin, y)
            p2 = self.world_to_screen(xmax, y)
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=self.grid_color)
            if p1[1] >= -20 and p1[1] <= height + 20:
                self.canvas.create_text(
                    6, p1[1] - 2, anchor='sw',
                    text=self._format_grid_label(y, self.y_unit),
                    fill='#888888', font=(self.font_family, 8))
            y += ystep

    def _grid_step(self, span):
        raw = max(span / 8, 1e-9)
        magnitude = 10 ** math.floor(math.log10(raw))
        for factor in [1, 2, 5, 10]:
            step = factor * magnitude
            if raw <= step:
                return step
        return 10 * magnitude

    def _format_grid_label(self, value, unit):
        if abs(value) >= 100:
            label = '{:.0f}'.format(value)
        elif abs(value) >= 10:
            label = '{:.1f}'.format(value).rstrip('0').rstrip('.')
        else:
            label = '{:.2f}'.format(value).rstrip('0').rstrip('.')
        return label + (unit if unit else '')

    def _draw_scalebar(self):
        sx_scale, sy_scale = self._scales()
        if sx_scale <= 0:
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        target_px = min(max(width * 0.18, 90), 180)
        raw_length = target_px / sx_scale
        length = self._friendly_scalebar_length(raw_length)
        bar_px = length * sx_scale
        margin = 24
        x2 = width - margin
        x1 = x2 - bar_px
        y = height - margin
        tick = 10
        self.canvas.create_line(x1, y - tick, x1, y, x2, y, x2, y - tick, fill=self.text_color, width=2)
        self.canvas.create_text(
            (x1 + x2) / 2, y - tick - 4,
            text=self._format_scalebar_label(length),
            fill=self.text_color, font=(self.font_family, 9),
            anchor='s')

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

    def _format_scalebar_label(self, length):
        if length >= 1000:
            km = length / 1000
            if abs(km - round(km)) < 1e-9:
                return '{:.0f}km'.format(km)
            return '{:.1f}km'.format(km).rstrip('0').rstrip('.')
        if abs(length - round(length)) < 1e-9:
            return '{:.0f}m'.format(length)
        return '{:.1f}m'.format(length).rstrip('0').rstrip('.')

    def _on_resize(self, event=None):
        self.redraw()

    def _on_mousewheel(self, event):
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        self._zoom(factor, axis='x' if self.zoom_x_by_default else 'both')
        self.redraw()

    def _on_shift_mousewheel(self, event):
        if self.independent_scale:
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            self._zoom(factor, axis='y')
            self.redraw()
            return
        if self.rotate_enabled:
            self.rotation += math.radians(5 if event.delta > 0 else -5)
            self.redraw()

    def _on_control_mousewheel(self, event):
        if self.independent_scale:
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            self._zoom(factor, axis='both' if self.zoom_x_by_default else 'x')
            self.redraw()

    def _zoom(self, factor, axis='both'):
        if self.independent_scale:
            if axis in ['both', 'x']:
                self.scale_x = max(0.001, min(self.scale_x * factor, 10000))
            if axis in ['both', 'y']:
                self.scale_y = max(0.001, min(self.scale_y * factor, 10000))
        else:
            self.scale = max(0.001, min(self.scale * factor, 10000))

    def _start_pan(self, event):
        self._last_drag = (event.x, event.y)

    def _pan(self, event):
        if self._last_drag is None:
            return
        dx = event.x - self._last_drag[0]
        dy = event.y - self._last_drag[1]
        wx, wy = self.screen_to_world_delta(dx, dy)
        self.center[0] += wx
        if not self.lock_y_center:
            self.center[1] += wy
        self._last_drag = (event.x, event.y)
        self.redraw()

    def _start_rotate(self, event):
        self._last_rotate = (event.x, event.y)

    def _rotate_drag(self, event):
        if not self.rotate_enabled or self._last_rotate is None:
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        cx = width / 2
        cy = height / 2
        a0 = math.atan2(self._last_rotate[1] - cy, self._last_rotate[0] - cx)
        a1 = math.atan2(event.y - cy, event.x - cx)
        self.rotation += a1 - a0
        self._last_rotate = (event.x, event.y)
        self.redraw()
