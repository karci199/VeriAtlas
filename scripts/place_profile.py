"""Everything the repository holds about one place, gathered in one screen.

The registry answers *what a place is* — its id, name, parent and the years it was
observed. It deliberately does not answer *what a place is like*: population, vote,
postcode, coordinate and the rest live in the fact table, in the raw pulls, or in a
source we have not folded in yet. This script walks all of them for one area and prints
what each one has, so a gap is visible as a gap rather than as a missing line.

That is also the design note the profile is meant to settle: attributes do not belong in
`areas_tr_*.csv`. Those files carry identity and lineage, one row per area, and stay
joinable. Everything below is either a series (belongs in the fact table, keyed by
area × period × breakdown) or a single attribute per area (belongs in a separate
attribute table, keyed by area, with the source named per field).

Run:  uv run python scripts/place_profile.py TR-16-006-11418
      uv run python scripts/place_profile.py TR-06-016-2149 TR-06-012-1649
"""

import csv
import gzip
import sys

sys.path.insert(0, "src")

from veriatlas.config import DATA, PUBLIC, RAW

PTT = RAW / "ptt" / "ptt_semt_2022.csv"
SECIM = RAW / "tuik_secim" / "secim_mahalle.csv"
ENDEKSA = RAW / "endeksa" / "demography"


def fold(text: str) -> str:
    text = (text or "").replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("çğıöşüâîû", "cgiosuaiu"):
        text = text.replace(a, b)
    return "".join(ch for ch in text if ch.isalnum())


def sade(ad: str) -> str:
    """Settlement name without its type word — the join key the PTT file needs."""
    ad = (ad or "").strip()
    if "(" in ad and ad.rindex(")") > ad.rindex("("):
        ic = ad[ad.rindex("(") + 1 : ad.rindex(")")]
        ad = ic if fold(ic).endswith(("koyu", "koy")) else ad[: ad.rindex("(")]
    key = fold(ad)
    for son in ("mahallesi", "mah", "beldesi", "belde", "koyu", "koy"):
        if key.endswith(son):
            return key[: -len(son)]
    return key


def registry() -> dict[str, dict]:
    """Every area the registry knows, whatever its level."""
    out: dict[str, dict] = {}
    for name in (
        "areas_tr.csv",
        "areas_tr_districts.csv",
        "areas_tr_neighbourhoods.csv",
        "areas_tr_villages.csv",
    ):
        for row in csv.DictReader((DATA / name).open(encoding="utf-8")):
            out[row["area_id"]] = row
    return out


def nuts() -> dict[str, tuple[str, str, str, str]]:
    """Province name -> (nuts1 id, nuts1 name, nuts2 id, nuts2 name)."""
    out = {}
    for row in csv.DictReader((DATA / "nuts_tr.csv").open(encoding="utf-8")):
        out[fold(row["province_name"])] = (
            row["nuts1_id"],
            row["nuts1_name"],
            row["nuts2_id"],
            row["nuts2_name"],
        )
    return out


def population(area_id: str) -> dict[int, dict[str, float]]:
    """year -> {breakdown: value} from the published web slices."""
    out: dict[int, dict[str, float]] = {}
    for name in ("population-neighbourhood.csv.gz", "population-village.csv.gz"):
        path = PUBLIC / name
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["area_id"] != area_id:
                    continue
                yil = int(row["year"])
                out.setdefault(yil, {})[row["age"] or "toplam"] = float(
                    row["value"] or 0
                )
    return out


def ptt_row(il: str, ilce: str, ad: str) -> dict | None:
    if not PTT.exists():
        return None
    hedef = sade(ad)
    for row in csv.DictReader(PTT.open(encoding="utf-8")):
        if fold(row["il"]) != fold(il):
            continue
        if fold(row["ilce"]) not in (fold(ilce), "merkez"):
            continue
        if sade(row["mahalle"]) == hedef:
            return row
    return None


def votes(il: str, ilce: str, ad: str, year: str = "2023") -> dict | None:
    """One settlement's row from the long-format election export.

    The file is `yil, cevre, ilce, birim, olcut, deger` — one line per measure, so a
    settlement's numbers are gathered rather than read off a row. A settlement can appear
    under several ballot-box groups within its district; they are summed.
    """
    if not SECIM.exists():
        return None
    hedef = sade(ad)
    toplam: dict[str, float] = {}
    with SECIM.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["yil"] != year or sade(row["birim"]) != hedef:
                continue
            if fold(row["ilce"]) not in (fold(ilce), fold(il) + "merkez"):
                continue
            try:
                toplam[row["olcut"]] = toplam.get(row["olcut"], 0) + float(
                    row["deger"] or 0
                )
            except ValueError:
                pass
    return toplam or None


def endeksa(plate: str, ilce: str, ad: str) -> dict | None:
    """Endeksa's 2024 cut for this settlement, if its province has been pulled.

    The settlement's name is `geo["District"]` — Endeksa's `level=3` — and the district
    it sits in is `geo["County"]`. Both are matched, because a province holds several
    `Cumhuriyet`.
    """
    import json

    if not ENDEKSA.exists():
        return None
    for path in sorted(ENDEKSA.glob(f"TR-{plate}-*.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")).values():
            geo = rec.get("geo") or {}
            if fold(geo.get("County", "")) not in (fold(ilce), fold(ilce) + "merkez"):
                continue
            if sade(geo.get("District", "")) == sade(ad):
                return rec
    return None


def kunye(area_id: str, kayit: dict[str, dict], ibbs: dict) -> None:
    row = kayit.get(area_id)
    if row is None:
        print(f"\n{area_id}: kayitta yok")
        return

    zincir = []
    node = row
    while node is not None:
        zincir.append(node)
        node = kayit.get(node.get("parent_id") or "")
    zincir.reverse()

    il = next((n for n in zincir if n["area_level"] == "province"), None)
    ilce = next((n for n in zincir if n["area_level"] == "district"), None)

    print("\n" + "=" * 72)
    print(f"{row['name_tr']}  [{area_id}]  ·  {row['area_level']}")
    print("=" * 72)

    print("\nKADEME")
    print("   ülke            Türkiye")
    if il:
        n1, n1ad, n2, n2ad = ibbs.get(fold(il["name_tr"]), ("", "", "", ""))
        print(f"   İBBS-1          {n1} {n1ad}")
        print(f"   İBBS-2          {n2} {n2ad}")
        print(f"   il              {il['name_tr']} [{il['area_id']}]")
    if ilce:
        print(f"   ilçe            {ilce['name_tr']} [{ilce['area_id']}]")
    belediye = row.get("municipality") or ""
    if belediye:
        print(f"   belediye        {belediye}")
    bucak = row.get("bucak") or ""
    if bucak:
        print(f"   bucak           {bucak}")
    print(f"   yerleşim        {row['name_tr']}")
    print(
        f"   kent / kır      {'kent (belediye mahallesi)' if belediye else 'kır (köy)'}"
    )

    print("\nKİMLİK VE SÜRE")
    print(f"   MEDAS kodu      {row.get('medas_code', '')}")
    print(f"   ilk görüldüğü   {row.get('first_seen', '')}")
    print(f"   son görüldüğü   {row.get('last_seen', '')}")
    print(f"   kaynak          {row.get('source_id', '')}")

    seri = population(area_id)
    print("\nNÜFUS")
    if seri:
        for yil in sorted(seri)[-3:]:
            parcalar = seri[yil]
            toplam = sum(parcalar.values())
            ayrinti = "  ".join(f"{k} {int(v):,}" for k, v in sorted(parcalar.items()))
            print(f"   {yil}            {int(toplam):>7,}   ({ayrinti})")
        print(f"   seri            {min(seri)}–{max(seri)}")
    else:
        print("   yok")

    if il and ilce:
        p = ptt_row(il["name_tr"], ilce["name_tr"], row["name_tr"])
        print("\nPTT (2022)")
        if p:
            print(f"   posta kodu      {p['pk']}")
            print(f"   semt sütunu     {p['semt']}")
        else:
            print("   eşleşmedi")

        v = votes(il["name_tr"], ilce["name_tr"], row["name_tr"])
        print("\nSEÇİM 2023")
        if v:
            kayitli = v.get("kayitli_secmen", 0)
            gecerli = v.get("gecerli_oy", 0)
            print(f"   kayıtlı seçmen  {int(kayitli):,}")
            if kayitli:
                print(
                    f"   katılım         %{100 * v.get('oy_kullanan', 0) / kayitli:.1f}"
                )
            if gecerli:
                sayac = ("sandik", "kayitli_secmen", "oy_kullanan", "gecerli_oy")
                buyuk = sorted(
                    ((k, x) for k, x in v.items() if k not in sayac and x > 0),
                    key=lambda kv: -kv[1],
                )[:4]
                for parti, oy in buyuk:
                    print(f"   {parti:15} %{100 * oy / gecerli:.1f}")
        else:
            print("   eşleşmedi")

        e = endeksa(il["area_id"].split("-")[1], ilce["name_tr"], row["name_tr"])
        print("\nENDEKSA (2024)")
        if e:
            d = e.get("demography") or {}
            alanlar = [
                ("nüfus", "Population"),
                ("yüzölçümü km²", "Area"),
                ("hane", "HouseholdCount"),
                ("belediye", "MunicipalityName"),
                ("ortalama yaş", "AverageAge"),
                ("ortalama gelir", "AverageIncome"),
            ]
            for etiket, anahtar in alanlar:
                if d.get(anahtar) not in (None, 0):
                    print(f"   {etiket:15} {d[anahtar]}")
            if not any(d.get(a) for _, a in alanlar):
                print("   kayıt var, sayılar boş")
        else:
            print("   bu il henüz çekilmedi ya da eşleşmedi")

    print("\nEKSİK")
    eksik = []
    if not row.get("medas_code"):
        eksik.append("MEDAS kodu")
    eksik += ["koordinat", "açıklama", "eski adlar (bu ekranda)"]
    print("   " + ", ".join(eksik))


def main() -> None:
    ids = sys.argv[1:]
    if not ids:
        raise SystemExit(__doc__)
    kayit = registry()
    ibbs = nuts()
    for area_id in ids:
        kunye(area_id, kayit, ibbs)


if __name__ == "__main__":
    main()
