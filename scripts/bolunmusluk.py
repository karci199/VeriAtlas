"""How divided the vote is, at every level: province, district, semt, neighbourhood.

Measured as the effective number of parties (Laakso-Taagepera): 1 / Σ payᵢ². Two parties
at 50-50 give 2.0; one party at 100% gives 1.0. It answers "how many parties does this
place effectively have", which is what "divided" means here — a place where one party
takes 45% and another 44% is more divided than one where a party takes 60% and eight
others split the rest.

Alliance columns are dropped before the shares are taken: the report carries both the
parties and the alliances they belong to, and counting both counts the same vote twice.

Run:  uv run python scripts/bolunmusluk.py [mv2023] [--min=1000] [--n=15]
"""

from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
TILES = ROOT / "public" / "tiles"

ITTIFAK = "İTTİFAK"


def enp(votes: dict[str, float]) -> tuple[float, list[tuple[str, float]]]:
    """Effective number of parties, and the shares it was computed from."""
    parties = {k: v for k, v in votes.items() if ITTIFAK not in k.upper() and v > 0}
    total = sum(parties.values())
    if total <= 0:
        return 0.0, []
    shares = sorted(((k, v / total) for k, v in parties.items()), key=lambda kv: -kv[1])
    return 1 / sum(s * s for _, s in shares), shares


def main(argv: list[str]) -> None:
    vote = next((a for a in argv if not a.startswith("--")), "mv2023")
    floor = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 1000))
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 15))

    ilce_path = TILES / f"secim-{vote}-ilce.json"
    ilceler = json.loads(ilce_path.read_text(encoding="utf-8"))

    iller: dict[str, dict] = collections.defaultdict(
        lambda: {"k": 0.0, "v": collections.Counter()}
    )
    ilce_rows, mahalle_rows = [], []
    for area, row in ilceler.items():
        il = "-".join(area.split("-")[:2])
        iller[il]["k"] += row.get("k", 0)
        iller[il]["v"].update(row.get("v", {}))
        if row.get("k", 0) >= floor:
            ilce_rows.append((row.get("ad", area), area, row))

    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area, row in json.loads(path.read_text(encoding="utf-8")).items():
            if row.get("k", 0) >= floor:
                mahalle_rows.append((row.get("ad", area), area, row))

    adlar = json.loads((TILES / "il-adlari.json").read_text(encoding="utf-8"))

    def goster(baslik, rows, ad_fn):
        hesap = []
        for item in rows:
            sayi, paylar = enp(item[-1].get("v", {}))
            if sayi:
                hesap.append((sayi, ad_fn(item), item[-1].get("k", 0), paylar))
        hesap.sort(reverse=True)
        print(f"\n=== {baslik} — EN BOLUNMUS {n} ===")
        for sayi, ad, kayitli, paylar in hesap[:n]:
            ilk = "  ".join(f"{p} {100 * s:.0f}%" for p, s in paylar[:3])
            print(f"{ad[:34]:34} {sayi:5.2f}  {int(kayitli):>9,}  {ilk}")
        print("--- EN TEK SESLI 5 ---")
        for sayi, ad, kayitli, paylar in hesap[-5:][::-1]:
            ilk = "  ".join(f"{p} {100 * s:.0f}%" for p, s in paylar[:2])
            print(f"{ad[:34]:34} {sayi:5.2f}  {int(kayitli):>9,}  {ilk}")

    goster("IL", [(k, k, {"v": v["v"], "k": v["k"]}) for k, v in iller.items()],
           lambda i: adlar.get(i[0], i[0]) if isinstance(adlar.get(i[0], ""), str)
           else i[0])
    goster("ILCE", ilce_rows, lambda i: f"{i[0]} ({i[1]})")
    goster("MAHALLE", mahalle_rows, lambda i: f"{i[0]} ({i[1].split('-')[1]})")


if __name__ == "__main__":
    main(sys.argv[1:])
