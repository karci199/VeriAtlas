"""Registered voters who produced no valid vote, by province and election.

kayıp = kayıtlı seçmen - geçerli oy: people on the roll who either did not turn
up or whose ballot was void. As a share of the roll it is the cleanest single
measure of how much of the electorate the result does not speak for.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("secmen", BASE / "secmen.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

K, O, G = "Kayıtlı seçmen sayısı", "Oy kullanan seçmen sayısı", "Geçerli oy sayısı"
GOSTER = ["1961", "1977", "1991", "2002", "2011", "2018", "2023"]


def main():
    il, _ = s.topla()
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), c in il.items():
        ulke[y].update(c)

    print("### ÜLKE — kayıtlı seçmenin geçerli oya dönüşmeyen kısmı")
    print(
        f"{'seçim':10}{'gitmeyen':>11}{'geçersiz':>10}{'kayıp':>11}{'kayıp %':>9}"
        f"{'gitmeyen %':>12}{'geçersiz %':>12}"
    )
    for y in s.YS:
        c = ulke[y]
        git, gec = c[K] - c[O], c[O] - c[G]
        kayip = c[K] - c[G]
        print(
            f"{s.AD.get(y, y):10}{git:>11,}{gec:>10,}{kayip:>11,}"
            f"{100 * kayip / c[K]:>8.1f}%{100 * git / c[K]:>11.1f}%{100 * gec / c[K]:>11.1f}%"
        )

    oran = {(y, k): 100 * (c[K] - c[G]) / c[K] for (y, k), c in il.items() if c[K]}
    iller = sorted({k for (_, k) in oran})

    print("\n### İL — kayıp oranı (%), seçilmiş yıllar; 2023'e göre sıralı")
    print(
        f"  {'il':16}"
        + "".join(f"{y:>9}" for y in GOSTER)
        + f"{'ort':>8}{'değişim':>9}"
    )
    rows = []
    for k in iller:
        v = [oran.get((y, k)) for y in GOSTER]
        hepsi = [oran[(y, k)] for y in s.YS if (y, k) in oran]
        rows.append(
            (k, v, statistics.fmean(hepsi), v[-1] - v[0] if v[0] and v[-1] else None)
        )
    rows.sort(key=lambda r: -(r[1][-1] or 0))
    for k, v, ort, dg in rows:
        hu = "".join(f"{x:>9.1f}" if x else f"{'-':>9}" for x in v)
        print(f"  {k:16}{hu}{ort:>8.1f}{(f'{dg:+.1f}' if dg is not None else '-'):>9}")

    with (BASE / "kayip_il.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "il",
                "yil",
                "kayitli",
                "gecerli",
                "gitmeyen",
                "gecersiz",
                "kayip",
                "kayip_yuzde",
                "gecersiz_yuzde",
            ]
        )
        for y, k in sorted(il, key=lambda t: (t[1], s.YS.index(t[0]))):
            c = il[(y, k)]
            if not c[K]:
                continue
            w.writerow(
                [
                    k,
                    s.AD.get(y, y),
                    c[K],
                    c[G],
                    c[K] - c[O],
                    c[O] - c[G],
                    c[K] - c[G],
                    round(100 * (c[K] - c[G]) / c[K], 2),
                    round(100 * (c[O] - c[G]) / c[O], 2) if c[O] else "",
                ]
            )
    print("\n-> kayip_il.csv")


if __name__ == "__main__":
    main()
