r"""Pack one indicator into the shape a map actually asks for.

The web export writes a tidy row per (area, period, breakdown) — right for analysis, wrong
for painting: colouring 38.000 neighbourhoods for one year means reading a million rows
and summing them in the browser. A map asks a much smaller question, always the same one:

    for this level and this year, what is the value in each area?

So this writes a cube: the years once, then one array of values per area, in that order.
Nulls are kept as nulls — a year an area has no reading for must stay empty, because the
map paints "veri yok" in its own colour and a zero there would be a lie with a shade.

    public/harita/<gösterge>-<düzey>.json

Breakdowns are summed away when the unit allows it (`additive = true` in the dictionary):
the total population of a district is the sum of its age-sex cells. An index or a rate
cannot be summed, so an indicator in such a unit is written per breakdown instead, one
cube per combination, and the page chooses.

**With `--kirilim` a countable indicator also gets one cube per single breakdown value** —
women, 25-29, university graduates — with the other breakdowns summed away. One dim at a
time on purpose: every pair of dims multiplies the files, and marital status alone
(5 × 2 × 16) would write three hundred of them to answer a question nobody asked yet.

Levels: provinces and districts always, the finer ones only when asked. A neighbourhood
cube is several megabytes and the map only needs it when the reader goes that deep.

Run:  uv run python scripts/build_map_cube.py population
      uv run python scripts/build_map_cube.py --tumu          # her uygun gösterge
      uv run python scripts/build_map_cube.py --tumu --ince    # mahalle ve köy de
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC
from veriatlas.indicators import load

OUT = PUBLIC / "harita"


#: The export does not name its files after the indicator — `marital_status` lands in
#: `marital.csv.gz`, `education_level_district` in `education-level-by-district.csv.gz`.
#: The mapping is read from the exporter itself rather than guessed, so a rename there
#: cannot leave a cube pointing at a file that no longer exists.
def export_names() -> dict[str, str]:
    """`DATASETS` from the exporter, read rather than imported.

    Importing that module runs it, and it opens the warehouse on the way in; this only
    needs one dict literal, so the file is parsed and the literal lifted out of the tree.
    """
    import ast

    source = Path(__file__).with_name("export_web.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        # Only the literal at the top; the file also calls DATASETS.update() with values
        # it computes, and those cannot be read without running it.
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        if not any(getattr(t, "id", None) == "DATASETS" for t in node.targets):
            continue
        # `**BASKA_SOZLUK` inside the literal shows up as a None key; those entries
        # cannot be read without running the file, and the ones we need are plain pairs.
        pairs = {}
        for key, value in zip(node.value.keys, node.value.values, strict=True):
            if key is None or not isinstance(value, ast.Constant):
                continue
            pairs[ast.literal_eval(key)] = value.value.removesuffix(".csv")
        return pairs
    raise SystemExit("export_web.py içinde DATASETS sözlüğü bulunamadı")


#: The export's file naming: the finer levels get their own file; the province one has no
#: suffix.
LEVEL_FILES = {
    "province": "",
    "district": "-district",
    "neighbourhood": "-neighbourhood",
    "village": "-village",
}

#: The map draws neighbourhoods and villages in one layer, because they are one kind of
#: place; the export keeps them in two files, because TÜİK counts them in two tables. The
#: cube for that layer is both files read together — without it every village in a
#: non-metropolitan province paints as "veri yok" while its neighbours are coloured.
SETTLEMENT = "yerlesim"
SETTLEMENT_PARTS = ("neighbourhood", "village")


NAMES: dict[str, str] = {}


def export_path(indicator: str, level: str) -> Path:
    if not NAMES:
        NAMES.update(export_names())
    stem = NAMES.get(indicator, indicator.replace("_", "-")) + LEVEL_FILES[level]
    return PUBLIC / f"{stem}.csv.gz"


def usable(spec) -> str | None:
    """Why this indicator cannot become a cube yet, or None if it can.

    A cube is one number per area per year, so a breakdown has to go somewhere. It is
    summed away when the unit allows it; when it does not — an index, a rate, a share —
    the only honest cube is one per breakdown, and that is not built yet. An indicator
    with no breakdown at all needs no summing and is always fine.
    """
    if not spec.dims:
        return None
    if spec.unit.additive:
        return None
    return f"toplanamaz birim ({spec.unit.unit_id}) + kırılım"


def slices_of(header: list[str]) -> list[str]:
    """The breakdown columns of an export, in file order."""
    known = {
        "area_id",
        "area",
        "level",
        "year",
        "value",
        "quality_flag",
        "vintage",
        "source_id",
    }
    return [name for name in header if name not in known]


def safe(text: str) -> str:
    """A dim value as a file name: the ids are ascii already, but ages carry a dash and
    education levels an underscore, and both must survive a round trip."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in text)


def build(
    indicator: str, fine: bool = False, quiet: bool = False, by_slice: bool = False
) -> list[str]:
    dictionary = load()
    spec = dictionary.indicators[indicator]
    reason = usable(spec)
    if reason:
        raise SystemExit(f"{indicator}: {reason}")

    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    levels = (
        {**LEVEL_FILES, SETTLEMENT: None}
        if fine
        else {"province": "", "district": "-district"}
    )
    for level in levels:
        if level == SETTLEMENT:
            paths = [export_path(indicator, part) for part in SETTLEMENT_PARTS]
            paths = [path for path in paths if path.exists()]
            if len(paths) < 2:
                continue
        else:
            path = export_path(indicator, level)
            if not path.exists():
                continue
            paths = [path]

        # (boyut, değer) → alan → yıl → toplam. None anahtarı hepsinin toplamıdır ve
        # her zaman yazılır; kırılım küpleri yalnız --kirilim ile istendiğinde.
        buckets: dict[tuple[str, str] | None, dict[str, dict[str, float]]] = {
            None: defaultdict(lambda: defaultdict(float))
        }
        names: dict[str, str] = {}
        for path in paths:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                header = handle.readline().rstrip("\n").split(",")
                area_at, name_at = header.index("area_id"), header.index("area")
                year_at, value_at = header.index("year"), header.index("value")
                dims = slices_of(header) if by_slice else []
                dim_at = {dim: header.index(dim) for dim in dims}
                for line in handle:
                    row = line.rstrip("\n").split(",")
                    value = row[value_at]
                    if not value:
                        continue
                    area, year, amount = row[area_at], row[year_at], float(value)
                    names.setdefault(area, row[name_at])
                    buckets[None][area][year] += amount
                    for dim in dims:
                        value_id = row[dim_at[dim]]
                        if not value_id:
                            continue
                        key = (dim, value_id)
                        if key not in buckets:
                            buckets[key] = defaultdict(lambda: defaultdict(float))
                        buckets[key][area][year] += amount

        totals = buckets[None]

        if not totals:
            continue
        years = sorted({year for area in totals.values() for year in area})
        cube = {
            "gosterge": indicator,
            "ad": spec.label_tr,
            "birim": spec.unit.unit_id,
            "duzey": level,
            "yillar": years,
            "deger": {
                area: [rows.get(year) for year in years]
                for area, rows in totals.items()
            },
            "ad_tr": names,
        }
        stem = indicator.replace("_", "-")
        target = OUT / f"{stem}-{level}.json"
        target.write_text(
            json.dumps(cube, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        written.append(
            f"{level}: {len(totals):,} alan × {len(years)} yıl, {target.stat().st_size // 1024} KB"
        )

        for key, rows in buckets.items():
            if key is None:
                continue
            dim, value = key
            part = dict(cube)
            part["kirilim"] = {"boyut": dim, "deger": value}
            part["deger"] = {
                area: [years_of.get(year) for year in years]
                for area, years_of in rows.items()
            }
            slice_file = OUT / f"{stem}-{level}--{safe(dim)}-{safe(value)}.json"
            slice_file.write_text(
                json.dumps(part, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        if by_slice and len(buckets) > 1:
            written.append(f"{level}: {len(buckets) - 1} kırılım küpü")

    if not written and not quiet:
        raise SystemExit(f"{indicator}: dışa aktarılmış dosya bulunamadı")
    if not quiet:
        for line in written:
            print(" ", line.replace(",", "."))
    return written


def build_all(fine: bool) -> None:
    dictionary = load()
    made = skipped = 0
    for name, spec in dictionary.indicators.items():
        if usable(spec):
            skipped += 1
            continue
        try:
            if build(name, fine=fine, quiet=True):
                made += 1
        except Exception as error:  # noqa: BLE001 - one bad file must not end the batch
            print(name, "HATA:", str(error)[:120])
    print(f"küp yazılan {made} gösterge, kırılımı toplanamadığı için atlanan {skipped}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if "--tumu" in flags:
        build_all("--ince" in flags)
    else:
        for name in args or ["population"]:
            print(name)
            build(name, fine="--ince" in flags, by_slice="--kirilim" in flags)
