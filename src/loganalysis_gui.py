import sys
import re
import subprocess
import os
import json
import bisect
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QDialog, QLineEdit, QCheckBox, QComboBox, 
    QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, 
    QListWidgetItem, QTabWidget, QMessageBox, QInputDialog, QTreeView,
    QAbstractItemView, QDockWidget, QToolBar, QStyle, QGroupBox, QFormLayout,
    QHeaderView
)
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractListModel, QModelIndex, QThread, QSize, QMutex

# Shared Color Maps
COLOR_MAP = {
    "Khaki": "#F0E68C", "Yellow": "#FFFF00", "Gold": "#FFD700", "Cyan": "#00FFFF",
    "Aqua": "#00FFFF", "Green": "#90EE90", "Lime": "#00FF00", "PaleGreen": "#98FB98",
    "Red": "#FFB6B6", "Salmon": "#FA8072", "Coral": "#FF7F50", "Blue": "#B6D0FF",
    "SkyBlue": "#87CEEB", "LightBlue": "#ADD8E6", "Gray": "#D3D3D3", "Silver": "#C0C0C0",
    "White": "#FFFFFF", "Orange": "#FFD580", "Wheat": "#F5DEB3", "Purple": "#E6E6FA",
    "Plum": "#DDA0DD", "Orchid": "#DA70D6", "Brown": "#EEDFCC", "Pink": "#FFD1DC", 
    "HotPink": "#FF69B4", "Violet": "#F3E5F5", "Navy": "#B0C4DE", "Teal": "#B2DFDB", 
    "Olive": "#F5F5DC", "Maroon": "#F4CCCC"
}

TEXT_COLOR_MAP = {
    "Black": "#000000", "Red": "#FF0000", "DarkRed": "#8B0000", "Crimson": "#DC143C",
    "Blue": "#0000FF", "DarkBlue": "#00008B", "RoyalBlue": "#4169E1", "Green": "#008000",
    "DarkGreen": "#006400", "SeaGreen": "#2E8B57", "Gray": "#808080", "DarkGray": "#A9A9A9",
    "White": "#FFFFFF", "Orange": "#FFA500", "DarkOrange": "#FF8C00", "Purple": "#800080",
    "DarkMagenta": "#8B008B", "Indigo": "#4B0082", "Brown": "#A52A2A", "SaddleBrown": "#8B4513",
    "Pink": "#FFC0CB", "DeepPink": "#FF1493", "Violet": "#EE82EE", "Navy": "#000080", 
    "Teal": "#008080", "Olive": "#808000", "Maroon": "#800000"
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QListView {
    background-color: #1e1e1e;
    color: #e0e0e0;
    selection-background-color: #3a3a3a;
    selection-color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #444;
}
QTabBar::tab {
    background: #333;
    color: #aaa;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background: #444;
    color: #fff;
    font-weight: bold;
}
QLineEdit, QComboBox, QCheckBox {
    background-color: #333;
    color: #e0e0e0;
    border: 1px solid #555;
    padding: 2px;
}
QPushButton {
    background-color: #444;
    color: #e0e0e0;
    border: 1px solid #555;
    padding: 5px;
}
QPushButton:hover {
    background-color: #555;
}
QStatusBar {
    background-color: #222;
    color: #888;
}
QMenuBar {
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QMenuBar::item:selected {
    background-color: #444;
}
QMenu {
    background-color: #2b2b2b;
    color: #e0e0e0;
    border: 1px solid #444;
}
QMenu::item:selected {
    background-color: #444;
}
QLabel {
    color: #e0e0e0;
}
"""

class AdbWorker(QThread):
    chunk_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.process = None

    def run(self):
        try:
            self.process = subprocess.Popen(
                ['adb', 'logcat', '-v', 'threadtime'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True, 
                encoding='utf-8', 
                errors='replace'
            )
            proc = self.process
            
            buffer = []
            while self.is_running:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                
                if line:
                    buffer.append(line)
                
                if len(buffer) >= 100 or (buffer and not line):
                    self.chunk_ready.emit(buffer)
                    buffer = []
            
            if buffer:
                self.chunk_ready.emit(buffer)
                
        except FileNotFoundError:
            self.error_occurred.emit("ADB not found. Please ensure 'adb' is in your PATH.")
        except Exception as e:
            self.error_occurred.emit(f"ADB Error: {str(e)}")
        finally:
            self.terminate_process()

    def stop(self):
        self.is_running = False
        self.terminate_process()
    
    def terminate_process(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.kill()
            except:
                pass
            self.process = None


class FilterWorker(QThread):
    finished_filtering = pyqtSignal(list, int, list)
    
    def __init__(self, lines, filters, show_only_filtered):
        super().__init__()
        self.lines = lines
        self.filters = filters
        self.show_only_filtered = show_only_filtered
        self.is_running = True

    def run(self):
        visible_indices = []
        match_count = 0
        
        # Initialize counts for ALL filters passed in
        filter_counts = [0] * len(self.filters)
        
        # Pre-compile active filters for speed
        active_filters = []
        for i, f in enumerate(self.filters):
            if f.get("active", True):
                f_data = f.copy()
                f_data['original_index'] = i 
                if f["regex"]:
                    try:
                        flags = 0 if f["case_sensitive"] else re.IGNORECASE
                        f_data["compiled_re"] = re.compile(f["text"], flags)
                    except re.error:
                        f_data["compiled_re"] = None
                active_filters.append(f_data)

        count = len(self.lines)
        for i in range(count):
            if not self.is_running:
                return

            line = self.lines[i]
            
            # If no active filters, line is visible if NOT show_only_filtered
            # Consistent with append_chunk: show everything if no filters
            if not active_filters:
                visible_indices.append(i)
                continue

            this_line_matches = [] # list of original_indices that matched
            matched_decision = False
            
            # Visibility and Counting Pass
            # We must check all active filters to get accurate counts, 
            # but priority is reversed for the visibility decision.
            
            # Determine matches for all active filters
            for ftr in active_filters:
                is_match = False
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
                
                if is_match:
                    filter_counts[ftr['original_index']] += 1
                    this_line_matches.append(ftr)
            
            # Decide visibility from the matches found (Highest index filter wins)
            if this_line_matches:
                # Iterate in reverse order of definition
                # ftr is from active_filters which is sorted by original index
                for ftr in reversed(this_line_matches):
                    if ftr["exclude"]:
                        matched_decision = False
                        break # Exclude wins priority
                    else:
                        matched_decision = True
                        break # Include wins priority
            
            if matched_decision:
                match_count += 1
                visible_indices.append(i)
            elif not self.show_only_filtered:
                visible_indices.append(i)
        
        self.finished_filtering.emit(visible_indices, match_count, filter_counts)

    def stop(self):
        self.is_running = False

class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_lines = [] 
        self.visible_indices = [] 
        self.filters = []
        self.show_line_numbers = True
        self.show_only_filtered = True
        self.font = QFont("Monospace", 10) # Default size 10
        
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
            clean_text = line_text.rstrip('\r\n')
            if self.show_line_numbers:
                return f"{real_idx + 1:6d} | {clean_text}"
            return clean_text

        if role == Qt.FontRole:
            return self.font

        if role == Qt.BackgroundRole or role == Qt.ForegroundRole:
            return self._get_color(line_text, role)

        return None

    def _get_color(self, line, role):
        if not self.filters:
            return None
            
        bg_result = None
        fg_result = None
        matched_any = False

        for ftr in reversed(self.filters):
            if not ftr.get("active", True):
                continue

            is_match = False
            if ftr["regex"]:
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
                    return None 
            else:
                if is_match:
                    matched_any = True
                    if ftr["bg_color"] != "None":
                        bg_result = ftr["bg_color"]
                    if ftr.get("text_color", "None") != "None":
                        fg_result = ftr["text_color"]
        
        # Default text color behavior depends on theme, but model returns specific colors
        # If no match and not filtered out, we want default colors.
        # Returning None lets the view decide based on palette/stylesheet.
        
        if not matched_any:
            if role == Qt.ForegroundRole:
                # If dark mode, we might want to return None to let QSS handle it,
                # or return specific gray.
                # Returning a specific gray works for both usually.
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
    
    def clear(self):
        self.beginResetModel()
        self.all_lines = []
        self.visible_indices = []
        self.endResetModel()
        
    def zoom(self, delta):
        size = self.font.pointSize() + delta
        if size < 6: size = 6
        if size > 30: size = 30
        self.font.setPointSize(size)
        self.layoutChanged.emit()
        
    def append_chunk(self, lines):
        start_real_idx = len(self.all_lines)
        self.all_lines.extend(lines)
        
        # Calculate visibility
        new_indices = []
        has_active_filters = any(f.get("active", True) for f in self.filters)
        
        for i, line in enumerate(lines):
            real_idx = start_real_idx + i
            if not has_active_filters:
                new_indices.append(real_idx)
                continue
                
            matched = False
            is_excluded = False
            
            # Incremental Counting and Visibility
            for ftr in self.filters:
                if not ftr.get("active", True):
                    continue
                is_match = False
                if ftr["regex"]:
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
                
                if is_match:
                    ftr['total_matches'] = ftr.get('total_matches', 0) + 1
                    # Priority logic: Exclude beats Include if both match a line
                    if ftr["exclude"]:
                        matched = False
                        is_excluded = True
                    else:
                        # Only set matched=True if we aren't already excluded by a higher index filter
                        # Wait, the list is processed in order. To maintain "last wins" (highest index wins):
                        # We just keep updating 'matched' and 'is_excluded'.
                        # This works because ftr is the ACTUAL dict and index is preserved.
                        matched = True
                        is_excluded = False
            
            if not is_excluded:
                if matched or not self.show_only_filtered:
                    new_indices.append(real_idx)

        if new_indices:
            first_row_idx = len(self.visible_indices)
            self.beginInsertRows(QModelIndex(), first_row_idx, first_row_idx + len(new_indices) - 1)
            self.visible_indices.extend(new_indices)
            self.endInsertRows()
            return True
        return False

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

    def find_next(self):
        self.parent().find_in_files(self.input_field.text(), forward=True, 
                                   case=self.chk_case.isChecked(), regex=self.chk_regex.isChecked())

    def find_prev(self):
        self.parent().find_in_files(self.input_field.text(), forward=False, 
                                   case=self.chk_case.isChecked(), regex=self.chk_regex.isChecked())
    
    def set_status(self, text):
        self.status_lbl.setText(text)


class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis (High Performance)")
        self.resize(1100, 800)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Permanent Status Widgets
        self.lbl_stats = QLabel("Lines: 0 | Visible: 0")
        self.status_bar.addPermanentWidget(self.lbl_stats)
        
        self.create_menu()
        self.init_ui()
        
        self.filter_thread = None
        self.adb_thread = None
        self.is_monitoring = False
        self.is_paused = False
        self.pending_chunks = []
        
        self.find_dialog = None
        
        # Apply dark mode by default or based on prefs? 
        # Let's start with Light (System) default.

    def create_menu(self):
        menubar = self.menuBar()
        style = self.style()

        # File menu
        file_menu = menubar.addMenu("File")
        open_action = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        load_filters_action = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "Load Filters", self)
        load_filters_action.setShortcut("Ctrl+L")
        load_filters_action.triggered.connect(self.load_filters)
        file_menu.addAction(load_filters_action)
        
        save_filters_action = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save Filters", self)
        save_filters_action.setShortcut("Ctrl+S")
        save_filters_action.triggered.connect(self.save_filters)
        file_menu.addAction(save_filters_action)
        
        file_menu.addSeparator()
        clear_logs_action = QAction(style.standardIcon(QStyle.SP_DialogResetButton), "Clear Logs", self)
        clear_logs_action.setShortcut("Ctrl+K")
        clear_logs_action.triggered.connect(self.clear_logs)
        file_menu.addAction(clear_logs_action)
        
        file_menu.addSeparator()
        exit_action = QAction(style.standardIcon(QStyle.SP_DialogCloseButton), "Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        add_filter_action = QAction(style.standardIcon(QStyle.SP_FileDialogNewFolder), "Add Filter", self)
        add_filter_action.setShortcut("Ctrl+Shift+F") 
        add_filter_action.triggered.connect(self.add_filter_dialog)
        edit_menu.addAction(add_filter_action)
        
        find_action = QAction(style.standardIcon(QStyle.SP_FileDialogContentsView), "Find", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_dialog)
        edit_menu.addAction(find_action)

        edit_menu.addSeparator()
        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_selection)
        edit_menu.addAction(copy_action)
        self.copy_action = copy_action

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
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.log_model.zoom(1))
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.log_model.zoom(-1))
        view_menu.addAction(zoom_out_action)
        
        # Theme Submenu
        theme_menu = view_menu.addMenu("Theme")
        self.light_theme_action = QAction("Light (System)", self, checkable=True)
        self.dark_theme_action = QAction("Dark", self, checkable=True)
        self.light_theme_action.setChecked(True)
        self.light_theme_action.triggered.connect(lambda: self.set_theme(light=True))
        self.dark_theme_action.triggered.connect(lambda: self.set_theme(light=False))
        theme_menu.addAction(self.light_theme_action)
        theme_menu.addAction(self.dark_theme_action)

        # Monitor Menu
        monitor_menu = menubar.addMenu("Monitor")
        self.adb_monitor_action = QAction(style.standardIcon(QStyle.SP_ComputerIcon), "Start ADB Logcat", self)
        self.adb_monitor_action.triggered.connect(self.toggle_adb_monitoring)
        monitor_menu.addAction(self.adb_monitor_action)
        
        self.pause_action = QAction(style.standardIcon(QStyle.SP_MediaPause), "Pause Monitoring", self, checkable=True)
        self.pause_action.setShortcut("Space")
        self.pause_action.triggered.connect(self.toggle_pause)
        self.pause_action.setEnabled(False) 
        monitor_menu.addAction(self.pause_action)

        # Tabs menu
        tabs_menu = menubar.addMenu("Tabs")
        add_tab_action = QAction(style.standardIcon(QStyle.SP_FileDialogNewFolder), "Add Tab", self)
        add_tab_action.setShortcut("Ctrl+T")
        add_tab_action.triggered.connect(self.add_filter_tab)
        tabs_menu.addAction(add_tab_action)
        
        del_tab_action = QAction(style.standardIcon(QStyle.SP_DialogDiscardButton), "Delete Tab", self)
        del_tab_action.setShortcut("Ctrl+D")
        del_tab_action.triggered.connect(self.delete_filter_tab)
        tabs_menu.addAction(del_tab_action)
        
        rename_tab_action = QAction("Rename Tab", self)
        rename_tab_action.setShortcut("Ctrl+R")
        rename_tab_action.triggered.connect(self.rename_filter_tab)
        tabs_menu.addAction(rename_tab_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        shortcuts_action = QAction(style.standardIcon(QStyle.SP_MessageBoxQuestion), "Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        about_action = QAction(style.standardIcon(QStyle.SP_MessageBoxInformation), "About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def init_ui(self):
        # Quick Filter Toolbar
        self.quick_filter_toolbar = QToolBar("Quick Filter")
        self.addToolBar(Qt.TopToolBarArea, self.quick_filter_toolbar)
        
        self.quick_input = QLineEdit()
        self.quick_input.setPlaceholderText("Quick Filter (Enter to add)...")
        self.quick_input.returnPressed.connect(self.add_quick_filter)
        self.quick_input.setFixedWidth(200)
        
        self.quick_filter_toolbar.addWidget(QLabel("  Quick Add: "))
        self.quick_filter_toolbar.addWidget(self.quick_input)
        
        self.quick_case = QCheckBox("Case")
        self.quick_regex = QCheckBox("Regex")
        self.quick_exclude = QCheckBox("Excl")
        
        self.quick_filter_toolbar.addWidget(self.quick_case)
        self.quick_filter_toolbar.addWidget(self.quick_regex)
        self.quick_filter_toolbar.addWidget(self.quick_exclude)

        self.quick_filter_toolbar.addSeparator()
        # Add Monitor Actions to Toolbar
        self.quick_filter_toolbar.addAction(self.adb_monitor_action)
        self.quick_filter_toolbar.addAction(self.pause_action)
        
        self.btn_clear = QPushButton()
        self.btn_clear.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.btn_clear.setToolTip("Clear Logs (Ctrl+K)")
        self.btn_clear.clicked.connect(self.clear_logs)
        self.quick_filter_toolbar.addWidget(self.btn_clear)
        
        # Main Layout
        # Main Layout - Changed to QTreeView for horizontal scroll support
        self.log_view = QTreeView()
        self.log_view.setUniformRowHeights(True) 
        self.log_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.log_view.setHeaderHidden(True)
        self.log_view.setRootIsDecorated(False)
        self.log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_view.header().setStretchLastSection(False)
        # Using ResizeToContents with millions of rows causes ANR because it calculates widths on every update.
        # Switch to Interactive with a large default width for performance.
        self.log_view.header().setSectionResizeMode(QHeaderView.Interactive)
        self.log_view.header().setDefaultSectionSize(3000) 
        
        self.log_model = LogModel()
        self.log_view.setModel(self.log_model)

        # Add selection context menu
        self.log_view.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.log_view.addAction(self.copy_action)

        self.filter_tabs = QTabWidget()
        self.filter_tabs.setTabBarAutoHide(False)
        self.filter_tabs.tabBarDoubleClicked.connect(self.rename_filter_tab_by_index) 
        
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

    def set_theme(self, light=True):
        if light:
            self.light_theme_action.setChecked(True)
            self.dark_theme_action.setChecked(False)
            QApplication.instance().setStyleSheet("")
        else:
            self.light_theme_action.setChecked(False)
            self.dark_theme_action.setChecked(True)
            QApplication.instance().setStyleSheet(DARK_STYLESHEET)

    def add_quick_filter(self):
        text = self.quick_input.text().strip()
        if not text: return
        
        filter_data = {
            "text": text,
            "case_sensitive": self.quick_case.isChecked(),
            "regex": self.quick_regex.isChecked(),
            "exclude": self.quick_exclude.isChecked(),
            "bg_color": "None",
            "text_color": "None",
            "active": True
        }
        
        filter_list, filters = self.current_filter_list()
        
        item = QListWidgetItem()
        self.apply_filter_colors_to_list_item(item, filter_data)
        filter_list.addItem(item)
        filters.append(filter_data)

        widget = FilterItemWidget(filter_data)
        widget.filter_toggled.connect(self._on_filter_toggled)
        filter_list.setItemWidget(item, widget)
        
        self.apply_filters()
        self.quick_input.clear()

    def update_stats(self):
        total = len(self.log_model.all_lines)
        visible = len(self.log_model.visible_indices)
        self.lbl_stats.setText(f"Lines: {total} | Visible: {visible}")

    def show_find_dialog(self):
        if not self.find_dialog:
            self.find_dialog = FindDialog(self)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()

    def find_in_files(self, text, forward=True, case=False, regex=False):
        if not text:
            return
            
        model = self.log_model
        start_idx = self.log_view.currentIndex().row()
        if start_idx < 0: start_idx = 0
        
        # Avoid infinite loop if nothing found
        visited_count = 0
        total = model.rowCount()
        if total == 0:
            return

        idx = start_idx
        
        while visited_count < total:
            if forward:
                idx += 1
                if idx >= total: idx = 0
            else:
                idx -= 1
                if idx < 0: idx = total - 1
            
            # Use raw string (model.all_lines via visible_indices)
            real_idx = model.visible_indices[idx]
            line = model.all_lines[real_idx]
            
            match = False
            if regex:
                flags = 0 if case else re.IGNORECASE
                try:
                    if re.search(text, line, flags):
                        match = True
                except: pass
            else:
                if case:
                    if text in line: match = True
                else:
                    if text.lower() in line.lower(): match = True
            
            if match:
                # Select it
                index_obj = model.index(idx, 0)
                self.log_view.setCurrentIndex(index_obj)
                self.log_view.scrollTo(index_obj, QAbstractItemView.PositionAtCenter)
                self.find_dialog.set_status("")
                return
            
            visited_count += 1
            
        self.find_dialog.set_status("Not found")

    def copy_selection(self):
        selection_model = self.log_view.selectionModel()
        selected_indexes = selection_model.selectedRows()
        
        if not selected_indexes:
            return

        # Sort indexes to copy in correct order
        selected_indexes.sort(key=lambda x: x.row())
        
        lines = []
        for idx in selected_indexes:
            # Data role gives exactly what's displayed (respecting 'show line numbers')
            text = self.log_model.data(idx, Qt.DisplayRole)
            if text:
                lines.append(text)
        
        if lines:
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(lines))
            self.status_bar.showMessage(f"Copied {len(lines)} lines to clipboard", 3000)


    def toggle_adb_monitoring(self):
        style = self.style()
        if not self.is_monitoring:
            self.log_model.clear()
            self.pending_chunks = []
            
            active_filters = []
            for filters in self.filters:
                for f in filters:
                    if f.get("active", True):
                        active_filters.append(f)
            self.log_model.filters = active_filters
            
            self.adb_thread = AdbWorker()
            self.adb_thread.chunk_ready.connect(self.on_adb_chunk)
            self.adb_thread.error_occurred.connect(self.on_adb_error)
            self.adb_thread.start()
            
            self.is_monitoring = True
            self.is_paused = False
            self.adb_monitor_action.setText("Stop ADB Logcat")
            self.adb_monitor_action.setIcon(style.standardIcon(QStyle.SP_MediaStop))
            self.pause_action.setEnabled(True)
            self.pause_action.setChecked(False)
            self.status_bar.showMessage("Monitoring ADB Logcat...")
        else:
            if self.adb_thread:
                self.adb_thread.stop()
                self.adb_thread.wait()
                self.adb_thread = None
            
            self.is_monitoring = False
            self.is_paused = False
            self.adb_monitor_action.setText("Start ADB Logcat")
            self.adb_monitor_action.setIcon(style.standardIcon(QStyle.SP_ComputerIcon))
            self.pause_action.setEnabled(False)
            self.status_bar.showMessage(f"Monitoring stopped.")
            self.update_stats()
            
            # Process leftovers
            while self.pending_chunks:
                chunk = self.pending_chunks.pop(0)
                self.log_model.append_chunk(chunk)
    
    def clear_logs(self):
        self.log_model.clear()
        self.pending_chunks = []
        self.update_stats()
        # Reset matching counts for UI consistency
        for tab in self.filters:
            for f in tab:
                f['total_matches'] = 0
        self.update_filter_counts_ui()
        self.status_bar.showMessage("Logs cleared.", 3000)
            
    def toggle_pause(self, checked):
        self.is_paused = checked
        if self.is_paused:
            self.status_bar.showMessage("Monitoring Paused (Buffering...)")
        else:
            self.status_bar.showMessage("Resuming...")
            # Flush buffer
            while self.pending_chunks:
                chunk = self.pending_chunks.pop(0)
                self.on_adb_chunk(chunk) # Process them

    def on_adb_chunk(self, lines):
        if self.is_paused:
            self.pending_chunks.append(lines)
            return

        was_at_bottom = False
        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar.value() == scrollbar.maximum():
            was_at_bottom = True
            
        data_added = self.log_model.append_chunk(lines)
        if data_added:
            self.update_stats()
            self.update_filter_counts_ui() # Real-time update
        
        if data_added and was_at_bottom:
            self.log_view.scrollToBottom()

    def on_adb_error(self, message):
        self.toggle_adb_monitoring() 
        QMessageBox.critical(self, "ADB Error", message)

    def rename_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        self.rename_filter_tab_by_index(idx)

    def rename_filter_tab_by_index(self, idx):
        if idx >= 0:
            current_name = self.filter_tabs.tabText(idx)
            new_name, ok = QInputDialog.getText(self, "Rename Tab", "Tab name:", text=current_name)
            if ok and new_name.strip():
                self.filter_tabs.setTabText(idx, new_name.strip())

    def show_about_dialog(self):
        QMessageBox.about(self, "About LogAnalysis GUI",
                          "<b>LogAnalysis GUI</b><br>"
                          "Version 0.0.6 (Polished UI)<br>"
                          "Developed by: Drew Yu<br>"
                          "Highlights: Dark Mode, Quick Filter, Icons.")

    def show_shortcuts(self):
        QMessageBox.information(self, "Shortcuts",
                                "<b>Keyboard Shortcuts</b><br><br>"
                                "<b>Ctrl+O</b>: Open File<br>"
                                "<b>Ctrl+C</b>: Copy Selection<br>"
                                "<b>Ctrl+F</b>: Find<br>"
                                "<b>Ctrl+Shift+F</b>: Add Filter<br>"
                                "<b>Ctrl+T</b>: Add Tab<br>"
                                "<b>Ctrl+D</b>: Delete Tab<br>"
                                "<b>Ctrl+(+/-)</b>: Zoom In/Out<br>"
                                "<b>Space</b>: Pause Monitoring<br>"
                                )

    # --- Standard filter/tab methods (Unchanged except renames) ---
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
        self.log_model.layoutChanged.emit()

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
        if self.is_monitoring:
            self.toggle_adb_monitoring()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Log File", "", "Log/Text Files (*.log *.txt);;All Files (*)"
        )
        if file_path:
            self.status_bar.showMessage("Loading file...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                self.log_model.set_lines(lines)
                self.status_bar.showMessage(f"Loaded: {file_path}")
                self.update_stats()
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
        # Only save selected tab
        idx = self.filter_tabs.currentIndex()
        if idx < 0: return
        
        tab_name = self.filter_tabs.tabText(idx)
        default_name = f"{tab_name}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Current Tab Filters", default_name, 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                filters_to_save = self.filters[idx]
                # Save as a dictionary containing the name and filters
                data = {
                    "name": tab_name,
                    "filters": filters_to_save
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                self.status_bar.showMessage(f"Filters from '{tab_name}' saved to {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error saving filters: {str(e)}")

    def load_filters(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Filters to Current Tab", "", 
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                
                loaded_set = []
                tab_name = None
                
                # Handle different JSON structures
                if isinstance(loaded, dict):
                    # New single-tab structure: {"name": "...", "filters": [...]}
                    loaded_set = loaded.get('filters', [])
                    tab_name = loaded.get('name')
                elif isinstance(loaded, list):
                    if len(loaded) > 0 and isinstance(loaded[0], dict) and 'filters' in loaded[0]:
                        # Legacy multi-tab structure (take the first one)
                        # Or if we saved a list with one dict previously
                        loaded_set = loaded[0]['filters']
                        tab_name = loaded[0].get('name')
                    else:
                        # Even older simple list format
                        loaded_set = loaded
                
                if not loaded_set and not isinstance(loaded_set, list):
                    self.status_bar.showMessage("Invalid filter file format.")
                    return

                filter_list, filters = self.current_filter_list()
                filter_list.clear()
                filters.clear()
                
                if tab_name:
                    idx = self.filter_tabs.currentIndex()
                    self.filter_tabs.setTabText(idx, tab_name)
                
                for filter_data in loaded_set:
                    item = QListWidgetItem()
                    self.apply_filter_colors_to_list_item(item, filter_data)
                    filter_list.addItem(item)
                    filters.append(filter_data)
                    
                    widget = FilterItemWidget(filter_data)
                    widget.filter_toggled.connect(self._on_filter_toggled)
                    filter_list.setItemWidget(item, widget)
                
                self.apply_filters()
                self.status_bar.showMessage(f"Filters loaded into current tab from {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error loading filters: {str(e)}")

    def apply_filters(self):
        # We need to pass ALL filters to the worker, but we also need to know which ones are active.
        # To map results back, we should pass the structure or a flattened list with IDs.
        # The 'self.filters' is a list of lists (tabs).
        
        # Flattener
        all_filters_flat = []
        # We also need a map to find them back.
        # map_back[flat_index] = (tab_index, filter_index)
        self.filter_map_back = {}
        
        flat_idx = 0
        all_filters_to_count = []
        self.filter_map_back = {}
        
        for tab_idx, filters in enumerate(self.filters):
            for filter_idx, f in enumerate(filters):
                # We pass EVERYTHING to the worker so we can scan once and update all counts
                # Worker will distinguish between "active for visibility" and "just for counting"
                f_data = f.copy()
                self.filter_map_back[flat_idx] = (tab_idx, filter_idx)
                all_filters_to_count.append(f_data)
                flat_idx += 1
        
        # LogModel needs the ACTUAL dictionaries to update counts in real-time during ADB stream
        flattened_originals = []
        for filters in self.filters:
            flattened_originals.extend(filters)
        self.log_model.filters = flattened_originals
        
        if not self.log_model.all_lines:
            # Still update UI to clear counts
            for tab in self.filters:
                for f in tab:
                    f['total_matches'] = 0
            self.on_filtering_finished([], 0, [0]*len(all_filters_to_count))
            return
        
        if self.filter_thread and self.filter_thread.isRunning():
            self.filter_thread.stop()
            self.filter_thread.wait()
        
        # Smart selection tracking: remember where we are in source
        self.target_source_idx = -1
        current_idx = self.log_view.currentIndex()
        if current_idx.isValid():
            row = current_idx.row()
            if row < len(self.log_model.visible_indices):
                self.target_source_idx = self.log_model.visible_indices[row]

        if not self.is_monitoring:
            self.status_bar.showMessage("Refiltering...")
            
        self.filter_thread = FilterWorker(
            self.log_model.all_lines, 
            all_filters_to_count, 
            self.log_model.show_only_filtered
        )
        self.filter_thread.finished_filtering.connect(self.on_filtering_finished)
        self.filter_thread.start()

    def on_filtering_finished(self, visible_indices, match_count, filter_counts=None):
        self.log_model.update_visible_indices(visible_indices)
        
        # Restore or Shift Selection
        if hasattr(self, 'target_source_idx') and self.target_source_idx != -1 and visible_indices:
            # Find the best row to select in the new visible list
            # visible_indices is sorted, so we can use bisect
            pos = bisect.bisect_left(visible_indices, self.target_source_idx)
            
            # Determine which available index is closer to our target
            new_row = -1
            if pos < len(visible_indices):
                # pos is the first index >= target. 
                # Check if it's the exact match or if the previous one is closer
                if pos > 0:
                    dist_curr = visible_indices[pos] - self.target_source_idx
                    dist_prev = self.target_source_idx - visible_indices[pos-1]
                    new_row = pos if dist_curr <= dist_prev else pos - 1
                else:
                    new_row = pos
            else:
                # Target is beyond the end, take the last available
                new_row = len(visible_indices) - 1
            
            if new_row != -1:
                model_idx = self.log_model.index(new_row, 0)
                self.log_view.setCurrentIndex(model_idx)
                # If we toggled filters, we want to make sure the user sees where they are
                self.log_view.scrollTo(model_idx, QAbstractItemView.PositionAtCenter)

        self.update_stats()
        
        if filter_counts and hasattr(self, 'filter_map_back'):
            # Reset ALL counts for ALL tabs first to ensure consistency
            for tab in self.filters:
                for f in tab:
                    f['total_matches'] = 0
                    
            # Update the source data with new counts from worker
            for flat_idx, count in enumerate(filter_counts):
                if flat_idx in self.filter_map_back:
                    tab_idx, filter_idx = self.filter_map_back[flat_idx]
                    if tab_idx < len(self.filters) and filter_idx < len(self.filters[tab_idx]):
                        # If monitoring, we should perhaps be careful about overwriting?
                        # But worker just finished a full scan.
                        self.filters[tab_idx][filter_idx]['total_matches'] = count
            
            self.update_filter_counts_ui()
            
    def update_filter_counts_ui(self):
        # Update the UI for the CURRENT tab
        current_tab_idx = self.filter_tabs.currentIndex()
        if current_tab_idx >= 0 and current_tab_idx < len(self.filter_tab_lists):
             current_list = self.filter_tab_lists[current_tab_idx]
             current_filters = self.filters[current_tab_idx]
             
             for i in range(current_list.count()):
                 item = current_list.item(i)
                 widget = current_list.itemWidget(item)
                 if widget and i < len(current_filters):
                     # Copy current count to widget's data (redundant if same ref, but safe)
                     widget.filter_data['total_matches'] = current_filters[i].get('total_matches', 0)
                     widget.update_display()
        
        if self.is_monitoring:
             self.status_bar.showMessage(f"Monitoring...")
        else:
             self.status_bar.showMessage(f"Refiltered complete.")

# --- Child Classes ---
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
        if self.filter_data["exclude"]: text = f"NOT: {text}"
        if self.filter_data["regex"]: text = f"REGEX: {text}"
        if self.filter_data["case_sensitive"]: text = f"CASE: {text}"
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
