# Implementation Plan - High Performance Log Viewer

The current application crashes with large files because `QTextEdit` attempts to render the entire file layout in memory as HTML. This is extremely memory-intensive. To support large files (e.g., 100MB+, millions of lines), we must switch to a **Model/View Architecture**.

## Problem Analysis
- **Current State**: `QTextEdit` loads all lines as a single HTML blob.
- **Bottleneck**: The HTML layout engine creates heavy objects for every DOM element (row/cell). A 50MB log file can easily consume 1GB+ of RAM when converted to styled HTML table rows.
- **Error**: `Exit code 137` indicates the OS killed the process due to Out Of Memory (OOM).

## Proposed Architecture: Model/View

We will replace `QTextEdit` with `QListView` backed by a custom `QAbstractListModel`. This enables **UI Virtualization**—only the lines currently visible on the screen are rendered.

### 1. Component Migration

| Current Component | New Component | Benefit |
| :--- | :--- | :--- |
| `QTextEdit` | `QListView` | Renders only visible items; minimal memory footprint. |
| `f.readlines()` | `QAbstractListModel` | Keeps data as raw Python strings; no HTML overhead. |
| HTML Styling | `QStyledItemDelegate` | Paints colors/text directly to the canvas on-the-fly. |

### 2. Implementation Details

#### A. The Log Model (`LogModel`)
A custom subclass of `QAbstractListModel`.
- **Data Source**: Holds `self.lines` (list of strings) and `self.filtered_indices` (list of integers).
- **Lazy Loading**: When the view asks for row 50, the model looks up `real_index = filtered_indices[50]` and returns `lines[real_index]`.
- **Memory Efficiency**: 1 million lines of text consumes only the memory required for the raw strings (~100MB for a 100MB file), rather than GBs for widget structures.

#### B. The Delegate (`LogDelegate`)
A custom subclass of `QStyledItemDelegate`.
- Handles the drawing of text and background colors.
- Inteprets the filter rules (regex/colors) at paint time.
- Supports high-performance text rendering without HTML parsing.

#### C. Filtering Logic
- Instead of hiding UI rows (slow), we regenerate the `filtered_indices` list in the model.
- **Multithreading**: Running the filter over 1 million lines can take 1-2 seconds in Python. We will run the filter logic in a background thread to prevent UI freezing.

### 3. Step-by-Step Refactor

1.  **Skeleton**: Create `LogModel` and `LogDelegate` classes.
2.  **View Swap**: Replace `QTextEdit` in `LogAnalysisMainWindow` with `QListView`.
3.  **Data Binding**: Connect the file loader to populate `LogModel`.
4.  **Styling**: Port the color logic from `apply_filters` to the `LogDelegate`.
5.  **Filtering**: Implement background filtering that updates the model's `filtered_indices`.

## Verification Plan
1.  **Load Test**: Open a 200MB+ log file.
2.  **Memory Monitor**: Ensure RAM usage stays proportional to file size (not 10x).
3.  **Scroll Performance**: Ensure 60fps scrolling efficiency.
