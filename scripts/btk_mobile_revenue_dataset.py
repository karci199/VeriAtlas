"""Revenue from mobile services, read off the chart images of the 2026-Q1 BTK report.

Two charts, both images (rendered with pypdfium2 at scale 4 and transcribed by eye):

* "Şekil 4-24 Yıllar İtibariyle Mobil Hizmetlerden Elde Edilen Gelir, Milyar ₺" — yearly,
  2017-2025, on two accounting bases: IFRS (UFRS) and the Turkish tax code (VUK);
* "Şekil 4-25 Mobil Hizmetlerden Elde Edilen Üç Aylık Gelirler, Milyar ₺" — quarterly,
  2024-1 … 2026-1 (IFRS).

Checks: the report's sentence states the last quarter (104,2 milyar ₺), and the four
quarters of 2025 add up to the year's IFRS figure within rounding.
"""

from __future__ import annotations

#: year -> (IFRS, tax code), billion lira
ANNUAL = {
    2017: (29.8, 26.7),
    2018: (34.7, 30.5),
    2019: (38.9, 34.9),
    2020: (43.0, 39.1),
    2021: (50.2, 45.8),
    2022: (73.2, 65.1),
    2023: (135.1, 119.4),
    2024: (256.2, 219.7),
    2025: (371.7, 333.7),
}
#: (year, quarter) -> IFRS revenue, billion lira
QUARTERLY = {
    (2024, 1): 47.7,
    (2024, 2): 59.9,
    (2024, 3): 71.4,
    (2024, 4): 77.2,
    (2025, 1): 79.2,
    (2025, 2): 89.2,
    (2025, 3): 104.1,
    (2025, 4): 99.3,
    (2026, 1): 104.2,
}
LAST_QUARTER_SENTENCE = 104.2  # "…yaklaşık 104,2 milyar ₺ olarak gerçekleşmiştir."


def check() -> None:
    if QUARTERLY[(2026, 1)] != LAST_QUARTER_SENTENCE:
        raise ValueError("mobil gelir: son çeyrek cümledeki değeri tutmuyor")
    for year in (2024, 2025):
        quarters = sum(QUARTERLY[(year, q)] for q in (1, 2, 3, 4))
        if abs(quarters - ANNUAL[year][0]) > 1.0:
            raise ValueError(
                f"mobil gelir {year}: çeyrekler {quarters:.1f}, yıllık {ANNUAL[year][0]:.1f}"
            )


if __name__ == "__main__":
    check()
    print(len(ANNUAL), "yıl", len(QUARTERLY), "çeyrek")
