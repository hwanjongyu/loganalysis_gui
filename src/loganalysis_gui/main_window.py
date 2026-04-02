import re
import json
import bisect
from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QLineEdit, QCheckBox, 
    QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, 
    QListWidgetItem, QTabWidget, QMessageBox, QInputDialog, QTreeView,
    QAbstractItemView, QToolBar, QStyle, QGroupBox, QFormLayout,
    QHeaderView, QTabBar, QApplication
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from .constants import COLOR_MAP, TEXT_COLOR_MAP, DARK_STYLESHEET, MAX_MONITOR_LINES
from .workers import AdbWorker, FilterWorker
from .models import LogModel
from .dialogs import FindDialog, FilterDialog
from .widgets import FilterItemWidget

class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis (High Performance)")
        self.resize(1100, 800)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.tab_modified = []
        self.tab_file_paths = []
        
        # Permanent Status Widgets
        self.lbl_stats = QLabel("Lines: 0 | Visible: 0")
        self.status_bar.addPermanentWidget(self.lbl_stats)
        
        self.create_menu()
        self.init_ui()
        
        self.filter_thread = None
        self.adb_thread = None
        self.is_monitoring = False
        self.is_paused = False
        self.is_refiltering = False
        self.pending_chunks = []
        self.filter_request_id = 0
        self.filter_map_back = {}
        self.target_source_idx = -1
        self.scroll_to_bottom_after_refilter = False
        
        self.find_dialog = None

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
        
        save_filters_as_action = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save Filters As...", self)
        save_filters_as_action.setShortcut("Ctrl+Shift+S")
        save_filters_as_action.triggered.connect(self.save_filters_as)
        file_menu.addAction(save_filters_as_action)
        
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
        self.log_view = QTreeView()
        self.log_view.setUniformRowHeights(True) 
        self.log_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.log_view.setHeaderHidden(True)
        self.log_view.setRootIsDecorated(False)
        self.log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.log_view.header().setStretchLastSection(False)
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
        self.tab_enabled = []
        self.tab_checkboxes = []
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

    def _next_filter_request_id(self):
        self.filter_request_id += 1
        return self.filter_request_id

    def _invalidate_filter_results(self):
        self.filter_request_id += 1
        self.filter_map_back = {}
        self.target_source_idx = -1
        self.is_refiltering = False

    def _stop_filter_worker(self):
        thread = self.filter_thread
        self.filter_thread = None
        if thread:
            thread.stop()
            if thread.isRunning():
                thread.wait()

    def _stop_adb_worker(self):
        thread = self.adb_thread
        self.adb_thread = None
        if thread:
            thread.stop()
            if thread.isRunning():
                thread.wait()

    def _effective_model_filters(self):
        effective_filters = []
        for tab_idx, filters in enumerate(self.filters):
            if not self.tab_enabled[tab_idx]:
                continue
            effective_filters.extend(filters)
        return effective_filters

    def _regex_error(self, pattern, case_sensitive):
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            re.compile(pattern, flags)
        except re.error as error:
            return str(error)
        return None

    def _normalize_filter_data(self, filter_data):
        normalized = {
            "text": filter_data.get("text", ""),
            "case_sensitive": filter_data.get("case_sensitive", False),
            "regex": filter_data.get("regex", False),
            "exclude": filter_data.get("exclude", False),
            "bg_color": filter_data.get("bg_color", "None"),
            "text_color": filter_data.get("text_color", "None"),
            "active": filter_data.get("active", True),
        }
        if "total_matches" in filter_data:
            normalized["total_matches"] = filter_data["total_matches"]
        return normalized

    def _validate_loaded_filters(self, loaded_filters):
        normalized_filters = []
        invalid_filters = []

        for raw_filter in loaded_filters:
            if not isinstance(raw_filter, dict):
                return None, ["Each filter entry must be an object."]

            filter_data = self._normalize_filter_data(raw_filter)
            if filter_data["regex"]:
                regex_error = self._regex_error(filter_data["text"], filter_data["case_sensitive"])
                if regex_error:
                    invalid_filters.append(f"\"{filter_data['text']}\": {regex_error}")

            normalized_filters.append(filter_data)

        return normalized_filters, invalid_filters

    def _refresh_tab_checkboxes(self):
        tab_bar = self.filter_tabs.tabBar()
        self.tab_checkboxes = []
        for index, enabled in enumerate(self.tab_enabled):
            checkbox = QCheckBox()
            checkbox.setProperty("tab_index", index)
            checkbox.setChecked(enabled)
            checkbox.setToolTip("Enable/Disable this filter set")
            checkbox.stateChanged.connect(self._on_tab_checkbox_changed)
            tab_bar.setTabButton(index, QTabBar.LeftSide, checkbox)
            self.tab_checkboxes.append(checkbox)

    def _on_tab_checkbox_changed(self, state):
        checkbox = self.sender()
        if not isinstance(checkbox, QCheckBox):
            return

        index = checkbox.property("tab_index")
        if not isinstance(index, int):
            return

        self._on_tab_toggled(index, state)

    def _apply_chunk_to_model(self, lines):
        was_at_bottom = False
        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar.value() == scrollbar.maximum():
            was_at_bottom = True

        data_added = self.log_model.append_chunk(lines)
        if data_added:
            self.update_stats()
            self.update_filter_counts_ui()

        trimmed = self._trim_live_log_buffer_if_needed(was_at_bottom)
        if data_added and was_at_bottom and not trimmed:
            self.log_view.scrollToBottom()

    def _flush_pending_chunks(self):
        if self.is_paused or self.is_refiltering or not self.pending_chunks:
            return

        chunks = self.pending_chunks
        self.pending_chunks = []
        for chunk in chunks:
            self._apply_chunk_to_model(chunk)

    def _trim_live_log_buffer_if_needed(self, preserve_bottom=False):
        if not self.is_monitoring:
            return False

        excess_lines = len(self.log_model.all_lines) - MAX_MONITOR_LINES
        if excess_lines <= 0:
            return False

        self._invalidate_filter_results()
        self.log_model.set_lines(self.log_model.all_lines[excess_lines:])
        if preserve_bottom:
            self.scroll_to_bottom_after_refilter = True

        self.status_bar.showMessage(
            f"Monitoring buffer trimmed to the most recent {MAX_MONITOR_LINES:,} lines.",
            5000,
        )
        self.apply_filters()
        return True

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

        if self.quick_regex.isChecked():
            regex_error = self._regex_error(text, self.quick_case.isChecked())
            if regex_error:
                message = f"Quick filter regex is invalid:\n{regex_error}"
                self.status_bar.showMessage(f"Invalid regex: {regex_error}", 5000)
                QMessageBox.warning(self, "Invalid Regex", message)
                return
        
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
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)
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

        if regex:
            regex_error = self._regex_error(text, case)
            if regex_error:
                message = f"Invalid regex: {regex_error}"
                if self.find_dialog:
                    self.find_dialog.set_status(message)
                self.status_bar.showMessage(message, 5000)
                return
            
        model = self.log_model
        visited_count = 0
        total = model.rowCount()
        if total == 0:
            return

        current_row = self.log_view.currentIndex().row()
        if current_row < 0:
            idx = -1 if forward else 0
        else:
            idx = current_row

        while visited_count < total:
            if forward:
                idx = (idx + 1) % total
            else:
                idx = (idx - 1) % total
            
            real_idx = model.visible_indices[idx]
            line = model.all_lines[real_idx]
            
            match = False
            if regex:
                flags = 0 if case else re.IGNORECASE
                if re.search(text, line, flags):
                    match = True
            else:
                if case:
                    if text in line: match = True
                else:
                    if text.lower() in line.lower(): match = True
            
            if match:
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

        selected_indexes.sort(key=lambda x: x.row())
        
        lines = []
        for idx in selected_indexes:
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
            self._stop_filter_worker()
            self._invalidate_filter_results()
            self.log_model.clear()
            self.pending_chunks = []
            self.log_model.filters = self._effective_model_filters()
            
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
            self._stop_adb_worker()
            self.is_monitoring = False
            self.is_paused = False
            self.is_refiltering = False
            self.adb_monitor_action.setText("Start ADB Logcat")
            self.adb_monitor_action.setIcon(style.standardIcon(QStyle.SP_ComputerIcon))
            self.pause_action.setEnabled(False)
            self.status_bar.showMessage(f"Monitoring stopped.")
            self.update_stats()
            self._flush_pending_chunks()
    
    def clear_logs(self):
        self._stop_filter_worker()
        self._invalidate_filter_results()
        self.log_model.clear()
        self.pending_chunks = []
        self.update_stats()
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
            self._flush_pending_chunks()

    def on_adb_chunk(self, lines):
        if self.is_paused or self.is_refiltering:
            self.pending_chunks.append(lines)
            return

        self._apply_chunk_to_model(lines)

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
                self.set_tab_modified(idx, True)

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
                                "<b>Ctrl+S</b>: Save Filters<br>"
                                "<b>Ctrl+Shift+S</b>: Save Filters As<br>"
                                "<b>Ctrl+C</b>: Copy Selection<br>"
                                "<b>Ctrl+F</b>: Find<br>"
                                "<b>Ctrl+Shift+F</b>: Add Filter<br>"
                                "<b>Ctrl+T</b>: Add Tab<br>"
                                "<b>Ctrl+D</b>: Delete Tab<br>"
                                "<b>Ctrl+(+/-)</b>: Zoom In/Out<br>"
                                "<b>Space</b>: Pause Monitoring<br>"
                                )

    def add_filter_tab(self):
        filter_list = QListWidget()
        filter_list.setDragDropMode(QListWidget.InternalMove)
        filter_list.itemDoubleClicked.connect(self.edit_filter_dialog)
        filter_list.installEventFilter(self)
        filter_list.model().rowsMoved.connect(lambda: self.sync_filter_order())
        self.filter_tab_lists.append(filter_list)
        self.filters.append([])
        self.tab_enabled.append(True)
        
        idx = len(self.filter_tab_lists) - 1
        self.filter_tabs.addTab(filter_list, f"Filter Set {idx+1}")
        self._refresh_tab_checkboxes()
        
        self.filter_tabs.setCurrentIndex(idx)
        self.tab_modified.append(False)
        self.tab_file_paths.append(None)

    def set_tab_modified(self, index, modified: bool):
        if 0 <= index < len(self.tab_modified):
            self.tab_modified[index] = modified
            current_text = self.filter_tabs.tabText(index)
            if modified:
                if not current_text.startswith("*"):
                    self.filter_tabs.setTabText(index, "*" + current_text)
            else:
                if current_text.startswith("*"):
                    self.filter_tabs.setTabText(index, current_text[1:])

    def _on_tab_toggled(self, index, state):
        if not 0 <= index < len(self.tab_enabled):
            return

        self.tab_enabled[index] = (state == Qt.Checked)
        self.set_tab_modified(index, True)
        self.apply_filters()

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
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def delete_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if len(self.filter_tab_lists) > 1 and idx >= 0:
            self.filter_tabs.removeTab(idx)
            del self.filter_tab_lists[idx]
            del self.filters[idx]
            del self.tab_enabled[idx]
            del self.tab_modified[idx]
            del self.tab_file_paths[idx]
            self._refresh_tab_checkboxes()
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
            self._stop_filter_worker()
            self._invalidate_filter_results()
            self.pending_chunks = []
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
            self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def _on_filter_toggled(self, filter_data, checked):
        self.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

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
            self.set_tab_modified(self.filter_tabs.currentIndex(), True)

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
                self.set_tab_modified(current_idx, True)
                return True
        return super().eventFilter(source, event)

    def save_filters(self):
        idx = self.filter_tabs.currentIndex()
        if idx < 0: return
        
        if self.tab_file_paths[idx]:
            self._do_save(idx, self.tab_file_paths[idx])
        else:
            self.save_filters_as()

    def save_filters_as(self):
        idx = self.filter_tabs.currentIndex()
        if idx < 0: return
        
        tab_name = self.filter_tabs.tabText(idx)
        if tab_name.startswith("*"): tab_name = tab_name[1:]
        default_name = f"{tab_name}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Current Tab Filters As", default_name, 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._do_save(idx, file_path)

    def _do_save(self, idx, file_path):
        try:
            tab_name = self.filter_tabs.tabText(idx)
            if tab_name.startswith("*"): tab_name = tab_name[1:]
            
            filters_to_save = self.filters[idx]
            data = {
                "name": tab_name,
                "enabled": self.tab_enabled[idx],
                "filters": filters_to_save
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.tab_file_paths[idx] = file_path
            self.set_tab_modified(idx, False)
            self.status_bar.showMessage(f"Filters from '{tab_name}' saved to {file_path}", 3000)
        except Exception as e:
            self.status_bar.showMessage(f"Error saving filters: {str(e)}", 5000)

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
                tab_enabled = True
                
                if isinstance(loaded, dict):
                    loaded_set = loaded.get('filters', [])
                    tab_name = loaded.get('name')
                    tab_enabled = loaded.get('enabled', True)
                elif isinstance(loaded, list):
                    if len(loaded) > 0 and isinstance(loaded[0], dict) and 'filters' in loaded[0]:
                        loaded_set = loaded[0]['filters']
                        tab_name = loaded[0].get('name')
                    else:
                        loaded_set = loaded
                
                if not loaded_set and not isinstance(loaded_set, list):
                    self.status_bar.showMessage("Invalid filter file format.")
                    return

                normalized_filters, invalid_filters = self._validate_loaded_filters(loaded_set)
                if normalized_filters is None:
                    self.status_bar.showMessage("Invalid filter file format.")
                    QMessageBox.warning(self, "Invalid Filter File", invalid_filters[0])
                    return
                if invalid_filters:
                    details = "\n".join(f"- {item}" for item in invalid_filters[:5])
                    if len(invalid_filters) > 5:
                        details += "\n- ..."
                    QMessageBox.warning(
                        self,
                        "Invalid Filter File",
                        f"Cannot load filters with invalid regular expressions:\n\n{details}",
                    )
                    self.status_bar.showMessage("Error loading filters: invalid regex in file.", 5000)
                    return

                filter_list, filters = self.current_filter_list()
                filter_list.clear()
                filters.clear()
                
                idx = self.filter_tabs.currentIndex()
                if tab_name:
                    self.filter_tabs.setTabText(idx, tab_name)
                
                self.tab_enabled[idx] = tab_enabled
                cb = self.tab_checkboxes[idx] if idx < len(self.tab_checkboxes) else None
                if isinstance(cb, QCheckBox):
                    cb.blockSignals(True)
                    cb.setChecked(tab_enabled)
                    cb.blockSignals(False)
                
                for filter_data in normalized_filters:
                    item = QListWidgetItem()
                    self.apply_filter_colors_to_list_item(item, filter_data)
                    filter_list.addItem(item)
                    filters.append(filter_data)
                    
                    widget = FilterItemWidget(filter_data)
                    widget.filter_toggled.connect(self._on_filter_toggled)
                    filter_list.setItemWidget(item, widget)
                
                self.apply_filters()
                self.tab_file_paths[idx] = file_path
                self.set_tab_modified(idx, False)
                self.status_bar.showMessage(f"Filters loaded into current tab from {file_path}")
            except Exception as e:
                self.status_bar.showMessage(f"Error loading filters: {str(e)}")

    def apply_filters(self):
        self.log_model.filters = self._effective_model_filters()
        self.filter_map_back = {}
        
        flat_idx = 0
        all_filters_to_count = []
        
        for tab_idx, filters in enumerate(self.filters):
            is_enabled = self.tab_enabled[tab_idx]
            for filter_idx, f in enumerate(filters):
                f_data = f.copy()
                if not is_enabled:
                    f_data["active"] = False
                
                self.filter_map_back[flat_idx] = (tab_idx, filter_idx)
                all_filters_to_count.append(f_data)
                flat_idx += 1

        self._stop_filter_worker()
        request_id = self._next_filter_request_id()
        
        if not self.log_model.all_lines:
            for tab in self.filters:
                for f in tab:
                    f['total_matches'] = 0
            self.on_filtering_finished(request_id, [], 0, [0] * len(all_filters_to_count))
            return

        self.target_source_idx = -1
        current_idx = self.log_view.currentIndex()
        if current_idx.isValid():
            row = current_idx.row()
            if row < len(self.log_model.visible_indices):
                self.target_source_idx = self.log_model.visible_indices[row]

        self.is_refiltering = self.is_monitoring
        if not self.is_monitoring:
            self.status_bar.showMessage("Refiltering...")
            
        self.filter_thread = FilterWorker(
            self.log_model.all_lines, 
            all_filters_to_count, 
            self.log_model.show_only_filtered,
            request_id
        )
        self.filter_thread.finished_filtering.connect(self.on_filtering_finished)
        self.filter_thread.start()

    def on_filtering_finished(self, request_id, visible_indices, match_count, filter_counts=None):
        if request_id != self.filter_request_id:
            return

        if self.sender() is self.filter_thread:
            self.filter_thread = None

        self.is_refiltering = False
        self.log_model.update_visible_indices(visible_indices)
        
        if hasattr(self, 'target_source_idx') and self.target_source_idx != -1 and visible_indices:
            pos = bisect.bisect_left(visible_indices, self.target_source_idx)
            new_row = -1
            if pos < len(visible_indices):
                if pos > 0:
                    dist_curr = visible_indices[pos] - self.target_source_idx
                    dist_prev = self.target_source_idx - visible_indices[pos-1]
                    new_row = pos if dist_curr <= dist_prev else pos - 1
                else:
                    new_row = pos
            else:
                new_row = len(visible_indices) - 1
            
            if new_row != -1:
                model_idx = self.log_model.index(new_row, 0)
                self.log_view.setCurrentIndex(model_idx)
                self.log_view.scrollTo(model_idx, QAbstractItemView.PositionAtCenter)

        self.update_stats()
        
        if filter_counts is not None and hasattr(self, 'filter_map_back'):
            for tab in self.filters:
                for f in tab:
                    f['total_matches'] = 0
                    
            for flat_idx, count in enumerate(filter_counts):
                if flat_idx in self.filter_map_back:
                    tab_idx, filter_idx = self.filter_map_back[flat_idx]
                    if tab_idx < len(self.filters) and filter_idx < len(self.filters[tab_idx]):
                        self.filters[tab_idx][filter_idx]['total_matches'] = count
            
            self.update_filter_counts_ui()
        else:
            self.update_filter_counts_ui()

        self._flush_pending_chunks()
        if self.scroll_to_bottom_after_refilter and self.log_model.rowCount() > 0:
            self.log_view.scrollToBottom()
        self.scroll_to_bottom_after_refilter = False
            
    def update_filter_counts_ui(self):
        current_tab_idx = self.filter_tabs.currentIndex()
        if current_tab_idx >= 0 and current_tab_idx < len(self.filter_tab_lists):
             current_list = self.filter_tab_lists[current_tab_idx]
             current_filters = self.filters[current_tab_idx]
             
             for i in range(current_list.count()):
                  item = current_list.item(i)
                  widget = current_list.itemWidget(item)
                  if widget and i < len(current_filters):
                      widget.filter_data['total_matches'] = current_filters[i].get('total_matches', 0)
                      widget.update_display()
        
        if self.is_monitoring:
             if self.is_paused:
                  self.status_bar.showMessage("Monitoring Paused (Buffering...)")
             elif self.is_refiltering:
                  self.status_bar.showMessage("Refiltering live logs...")
             else:
                  self.status_bar.showMessage("Monitoring...")
        else:
             self.status_bar.showMessage(f"Refiltered complete.")

    def closeEvent(self, event):
        modified_tabs = []
        for i, modified in enumerate(self.tab_modified):
            if modified:
                name = self.filter_tabs.tabText(i)
                if name.startswith("*"): name = name[1:]
                modified_tabs.append(name)
        
        if modified_tabs:
            tab_list_str = "\n".join([f"- {name}" for name in modified_tabs])
            msg = f"The following filter tabs have unsaved changes:\n\n{tab_list_str}\n\nDo you want to save before exiting?"
            
            res = QMessageBox.warning(
                self, "Unsaved Changes", msg,
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if res == QMessageBox.Save:
                for i, modified in enumerate(self.tab_modified):
                    if modified:
                        self.filter_tabs.setCurrentIndex(i)
                        self.save_filters()
                        if self.tab_modified[i]:
                            event.ignore()
                            return
                self._stop_filter_worker()
                self._stop_adb_worker()
                event.accept()
            elif res == QMessageBox.Discard:
                self._stop_filter_worker()
                self._stop_adb_worker()
                event.accept()
            else:
                event.ignore()
        else:
            self._stop_filter_worker()
            self._stop_adb_worker()
            event.accept()
