"""Which districts are the same place over time, when the map itself keeps changing.

A district time series is not comparable to itself. Denizli's Merkez was split in 2013
and Pamukkale — a district that already existed with five thousand people — came out of
it with three hundred thousand. Read literally that is +5.677% in one year, and every
per-cent-change column in the project has to either explain that or be wrong. It is the
open item behind "ilçede oran okunur, değişim okunmaz".

The successor mapping cannot be invented from the population file alone, because a split
does not say how the people were divided — but it does not need to. What makes a series
comparable is a **group that is stable across the whole window**: put the predecessor and
everything that came out of it in one bag, and the bag has the same territory in 2007 and
in 2025 whatever happened inside it. No shares, no assumptions, and the arithmetic is
exact rather than apportioned.

Groups are built from three observations, in this order:

1. **A district leaves the list** in year N and others **arrive** in the same province in
   the same year. That is the split, and the departure and the arrivals go in one bag.
2. **A district that was already there jumps** by more than the threshold in that same
   province-year. Pamukkale is this case: it existed, it did not arrive, and it grew by a
   factor of fifty-eight because it took half of Merkez. Only inside an event year — a
   district that doubles in a quiet year doubled honestly.
3. Anything else stays in a bag of its own.

The jump rule is confined to event years on purpose. Across the whole window there are
eighteen jumps over 40% in 2018 alone and nine in 2023, and none of them are boundary
changes: the first are small districts growing, the second is the earthquake moving people
around. Applied blindly, the rule would have welded a third of the country together.

**A rename is not a split.** One out and one in is `detect_district_renames.py`'s case and
it is left alone here: the registry already carries both ids with their validity, and the
adapters resolve them by year.

Verification is built in and refuses to write on failure: every group's population series
must move less than `MAX_JUMP` between consecutive years. That is what says the bag really
is the same territory — if a group still lurches, the grouping missed a member.

Run:  uv run python scripts/derive_district_successors.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from itertools import pairwise

import polars as pl

sys.path.insert(0, "src")

from veriatlas.areas import load_areas, load_districts
from veriatlas.config import DOCS, PUBLIC

TARGET = PUBLIC.parent / "src" / "veriatlas" / "data" / "areas_tr_district_groups.csv"
NOTES = DOCS / "ilce-ardillari.md"

#: Inside an event year, a district whose population moves by more than this — in either
#: direction, and by more than `MOVE_PEOPLE` at the same time — gave or took territory.
#:
#: Both directions, because a split has two sides and the taking side is not always the
#: new one. Denizli's Merkez became Merkezefendi while the already-existing Pamukkale took
#: half its people; İstanbul's 2008 reorganisation is the mirror image, with Büyükçekmece
#: losing three quarters of itself into districts that did not exist the year before.
#: Watching only the growth would have left both of those out of their own group.
MOVE = 0.25
MOVE_PEOPLE = 15_000

#: The check uses the same threshold as the rule, on purpose. A group that still moves
#: more than one member-sized boundary change means the grouping missed somebody — and
#: measuring the result by a different yardstick than the one that built it would let
#: exactly that through.
MAX_JUMP, MAX_JUMP_PEOPLE = MOVE, MOVE_PEOPLE


def population() -> tuple[dict, list[int]]:
    """District population per year, summed across every breakdown."""
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "district")
        )
        .with_columns(pl.col("period_start").dt.year().alias("year"))
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("value"))
    )
    if rows.is_empty():
        raise SystemExit("ilçe nüfusu depoda yok — önce scripts/load.py")
    people = {(r["area_id"], r["year"]): r["value"] for r in rows.iter_rows(named=True)}
    return people, sorted({year for _, year in people})


def events(people: dict, years: list[int], parent: dict) -> list[dict]:
    """Province-years where the district list changed, with everyone involved."""
    present = defaultdict(set)
    for area, year in people:
        present[(parent[area], year)].add(area)

    found = []
    for province in sorted({p for p, _ in present}):
        for before, after in pairwise(years):
            was = present.get((province, before), set())
            now = present.get((province, after), set())
            left, arrived = was - now, now - was
            # Whoever was already there and gave or took territory in the same year.
            moved = set()
            for area in was & now:
                first = people.get((area, before), 0)
                second = people.get((area, after), 0)
                if not first:
                    continue
                change = second - first
                if abs(change) > MOVE_PEOPLE and abs(change / first) > MOVE:
                    moved.add(area)

            # One out, one in and nobody else moved: a rename, and someone else's job.
            # With a mover in the same year it is not a rename — that is exactly Denizli,
            # where Merkez became Merkezefendi and Pamukkale quietly took half the city.
            if len(left) == 1 and len(arrived) == 1 and not moved:
                continue

            members = left | arrived | moved
            if not left and not arrived:
                # No district came or went: this is a transfer between two that stayed,
                # and it only counts as one if somebody gained while somebody else lost.
                # One mover on its own is a district that grew, which is allowed to happen.
                gained = any(people[(a, after)] > people[(a, before)] for a in moved)
                lost = any(people[(a, after)] < people[(a, before)] for a in moved)
                if not (gained and lost):
                    continue
            if len(members) < 2:
                # A district that simply appeared, with nothing to have come out of that
                # we can see. Left alone: guessing its parent is exactly what this file
                # exists not to do.
                continue
            found.append(
                {
                    "province": province,
                    "year": after,
                    "left": sorted(left),
                    "arrived": sorted(arrived),
                    "moved": sorted(moved),
                    "members": sorted(members),
                }
            )
    return found


def grouped(members_by_event: list[dict], areas: list[str]) -> dict[str, str]:
    """Union-find over the events: every area to the id of its group."""
    home = {area: area for area in areas}

    def root(area: str) -> str:
        while home[area] != area:
            home[area] = home[home[area]]
            area = home[area]
        return area

    for event in members_by_event:
        first, *rest = event["members"]
        for other in rest:
            a, b = root(first), root(other)
            if a != b:
                # The lower id wins so the group's name does not depend on the order the
                # events were read in.
                low, high = sorted([a, b])
                home[high] = low
    return {area: root(area) for area in areas}


def main() -> None:
    people, years = population()
    districts = load_districts()
    parent = {r["area_id"]: r["parent_id"] for r in districts.iter_rows(named=True)}
    name = {r["area_id"]: r["name_tr"] for r in districts.iter_rows(named=True)}
    provinces = {r["area_id"]: r["name_tr"] for r in load_areas().iter_rows(named=True)}
    areas = sorted({area for area, _ in people})

    found = events(people, years, parent)
    home = grouped(found, areas)

    members = defaultdict(list)
    for area, group in home.items():
        members[group].append(area)

    # region Verification and repair
    #
    # A group that still lurches has a member missing, and the missing member is nearly
    # always in the same province moving the other way in the same year — Hatay 2013 took
    # Payas out of Dörtyol and Arsuz out of İskenderun, and neither loss was steep enough
    # in per cent to trip the rule that built the groups. Rather than lowering that rule
    # until it swallows ordinary growth everywhere, the failure repairs itself: pull in the
    # province's counter-movers for that year, and check again.
    #
    # Exempt from all of this: a move that reverses the next year. Boundary changes are
    # permanent, so a district that gains a fifth and gives it straight back (Haymana in
    # 2018, Kırkağaç in 2010) moved on paper, not on the map.
    last = years[-1]

    def totals(inside):
        series = {}
        for year in years:
            total = sum(people.get((area, year), 0) for area in inside)
            if total:
                series[year] = total
        return series

    def lurches(inside):
        series = totals(inside)
        ordered = sorted(series)
        found = []
        for before, after in pairwise(ordered):
            if after != before + 1:
                continue
            move = series[after] / series[before] - 1
            if (
                abs(move) <= MAX_JUMP
                or abs(series[after] - series[before]) <= MAX_JUMP_PEOPLE
            ):
                continue
            # Did the level stick? A boundary change is permanent, so the year after
            # should look like the year of the change and not like the year before it.
            # Haymana goes 27k → 46k → 31k in 2018: measured as two moves that is a jump
            # and a partial reversal, measured as a level it is a spike that went home.
            # Comparing levels rather than moves is what tells those apart, and getting it
            # wrong welded Keçiören and Sincan onto Haymana for a boundary that never
            # moved.
            following = series.get(after + 1)
            earlier = series.get(before - 1)
            back_after = (
                following is not None and abs(following / series[before] - 1) < MAX_JUMP
            )
            back_before = (
                earlier is not None and abs(series[after] / earlier - 1) < MAX_JUMP
            )
            if back_after or back_before:
                continue
            found.append((before, after, move))
        return found

    for _ in range(5):
        broken = [(group, lurches(members[group])) for group in list(members)]
        broken = [(group, jumps) for group, jumps in broken if jumps]
        if not broken:
            break
        for group, jumps in broken:
            province = parent.get(group, "")
            for before, after, move in jumps:
                helpers = [
                    area
                    for area in areas
                    if parent.get(area) == province
                    and home[area] != group
                    and people.get((area, before))
                    and people.get((area, after))
                    and (people[(area, after)] - people[(area, before)]) * move < 0
                    and abs(people[(area, after)] - people[(area, before)]) > 5_000
                ]
                for area in helpers:
                    old_group = home[area]
                    for moving in members.pop(old_group, [area]):
                        home[moving] = group
                        members[group].append(moving)
    trouble = [
        (group, before, after, move, [name.get(a, a) for a in members[group]])
        for group in members
        for before, after, move in lurches(members[group])
    ]
    # endregion

    rows = []
    for group in sorted(members):
        inside = sorted(members[group], key=lambda a: -people.get((a, last), 0))
        label = " + ".join(name.get(a, a) for a in inside)
        rows.append(
            {
                "area_id": group,
                "group_label": label if len(inside) > 1 else name.get(group, group),
                "member_count": len(inside),
                "province": provinces.get(parent.get(group, ""), ""),
                "basis": "observed" if len(inside) > 1 else "single",
            }
        )

    if trouble:
        print("UYARI: gruplar hâlâ sıçrıyor, dosya yazılmadı:")
        for group, before, after, move, inside in trouble[:10]:
            print(
                "  {:<12} {}→{} %{:+.0f}  {}".format(
                    group, before, after, 100 * move, ", ".join(inside)[:60]
                )
            )
        raise SystemExit(1)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["area_id", "group_id", "group_label", "member_count", "basis"],
        )
        writer.writeheader()
        for area in areas:
            group = home[area]
            inside = sorted(members[group], key=lambda a: -people.get((a, last), 0))
            writer.writerow(
                {
                    "area_id": area,
                    "group_id": group,
                    "group_label": " + ".join(name.get(a, a) for a in inside),
                    "member_count": len(inside),
                    "basis": "observed" if len(inside) > 1 else "single",
                }
            )

    multi = [g for g, inside in members.items() if len(inside) > 1]
    lines = [
        "# İlçe ardılları — bölünen ilçeler ve karşılaştırılabilir gruplar",
        "",
        "Bir ilçenin nüfus serisi kendisiyle karşılaştırılabilir değil: Denizli'nin Merkez",
        "ilçesi 2013'te bölündü ve zaten var olan Pamukkale beş bin kişiden üç yüz bine",
        "çıktı. Bu %+5.677'lik artış demografi değil, sınır değişikliği.",
        "",
        "Bölünmenin insanları nasıl paylaştırdığını nüfus dosyası söylemiyor — ama",
        "söylemesi de gerekmiyor. Karşılaştırmayı mümkün kılan şey, **pencerenin tamamında",
        "sabit kalan bir grup**: bölünen ilçeyi ve ondan çıkan her şeyi aynı torbaya koy,",
        "torbanın toprağı 2007'de de 2025'te de aynı olsun. Pay tahmini yok, aritmetik tam.",
        "",
        f"Gözlenen olay: **{len(found)}**. Birden çok ilçe içeren grup: **{len(multi)}**.",
        f"Doğrulama: hiçbir grup ardışık iki yılda hem %{int(MAX_JUMP * 100)}'ten çok hem",
        f"{MAX_JUMP_PEOPLE:,} kişiden çok oynamıyor — ikisi birden olsaydı grup bir üyesini".replace(
            ",", "."
        ),
        "kaçırmış olurdu ve dosya yazılmazdı. İki koşul birden, çünkü tek başına her biri",
        "gürültü: Çamlıdere üç bin kişiyle ikiye katlanıp yarılanıyor (2018 adres denetimi,",
        "2023 depremi), kaçan bir bölünme üyesi ise asla küçük olmuyor.",
        "",
        "| il | yıl | ayrılan | gelen | toprak alan/veren |",
        "|---|---|---|---|---|",
    ]
    for event in found:
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                provinces.get(event["province"], event["province"]),
                event["year"],
                ", ".join(name.get(a, a) for a in event["left"]) or "—",
                ", ".join(name.get(a, a) for a in event["arrived"]) or "—",
                ", ".join(name.get(a, a) for a in event["moved"]) or "—",
            )
        )
    lines += [
        "",
        "## Nasıl okunur",
        "",
        "* **Ayrılan**: o yıl listeden düşen ilçe. Çoğu zaman 'Merkez'.",
        "* **Gelen**: aynı il ve aynı yılda listeye giren ilçeler.",
        "* **Büyüyen**: zaten var olan ama o yıl iki katından fazla büyüyen ilçe — yani",
        "  toprağın bir kısmını alan. Bu kural yalnız olay yıllarında işletiliyor:",
        "  2018'de %40'ı aşan on sekiz sıçrama var ve hiçbiri sınır değişikliği değil,",
        "  2023'tekiler ise depremin yerinden ettiği nüfus.",
        "* **Ad değişikliği bölünme değildir**: bir çıkıp bir girdiğinde bu dosya",
        "  karışmıyor, `detect_district_renames.py` ve kayıttaki geçerlilik aralıkları",
        "  o işi yapıyor.",
        "",
        "Grup kimliği, gruptaki en küçük alan kimliğidir — okuma sırasına göre değişmesin",
        "diye. Etiket, üyeleri 2025 nüfusuna göre büyükten küçüğe yazar.",
    ]
    NOTES.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("yazildi:", TARGET)
    print("        ", NOTES)
    print("  olay:", len(found), "| cok uyeli grup:", len(multi), "| ilce:", len(areas))
    for group in sorted(multi):
        inside = sorted(members[group], key=lambda a: -people.get((a, last), 0))
        print(
            "   {:<12} {}".format(
                provinces.get(parent.get(group, ""), ""),
                " + ".join(name.get(a, a) for a in inside),
            )
        )


if __name__ == "__main__":
    main()
