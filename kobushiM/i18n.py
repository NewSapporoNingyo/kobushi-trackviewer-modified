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

# Language code constants for Japanese, English, and Simplified Chinese /
# 日本語・英語・簡体字中国語の言語コード定数 /
# 日语、英语、简体中文的语言代码常量
_JA = 'ja'
_EN = 'en'
_ZH = 'zh'

# Mapping of supported language codes to their display names /
# サポート対象言語コードと表示名の対応表 /
# 支持的语言代码与显示名称的映射
SUPPORTED_LANGUAGES = {
    _JA: '日本語',
    _EN: 'English',
    _ZH: '简体中文',
}

# Master translation dictionary: stores UI text for each supported language /
# 全翻訳辞書：各サポート言語のUIテキストを格納 /
# 主翻译字典：存储每种支持语言的UI文本
_translations = {
    _JA: {
        'lang.name': '日本語',

        # Window titles / ウィンドウタイトル / 窗口标题
        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': '他軌道の設定',
        'window.font': 'フォント',

        # Menu / メニュー / 菜单
        'menu.file': 'ファイル',
        'menu.options': 'オプション',
        'menu.help': 'ヘルプ',
        'menu.lang': '言語選択 / Select Language / 语言选择',

        'menu.open': '開く...',
        'menu.reload': '再読み込み',
        'menu.save_image': '画像を保存...',
        'menu.save_trackdata': '線形情報を保存...',
        'menu.exit': '終了',

        'menu.controlpoints': '座標制御点...',
        'menu.plotlimit': '描画可能区間...',
        'menu.profylimit': '断面図y軸範囲...',
        'menu.font': 'フォント...',

        'menu.help_ref': 'ヘルプ...',
        'menu.about': 'Kobushiについて...',

        # Buttons / ボタン / 按钮
        'button.open': '開く',
        'button.ok': 'OK',
        'button.reset': 'リセット',
        'button.cancel': 'キャンセル',

        # Control panel / 操作パネル / 控制面板
        'frame.aux_info': '補助情報',
        'frame.chart_visibility': 'チャート表示',

        # Checkboxes / チェックボックス / 复选框
        'chk.station_pos': '駅座標',
        'chk.station_name': '駅名',
        'chk.station_mileage': '駅位置程',
        'chk.gradient_pos': '勾配変化点',
        'chk.gradient_val': '勾配値',
        'chk.curve_val': '曲線半径',
        'chk.prof_othert': '縦断面図他軌道',
        'chk.speedlimit': '速度制限',

        'chk.gradient_graph': '縦断面図',
        'chk.curve_graph': '曲線半径図',

        # Grid control / グリッド制御 / 网格控制
        'frame.grid': 'グリッド線',
        'grid.fixed': '固定',
        'grid.movable': '可動',
        'grid.none': '無',

        # Mode selection / モード選択 / 模式选择
        'frame.mode': 'モード選択',
        'mode.pan': '移動',
        'mode.measure': '測量',

        # Info panel / 情報パネル / 信息面板
        'info.mileage': '里程',
        'info.elevation': '標高',
        'info.gradient': '勾配',
        'info.radius': '曲線半径',
        'info.speedlimit': '制限速度',
        'info.no_limit': '制限なし',

        # Station jump / 駅移動 / 车站跳转
        'label.station_jump': '駅移動',

        # Canvas titles / キャンバス見出し / 画布标题
        'canvas.plan': '平面図',
        'canvas.profile': '縦断面図 / 標高',
        'canvas.radius': '曲線半径',

        # Treeview headings / ツリービュー見出し / Treeview列标题
        'tree.track_key': 'track key',
        'tree.from': 'From',
        'tree.to': 'To',
        'tree.color': 'Color',
        'tree.root': 'root',

        # Dialog messages / ダイアログメッセージ / 对话框消息
        'dialog.quit': 'Kobushi Track Viewerを終了しますか？',
        'dialog.station_not_found': '{value} はこのmap上に見つかりませんでした',
        'dialog.set_plotlimit': '描画可能区間を設定\nmap range:{min},{max}',
        'dialog.plotlimit_min': '最小値 (既定値:{value})',
        'dialog.plotlimit_max': '最大値 (既定値:{value})',
        'dialog.set_controlpoint': '座標制御点を追加',
        'dialog.cp_min': '最小値 (既定値: {value})',
        'dialog.cp_max': '最大値 (既定値: {value})',
        'dialog.cp_interval': '間隔 (既定値: {value})',
        'dialog.set_profylimit': '断面図Y軸範囲を設定',
        'dialog.ylimit_min': '最小値 (既定値:auto)',
        'dialog.ylimit_max': '最大値 (既定値:auto)',
        'dialog.color_title': '{trackkey} ,既定値: {color}',
        'dialog.distance_title': '{trackkey}: 距離程',
        'dialog.distance_prompt': '{label} (既定値: {value} m)',

        # About dialog / バージョン情報 / 关于对话框
        'about.text': 'Kobushi trackviewer(Modified)\nVersion {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\nReleased under the Apache License, Version 2.0 .\nhttps://www.apache.org/licenses/LICENSE-2.0',

        # Misc / その他 / 杂项
        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': 'Lv.',
        'label.check': 'Check',
        'filetype.ps': 'PostScript',
        'filetype.any': 'any format',
        'mileage.format': '{:.0f}m',

        # Background image / 背景画像 / 背景图片
        'frame.bgimage': '背景画像',
        'chk.bgimg_show': '表示',
        'button.import_bg': 'インポート',
        'button.adjust_bg': '調整',
        'button.align_to_station': '駅に合わせる',
        'button.pick_on_bg': '背景上の点を選択',
        'button.pick_on_bg_ok': '背景上の点を選択 (OK)',
        'button.apply': '適用',
        'label.bgimg_x': 'X (m)',
        'label.bgimg_y': 'Y (m)',
        'label.bgimg_width': '幅 (m)',
        'label.bgimg_height': '高さ (m)',
        'label.bgimg_rotation': '回転角度 (°)',
        'label.select_station': '駅を選択:',
        'dialog.adjust_bgimg': '背景画像の調整',
        'dialog.align_to_station': '駅に合わせる',
        'dialog.bgimg_load_error': '画像を読み込めません: {error}',
        'dialog.invalid_number': '入力値が無効です。数字を入力してください',
        'dialog.no_station_data': '最初に駅情報を含む路線ファイルを開いてください',
        'dialog.station_coord_error': '選択した駅の座標を取得できません',
        'dialog.pick_points_needed': '最初に背景画像上で2つの駅に対応する点を選択してください',
        'dialog.distance_too_short': '2つの駅または2つの選択点の距離が近すぎるため、位置合わせパラメータを計算できません',
        'dialog.pick_points_coincident': '選択した2つの背景点が重なっているため、位置合わせパラメータを計算できません',
        'frame.station1': '駅1',
        'frame.station2': '駅2',
    },
    _EN: {
        'lang.name': 'English',

        # Window titles / ウィンドウタイトル / 窗口标题
        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': 'Other Tracks',
        'window.font': 'Font',

        # Menu / メニュー / 菜单
        'menu.file': 'File',
        'menu.options': 'Options',
        'menu.help': 'Help',
        'menu.lang': '言語選択 / Select Language / 语言选择',

        'menu.open': 'Open...',
        'menu.reload': 'Reload',
        'menu.save_image': 'Save Image...',
        'menu.save_trackdata': 'Save Trackdata...',
        'menu.exit': 'Exit',

        'menu.controlpoints': 'Control Points...',
        'menu.plotlimit': 'Plot Limit...',
        'menu.profylimit': 'Profile Y-axis Range...',
        'menu.font': 'Font...',

        'menu.help_ref': 'Help...',
        'menu.about': 'About Kobushi...',

        # Buttons / ボタン / 按钮
        'button.open': 'Open',
        'button.ok': 'OK',
        'button.reset': 'Reset',
        'button.cancel': 'Cancel',

        # Control panel / 操作パネル / 控制面板
        'frame.aux_info': 'Auxiliary Info',
        'frame.chart_visibility': 'Chart Visibility',

        # Checkboxes / チェックボックス / 复选框
        'chk.station_pos': 'Station Position',
        'chk.station_name': 'Station Name',
        'chk.station_mileage': 'Station Mileage',
        'chk.gradient_pos': 'Gradient Change Points',
        'chk.gradient_val': 'Gradient Value',
        'chk.curve_val': 'Curve Radius',
        'chk.prof_othert': 'Other Tracks (Profile)',
        'chk.speedlimit': 'Speed Limit',

        'chk.gradient_graph': 'Gradient Graph',
        'chk.curve_graph': 'Curve Graph',

        # Grid control / グリッド制御 / 网格控制
        'frame.grid': 'Grid Lines',
        'grid.fixed': 'Fixed',
        'grid.movable': 'Movable',
        'grid.none': 'None',

        # Mode selection / モード選択 / 模式选择
        'frame.mode': 'Mode',
        'mode.pan': 'Pan',
        'mode.measure': 'Measure',

        # Info panel / 情報パネル / 信息面板
        'info.mileage': 'Mileage',
        'info.elevation': 'Elevation',
        'info.gradient': 'Gradient',
        'info.radius': 'Curve Radius',
        'info.speedlimit': 'Speed Limit',
        'info.no_limit': 'No limit',

        # Station jump / 駅移動 / 车站跳转
        'label.station_jump': 'Station Jump',

        # Canvas titles / キャンバス見出し / 画布标题
        'canvas.plan': 'Plan',
        'canvas.profile': 'Gradient / Height',
        'canvas.radius': 'Curve Radius',

        # Treeview headings / ツリービュー見出し / Treeview列标题
        'tree.track_key': 'track key',
        'tree.from': 'From',
        'tree.to': 'To',
        'tree.color': 'Color',
        'tree.root': 'root',

        # Dialog messages / ダイアログメッセージ / 对话框消息
        'dialog.quit': 'Quit Kobushi Track Viewer?',
        'dialog.station_not_found': '{value} was not found on this map.',
        'dialog.set_plotlimit': 'Set Plot Limit\nmap range:{min},{max}',
        'dialog.plotlimit_min': 'min (default:{value})',
        'dialog.plotlimit_max': 'max (default:{value})',
        'dialog.set_controlpoint': 'Set Additional Control Points',
        'dialog.cp_min': 'min (default: {value})',
        'dialog.cp_max': 'max (default: {value})',
        'dialog.cp_interval': 'interval (default: {value})',
        'dialog.set_profylimit': 'Set Profile Y-axis Range',
        'dialog.ylimit_min': 'min (default:auto)',
        'dialog.ylimit_max': 'max (default:auto)',
        'dialog.color_title': '{trackkey}, default: {color}',
        'dialog.distance_title': '{trackkey}: Distance',
        'dialog.distance_prompt': '{label} (default: {value} m)',

        # About dialog / バージョン情報 / 关于对话框
        'about.text': 'Kobushi trackviewer(Modified)\nVersion {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\nReleased under the Apache License, Version 2.0 .\nhttps://www.apache.org/licenses/LICENSE-2.0',

        # Misc / その他 / 杂项
        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': 'Lv.',
        'label.check': 'Check',
        'filetype.ps': 'PostScript',
        'filetype.any': 'any format',
        'mileage.format': '{:.0f}m',

        # Background image / 背景画像 / 背景图片
        'frame.bgimage': 'Background Image',
        'chk.bgimg_show': 'Show',
        'button.import_bg': 'Import',
        'button.adjust_bg': 'Adjust',
        'button.align_to_station': 'Align to Station',
        'button.pick_on_bg': 'Pick Point on BG',
        'button.pick_on_bg_ok': 'Pick Point on BG (OK)',
        'button.apply': 'Apply',
        'label.bgimg_x': 'X (m)',
        'label.bgimg_y': 'Y (m)',
        'label.bgimg_width': 'Width (m)',
        'label.bgimg_height': 'Height (m)',
        'label.bgimg_rotation': 'Rotation (°)',
        'label.select_station': 'Select Station:',
        'dialog.adjust_bgimg': 'Adjust Background Image',
        'dialog.align_to_station': 'Align to Station',
        'dialog.bgimg_load_error': 'Failed to load image: {error}',
        'dialog.invalid_number': 'Invalid input. Please enter a number.',
        'dialog.no_station_data': 'Please open a route file containing stations first.',
        'dialog.station_coord_error': 'Could not retrieve coordinates for the selected station.',
        'dialog.pick_points_needed': 'Please pick corresponding points on the background image for both stations first.',
        'dialog.distance_too_short': 'The distance between the two stations or the two picked points is too small to compute alignment parameters.',
        'dialog.pick_points_coincident': 'The two picked background points are coincident. Cannot compute alignment parameters.',
        'frame.station1': 'Station 1',
        'frame.station2': 'Station 2',
    },
    _ZH: {
        'lang.name': '简体中文',

        # Window titles / ウィンドウタイトル / 窗口标题
        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': '其他轨道设置',
        'window.font': '字体',

        # Menu / メニュー / 菜单
        'menu.file': '文件',
        'menu.options': '选项',
        'menu.help': '帮助',
        'menu.lang': '言語選択 / Select Language / 语言选择',

        'menu.open': '打开...',
        'menu.reload': '重新加载',
        'menu.save_image': '保存图像...',
        'menu.save_trackdata': '保存线形数据...',
        'menu.exit': '退出',

        'menu.controlpoints': '坐标控制点...',
        'menu.plotlimit': '绘图区间...',
        'menu.profylimit': '断面图Y轴范围...',
        'menu.font': '字体...',

        'menu.help_ref': '帮助...',
        'menu.about': '关于 Kobushi...',

        # Buttons / ボタン / 按钮
        'button.open': '打开',
        'button.ok': '确定',
        'button.reset': '重置',
        'button.cancel': '取消',

        # Control panel / 操作パネル / 控制面板
        'frame.aux_info': '辅助信息',
        'frame.chart_visibility': '图表显示',

        # Checkboxes / チェックボックス / 复选框
        'chk.station_pos': '车站坐标',
        'chk.station_name': '车站名称',
        'chk.station_mileage': '车站里程',
        'chk.gradient_pos': '坡度变化点',
        'chk.gradient_val': '坡度数值',
        'chk.curve_val': '曲线半径',
        'chk.prof_othert': '纵断面其他轨道',
        'chk.speedlimit': '限速',

        'chk.gradient_graph': '纵断面图',
        'chk.curve_graph': '曲线半径图',

        # Grid control / グリッド制御 / 网格控制
        'frame.grid': '网格线',
        'grid.fixed': '固定',
        'grid.movable': '可动',
        'grid.none': '无',

        # Mode selection / モード選択 / 模式选择
        'frame.mode': '模式选择',
        'mode.pan': '移动',
        'mode.measure': '测量',

        # Info panel / 情報パネル / 信息面板
        'info.mileage': '里程',
        'info.elevation': '标高',
        'info.gradient': '坡度',
        'info.radius': '曲线半径',
        'info.speedlimit': '限速',
        'info.no_limit': '无',

        # Station jump / 駅移動 / 车站跳转
        'label.station_jump': '车站跳转',

        # Canvas titles / キャンバス見出し / 画布标题
        'canvas.plan': '平面图',
        'canvas.profile': '纵断面 / 标高',
        'canvas.radius': '曲线半径',

        # Treeview headings / ツリービュー見出し / Treeview列标题
        'tree.track_key': '轨道编号',
        'tree.from': '起点',
        'tree.to': '终点',
        'tree.color': '颜色',
        'tree.root': '根',

        # Dialog messages / ダイアログメッセージ / 对话框消息
        'dialog.quit': '确定要退出 Kobushi Track Viewer 吗？',
        'dialog.station_not_found': '在地图上未找到 {value}。',
        'dialog.set_plotlimit': '设置绘图区间\n地图范围：{min}～{max}',
        'dialog.plotlimit_min': '最小值（默认：{value}）',
        'dialog.plotlimit_max': '最大值（默认：{value}）',
        'dialog.set_controlpoint': '设置附加控制点',
        'dialog.cp_min': '最小值（默认：{value}）',
        'dialog.cp_max': '最大值（默认：{value}）',
        'dialog.cp_interval': '间隔（默认：{value}）',
        'dialog.set_profylimit': '设置断面图Y轴范围',
        'dialog.ylimit_min': '最小值（默认：auto）',
        'dialog.ylimit_max': '最大值（默认：auto）',
        'dialog.color_title': '{trackkey}，默认值：{color}',
        'dialog.distance_title': '{trackkey}：距离',
        'dialog.distance_prompt': '{label}（默认值：{value} m）',

        # About dialog / バージョン情報 / 关于对话框
        'about.text': 'Kobushi trackviewer(Modified)\n版本 {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\n基于 Apache License, Version 2.0 发布。\nhttps://www.apache.org/licenses/LICENSE-2.0',

        # Misc / その他 / 杂项
        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': '水平',
        'label.check': '勾选',
        'filetype.ps': 'PostScript',
        'filetype.any': '所有格式',
        'mileage.format': '{:.0f}m',

        # Background image / 背景画像 / 背景图片
        'frame.bgimage': '背景图片',
        'chk.bgimg_show': '显示',
        'button.import_bg': '导入',
        'button.adjust_bg': '调整',
        'button.align_to_station': '对齐到车站',
        'button.pick_on_bg': '选择背景上的点',
        'button.pick_on_bg_ok': '选择背景上的点 (OK)',
        'button.apply': '应用',
        'label.bgimg_x': 'X (m)',
        'label.bgimg_y': 'Y (m)',
        'label.bgimg_width': '宽度 (m)',
        'label.bgimg_height': '高度 (m)',
        'label.bgimg_rotation': '旋转角度 (°)',
        'label.select_station': '选择车站:',
        'dialog.adjust_bgimg': '调整背景图片',
        'dialog.align_to_station': '对齐到车站',
        'dialog.bgimg_load_error': '无法加载图片: {error}',
        'dialog.invalid_number': '输入值无效，请输入数字',
        'dialog.no_station_data': '请先打开包含车站的路线文件',
        'dialog.station_coord_error': '无法获取所选车站的坐标',
        'dialog.pick_points_needed': '请先在背景图上为两个车站分别选择对应的点',
        'dialog.distance_too_short': '两个车站或两个选取点之间的距离过小，无法计算对齐参数',
        'dialog.pick_points_coincident': '选取的两个背景点重合，无法计算对齐参数',
        'frame.station1': '车站1',
        'frame.station2': '车站2',
    },
}

# Currently active language (default: Japanese) and callbacks for language change notification /
# 現在のアクティブ言語（デフォルト: 日本語）と、言語変更通知用コールバックリスト /
# 当前激活的语言（默认: 日语）和语言变更通知回调列表
_current_lang = _JA
_change_callbacks = []


def get(key, **kwargs):
    # Retrieve a localized string by key: lookup in current language, fallback to English, then key itself /
    # キーで翻訳文字列を取得：現在の言語→英語→キーそのものの順にフォールバック /
    # 通过键获取本地化字符串：依次在当前语言、英语、键本身中查找
    value = _translations.get(_current_lang, {}).get(key)
    if value is None:
        value = _translations[_EN].get(key, key)
    if kwargs:
        value = value.format(**kwargs)
    return value


def set_language(lang):
    # Switch the active language and notify all registered callbacks /
    # アクティブ言語を切り替え、登録された全コールバックに通知 /
    # 切换当前激活语言，并通知所有已注册的回调函数
    global _current_lang
    if lang in SUPPORTED_LANGUAGES:
        _current_lang = lang
        for cb in _change_callbacks:
            cb()


def get_language():
    # Return the currently active language code /
    # 現在のアクティブ言語コードを返す /
    # 返回当前激活的语言代码
    return _current_lang


def on_language_change(callback):
    # Register a callback that will be invoked whenever the language is changed /
    # 言語変更時に呼び出されるコールバックを登録 /
    # 注册一个在语言变更时会被调用的回调函数
    _change_callbacks.append(callback)
