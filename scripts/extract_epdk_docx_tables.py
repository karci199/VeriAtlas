"""Flatten every table of the EPDK yearly Word reports into one parquet file.

Each table becomes rows of (file, market, report year, table index, caption, row, col, text).
The caption is the nearest preceding paragraph that starts with "Tablo". Reading the XML
directly keeps merged cells as the repeated text Word shows, and needs no Office install.
Output: raw/epdk/docx_cells.parquet.
"""

import re
import sys
import zipfile
from xml.etree import ElementTree as ET

import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import RAW

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = RAW / "epdk" / "files"


def text(node) -> str:
    return "".join(t.text or "" for t in node.iter(W + "t")).strip()


def main() -> None:
    records = []
    for path in sorted(ROOT.glob("*_yillik/*.docx")):
        body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(
            W + "body"
        )
        head = " ".join(text(p) for p in list(body)[:60] if p.tag == W + "p")
        years = [int(y) for y in re.findall(r"\b(20[0-2]\d)\b", head)]
        caption = ""
        table_no = 0
        for node in body:
            if node.tag == W + "p":
                t = text(node)
                if re.match(r"^\s*Tablo\s*[\d.:]", t):
                    caption = t
            elif node.tag == W + "tbl":
                table_no += 1
                for r, tr in enumerate(node.iter(W + "tr")):
                    for c, tc in enumerate(tr.findall(W + "tc")):
                        records.append(
                            (
                                path.name,
                                path.parent.name,
                                min(years) if years else 0,
                                table_no,
                                caption,
                                r,
                                c,
                                text(tc),
                            )
                        )
        print(path.parent.name, path.name, table_no, "tablo", flush=True)
    frame = pl.DataFrame(
        records,
        schema=[
            "file",
            "market",
            "year_hint",
            "table",
            "caption",
            "row",
            "col",
            "text",
        ],
        orient="row",
    )
    frame.write_parquet(RAW / "epdk" / "docx_cells.parquet")
    print(frame.height, "hucre")


if __name__ == "__main__":
    main()
