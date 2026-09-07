"""Render the interactive mobile-market chart page from the extracted CSVs."""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
TEMPLATE = pathlib.Path(__file__).with_name("btk_mobil_template.html")
DEST = ROOT / "web" / "btk-mobil.html"


def load():
    detail = list(csv.DictReader(open(RAW / "mobil_abone_detay.csv", encoding="utf-8")))
    port = {r["donem"]: int(r["tasinan_numara"])
            for r in csv.DictReader(open(RAW / "numara_tasima.csv", encoding="utf-8"))}
    out = []
    for r in detail:
        def num(key):
            v = r.get(key, "")
            return float(v) if v else None

        row = {"d": r["donem"], "total": num("toplam"),
               "pre": num("on_odemeli_toplam"), "post": num("faturali_toplam"),
               "port": port.get(r["donem"])}
        for op in ("turkcell", "vodafone", "ttmobil"):
            row[op] = {"total": num(op + "_toplam"), "pre": num(op + "_on_odemeli"),
                       "post": num(op + "_faturali"),
                       "preShare": num(op + "_on_odemeli_pay"),
                       "postShare": num(op + "_faturali_pay")}
        out.append(row)
    return out


def load_annual():
    """Yearly series: revenue in three units, and fixed-line subscribers."""
    rev = {int(r["yil"]): r for r in
           csv.DictReader(open(RAW / "sektor_gelir_reel.csv", encoding="utf-8"))}
    fixed = {int(r["yil"]): r for r in
             csv.DictReader(open(RAW / "sabit_abone.csv", encoding="utf-8"))}
    out = []
    for y in sorted(set(rev) | set(fixed)):
        r, fx = rev.get(y, {}), fixed.get(y)
        pick = lambda k: float(r[k]) if r.get(k) else None
        out.append({
            "d": str(y),
            "big4_tl": pick("buyuk4_tl"), "big4_usd": pick("buyuk4_usd"),
            "big4_real": pick("buyuk4_tl_2025"),
            "big4_usdreal": pick("buyuk4_usd_2025"),
            "sector_tl": pick("sektor_tl"), "sector_usd": pick("sektor_usd"),
            "sector_real": pick("sektor_tl_2025"),
            "sector_usdreal": pick("sektor_usd_2025"),
            "fixed": float(fx["sabit_abone"]) if fx else None,
            "fx": pick("usd_try"),
        })
    return out


def main():
    DEST.parent.mkdir(exist_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__ANNUAL__", json.dumps(load_annual(), ensure_ascii=False))
    DEST.write_text(html.replace("__DATA__", json.dumps(load(), ensure_ascii=False)),
                    encoding="utf-8")
    print(str(DEST) + " · " + str(DEST.stat().st_size // 1024) + " KB")


if __name__ == "__main__":
    main()
