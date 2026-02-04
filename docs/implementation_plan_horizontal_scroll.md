# Implementation Plan - Enable Horizontal Scrolling

The user wants to be able to scroll horizontally to view long log lines. Currently, the `QListView` used for log display is optimized for vertical scrolling and performance, but it does not support horizontal scrolling for long lines effectively.

## Proposed Changes

### 1. Replace `QListView` with `QTreeView`
- `QTreeView` is a more versatile view that supports horizontal scrolling of columns natively.
- It still supports high-performance virtualization with `setUniformRowHeights(True)`.
- A `QAbstractListModel` (used by `LogModel`) is fully compatible with `QTreeView` (treated as 1 column).

### 2. Configure `QTreeView` for Log Display
- Set `setHeaderHidden(True)` to maintain the current "list" look.
- Set `setRootIsDecorated(False)` to hide expansion icons.
- Enable horizontal scrolling: `setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)`.
- Set the header resize mode to allow viewing long content. We will use `QHeaderView.ResizeToContents` with caution or simple interaction.
- **Performance Note**: `ResizeToContents` for millions of rows can be slow. However, for a single column of text, it might be acceptable if `uniformRowHeights` is on, or we can set a large fixed width and allow interactive resizing.
- **Dynamic Resizing**: We will set `self.log_view.header().setSectionResizeMode(QHeaderView.Interactive)` and `self.log_view.header().setStretchLastSection(True)` (or False if we want the scrollbar to trigger).

### 3. Update UI Setup in `LogAnalysisMainWindow.init_ui`
- Change initialization of `self.log_view`.
- Adjust signal connections if any (though `scrollTo` and `setCurrentIndex` are compatible).

## Step-by-Step Implementation

1.  **Modify Imports**: Ensure `QTreeView` and `QHeaderView` are imported from `PyQt5.QtWidgets`.
2.  **Update `init_ui`**:
    - Replace `QListView()` with `QTreeView()`.
    - Apply `setUniformRowHeights(True)`.
    - Apply list-style configurations (`setHeaderHidden`, `setRootIsDecorated`).
    - Configure the horizontal header to enable scrolling for long lines.
3.  **Adjust `on_adb_chunk` and other methods**:
    - Verify that `scrollToBottom()` and selection logic still work as expected (they should).

## Verification
- Load a file with very long lines (e.g., 500+ characters).
- Verify that a horizontal scrollbar appears.
- Verify that scrolling horizontally works.
- Verify that vertical scrolling and filtering performance remain high.
