"""Render the call-traffic page from the extracted CSVs."""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
TEMPLATE = pathlib.Path(__file__).with_name("btk_trafik_template.html")
DEST = ROOT / "web" / "btk-trafik.html"


def load(name, label, numeric):
    """Read one CSV, renaming the period column to `d` for the page."""
    with open(RAW / name, encoding="utf-8") as fh:
        rows = []
        for r in csv.DictReader(fh):
            row = {"d": r[label]}
            for key in numeric:
                row[key] = float(r[key]) if r[key] != "" else None
            rows.append(row)
    return rows


def main():
    annual = load("trafik_yillik.csv", "yil",
                  ("mobil", "sabit", "toplam", "mobil_pay"))
    tt = load("tt_trafik_dagilimi.csv", "donem",
              ("sebeke_ici", "mobil", "sth", "uluslararasi", "rehberlik",
               "bilesen_toplami", "toplam"))
    mobile = load("mobil_trafik_isletmeci.csv", "donem",
                  ("toplam", "turkcell", "vodafone", "ttmobil",
                   "turkcell_pay", "vodafone_pay", "ttmobil_pay"))

    html = TEMPLATE.read_text(encoding="utf-8")
    for token, rows in (("__ANNUAL__", annual), ("__TT__", tt), ("__MOBILE__", mobile)):
        html = html.replace(token, json.dumps(rows, ensure_ascii=False))
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(html, encoding="utf-8")
    print(f"{DEST} yazildi")


if __name__ == "__main__":
    main()
