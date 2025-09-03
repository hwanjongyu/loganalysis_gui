import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QMenuBar, QDialog, QLineEdit, QCheckBox, QComboBox, QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, QProgressDialog, QListWidgetItem, QTabWidget
)
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtCore import Qt

class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis")
        self.resize(900, 700)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.setCentralWidget(self.text_edit)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.filter_tabs = QTabWidget()
        self.filter_tab_lists = []  # List of QListWidget, one per tab
        self.filters = []  # List of filter lists, one per tab
        self.show_line_numbers = True  # Track line number visibility
        self.show_only_filtered = True  # Track filter-only visibility
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
        view_menu.addSeparator()
        next_page_action = QAction("Next Page", self)
        next_page_action.setShortcut("Ctrl+N")
        next_page_action.triggered.connect(self.next_page)
        view_menu.addAction(next_page_action)
        prev_page_action = QAction("Previous Page", self)
        prev_page_action.setShortcut("Ctrl+P")
        prev_page_action.triggered.connect(self.prev_page)
        view_menu.addAction(prev_page_action)

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

    def rename_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if idx >= 0:
            from PyQt5.QtWidgets import QInputDialog
            current_name = self.filter_tabs.tabText(idx)
            new_name, ok = QInputDialog.getText(self, "Rename Tab", "Tab name:", text=current_name)
            if ok and new_name.strip():
                self.filter_tabs.setTabText(idx, new_name.strip())

    def init_ui(self):
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.lines_per_page = 5000
        self.current_page = 0
        self.current_file_path = None
        self.total_lines = 0
        self.file_line_offsets = []
        self.next_btn = QPushButton("Next")
        self.prev_btn = QPushButton("Previous")
        self.next_btn.clicked.connect(self.next_page)
        self.prev_btn.clicked.connect(self.prev_page)
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)

        # Filter tab widget at the bottom (no add/delete tab buttons)
        self.filter_tabs = QTabWidget()
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
        layout.addLayout(nav_layout)
        layout.addWidget(splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def add_filter_tab(self):
        filter_list = QListWidget()
        filter_list.setDragDropMode(QListWidget.InternalMove)  # Enable drag-and-drop reordering
        filter_list.itemDoubleClicked.connect(self.edit_filter_dialog)
        filter_list.installEventFilter(self)
        filter_list.itemChanged.connect(self.toggle_filter_active)
        filter_list.model().rowsMoved.connect(lambda: self.sync_filter_order())
        self.filter_tab_lists.append(filter_list)
        self.filters.append([])
        idx = len(self.filter_tab_lists) - 1
        self.filter_tabs.addTab(filter_list, f"Filter Set {idx+1}")
        self.filter_tabs.setCurrentIndex(idx)

    def sync_filter_order(self):
        # Sync the order of self.filters with the QListWidget order
        filter_list, filters = self.current_filter_list()
        new_filters = []
        for i in range(filter_list.count()):
            item = filter_list.item(i)
            # Find the filter dict that matches this item's display text
            for f in filters:
                if self.format_filter_display(f) == item.text():
                    new_filters.append(f)
                    break
        if len(new_filters) == len(filters):
            filters.clear()
            filters.extend(new_filters)
        self.apply_filters()

    def delete_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if len(self.filter_tab_lists) > 1 and idx >= 0:
            self.filter_tabs.removeTab(idx)
            del self.filter_tab_lists[idx]
            del self.filters[idx]
            self.apply_filters()  # Refresh view after tab deletion

    def current_filter_list(self):
        idx = self.filter_tabs.currentIndex()
        return self.filter_tab_lists[idx], self.filters[idx]
        
    def format_filter_display(self, filter_data):
        """Format the filter text for display in the list."""
        text = filter_data["text"]
        if filter_data["exclude"]:
            text = f"NOT: {text}"
        if filter_data["regex"]:
            text = f"REGEX: {text}"
        if filter_data["case_sensitive"]:
            text = f"CASE: {text}"
        return text
        
    def toggle_line_numbers(self, checked):
        """Toggle the visibility of line numbers."""
        self.show_line_numbers = checked
        self.apply_filters()  # Refresh the display

    def toggle_show_only_filtered(self, checked):
        """Toggle showing only filtered lines."""
        self.show_only_filtered = checked
        self.apply_filters()  # Refresh the display
        
    def apply_filter_colors(self, item, filter_data):
        """Apply background and text colors to a list item."""
        bg_color = filter_data.get("bg_color", "None")
        text_color = filter_data.get("text_color", "None")
        
        if bg_color != "None":
            item.setBackground(QColor(bg_color))
        if text_color != "None":
            item.setForeground(QColor(text_color))
        
        item.setData(Qt.UserRole, filter_data)  # Store filter data for later use

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Log/Text Files (*.log *.txt);;All Files (*)"
        )
        if file_path:
            self.current_file_path = file_path
            self.current_page = 0
            self.status_bar.showMessage("Indexing file for fast loading...")
            self.prepare_file_offsets(file_path)
            self.status_bar.showMessage("Loading first page...")
            self.load_page()
            self.status_bar.showMessage(f"Loaded: {file_path}")

    def prepare_file_offsets(self, file_path):
        from PyQt5.QtWidgets import QProgressDialog
        self.file_line_offsets = [0]
        self.total_lines = 0
        progress = QProgressDialog("Indexing file for fast loading...", None, 0, 0, self)
        progress.setWindowTitle("Preparing File")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        offset = 0
        try:
            with open(file_path, 'rb') as f:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    offset += len(line)
                    self.file_line_offsets.append(offset)
                    self.total_lines += 1
                    if self.total_lines % 10000 == 0:
                        progress.setLabelText(f"Indexed {self.total_lines} lines...")
                        QApplication.processEvents()
            progress.setLabelText(f"Indexed {self.total_lines} lines. Done.")
            QApplication.processEvents()
        finally:
            progress.close()

    def load_page(self):
        if not self.current_file_path or not self.file_line_offsets or self.total_lines == 0:
            self.text_edit.clear()
            self.text_edit.append("No data loaded.")
            return
        start_line = self.current_page * self.lines_per_page
        end_line = min(start_line + self.lines_per_page, self.total_lines)
        rows = []
        # Use a larger fixed width, prevent wrapping, and center the line number
        td_style = "color:gray;padding-right:16px;text-align:right;width:100px;vertical-align:top;font-family:monospace;font-size:12px;border-right:1px solid #ccc;background:#f8f8f8;white-space:nowrap;"
        with open(self.current_file_path, 'rb') as f:
            f.seek(self.file_line_offsets[start_line])
            for i in range(start_line, end_line):
                line = f.readline()
                if not line:
                    break
                try:
                    decoded = line.decode('utf-8', errors='replace').rstrip()
                except Exception as e:
                    decoded = f"[Decode error: {e}]"
                rows.append(f"<tr><td style='{td_style}'>{i+1}</td><td style='white-space:pre;font-family:monospace;font-size:12px;'>{decoded}</td></tr>")
        self.text_edit.clear()
        if rows:
            html = "<table style='font-family:monospace;font-size:12px;table-layout:fixed;width:100%;border-collapse:collapse;'><tbody>" + ''.join(rows) + "</tbody></table>"
            self.text_edit.setHtml(html)
        else:
            self.text_edit.append("No data loaded.")
        self.status_bar.showMessage(f"Showing lines {start_line+1}-{end_line} of {self.total_lines}")
        # self.apply_filters()  # Keep filter logic disabled for now

    def next_page(self):
        if (self.current_page + 1) * self.lines_per_page < self.total_lines:
            self.current_page += 1
            self.apply_filters()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.apply_filters()

    def add_filter_dialog(self):
        filter_list, filters = self.current_filter_list()
        dialog = FilterDialog(self)
        if dialog.exec_():
            filter_data = dialog.get_filter_data()
            filter_data["active"] = True
            item = QListWidgetItem(self.format_filter_display(filter_data))
            item.setCheckState(Qt.Checked)
            self.apply_filter_colors(item, filter_data)
            filter_list.addItem(item)
            filters.append(filter_data)
            self.apply_filters()

    def edit_filter_dialog(self, item):
        filter_list, filters = self.current_filter_list()
        idx = filter_list.row(item)
        filter_data = filters[idx]
        dialog = FilterDialog(self, filter_data)
        if dialog.exec_():
            new_filter_data = dialog.get_filter_data()
            new_filter_data["active"] = item.checkState() == Qt.Checked
            filters[idx] = new_filter_data
            item.setText(self.format_filter_display(new_filter_data))
            self.apply_filter_colors(item, new_filter_data)
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

    def toggle_filter_active(self, item):
        filter_list, filters = self.current_filter_list()
        idx = filter_list.row(item)
        filters[idx]["active"] = item.checkState() == Qt.Checked
        self.apply_filters()

    def save_filters(self):
        import json
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Filters", "filters.json", "JSON Files (*.json);;All Files (*)")
        if file_path:
            try:
                # Save both filters and tab names
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
                # Only load to the current (active) tab, do not remove or add tabs
                filter_list, filters = self.current_filter_list()
                filter_list.clear()
                filters.clear()
                # Support both new (with names) and old (list of lists or list of filters) formats
                if loaded and isinstance(loaded, list) and isinstance(loaded[0], dict) and 'filters' in loaded[0]:
                    # New format with tab names: load only the first tab's filters
                    loaded_set = loaded[0]['filters']
                    tab_name = loaded[0].get('name')
                    if tab_name:
                        idx = self.filter_tabs.currentIndex()
                        self.filter_tabs.setTabText(idx, tab_name)
                elif loaded and isinstance(loaded, list) and loaded and isinstance(loaded[0], list):
                    # Multiple filter sets (tabs), legacy format: load only the first set
                    loaded_set = loaded[0]
                else:
                    # Single filter set (legacy or empty)
                    loaded_set = loaded
                for filter_data in loaded_set:
                    item = QListWidgetItem(self.format_filter_display(filter_data))
                    item.setCheckState(Qt.Checked if filter_data.get("active", True) else Qt.Unchecked)
                    self.apply_filter_colors(item, filter_data)
                    filter_list.addItem(item)
                    filters.append(filter_data)
                self.apply_filters()
                self.status_bar.showMessage(f"Filters loaded to current tab from {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error loading filters: {str(e)}")

    def apply_filters(self):
        # Combine all active filters from all tabs
        all_active_filters = []
        for filters in self.filters:
            all_active_filters.extend([f for f in filters if f.get("active", True)])
        filter_list, filters = self.current_filter_list()
        if not self.current_file_path or not self.file_line_offsets or self.total_lines == 0:
            self.text_edit.clear()
            self.text_edit.append("No data loaded.")
            return
        start_line = self.current_page * self.lines_per_page
        end_line = min(start_line + self.lines_per_page, self.total_lines)
        td_style = "color:gray;padding-right:16px;text-align:right;width:100px;vertical-align:top;font-family:monospace;font-size:12px;border-right:1px solid #ccc;background:#f8f8f8;white-space:nowrap;"
        text_color_map = {
            "Black": "#000000",
            "Red": "#FF0000",
            "Blue": "#0000FF",
            "Green": "#008000",
            "Gray": "#808080",
            "White": "#FFFFFF",
            "Orange": "#FFA500",
            "Purple": "#800080",
            "Brown": "#A52A2A",
            "Pink": "#FFC0CB",
            "Violet": "#EE82EE",
            "Navy": "#000080",
            "Teal": "#008080",
            "Olive": "#808000",
            "Maroon": "#800000"
        }
        color_map = {
            "Khaki": "#F0E68C",
            "Yellow": "#FFFF00",
            "Cyan": "#00FFFF",
            "Green": "#90EE90",
            "Red": "#FFB6B6",
            "Blue": "#B6D0FF",
            "Gray": "#D3D3D3",
            "White": "#FFFFFF",
            "Orange": "#FFD580",
            "Purple": "#E6E6FA",
            "Brown": "#EEDFCC",
            "Pink": "#FFD1DC",
            "Violet": "#F3E5F5",
            "Navy": "#B0C4DE",
            "Teal": "#B2DFDB",
            "Olive": "#F5F5DC",
            "Maroon": "#F4CCCC"
        }
        rows = []
        with open(self.current_file_path, 'rb') as f:
            f.seek(self.file_line_offsets[start_line])
            for i in range(start_line, end_line):
                line = f.readline()
                if not line:
                    break
                try:
                    decoded = line.decode('utf-8', errors='replace').rstrip()
                except Exception as e:
                    decoded = f"[Decode error: {e}]"
                cell_style = "white-space:pre;font-family:monospace;font-size:12px;"
                if not all_active_filters:
                    style = cell_style
                    if self.show_line_numbers:
                        rows.append(f"<tr><td style='{td_style}'>{i+1}</td><td style='{style}'>{decoded}</td></tr>")
                    else:
                        rows.append(f"<tr><td style='{style};padding-left:0'>{decoded}</td></tr>")
                else:
                    matched = False
                    last_color = None
                    last_text_color = None
                    # Change filter order: apply from bottom to top
                    for ftr in reversed(all_active_filters):
                        match = False
                        if ftr["regex"]:
                            import re
                            flags = 0 if ftr["case_sensitive"] else re.IGNORECASE
                            try:
                                if re.search(ftr["text"], decoded, flags):
                                    match = True
                            except re.error:
                                pass
                        else:
                            if ftr["case_sensitive"]:
                                if ftr["text"] in decoded:
                                    match = True
                            else:
                                if ftr["text"].lower() in decoded.lower():
                                    match = True
                        if ftr["exclude"]:
                            if match:
                                matched = False
                                break
                        else:
                            if match:
                                matched = True
                                last_color = ftr["bg_color"]
                                last_text_color = ftr.get("text_color", "None")
                    # Handle both matched and unmatched lines
                    if matched or not self.show_only_filtered:
                        style = "white-space:pre;font-family:monospace;font-size:12px;"
                        
                        if matched:
                            # Apply filter colors for matched lines
                            if last_color and last_color != "None":
                                style += f"background-color:{color_map.get(last_color, last_color)};"
                            if last_text_color and last_text_color != "None":
                                style += f"color:{text_color_map.get(last_text_color, last_text_color)};"
                        else:
                            # Gray color for unmatched lines
                            style += "color:#808080;"
                            
                        if not self.show_line_numbers:
                            style += "padding-left:0;"
                        if self.show_line_numbers:
                            rows.append(f"<tr><td style='{td_style}'>{i+1}</td><td style='{style}'>{decoded}</td></tr>")
                        else:
                            rows.append(f"<tr><td style='{style}'>{decoded}</td></tr>")
        if rows:
            table_style = "font-family:monospace;font-size:12px;table-layout:fixed;width:100%;border-collapse:collapse;"
            container_style = "margin:0;padding:0;"
            if not self.show_line_numbers:
                container_style = "margin:0;padding:0 10px;"  # Add padding when line numbers are hidden
            html = f"<div style='{container_style}'><table style='{table_style}'><tbody>" + ''.join(rows) + "</tbody></table></div>"
            self.text_edit.setHtml(html)
        else:
            self.text_edit.setHtml("<i>No lines matched the filter.</i>")
        if not all_active_filters:
            self.status_bar.showMessage(f"No filters active. Showing original file.")
        else:
            self.status_bar.showMessage(f"Filtered: {len(rows)} lines, {len(all_active_filters)} active filters.")

class FilterDialog(QDialog):
    def __init__(self, parent=None, filter_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Filter" if filter_data is None else "Edit Filter")
        self.setModal(True)
        self.text_input = QLineEdit()
        self.case_sensitive = QCheckBox("Case-sensitive")
        self.regex = QCheckBox("Regular expression")
        self.exclude = QCheckBox("Excluding")
        # More text and background colors
        self.text_color = QComboBox()
        self.text_color.addItems([
            "None", "Black", "Red", "Blue", "Green", "Gray", "White", "Orange", "Purple", "Brown", "Pink", "Violet", "Navy", "Teal", "Olive", "Maroon"
        ])
        self.bg_color = QComboBox()
        self.bg_color.addItems([
            "None", "Khaki", "Yellow", "Cyan", "Green", "Red", "Blue", "Gray", "White", "Orange", "Purple", "Brown", "Pink", "Violet", "Navy", "Teal", "Olive", "Maroon"
        ])
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
