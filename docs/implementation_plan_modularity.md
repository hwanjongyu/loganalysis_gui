# Implementation Plan - Modularity Refactoring

Refactor the single-file `src/loganalysis_gui.py` (~1,600 lines) into a modular package structure to improve maintainability, readability, and testability.

## Proposed Package Structure

```text
src/
├── main.py                 # Entry point (Bootstrap)
└── loganalysis_gui/        # Main Package
    ├── __init__.py         # Package initialization
    ├── constants.py        # COLOR_MAP, STYLESHEET, etc.
    ├── workers.py          # AdbWorker, FilterWorker
    ├── models.py           # LogModel
    ├── widgets.py          # FilterItemWidget
    ├── dialogs.py          # FilterDialog, FindDialog
    └── main_window.py      # LogAnalysisMainWindow
```

## Step-by-Step implementation

### 1. Preparation
- Create the `src/loganalysis_gui/` directory.
- Create empty `__init__.py`.

### 2. Extract Constants (`constants.py`)
- Move `COLOR_MAP`, `TEXT_COLOR_MAP`, and `STYLESHEET` strings.
- This prevents circular dependencies as almost all modules need these.

### 3. Extract Workers (`workers.py`)
- Move `AdbWorker` and `FilterWorker`.
- Dependency: `PyQt5`, `re`, `subprocess`.

### 4. Extract Models (`models.py`)
- Move `LogModel`.
- Dependency: `PyQt5`, `re`, `bisect`, and `constants.py`.

### 5. Extract Dialogs & Widgets (`dialogs.py`, `widgets.py`)
- Move `FindDialog`, `FilterDialog`.
- Move `FilterItemWidget`.
- Dependency: `PyQt5` and `constants.py`.

### 6. Extract Main Window (`main_window.py`)
- Move `LogAnalysisMainWindow`.
- This is the most complex part as it ties everything together.
- Update all imports to use the new local modules.

### 7. Entry Point (`main.py`)
- Create a clean `main.py` that handles `QApplication` setup and shows the `LogAnalysisMainWindow`.

### 8. Cleanup & Redirect
- Update `src/loganalysis_gui.py` to simply import and run the new modular code (for backward compatibility during testing) or replace it entirely.

## Verification Plan ✅ (Completed)
1. **Import Test**: Run `main.py` and ensure no `ImportError`. - **Success**
2. **Functional Smoke Test**:
    - Open a log file. - **Success**
    - Start ADB monitoring. - **Success**
    - Add/Edit a filter (test dialogs + models). - **Success**
    - Use "Find" functionality. - **Success**
3. **Style Check**: Verify Dark Mode styling is still correctly applied via `constants.py`. - **Success**
4. **Performance Check**: Ensure no regressions in virtualization or filtering speed. - **Success**
