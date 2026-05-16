#
#    Copyright 2021 konawasabi
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#

'''Track geometry generator: produces own-track and other-track coordinate arrays from parsed map data /
線形生成器：パース済みマップデータから自軌道・他軌道の座標配列を生成 /
线形生成器：从解析后的地图数据生成自有轨道和其他轨道的坐标数组
'''

# Standard math, NumPy for array operations, and the track coordinate computation module /
# math（標準数学）、NumPy（配列演算）、線形座標計算モジュール /
# 数学库、NumPy用于数组运算，以及轨道坐标计算模块
import math
import numpy as np
from . import trackcoordinate as tc

class TrackGenerator():
    # Generates 3D coordinates (x, y, z, bearing, radius, gradient, cant, etc.) at all control-point distances /
    # 全制御点距離において3D座標（x, y, z, 方位角, 半径, 勾配, カント等）を生成 /
    # 在所有控制点距离处生成3D坐标（x, y, z, 方位角, 半径, 坡度, 超高等）
    def __init__(self,environment,x0=None,y0=None,z0=None,theta0=None,r0=None,gr0=None,dist0=None,unitdist_default=None):
        # Store environment, own-track data, and a copy of the raw control point list /
        # 環境・自軌道データを保持し、生の制御点リストをコピー /
        # 保存环境、自有轨道数据，并复制原始控制点列表
        self.env = environment
        self.data_ownt = self.env.own_track.data
        self.list_cp = self.env.controlpoints.list_cp.copy()

        # Minimum and maximum distances at which map elements exist /
        # マップ要素が存在する距離程の最小, 最大値 /
        # 存在地图元素的距离范围的最小值和最大值
        self.cp_min = min(self.list_cp)
        self.cp_max = max(self.list_cp)

        # Add evenly spaced distance points to improve interpolation quality /
        # 等間隔で距離程を追加する（補間品質の向上） /
        # 添加等间距的距离点以提高插值质量
        equaldist_unit = 25 if unitdist_default is None else unitdist_default
        boundary_margin = 500
        if self.env.cp_arbdistribution != None:
            # Arbitrary equal-interval distribution range explicitly specified /
            # 距離程等間隔配置区間が指定されている場合 /
            # 明确指定了等间距分布范围
            if(len(self.env.station.position) > 0):
                self.env.cp_arbdistribution_default = [max(0, round(min(self.env.station.position.keys()),-2) - boundary_margin),\
                                                        round(max(self.env.station.position.keys()),-2) + boundary_margin,\
                                                        equaldist_unit]
            else:
                self.env.cp_arbdistribution_default = [max(0, round(self.cp_min,-2) - boundary_margin),\
                                                        round(self.cp_max,-2) + boundary_margin,\
                                                        equaldist_unit]
            cp_equaldist = np.arange(self.env.cp_arbdistribution[0],self.env.cp_arbdistribution[1],self.env.cp_arbdistribution[2])
            self.list_cp.extend(cp_equaldist)
            self.list_cp = sorted(list(set(self.list_cp)))
        elif(len(self.env.station.position) > 0):
            # Stations are set: add equal-spacing points ±boundary_margin around stations /
            # 駅が設定されている区間or距離程が存在する区間の前後boundary_margin mに追加 /
            # 有车站设置：在车站前后boundary_margin米范围内添加等间距点
            self.stationdist_min = max(0, round(min(self.env.station.position.keys()),-2) - boundary_margin)
            self.stationdist_max = round(max(self.env.station.position.keys()),-2) + boundary_margin
            cp_equaldist = np.arange(self.stationdist_min,self.stationdist_max,equaldist_unit)
            self.list_cp.extend(cp_equaldist)
            self.list_cp = sorted(list(set(self.list_cp)))

            self.env.cp_arbdistribution = [self.stationdist_min,self.stationdist_max,equaldist_unit]
            self.env.cp_arbdistribution_default = self.env.cp_arbdistribution
            self.env.cp_defaultrange = [self.stationdist_min,self.stationdist_max]
        else:
            # No stations: add equal-spacing points around the min/max control points /
            # 駅なし：制御点の最小/最大値を中心に等間隔点を追加 /
            # 无车站：在控制点最小/最大值周围添加等间距点
            cp_equaldist_min = max(0, round(self.cp_min,-2) - boundary_margin)
            cp_equaldist = np.arange(cp_equaldist_min,round(self.cp_max,-2) + boundary_margin,equaldist_unit)
            self.list_cp.extend(cp_equaldist)
            self.list_cp = sorted(list(set(self.list_cp)))

            self.env.cp_arbdistribution = [cp_equaldist_min,round(self.cp_max,-2) + boundary_margin,equaldist_unit]
            self.env.cp_arbdistribution_default = self.env.cp_arbdistribution
            self.env.cp_defaultrange = [self.env.cp_arbdistribution[0],self.env.cp_arbdistribution[1]]

        # Information about the last processed position (carried forward during generation) /
        # 前回処理した地点の情報（生成中に引き継がれる） /
        # 上一处理位置的信息（在生成过程中传递）
        self.last_pos = {}
        self.last_pos['x']               = x0     if x0     != None else 0
        self.last_pos['y']               = y0     if y0     != None else 0
        self.last_pos['z']               = z0     if z0     != None else 0
        self.last_pos['theta']           = theta0 if theta0 != None else 0
        self.last_pos['radius']          = r0     if r0     != None else 0
        self.last_pos['gradient']        = gr0    if gr0    != None else 0
        self.last_pos['distance']        = dist0  if dist0  != None else min(self.list_cp)
        self.last_pos['interpolate_func'] = 'line'
        self.last_pos['cant']            = 0
        self.last_pos['center']          = 0
        self.last_pos['gauge']           = 0

        # Separate tracking of radius-only state for transition curve computation /
        # 緩和曲線計算用に半径のみの状態を個別追跡 /
        # 单独追踪仅半径状态以用于过渡曲线计算
        self.radius_lastpos = {}
        self.radius_lastpos['distance'] = self.last_pos['distance']
        self.radius_lastpos['theta']    = self.last_pos['theta']
        self.radius_lastpos['radius']   = self.last_pos['radius']

        # List for storing resulting coordinate information (11 columns per row) /
        # 座標情報を格納するリスト（1行あたり11列） /
        # 用于存储最终坐标信息的列表（每行11列）
        self.result = np.zeros((len(self.list_cp), 11), dtype=np.float64)

        # List for storing curve radius vs. distance for the profile chart /
        # 縦断面図曲線半径情報を格納するリスト /
        # 用于存储纵断面图曲线半径相对距离的列表
        self.radius_dist = []

    def generate_owntrack(self):
        '''Generate own-track coordinate data for all control-point distances (self.list_cp).
        self.env: Environment object containing map elements.
        Result stored in self.result as [[distance,x,y,z,theta,radius,gradient,interpolate_func,cant,center,gauge],...].
        /
        マップ要素が存在する全ての距離程(self.list_cp)に対して自軌道の座標データを生成する。
        self.env: マップ要素が格納されたEnvironmentオブジェクト。
        結果はself.result に[[distance,xpos,ypos,zpos,theta,radius,gradient,interpolate_func,cant,center,gauge],[...],...]として格納する。
        /
        为所有控制点距离(self.list_cp)生成自有轨道坐标数据。
        self.env: 包含地图元素的Environment对象。
        结果存储于self.result，格式为[[distance,x,y,z,theta,radius,gradient,interpolate_func,cant,center,gauge],...]。
        '''
        # Create track pointers for each map element type /
        # 各マップ要素タイプ用のTrackPointerを作成 /
        # 为每种地图元素类型创建TrackPointer
        radius_p      = TrackPointer(self.env,'radius')
        gradient_p    = TrackPointer(self.env,'gradient')
        turn_p        = TrackPointer(self.env,'turn')
        interpolate_p = TrackPointer(self.env,'interpolate_func')
        cant_p        = TrackPointer(self.env,'cant')
        center_p      = TrackPointer(self.env,'center')
        gauge_p       = TrackPointer(self.env,'gauge')

        # Instantiate geometry calculators: gradient, curve, and cant /
        # 幾何計算機をインスタンス化：勾配、曲線、カント /
        # 实例化几何计算器：坡度、曲线、超高
        grad_gen  = tc.gradient_intermediate()
        curve_gen = tc.curve_intermediate()
        cant_gen  = tc.Cant(cant_p, self.data_ownt, self.last_pos)

        # Local variable cache: reduce dict access overhead inside the loop /
        # ローカル変数キャッシュ: dictアクセスを減らしてループ内のオーバーヘッドを低減 /
        # 局部变量缓存: 减少循环内字典访问以降低开销
        data = self.data_ownt
        lp = self.last_pos
        rlp = self.radius_lastpos
        list_cp = self.list_cp

        if not __debug__:
            # When -O option is specified: set up numpy warning tracing /
            # -O オプションが指定されている時のみ、デバッグ情報を処理 /
            # 仅在指定了-O选项时：设置numpy警告追踪
            def raise_warning_position(err,flag):
                # Print distance at which a RuntimeWarning occurred /
                # numpy RuntimeWarning発生時に当該点の距離程を印字 /
                # 打印发生RuntimeWarning所在点的距离
                raise RuntimeWarning('Numpy warning: '+str(err)+', '+str(flag)+' at '+str(dist))
            def print_warning_position(err,flag):
                print('Numpy warning: '+str(err)+', '+str(flag)+' at '+str(dist))
            np.seterr(all='call')
            np.seterrcall(print_warning_position)
            #np.seterrcall(raise_warning_position)

        #import pdb
        #pdb.set_trace()

        # Main loop: generate coordinates for each control-point distance /
        # メインループ：各制御点距離について座標を生成 /
        # 主循环：为每个控制点距离生成坐标
        for i, dist in enumerate(list_cp):

            # --- Process curve.setfunction (interpolation function) --- /
            # curve.setfunction に対する処理 /
            # 处理 curve.setfunction（插值函数）
            while (interpolate_p.onNextpoint(dist)):
                # Has the current element interval endpoint been reached? /
                # 注目している要素区間の終端に到達？ /
                # 是否已到达当前关注的元素区间终点？
                lp['interpolate_func'] = data[interpolate_p.pointer['next']]['value']
                interpolate_p.seeknext()

            # --- Process curve.setcenter --- /
            # curve.setcenter に対する処理 /
            # 处理 curve.setcenter
            center_tmp = lp['center']
            while (center_p.onNextpoint(dist)):
                center_tmp = data[center_p.pointer['next']]['value']
                center_p.seeknext()

            # --- Process curve.setgauge --- /
            # curve.setgauge に対する処理 /
            # 处理 curve.setgauge
            gauge_tmp = lp['gauge']
            while (gauge_p.onNextpoint(dist)):
                gauge_tmp = data[gauge_p.pointer['next']]['value']
                gauge_p.seeknext()

            # --- Process radius (curve alignment) --- /
            # radiusに対する処理 /
            # 处理半径（曲线线形）
            _c_theta = lp['theta']
            _c_ds = dist - lp['distance']

            # Optimization: batch-compute long straight segments with numpy /
            # 高速化: 長い直線区間をnumpyで一括計算 /
            # 优化：使用numpy批量计算长直线段
            if lp['radius'] == 0 and _c_ds > 0:
                _rn = radius_p.pointer['next']
                _gn = gradient_p.pointer['next']
                _tn = turn_p.pointer['next']
                _ipn = interpolate_p.pointer['next']
                _ctn = center_p.pointer['next']
                _ggn = gauge_p.pointer['next']
                _can = cant_p.pointer['next']
                _next_r = data[_rn]['distance'] if _rn is not None else float('inf')
                _next_g = data[_gn]['distance'] if _gn is not None else float('inf')
                _next_t = data[_tn]['distance'] if _tn is not None else float('inf')
                _next_ip = data[_ipn]['distance'] if _ipn is not None else float('inf')
                _next_ct = data[_ctn]['distance'] if _ctn is not None else float('inf')
                _next_gg = data[_ggn]['distance'] if _ggn is not None else float('inf')
                _next_ca = data[_can]['distance'] if _can is not None else float('inf')
                # Find the nearest upcoming change point /
                # 最も近い次回変化点を求める /
                # 找到最近的下一个变化点
                _next_change = min(_next_r, _next_g, _next_t, _next_ip, _next_ct, _next_gg, _next_ca)
                _rad_const = _rn is None or data[_rn]['value'] == 'c'
                _grad_const = _gn is None or data[_gn]['value'] == 'c'
                if _rad_const and _grad_const and _next_change > dist:
                    _batch_end = i
                    while _batch_end < len(list_cp) and list_cp[_batch_end] < _next_change:
                        _batch_end += 1
                    _bsize = _batch_end - i
                    if _bsize >= 5:
                        # Use numpy cumulative sum to batch-compute straight segment coordinates /
                        # numpy累積和で直線区間の座標を一括計算 /
                        # 使用numpy累加和批量计算直线段坐标
                        _bd = np.array(list_cp[i:_batch_end], dtype=np.float64)
                        _ds = np.empty(_bsize, dtype=np.float64)
                        _ds[0] = _bd[0] - lp['distance']
                        if _bsize > 1:
                            _ds[1:] = np.diff(_bd)
                        _ct = math.cos(lp['theta'])
                        _st = math.sin(lp['theta'])
                        _sgr = math.sin(math.atan(lp['gradient'] / 1000))
                        _nx = lp['x'] + _ct * np.cumsum(_ds)
                        _ny = lp['y'] + _st * np.cumsum(_ds)
                        _nz = lp['z'] + _sgr * np.cumsum(_ds)
                        _iff = 0 if lp['interpolate_func'] == 'sin' else 1
                        for _j in range(_bsize):
                            _idx = i + _j
                            self.result[_idx] = [_bd[_j], _nx[_j], _ny[_j], _nz[_j],
                                                lp['theta'], 0, lp['gradient'],
                                                _iff, lp['cant'], lp['center'], lp['gauge']]
                        lp['x'] = _nx[-1]
                        lp['y'] = _ny[-1]
                        lp['z'] = _nz[-1]
                        lp['distance'] = _bd[-1]
                        continue

            # Advance radius pointer past any segments whose end lies before 'dist' /
            # distより手前で終了する半径区間を進める /
            # 推进半径指针，跳过在dist之前结束的区段
            while (radius_p.overNextpoint(dist)):
                # Has the current element's interval end been exceeded? /
                # 注目している要素区間の終端を超えたか？ /
                # 当前关注的元素区间终点是否已被超越？
                if(radius_p.seekoriginofcontinuous(radius_p.pointer['next']) != None):
                    lp['radius']         = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['value']
                    rlp['radius']   = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['value']
                    rlp['distance'] = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['distance']
                    rlp['theta']    = lp['theta']
                radius_p.seeknext()

            _c_theta = lp['theta']
            _c_ds = dist - lp['distance']

            if(radius_p.pointer['last'] is None):
                # Before the first curve element /
                # 最初のcurve要素に到達していない場合 /
                # 尚未到达第一个曲线元素时
                if(radius_p.pointer['next'] is None):
                    # No curve elements exist in the map /
                    # curve要素が存在しないマップの場合 /
                    # 地图中不存在曲线元素时
                    if(lp['radius'] == 0):
                        x = math.cos(_c_theta) * _c_ds
                        y = math.sin(_c_theta) * _c_ds
                        tau = 0
                        radius = lp['radius']
                    else:
                        [x, y], tau =curve_gen.circular_curve(self.cp_max - self.cp_min,\
                                                                _c_theta,\
                                                                _c_ds)
                        radius = lp['radius']
                elif(lp['radius'] == 0):
                    x = math.cos(_c_theta) * _c_ds
                    y = math.sin(_c_theta) * _c_ds
                    tau = 0
                    radius = lp['radius']
                else:
                    [x, y], tau =curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - self.cp_min,\
                                                            _c_theta,\
                                                            _c_ds)
                    radius = lp['radius']
            elif(radius_p.pointer['next'] is None):
                # Reached the end of the curve element list /
                # curve要素リスト終端に到達 /
                # 已到达曲线元素列表末尾
                if(lp['radius'] == 0):
                    # Straight track (radius=0) /
                    # 曲線半径が0 (直線)の場合 /
                    # 直线轨道（半径=0）
                    x = math.cos(_c_theta) * _c_ds
                    y = math.sin(_c_theta) * _c_ds
                    tau = 0
                else:
                    # Constant-radius curve /
                    # 一定半径の曲線の場合 /
                    # 定半径曲线
                    [x, y], tau = curve_gen.circular_curve(self.cp_max - lp['distance'],\
                                                         lp['radius'],\
                                                         _c_theta,\
                                                         _c_ds)
                radius = lp['radius']
            else:
                # General case processing /
                # 一般の場合の処理 /
                # 一般情况处理
                if(data[radius_p.pointer['next']]['value'] == 'c'):
                    # Radius unchanged across the current interval? /
                    # 曲線半径が変化しない区間かどうか /
                    # 当前区间内曲线半径是否不变？
                    if(lp['radius'] == 0):
                        # Straight track (radius=0) /
                        # 曲線半径が0 (直線)の場合 /
                        # 直线轨道（半径=0）
                        x = math.cos(_c_theta) * _c_ds
                        y = math.sin(_c_theta) * _c_ds
                        tau = 0
                    else:
                        # Constant-radius curve /
                        # 一定半径の曲線の場合 /
                        # 定半径曲线
                        [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                lp['radius'],\
                                                                _c_theta,\
                                                                _c_ds)
                    radius = lp['radius']
                else:
                    # Radius changes across the current interval /
                    # 曲線半径が変化する場合 /
                    # 当前区间内曲线半径发生变化
                    if(data[radius_p.pointer['next']]['flag'] == 'i' or data[radius_p.pointer['last']]['flag'] == 'bt'):
                        # interpolate flag present /
                        # interpolateフラグがある /
                        # 存在interpolate标志
                        if(rlp['radius'] != data[radius_p.pointer['next']]['value']):
                            # Different radii before/after the interval → output transition curve /
                            # 注目区間前後で異なる曲線半径を取るなら緩和曲線を出力 /
                            # 区间前后半径不同 → 输出过渡曲线
                            pos_last            = curve_gen.transition_curve(data[radius_p.pointer['next']]['distance'] - data[radius_p.pointer['last']]['distance'],\
                                                rlp['radius'],\
                                                data[radius_p.pointer['next']]['value'],\
                                                rlp['theta'],\
                                                lp['interpolate_func'],\
                                                lp['distance'] - data[radius_p.pointer['last']]['distance'])
                            [x, y], tau, radius = curve_gen.transition_curve(data[radius_p.pointer['next']]['distance'] - data[radius_p.pointer['last']]['distance'],\
                                                rlp['radius'],\
                                                data[radius_p.pointer['next']]['value'],\
                                                rlp['theta'],\
                                                lp['interpolate_func'],\
                                                dist - data[radius_p.pointer['last']]['distance'])

                            x -= pos_last[0][0]
                            y -= pos_last[0][1]
                            tau -= pos_last[1]
                        elif(data[radius_p.pointer['next']]['value'] != 0):
                            # Radius unchanged but != 0 → output circular curve /
                            # 曲線半径が変化せず、!=0の場合は円軌道を出力 /
                            # 半径不变且!=0 → 输出圆曲线
                            [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                    lp['radius'],\
                                                                    _c_theta,\
                                                                    _c_ds)
                            radius = lp['radius']
                        else:
                            # Straight track /
                            # 直線軌道を出力 /
                            # 输出直线轨道
                            x = math.cos(_c_theta) * _c_ds
                            y = math.sin(_c_theta) * _c_ds
                            tau = 0
                            radius = lp['radius']
                    else:
                        # No interpolate flag /
                        # interpolateでない /
                        # 非interpolate
                        if(lp['radius'] == 0):
                            # Straight track (radius=0) /
                            # 曲線半径が0 (直線)の場合 /
                            # 直线轨道（半径=0）
                            x = math.cos(_c_theta) * _c_ds
                            y = math.sin(_c_theta) * _c_ds
                            tau = 0
                        else:
                            # Constant-radius curve /
                            # 一定半径の曲線の場合 /
                            # 定半径曲线
                            [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                 lp['radius'],\
                                                                 _c_theta,\
                                                                 _c_ds)
                        radius = lp['radius']

            # --- Process turn (turnout) --- /
            # turnに対する処理 /
            # 处理道岔（turn）
            if(turn_p.pointer['next'] != None):
                if(turn_p.onNextpoint(dist)):
                    tau += np.arctan(data[turn_p.pointer['next']]['value'])
                    turn_p.seeknext()

            # --- Process gradient (vertical alignment) --- /
            # gradientに対する処理 /
            # 处理坡度（纵断面线形）
            while(gradient_p.overNextpoint(dist)):
                if(gradient_p.seekoriginofcontinuous(gradient_p.pointer['next']) != None):
                    lp['gradient']  = data[gradient_p.seekoriginofcontinuous(gradient_p.pointer['next'])]['value']
                    lp['dist_grad'] = data[gradient_p.seekoriginofcontinuous(gradient_p.pointer['next'])]['distance']
                gradient_p.seeknext()

            _g_ds = dist - lp['distance']
            _g_gr = lp['gradient']

            if(gradient_p.pointer['last'] is None):
                # Before the first gradient element /
                # 最初の勾配要素に到達していない /
                # 尚未到达第一个坡度元素
                if(gradient_p.pointer['next'] is None):
                    # No gradient elements in the map /
                    # 勾配が存在しないmapの場合の処理 /
                    # 地图中不存在坡度元素
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                else:
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                gradient = _g_gr
            elif(gradient_p.pointer['next'] is None):
                # Past the last gradient element /
                # 最後の勾配要素を通過した /
                # 已通过最后一个坡度元素
                z = _g_ds * math.sin(math.atan(_g_gr/1000))
                gradient = _g_gr
            else:
                # General case processing /
                # 一般の場合の処理 /
                # 一般情况处理
                if(data[gradient_p.pointer['next']]['value'] == 'c'):
                    # Gradient unchanged across the interval /
                    # 注目区間の前後で勾配が変化しない場合 /
                    # 区间前后坡度不变
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                    gradient = _g_gr
                else:
                    if(data[gradient_p.pointer['next']]['flag'] == 'i' or data[gradient_p.pointer['last']]['flag'] == 'bt'):
                        # interpolate flag present /
                        # interpolateフラグがある場合 /
                        # 存在interpolate标志
                        if(_g_gr != data[gradient_p.pointer['next']]['value']):
                            # Gradients differ → output vertical transition curve /
                            # 注目区間の前後で勾配が変化するなら縦曲線を出力 /
                            # 坡度变化 → 输出竖曲线
                            [tmp_d, z], gradient = grad_gen.transition(data[gradient_p.pointer['next']]['distance'] - lp['distance'],\
                                                    _g_gr,\
                                                    data[gradient_p.pointer['next']]['value'],\
                                                    _g_ds)
                        else:
                            # Constant gradient /
                            # 一定勾配を出力 /
                            # 输出定坡度
                            z = _g_ds * math.sin(math.atan(_g_gr/1000))
                            gradient = _g_gr
                    else:
                        # No interpolate flag → output constant gradient /
                        # interpolateでない場合、一定勾配を出力 /
                        # 非interpolate → 输出定坡度
                        z = _g_ds * math.sin(math.atan(_g_gr/1000))
                        gradient = _g_gr

            # --- Process Cant (superelevation) --- /
            # Cantに対する処理 /
            # 处理超高（Cant）
            cant_tmp = cant_gen.process(dist, lp['interpolate_func'])

            # Update last position state for the next iteration /
            # 地点情報を更新（次イテレーション用） /
            # 更新位置状态信息（用于下一次迭代）
            lp['x']       += x
            lp['y']       += y
            lp['z']       += z
            lp['theta']   += tau
            lp['radius']   = radius
            lp['gradient'] = gradient
            lp['distance'] = dist
            lp['cant']            = cant_tmp
            lp['center']          = center_tmp
            lp['gauge']           = gauge_tmp

            # Store the result row for this control point /
            # この制御点の結果行を保存 /
            # 存储该控制点的结果行
            self.result[i] = [dist,
                lp['x'],
                lp['y'],
                lp['z'],
                lp['theta'],
                lp['radius'],
                lp['gradient'],
                0 if lp['interpolate_func'] == 'sin' else 1,
                lp['cant'],
                lp['center'],
                lp['gauge']]

        return self.result

    def generate_curveradius_dist(self):
        # Generate curve radius vs. distance array for the profile (vertical) chart /
        # 縦断面図用の曲線半径対距離の配列を生成 /
        # 生成纵断面图用的曲线半径-距离数组
        radius_p = TrackPointer(self.env,'radius')

        previous_pos_radius = {'is_bt':False, 'value':0}

        # Start with radius=0 at the beginning of track /
        # 線路始端は半径0で開始 /
        # 线路线路起点处半径=0
        self.radius_dist.append([min(self.list_cp),0])

        while (radius_p.pointer['next'] != None):
            new_radius = self.data_ownt[radius_p.pointer['next']]['value']
            flag = self.data_ownt[radius_p.pointer['next']]['flag']
            distance = self.data_ownt[radius_p.pointer['next']]['distance']
            if (new_radius == 'c'):
                # 'c' means radius unchanged — carry forward previous value /
                # 'c'（直前コマンドと同値） → 前の値を引き継ぐ /
                # 'c'（与前一命令相同）→ 继承前一值
                new_radius = previous_pos_radius['value']
                self.radius_dist.append([distance,new_radius])
            else:
                if(previous_pos_radius['is_bt']):
                    # Previous point is begin_transition → output transition curve /
                    # 直前点がbegin_transitionなら、緩和曲線を出力 /
                    # 前一点为begin_transition → 输出过渡曲线
                    self.radius_dist.append([distance,new_radius])
                else:
                    if(flag == 'i'):
                        # Current point is interpolate → output transition curve /
                        # 現在点がinterpolateなら、緩和曲線を出力 /
                        # 当前点为interpolate → 输出过渡曲线
                        self.radius_dist.append([distance,new_radius])
                    else:
                        # Step change in radius → insert two points for the instant jump /
                        # 階段状に変化する半径を出力（2点挿入で瞬間変化を表現） /
                        # 半径阶跃变化 → 插入两个点来表示瞬间跳变
                        self.radius_dist.append([distance,previous_pos_radius['value']])
                        self.radius_dist.append([distance,new_radius])

            previous_pos_radius['value'] = new_radius
            previous_pos_radius['is_bt'] = True if flag == 'bt' else False
            radius_p.seeknext()

        # End with radius=0 at the end of track /
        # 線路終端は半径0で終了 /
        # 线路终点处半径=0
        self.radius_dist.append([max(self.list_cp),0])
        return np.array(self.radius_dist)

class TrackPointer():
    # Lightweight pointer that walks through sorted map data entries for a given element key /
    # 指定された要素キーについて、ソート済みマップデータエントリを走査する軽量ポインタ /
    # 轻量级指针，用于遍历指定元素键的排序后地图数据条目
    def __init__(self,environment,target):
        self.pointer = {'last':None, 'next':0}
        self.env = environment
        self.target = target
        self.data = self.env.own_track.data
        self.ix_max = len(self.data) - 1

        # Seek to the first occurrence of the target key /
        # 対象キーが初めて現れる位置を探索 /
        # 查找目标键首次出现的位置
        self.seekfirst()

    def seek(self, ix0):
        '''Search for the index where the target element appears, starting from ix0.
        Returns None if the end of data is reached.
        /
        ix0以降で注目する要素が現れるインデックスを探索。データ終端まで到達した場合はNoneを返す。
        /
        从ix0开始搜索目标元素出现的索引。到达数据末尾时返回None。
        '''
        ix = ix0
        while True:
            if (ix > self.ix_max):
                ix = None
                break
            if(self.data[ix]['key'] != self.target):
                ix+=1
            else:
                break
        return ix

    def seekfirst(self):
        '''Search for the first index where the target element appears and set it to pointer['next'].
        /
        注目する要素が初めて現れるインデックスを探索して、pointer['next']にセットする。
        /
        搜索目标元素首次出现的索引并设置到pointer['next']。
        '''
        self.pointer['next'] = self.seek(0)

    def seeknext(self):
        '''Find the index of the next element and update self.pointer['last'] and ['next'].
        Does nothing if self.pointer['next'] is None.
        /
        次の要素が存在するインデックスを探し、self.pointer['last', 'next']を書き換える。
        self.pointer['next'] is None の場合は何もしない。
        /
        查找下一个元素存在的索引并更新self.pointer['last']和['next']。
        若self.pointer['next']为None则不执行任何操作。
        '''
        if(self.pointer['next'] != None):
            self.pointer['last'] = self.pointer['next']
            self.pointer['next'] = self.seek(self.pointer['next']+1)

    def insection(self,distance):
        '''Check if the given distance lies within the current element interval.
        True if self.pointer['last'] < given distance <= self.pointer['next'].
        /
        注目している要素の区間内かどうか調べる。
        self.pointer['last'] < 与えられたdistance <= self.pointer['next'] ならTrue
        /
        检查给定距离是否位于当前关注元素的区间内。
        若self.pointer['last'] < 给定distance <= self.pointer['next']则返回True。
        '''
        return (self.data[self.pointer['prev']]['distance'] > distance and self.data[self.pointer['next']]['distance'] <= distance)

    def onNextpoint(self,distance):
        '''Check if the given distance is exactly at the end of the current element interval.
        True if given distance == pointer['next'].
        Always False if pointer['next'] is None (end of element list).
        /
        注目している要素区間の終端にいるか調べる。
        与えられたdistance == 注目しているpointer['next'] ならTrue。
        pointer['next'] is None (要素リスト終端に到達した) なら必ずFalse。
        /
        检查给定距离是否恰好位于当前关注元素区间的终点。
        若给定distance == pointer['next']则返回True。
        若pointer['next']为None（已达元素列表末尾）则始终返回False。
        '''
        return (self.data[self.pointer['next']]['distance'] == distance) if self.pointer['next'] != None else False

    def overNextpoint(self,distance):
        '''Check if the given distance has exceeded the current element interval end.
        True if given distance > pointer['next'].
        Always False if pointer['next'] is None (end of element list).
        /
        注目している要素区間を超えたか調べる。
        与えられたdistance > 注目しているpointer['next'] ならTrue。
        pointer['next'] is None (要素リスト終端に到達した) なら必ずFalse。
        /
        检查给定距离是否已超过当前关注元素区间的终点。
        若给定distance > pointer['next']则返回True。
        若pointer['next']为None（已达元素列表末尾）则始终返回False。
        '''
        return (self.data[self.pointer['next']]['distance'] < distance) if self.pointer['next'] != None else False

    def beforeLastpoint(self,distance):
        '''Check if the given distance has not yet reached the current element interval start.
        True if given distance <= pointer['last'].
        Always True if pointer['last'] is None (before the first element).
        /
        注目している要素区間にまだ到達していないか調べる。
        与えられたdistance <= 注目しているpointer['last'] ならTrue。
        pointer['last'] is None (リスト始端の要素地点に到達していない) なら必ずTrue。
        /
        检查给定距离是否尚未到达当前关注元素区间的起点。
        若给定distance <= pointer['last']则返回True。
        若pointer['last']为None（尚未到达列表第一个元素）则始终返回True。
        '''
        return (self.data[self.pointer['last']]['distance'] >= distance) if self.pointer['last'] != None else True

    def seekoriginofcontinuous(self,index):
        '''If the element at the given index has value='c' (same as previously specified),
        backtrack to find the originating element whose value != 'c'.
        Returns None if not found all the way to the beginning of the list.
        /
        注目している要素のvalue=c (直前に指定した値と同一)であった場合、その起源となる要素(value != c)を示すインデックスを返す。
        リストの先頭まで探索しても見つからなかった場合はNoneを返す。
        /
        若给定索引处的元素value='c'（与上一指定值相同），回溯查找其起源元素（value != 'c'）。
        若一直追溯到列表开头仍未找到则返回None。
        '''
        if(index != None):
            while True:
                if(self.data[index]['key'] == self.target and self.data[index]['value'] != 'c'):
                    break
                else:
                    index -= 1
                    if(index < 0):
                        index = None
                        break
        return index

class OtherTrackGenerator():
    # Generates 3D coordinates for other (parallel) tracks by walking both track and own-track position lists /
    # 他軌道データリストと自軌道位置リストの両方を走査して、他軌道の3D座標を生成 /
    # 通过同时遍历其他轨道数据列表和自轨道位置列表来生成其他轨道的3D坐标
    class OtherTrackPointer(TrackPointer):
        # Pointer variant that uses othertrack.data[key] instead of own_track.data /
        # own_track.dataの代わりにothertrack.data[key]を使うポインタの派生版 /
        # 使用othertrack.data[key]而非own_track.data的指针变体
        def __init__(self,environment,target,trackkey):
            super().__init__(environment,target)
            self.data = environment.othertrack.data[trackkey]
            self.ix_max = len(self.data) - 1
            self.seekfirst()

    def __init__(self,environment,trackkey):
        self.env = environment
        self.trackkey = trackkey
        self.data = self.env.othertrack.data[trackkey]
        self.owntrack_position = self.env.owntrack_pos
        self.distrange={'min':min(self.data, key=lambda x: x['distance'])['distance'], 'max':max(self.data, key=lambda x: x['distance'])['distance']}

        # Last/next position state for interpolating across intervals /
        # 前回/今回の位置情報（区間補間用） /
        # 上一/下一位置状态（用于区间插值）
        self.pos = {'last':{}, 'next':{}}
        for key in ['x.position','x.radius','x.distance','y.position','y.radius','y.distance','interpolate_func','cant','center','gauge']:
            self.pos['last'][key] = 0
            self.pos['next'][key] = 0

    def generate(self):
        '''Compute other-track coordinates.
        Targets the track specified by the key given at instance creation.
        /
        他軌道座標を計算する。
        対象はインスタンス作成時に指定したkeyの軌道。
        /
        计算其他轨道坐标。
        目标是实例创建时指定的key对应的轨道。
        '''
        # Create track element pointers for each property /
        # 軌道要素ポインタの作成 /
        # 为每种属性创建轨道元素指针
        trackptr = {}
        for tpkey in ['x.position','x.radius','y.position','y.radius','interpolate_func','cant','center','gauge']:
            trackptr[tpkey] = self.OtherTrackPointer(self.env,tpkey,self.trackkey)

        # Coordinate computation and cant computation objects /
        # 座標計算オブジェクト、カント計算オブジェクト /
        # 坐标计算对象和超高计算对象
        track_gen = tc.OtherTrack()
        cant_gen  = tc.Cant(trackptr['cant'], self.data, self.pos['last'])

        num_owntrack = len(self.owntrack_position)
        self.result = np.zeros((num_owntrack, 8), dtype=np.float64)
        result_idx = 0

        #tp_keys = ['x.position','x.radius','y.position','y.radius']
        #skip_dimension = {'x.position':False, 'x.radius':False, 'y.position':False, 'y.radius':False}
        # Initialize pointer values: set initial last/next positions for each property /
        # ポインタ初期値設定：各プロパティの初期last/next値を設定 /
        # 初始化指针值：为每个属性设置初始的last/next值
        for tpkey in trackptr.keys():
            if trackptr[tpkey].pointer['next'] != None:
                for k in ['last','next']:
                    newval = self.data[trackptr[tpkey].pointer['next']]['value']
                    self.pos[k][tpkey] = newval if newval != 'c' else 0

        # Process each own-track position to compute corresponding other-track coordinates /
        # 各自軌道位置について、対応する他軌道座標を計算 /
        # 处理每个自有轨道位置，计算对应的其他轨道坐标
        for element in self.owntrack_position:
            if self.distrange['min'] > element[0]:
                # Skip positions before the target track appears /
                # 対象となる軌道が最初に現れる距離程にまだ達していないか？ → スキップ /
                # 跳过尚未到达目标轨道首次出现距离的位置
                continue

            # Advance position/radius pointers past elements whose end lies before element[0] /
            # ポインタを進める（element[0]より手前で終わる要素を通過） /
            # 推进指针（跳过在element[0]之前结束的元素）
            for tpkey in ['x.position','x.radius','y.position','y.radius']:
                while trackptr[tpkey].overNextpoint(element[0]):
                    trackptr[tpkey].seeknext()
                    self.pos['last'][tpkey] = self.pos['next'][tpkey]
                    if trackptr[tpkey].pointer['next'] != None:
                        k = 'next'
                        newval = self.data[trackptr[tpkey].pointer[k]]['value']
                        self.pos[k][tpkey] = newval if newval != 'c' else self.pos['last'][tpkey]

            # Advance interpolate_func / center / gauge pointers (exact same point as element[0]) /
            # interpolate_func/center/gauge用ポインタを進める（element[0]と同一点） /
            # 推进interpolate_func/center/gauge指针（与element[0]相同点）
            for tpkey in ['interpolate_func','center','gauge']:
                while trackptr[tpkey].onNextpoint(element[0]):
                    trackptr[tpkey].seeknext()
                    self.pos['last'][tpkey] = self.pos['next'][tpkey]
                    if trackptr[tpkey].pointer['next'] != None:
                        k = 'next'
                        newval = self.data[trackptr[tpkey].pointer[k]]['value']
                        self.pos[k][tpkey] = newval if newval != 'c' else self.pos['last'][tpkey]

            # --- Compute X (horizontal) absolute position --- /
            # X方向(水平)絶対座標の計算 /
            # 计算X（水平）绝对坐标
            if trackptr['x.position'].pointer['last'] != None and trackptr['x.position'].pointer['next'] != None:
                for k in ['last','next']:
                    self.pos[k]['x.distance'] = self.data[trackptr['x.position'].pointer[k]]['distance']

                temp_result_X = track_gen.absolute_position_X(self.pos['next']['x.distance'] - self.pos['last']['x.distance'],\
                                                                self.pos['last']['x.radius'],\
                                                                self.pos['last']['x.position'],\
                                                                self.pos['next']['x.position'],\
                                                                element[0] - self.pos['last']['x.distance'],\
                                                                element)
            else:
                # Fallback: compute X position using own-track bearing and last known relative X /
                # 自軌道方位角と最後の相対X位置で代替計算 /
                # 回退：使用自有轨道方位角和最后已知相对X位置计算
                theta = element[4]
                x_pos = self.pos['last']['x.position']
                temp_result_X = [-math.sin(theta) * x_pos + element[1], math.cos(theta) * x_pos + element[2]]

            # --- Compute Y (vertical) absolute position --- /
            # Y方向(鉛直)絶対座標の計算 /
            # 计算Y（垂直）方向绝对坐标
            if trackptr['y.position'].pointer['last'] != None and trackptr['y.position'].pointer['next'] != None:
                for k in ['last','next']:
                    self.pos[k]['y.distance'] = self.data[trackptr['y.position'].pointer[k]]['distance']
                temp_result_Y = track_gen.absolute_position_Y(self.pos['next']['y.distance'] - self.pos['last']['y.distance'],\
                                                                self.pos['last']['y.radius'],\
                                                                self.pos['last']['y.position'],\
                                                                self.pos['next']['y.position'],\
                                                                element[0] - self.pos['last']['y.distance'],\
                                                                element)
            else:
                temp_result_Y = [0,self.pos['last']['y.position']]+ np.array([element[0],element[3]])
                # Note: if result_Y is [distance, Yval], should the second term be [element[0], element[3]]? /
                # 註：result_Yが[distance, Yval]なら、第二項は[element[0],element[3]ではないか？ /
                # 注：若result_Y为[distance, Yval]，第二项是否应为[element[0], element[3]]？

            # Compute cant value at this position /
            # この位置でのカント値を計算 /
            # 计算该位置处的超高值
            temp_result_cant = cant_gen.process(element[0], self.pos['last']['interpolate_func'])

            # Store the result row /
            # 結果行を格納 /
            # 存储结果行
            self.result[result_idx] = [element[0],
                                temp_result_X[0],
                                temp_result_X[1],
                                temp_result_Y[1],
                                0 if self.pos['last']['interpolate_func'] == 'sin' else 1,
                                temp_result_cant,
                                self.pos['last']['center'],
                                self.pos['last']['gauge']]
            result_idx += 1
        return self.result[:result_idx]
