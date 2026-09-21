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
import csv
import json
import pathlib
import re

DATA = pathlib.Path(__file__).resolve().parents[1] / "public" / "elections"

# Elections in the window, with the decimal year used for the fit.
ELECTIONS = {
    "1983": 1983.0,
    "1987": 1987.0,
    "1991": 1991.0,
    "1995": 1995.0,
    "1999": 1999.0,
    "2002": 2002.0,
    "2007": 2007.0,
    "2011": 2011.0,
    "2015_7_haziran": 2015.4,
    "2015_1_kasim": 2015.8,
    "2018": 2018.0,
    "2023": 2023.0,
}
# In 2007 and 2011 the Kurdish parties ran their candidates as independents, so their
# votes sit in the pooled independent column. Counting that column as Kurdish-left in
# those two elections keeps them usable. It is an over-count wherever a non-Kurdish
# independent ran, but nationally the column is 5.2% in 2007 and 6.6% in 2011 and is
# concentrated in the southeast; leaving the two elections out instead loses a fifth of
# the period. --drop-0711 restores the stricter reading.
INDEPENDENT = "BĞMZ"  # pooled independents column
INDEPENDENT_IS_KURDISH = {"2007", "2011"}

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


def geo_slug(text: str) -> str:
    """Same folding the dataset builder uses, so names join across sources."""
    text = text.replace("İ", "i").replace("I", "ı").lower()
    for src, dst in zip("çğıöşü", "cgiosu"):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def district_area_ids() -> dict[str, str]:
    """(province area id, district slug) -> district area id, for the map join."""
    path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "veriatlas"
        / "data"
        / "areas_tr_districts.csv"
    )
    out = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[(row["parent_id"], geo_slug(row["name_tr"]))] = row["area_id"]
    return out


def bloc_of(party: str, year: str, blocs: dict) -> str:
    if party == "YTP":
        return "left" if year == "2002" else "right"
    return blocs.get(party, "other")


def shares(
    entry: dict, year: str, blocs: dict, kurdish: set
) -> tuple[float, float, bool, float]:
    """(left %, left-without-Kurdish %, CHP was on the ballot, Kurdish-party %)."""
    total = left = kurd = 0
    indep_is_kurdish = year in INDEPENDENT_IS_KURDISH
    for party, votes in entry["p"].items():
        total += votes
        if party == INDEPENDENT and indep_is_kurdish:
            left += votes
            kurd += votes
            continue
        if bloc_of(party, year, blocs) == "left":
            left += votes
        if party in kurdish:
            kurd += votes
    if not total:
        return None
    return (
        100 * left / total,
        100 * (left - kurd) / total,
        "CHP" in entry["p"],
        100 * kurd / total,
    )


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


def residual_sd(points: list[tuple[float, float]]) -> float:
    """Scatter left over once the trend is removed.

    A place that walks steadily in one direction is not unstable, however far it
    walks; a place that jumps around is. Plain standard deviation cannot tell those
    apart, so the trend is fitted first and the spread of what remains is measured.
    """
    n = len(points)
    if n < 3:
        return 0.0
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    denom = sum((x - mx) ** 2 for x, _ in points)
    b = sum((x - mx) * (y - my) for x, y in points) / denom if denom else 0.0
    return (sum((y - (my + b * (x - mx))) ** 2 for x, y in points) / (n - 2)) ** 0.5


def sd(values, weights=None) -> float:
    """Standard deviation; weighted when weights are given (population weighting)."""
    values = list(values)
    if len(values) < 2:
        return 0.0
    if weights is None:
        m = sum(values) / len(values)
        return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    weights = list(weights)
    w = sum(weights)
    m = sum(v * k for v, k in zip(values, weights)) / w
    return (sum(k * (v - m) ** 2 for v, k in zip(values, weights)) / w) ** 0.5


def pearson(xs, ys) -> float:
    xs, ys = list(xs), list(ys)
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den if den else 0.0


def collect(
    level: str = "il",
    start: int = 1983,
    min_voters: int = 5000,
    drop_0711: bool = False,
):
    """Deviation-from-country series per unit.

    level "il" folds post-1989 provinces back into their parent; level "ilce" keys
    districts by province and drops units whose electorate moved far out of step
    with the country, which is what a boundary change looks like in this data.
    """
    index = load_index()
    blocs, kurdish = index["blocs"], set(index["kurdish"])
    elections = {
        y: x
        for y, x in ELECTIONS.items()
        if x >= start and not (drop_0711 and y in INDEPENDENT_IS_KURDISH)
    }

    national = {}
    for year in elections:
        national[year] = shares(index["national"][year], year, blocs, kurdish)

    merged: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    names: dict[str, str] = {}
    # Area ids for the map join. A folded province carries both its own polygon and
    # the polygons of the provinces carved out of it: same territory, same value.
    areas: dict[str, list[str]] = collections.defaultdict(list)
    by_district = district_area_ids() if level == "ilce" else {}
    for entry in index["provinces"]:
        payload = json.loads(
            (DATA / f"{entry['slug']}.json").read_text(encoding="utf-8")
        )
        if level == "il":
            slug = NEW_PROVINCE.get(entry["slug"], entry["slug"])
            if slug == entry["slug"]:
                names[slug] = payload["name"]
            names.setdefault(slug, slug.title())
            areas[slug].append(entry["areaId"])
            units = [(slug, payload["total"])]
        else:
            units = [
                (f"{entry['slug']}/{d}", row["years"])
                for d, row in payload["districts"].items()
            ]
            for key, _ in units:
                d = key.split("/", 1)[1]
                names[key] = f"{payload['districts'][d]['name']} ({payload['name']})"
                area = by_district.get((entry["areaId"], d))
                if area is None and d == "merkez":
                    area = by_district.get((entry["areaId"], geo_slug(payload["name"])))
                if area:
                    areas[key].append(area)
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
        kurd_peak = 0.0
        for year, counts in years.items():
            got = shares(counts, year, blocs, kurdish)
            if not got:
                continue
            left, left_nk, has_chp, kurd_share = got
            kurd_peak = max(kurd_peak, kurd_share)
            if not has_chp and "CHP" in index["national"][year]["p"]:
                chp_missing.append(year)
                continue  # no CHP list: an absent choice, not a rejected one
            nat_left, nat_left_nk, _, _ = national[year]
            # Deviation first (that is what the trend is fitted on), then the unit's
            # own shares and weight, so the same series answers "did it move" as well
            # as "did it move relative to the country".
            series.append(
                (
                    elections[year],
                    left - nat_left,
                    left_nk - nat_left_nk,
                    left,
                    left_nk,
                    counts.get("e", 0),
                )
            )
        if len(series) < min_elections:
            continue
        series.sort()

        electorate = mean_registered(years, elections, 2018, 2023)
        early = mean_registered(years, elections, start, start + 8)
        growth = (
            (electorate / early) / (nat_late / nat_early)
            if early and electorate
            else None
        )
        if level == "ilce":
            if not early or not electorate:
                continue
            if electorate < min_voters:
                continue  # a few thousand voters swing on noise, not on a trend
            if not GROWTH_MIN <= growth <= GROWTH_MAX:
                boundary_suspect.append((names[slug], growth))
                continue

        def window(lo, hi, col, rows_=series):
            vals = [row[col] for row in rows_ if lo <= row[0] <= hi]
            return sum(vals) / len(vals) if vals else None

        early_w, late_w = (start, start + 8), (2018, 2023)
        rows.append(
            {
                "slug": slug,
                "name": names[slug],
                "n": len(series),
                "electorate": electorate,
                "growth": growth,
                "kurd_peak": kurd_peak,
                "areas": areas.get(slug, []),
                "chp_missing": chp_missing,
                "early": window(*early_w, 1),
                "late": window(*late_w, 1),
                "early_nk": window(*early_w, 2),
                "late_nk": window(*late_w, 2),
                "own_early": window(*early_w, 3),
                "own_late": window(*late_w, 3),
                "own_early_nk": window(*early_w, 4),
                "own_late_nk": window(*late_w, 4),
                "slope": slope([(p[0], p[1]) for p in series]),
                "slope_nk": slope([(p[0], p[2]) for p in series]),
                "resid": residual_sd([(p[0], p[1]) for p in series]),
                "resid_nk": residual_sd([(p[0], p[2]) for p in series]),
                "series": series,
            }
        )
        rows[-1]["shift"] = rows[-1]["late"] - rows[-1]["early"]
        rows[-1]["shift_nk"] = rows[-1]["late_nk"] - rows[-1]["early_nk"]
        rows[-1]["own"] = rows[-1]["own_late"] - rows[-1]["own_early"]
        rows[-1]["own_nk"] = rows[-1]["own_late_nk"] - rows[-1]["own_early_nk"]
    return index, national, rows, boundary_suspect


def dispersion(rows, national, elections, index, unit, width):
    """How far apart the places are, and how steadily each one moves.

    Three separate questions, easy to run together by accident:
      1. Are the places spreading apart over time? (cross-section sd per election)
      2. Which places are unstable rather than merely moving? (residual sd)
      3. Does a shrinking electorate go with moving right? (correlation)
    """
    print("\n### Ayrışma: birimler birbirinden uzaklaşıyor mu?")
    print(
        f"  {'seçim':14}{'sapma sd':>10}{'sd (seçmen ağırlıklı)':>24}"
        f"{'kürtsüz sd':>13}{'birim':>7}"
    )
    for year, x in elections.items():
        vals, weights, vals_nk = [], [], []
        for r in rows:
            point = next((p for p in r["series"] if p[0] == x), None)
            if not point:
                continue
            vals.append(point[1])
            vals_nk.append(point[2])
            weights.append(r["electorate"] or 1)
        if len(vals) < 5:
            continue
        label = next(y["label"] for y in index["years"] if y["id"] == year)
        print(
            f"  {label:14}{sd(vals):>10.2f}{sd(vals, weights):>24.2f}"
            f"{sd(vals_nk):>13.2f}{len(vals):>7}"
        )

    for key, title in (
        ("resid", "Kürt partileri solda"),
        ("resid_nk", "Kürt partileri hariç"),
    ):
        ordered = sorted(rows, key=lambda r: -r[key])
        print(
            f"\n### En oynak / en durağan {unit} — eğilim çıkarıldıktan sonra ({title})"
        )
        print(f"  {'birim':{width}}{'artık sd':>10}{'kayma':>9}")
        for group in (ordered[:8], ordered[-8:]):
            for r in group:
                shift = r["shift"] if key == "resid" else r["shift_nk"]
                print(f"  {r['name']:{width}}{r[key]:>10.2f}{shift:>+9.1f}")
            if group is ordered[:8]:
                print(f"  {'—' * (width + 19)}")

    # Electorate growth relative to the country: a place that grew far slower than
    # Türkiye has been emptying out. Does that go with moving right?
    usable = [r for r in rows if r["growth"]]
    if len(usable) > 10:
        print("\n### Seçmen artışı ile kayma arasındaki ilişki")
        print(
            "  (artış = birimin seçmen artışı / ülkenin seçmen artışı; "
            "1'in altı = ülkeden yavaş büyüyen, boşalan yer)"
        )
        for label, subset in (
            (f"tüm {unit}", usable),
            (
                "Kürt partisi payı hep %10 altında kalanlar",
                [r for r in usable if r["kurd_peak"] < 10],
            ),
        ):
            if len(subset) < 10:
                continue
            g = [r["growth"] for r in subset]
            print(
                f"  {label:44} n={len(subset):>4}  "
                f"r(kürtlü)={pearson(g, [r['shift'] for r in subset]):+.2f}  "
                f"r(kürtsüz)={pearson(g, [r['shift_nk'] for r in subset]):+.2f}"
            )
        slowest = sorted(usable, key=lambda r: r["growth"])[:15]
        print(f"\n  En çok boşalan 15 {unit}:")
        print(f"  {'birim':{width}}{'artış':>8}{'kayma':>9}{'kürtsüz':>9}")
        for r in slowest:
            print(
                f"  {r['name']:{width}}{r['growth']:>8.2f}"
                f"{r['shift']:>+9.1f}{r['shift_nk']:>+9.1f}"
            )


def absolute(rows, national, elections, unit, width, start):
    """The other question: did a place's own left share actually move?

    "Relative to Türkiye" has two moving ends. A place that never changed looks like
    it moved right whenever the country moves left. This section drops the reference
    point and reads each place against its own past, then puts the two side by side.
    """
    nat_early = sum(
        national[y][0] for y, x in elections.items() if start <= x <= start + 8
    ) / max(1, sum(1 for x in elections.values() if start <= x <= start + 8))
    nat_late = sum(
        national[y][0] for y, x in elections.items() if 2018 <= x <= 2023
    ) / max(1, sum(1 for x in elections.values() if 2018 <= x <= 2023))
    print(
        f"\n### Kendi geçmişine göre değişim (ülke: {nat_early:+.1f} → {nat_late:+.1f}, "
        f"yani {nat_late - nat_early:+.1f} puan)"
    )
    print(
        f"  {'birim':{width}}{'kendi sol %':>13}{'kendi değişim':>15}"
        f"{'TRye göre':>11}{'kürtsüz kendi':>15}"
    )
    ordered = sorted(rows, key=lambda r: -r["own"])
    for group in (ordered[:12], ordered[-12:]):
        for r in group:
            print(
                f"  {r['name']:{width}}{r['own_late']:>13.1f}{r['own']:>+15.1f}"
                f"{r['shift']:>+11.1f}{r['own_nk']:>+15.1f}"
            )
        if group is ordered[:12]:
            print(f"  {'—' * (width + 54)}")

    fell = [r for r in rows if r["own"] < 0]
    rose_but_lost = [r for r in rows if r["own"] > 0 and r["shift"] < 0]
    print(
        f"\n  Kendi sol payı gerçekten düşen {unit}: {len(fell)}/{len(rows)}. "
        f"Sol payı ARTTIĞI hâlde ülkeye göre geri düşen: {len(rose_but_lost)} "
        f"— bu {unit} sağa dönmedi, ülke onlardan hızlı sola gitti."
    )


def shift_share(rows, national, elections, unit, start):
    """Did the country change its mind, or did it move house?

    The national left share is a population-weighted average of local shares. It can
    move because places voted differently (within) or because the places that grew
    are not the places that shrank (composition). Splitting the two is the only way
    to say whether migration moved the national result on its own.
    """

    def snapshot(lo, hi):
        acc = {}
        for r in rows:
            pts = [p for p in r["series"] if lo <= p[0] <= hi]
            if not pts:
                return None
            acc[r["name"]] = (
                sum(p[3] for p in pts) / len(pts),  # own left share
                sum(p[5] for p in pts) / len(pts),  # electorate
            )
        return acc

    a = snapshot(start, start + 8)
    b = snapshot(2018, 2023)
    if not a or not b:
        print("\n(bileşim ayrıştırması için her birimde iki pencere de gerekli)")
        return
    wa_total = sum(w for _, w in a.values())
    wb_total = sum(w for _, w in b.values())
    within = sum((a[k][1] / wa_total) * (b[k][0] - a[k][0]) for k in a)
    between = sum((b[k][1] / wb_total - a[k][1] / wa_total) * a[k][0] for k in a)
    interaction = sum(
        (b[k][1] / wb_total - a[k][1] / wa_total) * (b[k][0] - a[k][0]) for k in a
    )
    total = within + between + interaction
    print(f"\n### Ülkedeki değişim nereden geliyor? ({unit} bileşimi)")
    print(f"  toplam değişim                    {total:>+7.2f} puan")
    print(f"  yerinde fikir değişimi (within)   {within:>+7.2f}")
    print(f"  nüfus kaymasi (between)           {between:>+7.2f}")
    print(f"  etkileşim                         {interaction:>+7.2f}")
    if abs(total) > 0.01:
        print(f"  nüfus kaymasının payı: %{100 * between / total:.0f}")


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
    ap.add_argument("--json", type=pathlib.Path, help="harita için birim başına kayma")
    ap.add_argument("--level", choices=("il", "ilce"), default="il")
    ap.add_argument(
        "--start",
        type=int,
        default=1983,
        help="pencerenin ilk seçimi; ilçe için 1995 daha güvenli (1983-87 raporlarında "
        "ilçelerin çoğu 'Merkez' diye geçiyor)",
    )
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument(
        "--dispersion", action="store_true", help="dagilim ve iliski bolumleri"
    )
    ap.add_argument(
        "--drop-0711",
        action="store_true",
        help="2007 ve 2011i tamamen disarida birak (bagimsizlari Kurt saymak yerine)",
    )
    ap.add_argument("--min-voters", type=int, default=5000)
    args = ap.parse_args()

    index, national, rows, boundary = collect(
        args.level, args.start, args.min_voters, args.drop_0711
    )
    unit = "il" if args.level == "il" else "ilçe"
    width = 16 if args.level == "il" else 30
    elections = {
        y: x
        for y, x in ELECTIONS.items()
        if x >= args.start and not (args.drop_0711 and y in INDEPENDENT_IS_KURDISH)
    }

    print("Sol blok payı, ülke geneli (%):")
    for year in elections:
        left, left_nk, _, _ = national[year]
        label = next(y["label"] for y in index["years"] if y["id"] == year)
        print(f"  {label:14}{left:>6.1f}{left_nk:>8.1f}  (Kürt partileri hariç)")
    print(
        "\n2007 ve 2011: "
        + (
            "dışarıda"
            if args.drop_0711
            else "içeride, bağımsız sütunu Kürt/sol sayılarak"
        )
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

    if args.dispersion:
        dispersion(rows, national, elections, index, unit, width)
        absolute(rows, national, elections, unit, width, args.start)
        shift_share(rows, national, elections, unit, args.start)

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

    if args.json:
        payload = {
            "level": args.level,
            "start": args.start,
            "minVoters": args.min_voters,
            "elections": [
                next(y["label"] for y in index["years"] if y["id"] == year)
                for year in elections
            ],
            "independentsAsKurdish": []
            if args.drop_0711
            else sorted(INDEPENDENT_IS_KURDISH),
            "boundaryDropped": len(boundary),
            "units": [
                {
                    "name": r["name"],
                    "areas": r["areas"],
                    "shift": round(r["shift"], 1),
                    "shiftNk": round(r["shift_nk"], 1),
                    "early": round(r["early"], 1),
                    "late": round(r["late"], 1),
                    "earlyNk": round(r["early_nk"], 1),
                    "lateNk": round(r["late_nk"], 1),
                    "n": r["n"],
                }
                for r in rows
                if r["areas"]
            ],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        without = sum(1 for r in rows if not r["areas"])
        print(f"\n-> {args.json} ({len(payload['units'])} birim", end="")
        print(f", sınırı bulunamayan {without}" if without else "", end=")\n")

    if args.csv:
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
