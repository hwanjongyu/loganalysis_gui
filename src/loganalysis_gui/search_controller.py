import re
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView

from .dialogs import FindDialog


class SearchController:
    """Manages FindDialog interaction, text/regex search navigation, and highlights."""

    def __init__(self, main_window):
        self.main_window = main_window

    @property
    def find_dialog(self) -> Optional[FindDialog]:
        return self.main_window.find_dialog

    @find_dialog.setter
    def find_dialog(self, val: Optional[FindDialog]):
        self.main_window.find_dialog = val

    @property
    def log_model(self):
        return self.main_window.log_model

    @property
    def log_view(self):
        return self.main_window.log_view

    @property
    def status_bar(self):
        return self.main_window.status_bar

    def show_find_dialog(self):
        if not self.find_dialog:
            self.find_dialog = FindDialog(self.main_window)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()

    def find_in_files(self, text: str, forward: bool = True, case: bool = False, regex: bool = False):
        if not text:
            return

        if regex:
            regex_error = self.main_window._regex_error(text, case)
            if regex_error:
                message = f"Invalid regex: {regex_error}"
                if self.find_dialog:
                    self.find_dialog.set_status(message)
                self.status_bar.showMessage(message, 5000)
                return

        model = self.log_model
        total = model.rowCount()
        if total == 0:
            return

        visited_count = 0
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
            line = model.get_line_text(real_idx)

            match = False
            if regex:
                flags = 0 if case else re.IGNORECASE
                if re.search(text, line, flags):
                    match = True
            else:
                if case:
                    if text in line:
                        match = True
                else:
                    if text.lower() in line.lower():
                        match = True

            if match:
                index_obj = model.index(idx, 0)
                self.log_view.setCurrentIndex(index_obj)
                self.log_view.scrollTo(index_obj, QAbstractItemView.PositionAtCenter)
                if self.find_dialog:
                    self.find_dialog.set_status("")
                return

            visited_count += 1

        if self.find_dialog:
            self.find_dialog.set_status("Not found")
