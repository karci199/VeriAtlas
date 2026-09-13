"""Where a district's residents live registered -- the reverse of hemşehrilik, at district level.

This is the mirror of fetch_medas_hemsehrilik.py: that one asks "of this district's
residents, which province are they registered to"; this one asks "of the people
registered to this district, which province do they actually live in". Same shape --
81 indicators (one per residence province), already open without ticking a breakdown --
same 50.000-cell cap forcing a province-by-province split.

Run:  uv run python scripts/fetch_medas_hemsehrilik_ters.py --il-no 1 [--tek-yil]
"""

import os
import runpy
import sys

OLCUM = "Nüfusa kayıtlı olunan ilçeye göre ikamet edilen il"

if __name__ == "__main__":
    extra: list[str] = []
    stem = "kayitliilce"
    number = 0
    if "--il-no" in sys.argv:
        at = sys.argv.index("--il-no")
        number = int(sys.argv[at + 1])
        del sys.argv[at : at + 2]
        extra = [] if "--tek-yil" in sys.argv else ["--tum-yillar"]
        if "--tek-yil" in sys.argv:
            sys.argv.remove("--tek-yil")
        os.environ["VERIATLAS_IL_NO"] = str(number)
        stem = f"kayitliilce-il{number:02d}"
    sys.argv = [
        "fetch_medas_districts.py",
        "--olcum",
        OLCUM,
        "--kirilim",
        "--kirilim-adi",
        "*",
        "--ad",
        stem,
        *extra,
        *sys.argv[1:],
    ]
    runpy.run_path("scripts/fetch_medas_districts.py", run_name="__main__")
