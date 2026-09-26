r"""Crop production at district level, every measure, every province, 2004 onwards (MEDAS).

The long job of docs/uzun-cekimler-plani.md. MEDAS will not take the whole country at
district level in one query (fruit alone is 405 indicators x 973 districts = 394.000 cells
for a single year, against a cap of 50.000), and the district fetcher can pick one
province or all of them, nothing in between. So the unit of work is one province and a
group of years, sized so that indicators x districts x years stays under the cap:

- the first group size assumes 20 districts; a query MEDAS would refuse is caught by the
  fetcher before the report ("LIMIT_ASILDI") and the group is halved;
- a province that needed a smaller group keeps it for the rest of that measure;
- newest years first, so a job cut short still holds the recent ones.

It survives being stopped: every file is named by measure, province and year range and
an existing, valid file is skipped, so the same command resumes. State and a pulse
(time and current query) are written to C:\veri-ham\medas\uzun\.

Each query is a fresh fetcher process (a fresh browser), because a MEDAS session slows
down the longer it lives. A downloaded file is checked: at least two district columns and
every requested year present; otherwise it is deleted and the query retried, then named in
the log and skipped. It waits while another MEDAS district fetch is running: two sessions
against MEDAS time each other out.

Start detached from C:\veri (so a closed chat or a removed worktree does not end it):
    powershell Start-Process -WindowStyle Hidden .venv\Scripts\python.exe
        -ArgumentList '-u','scripts\uzun_bitkisel_ilce.py'
        -RedirectStandardOutput C:\veri-ham\medas\uzun\bitkisel-ilce.log
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAW = Path(os.environ.get("VERIATLAS_RAW") or "C:/veri-ham")
OUT = RAW / "medas" / "ilce"
WORK = RAW / "medas" / "uzun"
STATE = WORK / "bitkisel-ilce-durum.json"
PULSE = WORK / "bitkisel-ilce-nabiz.txt"
SURVEY = RAW / "medas" / "kesif" / "bitkisel-retim-statistikleri.json"

#: (file key, measure label as MEDAS lists it), in the order they are fetched.
MEASURES = (
    ("meyve", "Meyveler içecek ve baharat bitkileri"),
    ("ortu-meyve", "Örtüaltı meyveler"),
    ("sebze", "Sebzeler"),
    ("ortu-sebze", "Örtüaltı sebzeler"),
    ("tahil", "Tahıllar ve diğer bitkisel ürünler"),
    ("kuru-sulu", "(Kuru / Sulu) - (1. Ekiliş / 2. Ekiliş) ürünleri"),
    ("sus", "Süs bitkileri"),
    ("ortu-sus", "Örtüaltı süs bitkileri"),
)
PROVINCES = 81
CELLS = 45000
GUESS_DISTRICTS = 20
DISTRICT_COLUMN = re.compile(r"\([^|]*\)-\d+")


def log(*parts) -> None:
    print(dt.datetime.now().astimezone().strftime("%H:%M:%S"), *parts, flush=True)


def other_fetch_running() -> bool:
    """Another fetch_medas_districts.py process (not a child of this job) is alive."""
    out = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
                "'*fetch_medas_districts*' -and $_.CommandLine -notlike '*Get-CimInstance*' "
                "}).Count"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return out not in ("", "0")


def valid(path: Path, years: list[int]) -> bool:
    if not path.exists() or path.stat().st_size < 500:
        return False
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    head = "\n".join(text.splitlines()[:3])
    if len(DISTRICT_COLUMN.findall(head)) < 2:
        return False
    found = {int(y) for y in re.findall(r"\|((?:19|20)\d\d)\|", text)}
    return set(years) <= found


def run(key: str, label: str, province: int, years: list[int]) -> str:
    """One query. Returns "ok", "limit" or "fail"."""
    stem = f"bitkisel-{key}-il{province:02d}"
    target = OUT / f"{stem}-ilce-kirilim-{min(years)}-{max(years)}.csv"
    if valid(target, years):
        return "ok"
    target.unlink(missing_ok=True)
    env = dict(
        os.environ,
        VERIATLAS_IL_NO=str(province),
        VERIATLAS_YILLAR=",".join(map(str, years)),
        PYTHONIOENCODING="utf-8",
        VERIATLAS_RAW=str(RAW),
    )
    command = [
        sys.executable,
        "-u",
        "scripts/fetch_medas_districts.py",
        "--konu",
        "bitkisel",
        "--olcum",
        label,
        "--kirilim",
        "--kirilim-adi",
        "*",
        "--ad",
        stem,
    ]
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1500,
            check=False,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        output = "ZAMAN_ASIMI"
    chosen = re.search(r"il: (.+)", output)
    note = chosen.group(1).strip() if chosen else "?"
    if "LIMIT_ASILDI" in output:
        return "limit"
    if valid(target, years):
        log("   indi", target.name, note, target.stat().st_size, "bayt")
        return "ok"
    target.unlink(missing_ok=True)
    log("   BASARISIZ", target.name, note, "|", " ".join(output.split())[-220:])
    return "fail"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    survey = {
        row["measure"]: row for row in json.loads(SURVEY.read_text(encoding="utf-8"))
    }
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    failed: list[str] = []
    while other_fetch_running():
        log("baska bir MEDAS ilce cekimi suruyor, bekleniyor")
        time.sleep(120)
    for key, label in MEASURES:
        row = survey[label]
        indicators = row["indicators"]
        years = sorted(row["years"], reverse=True)
        first = max(1, min(len(years), CELLS // (indicators * GUESS_DISTRICTS)))
        log("==", key, indicators, "gosterge,", len(years), "yil, ilk grup", first)
        for province in range(1, PROVINCES + 1):
            size = state.get(f"{key}:{province}", first)
            left = list(years)
            while left:
                group = left[:size]
                PULSE.write_text(
                    f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')} {key} il{province:02d} "
                    f"{min(group)}-{max(group)}\n",
                    encoding="utf-8",
                )
                outcome = run(key, label, province, group)
                if outcome == "limit" and size > 1:
                    size = max(1, size // 2)
                    state[f"{key}:{province}"] = size
                    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
                    log("   sinir asildi, grup", size, "yila indi:", key, province)
                    continue
                if outcome == "fail":
                    outcome = run(key, label, province, group)
                if outcome != "ok":
                    failed.append(f"{key} il{province:02d} {min(group)}-{max(group)}")
                left = left[len(group) :]
                time.sleep(3)
        log("==", key, "bitti; basarisiz:", len(failed))
    log("BITTI. basarisiz sorgular:", len(failed))
    for item in failed:
        log("   ", item)


if __name__ == "__main__":
    main()
