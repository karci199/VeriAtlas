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

4. Suburb held by a rural unit until a redraw (SUBURB_SPLITS): people above the rural line count
   as urban before the redraw. An estimate; the raw series keeps them where the registry had them.

5. No smoothing (SHOCK_FROM): Malatya, after the February 2023 earthquakes. The people left or
   moved for good, so rules 2 and 3 are not applied in any year; the series shows what was
   registered.

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
# From this year neither the election-year mean nor the blip rule may touch a province's series.
# Malatya: the February 2023 earthquakes moved people for good, and the registry is kept as it is
# in every year.
SHOCK_FROM = {"44": 2007}
SHOCK = SHOCK_FROM.get(PLATE, 9999)
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

# Retired units no name rule can place: absorbed by the centre in 2023 (Saltuk, Yunus Emre), a village (Hamamlı).
RETIRED_CLASS = {
    "TR-51-002-196399": "İlçe Merkezi",
    "TR-51-003-199107": "İlçe Merkezi",
    "TR-51-005-140587": "Köy",
}
# New or closed units that match no name: each takes the class of the unit it split from (or was
# absorbed into), read off the year the people moved. 2025 mahalle splits (Izmir, Erzurum, Sanliurfa,
# Ankara) and the units that appear or vanish in a redraw (Istanbul, Mugla, Van, Bayburt-sized ones).
RETIRED_CLASS |= {
    "TR-06-006-240655": "Köy",  # Tokar: 224 in 2025, taken from Ozmus and other villages
    "TR-10-007-147549": "Köy",  # Karyagmaz, closed 2022: its people went to villages
    "TR-25-019-190795": "Köy",  # Pehlivanli: villages around it took the people
    "TR-25-002-540062": "İlçe Merkezi",  # Gezkoy, 2025: 5,799 from Saltuklu (centre)
    "TR-34-037-199723": "İlçe Merkezi",  # Yenisehir 2018-22: from Site, Esenevler, Istiklal (centre)
    "TR-35-026-964817": "İlçe Merkezi",  # Necat Hepkon, 2025: from Camikebir, Colak Ibrahim Bey (centre)
    "TR-35-004-338624": "İlçe Merkezi",  # 100. Yil, 2025: 6,717 from R.Sevket Ince (centre)
    "TR-48-001-176221": "Kentsel Belde",  # Ortakentyahsi, 2013-17: Merkez, Bitez, Akcaalan (urban town)
    "TR-63-013-184842": "Köy",  # Saglamlar
    "TR-63-008-198255": "Köy",  # Gozele
    "TR-63-008-821991": "Köy",  # Karakecili
    "TR-63-008-263996": "Köy",  # Birlik
    "TR-63-008-760041": "Köy",  # Gul
    "TR-63-013-539429": "Köy",  # Alioglu
    "TR-63-001-128694": "İlçe Merkezi",  # Tepecik: Adnan Menderes (centre) gave most
    "TR-63-001-748517": "İlçe Merkezi",  # Ertugrul Gazi: same
    "TR-65-007-159231": "Köy",  # Akdamar, closed 2018
    "TR-65-004-159057": "Köy",  # Andicen, closed 2016
    "TR-80-005-548933": "Kırsal Belde",  # Murat Kurum Bey, 2025: 3,623 from Yesiltepe, Akyar (rural towns), Dereobasi (village)
    "TR-55-x1593-26751": "Köy",  # Alibeyli, 2007 only: renumbered as TR-55-008-37813
}
# A retired unit whose old district id is not a district any more: the district that holds it today.
RETIRED_HOME = {"TR-55-x1593-26751": "TR-55-008"}
# A rural unit that held a growing suburb until a redraw split the suburb off. Its people above a
# line from (from_year, rural) to (redraw_year, rural) belong to the urban class before the redraw.
# Fertek: 9,287 in 2022, 925 in 2023 as Sarıköprü and Kayaardı (urban) took the suburb.
SUBURB_SPLITS = [
    {
        "district": "TR-51-005",
        "units": ("TR-51-005-49191", "TR-51-005-184632"),
        "rural_class": "Köy",
        "urban_class": "İlçe Merkezi",
        "from_year": 2014,
        "from_rural": 2280,
        "redraw_year": 2023,
        "redraw_rural": 925,
    }
]

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
        # Only the same unit today can overrule the centre. A namesake in another town does not:
        # Niğde's Yenice (5,720 people) is not Dündarlı's Yenice.
        for a, d in decisions.items():
            other = registry.get(a)
            if (
                other
                and a.startswith(district + "-")
                and other.get("municipality") == r.get("municipality")
                and key(other["name_tr"]) == key(r.get("name_tr"))
            ):
                return "district_municipality", d["s"], district
        return "district_municipality", "İlçe Merkezi", district
    place = find_place(district, r.get("name_tr"))
    return ("late_name", place, district) if place else ("unresolved", None, district)


retired = {a: resolve(a) for a in cells if a not in decisions}
for area, cls in RETIRED_CLASS.items():
    if area in retired:
        retired[area] = ("manual", cls, RETIRED_HOME.get(area, area[:9]))
# A retired district's leftovers go to the district that took most of its places.
old_district = collections.defaultdict(collections.Counter)
for area, (_, _, d) in retired.items():
    home = area.rsplit("-", 1)[0]
    if home not in districts and d in districts:
        old_district[home][d] += 1
for area, (rule, cls, d) in list(retired.items()):
    if d not in districts:
        if (
            not old_district[d]
            and sum(population(area, y) for y in range(2007, 2026)) < 100
        ):
            # under 100 people in all years and no district took its places: park it in the first district
            retired[area] = (rule, cls, min(districts))
            continue
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

for split in SUBURB_SPLITS:
    if not split["district"].startswith(PREFIX):
        continue
    rural = fixed[(split["district"], split["rural_class"])]
    urban = fixed[(split["district"], split["urban_class"])]
    start, end = split["from_year"], split["redraw_year"]
    for year in range(start, end):
        people = sum(population(a, year) for a in split["units"])
        line = split["from_rural"] + (split["redraw_rural"] - split["from_rural"]) * (
            year - start
        ) / (end - start)
        moved = max(people - line, 0)
        rural[year] -= moved
        urban[year] += moved
        print("suburb split", year, round(people), "moved", round(moved))

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
            if after >= SHOCK:
                continue
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
    if year >= SHOCK:
        continue
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
                int(year in PRE_LOCAL_ELECTION and year < SHOCK),
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
