from PyQt5.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from .constants import COLOR_MAP, TEXT_COLOR_MAP


def describe_filter_text(filter_data):
    text = filter_data["text"]
    if filter_data["exclude"]:
        text = f"NOT: {text}"
    if filter_data["regex"]:
        text = f"REGEX: {text}"
    if filter_data["case_sensitive"]:
        text = f"CASE: {text}"
    return text


class FilterItemWidget(QWidget):
    filter_toggled = pyqtSignal(dict, bool)

    def __init__(self, filter_data, parent=None):
        super().__init__(parent)
        self.filter_data = filter_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.filter_data.get("active", True))
        self.checkbox.toggled.connect(self._on_checkbox_toggled)

        self.text_label = QLabel()
        self.count_label = QLabel()
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.count_label)
        
        self.update_display()

    def _on_checkbox_toggled(self, checked):
        self.filter_data["active"] = checked
        self.filter_toggled.emit(self.filter_data, checked)

    def update_display(self):
        text = describe_filter_text(self.filter_data)
        self.text_label.setText(text)
        
        count = self.filter_data.get('total_matches', 0)
        if count > 0: self.count_label.setText(f"({count})")
        else: self.count_label.setText("")

        bg_color_name = self.filter_data.get("bg_color", "None")
        text_color_name = self.filter_data.get("text_color", "None")
        style = ""
        if bg_color_name != "None": style += f"background-color: {COLOR_MAP.get(bg_color_name, bg_color_name)};"
        if text_color_name != "None": style += f"color: {TEXT_COLOR_MAP.get(text_color_name, text_color_name)};"
        self.text_label.setStyleSheet(style)
