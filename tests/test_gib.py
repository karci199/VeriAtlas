"""GİB active taxpayers: the silent paths the TOPLAM check does not cover."""

import datetime as dt

from veriatlas.adapters.gib import month_of, number, scrambled


def test_text_cell_thousands_dot_is_not_a_decimal_point():
    # 2013 corporate tax, previous December: "\xa012.630\xa0" is 12,630, not 12.63.
    assert number("\xa012.630\xa0") == 12630
    assert number(12630.0) == 12630
    assert number("") is None


def test_date_header_cell():
    # 2005 heads its month columns with Excel dates.
    assert month_of(dt.date(2005, 3, 1)) == dt.date(2005, 3, 1)
    assert month_of("ARALIK-2020") == dt.date(2020, 12, 1)


def _series(values_by_month):
    return {
        (f"TR-{i:02d}", month): value
        for month, values in values_by_month.items()
        for i, value in enumerate(values, start=1)
    }


def test_shifted_column_is_dropped_but_a_real_step_is_kept():
    base = [1000.0 * (1 + 9 * (i % 2)) + i for i in range(20)]  # neighbours differ
    shifted = base[1:] + base[:1]  # same total, values one row down
    stepped = [v * (2 if i < 10 else 1) for i, v in enumerate(base)]  # holds after
    table = _series(
        {
            dt.date(2025, 5, 1): base,
            dt.date(2025, 6, 1): shifted,
            dt.date(2025, 7, 1): base,
            dt.date(2025, 8, 1): stepped,
            dt.date(2025, 9, 1): stepped,
        }
    )
    assert scrambled(table) == [dt.date(2025, 6, 1)]


def test_last_month_is_compared_with_the_last_month_kept():
    base = [1000.0 * (1 + 9 * (i % 2)) + i for i in range(20)]  # neighbours differ
    shifted = base[1:] + base[:1]
    table = _series(
        {
            dt.date(2026, 6, 1): base,
            dt.date(2026, 7, 1): shifted,
            dt.date(2026, 8, 1): base,
        }
    )
    assert scrambled(table) == [dt.date(2026, 7, 1)]
