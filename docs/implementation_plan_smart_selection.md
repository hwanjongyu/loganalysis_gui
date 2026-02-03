# Implementation Plan - Smart Selection Tracking

Ensure the user doesn't lose their place when filters are toggled by keeping the selection on the same line or shifting it to the nearest available neighbor.

## Proposed Changes

### 1. `LogAnalysisMainWindow.apply_filters`
- Capture the source index of the current focused row in the log view.
- Store this as `self.target_source_idx`.

### 2. `LogAnalysisMainWindow.on_filtering_finished`
- Use `bisect_left` to find the best position for `self.target_source_idx` in the new `visible_indices`.
- If the exact index is found, restore selection to that row.
- If not found, select the immediate neighbor (either the next line or previous line in the source) that is now visible.
- Scroll the view to ensure this new selection is visible.

### 3. Imports
- Add `import bisect` to the top of `src/loganalysis_gui.py`.

## Verification Plan
1. **Selection Persistence**:
   - Filter for "A", select a line.
   - Change filter to include "A" and "B".
   - Verify the same line stays selected.
2. **Nearest Neighbor**:
   - Select a line "L".
   - Toggle a filter that *hides* line "L".
   - Verify that the selection moves to the line immediately before or after where "L" was.
   - Verify the view scrolls to that line.
