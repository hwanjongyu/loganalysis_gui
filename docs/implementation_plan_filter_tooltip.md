# Implementation Plan - Filter Hover Tooltips

Add the ability to see which filters matched a specific log line by hovering the mouse over the line.

## User Requirements
- **Visibility**: When hovering over a row in the log view, a tooltip should appear.
- **Content**: The tooltip should list all active filters that match the line.
- **Details**: Show the filter pattern, whether it's a regex, and its color configuration.

## Proposed Changes

### 1. `LogModel` Refactoring
- **New Helper `_get_matching_filters(self, line_text)`**:
    - Centralizes the logic for checking if a line matches the current filter set.
    - Handles Regex compilation errors gracefully.
    - Returns a list of dictionaries representing matching filters.
- **Update `_get_color(self, line, role)`**:
    - Refactor to use `_get_matching_filters` instead of the internal loop.
    - Maintain existing priority logic (last active filter wins).
- **Update `data(self, index, role)`**:
    - Add support for `Qt.ToolTipRole`.
    - If `_get_matching_filters` returns any results, format them into a multi-line string.

### 2. Tooltip Formatting
The tooltip string should follow a clean, readable format:
```text
Matching Filters:
• [REGEX] "fatal|error" (BG: DarkRed, FG: White)
• [TEXT] "system" (BG: Blue)
```

### 3. UI Configuration
- Ensure `self.log_view` has tooltips enabled (standard for `QTreeView`).

## Step-by-Step Implementation

1.  **Refactor `LogModel`**:
    - Implement `_get_matching_filters`.
    - Update `_get_color` to use it.
    - Add `Qt.ToolTipRole` support to `data`.
2.  **Test Ad-hoc**:
    - Create overlapping filters and verify the tooltip lists both.
    - Verify that "Exclude" filters (which hide lines) don't cause issues (they shouldn't be visible anyway in "Show Only Filtered" mode).

## Verification Plan
1. **Single Match**: Add one filter and hover over a matching line. Verify the tooltip shows the pattern.
2. **Multiple Matches**: Add two filters that both match the same line. Verify both are listed in the tooltip.
3. **No Match**: Hover over an unfiltered line. Verify no tooltip (or default behavior) appears.
4. **Regex Tooltip**: Verify that regex filters are explicitly labeled as `[REGEX]`.
