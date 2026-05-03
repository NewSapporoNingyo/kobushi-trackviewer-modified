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

import numpy as np
from . import trackgenerator as tgen
from . import i18n


class Mapplot():
    def __init__(self, env, cp_arbdistribution=None, unitdist_default=None):
        self.environment = env
        self.environment.cp_arbdistribution = cp_arbdistribution
        self.environment.cp_defaultrange = [0, 0]

        trackgenerator = tgen.TrackGenerator(self.environment, unitdist_default=unitdist_default)
        self.environment.owntrack_pos = trackgenerator.generate_owntrack()
        self.environment.owntrack_curve = trackgenerator.generate_curveradius_dist()

        self.environment.othertrack_pos = {}
        for key in self.environment.othertrack.data.keys():
            self.environment.othertrack_pos[key] = tgen.OtherTrackGenerator(self.environment, key).generate()

        self.distrange = {}
        self.distrange['plane'] = [
            min(self.environment.owntrack_pos[:, 0]),
            max(self.environment.owntrack_pos[:, 0])
        ]
        self.distrange['vertical'] = [
            min(self.environment.owntrack_pos[:, 0]),
            max(self.environment.owntrack_pos[:, 0])
        ]
        start_distance = min(self.environment.owntrack_pos[:, 0])
        self.distance_origin = start_distance
        self.height_origin = self.environment.owntrack_pos[
            self.environment.owntrack_pos[:, 0] == start_distance
        ][0][3]
        self.origin_angle = self.environment.owntrack_pos[
            self.environment.owntrack_pos[:, 0] == min(self.environment.owntrack_pos[:, 0])
        ][0][4]

        if len(self.environment.station.position) > 0:
            self.station_dist = np.array(list(self.environment.station.position.keys()))
            self.station_pos = self.environment.owntrack_pos[np.isin(self.environment.owntrack_pos[:, 0], self.station_dist)]
            self.nostation = False
        else:
            self.station_dist = np.array([])
            self.station_pos = np.array([])
            self.nostation = True

    def plane_data(self, distmin=None, distmax=None, othertrack_list=None):
        if distmin is not None:
            self.distrange['plane'][0] = distmin
        if distmax is not None:
            self.distrange['plane'][1] = distmax

        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['plane'][0],
            self.distrange['plane'][1])
        if len(owntrack) == 0:
            return {'owntrack': np.array([]), 'othertracks': [], 'stations': [], 'speedlimits': [], 'curve_sections': [], 'transition_sections': [], 'bounds': (-1, -1, 1, 1)}

        self.origin_angle = owntrack[0][4]
        owntrack = self.rotate_track(owntrack, -self.origin_angle)

        othertracks = []
        if othertrack_list is not None:
            for key in othertrack_list:
                key = '' if key == '\\' else key
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

        stations = self._station_points('plane')
        if len(stations) > 0:
            stations = self.rotate_track(stations, -self.origin_angle)

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
        if distmin is not None:
            self.distrange['vertical'][0] = distmin
        if distmax is not None:
            self.distrange['vertical'][1] = distmax

        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        owntrack = owntrack.copy()
        if len(owntrack) > 0:
            owntrack[:, 3] = owntrack[:, 3] - self.height_origin
        curve = self._distance_filter(
            self.environment.owntrack_curve,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        if len(owntrack) == 0:
            return {'owntrack': np.array([]), 'curve': np.array([]), 'othertracks': [], 'stations': [], 'gradient_labels': [], 'radius_labels': [], 'bounds': (-1, -1, 1, 1)}

        othertracks = []
        if othertrack_list is not None:
            for key in othertrack_list:
                key = '' if key == '\\' else key
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

        curve_points = []
        if len(curve) > 0:
            curve_points = np.array([[row[0], np.sign(row[1])] for row in curve])

        station_points = self._station_points('vertical')
        station_points = station_points.copy()
        if len(station_points) > 0:
            station_points[:, 3] = station_points[:, 3] - self.height_origin
        station_labels = self._station_labels(station_points)
        gradient_labels = self.gradient_labels(ymin)
        gradient_points = self.gradient_change_points(owntrack, ymin)
        radius_labels = self.radius_labels(0, 1)
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
        labels = []
        pointer = tgen.TrackPointer(self.environment, 'gradient')
        owntrack = self._distance_filter(
            self.environment.owntrack_pos,
            self.distrange['vertical'][0],
            self.distrange['vertical'][1])
        if len(owntrack) == 0:
            return labels

        def append_label(pos_start=None, pos_end=None, value=None):
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

        while pointer.pointer['next'] is not None:
            if pointer.data[pointer.pointer['next']]['distance'] < self.distrange['vertical'][0]:
                pointer.seeknext()
            else:
                break
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
        if pointer.pointer['last'] is None:
            append_label(pos_end=max(owntrack[:, 0]), pos_start=min(owntrack[:, 0]), value=0)
        else:
            append_label(pos_end=max(owntrack[:, 0]))
        return labels

    def radius_labels(self, ypos, yscale):
        labels = []
        pointer = tgen.TrackPointer(self.environment, 'radius')

        def append_label(pos_start=None, pos_end=None, value=None):
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

        while pointer.pointer['next'] is not None:
            if pointer.data[pointer.pointer['next']]['distance'] < self.distrange['vertical'][0]:
                pointer.seeknext()
            else:
                break
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
        if self.nostation:
            return np.array([])
        key = 'plane' if target == 'plane' else 'vertical'
        stationpos = self.station_pos
        stationpos = stationpos[stationpos[:, 0] >= self.distrange[key][0]]
        stationpos = stationpos[stationpos[:, 0] <= self.distrange[key][1]]
        return stationpos

    def _station_labels(self, stationpos):
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
        sections = []
        if len(self.environment.own_track.data) == 0:
            return sections
        radius_entries = [e for e in self.environment.own_track.data if e['key'] == 'radius']
        i = 0
        while i < len(radius_entries):
            entry = radius_entries[i]
            if entry['flag'] == '' and entry['value'] != 0 and entry['value'] != 'c':
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
        sections = []
        if len(self.environment.own_track.data) == 0:
            return sections
        radius_entries = [e for e in self.environment.own_track.data if e['key'] == 'radius']
        i = 0
        while i < len(radius_entries):
            entry = radius_entries[i]
            if entry['flag'] == 'bt':
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
        data = data[data[:, 0] >= distmin]
        data = data[data[:, 0] <= distmax]
        return data

    def _bounds(self, tracks):
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
        def rotate(tau1):
            return np.array([[np.cos(tau1), -np.sin(tau1)], [np.sin(tau1), np.cos(tau1)]])

        temp_i = input.T
        temp_rot = np.dot(rotate(angle), np.vstack((temp_i[1], temp_i[2])))
        return np.vstack((np.vstack((temp_i[0], temp_rot)), temp_i[3:])).T
