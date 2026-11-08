"""Build the data behind web/secim-kentkir-harita.html: election results per district,
split into urban (kent) and rural (kir) by the user's own decisions.

For every election in ELECTIONS this writes public/elections/kentkir/<code>.json plus an
index.json. Per place (district id like TR-37-001, province id like TR-37):

    {"t": {...}, "kent": {...}, "kir": {...}}      # each block: g valid, k registered,
                                                   # o cast, v {party: share of valid, %}

"t" is the whole place (from the official district tile) and exists everywhere. "kent" and
"kir" only exist for provinces whose every control row has a decision: the classifier is the
one the series script uses, so a decision change here and in the series always agree.
Unclassified ballot boxes (old village names that no longer resolve) are left out of both.

Run again whenever scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json changes:

    uv run python scripts/build_kentkir_secim.py            # every election
    uv run python scripts/build_kentkir_secim.py mv2023     # one election
"""

from __future__ import annotations

import collections
import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES_SCRIPT = ROOT / "scripts/analiz/kent_kir_2026_09_27/il_kent_kir_seri.py"
DECISIONS = ROOT / "scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json"
CONTROL = ROOT / "public/kentkir_kontrol.json"
TILES = ROOT / "public/tiles"
OUT = ROOT / "public/elections/kentkir"

URBAN = {"İlçe Merkezi", "Kentsel Belde", "İl Merkezi"}

# code -> label shown in the page. Turkish labels live here, not in the logic (decision K1).
ELECTIONS = {
    "mv2007": "2007 milletvekili",
    "mv2011": "2011 milletvekili",
    "mv2015h": "2015 Haziran milletvekili",
    "mv2015k": "2015 Kasım milletvekili",
    "mv2018": "2018 milletvekili",
    "mv2023": "2023 milletvekili",
    "cb2014": "2014 cumhurbaşkanlığı",
    "cb2018": "2018 cumhurbaşkanlığı",
    "cb2023t1": "2023 cumhurbaşkanlığı 1. tur",
    "cb2023t2": "2023 cumhurbaşkanlığı 2. tur",
    "ho2007": "2007 anayasa referandumu",
    "ho2010": "2010 anayasa referandumu",
    "ho2017": "2017 anayasa referandumu",
    "yerel_bel_2014": "2014 ilçe belediye başkanlığı",
    "yerel_bel_2019": "2019 ilçe belediye başkanlığı",
    "yerel_bel_2024": "2024 ilçe belediye başkanlığı",
    "yerel_bsb_2014": "2014 büyükşehir başkanlığı",
    "yerel_bsb_2019": "2019 büyükşehir başkanlığı",
    "yerel_bsb_2024": "2024 büyükşehir başkanlığı",
    "yerel_belmec_2014": "2014 ilçe belediye meclisi",
    "yerel_belmec_2019": "2019 ilçe belediye meclisi",
    "yerel_belmec_2024": "2024 ilçe belediye meclisi",
}
MIN_SHARE = 1.0  # a party under 1% of a place's valid votes is dropped from that place


def fully_decided_provinces() -> list[str]:
    """Plates whose every control row has a decision (offset ids included)."""
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    control = json.loads(CONTROL.read_text(encoding="utf-8"))

    def decided(area_id: str) -> bool:
        if area_id in decisions:
            return True
        head, num = area_id.rsplit("-", 1)
        return num.lstrip("-").isdigit() and any(
            f"{head}-{int(num) + off}" in decisions for off in (2000000, -2000000)
        )

    total: collections.Counter[str] = collections.Counter()
    done: collections.Counter[str] = collections.Counter()
    for row in control["rows"]:
        plate = row[0][3:5]
        total[plate] += 1
        done[plate] += decided(row[0])
    return sorted(p for p in total if done[p] == total[p])


class _Sink(io.StringIO):
    """Swallows the series script's printing; it also calls sys.stdout.reconfigure()."""

    def reconfigure(self, **_kwargs) -> None:
        return None


def run_series_script(plate: str) -> dict:
    """Run the series script for one province and return its globals.

    The script writes its two CSVs next to itself; here they go to a throwaway folder so a
    map rebuild never touches the committed series.
    """
    source = SERIES_SCRIPT.read_text(encoding="utf-8")
    source = source.replace(
        'HERE / f"il_kent_kir_seri_', 'SCRATCH / f"il_kent_kir_seri_'
    )
    scratch = Path(tempfile.mkdtemp(prefix="kentkir_seri_"))
    namespace = {
        "__file__": str(SERIES_SCRIPT),
        "__name__": "__main__",
        "SCRATCH": scratch,
    }
    argv = sys.argv
    sys.argv = [str(SERIES_SCRIPT), plate]
    try:
        with contextlib.redirect_stdout(_Sink()):
            exec(compile(source, str(SERIES_SCRIPT), "exec"), namespace)  # noqa: S102 -- our own series script
    finally:
        sys.argv = argv
    return namespace


class Classifier:
    """Urban / rural class of one election row, following the series script's resolver."""

    def __init__(self, plate: str):
        g = run_series_script(plate)
        self.plate = plate
        self.decisions = g["decisions"]
        self.resolve = g["resolve"]
        self.registry = g["registry"]
        self.key = g["key"]
        self.districts = g["districts"]
        self.retired = g["RETIRED_CLASS"]
        self.towns: dict[str, dict[str, str]] = collections.defaultdict(dict)
        for area_id, d in self.decisions.items():
            if d.get("y"):
                self.towns[area_id[:9]][d["y"]] = d["s"]

    def classify_all(self, rows: dict[str, dict]) -> dict[str, str | None]:
        """Classes of every row of one province tile, with the orphan rule applied.

        A ballot-box line that matches nothing today (a village or neighbourhood renamed or
        merged since) is given the class of the district's *orphan* units: units that exist
        now but that no line of this tile matches. It only fires when every orphan of the
        district shares one class and there are at least as many orphans as lost lines, so
        a district with mixed orphans stays unclassified rather than guessed.
        """
        classes = {a: self.classify(a, r) for a, r in rows.items()}
        seen_ids = set(rows)
        seen_names = {
            self.key(re.sub(r"\s*\(B\).*", "", r.get("ad") or ""))
            for r in rows.values()
        }
        orphans: dict[str, list[str]] = collections.defaultdict(list)
        for area_id, decision in self.decisions.items():
            head, num = area_id.rsplit("-", 1)
            offset_ids = (
                {f"{head}-{int(num) + off}" for off in (2000000, -2000000)}
                if num.isdigit()
                else set()
            )
            if area_id in seen_ids or offset_ids & seen_ids:
                continue
            name = self.registry.get(area_id, {}).get("name_tr")
            if name and self.key(name) in seen_names:
                continue
            orphans[area_id[:9]].append(decision["s"])
        lost: dict[str, list[str]] = collections.defaultdict(list)
        for area_id, cls in classes.items():
            if cls is None:
                lost[area_id[:9]].append(area_id)
        for district, lines in lost.items():
            found = orphans.get(district, [])
            if found and len(set(found)) == 1 and len(found) >= len(lines):
                for area_id in lines:
                    classes[area_id] = found[0]
        return classes

    def decision(self, area_id: str) -> str | None:
        if area_id in self.decisions:
            return self.decisions[area_id]["s"]
        head, num = area_id.rsplit("-", 1)
        if num.isdigit():
            for off in (2000000, -2000000):
                hit = self.decisions.get(f"{head}-{int(num) + off}")
                if hit:
                    return hit["s"]
        return None

    def classify(self, area_id: str, row: dict) -> str | None:
        district = area_id[:9]
        name = row.get("ad") or ""
        cls = self.decision(area_id)
        if cls:
            return cls
        if "~" not in area_id:
            try:
                cls = self.resolve(area_id)[1] or None
            except Exception:  # noqa: BLE001 -- resolve() raises on unknown units; None means unclassified
                cls = None
        if not cls and "(B)" in name:
            town = re.sub(r"\s*\(B\).*", "", name).strip()
            cls = self.towns[district].get(town)
            if not cls:
                hit = {
                    self.decisions[i]["s"]
                    for i, r in self.registry.items()
                    if i[:9] == district
                    and i in self.decisions
                    and town in r["name_tr"]
                }
                cls = (
                    hit.pop() if len(hit) == 1 else "Köy"
                )  # a town total with no label: rural
        if not cls and "~" in area_id:
            head = re.sub(r"\s*\(B\).*", "", name).split("-")[0].strip()
            towns = {self.key(t): c for t, c in self.towns[district].items()}
            if self.key(head) in towns and "-" in name:
                cls = towns[self.key(head)]
        if not cls and "~" in area_id:
            wanted = self.key(name)
            hits = [
                i
                for i, r in self.registry.items()
                if i[:9] == district
                and self.key(r["name_tr"]) == wanted
                and i not in self.decisions
            ]
            same_muni = [
                i
                for i in hits
                if (self.registry[i].get("municipality") or "").replace(" Bel.", "")
                == self.districts.get(district)
            ]
            hits = same_muni or hits
            classes = set()
            for i in hits:
                try:
                    classes.add(self.retired.get(i) or self.resolve(i)[1])
                except Exception:  # noqa: BLE001 -- resolve() raises on unknown units; None means unclassified
                    classes.add(None)
            if len(classes) == 1 and None not in classes:
                cls = classes.pop()
        if not cls and "~" in area_id:
            # A whole-town line (2017 lists a town as one unit without "(B)").
            towns = {self.key(t): c for t, c in self.towns[district].items()}
            if self.key(name) in towns:
                cls = towns[self.key(name)]
            else:
                found = set()
                for i, r in self.registry.items():
                    if i[:9] == district and self.key(
                        (r.get("municipality") or "").replace(" Bel.", "")
                    ) == self.key(name):
                        found.add(
                            self.decisions[i]["s"] if i in self.decisions else None
                        )
                if len(found) == 1 and None not in found:
                    cls = found.pop()
        return cls


def block(valid: int, registered: int, cast: int, votes: dict[str, int]) -> dict | None:
    if not valid:
        return None
    shares = {
        party: round(count / valid * 100, 1)
        for party, count in votes.items()
        if count / valid * 100 >= MIN_SHARE
    }
    return {"g": valid, "k": registered, "o": cast, "v": shares}


def add(acc: dict, row: dict) -> None:
    acc["g"] += row["g"]
    acc["k"] += row["k"]
    acc["o"] += row["o"]
    acc["v"].update(row["v"])


def empty() -> dict:
    return {"g": 0, "k": 0, "o": 0, "v": collections.Counter()}


def build(code: str, classifiers: dict[str, Classifier]) -> dict:
    district_tile = json.loads(
        (TILES / f"secim-{code}-ilce.json").read_text(encoding="utf-8")
    )
    places: dict[str, dict] = {}
    national: collections.Counter[str] = collections.Counter()
    province_total: dict[str, dict] = collections.defaultdict(empty)
    names: dict[str, str] = {}
    for area_id, row in district_tile.items():
        if not re.fullmatch(r"TR-\d\d-\d{3}", area_id):
            continue
        names[area_id] = row.get("ad", area_id)
        add(province_total[area_id[:5]], row)
        national.update(row["v"])
        places[area_id] = {"t": block(row["g"], row["k"], row["o"], row["v"])}
    for province_id, acc in province_total.items():
        places[province_id] = {"t": block(acc["g"], acc["k"], acc["o"], acc["v"])}

    unmatched = 0
    for plate, classifier in classifiers.items():
        tile = TILES / f"secim-{code}-mahalle-TR-{plate}.json"
        if not tile.exists():
            continue
        groups: dict[str, dict[str, dict]] = collections.defaultdict(
            lambda: {"kent": empty(), "kir": empty()}
        )
        rows = json.loads(tile.read_text(encoding="utf-8"))
        classes = classifier.classify_all(rows)
        for area_id, row in rows.items():
            cls = classes[area_id]
            if cls is None:
                unmatched += row["g"]
                continue
            side = "kent" if cls in URBAN else "kir"
            for scope in (area_id[:9], f"TR-{plate}"):
                add(groups[scope][side], row)
        for scope, sides in groups.items():
            for side, acc in sides.items():
                places.setdefault(scope, {"t": None})[side] = block(
                    acc["g"], acc["k"], acc["o"], acc["v"]
                )

    parties = [p for p, _ in national.most_common() if national[p] > 0][:14]
    return {
        "code": code,
        "label_tr": ELECTIONS[code],
        "parties": parties,
        "unmatched_valid": unmatched,
        "names": names,
        "places": places,
    }


def main() -> None:
    codes = sys.argv[1:] or list(ELECTIONS)
    plates = fully_decided_provinces()
    print(f"{len(plates)} fully decided provinces", flush=True)
    classifiers = {plate: Classifier(plate) for plate in plates}
    OUT.mkdir(parents=True, exist_ok=True)
    for code in codes:
        if not (TILES / f"secim-{code}-ilce.json").exists():
            print(code, "no district tile, skipped")
            continue
        data = build(code, classifiers)
        (OUT / f"{code}.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(
            code,
            len(data["places"]),
            "places,",
            data["unmatched_valid"],
            "unclassified valid",
            flush=True,
        )
    write_index(plates)


def write_index(plates: list[str]) -> None:
    """Index of whatever election files exist, so a one-election run never drops the others."""
    index = {}
    for code in ELECTIONS:
        path = OUT / f"{code}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            index[code] = {"label_tr": data["label_tr"], "parties": data["parties"]}
    (OUT / "index.json").write_text(
        json.dumps(
            {"elections": index, "provinces": [f"TR-{p}" for p in plates]},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
