"""Flatten KGM's district-to-district distance sheet into a parquet file.

`ilcemesafe.xlsx` is a long table (from province, from district, to province, to
district, km) of about a million rows; reading it with openpyxl takes minutes, so it is
done once here and the adapter reads `raw/kgm/district_distance_cells.parquet`.
"""

import sys
from pathlib import Path

import openpyxl
import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import RAW

SOURCE = RAW / "kgm" / "pdf" / "Root_Uzakliklar" / "ilcemesafe.xlsx"
TARGET = RAW / "kgm" / "district_distance_cells.parquet"


def main() -> None:
    sheet = openpyxl.load_workbook(SOURCE, read_only=True).worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    header = next(rows)
    if [str(h).strip() for h in header[:5]] != [
        "Kalkış İl",
        "Kalkış İlçe",
        "Varış İl",
        "Varış İlçe",
        "Toplam Uzunluk(km)",
    ]:
        raise SystemExit("beklenmeyen başlık: " + repr(header))
    records = [r[:5] for r in rows if r[0] is not None]
    frame = pl.DataFrame(
        records,
        schema=["from_province", "from_district", "to_province", "to_district", "km"],
        orient="row",
        infer_schema_length=None,
    )
    frame.write_parquet(Path(TARGET))
    print(frame.height, "satır ->", TARGET)


if __name__ == "__main__":
    main()
