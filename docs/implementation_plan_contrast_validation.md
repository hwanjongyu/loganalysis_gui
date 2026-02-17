# Implementation Plan - Contrast Validation Logic

Implement a contrast validation system in the `FilterDialog` to warn users when they select color combinations that are difficult to read.

## User Requirements
- **Validation**: Automatically check the contrast ratio between the selected `Background Color` and `Text Color`.
- **Feedback**: Display a warning message if the contrast ratio falls below a usable threshold (WCAG standard).
- **Default Handling**: If one color is set to "None", assume the default theme colors (Dark Mode/Light Mode).

## Proposed Changes

### 1. New Utility: `ContrastCalculations`
Add a helper method (or class) to handle color luminance and contrast:
- **Luminance Calculation**: 
  - Formula: `0.2126 * R + 0.7152 * G + 0.0722 * B` (standard sRGB luminance).
- **Contrast Ratio**: 
  - Formula: `(L1 + 0.05) / (L2 + 0.05)`, where L1 is the lighter and L2 is the darker luminance.

### 2. `FilterDialog` Enhancements
- **Helper `check_contrast(self)`**:
    - Retrieve selected hex codes from `bg_color` and `text_color` combo boxes.
    - If a color is "None", use defaults:
        - `Background: #1e1e1e` (Dark Mode default)
        - `Text: #e0e0e0` (High contrast gray)
    - Calculate the ratio.
- **Visual Warning**:
    - Add a `warning_lbl` (QLabel) above the buttons in `FilterDialog`.
    - Update the label text and color dynamically (e.g., Red text for "Poor Contrast").

### 3. Thresholds (WCAG 2.1)
- **Ratio < 3.0**: Critical (Warn: "Very poor readability!").
- **Ratio < 4.5**: Low (Warn: "Low contrast - may be hard to read.").
- **Ratio >= 4.5**: Good (No warning or green check).

## Step-by-Step Implementation

1.  **Modify `FilterDialog.__init__`**:
    - Initialize `self.contrast_warning = QLabel("")`.
    - Style it with `color: #ff5555; font-weight: bold;`.
2.  **Add `get_luminance(hex_str)` and `calculate_contrast(hex1, hex2)`**:
    - Implement the math.
3.  **Update `FilterDialog.update_preview`**:
    - Call the contrast check.
    - Update the `contrast_warning` label based on the result.

## Verification Plan
1. **Critical Warning**: Select `Background: Yellow` and `Text: White`. Verify a high-priority warning appears.
2. **Safe Pairing**: Select `Background: Navy` and `Text: White`. Verify no warning appears.
3. **Default Check**: Set both to "None". Verify no warning appears (using assumed dark mode defaults).
4. **Dynamic Update**: Verify the warning updates instantly as colors are changed in the combo boxes.
