r"""Bank branches, ATMs, Türk Telekom dealers and fashion chains, placed by coordinate.

Every institution here was read off its own branch finder (method and traps in
`docs/bankalar.md` and `docs/perakende-giyim.md`); the dumps sit under
`C:\veri-ham\{bankalar,operator,perakende}`. They share nothing but a coordinate, so the
district is the one whose boundary the point falls in — the same `locate` the chain
restaurants use — and never the source's own address text.

What makes this family dangerous is not placement but *what a record is*. Three finders
mix branches and ATMs under one `Type`, one lists the same dealer twice, one lists
call-centre channels as branches. Each of those is handled by a named rule below, and each
rule carries a count that trips when the source moves — a rule that silently keeps
working on a changed file is worse than no rule.

Validation, in the order `points` applies it:

1. **Kind is decided per source, explicitly** (`EXTRACTORS`). No field is trusted by
   name alone: Türkiye Finans's `Type="branch"` is an ATM in 578 of 658 rows.
2. **Duplicates** — a record id seen twice is dropped and counted; when the drop exceeds
   what was measured at fetch time (`MAX_DUPLICATES`) the load stops.
3. **Coordinates** — inside Türkiye's box, else abroad; a (0, 0) or blank point is
   "unplaced", which counts against the parse.
4. **Placement** — at most `MAX_UNPLACED` of domestic points may fall outside every
   district polygon.
5. **Province agreement** — where the source names its own province, the polygon's
   province must agree for at least `MIN_AGREEMENT` of rows. This is what catches swapped
   latitude/longitude (Akbank's `locationX` is the latitude) and a code list read with
   the wrong key, neither of which trips checks 3 or 4 on its own.
6. **Unrecognised province names** — a name that matches no province is counted; more
   than `MAX_UNKNOWN_NAMES` stops the load rather than shrinking check 5's denominator.
7. **Totals against BDDK** — state and participation bank branch sums must sit within
   `BDDK_BAND` of BDDK FinTürk's own group totals (2025-01). A scrape that doubles a bank
   passes every placement check; it does not pass this one.

Snapshots, not series: finders show what is open now and keep no history. Rows are
filed under the snapshot's year and replaced on reload.
"""

from __future__ import annotations

import datetime as dt
import json
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import ClassVar

import polars as pl

from ..areas import resolve_district
from ..config import PUBLIC, RAW
from .base import cached_copy
from .chain_stores import TURKEY, locate

FOLDER = RAW / "aglar"
RETRIEVED = dt.date(2026, 9, 21)
SNAPSHOT = dt.date(2026, 9, 21)
VINTAGE = "2026-09"

MAX_UNPLACED = 0.03
MIN_AGREEMENT = 0.97
MAX_UNKNOWN_NAMES = 0.02
#: BDDK FinTürk `bank_group_branches`, sector level, 2025-01. The scrape is 20 months
#: later and branch networks shrink, so the band is asymmetric.
BDDK = {"state": 4433, "participation": 1496, "sector": 10565}
#: TBB's ATM count for the sector, 2025-01 (`bank_atms`). An upper bound only: Garanti's
#: ~6.400 machines are missing from the scrape.
TBB_ATMS = 50574
BDDK_BAND = (0.85, 1.10)


@dataclass(frozen=True)
class Point:
    key: str
    kind: str  # "branch" | "atm" | "store"
    lat: float | None
    lng: float | None
    province: str | None = None  # "TR-xx" as the source states it, when it does
    # The district the source names, used only when there is no coordinate at all.
    named_district: str | None = None


def _num(value) -> float | None:
    if value in (None, "", 0, 0.0, "0"):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except ValueError:
        return None
    return number or None


# --- province names -----------------------------------------------------------------


def fold(text: str) -> str:
    """Upper-case ASCII without Turkish marks, letters only: 'Kahramanmaraş' -> 'KAHRAMANMARAS'."""
    text = text.replace("ı", "i").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if ch.isalpha()).upper()


ALIASES = {"AFYON": "AFYONKARAHISAR", "ICEL": "MERSIN", "KMARAS": "KAHRAMANMARAS"}


@cache
def _provinces() -> dict[str, str]:
    kapsam = json.loads((PUBLIC / "geo" / "kapsam.json").read_text(encoding="utf-8"))
    return {fold(v["ad"]): k for k, v in kapsam.items() if v["duzey"] == "il"}


class Unknown(str):
    """A province name that matched nothing; kept apart so check 6 can count it."""


def province(name) -> str | None:
    """'TR-xx' for a source's province text or plate number; `Unknown` when unmatched."""
    if name in (None, ""):
        return None
    if isinstance(name, int) or str(name).strip().isdigit():
        plate = int(name)
        return f"TR-{plate:02d}" if 1 <= plate <= 81 else Unknown(str(name))
    # ING splits İstanbul in two ('İstanbul-Anadolu'); the part before the dash is the city.
    key = fold(str(name).split("-")[0])
    key = ALIASES.get(key, key)
    return _provinces().get(key) or Unknown(str(name))


# --- one extractor per source -------------------------------------------------------


def _load(relative: str) -> dict:
    source = RAW / relative
    copy = cached_copy(source, FOLDER / relative.replace("/", "__"))
    return json.loads(copy.read_text(encoding="utf-8"))


def ziraat() -> Iterator[Point]:
    for r in _load("bankalar/ziraat_sube.json")["subeler"]:
        yield Point(
            f"s{r['id']}", "branch", _num(r["lat"]), _num(r["lng"]), province(r["il"])
        )
    for r in _load("bankalar/ziraat_atm.json")["atmler"]:
        yield Point(
            f"a{r['id']}", "atm", _num(r["lat"]), _num(r["lng"]), province(r["il"])
        )


def vakifbank() -> Iterator[Point]:
    d = _load("bankalar/vakifbank_sube_atm.json")
    for r in d["subeler"]:
        # Status 1 is an open branch. Status 2 (259 rows, 212 of them without a
        # coordinate, every one typed "Bilinmiyor") are closed or merged units.
        if r["BranchStatus"] != "1":
            continue
        yield Point(
            r["BranchCode"],
            "branch",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r["CityCode"]),
        )
    for r in d["atmler"]:
        yield Point(
            r["ATMCode"],
            "atm",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r.get("ilAd")),
        )


def halkbank() -> Iterator[Point]:
    for r in _load("bankalar/halkbank_sube.json")["subeler"]:
        yield Point(
            f"s{r['branchCode']}",
            "branch",
            _num(r["latitude"]),
            _num(r["longitude"]),
            province(r["cityName"]),
        )
    for r in _load("bankalar/halkbank_atm.json")["atmler"]:
        yield Point(
            f"a{r['atmCode']}",
            "atm",
            _num(r["latitude"]),
            _num(r["longitude"]),
            province(r["cityName"]),
        )


def isbank() -> Iterator[Point]:
    for city, rows in _load("bankalar/isbank_sube_atm.json")["iller"].items():
        for r in rows:
            kind = {"B": "branch", "A": "atm"}[r["Type"]]
            key = f"{kind}{r['BranchCode'] if kind == 'branch' else r['Atm_No']}|{r['Title']}"
            yield Point(
                key, kind, _num(r["Latitude"]), _num(r["Longitude"]), province(city)
            )


def denizbank() -> Iterator[Point]:
    for r in _load("bankalar/denizbank_sube_atm.json")["kayitlar"]:
        kind = {"branch": "branch", "atm": "atm"}[r["record-type"]]
        yield Point(
            f"{kind}{r['code']}|{r['name']}",
            kind,
            _num(r["latitude"]),
            _num(r["longitude"]),
        )


def yapikredi() -> Iterator[Point]:
    d = _load("bankalar/yapikredi_sube_atm.json")
    for r in d["subeler"]:
        yield Point(
            r["BranchCode"],
            "branch",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r.get("ilAd")),
        )
    for r in d["atmler"]:
        yield Point(
            str(r["TerminalID"]),
            "atm",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r.get("ilAd")),
        )


def turkiyefinans() -> Iterator[Point]:
    """`Type="branch"` is not a branch here (`docs/bankalar.md`, 2026-09-21 audit).

    A branch is a row typed branch, named `Şube`, not a lobby (`LOBİ`) — and one per
    coordinate, because the ATM in a branch is listed again as a "branch" at the same
    point. Everything typed atm stays an ATM.
    """
    seen: set[tuple[float, float]] = set()
    for r in _load("bankalar/turkiyefinans_sube_atm.json")["kayitlar"]:
        lat, lng = _num(r["Latitude"]), _num(r["Longitude"])
        name = r["Name"]
        if r["Type"] == "atm":
            yield Point(f"a|{name}|{lat}|{lng}", "atm", lat, lng)
        elif "Şube" in name and "LOBİ" not in name.upper() and (lat, lng) not in seen:
            seen.add((lat, lng))
            yield Point(f"b|{name}", "branch", lat, lng)


def akbank() -> Iterator[Point]:
    # `locationX` is the latitude. Check 5 is what proves it; see the module docstring.
    for cell in _load("bankalar/akbank_sube_atm.json")["sonuc"].values():
        for kind, rows in (("branch", cell["sube"]), ("atm", cell["atm"])):
            for r in rows:
                yield Point(
                    f"{kind}|{r.get('code', '')}|{r['name']}|{r['locationX']}",
                    kind,
                    _num(r["locationX"]),
                    _num(r["locationY"]),
                    province(r.get("cityName")),
                )


def kuveytturk() -> Iterator[Point]:
    """Type 1 branch, 2 ATM, 3 all-in-one cash machine (counted as an ATM)."""
    for r in _load("bankalar/kuveytturk_sube_atm.json")["kayitlar"]:
        kind = {1: "branch", 2: "atm", 3: "atm"}[r["Type"]]
        city = (r.get("District") or {}).get("City", {}).get("Name")
        # `Id` is the branch a machine belongs to, not the machine: one branch's five
        # ATMs share it (and 17 branches carry Id 0). Name plus point is the machine.
        yield Point(
            f"{r['Id']}|{r['Name']}|{r['Latitude']}|{r['Longitude']}",
            kind,
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(city),
        )


def vakifkatilim() -> Iterator[Point]:
    for i, r in enumerate(_load("bankalar/vakifkatilim_sube_atm.json")["kayitlar"]):
        kind = "atm" if "ATM" in (r.get("branchType") or "").upper() else "branch"
        yield Point(
            f"{i}",
            kind,
            _num(r["latitude"]),
            _num(r["longitude"]),
            province(r.get("cityName")),
        )


def teb() -> Iterator[Point]:
    d = _load("bankalar/teb_sube_atm.json")
    # Identical ATM rows are kept: two machines at one branch print the same card.
    for kind, rows in (("branch", d["subeler"]), ("atm", d["atmler"])):
        for i, r in enumerate(rows):
            key = (
                f"{kind}|{r['metin'][:80]}|{r['lat']}"
                if kind == "branch"
                else f"atm{i}"
            )
            yield Point(key, kind, _num(r["lat"]), _num(r["lng"]))


def sekerbank() -> Iterator[Point]:
    """`cityid` is the bank's own code and disagrees with the address — not used."""
    for r in _load("bankalar/sekerbank_sube_atm.json")["kayitlar"]:
        kind = "atm" if "ATM" in r["name"].upper() else "branch"
        lng, lat = r["location"]
        yield Point(r["id"], kind, _num(lat), _num(lng))


def ziraatkatilim() -> Iterator[Point]:
    for r in _load("bankalar/ziraatkatilim_sube.json")["subeler"]:
        yield Point(r["ad"], "branch", _num(r["lat"]), _num(r["lng"]))


def albaraka() -> Iterator[Point]:
    # ATMs carry branch code 0; one row is one machine, as with TEB.
    for i, r in enumerate(_load("bankalar/albaraka_sube_atm.json")["kayitlar"]):
        kind = {"B": "branch", "A": "atm"}[r["data"]["tip"]]
        key = f"b{r['data']['subeKodu']}|{r['lat']}" if kind == "branch" else f"a{i}"
        yield Point(
            key, kind, _num(r["lat"]), _num(r["lng"]), province(r["data"].get("sehir"))
        )


def fibabanka() -> Iterator[Point]:
    for r in _load("bankalar/fibabanka_sube_atm.json")["kayitlar"]:
        kind = {"1": "branch", "2": "atm"}[r["Type"]]
        yield Point(r["Id"], kind, _num(r["Latitude"]), _num(r["Longitude"]))


def emlakkatilim() -> Iterator[Point]:
    """`BranchType` "4" is a named branch; blank is an unnamed ATM point."""
    for i, r in enumerate(_load("bankalar/emlakkatilim_sube_atm.json")["kayitlar"]):
        kind = "branch" if r["BranchType"] == "4" else "atm"
        yield Point(
            f"b{r['BranchId']}" if kind == "branch" else f"a{i}",
            kind,
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r.get("CityName")),
        )


def qnb() -> Iterator[Point]:
    for r in _load("bankalar/qnb_atm.json")["atmler"]:
        city = (r.get("District") or {}).get("City", {}).get("Name")
        yield Point(
            str(r["Id"]),
            "atm",
            _num(r["Latitude"]),
            _num(r["Longtitude"]),
            province(city),
        )


def ing() -> Iterator[Point]:
    for r in _load("bankalar/ing_sube.json")["kayitlar"]:
        if r["info"]["isBranch"]:
            yield Point(
                r["info"]["code"],
                "branch",
                _num(r["maps"]["lat"]),
                _num(r["maps"]["lng"]),
                province(r.get("ilAd")),
            )


def turktelekom() -> Iterator[Point]:
    """The personal and corporate lists overlap: 1.777 rows, 893 partners. The key is
    the partner id, so a dealer in both lists is one dealer."""
    d = _load("operator/turktelekom_bayi.json")
    for r in d["bireysel"] + d["kurumsal"]:
        # CoordinateX is the latitude, as check 5 confirms.
        yield Point(
            str(r["PartnerID"]),
            "store",
            _num(r["CoordinateX"]),
            _num(r["CoordinateY"]),
            province(r.get("City")),
        )


def _vodafone(*kinds: str) -> Callable[[], Iterator[Point]]:
    """Vodafone's finder lists every kind of point in one file, and the kinds are not
    alike: `cep_merkezi` and `kurumsal_magaza` are Vodafone-branded shops, `hizmet_noktasi`
    a dealer selling lines, `odeme_noktasi` a shop that only takes bill payments (3.440 of
    5.891 — counted together they made Vodafone look six times Türk Telekom's size)."""

    def extract() -> Iterator[Point]:
        import csv

        copy = cached_copy(RAW / "zincir/vodafone.csv", FOLDER / "zincir__vodafone.csv")
        with copy.open(encoding="utf-8", newline="") as handle:
            for i, r in enumerate(csv.DictReader(handle)):
                if r["kind"] in kinds:
                    yield Point(
                        f"{i}",
                        "store",
                        _num(r["lat"]),
                        _num(r["lng"]),
                        province(r["province"]),
                    )

    return extract


def turkcell() -> Iterator[Point]:
    """Turkcell's own list of digital sales dealers (DSN, DSNPlus, DSNPlus Extra), a
    195-page PDF saved by hand on 2026-09-23 (turkcell.com.tr → Turkcell Mağazaları →
    "Dijital Satış Noktaları Listesi"). No coordinates: the province comes from the list's
    order, checked against the PDF's own per-province summary (81 provinces, 3.516
    dealers, and its per-type totals), and the district from each row's district label
    through the registry (`scripts/convert_turkcell_pdf.py`). Turkcell has no separate
    branded-shop tier: its store finder shows these same dealers (48 of Adana's 74)."""
    for r in _load("turkcell/elle/turkcelldijital_satirlar.json"):
        yield Point(str(r["no"]), "store", None, None, r["il"], r["ilce"])


def aras() -> Iterator[Point]:
    """Aras units of type 4 (branch). UnitId is not unique: 70 ids carry two branches
    with different names and points (GÖKSUN CEP and AFŞİN share one), so the name is
    the key. The dump lost its Turkish letters, so the address cannot give a province."""
    d = _load("kargo/aras_subeler.json")
    for r in d["data"]["Responses"]:
        # XCoor is the longitude, YCoor the latitude.
        yield Point(r["Name"], "store", _num(r["YCoor"]), _num(r["XCoor"]))


def dhl() -> Iterator[Point]:
    """DHL eCommerce (formerly MNG). The finder only answers "nearest branches" for a
    district, so every district was asked and the answers were merged on BranchCode;
    coordinates use a decimal comma. A leading zero, then the plate: 01100200 is Bilecik (11)."""
    d = _load("kargo/dhl_subeler.json")
    for r in d["branches"]:
        yield Point(
            r["BranchCode"],
            "store",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(int(r["BranchCode"][1:3])),
        )


def yurtici() -> Iterator[Point]:
    """Yurtiçi's branch endpoint answers one id at a time; ids 1-12000 were walked. Ids
    come in regional blocks of a thousand: 1002-7150, then 8010-8499 (the east and
    south-east — a first walk that stopped at 8000 left 17 provinces empty) and
    9000-9231 (more İstanbul); nothing above. The address is free text that usually ends in
    the province ("Merkez / Bilecik") but sometimes in a district or "İst."; only a last
    word that is a province counts as stated, the rest is left to the coordinate."""
    copy = cached_copy(
        RAW / "kargo/yurtici_subeler.jsonl", FOLDER / "kargo__yurtici.jsonl"
    )
    for line in copy.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        yield Point(
            str(r["Id"]),
            "store",
            _num(r.get("Latitude")),
            _num(r.get("Longitude")),
            _last_word_province(r["Address"]),
        )


def _last_word_province(address: str) -> str | None:
    words = address.replace("/", " ").split()
    found = province(words[-1]) if words else None
    return None if isinstance(found, Unknown) else found


def _ptt(kind: str) -> Callable[[], Iterator[Point]]:
    """PTT's own finder (enyakinptt.ptt.gov.tr/api/Isyerleri, base64 JSON, asked per
    plate), one extractor per workplace type: MERKEZ (the district's main office),
    ŞUBE (a branch under it) and ACENTELİK (run under contract by a shopkeeper,
    mostly in villages). The plate in `il_id` is the stated province."""

    def extract() -> Iterator[Point]:
        import csv

        copy = cached_copy(RAW / "ptt/isyerleri.csv", FOLDER / "ptt__isyerleri.csv")
        with copy.open(encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                if r["Cins"] == kind:
                    yield Point(
                        r["Sira"],
                        "store",
                        _num(r["Lat"]),
                        _num(r["Lon"]),
                        province(int(r["il_id"])),
                    )

    return extract


def surat() -> Iterator[Point]:
    """Sürat's delivery-point finder, asked per district by name; only type 3 (branch)
    is taken. The finder answers with nearby points, so districts overlap and the name
    plus the point is the key. "Acente" in the name marks a contracted agency (388 of
    818). Van/Başkale and Van/Edremit answered with a server error page, not a list."""
    copy = cached_copy(
        RAW / "kargo/surat_noktalar.jsonl", FOLDER / "kargo__surat.jsonl"
    )
    for line in copy.read_text(encoding="utf-8").splitlines():
        for r in json.loads(line)["rows"]:
            if r["TeslimatNoktasiTipi"] == 3:
                yield Point(
                    f"{r['Adi']}|{r['Enlem']}|{r['Boylam']}",
                    "store",
                    _num(r["Enlem"]),
                    _num(r["Boylam"]),
                )


def kolay_gelsin() -> Iterator[Point]:
    """Kolay Gelsin's delivery-point map (/api/dealers?branchType=0, GeoJSON). Its own
    units are named "<district> DN" (205) plus one "MERSİN DM"; the ~990 other points
    are contracted shops (Aygaz dealers, markets, stationers) and are left out, as
    Sürat's are. CityName is the stated province."""
    d = _load("kargo/kolaygelsin/dealers_bt0_false.json")
    for f in d["result"]["Branches"]["features"]:
        r = f["properties"]
        if r["BranchName"].split()[-1] not in {"DN", "DM"}:
            continue
        yield Point(
            r["BranchName"],
            "store",
            _num(r["Latitude"]),
            _num(r["Longitude"]),
            province(r["CityName"]),
        )


def _dmg(mark: str) -> Callable[[], Iterator[Point]]:
    """Doğtaş and Kelebek share one panel (services.dmgpanel.com/ajax/new-shops?mark=).
    Every shop carries `shop_type_name` (Bayi / Perakende / Outlet); the coordinate is
    the text "lat, lng" in `google_maps_link`. The province is the panel's own city,
    which splits İstanbul into "İstanbul - Avrupa" and "- Anadolu"."""

    def extract() -> Iterator[Point]:
        d = _load(f"mobilya/{mark}_magazalar.json")
        for r in d["shops"]:
            lat = lng = None
            parts = (r.get("google_maps_link") or "").split(",")
            if len(parts) == 2:
                lat, lng = _num(parts[0]), _num(parts[1])
            city = (r.get("city") or {}).get("name") or ""
            named = None
            if lat is None or lng is None:
                # 15 Kelebek shops give a short link, an address or nothing; the
                # panel's own district then places them.
                prov = city.split(" - ")[0]
                dist = (r.get("district") or {}).get("name") or ""
                if dist == f"{prov} Merkez":  # the panel writes "Artvin Merkez"
                    dist = "Merkez"
                try:
                    named = resolve_district(prov, dist)
                except KeyError:
                    # "Van Merkez" filed under Yenimahalle, a district Van does not
                    # have: a wrong label is left unplaced, not guessed.
                    named = None
            yield Point(str(r["id"]), "store", lat, lng, province(city), named)

    return extract


def _erciyes(brand: str) -> Callable[[], Iterator[Point]]:
    """Boydak group brands from brandapi.erciyes.com (the API behind istikbal.com.tr's
    store page), asked per plate. `FirmNumber` identifies the store; `ProvinceCode`
    is the plate the brand files it under."""

    def extract() -> Iterator[Point]:
        copy = cached_copy(
            RAW / "mobilya/erciyes_magazalar.jsonl", FOLDER / "mobilya__erciyes.jsonl"
        )
        for line in copy.read_text(encoding="utf-8").splitlines():
            q = json.loads(line)
            if q["brand"] != brand:
                continue
            if q["rows"] is None:
                raise ValueError(
                    f"{brand} plaka {q['plate']}: sorgu hata döndü ({q['error']})"
                )
            for r in q["rows"]:
                yield Point(
                    r["FirmNumber"],
                    "store",
                    _num(r.get("Latitude")),
                    _num(r.get("Longitude")),
                    province(r.get("ProvinceCode")),
                )

    return extract


def _stores(
    relative: str,
    key: str,
    lat: Callable,
    lng: Callable,
    prov: Callable | None = None,
    ident: Callable | None = None,
):
    def extract() -> Iterator[Point]:
        for i, r in enumerate(_load(relative)[key]):
            yield Point(
                str(ident(r)) if ident else str(i),
                "store",
                _num(lat(r)),
                _num(lng(r)),
                province(prov(r)) if prov else None,
            )

    return extract


#: (indicator, brand) -> extractor. Brand keys are `dim` values in indicators.toml.
BANKS: dict[str, Callable[[], Iterator[Point]]] = {
    "ziraat": ziraat,
    "vakifbank": vakifbank,
    "halkbank": halkbank,
    "isbank": isbank,
    "denizbank": denizbank,
    "yapikredi": yapikredi,
    "akbank": akbank,
    "teb": teb,
    "qnb": qnb,
    "sekerbank": sekerbank,
    "fibabanka": fibabanka,
    "ing": ing,
    "kuveytturk": kuveytturk,
    "turkiyefinans": turkiyefinans,
    "vakifkatilim": vakifkatilim,
    "ziraatkatilim": ziraatkatilim,
    "albaraka": albaraka,
    "emlakkatilim": emlakkatilim,
}
#: BDDK groups by ownership *and* by type, and the two partitions overlap: its "state"
#: group holds the three state participation banks as well (state + private + foreign
#: = deposit + participation + development = 10.565). Leaving them out put the scrape at
#: 0,86 of BDDK and looked like a shrinking network; with them it is 0,99.
STATE = {
    "ziraat",
    "vakifbank",
    "halkbank",
    "ziraatkatilim",
    "vakifkatilim",
    "emlakkatilim",
}
PARTICIPATION = {
    "kuveytturk",
    "turkiyefinans",
    "vakifkatilim",
    "ziraatkatilim",
    "albaraka",
    "emlakkatilim",
}

FASHION: dict[str, Callable[[], Iterator[Point]]] = {
    "lcwaikiki": _stores(
        "perakende/lcwaikiki_magaza.json",
        "magazalar",
        lambda r: r["Latitude"],
        lambda r: r["Longitude"],
        lambda r: r["CityCode"],
        lambda r: r["ID"],
    ),
    "defacto": _stores(
        "perakende/defacto_magaza.json",
        "magazalar",
        lambda r: r["Latitude"],
        lambda r: r["Longitude"],
    ),
    "mavi": _stores(
        "perakende/mavi_magaza.json",
        "magazalar",
        lambda r: r["geoPoint"]["latitude"],
        lambda r: r["geoPoint"]["longitude"],
        ident=lambda r: r.get("address", {}).get("id") or r["name"],
    ),
    "koton": _stores(
        "perakende/koton_magaza.json",
        "turkiye",
        lambda r: r["latitude"],
        lambda r: r["longitude"],
        lambda r: r["township"]["city"]["name"],
        lambda r: r["pk"],
    ),
    "sarar": _stores(
        "perakende/sarar_magaza.json",
        "magazalar",
        lambda r: r["lat"],
        lambda r: r["lng"],
    ),
    "zara": _stores(
        "perakende/zara_magaza.json",
        "magazalar",
        lambda r: r["latitude"],
        lambda r: r["longitude"],
        ident=lambda r: r["id"],
    ),
    # Same platform as Koton (`/stores/?format=json`); one row per store across the
    # group's banners — Superstep, SuperKids, House of Superstep, HeartBeat.
    "superstep": _stores(
        "perakende/superstep_magaza.json",
        "magazalar",
        lambda r: r["latitude"],
        lambda r: r["longitude"],
        lambda r: r["township"]["city"]["name"],
        lambda r: r["pk"],
    ),
    # H&M group's own store API, which the finder reads; 45 rows, as the page says.
    "hm": _stores(
        "perakende/hm_magaza.json",
        "magazalar",
        lambda r: r["latitude"],
        lambda r: r["longitude"],
        ident=lambda r: r["storeCode"],
    ),
    "skechers": _stores(
        "perakende/skechers_magaza.json",
        "magazalar",
        lambda r: r["lat"],
        lambda r: r["lng"],
    ),
}

#: Records that are rightly without a point and leave before check 3, per source, with
#: the count measured on 2026-09-21. A bigger drop means the source changed.
NOT_PHYSICAL = {
    # 75 "MOBİL SATIŞ OFİSİ" plus PAYCELL, SMS, IVR, KIOSK, E-DENİZBANK and head-office
    # desks: channels with a branch code but no premises.
    "denizbank": 109,
    # Sürat lists 33 branches with a zero coordinate; they are counted nowhere.
    "surat": 33,
}
#: Duplicate record keys measured on 2026-09-21; the TT lists overlap by design.
MAX_DUPLICATES = {
    "turk_telekom_office": 884,
    # The same branch code and point printed two or three times.
    "denizbank": 169,
    # Seven branch codes with two different points each; the first is kept.
    "halkbank": 7,
    # Asked district by district: three branches answer for two neighbouring districts.
    "surat": 3,
    "default": 0,
}
#: Northern Cyprus: Ziraat, Halkbank and Şekerbank list their branches there. Outside
#: Türkiye and outside the atlas, so abroad — the only place that is. Any other point
#: outside Türkiye's box is a broken coordinate (Halkbank has ATMs at 65°N) and counts
#: as unplaced.
KKTC = (32.2, 34.5, 34.7, 35.8)
#: A small network cannot meet a share: one Skechers store on a pier is 3%.
MIN_UNPLACED_ALLOWANCE = 2


# --- the checks ---------------------------------------------------------------------


@dataclass
class Report:
    brand: str
    kind: str
    records: int = 0
    duplicates: int = 0
    not_physical: int = 0
    abroad: int = 0
    unplaced: int = 0
    stated: int = 0
    agree: int = 0
    unknown_names: int = 0
    by_name: int = 0  # placed by the source's district name, having no coordinate

    @property
    def placed(self) -> int:
        return (
            self.records
            - self.duplicates
            - self.not_physical
            - self.abroad
            - self.unplaced
        )


REPORTS: dict[tuple[str, str], Report] = {}


@cache
def points(
    brand: str, extractor: Callable[[], Iterator[Point]]
) -> tuple[tuple[str, str], ...]:
    """(kind, district) for every placed record, after checks 2-6."""
    x0, y0, x1, y1 = TURKEY
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    reports: dict[str, Report] = {}
    mismatches: list[tuple[str, str, str]] = []
    for point in extractor():
        rep = reports.setdefault(point.kind, Report(brand, point.kind))
        rep.records += 1
        if (point.kind, point.key) in seen:
            rep.duplicates += 1
            continue
        seen.add((point.kind, point.key))
        if (point.lat is None or point.lng is None) and point.named_district:
            rep.by_name += 1
            out.append((point.kind, point.named_district))
            continue
        if point.lat is None or point.lng is None:
            if brand in NOT_PHYSICAL:
                rep.not_physical += 1
            else:
                rep.unplaced += 1
            continue
        if not (x0 <= point.lng <= x1 and y0 <= point.lat <= y1):
            k0, k1, k2, k3 = KKTC
            if k0 <= point.lng <= k2 and k1 <= point.lat <= k3:
                rep.abroad += 1
            else:
                rep.unplaced += 1
            continue
        area = locate(point.lng, point.lat)
        if area is None:
            rep.unplaced += 1
            continue
        out.append((point.kind, area))
        if isinstance(point.province, Unknown):
            rep.unknown_names += 1
        elif point.province:
            rep.stated += 1
            if area[:5] == point.province:
                rep.agree += 1
            elif len(mismatches) < 5:
                mismatches.append((point.key[:40], point.province, area))

    for rep in reports.values():
        REPORTS[(brand, rep.kind)] = rep
        where = f"{brand}/{rep.kind}"
        allowed = MAX_DUPLICATES.get(brand, MAX_DUPLICATES["default"])
        if rep.duplicates > allowed:
            raise ValueError(
                f"{where}: {rep.duplicates} yinelenen kayıt (ölçülen {allowed})"
            )
        if rep.not_physical > NOT_PHYSICAL.get(brand, 0):
            raise ValueError(
                f"{where}: {rep.not_physical} koordinatsız kanal (ölçülen {NOT_PHYSICAL[brand]})"
            )
        domestic = rep.records - rep.duplicates - rep.not_physical - rep.abroad
        if not domestic:
            raise ValueError(f"{where}: döküm boş")
        if rep.unplaced > max(MAX_UNPLACED * domestic, MIN_UNPLACED_ALLOWANCE):
            raise ValueError(
                f"{where}: {rep.unplaced}/{domestic} nokta hiçbir ilçeye düşmedi"
            )
        if rep.unknown_names / domestic > MAX_UNKNOWN_NAMES:
            raise ValueError(f"{where}: {rep.unknown_names} tanınmayan il adı")
        if rep.stated and rep.agree / rep.stated < MIN_AGREEMENT:
            raise ValueError(
                f"{where}: kaynağın ili ile poligonun ili {rep.agree}/{rep.stated} uyuşuyor; "
                f"örnek {mismatches}"
            )
    return tuple(out)


def check_bddk(branches: dict[str, int]) -> None:
    """Check 7: group totals against BDDK FinTürk; the sector total as a ceiling."""
    lo, hi = BDDK_BAND
    if sum(branches.values()) > BDDK["sector"] * hi:
        raise ValueError(
            f"şube toplamı {sum(branches.values())} sektörü aşıyor ({BDDK['sector']})"
        )
    for group, members in (("state", STATE), ("participation", PARTICIPATION)):
        total = sum(branches.get(b, 0) for b in members)
        ratio = total / BDDK[group]
        if not lo <= ratio <= hi:
            raise ValueError(
                f"{group} şube toplamı {total}, BDDK {BDDK[group]} (oran {ratio:.2f})"
            )


# --- adapters -----------------------------------------------------------------------


class _Network:
    indicator_id = ""
    source_id = "branch_finders"
    dim = ""
    kind = ""
    brands: ClassVar[dict[str, Callable[[], Iterator[Point]]]] = {}

    def fetch(self) -> Path:
        for brand, extractor in self.brands.items():
            points(brand, extractor)  # copies the dumps into FOLDER as a side effect
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        rows: dict[tuple[str, str, str], int] = {}
        totals: dict[str, int] = {}
        for brand, extractor in self.brands.items():
            for kind, area in points(brand, extractor):
                if kind != self.kind:
                    continue
                totals[brand] = totals.get(brand, 0) + 1
                for level, a in (("district", area), ("province", area[:5])):
                    rows[(level, a, brand)] = rows.get((level, a, brand), 0) + 1
        if self.indicator_id == "bank_branch_locations":
            check_bddk(totals)
        if (
            self.indicator_id == "bank_atm_locations"
            and sum(totals.values()) > TBB_ATMS
        ):
            raise ValueError(
                f"ATM toplamı {sum(totals.values())} TBB'yi ({TBB_ATMS}) aşıyor"
            )
        missing = [b for b in self.brands if b not in totals and self._expects(b)]
        if missing:
            raise ValueError(f"{self.indicator_id}: kaydı gelmeyen marka {missing}")
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": [a for _, a, _ in rows],
                "area_level": [lvl for lvl, _, _ in rows],
                "period_start": dt.date(SNAPSHOT.year, 1, 1),
                "frequency": "annual",
                "dims": [f"{self.dim}={b}" for _, _, b in rows],
                "value": [float(v) for v in rows.values()],
                "unit": "item",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )

    def _expects(self, brand: str) -> bool:
        return True


class BankBranchLocations(_Network):
    indicator_id = "bank_branch_locations"
    dim = "bank"
    kind = "branch"
    brands = BANKS

    def _expects(self, brand: str) -> bool:
        return brand != "qnb"  # QNB branches could not be fetched; ATMs only


class BankAtmLocations(_Network):
    indicator_id = "bank_atm_locations"
    dim = "bank"
    kind = "atm"
    brands = BANKS

    def _expects(self, brand: str) -> bool:
        return brand not in {"ziraatkatilim", "ing"}  # neither publishes ATMs


class TelecomDealers(_Network):
    indicator_id = "telecom_dealers"
    dim = "telecom_outlet"
    kind = "store"
    brands: ClassVar = {
        "turk_telekom_office": turktelekom,
        "vodafone_shop": _vodafone("cep_merkezi", "kurumsal_magaza"),
        "vodafone_dealer": _vodafone("hizmet_noktasi"),
        "vodafone_payment": _vodafone("odeme_noktasi"),
        "turkcell_dealer": turkcell,
    }


class CargoBranches(_Network):
    indicator_id = "cargo_branches"
    dim = "cargo_company"
    kind = "store"
    brands: ClassVar = {
        "aras": aras,
        "dhl_ecommerce": dhl,
        "yurtici": yurtici,
        "surat": surat,
        "kolay_gelsin": kolay_gelsin,
    }


class PostOffices(_Network):
    indicator_id = "post_offices"
    dim = "post_office_type"
    kind = "store"
    brands: ClassVar = {
        "main": _ptt("MERKEZ"),
        "branch": _ptt("ŞUBE"),
        "agency": _ptt("ACENTELİK"),
    }


class FurnitureStores(_Network):
    indicator_id = "furniture_stores"
    dim = "furniture_brand"
    kind = "store"
    brands: ClassVar = {
        "istikbal": _erciyes("İSTİKBAL"),
        "bellona": _erciyes("BELLONA"),
        "mondi": _erciyes("MONDİ"),
        "dogtas": _dmg("dogtas"),
        "kelebek": _dmg("kelebek"),
    }


class FashionStores(_Network):
    indicator_id = "fashion_stores"
    dim = "fashion_brand"
    kind = "store"
    brands = FASHION


NETWORK_ADAPTERS = {
    a.indicator_id: a
    for a in (
        BankBranchLocations,
        BankAtmLocations,
        TelecomDealers,
        FashionStores,
        CargoBranches,
        PostOffices,
        FurnitureStores,
    )
}
