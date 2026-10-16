from collections import OrderedDict
from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex
from PyQt5.QtGui import QColor, QFont
from .constants import COLOR_MAP, TEXT_COLOR_MAP
from .filter_engine import evaluate_line, find_matching_filters, prepare_filters, resolve_line_style

MAX_STYLE_CACHE_SIZE = 10000


def display_log_line_text(line_text):
    return line_text.rstrip('\r\n')


def measured_log_line_text(line_text):
    return display_log_line_text(line_text).rstrip()

class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_lines = [] 
        self.visible_indices = [] 
        self.visible_styles = None
        self._qcolor_cache = {}
        self._filters = []
        self.prepared_filters = []
        self._style_cache = OrderedDict()
        self.show_line_numbers = True
        self.show_only_filtered = True
        self.font = QFont("Monospace", 10) # Default size 10
        self.max_line_length = 0
        self.longest_line_text = ""
        self.visible_max_line_length = 0
        self.visible_longest_line_text = ""
        self.search_query = ""
        self.search_case = False
        self.search_regex = False
        self.is_dark_theme = True

    def _resolve_qcolor(self, color_spec):
        if not color_spec or color_spec == "None":
            return None
        hex_val = COLOR_MAP.get(color_spec, TEXT_COLOR_MAP.get(color_spec, color_spec))
        if hex_val not in self._qcolor_cache:
            if len(self._qcolor_cache) >= 512:
                self._qcolor_cache.clear()
            self._qcolor_cache[hex_val] = QColor(hex_val)
        return self._qcolor_cache[hex_val]

    @property
    def filters(self):
        return self._filters

    @filters.setter
    def filters(self, value):
        self._filters = value
        self.prepared_filters = prepare_filters(value)
        self.invalidate_filter_cache()

    def invalidate_filter_cache(self):
        self._style_cache.clear()
        self._qcolor_cache.clear()
        self.visible_styles = None

    def _display_text(self, line_text):
        if isinstance(line_text, bytes):
            line_text = line_text.decode("utf-8", errors="replace")
        return display_log_line_text(line_text)

    def _measured_text(self, line_text):
        if isinstance(line_text, bytes):
            line_text = line_text.decode("utf-8", errors="replace")
        return measured_log_line_text(line_text)

    def _update_visible_longest_line(self, measured_text):
        if len(measured_text) > self.visible_max_line_length:
            self.visible_max_line_length = len(measured_text)
            self.visible_longest_line_text = measured_text

    def get_line_text(self, real_idx):
        if 0 <= real_idx < len(self.all_lines):
            line = self.all_lines[real_idx]
            if isinstance(line, bytes):
                return line.decode("utf-8", errors="replace")
            return line
        return ""

    def _update_longest_line(self, lines):
        for line in lines:
            if isinstance(line, (bytes, str)) and len(line) <= self.max_line_length:
                continue
            measured_text = self._measured_text(line)
            measured_length = len(measured_text)
            if measured_length > self.max_line_length:
                self.max_line_length = measured_length
                self.longest_line_text = measured_text

    def _find_longest_visible_text(self, indices):
        longest_text = ""
        longest_length = 0
        for index in indices:
            if index >= len(self.all_lines):
                continue
            measured_text = self._measured_text(self.all_lines[index])
            measured_length = len(measured_text)
            if measured_length > longest_length:
                longest_length = measured_length
                longest_text = measured_text
        return longest_text
         
    def rowCount(self, parent=QModelIndex()):
        return len(self.visible_indices)

    def _is_search_match(self, line):
        if not self.search_query:
            return False
        
        if self.search_regex:
            try:
                from .filter_engine import get_compiled_regex
                regex = get_compiled_regex(self.search_query, self.search_case)
                return bool(regex.search(line))
            except Exception:
                return False
        else:
            if self.search_case:
                return self.search_query in line
            else:
                return self.search_query.lower() in line.lower()

    def _get_style(self, real_idx, line):
        if real_idx in self._style_cache:
            self._style_cache.move_to_end(real_idx)
            return self._style_cache[real_idx]

        matches = [matched.filter_data for matched in find_matching_filters(line, self.prepared_filters)]
        bg_color = None
        fg_color = None
        
        if not matches:
            fg_color = QColor("#808080")
        else:
            bg_result = None
            fg_result = None
            exclude_wins = False
            for ftr in reversed(matches):
                if ftr["exclude"]:
                    exclude_wins = True
                    break
                
                if bg_result is None and ftr["bg_color"] != "None":
                    bg_result = ftr["bg_color"]
                if fg_result is None and ftr.get("text_color", "None") != "None":
                    fg_result = ftr["text_color"]
                
                if bg_result and fg_result:
                    break
            
            if not exclude_wins:
                if bg_result:
                    bg_color = QColor(COLOR_MAP.get(bg_result, bg_result))
                if fg_result:
                    fg_color = QColor(TEXT_COLOR_MAP.get(fg_result, fg_result))
        
        if len(self._style_cache) >= MAX_STYLE_CACHE_SIZE:
            self._style_cache.popitem(last=False)
        self._style_cache[real_idx] = (bg_color, fg_color, matches)
        return self._style_cache[real_idx]

    def data(self, index, role):
        if not index.isValid():
            return None
        
        row = index.row()
        if row >= len(self.visible_indices):
            return None
            
        real_idx = self.visible_indices[row]
        line_text = self.all_lines[real_idx]
        if isinstance(line_text, bytes):
            line_text = line_text.decode("utf-8", errors="replace")

        if role == Qt.DisplayRole:
            clean_text = self._display_text(line_text)
            if self.show_line_numbers:
                return f"{real_idx + 1:6d} | {clean_text}"
            return clean_text

        if role == Qt.FontRole:
            return self.font

        if role == Qt.BackgroundRole:
            if self.search_query and self._is_search_match(line_text):
                return QColor("#3E2723") if self.is_dark_theme else QColor("#FFF9C4")
            if self.visible_styles is not None and 0 <= row < len(self.visible_styles):
                bg_val = self.visible_styles[row][0]
                return self._resolve_qcolor(bg_val)
            bg_color, _, _ = self._get_style(real_idx, line_text)
            return bg_color

        if role == Qt.ForegroundRole:
            if self.visible_styles is not None and 0 <= row < len(self.visible_styles):
                fg_val = self.visible_styles[row][1]
                return self._resolve_qcolor(fg_val)
            _, fg_color, _ = self._get_style(real_idx, line_text)
            return fg_color

        if role == Qt.ToolTipRole:
            _, _, matches = self._get_style(real_idx, line_text)
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

    def set_lines(self, lines, longest_line_text=None):
        self.beginResetModel()
        self.invalidate_filter_cache()
        self.all_lines = lines
        self.visible_indices = list(range(len(lines)))
        self.max_line_length = 0
        self.longest_line_text = ""
        self.visible_max_line_length = 0
        self.visible_longest_line_text = ""
        if longest_line_text is not None:
            self.longest_line_text = self._measured_text(longest_line_text)
            self.max_line_length = len(self.longest_line_text)
        else:
            self._update_longest_line(lines)
        self.visible_max_line_length = self.max_line_length
        self.visible_longest_line_text = self.longest_line_text
        self.endResetModel()
 
    def update_visible_indices(self, indices, widest_visible_text=None, visible_styles=None):
        if widest_visible_text is None:
            widest_visible_text = self._find_longest_visible_text(indices)
        else:
            widest_visible_text = self._measured_text(widest_visible_text)

        self.beginResetModel()
        self.visible_indices = indices
        self.visible_styles = visible_styles
        self.visible_max_line_length = len(widest_visible_text)
        self.visible_longest_line_text = widest_visible_text
        self.endResetModel()
    
    def clear(self):
        self.beginResetModel()
        self.invalidate_filter_cache()
        self.all_lines = []
        self.visible_indices = []
        self.max_line_length = 0
        self.longest_line_text = ""
        self.visible_max_line_length = 0
        self.visible_longest_line_text = ""
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
        new_styles = []
        widest_new_visible_text = ""
        widest_new_visible_length = 0
        prepared_filters = self.prepared_filters
        
        for i, line in enumerate(lines):
            real_idx = start_real_idx + i
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
                self.all_lines[real_idx] = line

            matching_filters, is_visible = evaluate_line(
                line,
                prepared_filters,
                self.show_only_filtered,
            )
            for matched_filter in matching_filters:
                filter_data = matched_filter.filter_data
                filter_data['total_matches'] = filter_data.get('total_matches', 0) + 1

            if is_visible:
                new_indices.append(real_idx)
                if self.visible_styles is not None:
                    new_styles.append(resolve_line_style(matching_filters))
                measured_text = self._measured_text(line)
                measured_length = len(measured_text)
                if measured_length > widest_new_visible_length:
                    widest_new_visible_length = measured_length
                    widest_new_visible_text = measured_text

        if new_indices:
            first_row_idx = len(self.visible_indices)
            self.beginInsertRows(QModelIndex(), first_row_idx, first_row_idx + len(new_indices) - 1)
            self.visible_indices.extend(new_indices)
            if self.visible_styles is not None:
                self.visible_styles.extend(new_styles)
            self.endInsertRows()
            if widest_new_visible_length:
                self._update_visible_longest_line(widest_new_visible_text)
            return True
        return False
