"""KTB 2007-2008 PDF counts: digits grouped only where foreigners + citizens = total."""

from veriatlas.adapters.ktb import split_counts


def test_counts_split_by_the_totals():
    tokens = "17 758 180 975 198 733 34 729 277 296 312 025".split()
    assert split_counts(tokens) == [17758, 180975, 198733, 34729, 277296, 312025]


def test_missing_foreign_cell_is_zero():
    assert split_counts("14 220 14 220 63 014 63 014".split()) == [
        0,
        14220,
        14220,
        0,
        63014,
        63014,
    ]
    assert split_counts("- 268 268 1 470 1 470".split()) == [0, 268, 268, 0, 1470, 1470]


def test_no_split_that_adds_up_is_refused():
    assert split_counts("1 2 4 5 6 7".split()) is None
