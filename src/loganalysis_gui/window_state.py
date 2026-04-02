from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PyQt5.QtWidgets import QCheckBox, QLineEdit, QListWidget, QWidget


@dataclass
class FilterTabState:
    tab_widget: QWidget
    filter_list: QListWidget
    search_input: QLineEdit
    filters: List[dict] = field(default_factory=list)
    enabled: bool = True
    modified: bool = False
    file_path: Optional[str] = None
    checkbox: Optional[QCheckBox] = None


@dataclass
class MainWindowRuntimeState:
    is_monitoring: bool = False
    is_paused: bool = False
    is_refiltering: bool = False
    pending_chunks: List[List[str]] = field(default_factory=list)
    filter_request_id: int = 0
    filter_map_back: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    target_source_idx: int = -1
    scroll_to_bottom_after_refilter: bool = False
