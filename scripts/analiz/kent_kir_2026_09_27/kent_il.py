"""Built-up town area per district of one province: Microsoft buildings + Endeksa geometry + TÜİK/Endeksa population.

Rule (fixed 2026-09-27 on İznik/Yenişehir/Kalecik): buildings with footprint < 1,500 m²,
buffered 50 m, unioned, shrunk 50 m; clusters clipped to the district; the town is the
largest cluster plus every cluster of >= 30 buildings within 300 m of it (chained).
A neighbourhood is urban when >= 50% of its buildings are inside the town.
"""

import gzip, json, math, sys, time
from pathlib import Path
import numpy as np, polars as pl, shapely, duckdb

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG, LOCAL24, wh, geo_code  # noqa: E402
OUT = D

t0 = time.time()
geo = json.loads((ROOT / f"public/geo/districts/TR-{PLATE}.geojson").read_text(encoding="utf-8"))
dist = {f["properties"]["area_id"]: (f["properties"]["name_tr"], shapely.from_geojson(json.dumps(f["geometry"]))) for f in geo["features"]}
prov = shapely.union_all([g for _, g in dist.values()])
lat0 = shapely.centroid(prov).y
KX = 111320 * math.cos(math.radians(lat0)); KY = 110574
proj = lambda g: shapely.transform(g, lambda a: a * np.array([KX, KY]))
minx, miny, maxx, maxy = prov.bounds

# buildings of the province: only the level-9 quadkey tiles that touch its bounding box
def quadkey_bbox(q):
    x = y = 0
    for i, ch in enumerate(q):
        m = 1 << (len(q) - 1 - i)
        if int(ch) & 1: x |= m
        if int(ch) & 2: y |= m
    n = 1 << len(q)
    lon = lambda t: t / n * 360 - 180
    lat = lambda t: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * t / n))))
    return lon(x), lat(y + 1), lon(x + 1), lat(y)


tiles = [f for f in sorted(Path("C:/veri-ham/msbuildings").glob("*.csv.gz"))
         if (lambda b: b[0] <= maxx and b[2] >= minx and b[1] <= maxy and b[3] >= miny)(quadkey_bbox(f.stem.split(".")[0]))]
print("karo", len(tiles), flush=True)
polys = []
for f in tiles:
    with gzip.open(f, "rt") as fh:
        for line in fh:
            g = json.loads(line)["geometry"]["coordinates"][0]
            x, y = g[0]
            if minx <= x <= maxx and miny <= y <= maxy:
                polys.append([(a * KX, b * KY) for a, b in g])
B = shapely.polygons([shapely.linearrings(p) for p in polys])
area = shapely.area(B)
cent = shapely.centroid(B)
tree = shapely.STRtree(cent)
print(f"bina {len(B)} ({time.time()-t0:.0f} sn)", flush=True)

c = duckdb.connect()
pop = c.sql(f"""select area_id, sum(value) v from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='population' and area_id like 'TR-{PLATE}-%' and year(period_start)={YEAR} group by 1""").pl()
POP = dict(pop.iter_rows())
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-") & (pl.col("last_seen").cast(pl.Int64) >= YEAR))
REG = {r["area_id"]: r for r in reg.iter_rows(named=True)}
allreg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-"))
def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())
VIL = {}  # district -> folded names of its 2007-2012 villages
for r in pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0).filter(
        pl.col("parent_id").str.starts_with(f"TR-{PLATE}-")).iter_rows(named=True):
    VIL.setdefault(r["parent_id"], set()).add(fold(r["name_tr"].removesuffix(" Köy.")))
BELDE = {}  # district -> {folded belde name: "X Bel."}
for r in allreg.iter_rows(named=True):
    BELDE.setdefault(r["parent_id"], {})[fold(r["municipality"].removesuffix(" Bel."))] = r["municipality"]

rows, nb_rows = [], []
for did, (dname, dg) in sorted(dist.items()):
    dgp = proj(dg)
    idx = tree.query(dgp, predicate="contains")
    small = idx[area[idx] < 5000]
    if len(small) == 0:
        continue
    parts = shapely.get_parts(shapely.intersection(shapely.buffer(shapely.union_all(shapely.buffer(B[small], 50)), -50), dgp))
    parts = parts[shapely.area(parts) > 0]
    ptree = shapely.STRtree(parts)
    hit = ptree.query(cent[small], predicate="within")
    cnt = np.bincount(hit[1], minlength=len(parts))
    # Seed: the cluster holding most of the population of the district's pre-2013
    # neighbourhoods (where people actually live), not the one with most buildings --
    # in Mudanya that was a villa sprawl (Bademli), not the town.
    ng = json.loads((ROOT / f"public/geo/neighbourhoods/{did}.geojson").read_text(encoding="utf-8"))
    score = np.zeros(len(parts))
    oldcnt = np.zeros(len(parts))
    for f in ng["features"]:
        aid = wh(f["properties"]["area_id"]); r = REG.get(aid)
        if not r or int(r["first_seen"]) > 2012:
            continue
        g = proj(shapely.from_geojson(json.dumps(f["geometry"])))
        sel = small[shapely.contains(g, cent[small])]
        if len(sel) == 0:
            continue
        h = ptree.query(cent[sel], predicate="within")[1]
        oldcnt += np.bincount(h, minlength=len(parts))
        if len(h) and POP.get(aid):
            share = np.bincount(h, minlength=len(parts)) / len(sel)
            score += share * POP[aid]
    keep = {int(np.argmax(score)) if score.max() > 0 else int(np.argmax(cnt))}
    grow = True
    while grow:
        grow = False
        cur = shapely.union_all(parts[list(keep)])
        for i in np.where(cnt >= 30)[0]:
            # only clusters that belong to the old town (mostly buildings of pre-2013
            # neighbourhoods): a village next to the town (Cihadiye) is not chained in
            if int(i) not in keep and oldcnt[i] >= 0.5 * cnt[i] and shapely.distance(parts[i], cur) < 300:
                keep.add(int(i)); grow = True
    town = shapely.union_all(parts[list(keep)])
    in_town = shapely.contains(town, cent[idx])
    # neighbourhoods
    urban_pop = total_pop = 0; hh = dw = 0; n_urban = 0
    ek = json.loads((Path("C:/veri-ham/endeksa/demography") / f"{did}.json").read_text(encoding="utf-8")) if (Path("C:/veri-ham/endeksa/demography") / f"{did}.json").exists() else {}
    # pass 1: each neighbourhood's dominant cluster; a separate cluster whose
    # neighbourhoods hold >= 5,000 people is a town of its own (DEGURBA's urban-cluster
    # threshold): Görükle, Demirtaş, former beldes like Yeniceköy. Smaller ones stay rural.
    dom = {}
    cpop = np.zeros(len(parts))
    for f in ng["features"]:
        aid = wh(f["properties"]["area_id"])
        g = proj(shapely.from_geojson(json.dumps(f["geometry"])))
        ss = small[shapely.contains(g, cent[small])]
        h = ptree.query(cent[ss], predicate="within")[1] if len(ss) else []
        if len(h):
            bc = np.bincount(h, minlength=len(parts)); k = int(np.argmax(bc))
            if bc[k] >= 0.5 * len(ss):
                dom[aid] = k; cpop[k] += POP.get(aid) or 0
    sat = {i for i in range(len(parts)) if i not in keep and cpop[i] >= 5000}
    # organised industrial zones: recorded, but cut out of the town and its area
    osb = [proj(shapely.from_geojson(json.dumps(f["geometry"]))) for f in ng["features"]
           if "osb" in fold(f["properties"]["name_tr"])]
    if osb:
        town = shapely.difference(town, shapely.union_all(osb))
        in_town = shapely.contains(town, cent[idx])
    n_sat = sat_pop = 0
    for f in ng["features"]:
        aid = wh(f["properties"]["area_id"])
        g = proj(shapely.from_geojson(json.dumps(f["geometry"])))
        sel = idx[shapely.contains(g, cent[idx])]
        nb, nin = len(sel), int(shapely.contains(town, cent[sel]).sum()) if len(sel) else 0
        p = POP.get(aid)
        code = aid.rsplit("-", 1)[-1]
        r = REG.get(aid)
        e = (ek.get(geo_code(aid)) or {}).get("demography") or {}
        share = nin / nb if nb else 0
        old = bool(r) and int(r["first_seen"]) <= 2012
        belde = BELDE.get(did, {}).get(fold(f["properties"]["name_tr"]))
        belde = belde if belde and belde != f"{dname} Bel." else None
        is_osb = "osb" in fold(f["properties"]["name_tr"])
        urban = nb > 0 and share >= 0.5 and not (belde and not old) and not is_osb
        sinif = "merkez" if urban else "kir"
        satellite = not urban and not is_osb and (dom.get(aid) in sat or (p or 0) >= 5000)
        if is_osb:
            sinif, note = "osb", "OSB (kent sınırından düşüldü)"
        elif satellite:
            urban, sinif = True, "kentsel_belde"
            if dom.get(aid) in sat:
                note = f"kentsel belde/uydu: {'eski belde ' + belde + ', ' if belde else ''}lekesi {int(cpop[dom[aid]])} kişi (>=5.000)"
            else:
                note = "kentsel belde/uydu: nüfus >=5.000, görüntüde eksik yeni yapılaşma"
        elif dom.get(aid) is not None and dom.get(aid) not in keep and 2000 <= cpop[dom[aid]] < 5000:
            # a separate settlement of 2,000-5,000: rural in the binary split, but a town
            sinif = "kasaba"
            note = f"kasaba: ayrı leke {int(cpop[dom[aid]])} kişi (2.000-5.000)" + (f", eski belde {belde}" if belde and not old else "")
        elif belde and not old:
            sinif = "kirsal_belde"
            note = f"eski belde merkezi ({belde}, 2014'e kadar)"
        elif old and urban:
            note = "2013 öncesi mahalle, kasabada"
        elif old:
            note = "2013 öncesi mahalle, kasaba dışında ayrı yerleşim"
        elif urban and fold(f["properties"]["name_tr"]) not in VIL.get(did, set()):
            note = "2013 sonrası kurulan/bölünen kent mahallesi"
        elif urban:
            note = "eski köy, kasabayla kesintisiz yapılaşmış (elle kontrol)"
        elif share >= 0.2:
            note = "eski köy, kasabaya bitişik ama ayrı"
        else:
            note = "köy"
        hh_, dw_ = e.get("HouseholdCount") or 0, e.get("HousingCount") or 0
        if dw_ > 300 and hh_ < 0.3 * dw_ and hh_ > 0:
            note += " · yazlık ağırlıklı (konutların <%30'unda hane)"
        if sinif == "kentsel_belde":
            n_sat += 1; sat_pop += p or 0
        nb_rows.append(dict(district=dname, area_id=aid, name=f["properties"]["name_tr"], code=code,
                            first_seen=r["first_seen"] if r else None, buildings=nb, in_town=nin,
                            urban=urban, sinif=sinif, note=note, share=round(share, 2), pop=p, hh=e.get("HouseholdCount"), dwellings=e.get("HousingCount")))
        if p:
            total_pop += p
            if urban:
                urban_pop += p; n_urban += 1
                hh += e.get("HouseholdCount") or 0; dw += e.get("HousingCount") or 0
    a_km2 = shapely.area(town) / 1e6
    rows.append(dict(district=dname, area_id=did, town_km2=round(a_km2, 2), town_buildings=int(in_town.sum()),
                     urban_nbhd=n_urban, urban_pop=urban_pop, merkez_pop=urban_pop - sat_pop, kentsel_belde_pop=sat_pop, total_pop=total_pop,
                     urban_share=round(urban_pop / total_pop * 100, 1) if total_pop else None,
                     density=round((urban_pop - sat_pop) / a_km2) if a_km2 else None, hh=hh, dwellings=dw,
                     dw_per_bldg=round(dw / in_town.sum(), 1) if in_town.sum() else None))
    print(rows[-1], f"({time.time()-t0:.0f} sn)", flush=True)

pl.DataFrame(rows).write_csv(OUT / f"kent_{PLATE}.csv")
pl.DataFrame(nb_rows).write_csv(OUT / f"kent_{PLATE}_mahalle.csv")
print("bitti", time.time() - t0)
