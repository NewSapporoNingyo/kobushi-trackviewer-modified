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

from PyQt6 import QtCore, QtGui, QtWidgets

from . import i18n


class OtherTrackTree(QtWidgets.QTreeWidget):
    def __init__(self, mainwindow, parent=None):
        super().__init__(parent)
        self.mainwindow = mainwindow
        self._items = {}
        self._root_item = None
        self._updating = False
        self.setColumnCount(4)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.refresh_headers()
        self.itemDoubleClicked.connect(self._edit_item)
        self.itemChanged.connect(self._on_item_changed)

    def refresh_headers(self):
        self.setHeaderLabels([
            i18n.get('tree.track_key'),
            i18n.get('tree.from'),
            i18n.get('tree.to'),
            i18n.get('tree.color'),
        ])

    def exists(self, item_id):
        return item_id == 'root' and self._root_item is not None

    def delete(self, item_id):
        if item_id == 'root':
            self.clear()
            self._items.clear()
            self._root_item = None

    def get_checked(self):
        checked = []
        for key, item in self._items.items():
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                checked.append(key)
        return checked

    def set(self, key, column, value):
        item = self._items.get(key)
        if item is None:
            return
        col = self._column_index(column)
        item.setText(col, str(value))

    def tag_configure(self, key, foreground=None, **kwargs):
        item = self._items.get(key)
        if item is None or foreground is None:
            return
        color = QtGui.QColor(foreground)
        for col in range(self.columnCount()):
            item.setForeground(col, QtGui.QBrush(color))

    def _check_ancestor(self, key):
        item = self._items.get(key)
        if item is not None:
            old_updating = self._updating
            self._updating = True
            try:
                item.setCheckState(0, QtCore.Qt.CheckState.Checked)
            finally:
                self._updating = old_updating

    def populate(self):
        self._updating = True
        try:
            self.clear()
            self._items.clear()
            self._root_item = QtWidgets.QTreeWidgetItem([i18n.get('tree.root'), '', '', ''])
            self._root_item.setExpanded(True)
            self.addTopLevelItem(self._root_item)

            result = self.mainwindow.result
            if result is None:
                return
            for key in result.othertrack.data.keys():
                data = result.othertrack.data[key]
                item = QtWidgets.QTreeWidgetItem([
                    key,
                    str(min(data, key=lambda x: x['distance'])['distance']),
                    str(max(data, key=lambda x: x['distance'])['distance']),
                    '###',
                ])
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, key)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                self._root_item.addChild(item)
                self._items[key] = item
                self.tag_configure(key, foreground=result.othertrack_linecolor[key]['current'])
            self.expandAll()
        finally:
            self._updating = False

    def _column_index(self, column):
        if isinstance(column, int):
            return column
        return {'#0': 0, '#1': 1, '#2': 2, '#3': 3}.get(column, 0)

    def _on_item_changed(self, item, column):
        if self._updating or item is self._root_item:
            return
        if column == 0 and self.mainwindow.result is not None:
            self.mainwindow.plot_all()

    def _edit_item(self, item, column):
        if item is self._root_item or self.mainwindow.result is None:
            return
        key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if key is None:
            return

        if column == 3:
            current = self.mainwindow.result.othertrack_linecolor[key]['current']
            title = i18n.get(
                'dialog.color_title',
                trackkey=key,
                color=self.mainwindow.result.othertrack_linecolor[key]['default'],
            )
            color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current), self, title)
            if color.isValid():
                self.mainwindow.result.othertrack_linecolor[key]['current'] = color.name()
                self.tag_configure(key, foreground=color.name())
                self.mainwindow.plot_all()
            return

        if column not in (1, 2):
            return
        label = i18n.get('tree.from') if column == 1 else i18n.get('tree.to')
        if column == 1:
            default = min(self.mainwindow.result.othertrack.data[key], key=lambda x: x['distance'])['distance']
        else:
            default = max(self.mainwindow.result.othertrack.data[key], key=lambda x: x['distance'])['distance']
        value, ok = QtWidgets.QInputDialog.getDouble(
            self,
            i18n.get('dialog.distance_title', trackkey=key),
            i18n.get('dialog.distance_prompt', label=label, value=str(default)),
            float(default),
            -1e12,
            1e12,
            3,
        )
        if ok:
            if column == 1:
                self.mainwindow.result.othertrack.cp_range[key]['min'] = value
            else:
                self.mainwindow.result.othertrack.cp_range[key]['max'] = value
            item.setText(column, str(value))
            self.mainwindow.plot_all()


class SubWindow(QtWidgets.QWidget):
    def __init__(self, master, mainwindow):
        super().__init__(mainwindow)
        self.mainwindow = mainwindow
        self.parent = master
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.setWindowTitle(i18n.get('window.othertracks'))
        self.create_widgets()
        self.resize(480, 360)
        self.move(1100, 0)
        self.show()

    def create_widgets(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        self.othertrack_tree = OtherTrackTree(self.mainwindow, self)
        layout.addWidget(self.othertrack_tree)

    def refresh_ui_text(self):
        self.setWindowTitle(i18n.get('window.othertracks'))
        self.othertrack_tree.refresh_headers()

    def click_tracklist(self, event=None):
        self.mainwindow.plot_all()

    def set_ottree_value(self):
        self.othertrack_tree.populate()
