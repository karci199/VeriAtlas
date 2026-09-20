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

from functools import cache
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


#: Districts, kept in their own file: today's 973 with the columns that will carry their
#: history (`valid_from` / `valid_to`), which the main registry has no use for.
DISTRICTS_PATH = Path(__file__).parent / "data" / "areas_tr_districts.csv"


def load_districts() -> pl.DataFrame:
    """Read the district registry: `area_id`, `name_tr`, `parent_id`, validity, source."""
    return pl.read_csv(DISTRICTS_PATH)


#: Neighbourhoods, derived from the MEDAS exports rather than published as a list — see
#: `scripts/build_neighbourhood_registry.py`. Kept apart from the districts for the same
#: reason they are kept apart from the provinces: different columns, different provenance,
#: and there are two orders of magnitude more of them.
NEIGHBOURHOODS_PATH = Path(__file__).parent / "data" / "areas_tr_neighbourhoods.csv"


def load_neighbourhoods() -> pl.DataFrame:
    """Read the neighbourhood registry: ids, current name, district, MEDAS code."""
    return pl.read_csv(NEIGHBOURHOODS_PATH)


#: `scripts/build_village_registry.py`. Separate from the neighbourhoods because they are
#: a different kind of place with a different provenance — and because they only exist in
#: the 51 provinces law 6360 left them in.
VILLAGES_PATH = Path(__file__).parent / "data" / "areas_tr_villages.csv"


def load_villages() -> pl.DataFrame:
    """Read the village registry: ids, current name, district, bucak, MEDAS code."""
    return pl.read_csv(VILLAGES_PATH)


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


#: Province names published sources write differently from the registry. Four of them, and
#: all four are older or shortened names rather than misspellings: `İçel` is what Mersin
#: was called until 2002, `K.Maraş` and `Afyon` are the short forms, `Agri` is `Ağrı` with
#: the Turkish letters dropped. They are listed one by one rather than normalised away:
#: two spellings of one province silently becoming two areas is what `resolve` exists to
#: prevent, and an alias is a decision, not a transformation.
PROVINCE_ALIASES = {
    "Afyon": "Afyonkarahisar",
    "Agri": "Ağrı",
    "İçel": "Mersin",
    "K.Maraş": "Kahramanmaraş",
}

#: District names the same way. Two kinds: the circumflex the registry keeps and sources
#: drop (`Kâhta`, `Lâpseki`, `Devrekâni`, `Lâçin`), and the space the registry keeps and
#: sources close up (`Gazi Osmanpaşa`, `Marmara Ereğlisi`, `Oniki Şubat`, `19 Mayıs`).
#: Keyed by (province id, source's spelling): a district name is only unique inside its
#: province.
#:
#: Three sources that share nothing else — BİM's store finder, Migros' dropdown and
#: TİTCK's pharmacy register — produce exactly this list and no other exception between
#: them, which is why it lives here rather than in any one adapter.
DISTRICT_ALIASES = {
    ("TR-02", "Kahta"): "Kâhta",
    ("TR-16", "MustafaKemalPaşa"): "Mustafakemalpaşa",
    ("TR-17", "Lapseki"): "Lâpseki",
    ("TR-19", "Laçin"): "Lâçin",
    ("TR-34", "Gaziosmanpaşa"): "Gazi Osmanpaşa",
    ("TR-37", "Devrekani"): "Devrekâni",
    ("TR-46", "Onikişubat"): "Oniki Şubat",
    ("TR-55", "19 mayıs"): "19 Mayıs",
    ("TR-59", "Marmaraereğlisi"): "Marmara Ereğlisi",
    ("TR-71", "Bahşılı"): "Bahşili",
}

#: What published sources call the central district of a province that has one. The
#: registry names it after the province itself — `Bolu`, `Afyonkarahisar` — and never
#: carries a district called `Merkez`. The rule is safe because the 30 provinces with no
#: district of their own name are exactly the 30 metropolitan ones, and those have no
#: `Merkez` either: their whole territory is divided into named districts.
CENTRE = "Merkez"


@cache
def _district_lookup() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """(province name -> id, (province id, district name) -> id), read once."""
    registry = load_areas().filter(pl.col("area_level") == "province")
    provinces = dict(zip(registry["name_tr"], registry["area_id"], strict=True))
    districts = {
        (row["parent_id"], row["name_tr"]): row["area_id"]
        for row in load_districts().iter_rows(named=True)
    }
    return provinces, districts


def resolve_district(province: str, district: str) -> str:
    """The area id of a district published as (province name, district name).

    Raises on anything it cannot place. That is the point: a coordinate that falls outside
    a boundary is a visible failure — something counts it and a threshold trips — but a
    *name* that fails to match is invisible. The district simply shows no pharmacies, and
    that reads as a fact about the country rather than a gap in the parsing.
    """
    published = province.strip()
    province_id = _district_lookup()[0].get(PROVINCE_ALIASES.get(published, published))
    if province_id is None:
        raise KeyError(f"kayıt defterinde olmayan il: {province!r}")
    name = district.strip()
    if name == CENTRE:
        name = PROVINCE_ALIASES.get(published, published)
    name = DISTRICT_ALIASES.get((province_id, name), name)
    area = _district_lookup()[1].get((province_id, name))
    if area is None:
        raise KeyError(f"kayıt defterinde olmayan ilçe: {published} / {district!r}")
    return area
