"""One party's share by urban/rural class across every election 2002-2024 (province).

AK Parti by default (present in all elections; presidential rounds counted as Erdoğan).
Institutional boxes (votes >= registered + 20) are dropped. Elections before 2014 reach
today's neighbourhoods only where the tile key is a current area_id: the quarters of
beldes closed in 2014 do not map, so for 2002-2011 "kır" is the villages alone and the
kasaba / kırsal belde columns stay empty.

usage: secim_tek_parti.py 16
"""

import json
import polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, D, ROOT  # noqa: E402

EL = ["mv2002", "mv2007", "mv2011", "mv2015h", "mv2015k", "mv2018", "mv2023", "cb2014", "cb2018", "cb2023t1", "cb2023t2",
      "yerel_bsb_2014", "yerel_bsb_2019", "yerel_bsb_2024", "yerel_bel_2019", "yerel_bel_2024"]
PARTY = ("AK PARTİ", "RECEP TAYYİP ERDOĞAN")
cls = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0)
C, S, DI = (dict(zip(cls["area_id"], cls[c])) for c in ("kent_kir", "son_sinif", "district"))
tot = {}
for e in EL:
    f = ROOT / f"public/tiles/secim-{e}-mahalle-TR-{PLATE}.json"
    if not f.exists():
        continue
    for k, v in json.loads(f.read_text(encoding="utf-8")).items():
        if v["o"] >= v["k"] + 20 or k not in C:
            continue
        n = sum(v["v"].get(p, 0) for p in PARTY)
        for key in ((e, "kent_kir", C[k]), (e, "sinif", S[k]), (e, "ilce", f"{DI[k]}|{C[k]}")):
            t = tot.setdefault(key, [0, 0]); t[0] += n; t[1] += v["g"]
pct = lambda *k: (round(tot[k][0] / tot[k][1] * 100, 1) if k in tot and tot[k][1] else None)
els = sorted({k[0] for k in tot}, key=EL.index)
a = pl.DataFrame([dict(secim=e, kent=pct(e, "kent_kir", "kent"), kir=pct(e, "kent_kir", "kır"),
                       **{s: pct(e, "sinif", s) for s in ("merkez", "kentsel_belde", "kasaba", "kirsal_belde", "kir")}) for e in els])
a = a.with_columns((pl.col("kir") - pl.col("kent")).round(1).alias("fark"))
a.write_csv(D / f"secim_tek_parti_{PLATE}.csv")
il = sorted({k[2].split("|")[0] for k in tot if k[1] == "ilce"})
b = pl.DataFrame([dict(ilce=i, **{e: (round(pct(e, "ilce", f"{i}|kır") - pct(e, "ilce", f"{i}|kent"), 1)
                                     if pct(e, "ilce", f"{i}|kent") is not None and pct(e, "ilce", f"{i}|kır") is not None else None) for e in els}) for i in il])
b.write_csv(D / f"secim_tek_parti_{PLATE}_ilce_fark.csv")
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_width_chars(240)
print(a); print(b)
