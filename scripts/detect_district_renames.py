"""Find district renames by watching one disappear as another appears.

A rename leaves a signature in the yearly exports: in province X a district is listed up
to year N and never again, and another is listed from N+1 on and never before. Nothing
else in the data says "Kazan became Kahramankazan" — but that shape does, and it is the
same shape the observation route already relies on (K11).

Two guards keep it from inventing links:

* **One in, one out.** If a province has two departures and three arrivals in the same
  year, this is a reorganisation, not a rename, and it is left alone — that is the
  split/merge case, which needs shares and a human.
* **The gap is exactly one year.** A district that vanishes in 2012 and something that
  turns up in 2018 are unrelated as far as we can tell.

Output is a proposal, not a fact: it goes to `docs/ilce-adlari.md` for reading and is
only written into the registry once checked. A wrong rename welds two different places
into one series, which is worse than two short series.

Run:  uv run python scripts/detect_district_renames.py
"""

import sys
from collections import defaultdict

sys.path.insert(0, "src")

from veriatlas.adapters.tuik_district_population import DOWNLOADS, read_export
from veriatlas.config import ROOT

REPORT = ROOT / "docs" / "ilce-adlari.md"


def main() -> None:
    exports = sorted(DOWNLOADS.glob("nufus-ilce-*.csv"))
    if not exports:
        raise SystemExit("indirilmis yil yok: once scripts/fetch_medas_districts.py")

    # (province, district) -> years seen, and the MEDAS code that came with it.
    seen: dict[tuple[str, str], set[int]] = defaultdict(set)
    codes: dict[tuple[str, str], str] = {}
    values: dict[tuple[str, str, int], float] = {}

    for path in exports:
        for year, province, district, code, value in read_export(path):
            seen[(province, district)].add(year)
            codes[(province, district)] = code
            values[(province, district, year)] = value

    span = sorted({y for years in seen.values() for y in years})
    first, last = span[0], span[-1]

    leaves: dict[tuple[str, int], list[tuple[str, str]]] = defaultdict(list)
    joins: dict[tuple[str, int], list[tuple[str, str]]] = defaultdict(list)

    for key, years in seen.items():
        province, _ = key
        if max(years) < last:
            leaves[(province, max(years))].append(key)
        if min(years) > first:
            joins[(province, min(years) - 1)].append(key)

    matches = []
    ambiguous = []
    for (province, year), gone in sorted(leaves.items()):
        arrived = joins.get((province, year), [])
        if len(gone) == 1 and len(arrived) == 1:
            old, new = gone[0], arrived[0]
            before = values.get((*old, year))
            after = values.get((*new, year + 1))
            # A rename keeps the population; a split does not. The ratio is reported so a
            # reader can see which one this is rather than trusting the label.
            ratio = (after / before) if before else None
            matches.append((province, year, old[1], new[1], before, after, ratio))
        elif gone or arrived:
            ambiguous.append(
                (province, year, [g[1] for g in gone], [a[1] for a in arrived])
            )

    lines = [
        "# İlçe adı değişiklikleri — gözlemden çıkarılan öneriler",
        "",
        "`scripts/detect_district_renames.py` üretti. **Bunlar öneri**, kayda elle",
        "işlenir: yanlış bir eşleştirme iki ayrı yeri tek seriye kaynatır.",
        "",
        "Kural: aynı ilde bir ilçe biterken tam bir tanesi başlıyorsa ve arada boşluk",
        "yoksa, aday sayılır. Oran (yeni/eski nüfus) 1'e yakınsa yeniden adlandırma,",
        "uzaksa bölünme ya da katılma demektir.",
        "",
        "| İl | Yıl | Eski | Yeni | Eski nüfus | Yeni nüfus | Oran |",
        "|---|---|---|---|---|---|---|",
    ]
    for province, year, old, new, before, after, ratio in matches:
        lines.append(
            "| "
            + province
            + " | "
            + str(year)
            + " → "
            + str(year + 1)
            + " | "
            + old
            + " | "
            + new
            + " | "
            + (f"{before:,.0f}" if before else "—")
            + " | "
            + (f"{after:,.0f}" if after else "—")
            + " | "
            + (f"{ratio:.2f}" if ratio else "—")
            + " |"
        )

    lines += [
        "",
        "## Tek eşleşmeyenler (bölünme / katılma adayları)",
        "",
        "Bunlara dokunulmadı: pay hesabı gerekiyor ve gözlemden çıkmıyor.",
        "",
    ]
    for province, year, gone, arrived in ambiguous:
        lines.append(
            "- **"
            + province
            + "** "
            + str(year)
            + " → "
            + str(year + 1)
            + ": biten ["
            + ", ".join(gone)
            + "], başlayan ["
            + ", ".join(arrived)
            + "]"
        )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("gozlem araligi:", first, "-", last)
    print("yeniden adlandirma adayi:", len(matches))
    for province, year, old, new, _, _, ratio in matches[:20]:
        print(
            "   ~",
            province,
            year,
            old,
            "->",
            new,
            ("oran " + f"{ratio:.2f}") if ratio else "",
        )
    print("belirsiz (bolunme/katilma):", len(ambiguous))
    print("rapor:", REPORT)


if __name__ == "__main__":
    main()
