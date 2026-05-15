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

# Import required libraries for math, numeric arrays, and GUI 
# 必要な数学・数値配列・GUIライブラリをインポート 
# 导入数学、数值数组和GUI所需的库
import math
import numpy as np
import tkinter as tk
from tkinter import ttk


# Interactive plotting canvas class for 2D data visualization with pan/zoom/rotate 
# パン・ズーム・回転操作が可能な2Dデータ可視化用インタラクティブ描画キャンバスクラス 
# 支持平移/缩放/旋转交互的2D数据可视化绘图Canvas类
class PlotCanvas(ttk.Frame):
    def __init__(self, master, title='', rotate_enabled=True, y_axis_down=False, world_grid=False, x_unit='', y_unit='', independent_scale=False, scalebar=False, lock_y_center=False, zoom_x_by_default=False, enable_lod=True):
        # Initialize parent Frame with no padding /
        # 親Frameをパディングなしで初期化 /
        # 初始化父框架，无内边距
        super().__init__(master, padding=0)

        # Store configuration parameters /
        # 設定パラメータを保存 /
        # 存储配置参数
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

        # Initialize view state variables /
        # ビュー状態変数を初期化 /
        # 初始化视图状态变量
        self.grid_mode = 'fixed'
        self.interactive = True
        self._view_fitted = False

        # Set default visual styling colors and font /
        # デフォルトの視覚スタイル（色・フォント）を設定 /
        # 设置默认视觉样式颜色和字体
        self.background = '#000000'
        self.grid_color = '#333333'
        self.line_color = '#ffffff'
        self.text_color = '#ffffff'
        self.font_family = 'TkDefaultFont'

        # Initialize view transform: center, scale, rotation /
        # ビュー変換を初期化：中心・拡大率・回転 /
        # 初始化视图变换：中心、缩放、旋转
        self.center = [0.0, 0.0]
        self.scale = 1.0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0

        # Renderer callback and data bounds 
        # レンダラーコールバックとデータ範囲 
        # 渲染回调函数和数据范围
        self.bounds = None
        self.renderer = None

        # Interaction state variables for drag/rotate/debounce 
        # ドラッグ・回転・デバウンスのための操作状態変数 /
        # 拖拽/旋转/防抖用的交互状态变量
        self._last_drag = None
        self._last_rotate = None
        self._zoom_debounce_id = None
        self._hq_debounce_id = None
        self._interacting = False
        self._pan_deferred = False

        # Create the underlying Tkinter Canvas widget and make it fill the frame 
        # 基盤となるTkinter Canvasウィジェットを作成し、フレーム全体を占有させる 
        # 创建底层的Tkinter Canvas控件，使其填充整个框架
        self.canvas = tk.Canvas(self, bg=self.background, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Bind mouse and resize events to handler methods 
        # マウス操作・リサイズイベントをハンドラメソッドにバインド 
        # 绑定鼠标和窗口大小改变事件到处理方法
        self.canvas.bind('<Configure>', self._on_resize)
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Shift-MouseWheel>', self._on_shift_mousewheel)
        self.canvas.bind('<Control-MouseWheel>', self._on_control_mousewheel)
        self.canvas.bind('<ButtonPress-1>', self._start_pan)
        self.canvas.bind('<B1-Motion>', self._pan)
        self.canvas.bind('<ButtonRelease-1>', self._stop_pan)
        self.canvas.bind('<ButtonPress-3>', self._start_rotate)
        self.canvas.bind('<B3-Motion>', self._rotate_drag)
        self.canvas.bind('<ButtonRelease-3>', self._stop_rotate)
        self.canvas.bind('<Double-Button-1>', self.fit)

    def set_renderer(self, renderer, bounds=None, keep_view=True):
        # Register a rendering callback function and optionally set data bounds; fit view or redraw accordingly 
        # 描画コールバック関数を登録し、オプションでデータ範囲を設定。必要に応じてビュー適合または再描画 
        # 注册渲染回调函数并可选择设置数据范围；按需执行视图适配或重绘
        self.renderer = renderer
        if bounds is not None:
            self.bounds = bounds
        if not keep_view or not self._view_fitted:
            self.fit()
        else:
            self.redraw()

    def fit(self, event=None):
        # Automatically fit the view to show all data bounds with 88% margin 
        # 全データ範囲を88%のマージンで画面内に収めるようビューを自動調整 
        # 自动调整视图，以88%的边距显示全部数据范围
        if not self.interactive:
            return
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
        self._view_fitted = True
        self.redraw()

    def reset_rotation(self):
        # Reset rotation angle to 0 degrees /
        # 回転角度を0度にリセット /
        # 将旋转角度重置为0度
        self.rotation = 0.0
        self.redraw()

    def set_font(self, family):
        # Set the font family used for on-canvas text /
        # キャンバス上のテキストに使用するフォントファミリを設定 /
        # 设置Canvas上文字使用的字体家族
        self.font_family = family
        self.redraw()

    def get_view_state(self):
        # Capture and return current view state as a dict for later restoration /
        # 現在のビュー状態を後で復元できるよう辞書として取得・返却 /
        # 获取当前视图状态并返回为字典，供后续恢复使用
        return {
            'center': self.center.copy(),
            'scale': self.scale,
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'rotation': self.rotation,
        }

    def set_view_state(self, state):
        # Restore view state from a previously captured state dict /
        # 以前保存した状態辞書からビュー状態を復元 /
        # 从之前保存的状态字典恢复视图状态
        if state is None:
            return
        self.center = state['center'].copy()
        self.scale = state['scale']
        self.scale_x = state['scale_x']
        self.scale_y = state['scale_y']
        self.rotation = state['rotation']
        if self.lock_y_center:
            self.center[1] = 0
        self._view_fitted = True
        self.redraw()

    def set_grid_mode(self, mode):
        # Switch grid display mode: 'fixed' / 'movable' / 'none' /
        # グリッド表示モードを切り替え：'fixed' / 'movable' / 'none' /
        # 切换网格显示模式：'fixed' / 'movable' / 'none'
        self.grid_mode = mode
        self.redraw()

    def redraw(self):
        # Full redraw: cancel pending debounced operations, clear canvas, then draw grid, title, renderer content, and scalebar /
        # 全再描画：保留中のデバウンス処理をキャンセルし、キャンバスをクリア後、グリッド・タイトル・レンダラ内容・スケールバーを描画 /
        # 完整重绘：取消待处理的防抖操作，清空画布，然后绘制网格、标题、渲染器内容和比例尺
        if self._zoom_debounce_id is not None:
            self.after_cancel(self._zoom_debounce_id)
        self._zoom_debounce_id = None
        self._pan_deferred = False
        self.canvas.delete('all')
        self._draw_grid()
        if self.title:
            self.canvas.create_text(
                8, 8, anchor='nw', text=self.title,
                fill=self.text_color, font=(self.font_family, 9, 'bold'),
                tags=('fixed',))
        if self.renderer is not None:
            self.renderer(self)
        if self.scalebar:
            self._draw_scalebar()

    def is_interacting(self):
        # Return whether the user is currently performing a pan/zoom/rotate interaction /
        # ユーザーが現在パン・ズーム・回転操作中かどうかを返す /
        # 返回用户是否正在进行平移/缩放/旋转交互操作
        return self._interacting

    def _schedule_hq_redraw(self):
        # Schedule a high-quality (non-debounced) redraw after 150ms to finalize interaction /
        # 操作終了時の高品質（デバウンスなし）再描画を150ms後にスケジュール /
        # 在交互结束后150ms安排一次高质量（非防抖）重绘作为最终渲染
        if self._hq_debounce_id is not None:
            self.after_cancel(self._hq_debounce_id)
        self._hq_debounce_id = self.after(150, self._hq_redraw)

    def _hq_redraw(self):
        # Execute the scheduled high-quality redraw, clearing interaction flag /
        # スケジュールされた高品質再描画を実行し、操作中フラグを解除 /
        # 执行已安排的高质量重绘，并清除交互标志
        self._hq_debounce_id = None
        self._interacting = False
        self.redraw()

    def world_to_screen(self, x, y):
        # Convert a single world coordinate (x, y) to screen pixel coordinates, applying rotation and scale /
        # 1つのワールド座標(x, y)を、回転・拡大率を適用してスクリーン座標に変換 /
        # 将单个世界坐标(x, y)转换为屏幕像素坐标，并应用旋转和缩放
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
        # Convert a screen-space pixel delta to a world-space delta, used during panning to update center /
        # スクリーン空間のピクセル差分をワールド空間の差分に変換。パン操作時の中心更新に使用 /
        # 将屏幕空间的像素偏移量转换为世界空间的偏移量，用于平移时更新视图中心
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        screen_y_sign = 1 if self.y_axis_down else -1
        sx_scale, sy_scale = self._scales()
        wx = -(c * dx / sx_scale + screen_y_sign * s * dy / sy_scale)
        wy = (s * dx / sx_scale - screen_y_sign * c * dy / sy_scale)
        return wx, wy

    def screen_to_world(self, sx, sy):
        # Convert screen pixel coordinates (sx, sy) back to world coordinates, inverse of world_to_screen /
        # スクリーン座標(sx, sy)をワールド座標に逆変換（world_to_screenの逆） /
        # 将屏幕像素坐标(sx, sy)反向转换为世界坐标（world_to_screen的逆运算）
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
        # Return current X and Y scales, respecting independent_scale mode /
        # 現在のX/Y拡大率を返す。independent_scaleモードに応じて個別/同一を切り替え /
        # 返回当前的X/Y缩放比例，根据independent_scale模式返回独立或统一的缩放值
        if self.independent_scale:
            return self.scale_x, self.scale_y
        return self.scale, self.scale

    def _world_to_screen_batch(self, points_np):
        # Batch convert many world points to screen coordinates using numpy for performance /
        # 多数のワールド座標点をnumpyを使って一括でスクリーン座標に変換（高速化） /
        # 使用numpy批量将多个世界坐标点转换为屏幕坐标，以提高性能
        if points_np.size == 0:
            return []
        cx, cy = self.center
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        screen_y_sign = 1 if self.y_axis_down else -1
        sx_scale, sy_scale = self._scales()
        dx = points_np[:, 0] - cx
        dy = points_np[:, 1] - cy
        rx = c * dx - s * dy
        ry = s * dx + c * dy
        sx = width / 2 + rx * sx_scale
        sy = height / 2 + screen_y_sign * ry * sy_scale
        coords = np.empty(sx.size + sy.size, dtype=np.float64)
        coords[0::2] = sx
        coords[1::2] = sy
        return coords.tolist()

    def _get_visible_world_bounds(self, margin=0.35):
        # Compute the visible world bounding box with an extra margin for culling 
        # クリッピング判定用に、余裕分を加えた可視ワールド座標範囲を計算 
        # 计算可见的世界坐标边界框，并附加一个边距以用于裁剪判断
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
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
        # Determine the level-of-detail stride based on current zoom scale to skip points when zoomed far out 
        # 現在のズーム倍率に基づいてLODストライドを決定し、遠視点時に描画点数を間引く 
        # 根据当前缩放比例确定LOD采样步长，在远视角时跳过部分点以提升性能
        if not self.enable_lod:
            return 1
        sx_scale, sy_scale = self._scales()
        effective_scale = min(sx_scale, sy_scale)
        if effective_scale >= 0.5:
            return 1
        elif effective_scale >= 0.1:
            return 2
        elif effective_scale >= 0.01:
            return 5
        else:
            return 10

    def line(self, points, fill=None, width=1):
        # Draw a polyline with viewport culling, segment splitting, and LOD optimization /
        # ビューポートクリッピング、セグメント分割、LOD最適化を行って折れ線を描画 /
        # 绘制折线，采用视口裁剪、分段分割和LOD优化策略
        pts = np.asarray(points)
        if pts.size == 0 or len(pts) < 2:
            return

        # 1. Get the world coordinate bounds of the visible screen area /
        # 1. 可視画面範囲のワールド座標境界を取得 /
        # 1. 获取屏幕视窗的世界坐标边界
        xmin, ymin, xmax, ymax = self._get_visible_world_bounds()

        # 2. Find mask and indices of points within the current viewport /
        # 2. 現在のビューポート内にある点のマスクとインデックスを抽出 /
        # 2. 找出当前视口范围内的点的掩码与索引
        mask = (pts[:, 0] >= xmin) & (pts[:, 0] <= xmax) & \
               (pts[:, 1] >= ymin) & (pts[:, 1] <= ymax)
        visible_idx = np.where(mask)[0]

        # Note: Changed the original < 2 condition to == 0 /
        #        If only 1 point is on screen, extending to 2 adjacent points yields 3 points total,
        #        which is enough to form a line segment that passes through a corner of the viewport /
        # 注意：以前の < 2 条件を == 0 に変更 /
        #        画面内に1点だけ存在する場合、外側に2点拡張すれば計3点となり、ビューポート隅を通過する線分を描画可能 /
        # 注意：这里将原先的 < 2 改为了 == 0 /
        #        因为如果屏幕内仅有1个点，加上向外扩展的2个点，共有3个点，也足以构成穿越角落的线段
        if len(visible_idx) == 0:
            return

        # === Core fix: split discontinuous segments === /
        # === コア修正部：不連続セグメントの分割 === /
        # === 核心修复区：分割不连续区段 ===
        # 3. Find gaps where the index jumps by more than 1, indicating the line left the visible area /
        # 3. インデックス差が1より大きい不連続点（画面外に出た区間）を検出 /
        # 3. 寻找不连续的区段（即跳跃的索引）。差值大于1代表线路曾经离开过屏幕
        breaks = np.where(np.diff(visible_idx) > 1)[0] + 1
        segments = np.split(visible_idx, breaks)

        stride = self._get_lod_stride()

        # 4. Render each continuous segment separately to avoid drawing lines across the screen connecting disjoint segments /
        # 4. 各連続セグメントを個別に描画し、離れた区間同士を画面横断線で結ばないようにする /
        # 4. 分段渲染线段，避免将两个不相连的屏幕内线段跨屏直连
        for seg in segments:
            if len(seg) == 0:
                continue

            # Extend the segment by 1 point on each side to prevent visual gaps at screen edges (equivalent to original extended_mask logic) /
            # 画面端での途切れを防ぐため、セグメントの前後に1点ずつ拡張（従来の extended_mask 同等ロジック） /
            # 向前后各扩展1个点的索引，防止线段在屏幕边缘断开（等同于原版的 extended_mask 逻辑）
            start_idx = max(0, seg[0] - 1)
            end_idx = min(len(pts) - 1, seg[-1] + 1)

            # Slice the data points for the current segment (right side of slice is exclusive, so +1) /
            # 現在のセグメントのデータ点をスライス取得（スライス右端は排他的なため+1） /
            # 使用切片获取当前连续线段的数据点（切片右侧为开区间所以要 +1）
            segment_pts = pts[start_idx : end_idx + 1]

            # Apply Level of Detail (LOD) subsampling to reduce rendering cost at distant zoom levels /
            # Level of Detail (LOD) を適用し、遠視点時のレンダリング負荷を低減 /
            # 应用 Level of Detail (LOD) 降低远视角的渲染开销
            if stride > 1:
                segment_pts = segment_pts[::stride]

            # The extracted segment must contain at least 2 points to draw a line /
            # 抽出家されたセグメントは線を描くために最低2点必要 /
            # 提取的线段点数需满足绘制要求（至少2点）
            if len(segment_pts) < 2:
                continue

            # Convert to screen coordinates and render in batch /
            # スクリーン座標に変換して一括描画 /
            # 转换为屏幕坐标并批量渲染
            coords = self._world_to_screen_batch(segment_pts)
            if len(coords) >= 4:
                self.canvas.create_line(
                    *coords, fill=fill or self.line_color, width=width,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def line_screen(self, coords, fill=None, width=1):
        # Draw a polyline directly from screen-space coordinates (no world transform) /
        # スクリーン座標で直接折れ線を描画（ワールド変換なし） /
        # 直接用屏幕坐标绘制折线（无需世界坐标变换）
        if len(coords) >= 4:
            self.canvas.create_line(
                *coords, fill=fill or self.line_color, width=width,
                capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def get_view_params(self):
        # Package current view parameters into a dict for use by renderers /
        # 現在のビューパラメータをレンダラ用に辞書にまとめる /
        # 将当前视图参数打包为字典，供渲染器使用
        sx_scale, sy_scale = self._scales()
        return {
            'width': max(1, self.canvas.winfo_width()),
            'height': max(1, self.canvas.winfo_height()),
            'center': self.center.copy(),
            'rotation': self.rotation,
            'sx_scale': sx_scale,
            'sy_scale': sy_scale,
            'y_axis_down': self.y_axis_down,
        }

    @staticmethod
    def _world_to_screen_static(points, vp):
        # Static version of world-to-screen batch conversion; used when a view_params dict is available /
        # ワールド→スクリーン一括変換の静的版。view_params辞書が利用可能な場合に使用 /
        # 世界坐标→屏幕坐标批量转换的静态版本；在已有view_params字典时使用
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
        dx = pts[:, 0] - cx
        dy = pts[:, 1] - cy
        rx = c * dx - s * dy
        ry = s * dx + c * dy
        sx = width / 2 + rx * sx_scale
        sy = height / 2 + screen_y_sign * ry * sy_scale
        coords = np.empty(sx.size + sy.size, dtype=np.float64)
        coords[0::2] = sx
        coords[1::2] = sy
        return coords.tolist()

    def point(self, x, y, radius=3, outline=None, fill=None):
        # Draw a single filled circle at the given world coordinate /
        # 指定されたワールド座標に塗りつぶし円を1つ描画 /
        # 在给定的世界坐标处绘制一个实心圆点
        sx, sy = self.world_to_screen(x, y)
        self.canvas.create_oval(
            sx - radius, sy - radius, sx + radius, sy + radius,
            outline=outline or self.line_color, fill=fill or self.background)

    def text(self, x, y, text, anchor='nw', angle=0, offset=(6, -6), font_size=9, fill=None):
        # Draw a text label at the given world coordinate with optional rotation and offset /
        # 指定されたワールド座標にテキストラベルを描画。回転・オフセット指定可 /
        # 在给定的世界坐标处绘制文本标签，支持旋转和偏移
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
        # Dispatch to the appropriate grid drawing method based on current grid_mode /
        # 現在のgrid_modeに応じて適切なグリッド描画メソッドに振り分け /
        # 根据当前grid_mode分派到相应的网格绘制方法
        if self.grid_mode == 'none':
            return
        if self.grid_mode == 'movable':
            self._draw_world_grid_square()
            return
        if self.world_grid:
            self._draw_world_grid()
            return
        # Fallback: draw a simple fixed screen-space grid with 80px spacing /
        # フォールバック：80px間隔のシンプルなスクリーン空間固定グリッドを描画 /
        # 回退方案：绘制简单的80像素间距屏幕空间固定网格
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        spacing = 80
        for x in range(0, width + spacing, spacing):
            self.canvas.create_line(x, 0, x, height, fill=self.grid_color, tags=('fixed',))
        for y in range(0, height + spacing, spacing):
            self.canvas.create_line(0, y, width, y, fill=self.grid_color, tags=('fixed',))

    def _draw_world_grid_square(self):
        # Draw a movable world-space grid with step sizes that adapt to the visible range /
        # 可視範囲に適応したステップサイズで可動式ワールド空間グリッドを描画 /
        # 绘制步长随可见范围自适应的可移动世界空间网格
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
        step = self._grid_step(max(xmax - xmin, ymax - ymin))
        x0 = math.floor(xmin / step) * step
        y0 = math.floor(ymin / step) * step
        x = x0
        while x <= xmax + step:
            p1 = self.world_to_screen(x, ymin)
            p2 = self.world_to_screen(x, ymax)
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=self.grid_color)
            x += step
        y = y0
        while y <= ymax + step:
            p1 = self.world_to_screen(xmin, y)
            p2 = self.world_to_screen(xmax, y)
            self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=self.grid_color)
            y += step

    def _draw_world_grid(self):
        # Draw a world-space grid with axis labels (unit-aware) anchored to fixed screen positions /
        # 軸ラベル付き（単位考慮）のワールド空間グリッドを描画。ラベルは画面上の固定位置に配置 /
        # 绘制带轴标签（带单位）的世界空间网格，标签固定在屏幕位置
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
        xspan = max(xmax - xmin, 1e-6)
        yspan = max(ymax - ymin, 1e-6)
        xmin -= xspan * 0.35
        xmax += xspan * 0.35
        ymin -= yspan * 0.35
        ymax += yspan * 0.35
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
                    fill='#888888', font=(self.font_family, 8),
                    tags=('fixed_y',))
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
                    fill='#888888', font=(self.font_family, 8),
                    tags=('fixed_x',))
            y += ystep

    def _grid_step(self, span):
        # Compute a "nice" grid step size (1, 2, 5, 10 * 10^n) that yields ~8 grid lines across the span /
        # スパン全体で約8本のグリッド線になるような「綺麗な」ステップサイズ (1, 2, 5, 10 × 10^n) を計算 /
        # 计算一个"美观"的网格步长（1, 2, 5, 10 × 10^n），使得跨度上约产生8条网格线
        raw = max(span / 8, 1e-9)
        magnitude = 10 ** math.floor(math.log10(raw))
        for factor in [1, 2, 5, 10]:
            step = factor * magnitude
            if raw <= step:
                return step
        return 10 * magnitude

    def _format_grid_label(self, value, unit):
        # Format a grid axis label with appropriate decimal places based on magnitude /
        # グリッド軸ラベルを値の大きさに応じた適切な小数点桁数で整形 /
        # 根据数值大小用合适的小数位数格式化网格轴标签
        if abs(value) >= 100:
            label = '{:.0f}'.format(value)
        elif abs(value) >= 10:
            label = '{:.1f}'.format(value).rstrip('0').rstrip('.')
        else:
            label = '{:.2f}'.format(value).rstrip('0').rstrip('.')
        return label + (unit if unit else '')

    def _draw_scalebar(self):
        # Draw a scale bar at the bottom-right corner with a friendly rounded length and label /
        # 右下隅に、丸められた見やすい長さとラベル付きのスケールバーを描画 /
        # 在右下角绘制比例尺，使用圆整后的友好长度和标签
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
        self.canvas.create_line(x1, y - tick, x1, y, x2, y, x2, y - tick, fill=self.text_color, width=2, tags=('fixed',))
        self.canvas.create_text(
            (x1 + x2) / 2, y - tick - 4,
            text=self._format_scalebar_label(length),
            fill=self.text_color, font=(self.font_family, 9),
            anchor='s', tags=('fixed',))

    def _friendly_scalebar_length(self, raw_length):
        # Find the nearest "friendly" length value (1, 2, 3, 5 * 10^n) for the scalebar /
        # スケールバー用に最も近い「見やすい」長さの値 (1, 2, 3, 5 × 10^n) を探索 /
        # 为比例尺找到最接近的"友好"长度值（1, 2, 3, 5 × 10^n）
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
        # Format scalebar label: meters for <1000, kilometers for >=1000 /
        # スケールバーラベルの整形：1000未満はメートル、1000以上はキロメートル /
        # 格式化比例尺标签：小于1000用米，大于等于1000用千米
        if length >= 1000:
            km = length / 1000
            if abs(km - round(km)) < 1e-9:
                return '{:.0f}km'.format(km)
            return '{:.1f}km'.format(km).rstrip('0').rstrip('.')
        if abs(length - round(length)) < 1e-9:
            return '{:.0f}m'.format(length)
        return '{:.1f}m'.format(length).rstrip('0').rstrip('.')

    def set_cursor(self, name):
        # Change the mouse cursor appearance over the canvas /
        # キャンバス上のマウスカーソル外観を変更 /
        # 更改Canvas上的鼠标光标样式
        self.canvas.config(cursor=name)

    def _on_resize(self, event=None):
        # Handle canvas resize event by triggering a full redraw /
        # キャンバスリサイズイベントを処理し、全体を再描画 /
        # 处理Canvas大小改变事件，触发完整重绘
        self.redraw()

    def _on_mousewheel(self, event):
        # Handle plain mouse wheel: zoom X-axis (if zoom_x_by_default) or both axes /
        # マウスホイール処理：X軸ズーム（zoom_x_by_default時）または両軸ズーム /
        # 处理普通鼠标滚轮：X轴缩放（若zoom_x_by_default）或双轴缩放
        if not self.interactive:
            return
        self._interacting = True
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        self._zoom(factor, axis='x' if self.zoom_x_by_default else 'both')
        self._schedule_redraw()
        self._schedule_hq_redraw()

    def _on_shift_mousewheel(self, event):
        # Handle Shift+MouseWheel: Y-axis zoom (independent scale mode) or view rotation (rotate mode) /
        # Shift+マウスホイール処理：Y軸ズーム（independent_scale時）またはビュー回転 /
        # 处理Shift+鼠标滚轮：Y轴缩放（独立缩放模式）或视图旋转
        if not self.interactive:
            return
        self._interacting = True
        if self.independent_scale:
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            self._zoom(factor, axis='y')
            self._schedule_redraw()
            self._schedule_hq_redraw()
            return
        if self.rotate_enabled:
            self.rotation += math.radians(5 if event.delta > 0 else -5)
            self._schedule_redraw()
            self._schedule_hq_redraw()

    def _on_control_mousewheel(self, event):
        # Handle Ctrl+MouseWheel: zoom the complementary axis (opposite of default zoom axis) /
        # Ctrl+マウスホイール処理：デフォルトと補完的な軸方向にズーム /
        # 处理Ctrl+鼠标滚轮：在默认缩放轴的互补方向上进行缩放
        if not self.interactive:
            return
        self._interacting = True
        if self.independent_scale:
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            self._zoom(factor, axis='both' if self.zoom_x_by_default else 'x')
            self._schedule_redraw()
            self._schedule_hq_redraw()

    def _zoom(self, factor, axis='both'):
        # Apply a zoom factor to the specified axis (or both), clamped to valid range /
        # 指定軸（または両軸）にズーム倍率を適用し、有効範囲にクランプ /
        # 对指定轴（或双轴）应用缩放因子，并钳制在有效范围内
        self._view_fitted = True
        if self.independent_scale:
            if axis in ['both', 'x']:
                self.scale_x = max(0.001, min(self.scale_x * factor, 10000))
            if axis in ['both', 'y']:
                self.scale_y = max(0.001, min(self.scale_y * factor, 10000))
        else:
            self.scale = max(0.001, min(self.scale * factor, 10000))

    def _schedule_redraw(self):
        # Schedule a debounced redraw after 50ms to coalesce rapid zoom events /
        # 高速なズーム操作を統合するため、50ms後にデバウンス再描画をスケジュール /
        # 安排50ms后的防抖重绘，以合并快速连续的缩放事件
        if self._zoom_debounce_id is not None:
            self.after_cancel(self._zoom_debounce_id)
        self._zoom_debounce_id = self.after(50, self._debounced_redraw)

    def _debounced_redraw(self):
        # Execute the debounced redraw (called after a quiet period during zoom) /
        # デバウンス再描画を実行（ズーム操作停止後に呼ばれる） /
        # 执行防抖重绘（在缩放操作静默后被调用）
        self._zoom_debounce_id = None
        self.redraw()

    def _start_pan(self, event):
        # Initialize pan interaction: record drag start position and cancel pending HQ redraw /
        # パン操作を開始：ドラッグ開始位置を記録し、保留中の高品質再描画をキャンセル /
        # 开始平移交互：记录拖拽起始位置，取消待处理的高质量重绘
        if not self.interactive:
            return
        self._interacting = True
        if self._hq_debounce_id is not None:
            self.after_cancel(self._hq_debounce_id)
            self._hq_debounce_id = None
        self._last_drag = (event.x, event.y)
        self._pan_deferred = True

    def _pan(self, event):
        # Perform panning: move all non-fixed items by screen delta, update world center /
        # パン実行：固定タグ以外の全アイテムを画面差分だけ移動し、ワールド中心を更新 /
        # 执行平移：按屏幕偏移量移动所有非固定项，并更新世界坐标中心
        if not self.interactive:
            return
        if self._last_drag is None:
            return
        dx = event.x - self._last_drag[0]
        dy = event.y - self._last_drag[1]
        move_dy = 0 if self.lock_y_center else dy
        self.canvas.move('all', dx, move_dy)
        self.canvas.move('fixed', -dx, -move_dy)
        if move_dy != 0:
            self.canvas.move('fixed_y', 0, -move_dy)
        if dx != 0:
            self.canvas.move('fixed_x', -dx, 0)
        wx, wy = self.screen_to_world_delta(dx, dy)
        self.center[0] += wx
        if not self.lock_y_center:
            self.center[1] += wy
        self._last_drag = (event.x, event.y)

    def _stop_pan(self, event):
        # End pan interaction: if deferred, perform final full redraw to fix pixel drift /
        # パン操作終了：遅延中の場合、ピクセルずれを修正するため最終的な全体再描画を実行 /
        # 结束平移交互：若处于延迟状态，执行最终完整重绘以修正像素漂移
        if self._pan_deferred:
            self._pan_deferred = False
            self._last_drag = None
            self._interacting = False
            self.redraw()

    def _start_rotate(self, event):
        # Initialize rotation interaction: record initial mouse position, cancel pending HQ redraw /
        # 回転操作を開始：マウス初期位置を記録し、保留中の高品質再描画をキャンセル /
        # 开始旋转交互：记录鼠标初始位置，取消待处理的高质量重绘
        if not self.interactive:
            return
        self._interacting = True
        if self._hq_debounce_id is not None:
            self.after_cancel(self._hq_debounce_id)
            self._hq_debounce_id = None
        self._last_rotate = (event.x, event.y)

    def _stop_rotate(self, event):
        # End rotation interaction: schedule a high-quality final redraw /
        # 回転操作終了：高品質な最終再描画をスケジュール /
        # 结束旋转交互：安排一次高质量最终重绘
        self._schedule_hq_redraw()

    def _rotate_drag(self, event):
        # Handle rotation dragging: compute angle between last and current mouse positions, accumulate rotation /
        # 回転ドラッグ処理：前回と現在のマウス位置の角度差を計算し、回転角度に加算 /
        # 处理旋转拖拽：计算上次与当前鼠标位置间的角度差，累加到旋转角度
        if not self.interactive:
            return
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
