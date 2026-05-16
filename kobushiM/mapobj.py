'''
    Copyright 2021-2023 konawasabi

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
# Import project header loader and regex module /
# プロジェクトのヘッダーローダーと正規表現モジュールをインポート /
# 导入项目表头加载器和正则表达式模块
from . import loadheader
import re

class Environment():
    '''A class that bundles all map elements together.
    self.rootpath:   Path to the parent directory of the Map file
    self.variable:   dict storing variables
    self.own_track:  Object storing own-track data
    self.station:    Object storing station data
    self.controlpoints: List of distance values where map elements are specified
    /
    Mapの構成要素をまとめるクラス。
    self.rootpath:   Mapファイルの親ディレクトリへのパス
    self.variable:   変数を格納するdict
    self.own_track:  自軌道データを格納するオブジェクト
    self.station:    stationデータを格納するオブジェクト
    self.controlpoints: Map要素が指定されている距離程リスト
    /
    汇总所有地图元素的类。
    self.rootpath:   地图文件的父目录路径
    self.variable:   存储变量的字典
    self.own_track:  存储自有轨道数据的对象
    self.station:    存储车站数据的对象
    self.controlpoints: 已指定地图元素的距离位置列表
    '''
    def __init__(self):
        # Initialize all sub-objects and default environment state /
        # 全サブオブジェクトとデフォルトの環境状態を初期化 /
        # 初始化所有子对象和默认环境状态
        self.rootpath = ''
        self.predef_vars = {'distance':0.0}
        self.variable = {}
        self.own_track = Owntrack(self)
        self.station = Station(self)
        self.controlpoints = ControlPoints(self)
        self.othertrack = Othertrack(self)
        self.speedlimit = SpeedLimit(self)

class Owntrack():
    '''Own-track data class.
    (1) Subclasses that transform own-track map elements parsed by the parser:
        curvefunc:      curve element operations
        legacyfunc:     legacy element operations (turn, curve, pitch, fog)
        gradientfunc:   gradient element operations
    (2) Variables:
        self.data:          Map element list
        self.environment:   Reference to the parent class (Environment)
    /
    自軌道データクラス
    (1)パーサが読み取った自軌道マップ要素を変換するサブクラス
        curvefunc:      curve要素の操作
        legacyfunc:     legacy要素(turn, curve, pitch, fog)の操作
        gradientfunc:   gradient要素の操作
    (2)変数類
        self.data:          マップ要素リスト
        self.environment:   親クラス（Environment）への参照
    /
    自轨道数据类
    (1) 转换解析器读取的自有轨道地图元素的子类：
        curvefunc:      curve元素操作
        legacyfunc:     legacy元素操作（turn, curve, pitch, fog）
        gradientfunc:   gradient元素操作
    (2) 变量：
        self.data:          地图元素列表
        self.environment:   对父类（Environment）的引用
    '''

    class curvefunc():
        # Handler for Curve.* map commands /
        # Curve.* マップコマンドのハンドラ /
        # Curve.* 地图命令的处理程序
        def __init__(self,p):
            self.parent = p
        def setgauge(self, *a):
            # Set track gauge /
            # 軌道ゲージを設定 /
            # 设置轨道轨距
            self.parent.putdata('gauge',a[0])
        def gauge(self, *a):
            self.setgauge(*a)
        def setcenter(self, *a):
            # Set track center offset /
            # 軌道中心オフセットを設定 /
            # 设置轨道中心偏移
            self.parent.putdata('center',a[0])
        def setfunction(self, *a):
            # Set interpolation function: 0→sine, otherwise→linear /
            # 補間関数を設定：0→サイン、それ以外→線形 /
            # 设置插值函数：0→正弦，其他→线性
            self.parent.putdata('interpolate_func','sin' if a[0] == 0 else 'line')
        def begintransition(self, *a):
            # Mark beginning of transition: set radius and cant to None with 'bt' flag /
            # 緩和区間開始：radiusとcantをNoneで'bt'フラグ付きで設定 /
            # 标记过渡区段开始：以'bt'标志将radius和cant设为None
            self.parent.putdata('radius',None,'bt')
            self.parent.putdata('cant',None,'bt')
        def begincircular(self, *a):
            self.begin(*a)
        def begin(self, *a):
            # Begin a constant curve: set radius and cant (cant defaults to 0) /
            # 定曲線開始：radiusとcantを設定（cantはデフォルト0） /
            # 开始定曲线：设置radius和cant（cant默认为0）
            if(len(a) == 2):
                self.parent.putdata('radius',a[0])
                self.parent.putdata('cant',a[1])
            elif(len(a) == 1):
                self.parent.putdata('radius',a[0])
                self.parent.putdata('cant',0)
        def end(self, *a):
            # End a curve: set radius=0 and cant=0 /
            # 曲線終了：radius=0, cant=0を設定 /
            # 曲线结束：设置radius=0, cant=0
            self.begin(0,0)
        def interpolate(self, *a):
            # Interpolated curve: set radius/cant with 'i' flag /
            # 補間曲線：radius/cantを'i'フラグ付きで設定 /
            # 插值曲线：以'i'标志设置radius/cant
            if(len(a) == 2):
                self.parent.putdata('radius',a[0],'i')
                self.parent.putdata('cant',a[1],'i')
            elif(len(a) == 1):
                self.parent.putdata('radius',a[0],'i')
                self.parent.putdata('cant',None,'i')
        def change(self, *a):
            # Change: alias for begin /
            # Change：beginのエイリアス /
            # Change：begin的别名
            self.begin(*a)

    class legacyfunc():
        # Handler for legacy Turn/Curve/Pitch/Fog commands /
        # 旧形式のTurn/Curve/Pitch/Fogコマンドのハンドラ /
        # 旧格式Turn/Curve/Pitch/Fog命令的处理程序
        def __init__(self,p):
            self.parent = p
        def turn(self, *a):
            self.parent.putdata('turn',a[0])
        def curve(self, *a):
            if(len(a) == 2):
                self.parent.putdata('radius',a[0])
                self.parent.putdata('cant',a[1])
            elif(len(a) == 1):
                self.parent.putdata('radius',a[0])
                self.parent.putdata('cant',0)
        def pitch(self, *a):
            self.parent.putdata('gradient',a[0])
        def fog(self, *a):
            # Fog is defined in the file but does not affect track geometry /
            # Fogはファイルで定義されるが軌道幾何に影響しない /
            # Fog在文件中定义但不影响轨道几何
            return None

    class gradientfunc():
        # Handler for Gradient.* map commands /
        # Gradient.* マップコマンドのハンドラ /
        # Gradient.* 地图命令的处理程序
        def __init__(self,p):
            self.parent = p
        def begintransition(self, *a):
            # Begin gradient transition /
            # 勾配緩和区間開始 /
            # 开始坡度过渡区段
            self.parent.putdata('gradient',None,'bt')
        def begin(self, *a):
            # Begin constant gradient /
            # 定勾配区間開始 /
            # 开始定坡度区段
            self.parent.putdata('gradient',a[0])
        def beginconst(self, *a):
            self.begin(*a)
        def end(self, *a):
            # End gradient: set to 0 (level) /
            # 勾配終了：0（水平）に設定 /
            # 坡度结束：设为0（水平）
            self.begin(0)
        def interpolate(self, *a):
            # Interpolated gradient /
            # 補間勾配 /
            # 插值坡度
            self.parent.putdata('gradient',a[0],'i')

    def __init__(self, p):
        # Initialize data list, coordinate arrays, and sub-function handlers /
        # データリスト・座標配列・サブ関数ハンドラを初期化 /
        # 初始化数据列表、坐标数组和子功能处理器
        self.data = []

        self.x = []
        self.y = []

        self.position = []

        self.environment = p

        self.curve = self.curvefunc(self)
        self.legacy = self.legacyfunc(self)
        self.gradient = self.gradientfunc(self)

    def putdata(self,key,value,flag=''):
        '''Append a map element entry to the data list as a dict.
        distance
            Value of the 'distance' variable at the time of invocation
        key
            Type of the map element
        value
            If None, substitute with 'c' meaning "same as the previous command's value"
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        /
        dataリストへ要素をdictとして追加する。
        distance
            呼び出された時点でのdistance変数の値
        key
            マップ要素の種別
        value
            Noneの場合、'c':直前のコマンドで指定された値と同一を代入
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        /
        将地图元素条目以字典形式追加到data列表。
        distance
            调用时distance变量的值
        key
            地图元素的类型
        value
            若为None，则代入'c'表示“与前一命令指定的值相同”
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        '''
        self.data.append({'distance':self.environment.predef_vars['distance'], 'value':'c' if value == None else value, 'key':key, 'flag':flag})

    def relocate(self):
        # Sort all own-track data entries by distance /
        # 全自軌道データ要素を距離でソート /
        # 按距离排序所有自有轨道数据条目
        self.data = sorted(self.data, key=lambda x: x['distance'])

class Station():
    def load(self, *argvs):
        # Construct an absolute path from the given filename and rootpath /
        # 与えられたファイル名とrootpathから絶対パスを作成する /
        # 根据给定的文件名和rootpath构造绝对路径
        input = loadheader.joinpath(self.environment.rootpath, argvs[0])

        # Determine whether it is a station list file /
        # station listファイルかどうか判定する /
        # 判断是否为车站列表文件
        f_path, rootpath_tmp, f_encoding = loadheader.loadheader(input,'BveTs Station List ',0.04)

        def read_stationlist(path,file_encoding):
            # Parse the station list CSV file into a {key: name} dict /
            # 駅リストCSVファイルを {key: name} 辞書にパース /
            # 将车站列表CSV文件解析为 {key: name} 字典
            result_stations = {}
            try:
                f=open(f_path,'r',encoding=file_encoding)
                f.readline()
                # Skip header line /
                # ヘッダー行空読み /
                # 跳过表头行
                while True:
                    buff = f.readline()
                    if(buff==''):
                        # EOF reached /
                        # EOFに達した /
                        # 已到文件末尾
                        break
                    buff = re.sub('#.*\n','\n',buff)
                    # Remove comments (lines starting with #) /
                    # コメントを除去する（#で始まる行） /
                    # 移除注释（以#开头的行内容）
                    buff = re.sub('\t', '', buff)
                    # Remove tab characters /
                    # tabを除去する /
                    # 移除制表符
                    buff = re.sub(' ', '', buff)
                    # Remove space characters /
                    # スペースを除去する /
                    # 移除空格
                    if(buff=='\n' or buff.count(',')<1):
                        # Skip blank lines or lines without a comma separator /
                        # 空白行（コメントのみの行など）、コンマ区切りが存在しない行なら次の行に進む /
                        # 跳过空行或没有逗号分隔符的行
                        continue
                    buff = buff.split(',')
                    result_stations[buff[0].lower()]=buff[1].replace('\"','')
                f.close()
            except:
                f.close()
                raise
            return result_stations

        try:
            self.stationkey = read_stationlist(f_path,f_encoding)
        except UnicodeDecodeError as e:
            # If decoding fails with the header-declared encoding, try the alternate encoding /
            # ヘッダー指定のエンコードでデコード失敗時、代替エンコードを試行 /
            # 如果使用表头声明的编码解码失败，尝试备选编码
            if f_encoding.casefold() == 'utf-8':
                encode_retry = 'shift_jis'
            else:
                encode_retry = 'utf-8'
            try:
                self.stationkey = read_stationlist(f_path,encode_retry)
            except Exception as e:
                raise RuntimeError('File encoding error: '+str(f_path))

    def put(self, *argvs):
        # Store a station entry at the current distance /
        # 現在の距離程に駅エントリを格納 /
        # 在当前距离位置存储车站条目
        #self.position.append({'distance':self.environment.variable['distance'], 'stationkey':argvs[0].lower()})
        self.position[self.environment.predef_vars['distance']]=argvs[0].lower()

    def __init__(self, parent):
        # Initialize station position dict and environment reference /
        # 駅位置辞書と環境参照を初期化 /
        # 初始化车站位置字典和环境引用
        self.position = {}
        self.stationkey = {}
        self.environment = parent

class ControlPoints():
    '''Creates a list of distance values where map elements exist.
    /
    マップ要素が存在する距離程のリストを作る
    /
    创建存在地图元素的距离位置列表
    '''
    def __init__(self, parent):
        # Initialize the control points list and environment reference /
        # 制御点リストと環境参照を初期化 /
        # 初始化控制点列表和环境引用
        self.list_cp = []
        self.environment = parent

    def add(self, value):
        # Add a distance value to the control points list /
        # 制御点リストに距離値を追加 /
        # 向控制点列表添加一个距离值
        self.list_cp.append(value)

    def relocate(self):
        '''Remove duplicates from self.list_cp and sort by distance.
        /
        self.list_cpについて、重複する要素を除去して距離順にソートする。
        /
        对self.list_cp去重并按距离排序。
        '''
        self.list_cp = sorted(list(set(self.list_cp)))

class Othertrack():
    class setposition():
        # Handler for setting X/Y position and radius of other tracks /
        # 他軌道のX/Y座標・半径を設定するハンドラ /
        # 设置其他轨道X/Y坐标和半径的处理程序
        def __init__(self, parent, dimension):
            self.parent = parent
            self.dimension = dimension
        def interpolate(self, *a):
            # Interpolate position and/or radius data for the given track key /
            # 指定トラックキーの座標・半径データを補間 /
            # 对指定轨道键的坐标/半径数据进行插值
            if(len(a)==1):
                # Position only, radius set to None /
                # 座標のみ、半径はNone /
                # 仅坐标，半径设为None
                self.parent.putdata(a[0],self.dimension+'.position',None)
                self.parent.putdata(a[0],self.dimension+'.radius',None)
            elif(len(a)==2):
                self.parent.putdata(a[0],self.dimension+'.position',a[1])
                self.parent.putdata(a[0],self.dimension+'.radius',None)
            elif(len(a)>=3):
                self.parent.putdata(a[0],self.dimension+'.position',a[1])
                self.parent.putdata(a[0],self.dimension+'.radius',a[2])

    class cantfunc():
        # Handler for Cant-related operations on other tracks /
        # 他軌道のCant関連操作ハンドラ /
        # 其他轨道的Cant相关操作处理程序
        def __init__(self, parent):
            self.parent = parent
        def setgauge(self, *a):
            self.parent.putdata(a[0],'gauge',a[1])
        def setcenter(self, *a):
            self.parent.putdata(a[0],'center',a[1])
        def setfunction(self, *a):
            # 0→sine interpolation, otherwise→linear /
            # 0→サイン補間、それ以外→線形 /
            # 0→正弦插值，其他→线性
            self.parent.putdata(a[0],'interpolate_func','sin' if a[1] == 0 else 'line')
        def begintransition(self, *a):
            self.parent.putdata(a[0],'cant',None,'bt')
        def begin(self, *a):
            self.parent.putdata(a[0],'cant',a[1],'i')
        def end(self, *a):
            self.parent.putdata(a[0],'cant',0,'i')
        def interpolate(self, *a):
            if len(a) == 1:
                self.parent.putdata(a[0],'cant',None,'i')
            else:
                self.parent.putdata(a[0],'cant',a[1],'i')

    def __init__(self,p):
        # Initialize the other-track data dict, environment, and sub-handlers /
        # 他軌道データ辞書・環境・サブハンドラを初期化 /
        # 初始化其他轨道数据字典、环境和子处理器
        self.data = {}
        self.environment = p
        self.x = self.setposition(self, 'x')
        self.y = self.setposition(self, 'y')
        self.cant = self.cantfunc(self)

    def position(self, *a):
        # Forward position calls to both X and Y setposition handlers /
        # 位置呼び出しをX/Y両方のsetpositionハンドラに転送 /
        # 将位置调用转发给X和Y两个setposition处理器
        if(len(a)==3):
            self.x.interpolate(a[0],a[1] if a[1] != None else 0,0)
            self.y.interpolate(a[0],a[2] if a[2] != None else 0,0)
        elif(len(a)==4):
            self.x.interpolate(a[0],a[1] if a[1] != None else 0,a[3] if a[3] != None else 0)
            self.y.interpolate(a[0],a[2] if a[2] != None else 0,0)
        elif(len(a)>=5):
            self.x.interpolate(a[0],a[1] if a[1] != None else 0,a[3] if a[3] != None else 0)
            self.y.interpolate(a[0],a[2] if a[2] != None else 0,a[4] if a[4] != None else 0)

    def gauge(self, *a):
        '''Legacy notation for Cant.SetGauge.
        /
        Cant.SetGaugeの旧表記
        /
        Cant.SetGauge的旧写法。
        '''
        self.cant.setgauge(*a)

    def putdata(self,trackkey,elementkey,value,flag=''):
        '''Append a map element entry to the other-track data list as a dict.
        trackkey
            Other track key
        elementkey
            Type of the map element
                'x.position' : X coordinate
                'x.radius'   : relative radius in X direction
                'y.position' : Y coordinate
                'y.radius'   : relative radius in Y direction
        value
            If None, substitute with 'c' meaning "same as the previous command's value"
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        /
        dataリストへ要素をdictとして追加する。
        trackkey
            他軌道キー
        elementkey
            マップ要素の種別
                'x.position' : x方向座標
                'x.radius'   : x方向相対半径
                'y.position' : y方向座標
                'y.radius'   : y方向相対半径
        value
            Noneの場合、'c':直前のコマンドで指定された値と同一を代入
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        /
        将地图元素条目以字典形式追加到其他轨道数据列表。
        trackkey
            其他轨道键
        elementkey
            地图元素的类型
                'x.position' : X方向坐标
                'x.radius'   : X方向相对半径
                'y.position' : Y方向坐标
                'y.radius'   : Y方向相对半径
        value
            若为None，则代入'c'表示“与前一命令指定的值相同”
        flag
            '':change, 'i':interpolate, 'bt':begintransition
        '''
        if type(trackkey) == float:
            trackkey_lc = str(int(trackkey)).lower()
        else:
            trackkey_lc = str(trackkey).lower()
        if trackkey_lc not in self.data.keys():
            self.data[trackkey_lc] = []
        self.data[trackkey_lc].append({'distance':self.environment.predef_vars['distance'], 'value':'c' if value == None else value, 'key':elementkey, 'flag':flag})

    def relocate(self):
        # Sort all other-track data entries by distance and compute per-track min/max distance range /
        # 全他軌道データ要素を距離でソートし、トラックごとの距離範囲（最小/最大）を計算 /
        # 按距离排序所有其他轨道数据条目，并计算每个轨道的距离范围（最小/最大）
        self.cp_range = {}
        for trackkey in self.data.keys():
            self.data[trackkey]     = sorted(self.data[trackkey], key=lambda x: x['distance'])
            self.cp_range[trackkey] = {'min':min(self.data[trackkey], key=lambda x: x['distance'])['distance'],'max':max(self.data[trackkey], key=lambda x: x['distance'])['distance']}

class SpeedLimit():
    # Data model for speed limit map elements /
    # 速度制限マップ要素のデータモデル /
    # 限速地图元素的数据模型
    def __init__(self, parent):
        self.data = []
        self.environment = parent

    def begin(self, *a):
        # Record a speed limit value at the current distance /
        # 現在の距離程に制限速度値を記録 /
        # 在当前距离位置记录限速值
        self.data.append({'distance': self.environment.predef_vars['distance'], 'speed': a[0] if len(a) > 0 else 0})

    def end(self, *a):
        # Record the end of a speed limit zone (speed=None) /
        # 速度制限区間終了を記録（speed=None） /
        # 记录限速区段结束（speed=None）
        self.data.append({'distance': self.environment.predef_vars['distance'], 'speed': None})

    def relocate(self):
        # Sort speed limit data by distance /
        # 速度制限データを距離でソート /
        # 按距离排序限速数据
        self.data = sorted(self.data, key=lambda x: x['distance'])
