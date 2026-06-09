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
            self.assertEqual(completions[0], (7, file_path, [b"alpha\n", b"beta\r\n", b"gamma"]))
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


if __name__ == "__main__":
    unittest.main()
