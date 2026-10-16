import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loganalysis_gui.workers import FileLoadWorker


class FileLoadWorkerTests(unittest.TestCase):
    def test_reads_lines_and_reports_progress(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(b"alpha\nbeta\r\ngamma")
            file_path = handle.name

        try:
            progress_events = []
            completions = []
            worker = FileLoadWorker(file_path, 7, chunk_size=4, progress_step=4)
            worker.progress_updated.connect(lambda *args: progress_events.append(args))
            worker.finished_loading.connect(lambda *args: completions.append(args))

            worker.run()

            self.assertGreaterEqual(len(progress_events), 2)
            self.assertEqual(progress_events[-1], (7, file_path, 17, 17, 3))
            self.assertEqual(completions[0], (7, file_path, [b"alpha\n", b"beta\r\n", b"gamma"], "alpha"))
        finally:
            os.unlink(file_path)

    def test_file_load_worker_computes_longest_line(self):
        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write(b"short\nvery long line with trailing padding    \r\nmedium line\n")
            file_path = handle.name

        try:
            completions = []
            worker = FileLoadWorker(file_path, 9)
            worker.finished_loading.connect(lambda *args: completions.append(args))
            worker.run()

            self.assertEqual(len(completions), 1)
            req_id, path, lines, longest_line = completions[0]
            self.assertEqual(req_id, 9)
            self.assertEqual(len(lines), 3)
            # measured_log_line_text strips trailing whitespace and crlf
            self.assertEqual(longest_line, "very long line with trailing padding")
        finally:
            os.unlink(file_path)

    def test_reports_missing_file(self):
        file_path = os.path.join(tempfile.gettempdir(), "missing-loganalysis-gui-test.log")
        if os.path.exists(file_path):
            os.unlink(file_path)

        errors = []
        worker = FileLoadWorker(file_path, 3)
        worker.load_failed.connect(lambda *args: errors.append(args))

        worker.run()

        self.assertEqual(errors, [(3, file_path, "File not found.")])

    def test_adb_worker_serial_targeting(self):
        from loganalysis_gui.workers import AdbWorker
        worker = AdbWorker(device_serial="test-serial-1234")
        self.assertEqual(worker.device_serial, "test-serial-1234")


    def test_filter_worker_handles_exception_safely(self):
        from loganalysis_gui.workers import FilterWorker
        # Pass None as self.lines to trigger a TypeError inside run()
        worker = FilterWorker(None, [], True, 42)
        
        failures = []
        worker.filtering_failed.connect(lambda *args: failures.append(args))
        
        worker.run()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][0], 42)
        self.assertIn("NoneType", failures[0][1])

    def test_adb_worker_validates_serial_characters(self):
        from loganalysis_gui.workers import AdbWorker
        worker = AdbWorker(device_serial="invalid; serial & injection")
        
        errors = []
        worker.error_occurred.connect(lambda *args: errors.append(args))
        
        worker.run()
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid characters in device serial", errors[0][0])

    def test_adb_worker_rejects_leading_hyphen_in_serial(self):
        from loganalysis_gui.workers import AdbWorker
        worker = AdbWorker(device_serial="-s_some_flag")
        
        errors = []
        worker.error_occurred.connect(lambda *args: errors.append(args))
        
        worker.run()
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid characters in device serial", errors[0][0])

    def test_search_worker_forward_and_backward(self):
        from loganalysis_gui.workers import SearchWorker
        lines = ["first apple\n", "banana\n", "second apple\n"]
        indices = [0, 1, 2]

        # Forward from index 0
        matches = []
        worker = SearchWorker(lines, indices, "apple", forward=True, start_row=0, request_id=1)
        worker.match_found.connect(lambda req, idx, real: matches.append((req, idx, real)))
        worker.run()
        self.assertEqual(matches, [(1, 2, 2)])

        # Backward from index 2
        matches.clear()
        worker = SearchWorker(lines, indices, "apple", forward=False, start_row=2, request_id=2)
        worker.match_found.connect(lambda req, idx, real: matches.append((req, idx, real)))
        worker.run()
        self.assertEqual(matches, [(2, 0, 0)])

    def test_search_worker_supports_regex_and_case_and_bytes(self):
        from loganalysis_gui.workers import SearchWorker
        lines = [b"DEBUG item\n", "INFO Item\n", b"ERROR ITEM\n"]
        indices = [0, 1, 2]

        # Case-sensitive regex
        matches = []
        worker = SearchWorker(lines, indices, r"ERROR\s+ITEM", forward=True, case=True, regex=True, request_id=3)
        worker.match_found.connect(lambda req, idx, real: matches.append((req, idx, real)))
        worker.run()
        self.assertEqual(matches, [(3, 2, 2)])

        # Case-insensitive plain text on byte line
        matches.clear()
        worker = SearchWorker(lines, indices, "debug", forward=True, case=False, regex=False, request_id=4)
        worker.match_found.connect(lambda req, idx, real: matches.append((req, idx, real)))
        worker.run()
        self.assertEqual(matches, [(4, 0, 0)])

    def test_search_worker_not_found_and_cancellation(self):
        from loganalysis_gui.workers import SearchWorker
        lines = ["line 1\n", "line 2\n"]
        indices = [0, 1]

        not_found = []
        worker = SearchWorker(lines, indices, "nonexistent", forward=True, request_id=5)
        worker.match_not_found.connect(lambda req: not_found.append(req))
        worker.run()
        self.assertEqual(not_found, [5])

        # Test cancellation before run
        worker = SearchWorker(lines, indices, "line", forward=True, request_id=6)
        worker.stop()
        matches = []
        worker.match_found.connect(lambda req, idx, real: matches.append((req, idx, real)))
        worker.run()
        self.assertEqual(matches, [])

    def test_adb_device_scan_worker_parses_devices(self):
        from unittest.mock import patch
        from loganalysis_gui.workers import AdbDeviceScanWorker

        mock_output = "List of devices attached\nemulator-5554\tdevice\nserial123\tdevice\nunauthorized-device\tunauthorized\n\n"
        with patch("subprocess.check_output", return_value=mock_output):
            worker = AdbDeviceScanWorker(request_id=10)
            results = []
            worker.devices_found.connect(lambda req, devs: results.append((req, devs)))
            worker.run()

            self.assertEqual(results, [(10, ["emulator-5554", "serial123"])])

    def test_adb_device_scan_worker_handles_timeout_and_missing(self):
        import subprocess
        from unittest.mock import patch
        from loganalysis_gui.workers import AdbDeviceScanWorker

        with patch("subprocess.check_output", side_effect=subprocess.TimeoutExpired(cmd="adb", timeout=3.0)):
            worker = AdbDeviceScanWorker(request_id=11)
            errors = []
            worker.scan_failed.connect(lambda req, reason: errors.append((req, reason)))
            worker.run()
            self.assertEqual(errors, [(11, "timeout")])

        with patch("subprocess.check_output", side_effect=FileNotFoundError()):
            worker = AdbDeviceScanWorker(request_id=12)
            errors.clear()
            worker.scan_failed.connect(lambda req, reason: errors.append((req, reason)))
            worker.run()
            self.assertEqual(errors, [(12, "not_found")])

    def test_filter_worker_precomputes_visible_styles(self):
        from loganalysis_gui.workers import FilterWorker
        lines = ["error line\n", "normal line\n", "warning line\n"]
        filters = [
            {"text": "error", "regex": False, "case_sensitive": False, "bg_color": "Red", "text_color": "White", "exclude": False, "active": True},
            {"text": "warning", "regex": False, "case_sensitive": False, "bg_color": "Yellow", "text_color": "Black", "exclude": False, "active": True},
        ]
        worker = FilterWorker(lines, filters, show_only_filtered=False, request_id=20)
        results = []
        worker.finished_filtering.connect(lambda *args: results.append(args))
        worker.run()

        self.assertEqual(len(results), 1)
        req_id, indices, match_count, f_counts, widest_text, styles = results[0]
        self.assertEqual(req_id, 20)
        self.assertEqual(indices, [0, 1, 2])
        self.assertEqual(len(styles), 3)
        # Red bg, White text for row 0
        self.assertEqual(styles[0], ("#FFB6B6", "#FFFFFF"))
        # No filter matched for row 1 -> default grey text
        self.assertEqual(styles[1], (None, "#808080"))
        # Yellow bg, Black text for row 2
        self.assertEqual(styles[2], ("#FFFF00", "#000000"))

    def test_log_model_uses_precomputed_styles_without_dynamic_evaluation(self):
        from loganalysis_gui.models import LogModel
        from PyQt5.QtCore import Qt

        model = LogModel()
        model.set_lines(["line 0\n", "line 1\n"])
        # Set precomputed styles directly
        model.update_visible_indices([0, 1], widest_visible_text="line 0", visible_styles=[("#FFFF00", "#000000"), (None, "#808080")])

        # Style cache should remain empty because precomputed styles are used
        bg_0 = model.data(model.index(0, 0), Qt.BackgroundRole)
        fg_0 = model.data(model.index(0, 0), Qt.ForegroundRole)
        self.assertEqual(bg_0.name().upper(), "#FFFF00")
        self.assertEqual(fg_0.name().upper(), "#000000")
        self.assertEqual(len(model._style_cache), 0)


if __name__ == "__main__":
    unittest.main()


