"""Render the fixed-broadband page from the extracted CSVs."""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
TEMPLATE = pathlib.Path(__file__).with_name("btk_genisbant_template.html")
DEST = ROOT / "web" / "btk-genisbant.html"

NUMERIC = ("xdsl", "kablo", "ftth", "fttb", "fiber", "kablosuz_sabit", "diger",
           "mobil_bilgisayar", "mobil_cep", "toplam", "sabit_toplam")


def load_subscribers():
    with open(RAW / "sabit_genisbant.csv", encoding="utf-8") as fh:
        rows = []
        for r in csv.DictReader(fh):
            row = {"d": r["donem"], "src": r["kaynak_rapor"]}
            for key in NUMERIC:
                row[key] = int(r[key]) if r[key] else None
            rows.append(row)
    return rows


def load_arpu():
    with open(RAW / "sabit_genisbant_arpu.csv", encoding="utf-8") as fh:
        return [{
            "yil": int(r["yil"]),
            "aylik_tl": float(r["aylik_tl"]),
            "aylik_usd": float(r["aylik_usd"]),
            "aylik_tl_2025": float(r["aylik_tl_2025"]),
        } for r in csv.DictReader(fh)]


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(load_subscribers(), ensure_ascii=False))
    html = html.replace("__ARPU__", json.dumps(load_arpu(), ensure_ascii=False))
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(html, encoding="utf-8")
    print(f"{DEST} yazildi")


if __name__ == "__main__":
    main()
