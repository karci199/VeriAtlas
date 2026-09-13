"""Wikipedia's merkez / kırsal split for a province's districts, from the navbox."""

import json
import pathlib
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

API = "https://tr.wikipedia.org/w/api.php"
UA = {"User-Agent": "VeriAtlas/1.0 (research; karci199@gmail.com)"}
ILCE = [
    "Akyurt",
    "Altındağ",
    "Ayaş",
    "Balâ",
    "Beypazarı",
    "Çamlıdere",
    "Çankaya",
    "Çubuk",
    "Elmadağ",
    "Etimesgut",
    "Evren",
    "Gölbaşı",
    "Güdül",
    "Haymana",
    "Kahramankazan",
    "Kalecik",
    "Keçiören",
    "Kızılcahamam",
    "Mamak",
    "Nallıhan",
    "Polatlı",
    "Pursaklar",
    "Sincan",
    "Şereflikoçhisar",
    "Yenimahalle",
]


def wikitext(client, title):
    r = client.get(
        API,
        params={"action": "parse", "page": title, "prop": "wikitext", "format": "json"},
    ).json()
    return None if "error" in r else r["parse"]["wikitext"]["*"]


def gruplar(text):
    """{group label: [names]} — the navbox writes them as grupN / listeN pairs."""
    out = {}
    for n in range(1, 8):
        g = re.search(rf"\|\s*grup{n}\s*=\s*(.+)", text)
        l = re.search(
            rf"\|\s*liste{n}\s*=(.*?)(?=\n\s*\|\s*(?:grup|liste)\d|\n\}}\}})",
            text,
            re.DOTALL,
        )
        if not g or not l:
            continue
        adlar = [
            m.group(2) or m.group(1)
            for m in re.finditer(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]", l.group(1))
        ]
        out[g.group(1).strip()] = [a.split(",")[0].strip() for a in adlar]
    return out


with httpx.Client(headers=UA, timeout=60) as c:
    sonuc = {}
    for ilce in ILCE:
        for title in (
            f"Şablon:{ilce} mahalleleri",
            f"Şablon:{ilce} mahalleleri ve semtleri",
        ):
            t = wikitext(c, title)
            if t:
                break
        if not t:
            print(f"{ilce:16} sablon yok")
            continue
        g = gruplar(t)
        # Every group is kept, not just "Merkez" and "Kırsal": Gölbaşı writes four
        # more -- "İncek Semti", "Karagedik Semti" and so on -- and dropping them left
        # 17 of its mahalles silently counted as urban.
        sonuc[ilce] = g
        ozet = "  ".join(f"{k}:{len(v)}" for k, v in g.items())
        print(f"{ilce:16} {ozet}")
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "mahalle-ankara.json")
    out.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("yazildi:", out)
