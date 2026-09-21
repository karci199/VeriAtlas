r"""Place names as sources write them, resolved to registry ids — or refused.

`areas.resolve` matches a name exactly, which is right for a statistical office: TÜİK
writes `Afyonkarahisar` and means the province with that name. Store finders do not. They
write `AFYON`, `İçel`, `K.Maraş`, `ONİKİŞUBAT` and `UŞAK MERKEZ`, and a loader that
accepts any of those by relaxing the comparison will sooner or later accept two different
places as one. This module keeps the strictness and puts the untidiness in one place:
every transformation below is named, bounded, and refuses what it cannot decide.

Measured against three coordinate-less dumps on 2026-09-20 (BİM 916 rows, Migros 973,
Seç Market 2.257), matching by exact name resolved 3.618 of 4.146 rows. What the other
528 were, and what is done about each:

**Provinces renamed before the registry's era** (53 rows). `Afyon` became
Afyonkarahisar in 2004, `İçel` became Mersin in 2002, and `K.Maraş` is an abbreviation
of Kahramanmaraş, not a name. These are a closed list of historical facts, so they live
in `PROVINCE_ALIASES` — not in a fuzzy comparison that would also match `Maraş` to
`Muş`.

**Central districts called `Merkez`** (about 380 rows). This is the interesting one and
it cannot be fixed with a table, because `Merkez` means two different things depending
on the province:

* In a province law 6360 left alone, the central district carries the province's name in
  our registry — Amasya's centre is the district `Amasya`, Bolu's is `Bolu`. A source
  saying `Merkez` there means that district and nothing else, so it resolves.
* In a metropolitan province the central district was **abolished** and split: Kahraman-
  maraş's `Merkez` became `Dulkadiroğlu` and `Oniki Şubat` in 2013, and the registry
  keeps the old one with `valid_to = 2012`. A source saying `Merkez` there is naming a
  place that no longer exists, and there is no honest way to pick one of the halves.
  Those rows are refused, not split, not assigned to the larger half.

The registry holds 22 such abolished `Merkez` districts, which is why this is a rule and
not an oversight to paper over.

**Spacing** (a handful). The registry writes `Oniki Şubat`, Seç Market writes
`ONİKİŞUBAT`. Matching ignores spaces only after an exact match has already failed, so a
real two-word name is never collapsed into a different one-word name by accident.

Nothing here guesses at a nearest match. `district_id` returns `None` and the caller
decides whether an unresolved row is tolerable; adapters that use this must count and
report what they dropped, the way `chain_stores` reports the branches its polygons did
not claim.
"""

from __future__ import annotations

import unicodedata
from functools import cache

import polars as pl

from .areas import load_areas, load_districts

#: Names sources still use for provinces that were renamed, folded like any other key.
#: A closed list of historical renames and one abbreviation — never a similarity rule.
PROVINCE_ALIASES = {
    "afyon": "afyonkarahisar",
    "icel": "mersin",
    "k.maras": "kahramanmaras",
    "kmaras": "kahramanmaras",
    "maras": "kahramanmaras",
    "antep": "gaziantep",
    "urfa": "sanliurfa",
}

#: Districts renamed one-for-one, keyed by province id. A rename is not a split: the
#: territory is unchanged and only the name moved, so the old name resolves onto the new
#: district with nothing lost. Each entry is checked against the registry, which still
#: holds the old district with a `valid_to` — `areas_tr_district_groups.csv` does not
#: link these, because it is built from splits and a pure rename leaves no trace in the
#: population series it reads.
#:
#: Splits deliberately stay out. Kahramanmaraş's `Merkez` has a group in that file
#: (`Dulkadiroğlu` + `Oniki Şubat`), and that is exactly the case where a name cannot be
#: resolved to one district — see `district_id`.
DISTRICT_RENAMES = {
    "TR-34": {"eyup": "eyupsultan"},  # 2018
    "TR-06": {"kazan": "kahramankazan"},  # 2016
}

#: Two spellings of one living district, where the registry picked one and sources use
#: the other. Not renames and not guesses — the same district written differently.
DISTRICT_VARIANTS = {
    "TR-55": {"ondokuzmayis": "19 mayis", "on dokuz mayis": "19 mayis"},
}

#: What a source writes when it means "the central district", in folded form. The
#: province's own name may be stuck on the front (`UŞAK MERKEZ`), which `_centre_wanted`
#: strips before comparing.
CENTRE = {"merkez", "merkez ilce", "il merkezi"}


def fold(name: str | None) -> str:
    """A comparison key: Turkish case rules applied, accents dropped, spacing collapsed.

    The key is deliberately lossy. `Ağrı`, `AGRI` and `agri` all become `agri`, because
    sources write province names in every combination of case and accent and none of
    those is a different place. What it must never do is merge two names that *are*
    different, which is why the loss stops at accents: `Muş` and `Muşkara` keep their
    own keys, and nothing here shortens, truncates or scores similarity.

    `İ` and `I` are mapped with Turkish rules before `lower()` rather than after. With
    full accent folding the end result is the same either way; it is written this way so
    the step stays correct if the accent map is ever narrowed.
    """
    if name is None:
        return ""
    text = str(name).strip().replace("İ", "i").replace("I", "ı").lower()
    for source, target in (
        ("ı", "i"),
        ("ş", "s"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ö", "o"),
        ("ç", "c"),
        ("â", "a"),
        ("î", "i"),
        ("û", "u"),
    ):
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.split())


def tighten(key: str) -> str:
    """The key with spaces and dots removed — `oniki subat` and `onikisubat` as one."""
    return key.replace(" ", "").replace(".", "").replace("-", "")


@cache
def _provinces() -> dict[str, str]:
    registry = load_areas().filter(pl.col("area_level") == "province")
    return {
        fold(row["name_tr"]): row["area_id"] for row in registry.iter_rows(named=True)
    }


@cache
def _districts() -> dict[str, dict[str, str]]:
    """Province id -> {folded current district name: district id}.

    Only districts that still exist: `valid_to` marks the ones law 6360 and its
    predecessors abolished, and resolving a name onto an abolished district would file
    today's store under a place that closed in 2012.
    """
    registry = load_districts().filter(pl.col("valid_to").is_null())
    out: dict[str, dict[str, str]] = {}
    for row in registry.iter_rows(named=True):
        out.setdefault(row["parent_id"], {})[fold(row["name_tr"])] = row["area_id"]
    return out


def province_id(name: str | None) -> str | None:
    """The province's id, or None when the name is not one we know.

    An id passed in comes back out, so a caller that already resolved a province — via
    `province_of_district`, say — can hand it straight to `district_id` without keeping
    a second name lookup alongside it.
    """
    if name in _provinces().values():
        return name
    key = fold(name)
    key = PROVINCE_ALIASES.get(key, PROVINCE_ALIASES.get(tighten(key), key))
    found = _provinces().get(key)
    if found is not None:
        return found
    tight = {tighten(k): v for k, v in _provinces().items()}
    return tight.get(tighten(key))


@cache
def _district_owners() -> dict[str, list[str]]:
    """Folded district name -> every province that has a district by that name."""
    owners: dict[str, list[str]] = {}
    for parent, names in _districts().items():
        for key in names:
            owners.setdefault(key, []).append(parent)
    return owners


def province_of_district(district: str | None) -> str | None:
    """The province a district name belongs to, when only one province has that name.

    For a source that gives a district and no province at all — Happy Center's store
    cards name `Ümraniye` and never say İstanbul. Most district names are unique across
    the country, so most rows resolve; the ones that are not (`Merkez` being the extreme
    case, but also real repeats like `Çayeli`-style duplicates) return None rather than
    picking the bigger province, which would quietly move stores between cities.
    """
    owners = _district_owners().get(fold(district), [])
    return owners[0] if len(owners) == 1 else None


def _centre_wanted(key: str, province_key: str) -> bool:
    """Whether this district label means "the central district of that province"."""
    if key in CENTRE:
        return True
    without = key.removeprefix(province_key).strip()
    return bool(without) and without in CENTRE and key.startswith(province_key)


def district_id(province: str | None, district: str | None) -> str | None:
    """The district's id within that province, or None when it cannot be decided.

    None means one of three things, and the caller should treat them the same way —
    as a row it did not place: the province is unknown, the district name matches
    nothing, or the label says `Merkez` in a province whose central district was split
    and no longer exists.
    """
    parent = province_id(province)
    if parent is None:
        return None
    within = _districts().get(parent, {})
    key = fold(district)
    key = DISTRICT_RENAMES.get(parent, {}).get(key, key)
    key = DISTRICT_VARIANTS.get(parent, {}).get(key, key)
    if key in within:
        return within[key]

    province_key = fold(
        next(
            (name for name, area in _provinces().items() if area == parent),
            "",
        )
    )
    if _centre_wanted(key, province_key):
        # The centre survives under the province's own name, or it does not survive.
        return within.get(province_key)

    tight = {tighten(k): v for k, v in within.items()}
    return tight.get(tighten(key))
