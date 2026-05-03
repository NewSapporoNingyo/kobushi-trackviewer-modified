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

_JA = 'ja'
_EN = 'en'
_ZH = 'zh'

SUPPORTED_LANGUAGES = {
    _JA: '日本語',
    _EN: 'English',
    _ZH: '简体中文',
}

_translations = {
    _JA: {
        'lang.name': '日本語',

        # Window titles
        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': '他軌道の設定',
        'window.font': 'フォント',

        # Menu
        'menu.file': 'ファイル',
        'menu.options': 'オプション',
        'menu.help': 'ヘルプ',
        'menu.lang': '言語選択 / Select Language / 语言选择',

        'menu.open': '開く...',
        'menu.reload': '再読み込み',
        'menu.save_image': '画像を保存...',
        'menu.save_trackdata': '走行位置情報を保存...',
        'menu.exit': '終了',

        'menu.controlpoints': '座標制御点...',
        'menu.plotlimit': '描画可能区間...',
        'menu.profylimit': '断面図y軸範囲...',
        'menu.font': 'フォント...',

        'menu.help_ref': 'ヘルプ...',
        'menu.about': 'Kobushiについて...',

        # Buttons
        'button.open': '開く',
        'button.ok': 'OK',
        'button.reset': 'リセット',
        'button.cancel': 'キャンセル',

        # Control panel
        'frame.aux_info': '補助情報',
        'frame.chart_visibility': 'チャート表示',

        # Checkboxes
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

        # Grid control
        'frame.grid': 'グリッド線',
        'grid.fixed': '固定',
        'grid.movable': '可動',
        'grid.none': '無',

        # Mode selection
        'frame.mode': 'モード選択',
        'mode.pan': '移動',
        'mode.measure': '測量',

        # Info panel
        'info.mileage': '里程',
        'info.elevation': '標高',
        'info.gradient': '勾配',
        'info.radius': '曲線半径',
        'info.speedlimit': '制限速度',
        'info.no_limit': '制限なし',

        # Station jump
        'label.station_jump': '駅移動',

        # Canvas titles
        'canvas.plan': '平面図',
        'canvas.profile': '縦断面図 / 標高',
        'canvas.radius': '曲線半径',

        # Treeview headings
        'tree.track_key': 'track key',
        'tree.from': 'From',
        'tree.to': 'To',
        'tree.color': 'Color',
        'tree.root': 'root',

        # Dialog messages
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

        # About dialog
        'about.text': 'Kobushi trackviewer(Modified)\nVersion {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\nReleased under the Apache License, Version 2.0 .\nhttps://www.apache.org/licenses/LICENSE-2.0',

        # Misc
        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': 'Lv.',
        'label.check': 'Check',
        'filetype.ps': 'PostScript',
        'filetype.any': 'any format',
        'mileage.format': '{:.0f}m',
    },
    _EN: {
        'lang.name': 'English',

        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': 'Other Tracks',
        'window.font': 'Font',

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

        'button.open': 'Open',
        'button.ok': 'OK',
        'button.reset': 'Reset',
        'button.cancel': 'Cancel',

        'frame.aux_info': 'Auxiliary Info',
        'frame.chart_visibility': 'Chart Visibility',

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

        'frame.grid': 'Grid Lines',
        'grid.fixed': 'Fixed',
        'grid.movable': 'Movable',
        'grid.none': 'None',

        'frame.mode': 'Mode',
        'mode.pan': 'Pan',
        'mode.measure': 'Measure',

        'info.mileage': 'Mileage',
        'info.elevation': 'Elevation',
        'info.gradient': 'Gradient',
        'info.radius': 'Curve Radius',
        'info.speedlimit': 'Speed Limit',
        'info.no_limit': 'No limit',

        'label.station_jump': 'Station Jump',

        'canvas.plan': 'Plan',
        'canvas.profile': 'Gradient / Height',
        'canvas.radius': 'Curve Radius',

        'tree.track_key': 'track key',
        'tree.from': 'From',
        'tree.to': 'To',
        'tree.color': 'Color',
        'tree.root': 'root',

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

        'about.text': 'Kobushi trackviewer(Modified)\nVersion {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\nReleased under the Apache License, Version 2.0 .\nhttps://www.apache.org/licenses/LICENSE-2.0',

        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': 'Lv.',
        'label.check': 'Check',
        'filetype.ps': 'PostScript',
        'filetype.any': 'any format',
        'mileage.format': '{:.0f}m',
    },
    _ZH: {
        'lang.name': '简体中文',

        'app.title': 'Kobushi Track Viewer-Modified',
        'window.othertracks': '其他轨道设置',
        'window.font': '字体',

        'menu.file': '文件',
        'menu.options': '选项',
        'menu.help': '帮助',
        'menu.lang': '言語選択 / Select Language / 语言选择',

        'menu.open': '打开...',
        'menu.reload': '重新加载',
        'menu.save_image': '保存图像...',
        'menu.save_trackdata': '保存走行位置数据...',
        'menu.exit': '退出',

        'menu.controlpoints': '坐标控制点...',
        'menu.plotlimit': '绘图区间...',
        'menu.profylimit': '断面图Y轴范围...',
        'menu.font': '字体...',

        'menu.help_ref': '帮助...',
        'menu.about': '关于 Kobushi...',

        'button.open': '打开',
        'button.ok': '确定',
        'button.reset': '重置',
        'button.cancel': '取消',

        'frame.aux_info': '辅助信息',
        'frame.chart_visibility': '图表显示',

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

        'frame.grid': '网格线',
        'grid.fixed': '固定',
        'grid.movable': '可动',
        'grid.none': '无',

        'frame.mode': '模式选择',
        'mode.pan': '移动',
        'mode.measure': '测量',

        'info.mileage': '里程',
        'info.elevation': '标高',
        'info.gradient': '坡度',
        'info.radius': '曲线半径',
        'info.speedlimit': '限速',
        'info.no_limit': '无',

        'label.station_jump': '车站跳转',

        'canvas.plan': '平面图',
        'canvas.profile': '纵断面 / 标高',
        'canvas.radius': '曲线半径',

        'tree.track_key': '轨道编号',
        'tree.from': '起点',
        'tree.to': '终点',
        'tree.color': '颜色',
        'tree.root': '根',

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

        'about.text': 'Kobushi trackviewer(Modified)\n版本 {version}\n\nCopyright © 2021-2024 konawasabi\nModified by Sapporo_ningyo\n基于 Apache License, Version 2.0 发布。\nhttps://www.apache.org/licenses/LICENSE-2.0',

        'unit.m': 'm',
        'unit.km': 'km',
        'label.lv': '水平',
        'label.check': '勾选',
        'filetype.ps': 'PostScript',
        'filetype.any': '所有格式',
        'mileage.format': '{:.0f}m',
    },
}

_current_lang = _JA
_change_callbacks = []


def get(key, **kwargs):
    value = _translations.get(_current_lang, {}).get(key)
    if value is None:
        value = _translations[_EN].get(key, key)
    if kwargs:
        value = value.format(**kwargs)
    return value


def set_language(lang):
    global _current_lang
    if lang in SUPPORTED_LANGUAGES:
        _current_lang = lang
        for cb in _change_callbacks:
            cb()


def get_language():
    return _current_lang


def on_language_change(callback):
    _change_callbacks.append(callback)
