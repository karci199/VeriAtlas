"""Which provinces or districts moved, relative to the country, since 1983.

A province's raw left-bloc share mostly tracks the national swing, so a province
that "went right" may simply have gone right with everybody else. What is asked
here is the *relative* trend: the province's left-bloc share minus the national
one, election by election, and the slope of that deviation over the last four
decades.

Two readings are reported side by side, because they do not agree and the
disagreement is the finding: with Kurdish parties counted on the left, and with
their votes taken out of the left bloc.

Elections used: 1983-2023, minus 2007 and 2011. In those two the Kurdish parties
ran candidates as independents, so their votes sit in the pooled independent
column and the left bloc collapses for reasons that have nothing to do with the
electorate. Province-years where CHP was not on the ballot at all (seven
provinces in 2023) are dropped for the same reason: an absent list is not a
choice voters made.

Provinces created after 1989 are folded back into the province they were carved
out of, so both ends of the comparison cover the same territory.

At district level (--level ilce) the same territory problem is bigger and cannot
be solved by a lookup table: the 2013 metropolitan law redrew district lines in 30
provinces and centres have been split repeatedly. Two filters stand in for it — a
district whose electorate moved far out of step with the country is dropped as a
boundary change rather than a swing, and very small districts are dropped because
a few thousand voters swing on noise. 1995 is the safer starting point there: in
the 1983-87 reports most districts are still filed as "Merkez".

Run: uv run python scripts/analyze_province_lean.py
     uv run python scripts/analyze_province_lean.py --level ilce --start 1995
     [--csv out.csv] [--top 15] [--min-voters 5000]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib

DATA = pathlib.Path(__file__).resolve().parents[1] / "public" / "elections"

# Elections in the window, with the decimal year used for the fit.
ELECTIONS = {
    "1983": 1983.0,
    "1987": 1987.0,
    "1991": 1991.0,
    "1995": 1995.0,
    "1999": 1999.0,
    "2002": 2002.0,
    "2015_7_haziran": 2015.4,
    "2015_1_kasim": 2015.8,
    "2018": 2018.0,
    "2023": 2023.0,
}
EXCLUDED = {
    "2007": "Kürt siyaseti bağımsız girdi",
    "2011": "Kürt siyaseti bağımsız girdi",
}

# Provinces created after 1989 -> the province they were carved out of.
NEW_PROVINCE = {
    "aksaray": "nigde",
    "bayburt": "gumushane",
    "karaman": "konya",
    "kirikkale": "ankara",
    "batman": "siirt",
    "sirnak": "siirt",
    "bartin": "zonguldak",
    "ardahan": "kars",
    "igdir": "kars",
    "yalova": "istanbul",
    "karabuk": "zonguldak",
    "kilis": "gaziantep",
    "osmaniye": "adana",
    "duzce": "bolu",
}

MIN_ELECTIONS = 8  # of the ten in the window

# A district whose electorate grew (or shrank) far faster than the country almost
# always changed shape rather than mind: the 2013 metropolitan law redrew district
# lines in 30 provinces, and centres have been split into new districts throughout.
# Such a unit is not the same place at both ends of the comparison, so it is dropped.
GROWTH_MIN, GROWTH_MAX = 0.45, 2.5


def load_index() -> dict:
    return json.loads((DATA / "index.json").read_text(encoding="utf-8"))


def bloc_of(party: str, year: str, blocs: dict) -> str:
    if party == "YTP":
        return "left" if year == "2002" else "right"
    return blocs.get(party, "other")


def shares(
    entry: dict, year: str, blocs: dict, kurdish: set
) -> tuple[float, float, bool]:
    """(left %, left-without-Kurdish %, CHP was on the ballot)."""
    total = left = kurd = 0
    for party, votes in entry["p"].items():
        total += votes
        if bloc_of(party, year, blocs) == "left":
            left += votes
        if party in kurdish:
            kurd += votes
    if not total:
        return None
    return 100 * left / total, 100 * (left - kurd) / total, "CHP" in entry["p"]


def fold(counts: dict, entry: dict) -> None:
    for key in ("e", "v", "g"):
        counts[key] = counts.get(key, 0) + entry[key]
    parties = counts.setdefault("p", {})
    for party, votes in entry["p"].items():
        parties[party] = parties.get(party, 0) + votes


def mean_registered(years: dict, elections: dict, lo: float, hi: float):
    """Average registered electorate over a window of elections, or None."""
    vals = [
        counts["e"]
        for year, counts in years.items()
        if year in elections and lo <= elections[year] <= hi and counts.get("e")
    ]
    return sum(vals) / len(vals) if vals else None


def slope(points: list[tuple[float, float]]) -> float:
    """Least-squares slope, in points of deviation per decade."""
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    denom = sum((x - mx) ** 2 for x, _ in points)
    return 10 * sum((x - mx) * (y - my) for x, y in points) / denom


def collect(level: str = "il", start: int = 1983, min_voters: int = 5000):
    """Deviation-from-country series per unit.

    level "il" folds post-1989 provinces back into their parent; level "ilce" keys
    districts by province and drops units whose electorate moved far out of step
    with the country, which is what a boundary change looks like in this data.
    """
    index = load_index()
    blocs, kurdish = index["blocs"], set(index["kurdish"])
    elections = {y: x for y, x in ELECTIONS.items() if x >= start}

    national = {}
    for year in elections:
        national[year] = shares(index["national"][year], year, blocs, kurdish)

    merged: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    names: dict[str, str] = {}
    for entry in index["provinces"]:
        payload = json.loads(
            (DATA / f"{entry['slug']}.json").read_text(encoding="utf-8")
        )
        if level == "il":
            slug = NEW_PROVINCE.get(entry["slug"], entry["slug"])
            if slug == entry["slug"]:
                names[slug] = payload["name"]
            names.setdefault(slug, slug.title())
            units = [(slug, payload["total"])]
        else:
            units = [
                (f"{entry['slug']}/{d}", row["years"])
                for d, row in payload["districts"].items()
            ]
            for key, _ in units:
                d = key.split("/", 1)[1]
                names[key] = f"{payload['districts'][d]['name']} ({payload['name']})"
        for key, years in units:
            for year, counts in years.items():
                if year in elections:
                    fold(merged[key].setdefault(year, {}), counts)

    min_elections = max(3, len(elections) - 2)
    nat_early = mean_registered(index["national"], elections, start, start + 8)
    nat_late = mean_registered(index["national"], elections, 2018, 2023)

    rows = []
    boundary_suspect = []
    for slug, years in merged.items():
        series = []
        chp_missing = []
        for year, counts in years.items():
            got = shares(counts, year, blocs, kurdish)
            if not got:
                continue
            left, left_nk, has_chp = got
            if not has_chp and "CHP" in index["national"][year]["p"]:
                chp_missing.append(year)
                continue  # no CHP list: an absent choice, not a rejected one
            nat_left, nat_left_nk, _ = national[year]
            series.append((elections[year], left - nat_left, left_nk - nat_left_nk))
        if len(series) < min_elections:
            continue
        series.sort()

        electorate = mean_registered(years, elections, 2018, 2023)
        if level == "ilce":
            early = mean_registered(years, elections, start, start + 8)
            if not early or not electorate:
                continue
            if electorate < min_voters:
                continue  # a few thousand voters swing on noise, not on a trend
            growth = (electorate / early) / (nat_late / nat_early)
            if not GROWTH_MIN <= growth <= GROWTH_MAX:
                boundary_suspect.append((names[slug], growth))
                continue

        def window(lo, hi, col, rows_=series):
            vals = [row[col] for row in rows_ if lo <= row[0] <= hi]
            return sum(vals) / len(vals) if vals else None

        early, late = (start, start + 8), (2018, 2023)
        rows.append(
            {
                "slug": slug,
                "name": names[slug],
                "n": len(series),
                "electorate": electorate,
                "chp_missing": chp_missing,
                "early": window(*early, 1),
                "late": window(*late, 1),
                "early_nk": window(*early, 2),
                "late_nk": window(*late, 2),
                "slope": slope([(x, d) for x, d, _ in series]),
                "slope_nk": slope([(x, d) for x, _, d in series]),
                "series": series,
            }
        )
        rows[-1]["shift"] = rows[-1]["late"] - rows[-1]["early"]
        rows[-1]["shift_nk"] = rows[-1]["late_nk"] - rows[-1]["early_nk"]
    return index, national, rows, boundary_suspect


def table(rows, suffix, title, n=15, width=16, start=1983):
    """suffix "" = Kurdish parties on the left, "_nk" = their votes taken out."""
    shift, early, late, sl = (
        "shift" + suffix,
        "early" + suffix,
        "late" + suffix,
        "slope" + suffix,
    )
    rows = sorted(rows, key=lambda r: -r[shift])
    head = f"{start % 100:02d}-{(start + 8) % 100:02d} fark"
    print(f"\n### {title}")
    print(
        f"  {'birim':{width}}{head:>12}{'18-23 fark':>12}"
        f"{'kayma':>9}{'eğilim':>9}{'seçim':>7}"
    )
    for group in (rows[:n], rows[-n:]):
        for r in group:
            print(
                f"  {r['name']:{width}}{r[early]:>+12.1f}{r[late]:>+12.1f}"
                f"{r[shift]:>+9.1f}{r[sl]:>+9.2f}{r['n']:>7}"
            )
        if group is rows[:n]:
            print(f"  {'—' * (width + 40)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=pathlib.Path)
    ap.add_argument("--level", choices=("il", "ilce"), default="il")
    ap.add_argument(
        "--start",
        type=int,
        default=1983,
        help="pencerenin ilk seçimi; ilçe için 1995 daha güvenli (1983-87 raporlarında "
        "ilçelerin çoğu 'Merkez' diye geçiyor)",
    )
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-voters", type=int, default=5000)
    args = ap.parse_args()

    index, national, rows, boundary = collect(args.level, args.start, args.min_voters)
    unit = "il" if args.level == "il" else "ilçe"
    width = 16 if args.level == "il" else 30
    elections = {y: x for y, x in ELECTIONS.items() if x >= args.start}

    print("Sol blok payı, ülke geneli (%):")
    for year in elections:
        left, left_nk, _ = national[year]
        label = next(y["label"] for y in index["years"] if y["id"] == year)
        print(f"  {label:14}{left:>6.1f}{left_nk:>8.1f}  (Kürt partileri hariç)")
    print(
        f"\nDışarıda bırakılan seçimler: "
        f"{', '.join(f'{y} ({w})' for y, w in EXCLUDED.items())}"
    )
    print(
        f"{unit.capitalize()} sayısı: {len(rows)}"
        + (" (1989 öncesi sınırlar)" if args.level == "il" else "")
    )
    if boundary:
        print(
            f"Sınırı değişmiş sayılıp elenen {unit}: {len(boundary)} "
            f"(seçmen artışı ülkenin {GROWTH_MIN}–{GROWTH_MAX} katı dışında). "
            "En uçtakiler: "
            + ", ".join(
                f"{n} ×{g:.1f}" for n, g in sorted(boundary, key=lambda t: -t[1])[:6]
            )
        )

    dropped = {r["name"]: r["chp_missing"] for r in rows if r["chp_missing"]}
    if dropped:
        shown = sorted(dropped.items())[:12]
        print(
            f"CHP listesi olmadığı için atlanan {unit}-seçim ({len(dropped)}): "
            + ", ".join(f"{k} {'/'.join(v)}" for k, v in shown)
            + (" …" if len(dropped) > len(shown) else "")
        )

    table(
        rows,
        "",
        "Ülkeye göre kayma — Kürt partileri solda",
        args.top,
        width,
        args.start,
    )
    table(
        rows,
        "_nk",
        "Ülkeye göre kayma — Kürt partileri hariç",
        args.top,
        width,
        args.start,
    )

    agree = [r for r in rows if r["shift"] * r["shift_nk"] > 0]
    agree.sort(key=lambda r: -(r["shift"] + r["shift_nk"]) / 2)
    print(f"\n### İki okumada da aynı yöne kayan {unit} (tanımdan bağımsız hareket)")
    print(f"  {'birim':{width}}{'kürtlü':>9}{'kürtsüz':>9}")
    for r in agree[:10] + agree[-10:]:
        print(f"  {r['name']:{width}}{r['shift']:>+9.1f}{r['shift_nk']:>+9.1f}")

    gap = sorted(rows, key=lambda r: -abs(r["shift"] - r["shift_nk"]))
    print(
        f"\n### İki okumanın en çok ayrıldığı {unit} (fark = Kürt partilerinin katkısı)"
    )
    print(f"  {'birim':{width}}{'kürtlü':>9}{'kürtsüz':>9}{'fark':>8}")
    for r in gap[:12]:
        print(
            f"  {r['name']:{width}}{r['shift']:>+9.1f}{r['shift_nk']:>+9.1f}"
            f"{r['shift'] - r['shift_nk']:>+8.1f}"
        )

    if args.csv:
        import csv

        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    unit,
                    "kayma_kurtlu",
                    "kayma_kurtsuz",
                    "egilim_kurtlu",
                    "egilim_kurtsuz",
                    "fark_83_91",
                    "fark_18_23",
                    "secim",
                ]
            )
            for r in sorted(rows, key=lambda r: -r["shift"]):
                w.writerow(
                    [
                        r["name"],
                        round(r["shift"], 1),
                        round(r["shift_nk"], 1),
                        round(r["slope"], 2),
                        round(r["slope_nk"], 2),
                        round(r["early"], 1),
                        round(r["late"], 1),
                        r["n"],
                    ]
                )
        print(f"\n-> {args.csv}")


if __name__ == "__main__":
    main()
