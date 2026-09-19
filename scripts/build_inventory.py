r"""Write `docs/envanter.md` from the warehouse, so the inventory cannot drift from it.

The hand-kept lists in `kaynak-envanteri.md` and `acik-isler.md` record what someone
decided at the time; they go stale quietly, and a stale list costs a whole session. It
happened three times on 2026-09-19 alone — AFAD earthquakes, GSB sport and Eurostat were
each proposed as "new" work while already loaded.

This file is generated instead: every indicator that has rows in `public/fact.parquet`,
with its level, period span and row count, grouped by topic. If an indicator is not in
here, it is not in the store — that is the whole contract.

Run:  uv run python scripts/build_inventory.py
Out:  docs/envanter.md
"""

from __future__ import annotations

import datetime as dt
import sys
import tomllib
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

DICTIONARY = Path("src/veriatlas/data/indicators.toml")
OUT = Path("docs/envanter.md")
#: Level names as the reader knows them, coarsest last so a span reads "il, ilçe".
LEVELS = {
    "country": "TR",
    "nuts1": "İBBS-1",
    "nuts2": "İBBS-2",
    "region": "bölge",
    "province": "il",
    "district": "ilçe",
    "neighbourhood": "mahalle",
    "village": "köy",
}


def main() -> None:
    fact = pl.scan_parquet(PUBLIC / "fact.parquet")
    summary = (
        fact.group_by("indicator_id")
        .agg(
            pl.len().alias("rows"),
            pl.col("period_start").min().alias("first"),
            pl.col("period_start").max().alias("last"),
            pl.col("area_level").unique().alias("levels"),
            pl.col("source_id").unique().alias("sources"),
        )
        .collect()
    )
    declared = tomllib.loads(DICTIONARY.read_text(encoding="utf-8"))["indicator"]

    by_topic: dict[str, list[dict]] = {}
    for row in summary.to_dicts():
        body = declared.get(row["indicator_id"], {})
        by_topic.setdefault(body.get("topic", "?"), []).append(row | {"body": body})

    lines = [
        f"# Envanter — depodaki {summary.height} gösterge",
        "",
        "**Bu dosya elle yazılmaz.** `scripts/build_inventory.py` warehouse'tan üretir;",
        "burada olmayan gösterge depoda yok demektir. Yeni kaynak önermeden önce buraya",
        "bakılır — 2026-09-19'da AFAD depremi, GSB sporu ve Eurostat üçü de 'yeni iş' diye",
        "önerildi, üçü de zaten yüklüydü.",
        "",
        f"Üretim: {dt.date.today():%Y-%m-%d} · {summary['rows'].sum():,} satır".replace(
            ",", "."
        ),
        "",
    ]
    for topic in sorted(by_topic, key=lambda t: -len(by_topic[t])):
        items = sorted(by_topic[topic], key=lambda r: r["indicator_id"])
        lines += [
            f"## {topic} ({len(items)})",
            "",
            "| Gösterge | Ad | Düzey | Dönem | Satır | Kaynak |",
            "|---|---|---|---|---|---|",
        ]
        for item in items:
            levels = ", ".join(
                LEVELS.get(level, level) for level in LEVELS if level in item["levels"]
            )
            span = f"{item['first']:%Y}-{item['last']:%Y}"
            label = item["body"].get("label_tr", "—")
            source = ", ".join(sorted(item["sources"]))
            lines.append(
                f"| `{item['indicator_id']}` | {label} | {levels} | {span} | "
                f"{item['rows']:,} | {source} |".replace(",", ".")
            )
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT, summary.height, "gösterge")


if __name__ == "__main__":
    main()
