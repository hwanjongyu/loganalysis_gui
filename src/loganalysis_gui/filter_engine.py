import re
import functools
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple

import threading

_REGEX_CACHE_LOCK = threading.Lock()
_REGEX_CACHE: Dict[Tuple[str, bool], Pattern[str]] = {}

def get_compiled_regex(pattern: str, case_sensitive: bool) -> Pattern[str]:
    key = (pattern, case_sensitive)
    with _REGEX_CACHE_LOCK:
        if key not in _REGEX_CACHE:
            if len(_REGEX_CACHE) >= 1024:
                _REGEX_CACHE.clear()
            flags = 0 if case_sensitive else re.IGNORECASE
            _REGEX_CACHE[key] = re.compile(pattern, flags)
        return _REGEX_CACHE[key]


@dataclass(frozen=True)
class PreparedFilter:
    filter_data: Dict[str, Any]
    original_index: int
    compiled_re: Optional[Pattern[str]] = None
    lowered_text: str = ""


def prepare_filters(filters: Sequence[Dict[str, Any]]) -> List[PreparedFilter]:
    prepared_filters = []
    for index, filter_data in enumerate(filters):
        if not filter_data.get("active", True) or not filter_data.get("text"):
            continue

        compiled_re = None
        lowered_text = ""
        if filter_data["regex"]:
            compiled_re = get_compiled_regex(filter_data["text"], filter_data["case_sensitive"])
        elif not filter_data["case_sensitive"]:
            lowered_text = filter_data["text"].lower()

        prepared_filters.append(
            PreparedFilter(
                filter_data=filter_data,
                original_index=index,
                compiled_re=compiled_re,
                lowered_text=lowered_text,
            )
        )
    return prepared_filters


def filter_matches_line(
    line: str,
    filter_data: Dict[str, Any],
    compiled_re: Optional[Pattern[str]] = None,
    lowered_text: str = "",
    line_lower: Optional[str] = None,
) -> bool:
    if filter_data["regex"]:
        regex = compiled_re
        if regex is None:
            regex = get_compiled_regex(filter_data["text"], filter_data["case_sensitive"])
        return bool(regex.search(line))

    if filter_data["case_sensitive"]:
        return filter_data["text"] in line
    haystack = line_lower if line_lower is not None else line.lower()
    needle = lowered_text or filter_data["text"].lower()
    return needle in haystack


def find_matching_filters(
    line: str,
    prepared_filters: Sequence[PreparedFilter],
    line_lower: Optional[str] = None,
) -> List[PreparedFilter]:
    if line_lower is None and any(not f.compiled_re and not f.filter_data["case_sensitive"] for f in prepared_filters):
        line_lower = line.lower()

    matches = []
    for prepared_filter in prepared_filters:
        if filter_matches_line(
            line,
            prepared_filter.filter_data,
            prepared_filter.compiled_re,
            prepared_filter.lowered_text,
            line_lower=line_lower,
        ):
            matches.append(prepared_filter)
    return matches


def evaluate_line(
    line: str,
    prepared_filters: Sequence[PreparedFilter],
    show_only_filtered: bool,
    line_lower: Optional[str] = None,
) -> Tuple[List[PreparedFilter], bool]:
    if not prepared_filters:
        return [], True

    matches = find_matching_filters(line, prepared_filters, line_lower=line_lower)
    if not matches:
        return [], not show_only_filtered

    return matches, not matches[-1].filter_data["exclude"]
