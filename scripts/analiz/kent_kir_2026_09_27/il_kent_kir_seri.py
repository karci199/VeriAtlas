"""Urban/rural population of one province, 2007-2025, on today's decisions (fixed list).

Two corrections to the raw series:

1. Retired ids. A unit that no longer exists has no decision of its own, so summing decisions
   alone loses it (Kayseri 2013: 152,521 people). Each retired id takes a class in this order:
   same code +-2,000,000; a former town's neighbourhood takes that town's class today; a village
   by its own name, then by the last part of a joined name ("Erkilet Emmiler" -> Emmiler); a
   leading place name ("Hisarcık Erciyes" -> Hisarcık); a neighbourhood of the district
   municipality by 2012 is the centre. Village and former town with no match today are rural.

2. Year-end before a local election. The December registry before a March local election
   (2008, 2013, 2018, 2023) moves people from the city to villages and back a year later. Those
   years are replaced per district and class by the mean of the neighbouring years, then scaled
   to the year's real total. The raw series is kept beside the corrected one.

3. One-year blips in other years, per district and class: off the mean of the neighbouring years
   by 10% and 100 people while those two years agree. Replaced by the mean, scaled to the total.

Writes il_kent_kir_seri_<plate>.csv and il_kent_kir_seri_<plate>_ilce.csv next to this file.

Run:  python il_kent_kir_seri.py 38
"""

import collections
import csv
import json
import re
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
PLATE = sys.argv[1]
HERE = Path(__file__).resolve().parent
DATA = HERE.parents[2] / "src" / "veriatlas" / "data"
WAREHOUSE = "C:/veri/warehouse.duckdb"
YEARS = list(range(2007, 2026))
PRE_LOCAL_ELECTION = (2008, 2013, 2018, 2023)
CLASSES = ["İlçe Merkezi", "Kentsel Belde", "Kırsal Belde", "Köy"]
URBAN = {"İlçe Merkezi", "Kentsel Belde"}
GENERIC = {
    "yeni",
    "fatih",
    "cumhuriyet",
    "merkez",
    "yukari",
    "asagi",
    "orta",
    "buyuk",
    "kucuk",
    "bahcelievler",
}
FOLD = str.maketrans("ıİşŞçÇğĞöÖüÜâîû", "iissccggoouuaiu")
PREFIX = f"TR-{PLATE}-"

decisions = json.loads((HERE / "kullanici_karar.json").read_text(encoding="utf-8"))
decisions = {k: v for k, v in decisions.items() if k.startswith(PREFIX)}
registry = {}
for kind in ("neighbourhoods", "villages"):
    with open(DATA / f"areas_tr_{kind}.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["area_id"].startswith(PREFIX):
                registry[row["area_id"]] = dict(row, kind=kind)
with open(DATA / "areas_tr_districts.csv", encoding="utf-8") as f:
    districts = {
        r["area_id"]: r["name_tr"]
        for r in csv.DictReader(f)
        if r["area_id"].startswith(PREFIX)
    }

# The registry also lists districts abolished in 2013 (Mardin Merkez); only those with units today count.
districts = {
    k: v for k, v in districts.items() if any(a.startswith(k + "-") for a in decisions)
}

con = duckdb.connect(WAREHOUSE, read_only=True)
cells = collections.defaultdict(dict)
for area, year, dims, value in con.execute(
    f"""select area_id, year(period_start), dims, sum(value) from fact
    where indicator_id='population' and area_id like '{PREFIX}%' and area_level in ('neighbourhood','village')
    group by 1,2,3"""
).fetchall():
    cells[area].setdefault(year, {})[dims] = value
province = dict(
    con.execute(
        f"""select year(period_start), sum(value) from fact where indicator_id='population'
        and area_id='TR-{PLATE}' and dims like 'age=%;sex=%' group by 1"""
    ).fetchall()
)


def population(area, year):
    """An unbroken row where it exists, otherwise 0-17 + 18+; never both."""
    c = cells.get(area, {}).get(year)
    if not c:
        return 0
    return c[""] if "" in c else sum(c.values())


def tokens(name):
    name = re.sub(r"\b(Mah|Köy|Mh|Bel)\.?", " ", name or "")
    return re.sub(r"[^a-z0-9 ]", " ", name.translate(FOLD).lower()).split()


def key(name):
    return "".join(tokens(name))


units = collections.defaultdict(dict)
towns = collections.defaultdict(dict)
for area, d in decisions.items():
    if area in registry:
        units[area[:9]][key(registry[area]["name_tr"])] = area
    if d.get("y"):
        towns[area[:9]][key(d["y"])] = area


def find_place(district, name):
    """A town or unit carrying this name today; a loose match must agree on one class."""
    k = key(name)
    if k in towns[district]:
        return decisions[towns[district][k]]["s"]
    if k in units[district]:
        return decisions[units[district][k]]["s"]
    hits = {
        decisions[a]["s"]
        for n, a in units[district].items()
        if n.startswith(k) or (k.startswith(n) and len(n) > 4)
    }
    return hits.pop() if len(hits) == 1 else None


def find_elsewhere(name):
    """The same place name in another district today: a town moved when districts were redrawn."""
    k = key(name)
    hits = [(d, towns[d][k]) for d in towns if k in towns[d]] or [
        (d, units[d][k]) for d in units if k in units[d]
    ]
    classes = {decisions[a]["s"] for _, a in hits}
    return (classes.pop(), hits[0][0]) if len(classes) == 1 else None


def resolve(area):
    """Rule, class today and the district that holds the place today."""
    r = registry.get(area, {})
    district = area.rsplit("-", 1)[0]
    code = area.rsplit("-", 1)[1]
    for offset in (2000000, -2000000):
        other = f"{district}-{int(code) + offset}" if code.isdigit() else None
        if other in decisions:
            return "code", decisions[other]["s"], district
    words = tokens(r.get("name_tr"))
    municipality = (r.get("municipality") or "").replace(" Bel.", "")
    is_village = r.get("kind") == "villages"
    if not is_village and municipality and municipality != districts.get(district):
        place = find_place(district, municipality)
        if place:
            return "former_town", place, district
        moved = find_elsewhere(municipality)
        if moved:
            return "former_town_moved", moved[0], moved[1]
        return "former_town_default", "Köy", district
    if is_village:
        for i in range(len(words)):
            joined = "".join(words[i:])
            if joined in units[district]:
                return "village_name", decisions[units[district][joined]]["s"], district
        moved = find_elsewhere(r.get("name_tr"))
        if moved and district not in districts:
            return "village_moved", moved[0], moved[1]
    for i in range(len(words) - 1, 0, -1):
        if " ".join(words[:i]) in GENERIC:
            continue
        joined = "".join(words[:i])
        hit = towns[district].get(joined) or units[district].get(joined)
        if hit:
            return "leading_name", decisions[hit]["s"], district
    if is_village:
        return "village_default", "Köy", district
    if (
        municipality == districts.get(district)
        and r.get("first_seen", "9999") <= "2012"
    ):
        place = find_place(district, r.get("name_tr"))
        return (
            "district_municipality",
            "İlçe Merkezi"
            if place
            in (
                None,
                "İlçe Merkezi",
            )
            else place,
            district,
        )
    place = find_place(district, r.get("name_tr"))
    return ("late_name", place, district) if place else ("unresolved", None, district)


retired = {a: resolve(a) for a in cells if a not in decisions}
# A retired district's leftovers go to the district that took most of its places.
old_district = collections.defaultdict(collections.Counter)
for area, (_, _, d) in retired.items():
    home = area.rsplit("-", 1)[0]
    if home not in districts and d in districts:
        old_district[home][d] += 1
for area, (rule, cls, d) in retired.items():
    if d not in districts:
        retired[area] = (rule, cls, old_district[d].most_common(1)[0][0])
rules = collections.defaultdict(collections.Counter)
for area, (rule, _, _) in retired.items():
    rules[rule]["ids"] += 1
    for year in (2012, 2017, 2022):
        rules[rule][year] += population(area, year)
for rule, counts in rules.items():
    print(rule, dict(counts))
print(
    "unresolved",
    [
        registry.get(a, {}).get("name_tr")
        for a, (_, c, _) in retired.items()
        if c is None
    ],
)
print("old districts", {k: dict(v) for k, v in old_district.items()})

raw = collections.defaultdict(
    lambda: collections.Counter()
)  # (district, class) -> year -> people
for area in cells:
    cls, target = (
        (decisions[area]["s"], area[:9]) if area in decisions else retired[area][1:]
    )
    for year in YEARS:
        raw[(target, cls)][year] += population(area, year)

fixed = {k: collections.Counter(v) for k, v in raw.items()}

# One-year blips first (Yıldızeli 2014: three centre neighbourhoods jump by half and fall back),
# judged against the nearest years outside the election years, worst first, so an election-year
# mean is not built on a blip and a real change of level is left alone.
BLIP_SHARE, BLIP_PEOPLE = 0.10, 100
CLEAN = [y for y in YEARS if y not in PRE_LOCAL_ELECTION]
blips = []
for k, v in fixed.items():
    for _ in range(len(CLEAN)):
        worst = None
        for before, year, after in zip(CLEAN, CLEAN[1:], CLEAN[2:]):
            mean = (v[before] + v[after]) / 2
            off = abs(v[year] - mean)
            if (
                mean
                and off >= max(BLIP_SHARE * mean, BLIP_PEOPLE)
                and abs(v[before] - v[after]) <= BLIP_SHARE * mean
                and (worst is None or off > worst[0])
            ):
                worst = (off, year, mean)
        if worst is None:
            break
        blips.append(
            (districts.get(k[0]), k[1], worst[1], round(v[worst[1]]), round(worst[2]))
        )
        v[worst[1]] = worst[2]
print("one-year blips", blips)

for year in PRE_LOCAL_ELECTION:
    for v in fixed.values():
        v[year] = (v[year - 1] + v[year + 1]) / 2
for year in YEARS:
    scale = sum(v[year] for v in raw.values()) / sum(v[year] for v in fixed.values())
    for v in fixed.values():
        v[year] *= scale


def share(source, year, district=None):
    by = collections.Counter()
    for (d, cls), v in source.items():
        if district is None or d == district:
            by[cls] += v[year]
    total = sum(by.values())
    return by, total, sum(by[c] for c in URBAN) / total * 100


with open(
    HERE / f"il_kent_kir_seri_{PLATE}.csv", "w", encoding="utf-8", newline=""
) as f:
    w = csv.writer(f)
    w.writerow(
        [
            "yil",
            "il_toplam",
            "birim_toplam",
            "ham_kent",
            "ham_kir",
            "ham_oran",
            "kent",
            "kir",
            "oran",
            "merkez",
            "kentsel_belde",
            "kirsal_belde",
            "koy",
            "duzeltildi",
        ]
    )
    for year in YEARS:
        rb, rt, rp = share(raw, year)
        fb, ft, fp = share(fixed, year)
        fk = sum(fb[c] for c in URBAN)
        rk = sum(rb[c] for c in URBAN)
        w.writerow(
            [
                year,
                int(province[year]),
                int(rt),
                int(rk),
                int(rt - rk),
                round(rp, 2),
                round(fk),
                round(ft - fk),
                round(fp, 2),
                *[round(fb[c]) for c in CLASSES],
                int(year in PRE_LOCAL_ELECTION),
            ]
        )
        print(
            year,
            int(rt),
            int(province[year]),
            "ham",
            round(rp, 2),
            "duz",
            round(fp, 2),
            [round(fb[c]) for c in CLASSES],
        )

with open(
    HERE / f"il_kent_kir_seri_{PLATE}_ilce.csv", "w", encoding="utf-8", newline=""
) as f:
    w = csv.writer(f)
    w.writerow(["ilce", "yil", "ham_nufus", "ham_oran", "nufus", "kent", "kir", "oran"])
    for d, name in sorted(districts.items()):
        for year in YEARS:
            _, rt, rp = share(raw, year, d)
            fb, ft, fp = share(fixed, year, d)
            fk = sum(fb[c] for c in URBAN)
            w.writerow(
                [
                    name,
                    year,
                    int(rt),
                    round(rp, 1),
                    round(ft),
                    round(fk),
                    round(ft - fk),
                    round(fp, 1),
                ]
            )
