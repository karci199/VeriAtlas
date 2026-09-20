r"""Where is the vote actually contested — across every election in the archive, not one.

A single election's closest districts are mostly noise: 24 votes in Çarşıbaşı in 2024 says
something about 2024. The question here is different — which places are *habitually* close,
across parliamentary, presidential, local and referendum votes from 1961 to 2024.

The measure is the one thing every ballot in the archive has in common: **the gap between
the top two contestants, as a share of valid votes.** For a party list that is the first
two parties, for a presidential round the first two candidates, for a referendum Evet and
Hayır. Nothing else is comparable across 1961 and 2024, and anything richer (effective
number of parties, volatility) would be defined differently for a two-option referendum
than for a thirty-party list.

Three rules the numbers depend on:

* **Alliance rows are dropped.** From 2018 the tables carry `CUMHUR İTTİFAKI` and friends
  *beside* the parties that make them up. They are sums, not contestants; counted as a
  contestant they would win most districts and make every 2018/2023 race look lopsided.
  The parties are what is compared, in every year.
* **`BİMZ` is kept and is a known weak point.** It is the independents' *total*, not one
  candidate. In a mayoral race it is usually one person and behaves like a party; in a
  parliamentary one it can be several. It is left in because dropping it would erase the
  places where an independent actually won, and flagged because in those places the gap is
  measured against a sum.
* **An area is only ranked if it appears in most of the archive.** A district created in
  2013 has no 1991 result, and a mean over three elections is not comparable to a mean
  over twenty-five. The floor is set by `--en-az`.

The province is the sum of its districts' votes, not the average of their gaps: a province
is one contest for president and for referendum, and averaging district gaps would report
Şırnak as competitive because its districts lean different ways.

Neighbourhood level is deliberately narrower — only the elections whose neighbourhood
tiles cover all 81 provinces — and it drops places whose name says they are an institution
(`cezaevi`, `ceza infaz`), where the electorate is not a resident population.

Run:  uv run python scripts/analiz/rekabet.py [--en-az 18] [--asgari-oy 5000]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TILES = ROOT / "public" / "tiles"
sys.path.insert(0, str(ROOT / "src"))

from veriatlas.areas import load_areas, load_districts

#: The ballots compared. `_genel` and `_yurtdisi` are subsets of their own election and
#: would count the same vote twice; `aday`/`cikan` are candidate and winner lists, not
#: votes. Local elections are represented by the mayoral ballot alone — the council,
#: metropolitan and provincial-assembly ballots of the same day are the same electorate
#: voting again, and four copies of one day would drown out the other thirty years.
FAMILIES = {
    "mv": "Milletvekili",
    "cb": "Cumhurbaşkanı",
    "ho": "Halkoylaması",
    "yerel_bel": "Belediye başkanı",
}
ALLIANCE = "İTTİFAK"
INSTITUTION = ("cezaevi", "ceza infaz", "açık cezaevi")


def elections() -> list[str]:
    found = []
    for path in sorted(TILES.glob("secim-*-ilce.json")):
        name = path.name[len("secim-") : -len("-ilce.json")]
        if name.endswith(("_genel", "_yurtdisi")):
            continue
        family = name.rstrip("0123456789").rstrip("t").rstrip("_h k".strip())
        for prefix in FAMILIES:
            if name.startswith(prefix) and not name.startswith("yerel_bel" + "mec"):
                found.append(name)
                break
        del family
    return sorted(set(found))


def contestants(votes: dict[str, float]) -> list[tuple[str, float]]:
    real = {k: v for k, v in votes.items() if ALLIANCE not in k.upper()}
    return sorted(real.items(), key=lambda kv: -kv[1])


def gap(votes: dict[str, float], valid: float) -> tuple[float, str] | None:
    ranked = contestants(votes)
    if len(ranked) < 2 or not valid:
        return None
    return (ranked[0][1] - ranked[1][1]) / valid * 100, ranked[0][0]


def read(name: str, level: str, province: str | None = None) -> dict:
    path = (
        TILES / f"secim-{name}-{level}.json"
        if province is None
        else TILES / f"secim-{name}-{level}-{province}.json"
    )
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect(level: str, names: list[str]) -> tuple[dict, dict, dict]:
    """area -> [gaps], area -> [winners], area -> label."""
    gaps: dict[str, list[float]] = collections.defaultdict(list)
    winners: dict[str, list[str]] = collections.defaultdict(list)
    labels: dict[str, str] = {}
    province_votes: dict[str, dict[str, dict[str, float]]] = collections.defaultdict(
        dict
    )

    for name in names:
        tile = read(name, level)
        for area, record in tile.items():
            votes = record.get("v") or {}
            valid = record.get("g") or sum(votes.values())
            labels.setdefault(area, record.get("ad", area))
            measured = gap(votes, valid)
            if measured is None:
                continue
            gaps[area].append(measured[0])
            winners[area].append(measured[1])
            # The province is summed from the same rows, election by election.
            bucket = province_votes[name].setdefault(area[:5], collections.Counter())
            for party, count in votes.items():
                bucket[party] += count
    return gaps, winners, labels, province_votes


def province_rows(province_votes: dict) -> tuple[dict, dict]:
    gaps: dict[str, list[float]] = collections.defaultdict(list)
    winners: dict[str, list[str]] = collections.defaultdict(list)
    for _name, provinces in province_votes.items():
        for area, votes in provinces.items():
            valid = sum(v for k, v in votes.items() if ALLIANCE not in k.upper())
            measured = gap(dict(votes), valid)
            if measured is None:
                continue
            gaps[area].append(measured[0])
            winners[area].append(measured[1])
    return gaps, winners


def report(title: str, rows: list[tuple], head: int) -> None:
    print(f"\n=== {title}")
    for row in rows[:head]:
        print("  " + row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Genel rekabet haritası")
    parser.add_argument("--en-az", type=int, default=18, help="asgari seçim sayısı")
    parser.add_argument("--kac", type=int, default=15, help="listelenecek satır")
    parser.add_argument(
        "--asgari-oy", type=int, default=2000, help="mahallede asgari geçerli oy"
    )
    args = parser.parse_args()

    names = elections()
    print(f"{len(names)} seçim: " + ", ".join(names))

    areas = load_areas()
    provinces = {
        row["area_id"]: row["name_tr"]
        for row in areas.filter(areas["area_level"] == "province").iter_rows(named=True)
    }
    district_parent = {
        row["area_id"]: row["parent_id"]
        for row in load_districts().iter_rows(named=True)
    }

    gaps, winners, labels, province_votes = collect("ilce", names)
    pg, pw = province_rows(province_votes)

    prov_rows = []
    for area, values in pg.items():
        if len(values) < args.en_az or area not in provinces:
            continue
        prov_rows.append(
            (
                f"{provinces[area]:<14} ortalama fark {statistics.mean(values):5.1f} puan"
                f"  | {len(values)} seçim | {len(set(pw[area]))} farklı kazanan"
                f" | en dar {min(values):4.1f}",
                statistics.mean(values),
            )
        )
    prov_rows.sort(key=lambda r: r[1])
    report(f"EN CEKISMELI ILLER (en az {args.en_az} secim)", prov_rows, args.kac)
    report("EN TEK SESLİ İLLER", prov_rows[::-1], args.kac)

    dist_rows = []
    for area, values in gaps.items():
        if len(values) < args.en_az:
            continue
        parent = district_parent.get(area)
        if parent is None:
            continue
        dist_rows.append(
            (
                f"{provinces.get(parent, parent)} {labels[area]:<18}"
                f" ortalama fark {statistics.mean(values):5.1f} puan | {len(values)} seçim"
                f" | {len(set(winners[area]))} farklı kazanan",
                statistics.mean(values),
            )
        )
    dist_rows.sort(key=lambda r: r[1])
    report(f"EN CEKISMELI ILCELER (en az {args.en_az} secim)", dist_rows, args.kac)
    report("EN TEK SESLİ İLÇELER", dist_rows[::-1], args.kac)

    turnover = [
        (
            f"{provinces.get(district_parent.get(a), '')} {labels[a]:<18}"
            f" {len(set(w))} farklı kazanan | {len(gaps[a])} seçim"
            f" | ortalama fark {statistics.mean(gaps[a]):5.1f}",
            len(set(w)),
        )
        for a, w in winners.items()
        if len(gaps[a]) >= args.en_az and a in district_parent
    ]
    turnover.sort(key=lambda r: -r[1])
    report("EN ÇOK EL DEĞİŞTİREN İLÇELER", turnover, args.kac)

    neighbourhoods(args, provinces, district_parent)


#: The elections whose neighbourhood tiles cover all 81 provinces. The archive goes back
#: to 1961 at district level but only to 2002 here, and a mean over a different set of
#: elections is a different number — so the neighbourhood table is its own analysis with
#: its own window, not a finer-grained version of the district one.
MAHALLE_ELECTIONS = [
    "mv2002",
    "mv2007",
    "mv2011",
    "mv2015h",
    "mv2015k",
    "mv2018",
    "mv2023",
    "cb2014",
    "cb2018",
    "cb2023t1",
    "cb2023t2",
    "ho2007",
    "ho2010",
    "ho2017",
    "yerel_bel_2014",
    "yerel_bel_2019",
    "yerel_bel_2024",
]


def neighbourhoods(args, provinces: dict, district_parent: dict) -> None:
    gaps: dict[str, list[float]] = collections.defaultdict(list)
    winners: dict[str, list[str]] = collections.defaultdict(list)
    labels: dict[str, str] = {}
    votes_seen: dict[str, list[float]] = collections.defaultdict(list)

    for province in sorted(provinces):
        for name in MAHALLE_ELECTIONS:
            tile = read(name, "mahalle", province)
            for area, record in tile.items():
                label = record.get("ad", area)
                if any(word in label.casefold() for word in INSTITUTION):
                    # A prison's ballot box is not a neighbourhood's opinion.
                    continue
                votes = record.get("v") or {}
                valid = record.get("g") or sum(votes.values())
                measured = gap(votes, valid)
                if measured is None or valid < args.asgari_oy:
                    continue
                labels.setdefault(area, label)
                gaps[area].append(measured[0])
                winners[area].append(measured[1])
                votes_seen[area].append(valid)

    rows = []
    floor = max(args.en_az - 4, len(MAHALLE_ELECTIONS) - 3)
    for area, values in gaps.items():
        if len(values) < floor:
            continue
        district = area.rsplit("-", 1)[0]
        rows.append(
            (
                f"{provinces.get(district_parent.get(district), '')} "
                f"{labels[area]:<26} ortalama fark {statistics.mean(values):5.1f} puan"
                f" | {len(values)} seçim | {len(set(winners[area]))} farklı kazanan"
                f" | ort. {statistics.mean(votes_seen[area]):,.0f} oy",
                statistics.mean(values),
            )
        )
    rows.sort(key=lambda r: r[1])
    report(
        f"EN CEKISMELI MAHALLELER ({len(MAHALLE_ELECTIONS)} secim, en az {floor})",
        rows,
        args.kac,
    )


if __name__ == "__main__":
    main()
