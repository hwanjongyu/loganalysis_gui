import os
import sys
import unittest
from unittest.mock import Mock

from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loganalysis_gui.main_window import LogAnalysisMainWindow
from loganalysis_gui.search_controller import SearchController

app = QApplication.instance() or QApplication(sys.argv)


class DummyFindDialog:
    def __init__(self):
        self.status = ""
        self.shown = False

    def set_status(self, text):
        self.status = text

    def show(self):
        self.shown = True

    def raise_(self):
        pass

    def activateWindow(self):
        pass


class SearchControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = LogAnalysisMainWindow()
        self.controller = self.window.search_controller

    def tearDown(self):
        self.controller.stop_search()
        self.window.close()
        app.processEvents()

    def test_find_in_files_empty_text_does_nothing(self):
        self.window.log_model.set_lines(["alpha\n"])
        self.window.log_model.update_visible_indices([0])
        self.controller.find_dialog = DummyFindDialog()

        self.controller.find_in_files("")
        self.assertEqual(self.controller.find_dialog.status, "")
        self.assertEqual(self.window.log_view.currentIndex().row(), -1)

    def test_find_in_files_invalid_regex_reports_error(self):
        self.window.log_model.set_lines(["alpha\n"])
        self.window.log_model.update_visible_indices([0])
        self.controller.find_dialog = DummyFindDialog()

        self.controller.find_in_files("[invalid", regex=True)
        self.assertTrue(self.controller.find_dialog.status.startswith("Invalid regex:"))
        self.assertIn("Invalid regex:", self.window.status_bar.currentMessage())

    def test_find_in_files_async_mode_finds_match(self):
        self.window.log_model.set_lines(["first\n", "target line\n", "third\n"])
        self.window.log_model.update_visible_indices([0, 1, 2])
        self.controller.find_dialog = DummyFindDialog()

        # Force async_search=True
        self.controller.find_in_files("target", forward=True, async_search=True)
        self.assertIsNotNone(self.controller.search_thread)

        # Wait for thread completion
        if self.controller.search_thread.isRunning():
            self.controller.search_thread.wait(2000)
        app.processEvents()

        self.assertEqual(self.window.log_view.currentIndex().row(), 1)
        self.assertEqual(self.controller.find_dialog.status, "")
        self.assertEqual(self.window.status_bar.currentMessage(), "Match found.")

    def test_find_in_files_async_mode_reports_not_found(self):
        self.window.log_model.set_lines(["first\n", "second\n"])
        self.window.log_model.update_visible_indices([0, 1])
        self.controller.find_dialog = DummyFindDialog()

        self.controller.find_in_files("missing", forward=True, async_search=True)
        self.assertIsNotNone(self.controller.search_thread)

        if self.controller.search_thread.isRunning():
            self.controller.search_thread.wait(2000)
        app.processEvents()

        self.assertEqual(self.controller.find_dialog.status, "Not found")
        self.assertEqual(self.window.status_bar.currentMessage(), "Not found.")

    def test_stop_search_terminates_running_worker(self):
        self.window.log_model.set_lines([f"line {i}\n" for i in range(10000)])
        self.window.log_model.update_visible_indices(list(range(10000)))

        self.controller.find_in_files("target", async_search=True)
        worker = self.controller.search_thread
        self.assertIsNotNone(worker)

        self.controller.stop_search()
        self.assertIsNone(self.controller.search_thread)
        self.assertFalse(worker.is_running)


if __name__ == "__main__":
    unittest.main()
