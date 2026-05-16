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

# NumPy for array operations, project track generator and i18n modules /
# NumPy（配列演算）、プロジェクト内の線形生成・国際化モジュール /
# NumPy用于数组运算，以及项目内的线形生成和国际化模块
import numpy as np
from . import trackgenerator as tgen
from . import i18n


class Mapplot():
    # High-level data preparer: computes plane/profile plot data, station info, speed limits, etc. /
    # 高レベルデータ準備クラス：平面図・縦断面図データ、駅情報、速度制限などを計算 /
    # 高层数据准备类：计算平面图/纵断面图数据、车站信息、限速等
    def __init__(self, env, cp_arbdistribution=None, unitdist_default=None):
        # Store the environment and configure arbitrary distribution / default range for control points /
        # 環境を保持し、制御点の任意分布/デフォルト範囲を設定 /
        # 存储环境并配置控制点的任意分布/默认范围
        self.environment = env
        self.environment.cp_arbdistribution = cp_arbdistribution
        self.environment.cp_defaultrange = [0, 0]

        # Generate own-track geometry and curve radius data via TrackGenerator /
        # TrackGeneratorを用いて自軌道の線形および曲線半径データを生成 /
        # 通过TrackGenerator生成自有轨道线形和曲线半径数据
        trackgenerator = tgen.TrackGenerator(self.environment, unitdist_default=unitdist_default)
        self.environment.owntrack_pos = trackgenerator.generate_owntrack()
        self.environment.owntrack_curve = trackgenerator.generate_curveradius_dist()

        # Initialize as empty dict; other tracks are lazily computed on first plot request /
        # 空辞書で初期化。他軌道は初回描画要求時に遅延計算する /
        # 初始化为空字典，在此不预先计算他轨道，改为在绘图时按需懒加载
        self.environment.othertrack_pos = {}

        # Set up initial distance ranges for both plane and vertical views /
        # 平面図・縦断面図の両方に初期距離範囲を設定 /
        # 为平面图和纵断面图分别设置初始距离范围
        self.distrange = {}
        self.distrange['plane'] = [
            min(self.environment.owntrack_pos[:, 0]),
            max(self.environment.owntrack_pos[:, 0])
        ]
        self.distrange['vertical'] = [
            min(self.environment.owntrack_pos[:, 0]),
            max(self.environment.owntrack_pos[:, 0])
        ]

        # Record the origin distance, height, and angle at the starting point for relative transforms /
        # 起点の原点距離・標高・角度を記録し、相対変換に使用 /
        # 记录起点处的原点距离、标高和角度，用于相对变换
        start_distance = min(self.environment.owntrack_pos[:, 0])
        self.distance_origin = start_distance
        self.height_origin = self.environment.owntrack_pos[
            self.environment.owntrack_pos[:, 0] == start_distance
        ][0][3]
        self.origin_angle = self.environment.owntrack_pos[
            self.environment.owntrack_pos[:, 0] == min(self.environment.owntrack_pos[:, 0])
        ][0][4]

        # Extract station distances and positions; flag whether any station data exists /
        # 駅の距離程と位置を抽出。駅データの有無をフラグ化 /
        # 提取车站距离和位置，并标记是否存在车站数据
        if len(self.environment.station.position) > 0:
            self.station_dist = np.array(list(self.environment.station.position.keys()))
            self.station_pos = self.environment.owntrack_pos[np.isin(self.environment.owntrack_pos[:, 0], self.station_dist)]
            self.nostation = False
        else:
            self.station_dist = np.array([])
            self.station_pos = np.array([])
            self.nostation = True

    def plane_data(self, distmin=None, distmax=None, othertrack_list=None):
        # Prepare all data needed to render the horizontal (plan) view /
        # 平面図（水平ビュー）のレンダリングに必要な全データを準備 /
        # 准备水平（平面）视图渲染所需的全部数据
        if distmin is not None:
            self.distrange['plane'][0] = distmin
        if distmax is not None:
            self.distrange['plane'][1] = distmax

        # Filter own track to the requested distance range /
        # 指定距離範囲に自軌道をフィルタ /
        # 将自有轨道过滤到请求的距离范围
        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['plane'][0],
            self.distrange['plane'][1])
        if len(owntrack) == 0:
            return {'owntrack': np.array([]), 'othertracks': [], 'stations': [], 'speedlimits': [], 'curve_sections': [], 'transition_sections': [], 'bounds': (-1, -1, 1, 1)}

        # Rotate the track so that the origin segment aligns horizontally /
        # 原点区間が水平になるよう軌道を回転 /
        # 旋转轨道使起点段对齐到水平方向
        self.origin_angle = owntrack[0][4]
        owntrack = self.rotate_track(owntrack, -self.origin_angle)

        # Collect other (external) track data for the given track keys /
        # 指定トラックキーについて他軌道データを収集 /
        # 收集指定轨道键对应的其他轨道数据
        othertracks = []
        if othertrack_list is not None:
            for key in othertrack_list:
                key = '' if key == '\\' else key

                # --- Lazy loading: compute other track data on first access --- /
                # --- 遅延読み込み：初回アクセス時に他軌道データを動的計算 --- /
                # --- 按需计算（懒加载）逻辑 ---
                if key not in self.environment.othertrack_pos:
                    gen = tgen.OtherTrackGenerator(self.environment, key)
                    self.environment.othertrack_pos[key] = gen.generate()
                # ------------------------------------------------------------

                # Filter the other track to the overlapping distance range /
                # 重複する距離範囲に他軌道をフィルタ /
                # 将其他轨道过滤到重叠的距离范围
                othertrack = self.environment.othertrack_pos[key]
                othertrack = self._distance_filter(
                    othertrack,
                    max(self.environment.othertrack.cp_range[key]['min'], self.distrange['plane'][0]),
                    min(self.environment.othertrack.cp_range[key]['max'], self.distrange['plane'][1]))
                if len(othertrack) > 0:
                    othertracks.append({
                        'key': key,
                        'points': self.rotate_track(othertrack, -self.origin_angle),
                        'color': self.environment.othertrack_linecolor[key]['current']
                    })

        # Collect station points and rotate to match the view /
        # 駅位置を収集し、ビューに合わせて回転 /
        # 收集车站位置点并按视图旋转
        stations = self._station_points('plane')
        if len(stations) > 0:
            stations = self.rotate_track(stations, -self.origin_angle)

        # Compute bounding box, speed limit visuals, curve sections, and transition sections /
        # バウンディングボックス、速度制限描画、曲線区間、緩和区間を計算 /
        # 计算边界框、限速可视化、曲线段和过渡段
        bounds = self._bounds([owntrack] + [track['points'] for track in othertracks])
        speedlimits = self._speedlimit_plane_data(owntrack)
        curve_sections = self._curve_sections_plane_data(owntrack)
        transition_sections = self._transition_sections_plane_data(owntrack)
        return {
            'owntrack': owntrack,
            'othertracks': othertracks,
            'stations': self._station_labels(stations),
            'speedlimits': speedlimits,
            'curve_sections': curve_sections,
            'transition_sections': transition_sections,
            'bounds': bounds
        }

    def profile_data(self, distmin=None, distmax=None, othertrack_list=None, ylim=None):
        # Prepare all data needed to render the vertical (profile) view /
        # 縦断面図（垂直ビュー）のレンダリングに必要な全データを準備 /
        # 准备纵断面（垂直）视图渲染所需的全部数据
        if distmin is not None:
            self.distrange['vertical'][0] = distmin
        if distmax is not None:
            self.distrange['vertical'][1] = distmax

        # Filter own track and make height relative to origin /
        # 自軌道をフィルタし、標高を原点相対に変換 /
        # 过滤自有轨道并将标高转为相对于原点
        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        owntrack = owntrack.copy()
        if len(owntrack) > 0:
            owntrack[:, 3] = owntrack[:, 3] - self.height_origin

        # Filter curve radius data for the profile distance range /
        # 縦断面距離範囲に曲線半径データをフィルタ /
        # 过滤纵断面距离范围内的曲线半径数据
        curve = self._distance_filter(
            self.environment.owntrack_curve,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        if len(owntrack) == 0:
            return {'owntrack': np.array([]), 'curve': np.array([]), 'othertracks': [], 'stations': [], 'gradient_labels': [], 'radius_labels': [], 'bounds': (-1, -1, 1, 1)}

        # Collect other track data, making height relative to origin /
        # 他軌道データを収集し、標高を原点相対に変換 /
        # 收集其他轨道数据，将标高转为相对于原点
        othertracks = []
        if othertrack_list is not None:
            for key in othertrack_list:
                key = '' if key == '\\' else key

                # --- Lazy loading: compute other track data on first access --- /
                # --- 遅延読み込み：初回アクセス時に他軌道データを動的計算 --- /
                # --- 按需计算（懒加载）逻辑 ---
                if key not in self.environment.othertrack_pos:
                    gen = tgen.OtherTrackGenerator(self.environment, key)
                    self.environment.othertrack_pos[key] = gen.generate()
                # ------------------------------------------------------------

                othertrack = self.environment.othertrack_pos[key]
                othertrack = self._distance_filter(
                    othertrack,
                    max(self.environment.othertrack.cp_range[key]['min'], self.distrange['vertical'][0]),
                    min(self.environment.othertrack.cp_range[key]['max'], self.distrange['vertical'][1]))
                if len(othertrack) > 0:
                    othertrack = othertrack.copy()
                    othertrack[:, 3] = othertrack[:, 3] - self.height_origin
                    othertracks.append({
                        'key': key,
                        'points': othertrack,
                        'color': self.environment.othertrack_linecolor[key]['current']
                    })

        # Determine Y-axis range: either explicit ylim or auto-computed with padding /
        # Y軸範囲を決定：明示的なylim指定、または自動計算＋パディング /
        # 确定Y轴范围：使用显式指定的ylim，或自动计算并添加边距
        if ylim is None:
            heightmin = min(owntrack[:, 3])
            heightmax = max(owntrack[:, 3])
            if heightmax != heightmin:
                ymin = heightmin - (heightmax - heightmin) * 0.2
                ymax = heightmax + (heightmax - heightmin) * 0.1
            else:
                ymin = heightmin - 5
                ymax = heightmax + 5
        else:
            ymin, ymax = ylim

        # Build curve sign data: distance × sign(radius) /
        # 曲線符号データを作成：距離 × sign(半径) /
        # 构建曲线符号数据：距离 × sign(半径)
        curve_points = []
        if len(curve) > 0:
            curve_points = np.array([[row[0], np.sign(row[1])] for row in curve])

        # Prepare station data with relative height /
        # 駅データを相対標高付きで準備 /
        # 准备带相对标高的车站数据
        station_points = self._station_points('vertical')
        station_points = station_points.copy()
        if len(station_points) > 0:
            station_points[:, 3] = station_points[:, 3] - self.height_origin
        station_labels = self._station_labels(station_points)

        # Gather gradient and radius labels/points for the profile chart /
        # 縦断面図用の勾配・曲線半径ラベルと変化点を収集 /
        # 收集纵断面图的坡度和曲线半径标签及变化点
        gradient_labels = self.gradient_labels(ymin)
        gradient_points = self.gradient_change_points(owntrack, ymin)
        radius_labels = self.radius_labels(0, 1)

        # Build separate bounds for profile and radius sub-charts /
        # 縦断面図と曲線半径図の各サブチャートの範囲を構築 /
        # 构建纵断面图和曲线半径图各自子图的范围
        profile_bounds = (
            self.distrange['vertical'][0],
            ymin,
            self.distrange['vertical'][1],
            ymax)
        radius_bounds = (
            self.distrange['vertical'][0],
            -2.2,
            self.distrange['vertical'][1],
            2.2)

        return {
            'owntrack': owntrack,
            'curve': curve_points,
            'othertracks': othertracks,
            'stations': station_labels,
            'gradient_labels': gradient_labels,
            'gradient_points': gradient_points,
            'radius_labels': radius_labels,
            'station_top': ymax,
            'bounds': profile_bounds,
            'radius_bounds': radius_bounds
        }

    def gradient_change_points(self, owntrack, target_y):
        # Collect distance/height pairs where gradient changes occur for drawing vertical lines /
        # 勾配変化点での距離/標高ペアを収集し、縦線描画に使用 /
        # 收集坡度变化点处的距离/标高对，用于绘制垂直线
        points = []
        if len(owntrack) == 0:
            return points
        gradient_distances = sorted(set(
            item['distance'] for item in self.environment.own_track.data
            if item['key'] == 'gradient'
        ))
        for distance in gradient_distances:
            if self.distrange['vertical'][0] <= distance <= self.distrange['vertical'][1]:
                z = np.interp(distance, owntrack[:, 0], owntrack[:, 3])
                points.append({'x': distance, 'z': z, 'target_y': target_y})
        return points

    def gradient_labels(self, ypos):
        # Generate gradient value labels positioned along the profile chart /
        # 縦断面図に沿って勾配値ラベルを生成 /
        # 生成沿纵断面图分布的坡度值标签
        labels = []
        pointer = tgen.TrackPointer(self.environment, 'gradient')
        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        if len(owntrack) == 0:
            return labels

        def append_label(pos_start=None, pos_end=None, value=None):
            # Create a single gradient label at the midpoint of a gradient segment /
            # 勾配区間の中点に1つの勾配ラベルを作成 /
            # 在坡度段的中点创建一个坡度标签
            if pos_end is None:
                pos_end = pointer.data[pointer.pointer['next']]['distance']
            if pos_start is None:
                pos_start = pointer.data[pointer.pointer['last']]['distance']
            if value is None:
                valuecontain = pointer.seekoriginofcontinuous(pointer.pointer['last'])
                value = pointer.data[valuecontain]['value'] if valuecontain is not None else 0
            mid = (pos_start + pos_end) / 2
            if self.distrange['vertical'][0] < mid < self.distrange['vertical'][1]:
                labels.append({'x': mid, 'y': ypos, 'text': str(np.fabs(value)) if value != 0 else i18n.get('label.lv')})

        # Skip gradient entries before the visible distance range /
        # 可視距離範囲より前の勾配エントリをスキップ /
        # 跳过可见距离范围之前的坡度条目
        while pointer.pointer['next'] is not None:
            if pointer.data[pointer.pointer['next']]['distance'] < self.distrange['vertical'][0]:
                pointer.seeknext()
            else:
                break

        # Iterate through gradient entries within the visible range, generating labels per segment /
        # 可視範囲内の勾配エントリを反復処理し、区間ごとにラベルを生成 /
        # 遍历可见范围内的坡度条目，逐段生成标签
        while pointer.pointer['next'] is not None and pointer.data[pointer.pointer['next']]['distance'] <= self.distrange['vertical'][1]:
            if pointer.pointer['last'] is None:
                append_label(pos_start=min(owntrack[:, 0]), value=0)
            elif pointer.data[pointer.pointer['next']]['flag'] == 'bt':
                append_label()
            elif pointer.data[pointer.pointer['next']]['flag'] == 'i':
                if pointer.data[pointer.seekoriginofcontinuous(pointer.pointer['next'])]['value'] == pointer.data[pointer.pointer['last']]['value']:
                    append_label()
            elif pointer.data[pointer.pointer['next']]['flag'] == '':
                if pointer.data[pointer.pointer['last']]['flag'] != 'bt':
                    append_label()
            pointer.seeknext()

        # Emit the final segment label after the last gradient entry /
        # 最終勾配エントリの後に最後の区間ラベルを出力 /
        # 在最后一条坡度条目之后输出末端区间标签
        if pointer.pointer['last'] is None:
            append_label(pos_end=max(owntrack[:, 0]), pos_start=min(owntrack[:, 0]), value=0)
        else:
            append_label(pos_end=max(owntrack[:, 0]))
        return labels

    def radius_labels(self, ypos, yscale):
        # Generate curve radius value labels for the radius chart /
        # 曲線半径図用の半径値ラベルを生成 /
        # 生成曲线半径图的半径值标签
        labels = []
        pointer = tgen.TrackPointer(self.environment, 'radius')

        def append_label(pos_start=None, pos_end=None, value=None):
            # Create a single radius label at the midpoint of a curve segment /
            # 曲線区間の中点に1つの半径ラベルを作成 /
            # 在曲线段的中点创建一个半径标签
            if pos_end is None:
                pos_end = pointer.data[pointer.pointer['next']]['distance']
            if pos_start is None:
                pos_start = pointer.data[pointer.pointer['last']]['distance']
            if value is None:
                value = pointer.data[pointer.seekoriginofcontinuous(pointer.pointer['last'])]['value']
            if value != 0:
                mid = (pos_start + pos_end) / 2
                if self.distrange['vertical'][0] < mid < self.distrange['vertical'][1]:
                    labels.append({'x': mid, 'y': ypos + np.sign(value) * yscale * 1.5, 'text': '{:.0f}'.format(np.fabs(value))})

        # Skip radius entries before the visible distance range /
        # 可視距離範囲より前の半径エントリをスキップ /
        # 跳过可见距离范围之前的半径条目
        while pointer.pointer['next'] is not None:
            if pointer.data[pointer.pointer['next']]['distance'] < self.distrange['vertical'][0]:
                pointer.seeknext()
            else:
                break

        # Iterate through radius entries within the visible range, generating labels per segment /
        # 可視範囲内の半径エントリを反復処理し、区間ごとにラベルを生成 /
        # 遍历可见范围内的半径条目，逐段生成标签
        while pointer.pointer['next'] is not None and pointer.data[pointer.pointer['next']]['distance'] <= self.distrange['vertical'][1]:
            if pointer.pointer['last'] is not None:
                if pointer.data[pointer.pointer['next']]['flag'] == 'bt':
                    append_label()
                elif pointer.data[pointer.pointer['next']]['flag'] == 'i':
                    if pointer.data[pointer.seekoriginofcontinuous(pointer.pointer['next'])]['value'] == pointer.data[pointer.pointer['last']]['value']:
                        append_label()
                elif pointer.data[pointer.pointer['next']]['flag'] == '':
                    if pointer.data[pointer.pointer['last']]['flag'] != 'bt':
                        append_label()
            pointer.seeknext()
        return labels

    def _station_points(self, target):
        # Filter station positions to the requested distance range /
        # 駅位置を要求距離範囲にフィルタ /
        # 过滤车站位置到请求的距离范围
        if self.nostation:
            return np.array([])
        key = 'plane' if target == 'plane' else 'vertical'
        stationpos = self.station_pos
        stationpos = stationpos[stationpos[:, 0] >= self.distrange[key][0]]
        stationpos = stationpos[stationpos[:, 0] <= self.distrange[key][1]]
        return stationpos

    def _station_labels(self, stationpos):
        # Build label dicts for stations: distance, mileage, name, and screen point /
        # 駅用ラベル辞書を作成：距離、里程、駅名、描画座標 /
        # 构建车站标签字典：距离、里程、站名和屏幕坐标点
        labels = []
        if len(stationpos) == 0:
            return labels
        for row in stationpos:
            station_key = self.environment.station.position[row[0]]
            labels.append({
                'distance': row[0],
                'mileage': row[0] - self.distance_origin,
                'name': self.environment.station.stationkey[station_key],
                'point': row
            })
        return labels

    def _speedlimit_plane_data(self, owntrack):
        # Generate speed limit markers for the plan view: position, angle, speed value /
        # 平面図用速度制限マーカーを生成：位置、角度、制限速度値 /
        # 生成平面图的限速标记：位置、角度、限速值
        result = []
        if len(self.environment.speedlimit.data) == 0 or len(owntrack) == 0:
            return result
        for entry in self.environment.speedlimit.data:
            d = entry['distance']
            if d < self.distrange['plane'][0] or d > self.distrange['plane'][1]:
                continue
            idx = np.searchsorted(owntrack[:, 0], d)
            if idx >= len(owntrack):
                idx = len(owntrack) - 1
            pos = owntrack[idx]
            result.append({
                'distance': d,
                'x': pos[1],
                'y': pos[2],
                'theta': pos[4] - self.origin_angle,
                'speed': entry['speed'],
            })
        return result

    def _curve_sections_plane_data(self, owntrack):
        # Identify continuous curve (constant-radius) sections for the plan view /
        # 平面図用の連続曲線（定半径）区間を特定 /
        # 识别平面图的连续曲线（定半径）区段
        sections = []
        if len(self.environment.own_track.data) == 0:
            return sections
        radius_entries = [e for e in self.environment.own_track.data if e['key'] == 'radius']
        i = 0
        while i < len(radius_entries):
            entry = radius_entries[i]
            if entry['flag'] == '' and entry['value'] != 0 and entry['value'] != 'c':
                # Start of a constant-radius section /
                # 定半径区間の開始 /
                # 定半径区段的开始
                start_d = entry['distance']
                radius_val = entry['value']
                i += 1
                while i < len(radius_entries):
                    next_entry = radius_entries[i]
                    if next_entry['flag'] == '':
                        end_d = next_entry['distance']
                        break
                    i += 1
                else:
                    end_d = max(self.environment.owntrack_pos[:, 0])
                # Clip section to the visible range /
                # 区間を可視範囲にクリップ /
                # 将区段裁剪到可见范围
                if start_d >= self.distrange['plane'][1] or end_d <= self.distrange['plane'][0]:
                    continue
                start_d = max(start_d, self.distrange['plane'][0])
                end_d = min(end_d, self.distrange['plane'][1])
                if end_d > start_d:
                    sections.append({
                        'start': start_d,
                        'end': end_d,
                        'radius': radius_val,
                    })
            else:
                i += 1
        return sections

    def _transition_sections_plane_data(self, owntrack):
        # Identify transition (begintransition) sections for the plan view /
        # 平面図用の緩和区間（begintransition）を特定 /
        # 识别平面图的过渡区段（begintransition）
        sections = []
        if len(self.environment.own_track.data) == 0:
            return sections
        radius_entries = [e for e in self.environment.own_track.data if e['key'] == 'radius']
        i = 0
        while i < len(radius_entries):
            entry = radius_entries[i]
            if entry['flag'] == 'bt':
                # Start of a transition section /
                # 緩和区間の開始 /
                # 过渡区段的开始
                start_d = entry['distance']
                i += 1
                while i < len(radius_entries):
                    next_entry = radius_entries[i]
                    if next_entry['flag'] == '':
                        end_d = next_entry['distance']
                        break
                    i += 1
                else:
                    end_d = max(self.environment.owntrack_pos[:, 0])
                # Clip section to the visible range /
                # 区間を可視範囲にクリップ /
                # 将区段裁剪到可见范围
                if start_d >= self.distrange['plane'][1] or end_d <= self.distrange['plane'][0]:
                    continue
                start_d = max(start_d, self.distrange['plane'][0])
                end_d = min(end_d, self.distrange['plane'][1])
                if end_d > start_d:
                    sections.append({
                        'start': start_d,
                        'end': end_d,
                    })
            else:
                i += 1
        return sections

    def get_track_info_at(self, distance):
        # Look up track state at a given distance: mileage, elevation, gradient, radius, speed limit /
        # 指定距離における軌道状態を検索：里程、標高、勾配、曲線半径、制限速度 /
        # 查询指定距离处的轨道状态：里程、标高、坡度、曲线半径、限速
        own = self.environment.owntrack_pos
        if len(own) == 0 or distance < own[0][0] or distance > own[-1][0]:
            return None
        idx = np.searchsorted(own[:, 0], distance)
        if idx >= len(own):
            idx = len(own) - 1
        pos = own[idx]
        mileage = distance - self.distance_origin
        elevation = pos[3] - self.height_origin
        gradient = pos[6]
        radius = pos[5]
        # Walk through speed limit data to find the last applicable speed /
        # 速度制限データを走査し、最も近い適用速度を検索 /
        # 遍历限速数据找到最后适用的速度值
        speed = None
        for entry in self.environment.speedlimit.data:
            if entry['distance'] > distance:
                break
            speed = entry['speed']
        return {
            'distance': distance,
            'mileage': mileage,
            'elevation': elevation,
            'gradient': gradient,
            'radius': radius,
            'speed': speed,
        }

    def _distance_filter(self, data, distmin, distmax):
        # Filter numpy array rows whose first column (distance) falls within [distmin, distmax] /
        # 第1列（距離）が [distmin, distmax] の範囲内にあるnumpy配列の行を抽出 /
        # 筛选第1列（距离）在 [distmin, distmax] 范围内的numpy数组行
        data = data[data[:, 0] >= distmin]
        data = data[data[:, 0] <= distmax]
        return data

    def _bounds(self, tracks):
        # Compute the 2D bounding box of all track point arrays with a 5% padding /
        # 全軌道点配列の2Dバウンディングボックスを計算し、5%のパディングを付加 /
        # 计算所有轨道点数组的2D边界框，并附加5%的边距
        points = [track[:, 1:3] for track in tracks if len(track) > 0]
        if len(points) == 0:
            return (-1, -1, 1, 1)
        points = np.vstack(points)
        xmin = float(min(points[:, 0]))
        xmax = float(max(points[:, 0]))
        ymin = float(min(points[:, 1]))
        ymax = float(max(points[:, 1]))
        pad = max(xmax - xmin, ymax - ymin, 1) * 0.05
        return (xmin - pad, ymin - pad, xmax + pad, ymax + pad)

    def rotate_track(self, input, angle):
        # Rotate the X/Y columns of a track array around the origin by the given angle /
        # 軌道配列のX/Y列を原点中心に指定角度で回転 /
        # 将轨道数组的X/Y列以原点为中心旋转指定角度
        def rotate(tau1):
            return np.array([[np.cos(tau1), -np.sin(tau1)], [np.sin(tau1), np.cos(tau1)]])

        temp_i = input.T
        temp_rot = np.dot(rotate(angle), np.vstack((temp_i[1], temp_i[2])))
        return np.vstack((np.vstack((temp_i[0], temp_rot)), temp_i[3:])).T
