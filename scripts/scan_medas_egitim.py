"""Survey the ADNKS topic: which measures reach which levels, and how wide each is.

A wrapper around scan_medas_topic.py that carries the topic name in the source rather
than on the command line. MEDAS matches the topic by exact label, and a Turkish label
handed through git-bash argv arrives re-encoded in cp1254 — the select then silently
finds nothing. Source text is read as UTF-8 whatever the shell does.

Run:  uv run python scripts/scan_medas_nufus.py
"""

import pathlib
import runpy
import sys

TOPIC = "Ulusal Eğitim İstatistikleri"

if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent
    sys.argv = ["scan_medas_topic.py", TOPIC, *sys.argv[1:]]
    runpy.run_path(str(here / "scan_medas_topic.py"), run_name="__main__")
