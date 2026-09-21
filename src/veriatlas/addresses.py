r"""The district behind a free-text address, when the source never names one.

Some store finders publish an address and a province and nothing else. The address
almost always names the district — but not always by its district name. Turkish
addresses lean on the *semt*, the quarter people actually say: a Yunus Market in Ankara
is "Batıkent", "Eryaman" or "Çayyolu", none of which is a district. Batıkent is in
Yenimahalle, Eryaman in Etimesgut, Çayyolu in Çankaya, and no official layer records
that (`docs/semt.md`: semt appears in no register at all).

What does exist is PTT's postal code table, which lists every **mahalle** with its
district — 1.272.201 rows covering 72.640 neighbourhoods. Semt names are not in it
either, but they do not need to be: a semt is built out of mahalles that carry its name
(`Batıkent Mah.`, `Eryaman Mah.`), so looking the token up as a neighbourhood lands in
the right district. That is the whole idea here — the semt layer is reached through the
mahalle layer, which is official.

Three passes, in order, each stricter than a human reading the address would be:

1. **The district's own name**, as the address tail usually gives it (`… Mamak /
   Ankara`). One or two words, matched inside the named province only.
2. **A mahalle named in the address** (`Yenibatı Mh.`, `Cebeci Mah.`). The name has to
   belong to exactly one district of that province.
3. **A bare token in the tail** (`… Batıkent / Ankara`), looked up the same way.

A neighbourhood name that several districts of the same province share resolves to
nothing: 3.140 of the 67.973 province-neighbourhood pairs are shared that way, and
picking one would move a store across the city. There is no fourth pass — in particular
no "assume the central district", which would quietly file every unreadable address in
one place and make that district look busy.

Measured on Yunus Market's 92 branches (2026-09-20): 55 by district name, 24 by
mahalle, 5 by bare token, 8 unresolved.
"""

from __future__ import annotations

import csv
import re
from functools import cache

from .config import RAW
from .labels import district_id, fold, province_id

#: PTT's postal code export, the only country-wide neighbourhood list we have.
POSTAL_CODES = RAW / "ptt"

#: What a source writes after a neighbourhood's name. `M.` is included because addresses
#: abbreviate that far, and the alternatives are ordered longest-first so `Mah` cannot
#: match inside `Mahallesi` and leave `lesi` behind.
#:
#: Only the marker is matched, never the name in front of it. A pattern that captured
#: both read `Gülabi Bey Mah.` as `Bey` — any quantifier has to pick a length, and a
#: neighbourhood name is one, two or three words with no rule saying which. The words
#: before the marker are taken apart in `_before`, longest first, so `Gülabi Bey` is
#: tried before `Bey`.
NEIGHBOURHOOD = re.compile(
    r"\b(?:Mahallesi|Mahalle|Mah\.|Mah|Mh\.|Mh|M\.)(?:\b|\.)",
    re.IGNORECASE,
)

#: How many words before the marker can make up a neighbourhood name.
NAME_WORDS = 3

#: Words that appear where a place name would and are not one.
NOT_A_PLACE = {"", "no", "cd", "cad", "caddesi", "sk", "sok", "sokak", "avm", "plaza"}


def _dump() -> str:
    found = sorted(POSTAL_CODES.glob("postakodu_*.csv"))
    if not found:
        raise FileNotFoundError(f"PTT posta kodu dökümü yok: {POSTAL_CODES}")
    return str(found[-1])


@cache
def _index() -> dict[tuple[str, str], str]:
    """(folded province, folded neighbourhood) -> district name, for unique pairs only.

    Built from the raw export rather than the warehouse: the warehouse keeps the postal
    code *count* per district, which is the indicator, and throws the names away.
    """
    owners: dict[tuple[str, str], set[str]] = {}
    with open(_dump(), encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = re.sub(
                r"\s*(?:MAHALLESİ|MAH\.|MAH|MH\.|MH)\s*$",
                "",
                row["mahalle"].strip(),
                flags=re.IGNORECASE,
            )
            key = (fold(row["il"]), fold(name))
            if key[1]:
                owners.setdefault(key, set()).add(row["ilce"])
    return {key: next(iter(value)) for key, value in owners.items() if len(value) == 1}


def _before(text: str) -> list[str]:
    """The candidate names ending at `text`, longest first: three words, two, then one.

    A candidate stops at anything that cannot be part of a name — a house number, a
    comma, a previous street — so `No: 250 / 29 Ulukavak` offers `Ulukavak` and not
    `29 Ulukavak`.
    """
    words: list[str] = []
    for word in reversed(text.split()):
        if not re.fullmatch(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", word):
            break
        words.insert(0, word)
        if len(words) == NAME_WORDS:
            break
    return [" ".join(words[-size:]) for size in range(len(words), 0, -1)]


def _as_district(province: str, name: str) -> str | None:
    known = _index().get((fold(province), fold(name)))
    return district_id(province, known) if known else None


def district_from_address(province: str | None, address: str | None) -> str | None:
    """The district this address sits in, or None when it cannot be decided.

    `province` is the province the source filed the row under; nothing is matched
    outside it, so a `Bismil` written under Gaziantep stays unresolved rather than
    travelling to Diyarbakır.
    """
    if province_id(province) is None or not address:
        return None

    # `… Mamak / Ankara` puts the district one part before the end, and
    # `… Bahabey Cd. No: 60/A ÇORUM` puts it at the very end with no separator at all.
    # Both are read: the second form is how a source writes an address in the provincial
    # centre, and skipping it lost every such branch — six of Yunus Market's eight
    # unresolved rows were of this shape.
    # Every slash-separated part, from the end. The district is usually one before the
    # last (`… Mamak / Ankara`) or, in a provincial centre, the last one with no
    # separator at all (`… No: 60/A ÇORUM`). It is occasionally further back still:
    # `… No: 6BA / 5 ETİMESGUT / BAĞLICA / ANKARA` names the district, then the semt,
    # then the province. Only a name that is a district *of the named province* is
    # taken, so walking further back cannot pull in a place from somewhere else.
    candidates = [part.strip() for part in reversed(address.split("/"))]

    # Every one- and two-word window in each part, from the end. Not just the final
    # words: an address that ends `… No: 4/1 Avcılar İstanbul` puts the district second
    # from last, behind the province, and reading only the tail found `İstanbul`, which
    # is not a district of İstanbul, and stopped. Windows are tried longest-first at each
    # position so `Oniki Şubat` is preferred over `Şubat`.
    for candidate in candidates:
        words = candidate.split()
        for start in range(len(words) - 1, -1, -1):
            for size in (2, 1):
                if start + size <= len(words):
                    found = district_id(province, " ".join(words[start : start + size]))
                    if found:
                        return found

    for match in NEIGHBOURHOOD.finditer(address):
        for name in _before(address[: match.start()]):
            found = _as_district(province, name)
            if found:
                return found

    for candidate in candidates:
        for word in reversed(candidate.split()):
            if fold(word) not in NOT_A_PLACE:
                found = _as_district(province, word)
                if found:
                    return found
    return None
