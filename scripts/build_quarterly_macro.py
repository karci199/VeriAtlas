"""Build the quarterly FX and CPI reference series the ARPU dataset deflates with.

Sources, all open and key-free:
  * ECB daily euro reference rates (eurofxref-hist.csv) -> EUR/TRY directly and
    USD/TRY as EUR/TRY divided by EUR/USD. Quarterly figures are the mean of the
    daily rates in the quarter, which is what BTK itself uses when it converts
    ARPU to euro.
  * Turkish consumer prices: Eurostat HICP (prc_hicp_midx, geo=TR, CP00). TUIK's
    own TUFE is not available through an open API, and the OECD series that FRED
    carried stops in early 2025. Eurostat runs to 2025-12, so the newest quarter
    has no Turkish deflator - that gap is left empty rather than extrapolated.
  * US consumer prices: FRED CPIAUCNS. Euro-area consumer prices: FRED
    CP0000EZ19M086NEST (Eurostat HICP for the euro area).

Run with the three downloads already in a directory passed as argv[1].
"""

import csv
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "raw" / "ref" / "makro_ceyreklik.csv"


def quarter(year, month):
    return f"{year}-{(month - 1) // 3 + 1}"


def fx_quarters(path):
    """Mean daily EUR/TRY and USD/TRY per quarter, from the ECB history file."""
    eur_try, usd_try = {}, {}
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        date = r["Date"]
        try_rate, usd_rate = r.get("TRY", "").strip(), r.get("USD", "").strip()
        if not try_rate or not usd_rate or try_rate == "N/A" or usd_rate == "N/A":
            continue
        y, m, _ = (int(v) for v in date.split("-"))
        q = quarter(y, m)
        eur_try.setdefault(q, []).append(float(try_rate))
        usd_try.setdefault(q, []).append(float(try_rate) / float(usd_rate))
    return ({q: statistics.fmean(v) for q, v in eur_try.items()},
            {q: statistics.fmean(v) for q, v in usd_try.items()})


def fred_quarters(path):
    """Mean monthly index per quarter from a FRED csv."""
    out = {}
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        for date, value in reader:
            if value in ("", "."):
                continue
            y, m, _ = (int(v) for v in date.split("-"))
            out.setdefault(quarter(y, m), []).append(float(value))
    return {q: statistics.fmean(v) for q, v in out.items()}


def eurostat_quarters(path):
    """Mean monthly index per quarter from a Eurostat JSON-stat response."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    index = data["dimension"]["time"]["category"]["index"]
    values = data["value"]
    out = {}
    for period, pos in index.items():
        v = values.get(str(pos))
        if v is None:
            continue
        y, m = (int(x) for x in period.split("-"))
        out.setdefault(quarter(y, m), []).append(float(v))
    return {q: statistics.fmean(v) for q, v in out.items()}


def main(src):
    src = pathlib.Path(src)
    eur_try, usd_try = fx_quarters(src / "eurofxref-hist.csv")
    tr_cpi = eurostat_quarters(src / "tr_hicp.json")
    us_cpi = fred_quarters(src / "CPIAUCNS.csv")
    ea_cpi = fred_quarters(src / "CP0000EZ19M086NEST.csv")

    periods = sorted(
        (q for q in eur_try if int(q.split("-")[0]) >= 2011),
        key=lambda q: (int(q.split("-")[0]), int(q.split("-")[1])),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("donem", "eur_try", "usd_try", "tufe_tr", "tufe_abd", "tufe_euro"))
        for q in periods:
            w.writerow((
                q,
                round(eur_try[q], 4),
                round(usd_try[q], 4),
                round(tr_cpi[q], 3) if q in tr_cpi else "",
                round(us_cpi[q], 3) if q in us_cpi else "",
                round(ea_cpi[q], 3) if q in ea_cpi else "",
            ))
    print(f"{OUT} yazildi ({len(periods)} ceyrek)")


if __name__ == "__main__":
    main(sys.argv[1])
