import re

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QCheckBox, QLabel, QComboBox, QGroupBox, QFormLayout, QMessageBox
)
from PyQt5.QtGui import QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt
from .constants import COLOR_MAP, TEXT_COLOR_MAP

class FindDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Find text...")
        self.input_field.returnPressed.connect(self.find_next)
        input_layout.addWidget(self.input_field)
        
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.find_next)
        self.btn_prev = QPushButton("Previous")
        self.btn_prev.clicked.connect(self.find_prev)
        input_layout.addWidget(self.btn_prev)
        input_layout.addWidget(self.btn_next)
        
        layout.addLayout(input_layout)
        
        opt_layout = QHBoxLayout()
        self.chk_case = QCheckBox("Case sensitive")
        self.chk_regex = QCheckBox("Regex")
        opt_layout.addWidget(self.chk_case)
        opt_layout.addWidget(self.chk_regex)
        opt_layout.addStretch()
        layout.addLayout(opt_layout)
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: red")
        layout.addWidget(self.status_lbl)

        # Signals for real-time highlighting
        self.input_field.textChanged.connect(self._on_search_params_changed)
        self.chk_case.toggled.connect(self._on_search_params_changed)
        self.chk_regex.toggled.connect(self._on_search_params_changed)

    def _on_search_params_changed(self):
        if hasattr(self.parent(), "update_search_highlights"):
            self.parent().update_search_highlights(
                self.input_field.text(),
                self.chk_case.isChecked(),
                self.chk_regex.isChecked()
            )

    def hideEvent(self, event):
        if hasattr(self.parent(), "clear_search_highlights"):
            self.parent().clear_search_highlights()
        super().hideEvent(event)

    def closeEvent(self, event):
        if hasattr(self.parent(), "clear_search_highlights"):
            self.parent().clear_search_highlights()
        super().closeEvent(event)

    def find_next(self):
        self.parent().find_in_files(self.input_field.text(), forward=True, 
                                   case=self.chk_case.isChecked(), regex=self.chk_regex.isChecked())

    def find_prev(self):
        self.parent().find_in_files(self.input_field.text(), forward=False, 
                                   case=self.chk_case.isChecked(), regex=self.chk_regex.isChecked())
    
    def set_status(self, text):
        self.status_lbl.setText(text)


class FilterDialog(QDialog):
    def __init__(self, parent=None, filter_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Filter" if filter_data is None else "Edit Filter")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Input Widgets
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text to match...")
        
        # Options
        self.case_sensitive = QCheckBox("Case Sensitive")
        self.regex = QCheckBox("Regex")
        self.exclude = QCheckBox("Exclude Line")
        
        # Colors
        self.text_color = QComboBox()
        self.text_color.addItem("None")
        for name in sorted(TEXT_COLOR_MAP.keys()):
            color_hex = TEXT_COLOR_MAP[name]
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(color_hex))
            self.text_color.addItem(QIcon(pixmap), name)
        
        self.bg_color = QComboBox()
        self.bg_color.addItem("None")
        for name in sorted(COLOR_MAP.keys()):
            color_hex = COLOR_MAP[name]
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(color_hex))
            self.bg_color.addItem(QIcon(pixmap), name)
        
        # Preview
        self.preview_lbl = QLabel("Preview Text")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setFixedHeight(50)
        self.preview_lbl.setStyleSheet("border: 1px solid #555; padding: 10px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 11pt;")
        
        # Buttons
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Contrast Warning
        self.contrast_lbl = QLabel("")
        self.contrast_lbl.setWordWrap(True)
        self.contrast_lbl.setStyleSheet("color: #ff5555; font-weight: bold; font-size: 9pt;")
        
        # Connect signals for preview
        self.text_input.textChanged.connect(self.update_preview)
        self.case_sensitive.toggled.connect(self.update_preview)
        self.regex.toggled.connect(self.update_preview)
        self.exclude.toggled.connect(self.update_preview)
        self.text_color.currentTextChanged.connect(self.update_preview)
        self.bg_color.currentTextChanged.connect(self.update_preview)
        
        self.layout_ui()
        
        if filter_data:
            self.text_input.setText(filter_data.get("text", ""))
            self.case_sensitive.setChecked(filter_data.get("case_sensitive", False))
            self.regex.setChecked(filter_data.get("regex", False))
            self.exclude.setChecked(filter_data.get("exclude", False))
            
            idx = self.bg_color.findText(filter_data.get("bg_color", "None"))
            if idx >= 0: self.bg_color.setCurrentIndex(idx)
            
            idx = self.text_color.findText(filter_data.get("text_color", "None"))
            if idx >= 0: self.text_color.setCurrentIndex(idx)
            
        self.update_preview()

    def accept(self):
        if self.regex.isChecked():
            flags = 0 if self.case_sensitive.isChecked() else re.IGNORECASE
            try:
                re.compile(self.text_input.text(), flags)
            except re.error as error:
                QMessageBox.warning(
                    self,
                    "Invalid Regex",
                    f"Cannot save this filter because the regular expression is invalid:\n{error}",
                )
                return

        super().accept()

    def layout_ui(self):
        main_layout = QVBoxLayout()
        
        # 1. Matching Group
        match_group = QGroupBox("Match Criteria")
        match_layout = QVBoxLayout()
        match_layout.addWidget(self.text_input)
        
        opts_layout = QHBoxLayout()
        opts_layout.addWidget(self.case_sensitive)
        opts_layout.addWidget(self.regex)
        opts_layout.addWidget(self.exclude)
        opts_layout.addStretch()
        match_layout.addLayout(opts_layout)
        match_group.setLayout(match_layout)
        main_layout.addWidget(match_group)
        
        # 2. Appearance Group
        color_group = QGroupBox("Appearance")
        color_layout = QHBoxLayout()
        
        form_layout = QFormLayout()
        form_layout.addRow("Text Color:", self.text_color)
        form_layout.addRow("Background:", self.bg_color)
        
        color_layout.addLayout(form_layout)
        color_layout.addWidget(self.preview_lbl, 1) # Preview takes remaining space
        
        color_group.setLayout(color_layout)
        main_layout.addWidget(color_group)
        
        # 3. Footer
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.contrast_lbl, 1) # Label takes available stretch
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)

    def update_preview(self):
        text = self.text_input.text()
        if not text: text = "Preview Text"
        
        # Add visual markers for options
        if self.exclude.isChecked(): text = f" [EXCL] {text}"
        if self.regex.isChecked(): text = f" [REGEX] {text}"
        if self.case_sensitive.isChecked(): text = f" [CASE] {text}"
            
        bg_name = self.bg_color.currentText()
        text_name = self.text_color.currentText()
        
        style = "border: 1px solid #555; padding: 10px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 11pt;"
        
        if bg_name != "None":
            style += f"background-color: {COLOR_MAP.get(bg_name, bg_name)};"
        else:
            style += "background-color: transparent;"
            
        if text_name != "None":
            style += f"color: {TEXT_COLOR_MAP.get(text_name, text_name)};"
        else:
            style += "color: #e0e0e0;" # Default for preview
            
        self.preview_lbl.setStyleSheet(style)
        self.preview_lbl.setText(text)
        self.check_contrast()

    def check_contrast(self):
        bg_name = self.bg_color.currentText()
        fg_name = self.text_color.currentText()
        
        # Assumptions for Dark Mode (Default)
        bg_hex = COLOR_MAP.get(bg_name, "#1e1e1e") if bg_name != "None" else "#1e1e1e"
        fg_hex = TEXT_COLOR_MAP.get(fg_name, "#e0e0e0") if fg_name != "None" else "#e0e0e0"
        
        try:
            ratio = self.calculate_contrast(bg_hex, fg_hex)
            
            if ratio < 3.0:
                self.contrast_lbl.setText("⚠️ Critical: Very poor contrast!")
                self.contrast_lbl.setToolTip(f"Contrast Ratio: {ratio:.2f}:1 (Target: 4.5:1)")
            elif ratio < 4.5:
                self.contrast_lbl.setText("⚠️ Warning: Low contrast.")
                self.contrast_lbl.setToolTip(f"Contrast Ratio: {ratio:.2f}:1 (Target: 4.5:1)")
            else:
                self.contrast_lbl.setText("")
                self.contrast_lbl.setToolTip("")
        except ValueError:
            self.contrast_lbl.setText("")

    def calculate_contrast(self, hex1, hex2):
        def get_l(c):
            # Hex to linear sRGB
            rgb = [int(c.lstrip('#')[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
            # Gamma correction
            rgb = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
            # Relative luminance
            return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            
        l1 = get_l(hex1)
        l2 = get_l(hex2)
        
        brightest = max(l1, l2)
        darkest = min(l1, l2)
        return (brightest + 0.05) / (darkest + 0.05)

    def get_filter_data(self):
        return {
            "text": self.text_input.text(),
            "case_sensitive": self.case_sensitive.isChecked(),
            "regex": self.regex.isChecked(),
            "exclude": self.exclude.isChecked(),
            "bg_color": self.bg_color.currentText(),
            "text_color": self.text_color.currentText()
        }
