"""An older report writes a party's zero as an empty cell, not as "0".

Counting the numbers in a row and comparing that count against the table width therefore
drops every row of such a report, and the file parses to nothing at all -- no error, no
warning, an empty result that looks exactly like a report with no data in it. This is the
failure these tests exist to catch.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import parse_secim

HEADER = (
    "<tr><td></td><td>İl</td><td></td><td></td><td>İlçe</td><td></td>"
    "<td>Belediye</td><td></td><td>Sandık sayısı</td><td></td>"
    "<td>Kayıtlı seçmen sayısı</td><td></td><td>Oy kullanan seçmen sayısı</td><td></td>"
    "<td>Gecerli oy sayısı</td><td></td><td>ANAP</td><td></td><td>CHP</td></tr>"
)


def row(
    indent: int,
    name: str,
    sandik: str,
    kayitli: str,
    oy: str,
    gecerli: str,
    anap: str,
    chp: str,
) -> str:
    cells = [""] * 19
    cells[indent] = name
    for column, value in zip(
        (8, 10, 12, 14, 16, 18), (sandik, kayitli, oy, gecerli, anap, chp), strict=True
    ):
        cells[column] = value
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def write(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    path = tmp_path / "adana.html"
    path.write_text(f"<table>{HEADER}{body}</table>", encoding="windows-1254")
    return path


def test_bos_hucre_sifir_sayilir(tmp_path: pathlib.Path) -> None:
    """A blank cell is a zero, and the row it sits in still parses."""
    body = (
        row(1, "Adana", "2799", "835154", "713149", "667923", "143606", "200000")
        + row(4, "Seyhan", "1565", "562326", "489246", "476233", "90000", "150000")
        # Karayusuflu's CHP cell is empty: the party took no votes there.
        + row(6, "Karayusuflu", "5", "1381", "1264", "1229", "596", "")
    )
    kayitlar = parse_secim.read_report(write(tmp_path, body))
    duzeyler = [k["level"] for k in kayitlar]
    assert duzeyler == ["il", "ilce", "mahalle"], kayitlar
    yerlesim = kayitlar[-1]
    assert yerlesim["name"] == "Karayusuflu"
    assert yerlesim["parent"] == "Seyhan"
    assert yerlesim["values"]["CHP"] == 0
    assert yerlesim["values"]["ANAP"] == 596
    assert yerlesim["values"]["kayitli"] == 1381


def test_seat_column_is_not_a_party(tmp_path: pathlib.Path) -> None:
    """ "Üyelik sayısı" is a seat count; counted as a party it inflates the vote total."""
    header = HEADER.replace(
        "<td>ANAP</td>", "<td>Üyelik sayısı</td><td></td><td>ANAP</td>"
    )
    path = tmp_path / "uyelik.html"
    path.write_text(f"<table>{header}</table>", encoding="windows-1254")
    rows = [
        parse_secim.cells_of(r)
        for r in __import__("re").findall(r"(?is)<tr[^>]*>(.*?)</tr>", header)
    ]
    _, degerler = parse_secim.header_columns(rows)
    assert "Üyelik sayısı" not in degerler.values()
    assert "ANAP" in degerler.values()
