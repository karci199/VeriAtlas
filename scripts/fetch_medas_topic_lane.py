"""One lane: scan each MEDAS topic that has no survey yet, then pull them all.

Run from the durum-ozeti-plan worktree:
    uv run python scripts/fetch_medas_topic_lane.py LOG "prefix=Topic" ...
"""

import os
import re
import subprocess
import sys
from pathlib import Path

log_path = Path(sys.argv[1])
pairs = sys.argv[2:]
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
python = sys.executable

with log_path.open("a", encoding="utf-8") as log:
    for pair in pairs:
        topic = pair.split("=", 1)[1]
        slug = re.sub(r"[^A-Za-z0-9]+", "-", topic).strip("-").lower()
        if not Path("raw/medas/kesif", slug + ".json").exists():
            log.write("== TARAMA " + topic + "\n")
            log.flush()
            subprocess.run(
                [python, "-u", "scripts/scan_medas_topic.py", topic],
                check=False,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
            )
    log.write("== CEKIM\n")
    log.flush()
    subprocess.run(
        [python, "-u", "scripts/fetch_medas_topic.py", *pairs],
        check=False,
        stdout=log,
        stderr=subprocess.STDOUT,
        env=env,
    )
    log.write("== KOL BITTI\n")
