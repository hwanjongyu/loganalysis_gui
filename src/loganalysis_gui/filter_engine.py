import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple


@dataclass(frozen=True)
class PreparedFilter:
    filter_data: Dict[str, Any]
    original_index: int
    compiled_re: Optional[Pattern[str]] = None


def prepare_filters(filters: Sequence[Dict[str, Any]]) -> List[PreparedFilter]:
    prepared_filters = []
    for index, filter_data in enumerate(filters):
        if not filter_data.get("active", True):
            continue

        compiled_re = None
        if filter_data["regex"]:
            flags = 0 if filter_data["case_sensitive"] else re.IGNORECASE
            compiled_re = re.compile(filter_data["text"], flags)

        prepared_filters.append(
            PreparedFilter(
                filter_data=filter_data,
                original_index=index,
                compiled_re=compiled_re,
            )
        )
    return prepared_filters


def filter_matches_line(
    line: str,
    filter_data: Dict[str, Any],
    compiled_re: Optional[Pattern[str]] = None,
) -> bool:
    if filter_data["regex"]:
        regex = compiled_re
        if regex is None:
            flags = 0 if filter_data["case_sensitive"] else re.IGNORECASE
            regex = re.compile(filter_data["text"], flags)
        return bool(regex.search(line))

    if filter_data["case_sensitive"]:
        return filter_data["text"] in line
    return filter_data["text"].lower() in line.lower()


def find_matching_filters(
    line: str,
    prepared_filters: Sequence[PreparedFilter],
) -> List[PreparedFilter]:
    matches = []
    for prepared_filter in prepared_filters:
        if filter_matches_line(
            line,
            prepared_filter.filter_data,
            prepared_filter.compiled_re,
        ):
            matches.append(prepared_filter)
    return matches


def evaluate_line(
    line: str,
    prepared_filters: Sequence[PreparedFilter],
    show_only_filtered: bool,
) -> Tuple[List[PreparedFilter], bool]:
    if not prepared_filters:
        return [], True

    matches = find_matching_filters(line, prepared_filters)
    if not matches:
        return [], not show_only_filtered

    return matches, not matches[-1].filter_data["exclude"]
