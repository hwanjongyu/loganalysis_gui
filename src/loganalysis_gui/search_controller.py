import re
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView

from .constants import ASYNC_SEARCH_THRESHOLD
from .dialogs import FindDialog
from .workers import SearchWorker


class SearchController:
    """Manages FindDialog interaction, text/regex search navigation, and highlights."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.search_thread: Optional[SearchWorker] = None
        self.search_request_id: int = 0

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

    def stop_search(self):
        thread = self.search_thread
        self.search_thread = None
        if thread is not None:
            try:
                if hasattr(thread, "stop"):
                    thread.stop()
                if hasattr(thread, "isRunning") and thread.isRunning():
                    thread.wait(500)
            except RuntimeError:
                pass

    def find_in_files(
        self,
        text: str,
        forward: bool = True,
        case: bool = False,
        regex: bool = False,
        async_search: Optional[bool] = None,
    ):
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

        use_async = (
            async_search if async_search is not None else (total > ASYNC_SEARCH_THRESHOLD)
        )

        current_row = self.log_view.currentIndex().row()

        if not use_async:
            self._find_inline(text, forward, case, regex, total, current_row)
        else:
            self._find_async(text, forward, case, regex, current_row)

    def _find_inline(
        self,
        text: str,
        forward: bool,
        case: bool,
        regex: bool,
        total: int,
        current_row: int,
    ):
        model = self.log_model
        visited_count = 0
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

    def _find_async(
        self,
        text: str,
        forward: bool,
        case: bool,
        regex: bool,
        current_row: int,
    ):
        self.stop_search()
        self.search_request_id += 1
        req_id = self.search_request_id

        if self.find_dialog:
            self.find_dialog.set_status("Searching...")
        self.status_bar.showMessage("Searching...", 0)

        lines_snapshot = self.log_model.all_lines[:]
        indices_snapshot = self.log_model.visible_indices[:]

        worker = SearchWorker(
            lines=lines_snapshot,
            visible_indices=indices_snapshot,
            pattern=text,
            forward=forward,
            case=case,
            regex=regex,
            start_row=current_row,
            request_id=req_id,
        )
        self.search_thread = worker
        if hasattr(self.main_window, "_track_worker"):
            self.main_window._track_worker(worker)

        worker.match_found.connect(self.on_search_match_found)
        worker.match_not_found.connect(self.on_search_match_not_found)
        worker.search_failed.connect(self.on_search_failed)
        worker.progress_updated.connect(self.on_search_progress)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def on_search_match_found(self, req_id: int, idx: int, real_idx: int):
        if req_id != self.search_request_id:
            return
        model = self.log_model
        if 0 <= idx < model.rowCount():
            index_obj = model.index(idx, 0)
            self.log_view.setCurrentIndex(index_obj)
            self.log_view.scrollTo(index_obj, QAbstractItemView.PositionAtCenter)
        if self.find_dialog:
            self.find_dialog.set_status("")
        self.status_bar.showMessage("Match found.", 2000)

    def on_search_match_not_found(self, req_id: int):
        if req_id != self.search_request_id:
            return
        if self.find_dialog:
            self.find_dialog.set_status("Not found")
        self.status_bar.showMessage("Not found.", 3000)

    def on_search_failed(self, req_id: int, error_msg: str):
        if req_id != self.search_request_id:
            return
        msg = f"Search error: {error_msg}"
        if self.find_dialog:
            self.find_dialog.set_status(msg)
        self.status_bar.showMessage(msg, 5000)

    def on_search_progress(self, req_id: int, visited: int, total: int):
        if req_id != self.search_request_id:
            return
        pct = int(visited * 100 / max(total, 1))
        msg = f"Searching... ({pct}%)"
        if self.find_dialog:
            self.find_dialog.set_status(msg)
        self.status_bar.showMessage(msg, 0)

