# 🚀 LogAnalysisGUI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LogAnalysisGUI** is a high-performance, cross-platform graphical tool designed for surgical log analysis. Inspired by the classic *TestAnalysisTool*, it brings professional-grade log exploration, filtering, and real-time monitoring to Windows, macOS, and Linux.

---

## ✨ Key Features

### 🚄 Unparalleled Performance
Built on a high-speed **Model-View Architecture**, LogAnalysisGUI handles files with millions of lines smoothly. By virtualizing the presentation layer, the UI remains responsive even when processing gigabytes of data.

### 🤖 Real-time ADB Monitoring
Stream logs directly from connected Android devices via `adb logcat`.
- **Live Filtering**: Apply complex filters to the stream in real-time.
- **Auto-Scroll**: Keep up with high-velocity logs automatically.
- **Start/Pause**: Stop the stream to investigate, then resume without losing context.

### 🔍 Advanced Filter System
The heart of LogAnalysisGUI is its powerful multi-layered filtering engine:
- **Include/Exclude/Highlight**: Precisely control what you see and what you hide.
- **Regex Support**: Use standard regular expressions for complex pattern matching.
- **Match Counting**: Instantly see how many times each filter triggers across the dataset.
- **Persistent Profiles**: Save and load filter sets (JSON) for recurring analysis tasks.
- **Color Coding**: Customize background and foreground colors for instant visual recognition.

### 🎨 Modern & Responsive UI
- **Dark Mode Support**: Seamlessly switch between light and dark themes.
- **Tabbed Management**: Organize logic into separate filter tabs for different analysis contexts.
- **Smart Selection**: Intelligently copy log data with optional line numbers.
- **Zoom Control**: On-the-fly font size adjustment with `Ctrl +` and `Ctrl -`.

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
python src/loganalysis_gui.py
```

---

## 💡 Inspiration

`LogAnalysisGUI` is heavily inspired by [TestAnalysisTool](https://textanalysistool.github.io/). This project aims to bring that beloved workflow to the modern, cross-platform era while adding advanced features like real-time ADB streaming and multi-threaded performance.

---

## 📄 License
Distributed under the MIT License.