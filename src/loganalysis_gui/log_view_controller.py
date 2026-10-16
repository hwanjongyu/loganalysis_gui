import sys
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QApplication, QMenu


def _get_qmenu():
    main_window_mod = sys.modules.get("loganalysis_gui.main_window")
    if main_window_mod and hasattr(main_window_mod, "QMenu"):
        return main_window_mod.QMenu
    return QMenu


class LogViewController:
    """Manages log view presentation, column widths, zooming, full line display mode, and context menus."""

    def __init__(self, main_window):
        self.main_window = main_window

    @property
    def log_view(self):
        return self.main_window.log_view

    @property
    def log_model(self):
        return self.main_window.log_model

    @property
    def status_bar(self):
        return self.main_window.status_bar

    @property
    def full_line_display_enabled(self) -> bool:
        return self.main_window.full_line_display_enabled

    @full_line_display_enabled.setter
    def full_line_display_enabled(self, val: bool):
        self.main_window.full_line_display_enabled = val

    def base_log_column_width(self) -> int:
        viewport_width = self.log_view.viewport().width()
        if viewport_width > 0:
            return viewport_width
        return self.log_view.header().defaultSectionSize()

    def update_log_column_width(self):
        if not hasattr(self.main_window, "log_view") or not hasattr(self.main_window, "log_model"):
            return

        width = self.base_log_column_width()
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

    def apply_log_view_display_mode(self):
        if not hasattr(self.main_window, "log_view"):
            return

        elide_mode = Qt.ElideNone if self.full_line_display_enabled else Qt.ElideRight
        self.log_view.setTextElideMode(elide_mode)

        if hasattr(self.main_window, "full_line_display_action"):
            self.main_window.full_line_display_action.blockSignals(True)
            self.main_window.full_line_display_action.setChecked(self.full_line_display_enabled)
            self.main_window.full_line_display_action.blockSignals(False)

        self.update_log_column_width()
        self.update_mode_indicators()

    def toggle_full_line_display(self, checked: bool):
        self.full_line_display_enabled = checked
        self.apply_log_view_display_mode()

    def toggle_line_numbers(self, checked: bool):
        self.log_model.show_line_numbers = checked
        self.log_model.layoutChanged.emit()
        self.update_log_column_width()

    def zoom_log(self, delta: int):
        self.log_model.zoom(delta)
        self.update_log_column_width()

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
        menu_cls = _get_qmenu()
        menu = menu_cls(self.main_window)

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
                    raw_text = self.log_model.get_line_text(real_idx).rstrip("\r\n")
                    selected_text = raw_text.strip()

        add_include_act = None
        add_exclude_act = None
        if selected_text:
            display_text = selected_text if len(selected_text) <= 30 else selected_text[:27] + "..."
            add_include_act = menu.addAction(f'Add as Include Filter: "{display_text}"')
            add_exclude_act = menu.addAction(f'Add as Exclude Filter: "{display_text}"')

        chosen_action = menu.exec_(self.log_view.viewport().mapToGlobal(position))

        if chosen_action:
            if chosen_action == add_include_act:
                self.main_window.add_quick_filter_from_text(selected_text, exclude=False)
            elif chosen_action == add_exclude_act:
                self.main_window.add_quick_filter_from_text(selected_text, exclude=True)

    def create_mode_indicator(self, label, text: str, active: bool, tooltip: str):
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

    def update_mode_indicators(self):
        if hasattr(self.main_window, "show_only_filtered_indicator") and hasattr(self.main_window, "log_model"):
            show_only_filtered = self.log_model.show_only_filtered
            self.create_mode_indicator(
                self.main_window.show_only_filtered_indicator,
                "Matches only" if show_only_filtered else "All lines",
                show_only_filtered,
                "Indicates whether the log view hides lines that do not match filters.",
            )

        if hasattr(self.main_window, "full_line_display_indicator"):
            self.create_mode_indicator(
                self.main_window.full_line_display_indicator,
                "Full lines" if self.full_line_display_enabled else "Compact lines",
                self.full_line_display_enabled,
                "Indicates whether long lines are shown at full width or in compact mode.",
            )
