# Shared Color Maps and Styles
MAX_MONITOR_LINES = 200000

COLOR_MAP = {
    "Khaki": "#F0E68C", "Yellow": "#FFFF00", "Gold": "#FFD700", "Cyan": "#00FFFF",
    "Aqua": "#00FFFF", "Green": "#90EE90", "Lime": "#00FF00", "PaleGreen": "#98FB98",
    "Red": "#FFB6B6", "Salmon": "#FA8072", "Coral": "#FF7F50", "Blue": "#B6D0FF",
    "SkyBlue": "#87CEEB", "LightBlue": "#ADD8E6", "Gray": "#D3D3D3", "Silver": "#C0C0C0",
    "White": "#FFFFFF", "Orange": "#FFD580", "Wheat": "#F5DEB3", "Purple": "#E6E6FA",
    "Plum": "#DDA0DD", "Orchid": "#DA70D6", "Brown": "#EEDFCC", "Pink": "#FFD1DC", 
    "HotPink": "#FF69B4", "Violet": "#F3E5F5", "Navy": "#B0C4DE", "Teal": "#B2DFDB", 
    "Olive": "#F5F5DC", "Maroon": "#F4CCCC"
}

TEXT_COLOR_MAP = {
    "Black": "#000000", "Red": "#FF0000", "DarkRed": "#8B0000", "Crimson": "#DC143C",
    "Blue": "#0000FF", "DarkBlue": "#00008B", "RoyalBlue": "#4169E1", "Green": "#008000",
    "DarkGreen": "#006400", "SeaGreen": "#2E8B57", "Gray": "#808080", "DarkGray": "#A9A9A9",
    "White": "#FFFFFF", "Orange": "#FFA500", "DarkOrange": "#FF8C00", "Purple": "#800080",
    "DarkMagenta": "#8B008B", "Indigo": "#4B0082", "Brown": "#A52A2A", "SaddleBrown": "#8B4513",
    "Pink": "#FFC0CB", "DeepPink": "#FF1493", "Violet": "#EE82EE", "Navy": "#000080", 
    "Teal": "#008080", "Olive": "#808000", "Maroon": "#800000"
}

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1a1e;
    color: #e2e2e6;
}
QListView, QTreeView {
    background-color: #121214;
    color: #e2e2e6;
    border: 1px solid #2e2e34;
    selection-background-color: #2e303e;
    selection-color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #2e2e34;
    background-color: #1a1a1e;
}
QTabBar::tab {
    background-color: #121214;
    color: #a0a0a5;
    border: 1px solid #2e2e34;
    border-bottom-color: transparent;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1a1a1e;
    color: #ffffff;
    font-weight: bold;
    border-bottom-color: #1a1a1e;
}
QLineEdit, QComboBox, QCheckBox {
    background-color: #121214;
    color: #e2e2e6;
    border: 1px solid #2e2e34;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4a5a8a;
}
QPushButton {
    background-color: #2e303e;
    color: #ffffff;
    border: 1px solid #3e405e;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #3e425e;
}
QPushButton:pressed {
    background-color: #1e202e;
}
QStatusBar {
    background-color: #121214;
    color: #8a8a90;
    border-top: 1px solid #2e2e34;
}
QMenuBar {
    background-color: #1a1a1e;
    color: #e2e2e6;
    border-bottom: 1px solid #2e2e34;
}
QMenuBar::item:selected {
    background-color: #2e303e;
}
QMenu {
    background-color: #1a1a1e;
    color: #e2e2e6;
    border: 1px solid #2e2e34;
}
QMenu::item:selected {
    background-color: #2e303e;
}
QLabel {
    color: #e2e2e6;
}
QProgressBar {
    border: 1px solid #2e2e34;
    border-radius: 4px;
    text-align: center;
    background-color: #121214;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #3e5a9a;
    border-radius: 3px;
}
QGroupBox {
    border: 1px solid #2e2e34;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 3px;
}
"""

LIGHT_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f4f4f7;
    color: #2c2c30;
}
QListView, QTreeView {
    background-color: #ffffff;
    color: #2c2c30;
    border: 1px solid #dcdce2;
    selection-background-color: #e2e6f0;
    selection-color: #1c1c20;
}
QTabWidget::pane {
    border: 1px solid #dcdce2;
    background-color: #f4f4f7;
}
QTabBar::tab {
    background-color: #e8e8ee;
    color: #6a6a70;
    border: 1px solid #dcdce2;
    border-bottom-color: transparent;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #f4f4f7;
    color: #1c1c20;
    font-weight: bold;
    border-bottom-color: #f4f4f7;
}
QLineEdit, QComboBox, QCheckBox {
    background-color: #ffffff;
    color: #2c2c30;
    border: 1px solid #dcdce2;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #8a9ac0;
}
QPushButton {
    background-color: #e2e6f0;
    color: #1c1c20;
    border: 1px solid #cbd2e0;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #d2daf0;
}
QPushButton:pressed {
    background-color: #c2cbdc;
}
QStatusBar {
    background-color: #e8e8ee;
    color: #6a6a70;
    border-top: 1px solid #dcdce2;
}
QMenuBar {
    background-color: #f4f4f7;
    color: #2c2c30;
    border-bottom: 1px solid #dcdce2;
}
QMenuBar::item:selected {
    background-color: #e2e6f0;
}
QMenu {
    background-color: #ffffff;
    color: #2c2c30;
    border: 1px solid #dcdce2;
}
QMenu::item:selected {
    background-color: #e2e6f0;
}
QLabel {
    color: #2c2c30;
}
QProgressBar {
    border: 1px solid #dcdce2;
    border-radius: 4px;
    text-align: center;
    background-color: #ffffff;
    color: #1c1c20;
}
QProgressBar::chunk {
    background-color: #8a9ac0;
    border-radius: 3px;
}
QGroupBox {
    border: 1px solid #dcdce2;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 3px;
}
"""
