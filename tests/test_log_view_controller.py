import os
import sys
import unittest
from unittest.mock import Mock, patch

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loganalysis_gui.main_window import LogAnalysisMainWindow
from loganalysis_gui.log_view_controller import LogViewController

app = QApplication.instance() or QApplication(sys.argv)


class LogViewControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = LogAnalysisMainWindow()
        self.controller = self.window.log_view_controller

    def tearDown(self):
        self.window.close()
        app.processEvents()

    def test_toggle_full_line_display_updates_column_width_and_action(self):
        self.controller.toggle_full_line_display(True)
        self.assertTrue(self.window.full_line_display_enabled)
        self.assertTrue(self.window.full_line_display_action.isChecked())

        self.controller.toggle_full_line_display(False)
        self.assertFalse(self.window.full_line_display_enabled)
        self.assertFalse(self.window.full_line_display_action.isChecked())

    def test_zoom_log_modifies_font_size(self):
        initial_size = self.window.log_model.font.pointSize()
        self.controller.zoom_log(2)
        self.assertEqual(self.window.log_model.font.pointSize(), initial_size + 2)

        self.controller.zoom_log(-1)
        self.assertEqual(self.window.log_model.font.pointSize(), initial_size + 1)

    def test_toggle_line_numbers_updates_model_setting(self):
        self.assertTrue(self.window.log_model.show_line_numbers)
        self.controller.toggle_line_numbers(False)
        self.assertFalse(self.window.log_model.show_line_numbers)

        self.controller.toggle_line_numbers(True)
        self.assertTrue(self.window.log_model.show_line_numbers)

    def test_copy_selection_copies_selected_lines(self):
        self.window.log_model.set_lines(["alpha line\n", "beta line\n"])
        self.window.log_model.update_visible_indices([0, 1])

        # Select first row
        index_obj = self.window.log_model.index(0, 0)
        self.window.log_view.setCurrentIndex(index_obj)
        self.window.log_view.selectionModel().select(
            index_obj,
            self.window.log_view.selectionModel().ClearAndSelect | self.window.log_view.selectionModel().Rows,
        )
        self.controller.copy_selection()

        clipboard = QApplication.clipboard()
        self.assertIn("alpha line", clipboard.text())


if __name__ == "__main__":
    unittest.main()
