"""Run the census queue again and again until a pass brings nothing new.

TÜİK's census server drops the session now and then ("oturum acilamadi", connection reset).
The queue gives a step five tries and then moves on, so one pass leaves holes: on 2 Ekim a
pass over the village-age step ended at 34 of 81 provinces for 2000. The files already on
disk are skipped, so another pass costs only the missing ones. This repeats the pass, with a
pause so the server can recover, and stops after two passes in a row that add no file.

Run:  python scripts/sayim_dongu.py [--bekle <pid>]   # wait for a running queue first
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("VERIATLAS_RAW") or "C:/veri-ham") / "tuik_sayim"
PAUSE_BETWEEN = 15 * 60


def count_files() -> int:
    return sum(1 for p in OUT.glob("*/koy/*.html")) + sum(
        1 for p in OUT.glob("*/*.html")
    )


def alive(pid: int) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return str(pid) in out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bekle", type=int, help="pid of a running queue to wait for")
    args = ap.parse_args()
    while args.bekle and alive(args.bekle):
        time.sleep(60)
    empty_passes = 0
    for number in range(1, 40):
        before = count_files()
        log = OUT / f"cekim-dongu-{number:02d}.log"
        print(time.strftime("%H:%M:%S"), f"pass {number}, {before} files", flush=True)
        with log.open("w", encoding="utf-8") as handle:
            subprocess.run(
                [
                    sys.executable,
                    "-u",
                    str(ROOT / "scripts/fetch_census_districts.py"),
                    "--kuyruk",
                ],
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        added = count_files() - before
        print(time.strftime("%H:%M:%S"), f"pass {number} added {added}", flush=True)
        empty_passes = empty_passes + 1 if added == 0 else 0
        if empty_passes >= 2:
            print("two empty passes: done or blocked", flush=True)
            break
        time.sleep(PAUSE_BETWEEN)


if __name__ == "__main__":
    main()
