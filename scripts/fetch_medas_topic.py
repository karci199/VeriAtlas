"""Pull every measure of one or more MEDAS topics, from their scan_medas_topic.py survey.

    uv run python scripts/fetch_medas_topic.py "saglik=Sağlık İstatistikleri" ...

Each `prefix=topic` reads raw/medas/kesif/<slug>.json (written by scan_medas_topic.py) and
queues every measure as `<prefix>-NN` through fetch_medas_simple: all breakdowns opened,
country + province, or country only when the survey offers nothing below Türkiye. The
fetcher slices a measure over the 50.000-cell limit by itself.

A measure whose label is contained in an earlier item of the same topic would be clicked
wrongly (the fetcher takes the first item containing the label); such measures are
skipped and named, not guessed. Every file is mirrored to C:/veri-ham/medas/basit.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import fetch_medas_simple as simple

KESIF = simple.OUT.parent / "kesif"
MIRROR = Path("C:/veri-ham/medas/basit")


def slug(topic: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", topic).strip("-").lower()


new = []
for arg in sys.argv[1:]:
    prefix, topic = arg.split("=", 1)
    survey = KESIF / (slug(topic) + ".json")
    rows = json.loads(survey.read_text(encoding="utf-8"))
    labels = [row["measure"] for row in rows]
    for index, row in enumerate(rows):
        label = row["measure"]
        name = f"{prefix}-{index + 1:02d}"
        # OLCULER=3,5: only these measure numbers (the rest were fetched or are surveys).
        only = os.environ.get("OLCULER")
        if only and str(index + 1) not in only.split(","):
            continue
        if not row.get("years") and not row.get("breakdowns"):
            print("ATLANDI (yil yok):", name, label)
            continue
        earlier = [
            o for o in labels[:index] if " ".join(label.split()) in " ".join(o.split())
        ]
        # The fetcher now prefers an exact name, so only a label that is not a whole item
        # name of its own is still ambiguous; OLCULER naming it explicitly takes it.
        if earlier and not only:
            print("ATLANDI (belirsiz ad):", name, label, "<-", earlier[0])
            continue
        levels = row.get("levels") or []
        province = any("İl" in lv or "BBS3" in lv for lv in levels)
        areas = 82 if province else 1
        # Too wide for one year with every breakdown open (ceza infaz: ~650 indicators x
        # 82 areas), or the survey could not count it: one breakdown per query instead,
        # each a marginal table that fits and is sliced over years by the fetcher.
        wide = row["breakdowns"] and (
            row["indicators"] == 0
            or row["indicators"] * areas > 45000
            # KIRILIM_HEPSI=1: every measure one breakdown per query — the way to reach
            # breakdowns that could not be crossed with the others ("CAPRAZ ALINAMAYAN").
            or bool(os.environ.get("KIRILIM_HEPSI"))
        )
        if wide and not os.environ.get("KIRILIM_KIRILIM"):
            # Postponed by the user (2026-09-13): see docs/yol-haritasi.md. Run with
            # KIRILIM_KIRILIM=1 to take these one breakdown per query.
            print(
                "ERTELENDI (genis olcu):",
                name,
                label,
                "|",
                row["indicators"],
                "gosterge",
            )
            continue
        parts = (
            [(f"{name}-k{j + 1:02d}", b) for j, b in enumerate(row["breakdowns"])]
            if wide
            else [(name, bool(row["breakdowns"]))]
        )
        # Print media stops at İBBS2: without this it came down as Türkiye only.
        region = not province and any("BBS2" in lv for lv in levels)
        for part_name, breakdowns in parts:
            if region:
                simple.NUTS2_LOWEST.add(part_name)
            elif not province:
                simple.COUNTRY_ONLY.add(part_name)
            new.append((part_name, topic, label, breakdowns))
        print(
            name,
            "|",
            label[:70],
            "|",
            row["indicators"],
            "gosterge |",
            levels[-1:] or "-",
            "|",
            len(row["years"]),
            "yil",
            "| kirilim kirilim: " + str(len(parts)) if wide else "",
        )

# One named breakdown must tick exactly that row: the fetcher's substring test would tick
# "Yaş grubu" and "Suç işlediği andaki yaşı" when asked for "Yaş".
import inspect

source = inspect.getsource(simple.build_query)
patched = source.replace(
    "wanted.lower() in text.lower()", "wanted.lower() == text.lower()"
)
if patched == source:
    raise SystemExit("build_query kirilim yamasi tutmadi")
exec(patched, simple.__dict__)  # noqa: S102

simple.MEASURES.extend(new)
sys.argv = [sys.argv[0], *[name for name, *_ in new]]
simple.main()
for hint, breakdown in sorted(set(simple.SKIPPED_BREAKDOWNS)):
    print("CAPRAZ ALINAMAYAN KIRILIM:", hint, "|", breakdown)

MIRROR.mkdir(parents=True, exist_ok=True)
copied = 0
# With RAW pointing at C:/veri-ham the output *is* the mirror; copying a file onto
# itself fails on Windows with "in use" and ended the run with a traceback.
same = simple.OUT.resolve() == MIRROR.resolve()
for name, *_ in [] if same else new:
    for path in sorted(simple.OUT.glob("nufus-" + name + "-*.csv")):
        shutil.copy2(path, MIRROR / path.name)
        copied += 1
print("aynalandi:", copied, "dosya")
