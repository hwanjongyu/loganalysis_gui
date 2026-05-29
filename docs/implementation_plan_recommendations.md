# Implementation Plan - Performance & Find Dialog Polish

This implementation plan outlines the additions and enhancements proposed to fulfill the three key technical recommendations:
1. **Memory-Mapped Files (`mmap`)** for efficient gigabyte log file parsing inside `FileLoadWorker`.
2. **Regex Compilation Caching** in `filter_engine.py` using a central, memory-efficient compiled pattern cache.
3. **Non-Destructive Soft Find Highlights** in `LogModel` and `FindDialog` to highlight all search matches on screen simultaneously.

---

## Proposed Changes

### 1. Centralized Regex Caching (`filter_engine.py`)

#### [MODIFY] [filter_engine.py](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/filter_engine.py)
* Introduce a module-level dictionary cache `_REGEX_CACHE: Dict[Tuple[str, bool], Pattern[str]]` to store compiled regex patterns.
* Update `prepare_filters` and `filter_matches_line` to fetch from the cache instead of compiling on every invocation or thread start.
* This avoids rebuilding compiled patterns when switching tabs or modifying separate filters.

```python
_REGEX_CACHE = {}

def get_compiled_regex(pattern: str, case_sensitive: bool) -> Pattern[str]:
    key = (pattern, case_sensitive)
    if key not in _REGEX_CACHE:
        flags = 0 if case_sensitive else re.IGNORECASE
        _REGEX_CACHE[key] = re.compile(pattern, flags)
    return _REGEX_CACHE[key]
```

---

### 2. Memory-Mapped Logging Ingestion (`workers.py` & `models.py`)

#### [MODIFY] [workers.py](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/workers.py)
* Update `FileLoadWorker.run` to leverage Python's built-in `mmap` module for reading file bytes, rather than performing standard file block chunking.
* For very large files (e.g., >2GB), `mmap` allows scanning lines off-heap and yields massive throughput speedups because the operating system manages memory-cached pages natively.

```python
import mmap

# inside FileLoadWorker.run()
with open(self.file_path, "rb") as f:
    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        # Efficiently read and decode lines utilizing mmap stream indexing
```

---

### 3. Non-Destructive Soft Find Highlights (`models.py`, `dialogs.py` & `main_window.py`)

#### [MODIFY] [models.py](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/models.py)
* Add `search_query: str = ""` and helper flags (`search_case`, `search_regex`) to the `LogModel` class.
* Update `LogModel.data` under `Qt.BackgroundRole`:
  * If a row matches the active search parameters, highlight it with a modern soft yellow (`#FFF9C4` / light theme) or soft amber/brown (`#3E2723` / dark theme) selection background.
  * This highlights *all* visible occurrences of the search term in the viewer at the same time, without modifying visibility indices (non-destructive).

#### [MODIFY] [dialogs.py](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/dialogs.py)
* Update `FindDialog` text fields to emit a live `textChanged` or selection update event.
* This allows instant visual feedback as the user types their search query into the search dialog.

#### [MODIFY] [main_window.py](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/main_window.py)
* Connect `FindDialog` search inputs to a new window slot `update_search_highlights(query, case, regex)` that pushes search variables down to `LogModel` and triggers a visual model repaint (`layoutChanged.emit()`).
* Ensure that closing the `FindDialog` or clearing the search text resets `LogModel.search_query` and restores standard coloring instantly.

---

## Verification Plan

### Automated Tests
* Add test cases in `tests/test_filter_engine.py` to assert that regex patterns are retrieved from the cache and not recompiled.
* Add test cases in `tests/test_workers.py` to verify that `mmap` reads complete lines identically to the block-based parser.
* Add test cases in `tests/test_main_window.py` validating that:
  * Setting a search query applies the soft background color to matching visible lines.
  * Clearing the search query restores normal styling.

### Manual Verification
* Load a large log file (>100MB) to verify load speed and memory usage.
* Open `Find` (Ctrl+F) and type a common term (e.g., `Info`). Observe that all visible matching rows are softly highlighted.
* Press `Next` and `Previous` to verify active match focus, then close the dialog to ensure highlights clear immediately.
