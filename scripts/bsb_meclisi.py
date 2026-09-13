"""Metropolitan council seats, built the way the law builds them.

Law 5216 art. 12: the metropolitan council is not elected. It is made of one member for
every five elected members of each district's own council, plus the district mayors, who
sit ex officio. So the metropolitan council is a derived body and its party balance can be
wrong-footed by district boundaries: a party that wins many small districts sits larger
than its vote.

Getting there needs three steps, and each is a rule rather than a choice:

  1. **Council size by population** — law 2972 art. 5, the brackets below. The population
     is the district's, not the electorate's, because that is what the law counts.
  2. **Seats by D'Hondt** among the parties that clear the district's 10% threshold
     (law 2972 art. 23). Below that a party takes no seat however many votes it has.
  3. **One in five**, and the mayors added.

The 1/5 is taken as `size // 5` — five members give one, nine give one, fifteen give three.
Where the count is checkable the total is printed, so a wrong bracket table shows up as a
wrong national total rather than as a plausible-looking party split.

Run:  uv run python scripts/bsb_meclisi.py [2024] [--baraj=10]
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"

#: (population ceiling, members) — law 2972 art. 5.
KADEME = [
    (10_000, 9),
    (20_000, 11),
    (50_000, 15),
    (100_000, 25),
    (250_000, 31),
    (500_000, 37),
    (1_000_000, 45),
    (float("inf"), 55),
]


#: Reserved seats by council size — law 2972 art. 23. They are not part of the D'Hondt
#: share-out: the divisor count is the council size minus these, and they all go to the
#: party with the most votes in that district. Leaving them out understates the leading
#: party by one to six seats per district, which across 973 districts is thousands.
KONTENJAN = {9: 1, 11: 1, 15: 2, 25: 3, 31: 3, 37: 4, 45: 5, 55: 6}


def uye_sayisi(nufus: float) -> int:
    return next(n for tavan, n in KADEME if nufus <= tavan)


def dhondt(oylar: dict[str, float], sandalye: int, baraj: float) -> dict[str, int]:
    """Seats by D'Hondt among the parties over the district threshold."""
    toplam = sum(oylar.values())
    if toplam <= 0 or sandalye <= 0:
        return {}
    yarisan = {k: v for k, v in oylar.items() if 100 * v / toplam >= baraj}
    if not yarisan:
        yarisan = oylar
    dagitim: dict[str, int] = collections.Counter()
    for _ in range(sandalye):
        kazanan = max(yarisan, key=lambda k: yarisan[k] / (dagitim[k] + 1))
        dagitim[kazanan] += 1
    return dict(dagitim)


def main(argv: list[str]) -> None:
    yil = next((a for a in argv if not a.startswith("--")), "2024")
    baraj = float(next((a.split("=")[1] for a in argv if a.startswith("--baraj=")), 10))

    nufus_tab = json.loads((TILES / "ilce-veri.json").read_text(encoding="utf-8"))
    meclis = json.loads(
        (TILES / f"secim-yerel_belmec_{yil}-ilce.json").read_text(encoding="utf-8")
    )
    baskan = json.loads(
        (TILES / f"secim-yerel_bel_{yil}-ilce.json").read_text(encoding="utf-8")
    )
    bsb_ilce = set(
        json.loads(
            (TILES / f"secim-yerel_bsb_{yil}-ilce.json").read_text(encoding="utf-8")
        )
    )

    uye_toplam = 0
    ulke = collections.Counter()
    bsb = collections.defaultdict(lambda: {"uye": collections.Counter(),
                                           "baskan": collections.Counter()})
    nufussuz = 0
    for area, row in meclis.items():
        oy = {k: v for k, v in row.get("v", {}).items() if "İTTİFAK" not in k.upper()}
        if not oy or sum(oy.values()) <= 0:
            continue
        yillar = nufus_tab.get(area) or {}
        nufus = (yillar.get(yil) or yillar.get("2023") or [None])[0]
        if not nufus:
            nufussuz += 1
            continue
        n = uye_sayisi(nufus)
        uye_toplam += n
        kont = KONTENJAN[n]
        dagitim = collections.Counter(dhondt(oy, n - kont, baraj))
        dagitim[max(oy, key=oy.get)] += kont
        dagitim = dict(dagitim)
        ulke.update(dagitim)
        if area in bsb_ilce:
            il = "-".join(area.split("-")[:2])
            for parti, adet in dagitim.items():
                bsb[il]["uye"][parti] += adet // 5
            kazanan = baskan.get(area, {}).get("v")
            if kazanan:
                temiz = {k: v for k, v in kazanan.items() if "İTTİFAK" not in k.upper()}
                if temiz:
                    bsb[il]["baskan"][max(temiz, key=temiz.get)] += 1

    print(f"{yil} · ilce belediye meclisi toplam uyelik: {uye_toplam:,} "
          f"(nufusu bulunamayan {nufussuz} ilce disarida)")
    print(f"ulke geneli meclis uyeligi (D Hondt, %{baraj:g} baraj):")
    for parti, adet in ulke.most_common(10):
        print(f"   {parti[:24]:24} {adet:6,}  %{100 * adet / sum(ulke.values()):5.1f}")

    print(f"\n=== BUYUKSEHIR MECLISLERI ({len(bsb)} il) ===")
    il_ad = json.loads((TILES / "il-adlari.json").read_text(encoding="utf-8"))
    genel = collections.Counter()
    for il, veri in sorted(bsb.items()):
        ad = il_ad.get(il, il)
        ad = ad.get("ad", il) if isinstance(ad, dict) else ad
        toplam = veri["uye"] + veri["baskan"]
        genel.update(toplam)
        n = sum(toplam.values())
        ilk = "  ".join(
            f"{p.split()[0][:9]} {a}" for p, a in toplam.most_common(4)
        )
        print(f"{str(ad)[:14]:14} {n:4} uye  ({sum(veri['uye'].values())} meclisten + "
              f"{sum(veri['baskan'].values())} baskan)   {ilk}")
    print(f"\n30 buyuksehir toplam: {sum(genel.values()):,} uye")
    for parti, adet in genel.most_common(8):
        print(f"   {parti[:24]:24} {adet:5,}  %{100 * adet / sum(genel.values()):5.1f}")




def sapma(yil: str = "2024", baraj: float = 10.0) -> None:
    """Seat share against two different vote shares, per metropolitan province.

    Two comparisons because they answer different questions. The metropolitan mayor's own
    vote is what the province actually gave that office; the sum of the district council
    votes is what it gave the party. A council derived from districts can diverge from
    both, and the two divergences are not the same number.

    Gallagher's index is reported per province: the root of half the sum of squared
    differences, the standard measure of how far a seat share sits from a vote share.
    """
    import math

    nufus_tab = json.loads((TILES / "ilce-veri.json").read_text(encoding="utf-8"))
    meclis = json.loads(
        (TILES / f"secim-yerel_belmec_{yil}-ilce.json").read_text(encoding="utf-8")
    )
    baskan = json.loads(
        (TILES / f"secim-yerel_bel_{yil}-ilce.json").read_text(encoding="utf-8")
    )
    bsb_tab = json.loads(
        (TILES / f"secim-yerel_bsb_{yil}-ilce.json").read_text(encoding="utf-8")
    )
    il_ad = json.loads((TILES / "il-adlari.json").read_text(encoding="utf-8"))

    sandalye = collections.defaultdict(collections.Counter)
    meclis_oy = collections.defaultdict(collections.Counter)
    bsb_oy = collections.defaultdict(collections.Counter)
    for area, row in meclis.items():
        if area not in bsb_tab:
            continue
        oy = {k: v for k, v in row.get("v", {}).items() if "İTTİFAK" not in k.upper()}
        yillar = nufus_tab.get(area) or {}
        nufus = (yillar.get(yil) or yillar.get("2023") or [None])[0]
        if not oy or sum(oy.values()) <= 0 or not nufus:
            continue
        il = "-".join(area.split("-")[:2])
        meclis_oy[il].update(oy)
        bsb_oy[il].update(
            {k: v for k, v in bsb_tab[area].get("v", {}).items()
             if "İTTİFAK" not in k.upper()}
        )
        n = uye_sayisi(nufus)
        kont = KONTENJAN[n]
        pay_ = collections.Counter(dhondt(oy, n - kont, baraj))
        pay_[max(oy, key=oy.get)] += kont
        for parti, adet in pay_.items():
            sandalye[il][parti] += adet // 5
        kaz = {k: v for k, v in baskan.get(area, {}).get("v", {}).items()
               if "İTTİFAK" not in k.upper()}
        if kaz:
            sandalye[il][max(kaz, key=kaz.get)] += 1

    def yuzde(c):
        t = sum(c.values())
        return {k: 100 * v / t for k, v in c.items()} if t else {}

    print(f"\n{'il':14} {'uye':>4} {'parti':16} {'sandalye%':>9} {'bsb oy%':>8} "
          f"{'meclis oy%':>10} {'sapma(bsb)':>10} {'sapma(mec)':>10}")
    gall = []
    for il in sorted(sandalye, key=lambda i: -sum(sandalye[i].values())):
        s, b, m = yuzde(sandalye[il]), yuzde(bsb_oy[il]), yuzde(meclis_oy[il])
        ad = il_ad.get(il, il)
        ad = ad.get("ad", il) if isinstance(ad, dict) else ad
        g = math.sqrt(sum((s.get(k, 0) - m.get(k, 0)) ** 2 for k in set(s) | set(m)) / 2)
        gall.append((g, str(ad)))
        for parti in sorted(s, key=lambda k: -s[k])[:3]:
            print(f"{str(ad)[:14]:14} {sum(sandalye[il].values()):4} {parti[:16]:16} "
                  f"{s[parti]:8.1f}% {b.get(parti, 0):7.1f}% {m.get(parti, 0):9.1f}% "
                  f"{s[parti] - b.get(parti, 0):+9.1f} {s[parti] - m.get(parti, 0):+9.1f}")
    gall.sort(reverse=True)
    print("\nGallagher (sandalye vs ilce meclisi oyu) — en orantisiz 8:")
    for g, ad in gall[:8]:
        print(f"   {ad[:16]:16} {g:5.2f}")
    print("en orantili 5:")
    for g, ad in gall[-5:]:
        print(f"   {ad[:16]:16} {g:5.2f}")


if __name__ == "__main__":
    if "--sapma" in sys.argv:
        sapma(next((a for a in sys.argv[1:] if not a.startswith("--")), "2024"))
    else:
        main(sys.argv[1:])
