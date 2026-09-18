r"""Çiğ köfte chains: Oses, Ziyafet and Komagene branch lists, from each brand's own site.

Çiğ köfte has no registry. TESK counts tradesmen, TOBB counts companies, neither tells a
kebab shop from a hairdresser, and the business directories undercount (see the bulurum
note in `docs/acik-isler.md`). What does exist is that every chain publishes its own branch
list to sell franchises — so the chains are countable even though the trade is not.

Three brands, three protocols, none of them guessed:

* **Oses** — the whole country sits inline in one page as `gMaps.locations = [...]`, with
  district, province and coordinate per branch. One request, 1.670 branches.
* **Ziyafet** — the dealer map is a **Google My Maps** embed, and Google's robots.txt
  explicitly allows `/maps/d/`, so the brand's own map exports as KML with `forcekml=1`.
  459 placemarks, coordinate and phone, no district: the adapter places them by point.
* **Komagene** — an SPA talking to `gateway.komagene.com.tr`. Two endpoints, read off the
  page's own XHR after selecting a province and pressing "ŞUBELERİ GETİR":
  `b2c/site/getwebportalilceler` {"IlId": n} and `b2c/site/getsubebilgileri`
  {"IlceId": "n"}. Both work without a browser once the ids are known, and the ids are the
  brand's own — `IlId` 164 is Adana — so the province list below was read off the select.

Every brand's own count is written down as the source states it, because the numbers that
circulate for this trade are marketing: an AI summary quoted to us said Komagene "~3.050"
and Ziyafet "~700", while Ziyafet's own page says 455 dealers in 57 provinces as of
August 2026.

Run:  uv run python scripts/fetch_cigkofte.py
Out:  C:\veri-ham\cigkofte\<brand>_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path("C:/veri-ham/cigkofte")

BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

OSES_URL = "https://www.oses.com.tr/oses-cigkofte-subeleri"
#: The brand's own Google My Maps id, taken from the iframe on its dealer page.
ZIYAFET_MAP = "1b_ViJ7hrIv8oMiHeWMZtZnmMxhspC_M"
ZIYAFET_KML = f"https://www.google.com/maps/d/kml?mid={ZIYAFET_MAP}&forcekml=1"
KOMAGENE = "https://gateway.komagene.com.tr/b2c/site/"

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}

#: Komagene's own province ids, from the `drpIl` select. "YURTDIŞI" (460) is left out: it
#: is not a province and its branches are abroad.
KOMAGENE_PROVINCES = {
    "ADANA": 164, "ADIYAMAN": 165, "AFYONKARAHİSAR": 166, "AĞRI": 167, "AKSARAY": 231,
    "AMASYA": 168, "ANKARA": 169, "ANTALYA": 170, "ARDAHAN": 238, "ARTVİN": 171,
    "AYDIN": 172, "BALIKESİR": 173, "BARTIN": 237, "BATMAN": 235, "BAYBURT": 232,
    "BİLECİK": 174, "BİNGÖL": 175, "BİTLİS": 176, "BOLU": 177, "BURDUR": 178,
    "BURSA": 179, "ÇANAKKALE": 180, "ÇANKIRI": 181, "ÇORUM": 182, "DENİZLİ": 183,
    "DİYARBAKIR": 184, "DÜZCE": 244, "EDİRNE": 185, "ELAZIĞ": 186, "ERZİNCAN": 187,
    "ERZURUM": 188, "ESKİŞEHİR": 189, "GAZİANTEP": 190, "GİRESUN": 191,
    "GÜMÜŞHANE": 192, "HAKKARİ": 193, "HATAY": 194, "IĞDIR": 239, "ISPARTA": 195,
    "İSTANBUL": 197, "İZMİR": 198, "KAHRAMANMARAŞ": 209, "KARABÜK": 241,
    "KARAMAN": 233, "KARS": 199, "KASTAMONU": 200, "KAYSERİ": 201, "KIRIKKALE": 234,
    "KIRKLARELİ": 202, "KIRŞEHİR": 203, "KİLİS": 242, "KOCAELİ": 204, "KONYA": 205,
    "KÜTAHYA": 206, "MALATYA": 207, "MANİSA": 208, "MARDİN": 210, "MERSİN": 196,
    "MUĞLA": 211, "MUŞ": 212, "NEVŞEHİR": 213, "NİĞDE": 214, "ORDU": 215,
    "OSMANİYE": 243, "RİZE": 216, "SAKARYA": 217, "SAMSUN": 218, "SİİRT": 219,
    "SİNOP": 220, "SİVAS": 221, "ŞANLIURFA": 226, "ŞIRNAK": 236, "TEKİRDAĞ": 222,
    "TOKAT": 223, "TRABZON": 224, "TUNCELİ": 225, "UŞAK": 227, "VAN": 228,
    "YALOVA": 240, "YOZGAT": 229, "ZONGULDAK": 230,
}

COLUMNS = ["name", "province", "district", "address", "phone", "lat", "lng"]


def get(url: str, data: bytes | None = None, tries: int = 4) -> str:
    headers = {"User-Agent": BROWSER, "Accept": "*/*"}
    if data is not None:
        headers |= {
            "Content-Type": "application/json",
            "Origin": "https://www.komagene.com.tr",
            "Referer": "https://www.komagene.com.tr/",
        }
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(3 * 2**attempt)
    raise AssertionError("unreachable")


def oses() -> list[dict]:
    page = get(OSES_URL)
    match = re.search(r"gMaps\.locations\s*=\s*(\[.*?\]);", page, re.DOTALL)
    if not match:
        raise ValueError("Oses: gMaps.locations bulunamadı — sayfa değişmiş olabilir")
    return [
        {
            "name": row["name"],
            "province": row["cityName"],
            "district": row["townName"],
            "address": row["address"],
            "phone": row.get("phone", ""),
            "lat": row["lat"],
            "lng": row["lng"],
        }
        for row in json.loads(match.group(1))
    ]


def ziyafet() -> list[dict]:
    root = ET.fromstring(get(ZIYAFET_KML))
    rows = []
    for placemark in root.findall(".//k:Placemark", KML_NS):
        name = placemark.find("k:name", KML_NS)
        description = placemark.find("k:description", KML_NS)
        point = placemark.find(".//k:coordinates", KML_NS)
        if point is None or not (point.text or "").strip():
            continue
        lng, lat, *_ = point.text.strip().split(",")
        rows.append(
            {
                # The map's labels carry newlines and a branch number: "ÇERKEZKÖY-1\n".
                "name": " ".join((name.text or "").split()),
                "province": "",  # the map has no province field; the point decides
                "district": "",
                "address": "",
                "phone": " ".join((description.text or "").split())
                if description is not None
                else "",
                "lat": lat,
                "lng": lng,
            }
        )
    return rows


def komagene() -> list[dict]:
    rows = []
    for province, province_id in KOMAGENE_PROVINCES.items():
        payload = json.dumps({"IlId": province_id}).encode("utf-8")
        answer = json.loads(get(KOMAGENE + "getwebportalilceler", payload))
        districts = answer["Data"]["Ilceler"]
        time.sleep(0.3)
        for district in districts:
            body = json.dumps({"IlceId": str(district["Id"])}).encode("utf-8")
            branches = json.loads(get(KOMAGENE + "getsubebilgileri", body))["Data"]
            time.sleep(0.3)
            for branch in branches or []:
                rows.append(
                    {
                        "name": branch["BracnhName"],  # the source's own spelling
                        "province": branch["Il"],
                        "district": branch["Ilce"],
                        "address": branch["BranchAdress"],
                        "phone": branch.get("PaketTelefon", ""),
                        "lat": branch["Latitude"],
                        "lng": branch["Longitude"],
                    }
                )
        print(f"  {province}: {len(districts)} ilçe, toplam {len(rows)}", flush=True)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(tz=dt.UTC).date()
    for brand, fetch in (("oses", oses), ("ziyafet", ziyafet), ("komagene", komagene)):
        print(f"== {brand}", flush=True)
        rows = fetch()
        target = OUT / f"{brand}_{today:%Y-%m-%d}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{brand}: {len(rows):,} şube -> {target}", flush=True)


if __name__ == "__main__":
    main()
