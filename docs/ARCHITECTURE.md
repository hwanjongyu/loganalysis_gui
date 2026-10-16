# Project Architecture & Roles

This document defines the roles, design patterns, and architectural responsibilities of the key components within the `LogAnalysisGUI` project following the Phase 1~4 architectural refactoring and performance modernization.

---

## 🏗️ High-Level System Architecture

The application adopts a **Decoupled Model-View-Controller (MVC) & Multi-Worker Architecture** tailored for PyQt5, delivering sub-millisecond UI latency across multi-million line log datasets.

```mermaid
graph TD
    subgraph UI Layer (Qt Main Thread)
        MW["LogAnalysisMainWindow<br/>(Lightweight Orchestrator & Signal Broker)"]
        FM["FilterManager<br/>(Tabs, CRUD, Persistence)"]
        AC["AdbController<br/>(Discovery & Lifecycle)"]
        SC["SearchController<br/>(FindDialog & Navigation)"]
        LVC["LogViewController<br/>(Viewport, Columns, Zoom, Menu)"]
        LV["LogView (QTreeView / Virtual Delegate)"]
    end

    subgraph Domain Models & State
        LM["LogModel<br/>(Snapshot Virtual Model & Color Cache)"]
        FTD["FilterTabData<br/>(Pure Data Class, Decoupled)"]
        FTW["FilterTabWidgets<br/>(Qt UI Widget References)"]
        FTS["FilterTabState<br/>(Composition Wrapper)"]
        FE["FilterEngine<br/>(Precomputed Styling & Regex Cache)"]
    end

    subgraph Background Asynchronous Workers (QThreads)
        FLW["FileLoadWorker<br/>(Chunked Stream & Max Line Offload)"]
        FW["FilterWorker<br/>(Visibility & Style Precomputation)"]
        SW["SearchWorker<br/>(Off-Thread Text / Regex Scan)"]
        AW["AdbWorker<br/>(Process Stream & Batch Buffer)"]
        ADW["AdbDeviceScanWorker<br/>(Non-blocking 'adb devices')"]
    end

    MW --> FM
    MW --> AC
    MW --> SC
    MW --> LVC
    MW --> LV

    FM --> FTS
    FTS --> FTD
    FTS --> FTW

    LV --> LM
    LM --> FE

    LM -.->|Async Signal/Slot| FLW
    LM -.->|Async Signal/Slot| FW
    SC -.->|Async Signal/Slot| SW
    AC -.->|Async Signal/Slot| AW
    AC -.->|Async Signal/Slot| ADW
```

---

## 🏛️ Component Responsibilities

### 1. Presentation & Controller Layer (`UI Layer`)

*   **`LogAnalysisMainWindow` ([`main_window.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/main_window.py))**
    *   **Role**: Top-level application coordinator and signal broker.
    *   **Responsibilities**: Manages main window layout, menu bar actions, status bar permanent indicators, central event filtering, and backward-compatible delegation to specialized controllers. Slimmed down from monolithic God-class (~1,700 lines) to clean orchestrator.
    *   **Thread Safety**: Enforces worker tracking (`_track_worker`) and deterministic teardown join barriers (`_cleanup_all_workers`).

*   **`FilterManager` ([`filter_manager.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/filter_manager.py))**
    *   **Role**: Filter tab lifecycle and persistence controller.
    *   **Responsibilities**: Filter CRUD, drag-and-drop tab reordering, filter list item widget styling, in-place search filtering, and crash-resilient atomic JSON saving (`.tmp` -> `os.replace`).

*   **`AdbController` ([`adb_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/adb_controller.py))**
    *   **Role**: ADB device discovery and streaming controller.
    *   **Responsibilities**: Asynchronous device list polling (`AdbDeviceScanWorker`), toolbar device selector integration, live logcat process lifecycle, and safe TOCTOU process teardown.

*   **`SearchController` ([`search_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/search_controller.py))**
    *   **Role**: Log search and navigation manager.
    *   **Responsibilities**: `FindDialog` display/debouncing, adaptive search dispatch (inline fast-path for < 5,000 lines vs off-thread `SearchWorker` for massive logs), and selection centering.

*   **`LogViewController` ([`log_view_controller.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/log_view_controller.py))**
    *   **Role**: Viewport presentation controller.
    *   **Responsibilities**: Dynamic column width measurement via `QFontMetrics`, full-line display vs compact mode toggle, on-the-fly font zoom (`Ctrl +` / `Ctrl -`), selection clipboard copying, log context menu, and mode indicator badges.

---

### 2. Domain & State Layer (`Domain Models`)

*   **`LogModel` ([`models.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/models.py))**
    *   **Role**: Single Source of Truth (`QAbstractListModel`).
    *   **Responsibilities**: Holds log dataset (`all_lines`), manages mapped `visible_indices`, caches `visible_styles` for zero-overhead paint events, and bounds dynamic style evaluation in an LRU cache (capped at 10,000 items).

*   **`FilterTabData` & `FilterTabState` ([`window_state.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/window_state.py))**
    *   **Role**: Pure domain state decoupled from Qt widgets.
    *   **Responsibilities**: Separates pure data structures (`FilterTabData`: name, filter rules, enabled, modified, file path) from UI references (`FilterTabWidgets`), composited via `FilterTabState` for seamless backward compatibility.

*   **`FilterEngine` ([`filter_engine.py`](file:///home/drew/github/hwanjongyu/loganalysis_gui/src/loganalysis_gui/filter_engine.py))**
    *   **Role**: Regex compilation and rule evaluation core.
    *   **Responsibilities**: Global regex cache (`get_compiled_regex`), filter matching logic, include/exclude priority resolution, and precomputed line styling (`resolve_line_style`).

---

### 3. Asynchronous Worker Threads (`QThreads`)

All heavy I/O, regex parsing, and subprocess streaming are completely isolated from the Qt GUI event loop:

*   **`FileLoadWorker`**: Buffered chunk streaming (safely reading files without kernel `SIGBUS` hazards), computing off-thread longest line lengths with upper-bound short-circuiting.
*   **`FilterWorker`**: Evaluates regex/text rules against a snapshot of lines, computing `visible_indices` and precomputing `visible_styles` in a single pass to eliminate scroll-time regex re-evaluations.
*   **`SearchWorker`**: Scans millions of lines off-thread for text or regex patterns in forward/backward direction with real-time progress updates and instant cancellation.
*   **`AdbWorker`**: Streams `adb logcat` via validated device serials, buffering incoming lines and emitting batched chunks to avoid event-loop congestion.
*   **`AdbDeviceScanWorker`**: Non-blocking `adb devices` scanner with 3.0s timeout, eliminating main-thread freezes when ADB daemon restarts.

---

## 🔄 Concurrency, Safety & Lifecycle Contracts

1. **Deterministic Join Barriers**:
   All background workers implement `stop()` and are waited on with explicit join timeouts (`wait(1000)`) during cancellation, window closure, or tab teardown, eliminating `SIGABRT` crashes on exit.
2. **Immutable Snapshot Filtering**:
   When launching a `FilterWorker` or `SearchWorker`, worker threads receive snapshot copies of lines (`all_lines[:]`) rather than references to mutable state, eliminating thread race conditions during live streaming.
3. **Hysteresis Buffer Trimming**:
   Live logcat buffers are trimmed in hysteresis batches (`MONITOR_TRIM_BATCH = 20,000` lines) once the buffer exceeds `MAX_MONITOR_LINES + trim_batch`, preventing the CPU-thrashing refilter loop on every single streamed line.
4. **C++ Object Lifecycle Guards**:
   Worker completion handlers and teardown loops wrap `isRunning()` queries in `try...except RuntimeError` guards to gracefully handle Qt C++ objects cleaned up via `deleteLater()`.

---

## 🧪 Verification & Test Suite

The architecture is covered by **81 comprehensive unit tests** executing in under 26 seconds:
- `test_main_window.py`: UI orchestration, tab manipulation, mock menus, and file load flows.
- `test_workers.py`: Worker execution, progress emission, cancellation, timeout, and regex safety.
- `test_search_controller.py`: Search dialog debounce, async/sync search dispatch, regex errors, and termination.
- `test_log_view_controller.py`: Column metrics, full-line toggling, zoom level adjustment, and row selection.
