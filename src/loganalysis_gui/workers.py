import subprocess
from PyQt5.QtCore import QThread, pyqtSignal
from .filter_engine import evaluate_line, prepare_filters
from .models import measured_log_line_text

class AdbWorker(QThread):
    chunk_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.process = None

    def run(self):
        try:
            self.process = subprocess.Popen(
                ['adb', 'logcat', '-v', 'threadtime'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
            self.terminate_process()

    def stop(self):
        self.is_running = False
        self.terminate_process()
    
    def terminate_process(self):
        if not self.process:
            return

        process = self.process
        self.process = None

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
                if self.is_running:
                    self.error_occurred.emit(f"ADB Error: {error}")
        except OSError as error:
            if self.is_running:
                self.error_occurred.emit(f"ADB Error: {error}")


class FilterWorker(QThread):
    finished_filtering = pyqtSignal(int, list, int, list, str)
    
    def __init__(self, lines, filters, show_only_filtered, request_id):
        super().__init__()
        self.lines = lines
        self.filters = filters
        self.show_only_filtered = show_only_filtered
        self.request_id = request_id
        self.is_running = True

    def run(self):
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

    def stop(self):
        self.is_running = False
