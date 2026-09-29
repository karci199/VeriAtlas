"""Population by year for every province, district, belde and neighbourhood/village, for the
ranking page web/nufus.html.

usage: build_population_table.py [--fact PATH]

Levels
  province, district  ADNKS district totals (sum of the age x sex rows), 2007-2025
  neighbourhood       every neighbourhood and village id with its own years: ids of 2007-2012
                      and of 2013-2025 are different registries, so a place renumbered in
                      2013 shows as two rows, each with its own span
  belde               official: a neighbourhood whose registry municipality is not the
                      district's own (non-metropolitan provinces only), summed 2013-2025;
                      a belde's quarters are also listed as neighbourhoods

Writes public/nufus_birimler.json (git-ignored, ~8 MB):
  years, provinces [[id, name]], districts [[id, name, province index]],
  settlements [name], history {district index: [dated notes]}, units [[level, name, district index, first year index, [population ...],
  settlement index (neighbourhoods/villages only, -1 otherwise or unknown),
  under-18 series [first year index, values] or null]]
"""
import json
import sys
from pathlib import Path

import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FACT = sys.argv[sys.argv.index("--fact") + 1] if "--fact" in sys.argv else "C:/veri/public/fact.parquet"
KK = Path("C:/veri-ham/analiz/kent_kir")
YEARS = list(range(2007, 2026))

areas = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr.csv", infer_schema_length=0)
prov = areas.filter(pl.col("area_level") == "province").sort("area_id")
dist = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0).sort("area_id")
P = {r["area_id"]: i for i, r in enumerate(prov.iter_rows(named=True))}
D = {r["area_id"]: i for i, r in enumerate(dist.iter_rows(named=True))}

pop = duckdb.sql(f"""select area_id, area_level, year(period_start) y, sum(value) v from read_parquet('{FACT}')
  where indicator_id='population' and area_level in ('district','neighbourhood','village') group by 1,2,3""").pl()
series = {}
for r in pop.iter_rows(named=True):
    series.setdefault((r["area_id"], r["area_level"]), {})[r["y"]] = int(r["v"])

# under-18s. Neighbourhoods carry an age=0-17 row (suppressed where tiny, so missing is
# missing, not zero); districts only 5-year bands, 18-19 taken as 2/5 of 15-19; villages of
# non-metropolitan provinces have totals only
U17 = {}
for r in duckdb.sql(f"""select area_id, year(period_start) y, sum(value) v from read_parquet('{FACT}')
  where indicator_id='population' and area_level='neighbourhood' and dims='age=0-17' group by 1,2""").pl().iter_rows(named=True):
    U17.setdefault(r["area_id"], {})[r["y"]] = int(r["v"])
for r in duckdb.sql(f"""select area_id, year(period_start) y,
    sum(value) filter (where dims like 'age=0-4;%' or dims like 'age=5-9;%' or dims like 'age=10-14;%') a,
    sum(value) filter (where dims like 'age=15-19;%') b
  from read_parquet('{FACT}') where indicator_id='population' and area_level='district' group by 1,2""").pl().iter_rows(named=True):
    if r["a"] is not None:
        U17.setdefault(r["area_id"], {})[r["y"]] = int(round(r["a"] + 0.6 * (r["b"] or 0)))


def upack(*ids):
    """under-18 series of one or more ids summed (a year counts only if every id has it)"""
    acc = {}
    ys = None
    for i in ids:
        s_ = U17.get(i, {})
        ys = set(s_) if ys is None else ys & set(s_)
        for y, v in s_.items():
            acc[y] = acc.get(y, 0) + v
    acc = {y: v for y, v in acc.items() if ys and y in ys}
    p_ = pack(acc) if acc else None
    return list(p_) if p_ else None


def pack(s):
    ys = [y for y in YEARS if y in s]
    if not ys:
        return None
    first, last = YEARS.index(ys[0]), YEARS.index(ys[-1])
    return first, [s.get(YEARS[i]) for i in range(first, last + 1)]


names = {}
for f, suffix in (("areas_tr_neighbourhoods.csv", " Mah."), ("areas_tr_villages.csv", " Köy.")):
    for r in pl.read_csv(ROOT / "src/veriatlas/data" / f, infer_schema_length=0).iter_rows(named=True):
        names[r["area_id"]] = r["name_tr"].removesuffix(suffix).strip()

sys.path.insert(0, str(ROOT / "scripts/analiz/kent_kir_2026_09_27"))
_argv, sys.argv = sys.argv, [sys.argv[0], "06"]
from il import wh  # noqa: E402

sys.argv = _argv
# settlement ("yerleşim"), official for now (user, 2026-09-29; our own urban/rural split comes
# later): a village is "<district> Köyleri", a belde quarter carries the belde (set further
# down), any other quarter "<district> Merkez". Metropolitan provinces turned their villages
# into quarters in 2013; a quarter that first appears in 2013 there is marked as such.
METRO = {"01", "06", "07", "09", "10", "16", "20", "21", "25", "26", "27", "31", "33", "34", "35", "38", "41", "42",
         "44", "45", "46", "47", "48", "52", "54", "55", "59", "61", "63", "65"}
FIRST = {}
for f in ("areas_tr_neighbourhoods.csv", "areas_tr_villages.csv"):
    for r in pl.read_csv(ROOT / "src/veriatlas/data" / f, infer_schema_length=0).iter_rows(named=True):
        FIRST[r["area_id"]] = int(r["first_seen"])
SETTLE_NAMES = []


def settle(name):
    if name not in SETTLE_NAMES:
        SETTLE_NAMES.append(name)
    return SETTLE_NAMES.index(name)


def official_settlement(aid, lvl, did):
    dn = dist["name_tr"][D[did]]
    if lvl == "village":
        return settle(f"{dn} Köyleri")
    if aid[3:5] in METRO and FIRST.get(aid) == 2013:
        return settle(f"{dn} Köyleri (2013'e kadar köy)")
    return settle(f"{dn} Merkez")


# district lineage. A rename keeps the MEDAS code under a new id (Eyüp -> Eyüpsultan,
# Kazan -> Kahramankazan): one series under the current id. A district that opens or closes
# gets a dated note; where it came from / went to is read off its quarters' registry history.
REN = {}
for code, g in dist.group_by("medas_code"):
    if len(g) > 1:
        cur = g.filter(pl.col("valid_to").is_null())
        if len(cur) == 1:
            for r in g.filter(pl.col("valid_to").is_not_null()).iter_rows(named=True):
                REN[r["area_id"]] = (cur["area_id"][0], r["name_tr"], r["valid_to"])
for old, (new_, oldname, _) in REN.items():
    for (aid, lvl), s_ in list(series.items()):
        if lvl == "district" and aid == old:
            tgt = series.setdefault((new_, "district"), {})
            for y, v in s_.items():
                tgt.setdefault(y, v)
            del series[(aid, lvl)]
dtot = {aid: s_ for (aid, lvl), s_ in series.items() if lvl == "district"}
HIST = {}


# where a district's quarters were before it opened, from each quarter's registry history
# ("TR-06-002:2007;TR-06-022:2008-2025"), weighted by the quarter's population in the year
LINEAGE = {}
for f in ("areas_tr_neighbourhoods.csv", "areas_tr_villages.csv"):
    for r in pl.read_csv(ROOT / "src/veriatlas/data" / f, infer_schema_length=0).iter_rows(named=True):
        spans = []
        for part in (r["parent_history"] or "").split(";"):
            if ":" in part:
                pid, yrs = part.split(":")
                y0, _, y1 = yrs.partition("-")
                spans.append((REN.get(pid, (pid,))[0], int(y0), int(y1 or y0)))
        LINEAGE[r["area_id"]] = spans


QBY = {}
for q, spans in LINEAGE.items():
    for pid, _, _ in spans:
        QBY.setdefault(pid, set()).add(q)


def parent_in(aid, y):
    for pid, y0, y1 in LINEAGE.get(aid, []):
        if y0 <= y <= y1:
            return pid
    return None


PNAME = {r["area_id"]: r["name_tr"] for r in prov.iter_rows(named=True)}


def dname(k):
    """district name; a bare "Merkez" is ambiguous, so it carries its province"""
    n = dist["name_tr"][D[k]] if k in D else k
    return f"{PNAME.get(k[:5], '')} Merkez" if n == "Merkez" else n


def sources(did, y):
    """districts whose quarters formed `did` in year y, largest first, as name (share %)"""
    w = {}
    for aid, spans in LINEAGE.items():
        if parent_in(aid, y) != did:
            continue
        before = parent_in(aid, y - 1)
        if before and before != did:
            pop_ = (series.get((aid, "neighbourhood")) or series.get((aid, "village")) or {}).get(y, 0)
            w[before] = w.get(before, 0) + pop_
    tot = sum(w.values())
    return [(dname(k), round(v / tot * 100)) for k, v in sorted(w.items(), key=lambda x: -x[1]) if tot and v / tot >= 0.02]


closed = {}
for r in dist.filter(pl.col("valid_to").is_not_null()).iter_rows(named=True):
    if r["area_id"] not in REN:
        closed.setdefault((r["area_id"][:5], int(r["valid_to"])), []).append(dname(r["area_id"]))

# a closed district whose quarters all went to one district opened the next year, and
# that district took quarters from nowhere else, only changed its name (Aydın Merkez ->
# Efeler, Trabzon Merkez -> Ortahisar): merged like a rename
for r in dist.filter(pl.col("valid_to").is_not_null()).iter_rows(named=True):
    old = r["area_id"]
    if old in REN or old not in dtot:
        continue
    y = max(dtot[old])
    heirs = {parent_in(q, y + 1) for q in LINEAGE if parent_in(q, y) == old} - {None, old}
    if len(heirs) != 1:
        continue
    new_ = heirs.pop()
    src = sources(new_, y + 1)
    if new_ in dtot and min(dtot[new_]) == y + 1 and len(src) == 1:
        tgt = dtot[new_]
        for yy, v in dtot.pop(old).items():
            tgt.setdefault(yy, v)
        series.pop((old, "district"), None)
        REN[old] = (new_, dname(old), str(y))

renamed_to = {v[0]: (v[1], v[2]) for v in REN.values()}
for r in dist.iter_rows(named=True):
    aid, i = r["area_id"], D[r["area_id"]]
    notes = []
    if aid in renamed_to:
        oldname, until = renamed_to[aid]
        notes.append(f"{until} yılına kadar adı {oldname}; {int(until) + 1} yılından itibaren {r['name_tr']}.")
    elif r["valid_from"] and aid in dtot:
        y = min(dtot[aid])
        src = sources(aid, y)
        prev = closed.get((aid[:5], y - 1))
        txt = f"{y} yılında kuruldu"
        gone = [n for n, _ in src if n in (prev or [])]
        if gone and len(gone) == len(src):
            txt += f"; {', '.join(gone)} ilçesi {y - 1}'den sonra kapandı ve bölündü, mahallelerinin bir kısmı buraya geçti"
        elif src:
            txt += "; mahalleleri önceden şu ilçelerdeydi: " + ", ".join(f"{n} (%{w})" for n, w in src)
        notes.append(txt + ".")
    if r["valid_to"] and aid not in REN and aid in dtot:
        y = max(dtot[aid])
        heirs = {}
        for q, spans in LINEAGE.items():
            if parent_in(q, y) == aid:
                nxt = parent_in(q, y + 1)
                if nxt and nxt != aid:
                    heirs[nxt] = heirs.get(nxt, 0) + (series.get((q, "neighbourhood")) or series.get((q, "village")) or {}).get(y, 0)
        tot = sum(heirs.values())
        hs = [f"{dname(k)} (%{round(v / tot * 100)})" for k, v in sorted(heirs.items(), key=lambda x: -x[1]) if tot and v / tot >= 0.02]
        notes.append(f"{y} yılından sonra kaldırıldı" + (f"; mahalleleri şu ilçelere geçti: {', '.join(hs)}." if hs else "."))
    # boundary changes of a district that stayed: quarters moving in or out in a year, when
    # they are at least 3% of the district and 500 people (Pamukkale takes Denizli Merkez in
    # 2013, Büyükçekmece gives Esenyurt and Beylikdüzü its quarters in 2008)
    if aid in dtot:
        for y in sorted(dtot[aid]):
            if y - 1 not in dtot[aid] or (r["valid_from"] and y == min(dtot[aid])):
                continue
            gin, gout = {}, {}
            for q in QBY.get(aid, ()):  # quarters that were ever in this district
                a0, a1 = parent_in(q, y - 1), parent_in(q, y)
                if a0 == a1 or aid not in (a0, a1):
                    continue
                pop_ = (series.get((q, "neighbourhood")) or series.get((q, "village")) or {})
                n = pop_.get(y if a1 == aid else y - 1, 0)
                other = a0 if a1 == aid else a1
                if other:
                    (gin if a1 == aid else gout)[other] = (gin if a1 == aid else gout).get(other, 0) + n
            base = dtot[aid][y - 1]
            for tag, g in (("aldı", gin), ("verdi", gout)):
                tot = sum(g.values())
                if tot >= 500 and tot >= 0.03 * base:
                    tr = lambda n: f"{n:,}".replace(",", ".")  # noqa: E731  Turkish thousands
                    parts = ", ".join(f"{dname(k)} ({tr(n)})" for k, n in sorted(g.items(), key=lambda x: -x[1])[:4])
                    move = f"{parts} ilçesinden mahalle aldı" if tag == "aldı" else f"mahallelerini {parts} ilçesine verdi"
                    notes.append(f"{y}: {move}; nüfusu {tr(base)} → {tr(dtot[aid][y])}.")
    if notes:
        HIST[i] = notes

units = []
for (aid, lvl), s in series.items():
    if lvl != "district" or aid not in D or aid in REN:
        continue
    first, vals = pack(s)
    olds = [o for o, v in REN.items() if v[0] == aid]
    for o in olds:  # a renamed district's earlier years
        for y, v in U17.get(o, {}).items():
            U17.setdefault(aid, {}).setdefault(y, v)
    units.append(["ilce", dist["name_tr"][D[aid]], D[aid], first, vals, -1, upack(aid)])
prov_tot = {}
for (aid, lvl), s in series.items():
    if lvl == "district" and aid[:5] in P:
        for y, v in s.items():
            prov_tot.setdefault(aid[:5], {}).setdefault(y, 0)
            prov_tot[aid[:5]][y] += v
for pid, s in prov_tot.items():
    first, vals = pack(s)
    # a year counts when every district with a total that year also has its under-18s
    acc = {}
    for y in s:
        ds = [a for (a, lvl), s_ in series.items() if lvl == "district" and a[:5] == pid and y in s_]
        if ds and all(y in U17.get(a, {}) for a in ds):
            acc[y] = sum(U17[a][y] for a in ds)
    units.append(["il", prov["name_tr"][P[pid]], -1 - P[pid], first, vals, -1, list(pack(acc)) if acc else None])  # negative index = province
for (aid, lvl), s in series.items():
    if lvl == "district":
        continue
    did = aid.rsplit("-", 1)[0]
    did = REN.get(did, (did,))[0]
    if did not in D:
        continue
    first, vals = pack(s)
    units.append(["koy" if lvl == "village" else "mahalle", names.get(aid, aid), D[did], first, vals,
                  official_settlement(aid, lvl, did) if YEARS[first + len(vals) - 1] >= 2013 else -1,
                  upack(aid) if lvl == "neighbourhood" else None, aid])

# beldes: official status for now (user, 2026-09-29) -- a neighbourhood whose municipality
# in the TÜİK registry is not the district's own is a belde quarter. Only non-metropolitan
# provinces still have beldes; closed ones (2014) are not beldes here. 2013-2025 on the
# registry's current ids, 2007-2012 on the older ids of the same belde.
def _fold(t):
    t = (t or "").replace("İ", "i").replace("I", "ı").lower()
    for x, y in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(x, y)
    return "".join(ch for ch in t if ch.isalpha())


reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(pl.col("last_seen") == "2025")
BELDE_OF = {}
for r in reg.iter_rows(named=True):
    did = r["parent_id"]
    mun = (r["municipality"] or "").removesuffix(" Bel.").strip()
    if did in D and mun and _fold(mun) != _fold(dist["name_tr"][D[did]]) and "Büyükşehir" not in mun:
        BELDE_OF[r["area_id"]] = mun
belde = {}
bu17 = {}
for aid, name in BELDE_OF.items():
    did = aid.rsplit("-", 1)[0]
    bu17.setdefault((did, name), []).append(aid)
    b = belde.setdefault((did, name), {})
    for y, v in (series.get((aid, "neighbourhood")) or {}).items():
        b[y] = b.get(y, 0) + v  # outside metropolitan provinces the ids run from 2007
# 2007-2012: those years run on the older neighbourhood ids; a quarter whose registry
# municipality is a belde that still stands in the same district is counted with it (the
# registry keeps the newest municipality name, which for a surviving belde is its own)
old_reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(pl.col("last_seen").cast(pl.Int32) <= 2012)
for r in old_reg.iter_rows(named=True):
    did = REN.get(r["parent_id"], (r["parent_id"],))[0]
    mun = (r["municipality"] or "").removesuffix(" Bel.").strip()
    if (did, mun) in belde:
        bu17[(did, mun)].append(r["area_id"])
        b = belde[(did, mun)]
        for y, v in (series.get((r["area_id"], "neighbourhood")) or {}).items():
            if y <= 2012:
                b[y] = b.get(y, 0) + v
for (did, name), s_ in belde.items():
    if s_:
        first, vals = pack(s_)
        # under-18s: the quarters' rows summed per year (quarters of 2007-2012 and of today
        # never overlap in a year, so the sum is over whichever ids that year has)
        acc = {}
        for q in bu17[(did, name)]:
            for y, v in U17.get(q, {}).items():
                acc[y] = acc.get(y, 0) + v
        units.append(["belde", name, D[did], first, vals, -1, list(pack(acc)) if acc else None])
# a belde quarter's settlement is its belde (official), whatever the analysis said
for u in units:
    if u[0] == "mahalle" and u[7] in BELDE_OF:
        u[5] = settle(BELDE_OF[u[7]])
for u in units:
    if u[0] in ("mahalle", "koy"):
        del u[7]

# a district's own quarters summed per year: today's boundaries, used as the share base in
# years the district did not exist yet (Kayapınar, Ataşehir in 2007)
cb = {}
for u in units:
    if u[0] in ("mahalle", "koy"):
        acc = cb.setdefault(u[2], {})
        for i, v in enumerate(u[4]):
            if v is not None:
                y = YEARS[u[3] + i]
                acc[y] = acc.get(y, 0) + v
district_cb = {str(k): list(pack(v)) for k, v in cb.items() if v}

out = dict(years=YEARS, provinces=[[r["area_id"], r["name_tr"]] for r in prov.iter_rows(named=True)],
           districts=[[r["area_id"], r["name_tr"], P.get(r["area_id"][:5], -1)] for r in dist.iter_rows(named=True)],
           settlements=SETTLE_NAMES, district_cb=district_cb, history={str(k): v for k, v in HIST.items()}, units=units)
dst = ROOT / "public/nufus_birimler.json"
dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
from collections import Counter  # noqa: E402
print(dst, f"{dst.stat().st_size / 1e6:.1f} MB", Counter(u[0] for u in units))
