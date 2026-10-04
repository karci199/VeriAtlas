"""Shared province parameters for the urban/rural pipeline.

PLATE  first argument ("16")
YEAR   base year, env KK_YIL (default 2024 -- the year Endeksa's snapshot equals ADNKS exactly)
D      output directory, env KK_DIR (default C:/veri-ham/analiz/kent_kir/<plate>)
NAME   province name as in the registry ("Bursa"), IL_UP ascii upper ("MANISA": ADNKS export
       file names, labels), PTT_IL Turkish upper ("MANİSA": PTT tables), SLUG ascii lower
       ("manisa": census files).
"""

import os, sys
from pathlib import Path
import polars as pl

PLATE = sys.argv[1]
YEAR = int(os.environ.get("KK_YIL", "2024"))
D = Path(os.environ.get("KK_DIR", f"C:/veri-ham/analiz/kent_kir/{PLATE}"))
D.mkdir(parents=True, exist_ok=True)
ROOT = Path("C:/veri")
_areas = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr.csv", infer_schema_length=0)
NAME = _areas.filter(pl.col("area_id") == f"TR-{PLATE}")["name_tr"][0]


def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


SLUG = fold(NAME)
IL_UP = SLUG.upper()
PTT_IL = NAME.replace("i", "İ").upper()

# 2024 local election at neighbourhood level: metropolitan mayor in the 30 büyükşehir, provincial
# council (il genel meclisi) elsewhere -- the only local ballot cast in villages there
from il_surum import SURUM  # noqa: E402  pipeline version; run_tr reruns a province whose surum.txt differs

# Village ids: geometry, Endeksa demography and the election tiles key villages of the 51
# non-metropolitan provinces by Endeksa's id = MEDAS code + 2,000,000 (checked: Afyon 421/421,
# Kastamonu 1054/1054); the warehouse (population, registry) uses the MEDAS code. wh() maps any
# id to the warehouse id, geo_code() gives the Endeksa code of a warehouse id.
_VIL = set(pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0)
           .filter(pl.col("parent_id").str.starts_with(f"TR-{PLATE}-"))["area_id"])


def wh(aid):
    # only subtract when the *result* is a real village id -- a genuine neighbourhood code
    # can also exceed 2,000,000 (a post-2013 split carries a year-prefixed code, e.g.
    # Yıldırım Sakarya = 2018099), and must not be mistaken for a shifted village
    did, code = aid.rsplit("-", 1)
    if code.isdigit() and int(code) >= 2000000:
        alt = f"{did}-{int(code) - 2000000}"
        if alt in _VIL:
            return alt
    return aid


def geo_code(aid):
    code = aid.rsplit("-", 1)[1]
    return str(int(code) + 2000000) if aid in _VIL else code


LOCAL24 = "yerel_bsb_2024" if (ROOT / f"public/tiles/secim-yerel_bsb_2024-mahalle-TR-{PLATE}.json").exists() else "yerel_ilgen_2024"
