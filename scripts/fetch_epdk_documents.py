"""Download every document linked from EPDK's report and official statistics pages.

`raw/epdk/envanter.tsv` lists the links (market, page, document id, label); the labels are
mostly empty because the page shows icons, so the file's own name and type are what
identify it afterwards. Each document is saved once as `raw/epdk/files/<market>/<id>.<ext>`;
the extension comes from the server's filename. Documents already on disk are skipped, so
the run can be restarted.
"""

import csv
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

ROOT = RAW / "epdk"
BASE = "https://www.epdk.gov.tr/Detay/DownloadDocument?id="


def main() -> None:
    rows = list(
        csv.reader((ROOT / "envanter.tsv").open(encoding="utf-8"), delimiter="\t")
    )
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=180, follow_redirects=True
    )
    done: set[str] = set()
    index = ROOT / "files" / "index.tsv"
    index.parent.mkdir(parents=True, exist_ok=True)
    known = (
        {line.split("\t")[1] for line in index.read_text(encoding="utf-8").splitlines()}
        if index.exists()
        else set()
    )
    with index.open("a", encoding="utf-8") as out:
        for market, _page, doc_id, label in rows:
            if doc_id in done or doc_id in known:
                continue
            done.add(doc_id)
            try:
                response = client.get(BASE + doc_id)
            except httpx.HTTPError as error:
                print("HATA", doc_id, error)
                continue
            disposition = response.headers.get("content-disposition", "")
            name = re.search(r'filename="?([^";]+)', disposition)
            ext = Path(name.group(1)).suffix.lower() if name else ".bin"
            target = (
                ROOT / "files" / market / (re.sub(r"[^A-Za-z0-9]", "_", doc_id) + ext)
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            out.write(
                f"{market}\t{doc_id}\t{target.name}\t{len(response.content)}\t{label}\n"
            )
            out.flush()
            print(market, target.name, len(response.content), flush=True)
            time.sleep(0.5)
    print("BITTI")


if __name__ == "__main__":
    main()
