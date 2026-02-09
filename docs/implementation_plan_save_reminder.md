# Implementation Plan: Save Reminder for Modified Tabs

This plan outlines the steps to implement a save reminder when the user attempts to close the application with unsaved filter tab changes.

## 1. Tracking Modifications

We need to track the "modified" status of each filter tab independently.

- **Storage**:
    - Add `self.tab_modified = []` (list of booleans) to `LogAnalysisMainWindow`.
    - Add `self.tab_file_paths = []` (list of strings or `None`) to `LogAnalysisMainWindow`.
- **Logic**:
    - Create a helper method `set_tab_modified(self, index, modified: bool)` to update the status and visually indicate it (e.g., adding a `*` prefix to the tab text).

## 2. Integrating Modification Checks

The `tab_modified` status will be set to `True` in the following scenarios:
- Adding a filter (via dialog or quick filter).
- Editing a filter.
- Deleting a filter.
- Reordering filters.
- Toggling a filter's active state.
- Toggling a tab's enabled state.
- Renaming a tab.
- Adding a new tab.

The `tab_modified` status will be set to `False` in:
- Saving filters to a file.
- Loading filters from a file.

## 3. Visual Feedback

- Use a `*` prefix in the tab title to indicate unsaved changes.
- Ensure the `*` represents the *modified* state, and is removed once saved.

## 4. Close Event Handling

- Override `closeEvent(self, event)` in `LogAnalysisMainWindow`.
- Check if any tab has `tab_modified == True`.
- If modified tabs exist:
    - Construct a message listing the modified tabs.
    - Display a `QMessageBox` asking the user if they want to save changes, discard them, or cancel the closing process.
    - Since "Save" might involve multiple tabs/files, we will provide:
        - **Yes (Save)**: This will prompt the user to save each modified tab one by one (or we could simplify it to just "Close anyway" vs "Cancel").
        - **No (Discard)**: Close the app.
        - **Cancel**: Keep the app open.

## 5. Implementation Steps

1.  **Initialize flags**: Update `__init__` and `add_filter_tab`.
2.  **Add `set_tab_modified`**: Implement the helper.
3.  **Update existing methods**: Add `set_tab_modified(idx, True)` calls where appropriate.
4.  **Update `save_filters` and `load_filters`**: Reset the flag and update tab title.
5.  **Override `closeEvent`**: Implement the logic to prompt the user.

## 6. Verification Plan

- Create a tab, add a filter -> Check if `*` appears.
- Save the tab -> Check if `*` disappears.
- Edit a filter in the saved tab -> Check if `*` reappears.
- Close the app with a modified tab -> Check if prompt appears.
- Select "Cancel" -> App should stay open.
- Select "No" (Discard) -> App should close.
- Select "Yes" (Save) -> Prompts for saving, then closes only if saved.
