import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QMenuBar, QDialog, QLineEdit, QCheckBox, QComboBox, 
    QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, QProgressDialog, 
    QListWidgetItem, QTabWidget, QMessageBox, QInputDialog
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, pyqtSignal

# Shared Color Maps
COLOR_MAP = {
    "Khaki": "#F0E68C", "Yellow": "#FFFF00", "Cyan": "#00FFFF", "Green": "#90EE90",
    "Red": "#FFB6B6", "Blue": "#B6D0FF", "Gray": "#D3D3D3", "White": "#FFFFFF",
    "Orange": "#FFD580", "Purple": "#E6E6FA", "Brown": "#EEDFCC", "Pink": "#FFD1DC",
    "Violet": "#F3E5F5", "Navy": "#B0C4DE", "Teal": "#B2DFDB", "Olive": "#F5F5DC",
    "Maroon": "#F4CCCC"
}

TEXT_COLOR_MAP = {
    "Black": "#000000", "Red": "#FF0000", "Blue": "#0000FF", "Green": "#008000",
    "Gray": "#808080", "White": "#FFFFFF", "Orange": "#FFA500", "Purple": "#800080",
    "Brown": "#A52A2A", "Pink": "#FFC0CB", "Violet": "#EE82EE", "Navy": "#000080",
    "Teal": "#008080", "Olive": "#808000", "Maroon": "#800000"
}

class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis")
        self.resize(900, 700)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.filter_tabs = QTabWidget()
        self.filter_tab_lists = []  # List of QListWidget, one per tab
        self.filters = []  # List of filter lists, one per tab
        
        self.show_line_numbers = True
        self.show_only_filtered = True
        
        # Data storage
        self.all_lines = []
        self.current_file_path = None
        
        self.create_menu()
        self.init_ui()

    def create_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        load_filters_action = QAction("Load Filters", self)
        load_filters_action.setShortcut("Ctrl+L")
        load_filters_action.triggered.connect(self.load_filters)
        file_menu.addAction(load_filters_action)
        
        save_filters_action = QAction("Save Filters", self)
        save_filters_action.setShortcut("Ctrl+S")
        save_filters_action.triggered.connect(self.save_filters)
        file_menu.addAction(save_filters_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        add_filter_action = QAction("Add Filter", self)
        add_filter_action.setShortcut("Ctrl+F")
        add_filter_action.triggered.connect(self.add_filter_dialog)
        edit_menu.addAction(add_filter_action)

        # View menu
        view_menu = menubar.addMenu("View")
        show_only_filtered_action = QAction("Show Only Filtered Lines", self, checkable=True)
        show_only_filtered_action.setChecked(True)
        show_only_filtered_action.setShortcut("Ctrl+H")
        show_only_filtered_action.triggered.connect(self.toggle_show_only_filtered)
        view_menu.addAction(show_only_filtered_action)
        
        show_line_numbers_action = QAction("Show Line Numbers", self, checkable=True)
        show_line_numbers_action.setChecked(True)
        show_line_numbers_action.triggered.connect(self.toggle_line_numbers)
        view_menu.addAction(show_line_numbers_action)

        # Tabs menu
        tabs_menu = menubar.addMenu("Tabs")
        add_tab_action = QAction("Add Tab", self)
        add_tab_action.setShortcut("Ctrl+T")
        add_tab_action.triggered.connect(self.add_filter_tab)
        tabs_menu.addAction(add_tab_action)
        
        del_tab_action = QAction("Delete Tab", self)
        del_tab_action.setShortcut("Ctrl+D")
        del_tab_action.triggered.connect(self.delete_filter_tab)
        tabs_menu.addAction(del_tab_action)
        
        rename_tab_action = QAction("Rename Tab", self)
        rename_tab_action.setShortcut("Ctrl+R")
        rename_tab_action.triggered.connect(self.rename_filter_tab)
        tabs_menu.addAction(rename_tab_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def rename_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if idx >= 0:
            current_name = self.filter_tabs.tabText(idx)
            new_name, ok = QInputDialog.getText(self, "Rename Tab", "Tab name:", text=current_name)
            if ok and new_name.strip():
                self.filter_tabs.setTabText(idx, new_name.strip())

    def show_about_dialog(self):
        QMessageBox.about(self, "About LogAnalysis GUI",
                          "<b>LogAnalysis GUI</b><br>"
                          "Version 0.0.2<br>"
                          "Developed by: Drew Yu<br>"
                          "Email: drew.developer@gmail.com<br><br>"
                          "A simple log analysis tool built with PyQt5.<br>"
                          "Now supports loading full files without paging.")

    def init_ui(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        
        # Filter tab widget
        self.filter_tab_lists = []
        self.filters = []
        self.add_filter_tab()  # Start with one tab
        
        filter_panel = QWidget()
        filter_layout = QVBoxLayout()
        filter_layout.addWidget(self.filter_tabs)
        filter_panel.setLayout(filter_layout)

        # Use QSplitter for resizable panes
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.text_edit)
        splitter.addWidget(filter_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def add_filter_tab(self):
        filter_list = QListWidget()
        filter_list.setDragDropMode(QListWidget.InternalMove)
        filter_list.itemDoubleClicked.connect(self.edit_filter_dialog)
        filter_list.installEventFilter(self)
        filter_list.model().rowsMoved.connect(lambda: self.sync_filter_order())
        self.filter_tab_lists.append(filter_list)
        self.filters.append([])
        idx = len(self.filter_tab_lists) - 1
        self.filter_tabs.addTab(filter_list, f"Filter Set {idx+1}")
        self.filter_tabs.setCurrentIndex(idx)

    def sync_filter_order(self):
        filter_list, filters = self.current_filter_list()
        new_filters = []
        for i in range(filter_list.count()):
            item = filter_list.item(i)
            filter_data_from_item = item.data(Qt.UserRole)
            if filter_data_from_item:
                new_filters.append(filter_data_from_item)
        if len(new_filters) == len(filters):
            filters.clear()
            filters.extend(new_filters)
            # Reapply colors
            for i in range(filter_list.count()):
                item = filter_list.item(i)
                self.apply_filter_colors(item, filters[i])
        self.apply_filters()

    def delete_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if len(self.filter_tab_lists) > 1 and idx >= 0:
            self.filter_tabs.removeTab(idx)
            del self.filter_tab_lists[idx]
            del self.filters[idx]
            self.apply_filters()

    def current_filter_list(self):
        idx = self.filter_tabs.currentIndex()
        return self.filter_tab_lists[idx], self.filters[idx]
        
    def toggle_line_numbers(self, checked):
        self.show_line_numbers = checked
        self.apply_filters()

    def toggle_show_only_filtered(self, checked):
        self.show_only_filtered = checked
        self.apply_filters()
        
    def apply_filter_colors(self, item, filter_data):
        bg_color = filter_data.get("bg_color", "None")
        text_color = filter_data.get("text_color", "None")
        
        if bg_color != "None":
            item.setBackground(QColor(bg_color))
        if text_color != "None":
            item.setForeground(QColor(text_color))
        
        item.setData(Qt.UserRole, filter_data)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Log/Text Files (*.log *.txt);;All Files (*)"
        )
        if file_path:
            self.current_file_path = file_path
            self.status_bar.showMessage("Loading file...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            try:
                # Use errors='replace' to avoid crashing on binary bits
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    self.all_lines = f.readlines()
                
                self.status_bar.showMessage(f"Loaded: {file_path} ({len(self.all_lines)} lines)")
                self.apply_filters()
            except Exception as e:
                self.status_bar.showMessage(f"Error loading file: {str(e)}")
            finally:
                QApplication.restoreOverrideCursor()

    def add_filter_dialog(self):
        filter_list, filters = self.current_filter_list()
        dialog = FilterDialog(self)
        if dialog.exec_():
            filter_data = dialog.get_filter_data()
            filter_data["active"] = True
            
            item = QListWidgetItem()
            self.apply_filter_colors(item, filter_data)
            filter_list.addItem(item)
            filters.append(filter_data)

            widget = FilterItemWidget(filter_data)
            widget.filter_toggled.connect(self._on_filter_toggled)
            filter_list.setItemWidget(item, widget)
            
            self.apply_filters()

    def _on_filter_toggled(self, filter_data, checked):
        self.apply_filters()

    def edit_filter_dialog(self, item):
        filter_list, filters = self.current_filter_list()
        idx = filter_list.row(item)
        filter_data = filters[idx]
        dialog = FilterDialog(self, filter_data)
        if dialog.exec_():
            new_filter_data = dialog.get_filter_data()
            widget = filter_list.itemWidget(item)
            if widget:
                new_filter_data["active"] = widget.checkbox.isChecked()
            else:
                new_filter_data["active"] = filter_data.get("active", True)

            filters[idx] = new_filter_data
            self.apply_filter_colors(item, new_filter_data)

            if widget:
                widget.filter_data = new_filter_data
                widget.update_display()
            
            self.apply_filters()

    def eventFilter(self, source, event):
        current_idx = self.filter_tabs.currentIndex()
        if current_idx >= 0 and source == self.filter_tab_lists[current_idx] and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Delete:
                selected_items = self.filter_tab_lists[current_idx].selectedItems()
                for item in selected_items:
                    idx = self.filter_tab_lists[current_idx].row(item)
                    self.filter_tab_lists[current_idx].takeItem(idx)
                    del self.filters[current_idx][idx]
                self.apply_filters()
                return True
        return super().eventFilter(source, event)

    def save_filters(self):
        import json
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Filters", "filters.json", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                data = []
                for idx, filters in enumerate(self.filters):
                    tab_name = self.filter_tabs.tabText(idx)
                    data.append({
                        "name": tab_name,
                        "filters": filters
                    })
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.status_bar.showMessage(f"Filters saved to {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error saving filters: {str(e)}")

    def load_filters(self):
        import json
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Filters", "filters.json", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                filter_list, filters = self.current_filter_list()
                filter_list.clear()
                filters.clear()
                
                # Format handling
                if loaded and isinstance(loaded, list) and isinstance(loaded[0], dict) and 'filters' in loaded[0]:
                    loaded_set = loaded[0]['filters']
                    tab_name = loaded[0].get('name')
                    if tab_name:
                        idx = self.filter_tabs.currentIndex()
                        self.filter_tabs.setTabText(idx, tab_name)
                elif loaded and isinstance(loaded, list) and loaded and isinstance(loaded[0], list):
                    loaded_set = loaded[0]
                else:
                    loaded_set = loaded
                
                for filter_data in loaded_set:
                    item = QListWidgetItem()
                    self.apply_filter_colors(item, filter_data)
                    filter_list.addItem(item)
                    filters.append(filter_data)
                    
                    widget = FilterItemWidget(filter_data)
                    widget.filter_toggled.connect(self._on_filter_toggled)
                    filter_list.setItemWidget(item, widget)
                self.apply_filters()
                self.status_bar.showMessage(f"Filters loaded from {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error loading filters: {str(e)}")

    def apply_filters(self):
        if not self.all_lines:
            self.text_edit.clear()
            self.text_edit.append("No data loaded.")
            return

        # Combine all active filters
        all_active_filters = []
        for filters in self.filters:
            for f in filters:
                if f.get("active", True):
                    f['total_matches'] = 0
                    all_active_filters.append(f)
        
        td_style = "color:gray;padding-right:16px;text-align:right;width:100px;vertical-align:top;font-family:monospace;font-size:12px;border-right:1px solid #ccc;background:#f8f8f8;white-space:nowrap;"
        common_cell_style = "white-space:pre;font-family:monospace;font-size:12px;"
        
        rows = []
        
        # Performance: Optimization for large file loops
        import re
        
        for i, line in enumerate(self.all_lines):
            decoded = line.rstrip()
            
            if not all_active_filters:
                # No filters, just show line
                if self.show_line_numbers:
                    rows.append(f"<tr><td style='{td_style}'>{i+1}</td><td style='{common_cell_style}'>{decoded}</td></tr>")
                else:
                     rows.append(f"<tr><td style='{common_cell_style};padding-left:0'>{decoded}</td></tr>")
                continue

            matched = False
            last_match_style = ""
            
            # Check filters
            # Filters are applied from bottom of the list to top (priority)
            for ftr in reversed(all_active_filters):
                is_match = False
                if ftr["regex"]:
                    flags = 0 if ftr["case_sensitive"] else re.IGNORECASE
                    try:
                        if re.search(ftr["text"], decoded, flags):
                            is_match = True
                    except re.error:
                        pass
                else:
                    if ftr["case_sensitive"]:
                        if ftr["text"] in decoded:
                            is_match = True
                    else:
                        if ftr["text"].lower() in decoded.lower():
                            is_match = True
                
                if ftr["exclude"]:
                    if is_match:
                        matched = False
                        break # Exclude wins immediately
                else:
                    if is_match:
                        matched = True
                        ftr['total_matches'] += 1
                        
                        # Determine style contribution
                        bg = ftr["bg_color"]
                        fg = ftr.get("text_color", "None")
                        
                        extra_style = ""
                        if bg != "None":
                            extra_style += f"background-color:{COLOR_MAP.get(bg, bg)};"
                        if fg != "None":
                            extra_style += f"color:{TEXT_COLOR_MAP.get(fg, fg)};"
                        
                        # Since we iterate reversed (priority), the first match we find here
                        # effectively determines the styling if we stop or accumulate.
                        # The original logic seemed to allow "last applied" to win.
                        # "Last applied" in reversed loop is the "First" in the UI list (top of list).
                        # Let's stick to the behavior: Top of list overrides bottom.
                        # So we overwrite last_match_style
                        last_match_style = extra_style

            # Decision to show line
            if matched or not self.show_only_filtered:
                style = common_cell_style
                if matched and last_match_style:
                    style += last_match_style
                elif not matched:
                     # Unmatched lines in "show all" mode get grayed out
                    style += "color:#808080;"
                
                if not self.show_line_numbers:
                    style += "padding-left:0;"
                    rows.append(f"<tr><td style='{style}'>{decoded}</td></tr>")
                else:
                    rows.append(f"<tr><td style='{td_style}'>{i+1}</td><td style='{style}'>{decoded}</td></tr>")

        if rows:
            table_style = "font-family:monospace;font-size:12px;table-layout:fixed;width:100%;border-collapse:collapse;"
            container_style = "margin:0;padding:0;"
            if not self.show_line_numbers:
                container_style = "margin:0;padding:0 10px;"
            html = f"<div style='{container_style}'><table style='{table_style}'><tbody>" + ''.join(rows) + "</tbody></table></div>"
            self.text_edit.setHtml(html)
        else:
            self.text_edit.setHtml("<i>No lines matched the filter.</i>")

        if not all_active_filters:
            self.status_bar.showMessage(f"Showing all {len(self.all_lines)} lines.")
        else:
            self.status_bar.showMessage(f"Filtered view: {len(rows)} lines shown out of {len(self.all_lines)}.")

        # Update filter match counts in UI
        filter_list, filters = self.current_filter_list()
        for i in range(filter_list.count()):
            item = filter_list.item(i)
            filter_data = filters[i]
            widget = filter_list.itemWidget(item)
            if widget:
                widget.filter_data = filter_data
                widget.update_display()


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
        text = self.filter_data["text"]
        if self.filter_data["exclude"]:
            text = f"NOT: {text}"
        if self.filter_data["regex"]:
            text = f"REGEX: {text}"
        if self.filter_data["case_sensitive"]:
            text = f"CASE: {text}"
        
        self.text_label.setText(text)
        
        count = self.filter_data.get('total_matches', 0)
        if count > 0:
            self.count_label.setText(f"({count})")
        else:
            self.count_label.setText("")

        bg_color_name = self.filter_data.get("bg_color", "None")
        text_color_name = self.filter_data.get("text_color", "None")

        style_sheet = ""
        if bg_color_name != "None":
            style_sheet += f"background-color: {COLOR_MAP.get(bg_color_name, bg_color_name)};"
        
        if text_color_name != "None":
            style_sheet += f"color: {TEXT_COLOR_MAP.get(text_color_name, text_color_name)};"
        
        self.text_label.setStyleSheet(style_sheet)

class FilterDialog(QDialog):
    def __init__(self, parent=None, filter_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Filter" if filter_data is None else "Edit Filter")
        self.setModal(True)
        self.text_input = QLineEdit()
        self.case_sensitive = QCheckBox("Case-sensitive")
        self.regex = QCheckBox("Regular expression")
        self.exclude = QCheckBox("Excluding")
        
        self.text_color = QComboBox()
        self.text_color.addItem("None")
        self.text_color.addItems(sorted([k for k in TEXT_COLOR_MAP.keys()]))
        
        self.bg_color = QComboBox()
        self.bg_color.addItem("None")
        self.bg_color.addItems(sorted([k for k in COLOR_MAP.keys()]))
        
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.layout_ui()
        
        if filter_data:
            self.text_input.setText(filter_data["text"])
            self.case_sensitive.setChecked(filter_data["case_sensitive"])
            self.regex.setChecked(filter_data["regex"])
            self.exclude.setChecked(filter_data["exclude"])
            
            idx = self.bg_color.findText(filter_data["bg_color"])
            if idx >= 0:
                self.bg_color.setCurrentIndex(idx)
            idx = self.text_color.findText(filter_data.get("text_color", "None"))
            if idx >= 0:
                self.text_color.setCurrentIndex(idx)

    def layout_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Text:"))
        layout.addWidget(self.text_input)
        layout.addWidget(self.case_sensitive)
        layout.addWidget(self.regex)
        layout.addWidget(self.exclude)
        layout.addWidget(QLabel("Text Color:"))
        layout.addWidget(self.text_color)
        layout.addWidget(QLabel("Background:"))
        layout.addWidget(self.bg_color)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_filter_data(self):
        return {
            "text": self.text_input.text(),
            "case_sensitive": self.case_sensitive.isChecked(),
            "regex": self.regex.isChecked(),
            "exclude": self.exclude.isChecked(),
            "bg_color": self.bg_color.currentText(),
            "text_color": self.text_color.currentText()
        }

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LogAnalysisMainWindow()
    window.show()
    sys.exit(app.exec_())
