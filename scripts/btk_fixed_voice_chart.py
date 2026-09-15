"""Render the fixed-voice technology page from the extracted CSV."""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
TEMPLATE = pathlib.Path(__file__).with_name("btk_sabit_ses_template.html")
DEST = ROOT / "web" / "btk-sabit-ses.html"

NUMERIC = ("tt_pstn", "tt_isdn", "tt_ankesor", "sth_pstn", "sth_isdn", "sth_voip",
           "tt_toplam", "sth_toplam", "bilesen_toplami", "toplam")


def load():
    with open(RAW / "sabit_ses_teknoloji.csv", encoding="utf-8") as fh:
        rows = []
        for r in csv.DictReader(fh):
            row = {"d": r["donem"], "src": r["kaynak_rapor"], "note": r["not"]}
            for key in NUMERIC:
                row[key] = int(r[key]) if r[key] else None
            # Difference between the printed total and the cells beside it, so the
            # page can flag the quarters where the report does not add up.
            row["gap"] = (None if row["bilesen_toplami"] is None
                          else row["toplam"] - row["bilesen_toplami"])
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
