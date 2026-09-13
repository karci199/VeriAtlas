"""Ankara 2025: urban / rural per neighbourhood, with the basis written next to it.

No single source answers this. The province is metropolitan, so TÜİK calls all of it
urban and the election reports stopped carrying the split in 2011. So four rules are
applied in order, and each neighbourhood records which one decided it:

  wiki-kırsal   Wikipedia's navbox puts it in a "Kırsal Mahalleler" group
  semt          it sits in a named semt group the reader classed by hand
                (İncek is urban; Karagedik, Oyaca, Karaali, Temelli are rural)
  elle          a hand list, for districts Wikipedia does not split at all
  yoğunluk      fewer than 100 people per km² (Endeksa's area), where nothing else says

The density fallback is what confirms the hand list rather than replacing it: Altındağ's
five rural neighbourhoods run 10-41 people/km² and the next one up, Solfasol, is 436.
"""

import collections
import csv
import gzip
import json
import sys

sys.path.insert(0, "src")

from veriatlas.config import DATA, PUBLIC, RAW

WIKI = RAW / "wikipedia" / "mahalle-ankara.json"
YOGUNLUK_ESIGI = 100

#: Semt groups the reader placed by hand. Everything not named here that is a semt group
#: falls through to the density test.
SEMT_KENT = {"İncek"}
SEMT_KIR = {"Karagedik", "Oyaca", "Karaali", "Temelli"}

#: Districts Wikipedia does not split, where the rural ones are named by hand.
ELLE_KIR = {
    "Altındağ": {"Tatlar", "Gicik", "Peçenek", "Aydıncık", "Kavaklı"},
}


def fold(text: str) -> str:
    text = (text or "").replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("çğıöşüâîû", "cgiosuaiu"):
        text = text.replace(a, b)
    key = "".join(ch for ch in text if ch.isalnum())
    for son in ("mah", "koyu", "koy"):
        if key.endswith(son):
            return key[: -len(son)]
    return key


def alanlar() -> dict[tuple[str, str], float]:
    """(district, neighbourhood) -> km², from Endeksa's 2024 cut."""
    out = {}
    for path in (RAW / "endeksa" / "demography").glob("TR-06-*.json"):
        for rec in json.loads(path.read_text(encoding="utf-8")).values():
            geo, dem = rec.get("geo") or {}, rec.get("demography") or {}
            if dem.get("Area"):
                out[(fold(geo.get("County", "")), fold(geo.get("District", "")))] = dem[
                    "Area"
                ]
    return out


def nufus() -> collections.Counter:
    out = collections.Counter()
    with gzip.open(
        PUBLIC / "population-neighbourhood.csv.gz", "rt", encoding="utf-8"
    ) as fh:
        for row in csv.DictReader(fh):
            if row["year"] == "2025" and row["area_id"].startswith("TR-06-"):
                out[row["area_id"]] += float(row["value"] or 0)
    return out


def sinifla(wiki: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Folded name -> ("kent"/"kır", basis), from one district's navbox groups."""
    tur, dayanak = {}, {}
    for grup, adlar in wiki.items():
        etiket = grup.lower()
        if "kırsal" in etiket or "kirsal" in etiket:
            karar, gerekce = "kır", "wiki-kırsal"
        elif "merkez" in etiket or "kentsel" in etiket:
            karar, gerekce = "kent", "wiki-merkez"
        elif any(s in grup for s in SEMT_KIR):
            karar, gerekce = "kır", "semt"
        elif any(s in grup for s in SEMT_KENT):
            karar, gerekce = "kent", "semt"
        else:
            continue
        for ad in adlar:
            anahtar = fold(ad)
            # A name in two groups is urban: Çubuk lists Atatürk and Barbaros twice.
            if karar == "kent" or anahtar not in tur:
                tur[anahtar], dayanak[anahtar] = karar, gerekce
    return tur, dayanak


def main() -> None:
    wiki = json.loads(WIKI.read_text(encoding="utf-8"))
    alan, pop = alanlar(), nufus()
    ilce = {
        r["area_id"]: r["name_tr"]
        for r in csv.DictReader(
            (DATA / "areas_tr_districts.csv").open(encoding="utf-8")
        )
        if r["parent_id"] == "TR-06"
    }
    mahalle = collections.defaultdict(list)
    for row in csv.DictReader(
        (DATA / "areas_tr_neighbourhoods.csv").open(encoding="utf-8")
    ):
        if row["parent_id"] in ilce:
            mahalle[row["parent_id"]].append(row)

    baslik = f"{'ilçe':16} {'mah':>4} {'kent':>4} {'kır':>4} {'kent nüfus':>11} {'kır nüfus':>10} {'kır%':>6}"
    print("ANKARA 2025 — kent / kır")
    print(baslik)
    toplam = collections.Counter()
    sayac = collections.Counter()
    satirlar = []
    for aid, ad in sorted(ilce.items(), key=lambda kv: kv[1]):
        birimler = mahalle[aid]
        if not birimler:
            continue
        w = wiki.get(ad) or wiki.get("Balâ" if ad == "Bala" else "")
        tur, dayanak = sinifla(w) if w else ({}, {})
        elle = {fold(x) for x in ELLE_KIR.get(ad, set())}
        nk = nr = 0
        kent = kir = 0
        for m in birimler:
            anahtar = fold(m["name_tr"])
            n = pop.get(m["area_id"], 0)
            if anahtar in elle:
                karar, gerekce = "kır", "elle"
            elif anahtar in tur:
                karar, gerekce = tur[anahtar], dayanak[anahtar]
            else:
                a = alan.get((fold(ad), anahtar))
                if a and n and n / a < YOGUNLUK_ESIGI:
                    karar, gerekce = "kır", "yoğunluk"
                else:
                    karar, gerekce = "kent", "artık"
            sayac[gerekce] += 1
            if karar == "kır":
                nr += n
                kir += 1
            else:
                nk += n
                kent += 1
            satirlar.append((ad, m["name_tr"], int(n), karar, gerekce))
        toplam["kent"] += nk
        toplam["kır"] += nr
        pay = 100 * nr / (nk + nr) if nk + nr else 0
        print(
            f"{ad:16} {len(birimler):>4} {kent:>4} {kir:>4} {int(nk):>11,} {int(nr):>10,} %{pay:5.1f}"
        )
    t = toplam["kent"] + toplam["kır"]
    print(
        f"{'ANKARA':16} {'':>4} {'':>4} {'':>4} {int(toplam['kent']):>11,} "
        f"{int(toplam['kır']):>10,} %{100 * toplam['kır'] / t:5.1f}"
    )
    print("\ndayanak:", dict(sayac))

    out = RAW / "derived" / "ankara-kent-kir.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ilçe", "mahalle", "nüfus_2025", "tür", "dayanak"])
        w.writerows(satirlar)
    print("yazildi:", out)


if __name__ == "__main__":
    main()
