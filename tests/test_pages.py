import pytest

from offlinepdf.core import InvalidRangeError, format_selection, parse_ranges, parse_selection


def test_single_pages_and_ranges():
    assert parse_ranges("1, 3-5", 10) == [[0], [2, 3, 4]]


def test_open_ended_ranges():
    assert parse_ranges("8-", 10) == [[7, 8, 9]]
    assert parse_ranges("-2", 10) == [[0, 1]]


def test_reverse_range_and_last_keyword():
    assert parse_ranges("4-2", 10) == [[3, 2, 1]]
    assert parse_selection("end", 7) == [6]
    assert parse_selection("son", 7) == [6]


def test_selection_dedupes_and_keeps_typed_order():
    assert parse_selection("3, 1-3; 2", 5) == [2, 0, 1]


@pytest.mark.parametrize("spec", ["", "0", "11", "a-b", "1-99", "--", "1--3"])
def test_invalid_specs(spec):
    with pytest.raises(InvalidRangeError):
        parse_selection(spec, 10)


def test_format_selection_round_trip():
    indices = [0, 1, 2, 5, 7, 8]
    text = format_selection(indices)
    assert text == "1-3, 6, 8-9"
    assert sorted(parse_selection(text, 10)) == indices
