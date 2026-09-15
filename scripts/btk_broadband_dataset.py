"""Build a fixed-broadband dataset from BTK quarterly market reports.

Every figure below is the year-end (fourth-quarter) row of "Cizelge 3-1 Toplam
Internet Abone Sayilari", plus the 2026-1 row from the latest report. BTK revises
past quarters silently, so each period is taken from the NEWEST report that still
prints it; the report year is recorded per row.

Reporting caveats that break naive year-on-year reading:
  * 2008-2009: fiber is not broken out at all and mobile is a single line.
  * 2010: mobile computer/handset are still one line ("Mobil internet").
  * 2010-2013: FTTH/FTTB are reported only as a combined "Fiber" total.
  * up to 2020: fixed wireless sits inside "Diger"; it becomes its own line in 2021.
  * "Diger" holds ISDN, satellite, metro ethernet, PLC, frame relay and ATM.
    Dial-up is outside the table (it is not broadband) and ends in 2017.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
REF = ROOT / "raw" / "ref"
BASE_YEAR = 2025

FIELDS = (
    "donem", "xdsl", "kablo", "ftth", "fttb", "fiber", "kablosuz_sabit", "diger",
    "mobil_bilgisayar", "mobil_cep", "toplam", "kaynak_rapor",
)

# donem: (xdsl, kablo, ftth, fttb, fiber, fixed wireless, other, mobile pc,
#         mobile handset, reported total, source report)
# None marks "not broken out in that report", which is not the same as zero.
ROWS = (
    ("2008-4", 5_894_522, 67_408, None, None, None, None, 24_171, None, 0, 5_986_101, "2009"),
    ("2009-4", 6_216_028, 146_622, None, None, None, None, 23_644, None, 396_363, 6_782_657, "2009"),
    ("2010-4", 6_640_911, 273_908, None, None, 154_059, None, 155_478, None, 1_448_020, 8_672_376, "2011"),
    ("2011-4", 6_776_036, 460_451, None, None, 267_144, None, 159_383, 1_547_421, 4_907_380, 14_117_815, "2012"),
    ("2012-4", 6_643_299, 500_658, None, None, 645_092, None, 139_665, 1_674_533, 18_045_808, 27_649_055, "2013"),
    ("2013-4", 6_644_543, 486_497, None, None, 1_193_704, None, 116_043, 1_701_014, 22_472_129, 32_613_930, "2014"),
    ("2014-4", 6_799_100, 558_456, 472_424, 984_973, 1_457_397, None, 97_326, 1_354_746, 31_005_915, 41_272_940, "2015"),
    ("2015-4", 7_157_200, 629_064, 641_776, 1_030_852, 1_672_628, None, 90_845, 1_597_606, 37_469_948, 48_617_291, "2016"),
    ("2016-4", 7_764_204, 736_916, 758_150, 1_167_930, 1_926_080, None, 116_077, 1_237_749, 50_499_165, 62_280_191, "2017"),
    ("2017-4", 8_656_181, 826_734, 1_014_122, 1_322_565, 2_336_687, None, 105_303, 828_369, 56_116_304, 68_869_578, "2017"),
    ("2018-4", 9_491_634, 932_121, 1_465_353, 1_335_204, 2_800_557, None, 182_914, 655_999, 60_436_864, 74_500_089, "2019"),
    ("2019-4", 9_662_248, 1_084_446, 1_981_382, 1_231_916, 3_213_298, None, 271_986, 723_354, 61_684_363, 76_639_695, "2020"),
    ("2020-4", 11_036_313, 1_298_340, 2_709_882, 1_295_998, 4_005_880, None, 394_320, 490_313, 65_139_424, 82_364_590, "2021"),
    ("2021-4", 11_386_117, 1_373_647, 3_507_646, 1_333_262, 4_840_908, 316_810, 218_254, 447_196, 69_581_807, 88_164_739, "2022"),
    ("2022-4", 11_171_402, 1_419_362, 4_419_013, 1_283_852, 5_702_865, 483_703, 221_471, 706_493, 70_944_563, 90_649_859, "2023"),
    ("2023-4", 10_816_291, 1_464_420, 5_491_159, 1_262_220, 6_753_379, 394_724, 171_416, 669_193, 73_046_184, 93_315_607, "2024"),
    ("2024-4", 10_124_256, 1_471_221, 6_845_641, 1_226_988, 8_072_629, 637_560, 190_964, 706_492, 75_180_553, 96_383_675, "2025"),
    ("2025-4", 8_678_952, 1_490_749, 8_670_664, 1_174_562, 9_845_226, 795_079, 189_889, 775_395, 75_667_652, 97_442_942, "2026-Q1"),
    ("2026-1", 8_347_167, 1_513_449, 9_150_396, 1_151_936, 10_302_332, 867_666, 216_512, 762_257, 77_495_014, 99_504_397, "2026-Q1"),
)

# Cizelge 3-3/3-4, 2026-Q1 report: fixed-broadband ISP service revenue, lira.
ANNUAL_REVENUE = {
    2020: 12_334_386_474, 2021: 15_406_066_019, 2022: 21_463_001_301,
    2023: 34_563_506_139, 2024: 63_353_088_238, 2025: 105_593_891_660,
}
QUARTERLY_REVENUE = {
    "2025-1": 21_151_569_648, "2025-2": 23_616_740_231, "2025-3": 28_774_264_523,
    "2025-4": 32_051_317_257, "2026-1": 33_475_278_067,
}


def fixed_total(row):
    """Fixed broadband = reported total minus the two mobile lines."""
    mobile = (row["mobil_bilgisayar"] or 0) + (row["mobil_cep"] or 0)
    return row["toplam"] - mobile


def build():
    rows = [dict(zip(FIELDS, r)) for r in ROWS]
    for row in rows:
        row["sabit_toplam"] = fixed_total(row)
    return rows


def write(rows):
    out = RAW / "sabit_genisbant.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=(*FIELDS[:-1], "sabit_toplam", "kaynak_rapor"))
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row[k] is None else row[k]) for k in w.fieldnames})

    out = RAW / "sabit_genisbant_gelir.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("donem", "gelir_tl", "tur"))
        for year, value in sorted(ANNUAL_REVENUE.items()):
            w.writerow((year, value, "yillik"))
        for period, value in sorted(QUARTERLY_REVENUE.items()):
            w.writerow((period, value, "ceyreklik"))


def arpu(rows):
    """Monthly revenue per fixed-broadband subscriber, three ways.

    Subscribers are the mean of the opening and closing year-end counts, since
    the revenue accrues over the year. Nominal lira are useless across this
    stretch of inflation, so the same figure is also given in current dollars
    and in constant BASE_YEAR lira.
    """
    with open(REF / "makro.csv", encoding="utf-8") as fh:
        macro = {int(r["yil"]): r for r in csv.DictReader(fh)}
    year_end = {int(r["donem"][:4]): r["sabit_toplam"]
                for r in rows if r["donem"].endswith("-4")}
    base_cpi = float(macro[BASE_YEAR]["tufe_2010_100"])

    out = []
    for year, revenue in sorted(ANNUAL_REVENUE.items()):
        subs = (year_end[year - 1] + year_end[year]) / 2
        monthly = revenue / subs / 12
        out.append({
            "yil": year,
            "gelir_tl": revenue,
            "ortalama_abone": round(subs),
            "aylik_tl": round(monthly, 2),
            "aylik_usd": round(monthly / float(macro[year]["usd_try_ortalama"]), 2),
            f"aylik_tl_{BASE_YEAR}": round(
                monthly * base_cpi / float(macro[year]["tufe_2010_100"]), 2),
        })
    return out


def write_arpu(rows):
    values = arpu(rows)
    with open(RAW / "sabit_genisbant_arpu.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(values[0]))
        w.writeheader()
        w.writerows(values)


if __name__ == "__main__":
    built = build()
    write(built)
    write_arpu(built)
