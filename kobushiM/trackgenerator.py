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

'''
'''

import math
import numpy as np
from . import trackcoordinate as tc

class TrackGenerator():
    def __init__(self,environment,x0=None,y0=None,z0=None,theta0=None,r0=None,gr0=None,dist0=None,unitdist_default=None):
        self.env = environment
        self.data_ownt = self.env.own_track.data
        self.list_cp = self.env.controlpoints.list_cp.copy()
        
        # マップ要素が存在する距離程の最小, 最大値
        self.cp_min = min(self.list_cp)
        self.cp_max = max(self.list_cp)
        
        # 等間隔で距離程を追加する
        equaldist_unit = 25 if unitdist_default is None else unitdist_default
        boundary_margin = 500
        if self.env.cp_arbdistribution != None: # 距離程等間隔配置区間が指定されている場合
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
        elif(len(self.env.station.position) > 0): # 駅が設定されている区間or距離程が存在する区間の前後boundary_margin mに追加
            self.stationdist_min = max(0, round(min(self.env.station.position.keys()),-2) - boundary_margin)
            self.stationdist_max = round(max(self.env.station.position.keys()),-2) + boundary_margin
            cp_equaldist = np.arange(self.stationdist_min,self.stationdist_max,equaldist_unit)
            self.list_cp.extend(cp_equaldist)
            self.list_cp = sorted(list(set(self.list_cp)))
            
            self.env.cp_arbdistribution = [self.stationdist_min,self.stationdist_max,equaldist_unit]
            self.env.cp_arbdistribution_default = self.env.cp_arbdistribution
            self.env.cp_defaultrange = [self.stationdist_min,self.stationdist_max]
        else:
            cp_equaldist_min = max(0, round(self.cp_min,-2) - boundary_margin)
            cp_equaldist = np.arange(cp_equaldist_min,round(self.cp_max,-2) + boundary_margin,equaldist_unit)
            self.list_cp.extend(cp_equaldist)
            self.list_cp = sorted(list(set(self.list_cp)))
            
            self.env.cp_arbdistribution = [cp_equaldist_min,round(self.cp_max,-2) + boundary_margin,equaldist_unit]
            self.env.cp_arbdistribution_default = self.env.cp_arbdistribution
            self.env.cp_defaultrange = [self.env.cp_arbdistribution[0],self.env.cp_arbdistribution[1]]
        
        # 前回処理した地点の情報
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
        
        self.radius_lastpos = {}
        self.radius_lastpos['distance'] = self.last_pos['distance']
        self.radius_lastpos['theta']    = self.last_pos['theta']
        self.radius_lastpos['radius']   = self.last_pos['radius']
        
        #座標情報を格納するリスト
        self.result = np.zeros((len(self.list_cp), 11), dtype=np.float64)
        
        #縦断面図曲線半径情報を格納するリスト
        self.radius_dist = []
    def generate_owntrack(self):
        '''マップ要素が存在する全ての距離程(self.list_cp)に対して自軌道の座標データを生成する。
        self.env: マップ要素が格納されたEnvironmentオブジェクト。
        結果はself.result に[[distance,xpos,ypos,zpos,theta,radius,gradient,interpolate_func,cant,center,gauge],[d.,x.,y.,...],[...],...]として格納する。
        '''
        radius_p      = TrackPointer(self.env,'radius')
        gradient_p    = TrackPointer(self.env,'gradient')
        turn_p        = TrackPointer(self.env,'turn')
        interpolate_p = TrackPointer(self.env,'interpolate_func')
        cant_p        = TrackPointer(self.env,'cant')
        center_p      = TrackPointer(self.env,'center')
        gauge_p       = TrackPointer(self.env,'gauge')
        
        grad_gen  = tc.gradient_intermediate()
        curve_gen = tc.curve_intermediate()
        cant_gen  = tc.Cant(cant_p, self.data_ownt, self.last_pos)
        
        # ローカル変数キャッシュ: dictアクセスを減らしてループ内のオーバーヘッドを低減
        data = self.data_ownt
        lp = self.last_pos
        rlp = self.radius_lastpos
        list_cp = self.list_cp
        
        if not __debug__: # -O オプションが指定されている時のみ、デバッグ情報を処理
            # numpy RuntimeWarning発生時に当該点の距離程を印字
            def raise_warning_position(err,flag):
                raise RuntimeWarning('Numpy warning: '+str(err)+', '+str(flag)+' at '+str(dist))
            def print_warning_position(err,flag):
                print('Numpy warning: '+str(err)+', '+str(flag)+' at '+str(dist))
            np.seterr(all='call')
            np.seterrcall(print_warning_position)
            #np.seterrcall(raise_warning_position)
            
        #import pdb
        #pdb.set_trace()
        
        for i, dist in enumerate(list_cp):
            # curve.setfunction に対する処理
            while (interpolate_p.onNextpoint(dist)): #注目している要素区間の終端に到達？
                lp['interpolate_func'] = data[interpolate_p.pointer['next']]['value']
                interpolate_p.seeknext()
                
            # curve.setcenter に対する処理
            center_tmp = lp['center']
            while (center_p.onNextpoint(dist)): #注目している要素区間の終端に到達？
                center_tmp = data[center_p.pointer['next']]['value']
                center_p.seeknext()
                
            # curve.setgauge に対する処理
            gauge_tmp = lp['gauge']
            while (gauge_p.onNextpoint(dist)): #注目している要素区間の終端に到達？
                gauge_tmp = data[gauge_p.pointer['next']]['value']
                gauge_p.seeknext()
            
            # radiusに対する処理
            _c_theta = lp['theta']
            _c_ds = dist - lp['distance']
            
            # 高速化: 長い直線区間をnumpyで一括計算
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
                _next_change = min(_next_r, _next_g, _next_t, _next_ip, _next_ct, _next_gg, _next_ca)
                _rad_const = _rn is None or data[_rn]['value'] == 'c'
                _grad_const = _gn is None or data[_gn]['value'] == 'c'
                if _rad_const and _grad_const and _next_change > dist:
                    _batch_end = i
                    while _batch_end < len(list_cp) and list_cp[_batch_end] < _next_change:
                        _batch_end += 1
                    _bsize = _batch_end - i
                    if _bsize >= 5:
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
                        
            while (radius_p.overNextpoint(dist)): #注目している要素区間の終端を超えたか？
                if(radius_p.seekoriginofcontinuous(radius_p.pointer['next']) != None):
                    lp['radius']         = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['value']
                    rlp['radius']   = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['value']
                    rlp['distance'] = data[radius_p.seekoriginofcontinuous(radius_p.pointer['next'])]['distance']
                    rlp['theta']    = lp['theta']
                radius_p.seeknext()
            _c_theta = lp['theta']
            _c_ds = dist - lp['distance']
            if(radius_p.pointer['last'] is None): # 最初のcurve要素に到達していない場合
                if(radius_p.pointer['next'] is None): # curve要素が存在しないマップの場合
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
            elif(radius_p.pointer['next'] is None): # curve要素リスト終端に到達
                if(lp['radius'] == 0): # 曲線半径が0 (直線)の場合
                    x = math.cos(_c_theta) * _c_ds
                    y = math.sin(_c_theta) * _c_ds
                    tau = 0
                else: # 一定半径の曲線の場合
                    [x, y], tau = curve_gen.circular_curve(self.cp_max - lp['distance'],\
                                                         lp['radius'],\
                                                         _c_theta,\
                                                         _c_ds)
                radius = lp['radius']
            else: # 一般の場合の処理
                if(data[radius_p.pointer['next']]['value'] == 'c'): # 曲線半径が変化しない区間かどうか
                    if(lp['radius'] == 0): # 曲線半径が0 (直線)の場合
                        x = math.cos(_c_theta) * _c_ds
                        y = math.sin(_c_theta) * _c_ds
                        tau = 0
                    else: # 一定半径の曲線の場合
                        [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                lp['radius'],\
                                                                _c_theta,\
                                                                _c_ds)
                    radius = lp['radius']
                else: # 曲線半径が変化する場合
                    if(data[radius_p.pointer['next']]['flag'] == 'i' or data[radius_p.pointer['last']]['flag'] == 'bt'): # interpolateフラグがある
                        if(rlp['radius'] != data[radius_p.pointer['next']]['value']): # 注目区間前後で異なる曲線半径を取るなら緩和曲線を出力
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
                        elif(data[radius_p.pointer['next']]['value'] != 0): # 曲線半径が変化せず、!=0の場合は円軌道を出力
                            [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                    lp['radius'],\
                                                                    _c_theta,\
                                                                    _c_ds)
                            radius = lp['radius']
                        else: # 直線軌道を出力
                            x = math.cos(_c_theta) * _c_ds
                            y = math.sin(_c_theta) * _c_ds
                            tau = 0
                            radius = lp['radius']
                    else: # interpolateでない
                        if(lp['radius'] == 0): # 曲線半径が0 (直線)の場合
                            x = math.cos(_c_theta) * _c_ds
                            y = math.sin(_c_theta) * _c_ds
                            tau = 0
                        else: # 一定半径の曲線の場合
                            [x, y], tau = curve_gen.circular_curve(data[radius_p.pointer['next']]['distance'] - lp['distance'],\
                                                                 lp['radius'],\
                                                                 _c_theta,\
                                                                 _c_ds)
                        radius = lp['radius']
            # turnに対する処理
            if(turn_p.pointer['next'] != None):
                if(turn_p.onNextpoint(dist)):
                    tau += np.arctan(data[turn_p.pointer['next']]['value'])
                    turn_p.seeknext()
            
            # gradientに対する処理
            while(gradient_p.overNextpoint(dist)): #注目している要素区間の終端を超えたか？
                if(gradient_p.seekoriginofcontinuous(gradient_p.pointer['next']) != None):
                    lp['gradient']  = data[gradient_p.seekoriginofcontinuous(gradient_p.pointer['next'])]['value']
                    lp['dist_grad'] = data[gradient_p.seekoriginofcontinuous(gradient_p.pointer['next'])]['distance']
                gradient_p.seeknext()
            _g_ds = dist - lp['distance']
            _g_gr = lp['gradient']
            if(gradient_p.pointer['last'] is None): #最初の勾配要素に到達していない
                if(gradient_p.pointer['next'] is None): # 勾配が存在しないmapの場合の処理
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                else:
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                gradient = _g_gr
            elif(gradient_p.pointer['next'] is None): #最後の勾配要素を通過した
                z = _g_ds * math.sin(math.atan(_g_gr/1000))
                gradient = _g_gr
            else: # 一般の場合の処理
                if(data[gradient_p.pointer['next']]['value'] == 'c'): # 注目区間の前後で勾配が変化しない場合
                    z = _g_ds * math.sin(math.atan(_g_gr/1000))
                    gradient = _g_gr
                else:
                    if(data[gradient_p.pointer['next']]['flag'] == 'i' or data[gradient_p.pointer['last']]['flag'] == 'bt'): # interpolateフラグがある場合
                        if(_g_gr != data[gradient_p.pointer['next']]['value']): # 注目区間の前後で勾配が変化するなら縦曲線を出力
                            [tmp_d, z], gradient = grad_gen.transition(data[gradient_p.pointer['next']]['distance'] - lp['distance'],\
                                                    _g_gr,\
                                                    data[gradient_p.pointer['next']]['value'],\
                                                    _g_ds)
                        else: # 一定勾配を出力
                            z = _g_ds * math.sin(math.atan(_g_gr/1000))
                            gradient = _g_gr
                    else: # interpolateでない場合、一定勾配を出力
                        z = _g_ds * math.sin(math.atan(_g_gr/1000))
                        gradient = _g_gr
                        
            #Cantに対する処理
            cant_tmp = cant_gen.process(dist, lp['interpolate_func'])
            
            # 地点情報を更新
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
        radius_p = TrackPointer(self.env,'radius')
        
        previous_pos_radius = {'is_bt':False, 'value':0}
        
        self.radius_dist.append([min(self.list_cp),0])
        
        while (radius_p.pointer['next'] != None):
            new_radius = self.data_ownt[radius_p.pointer['next']]['value']
            flag = self.data_ownt[radius_p.pointer['next']]['flag']
            distance = self.data_ownt[radius_p.pointer['next']]['distance']
            if (new_radius == 'c'):
                new_radius = previous_pos_radius['value']
                self.radius_dist.append([distance,new_radius])
            else:
                if(previous_pos_radius['is_bt']): # 直前点がbegin_transitionなら、緩和曲線を出力
                    self.radius_dist.append([distance,new_radius])
                else:
                    if(flag == 'i'): # 現在点がinterpolateなら、緩和曲線を出力
                        self.radius_dist.append([distance,new_radius])
                    else: # 現在点で階段状に変化する半径を出力
                        self.radius_dist.append([distance,previous_pos_radius['value']])
                        self.radius_dist.append([distance,new_radius])
                        
            previous_pos_radius['value'] = new_radius
            previous_pos_radius['is_bt'] = True if flag == 'bt' else False
            radius_p.seeknext()
            
        self.radius_dist.append([max(self.list_cp),0])
        return np.array(self.radius_dist)
        
class TrackPointer():
    def __init__(self,environment,target):
        self.pointer = {'last':None, 'next':0}
        self.env = environment
        self.target = target
        self.data = self.env.own_track.data
        self.ix_max = len(self.data) - 1
        
        self.seekfirst()
    def seek(self, ix0):
        '''ix0以降で注目する要素が現れるインデックスを探索。データ終端まで到達した場合はNoneを返す。
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
        '''注目する要素が初めて現れるインデックスを探索して、pointer['next']にセットする。
        '''
        self.pointer['next'] = self.seek(0)
    def seeknext(self):
        '''次の要素が存在するインデックスを探し、self.pointer['last', 'next']を書き換える。
        self.pointer['next'] is None の場合は何もしない。
        '''
        if(self.pointer['next'] != None):
            self.pointer['last'] = self.pointer['next']
            self.pointer['next'] = self.seek(self.pointer['next']+1)
    def insection(self,distance):
        '''注目している要素の区間内かどうか調べる。
        self.pointer['last'] < 与えられたdistance <= self.pointer['next'] ならTrue
        '''
        return (self.data[self.pointer['prev']]['distance'] > distance and self.data[self.pointer['next']]['distance'] <= distance)
    def onNextpoint(self,distance):
        '''注目している要素区間の終端にいるか調べる。
        与えられたdistance == 注目しているpointer['next'] ならTrue。
        pointer['next'] is None (要素リスト終端に到達した) なら必ずFalse。
        '''
        return (self.data[self.pointer['next']]['distance'] == distance) if self.pointer['next'] != None else False
    def overNextpoint(self,distance):
        '''注目している要素区間を超えたか調べる。
        与えられたdistance > 注目しているpointer['next'] ならTrue。
        pointer['next'] is None (要素リスト終端に到達した) なら必ずFalse。
        '''
        return (self.data[self.pointer['next']]['distance'] < distance) if self.pointer['next'] != None else False
    def beforeLastpoint(self,distance):
        '''注目している要素区間にまだ到達していないか調べる。
        与えられたdistance <= 注目しているpointer['last'] ならTrue。
        pointer['last'] is None (リスト始端の要素地点に到達していない) なら必ずTrue。
        '''
        return (self.data[self.pointer['last']]['distance'] >= distance) if self.pointer['last'] != None else True
    def seekoriginofcontinuous(self,index):
        '''注目している要素のvalue=c (直前に指定した値と同一)であった場合、その起源となる要素(value != c)を示すインデックスを返す。
        リストの先頭まで探索しても見つからなかった場合はNoneを返す。
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
    class OtherTrackPointer(TrackPointer):
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
        # 前回処理した地点の情報
        self.pos = {'last':{}, 'next':{}}
        for key in ['x.position','x.radius','x.distance','y.position','y.radius','y.distance','interpolate_func','cant','center','gauge']:
            self.pos['last'][key] = 0
            self.pos['next'][key] = 0
    
    def generate(self):
        '''他軌道座標を計算する。
        対象はインスタンス作成時に指定したkeyの軌道。
        '''
        # 軌道要素ポインタの作成
        trackptr = {}
        for tpkey in ['x.position','x.radius','y.position','y.radius','interpolate_func','cant','center','gauge']:
            trackptr[tpkey] = self.OtherTrackPointer(self.env,tpkey,self.trackkey)
            
        track_gen = tc.OtherTrack() # 座標計算オブジェクト
        cant_gen  = tc.Cant(trackptr['cant'], self.data, self.pos['last']) # カント計算オブジェクト
        
        num_owntrack = len(self.owntrack_position)
        self.result = np.zeros((num_owntrack, 8), dtype=np.float64)
        result_idx = 0
        
        #tp_keys = ['x.position','x.radius','y.position','y.radius']
        #skip_dimension = {'x.position':False, 'x.radius':False, 'y.position':False, 'y.radius':False}
        for tpkey in trackptr.keys(): # ポインタ初期値設定
            if trackptr[tpkey].pointer['next'] != None:
                for k in ['last','next']:
                    newval = self.data[trackptr[tpkey].pointer['next']]['value']
                    self.pos[k][tpkey] = newval if newval != 'c' else 0
                    
        for element in self.owntrack_position: # 自軌道が指定されている全ての距離程について計算する
            if self.distrange['min'] > element[0]: # 対象となる軌道が最初に現れる距離程にまだ達していないか？
                continue
            for tpkey in ['x.position','x.radius','y.position','y.radius']: # ポインタを進める
                while trackptr[tpkey].overNextpoint(element[0]):
                    trackptr[tpkey].seeknext()
                    self.pos['last'][tpkey] = self.pos['next'][tpkey]
                    if trackptr[tpkey].pointer['next'] != None:
                        k = 'next'
                        newval = self.data[trackptr[tpkey].pointer[k]]['value']
                        self.pos[k][tpkey] = newval if newval != 'c' else self.pos['last'][tpkey]
            for tpkey in ['interpolate_func','center','gauge']: # ポインタを進める
                while trackptr[tpkey].onNextpoint(element[0]):
                    trackptr[tpkey].seeknext()
                    self.pos['last'][tpkey] = self.pos['next'][tpkey]
                    if trackptr[tpkey].pointer['next'] != None:
                        k = 'next'
                        newval = self.data[trackptr[tpkey].pointer[k]]['value']
                        self.pos[k][tpkey] = newval if newval != 'c' else self.pos['last'][tpkey]
            
            if trackptr['x.position'].pointer['last'] != None and trackptr['x.position'].pointer['next'] != None: # skip_dimension に従って計算するかどうか判断する
                for k in ['last','next']:
                    self.pos[k]['x.distance'] = self.data[trackptr['x.position'].pointer[k]]['distance']
                
                temp_result_X = track_gen.absolute_position_X(self.pos['next']['x.distance'] - self.pos['last']['x.distance'],\
                                                                self.pos['last']['x.radius'],\
                                                                self.pos['last']['x.position'],\
                                                                self.pos['next']['x.position'],\
                                                                element[0] - self.pos['last']['x.distance'],\
                                                                element)
            else:
                theta = element[4]
                x_pos = self.pos['last']['x.position']
                temp_result_X = [-math.sin(theta) * x_pos + element[1], math.cos(theta) * x_pos + element[2]]
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
                # result_Y: [distance, Yval]なら、第二項は[element[0],element[3]ではないか？
                
            temp_result_cant = cant_gen.process(element[0], self.pos['last']['interpolate_func'])
            
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
