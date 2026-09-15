"""Scan the EPDK monthly LPG PDF reports (2011-2018) for the province x product table.

Writes raw/epdk/lpg_pdf_scan.json: per month, the rows read as text lines (name + four
sales/share pairs), the printed TOTAL row, and names that did not resolve. The adapter
(epdk_monthly.LpgSalesMonthly) keeps only months whose provinces add up to the total.
"""

import glob
import json
import re
import sys

import pypdfium2 as pdfium

sys.path.insert(0, "src")
from veriatlas.adapters.epdk_history import number_tr, province_or_none
from veriatlas.adapters.kgm import fold

NAMES = (
    ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
)
M = {fold(x): i + 1 for i, x in enumerate(NAMES)}
N = r"(-?[\d.]+(?:,\d+)?)"
ROW = re.compile(r"^(\D+?) " + " ".join([N + r" %?" + N + "%?"] * 4) + r"\s*$")
PRODUCT_TABLE = re.compile(
    r"illere göre ürün bazında|illere ve ürünlere göre|il ve ürün bazında|illere ve ürün türüne",
    re.IGNORECASE,
)
MONTH_NAME = re.compile(
    r"(20[01]\d)\s*(?:yılı|YILI)?\s*(\w+)\s*(?:ayı|AYI)|(\w+)\s+(20[01]\d)"
)
MONTH_NUM = re.compile(r"\b(\d{1,2})/(20[01]\d)\b")


def month_of(text):
    for m in MONTH_NAME.finditer(text):
        if m.group(1) and fold(m.group(2)) in M:
            return f"{m.group(1)}-{M[fold(m.group(2))]:02d}"
        if m.group(3) and fold(m.group(3)) in M:
            return f"{m.group(4)}-{M[fold(m.group(3))]:02d}"
    m = MONTH_NUM.search(text)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    return None


out = {}
files = sorted(glob.glob("C:/veri-ham/epdk/files/lpg_resmi/*.pdf"))
for n, f in enumerate(files, 1):
    try:
        doc = pdfium.PdfDocument(f)
    except Exception as e:
        print(n, f, "ACILMADI", e, flush=True)
        continue
    rows, total, bad, month, pages, carry = {}, None, [], None, 0, False
    for page in doc:
        tx = page.get_textpage().get_text_range().replace("\r", "").replace("Đ", "İ")
        cap = PRODUCT_TABLE.search(tx)
        if cap:
            line = tx[max(0, cap.start() - 80) : cap.end()]
            month = month or month_of(line)
            carry = True
        elif not (carry and len(rows) < 81):
            carry = False
            continue
        else:
            carry = False  # the table's second page: no caption, rows go on
        pages += 1
        for raw in tx.split("\n"):
            m = ROW.match(raw.strip())
            if not m:
                continue
            v = [number_tr(x) for x in m.groups()[1:]]
            name = m.group(1).strip()
            if fold(name) in ("toplam", "geneltoplam"):
                total = v
                continue
            pid = province_or_none(name)
            if pid is None:
                bad.append(name)
            elif pid in rows and rows[pid] != [v[0], v[2], v[4], v[6]]:
                bad.append("CIFT " + name)
            else:
                rows[pid] = [v[0], v[2], v[4], v[6]]
    if pages:
        out.setdefault(month or "?", []).append(
            {"file": f.split("\\")[-1], "rows": rows, "total": total, "bad": bad}
        )
    print(n, len(files), f.split("\\")[-1], month, pages, len(rows), flush=True)
json.dump(
    out,
    open("C:/veri-ham/epdk/lpg_pdf_scan.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
print("BITTI", len(out))
