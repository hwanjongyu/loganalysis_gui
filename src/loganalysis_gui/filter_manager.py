import json
import os
import re
from typing import List, Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from .constants import COLOR_MAP, TEXT_COLOR_MAP
from .widgets import FilterItemWidget, describe_filter_text
from .window_state import FilterTabState


def _get_qmenu():
    import sys
    mw = sys.modules.get("loganalysis_gui.main_window")
    return getattr(mw, "QMenu", QMenu) if mw else QMenu


def _get_qfiledialog():
    import sys
    mw = sys.modules.get("loganalysis_gui.main_window")
    return getattr(mw, "QFileDialog", QFileDialog) if mw else QFileDialog


def _get_qmessagebox():
    import sys
    mw = sys.modules.get("loganalysis_gui.main_window")
    return getattr(mw, "QMessageBox", QMessageBox) if mw else QMessageBox


class FilterManager:
    """Manages filter tabs, filter items, search filtering, and JSON serialization."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.filter_tab_states: List[FilterTabState] = []

    @property
    def filter_tabs(self):
        return self.main_window.filter_tabs

    def tab_state(self, index: int) -> Optional[FilterTabState]:
        if 0 <= index < len(self.filter_tab_states):
            return self.filter_tab_states[index]
        return None

    def current_tab_state(self) -> Optional[FilterTabState]:
        return self.tab_state(self.filter_tabs.currentIndex())

    def effective_model_filters(self) -> List[dict]:
        effective = []
        for state in self.filter_tab_states:
            if not state.enabled:
                continue
            effective.extend(state.filters)
        return effective

    def regex_error(self, pattern: str, case_sensitive: bool) -> Optional[str]:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            re.compile(pattern, flags)
        except re.error as error:
            return str(error)
        return None

    def normalize_filter_data(self, filter_data: dict) -> dict:
        normalized = {
            "text": filter_data.get("text", ""),
            "case_sensitive": filter_data.get("case_sensitive", False),
            "regex": filter_data.get("regex", False),
            "exclude": filter_data.get("exclude", False),
            "bg_color": filter_data.get("bg_color", "None"),
            "text_color": filter_data.get("text_color", "None"),
            "active": filter_data.get("active", True),
            "description": filter_data.get("description", ""),
        }
        if "total_matches" in filter_data:
            normalized["total_matches"] = filter_data["total_matches"]
        return normalized

    def validate_loaded_filters(self, loaded_filters):
        normalized_filters = []
        invalid_filters = []

        for raw_filter in loaded_filters:
            if not isinstance(raw_filter, dict):
                return None, ["Each filter entry must be an object."]

            filter_data = self.normalize_filter_data(raw_filter)
            if filter_data["regex"]:
                err = self.regex_error(filter_data["text"], filter_data["case_sensitive"])
                if err:
                    invalid_filters.append(f"\"{filter_data['text']}\": {err}")

            normalized_filters.append(filter_data)

        return normalized_filters, invalid_filters

    def refresh_tab_checkboxes(self):
        tab_bar = self.filter_tabs.tabBar()
        for index, tab_state in enumerate(self.filter_tab_states):
            old_checkbox = tab_bar.tabButton(index, QTabBar.LeftSide)
            if old_checkbox:
                old_checkbox.deleteLater()
            checkbox = QCheckBox()
            checkbox.setProperty("tab_index", index)
            checkbox.setChecked(tab_state.enabled)
            checkbox.setToolTip("Enable/Disable this filter set")
            checkbox.stateChanged.connect(self._on_tab_checkbox_changed)
            tab_bar.setTabButton(index, QTabBar.LeftSide, checkbox)
            tab_state.checkbox = checkbox

    def _on_tab_checkbox_changed(self, state):
        sender = self.main_window.sender()
        if not sender:
            return
        idx = sender.property("tab_index")
        if idx is not None:
            self.on_tab_toggled(idx, state)

    def on_tab_toggled(self, index: int, state):
        tab_state = self.tab_state(index)
        if tab_state is None:
            return

        tab_state.enabled = (state == Qt.Checked)
        self.set_tab_modified(index, True)
        self.main_window.apply_filters()

    def set_tab_modified(self, index: int, modified: bool):
        tab_state = self.tab_state(index)
        if tab_state is not None:
            tab_state.modified = modified
            current_text = self.filter_tabs.tabText(index)
            if modified:
                if not current_text.startswith("*"):
                    self.filter_tabs.setTabText(index, "*" + current_text)
            else:
                if current_text.startswith("*"):
                    self.filter_tabs.setTabText(index, current_text[1:])

    def add_filter_tab(self):
        filter_list = QListWidget()
        filter_list.setDragDropMode(QListWidget.InternalMove)
        filter_list.setAlternatingRowColors(True)
        filter_list.itemDoubleClicked.connect(self.main_window.edit_filter_dialog)
        filter_list.setContextMenuPolicy(Qt.CustomContextMenu)
        filter_list.installEventFilter(self.main_window)
        filter_list.model().rowsMoved.connect(lambda: self.sync_filter_order())

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search filters in this tab...")

        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)
        tab_layout.addWidget(search_input)
        tab_layout.addWidget(filter_list)

        tab_state = FilterTabState(
            tab_widget=tab_widget,
            filter_list=filter_list,
            search_input=search_input,
        )
        self.filter_tab_states.append(tab_state)

        search_input.textChanged.connect(lambda _text, state=tab_state: self.apply_filter_search(state))
        filter_list.customContextMenuRequested.connect(
            lambda position, state=tab_state: self.show_filter_context_menu(state, position)
        )

        idx = len(self.filter_tab_states) - 1
        self.filter_tabs.addTab(tab_widget, f"Filter Set {idx + 1}")
        self.refresh_tab_checkboxes()
        self.filter_tabs.setCurrentIndex(idx)

    def delete_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        if len(self.filter_tab_states) > 1 and idx >= 0:
            tab_state = self.filter_tab_states[idx]
            self.filter_tabs.removeTab(idx)
            del self.filter_tab_states[idx]
            if tab_state.tab_widget:
                tab_state.tab_widget.deleteLater()
            self.refresh_tab_checkboxes()
            self.main_window.apply_filters()

    def rename_filter_tab(self):
        idx = self.filter_tabs.currentIndex()
        self.rename_filter_tab_by_index(idx)

    def rename_filter_tab_by_index(self, idx: int):
        if idx < 0:
            return

        current_title = self.filter_tabs.tabText(idx)
        has_asterisk = current_title.startswith("*")
        display_title = current_title[1:] if has_asterisk else current_title

        new_title, ok = QInputDialog.getText(
            self.main_window,
            "Rename Filter Tab",
            "Enter new tab name:",
            QLineEdit.Normal,
            display_title,
        )
        if ok and new_title.strip():
            final_title = f"*{new_title.strip()}" if has_asterisk else new_title.strip()
            self.filter_tabs.setTabText(idx, final_title)
            self.set_tab_modified(idx, True)

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
                widget = filter_list.itemWidget(item)
                if not widget:
                    widget = FilterItemWidget(filters[i])
                    widget.filter_toggled.connect(self.main_window._on_filter_toggled)
                    filter_list.setItemWidget(item, widget)
        self.main_window.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def current_filter_list(self):
        tab_state = self.current_tab_state()
        return tab_state.filter_list, tab_state.filters

    def apply_filter_colors_to_list_item(self, item: QListWidgetItem, filter_data: dict):
        bg_color = filter_data.get("bg_color", "None")
        text_color = filter_data.get("text_color", "None")
        if bg_color != "None":
            item.setBackground(QColor(COLOR_MAP.get(bg_color, bg_color)))
        if text_color != "None":
            item.setForeground(QColor(TEXT_COLOR_MAP.get(text_color, text_color)))

    def build_filter_item(self, filter_data: dict):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, filter_data)
        item.setToolTip(describe_filter_text(filter_data))
        self.apply_filter_colors_to_list_item(item, filter_data)

        widget = FilterItemWidget(filter_data)
        widget.filter_toggled.connect(self.main_window._on_filter_toggled)
        return item, widget

    def insert_filter_item(self, tab_state: FilterTabState, filter_data: dict, row: Optional[int] = None):
        item, widget = self.build_filter_item(filter_data)

        if row is None or row < 0 or row > tab_state.filter_list.count():
            row = tab_state.filter_list.count()

        tab_state.filter_list.insertItem(row, item)
        tab_state.filters.insert(row, filter_data)
        tab_state.filter_list.setItemWidget(item, widget)
        self._update_filter_item_visibility(tab_state, item)
        return item

    def _update_filter_item_visibility(self, tab_state: FilterTabState, item: QListWidgetItem):
        query = tab_state.search_input.text().strip().lower()
        if not query:
            item.setHidden(False)
            return

        filter_data = item.data(Qt.UserRole) or {}
        matches = (
            query in filter_data.get("text", "").lower()
            or query in filter_data.get("description", "").lower()
        )
        item.setHidden(not matches)

    def apply_filter_search(self, tab_state: FilterTabState):
        for i in range(tab_state.filter_list.count()):
            item = tab_state.filter_list.item(i)
            if item:
                self._update_filter_item_visibility(tab_state, item)

    def selected_filter_items(self, tab_state: FilterTabState, target_item: Optional[QListWidgetItem] = None):
        selected_items = tab_state.filter_list.selectedItems()
        if target_item is not None and target_item not in selected_items:
            tab_state.filter_list.clearSelection()
            target_item.setSelected(True)
            tab_state.filter_list.setCurrentItem(target_item)
            selected_items = [target_item]
        return selected_items

    def delete_filter_items(self, tab_state: FilterTabState, items: List[QListWidgetItem]):
        rows = sorted(
            {tab_state.filter_list.row(item) for item in items if item is not None},
            reverse=True,
        )
        if not rows:
            return

        for row in rows:
            tab_state.filter_list.takeItem(row)
            del tab_state.filters[row]

        self.main_window.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def duplicate_filter_item(self, tab_state: FilterTabState, item: QListWidgetItem):
        row = tab_state.filter_list.row(item)
        if row < 0 or row >= len(tab_state.filters):
            return

        duplicated_filter = self.normalize_filter_data(tab_state.filters[row])
        duplicated_item = self.insert_filter_item(tab_state, duplicated_filter, row + 1)
        tab_state.filter_list.setCurrentItem(duplicated_item)
        duplicated_item.setSelected(True)
        self.main_window.apply_filters()
        self.set_tab_modified(self.filter_tabs.currentIndex(), True)

    def copy_filter_pattern(self, tab_state: FilterTabState, item: QListWidgetItem):
        row = tab_state.filter_list.row(item)
        if row < 0 or row >= len(tab_state.filters):
            return

        pattern = tab_state.filters[row].get("text", "")
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(pattern)
            self.main_window.status_bar.showMessage(f"Copied filter pattern: {pattern}", 2000)

    def show_filter_context_menu(self, tab_state: FilterTabState, position: QPoint):
        item = tab_state.filter_list.itemAt(position)
        if item is None:
            return

        selected_items = self.selected_filter_items(tab_state, item)
        menu_cls = _get_qmenu()
        menu = menu_cls(self.main_window)
        edit_action = menu.addAction("Edit")
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        copy_action = menu.addAction("Copy Pattern")
        chosen_action = menu.exec_(tab_state.filter_list.mapToGlobal(position))

        if chosen_action == edit_action:
            self.main_window.edit_filter_dialog(item)
        elif chosen_action == duplicate_action:
            self.duplicate_filter_item(tab_state, item)
        elif chosen_action == delete_action:
            self.delete_filter_items(tab_state, selected_items)
        elif chosen_action == copy_action:
            self.copy_filter_pattern(tab_state, item)

    def save_filters(self):
        idx = self.filter_tabs.currentIndex()
        if idx < 0:
            return

        tab_state = self.tab_state(idx)
        if tab_state and tab_state.file_path:
            self.do_save(idx, tab_state.file_path)
        else:
            self.save_filters_as()

    def save_filters_as(self):
        idx = self.filter_tabs.currentIndex()
        if idx < 0:
            return

        tab_name = self.filter_tabs.tabText(idx)
        if tab_name.startswith("*"):
            tab_name = tab_name[1:]
        default_name = f"{tab_name}.json"

        file_path, _ = _get_qfiledialog().getSaveFileName(
            self.main_window,
            "Save Current Tab Filters As",
            default_name,
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.do_save(idx, file_path)

    def do_save(self, idx: int, file_path: str):
        temp_path = None
        try:
            tab_name = self.filter_tabs.tabText(idx)
            if tab_name.startswith("*"):
                tab_name = tab_name[1:]

            tab_state = self.tab_state(idx)
            if not tab_state:
                return

            filters_to_save = []
            for f in tab_state.filters:
                f_copy = f.copy()
                f_copy.pop("total_matches", None)
                filters_to_save.append(f_copy)

            data = {
                "name": tab_name,
                "enabled": tab_state.enabled,
                "filters": filters_to_save,
            }
            temp_path = f"{file_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, file_path)
            temp_path = None

            tab_state.file_path = file_path
            self.set_tab_modified(idx, False)
            self.main_window.status_bar.showMessage(f"Filters from '{tab_name}' saved to {file_path}", 3000)
        except OSError as error:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            self.main_window.status_bar.showMessage(f"Error saving filters: {error}", 5000)

    def load_filters(self):
        file_path, _ = _get_qfiledialog().getOpenFileName(
            self.main_window,
            "Load Filters to Current Tab",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            loaded_set = []
            tab_name = None
            tab_enabled = True

            if isinstance(loaded, dict):
                loaded_set = loaded.get("filters", [])
                tab_name = loaded.get("name")
                tab_enabled = loaded.get("enabled", True)
            elif isinstance(loaded, list):
                if len(loaded) > 0 and isinstance(loaded[0], dict) and "filters" in loaded[0]:
                    loaded_set = loaded[0]["filters"]
                    tab_name = loaded[0].get("name")
                else:
                    loaded_set = loaded

            if not loaded_set and not isinstance(loaded_set, list):
                self.main_window.status_bar.showMessage("Invalid filter file format.")
                return

            normalized_filters, invalid_filters = self.validate_loaded_filters(loaded_set)
            if normalized_filters is None:
                self.main_window.status_bar.showMessage("Invalid filter file format.")
                _get_qmessagebox().warning(self.main_window, "Invalid Filter File", invalid_filters[0])
                return

            if invalid_filters:
                details = "\n".join(f"- {item}" for item in invalid_filters[:5])
                if len(invalid_filters) > 5:
                    details += "\n- ..."
                _get_qmessagebox().warning(
                    self.main_window,
                    "Invalid Filter File",
                    f"Cannot load filters with invalid regular expressions:\n\n{details}",
                )
                self.main_window.status_bar.showMessage("Error loading filters: invalid regex in file.", 5000)
                return

            filter_list, filters = self.current_filter_list()
            filter_list.clear()
            filters.clear()

            curr_idx = self.filter_tabs.currentIndex()
            tab_state = self.tab_state(curr_idx)

            if tab_name:
                self.filter_tabs.setTabText(curr_idx, tab_name)

            if tab_state:
                tab_state.enabled = tab_enabled
                if tab_state.checkbox:
                    tab_state.checkbox.setChecked(tab_enabled)

            for filter_data in normalized_filters:
                self.insert_filter_item(tab_state, filter_data)

            if tab_state:
                tab_state.file_path = file_path
            self.set_tab_modified(curr_idx, False)

            self.main_window.apply_filters()
            display_name = tab_name or os.path.basename(file_path)
            self.main_window.status_bar.showMessage(f"Loaded filters: {display_name}", 3000)
        except json.JSONDecodeError:
            _get_qmessagebox().warning(
                self.main_window,
                "Invalid Filter File",
                "Cannot load filters: the selected file is not valid JSON.",
            )
            self.main_window.status_bar.showMessage("Error loading filters: invalid JSON file.", 5000)
        except OSError as error:
            self.main_window.status_bar.showMessage(f"Error loading filters: {error}", 5000)

    def reset_filter_counts(self):
        for tab_state in self.filter_tab_states:
            for f in tab_state.filters:
                f["total_matches"] = 0

    def update_filter_counts_ui(self):
        for tab_state in self.filter_tab_states:
            filter_list = tab_state.filter_list
            for i in range(filter_list.count()):
                item = filter_list.item(i)
                widget = filter_list.itemWidget(item)
                if widget and i < len(tab_state.filters):
                    widget.filter_data["total_matches"] = tab_state.filters[i].get("total_matches", 0)
                    widget.update_display()
