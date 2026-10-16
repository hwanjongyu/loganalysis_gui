import re
import json
import bisect
import os
import shutil
import subprocess
from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog, QStatusBar,
    QVBoxLayout, QWidget, QLineEdit, QCheckBox, 
    QPushButton, QLabel, QHBoxLayout, QListWidget, QSplitter, 
    QListWidgetItem, QTabWidget, QMessageBox, QInputDialog, QTreeView,
    QAbstractItemView, QToolBar, QStyle, QGroupBox, QFormLayout, QMenu,
    QHeaderView, QTabBar, QApplication, QProgressBar, QComboBox
)
from PyQt5.QtGui import QColor, QFontMetrics
from PyQt5.QtCore import Qt

from .constants import (
    COLOR_MAP,
    TEXT_COLOR_MAP,
    DARK_STYLESHEET,
    LIGHT_STYLESHEET,
    MAX_MONITOR_LINES,
    MONITOR_TRIM_BATCH,
)
from .workers import AdbWorker, FileLoadWorker, FilterWorker
from .models import LogModel
from .dialogs import FindDialog, FilterDialog
from .widgets import FilterItemWidget, describe_filter_text
from .window_state import FilterTabState, MainWindowRuntimeState
from .filter_manager import FilterManager
from .adb_controller import AdbController
from .search_controller import SearchController

class LogAnalysisMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LogAnalysis (High Performance)")
        self.resize(1100, 800)

        self.filter_manager = FilterManager(self)
        self.adb_controller = AdbController(self)
        self.search_controller = SearchController(self)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.full_line_display_enabled = False
        
        # Permanent Status Widgets
        self.lbl_stats = QLabel("Lines: 0 | Visible: 0")
        self.status_bar.addPermanentWidget(self.lbl_stats)
        self.loaded_file_label = QLabel()
        self.loaded_file_label.setVisible(False)
        self.status_bar.addPermanentWidget(self.loaded_file_label)
        self.file_load_progress = QProgressBar()
        self.file_load_progress.setVisible(False)
        self.file_load_progress.setFixedWidth(150)
        self.file_load_progress.setTextVisible(True)
        self.file_load_progress.setFormat("%p%")
        self.status_bar.addPermanentWidget(self.file_load_progress)
        
        self.filter_thread = None
        self.adb_thread = None
        self.file_load_thread = None
        self._active_workers = set()
        self.runtime = MainWindowRuntimeState()
        self.find_dialog = None

        self.create_menu()
        self.init_ui()

    @property
    def filter_tab_states(self):
        return self.filter_manager.filter_tab_states

    @filter_tab_states.setter
    def filter_tab_states(self, val):
        self.filter_manager.filter_tab_states = val

    def _track_worker(self, worker):
        if not worker:
            return
        self._active_workers.add(worker)
        if hasattr(worker, "finished"):
            try:
                worker.finished.connect(lambda: self._active_workers.discard(worker))
            except (AttributeError, TypeError):
                pass

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
        self.show_only_filtered_action = QAction("Show Only Filtered Lines", self, checkable=True)
        self.show_only_filtered_action.setChecked(True)
        self.show_only_filtered_action.setShortcut("Ctrl+H")
        self.show_only_filtered_action.toggled.connect(self.toggle_show_only_filtered)
        view_menu.addAction(self.show_only_filtered_action)
        
        show_line_numbers_action = QAction("Show Line Numbers", self, checkable=True)
        show_line_numbers_action.setChecked(True)
        show_line_numbers_action.triggered.connect(self.toggle_line_numbers)
        view_menu.addAction(show_line_numbers_action)

        self.full_line_display_action = QAction("Full Line Display", self, checkable=True)
        self.full_line_display_action.setChecked(self.full_line_display_enabled)
        self.full_line_display_action.toggled.connect(self.toggle_full_line_display)
        view_menu.addAction(self.full_line_display_action)
        
        view_menu.addSeparator()
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.zoom_log(1))
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.zoom_log(-1))
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
        self.quick_filter_toolbar.addWidget(QLabel("  Modes: "))
        self.show_only_filtered_indicator = QLabel()
        self.full_line_display_indicator = QLabel()
        self.quick_filter_toolbar.addWidget(self.show_only_filtered_indicator)
        self.quick_filter_toolbar.addWidget(self.full_line_display_indicator)

        self.quick_filter_toolbar.addSeparator()

        # Add Device Selector to Toolbar
        self.device_selector = QComboBox()
        self.device_selector.setFixedWidth(130)
        self.device_selector.setToolTip("Target ADB Device Serial")

        self.btn_refresh_devices = QPushButton()
        self.btn_refresh_devices.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_refresh_devices.setToolTip("Scan for connected ADB Devices")
        self.btn_refresh_devices.clicked.connect(self.refresh_adb_devices)

        self.quick_filter_toolbar.addWidget(QLabel("  Device: "))
        self.quick_filter_toolbar.addWidget(self.device_selector)
        self.quick_filter_toolbar.addWidget(self.btn_refresh_devices)

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
        self.log_view.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.log_view.header().setStretchLastSection(False)
        self.log_view.header().setSectionResizeMode(QHeaderView.Interactive)
        self.log_view.header().setDefaultSectionSize(400) 
        
        self.log_model = LogModel()
        self.log_model.is_dark_theme = False
        self.log_view.setModel(self.log_model)
        self._apply_log_view_display_mode()
        self._update_mode_indicators()

        # Add selection context menu
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self.show_log_context_menu)

        self.filter_tabs = QTabWidget()
        self.filter_tabs.setTabBarAutoHide(False)
        self.filter_tabs.tabBarDoubleClicked.connect(self.rename_filter_tab_by_index) 
        
        self.filter_tab_states = []
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
        self.refresh_adb_devices()
        self.set_theme(light=True)

    def _next_filter_request_id(self):
        self.runtime.filter_request_id += 1
        return self.runtime.filter_request_id

    def _next_file_load_request_id(self):
        self.runtime.file_load_request_id += 1
        return self.runtime.file_load_request_id

    def _invalidate_filter_results(self):
        self.runtime.filter_request_id += 1
        self.runtime.filter_map_back = {}
        self.runtime.target_source_idx = -1
        self.runtime.is_refiltering = False

    def _reset_filter_counts(self):
        self.filter_manager.reset_filter_counts()

    def _update_loaded_file_label(self):
        file_path = self.runtime.loaded_file_path
        if not file_path:
            self.loaded_file_label.clear()
            self.loaded_file_label.setToolTip("")
            self.loaded_file_label.setVisible(False)
            return

        self.loaded_file_label.setText(f"File: {os.path.basename(file_path) or file_path}")
        self.loaded_file_label.setToolTip(file_path)
        self.loaded_file_label.setVisible(True)

    def _stop_filter_worker(self):
        thread = self.filter_thread
        self.filter_thread = None
        if thread:
            thread.stop()
            try:
                thread.finished_filtering.disconnect()
            except (TypeError, AttributeError):
                pass
            try:
                thread.filtering_failed.disconnect()
            except (TypeError, AttributeError):
                pass
            if hasattr(thread, "isRunning") and thread.isRunning():
                thread.wait(1000)
            thread.finished.connect(thread.deleteLater)

    def _finish_file_load_ui(self):
        self.runtime.is_loading_file = False
        self.runtime.loading_file_path = None
        self.file_load_progress.setVisible(False)
        self.file_load_progress.setRange(0, 100)
        self.file_load_progress.setValue(0)
        self.file_load_progress.setFormat("%p%")

    def _cancel_file_load(self):
        if not self.runtime.is_loading_file and self.file_load_thread is None:
            return

        self.runtime.file_load_request_id += 1
        self.runtime.pending_status_message = None

        thread = self.file_load_thread
        self.file_load_thread = None
        self._finish_file_load_ui()
        if thread:
            thread.stop()
            try:
                thread.progress_updated.disconnect()
            except (TypeError, AttributeError):
                pass
            try:
                thread.finished_loading.disconnect()
            except (TypeError, AttributeError):
                pass
            try:
                thread.load_failed.disconnect()
            except (TypeError, AttributeError):
                pass
            if hasattr(thread, "isRunning") and thread.isRunning():
                thread.wait(1000)
            thread.finished.connect(thread.deleteLater)

    def _update_file_load_progress_ui(self, file_path, bytes_read, total_bytes, line_count):
        file_name = os.path.basename(file_path) or file_path
        self.file_load_progress.setVisible(True)

        if total_bytes > 0:
            percent = min(100, int((bytes_read / total_bytes) * 100))
            self.file_load_progress.setRange(0, 100)
            self.file_load_progress.setValue(percent)
            self.file_load_progress.setFormat(f"{percent}%")
            self.status_bar.showMessage(
                f"Loading {file_name}... {percent}% ({line_count:,} lines)"
            )
            return

        self.file_load_progress.setRange(0, 0)
        self.file_load_progress.setFormat("")
        self.status_bar.showMessage(f"Loading {file_name}... ({line_count:,} lines)")

    def _start_file_load(self, file_path):
        self._stop_filter_worker()
        self._cancel_file_load()
        self._invalidate_filter_results()
        self.runtime.pending_chunks = []
        self.runtime.pending_status_message = None

        request_id = self._next_file_load_request_id()
        self.runtime.is_loading_file = True
        self.runtime.loading_file_path = file_path
        self._update_file_load_progress_ui(file_path, 0, 0, 0)

        self.file_load_thread = FileLoadWorker(file_path, request_id)
        self._track_worker(self.file_load_thread)
        self.file_load_thread.progress_updated.connect(self.on_file_load_progress)
        self.file_load_thread.finished_loading.connect(self.on_file_loaded)
        self.file_load_thread.load_failed.connect(self.on_file_load_failed)
        self.file_load_thread.start()

    def _stop_adb_worker(self):
        self.adb_controller.stop_adb_worker()

    def _effective_model_filters(self):
        return self.filter_manager.effective_model_filters()

    def _regex_error(self, pattern, case_sensitive):
        return self.filter_manager.regex_error(pattern, case_sensitive)

    def _normalize_filter_data(self, filter_data):
        return self.filter_manager.normalize_filter_data(filter_data)

    def _validate_loaded_filters(self, loaded_filters):
        return self.filter_manager.validate_loaded_filters(loaded_filters)

    def _tab_state(self, index):
        return self.filter_manager.tab_state(index)

    def _current_tab_state(self):
        return self.filter_manager.current_tab_state()

    def _refresh_tab_checkboxes(self):
        self.filter_manager.refresh_tab_checkboxes()

    def _create_mode_indicator(self, label, text, active, tooltip):
        label.setText(text)
        label.setToolTip(tooltip)
        label.setStyleSheet(
            (
                "QLabel {"
                "border: 1px solid #2f7d32;"
                "border-radius: 8px;"
                "padding: 2px 8px;"
                "background-color: #d8f3dc;"
                "color: #1b4332;"
                "font-weight: bold;"
                "}"
            )
            if active
            else (
                "QLabel {"
                "border: 1px solid #888;"
                "border-radius: 8px;"
                "padding: 2px 8px;"
                "background-color: #f0f0f0;"
                "color: #555;"
                "}"
            )
        )

    def _update_mode_indicators(self):
        if hasattr(self, "show_only_filtered_indicator") and hasattr(self, "log_model"):
            show_only_filtered = self.log_model.show_only_filtered
            self._create_mode_indicator(
                self.show_only_filtered_indicator,
                "Matches only" if show_only_filtered else "All lines",
                show_only_filtered,
                "Indicates whether the log view hides lines that do not match filters.",
            )

        if hasattr(self, "full_line_display_indicator"):
            self._create_mode_indicator(
                self.full_line_display_indicator,
                "Full lines" if self.full_line_display_enabled else "Compact lines",
                self.full_line_display_enabled,
                "Indicates whether long lines are shown at full width or in compact mode.",
            )

    def _filter_matches_search(self, filter_data, query):
        normalized_query = query.strip().lower()
        if not normalized_query:
            return True

        haystacks = [
            filter_data.get("text", ""),
            describe_filter_text(filter_data),
        ]
        return any(normalized_query in text.lower() for text in haystacks)

    def _update_filter_item_visibility(self, tab_state, item):
        self.filter_manager._update_filter_item_visibility(tab_state, item)

    def _apply_filter_search(self, tab_state):
        self.filter_manager.apply_filter_search(tab_state)

    def _build_filter_item(self, filter_data):
        return self.filter_manager.build_filter_item(filter_data)

    def _insert_filter_item(self, tab_state, filter_data, row=None):
        return self.filter_manager.insert_filter_item(tab_state, filter_data, row)

    def _selected_filter_items(self, tab_state, target_item=None):
        return self.filter_manager.selected_filter_items(tab_state, target_item)

    def _delete_filter_items(self, tab_state, items):
        self.filter_manager.delete_filter_items(tab_state, items)

    def _duplicate_filter_item(self, tab_state, item):
        self.filter_manager.duplicate_filter_item(tab_state, item)

    def _copy_filter_pattern(self, tab_state, item):
        self.filter_manager.copy_filter_pattern(tab_state, item)

    def _show_filter_context_menu(self, tab_state, position):
        self.filter_manager.show_filter_context_menu(tab_state, position)

    def _on_tab_checkbox_changed(self, state):
        self.filter_manager._on_tab_checkbox_changed(state)

    def _apply_chunk_to_model(self, lines):
        was_at_bottom = False
        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar.value() == scrollbar.maximum():
            was_at_bottom = True

        data_added = self.log_model.append_chunk(lines)
        self._update_log_column_width()
        if data_added:
            self.update_stats()
            self.update_filter_counts_ui()

        trimmed = self._trim_live_log_buffer_if_needed(was_at_bottom)
        if data_added and was_at_bottom and not trimmed:
            self.log_view.scrollToBottom()

    def _flush_pending_chunks(self):
        if self.runtime.is_paused or self.runtime.is_refiltering or not self.runtime.pending_chunks:
            return

        chunks = self.runtime.pending_chunks
        self.runtime.pending_chunks = []
        for i, chunk in enumerate(chunks):
            self._apply_chunk_to_model(chunk)
            if self.runtime.is_refiltering:
                self.runtime.pending_chunks = chunks[i + 1:] + self.runtime.pending_chunks
                break

    def _base_log_column_width(self):
        viewport_width = self.log_view.viewport().width()
        if viewport_width > 0:
            return viewport_width
        return self.log_view.header().defaultSectionSize()

    def _apply_log_view_display_mode(self):
        if not hasattr(self, "log_view"):
            return

        elide_mode = Qt.ElideNone if self.full_line_display_enabled else Qt.ElideRight
        self.log_view.setTextElideMode(elide_mode)

        if hasattr(self, "full_line_display_action"):
            self.full_line_display_action.blockSignals(True)
            self.full_line_display_action.setChecked(self.full_line_display_enabled)
            self.full_line_display_action.blockSignals(False)

        self._update_log_column_width()
        self._update_mode_indicators()

    def _update_log_column_width(self):
        if not hasattr(self, "log_view") or not hasattr(self, "log_model"):
            return

        width = self._base_log_column_width()
        if self.full_line_display_enabled:
            metrics = QFontMetrics(self.log_model.font)
            prefix = ""
            if self.log_model.show_line_numbers:
                max_line_number = max(len(self.log_model.all_lines), 1)
                prefix = f"{max_line_number:6d} | "

            if self.log_model.visible_longest_line_text:
                sample_text = f"{prefix}{self.log_model.visible_longest_line_text}"
                content_width = metrics.horizontalAdvance(sample_text) + 24
                width = max(width, content_width)

        self.log_view.header().resizeSection(0, width)

    def _trim_live_log_buffer_if_needed(self, preserve_bottom=False):
        if not self.runtime.is_monitoring:
            return False

        trim_batch = getattr(self, "monitor_trim_batch", None)
        if trim_batch is None:
            trim_batch = min(MONITOR_TRIM_BATCH, max(1, MAX_MONITOR_LINES // 10))

        excess_lines = len(self.log_model.all_lines) - MAX_MONITOR_LINES
        if excess_lines < trim_batch:
            return False

        self._invalidate_filter_results()
        self.log_model.set_lines(
            self.log_model.all_lines[excess_lines:],
            longest_line_text=self.log_model.longest_line_text,
        )
        self._update_log_column_width()
        if preserve_bottom:
            self.runtime.scroll_to_bottom_after_refilter = True

        self.status_bar.showMessage(
            f"Monitoring buffer trimmed to the most recent {MAX_MONITOR_LINES:,} lines.",
            5000,
        )
        self.apply_filters()
        return True

    def set_theme(self, light=True):
        if hasattr(self, "log_model"):
            self.log_model.is_dark_theme = not light
        if light:
            self.light_theme_action.setChecked(True)
            self.dark_theme_action.setChecked(False)
            QApplication.instance().setStyleSheet(LIGHT_STYLESHEET)
        else:
            self.light_theme_action.setChecked(False)
            self.dark_theme_action.setChecked(True)
            QApplication.instance().setStyleSheet(DARK_STYLESHEET)
        if hasattr(self, "log_model"):
            self.log_model.layoutChanged.emit()

    def update_search_highlights(self, query, case, regex):
        if hasattr(self, "log_model"):
            self.log_model.search_query = query
            self.log_model.search_case = case
            self.log_model.search_regex = regex
            self.log_model.layoutChanged.emit()

    def clear_search_highlights(self):
        if hasattr(self, "log_model"):
            self.log_model.search_query = ""
            self.log_model.layoutChanged.emit()

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
        
        self._insert_filter_item(self._current_tab_state(), filter_data)
        
        self.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)
        self.quick_input.clear()

    def update_stats(self):
        total = len(self.log_model.all_lines)
        visible = len(self.log_model.visible_indices)
        self.lbl_stats.setText(f"Lines: {total} | Visible: {visible}")

    def show_find_dialog(self):
        self.search_controller.show_find_dialog()

    def find_in_files(self, text, forward=True, case=False, regex=False):
        self.search_controller.find_in_files(text, forward=forward, case=case, regex=regex)

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

    def show_log_context_menu(self, position):
        menu = QMenu(self)
        
        copy_act = menu.addAction("Copy Selection")
        copy_act.triggered.connect(self.copy_selection)
        
        selection_model = self.log_view.selectionModel()
        selected_indexes = selection_model.selectedRows()
        
        selected_text = ""
        if len(selected_indexes) == 1:
            idx = selected_indexes[0]
            if idx.isValid():
                row = idx.row()
                if row < len(self.log_model.visible_indices):
                    real_idx = self.log_model.visible_indices[row]
                    raw_text = self.log_model.get_line_text(real_idx).rstrip('\r\n')
                    selected_text = raw_text.strip()
        
        add_include_act = None
        add_exclude_act = None
        if selected_text:
            display_text = selected_text if len(selected_text) <= 30 else selected_text[:27] + "..."
            add_include_act = menu.addAction(f"Add as Include Filter: \"{display_text}\"")
            add_exclude_act = menu.addAction(f"Add as Exclude Filter: \"{display_text}\"")
            
        chosen_action = menu.exec_(self.log_view.viewport().mapToGlobal(position))
        
        if chosen_action:
            if chosen_action == add_include_act:
                self.add_quick_filter_from_text(selected_text, exclude=False)
            elif chosen_action == add_exclude_act:
                self.add_quick_filter_from_text(selected_text, exclude=True)

    def add_quick_filter_from_text(self, text, exclude=False):
        if not text:
            return
        filter_data = {
            "text": text,
            "case_sensitive": False,
            "regex": False,
            "exclude": exclude,
            "bg_color": "None",
            "text_color": "None",
            "active": True,
            "description": "Quick context filter"
        }
        self._insert_filter_item(self._current_tab_state(), filter_data)
        self.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def toggle_adb_monitoring(self):
        self.adb_controller.toggle_adb_monitoring()

    def refresh_adb_devices(self):
        self.adb_controller.refresh_adb_devices()

    def clear_logs(self):
        self._cancel_file_load()
        self._stop_filter_worker()
        self.search_controller.stop_search()
        self._invalidate_filter_results()
        self.runtime.pending_status_message = None
        self.runtime.loaded_file_path = None
        self._update_loaded_file_label()
        self.log_model.clear()
        self._update_log_column_width()
        self.runtime.pending_chunks = []
        self.update_stats()
        self._reset_filter_counts()
        self.update_filter_counts_ui()
        self.status_bar.showMessage("Logs cleared.", 3000)
            
    def toggle_pause(self, checked):
        self.runtime.is_paused = checked
        if self.runtime.is_paused:
            self.status_bar.showMessage("Monitoring Paused (Buffering...)")
        else:
            self.status_bar.showMessage("Resuming...")
            self._flush_pending_chunks()

    def on_adb_chunk(self, lines):
        self.adb_controller.on_adb_chunk(lines)

    def on_adb_error(self, message):
        self.adb_controller.on_adb_error(message)

    def rename_filter_tab(self):
        self.filter_manager.rename_filter_tab()

    def rename_filter_tab_by_index(self, idx):
        self.filter_manager.rename_filter_tab_by_index(idx)

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
        self.filter_manager.add_filter_tab()

    def set_tab_modified(self, index, modified: bool):
        self.filter_manager.set_tab_modified(index, modified)

    def _on_tab_toggled(self, index, state):
        self.filter_manager.on_tab_toggled(index, state)

    def sync_filter_order(self):
        self.filter_manager.sync_filter_order()

    def delete_filter_tab(self):
        self.filter_manager.delete_filter_tab()

    def current_filter_list(self):
        return self.filter_manager.current_filter_list()

    def toggle_line_numbers(self, checked):
        self.log_model.show_line_numbers = checked
        self.log_model.layoutChanged.emit()
        self._update_log_column_width()

    def toggle_full_line_display(self, checked):
        self.full_line_display_enabled = checked
        self._apply_log_view_display_mode()

    def zoom_log(self, delta):
        self.log_model.zoom(delta)
        self._update_log_column_width()

    def toggle_show_only_filtered(self, checked):
        self.log_model.show_only_filtered = checked
        self._update_mode_indicators()
        self.apply_filters()

    def apply_filter_colors_to_list_item(self, item, filter_data):
        self.filter_manager.apply_filter_colors_to_list_item(item, filter_data)
        item.setData(Qt.UserRole, filter_data)

    def open_file(self):
        if self.runtime.is_monitoring:
            self.toggle_adb_monitoring()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Log File", "", "Log/Text Files (*.log *.txt);;All Files (*)"
        )
        if file_path:
            if not os.path.isfile(file_path):
                QMessageBox.warning(self, "Invalid File", "The selected path is not a regular file.")
                return

            try:
                size = os.path.getsize(file_path)
                MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
                if size > MAX_FILE_SIZE:
                    QMessageBox.warning(
                        self, 
                        "File Too Large", 
                        f"Opening files larger than 500 MB is blocked to prevent system memory exhaustion.\n"
                        f"Selected file size: {size / (1024*1024):.1f} MB."
                    )
                    return
            except OSError as e:
                QMessageBox.warning(self, "File Error", f"Cannot access file details: {str(e)}")
                return

            self._start_file_load(file_path)

    def on_file_load_progress(self, request_id, file_path, bytes_read, total_bytes, line_count):
        if request_id != self.runtime.file_load_request_id or not self.runtime.is_loading_file:
            return

        self._update_file_load_progress_ui(file_path, bytes_read, total_bytes, line_count)

    def on_file_loaded(self, request_id, file_path, lines, longest_line_text=None):
        if request_id != self.runtime.file_load_request_id:
            return

        if self.sender() is self.file_load_thread:
            self.file_load_thread = None

        self._finish_file_load_ui()
        self.runtime.loaded_file_path = file_path
        self._update_loaded_file_label()
        self.log_model.set_lines(lines, longest_line_text=longest_line_text)
        self._update_log_column_width()
        self.update_stats()
        self.runtime.pending_status_message = f"Loaded: {file_path} ({len(lines):,} lines)"
        self.apply_filters()

    def on_file_load_failed(self, request_id, file_path, message):
        if request_id != self.runtime.file_load_request_id:
            return

        if self.sender() is self.file_load_thread:
            self.file_load_thread = None

        self._finish_file_load_ui()
        self.runtime.pending_status_message = None
        self.status_bar.showMessage(f"Error loading file: {message}", 5000)
        QMessageBox.warning(
            self,
            "Open File Error",
            f"Cannot load '{file_path}':\n\n{message}",
        )

    def add_filter_dialog(self):
        tab_state = self._current_tab_state()
        dialog = FilterDialog(self)
        if dialog.exec_():
            filter_data = dialog.get_filter_data()
            filter_data["active"] = True

            self._insert_filter_item(tab_state, filter_data)
            
            self.apply_filters()
            self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def _on_filter_toggled(self, filter_data, checked):
        self.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def edit_filter_dialog(self, item):
        tab_state = self._current_tab_state()
        filter_list = tab_state.filter_list
        idx = filter_list.row(item)
        filter_data = tab_state.filters[idx]
        dialog = FilterDialog(self, filter_data)
        if dialog.exec_():
            new_filter_data = dialog.get_filter_data()
            widget = filter_list.itemWidget(item)
            if widget:
                new_filter_data["active"] = widget.checkbox.isChecked()
            else:
                new_filter_data["active"] = filter_data.get("active", True)

            tab_state.filters[idx] = new_filter_data
            self.apply_filter_colors_to_list_item(item, new_filter_data)

            if widget:
                widget.filter_data = new_filter_data
                widget.update_display()

            self._update_filter_item_visibility(tab_state, item)
            
            self.apply_filters()
            self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def eventFilter(self, source, event):
        current_tab_state = self._current_tab_state()
        if current_tab_state and source == current_tab_state.filter_list and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Delete:
                self._delete_filter_items(
                    current_tab_state,
                    current_tab_state.filter_list.selectedItems(),
                )
                return True
        return super().eventFilter(source, event)

    def save_filters(self):
        self.filter_manager.save_filters()

    def save_filters_as(self):
        self.filter_manager.save_filters_as()

    def _do_save(self, idx, file_path):
        self.filter_manager.do_save(idx, file_path)

    def load_filters(self):
        self.filter_manager.load_filters()

    def apply_filters(self):
        self.log_model.filters = self._effective_model_filters()
        self.runtime.filter_map_back = {}
        
        flat_idx = 0
        all_filters_to_count = []
        
        for tab_idx, tab_state in enumerate(self.filter_tab_states):
            for filter_idx, f in enumerate(tab_state.filters):
                f_data = f.copy()
                if not tab_state.enabled:
                    f_data["active"] = False
                
                self.runtime.filter_map_back[flat_idx] = (tab_idx, filter_idx)
                all_filters_to_count.append(f_data)
                flat_idx += 1

        self._stop_filter_worker()
        request_id = self._next_filter_request_id()
        
        if not self.log_model.all_lines:
            self._reset_filter_counts()
            self.on_filtering_finished(request_id, [], 0, [0] * len(all_filters_to_count), "", [])
            return

        self.runtime.target_source_idx = -1
        current_idx = self.log_view.currentIndex()
        if current_idx.isValid():
            row = current_idx.row()
            if row < len(self.log_model.visible_indices):
                self.runtime.target_source_idx = self.log_model.visible_indices[row]

        self.runtime.is_refiltering = self.runtime.is_monitoring
        if not self.runtime.is_monitoring:
            self.status_bar.showMessage("Refiltering...")
            
        self.filter_thread = FilterWorker(
            self.log_model.all_lines[:], 
            all_filters_to_count, 
            self.log_model.show_only_filtered,
            request_id
        )
        self._track_worker(self.filter_thread)
        self.filter_thread.finished_filtering.connect(self.on_filtering_finished)
        self.filter_thread.filtering_failed.connect(self.on_filtering_failed)
        self.filter_thread.start()

    def on_filtering_finished(
        self,
        request_id,
        visible_indices,
        match_count,
        filter_counts=None,
        widest_visible_text="",
        visible_styles=None,
    ):
        if request_id != self.runtime.filter_request_id:
            return

        if self.sender() is self.filter_thread:
            self.filter_thread = None

        self.runtime.is_refiltering = False
        self.log_model.update_visible_indices(visible_indices, widest_visible_text, visible_styles)
        self._update_log_column_width()
        
        if self.runtime.target_source_idx != -1 and visible_indices:
            pos = bisect.bisect_left(visible_indices, self.runtime.target_source_idx)
            new_row = -1
            if pos < len(visible_indices):
                if pos > 0:
                    dist_curr = visible_indices[pos] - self.runtime.target_source_idx
                    dist_prev = self.runtime.target_source_idx - visible_indices[pos-1]
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
        
        if filter_counts is not None:
            for tab_state in self.filter_tab_states:
                for f in tab_state.filters:
                    f['total_matches'] = 0
                    
            for flat_idx, count in enumerate(filter_counts):
                if flat_idx in self.runtime.filter_map_back:
                    tab_idx, filter_idx = self.runtime.filter_map_back[flat_idx]
                    tab_state = self._tab_state(tab_idx)
                    if tab_state is not None and filter_idx < len(tab_state.filters):
                        tab_state.filters[filter_idx]['total_matches'] = count
            
            self.update_filter_counts_ui()
        else:
            self.update_filter_counts_ui()

        self._flush_pending_chunks()
        if self.runtime.scroll_to_bottom_after_refilter and self.log_model.rowCount() > 0:
            self.log_view.scrollToBottom()
        self.runtime.scroll_to_bottom_after_refilter = False
            
    def on_filtering_failed(self, request_id, error_message):
        if request_id != self.runtime.filter_request_id:
            return

        if self.sender() is self.filter_thread:
            self.filter_thread = None

        self.runtime.is_refiltering = False
        self.status_bar.showMessage(f"Filtering error: {error_message}", 5000)
        self._flush_pending_chunks()

    def update_filter_counts_ui(self):
        self.filter_manager.update_filter_counts_ui()
        
        if self.runtime.is_monitoring:
            if self.runtime.is_paused:
                self.status_bar.showMessage("Monitoring Paused (Buffering...)")
            elif self.runtime.is_refiltering:
                self.status_bar.showMessage("Refiltering live logs...")
            else:
                self.status_bar.showMessage("Monitoring...")
        elif self.runtime.is_loading_file:
            return
        elif self.runtime.pending_status_message:
            self.status_bar.showMessage(self.runtime.pending_status_message, 5000)
            self.runtime.pending_status_message = None
        else:
            self.status_bar.showMessage(f"Refiltered complete.")

    def _cleanup_all_workers(self):
        self._cancel_file_load()
        self._stop_filter_worker()
        self._stop_adb_worker()
        self.search_controller.stop_search()
        for worker in list(self._active_workers):
            try:
                if hasattr(worker, "stop"):
                    worker.stop()
                if hasattr(worker, "isRunning") and worker.isRunning():
                    worker.wait(1000)
            except RuntimeError:
                pass
        self._active_workers.clear()

    def closeEvent(self, event):
        modified_tabs = []
        for i, tab_state in enumerate(self.filter_tab_states):
            if tab_state.modified:
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
                for i, tab_state in enumerate(self.filter_tab_states):
                    if tab_state.modified:
                        self.filter_tabs.setCurrentIndex(i)
                        self.save_filters()
                        if self._tab_state(i).modified:
                            event.ignore()
                            return
                self._cleanup_all_workers()
                event.accept()
            elif res == QMessageBox.Discard:
                self._cleanup_all_workers()
                event.accept()
            else:
                event.ignore()
        else:
            self._cleanup_all_workers()
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_log_column_width()
