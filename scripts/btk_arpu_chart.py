"""Render the per-operator ARPU page from the extracted CSV."""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
TEMPLATE = pathlib.Path(__file__).with_name("btk_arpu_template.html")
DEST = ROOT / "web" / "btk-arpu.html"

NUMERIC = ("tl", "eur", "usd", "tl_reel", "eur_reel", "usd_reel")


def load():
    with open(RAW / "mobil_arpu_isletmeci.csv", encoding="utf-8") as fh:
        rows = []
        for r in csv.DictReader(fh):
            row = {"donem": r["donem"], "isletmeci": r["isletmeci"], "tip": r["tip"]}
            for key in NUMERIC:
                row[key] = float(r[key]) if r[key] else None
            rows.append(row)
    return rows


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(load(), ensure_ascii=False))
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(html, encoding="utf-8")
    print(f"{DEST} yazildi")


if __name__ == "__main__":
    main()
