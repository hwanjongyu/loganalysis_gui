# Implementation Plan - Add Filter Dialog UI Polish

This plan outlines the visual and functional enhancements for the `Add / Edit Filter` dialog to make it feel more premium and intuitive.

## Proposed Changes

### 1. Enhanced `FilterDialog` Layout
- Use a cleaner `QVBoxLayout` with consistent margins and spacing.
- Improve the `Match Criteria` section with a clearer layout.
- Use a dedicated `Preview` section that looks more like a log entry.

### 2. Color Combo Boxes with Icons
- Subclass or enhance `QComboBox` to show a small colored square next to each color name.
- This helps users quickly identify colors without reading every name.

### 3. Styled Preview
- Make the preview label look like a real row in the log view.
- Support "Exclude" (NOT) visual cues in the preview if possible (e.g., strikethrough or a specific icon).

### 4. General Aesthetics
- Consistent font usage (Monospace for the text input and preview).
- Better padding and button placement.

## Verification Plan
1. **Visual Check**:
   - Open the "Add Filter" dialog.
   - Verify that color combo boxes show color icons.
2. **Interactive Preview**:
   - Type text in the input.
   - Change colors.
   - Verify the preview updates instantly and accurately reflects how the filter will look in the main log view.
3. **Functional Check**:
   - Save a filter from the polished dialog.
   - Verify it is applied correctly to the log list.
