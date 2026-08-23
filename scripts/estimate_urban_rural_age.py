"""Estimate urban/rural age-band distribution for a district where TÜİK stops
publishing the urban/rural split (metropolitan law, 2013+).

Inputs (all real):
  * district age bands x sex per year           -- TÜİK MEDAS (raw/medas/ilce/nufus-ilce-kirilim-YYYY.csv)
  * urban/rural age bands, last published years -- TÜİK (2007-2012, şehir/köy)
  * urban total per year                        -- sum of centre-neighbourhood ADNKS populations
  * optionally one year with urban bands 0-64   -- Endeksa neighbourhood dump (2024)

Method: iterative proportional fitting (IPF). For each year a 19-band x {urban, rural}
table is fitted so that row sums equal the district bands (real) and column sums equal
the urban/rural totals (real). The seed carries the *shape* of the urban share per band,
interpolated linearly between the last real year (2012) and the anchor year (2024).
Only the interior cells are estimates; all margins are exact.

Sex split of the estimated urban/rural cells uses the district band sex ratio, except
where the anchor year provides real sex-specific urban bands.

Output: JSON {year: {Toplam|Kent|Kır: {m: [...19], f: [...19]}, est: bool}} consumed by
the population-pyramid page (web) -- not by the Excel workbook, which keeps 65+ as one band.
See docs/kararlar.md K28 addendum.
"""

from __future__ import annotations


def ipf(
    row_totals: list[float],
    urban_total: float,
    seed_share: list[float],
    iters: int = 300,
) -> tuple[list[int], list[int]]:
    """Fit urban/rural cells to row totals and the urban column total."""
    urban = [v * s for v, s in zip(row_totals, seed_share)]
    rural = [v - u for v, u in zip(row_totals, urban)]
    rural_total = sum(row_totals) - urban_total
    for _ in range(iters):
        f = urban_total / sum(urban)
        urban = [x * f for x in urban]
        g = rural_total / sum(rural)
        rural = [x * g for x in rural]
        urban = [u * v / (u + r) for u, r, v in zip(urban, rural, row_totals)]
        rural = [v - u for v, u in zip(row_totals, urban)]
    urban_i = [round(x) for x in urban]
    urban_i[-1] += round(urban_total) - sum(urban_i)
    urban_i = [min(max(u, 0), int(v)) for u, v in zip(urban_i, row_totals)]
    return urban_i, [int(v) - u for v, u in zip(row_totals, urban_i)]


def seed_for_year(
    year: int,
    share_a: list[float],
    share_b: list[float],
    year_a: int = 2012,
    year_b: int = 2024,
) -> list[float]:
    w = min(max((year - year_a) / (year_b - year_a), 0.0), 1.0)
    return [a * (1 - w) + b * w for a, b in zip(share_a, share_b)]
