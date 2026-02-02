import sys
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QDialog, QLineEdit, QCheckBox, QComboBox, 
    QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, 
    QListWidgetItem, QTabWidget, QMessageBox, QInputDialog, QListView,
    QAbstractItemView
)
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractListModel, QModelIndex, QThread, QSize

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

class FilterWorker(QThread):
    """
    Background worker to scan all lines and determine which ones match the filters.
    Returns a list of indices that matched.
    """
    finished_filtering = pyqtSignal(list, int) # list of indices, match count

    def __init__(self, lines, filters, show_only_filtered):
        super().__init__()
        self.lines = lines
        self.filters = filters
        self.show_only_filtered = show_only_filtered
        self.is_running = True

    def run(self):
        visible_indices = []
        match_count = 0
        
        # Pre-compile regexes for performance
        active_filters = []
        for f in self.filters:
            if f.get("active", True):
                f_data = f.copy()
                if f["regex"]:
                    flags = 0 if f["case_sensitive"] else re.IGNORECASE
                    try:
                        f_data["compiled_re"] = re.compile(f["text"], flags)
                    except re.error:
                        f_data["compiled_re"] = None
                active_filters.append(f_data)

        # If no filters are active/exist
        if not active_filters:
            # If show_only_filtered is True, we show nothing? 
            # Or usually "Show Only Filtered" means "Show matches". If no filters, nothing matches.
            # But the logic in original app was: if valid filters exist, filter. 
            # If no filters, showing all is usually simpler, OR showing nothing.
            # Let's align with typical behavior: No filters defined -> Show everything?
            # Or No filters -> Show everything regardless of "Show Only Filtered" toggle?
            # Reverting to original logic: If "filters exist", we filter. If list is empty -> Show all.
            pass

        # Optimization: reverse active filters once for priority logic check
        # But for 'inclusion', any match allows it to be shown (unless excluded).
        # We need to loop line by line.
        
        count = len(self.lines)
        for i in range(count):
            if not self.is_running:
                return

            line = self.lines[i]
            
            # Logic:
            # If no filters active: Show all loop
            if not active_filters:
                visible_indices.append(i)
                continue

            # Check matches
            matched = False
            for ftr in reversed(active_filters):
                is_match = False
                
                # Check Match
                if ftr["regex"]:
                    if ftr["compiled_re"] and ftr["compiled_re"].search(line):
                        is_match = True
                else:
                    if ftr["case_sensitive"]:
                        if ftr["text"] in line:
                            is_match = True
                    else:
                        if ftr["text"].lower() in line.lower():
                            is_match = True
                
                if ftr["exclude"]:
                    if is_match:
                        matched = False
                        break # Explicitly excluded, stop checking
                else:
                    if is_match:
                        matched = True
                        # Continue checking? 
                        # In painting logic, we care about the LAST match for color.
                        # In visibility logic, we just need ONE match to show it.
                        # Exclude overrides all.
            
            if matched:
                match_count += 1
                visible_indices.append(i)
            elif not self.show_only_filtered:
                # If we are NOT showing only filtered, we show unmatched lines too
                visible_indices.append(i)
        
        self.finished_filtering.emit(visible_indices, match_count)

    def stop(self):
        self.is_running = False

class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_lines = [] # Raw string data
        self.visible_indices = [] # Indices of lines to show
        self.filters = []
        self.show_line_numbers = True
        self.show_only_filtered = True # Default state
        self.font = QFont("Monospace")
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.visible_indices)

    def data(self, index, role):
        if not index.isValid():
            return None
        
        row = index.row()
        if row >= len(self.visible_indices):
            return None
            
        real_idx = self.visible_indices[row]
        line_text = self.all_lines[real_idx]

        if role == Qt.DisplayRole:
            # Strip newline for display
            clean_text = line_text.rstrip('\r\n')
            if self.show_line_numbers:
                return f"{real_idx + 1:6d} | {clean_text}"
            return clean_text

        if role == Qt.FontRole:
            return self.font

        if role == Qt.BackgroundRole or role == Qt.ForegroundRole:
            # Determine color dynamically for valid view items
            # This is fast enough for the viewport (e.g. 50 items)
            return self._get_color(line_text, role)

        return None

    def _get_color(self, line, role):
        if not self.filters:
            return None

        # Filter logic again for coloring
        # We process from bottom to top (priority)
        # The topmost filter in the list (last in iteration? no reversed)
        # In UI list: Index 0 is top. We want Top to override Bottom? 
        # Usually in lists, the item on top is highest priority.
        # Original code reversed the list. Let's stick to that.
        
        bg_result = None
        fg_result = None
        
        matched_any = False

        for ftr in reversed(self.filters):
            if not ftr.get("active", True):
                continue

            is_match = False
            # Quick check
            if ftr["regex"]:
                # We should re-compile or cache. `re` module caches internally.
                try:
                    flags = 0 if ftr["case_sensitive"] else re.IGNORECASE
                    if re.search(ftr["text"], line, flags):
                        is_match = True
                except: pass
            else:
                if ftr["case_sensitive"]:
                    if ftr["text"] in line:
                        is_match = True
                else:
                    if ftr["text"].lower() in line.lower():
                        is_match = True
            
            if ftr["exclude"]:
                if is_match:
                    return None # Excluded lines have no special color (or shouldn't be here)
            else:
                if is_match:
                    matched_any = True
                    # Set colors
                    if ftr["bg_color"] != "None":
                        bg_result = ftr["bg_color"]
                    if ftr.get("text_color", "None") != "None":
                        fg_result = ftr["text_color"]
        
        if not matched_any:
            # If line is shown but not matched (i.e. context), make it gray?
            if role == Qt.ForegroundRole:
                return QColor("#808080")
            return None

        if role == Qt.BackgroundRole and bg_result:
            return QColor(COLOR_MAP.get(bg_result, bg_result))
        if role == Qt.ForegroundRole and fg_result:
            return QColor(TEXT_COLOR_MAP.get(fg_result, fg_result))
            
        return None

    def set_lines(self, lines):
        self.beginResetModel()
        self.all_lines = lines
        self.visible_indices = list(range(len(lines)))
        self.endResetModel()

    def update_visible_indices(self, indices):
        self.beginResetModel()
        self.visible_indices = indices
        self.endResetModel()

class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis (High Performance)")
        self.resize(900, 700)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.create_menu()
        self.init_ui()
        
        # Filtering Thread
        self.filter_thread = None

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

    def init_ui(self):
        # Replaced QTextEdit with QListView
        self.log_view = QListView()
        self.log_view.setUniformItemSizes(True) # Performance Optimization
        self.log_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        self.log_model = LogModel()
        self.log_view.setModel(self.log_model)

        self.filter_tabs = QTabWidget()
        self.filter_tab_lists = []
        self.filters = []
        self.add_filter_tab()

        filter_panel = QWidget()
        filter_layout = QVBoxLayout()
        filter_layout.addWidget(self.filter_tabs)
        filter_panel.setLayout(filter_layout)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.log_view)
        splitter.addWidget(filter_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

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
                          "Version 0.0.3 (Performance)<br>"
                          "Developed by: Drew Yu<br>"
                          "Optimized for large files using QListView.")

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
            for i in range(filter_list.count()):
                item = filter_list.item(i)
                self.apply_filter_colors_to_list_item(item, filters[i])
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
        self.log_model.show_line_numbers = checked
        self.log_model.layoutChanged.emit() # Force refresh

    def toggle_show_only_filtered(self, checked):
        self.log_model.show_only_filtered = checked
        self.apply_filters()

    def apply_filter_colors_to_list_item(self, item, filter_data):
        bg_color = filter_data.get("bg_color", "None")
        text_color = filter_data.get("text_color", "None")
        if bg_color != "None":
            item.setBackground(QColor(COLOR_MAP.get(bg_color, bg_color)))
        if text_color != "None":
            item.setForeground(QColor(TEXT_COLOR_MAP.get(text_color, text_color)))
        item.setData(Qt.UserRole, filter_data)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Log/Text Files (*.log *.txt);;All Files (*)"
        )
        if file_path:
            self.status_bar.showMessage("Loading file...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                # Read all lines
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                self.log_model.set_lines(lines)
                self.status_bar.showMessage(f"Loaded: {file_path} ({len(lines)} lines)")
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
            self.apply_filter_colors_to_list_item(item, filter_data)
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
            self.apply_filter_colors_to_list_item(item, new_filter_data)

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
                    self.apply_filter_colors_to_list_item(item, filter_data)
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
        if not self.log_model.all_lines:
            return

        # Combine active filters
        active_filters = []
        for filters in self.filters:
            for f in filters:
                if f.get("active", True):
                    active_filters.append(f)
        
        # Pass filters to model so it can paint
        self.log_model.filters = active_filters
        
        # Stop existing thread if running
        if self.filter_thread and self.filter_thread.isRunning():
            self.filter_thread.stop()
            self.filter_thread.wait()
        
        # Start new filtering thread
        self.status_bar.showMessage("Filtering...")
        self.filter_thread = FilterWorker(
            self.log_model.all_lines, 
            active_filters, 
            self.log_model.show_only_filtered
        )
        self.filter_thread.finished_filtering.connect(self.on_filtering_finished)
        self.filter_thread.start()

    def on_filtering_finished(self, visible_indices, match_count):
        self.log_model.update_visible_indices(visible_indices)
        self.status_bar.showMessage(f"Showing {len(visible_indices)} lines ({match_count} matched)")
        
        # Update match counts in UI (approximation, since we don't count per-filter in this condensed loop yet)
        # Note: The high-perf worker only counts total matches or we'd need a more complex return structure.
        # For now, we skip updating individual filter match counts to save performance? 
        # Or we can make the worker return a dict of {filter_idx: count}. 
        # For simplicity in this step, we'll accept that individual counts might not update live in high-perf mode.
        pass

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
