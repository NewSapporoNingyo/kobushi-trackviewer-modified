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

# NumPy for array math, SciPy integrate for numerical integration /
# NumPy（配列演算）、SciPy integrate（数値積分） /
# NumPy用于数组运算，SciPy integrate用于数值积分
import numpy as np
from scipy import integrate

class gradient():
    # Computes elevation changes for straight gradient and vertical transition curves /
    # 一定勾配と縦曲線に対する標高変化を計算 /
    # 计算定坡度和竖曲线的标高变化
    def __init__(self):
        pass
    def straight(self, L, gr):
        '''Return the elevation change for a constant gradient.
        L: gradient length [m]
        gr: gradient [‰]
        /
        一定勾配に対する高度変化を返す。
        L: 勾配長 [m]
        gr: 勾配 [‰]
        /
        返回定坡度的标高变化。
        L: 坡度长度 [m]
        gr: 坡度 [‰]
        '''
        dist = L
        theta = np.arctan(gr/1000)
        return np.array([dist,dist*np.sin(theta)]).T

    def transition(self, L, gr1, gr2, y0=0, n=5):
        '''Return the elevation change for a vertical transition curve.
        L: gradient length [m]
        gr1: starting gradient [‰]
        gr2: ending gradient [‰]
        /
        縦曲線に対する高度変化を返す。
        L: 勾配長 [m]
        gr1: 始点の勾配 [‰]
        gr2: 終点の勾配 [‰]。
        /
        返回竖曲线的标高变化。
        L: 坡度长度 [m]
        gr1: 起点坡度 [‰]
        gr2: 终点坡度 [‰]
        '''
        dist = np.linspace(0,L,n)
        theta1 = np.arctan(gr1/1000)
        theta2 = np.arctan(gr2/1000)
        return np.vstack((dist,y0+L/(theta2-theta1)*np.cos(theta1)-L/(theta2-theta1)*np.cos((theta2-theta1)/L*dist+theta1))).T

class gradient_intermediate(gradient):
    # Provides elevation/gradient at a single intermediate point along a gradient segment /
    # 勾配区間内の単一の中間点における標高/勾配を提供 /
    # 提供坡度段内单个中间点处的标高/坡度
    def __init__(self):
        pass
    def straight(self, L, gr, l_intermediate):
        '''Return the elevation change at l_intermediate for a constant gradient of total length L.
        L: gradient length [m]
        gr: gradient [‰]
        /
        全長Lの一定勾配について、l_intermediateでの高度変化を返す。
        L: 勾配長 [m]
        gr: 勾配 [‰]
        /
        返回全长L的定坡度在 l_intermediate 处的标高变化。
        L: 坡度长度 [m]
        gr: 坡度 [‰]
        '''
        dist = l_intermediate
        theta = np.arctan(gr/1000)
        return np.array([dist,dist*np.sin(theta)]).T[-1]

    def transition(self, L, gr1, gr2, l_intermediate, y0=0):
        '''Return the elevation change and gradient at l_intermediate for a vertical curve of total length L.
        L: vertical curve length [m]
        gr1: starting gradient [‰]
        gr2: ending gradient [‰]
        /
        全長Lの縦曲線について、l_intermediateでの高度変化、勾配を返す。
        L: 縦曲線長 [m]
        gr1: 始点の勾配 [‰]
        gr2: 終点の勾配 [‰]。
        /
        返回全长L的竖曲线在 l_intermediate 处的标高变化和坡度。
        L: 竖曲线长度 [m]
        gr1: 起点坡度 [‰]
        gr2: 终点坡度 [‰]
        '''
        dist = l_intermediate
        theta1 = np.arctan(gr1/1000)
        theta2 = np.arctan(gr2/1000)
        return np.vstack((dist,y0+L/(theta2-theta1)*np.cos(theta1)-L/(theta2-theta1)*np.cos((theta2-theta1)/L*dist+theta1))).T[-1], 1000*np.tan((theta2 - theta1)/L*l_intermediate + theta1)

class curve():
    # Computes horizontal alignment: straight lines, circular curves, and transition curves (clothoid / sin half-wave) /
    # 平面線形（直線・円曲線・緩和曲線（クロソイド / sin半波長逓減））を計算 /
    # 计算平曲线线形：直线、圆曲线、过渡曲线（回旋线 / sin半波长递减）
    def __init__(self):
        pass
    def clothoid_dist(self, A, l, elem):
        '''Return the X or Y coordinate of a clothoid curve.
        A: clothoid parameter
        l: arc length [m]
        elem: coordinate component to compute ('X' or 'Y')
        /
        クロソイド曲線の座標を返す。
        A: クロソイドパラメータ
        l: 弧長 [m]
        elem: 求める座標成分 'X'/'Y'
        /
        返回回旋曲线的坐标。
        A: 回旋参数
        l: 弧长 [m]
        elem: 要计算的坐标分量（'X' 或 'Y'）
        '''
        if elem == 'X':
            return l*(1-1/40*(l/A)**4+1/3456*(l/A)**8-1/599040*(l/A)**12)
        else:
            return l*(1/6*(l/A)**2-1/336*(l/A)**6+1/42240*(l/A)**10-1/9676800*(l/A)**14)

    def rotate(self, tau1):
        '''Return a 2D rotation matrix.
        tau1: rotation angle [rad]
        /
        ２次元回転行列を返す。
        tau1: 回転角度 [rad]
        /
        返回二维旋转矩阵。
        tau1: 旋转角度 [rad]
        '''
        return np.array([[np.cos(tau1), -np.sin(tau1)], [np.sin(tau1),  np.cos(tau1)]])

    def straight(self, L, theta):
        '''Return the plane coordinates of a straight track segment.
        L: straight length [m]
        theta: track bearing at the starting point [rad]
        /
        直線軌道の平面座標を返す。
        L: 直線長さ [m]
        theta: 始点での軌道方位角 [rad]
        /
        返回直线轨道段的平面坐标。
        L: 直线长度 [m]
        theta: 起点处的轨道方位角 [rad]
        '''
        dist = L
        res=np.array([dist,0]).T
        return np.dot(self.rotate(theta), res).T

    def circular_curve(self, L, R, theta, n=10):
        '''Return the plane coordinates of a circular curve.
        L: curve length [m]
        R: curve radius [m]
        theta: track bearing at the starting point [rad]
        n: number of intermediate subdivisions
        /
        円軌道の平面座標を返す。
        L: 軌道長さ [m]
        R: 曲線半径 [m]
        theta: 始点での軌道方位角 [rad]
        n: 中間点の分割数
        /
        返回圆曲线的平面坐标。
        L: 轨道长度 [m]
        R: 曲线半径 [m]
        theta: 起点处的轨道方位角 [rad]
        n: 中间点的分割数
        '''
        dist = np.linspace(0,L,n)
        tau = L/R
        res = [np.fabs(R)*np.sin(dist/np.fabs(R)),R*(1-np.cos(dist/np.fabs(R)))]
        return (np.dot(self.rotate(theta), res).T)[1:], tau

    def transition_curve(self, L, r1, r2, theta, func, n=5):
        '''Return the plane coordinates of a transition curve.
        L: curve length [m]
        r1: radius at the start [m]
        r2: radius at the end [m]
        theta: track bearing at the start [rad]
        func: curvature reduction function ('line': linear, 'sin': half-sine wave)
        n: number of intermediate subdivisions
        /
        緩和曲線の平面座標を返す。
        L: 軌道長さ [m]
        r1: 始点の曲線半径 [m]
        r2: 終点の曲線半径 [m]
        theta: 始点での軌道方位角 [rad]
        func: 逓減関数('line': 直線逓減, 'sin':sin半波長逓減)
        n: 中間点の分割数
        /
        返回过渡曲线的平面坐标。
        L: 轨道长度 [m]
        r1: 起点的曲线半径 [m]
        r2: 终点的曲线半径 [m]
        theta: 起点处的轨道方位角 [rad]
        func: 曲率递减函数（'line': 线性递减, 'sin': 正弦半波长递减）
        n: 中间点的分割数
        '''
        r1 = np.inf if r1==0 else r1
        r2 = np.inf if r2==0 else r2

        if func == 'line':
            # Linear curvature reduction case: L0 is the distance at which curvature becomes zero /
            # 直線逓減の場合：L0は曲率が0となる距離 /
            # 线性递减时：L0为曲率变为零处的距离
            # When start/end curvatures have the same sign → L0<0 or L0>L; opposite sign → 0<L0<L /
            # 始終点の曲率が同符号の場合はL0<0 or L0>L、異符号の場合は0<L0<Lとなる /
            # 起终点曲率同号时L0<0或L0>L，异号时0<L0<L
            L0 = L*(1-(1/(1-(r2)/(r1))))

            # Determine clothoid parameter A /
            # クロソイドパラメータAの決定 /
            # 确定回旋参数A
            if(r1 != np.inf):
                A = np.sqrt(np.fabs(L0)*np.fabs(r1))
            else:
                A = np.sqrt(np.fabs(L-L0)*np.fabs(r2))

            if (1/r1 < 1/r2):
                # Curvature increases to the right /
                # 右向きに曲率が増加する場合 /
                # 曲率向右增加时
                tau1 = (A/r1)**2/2
                # Bearing angle at the start of the transition curve /
                # 緩和曲線始端の方位角 /
                # 过渡曲线起端的方位角
                dist = np.linspace(A**2/r1,A**2/r2,n)
                # Bearing change across the transition; clothoid tangent angle τ = l^2/(2A^2) measured from origin L0 /
                # 緩和曲線通過前後での方位角変化。クロソイド曲線の接線角τは、原点(L0)からの距離lに対してτ=l^2/(2A^2) /
                # 过渡曲线前后的方位角变化；回旋曲线的切线角τ在距原点L0距离l处为τ=l^2/(2A^2)
                turn = ((L-L0)**2-L0**2)/(2*A**2)
                result=np.vstack((self.clothoid_dist(A,dist,'X'),self.clothoid_dist(A,dist,'Y'))).T
            else:
                # Curvature increases to the left /
                # 左向きに曲率が増加する場合 /
                # 曲率向左增加时
                tau1 = -(A/r1)**2/2
                dist = np.linspace(-A**2/r1,-A**2/r2,n)
                turn = -((L-L0)**2-L0**2)/(2*A**2)
                result=np.vstack((self.clothoid_dist(A,dist,'X'),self.clothoid_dist(A,dist,'Y')*(-1))).T
        elif func == 'sin':
            # Half-sine wave curvature reduction /
            # sin半波長逓減 /
            # 正弦半波长递减
            output = self.harfsin_intermediate(L, r1, r2, L)
            tau1 = 0
            turn = output[2]
            rl = output[3] #if output[3] != 0 else np.inf

            result_temp = np.vstack((output[0],output[1])).T
            result = result_temp[::int(np.ceil(len(output[0])/n))]
            result = np.vstack((result,result_temp[-1]))
        else:
            raise RuntimeError('invalid transition function')

        return (np.dot(self.rotate(theta), np.dot(self.rotate(-tau1),(result-result[0]).T)).T)[1:], turn

    def harfsin_intermediate(self, L, r1, r2, l_intermediate, dL=1):
        # Compute coordinates, bearing, and radius at an intermediate point of a sin half-wave transition /
        # sin半波長逓減緩和曲線の中間点における座標・方位角・半径を計算 /
        # 计算正弦半波长递减过渡曲线中间点的坐标、方位角和半径
        def K(x,R1,R2,L):
            '''Return the curvature for a sin half-wave transition curve.
            x: distance from the start
            R1: radius at the start
            R2: radius at the end
            L: total length of the transition curve
            /
            sin半波長逓減の緩和曲線に対する曲率を返す。
            x: 始点からの距離
            R1: 始点での曲率半径
            R2: 終点での曲率半径
            L: 緩和曲線の全長
            /
            返回正弦半波长递减过渡曲线的曲率。
            x: 距起点的距离
            R1: 起点曲率半径
            R2: 终点曲率半径
            L: 过渡曲线全长
            '''
            return (1/R2-1/R1)/2*(np.sin(np.pi/L*x-np.pi/2)+1)+1/R1

        if l_intermediate > 0:
            if l_intermediate/5 <= dL:
                dL = l_intermediate/5
            tau_X = np.linspace(0,l_intermediate,int((l_intermediate)/dL)+1)
            tau = integrate.cumulative_trapezoid(K(tau_X,r1,r2,L),tau_X,initial = 0)
            X = integrate.cumulative_trapezoid(np.cos(tau),tau_X,initial = 0)
            Y = integrate.cumulative_trapezoid(np.sin(tau),tau_X,initial = 0)
            r_interm = 1/K(l_intermediate,r1,r2,L) if K(l_intermediate,r1,r2,L) != 0 else np.inf
        else:
            X = 0
            Y = 0
            tau = np.array([0])
            r_interm = r1 if r1 != 0 else np.inf
        return (X,Y,tau[-1],r_interm)

class curve_intermediate(curve):
    # Provides coordinates/bearing/radius at a single intermediate point along a curve segment /
    # 曲線区間内の単一の中間点における座標/方位角/半径を提供 /
    # 提供曲线段内单个中间点处的坐标/方位角/半径
    def straight(self,L, theta, l_intermediate):
        '''Return the plane coordinates of a straight track at l_intermediate.
        L: straight length [m]
        theta: track bearing at the starting point [rad]
        l_intermediate: distance from the origin at which to output coordinates
        /
        直線軌道の平面座標を返す。
        L: 直線長さ [m]
        theta: 始点での軌道方位角 [rad]
        l_intermediate: 座標を出力する原点からの距離
        /
        返回直线轨道在 l_intermediate 处的平面坐标。
        L: 直线长度 [m]
        theta: 起点处的轨道方位角 [rad]
        l_intermediate: 输出坐标的位置距原点的距离
        '''
        dist = l_intermediate
        res=np.array([dist,0]).T
        return np.dot(self.rotate(theta), res).T

    def circular_curve(self,L, R, theta, l_intermediate):
        '''Return the coordinates and bearing at l_intermediate for a circular curve of total length L.
        L: curve length [m]
        R: curve radius [m]
        theta: track bearing at the starting point [rad]
        l_intermediate: distance from the origin at which to output coordinates
        /
        全長Lの円曲線について、l_intermediateでの座標、方位を返す。
        L: 軌道長さ [m]
        R: 曲線半径 [m]
        theta: 始点での軌道方位角 [rad]
        l_intermediate: 座標を出力する原点からの距離
        /
        返回全长L的圆曲线在 l_intermediate 处的坐标和方位角。
        L: 轨道长度 [m]
        R: 曲线半径 [m]
        theta: 起点处的轨道方位角 [rad]
        l_intermediate: 输出坐标的位置距原点的距离
        '''
        dist = np.array([0,l_intermediate])
        tau = l_intermediate/R
        res = [np.fabs(R)*np.sin(dist/np.fabs(R)),R*(1-np.cos(dist/np.fabs(R)))]
        return (np.dot(self.rotate(theta), res).T)[-1], tau

    def transition_curve(self,L, r1, r2, theta, func, l_intermediate):
        '''Return the coordinates, bearing, and curve radius at l_intermediate for a transition curve of total length L.
        L: curve length [m]
        r1: radius at the start [m]
        r2: radius at the end [m]
        theta: track bearing at the start [rad]
        func: curvature reduction function ('line': linear, 'sin': half-sine wave)
        l_intermediate: distance from the origin at which to output coordinates
        /
        全長Lの緩和曲線について、l_intermediateでの座標、方位、曲線半径を返す。
        L: 軌道長さ [m]
        r1: 始点の曲線半径 [m]
        r2: 終点の曲線半径 [m]
        theta: 始点での軌道方位角 [rad]
        func: 逓減関数('line': 直線逓減, 'sin':sin半波長逓減)
        l_intermediate: 座標を出力する原点からの距離
        /
        返回全长L的过渡曲线在 l_intermediate 处的坐标、方位角和曲线半径。
        L: 轨道长度 [m]
        r1: 起点的曲线半径 [m]
        r2: 终点的曲线半径 [m]
        theta: 起点处的轨道方位角 [rad]
        func: 曲率递减函数（'line': 线性递减, 'sin': 正弦半波长递减）
        l_intermediate: 输出坐标的位置距原点的距离
        '''
        r1 = np.inf if r1==0 else r1
        r2 = np.inf if r2==0 else r2

        # Treat very large radii (>1e6) as straight (infinite radius) /
        # 非常に大きな半径（>1e6）は直線（半径無限大）として扱う /
        # 将非常大的半径（>1e6）视为直线（半径无穷大）
        r1 = np.inf if np.fabs(r1)>1e6 else r1
        r2 = np.inf if np.fabs(r2)>1e6  else r2

        #print(L, r1, r2, theta, func, l_intermediate)

        if func == 'line':
            # Linear curvature reduction case /
            # 直線逓減の場合 /
            # 线性递减情况
            # L0: distance at which curvature becomes zero /
            # L0：曲率が0となる距離 /
            # L0：曲率为零处的距离
            # Same-sign → L0<0 or L0>L; opposite-sign → 0<L0<L /
            # 始終点の曲率が同符号の場合はL0<0 or L0>L、異符号の場合は0<L0<Lとなる /
            # 起终点曲率同号时L0<0或L0>L，异号时0<L0<L
            L0 = L*(1-(1/(1-(r2)/(r1))))

            # Intermediate radius at l_intermediate via linear interpolation of curvatures /
            # l_intermediateでの曲率の線形補間による中間半径 /
            # 通过曲率线性插值得出 l_intermediate 处的中半径
            rl = 1/(1/r1 + (1/r2 - 1/r1)/L * l_intermediate) if (1/r1 + (1/r2 - 1/r1)/L * l_intermediate) != 0 else np.inf

            # Determine clothoid parameter A /
            # クロソイドパラメータAの決定 /
            # 确定回旋参数A
            if(r1 != np.inf):
                A = np.sqrt(np.fabs(L0)*np.fabs(r1))
            else:
                A = np.sqrt(np.fabs(L-L0)*np.fabs(r2))

            if (1/r1 < 1/r2):
                # Curvature increases to the right /
                # 右向きに曲率が増加する場合 /
                # 曲率向右增加
                tau1 = (A/r1)**2/2
                # Bearing angle at the start of the transition curve /
                # 緩和曲線始端の方位角 /
                # 过渡曲线起端的方位角
                dist = np.array([0,l_intermediate])+A**2/r1
                # Bearing change; clothoid tangent angle τ = l^2/(2A^2) measured from origin L0 /
                # 緩和曲線通過前後での方位角変化。クロソイド曲線の接線角τは、原点(L0)からの距離lに対してτ=l^2/(2A^2) /
                # 方位角变化；回旋曲线的切线角τ在距原点L0距离l处为τ=l^2/(2A^2)
                turn = ((l_intermediate-L0)**2-L0**2)/(2*A**2)
                result=np.vstack((self.clothoid_dist(A,dist,'X'),self.clothoid_dist(A,dist,'Y'))).T
            else:
                # Curvature increases to the left /
                # 左向きに曲率が増加する場合 /
                # 曲率向左增加
                tau1 = -(A/r1)**2/2
                dist = np.array([0,l_intermediate])+(-A**2/r1)
                turn = -((l_intermediate-L0)**2-L0**2)/(2*A**2)
                result=np.vstack((self.clothoid_dist(A,dist,'X'),self.clothoid_dist(A,dist,'Y')*(-1))).T
        elif func == 'sin':
            # Half-sine wave curvature reduction /
            # sin半波長逓減 /
            # 正弦半波长递减
            output = self.harfsin_intermediate(L, r1, r2, l_intermediate)
            tau1 = 0
            turn = output[2]
            rl = output[3] #if output[3] != 0 else np.inf
            result = np.vstack((output[0],output[1])).T
        else:
            raise RuntimeError('invalid transition function')
        return (np.dot(self.rotate(theta), np.dot(self.rotate(-tau1),(result-result[0]).T)).T)[-1], turn, rl if np.fabs(rl) < 1e6 else 0

    def harfsin_intermediate(self, L, r1, r2, l_intermediate, dL=1):
        # Compute coordinates, bearing, and radius at an intermediate point of a sin half-wave transition /
        # sin半波長逓減緩和曲線の中間点における座標・方位角・半径を計算 /
        # 计算正弦半波长递减过渡曲线中间点的坐标、方位角和半径
        def K(x,R1,R2,L):
            '''Return the curvature for a sin half-wave transition curve.
            x: distance from the start
            R1: radius at the start
            R2: radius at the end
            L: total length of the transition curve
            /
            sin半波長逓減の緩和曲線に対する曲率を返す。
            x: 始点からの距離
            R1: 始点での曲率半径
            R2: 終点での曲率半径
            L: 緩和曲線の全長
            /
            返回正弦半波长递减过渡曲线的曲率。
            x: 距起点的距离
            R1: 起点曲率半径
            R2: 终点曲率半径
            L: 过渡曲线全长
            '''
            return (1/R2-1/R1)/2*(np.sin(np.pi/L*x-np.pi/2)+1)+1/R1

        if l_intermediate > 0:
            if l_intermediate/5 <= dL:
                dL = l_intermediate/5
            tau_X = np.linspace(0,l_intermediate,int((l_intermediate)/dL)+1)
            tau = integrate.cumulative_trapezoid(K(tau_X,r1,r2,L),tau_X,initial = 0)
            X = integrate.cumulative_trapezoid(np.cos(tau),tau_X,initial = 0)
            Y = integrate.cumulative_trapezoid(np.sin(tau),tau_X,initial = 0)
            r_interm = 1/K(l_intermediate,r1,r2,L) if K(l_intermediate,r1,r2,L) != 0 else np.inf
        else:
            X = 0
            Y = 0
            tau = np.array([0])
            r_interm = r1 if r1 != 0 else np.inf
        return (X,Y,tau[-1],r_interm)

class Cant():
    # Processes cant (superelevation) data along the track using a track pointer for incremental advancement /
    # 線路ポインタを用いて軌道沿いのカント（片勾配）データを逐次的に処理 /
    # 使用轨道指针沿轨道逐步处理超高（cant）数据
    def __init__(self, pointer, data, last_pos):
        # Initialize with a track pointer, own-track data, and last known position /
        # 線路ポインタ、自軌道データ、最後の既知位置で初期化 /
        # 使用轨道指针、自有轨道数据和上次已知位置初始化
        self.pointer       = pointer
        self.data_ownt     = data
        self.last_pos      = last_pos

        # Track the last cant value for interpolation /
        # 補間用に最後のカント値を追跡 /
        # 跟踪最后的cant值用于插值
        self.cant_lastpos = {}
        self.cant_lastpos['distance'] = 0 #last_pos['distance']
        self.cant_lastpos['value']    = last_pos['cant']

    def process(self, dist, func):
        # Compute the cant value at distance 'dist' using the given interpolation function /
        # 指定距離distにおけるカント値を、与えられた補間関数を用いて計算 /
        # 使用给定的插值函数计算距离dist处的cant值
        # Advance pointer past any segments whose end lies before 'dist' /
        # distより手前で終了する区間をポインタが通過するよう進める /
        # 将指针推进到已超过dist结束的区段之后
        while (self.pointer.overNextpoint(dist)):
            # Has the current element's interval end been exceeded? /
            # 注目している要素区間の終端を超えたか？ /
            # 当前关注的元素区间末端是否已被超越？
            if(self.pointer.seekoriginofcontinuous(self.pointer.pointer['next']) != None):
                self.cant_lastpos['distance'] = self.data_ownt[self.pointer.seekoriginofcontinuous(self.pointer.pointer['next'])]['distance']
                self.cant_lastpos['value']    = self.data_ownt[self.pointer.seekoriginofcontinuous(self.pointer.pointer['next'])]['value']
            self.pointer.seeknext()

        result = 0
        if(self.pointer.pointer['last'] == None):
            # Before the first data element: return the initial last cant value /
            # 最初の要素に到達していない：初期のlast cant値を返す /
            # 尚未到达第一个元素：返回初始的last cant值
            result = self.cant_lastpos['value']
        elif(self.pointer.pointer['next'] == None):
            # Past the last data element: return the stored last cant value /
            # 最後の要素を通過した：格納済みのlast cant値を返す /
            # 已通过最后一个元素：返回存储的last cant值
            result = self.cant_lastpos['value']
        else:
            # General case: process the current interval /
            # 一般の場合の処理 /
            # 一般情况：处理当前区间
            if(self.data_ownt[self.pointer.pointer['next']]['value'] == 'c'):
                # 'c' means the value is unchanged — same as the previous command /
                # 注目区間の前後でvalueが変化しない場合（'c': 直前コマンドと同値） /
                # 'c'表示值不变——与前一命令相同
                result = self.cant_lastpos['value']
            else:
                if(self.data_ownt[self.pointer.pointer['next']]['flag'] == 'i' or self.data_ownt[self.pointer.pointer['last']]['flag'] == 'bt'):
                    # Interpolate or begin-transition flag: compute transition between last and next cant values /
                    # interpolateフラグまたはbegintransitionがある場合：前後のカント値間で遷移を計算 /
                    # 有interpolate或begintransition标志：计算前后cant值之间的过渡
                    if(self.cant_lastpos['value'] != self.data_ownt[self.pointer.pointer['next']]['value']):
                        result = self.transition(self.data_ownt[self.pointer.pointer['next']]['distance'] - self.data_ownt[self.pointer.pointer['last']]['distance'],\
                                                 self.cant_lastpos['value'],\
                                                 self.data_ownt[self.pointer.pointer['next']]['value'],\
                                                 func,\
                                                 dist - self.data_ownt[self.pointer.pointer['last']]['distance'])
                    else:
                        result = self.cant_lastpos['value']
                else:
                    # No interpolate flag: output the lastpos value directly /
                    # interpolateでない場合、lastposのvalueをそのまま出力 /
                    # 非interpolate：直接输出lastpos的值
                    result = self.cant_lastpos['value']
        return result

    def transition(self, L, c1, c2, func, l_intermediate):
        # Interpolate cant value between c1 and c2 over length L using the specified function /
        # 指定された関数で長さLにわたってc1とc2間のカント値を補間 /
        # 使用指定函数在长度L上对c1和c2间的cant值进行插值
        if(func == 'sin'):
            result = (c2-c1)/2*(np.sin(np.pi/L*l_intermediate-np.pi/2)+1)+c1
        else:
            result = (c2-c1)/L*l_intermediate + c1
        return result

class OtherTrack():
    # Computes relative and absolute positions of other (parallel) tracks relative to the own track /
    # 他軌道の自軌道に対する相対位置・絶対位置を計算 /
    # 计算其他（平行）轨道相对于自有轨道的相对位置和绝对位置
    def __init__(self):
        pass

    def relative_position(self, L, radius, ya, yb, l_intermediate):
        '''Return the relative position of an other track at a given point.
        L:              segment length
        radius:         relative radius
        ya, yb:         relative positions at the segment start and end
        l_intermediate: position at which to compute coordinates
        /
        注目点での相対座標を返す。
        L:              区間長
        radius:         相対半径
        ya, yb:         区間始終点での相対位置
        l_intermediate: 座標を求める位置
        /
        返回其他轨道在指定点的相对坐标。
        L:              区段长度
        radius:         相对半径
        ya, yb:         区段起终点的相对位置
        l_intermediate: 求解坐标的位置
        '''
        if L == 0:
            Y = yb
        elif radius != 0:
            sintheta = np.sqrt(L**2+(yb-ya)**2)/(2*radius)
            if np.fabs(sintheta) <= 1:
                # Relative radius and segment length allow circular arc calculation /
                # 与えられた相対半径radiusと区間長Lで座標計算できるか判断する /
                # 给定的相对半径和区段长度允许进行圆弧计算
                # Angle between the chord connecting start/end and the own track /
                # 注目する区間の始終点を結ぶ直線が自軌道となす角 /
                # 连接起终点的弦与自有轨道之间的夹角
                tau = np.arctan((yb-ya)/L)
                # Bearing change over the segment /
                # 注目する区間での方位角の変化 /
                # 该区段内的方位角变化
                theta = 2*np.arcsin(sintheta)

                # Bearing angle relative to own track at the segment start /
                # 区間始点での自軌道に対する方位角 /
                # 区段起点处相对自有轨道的方位角
                phiA = theta/2-tau
                # Center coordinates of the circular arc /
                # 円軌道の中心座標 /
                # 圆弧的中心坐标
                x0 = 0 + radius*np.sin(phiA)
                y0 = ya + radius*np.cos(phiA)
                # Coordinates at the target point /
                # 注目点の座標 /
                # 目标点的坐标
                Y = y0 - radius*np.cos(np.arcsin((l_intermediate-x0)/radius))
            else:
                # Cannot compute with the given radius and L — fallback to straight line /
                # 計算できないradius, Lの場合、直線として計算 /
                # 无法以给定的半径和L计算——回退为直线
                Y = (yb - ya)/L * l_intermediate + ya if L != 0 else 0
        else:
            # radius==0: compute as a straight line /
            # radius==0 なら直線として計算 /
            # radius==0：按直线计算
            Y = (yb - ya)/L * l_intermediate + ya if L != 0 else 0

        return Y

    def rotate(self, tau1):
        '''Return a 2D rotation matrix.
        tau1: rotation angle [rad]
        /
        ２次元回転行列を返す。
        tau1: 回転角度 [rad]
        /
        返回二维旋转矩阵。
        tau1: 旋转角度 [rad]
        '''
        return np.array([[np.cos(tau1), -np.sin(tau1)], [np.sin(tau1),  np.cos(tau1)]])

    def absolute_position_X(self, L, radius, xa, xb, l_intermediate, pos_ownt):
        '''Return the absolute X-direction (horizontal) coordinates of an other track.
        L:              segment length
        radius:         relative radius
        xa, xb:         X positions at the segment start and end
        l_intermediate: position at which to compute coordinates
        pos_ownt:       own-track coordinate info at the target position
        /
        他軌道x方向(水平方向)の絶対座標を返す
        L:              区間長
        radius:         相対半径
        xa, xb:         区間始終点でのx方向位置
        l_intermediate: 座標を求める位置
        pos_ownt:       座標を求める位置での自軌道の座標情報
        /
        返回其他轨道X方向（水平方向）的绝对坐标。
        L:              区段长度
        radius:         相对半径
        xa, xb:         区段起终点的X方向位置
        l_intermediate: 求解坐标的位置
        pos_ownt:       目标位置处的自有轨道坐标信息
        '''
        # Compute relative X position, then rotate by own-track bearing and add own-track coordinates /
        # 相対X位置を計算し、自軌道方位角で回転して自軌道座標に加算する /
        # 计算相对X位置，然后按自有轨道方位角旋转并加上自有轨道坐标
        posrel = np.array([0,self.relative_position(L, radius, xa, xb, l_intermediate)])
        return np.dot(self.rotate(pos_ownt[4]),posrel) + np.array([pos_ownt[1],pos_ownt[2]])

    def absolute_position_Y(self, L, radius, ya, yb, l_intermediate, pos_ownt):
        '''Return the absolute Y-direction (vertical) coordinates of an other track.
        L:              segment length
        radius:         relative radius
        ya, yb:         Y positions at the segment start and end
        l_intermediate: position at which to compute coordinates
        pos_ownt:       own-track coordinate info at the target position
        /
        他軌道y方向(鉛直方向)の絶対座標を返す
        L:              区間長
        radius:         相対半径
        ya, yb:         区間始終点でのy方向位置
        l_intermediate: 座標を求める位置
        pos_ownt:       座標を求める位置での自軌道の座標情報
        /
        返回其他轨道Y方向（垂直方向）的绝对坐标。
        L:              区段长度
        radius:         相对半径
        ya, yb:         区段起终点的Y方向位置
        l_intermediate: 求解坐标的位置
        pos_ownt:       目标位置处的自有轨道坐标信息
        '''
        # Compute relative Y position and add own-track coordinates (no rotation needed for vertical) /
        # 相対Y位置を計算し、自軌道座標に加算する（鉛直方向は回転不要） /
        # 计算相对Y位置并加上自有轨道坐标（垂直方向无需旋转）
        posrel = np.array([0,self.relative_position(L, radius, ya, yb, l_intermediate)])
        return posrel + np.array([pos_ownt[0],pos_ownt[3]])
        # Note: if result_Y is [distance, Yval], should the second term be [element[0], element[3]]? /
        # 註：result_Yが[distance, Yval]なら、第二項は[element[0],element[3]ではないか？ /
        # 注：若result_Y为[distance, Yval]，第二项是否应为[element[0], element[3]]？
