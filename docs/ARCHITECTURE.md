# Project Architecture & Roles

This document defines the roles and responsibilities of the key components within the `LogAnalysisGUI` project following the transition to a High-Performance Model/View Architecture.

## 🏗️ Software Architecture Roles

The application follows a **Model-View-Controller (modified)** pattern tailored for PyQt5.

### 1. The Data Authority: `LogModel`
**Role**: Single Source of Truth.
**Responsibilities**:
*   **Data Storage**: Holds the raw log lines (`all_lines`) in memory.
*   **Visibility Logic**: Determines which lines are displayed based on `visible_indices`.
*   **Formatting**: Provides data to the View (`DisplayRole`) and styling (`BackgroundRole`, `ForegroundRole`).
*   **Thread Safety**: Acts as the synchronization point for data updates from workers.

### 2. The Orchestrator: `LogAnalysisMainWindow`
**Role**: Application Controller.
**Responsibilities**:
*   **Lifecycle Management**: Starts and stops the application, manages window state.
*   **Worker Management**: Spawns, connects, and terminates background threads (`AdbWorker`, `FilterWorker`, `FileLoadWorker`).
*   **Input Handling**: Captures user intent (Menu clicks, Filter toggles) and routes them to the Model.
*   **Feedback**: Updates the `QStatusBar` and handles modal dialogs (`FilterDialog`).
*   **State Composition**: Delegates filter-tab metadata and runtime controller flags to `window_state.py` so tab enable/modified/file-path state and monitoring/refilter state are grouped instead of spread across parallel lists and loose attributes.

### 3. The Workhorses: `Background Threads`
To ensure the UI remains frozen-free (60fps), heavy lifting is delegated to dedicated workers.

*   **`FilterWorker` (QThread)**
    *   **Role**: Search Engine.
    *   **Responsibility**: Iterates through the full dataset (millions of lines) to verify Regex/String matches against active filters. Returns specific indices to show.
    *   **Shared Rules**: Reuses the same `filter_engine` matching and include/exclude precedence rules as the live append and model styling paths so filter behavior stays consistent across threads.

*   **`FileLoadWorker` (QThread)**
    *   **Role**: File Ingestor.
    *   **Responsibility**: Reads selected log files off the UI thread, emits incremental progress, and returns the full in-memory line list only after the file is fully loaded.
    *   **UX Contract**: Keeps the previous log visible while a replacement file is loading and relies on request-id invalidation so stale load completions cannot overwrite newer user actions.
    
*   **`AdbWorker` (QThread)**
    *   **Role**: Data Ingestor.
    *   **Responsibility**: Manages the `adb logcat` subprocess. Buffers high-velocity stream data and emits batched chunks to the UI thread to prevent event-loop flooding.
    *   **Retention Policy**: Live monitoring keeps only the most recent `MAX_MONITOR_LINES` entries in memory; older lines are trimmed and the current filter view is recalculated.

### 4. The Presentation Layer: `QTreeView`
**Role**: Virtualized Renderer.
**Responsibilities**:
*   **Virtualization**: Renders *only* the rows currently visible in the viewport.
*   **Performance**: handling scroll events and painting text/colors requested by the `LogModel`.

---

## 🔄 Thread Ownership & State Flow

The current implementation uses a strict ownership model to keep UI state coherent:

*   **UI thread owns mutable application state**: `LogModel`, filter tabs, enabled/disabled tab state, and status-bar messaging are all mutated from `LogAnalysisMainWindow`.
*   **Window controller state is grouped by responsibility**: `FilterTabState` owns per-tab widgets/filters/metadata, and `MainWindowRuntimeState` owns monitoring, refiltering, pending chunk buffering, and request-id bookkeeping.
*   **`FilterWorker` operates on a request token**: each refilter operation gets a monotonically increasing request id. Completed results are ignored unless they match the latest request, which prevents stale filter results from overwriting newer UI state after clear/open/close operations.
*   **`FileLoadWorker` also operates on a request token**: opening a different file, clearing logs, starting monitoring, or closing the window invalidates earlier file-load completions before they can replace the current model.
*   **Filter semantics are centralized**: filter matching, active-filter handling, and include/exclude precedence now live in `filter_engine.py` and are shared by `FilterWorker`, tooltips/colors in `LogModel`, and incremental live append filtering.
*   **Live ADB chunks are buffered during refiltering**: while a `FilterWorker` recalculates visibility during monitoring, incoming `adb logcat` chunks are queued in `pending_chunks` and flushed only after the latest filter pass completes. This avoids dropping newly streamed lines when the worker publishes a snapshot.
*   **`AdbWorker` owns subprocess I/O only**: the worker is responsible for `adb logcat` process management and batched chunk emission, but start/stop/wait decisions remain in the main window.
*   **State resets invalidate in-flight work**: opening a new file, clearing logs, toggling monitoring, and closing the window invalidate previous filter requests before the model is reset.

---

## 👥 Contributor Roles (Suggested)

As the project grows, these human roles define how we manage the repository.

| Role | Responsibilities |
| :--- | :--- |
| **Maintainer / Architect** | • Defines the high-level roadmap.<br>• Approves changes to `LogModel` core logic.<br>• Manages the release pipeline (PyInstaller builds). |
| **Feature Developer** | • Implements new features (e.g., "Search", "Go To Line") without blocking the UI thread.<br>• Adds new data sources (e.g., SSH, Serial Port). |
| **QA / Tester** | • Validates performance with large files (1GB+).<br>• Verifies ADB stability on different platforms (Windows, Linux, macOS). |
| **UI/UX Designer** | • Refines the color palettes (`COLOR_MAP`).<br>• Improves the filter management UI (Drag & Drop, Grouping). |
