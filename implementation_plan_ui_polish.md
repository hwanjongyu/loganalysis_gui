# Implementation Plan - UI Polish (Phase 2)

This plan focuses on elevating the visual quality and daily usability of the LogAnalysisGUI, moving beyond functional requirements to a polished, professional experience.

## 1. Visual Refresh (Theme & Icons)
**Goal**: Make the application look modern and reduce cognitive load.

- [x] **Dark/Light Mode Toggle**: Implement a `View -> Theme` menu.
    *   **Dark Mode**: specialized QSS (Qt Style Sheet) for dark background, light text, and subdued borders.
    *   **Light Mode**: Default system look.
- [x] **Menu Icons**: Add standard Qt icons (`QStyle.SP_*`) to all menu actions (Open, Save, Exit, Start/Stop, etc.) for quicker visual recognition.

## 2. "Quick Filter" Toolbar
**Goal**: Allow rapid, ad-hoc filtering without opening a modal dialog (addressed from Expert Review).

- [x] **Component**: A new `QToolBar` or widget above the Log View.
- [x] **Elements**:
    *   One `QLineEdit` for text.
    *   Three toggle buttons: `Case`, `Regex`, `Exclude`.
    *   `Add` button.
- [x] **Behavior**: Pressing Enter on the text field immediately creates a temporary active filter or adds it to the current set.

## 3. Enhanced Status Bar
**Goal**: Provide system-level feedback for power users.

- [x] **Widgets**: Add permanent widgets to the right side of the status bar.
    *   **Line Count**: `Total: N | Visible: M`
    *   **Memory Usage**: (Optional) `Mem: XX MB` (Skipped for now)
    *   **Encoding**: `UTF-8` (Skipped for now)

## 4. Filter List Improvements
**Goal**: Make the side panel less "plain list" and more "control panel".

- [x] **Refine item styling**: Add spacing between filter items.
- [x] **Drag & Drop**: Ensure visual feedback when reordering.
- [x] **Match Counts**: Added per-filter match counts (User Request).

## 5. Keyboard Shortcuts Cheat Sheet
**Goal**: Aid discovery of the new features.

- [x] **Action**: Add a `Help -> Shortcuts` dialog showing:
    *   `Ctrl+F`: Find
    *   `Ctrl+Shift+F`: Add Filter
    *   `Space`: Pause Monitoring
    *   `Ctrl +/-`: Zoom

## Execution Order
1.  **Icons & Shortcuts Help**: Low hanging fruit, high impact.
2.  **Quick Filter Toolbar**: High usability value.
3.  **Dark Mode**: High aesthetic value.
4.  **Status Bar**: Polish.
