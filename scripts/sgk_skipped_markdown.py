"""Write the SGK province tables the adapter leaves out as Markdown, so they stay readable.

One file per skipped topic under `docs/sgk-dislanan/`, one table per yearbook sheet:
provinces down, the printed column headings across, values as printed. The reasons
are in `SKIPPED_TOPICS` (adapters/sgk_provinces.py) and `docs/sgk.md`.

Run:  uv run python scripts/sgk_skipped_markdown.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")

from veriatlas.adapters.sgk_provinces import CELLS, SKIPPED_TOPICS, topic_of
from veriatlas.areas import load_areas

OUT = Path("docs/sgk-dislanan")


def short(header: str) -> str:
    parts = [
        p for p in header.split(" > ") if not p.lower().startswith(("tablo", "table"))
    ]
    return " / ".join(parts).replace("|", "/") or "?"


def main() -> None:
    cells = pl.read_parquet(CELLS)
    names = {
        int(r["area_id"][3:]): r["name_tr"]
        for r in load_areas().filter(pl.col("area_level") == "province").to_dicts()
    }
    titles = cells.select("title").unique()["title"].to_list()
    topic = {t: topic_of(t) for t in titles}
    cells = cells.with_columns(pl.col("title").replace_strict(topic).alias("topic"))
    OUT.mkdir(parents=True, exist_ok=True)
    for key, reason in SKIPPED_TOPICS.items():
        part = cells.filter(pl.col("topic") == key)
        lines = [f"# SGK yıllığı: depolanmayan tablo — `{key}`", "", reason, ""]
        for (year, sheet, title), table in part.group_by(
            "year", "sheet", "title", maintain_order=True
        ):
            table = table.sort("block", "row", "col")
            lines += [f"## {year} · {sheet}", "", title or "(başlıksız)", ""]
            for (block,), blk in table.group_by("block", maintain_order=True):
                cols = blk.select("col", "header").unique().sort("col")
                heads = [short(h) for h in cols["header"]]
                lines.append("| İl | " + " | ".join(heads) + " |")
                lines.append("|---" * (len(heads) + 1) + "|")
                wide = blk.pivot(
                    on="col", index="plate", values="value", aggregate_function="first"
                )
                for row in wide.sort("plate").iter_rows(named=True):
                    vals = [row.get(str(c)) for c in cols["col"]]
                    text = ["" if v is None else f"{v:g}" for v in vals]
                    lines.append(
                        f"| {names[row['plate']]} | " + " | ".join(text) + " |"
                    )
                lines.append("")
        (OUT / f"{key}.md").write_text("\n".join(lines), encoding="utf-8")
        print(key, part.height)


if __name__ == "__main__":
    main()
