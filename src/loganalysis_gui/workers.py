import os
import re
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
from .filter_engine import evaluate_line, prepare_filters
from .models import measured_log_line_text


class FileLoadWorker(QThread):
    progress_updated = pyqtSignal(int, str, int, int, int)
    finished_loading = pyqtSignal(int, str, list, str)
    load_failed = pyqtSignal(int, str, str)

    def __init__(self, file_path, request_id, *, chunk_size=262144, progress_step=1048576):
        super().__init__()
        self.file_path = file_path
        self.request_id = request_id
        self.chunk_size = chunk_size
        self.progress_step = max(progress_step, 1)
        self.is_running = True

    def run(self):
        try:
            total_bytes = os.path.getsize(self.file_path)
            lines = []

            if total_bytes == 0:
                self.progress_updated.emit(
                    self.request_id,
                    self.file_path,
                    0,
                    0,
                    0,
                )
                self.finished_loading.emit(self.request_id, self.file_path, [], "")
                return

            bytes_read = 0
            next_progress_bytes = 0
            longest_line_text = ""
            max_line_len = 0

            with open(self.file_path, "rb") as handle:
                while self.is_running:
                    line_bytes = handle.readline()
                    if not line_bytes:
                        break

                    bytes_read += len(line_bytes)
                    lines.append(line_bytes)

                    if len(line_bytes) > max_line_len:
                        line_str = line_bytes.decode("utf-8", errors="replace")
                        measured = measured_log_line_text(line_str)
                        if len(measured) > max_line_len:
                            max_line_len = len(measured)
                            longest_line_text = measured

                    if bytes_read >= next_progress_bytes:
                        self.progress_updated.emit(
                            self.request_id,
                            self.file_path,
                            bytes_read,
                            total_bytes,
                            len(lines),
                        )
                        next_progress_bytes = bytes_read + self.progress_step

            if not self.is_running:
                return

            self.progress_updated.emit(
                self.request_id,
                self.file_path,
                total_bytes,
                total_bytes,
                len(lines),
            )
            self.finished_loading.emit(self.request_id, self.file_path, lines, longest_line_text)
        except FileNotFoundError:
            self.load_failed.emit(self.request_id, self.file_path, "File not found.")
        except OSError as error:
            self.load_failed.emit(self.request_id, self.file_path, str(error))

    def stop(self):
        self.is_running = False

class AdbWorker(QThread):
    chunk_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_serial=None):
        super().__init__()
        self.is_running = True
        self.process = None
        self.device_serial = device_serial

    def run(self):
        try:
            cmd = ['adb']
            if self.device_serial:
                if self.device_serial.startswith('-') or not all(c.isalnum() or c in '.-_:' for c in self.device_serial):
                    raise ValueError("Invalid characters in device serial.")
                cmd.extend(['-s', self.device_serial])
            cmd.extend(['logcat', '-v', 'threadtime'])

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True, 
                encoding='utf-8', 
                errors='replace'
            )
            proc = self.process
            
            buffer = []
            while self.is_running:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                
                if line:
                    buffer.append(line)
                
                if len(buffer) >= 100 or (buffer and not line):
                    self.chunk_ready.emit(buffer)
                    buffer = []
            
            if buffer:
                self.chunk_ready.emit(buffer)
                
        except FileNotFoundError:
            self.error_occurred.emit("ADB not found. Please ensure 'adb' is in your PATH.")
        except Exception as e:
            self.error_occurred.emit(f"ADB Error: {str(e)}")
        finally:
            self.cleanup_process()

    def stop(self):
        self.is_running = False
        proc = self.process
        if proc:
            try:
                proc.terminate()
            except (OSError, ProcessLookupError):
                pass

    def cleanup_process(self):
        process = self.process
        self.process = None
        if not process:
            return

        try:
            process.stdout.close()
        except Exception:
            pass

        if process.poll() is not None:
            return

        try:
            process.terminate()
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError) as error:
                self.error_occurred.emit(f"ADB cleanup error: {error}")
        except OSError as error:
            self.error_occurred.emit(f"ADB cleanup error: {error}")


class FilterWorker(QThread):
    finished_filtering = pyqtSignal(int, list, int, list, str)
    filtering_failed = pyqtSignal(int, str)
    
    def __init__(self, lines, filters, show_only_filtered, request_id):
        super().__init__()
        self.lines = lines
        self.filters = filters
        self.show_only_filtered = show_only_filtered
        self.request_id = request_id
        self.is_running = True

    def run(self):
        try:
            visible_indices = []
            match_count = 0
            widest_visible_text = ""
            widest_visible_length = 0
            
            # Initialize counts for ALL filters passed in
            filter_counts = [0] * len(self.filters)
            
            prepared_filters = prepare_filters(self.filters)

            count = len(self.lines)
            for i in range(count):
                if not self.is_running:
                    return

                line = self.lines[i]
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                matching_filters, is_visible = evaluate_line(
                    line,
                    prepared_filters,
                    self.show_only_filtered,
                )
                for matched_filter in matching_filters:
                    filter_counts[matched_filter.original_index] += 1

                if matching_filters and not matching_filters[-1].filter_data["exclude"]:
                    match_count += 1

                if is_visible:
                    visible_indices.append(i)
                    measured_text = measured_log_line_text(line)
                    measured_length = len(measured_text)
                    if measured_length > widest_visible_length:
                        widest_visible_length = measured_length
                        widest_visible_text = measured_text
            
            self.finished_filtering.emit(
                self.request_id,
                visible_indices,
                match_count,
                filter_counts,
                widest_visible_text,
            )
        except Exception as e:
            self.filtering_failed.emit(self.request_id, str(e))

    def stop(self):
        self.is_running = False


class SearchWorker(QThread):
    match_found = pyqtSignal(int, int, int)       # request_id, visible_index, real_index
    match_not_found = pyqtSignal(int)             # request_id
    search_failed = pyqtSignal(int, str)          # request_id, error_message
    progress_updated = pyqtSignal(int, int, int)  # request_id, checked_count, total_count

    def __init__(
        self,
        lines: list,
        visible_indices: list,
        pattern: str,
        forward: bool = True,
        case: bool = False,
        regex: bool = False,
        start_row: int = -1,
        request_id: int = 0,
    ):
        super().__init__()
        self.lines = lines
        self.visible_indices = visible_indices
        self.pattern = pattern
        self.forward = forward
        self.case = case
        self.regex = regex
        self.start_row = start_row
        self.request_id = request_id
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            total = len(self.visible_indices)
            if total == 0:
                self.match_not_found.emit(self.request_id)
                return

            if self.regex:
                flags = 0 if self.case else re.IGNORECASE
                compiled_regex = re.compile(self.pattern, flags)
                search_term = None
            else:
                compiled_regex = None
                search_term = self.pattern if self.case else self.pattern.lower()

            visited_count = 0
            if self.start_row < 0:
                idx = -1 if self.forward else 0
            else:
                idx = self.start_row

            while visited_count < total:
                if not self.is_running:
                    return

                if self.forward:
                    idx = (idx + 1) % total
                else:
                    idx = (idx - 1) % total

                real_idx = self.visible_indices[idx]
                raw_line = self.lines[real_idx]
                if isinstance(raw_line, bytes):
                    line_text = raw_line.decode("utf-8", errors="replace")
                else:
                    line_text = str(raw_line)

                match = False
                if compiled_regex:
                    if compiled_regex.search(line_text):
                        match = True
                else:
                    if self.case:
                        if search_term in line_text:
                            match = True
                    else:
                        if search_term in line_text.lower():
                            match = True

                if match:
                    self.match_found.emit(self.request_id, idx, real_idx)
                    return

                visited_count += 1
                if visited_count % 10000 == 0:
                    self.progress_updated.emit(self.request_id, visited_count, total)

            self.match_not_found.emit(self.request_id)
        except Exception as e:
            self.search_failed.emit(self.request_id, str(e))
