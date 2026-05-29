import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from PyQt5.QtCore import QPoint, Qt
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
        self.window._cancel_file_load()
        self.window._stop_filter_worker()
        self.window._stop_adb_worker()
        self.window.deleteLater()
        self.app.processEvents()

    def tab_state(self, index=0):
        return self.window._tab_state(index)

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

    def add_filter_item(self, filter_data, *, index=0):
        tab_state = self.tab_state(index)
        self.window._insert_filter_item(tab_state, filter_data)
        return tab_state.filter_list.item(tab_state.filter_list.count() - 1)

    def test_full_line_display_starts_disabled(self):
        self.assertFalse(self.window.full_line_display_enabled)
        self.assertFalse(self.window.full_line_display_action.isChecked())
        self.assertEqual(self.window.log_view.textElideMode(), Qt.ElideRight)

    def test_filter_tab_contains_search_box(self):
        tab_state = self.tab_state(0)

        self.assertEqual(tab_state.search_input.placeholderText(), "Search filters in this tab...")
        self.assertIs(self.window.filter_tabs.widget(0), tab_state.tab_widget)

    def test_filter_search_hides_non_matching_items_without_changing_filters(self):
        alpha_item = self.add_filter_item(make_filter("alpha"))
        beta_item = self.add_filter_item(make_filter("beta"))

        self.tab_state(0).search_input.setText("alp")
        self.app.processEvents()

        self.assertFalse(alpha_item.isHidden())
        self.assertTrue(beta_item.isHidden())
        self.assertEqual([item["text"] for item in self.tab_state(0).filters], ["alpha", "beta"])

    def test_mode_indicators_track_show_only_filtered_and_full_line_display(self):
        self.assertEqual(self.window.show_only_filtered_indicator.text(), "Matches only")
        self.assertEqual(self.window.full_line_display_indicator.text(), "Compact lines")

        self.window.show_only_filtered_action.setChecked(False)
        self.window.full_line_display_action.setChecked(True)

        self.assertEqual(self.window.show_only_filtered_indicator.text(), "All lines")
        self.assertEqual(self.window.full_line_display_indicator.text(), "Full lines")

    def test_disabled_tabs_do_not_reach_model_filters(self):
        self.window.add_filter_tab()
        self.tab_state(0).filters.append(make_filter("alpha"))
        self.tab_state(1).filters.append(make_filter("beta"))
        self.tab_state(1).enabled = False

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

        remaining_checkbox = self.tab_state(0).checkbox
        remaining_checkbox.setChecked(False)
        self.app.processEvents()

        self.assertFalse(self.tab_state(0).enabled)

    def test_delete_filter_tab_stops_active_filter_worker(self):
        self.window.add_filter_tab()
        self.tab_state(0).filters.append(make_filter("alpha"))
        self.tab_state(1).filters.append(make_filter("beta"))

        active_worker = Mock()
        active_worker.isRunning.return_value = True
        self.window.filter_thread = active_worker

        self.window.filter_tabs.setCurrentIndex(0)
        self.window.delete_filter_tab()

        active_worker.stop.assert_called_once()
        active_worker.wait.assert_called_once()
        self.assertEqual(len(self.window.filter_tab_states), 1)
        self.assertEqual(self.tab_state(0).filters[0]["text"], "beta")
        self.assertEqual(self.tab_state(0).checkbox.property("tab_index"), 0)

    def test_stale_filter_results_are_ignored(self):
        self.window.runtime.filter_request_id = 2
        self.window.log_model.set_lines(["alpha\n"])
        self.window.log_model.update_visible_indices([0])

        self.window.on_filtering_finished(1, [], 0, [0])

        self.assertEqual(self.window.log_model.visible_indices, [0])

    def test_file_load_progress_updates_status_and_progress_bar(self):
        self.window.runtime.file_load_request_id = 1
        self.window.runtime.is_loading_file = True

        self.window.on_file_load_progress(1, "/tmp/sample.log", 50, 100, 12)

        self.assertFalse(self.window.file_load_progress.isHidden())
        self.assertEqual(self.window.file_load_progress.value(), 50)
        self.assertEqual(self.window.file_load_progress.format(), "50%")
        self.assertEqual(
            self.window.status_bar.currentMessage(),
            "Loading sample.log... 50% (12 lines)",
        )

    def test_stale_file_load_result_is_ignored(self):
        self.window.runtime.file_load_request_id = 2
        self.window.runtime.is_loading_file = True
        self.window.log_model.set_lines(["current\n"])

        self.window.on_file_loaded(1, "/tmp/new.log", ["new\n"])

        self.assertEqual(self.window.log_model.all_lines, ["current\n"])
        self.assertTrue(self.window.runtime.is_loading_file)

    def test_file_load_completion_updates_model_and_status(self):
        self.window.runtime.file_load_request_id = 1
        self.window.runtime.is_loading_file = True
        self.window.runtime.loading_file_path = "/tmp/sample.log"
        self.window.file_load_progress.setVisible(True)

        self.window.on_file_loaded(1, "/tmp/sample.log", ["alpha\n", "beta\n"])
        self.wait_for_filtering()

        self.assertEqual(self.window.log_model.all_lines, ["alpha\n", "beta\n"])
        self.assertFalse(self.window.runtime.is_loading_file)
        self.assertTrue(self.window.file_load_progress.isHidden())
        self.assertEqual(self.window.loaded_file_label.text(), "File: sample.log")
        self.assertEqual(self.window.loaded_file_label.toolTip(), "/tmp/sample.log")
        self.assertEqual(
            self.window.status_bar.currentMessage(),
            "Loaded: /tmp/sample.log (2 lines)",
        )

    def test_loaded_file_label_persists_after_refilter_status_changes(self):
        self.window.runtime.file_load_request_id = 1
        self.window.runtime.is_loading_file = True

        self.window.on_file_loaded(1, "/tmp/sample.log", ["alpha\n", "beta\n"])
        self.wait_for_filtering()
        self.window.apply_filters()
        self.wait_for_filtering()

        self.assertEqual(self.window.status_bar.currentMessage(), "Refiltered complete.")
        self.assertEqual(self.window.loaded_file_label.text(), "File: sample.log")
        self.assertEqual(self.window.loaded_file_label.toolTip(), "/tmp/sample.log")

    def test_file_load_error_preserves_current_lines(self):
        self.window.log_model.set_lines(["current\n"])
        self.window.runtime.file_load_request_id = 1
        self.window.runtime.is_loading_file = True
        self.window.file_load_progress.setVisible(True)

        with patch("loganalysis_gui.main_window.QMessageBox.warning") as warning:
            self.window.on_file_load_failed(1, "/tmp/missing.log", "File not found.")

        warning.assert_called_once()
        self.assertEqual(self.window.log_model.all_lines, ["current\n"])
        self.assertFalse(self.window.runtime.is_loading_file)
        self.assertTrue(self.window.file_load_progress.isHidden())
        self.assertEqual(
            self.window.status_bar.currentMessage(),
            "Error loading file: File not found.",
        )

    def test_clear_logs_cancels_active_file_load(self):
        active_worker = Mock()
        active_worker.isRunning.return_value = True
        self.window.file_load_thread = active_worker
        self.window.runtime.is_loading_file = True
        self.window.file_load_progress.setVisible(True)

        self.window.clear_logs()

        active_worker.stop.assert_called_once()
        active_worker.wait.assert_called_once()
        self.assertIsNone(self.window.file_load_thread)
        self.assertFalse(self.window.runtime.is_loading_file)
        self.assertTrue(self.window.file_load_progress.isHidden())
        self.assertTrue(self.window.loaded_file_label.isHidden())

    def test_stale_filter_width_candidate_is_ignored(self):
        self.window.toggle_full_line_display(True)
        self.window.runtime.filter_request_id = 2
        self.window.log_model.set_lines(["short\n", "other\n"])
        self.window.log_model.update_visible_indices([0], "short")
        self.window._update_log_column_width()

        expected_width = self.expected_full_line_width("short")
        self.window.on_filtering_finished(1, [1], 0, [0], "x" * 500)

        self.assertEqual(self.window.log_model.visible_indices, [0])
        self.assertEqual(self.window.log_view.header().sectionSize(0), expected_width)

    def test_live_chunks_buffer_during_refilter_and_flush_afterward(self):
        self.window.runtime.is_monitoring = True
        self.window.runtime.is_refiltering = True

        self.window.on_adb_chunk(["alpha\n"])
        self.assertEqual(self.window.runtime.pending_chunks, [["alpha\n"]])
        self.assertEqual(self.window.log_model.all_lines, [])

        self.window.runtime.is_refiltering = False
        self.window._flush_pending_chunks()

        self.assertEqual(self.window.runtime.pending_chunks, [])
        self.assertEqual(self.window.log_model.all_lines, ["alpha\n"])
        self.assertEqual(self.window.log_model.visible_indices, [0])

    def test_monitoring_trims_old_lines_after_limit(self):
        self.window.runtime.is_monitoring = True

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
        self.tab_state(0).filters.append(make_filter(visible_line))

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
        self.tab_state(0).filters.append(make_filter("keep"))
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

    def test_duplicate_filter_item_inserts_copy_after_source(self):
        source_item = self.add_filter_item(make_filter("alpha"))
        tab_state = self.tab_state(0)

        self.window._duplicate_filter_item(tab_state, source_item)

        self.assertEqual([item["text"] for item in tab_state.filters], ["alpha", "alpha"])
        self.assertIsNot(tab_state.filters[0], tab_state.filters[1])
        self.assertEqual(tab_state.filter_list.currentRow(), 1)

    def test_copy_filter_pattern_places_text_on_clipboard(self):
        source_item = self.add_filter_item(make_filter("alpha"))

        self.window._copy_filter_pattern(self.tab_state(0), source_item)

        self.assertEqual(self.app.clipboard().text(), "alpha")

    def test_delete_filter_items_removes_selected_rows(self):
        first_item = self.add_filter_item(make_filter("alpha"))
        second_item = self.add_filter_item(make_filter("beta"))
        tab_state = self.tab_state(0)
        first_item.setSelected(True)
        second_item.setSelected(True)

        self.window._delete_filter_items(tab_state, [first_item, second_item])

        self.assertEqual(tab_state.filter_list.count(), 0)
        self.assertEqual(tab_state.filters, [])

    def test_filter_context_menu_delete_uses_clicked_item(self):
        self.add_filter_item(make_filter("alpha"))
        second_item = self.add_filter_item(make_filter("beta"))
        tab_state = self.tab_state(0)
        second_rect = tab_state.filter_list.visualItemRect(second_item)

        class FakeAction:
            def __init__(self, text):
                self._text = text

            def text(self):
                return self._text

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                self._actions = []

            def addAction(self, text):
                action = FakeAction(text)
                self._actions.append(action)
                return action

            def exec_(self, *_args, **_kwargs):
                return next(action for action in self._actions if action.text() == "Delete")

        with patch.object(tab_state.filter_list, "mapToGlobal", return_value=QPoint(5, 5)), patch(
            "loganalysis_gui.main_window.QMenu",
            FakeMenu,
        ):
            self.window._show_filter_context_menu(tab_state, second_rect.center())

        self.assertEqual(tab_state.filter_list.count(), 1)
        self.assertEqual(tab_state.filters[0]["text"], "alpha")

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
        self.assertEqual(self.tab_state(0).filters, [])

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
            self.assertEqual(self.tab_state(0).filters, [])
        finally:
            os.unlink(filter_path)

    def test_load_filters_reports_invalid_json_and_keeps_existing_filters(self):
        self.tab_state(0).filters.append(make_filter("keep"))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{invalid json")
            filter_path = handle.name

        try:
            with patch(
                "loganalysis_gui.main_window.QFileDialog.getOpenFileName",
                return_value=(filter_path, ""),
            ), patch("loganalysis_gui.main_window.QMessageBox.warning") as warning:
                self.window.load_filters()

            warning.assert_called_once()
            self.assertEqual([item["text"] for item in self.tab_state(0).filters], ["keep"])
            self.assertEqual(
                self.window.status_bar.currentMessage(),
                "Error loading filters: invalid JSON file.",
            )
        finally:
            os.unlink(filter_path)

    def test_save_filters_reports_write_error_without_clearing_modified_state(self):
        tab_state = self.tab_state(0)
        tab_state.filters.append(make_filter("alpha"))
        self.window.set_tab_modified(0, True)

        with patch("builtins.open", side_effect=OSError("disk full")):
            self.window._do_save(0, "/tmp/filters.json")

        self.assertEqual(self.window.status_bar.currentMessage(), "Error saving filters: disk full")
        self.assertIsNone(tab_state.file_path)
        self.assertTrue(tab_state.modified)

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
        tab_state = self.tab_state(0)
        tab_state.filters.append(filter_data)
        tab_state.enabled = False
        tab_state.checkbox.blockSignals(True)
        tab_state.checkbox.setChecked(False)
        tab_state.checkbox.blockSignals(False)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            filter_path = handle.name

        try:
            self.window._do_save(0, filter_path)
            tab_state.filters.clear()
            tab_state.filter_list.clear()
            tab_state.enabled = True
            tab_state.checkbox.blockSignals(True)
            tab_state.checkbox.setChecked(True)
            tab_state.checkbox.blockSignals(False)

            with patch(
                "loganalysis_gui.main_window.QFileDialog.getOpenFileName",
                return_value=(filter_path, ""),
            ):
                self.window.load_filters()

            loaded_filter = self.tab_state(0).filters[0]
            self.assertEqual(loaded_filter["text"], "alpha.*")
            self.assertTrue(loaded_filter["case_sensitive"])
            self.assertTrue(loaded_filter["regex"])
            self.assertTrue(loaded_filter["exclude"])
            self.assertEqual(loaded_filter["bg_color"], "Yellow")
            self.assertEqual(loaded_filter["text_color"], "Black")
            self.assertFalse(loaded_filter["active"])
            self.assertFalse(self.tab_state(0).enabled)
        finally:
            os.unlink(filter_path)

    def test_soft_find_highlights_and_theme_sync(self):
        self.window.log_model.set_lines(["matching log line\n", "other log line\n"])
        self.window.log_model.update_visible_indices([0, 1])
        
        self.assertFalse(self.window.log_model.is_dark_theme)
        
        self.window.update_search_highlights("matching", case=False, regex=False)
        self.assertEqual(self.window.log_model.search_query, "matching")
        
        bg_matching = self.window.log_model.data(self.window.log_model.index(0, 0), Qt.BackgroundRole)
        bg_other = self.window.log_model.data(self.window.log_model.index(1, 0), Qt.BackgroundRole)
        
        self.assertEqual(bg_matching.name().upper(), "#FFF9C4")
        self.assertIsNone(bg_other)
        
        self.window.set_theme(light=False)
        self.assertTrue(self.window.log_model.is_dark_theme)
        
        bg_matching_dark = self.window.log_model.data(self.window.log_model.index(0, 0), Qt.BackgroundRole)
        self.assertEqual(bg_matching_dark.name().upper(), "#3E2723")
        
        self.window.clear_search_highlights()
        self.assertEqual(self.window.log_model.search_query, "")
        
        bg_cleared = self.window.log_model.data(self.window.log_model.index(0, 0), Qt.BackgroundRole)
        self.assertIsNone(bg_cleared)

    def test_filter_description_roundtrip_and_tooltip(self):
        filter_data = make_filter("pattern")
        filter_data["description"] = "Filter for pattern matching"
        
        item = self.add_filter_item(filter_data)
        tab_state = self.tab_state(0)
        
        normalized = self.window._normalize_filter_data(tab_state.filters[-1])
        self.assertEqual(normalized["description"], "Filter for pattern matching")
        
        widget = tab_state.filter_list.itemWidget(item)
        self.assertEqual(widget.toolTip(), "Filter for pattern matching")
        self.assertEqual(widget.text_label.toolTip(), "Filter for pattern matching")
        self.assertEqual(widget.desc_label.text(), " // Filter for pattern matching")
        self.assertFalse(widget.desc_label.isHidden())

    def test_filter_dialog_theme_aware_contrast_check(self):
        # Parent window set to Dark theme
        self.window.set_theme(light=False)
        dialog_dark = FilterDialog(self.window)
        # Select low contrast colors on dark theme
        dialog_dark.bg_color.setCurrentText("Gray")
        dialog_dark.text_color.setCurrentText("White")
        dialog_dark.check_contrast()
        self.assertTrue(any(word in (dialog_dark.contrast_lbl.text().lower() + dialog_dark.contrast_lbl.toolTip().lower()) for word in ["contrast", "poor", "warning"]))

        # Parent window set to Light theme
        self.window.set_theme(light=True)
        dialog_light = FilterDialog(self.window)
        # Select low contrast colors on light theme
        dialog_light.bg_color.setCurrentText("White")
        dialog_light.text_color.setCurrentText("White")
        dialog_light.check_contrast()
        self.assertTrue(any(word in (dialog_light.contrast_lbl.text().lower() + dialog_light.contrast_lbl.toolTip().lower()) for word in ["contrast", "poor", "warning"]))

    def test_log_view_custom_context_menu_include_filter(self):
        self.window.log_model.set_lines(["first log line\n", "second log line\n"])
        self.window.log_model.update_visible_indices([0, 1])

        # Selection of the first row
        index_obj = self.window.log_model.index(0, 0)
        self.window.log_view.setCurrentIndex(index_obj)
        self.window.log_view.selectionModel().select(
            index_obj,
            self.window.log_view.selectionModel().ClearAndSelect | self.window.log_view.selectionModel().Rows
        )

        # Trigger quick filter creation via helper directly
        self.window.add_quick_filter_from_text("first log line", exclude=False)

        # Assert that the filter is created correctly in the active tab state
        tab_state = self.tab_state(0)
        self.assertEqual(len(tab_state.filters), 1)
        self.assertEqual(tab_state.filters[0]["text"], "first log line")
        self.assertFalse(tab_state.filters[0]["exclude"])
        self.assertEqual(tab_state.filters[0]["description"], "Quick context filter")


if __name__ == "__main__":
    unittest.main()
