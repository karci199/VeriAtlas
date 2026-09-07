"""What moves the vote: one candidate's share against the things a neighbourhood is.

Three readings, deliberately in this order, because each one takes something away from the
one before it:

  1. **tek tek** — every predictor on its own. Flattering and misleading: income and
     education are nearly the same variable here, and both partly stand for "which region
     is this".
  2. **birlikte** — all of them at once, standardised, so the coefficients can be compared
     with each other. What is left of income once education is in the model?
  3. **ilçe içi** — the same regression after every variable is measured against its own
     district's mean. Geography is then held still and the question becomes "between two
     neighbourhoods of the same district, what predicts the difference?"

Weighted by valid votes throughout. R² is reported so the reader can see how much is
explained rather than only what is significant — with fifty thousand settlements
everything is significant.

Ecological: this describes settlements, not voters.

Run:  uv run python scripts/oy_belirleyici.py [cb2023t1] [--aday=Erdoğan]
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
DEM = HAM / "endeksa" / "demography"
TILES = ROOT / "public" / "tiles"

ADAY_PARCA = {
    "Erdoğan": "ERDO",
    "Kılıçdaroğlu": "KILI",
    "Oğan": "SİNAN",
}

DEGISKENLER = [
    ("hane geliri", "gelir"),
    ("lisans payı", "lisans"),
    ("okuma-yazma yok", "okumaz"),
    ("65+ payı", "yasli"),
    ("0-14 payı", "cocuk"),
    ("hane büyüklüğü", "hane_kisi"),
    ("nüfus yoğunluğu (log)", "yogunluk"),
    ("erkek payı", "erkek"),
]


def veri(vote: str) -> tuple[list[dict], list[str]]:
    oylar: dict[str, dict] = {}
    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area_id, row in json.loads(path.read_text(encoding="utf-8")).items():
            if area_id.count("-") == 3:
                oylar[area_id] = row

    rows: list[dict] = []
    for path in sorted(DEM.glob("TR-*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ident, record in dump.items():
            dem = record.get("demography") or {}
            nufus = dem.get("PopulationTotal") or 0
            hane = dem.get("HouseholdCount") or 0
            gelir = dem.get("HouseIncome") or 0
            egitim = dem.get("EducationTotal") or 0
            oy = oylar.get(f"{path.stem}-{ident}")
            if not (nufus and hane and gelir and egitim and oy):
                continue
            gecerli = oy.get("g") or sum(oy.get("v", {}).values())
            if gecerli < 100:
                continue
            cocuk = sum(
                dem.get(f"Age_{a}_{b}_Total") or 0 for a, b in (("0", "4"), ("5", "9"), ("10", "14"))
            )
            paylar = {}
            for ad, parca in ADAY_PARCA.items():
                paylar[ad] = sum(
                    v for k, v in oy.get("v", {}).items() if parca in k.upper()
                ) / gecerli
            rows.append(
                {
                    "ilce": path.stem,
                    "agirlik": gecerli,
                    "gelir": gelir,
                    "lisans": (dem.get("EduLicenseDegree") or 0) / egitim,
                    "okumaz": (dem.get("EduNonLiterated") or 0) / egitim,
                    "yasli": (dem.get("Age_65_Total") or 0) / nufus,
                    "cocuk": cocuk / nufus,
                    "hane_kisi": nufus / hane,
                    "yogunluk": np.log10(max(dem.get("PopulationDensity") or 1, 1)),
                    "erkek": (dem.get("PopulationMale") or 0) / nufus,
                    **paylar,
                }
            )
    return rows, list(ADAY_PARCA)


def standartla(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    ortalama = np.average(x, weights=w)
    sapma = np.sqrt(np.average((x - ortalama) ** 2, weights=w))
    return (x - ortalama) / sapma if sapma else x * 0


def regresyon(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """Weighted least squares with an intercept; returns (coefficients, R²)."""
    A = np.column_stack([np.ones(len(y)), X])
    W = w / w.sum()
    beta = np.linalg.lstsq(A * np.sqrt(W)[:, None], y * np.sqrt(W), rcond=None)[0]
    tahmin = A @ beta
    ort = np.average(y, weights=w)
    ss_res = np.average((y - tahmin) ** 2, weights=w)
    ss_tot = np.average((y - ort) ** 2, weights=w)
    return beta[1:], 1 - ss_res / ss_tot if ss_tot else float("nan")


def ilce_ici(rows: list[dict], alanlar: list[str]) -> list[dict]:
    """Every value measured against its own district's vote-weighted mean."""
    ortalama: dict[str, dict] = {}
    for row in rows:
        acc = ortalama.setdefault(row["ilce"], {"w": 0.0, **{a: 0.0 for a in alanlar}})
        acc["w"] += row["agirlik"]
        for a in alanlar:
            acc[a] += row[a] * row["agirlik"]
    out = []
    for row in rows:
        acc = ortalama[row["ilce"]]
        if acc["w"] < 2000:
            continue
        out.append({"agirlik": row["agirlik"], **{a: row[a] - acc[a] / acc["w"] for a in alanlar}})
    return out


def main(argv: list[str]) -> None:
    vote = next((a for a in argv if not a.startswith("--")), "cb2023t1")
    aday = next((a.split("=")[1] for a in argv if a.startswith("--aday=")), "Erdoğan")
    rows, adaylar = veri(vote)
    print(
        f"{vote} · {aday} payı · {len(rows):,} yerleşim · "
        f"{sum(r['agirlik'] for r in rows):,.0f} geçerli oy"
    )
    if len(rows) < 100:
        print("çok az eşleşme — Endeksa çekimi ilerleyince tekrar çalıştır")
        return

    alanlar = [alan for _, alan in DEGISKENLER]
    w = np.array([r["agirlik"] for r in rows], dtype=float)
    y = np.array([r[aday] for r in rows], dtype=float)
    X = {alan: np.array([r[alan] for r in rows], dtype=float) for alan in alanlar}

    print("\n=== 1) Tek tek (her değişken yalnız başına)")
    print(f"{'Değişken':26}{'korelasyon':>12}{'R²':>8}")
    tekil = []
    for etiket, alan in DEGISKENLER:
        xs = standartla(X[alan], w)
        _, r2 = regresyon(xs[:, None], y, w)
        korelasyon = np.average(xs * standartla(y, w), weights=w)
        tekil.append((abs(korelasyon), etiket, korelasyon, r2))
        print(f"{etiket:26}{korelasyon:>+12.3f}{r2:>8.3f}")

    print("\n=== 2) Hepsi birlikte (standartlaştırılmış katsayılar)")
    Xs = np.column_stack([standartla(X[alan], w) for alan in alanlar])
    beta, r2 = regresyon(Xs, standartla(y, w), w)
    for (etiket, _), katsayi in sorted(
        zip(DEGISKENLER, beta, strict=False), key=lambda t: -abs(t[1])
    ):
        print(f"{etiket:26}{katsayi:>+12.3f}")
    print(f"{'toplam açıklanan (R²)':26}{r2:>12.3f}")

    print("\n=== 3) Aynı ilçenin mahalleleri arasında (coğrafya sabit)")
    fark = ilce_ici(rows, [*alanlar, aday])
    wf = np.array([r["agirlik"] for r in fark], dtype=float)
    yf = standartla(np.array([r[aday] for r in fark], dtype=float), wf)
    Xf = np.column_stack([standartla(np.array([r[alan] for r in fark]), wf) for alan in alanlar])
    beta_f, r2_f = regresyon(Xf, yf, wf)
    for (etiket, _), katsayi in sorted(
        zip(DEGISKENLER, beta_f, strict=False), key=lambda t: -abs(t[1])
    ):
        print(f"{etiket:26}{katsayi:>+12.3f}")
    print(f"{'toplam açıklanan (R²)':26}{r2_f:>12.3f}")

    print("\n=== Değişkenler birbiriyle ne kadar örtüşüyor")
    for i, (etiket_i, alan_i) in enumerate(DEGISKENLER):
        for etiket_j, alan_j in DEGISKENLER[i + 1 :]:
            ortak = np.average(
                standartla(X[alan_i], w) * standartla(X[alan_j], w), weights=w
            )
            if abs(ortak) >= 0.6:
                print(f"  {etiket_i} × {etiket_j}: {ortak:+.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
