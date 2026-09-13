"""One entry point for every fetch: three lanes, each a single session, run in parallel.

The lanes are the three sources, and they are parallel because they are different servers:

    endeksa   app.endeksa.com          mahalle demografisi
    medas     biruni.tuik.gov.tr/medas ölçümler
    secim     biruni.tuik.gov.tr/secim… seçim raporları

Inside a lane everything is sequential. That is not caution, it is measurement: two
sessions on the election application made both province reports time out, while the same
two fetched one after another took two seconds each.

Every job is resumable — a file on disk is skipped — so this may be stopped and started
again at any time, which is what makes it safe to run unattended.

Run:  uv run python scripts/cek.py            # üç şerit birden
      uv run python scripts/cek.py secim      # tek şerit
      uv run python scripts/cek.py --durum    # ne kaldı, çekmeden
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
LOG = HAM / "cek.log"

YEARS = ",".join(str(y) for y in range(2007, 2026))
PROVINCES = ROOT / "src" / "veriatlas" / "data" / "nuts_tr.csv"

CB = ["cb2023t1", "cb2023t2", "cb2018", "cb2014"]
HO = ["ho2017", "ho2010", "ho2007", "ho1988", "ho1987", "ho1982"]
MV = ["mv2023", "mv2018", "mv2015k", "mv2015h", "mv2011", "mv2007", "mv2002", "mv1999",
      "mv1995", "mv1991"]
YEREL = [f"yerel_{office}_{year}"
         for office in ("bsb", "bel", "belmec", "ilgen")
         for year in ("2024", "2019", "2014", "2009", "2004", "1999", "1994", "1989")]

_lock = threading.Lock()


def log(lane: str, message: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} [{lane}] {message}"
    with _lock:
        print(line, flush=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def run(lane: str, args: list[str]) -> None:
    """One child process, its failure logged and the lane carried on.

    A lane must not stop because one measure refused: the rest of the queue is hours of
    work and the failure is usually a year the source does not publish.
    """
    log(lane, "→ " + " ".join(args[1:]))
    try:
        result = subprocess.run(
            [PY, "-u", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=36000,
            check=False,
        )
        tail = (result.stdout or result.stderr or "").strip().splitlines()[-1:]
        log(lane, ("  " + tail[0][:120]) if tail else "  (çıktı yok)")
    except Exception as exc:  # noqa: BLE001
        log(lane, f"  HATA {str(exc)[:120]}")


def provinces() -> list[str]:
    rows = PROVINCES.read_text(encoding="utf-8").splitlines()[1:]
    return [row.split(",")[0].upper() for row in rows if row.strip()]


def lane_endeksa() -> None:
    run("endeksa", ["scripts/fetch_endeksa_demography.py"])


def lane_medas() -> None:
    run("medas", ["scripts/fetch_medas_simple.py"])
    for measure in ("cocuk-nufus-ilce", "hane-tipleri-ilce", "okuma-yazma-orani-ilce"):
        run("medas", ["scripts/fetch_medas_simple.py", measure, f"--yil={YEARS}"])
    for province in provinces():
        for measure in ("medeni", "hemsehrilik", "okuma-yazma"):
            run("medas", ["scripts/fetch_medas_marital_district.py",
                          f"--olcum={measure}", province, "--all"])
    run("medas", ["scripts/fetch_medas_neighbourhoods.py", "--all"])
    run("medas", ["scripts/fetch_medas_neighbourhoods_early.py", "--all"])


def lane_secim() -> None:
    for vote in CB + HO + MV + YEREL:
        run("secim", ["scripts/fetch_secim.py", vote])


LANES = {"endeksa": lane_endeksa, "medas": lane_medas, "secim": lane_secim}


def durum() -> None:
    subprocess.run([PY, "scripts/durum_raporu.py"], cwd=ROOT, check=False)
    print(f"durum sayfası: {ROOT / 'web' / 'durum.html'}")


def main(argv: list[str]) -> None:
    if "--durum" in argv:
        durum()
        return
    wanted = [a for a in argv if a in LANES] or list(LANES)
    log("cek", "şeritler: " + ", ".join(wanted))
    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        for lane in wanted:
            pool.submit(LANES[lane])
    log("cek", "bitti")
    durum()


if __name__ == "__main__":
    main(sys.argv[1:])
