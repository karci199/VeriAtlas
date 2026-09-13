"""Neighbourhood demography from Endeksa, keyed by our own area ids.

The earlier puller lived in the data directory and was lost with it. This one lives in the
repository and is driven by what the repository already knows: every neighbourhood in
`public/geo/neighbourhoods/<district>.geojson` carries its Endeksa id, and the file name
carries our district id. So the run needs no cached plan — the list of what to fetch is a
committed artefact.

    GET app.endeksa.com/demography?countryId&cityId&countyId&districtId&level=3

answers AES-ECB ciphertext (same key as the geometry endpoint). All four ids are required:
with the district id alone the service answers `{"Demography": null}` and looks broken.

Output: one file per district, `<data root>/endeksa/demography/<area_id>.json`, keyed by
Endeksa id — names are stored inside as attributes because names change between years and
ids do not. A district already on disk is topped up neighbourhood by neighbourhood, so a
run may be stopped and restarted at any time.

Data root is `VERIATLAS_HAM` or C:/veri-ham — deliberately outside the repository, after a
worktree cleanup followed a junction into the shared store and emptied it.

Run:  uv run python scripts/fetch_endeksa_demography.py            # eksik olan her yer
      uv run python scripts/fetch_endeksa_demography.py TR-16      # tek il
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
OUT = HAM / "endeksa" / "demography"
GEO = ROOT / "public" / "geo" / "neighbourhoods"
LOG = HAM / "endeksa" / "demografi.log"
WORKERS = 2
PAUSE = 0.25

_spec = importlib.util.spec_from_file_location(
    "fg", ROOT / "scripts" / "fetch_endeksa_geo.py"
)
fg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fg)


#: The geometry helper's `get` always talks to geo/map; the demography answer lives at its
#: own path. Asking geo/map for a districtId returns a perfectly valid geometry with no
#: Demography key — which reads as "this neighbourhood has no data" and silently fetched
#: nothing at all.
API = "https://app.endeksa.com/demography"


def demography(client: httpx.Client, **params) -> dict | None:
    """The decrypted demography answer, or None when the service returns an empty one."""
    response = client.get(API, params=params, timeout=30)
    response.raise_for_status()
    body = fg.decrypt(response.text)
    return body.get("Demography")


def key_of(name: str) -> str:
    """A name comparable across sources: ascii letters, lower case."""
    text = name.strip().lower()
    for a, b in zip("İIÇĞÖŞÜçğıöşü", "iicgosucgiosu"):
        text = text.replace(a, b)
    return "".join(ch for ch in text if ch.isalnum())


def log(message: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def districts(prefix: str | None) -> list[pathlib.Path]:
    files = sorted(GEO.glob("TR-*.geojson"))
    return [f for f in files if not prefix or f.stem.startswith(prefix)]


def county_ids(client: httpx.Client, plate: int) -> dict[str, int]:
    """Endeksa CountyId per county name, for one province."""
    # subGeometries="true" is what makes level 1 answer with the counties; without it the
    # response is the province outline alone and every district looks unmatched.
    level1 = fg.get(client, cityId=plate, countryId=1, level=1, subGeometries="true")
    out = {}
    for feature in level1.get("features", []):
        props = feature["properties"]
        name = (props.get("County") or props.get("description") or "").strip()
        if name and props.get("CountyId"):
            out[key_of(name)] = props["CountyId"]
    return out


def main(argv: list[str]) -> None:
    prefix = next((a for a in argv if a.startswith("TR-")), None)
    OUT.mkdir(parents=True, exist_ok=True)
    files = districts(prefix)
    log(f"{len(files)} ilce dosyasi")

    names = {}
    for row in (
        (ROOT / "src" / "veriatlas" / "data" / "areas_tr_districts.csv")
        .read_text(encoding="utf-8")
        .splitlines()[1:]
    ):
        cells = row.split(",")
        if len(cells) > 2:
            names[cells[0]] = cells[2]

    done_total = 0
    with httpx.Client(headers=fg.HEADERS, timeout=90) as client:
        counties: dict[int, dict[str, int]] = {}
        for path in files:
            area_id = path.stem
            plate = int(area_id.split("-")[1])
            target = OUT / f"{area_id}.json"
            have = (
                json.loads(target.read_text(encoding="utf-8"))
                if target.exists()
                else {}
            )

            geo = json.loads(path.read_text(encoding="utf-8"))
            # Some district files carry the Endeksa id as its own property, others only
            # in the area id's last segment (TR-16-006-183945). Both are the same number.
            wanted = []
            for feature in geo["features"]:
                props = feature["properties"]
                ident = (
                    props.get("endeksa_id") or props.get("area_id", "").split("-")[-1]
                )
                if str(ident).isdigit():
                    wanted.append((str(ident), props.get("name_tr")))
            todo = [(i, n) for i, n in wanted if i not in have]
            if not todo:
                continue

            if plate not in counties:
                try:
                    counties[plate] = county_ids(client, plate)
                except Exception as exc:  # noqa: BLE001
                    log(f"  {area_id}: il listesi alinamadi ({exc})")
                    continue
            county_name = names.get(area_id, "")
            key = key_of(county_name)
            county_id = counties[plate].get(key)
            if county_id is None:
                # The registry names a province's central district after the province
                # ("Afyonkarahisar"), Endeksa calls it "Merkez" — and Kâhta is written with
                # the circumflex on one side only. Both were skipping whole districts.
                for aday in ("merkez", key + "merkez", key.removesuffix("merkez")):
                    county_id = counties[plate].get(aday)
                    if county_id:
                        break
            if county_id is None:
                hits = [v for k, v in counties[plate].items() if k.startswith(key[:6])]
                county_id = hits[0] if len(hits) == 1 else None
            if county_id is None:
                log(f"  {area_id} ({county_name}): Endeksa ilcesi eslesmedi")
                continue

            def one(job, plate=plate, county_id=county_id, area_id=area_id):
                """One neighbourhood. Empty answers are retried: the service returns an
                empty Demography now and then for a neighbourhood it serves a second
                later, and taking that as "no data" leaves permanent holes."""
                district_id, name = job
                for attempt in range(3):
                    try:
                        body = demography(
                            client,
                            countryId=1,
                            cityId=plate,
                            countyId=county_id,
                            districtId=int(district_id),
                            level=3,
                        )
                    except Exception as exc:  # noqa: BLE001
                        # 429 means we are asking faster than the service wants; waiting a
                        # beat is the whole fix, and logging every one of them buries the
                        # real errors.
                        if "429" in str(exc):
                            time.sleep(5)
                            continue
                        log(f"  {area_id}/{district_id}: {str(exc)[:120]}")
                        body = None
                    if body:
                        return district_id, {"name_tr": name, "demography": body}
                    time.sleep(1.0 * (attempt + 1))
                return district_id, None

            new = 0
            # A few at a time: one request at a time put the whole country at seventeen
            # hours, and the service answers three comfortably.
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                for district_id, record in pool.map(one, todo):
                    if record is None:
                        continue
                    have[district_id] = record
                    new += 1
                    if new % 40 == 0:
                        target.write_text(
                            json.dumps(have, ensure_ascii=False), encoding="utf-8"
                        )
            target.write_text(json.dumps(have, ensure_ascii=False), encoding="utf-8")
            done_total += new
            log(f"  {area_id} ({county_name}): {new} yeni, toplam {len(have)}")
    log(f"bitti — {done_total} yeni mahalle")


if __name__ == "__main__":
    main(sys.argv[1:])
