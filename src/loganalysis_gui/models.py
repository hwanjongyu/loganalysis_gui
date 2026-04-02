import re
from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex
from PyQt5.QtGui import QColor, QFont
from .constants import COLOR_MAP, TEXT_COLOR_MAP

class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_lines = [] 
        self.visible_indices = [] 
        self.filters = []
        self.show_line_numbers = True
        self.show_only_filtered = True
        self.font = QFont("Monospace", 10) # Default size 10
        self.max_line_length = 0
        self.longest_line_text = ""

    def _display_text(self, line_text):
        return line_text.rstrip('\r\n')

    def _measured_text(self, line_text):
        return self._display_text(line_text).rstrip()

    def _update_longest_line(self, lines):
        for line in lines:
            measured_text = self._measured_text(line)
            measured_length = len(measured_text)
            if measured_length > self.max_line_length:
                self.max_line_length = measured_length
                self.longest_line_text = measured_text
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.visible_indices)

    def data(self, index, role):
        if not index.isValid():
            return None
        
        row = index.row()
        if row >= len(self.visible_indices):
            return None
            
        real_idx = self.visible_indices[row]
        line_text = self.all_lines[real_idx]

        if role == Qt.DisplayRole:
            clean_text = self._display_text(line_text)
            if self.show_line_numbers:
                return f"{real_idx + 1:6d} | {clean_text}"
            return clean_text

        if role == Qt.FontRole:
            return self.font

        if role == Qt.BackgroundRole or role == Qt.ForegroundRole:
            return self._get_color(line_text, role)

        if role == Qt.ToolTipRole:
            matches = self._get_matching_filters(line_text)
            if matches:
                tip = "<b>Matching Filters:</b><br/>"
                for m in matches:
                    prefix = "[REGEX]" if m["regex"] else "[TEXT]"
                    options = []
                    if m["bg_color"] != "None": options.append(f"BG: {m['bg_color']}")
                    if m.get("text_color", "None") != "None": options.append(f"FG: {m['text_color']}")
                    opt_str = f" ({', '.join(options)})" if options else ""
                    
                    # Highlight pattern if excluded
                    pattern = f"<strike>{m['text']}</strike>" if m["exclude"] else f"\"{m['text']}\""
                    tip += f"• {prefix} {pattern}{opt_str}<br/>"
                return tip

        return None

    def _get_matching_filters(self, line):
        if not self.filters:
            return []
            
        matches = []
        for ftr in self.filters:
            if not ftr.get("active", True):
                continue

            is_match = False
            if ftr["regex"]:
                flags = 0 if ftr["case_sensitive"] else re.IGNORECASE
                if re.search(ftr["text"], line, flags):
                    is_match = True
            else:
                if ftr["case_sensitive"]:
                    if ftr["text"] in line:
                        is_match = True
                else:
                    if ftr["text"].lower() in line.lower():
                        is_match = True
            
            if is_match:
                matches.append(ftr)
        return matches

    def _get_color(self, line, role):
        matches = self._get_matching_filters(line)
        if not matches:
            if role == Qt.ForegroundRole:
                return QColor("#808080")
            return None
            
        bg_result = None
        fg_result = None
        
        # Priority: Last active non-exclude filter wins for colors.
        # If any match is an exclude, it might have been hidden by the worker, 
        # but here we just return default if the highest priority match is an exclude.
        for ftr in reversed(matches):
            if ftr["exclude"]:
                return None # Exclude wins priority
            
            if bg_result is None and ftr["bg_color"] != "None":
                bg_result = ftr["bg_color"]
            if fg_result is None and ftr.get("text_color", "None") != "None":
                fg_result = ftr["text_color"]
            
            if bg_result and fg_result:
                break

        if role == Qt.BackgroundRole and bg_result:
            return QColor(COLOR_MAP.get(bg_result, bg_result))
        if role == Qt.ForegroundRole:
            if fg_result:
                return QColor(TEXT_COLOR_MAP.get(fg_result, fg_result))
            return None
            
        return None

    def set_lines(self, lines):
        self.beginResetModel()
        self.all_lines = lines
        self.visible_indices = list(range(len(lines)))
        self.max_line_length = 0
        self.longest_line_text = ""
        self._update_longest_line(lines)
        self.endResetModel()

    def update_visible_indices(self, indices):
        self.beginResetModel()
        self.visible_indices = indices
        self.endResetModel()
    
    def clear(self):
        self.beginResetModel()
        self.all_lines = []
        self.visible_indices = []
        self.max_line_length = 0
        self.longest_line_text = ""
        self.endResetModel()
        
    def zoom(self, delta):
        size = self.font.pointSize() + delta
        if size < 6: size = 6
        if size > 30: size = 30
        self.font.setPointSize(size)
        self.layoutChanged.emit()
        
    def append_chunk(self, lines):
        start_real_idx = len(self.all_lines)
        self.all_lines.extend(lines)
        self._update_longest_line(lines)
        
        # Calculate visibility
        new_indices = []
        has_active_filters = any(f.get("active", True) for f in self.filters)
        
        for i, line in enumerate(lines):
            real_idx = start_real_idx + i
            if not has_active_filters:
                new_indices.append(real_idx)
                continue
                
            matched = False
            is_excluded = False
            
            # Incremental Counting and Visibility
            for ftr in self.filters:
                if not ftr.get("active", True):
                    continue
                is_match = False
                if ftr["regex"]:
                    flags = 0 if ftr["case_sensitive"] else re.IGNORECASE
                    if re.search(ftr["text"], line, flags):
                        is_match = True
                else:
                    if ftr["case_sensitive"]:
                        if ftr["text"] in line:
                            is_match = True
                    else:
                        if ftr["text"].lower() in line.lower():
                            is_match = True
                
                if is_match:
                    ftr['total_matches'] = ftr.get('total_matches', 0) + 1
                    # Priority logic: Exclude beats Include if both match a line
                    if ftr["exclude"]:
                        matched = False
                        is_excluded = True
                    else:
                        matched = True
                        is_excluded = False
            
            if not is_excluded:
                if matched or not self.show_only_filtered:
                    new_indices.append(real_idx)

        if new_indices:
            first_row_idx = len(self.visible_indices)
            self.beginInsertRows(QModelIndex(), first_row_idx, first_row_idx + len(new_indices) - 1)
            self.visible_indices.extend(new_indices)
            self.endInsertRows()
            return True
        return False
