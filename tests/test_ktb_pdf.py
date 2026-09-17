"""KTB 2007-2008 PDF counts: digits grouped only where foreigners + citizens = total."""

from veriatlas.adapters.ktb import split_counts


def cells(line: str) -> list[str]:
    """A row as the PDF text layer gives it."""
    return line.split()


def test_counts_split_by_the_totals():
    tokens = cells("17 758 180 975 198 733 34 729 277 296 312 025")
    assert split_counts(tokens) == [17758, 180975, 198733, 34729, 277296, 312025]


def test_missing_foreign_cell_is_zero():
    assert split_counts(cells("14 220 14 220 63 014 63 014")) == [
        0,
        14220,
        14220,
        0,
        63014,
        63014,
    ]
    assert split_counts(cells("- 268 268 1 470 1 470")) == [0, 268, 268, 0, 1470, 1470]


def test_no_split_that_adds_up_is_refused():
    assert split_counts(cells("1 2 4 5 6 7")) is None
