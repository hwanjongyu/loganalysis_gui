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


class BadgeLabel(QLabel):
    def __init__(self, text, bg_color, fg_color, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"QLabel {{"
            f"  background-color: {bg_color};"
            f"  color: {fg_color};"
            f"  border-radius: 3px;"
            f"  padding: 1px 5px;"
            f"  font-size: 8pt;"
            f"  font-weight: bold;"
            f"  background: {bg_color};"
            f"}}"
        )


class FilterItemWidget(QWidget):
    filter_toggled = pyqtSignal(dict, bool)

    def __init__(self, filter_data, parent=None):
        super().__init__(parent)
        self.filter_data = filter_data
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.filter_data.get("active", True))
        self.checkbox.toggled.connect(self._on_checkbox_toggled)

        self.badge_layout = QHBoxLayout()
        self.badge_layout.setSpacing(4)
        self.badge_layout.setContentsMargins(0, 0, 0, 0)

        self.text_label = QLabel()
        self.desc_label = QLabel()
        self.count_label = QLabel()
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(self.checkbox)
        layout.addLayout(self.badge_layout)
        layout.addWidget(self.text_label)
        layout.addWidget(self.desc_label, 1)
        layout.addWidget(self.count_label)
        
        self.update_display()

    def _on_checkbox_toggled(self, checked):
        self.filter_data["active"] = checked
        self.filter_toggled.emit(self.filter_data, checked)

    def is_background_dark(self, bg_name):
        if bg_name == "None":
            return False
        hex_color = COLOR_MAP.get(bg_name, bg_name)
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return False
        try:
            rgb = [int(hex_color[i:i+2], 16) / 255.0 for i in (1, 3, 5)]
            luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            return luminance < 0.5
        except Exception:
            return False

    def update_display(self):
        # Set raw text
        self.text_label.setText(self.filter_data["text"])
        
        count = self.filter_data.get('total_matches', 0)
        self.count_label.setText(f"({count:,})" if count > 0 else "")

        bg_color_name = self.filter_data.get("bg_color", "None")
        text_color_name = self.filter_data.get("text_color", "None")
        active = self.filter_data.get("active", True)
        
        # Clear old badges
        while self.badge_layout.count():
            item = self.badge_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add option badges (desaturated colors depending on active state)
        if self.filter_data.get("exclude"):
            bg = "#ef9a9a" if not active else "#E57373"
            fg = "#ffffff"
            self.badge_layout.addWidget(BadgeLabel("NOT", bg, fg))
        if self.filter_data.get("regex"):
            bg = "#e1bee7" if not active else "#BA68C8"
            fg = "#ffffff"
            self.badge_layout.addWidget(BadgeLabel("REGEX", bg, fg))
        if self.filter_data.get("case_sensitive"):
            bg = "#b3e5fc" if not active else "#4FC3F7"
            fg = "#666666" if not active else "#000000"
            self.badge_layout.addWidget(BadgeLabel("CASE", bg, fg))

        if not active:
            # Grayed-out/strike-through style for disabled filters
            self.text_label.setStyleSheet("color: #888888; text-decoration: line-through; background: transparent;")
            self.desc_label.setStyleSheet("color: #aaaaaa; font-style: italic; font-size: 9pt; background: transparent;")
            self.count_label.setStyleSheet("color: #888888; background: transparent;")
            self.setStyleSheet("background-color: rgba(128, 128, 128, 20); border-radius: 4px;")
            
            desc = self.filter_data.get("description", "")
            if desc:
                self.desc_label.setText(f" // {desc}")
                self.setToolTip(desc)
                self.text_label.setToolTip(desc)
            else:
                self.desc_label.setText("")
                self.setToolTip(self.filter_data["text"])
                self.text_label.setToolTip(self.filter_data["text"])
            return

        # Active state: transparent container stylesheet
        self.setStyleSheet("background: transparent;")
        
        # Configure text colors (with transparent background to let selection highlight show through)
        text_style = "background: transparent;"
        if text_color_name != "None":
            text_style += f"color: {TEXT_COLOR_MAP.get(text_color_name, text_color_name)};"
        self.text_label.setStyleSheet(text_style)
        self.count_label.setStyleSheet("background: transparent; color: #888888;")

        # Dynamic Description Color for Contrast
        desc = self.filter_data.get("description", "")
        if desc:
            self.desc_label.setText(f" // {desc}")
            is_dark_bg = self.is_background_dark(bg_color_name)
            desc_color = "#b0b0b5" if is_dark_bg else "#66666a"
            self.desc_label.setStyleSheet(f"color: {desc_color}; font-style: italic; font-size: 9pt; background: transparent;")
            self.setToolTip(desc)
            self.text_label.setToolTip(desc)
        else:
            self.desc_label.setText("")
            self.desc_label.setStyleSheet("background: transparent;")
            self.setToolTip(self.filter_data["text"])
            self.text_label.setToolTip(self.filter_data["text"])
