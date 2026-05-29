# 🚀 LogAnalysisGUI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LogAnalysisGUI** is a high-performance, cross-platform graphical tool designed for surgical log analysis. Inspired by the classic *TestAnalysisTool*, it brings professional-grade log exploration, filtering, and real-time monitoring to Windows, macOS, and Linux.

---

## ✨ Key Features

### 🚄 Unparalleled Performance
Built on a high-speed **Model-View Architecture**, LogAnalysisGUI handles files with millions of lines smoothly. By virtualizing the presentation layer, the UI remains responsive even when processing gigabytes of data.
- **Background File Loading**: Large log files now load off the UI thread with status-bar progress feedback, so opening them does not freeze the window.

### 🤖 Real-time ADB Monitoring
Stream logs directly from connected Android devices via `adb logcat`.
- **Live Filtering**: Apply complex filters to the stream in real-time.
- **Auto-Scroll**: Keep up with high-velocity logs automatically.
- **Start/Pause**: Stop the stream to investigate, then resume without losing context.
- **Bounded Live Buffer**: Long monitoring sessions keep a rolling in-memory window instead of growing without limit.
- **Multi-Device Target Selector**: Scan connected emulators and devices dynamically, selecting and targeting streams via specific serials (`adb -s <serial> logcat`) right from the toolbar.

### 🔍 Advanced Filter System
The heart of LogAnalysisGUI is its powerful multi-layered filtering engine:
- **Include/Exclude/Highlight**: Precisely control what you see and what you hide.
- **Regex Support**: Use standard regular expressions for complex pattern matching.
- **Match Counting**: Instantly see how many times each filter triggers across the dataset.
- **Persistent Profiles**: Save and load filter sets (JSON) for recurring analysis tasks.
- **Color Coding**: Customize background and foreground colors for instant visual recognition.
- **Tab-Local Filter Search**: Narrow large filter sets in-place without changing the actual log-filter result.
- **Right-Click Filter Actions**: Edit, duplicate, delete, or copy a filter pattern directly from the list.
- **Context-Sensitive Log Filters**: Right-click directly on any log row to instantly generate and append an Include or Exclude filter matching that exact string into your active tab.

### 🎨 Modern & Responsive UI
- **Dark Mode Support**: Seamlessly switch between light and dark themes.
- **Tabbed Management**: Organize logic into separate filter tabs for different analysis contexts.
- **Mode Badges**: Quick Filter toolbar badges show whether you are viewing matches only and whether full-line display is active.
- **Load Progress Feedback**: The status bar shows file-open progress, keeps the current log visible until the new file is ready, and keeps the loaded file name visible after transient status updates.
- **Smart Selection**: Intelligently copy log data with optional line numbers.
- **Zoom Control**: On-the-fly font size adjustment with `Ctrl +` and `Ctrl -`.
- **Theme-Aware Contrast Verification**: Dynamic contrast previews that adapt to whether a light or dark theme is active, ensuring WCAG accessibility warnings are always accurate.

---

## 🏗️ Architecture

The application follows a robust **threaded architecture** to ensure the main interface never freezes:
- **LogModel**: The central source of truth, managing visibility and styling.
- **FilterWorker**: Background thread that handles heavy regex computations.
- **AdbWorker**: Manages the `adb` subprocess and buffers incoming streams for efficient UI updates.

---

## 🚀 Getting Started

### Requirements
- **Python 3.8+**
- **PyQt5**
- **ADB (Android Debug Bridge)** - *Optional, for real-time monitoring*

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/hwanjongyu/loganalysis_gui.git
   cd loganalysis_gui
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the App
```bash
python src/main.py
```

`src/loganalysis_gui.py` remains as a compatibility wrapper, but `src/main.py` is the canonical entry point.

### Running Tests
```bash
python -m unittest discover -v
```

### Packaging
Build the highly optimized, lightweight desktop bundle with PyInstaller (configured to exclude unused heavy Qt modules, reducing output standalone binary to under 45MB):

```bash
pyinstaller loganalysis_gui.spec
```

If you need Qt plugin diagnostics while debugging a packaged build, set the flag before launching the packaged app:

```bash
LOGANALYSIS_QT_DEBUG_PLUGINS=1 ./dist/loganalysis_gui
```

---

## 💡 Inspiration

`LogAnalysisGUI` is heavily inspired by [TestAnalysisTool](https://textanalysistool.github.io/). This project aims to bring that beloved workflow to the modern, cross-platform era while adding advanced features like real-time ADB streaming and multi-threaded performance.

---

## 📄 License
Distributed under the MIT License.
