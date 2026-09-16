"""Mobile churn rates by operator, read off the chart images of the BTK market reports.

"Mobil İşletmecilerin Abone Kayıp Oranları (Churn Rate), %" prints a data table under the
chart, monthly for the last twelve months — but the whole figure is an image, so the numbers
are not in the text layer. Each first-quarter report was rendered (pypdfium2, scale 4, the
band under the caption) and its table transcribed by eye.

Reports read: 2017-Q1 … 2026-Q1 first quarters. Together they cover April 2016 … March 2026
with one gap, April 2018 … February 2019: the 2019 reports are laid out as a magazine and
their figure captions are inside the images, so the chart could not be located.

Checks (run by the adapter): where two reports overlap, the month must agree; the sentence
above the chart states the last month, which must match the table's last column.
"""

from __future__ import annotations

OPERATORS = ("tt_mobil", "vodafone", "turkcell")  # "Avea" before 2018 is TT Mobil
MONTHS = {
    "2017-Q1": (2016, 4),
    "2018-Q1": (2017, 4),
    "2020-Q1": (2019, 3),
    "2021-Q1": (2020, 3),
    "2022-Q1": (2021, 3),
    "2023-Q1": (2022, 3),
    "2024-Q1": (2023, 3),
    "2025-Q1": (2024, 3),
    "2026-Q1": (2025, 3),
}
#: report -> operator -> the table's row, first month first
ROWS = {
    "2017-Q1": {  # Nisan 16 … Mart 17, operator named "Avea"
        "tt_mobil": [2.7, 2.7, 2.7, 2.5, 2.3, 2.2, 2.2, 2.2, 2.4, 2.4, 2.4, 2.8],
        "vodafone": [2.7, 2.7, 2.6, 2.4, 2.4, 2.2, 2.4, 2.1, 2.5, 2.2, 2.4, 2.8],
        "turkcell": [2.6, 3.3, 2.4, 2.4, 2.2, 1.9, 1.9, 1.8, 1.9, 1.9, 1.8, 1.4],
    },
    "2018-Q1": {  # Nisan 17 … Mart 18, "Avea"
        "tt_mobil": [2.6, 2.7, 2.6, 2.7, 2.3, 2.1, 2.1, 2.1, 2.3, 2.2, 2.3, 2.3],
        "vodafone": [2.6, 2.6, 2.4, 2.5, 2.3, 2.1, 2.2, 2.1, 2.5, 2.2, 2.2, 2.5],
        "turkcell": [1.2, 1.3, 1.7, 1.9, 2.0, 1.7, 1.9, 1.8, 3.6, 1.5, 1.3, 1.5],
    },
    "2020-Q1": {  # Mart 19 … Mart 20 (13 columns)
        "tt_mobil": [2.1, 2.4, 2.4, 2.4, 2.6, 2.8, 2.6, 2.6, 2.5, 2.6, 2.5, 2.4, 2.1],
        "vodafone": [2.0, 2.7, 2.0, 2.0, 2.3, 2.0, 2.7, 2.2, 2.3, 5.0, 2.2, 2.3, 2.1],
        "turkcell": [1.8, 1.9, 2.0, 2.2, 2.9, 2.3, 2.4, 2.4, 6.9, 4.2, 2.1, 2.1, 1.9],
    },
    "2021-Q1": {  # Mart 20 … Mart 21
        "tt_mobil": [2.1, 2.3, 2.7, 2.9, 2.5, 2.2, 2.3, 2.2, 2.4, 2.6, 2.1, 1.9, 2.1],
        "vodafone": [2.1, 1.5, 1.8, 2.1, 1.9, 1.6, 1.6, 1.8, 1.5, 5.4, 1.5, 1.4, 1.7],
        "turkcell": [1.9, 1.5, 1.7, 2.5, 2.5, 2.4, 2.4, 2.2, 2.4, 4.3, 1.7, 1.6, 2.0],
    },
    "2022-Q1": {  # Mart 21 … Mart 22
        "tt_mobil": [2.1, 1.8, 1.6, 2.0, 1.8, 1.9, 1.8, 1.7, 2.1, 2.2, 1.6, 1.7, 1.8],
        "vodafone": [1.7, 1.4, 1.0, 1.5, 1.4, 1.4, 1.6, 1.4, 1.3, 6.3, 1.5, 1.4, 1.6],
        "turkcell": [2.0, 1.7, 1.3, 2.0, 1.8, 2.0, 2.0, 1.9, 2.3, 3.4, 1.6, 1.6, 1.6],
    },
    "2023-Q1": {  # Mart 22 … Mart 23
        "tt_mobil": [1.8, 1.5, 1.7, 2.2, 1.7, 1.8, 1.7, 1.7, 1.7, 3.1, 1.7, 1.2, 2.0],
        "vodafone": [1.6, 1.2, 1.2, 1.2, 1.0, 1.2, 1.4, 1.7, 1.7, 5.5, 1.4, 1.0, 1.3],
        "turkcell": [1.6, 1.7, 1.7, 1.8, 1.8, 2.1, 1.9, 2.1, 2.1, 3.8, 2.1, 1.2, 1.9],
    },
    "2024-Q1": {  # Mart 23 … Mart 24
        "tt_mobil": [2.0, 1.8, 2.3, 1.7, 1.7, 1.9, 1.7, 2.2, 2.4, 2.0, 1.6, 1.8, 2.0],
        "vodafone": [1.3, 1.2, 1.5, 1.1, 1.4, 1.4, 2.2, 1.8, 2.0, 3.4, 1.3, 1.1, 1.2],
        "turkcell": [1.9, 1.9, 2.1, 1.7, 1.9, 2.0, 1.9, 2.1, 2.0, 3.0, 1.7, 1.5, 1.5],
    },
    "2025-Q1": {  # Mart 24 … Mart 25
        "tt_mobil": [2.0, 1.8, 2.1, 1.8, 1.6, 2.6, 1.9, 1.9, 1.9, 4.2, 1.3, 1.7, 2.2],
        "vodafone": [1.2, 0.9, 1.3, 2.1, 1.4, 2.2, 2.4, 1.4, 1.5, 4.8, 1.1, 1.3, 2.2],
        "turkcell": [1.5, 1.4, 1.7, 1.6, 2.0, 2.5, 2.0, 2.0, 2.0, 4.4, 1.7, 1.6, 1.9],
    },
    "2026-Q1": {  # Mart 25 … Mart 26
        "tt_mobil": [2.2, 2.5, 2.5, 2.2, 2.1, 1.8, 1.8, 2.5, 2.4, 3.6, 2.1, 1.5, 1.5],
        "vodafone": [2.2, 2.3, 2.4, 2.3, 2.4, 2.3, 3.0, 2.4, 2.6, 3.6, 1.8, 1.6, 2.0],
        "turkcell": [1.9, 2.2, 2.3, 2.0, 2.5, 2.7, 2.5, 2.5, 2.2, 3.4, 1.6, 1.7, 1.6],
    },
}
#: the last month as the sentence above each chart states it
SENTENCES = {
    "2026-Q1": {"tt_mobil": 1.5, "vodafone": 2.0, "turkcell": 1.6},
    "2025-Q1": {"tt_mobil": 2.2, "vodafone": 2.2, "turkcell": 1.9},
}


def series() -> dict[tuple[int, int], dict[str, float]]:
    """(year, month) -> {operator: churn %}, with the overlaps checked."""
    out: dict[tuple[int, int], dict[str, float]] = {}
    for report, rows in ROWS.items():
        year, month = MONTHS[report]
        for index in range(len(rows["turkcell"])):
            period = (year + (month - 1 + index) // 12, (month - 1 + index) % 12 + 1)
            for operator in OPERATORS:
                value = rows[operator][index]
                seen = out.setdefault(period, {}).get(operator)
                if seen is not None and abs(seen - value) > 0.051:
                    raise ValueError(f"{report} {period} {operator}: {seen} ≠ {value}")
                out[period][operator] = value
    for report, stated in SENTENCES.items():
        year, month = MONTHS[report]
        last = len(ROWS[report]["turkcell"]) - 1
        period = (year + (month - 1 + last) // 12, (month - 1 + last) % 12 + 1)
        if out[period] != stated:
            raise ValueError(f"{report}: son ay {out[period]} ≠ cümle {stated}")
    return out


if __name__ == "__main__":
    data = series()
    print(len(data), "ay", min(data), "-", max(data))
