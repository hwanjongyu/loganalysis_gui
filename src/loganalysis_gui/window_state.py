from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PyQt5.QtWidgets import QCheckBox, QLineEdit, QListWidget, QWidget


@dataclass
class FilterTabData:
    """Pure domain data model for a filter tab, decoupled from Qt widgets."""
    name: str = "Filter 1"
    filters: List[dict] = field(default_factory=list)
    enabled: bool = True
    modified: bool = False
    file_path: Optional[str] = None


@dataclass
class FilterTabWidgets:
    """Qt UI widgets associated with a filter tab presentation."""
    tab_widget: Optional[QWidget] = None
    filter_list: Optional[QListWidget] = None
    search_input: Optional[QLineEdit] = None
    checkbox: Optional[QCheckBox] = None


class FilterTabState:
    """Composite state that connects pure domain FilterTabData with UI FilterTabWidgets."""

    def __init__(
        self,
        tab_widget: Optional[QWidget] = None,
        filter_list: Optional[QListWidget] = None,
        search_input: Optional[QLineEdit] = None,
        filters: Optional[List[dict]] = None,
        enabled: bool = True,
        modified: bool = False,
        file_path: Optional[str] = None,
        checkbox: Optional[QCheckBox] = None,
        data: Optional[FilterTabData] = None,
        widgets: Optional[FilterTabWidgets] = None,
    ):
        if data is not None:
            self.data = data
        else:
            self.data = FilterTabData(
                filters=filters if filters is not None else [],
                enabled=enabled,
                modified=modified,
                file_path=file_path,
            )

        if widgets is not None:
            self.widgets = widgets
        elif (
            tab_widget is not None
            or filter_list is not None
            or search_input is not None
            or checkbox is not None
        ):
            self.widgets = FilterTabWidgets(
                tab_widget=tab_widget,
                filter_list=filter_list,
                search_input=search_input,
                checkbox=checkbox,
            )
        else:
            self.widgets = None

    @property
    def filters(self) -> List[dict]:
        return self.data.filters

    @filters.setter
    def filters(self, val: List[dict]):
        self.data.filters = val

    @property
    def enabled(self) -> bool:
        return self.data.enabled

    @enabled.setter
    def enabled(self, val: bool):
        self.data.enabled = val

    @property
    def modified(self) -> bool:
        return self.data.modified

    @modified.setter
    def modified(self, val: bool):
        self.data.modified = val

    @property
    def file_path(self) -> Optional[str]:
        return self.data.file_path

    @file_path.setter
    def file_path(self, val: Optional[str]):
        self.data.file_path = val

    @property
    def tab_widget(self) -> Optional[QWidget]:
        return self.widgets.tab_widget if self.widgets else None

    @tab_widget.setter
    def tab_widget(self, val: Optional[QWidget]):
        if self.widgets is None:
            self.widgets = FilterTabWidgets(tab_widget=val)
        else:
            self.widgets.tab_widget = val

    @property
    def filter_list(self) -> Optional[QListWidget]:
        return self.widgets.filter_list if self.widgets else None

    @filter_list.setter
    def filter_list(self, val: Optional[QListWidget]):
        if self.widgets is None:
            self.widgets = FilterTabWidgets(filter_list=val)
        else:
            self.widgets.filter_list = val

    @property
    def search_input(self) -> Optional[QLineEdit]:
        return self.widgets.search_input if self.widgets else None

    @search_input.setter
    def search_input(self, val: Optional[QLineEdit]):
        if self.widgets is None:
            self.widgets = FilterTabWidgets(search_input=val)
        else:
            self.widgets.search_input = val

    @property
    def checkbox(self) -> Optional[QCheckBox]:
        return self.widgets.checkbox if self.widgets else None

    @checkbox.setter
    def checkbox(self, val: Optional[QCheckBox]):
        if self.widgets is None:
            self.widgets = FilterTabWidgets(checkbox=val)
        else:
            self.widgets.checkbox = val


@dataclass
class MainWindowRuntimeState:
    is_monitoring: bool = False
    is_paused: bool = False
    is_refiltering: bool = False
    is_loading_file: bool = False
    loaded_file_path: Optional[str] = None
    pending_chunks: List[List[str]] = field(default_factory=list)
    filter_request_id: int = 0
    file_load_request_id: int = 0
    filter_map_back: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    target_source_idx: int = -1
    scroll_to_bottom_after_refilter: bool = False
    loading_file_path: Optional[str] = None
    pending_status_message: Optional[str] = None
