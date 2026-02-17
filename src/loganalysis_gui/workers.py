import re
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal

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
        if self.process:
            try:
                self.process.terminate()
                self.process.kill()
            except:
                pass
            self.process = None


class FilterWorker(QThread):
    finished_filtering = pyqtSignal(list, int, list)
    
    def __init__(self, lines, filters, show_only_filtered):
        super().__init__()
        self.lines = lines
        self.filters = filters
        self.show_only_filtered = show_only_filtered
        self.is_running = True

    def run(self):
        visible_indices = []
        match_count = 0
        
        # Initialize counts for ALL filters passed in
        filter_counts = [0] * len(self.filters)
        
        # Pre-compile active filters for speed
        active_filters = []
        for i, f in enumerate(self.filters):
            if f.get("active", True):
                f_data = f.copy()
                f_data['original_index'] = i 
                if f["regex"]:
                    try:
                        flags = 0 if f["case_sensitive"] else re.IGNORECASE
                        f_data["compiled_re"] = re.compile(f["text"], flags)
                    except re.error:
                        f_data["compiled_re"] = None
                active_filters.append(f_data)

        count = len(self.lines)
        for i in range(count):
            if not self.is_running:
                return

            line = self.lines[i]
            
            # If no active filters, line is visible if NOT show_only_filtered
            # Consistent with append_chunk: show everything if no filters
            if not active_filters:
                visible_indices.append(i)
                continue

            this_line_matches = [] # list of original_indices that matched
            matched_decision = False
            
            # Visibility and Counting Pass
            # We must check all active filters to get accurate counts, 
            # but priority is reversed for the visibility decision.
            
            # Determine matches for all active filters
            for ftr in active_filters:
                is_match = False
                if ftr["regex"]:
                    if ftr["compiled_re"] and ftr["compiled_re"].search(line):
                        is_match = True
                else:
                    if ftr["case_sensitive"]:
                        if ftr["text"] in line:
                            is_match = True
                    else:
                        if ftr["text"].lower() in line.lower():
                            is_match = True
                
                if is_match:
                    filter_counts[ftr['original_index']] += 1
                    this_line_matches.append(ftr)
            
            # Decide visibility from the matches found (Highest index filter wins)
            if this_line_matches:
                # Iterate in reverse order of definition
                # ftr is from active_filters which is sorted by original index
                for ftr in reversed(this_line_matches):
                    if ftr["exclude"]:
                        matched_decision = False
                        break # Exclude wins priority
                    else:
                        matched_decision = True
                        break # Include wins priority
            
            if matched_decision:
                match_count += 1
                visible_indices.append(i)
            elif not self.show_only_filtered:
                visible_indices.append(i)
        
        self.finished_filtering.emit(visible_indices, match_count, filter_counts)

    def stop(self):
        self.is_running = False
