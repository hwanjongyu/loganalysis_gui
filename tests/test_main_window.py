import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QApplication

from loganalysis_gui.dialogs import FilterDialog
from loganalysis_gui.main_window import LogAnalysisMainWindow


def make_filter(text, *, active=True):
    return {
        "text": text,
        "case_sensitive": False,
        "regex": False,
        "exclude": False,
        "bg_color": "None",
        "text_color": "None",
        "active": active,
    }


class DummyFindDialog:
    def __init__(self):
        self.status = None

    def set_status(self, text):
        self.status = text


class LogAnalysisMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = LogAnalysisMainWindow()

    def tearDown(self):
        self.window._stop_filter_worker()
        self.window._stop_adb_worker()
        self.window.deleteLater()
        self.app.processEvents()

    def wait_for_filtering(self):
        thread = self.window.filter_thread
        if thread is not None:
            thread.wait()
        self.app.processEvents()

    def expected_full_line_width(self, content):
        metrics = QFontMetrics(self.window.log_model.font)
        prefix = ""
        if self.window.log_model.show_line_numbers:
            max_line_number = max(len(self.window.log_model.all_lines), 1)
            prefix = f"{max_line_number:6d} | "

        return max(
            self.window.log_view.viewport().width(),
            metrics.horizontalAdvance(f"{prefix}{content}") + 24,
        )

    def test_full_line_display_starts_disabled(self):
        self.assertFalse(self.window.full_line_display_enabled)
        self.assertFalse(self.window.full_line_display_action.isChecked())
        self.assertEqual(self.window.log_view.textElideMode(), Qt.ElideRight)

    def test_disabled_tabs_do_not_reach_model_filters(self):
        self.window.add_filter_tab()
        self.window.filters[0].append(make_filter("alpha"))
        self.window.filters[1].append(make_filter("beta"))
        self.window.tab_enabled[1] = False

        self.window.apply_filters()

        self.assertEqual(
            [filter_data["text"] for filter_data in self.window.log_model.filters],
            ["alpha"],
        )

    def test_find_starts_from_first_row_without_selection(self):
        self.window.find_dialog = DummyFindDialog()
        self.window.log_model.set_lines(["alpha\n", "beta\n"])
        self.window.log_model.update_visible_indices([0, 1])

        self.window.find_in_files("alpha", forward=True)

        self.assertEqual(self.window.log_view.currentIndex().row(), 0)
        self.assertEqual(self.window.find_dialog.status, "")

    def test_tab_checkbox_stays_aligned_after_tab_deletion(self):
        self.window.add_filter_tab()

        self.window.filter_tabs.setCurrentIndex(0)
        self.window.delete_filter_tab()

        remaining_checkbox = self.window.tab_checkboxes[0]
        remaining_checkbox.setChecked(False)
        self.app.processEvents()

        self.assertEqual(self.window.tab_enabled, [False])

    def test_stale_filter_results_are_ignored(self):
        self.window.filter_request_id = 2
        self.window.log_model.set_lines(["alpha\n"])
        self.window.log_model.update_visible_indices([0])

        self.window.on_filtering_finished(1, [], 0, [0])

        self.assertEqual(self.window.log_model.visible_indices, [0])

    def test_stale_filter_width_candidate_is_ignored(self):
        self.window.toggle_full_line_display(True)
        self.window.filter_request_id = 2
        self.window.log_model.set_lines(["short\n", "other\n"])
        self.window.log_model.update_visible_indices([0], "short")
        self.window._update_log_column_width()

        expected_width = self.expected_full_line_width("short")
        self.window.on_filtering_finished(1, [1], 0, [0], "x" * 500)

        self.assertEqual(self.window.log_model.visible_indices, [0])
        self.assertEqual(self.window.log_view.header().sectionSize(0), expected_width)

    def test_live_chunks_buffer_during_refilter_and_flush_afterward(self):
        self.window.is_monitoring = True
        self.window.is_refiltering = True

        self.window.on_adb_chunk(["alpha\n"])
        self.assertEqual(self.window.pending_chunks, [["alpha\n"]])
        self.assertEqual(self.window.log_model.all_lines, [])

        self.window.is_refiltering = False
        self.window._flush_pending_chunks()

        self.assertEqual(self.window.pending_chunks, [])
        self.assertEqual(self.window.log_model.all_lines, ["alpha\n"])
        self.assertEqual(self.window.log_model.visible_indices, [0])

    def test_monitoring_trims_old_lines_after_limit(self):
        self.window.is_monitoring = True

        with patch("loganalysis_gui.main_window.MAX_MONITOR_LINES", 3), patch.object(
            self.window, "apply_filters"
        ) as apply_filters:
            self.window.on_adb_chunk(["1\n", "2\n", "3\n", "4\n"])

        apply_filters.assert_called_once()
        self.assertEqual(self.window.log_model.all_lines, ["2\n", "3\n", "4\n"])

    def test_compact_mode_keeps_column_at_viewport_width(self):
        self.window.on_adb_chunk(["x" * 500 + "\n"])

        self.assertEqual(self.window.log_view.textElideMode(), Qt.ElideRight)
        self.assertEqual(
            self.window.log_view.header().sectionSize(0),
            self.window.log_view.viewport().width(),
        )

    def test_view_menu_action_enables_full_line_display(self):
        initial_width = self.window.log_view.header().sectionSize(0)

        self.window.full_line_display_action.trigger()
        self.window.on_adb_chunk(["x" * 500 + "\n"])

        self.assertTrue(self.window.full_line_display_enabled)
        self.assertTrue(self.window.full_line_display_action.isChecked())
        self.assertEqual(self.window.log_view.textElideMode(), Qt.ElideNone)
        self.assertGreater(self.window.log_view.header().sectionSize(0), initial_width)

    def test_view_menu_action_restores_compact_mode(self):
        self.window.full_line_display_action.trigger()
        self.window.on_adb_chunk(["x" * 500 + "\n"])

        self.window.full_line_display_action.trigger()

        self.assertFalse(self.window.full_line_display_enabled)
        self.assertFalse(self.window.full_line_display_action.isChecked())
        self.assertEqual(self.window.log_view.textElideMode(), Qt.ElideRight)
        self.assertEqual(
            self.window.log_view.header().sectionSize(0),
            self.window.log_view.viewport().width(),
        )

    def test_column_width_ignores_trailing_padding(self):
        content = "value" * 100
        self.window.toggle_full_line_display(True)
        self.window.on_adb_chunk([content + (" " * 200) + "\n"])

        expected_width = self.expected_full_line_width(content)

        self.assertEqual(self.window.log_view.header().sectionSize(0), expected_width)

    def test_full_line_display_uses_widest_visible_filtered_line(self):
        hidden_line = "x" * 400
        visible_line = "keep"

        self.window.toggle_full_line_display(True)
        self.window.log_model.set_lines([f"{visible_line}\n", f"{hidden_line}\n"])
        self.window.filters[0].append(make_filter(visible_line))

        self.window.apply_filters()
        self.wait_for_filtering()

        self.assertEqual(self.window.log_model.visible_indices, [0])
        self.assertEqual(
            self.window.log_view.header().sectionSize(0),
            self.expected_full_line_width(visible_line),
        )

    def test_live_append_ignores_hidden_long_lines_for_full_line_width(self):
        visible_line = "keep visible"
        hidden_line = "x" * 500
        wider_visible_line = f"keep {'y' * 120}"

        self.window.toggle_full_line_display(True)
        self.window.filters[0].append(make_filter("keep"))
        self.window.log_model.set_lines([f"{visible_line}\n"])
        self.window.apply_filters()
        self.wait_for_filtering()

        initial_width = self.expected_full_line_width(visible_line)
        self.assertEqual(self.window.log_view.header().sectionSize(0), initial_width)

        self.window.on_adb_chunk([f"{hidden_line}\n"])
        self.assertEqual(self.window.log_view.header().sectionSize(0), initial_width)

        self.window.on_adb_chunk([f"{wider_visible_line}\n"])
        self.assertEqual(
            self.window.log_view.header().sectionSize(0),
            self.expected_full_line_width(wider_visible_line),
        )

    def test_append_chunk_uses_last_matching_filter_precedence(self):
        include_filter = make_filter("alpha")
        exclude_filter = make_filter("alpha")
        exclude_filter["exclude"] = True

        self.window.log_model.filters = [include_filter, exclude_filter]
        self.window.log_model.append_chunk(["alpha\n"])
        self.assertEqual(self.window.log_model.visible_indices, [])

        self.window.log_model.clear()
        self.window.log_model.filters = [exclude_filter, include_filter]
        self.window.log_model.append_chunk(["alpha\n"])
        self.assertEqual(self.window.log_model.visible_indices, [0])

    def test_invalid_find_regex_sets_status(self):
        self.window.find_dialog = DummyFindDialog()
        self.window.find_in_files("(", regex=True)

        self.assertTrue(self.window.find_dialog.status.startswith("Invalid regex:"))
        self.assertFalse(self.window.log_view.currentIndex().isValid())

    def test_invalid_quick_filter_is_rejected(self):
        self.window.quick_input.setText("(")
        self.window.quick_regex.setChecked(True)

        with patch("loganalysis_gui.main_window.QMessageBox.warning") as warning:
            self.window.add_quick_filter()

        warning.assert_called_once()
        self.assertEqual(self.window.filters[0], [])

    def test_filter_dialog_rejects_invalid_regex(self):
        dialog = FilterDialog(self.window)
        dialog.text_input.setText("(")
        dialog.regex.setChecked(True)

        with patch("loganalysis_gui.dialogs.QMessageBox.warning") as warning:
            dialog.accept()

        warning.assert_called_once()
        self.assertEqual(dialog.result(), 0)

    def test_load_filters_rejects_invalid_regex_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"filters": [{"text": "(", "regex": True}]}, handle)
            filter_path = handle.name

        try:
            with patch(
                "loganalysis_gui.main_window.QFileDialog.getOpenFileName",
                return_value=(filter_path, ""),
            ), patch("loganalysis_gui.main_window.QMessageBox.warning") as warning:
                self.window.load_filters()

            warning.assert_called_once()
            self.assertEqual(self.window.filters[0], [])
        finally:
            os.unlink(filter_path)

    def test_save_and_load_filters_round_trip(self):
        filter_data = make_filter("alpha.*", active=False)
        filter_data.update(
            {
                "case_sensitive": True,
                "regex": True,
                "exclude": True,
                "bg_color": "Yellow",
                "text_color": "Black",
            }
        )
        self.window.filters[0].append(filter_data)
        self.window.tab_enabled[0] = False
        self.window.tab_checkboxes[0].blockSignals(True)
        self.window.tab_checkboxes[0].setChecked(False)
        self.window.tab_checkboxes[0].blockSignals(False)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            filter_path = handle.name

        try:
            self.window._do_save(0, filter_path)
            self.window.filters[0].clear()
            self.window.filter_tab_lists[0].clear()
            self.window.tab_enabled[0] = True
            self.window.tab_checkboxes[0].blockSignals(True)
            self.window.tab_checkboxes[0].setChecked(True)
            self.window.tab_checkboxes[0].blockSignals(False)

            with patch(
                "loganalysis_gui.main_window.QFileDialog.getOpenFileName",
                return_value=(filter_path, ""),
            ):
                self.window.load_filters()

            loaded_filter = self.window.filters[0][0]
            self.assertEqual(loaded_filter["text"], "alpha.*")
            self.assertTrue(loaded_filter["case_sensitive"])
            self.assertTrue(loaded_filter["regex"])
            self.assertTrue(loaded_filter["exclude"])
            self.assertEqual(loaded_filter["bg_color"], "Yellow")
            self.assertEqual(loaded_filter["text_color"], "Black")
            self.assertFalse(loaded_filter["active"])
            self.assertFalse(self.window.tab_enabled[0])
        finally:
            os.unlink(filter_path)


if __name__ == "__main__":
    unittest.main()
