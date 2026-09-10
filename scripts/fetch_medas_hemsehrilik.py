"""Where a district's residents are registered — hemşehrilik, at district level.

ADNKS publishes, for every district, how many of its residents are registered to each of
the 81 provinces. That is 81 indicators per district and it exists at district level; the
province-level twin ("İkamet edilen ile göre…") is a different measure and coarser.

The label is carried here rather than passed on the command line: a Turkish string handed
through git-bash argv arrives re-encoded and the measure is silently not found, which
shows up only as an empty year list. Same reason as scan_medas_nufus.py.

Run:  uv run python scripts/fetch_medas_hemsehrilik.py [--yil 2024 ...]
"""

import runpy
import sys

OLCUM = "İkamet edilen ilçeye göre nüfusa kayıtlı olunan il"

#: The 81 provinces are not indicators of the measure until this breakdown is opened and
#: ticked — clicking the measure alone leaves "gösterge adedi: 0" and the flow then finds
#: no years, which looks exactly like a measure that publishes none.
KIRILIM = "Nüfusa Kayıtlı Olunan İl"

if __name__ == "__main__":
    sys.argv = [
        "fetch_medas_districts.py",
        "--olcum", OLCUM,
        "--kirilim",
        "--kirilim-adi", KIRILIM,
        "--ad", "hemsehrilik",
        *sys.argv[1:],
    ]
    runpy.run_path("scripts/fetch_medas_districts.py", run_name="__main__")
