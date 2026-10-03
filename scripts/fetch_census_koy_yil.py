"""Run one year of the census village queue step "koy koy yas" in its own process.

The main queue (`fetch_census_districts.py --kuyruk`) walks the years one after the other;
this runs a single year beside it. Files already on disk are skipped, so the queue later
finds the finished year and passes over it. Variable names are written here, not on the
command line, because non-ASCII arguments arrive garbled through Windows process launchers.

Run:  python scripts/fetch_census_koy_yil.py 1990
"""

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")
import fetch_census_districts as census

VARIABLES = ["Beşerli Yaş Grubu", "0-14,15-64,65+"]

if __name__ == "__main__":
    census.fetch_villages(int(sys.argv[1]), VARIABLES)
