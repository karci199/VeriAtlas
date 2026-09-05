"""Simulate a mixed electoral system on the 2023 parliamentary vote.

System: 100 national seats (Hare largest remainder, no threshold, parties only) plus
50 regions x 10 seats. Regions are built from whole districts (ilçe), contiguous,
weighted by registered voters, province borders ignored, size within +-TOL of the
national average. Many random plans are generated (spanning-tree recursive bisection),
and seats are reported as median and range across plans, for three regional formulas.

Usage: python scripts/simulate_regions_2023.py [--plans N] [--tol 0.07] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.strtree import STRtree

ELECTIONS = Path("C:/veri/raw/tuik_secim_ilce/secim_ilce.csv")
GEO_DIR = Path("C:/veri/public/geo/districts")
AREAS = Path("C:/veri/public/areas.geojson")
OUT_DIR = Path("C:/veri/raw/derived")
YEAR = "2023"
REGIONS = 50
REGION_SEATS = 10
NATIONAL_SEATS = 100

COUNT_MEASURES = {
    "Kayıtlı seçmen sayısı",
    "Oy kullanan seçmen sayısı",
    "Geçerli oy sayısı",
    "Sandık sayısı",
}
INDEPENDENT = "BĞMZ"
ALLIANCE_JOINT = {  # joint-list votes cast for the alliance only, split to members by their district votes
    "CUMHUR İTTİFAKI": ("AK PARTİ", "MHP", "BÜYÜK BİRLİK", "YENİDEN REFAH"),
    "MİLLET İTTİFAKI": ("CHP", "İYİ PARTİ"),
}
SUBTOTAL_ROWS = {"il/ilcemerkezi", "belde/koy"}
CIRCLE_ALIASES = {"k_maras": "kahramanmaras"}
DISTRICT_ALIASES = {  # (province code, normalised report name) -> normalised geo name
}
# Islands with no land neighbour: attach to the district their ferry serves.
ISLAND_LINKS = {
    "adalar": ("TR-34", "kartal"),
    "bozcaada": ("TR-17", "ezine"),
    "gokceada": ("TR-17", "eceabat"),
    "marmara": ("TR-10", "erdek"),
}
# Bridges / ferries across straits: (province, district) pairs.
STRAIT_LINKS = [
    (("TR-34", "sariyer"), ("TR-34", "beykoz")),
    (("TR-34", "besiktas"), ("TR-34", "uskudar")),
    (("TR-34", "eminonu"), ("TR-34", "uskudar")),
    (("TR-17", "gelibolu"), ("TR-17", "lapseki")),
    (("TR-17", "eceabat"), ("TR-17", "canakkale")),
]
ACTUAL_2023 = {
    "AK PARTİ": 268,
    "CHP": 169,
    "YEŞİL SOL PARTİ": 61,
    "MHP": 50,
    "İYİ PARTİ": 43,
    "YRP": 5,
    "TİP": 4,
}


def norm(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("ı", "i")
    return text.replace(" ", "")


# --------------------------------------------------------------------------- data
def load_geometry():
    """{area_id: dict(name, province, geom)} for every district."""
    out = {}
    for path in sorted(GEO_DIR.glob("TR-*.geojson")):
        for f in json.load(path.open(encoding="utf-8"))["features"]:
            p = f["properties"]
            out[p["area_id"]] = {
                "name": p["name_tr"],
                "province": p["parent_id"],
                "geom": shape(f["geometry"]),
            }
    return out


def province_codes():
    """{normalised province name: TR-XX}."""
    out = {}
    for f in json.load(AREAS.open(encoding="utf-8"))["features"]:
        p = f["properties"]
        if (
            p.get("area_level", "province") == "province"
            or p["area_id"].count("-") == 1
        ):
            out[norm(p.get("name_tr") or p.get("name"))] = p["area_id"]
    return out


def load_votes(geo):
    """{area_id: {'registered': n, 'valid': n, 'votes': {party: n}}} for YEAR."""
    codes = province_codes()
    by_prov_name = defaultdict(dict)
    for area_id, d in geo.items():
        by_prov_name[d["province"]][norm(d["name"])] = area_id
    rows = defaultdict(lambda: {"registered": 0, "valid": 0, "votes": defaultdict(int)})
    unmatched = set()
    with ELECTIONS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["yil"] != YEAR:
                continue
            prov = re.sub(r"_\d+$", "", r["cevre"])
            prov = CIRCLE_ALIASES.get(prov, prov)
            code = codes.get(norm(prov))
            name = norm(r["birim"])
            if code is None or "toplam" in name or name in SUBTOTAL_ROWS:
                continue
            name = name.removesuffix("merkez")
            name = DISTRICT_ALIASES.get((code, name), name)
            area_id = by_prov_name[code].get(name)
            if area_id is None:
                unmatched.add((code, r["birim"]))
                continue
            rec = rows[area_id]
            m, v = r["olcut"], int(r["deger"])
            if m == "Kayıtlı seçmen sayısı":
                rec["registered"] += v
            elif m == "Geçerli oy sayısı":
                rec["valid"] += v
            elif m not in COUNT_MEASURES:
                rec["votes"][m] += v
    if unmatched:
        raise SystemExit(f"unmatched districts: {sorted(unmatched)}")
    for rec in rows.values():
        for joint, members in ALLIANCE_JOINT.items():
            pool = rec["votes"].pop(joint, 0)
            base = {m: rec["votes"].get(m, 0) for m in members}
            tot = sum(base.values())
            if pool and tot:
                for m, v in base.items():
                    rec["votes"][m] += round(pool * v / tot)
    return dict(rows)


def build_adjacency(geo, votes):
    ids = [i for i in geo if i in votes]
    geoms = [geo[i]["geom"] for i in ids]
    tree = STRtree(geoms)
    adj = {i: set() for i in ids}
    for a_idx, a in enumerate(ids):
        for b_idx in tree.query(geoms[a_idx]):
            b = ids[b_idx]
            if b <= a:
                continue
            g1, g2 = geoms[a_idx], geoms[b_idx]
            if g1.intersects(g2) and (
                g1.touches(g2) or g1.intersection(g2).length > 0 or g1.overlaps(g2)
            ):
                adj[a].add(b)
                adj[b].add(a)
    by_name = {(geo[i]["province"], norm(geo[i]["name"])): i for i in ids}
    links = list(STRAIT_LINKS)
    for island, target in ISLAND_LINKS.items():
        src = next(((p, n) for (p, n) in by_name if n == island), None)
        if src:
            links.append((src, target))
    for a, b in links:
        if a in by_name and b in by_name:
            adj[by_name[a]].add(by_name[b])
            adj[by_name[b]].add(by_name[a])
    return adj


def components(adj):
    seen, comps = set(), []
    for start in adj:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            n = stack.pop()
            comp.append(n)
            for m in adj[n]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        comps.append(comp)
    return comps


# --------------------------------------------------------------------------- partition
def random_spanning_tree(nodes, adj, rng):
    """Random tree via randomised Prim; returns children map and root."""
    nodes = set(nodes)
    root = rng.choice(sorted(nodes))
    in_tree = {root}
    frontier = [(root, m) for m in adj[root] if m in nodes]
    children = defaultdict(list)
    while frontier:
        k = rng.randrange(len(frontier))
        frontier[k], frontier[-1] = frontier[-1], frontier[k]
        a, b = frontier.pop()
        if b in in_tree:
            continue
        in_tree.add(b)
        children[a].append(b)
        frontier.extend((b, m) for m in adj[b] if m in nodes and m not in in_tree)
    if len(in_tree) != len(nodes):
        return None, None
    return children, root


def subtree_weights(children, root, weight):
    order, stack = [], [root]
    while stack:
        n = stack.pop()
        order.append(n)
        stack.extend(children.get(n, ()))
    w = {}
    for n in reversed(order):
        w[n] = weight[n] + sum(w[c] for c in children.get(n, ()))
    return w, order


def peel_region(nodes, k, adj, weight, unit, tol, rng, attempts=40):
    """Cut one region (within tolerance) off `nodes`, leaving a contiguous remainder
    whose weight still fits k-1 regions within tolerance. Returns (region, rest)."""
    lo, hi = unit * (1 - tol), unit * (1 + tol)
    lo2, hi2 = (k - 1) * unit * (1 - tol), (k - 1) * unit * (1 + tol)
    for _ in range(attempts):
        children, root = random_spanning_tree(nodes, adj, rng)
        if children is None:
            return None
        w, _ = subtree_weights(children, root, weight)
        total = w[root]
        cands = [
            n
            for n, wn in w.items()
            if n != root and lo <= wn <= hi and lo2 <= total - wn <= hi2
        ]
        if not cands:
            continue
        cut = rng.choice(cands)
        region, stack = set(), [cut]
        while stack:
            n = stack.pop()
            region.add(n)
            stack.extend(children.get(n, ()))
        return region, set(nodes) - region
    return None


def partition(nodes, k, adj, weight, unit, tol, rng):
    """Peel regions one at a time; None if a step finds no admissible cut."""
    regions, rest = [], set(nodes)
    while k > 1:
        res = peel_region(rest, k, adj, weight, unit, tol, rng)
        if res is None:
            return None
        region, rest = res
        regions.append(region)
        k -= 1
    regions.append(rest)
    return regions


def make_plan(adj, weight, unit, tol, rng, max_tries=200):
    nodes = list(adj)
    for _ in range(max_tries):
        plan = partition(nodes, REGIONS, adj, weight, unit, tol, rng)
        if plan is not None:
            return plan
    raise SystemExit("could not build a plan within tolerance; loosen --tol")


# --------------------------------------------------------------------------- allocation
def hare_lr(votes: dict[str, int], seats: int) -> dict[str, int]:
    total = sum(votes.values())
    if total == 0:
        return {}
    quota = total / seats
    base = {p: int(v // quota) for p, v in votes.items()}
    left = seats - sum(base.values())
    for p in sorted(votes, key=lambda p: votes[p] % quota, reverse=True)[:left]:
        base[p] += 1
    return {p: s for p, s in base.items() if s}


def divisor(
    votes: dict[str, int], seats: int, step: float, first: float = 1.0
) -> dict[str, int]:
    out = defaultdict(int)
    for _ in range(seats):
        best = max(
            votes,
            key=lambda p: votes[p] / (first if out[p] == 0 else 1 + step * out[p]),
        )
        out[best] += 1
    return dict(out)


def dhondt(votes, seats):
    return divisor(votes, seats, 1.0)


def sainte_lague(votes, seats):
    return divisor(votes, seats, 2.0)


FORMULAS = {"Hare artık": hare_lr, "Sainte-Laguë": sainte_lague, "D'Hondt": dhondt}


def region_votes(plan, votes):
    out = []
    for region in plan:
        tally = defaultdict(int)
        for d in region:
            for p, v in votes[d]["votes"].items():
                tally[p] += v
        out.append(tally)
    return out


def seats_for_plan(plan, votes):
    result = {}
    for name, fn in FORMULAS.items():
        total = defaultdict(int)
        for tally in region_votes(plan, votes):
            party_votes = {p: v for p, v in tally.items() if p != INDEPENDENT and v > 0}
            for p, s in fn(party_votes, REGION_SEATS).items():
                total[p] += s
        result[name] = dict(total)
    return result


# --------------------------------------------------------------------------- output
def plan_geojson(plan, geo, votes, weight):
    from shapely.ops import unary_union

    feats = []
    for i, region in enumerate(sorted(plan, key=lambda r: min(r)), start=1):
        provs = defaultdict(int)
        for d in region:
            provs[geo[d]["province"]] += weight[d]
        main = sorted(provs, key=provs.get, reverse=True)
        geom = unary_union([geo[d]["geom"] for d in region]).simplify(0.002)
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "region": i,
                    "registered": sum(weight[d] for d in region),
                    "districts": len(region),
                    "provinces": main,
                    "seats": REGION_SEATS,
                },
                "geometry": json.loads(json.dumps(geom.__geo_interface__)),
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", type=int, default=100)
    ap.add_argument("--tol", type=float, default=0.07)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    geo = load_geometry()
    votes = load_votes(geo)
    missing = [i for i in geo if i not in votes]
    print(f"districts with votes: {len(votes)}; geometry without votes: {len(missing)}")
    adj = build_adjacency(geo, votes)
    comps = components(adj)
    if len(comps) > 1:
        for c in comps[1:]:
            print("isolated:", [geo[d]["name"] for d in c])
        raise SystemExit("graph not connected; add ISLAND_LINKS")
    weight = {d: votes[d]["registered"] for d in adj}
    unit = sum(weight.values()) / REGIONS
    print(
        f"registered total {sum(weight.values()):,}; region target {unit:,.0f} +-{args.tol:.0%}"
    )

    national = defaultdict(int)
    for d in votes.values():
        for p, v in d["votes"].items():
            if p != INDEPENDENT:
                national[p] += v
    national_total = sum(national.values())
    national_seats = hare_lr(dict(national), NATIONAL_SEATS)

    rng = random.Random(args.seed)
    plans, per_plan = [], []
    for n in range(args.plans):
        plan = make_plan(adj, weight, unit, args.tol, rng)
        plans.append(plan)
        per_plan.append(seats_for_plan(plan, votes))
        if (n + 1) % 10 == 0:
            print(f"  {n + 1} plans")

    parties = sorted(national, key=national.get, reverse=True)
    summary = {}
    for name in FORMULAS:
        summary[name] = {}
        for p in parties:
            vals = sorted(r[name].get(p, 0) for r in per_plan)
            summary[name][p] = {
                "min": vals[0],
                "p5": vals[len(vals) // 20],
                "median": vals[len(vals) // 2],
                "p95": vals[-max(1, len(vals) // 20)],
                "max": vals[-1],
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(
        {
            "year": YEAR,
            "regions": REGIONS,
            "region_seats": REGION_SEATS,
            "national_seats": NATIONAL_SEATS,
            "tolerance": args.tol,
            "region_target": round(unit),
            "plans": args.plans,
            "national_votes": dict(national),
            "national_seats_hare": national_seats,
            "regional": summary,
            "actual_2023": ACTUAL_2023,
        },
        (OUT_DIR / "simulation_2023_summary.json").open("w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    json.dump(
        plan_geojson(plans[0], geo, votes, weight),
        (OUT_DIR / "regions_2023_plan.geojson").open("w", encoding="utf-8"),
        ensure_ascii=False,
    )

    print(f"\n{'Parti':<14}{'Oy %':>7}{'TR 100':>8}", end="")
    for name in FORMULAS:
        print(f"{name + ' 500':>22}", end="")
    print(f"{'Toplam (Hare)':>15}{'Gerçek':>8}")
    for p in parties:
        share = national[p] / national_total
        if share < 0.003 and national_seats.get(p, 0) == 0:
            continue
        print(f"{p:<14}{share:>7.1%}{national_seats.get(p, 0):>8}", end="")
        for name in FORMULAS:
            s = summary[name][p]
            print(f"{s['median']:>10} [{s['p5']:>3}-{s['p95']:>3}]   ", end="")
        tot = national_seats.get(p, 0) + summary["Hare artık"][p]["median"]
        print(f"{tot:>15}{ACTUAL_2023.get(p, 0):>8}")
    print()
    for name in FORMULAS:
        gall, maj = [], 0
        for r in per_plan:
            tot = {p: national_seats.get(p, 0) + r[name].get(p, 0) for p in parties}
            gall.append(
                (
                    0.5
                    * sum(
                        (national[p] / national_total - tot[p] / 600) ** 2
                        for p in parties
                    )
                    * 1e4
                )
                ** 0.5
            )
            maj += max(tot.values()) > 300
        gall.sort()
        print(
            f"{name:<14} Gallagher ortanca {gall[len(gall) // 2]:.2f}  tek parti çoğunluğu: {maj}/{len(per_plan)} plan"
        )
    actual_g = (
        0.5
        * sum(
            (national[p] / national_total - ACTUAL_2023.get(p, 0) / 600) ** 2
            for p in parties
        )
        * 1e4
    ) ** 0.5
    print(f"{'Gerçek 2023':<14} Gallagher {actual_g:.2f}")
    all_sizes = [sum(weight[d] for d in r) for plan in plans for r in plan]
    print(f"region size over all plans: {min(all_sizes):,} - {max(all_sizes):,}")
    sizes = [sum(weight[d] for d in r) for r in plans[0]]
    print(
        f"\nexample plan: region size {min(sizes):,} - {max(sizes):,}; written to {OUT_DIR}"
    )


if __name__ == "__main__":
    main()
