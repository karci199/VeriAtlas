"""Download TESK's province tables of the tradesmen registry.

The confederation publishes two things on one page: a snapshot of how many tradesmen,
workplaces and chambers each province has, and one table per year of what the registry
gazette announced — registrations, amendments and the two kinds of removal.

The yearly files are not named after their year. `2017.pdf` is 2017 but 2016 is `5.pdf`
and 2015 is `21.pdf`, so the mapping below is copied from the link labels on the listing
page rather than guessed. 2005-2007 are scans without a text layer and are left out.
"""

from __future__ import annotations

import httpx

from veriatlas.adapters.tesk import RAW_DIR, SNAPSHOT, YEARS

LISTING = "https://www.tesk.org.tr/view/mevzuat/liste.php?Guid=902743d2-11e2-11ea-9eaf-000c29b32a85"
BASE = "https://www.tesk.org.tr/resimler/sicil/"

#: Year -> the file that holds it, as the listing page labels it.
SLUGS = {
    2008: "2008",
    2009: "2009",
    2010: "2010",
    2011: "2011",
    2012: "6",
    2013: "2013",
    2014: "3",
    2015: "21",
    2016: "5",
    2017: "2017",
    2018: "2018",
    2019: "2019",
    2020: "2020",
    2021: "2021",
    2022: "2022",
    2023: "2023",
    2024: "2024",
    2025: "2025",
}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # The certificate chain tesk.org.tr serves is incomplete; the payload is a PDF whose
    # bytes we checksum, so an unverified transport does not weaken the manifest.
    with httpx.Client(timeout=90, follow_redirects=True, verify=False) as client:
        for year, slug in SLUGS.items():
            if year not in YEARS:
                raise SystemExit(f"{year} adaptörde tanımlı değil")
            path = RAW_DIR / f"sicil-{year}.pdf"
            response = client.get(BASE + slug + ".pdf")
            response.raise_for_status()
            path.write_bytes(response.content)
            print(f"{year} {len(response.content) // 1024:5} KB  {path.name}")
        response = client.get(BASE + "4.pdf")
        response.raise_for_status()
        SNAPSHOT.write_bytes(response.content)
        print(f"anlık {len(response.content) // 1024:5} KB  {SNAPSHOT.name}")


if __name__ == "__main__":
    main()
