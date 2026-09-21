"""EPDK akaryakıt bayi kaydı → (lisans no, ilçe id, dağıtıcı). Üç adım, sırayla:

1. İl ve ilçe sütunu (12.187 kayıt). Büyükşehirde "MERKEZ" 2012 öncesinin ilçesidir, eşleşmez.
2. Adreste geçen ilçe adı (adres_ilce).
3. Adreste geçen mahalle/semt adı, ilin 2025 mahalle defterinde tek bir ilçeye çıkıyorsa.
   Birden çok ilçeye çıkıyorsa yerleştirilmez — tahmin yok.
İhrakiye (deniz yakıt istasyonu, 28) kara istasyonu değildir, alınmaz.
"""
import csv, json, re, sys
import xlrd
sys.path.insert(0, "C:/veri-ham/zincir")
from adres_ilce import ilce as adres_ilce

ROOT = "C:/veri/.claude/worktrees/durum-ozeti-plan-78c634"
K = json.load(open("C:/veri/public/geo/kapsam.json", encoding="utf-8"))


def fold(n):
    n = n.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıişçğöüâî", "iiscgouai"):
        n = n.replace(a, b)
    return re.sub(r"[^a-z0-9 ]", " ", n)


IL = {fold(v["ad"]).replace(" ", ""): a for a, v in K.items() if v["duzey"] == "il"}
ILCE = {(a[:5], fold(v["ad"]).replace(" ", "")): a for a, v in K.items() if v["duzey"] == "ilce"}
MAH = {}
for r in csv.DictReader(open(f"{ROOT}/src/veriatlas/data/areas_tr_neighbourhoods.csv", encoding="utf-8")):
    if r["last_seen"] != "2025":
        continue
    core = re.sub(r"\b(mah|mahallesi|koyu|mh)\b\.?", "", fold(r["name_tr"])).strip()
    if len(core) >= 4:
        MAH.setdefault(r["parent_id"][:5], {}).setdefault(core, set()).add(r["parent_id"])


def by_mahalle(p, address):
    t = " " + re.sub(r"\s+", " ", fold(address.split("(")[0])) + " "
    hits = set()
    for core, ds in MAH.get(p, {}).items():
        if f" {core} " in t:
            hits |= ds
    return hits.pop() if len(hits) == 1 else None


def main():
    s = xlrd.open_workbook("C:/veri-ham/epdk/akaryakit_bayilik/petrolBayilikLisanslar_2026-09-21.xls").sheet_by_index(0)
    out, how, left = [], {"sütun": 0, "adres": 0, "mahalle": 0}, []
    for r in range(1, s.nrows):
        if s.cell_value(r, 12) != "Akaryakıt":
            continue
        p = IL[fold(s.cell_value(r, 8)).replace(" ", "")]
        d = fold(s.cell_value(r, 7)).replace(" ", "")
        a = ILCE.get((p, fold(K[p]["ad"]).replace(" ", "") if d == "merkez" else d))
        step = "sütun"
        if not a:
            a, step = adres_ilce(p, s.cell_value(r, 6)), "adres"
        if not a:
            a, step = by_mahalle(p, s.cell_value(r, 6)), "mahalle"
        if not a:
            left.append((s.cell_value(r, 1), s.cell_value(r, 8), s.cell_value(r, 6)))
            continue
        how[step] += 1
        out.append((s.cell_value(r, 1), a, s.cell_value(r, 9).strip()))
    with open("C:/veri-ham/epdk/akaryakit_bayilik/istasyon_ilce.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["lisans_no", "area_id", "dagitici"]); w.writerows(out)
    with open("C:/veri-ham/epdk/akaryakit_bayilik/yerlesmeyen.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["lisans_no", "il", "adres"]); w.writerows(left)
    return how, len(left)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(*main())
