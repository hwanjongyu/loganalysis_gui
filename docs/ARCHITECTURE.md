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
*   **Worker Management**: Spawns, connects, and terminates background threads (`AdbWorker`, `FilterWorker`).
*   **Input Handling**: Captures user intent (Menu clicks, Filter toggles) and routes them to the Model.
*   **Feedback**: Updates the `QStatusBar` and handles modal dialogs (`FilterDialog`).

### 3. The Workhorses: `Background Threads`
To ensure the UI remains frozen-free (60fps), heavy lifting is delegated to dedicated workers.

*   **`FilterWorker` (QThread)**
    *   **Role**: Search Engine.
    *   **Responsibility**: Iterates through the full dataset (millions of lines) to verify Regex/String matches against active filters. Returns specific indices to show.
    
*   **`AdbWorker` (QThread)**
    *   **Role**: Data Ingestor.
    *   **Responsibility**: Manages the `adb logcat` subprocess. Buffers high-velocity stream data and emits batched chunks to the UI thread to prevent event-loop flooding.

### 4. The Presentation Layer: `QTreeView`
**Role**: Virtualized Renderer.
**Responsibilities**:
*   **Virtualization**: Renders *only* the rows currently visible in the viewport.
*   **Performance**: handling scroll events and painting text/colors requested by the `LogModel`.

---

## 👥 Contributor Roles (Suggested)

As the project grows, these human roles define how we manage the repository.

| Role | Responsibilities |
| :--- | :--- |
| **Maintainer / Architect** | • Defines the high-level roadmap.<br>• Approves changes to `LogModel` core logic.<br>• Manages the release pipeline (PyInstaller builds). |
| **Feature Developer** | • Implements new features (e.g., "Search", "Go To Line") without blocking the UI thread.<br>• Adds new data sources (e.g., SSH, Serial Port). |
| **QA / Tester** | • Validates performance with large files (1GB+).<br>• Verifies ADB stability on different platforms (Windows, Linux, macOS). |
| **UI/UX Designer** | • Refines the color palettes (`COLOR_MAP`).<br>• Improves the filter management UI (Drag & Drop, Grouping). |
