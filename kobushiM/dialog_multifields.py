'''
    Copyright 2021 konawasabi

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

from PyQt6 import QtCore, QtWidgets

from . import i18n


class _FieldAccessor:
    def __init__(self, widget, field_type):
        self.widget = widget
        self.field_type = field_type

    def get(self):
        if self.field_type == 'str':
            return self.widget.text()
        return self.widget.value()

    def set(self, value):
        if self.field_type == 'str':
            self.widget.setText(str(value))
        else:
            self.widget.setValue(float(value))


class dialog_multifields:
    def __init__(self, mainwindow, variable, title=None, message=None):
        self.mainwindow = mainwindow
        self.variables = {}
        self.entries = {}
        self.labels = {}
        self.result = False

        self.dialog = QtWidgets.QDialog(mainwindow)
        self.dialog.setWindowTitle(title or '')
        self.dialog.setModal(True)

        layout = QtWidgets.QVBoxLayout(self.dialog)
        if message is not None:
            label = QtWidgets.QLabel(message)
            label.setWordWrap(True)
            layout.addWidget(label)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        for field in variable:
            name = field['name']
            field_type = field.get('type', 'str')
            self.labels[name] = QtWidgets.QLabel(field.get('label', name))
            if field_type == 'str':
                widget = QtWidgets.QLineEdit()
                widget.setText(str(field.get('default', '')))
            else:
                widget = QtWidgets.QDoubleSpinBox()
                widget.setRange(-1e12, 1e12)
                widget.setDecimals(6)
                widget.setSingleStep(1.0)
                widget.setValue(float(field.get('default', 0.0)))
            self.entries[name] = widget
            self.variables[name] = _FieldAccessor(widget, field_type)
            form.addRow(self.labels[name], widget)

        buttons = QtWidgets.QDialogButtonBox()
        self.button_ok = buttons.addButton(i18n.get('button.ok'), QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_reset = buttons.addButton(i18n.get('button.reset'), QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        self.button_cancel = buttons.addButton(i18n.get('button.cancel'), QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        self.button_ok.clicked.connect(self.clickOk)
        self.button_reset.clicked.connect(self.clickreset)
        self.button_cancel.clicked.connect(self.clickCancel)

        QtCore.QTimer.singleShot(0, self._focus_first_field)
        self.dialog.exec()

    def _focus_first_field(self):
        if self.entries:
            next(iter(self.entries.values())).setFocus()

    def clickOk(self, event=None):
        self.result = 'OK'
        self.dialog.accept()

    def clickreset(self, event=None):
        self.result = 'reset'
        self.dialog.accept()

    def clickCancel(self, event=None):
        self.dialog.reject()
