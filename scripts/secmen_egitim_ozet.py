"""Women voters by education, per district, from the 2023 voter profile reports.

Columns are read from each district's own header rather than by position: a district
where a category has no one in it is served without that column, so the tenth cell is
"Doktora" in one district and "Bilinmeyen" in the next. Summing by position mixes them
and nothing in the file says so.

Run:  uv run python scripts/secmen_egitim_ozet.py [yil]
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

HAM = pathlib.Path("C:/veri-ham/secim/profil/secmen")

UNI = ("Yüksekokul", "Yüksek lisans", "Doktora")
NONE_LITERATE = "Okuma yazma  bilmeyen"


def cells(row: str) -> list[str]:
    return [
        re.sub("<[^>]+>", "", c).replace("&nbsp;", " ").strip()
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
    ]


def number(text: str) -> float:
    text = text.replace(".", "").replace(",", ".")
    return 0.0 if text in ("-", "") else float(text)


def read(path: pathlib.Path) -> dict[str, dict[str, float]]:
    """{district: {education label: women}} — labels as that district's header wrote them."""
    html = path.read_bytes().decode("iso-8859-9", "replace")
    out: dict[str, dict[str, float]] = collections.defaultdict(
        lambda: collections.defaultdict(float)
    )
    district, header = None, []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
        seen = [c for c in cells(row) if c]
        if len(seen) >= 6 and "Okuma yazma" in " ".join(seen[:3]):
            district, header = seen[0], seen[1:]
            continue
        if not district:
            continue
        values = None
        if seen and seen[0] == "Kadın":
            values = seen[1:]
        elif len(seen) > 2 and seen[1] == "Kadın":
            values = seen[2:]
        if values and len(values) == len(header):
            for label, value in zip(header, values):
                out[district][label] += number(value)
    return out


def main(year: str = "2023") -> None:
    rows = []
    for path in sorted(HAM.glob(f"{year}__yas_grubu__egitim_durumu__*.html")):
        province = path.stem.split("__")[-1]
        for district, byedu in read(path).items():
            total = byedu.get("Toplam", 0.0)
            if total < 10:
                continue
            uni = sum(v for k, v in byedu.items() if any(u in k for u in UNI))
            illiterate = sum(
                v for k, v in byedu.items() if k.startswith("Okuma yazma") and "bilmeyen" in k
            )
            rows.append((district, province, total, illiterate, uni))

    total = sum(r[2] for r in rows)
    print(f"ilce: {len(rows)}  kadin secmen: {int(total):,}")
    print(
        f"TR — okuma yazma bilmeyen %{100 * sum(r[3] for r in rows) / total:.2f}"
        f" | universite %{100 * sum(r[4] for r in rows) / total:.2f}"
    )

    def show(title, key, rows_, count=15):
        print(f"\n=== {title} ===")
        for d, p, t, i, u in sorted(rows_, key=key)[:count]:
            print(f"{d:22} {p:15} {100 * key.pay(d, p, t, i, u):6.2f}%  {int(key.num(i, u)):>8,} / {int(t):>9,}")

    for title, pick in (("UNIVERSITE MEZUNU KADIN — EN YUKSEK", 4), ("EN DUSUK", 4)):
        pass  # printed below with explicit loops

    uni_sorted = sorted(rows, key=lambda r: -100 * r[4] / r[2])
    print("\n=== UNIVERSITE MEZUNU KADIN (yuksekokul/fakulte + y.lisans + doktora) — EN YUKSEK 15 ===")
    for d, p, t, i, u in uni_sorted[:15]:
        print(f"{d:22} {p:15} {100 * u / t:6.2f}%  {int(u):>8,} / {int(t):>9,}")
    print("\n=== EN DUSUK 15 ===")
    for d, p, t, i, u in uni_sorted[-15:]:
        print(f"{d:22} {p:15} {100 * u / t:6.2f}%  {int(u):>8,} / {int(t):>9,}")

    ill_sorted = sorted(rows, key=lambda r: -100 * r[3] / r[2])
    print("\n=== OKUMA YAZMA BILMEYEN KADIN — EN YUKSEK 15 ===")
    for d, p, t, i, u in ill_sorted[:15]:
        print(f"{d:22} {p:15} {100 * i / t:6.2f}%  {int(i):>8,} / {int(t):>9,}")


if __name__ == "__main__":
    main(*sys.argv[1:])
