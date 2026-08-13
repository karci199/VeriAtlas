"""Area registry: the names a source publishes, resolved to stable identifiers.

No source we have publishes a code — TUIK reports carry only the Turkish name. So the
name has to be the lookup key, which makes an unmatched name the most likely way for
an import to go quietly wrong. `resolve` therefore refuses to guess: an unknown name
raises instead of producing a null id.

Province ids are ISO 3166-2:TR (`TR-34`), the numeric part being the plate code.

This is the first slice of the time-dependent geography registry, and deliberately the
easy half: provinces have been stable since 1989. Districts have not — law 6360 split
them and turned villages into neighbourhoods in 2013 — so district-level areas will
need validity ranges and successor links before they can be loaded (open item 3).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

REGISTRY_PATH = Path(__file__).parent / "data" / "areas_tr.csv"

#: Population per province, used to weight province values into region values. Kept
#: apart from the registry: a name is permanent, a population is an observation with a
#: date on it.
WEIGHTS_PATH = Path(__file__).parent / "data" / "area_weights_tr.csv"

#: Membership, one row per (area, parent, hierarchy). A province sits in two hierarchies
#: at once — a geographic region (Marmara) and a statistical one (TR41 Bursa alt bölgesi)
#: — so a single parent column would force us to drop one of them.
PARENTS_PATH = Path(__file__).parent / "data" / "area_parents_tr.csv"

#: Hand-maintained İBBS membership: TurkiyeAPI carries geographic regions only.
NUTS_PATH = Path(__file__).parent / "data" / "nuts_tr.csv"


def load_areas() -> pl.DataFrame:
    """Read the registry: `area_id`, `area_level`, `name_tr`."""
    return pl.read_csv(REGISTRY_PATH)


def load_parents(hierarchy: str | None = None) -> pl.DataFrame:
    """Read membership: `area_id`, `parent_id`, `hierarchy`."""
    parents = pl.read_csv(PARENTS_PATH)
    if hierarchy is not None:
        parents = parents.filter(pl.col("hierarchy") == hierarchy)
    return parents


def load_weights() -> pl.DataFrame:
    """Read the aggregation weights: `area_id`, `population`, provenance columns."""
    return pl.read_csv(WEIGHTS_PATH)


def resolve(names: list[str], level: str = "province") -> dict[str, str]:
    """Map published names to area ids, raising if any name is unknown.

    Matching ignores surrounding whitespace but nothing else: `Kahramanmaraş` and
    `Maraş` are different strings, and silently accepting either would let two spellings
    of one province become two areas.
    """
    registry = load_areas().filter(pl.col("area_level") == level)
    known = dict(zip(registry["name_tr"], registry["area_id"], strict=True))

    resolved: dict[str, str] = {}
    unknown: list[str] = []
    for name in names:
        stripped = name.strip()
        if stripped in known:
            resolved[name] = known[stripped]
        else:
            unknown.append(name)

    if unknown:
        raise KeyError(
            "unknown "
            + level
            + " name(s), add them to areas_tr.csv or fix the source: "
            + ", ".join(sorted(unknown))
        )

    return resolved
