import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from loganalysis_gui.filter_engine import evaluate_line, filter_matches_line, find_matching_filters, prepare_filters


def make_filter(text, *, active=True, regex=False, case_sensitive=False, exclude=False):
    return {
        "text": text,
        "case_sensitive": case_sensitive,
        "regex": regex,
        "exclude": exclude,
        "bg_color": "None",
        "text_color": "None",
        "active": active,
    }


class FilterEngineTests(unittest.TestCase):
    def test_no_active_filters_show_everything(self):
        prepared_filters = prepare_filters([make_filter("alpha", active=False)])

        matches, is_visible = evaluate_line("beta\n", prepared_filters, show_only_filtered=True)

        self.assertEqual(matches, [])
        self.assertTrue(is_visible)

    def test_find_matching_filters_skips_inactive_filters(self):
        filters = [
            make_filter("alpha", active=False),
            make_filter("alpha"),
        ]

        matches = find_matching_filters("alpha\n", prepare_filters(filters))

        self.assertEqual([match.original_index for match in matches], [1])

    def test_last_matching_filter_decides_visibility(self):
        filters = [
            make_filter("alpha"),
            make_filter("alpha", exclude=True),
        ]

        matches, is_visible = evaluate_line("alpha\n", prepare_filters(filters), show_only_filtered=True)
        self.assertEqual([match.original_index for match in matches], [0, 1])
        self.assertFalse(is_visible)

        filters.reverse()
        matches, is_visible = evaluate_line("alpha\n", prepare_filters(filters), show_only_filtered=True)
        self.assertEqual([match.original_index for match in matches], [0, 1])
        self.assertTrue(is_visible)

    def test_non_matching_line_respects_show_only_filtered(self):
        prepared_filters = prepare_filters([make_filter("alpha")])

        matches, is_visible = evaluate_line("beta\n", prepared_filters, show_only_filtered=True)
        self.assertEqual(matches, [])
        self.assertFalse(is_visible)

        matches, is_visible = evaluate_line("beta\n", prepared_filters, show_only_filtered=False)
        self.assertEqual(matches, [])
        self.assertTrue(is_visible)

    def test_filter_matches_line_handles_case_and_regex(self):
        case_sensitive_filter = make_filter("Alpha", case_sensitive=True)
        case_insensitive_filter = make_filter("Alpha")
        regex_filter = make_filter(r"alpha\d+", regex=True)

        self.assertFalse(filter_matches_line("alpha\n", case_sensitive_filter))
        self.assertTrue(filter_matches_line("alpha\n", case_insensitive_filter))
        self.assertTrue(filter_matches_line("ALPHA42\n", regex_filter))

    def test_regex_compilation_uses_cache(self):
        from loganalysis_gui.filter_engine import get_compiled_regex, _REGEX_CACHE
        _REGEX_CACHE.clear()

        regex1 = get_compiled_regex("alpha.*", case_sensitive=True)
        regex2 = get_compiled_regex("alpha.*", case_sensitive=True)

        self.assertIs(regex1, regex2)
        self.assertEqual(len(_REGEX_CACHE), 1)


if __name__ == "__main__":
    unittest.main()
