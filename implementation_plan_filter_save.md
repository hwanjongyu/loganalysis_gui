# Implementation Plan - Separated Filter Saving

Update the filter saving logic to save only the currently selected tab and use a tab-separated format for better interoperability and clarity.

## Proposed Changes

### 1. `LogAnalysisMainWindow.save_filters`
- Modify to save only the filters from the active tab (`self.filter_tabs.currentIndex()`).
- Implement saving as a tab-separated text file (`.txt`) where each line represents one filter.
- Fields: `Text`, `CaseSensitive`, `Regex`, `Exclude`, `BgColor`, `TextColor`, `Active`.
- Maintain backward compatibility by allowing JSON export of the single tab.

### 2. `LogAnalysisMainWindow.load_filters`
- Add support for parsing the new tab-separated `.txt` format.
- Automatically detect the format (JSON vs TSV).
- Update the current tab's text to match the filename if loading from a `.txt` file.

### 3. Imports
- Add `import os` for path manipulation.

## Verification Plan
1. **Save Selected Tab**:
   - Create multiple tabs with different filters.
   - Select one tab and save it.
   - Verify that only that tab's filters are in the file.
2. **TSV Format Check**:
   - Open the saved `.txt` file in a text editor.
   - Verify fields are separated by `\t`.
3. **Round-trip Verification**:
   - Clear filters in a tab.
   - Load the saved `.txt` file.
   - Verify all filter settings (colors, regex, etc.) are restored correctly.
4. **JSON Compatibility**:
   - Verify that loading an old `filters.json` still works (even if it only loads the first tab/set).
