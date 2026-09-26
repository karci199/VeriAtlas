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
KESIF = RAW / "medas" / "kesif"

#: (file key, measure label as MEDAS lists it), in the order they are fetched.
CROPS = (
    ("meyve", "Meyveler içecek ve baharat bitkileri"),
    ("ortu-meyve", "Örtüaltı meyveler"),
    ("sebze", "Sebzeler"),
    ("ortu-sebze", "Örtüaltı sebzeler"),
    ("tahil", "Tahıllar ve diğer bitkisel ürünler"),
    ("kuru-sulu", "(Kuru / Sulu) - (1. Ekiliş / 2. Ekiliş) ürünleri"),
    ("sus", "Süs bitkileri"),
    ("ortu-sus", "Örtüaltı süs bitkileri"),
)
#: After the crops, every measure of these topics that reaches district level, in the
#: survey's order: (fetcher topic key, file prefix, survey file).
LATER = (
    ("hayvan", "hayvan", "hayvanc-l-k-statistikleri.json"),
    ("alet", "alet", "tar-msal-alet-ve-makine-statistikleri.json"),
)
PROVINCES = 81
CELLS = 45000
GUESS_DISTRICTS = 20
#: Districts in the country, for sizing a whole-country query.
ALL_DISTRICTS = 973
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


def jobs() -> list[tuple[str, str, dict]]:
    """(fetcher topic key, file key, survey row) for every measure, in order."""
    crops = {
        r["measure"]: r
        for r in json.loads(
            (KESIF / "bitkisel-retim-statistikleri.json").read_text(encoding="utf-8")
        )
    }
    out = [("bitkisel", "bitkisel-" + key, crops[label]) for key, label in CROPS]
    for topic, prefix, name in LATER:
        rows = json.loads((KESIF / name).read_text(encoding="utf-8"))
        for number, row in enumerate(rows, start=1):
            if any("İlçe" in level for level in row.get("levels") or []):
                out.append((topic, f"{prefix}-{number:02d}", row))
    return out


def run(topic: str, key: str, row: dict, province: int, years: list[int]) -> str:
    """One query. Returns "ok", "limit" or "fail".

    A measure with no breakdown is asked without one: the fetcher reads a breakdown
    query that comes back with a single indicator as one whose ticks did not take.
    """
    label = row["measure"]
    breakdown = bool(row["breakdowns"])
    stem = f"{key}-il{province:02d}"
    middle = "-ilce-kirilim-" if breakdown else "-ilce-"
    target = OUT / f"{stem}{middle}{min(years)}-{max(years)}.csv"
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
        topic,
        "--olcum",
        label,
        *(["--kirilim", "--kirilim-adi", "*"] if breakdown else []),
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
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    failed: list[str] = []
    while other_fetch_running():
        log("baska bir MEDAS ilce cekimi suruyor, bekleniyor")
        time.sleep(120)
    for topic, key, row in jobs():
        indicators = row["indicators"]
        years = sorted(row["years"], reverse=True)
        # A narrow measure takes the whole country at once (province 0 = "HEPSİ"): one
        # indicator x 973 districts x 22 years is 21.000 cells, and asking it province by
        # province cost 81 queries where one or two do.
        whole = indicators * ALL_DISTRICTS <= CELLS
        provinces = [0] if whole else list(range(1, PROVINCES + 1))
        spread = ALL_DISTRICTS if whole else GUESS_DISTRICTS
        first = max(1, min(len(years), CELLS // (indicators * spread)))
        log(
            "==",
            key,
            indicators,
            "gosterge,",
            len(years),
            "yil, ilk grup",
            first,
            "| butun ulke tek sorguda" if whole else "| il il",
        )
        for province in provinces:
            size = state.get(f"{key}:{province}", first)
            left = list(years)
            while left:
                group = left[:size]
                PULSE.write_text(
                    f"{dt.datetime.now().astimezone().isoformat(timespec='seconds')} {key} il{province:02d} "
                    f"{min(group)}-{max(group)}\n",
                    encoding="utf-8",
                )
                outcome = run(topic, key, row, province, group)
                if outcome == "limit" and size > 1:
                    size = max(1, size // 2)
                    state[f"{key}:{province}"] = size
                    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
                    log("   sinir asildi, grup", size, "yila indi:", key, province)
                    continue
                if outcome == "fail":
                    outcome = run(topic, key, row, province, group)
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
