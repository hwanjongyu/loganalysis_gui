# Shared Color Maps and Styles
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
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QListView, QTreeView {
    background-color: #1e1e1e;
    color: #e0e0e0;
    selection-background-color: #3a3a3a;
    selection-color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #444;
}
QTabBar::tab {
    background: #333;
    color: #aaa;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background: #444;
    color: #fff;
    font-weight: bold;
}
QLineEdit, QComboBox, QCheckBox {
    background-color: #333;
    color: #e0e0e0;
    border: 1px solid #555;
    padding: 2px;
}
QPushButton {
    background-color: #444;
    color: #e0e0e0;
    border: 1px solid #555;
    padding: 5px;
}
QPushButton:hover {
    background-color: #555;
}
QStatusBar {
    background-color: #222;
    color: #888;
}
QMenuBar {
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QMenuBar::item:selected {
    background-color: #444;
}
QMenu {
    background-color: #2b2b2b;
    color: #e0e0e0;
    border: 1px solid #444;
}
QMenu::item:selected {
    background-color: #444;
}
QLabel {
    color: #e0e0e0;
}
"""
