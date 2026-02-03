# Implementation Plan - Separated Filter Saving (Final)

Update the filter saving logic to save only the currently selected tab using the JSON format.

## Proposed Changes

### 1. `LogAnalysisMainWindow.save_filters`
- Modify to save only the filters from the active tab (`self.filter_tabs.currentIndex()`).
- Implement saving as a JSON file (`.json`) containing the tab name and the filter list.
- Format: `{"name": "Tab Name", "filters": [...]}`.

### 2. `LogAnalysisMainWindow.load_filters`
- Add support for parsing the new single-tab JSON format.
- Maintain backward compatibility for:
  - Legacy multi-tab JSON files (loads the first tab).
  - Legacy simple list-based JSON files.
- Automatically update the current tab's text to match the saved name or filename.

### 3. Imports
- Ensure `import json` and `import os` are present.

## Verification Plan
1. **Save Selected Tab**:
   - Create multiple tabs with different filters.
   - Select one tab and save it.
   - Verify that only that tab's filters are in the file.
2. **JSON Structure Check**:
   - Open the saved `.json` file.
   - Verify it contains the `name` and `filters` keys.
3. **Round-trip Verification**:
   - Clear filters in a tab.
   - Load the saved `.json` file.
   - Verify all filter settings (colors, regex, etc.) are restored correctly.
4. **Legacy Compatibility**:
   - Verify that loading an old `filters.json` (multi-tab or simple list) still works.
