# Implementation Plan - Fix Multi-line Copying [COMPLETED]

This plan addresses the issue where `Ctrl+C` or a "Copy" action only copies a single line even when multiple lines are selected in the log view.

## Problem Description
The `QListView` highlighting selection works correctly (ExtendedSelection is enabled), but there is no explicit handling for the "Copy" action. Users expect `Ctrl+C` to copy all selected lines to the clipboard. Currently, if any copy behavior exists, it is likely a platform default that only captures the focused item.

## Proposed Changes

### 1. Implement `copy_selection` in `LogAnalysisMainWindow`
- **Method**: `copy_selection(self)`
- **Logic**:
    1. Retrieve all selected row indexes from `self.log_view.selectionModel()`.
    2. Sort indexes to preserve the original log sequence.
    3. Extract the `DisplayRole` text (the visible line) for each index from `LogModel`.
    4. Join lines with the system newline character.
    5. Update the global `QApplication.clipboard()` with the result.
    6. Provide visual feedback via `self.status_bar.showMessage()`.

### 2. UI Integration
- **Menu Bar**: Add a "Copy" action to the "Edit" menu.
- **Shortcut**: Assign `Ctrl+C` to the "Copy" action.
- **Context Menu**: 
    - Set `log_view` context menu policy to `Qt.ActionsContextMenu`.
    - Add the "Copy" action to the `log_view` widget so it appears on right-click.
- **Shortcuts Help**: Update the `Help -> Shortcuts` dialog to include `Ctrl+C`.

## Verification Plan
1. **Selection Test**: Select a single line and press `Ctrl+C`. Verify it is copied.
2. **Multi-selection Test**: Select multiple non-contiguous lines (Ctrl+Click) and press `Ctrl+C`. Verify all are copied in order.
3. **Range Selection Test**: Select a range of lines (Shift+Click) and press `Ctrl+C`. Verify all are copied.
4. **Context Menu Test**: Right-click on a selection and select "Copy" from the menu. Verify it works.
5. **Shortcut Test**: Verify the shortcut `Ctrl+C` works even when the menu is not open.
