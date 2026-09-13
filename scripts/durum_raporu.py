"""A self-contained HTML page showing what is being fetched and how far it has got.

No server: the numbers are counted from disk and written *into* the page, and the page
refreshes itself on a timer. Opening it from the file system is enough — a page that
fetched a JSON beside it would be blocked by the browser's file:// rules, which is why the
data is inlined instead.

Run it once for a snapshot, or with --izle to keep rewriting it every minute:

    uv run python scripts/durum_raporu.py --izle
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
OUT = ROOT / "web" / "durum.html"


CB = ["cb2023t1", "cb2023t2", "cb2018", "cb2014"]
HO = ["ho2017", "ho2010", "ho2007", "ho1988", "ho1987", "ho1982"]
MV = [
    "mv2023",
    "mv2018",
    "mv2015k",
    "mv2015h",
    "mv2011",
    "mv2007",
    "mv2002",
    "mv1999",
    "mv1995",
    "mv1991",
]


def count(path: pathlib.Path, pattern: str = "*") -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def stems(path: pathlib.Path, pattern: str, exclude_prefix: str = "") -> int:
    """Count distinct measures, not distinct year files (each measure has one file per year)."""
    if not path.exists():
        return 0
    seen = set()
    for f in path.glob(pattern):
        if exclude_prefix and f.name.startswith(exclude_prefix):
            continue
        stem = f.stem.rsplit("-", 1)[0] if f.stem[-4:].isdigit() else f.stem
        seen.add(stem)
    return len(seen)


def provinces(path: pathlib.Path, prefix: str) -> int:
    """Count distinct il numbers among prefix-ilNN-... files."""
    if not path.exists():
        return 0
    seen = set()
    for f in path.glob(f"{prefix}-il*-*.csv"):
        parts = f.name.split("-")
        if len(parts) > 1 and parts[1].startswith("il"):
            seen.add(parts[1])
    return len(seen)


def bytes_of(path: pathlib.Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def neighbourhoods_done() -> tuple[int, int]:
    """Fetched neighbourhoods against the number the geometry says exist."""
    want = 0
    geo = ROOT / "public" / "geo" / "neighbourhoods"
    for path in geo.glob("TR-*.geojson"):
        want += path.read_text(encoding="utf-8").count('"area_level"')
    have = 0
    for path in (HAM / "endeksa" / "demografi").glob("*.json"):
        try:
            have += len(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:  # yarim yazilmis dosya: say, gecme
            print("okunamadi:", path.name, exc)
    for path in (HAM / "endeksa" / "demography").glob("*.json"):
        try:
            have += len(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:  # yarim yazilmis dosya: say, gecme
            print("okunamadi:", path.name, exc)
    return have, want


def rows() -> list[dict]:
    dem_have, dem_want = neighbourhoods_done()
    medas = HAM / "medas"
    secim = HAM / "secim"
    out = [
        {
            "ad": "Endeksa mahalle demografisi",
            "bitti": count(HAM / "endeksa" / "demography", "TR-*.json"),
            "hedef": 973,
            "birim": "ilçe dosyası",
            "not": f"{dem_have:,} / {dem_want:,} mahalle",
        },
        {
            "ad": "MEDAS ilçe ölçümleri",
            "bitti": stems(medas / "ilce", "*.csv", exclude_prefix="hemsehrilik-"),
            "hedef": 60,
            "birim": "dosya",
            "not": "bağımlılık, çocuk nüfus, hane tipleri…",
        },
        {
            "ad": "MEDAS hemşehrilik (il il)",
            "bitti": provinces(medas / "ilce", "hemsehrilik"),
            "hedef": 81,
            "birim": "il",
            "not": "ikamet edilen ilçeye göre nüfusa kayıtlı il",
        },
        {
            "ad": "MEDAS okuma-yazma (il il)",
            "bitti": count(medas / "egitim", "*.csv"),
            "hedef": 81,
            "birim": "il",
            "not": "cinsiyet × yaş grubu",
        },
        {
            "ad": "MEDAS medeni durum (il il)",
            "bitti": count(medas / "medeni", "*.csv"),
            "hedef": 81,
            "birim": "il",
            "not": "2008-2025",
        },
        {
            "ad": "Seçim: cumhurbaşkanlığı",
            "bitti": sum(count(secim / v, "*.html") for v in CB),
            "hedef": 4 * 81,
            "birim": "rapor",
            "not": "2023 iki tur, 2018, 2014 · il başına",
        },
        {
            "ad": "Seçim: halkoylaması",
            "bitti": sum(count(secim / v, "*.html") for v in HO),
            "hedef": 3051,  # gercek yil basina alan toplami, sabit 950 tahmini degil
            "birim": "rapor",
            "not": "2017-1982 · ilçe başına",
        },
        {
            "ad": "Seçim: milletvekili",
            "bitti": sum(count(secim / v, "*.html") for v in MV),
            "hedef": 9422,  # gercek yil basina ilce toplami, sabit 973 tahmini degil
            "birim": "rapor",
            "not": "2023-1991 · ilçe başına",
        },
        {
            "ad": "Seçim: yerel",
            "bitti": sum(count(p, "*.html") for p in secim.glob("yerel_*")),
            "hedef": 1969,  # gercek ofis/yil toplami (bsb ve 2014+ ilgen kucuk kapsamli)
            "birim": "rapor",
            "not": "4 ofis × 8 yıl · il başına",
        },
    ]
    for row in out:
        row["oran"] = (
            min(100, round(100 * row["bitti"] / row["hedef"])) if row["hedef"] else 0
        )
    return out


def log_tail(path: pathlib.Path, n: int = 6) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


def html() -> str:
    data = rows()
    total_mb = bytes_of(HAM) / 1e6
    now = (
        datetime.datetime.now(tz=datetime.UTC)
        .astimezone()
        .strftime("%d.%m.%Y %H:%M:%S")
    )
    logs = {
        "Endeksa": log_tail(HAM / "endeksa" / "demografi.log"),
        "Seçim": log_tail(HAM / "secim" / "cekim.log"),
        # The MEDAS scripts each print their own progress; the queue's own log is the one
        # that shows where the lane is.
        "MEDAS": log_tail(HAM / "medas_kuyruk.log") or log_tail(HAM / "medas" / "cekim.log"),
    }
    bars = "\n".join(
        f"""<tr><td class="ad">{r["ad"]}<small>{r["not"]}</small></td>
        <td class="bar"><div><span style="width:{r["oran"]}%"></span></div></td>
        <td class="say">{r["bitti"]:,} / {r["hedef"]:,}<small>{r["birim"]}</small></td>
        <td class="pct">%{r["oran"]}</td></tr>"""
        for r in data
    )
    log_html = "\n".join(
        f"<section><h3>{name}</h3><pre>{'<br>'.join(lines) or 'kayıt yok'}</pre></section>"
        for name, lines in logs.items()
    )
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<title>VeriAtlas — çekim durumu</title>
<style>
 body {{ margin:0; background:#121315; color:#e9eaee; font:14px/1.5 "Segoe UI",system-ui,sans-serif; }}
 header {{ padding:16px 22px; border-bottom:1px solid #2a2d33; display:flex; justify-content:space-between; align-items:baseline; }}
 h1 {{ margin:0; font-size:18px; }} .zaman {{ color:#8b919c; font-size:12.5px; }}
 main {{ padding:18px 22px; max-width:1000px; }}
 table {{ width:100%; border-collapse:collapse; }}
 td {{ padding:9px 8px; border-bottom:1px solid #24272d; vertical-align:middle; }}
 .ad {{ width:38%; }} .ad small {{ display:block; color:#8b919c; font-size:11.5px; }}
 .bar div {{ background:#24272d; border-radius:6px; height:10px; overflow:hidden; }}
 .bar span {{ display:block; height:100%; background:linear-gradient(90deg,#4f8ff7,#4caf6e); }}
 .say {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
 .say small {{ display:block; color:#8b919c; font-size:11px; }}
 .pct {{ text-align:right; width:56px; font-weight:600; }}
 section {{ margin-top:18px; }} h3 {{ font-size:13px; color:#8b919c; margin:0 0 6px; text-transform:uppercase; letter-spacing:.5px; }}
 pre {{ background:#0f1012; border:1px solid #24272d; border-radius:8px; padding:10px 12px; font-size:12px; color:#b9bec7; overflow-x:auto; margin:0; }}
</style></head><body>
<header><h1>VeriAtlas — çekim durumu</h1>
<div class="zaman">{now} · ham depo {total_mb:,.0f} MB · sayfa dakikada bir yenilenir</div></header>
<main><table>{bars}</table>{log_html}</main></body></html>"""


def main(argv: list[str]) -> None:
    watch = "--izle" in argv
    while True:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(html(), encoding="utf-8")
        print(f"yazildi: {OUT}")
        if not watch:
            return
        time.sleep(60)


if __name__ == "__main__":
    main(sys.argv[1:])
