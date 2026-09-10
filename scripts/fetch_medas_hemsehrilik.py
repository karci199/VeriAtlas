"""Where a district's residents are registered — hemşehrilik, at district level.

ADNKS publishes, for every district, how many of its residents are registered to each of
the 81 provinces. That is 81 indicators per district and it exists at district level; the
province-level twin ("İkamet edilen ile göre…") is a different measure and coarser.

The label is carried here rather than passed on the command line: a Turkish string handed
through git-bash argv arrives re-encoded and the measure is silently not found, which
shows up only as an empty year list. Same reason as scan_medas_nufus.py.

Run:  uv run python scripts/fetch_medas_hemsehrilik.py [--yil 2024 ...]
"""

import os
import pathlib
import runpy
import sys

OLCUM = "İkamet edilen ilçeye göre nüfusa kayıtlı olunan il"

#: No breakdown. The measure already *is* the eighty-one provinces: the topic scan reports
#: it as 81 indicators at district level on its own. Ticking a breakdown on top of that
#: leaves "gösterge adedi: 0" -- which reads as "this measure has nothing", and is how the
#: earlier run was written off.


#: 81 indicators x 973 districts is 78.813 for one year and MEDAS refuses anything over
#: 50.000. The provinces are therefore ticked in two halves -- 41 and 40 -- which is
#: 39.893 and 38.920, and the two files together are the year.
def slice_file(number: int) -> str:
    import csv

    root = pathlib.Path(__file__).resolve().parents[1]
    names = sorted(
        row["name_tr"]
        for row in csv.DictReader(
            (root / "src" / "veriatlas" / "data" / "areas_tr.csv").open(
                encoding="utf-8"
            )
        )
        if row.get("area_level") == "province"
    )
    part = names[:41] if number == 1 else names[41:]
    path = root / f".medas-il-dilim{number}.txt"
    path.write_text(chr(10).join(part), encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    extra: list[str] = []
    stem = "hemsehrilik"
    number = 0
    if "--il-no" in sys.argv:
        # One province's districts, every year at once. The measure is 81 indicators and
        # the country is 973 districts -- 78.813 for a single year, over MEDAS's cap of
        # 50.000, so the country cannot be asked for at all. A province is a few thousand.
        at = sys.argv.index("--il-no")
        number = int(sys.argv[at + 1])
        # Left in place, the bare number is read as a year further down and a second,
        # meaningless file is written beside the real one.
        del sys.argv[at : at + 2]
        # İstanbul is the one province the whole series does not fit for: 81 indicators
        # x 39 districts x 19 years is 60.021, over MEDAS's cap of 50.000, and the report
        # comes back with no level selected at all. `--tek-yil` asks for it a year at a
        # time instead, which is 3.159.
        extra = [] if "--tek-yil" in sys.argv else ["--tum-yillar"]
        if "--tek-yil" in sys.argv:
            sys.argv.remove("--tek-yil")
        os.environ["VERIATLAS_IL_NO"] = str(number)
        stem = f"hemsehrilik-il{number:02d}"
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
