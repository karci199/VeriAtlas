"""Build the M2M (machine-to-machine) subscriber series from the BTK reports.

Two sources of different precision, kept apart:

  * ANNUAL - the executive-summary table ("Ozet Bilgiler") prints M2M to the
    single subscriber, alongside the total mobile count, for the report year and
    the one before it. That is text, not a chart, so these are exact. Only 2011
    is missing from every summary table; it exists solely as a bar label in the
    2014 report's figure and is therefore rounded to the hundred thousand.

  * QUARTERLY - figure "Sekil 4-2 M2M Abone Sayisi", read off a rendered page.
    The newest report's window is 2024-1 to 2026-1. Earlier reports carry their
    own years' quarters and could extend this backwards; that has not been done.

Two definition changes matter more than the numbers:

  1. "Mobil abone (kisi) sayisi" in the summary table used to be the total minus
     M2M *and* minus mobile-computer internet subscribers. From the 2021 report
     it is the total minus M2M alone - the mobile-computer line is still printed
     but no longer taken out. The kisi_formulu column records which applies, and
     the test suite checks each year against the arithmetic it claims.
  2. From the 2026-1 report BTK stopped counting M2M in the headline mobile
     subscriber figure altogether and recomputed penetration on real users only.
     So 2026-1's 85.960.875 is not comparable with the 99.691.361 printed for
     2025 - the M2M-inclusive 2026-1 total is about 98,3 million.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"

# yil: (m2m, toplam mobil abone incl. M2M, raporun "kisi" satiri, kaynak rapor)
ANNUAL = (
    (2011, 1_200_000, None, None, "2014"),
    (2012, 1_692_180, 67_680_547, 64_313_834, "2013"),
    (2013, 2_112_901, 69_661_108, 65_847_193, "2013"),
    (2014, 2_515_527, 71_888_416, 68_018_143, "2014"),
    (2015, 3_159_472, 73_639_261, 68_882_183, "2015"),
    (2016, 3_959_664, 75_061_699, 69_864_286, "2016"),
    (2017, 4_495_436, 77_800_170, 72_476_365, "2017"),
    (2018, 5_209_371, 80_117_999, 74_252_629, "2019"),
    (2019, 5_861_438, 80_790_877, 74_206_085, "2019"),
    (2020, 6_380_454, 82_128_104, 75_257_337, "2020"),
    (2021, 7_444_802, 86_288_834, 78_844_032, "2021"),
    (2022, 8_090_447, 90_297_565, 82_207_118, "2022"),
    (2023, 9_332_867, 92_230_985, 82_898_118, "2023"),
    (2024, 10_394_461, 94_320_271, 83_925_810, "2024"),
    (2025, 11_941_485, 99_691_361, 87_749_876, "2025"),
)

# Bar labels off "Sekil 4-2", in millions, from the 2026-1 report.
QUARTERLY = (
    ("2024-1", 9.5), ("2024-2", 9.7), ("2024-3", 10.0), ("2024-4", 10.4),
    ("2025-1", 10.8), ("2025-2", 11.2), ("2025-3", 11.4), ("2025-4", 11.9),
    ("2026-1", 12.3),
)

# Mobile-computer internet subscribers, as printed in the same summary tables.
# Listed only for the years the "kisi" row actually subtracts them (2012-2020).
MOBILE_COMPUTER = {
    2012: 1_674_533, 2013: 1_701_014, 2014: 1_354_746, 2015: 1_597_606,
    2016: 1_237_749, 2017: 828_369, 2018: 655_999, 2019: 723_354,
    2020: 490_313,
}

# 2026-1 is reported on the new, M2M-excluding basis.
REAL_USERS_2026Q1 = 85_960_875

# Year-end population, exactly as footnoted in the reports (TUIK). 2011 and 2018
# are absent: no report footnotes them, and no outside figure is substituted, so
# those two years carry no penetration.
NUFUS = {
    2012: 75_627_384, 2013: 76_667_864, 2014: 77_695_904, 2015: 78_741_053,
    2016: 79_814_871, 2017: 80_810_525, 2019: 83_154_997, 2020: 83_614_362,
    2021: 84_680_273, 2022: 85_279_553, 2023: 85_372_377, 2024: 85_664_944,
    2025: 86_092_168,
}
# Population excluding ages 0-9, the base BTK uses for its alternative rate.
NUFUS_0_9_HARIC = {
    2013: 64_190_215, 2015: 66_021_818, 2019: 70_348_822, 2020: 70_966_062,
    2021: 72_142_462, 2022: 72_980_856, 2023: 73_457_837, 2024: 74_197_473,
    2025: 75_079_696,
}


def build_annual():
    keys = ("yil", "m2m", "toplam", "kisi", "kaynak_rapor")
    rows = [dict(zip(keys, r)) for r in ANNUAL]
    for row in rows:
        toplam, yil = row["toplam"], row["yil"]
        row["m2m_pay"] = (None if toplam is None
                          else round(100 * row["m2m"] / toplam, 2))
        row["kisi_formulu"] = ("toplam - m2m - mobil_bilgisayar"
                               if yil in MOBILE_COMPUTER else "toplam - m2m")
        # BTK's own alternative rate divides total-minus-M2M by population; the
        # "kisi" row is not used, since for 2012-2020 it takes out one item more.
        gercek = None if toplam is None else toplam - row["m2m"]
        row["gercek_kullanici"] = gercek
        nufus, nufus9 = NUFUS.get(yil), NUFUS_0_9_HARIC.get(yil)
        row["nufus"] = nufus
        row["yaygin_m2m_dahil"] = (None if (toplam is None or nufus is None)
                                   else round(100 * toplam / nufus, 1))
        row["yaygin_m2m_haric"] = (None if (gercek is None or nufus is None)
                                   else round(100 * gercek / nufus, 1))
        row["yaygin_m2m_ve_0_9_haric"] = (None if (gercek is None or nufus9 is None)
                                          else round(100 * gercek / nufus9, 1))
    return rows


def build_quarterly():
    return [{"donem": d, "m2m_milyon": v} for d, v in QUARTERLY]


def write(rows, name, fields):
    out = RAW / name
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in fields})
    print(f"{out} yazildi")


if __name__ == "__main__":
    write(build_annual(), "m2m_yillik.csv",
          ("yil", "m2m", "toplam", "gercek_kullanici", "kisi", "nufus", "m2m_pay",
           "yaygin_m2m_dahil", "yaygin_m2m_haric", "yaygin_m2m_ve_0_9_haric",
           "kisi_formulu", "kaynak_rapor"))
    write(build_quarterly(), "m2m_ceyreklik.csv", ("donem", "m2m_milyon"))
