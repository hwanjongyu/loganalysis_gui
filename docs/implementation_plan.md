# Implementation Plan - ADB Logcat Monitoring

This plan outlines the addition of real-time `adb logcat` monitoring to the LogAnalysisGUI. This feature allows users to connect to an Android device and stream logs directly into the application, maintaining existing filtering capabilities.

## User Requirements
1.  **Source**: Stream from `adb logcat`.
2.  **Action**: "Monitoring" menu toggle.
3.  **Behavior**:
    *   Clear existing logs when monitoring starts.
    *   Retain and apply current filter configurations to the live stream.

## Architectural Changes

The current architecture is optimized for static file loading (bulk filtering). We need to adapt it for **Stream Processing**.

### 1. New Component: `AdbWorker`
A `QThread` subclass responsible for:
- Executing `adb logcat -v threadtime` as a subprocess.
- Reading `stdout` line-by-line in real-time.
- Emitting a generic `new_lines_ready(list)` signal (batching lines is better for UI performance than emitting every single line).

### 2. LogModel Enhancements (`Stream Mode`)
The `LogModel` needs a specific method to handle incremental updates without re-scanning the entire dataset.

- **Current**: `set_lines()` (Replace all), `update_visible_indices()` (Replace view).
- **New**: `append_lines(lines)`
    - This method will take a batch of new lines.
    - It will run the *current active filters* against these new lines specifically.
    - It will append to `self.all_lines`.
    - It will append matching indices to `self.visible_indices`.
    - It will emit `layoutChanged` or `rowsInserted` to update the View.

### 3. UI Integration
- **Menu**: Add `Monitor` -> `Start ADB Logcat`.
- **State Management**:
    - When `Start` is clicked:
        1.  Check for ADB availability (optional but good).
        2.  Call `LogModel.clear()` (Need to implement this).
        3.  Start `AdbWorker`.
        4.  Change Menu Text to "Stop ADB Logcat".
    - When `Stop` is clicked:
        1.  Stop `AdbWorker`.
        2.  Reset Menu Text.

### 4. Handling Filter Changes
If the user modifies filters while streaming:
- We continue to use the existing `apply_filters()` logic.
- Takes the *entire* `all_lines` (which now includes the streamed history), re-runs the full `FilterWorker` in the background, and updates the view. This is consistent with static file behavior and correct.

## Step-by-Step Implementation

1.  **Define `AdbWorker`**: Create the thread class to manage the subprocess.
2.  **Update `LogModel`**:
    - Add `clear()` method.
    - Add `append_chunk(lines)` method.
    - Implement the "incremental filter check" logic within `append_chunk` to decide which of the new lines are visible.
3.  **Update `LogAnalysisMainWindow`**:
    - Add the "Monitor" menu.
    - Add `toggle_adb_monitoring()` slot.
    - Connect `AdbWorker` signals to `LogModel.append_chunk`.
4.  **Auto-Scroll**: Ensure the `QListView` scrolls to the bottom when new logs arrive (optional but expected behavior for monitoring).

## Verification
1.  **Refactor Check**: Ensure the new Streaming logic doesn't break the high-performance static file loading.
2.  **Live Test**: Run with a connected Emulator or Device.
3.  **Filter Test**: Add a filter (e.g., "ActivityManager") while streaming and verify only those lines appear.
4.  **Clear Test**: Stop and Start again to ensure the buffer flushes.
