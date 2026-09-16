"""Fixed broadband subscriptions by speed band, read off the pie charts of BTK reports.

"Hızlara Göre Sabit Genişbant İnternet Abonelerinin Dağılımı, %" is a pie chart whose slice
labels are part of the image, so the pages were rendered (pypdfium2, scale 4) and read by
eye. A slice is named by its colour, which the legend gives; the nine shares must add up to
100 (± 0.3 for rounding), which is the check.

Read from the fourth-quarter reports 2021-2025 and 2026-Q1 — the band definitions before
2021 are different (x≤1, 1-2, 2-4, 4-8, 8-10, 10-30, 30-50, 50-100, 100+ in the 2017 report),
so the older charts are not comparable and were left out.

In the 2022-Q4 and 2024-Q4 charts three slices are too thin to label in place and their
values hang on leader lines; the assignment there follows the neighbouring years' trend
(x≤2 falling, 100+ rising) rather than the drawing order.
"""

from __future__ import annotations

BANDS = (
    "le_2",
    "2_4",
    "4_10",
    "10_16",
    "16_24",
    "24_35",
    "35_50",
    "50_100",
    "gt_100",
)
#: report -> share per band, in the order above
SHARES = {
    "2021-Q4": [1.5, 0.3, 8.0, 31.8, 24.1, 17.7, 8.8, 7.7, 0.1],
    "2022-Q4": [1.0, 0.1, 4.2, 26.0, 24.6, 19.5, 12.6, 11.6, 0.4],
    "2023-Q4": [0.1, 0.1, 2.4, 19.6, 20.9, 20.1, 14.9, 19.2, 2.8],
    "2024-Q4": [0.1, 0.2, 1.8, 12.7, 14.2, 20.2, 20.4, 24.0, 6.5],
    "2025-Q4": [0.0, 0.1, 1.4, 8.1, 9.5, 14.8, 24.4, 29.0, 12.6],
    "2026-Q1": [0.1, 0.1, 1.4, 7.5, 8.5, 13.6, 24.3, 30.0, 14.6],
}


def series() -> dict[str, dict[str, float]]:
    """report -> {band: share}, with the 100% check."""
    out = {}
    for report, shares in SHARES.items():
        if abs(sum(shares) - 100) > 0.3:
            raise ValueError(f"{report}: paylar {sum(shares):.1f}")
        out[report] = dict(zip(BANDS, shares, strict=True))
    return out


if __name__ == "__main__":
    print(len(series()), "dönem")
