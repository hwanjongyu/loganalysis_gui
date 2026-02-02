# LogAnalysisGUI

A cross-platform, Python-based graphical user interface for log file analysis.

## Introduction

`LogAnalysisGUI` is a simple yet powerful tool for developers, testers, and support engineers to view, search, and analyze application logs. This project was born out of the need for a cross-platform log analysis tool.

It is heavily inspired by the fantastic [TestAnalysisTool](https://textanalysistool.github.io/), which provides excellent functionality but is limited to the Windows operating system. `LogAnalysisGUI` aims to bring similar features to users on Windows, macOS, and Linux, all thanks to the power of Python and its versatile GUI libraries.

## Features

* **Cross-Platform:** Works on Windows, macOS, and Linux.
* **File Handling:** Easily open and view large log files.
* **Real-time Search:** Search and filter log entries as you type.
* **Highlighting:** Define custom rules to highlight lines containing specific keywords (e.g., "ERROR", "WARN", "DEBUG").
* **Filtering:** Hide or show lines based on content to focus on what's important.
* **Simple Interface:** An intuitive and clean user interface that requires no learning curve.


## Inspiration

This project would not exist without the inspiration from [TestAnalysisTool](https://textanalysistool.github.io/). If you are a Windows user and need a feature-rich, native application, we highly recommend checking it out. `LogAnalysisGUI` is an attempt to recreate its useful core functionality in a cross-platform environment.

## Requirements

* Python 3.8 or newer
* PyQt5

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/hwanjongyu/loganalysis_gui.git](https://github.com/hwanjongyu/loganalysis_gui.git)
    cd LogAnalysisGUI
    ```

2.  **(Recommended) Create a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

## Usage

To launch the application, run the main Python script from the project's root directory:

```bash
python loganalysis_gui.py
```