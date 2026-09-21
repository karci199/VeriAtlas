"""Iznik: urban/rural split, turnout and right/left bloc shares by election.

Urban = the seven town-centre neighbourhoods; every other unit is a village.
After the 2012 metropolitan law all villages were relabelled "Mah.", so the
urban/rural line cannot be read off the unit type and comes from this list.

Bloc labels are a judgement call and are printed with the unclassified share so
the classification can be checked and overridden.
"""

import collections
import csv
import pathlib

BASE = pathlib.Path(__file__).parent
AGG = {"sandik", "kayitli_secmen", "oy_kullanan", "gecerli_oy"}
YEARS = [
    "1991",
    "1995",
    "1999",
    "2002",
    "2007",
    "2011",
    "2015h",
    "2015k",
    "2018",
    "2023",
]
LABEL = {"2015h": "2015-Haz", "2015k": "2015-Kas"}

URBAN = {
    "mustafakemalpasa",
    "selcuk",
    "yesilcami",
    "yesilcamii",
    "yeni",
    "yenimahalle",
    "esrefzade",
    "mahmutcelebi",
    "beyler",
}

SOL = {
    "SHP",
    "DSP",
    "CHP",
    "YTP",
    "HADEP",
    "DEHAP",
    "DTP",
    "DBP",
    "HDP",
    "YEŞİL SOL PARTİ",
    "SOL PARTİ",
    "ÖDP",
    "EMEP",
    "SİP",
    "TKP",
    "TKH",
    "TİP",
    "HKP",
    "İP",
    "VATAN PARTİSİ",
    "KP",
    "SP",
    "MEMLEKET",
}
SAG = {
    "DYP",
    "ANAP",
    "RP",
    "FP",
    "SAADET PARTİSİ",
    "MHP",
    "BBP",
    "BÜYÜK BİRLİK",
    "DP",
    "AK PARTİ",
    "GENÇ PARTİ",
    "BTP",
    "HYP",
    "ATP",
    "LDP",
    "MİLLET PARTİSİ",
    "MİLLET",
    "YDP",
    "YDH",
    "YENİ PARTİ",
    "YURT-P",
    "HEPAR",
    "HAS PARTİ",
    "MMP",
    "HÜDA PAR",
    "İYİ PARTİ",
    "YENİDEN REFAH",
    "ZAFER PARTİSİ",
    "ANADOLU PARTİSİ",
    "MİLLİ YOL",
    "AP",
    "DTP-1999",
}
ITTIFAK = "İTTİFAK"


def tr_lower(text):
    """Lowercase Turkish text: 'İ'.lower() yields a combining dot in Python."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def norm(name):
    t = tr_lower(name.replace("Mah.", "").replace("Köyü", "").strip())
    for a, b in zip("çğıöşü", "cgiosu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalnum())


# Aggregate captions only. "Belde/Köy" is a subtotal, but "... (B) Belde" is a
# real settlement, so the caption is matched exactly rather than by substring.
SKIP_EXACT = ("belde/köy", "belde /köy")
SKIP_WORDS = ("toplam", "ilçe merkezi", "bucağ", "bursa", "iznik", "seçim çevresi")


def load():
    """{(year, unit): {measure: value}} for Iznik's own neighbourhoods/villages.

    Aggregate rows are dropped by name; the same caption ("Belde/Köy") appears
    at both province and district level, so matching is case-insensitive.
    """
    units = collections.defaultdict(dict)
    totals = collections.defaultdict(dict)
    with open(BASE / "secim_mahalle.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["ilce"] != "i_znik":
            continue
        name = r["birim"]
        low = tr_lower(name)
        if low in SKIP_EXACT or any(w in low for w in SKIP_WORDS):
            if low in ("iznik", "iznik ilçe toplamı"):
                totals[r["yil"]][r["olcut"]] = int(r["deger"])
            continue
        units[(r["yil"], name)][r["olcut"]] = int(r["deger"])
    return units, totals


def main():
    units, totals = load()
    out = []
    for y in YEARS:
        rows = [(n, v) for (yy, n), v in units.items() if yy == y]
        kent = [v for n, v in rows if norm(n) in URBAN]
        kir = [v for n, v in rows if norm(n) not in URBAN]
        if not kent or not kir:
            print(f"{y}: birim bulunamadi (kent={len(kent)} kir={len(kir)})")
            continue

        def agg(group, key):
            return sum(v.get(key, 0) for v in group)

        def bloc(group):
            sol = sag = diger = 0
            for v in group:
                for col, val in v.items():
                    if col in AGG or ITTIFAK in col:
                        continue
                    if col in SOL:
                        sol += val
                    elif col in SAG:
                        sag += val
                    else:
                        diger += val
            return sol, sag, diger

        rec = {"yil": LABEL.get(y, y), "kent_birim": len(kent), "kir_birim": len(kir)}
        for tag, g in (("kent", kent), ("kir", kir), ("ilce", kent + kir)):
            kay, gec = agg(g, "kayitli_secmen"), agg(g, "gecerli_oy")
            sol, sag, diger = bloc(g)
            rec[f"{tag}_kayitli"] = kay
            rec[f"{tag}_gecerli"] = gec
            rec[f"{tag}_katilim"] = 100 * gec / kay if kay else 0
            top = sol + sag + diger
            rec[f"{tag}_sol"] = 100 * sol / top if top else 0
            rec[f"{tag}_sag"] = 100 * sag / top if top else 0
            rec[f"{tag}_diger"] = 100 * diger / top if top else 0
        rec["kentlesme"] = 100 * rec["kent_kayitli"] / rec["ilce_kayitli"]
        resmi = totals.get(y, {}).get("kayitli_secmen")
        rec["ilce_toplam_satiri"] = resmi or ""
        rec["fark"] = (rec["ilce_kayitli"] - resmi) if resmi else ""
        out.append(rec)

    print("KENTLEŞME (kent kayıtlı / toplam kayıtlı) ve KATILIM (geçerli oy / kayıtlı)")
    print(
        f"{'yıl':9} {'kent kay.':>9} {'kır kay.':>9} {'kent%':>6} "
        f"{'katılım kent':>13} {'katılım kır':>12} {'katılım ilçe':>13}"
    )
    for r in out:
        print(
            f"{r['yil']:9} {r['kent_kayitli']:>9,} {r['kir_kayitli']:>9,} "
            f"{r['kentlesme']:>6.1f} {r['kent_katilim']:>13.1f} "
            f"{r['kir_katilim']:>12.1f} {r['ilce_katilim']:>13.1f}"
        )

    print("\nBLOK OY ORANI (geçerli oy içinde %, ittifak mührü hariç)")
    print(
        f"{'yıl':9} {'kent sağ':>9} {'kent sol':>9} {'kent diğer':>11} "
        f"{'kır sağ':>9} {'kır sol':>9} {'kır diğer':>10}"
    )
    for r in out:
        print(
            f"{r['yil']:9} {r['kent_sag']:>9.1f} {r['kent_sol']:>9.1f} "
            f"{r['kent_diger']:>11.1f} {r['kir_sag']:>9.1f} {r['kir_sol']:>9.1f} "
            f"{r['kir_diger']:>10.1f}"
        )

    print()
    print("DOĞRULAMA (kent+kır kayıtlı  vs  raporun ilçe toplamı satırı)")
    for r in out:
        print(
            f"  {r['yil']:9} hesap {r['ilce_kayitli']:>7,}  rapor "
            f"{r['ilce_toplam_satiri'] or '-':>9}  fark {r['fark']}"
        )

    dest = BASE / "iznik_kent_kir.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
