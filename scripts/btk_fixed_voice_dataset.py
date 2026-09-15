"""Build a quarterly fixed-voice dataset, split by technology and by operator group.

Source: "Cizelge 2-1 Abone Sayilarinin Teknoloji Bazinda Dagilimi" in the BTK
quarterly market reports. The table first appears in the 2015 report, so the
series starts at 2014-4; earlier reports carry no technology split.

The table is laid out as two rows per quarter. Turk Telekom reports analog PSTN
lines, ISDN voice-channel equivalents and payphones; the alternative operators
(STH - sabit telefon hizmeti) report PSTN, ISDN and VoIP. Turk Telekom's VoIP
cell is always a dash, and STH operators run no payphones, so those combinations
are absent rather than zero.

Each quarter is taken from the newest report that still prints it, because BTK
revises earlier quarters. The 2022-4 STH row is the clearest case: the 2022
report repeats the 2020-4 figures there, and the 2023 report prints the real
ones.

In 11 of the 46 quarters the TOPLAM column does not equal the sum of the cells
printed beside it. Every figure here was read back off the PDF a second time, so
these gaps are the reports', not a transcription slip; REPORTED_GAP records each
one exactly, and the test suite fails if any of them moves. Both numbers are
kept: `toplam` is what BTK publishes (and what the rest of the project uses),
`bilesen_toplami` is what its own breakdown adds up to.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"

FIELDS = ("donem", "tt_pstn", "tt_isdn", "tt_ankesor",
          "sth_pstn", "sth_isdn", "sth_voip", "toplam", "kaynak_rapor", "not")

# donem, (TT: pstn, isdn, payphone), (STH: pstn, isdn, voip), reported total, report
ROWS = (
    ("2014-4", 9_933_616, 311_382, 83_283, 1_550_397, 39_283, 610_904, 12_528_865, "2015", ""),
    ("2015-1", 9_526_966, 310_726, 82_716, 1_630_789, 33_857, 615_441, 12_200_495, "2015", ""),
    ("2015-2", 9_194_586, 310_484, 82_088, 1_678_619, 35_385, 636_511, 11_937_673, "2015", ""),
    ("2015-3", 8_897_899, 309_140, 81_159, 1_696_834, 38_376, 672_655, 11_696_067, "2015", ""),
    ("2015-4", 8_650_148, 311_250, 80_798, 1_702_423, 42_017, 706_419, 11_493_057, "2016", ""),
    ("2016-1", 8_342_741, 311_308, 80_022, 1_821_554, 39_908, 725_822, 11_322_407, "2016", ""),
    ("2016-2", 8_092_398, 309_944, 79_306, 1_921_786, 39_329, 805_732, 11_248_495, "2016", ""),
    ("2016-3", 7_847_143, 307_072, 77_738, 1_988_591, 37_420, 822_440, 11_080_404, "2016", ""),
    ("2016-4", 7_598_647, 307_100, 76_362, 2_116_435, 47_517, 931_498, 11_077_559, "2017", ""),
    ("2017-1", 7_342_782, 300_228, 74_509, 2_244_748, 40_075, 1_007_272, 11_009_614, "2017", ""),
    ("2017-2", 7_121_709, 294_820, 70_904, 2_371_281, 29_404, 1_079_326, 10_967_444, "2017", ""),
    ("2017-3", 6_916_080, 292_264, 69_160, 2_587_257, 28_075, 1_157_117, 11_049_953, "2018", ""),
    ("2017-4", 6_735_355, 292_816, 67_517, 2_834_614, 29_905, 1_348_237, 11_308_444, "2018", ""),
    ("2018-1", 6_520_797, 291_316, 66_149, 3_180_518, 35_614, 1_400_663, 11_495_057, "2018", ""),
    ("2018-2", 6_344_618, 291_816, 65_172, 3_392_354, 32_484, 1_365_185, 11_491_629, "2018", ""),
    ("2018-3", 6_177_626, 291_174, 64_711, 3_652_152, 35_743, 1_320_694, 11_542_100, "2018", ""),
    ("2018-4", 5_987_899, 287_048, 63_856, 3_973_934, 38_910, 1_320_694, 11_633_461, "2019",
     "STH VoIP hucresi 2018-3 ile ayni basilmis"),
    ("2019-1", 5_772_299, 281_036, 61_195, 4_210_508, 30_803, 1_281_814, 11_605_347, "2019", ""),
    ("2019-2", 5_549_107, 267_524, 57_561, 4_376_948, 30_565, 1_188_460, 11_470_165, "2019", ""),
    ("2019-3", 5_387_034, 267_332, 55_773, 4_621_801, 30_985, 1_179_623, 11_542_548, "2019", ""),
    ("2019-4", 5_219_515, 264_670, 55_113, 4_820_590, 25_084, 1_147_931, 11_532_903, "2020",
     "2019 raporu ayni satir icin 11.371.728 basmisti; kendi bilesenleriyle tutmuyordu"),
    ("2020-1", 5_036_689, 259_414, 55_779, 5_042_912, 23_189, 1_301_884, 11_716_867, "2020", ""),
    ("2020-2", 4_916_700, 255_552, 52_102, 5_385_636, 19_298, 1_460_803, 12_090_091, "2020", ""),
    ("2020-3", 4_788_334, 251_996, 51_020, 5_674_345, 21_004, 1_513_691, 12_300_390, "2020", ""),
    ("2020-4", 4_666_259, 251_112, 49_868, 5_958_347, 20_156, 1_502_862, 12_448_604, "2021", ""),
    ("2021-1", 4_527_322, 246_940, 48_357, 6_043_345, 20_118, 1_508_186, 12_394_268, "2021", ""),
    ("2021-2", 4_410_850, 238_280, 47_353, 6_100_583, 20_958, 1_488_930, 12_306_954, "2021", ""),
    ("2021-3", 4_303_407, 222_142, 46_754, 6_208_582, 20_069, 1_455_576, 12_256_530, "2021", ""),
    ("2021-4", 4_200_206, 213_664, 45_695, 6_320_114, 20_299, 1_510_038, 12_310_016, "2022", ""),
    ("2022-1", 4_085_078, 207_460, 45_016, 6_317_078, 18_463, 1_445_829, 12_118_924, "2022", ""),
    ("2022-2", 3_986_124, 201_682, 44_201, 6_143_079, 18_365, 1_388_585, 11_782_076, "2022", ""),
    ("2022-3", 3_891_957, 199_106, 43_575, None, None, None, 11_539_908, "2022",
     "STH satiri raporda 2022-2 ile ayni basilmis; toplamla tutmadigi icin bos birakildi"),
    ("2022-4", 3_808_570, 197_534, 42_456, 5_725_536, 15_862, 1_407_939, 11_197_979, "2023",
     "2022 raporu ayni satira 2020-4 STH degerlerini basmisti"),
    ("2023-1", 3_707_400, 195_908, 42_327, 5_491_190, 12_037, 1_443_345, 10_892_207, "2023", ""),
    ("2023-2", 3_597_132, 191_910, 40_294, 5_351_328, 12_037, 1_421_884, 10_614_585, "2023", ""),
    ("2023-3", 3_510_086, 188_006, 39_434, 5_199_018, 12_036, 1_358_695, 10_307_275, "2023", ""),
    ("2023-4", 3_425_610, 187_292, 38_158, 5_006_599, 8_883, 1_258_992, 9_925_534, "2024", ""),
    ("2024-1", 3_337_289, 184_898, 37_491, 4_827_703, 18_241, 990_485, 9_396_107, "2024", ""),
    ("2024-2", 3_253_460, 180_062, 37_073, 4_667_975, 17_235, 1_252_459, 9_408_264, "2024", ""),
    ("2024-3", 3_181_902, 177_208, 36_398, 4_524_078, 17_204, 1_219_938, 9_157_239, "2024", ""),
    ("2024-4", 3_104_080, 176_470, 36_224, 4_428_818, 8_464, 1_272_158, 9_026_297, "2025", ""),
    ("2025-1", 3_015_854, 168_108, 35_272, 4_402_089, 15_852, 1_264_387, 8_901_562, "2026-Q1", ""),
    ("2025-2", 2_938_294, 162_224, 33_611, 4_286_955, 14_555, 1_359_309, 8_794_961, "2026-Q1", ""),
    ("2025-3", 2_873_578, 161_130, 31_972, 4_127_229, 14_234, 1_261_411, 8_469_554, "2026-Q1", ""),
    ("2025-4", 2_799_628, 157_902, 31_175, 4_024_187, 14_811, 1_363_153, 8_390_856, "2026-Q1", ""),
    ("2026-1", 2_717_106, 155_466, 30_077, 3_947_996, 14_714, 1_421_379, 8_286_738, "2026-Q1", ""),
)

PARTS = ("tt_pstn", "tt_isdn", "tt_ankesor", "sth_pstn", "sth_isdn", "sth_voip")

# Reported TOPLAM minus the sum of the cells printed beside it, where the two
# disagree. Verified twice against the PDFs; see the module docstring.
REPORTED_GAP = {
    "2015-3": 4, "2015-4": 2, "2016-1": 1_052, "2018-4": -38_880,
    "2019-1": -32_308, "2020-1": -3_000, "2022-2": 40, "2022-4": 82,
    "2024-3": 511, "2024-4": 83, "2025-2": 13,
}


def build():
    rows = [dict(zip(FIELDS, r)) for r in ROWS]
    for row in rows:
        parts = [row[k] for k in PARTS]
        row["bilesen_toplami"] = None if None in parts else sum(parts)
        row["tt_toplam"] = row["tt_pstn"] + row["tt_isdn"] + row["tt_ankesor"]
        row["sth_toplam"] = (None if row["sth_pstn"] is None
                             else row["sth_pstn"] + row["sth_isdn"] + row["sth_voip"])
    return rows


def write(rows):
    out = RAW / "sabit_ses_teknoloji.csv"
    fieldnames = (*FIELDS[:-2], "tt_toplam", "sth_toplam", "bilesen_toplami",
                  "kaynak_rapor", "not")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row[k] is None else row[k]) for k in fieldnames})
    print(f"{out} yazildi")


if __name__ == "__main__":
    write(build())
