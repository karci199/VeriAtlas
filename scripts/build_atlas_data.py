"""Build the data bundle for the atlas page (web/atlas.html).

Writes public/atlas/TR-16-006.json — one district, everything the three panels need:
identity card, settlement list, population series, age bands (district / urban / rural),
marital status (district / urban / rural / neighbourhood). Also copies the neighbourhood
geometry to public/geo/neighbourhoods/TR-16-006.geojson in the same shape as the
district files (area_id, name_tr, area_level, parent_id).

Sources: Endeksa dump (raw/endeksa/TR-16-006, TÜİK ADNKS 2024 by neighbourhood), TÜİK
MEDAS district files (raw/medas), desktop series workbook for 1935-2025 urban/rural
population. Estimates are flagged with "estimate": true and never mixed into measured
cells silently (decision K28).
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RAW = Path("C:/veri/raw")
ENDEKSA = RAW / "endeksa" / "TR-16-006"
OUT = ROOT / "public" / "atlas"
GEO_OUT = ROOT / "public" / "geo" / "neighbourhoods"
DISTRICT = "TR-16-006"
YEAR = 2024

TR_LOWER = str.maketrans(
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ", "abcçdefgğhıijklmnoöprsştuüvyz"
)
BANDS13 = [
    (0, 4),
    (5, 9),
    (10, 14),
    (15, 19),
    (20, 24),
    (25, 29),
    (30, 34),
    (35, 39),
    (40, 44),
    (45, 49),
    (50, 54),
    (55, 59),
    (60, 64),
]
BANDS19 = [
    "0-4",
    "5-9",
    "10-14",
    "15-19",
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65-69",
    "70-74",
    "75-79",
    "80-84",
    "85-89",
    "90+",
]
MARITAL = {
    "MarriedNever": "never",
    "Married": "married",
    "Divorced": "divorced",
    "Widow": "widowed",
}
MARITAL_TR = {
    "Hiç Evlenmedi": "never",
    "Evli": "married",
    "Boşandı": "divorced",
    "Eşi Öldü": "widowed",
}
RURAL_TOWNS = {"Boyalıca", "Elbeyli"}


def title_tr(s: str) -> str:
    return " ".join(w[:1] + w[1:].translate(TR_LOWER) for w in s.split())


def load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(obj, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)


def read_medas(path: Path) -> tuple[list[str], list[str]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("iso-8859-9")
    lines = text.splitlines()
    header = lines[2].split("|")
    row = next(line for line in lines if "znik" in line).split("|")
    return header, row


def age_keys(sfx: str) -> list[str]:
    return [f"Age_{a}_{b}_{sfx}" for a, b in BANDS13] + [f"Age_65_{sfx}"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    GEO_OUT.mkdir(parents=True, exist_ok=True)

    county = load(ENDEKSA / "county.json")["Demography"]
    units = []
    urban_age = {s: [0] * 14 for s in ("Male", "Female")}
    urban_marital = {k: 0 for k in MARITAL.values()}
    urban_sex = {"Male": 0, "Female": 0}
    for f in sorted(glob.glob(str(ENDEKSA / "[0-9]*.json"))):
        d = load(f)["Demography"]
        did = d["DistrictId"]
        name = title_tr(d["DistrictName"])
        if did < 100000:
            kind, settlement, urban = "centre", "İlçe merkezi", True
        elif name in RURAL_TOWNS:
            kind, settlement, urban = "rural_town", name, False
        else:
            kind, settlement, urban = "village", name, False
        age_ok = (
            sum(d[k] or 0 for k in age_keys("Total")) == d["PopulationTotal"]
            and d["PopulationTotal"] > 0
        )
        marital = {v: d[k] for k, v in MARITAL.items()}
        marital_ok = sum(marital.values()) > 0
        u = {
            "id": f"{DISTRICT}-{did}",
            "endeksa_id": did,
            "name": name,
            "kind": kind,
            "settlement": settlement,
            "urban": urban,
            "population": d["PopulationTotal"],
            "male": d["PopulationMale"],
            "female": d["PopulationFemale"],
            "households": d["HouseholdCount"] or None,
            "area_km2_endeksa": round(d["Area"], 2),
            "age": {
                "bands": [f"{a}-{b}" for a, b in BANDS13] + ["65+"],
                "male": [d[k] for k in age_keys("Male")],
                "female": [d[k] for k in age_keys("Female")],
            }
            if age_ok
            else None,
            "marital": marital if marital_ok else None,
        }
        units.append(u)
        if urban:
            for s, acc in urban_age.items():
                for i, k in enumerate(age_keys(s)):
                    acc[i] += d[k]
            for k, v in MARITAL.items():
                urban_marital[v] += d[k]
            urban_sex["Male"] += d["PopulationMale"]
            urban_sex["Female"] += d["PopulationFemale"]
    order = {"centre": 0, "urban_town": 1, "rural_town": 2, "village": 3}
    units.sort(key=lambda u: (order[u["kind"]], u["name"]))

    # district age 19 bands x sex (TÜİK MEDAS)
    header, row = read_medas(RAW / "medas" / "ilce" / f"nufus-ilce-kirilim-{YEAR}.csv")
    tuik = {}
    for h, v in zip(header, row):
        if " ve " in h and v:
            s, b = h.split(" ve ")
            tuik[(s, b)] = int(float(v))
    dist_age = {
        "bands": BANDS19,
        "male": [tuik[("Erkek", b)] for b in BANDS19],
        "female": [tuik[("Kadın", b)] for b in BANDS19],
    }
    assert sum(dist_age["male"]) + sum(dist_age["female"]) == county["PopulationTotal"]

    # urban/rural 65+ sub-bands: estimate (IPF) from scripts/estimate_urban_rural_age + 2012 shares
    est_all = load(RAW / "derived" / "iznik_age_urban_rural_2007_2025.json")
    est = est_all[str(YEAR)]
    age_series = {
        y: {
            "district": {
                "bands": BANDS19,
                "male": v["Toplam"]["m"],
                "female": v["Toplam"]["f"],
            },
            "urban": {
                "bands": BANDS19,
                "male": v["Kent"]["m"],
                "female": v["Kent"]["f"],
                "estimate_from_band": 0 if v["est"] else None,
            },
            "rural": {
                "bands": BANDS19,
                "male": v["Kır"]["m"],
                "female": v["Kır"]["f"],
                "estimate_from_band": 0 if v["est"] else None,
            },
        }
        for y, v in est_all.items()
    }
    urban_age19 = {
        "bands": BANDS19,
        "male": est["Kent"]["m"],
        "female": est["Kent"]["f"],
        "estimate_from_band": 13,
    }
    rural_age19 = {
        "bands": BANDS19,
        "male": est["Kır"]["m"],
        "female": est["Kır"]["f"],
        "estimate_from_band": 13,
    }
    assert sum(urban_age19["male"][:13]) == sum(urban_age["Male"][:13])

    # district marital x sex x age (TÜİK MEDAS, 2024)
    header, row = read_medas(
        RAW / "medas" / "medeni" / f"nufus-medeni-ilce-bursa-{YEAR}-{YEAR}.csv"
    )
    mar = {}
    for h, v in zip(header, row):
        if h.count(" ve ") == 2 and v:
            s, a, m = h.split(" ve ")
            mar.setdefault(MARITAL_TR[m], {}).setdefault(
                "Erkek" == s and "male" or "female", {}
            )[a] = int(float(v))
    mar_ages = sorted(
        {a for m in mar.values() for s in m.values() for a in s},
        key=lambda x: int(re.match(r"\d+", x).group()),
    )
    dist_marital = {
        "total": {k: county[src] for src, k in MARITAL.items()},
        "by_sex_age": {
            "ages": mar_ages,
            **{
                k: {
                    s: [mar[k][s].get(a, 0) for a in mar_ages]
                    for s in ("male", "female")
                }
                for k in mar
            },
        },
    }
    assert sum(dist_marital["total"].values()) == sum(
        v for k in mar.values() for s in k.values() for v in s.values()
    )

    # population series 1935-2025 (desktop workbook, urban = centre neighbourhoods)
    wb = openpyxl.load_workbook(
        "C:/Users/katan/OneDrive/Desktop/demografi/iznik_kent_kir.xlsx", data_only=True
    )
    ws = wb["Yillik 1935-2025"]
    real = {}
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] and r[4] != "Interpolasyon":
            real[int(r[0])] = (int(r[1]), int(r[2]))
    real[2000] = (20169, 24601)
    real[2007] = (22179, 22335)
    series = [
        {"year": y, "urban": k, "rural": r, "estimate": False}
        for y, (k, r) in sorted(real.items())
    ]

    # series-level urban/rural totals used as map/table context
    bundle = {
        "id": DISTRICT,
        "name": "İznik",
        "province": "Bursa",
        "province_id": "TR-16",
        "region": "Doğu Marmara",
        "reference_year": YEAR,
        "card": {
            "area_km2": 753,
            "area_note": "HGM; İznik Gölü ≈298 km² dahil, kara ≈455 km²",
            "elevation_m": 98,
            "distance_to_province_km": 76,
            "population": county["PopulationTotal"],
            "population_2025": 45510,
            "urban_population": urban_sex["Male"] + urban_sex["Female"],
            "households": county["HouseholdCount"],
            "centre_units": sum(1 for u in units if u["kind"] == "centre"),
            "rural_units": sum(1 for u in units if u["kind"] != "centre"),
        },
        "units": units,
        "series": series,
        "age": {"district": dist_age, "urban": urban_age19, "rural": rural_age19},
        "age_series": age_series,
        "marital": {
            "district": dist_marital,
            "urban": urban_marital,
            "rural": {k: county[src] - urban_marital[k] for src, k in MARITAL.items()},
        },
        "sources": [
            "TÜİK ADNKS 2024 (MEDAS: ilçe yaş × cinsiyet; medeni durum × cinsiyet × yaş)",
            "Endeksa mahalle dökümü 2024 (TÜİK ile birebir; yaş ve medeni durum mahalle düzeyi)",
            "Genel nüfus sayımları 1935–2000; ADNKS 2007–2025 (kent/kır serisi)",
            "HGM (alan), Wikipedia (rakım, uzaklık)",
        ],
    }
    dump(bundle, OUT / f"{DISTRICT}.json")

    # neighbourhood geometry in the district-file shape
    geo = load(ENDEKSA / "geo.json")
    by_id = {u["endeksa_id"]: u for u in units}
    feats = []
    for f in geo["features"]:
        did = int(f["id"])
        if did not in by_id:
            continue
        u = by_id[did]
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "area_id": u["id"],
                    "name_tr": u["name"],
                    "area_level": "neighbourhood",
                    "parent_id": DISTRICT,
                    "kind": u["kind"],
                },
                "geometry": f["geometry"],
            }
        )
    dump(
        {"type": "FeatureCollection", "features": feats},
        GEO_OUT / f"{DISTRICT}.geojson",
    )
    print("ok", len(units), "units,", len(feats), "polygons")


if __name__ == "__main__":
    main()
