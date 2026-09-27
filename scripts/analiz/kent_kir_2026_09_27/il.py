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
