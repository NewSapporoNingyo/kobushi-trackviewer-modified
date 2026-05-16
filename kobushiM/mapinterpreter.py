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
# Lark parser framework and utility modules for math, random, and file I/O /
# Larkパーサフレームワークと、数学・乱数・ファイル入出力のユーティリティモジュール /
# Lark解析器框架以及数学、随机数、文件I/O的实用模块
from lark import Lark, Transformer, v_args, exceptions
import math
import random
import os

# Import project-local modules for header parsing, map data structures, and grammar loading /
# ヘッダー解析・マップデータ構造・文法ロード用のプロジェクト内モジュールをインポート /
# 导入项目内模块：表头解析、地图数据结构、语法加载
from . import loadheader
from . import mapobj
from . import loadmapgrammer

# Decorator: inline all rule arguments so they are passed as flat args instead of a list /
# デコレーター：ルール引数をリストではなくフラット引数として受け取るようインライン化 /
# 装饰器：将规则参数内联，使其以扁平参数而非列表形式传入
@v_args(inline=True)
class ParseMap(Transformer):
    # Import standard Python operators for use as grammar action symbols /
    # 文法アクション記号として使うため、Python標準演算子をインポート /
    # 导入Python标准运算符，用作语法动作符号
    from operator import sub, mul, mod, neg, pos

    # Map grammar number tokens to Python float, null to NoneType /
    # 文法上の数値トークンをPython floatに、nullをNoneTypeにマッピング /
    # 将语法数字标记映射为Python float，null映射为NoneType
    number = float
    null_value = type(None)

    def __init__(self,env,parser,prompt=False):
        # Store prompt mode flag (used for interactive debugging/unit tests) /
        # プロンプトモードフラグを保存（対話的デバッグ/単体テスト時に使用） /
        # 存储提示模式标志（用于交互式调试/单元测试）
        self.promptmode = prompt

        # Load grammar definition; either reuse an existing Lark parser or create a new one /
        # 文法定義をロード。既存のLarkパーサを再利用するか、新規作成 /
        # 加载语法定义；复用已有的Lark解析器或创建新的
        grammer_fp = loadmapgrammer.loadmapgrammer()
        # Optimization: enable Lark cache to speed up subsequent cold starts /
        # 最適化：Larkキャッシュを有効化し、二次起動・コールドスタートを高速化 /
        # 优化：开启 Lark cache 以提升二次加载及冷启动性能
        self.parser = Lark(grammer_fp.read(), parser='lalr', maybe_placeholders=True, cache=True) if parser == None else parser
        grammer_fp.close()

        # Set or inherit the map environment; mark whether this is the root parser /
        # マップ環境を設定または継承し、ルートパーサかどうかを記録 /
        # 设置或继承地图环境，并标记是否为根解析器
        if(env==None):
            self.environment = mapobj.Environment()
            self.isroot=True
        else:
            self.environment = env
            self.isroot=False

    def set_distance(self, value):
        # Set the current distance (mileage) value along the track /
        # 距離程設定 /
        # 设置当前沿途里程距离
        self.environment.predef_vars['distance'] = float(value)
        self.environment.controlpoints.add(float(value))

    def call_predefined_variable(self, argument):
        # Call a predefined variable (in practice, only 'distance' is used) /
        # 規定変数呼び出し（実質的にはdistanceのみ） /
        # 调用预定义变量（实际只有distance）
        return self.environment.predef_vars[argument.lower()]

    def set_variable(self, *argument):
        # Assign a value to a user-defined variable /
        # 変数設定 /
        # 变量赋值
        self.environment.variable[argument[0].lower()]=argument[1]

    def call_variable(self, argument):
        # Retrieve the value of a user-defined variable /
        # 変数呼び出し /
        # 变量调用
        return self.environment.variable[argument.lower()]

    def call_function(self, *argument):
        # Invoke a mathematical function: 'rand' for random, 'abs' for absolute, others via math module /
        # 数学関数呼び出し：'rand'は乱数、'abs'は絶対値、その他はmathモジュール経由 /
        # 数学函数调用：'rand'调用随机数，'abs'调用绝对值，其他通过math模块调用
        label = argument[0].lower()
        if (label == 'rand'):
            if(argument[1] == None):
                # rand() with no argument — returns [0, 1) /
                # 引数なしrand — [0, 1) の乱数を返す /
                # 无参数rand — 返回 [0, 1) 的随机数
                return random.random()
            else:
                return random.uniform(0,argument[1])
        elif(label == 'abs'):
            return getattr(math,'fabs')(*argument[1:])
        else:
            return getattr(math,label)(*argument[1:])

    def remquote(self, value):
        # Remove surrounding single quotes from a string literal /
        # 文字列からシングルクォート除去 /
        # 移除字符串字面量的单引号
        return value.replace("\'","")

    def add(self, *argument):
        # Add operator: support string concatenation with implicit numeric-to-string conversion /
        # add演算子：文字列結合（暗黙の数値→文字列変換付き） /
        # 加法运算符：支持字符串拼接，并隐式将数字转为字符串
        if(len(argument) == 2):
            if((type(argument[0]) == type(str()) and type(argument[1]) == type(str())) or (type(argument[0]) != type(str()) and type(argument[1]) != type(str()))):
                return argument[0]+argument[1]
            elif(type(argument[0]) == type(str())):
                # If one arg is string and the other is number, convert number to int string and concatenate /
                # 一方が文字列で一方が数値なら、数値を整数文字列に変換して結合 /
                # 若一个参数为字符串另一个为数字，则将数字转为整数字符串后拼接
                return argument[0]+str(int(argument[1]))
            else:
                return str(int(argument[0]))+argument[1]
        return 0

    def div(self, *argument):
        # Division operator: returns signed infinity on division by zero /
        # div演算子：ゼロ除算時は符号付き無限大を返す /
        # 除法运算符：除以零时返回带符号的无穷大
        if(len(argument) == 2):
            return argument[0] / argument[1] if argument[1] != 0 else math.copysign(math.inf,argument[0])
        return 0

    def map_element(self, *argument):
        # Process a map element statement: dispatch to the appropriate object method /
        # マップ要素文を処理し、適切なオブジェクトメソッドに振り分ける /
        # 处理地图元素语句，分派到相应的对象方法
        #import pdb
        #pdb.set_trace()
        if(self.promptmode):
            # Prompt mode (for interactive testing): only print parsed structure, no actual data population /
            # プロンプトモード（テスト時のみ使用）のとき、マップ要素の構文解析だけ行い、実際のデータ投入はしない /
            # 提示模式（仅测试时用）：只输出解析后的结构，不实际填充数据
            a = 1
            for i in argument:
                if(i.data == 'mapobject'):
                    label = i.children[0]
                    key = i.children[1]
                    print('mapobject: label=',label,', key=',key)
                elif(i.data == 'mapfunc'):
                    label = i.children[0]
                    f_arg = i.children[1:]
                    print('mapfunc: label=',label,', args=',f_arg)
            print()
        else:
            # Extract the first map element name and lowercase it for case-insensitive matching /
            # 先頭のマップ要素名を抽出して小文字に変換（大文字小文字を区別しないマッチのため） /
            # 提取第一个地图元素名并转为小写，以便不区分大小写匹配
            first_obj = argument[0].children[0].lower()
            if(first_obj in ['curve','gradient','legacy']):
                # Elements related to the own track: navigate the attribute chain and call the final method /
                # 自軌道に関係する要素：属性チェーンを辿って最終メソッドを呼び出す /
                # 与自有轨道相关的元素：遍历属性链并调用最终方法
                temp = getattr(self.environment.own_track, first_obj)
                for elem in argument[1:]:
                    # Walk through intermediate elements (e.g., Track.X.Interpolate(...) or Track.Position(...)) /
                    # 中間要素を辿る（例: Track.X.Interpolate(...) or Track.Position(...) ） /
                    # 遍历中间元素（例如 Track.X.Interpolate(...) 或 Track.Position(...) ）
                    if(elem.data == 'mapfunc'):
                        break
                    temp = getattr(temp, elem.children[0].lower())
                getattr(temp, argument[-1].children[0].lower())(*argument[-1].children[1:])
            elif(first_obj in ['station']):
                # Station element: retrieve the station key and build argument list with key prepended /
                # station要素：stationKeyを取得し、keyを先頭に付加した引数リストを構築 /
                # 车站元素：获取stationKey，并将key添加到参数列表头部
                key = argument[0].children[1]
                temp = getattr(self.environment, first_obj)
                for elem in argument[1:]:
                    # Check for child elements before reaching the function call /
                    # 関数呼び出しに到達する前に子要素を確認 /
                    # 到达函数调用前检查子元素
                    if(elem.data == 'mapfunc'):
                        break
                    temp = getattr(temp, elem.children[0].lower())
                if(key == None):
                    # No station key provided: pass the map-file arguments as-is /
                    # stationKeyが指定されていない場合、マップファイルで指定された引数をそのまま渡す /
                    # 未指定stationKey：直接传递地图文件中指定的参数
                    temp_argv=argument[-1].children[1:]
                else:
                    # Station key present: prepend it to the argument list /
                    # stationKeyがある場合、マップファイル指定の引数の先頭にkeyを追加する /
                    # 有stationKey：将其添加到参数列表的最前面
                    temp_argv = [key]
                    temp_argv.extend(argument[-1].children[1:])
                getattr(temp, argument[-1].children[0].lower())(*temp_argv)
            elif(first_obj in ['track']):
                # External track element: build arg list with track key, handle Cant as a special case /
                # 他軌道要素：trackKey付き引数リストを構築し、Cantは特殊ケースとして扱う /
                # 外部轨道元素：构建带trackKey的参数列表，Cant作为特殊情况处理
                key = argument[0].children[1]
                temp_argv = [key]
                temp_argv.extend(argument[-1].children[1:])
                temp = getattr(self.environment, 'othertrack')
                if(argument[1].children[0].lower() == 'cant' and argument[1].data == 'mapfunc'):
                    # Track[key].Cant(x): use the cant interpolate path /
                    # Track[key].Cant(x)かどうか：cant用の補間パスを使用 /
                    # Track[key].Cant(x)：使用cant的插值路径
                    temp = getattr(temp, 'cant')
                    getattr(temp, 'interpolate')(*temp_argv)
                else:
                    # General case: walk the attribute chain like for own-track elements /
                    # 一般の要素の場合：自軌道と同様に属性チェーンを辿る /
                    # 一般情况：像自有轨道一样遍历属性链
                    for elem in argument[1:]:
                        if(elem.data == 'mapfunc'):
                            break
                        temp = getattr(temp, elem.children[0].lower())
                    getattr(temp, argument[-1].children[0].lower())(*temp_argv)
            elif(first_obj in ['speedlimit']):
                # Speed limit element: dispatch directly to the speedlimit object /
                # 速度制限要素：speedlimitオブジェクトに直接振り分け /
                # 限速元素：直接分派到speedlimit对象
                temp = getattr(self.environment, 'speedlimit')
                getattr(temp, argument[-1].children[0].lower())(*argument[-1].children[1:])

    def include_file(self, path):
        # Include an external map file: resolve path relative to root, create sub-interpreter, and load /
        # 外部ファイルインクルード：ルートからの相対パスを解決し、サブインタープリタを作成してロード /
        # 外部文件包含：相对于根路径解析，创建子解释器并加载
        input = loadheader.joinpath(self.environment.rootpath, path)
        interpreter = ParseMap(self.environment,self.parser)
        try:
            interpreter.load_files(input)
        except OSError as e:
            print('Warning: '+str(e))

    def start(self, *argument):
        # Top-level grammar rule: return the populated environment after all statements are processed /
        # 最上位文法ルール：全ステートメント処理後、構築されたenvironmentを返す /
        # 顶层语法规则：所有语句处理完毕后返回填充好的environment
        if(all(elem == None for elem in argument)):
            return self.environment

    def load_files(self, path, datastring = None, virtualroot = None, virtualfilename = None):
        # Load and parse a map file (or an in-memory string), build the syntax tree, and transform it /
        # マップファイル（またはメモリ上文字列）をロード・構文解析し、ツリーを構築・変換 /
        # 加载并解析地图文件（或内存字符串），构建语法树并变换
        if datastring is None:
            # Load from a real file: determine path, root directory, and encoding via header /
            # 実ファイルからロード：ヘッダーを解析してファイルパス、ルートディレクトリ、エンコーディングを決定 /
            # 从真实文件加载：通过表头获取文件路径、根目录和编码
            f_path, rootpath_tmp, f_encoding = loadheader.loadheader(path,'BveTs Map ',2)
            def readfile(filepath,fileencode):
                # Helper to read the file content after consuming the header line /
                # ヘッダー行を空読みした後、ファイル内容を読み込むヘルパー /
                # 辅助函数：消费表头行后读取完整的文件内容
                try:
                    f=open(filepath,'r',encoding=fileencode)
                    f.readline()
                    # Skip header line /
                    # ヘッダー行空読み /
                    # 跳过表头行
                    linecount = 1

                    filebuffer = f.read()
                    f.close()
                except:
                    f.close()
                    raise
                return filebuffer
            if(self.isroot):
                # Record root path only for top-level map files /
                # 最上層のマップファイルの場合のみ、ルートパスを記録 /
                # 仅对最顶层地图文件记录根路径
                self.environment.rootpath = rootpath_tmp

            try:
                # Attempt to open the file with the encoding declared in the header /
                # ファイルオープン — ヘッダー指定のエンコーディングで読み込みを試行 /
                # 打开文件 — 尝试使用表头声明的编码读取
                filebuffer = readfile(f_path,f_encoding)
            except UnicodeDecodeError as e:
                # Fallback: if decoding fails, try an alternate encoding (utf-8 ↔ CP932) /
                # ファイル指定のエンコードでオープンできない時 — 代替エンコードを試行 (utf-8 ↔ CP932) /
                # 读取失败时 — 尝试备选编码（utf-8 ↔ CP932）
                if f_encoding.casefold() == 'utf-8':
                    encode_retry = 'CP932'
                else:
                    encode_retry = 'utf-8'
                print('Warning: '+str(f_path.name)+' cannot be decoded with '+f_encoding+'. Kobushi tries to decode with '+encode_retry+'.')
                filebuffer = readfile(f_path,encode_retry)
        else:
            # Parse from an in-memory string instead of a real file /
            # 実ファイルの代わりに文字列をパースする場合の処理 /
            # 处理从内存字符串而非真实文件解析的情况
            filebuffer = datastring
            rootpath_tmp = virtualroot
            f_path = virtualfilename
            self.environment.rootpath = rootpath_tmp

        try:
            # Parse the source text into a Lark syntax tree /
            # 構文解析 — ソーステキストをLark構文木に変換 /
            # 语法解析 — 将源文本转为Lark语法树
            print('Parsing syntax tree...')
            tree = self.parser.parse(filebuffer)
        except Exception as e:
            raise RuntimeError('ParseError: in file '+str(f_path)+'\n'+str(e))

        #print(tree)
        #import pdb
        #pdb.set_trace()
        try:
            # Transform the syntax tree: interpret map elements and populate data objects /
            # ツリー処理 — 構文木を解釈し、マップ要素をデータオブジェクトに格納 /
            # 语法树处理 — 解释地图元素并填充到数据对象中
            print('Interpreting map elements...')
            self.transform(tree)
        except Exception as e:
            raise RuntimeError('IntepretationError: in file '+str(f_path)+', distance='+str(self.environment.predef_vars['distance'])+'\n'+str(e))
            #print(self.environment.variable)


        if(self.isroot):
            # After the root map file is fully loaded, sort all data by distance and calculate geometry /
            # 最上層のマップファイルのロードが完了したら、データを距離でソートして幾何計算を実行 /
            # 最顶层地图文件加载完成后，按距离排序全部数据并计算几何信息
            print('Calculating track geometry and sorting distances...')
            self.environment.controlpoints.relocate()
            self.environment.own_track.relocate()
            self.environment.othertrack.relocate()
            self.environment.speedlimit.relocate()

        print(str(f_path.name)+' loaded.')
        return self.environment
