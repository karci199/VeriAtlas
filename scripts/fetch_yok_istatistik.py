"""Download every table of YÖK İstatistik's yearly releases, 2013-2014 to 2025-2026.

For each "YYYY-YYYY Öğretim Yılı" menu item, every table label that has an xls icon beside it
is exported. Files go to `raw/yok_istatistik/<year>/<server name>` (the server names them
`<year>_T<number>.xls`), with `index.tsv` recording year, label and file. Files already on
disk are skipped, so the run can be restarted; a new session is opened per year.
"""

import sys
import time

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

from yok_zk import YokStat

from veriatlas.config import RAW

OUT = RAW / "yok_istatistik"
YEARS = [f"{y}-{y + 1} Öğretim Yılı" for y in range(2013, 2026)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT / "index.tsv"
    done = (
        {
            tuple(line.split("\t")[:2])
            for line in index.read_text(encoding="utf-8").splitlines()
        }
        if index.exists()
        else set()
    )
    wanted = [y for y in YEARS if len(sys.argv) < 2 or y[:9] in sys.argv[1:]]
    for year in wanted:
        session = YokStat()
        answer = session.click(session.find(year))
        widgets = session.widgets(answer)
        labels = [
            text.strip()
            for i, (_, _, text, _) in enumerate(widgets)
            if text.strip()
            and any(src.endswith("xls.png") for _, _, _, src in widgets[i + 1 : i + 3])
        ]
        print(year, len(labels), "tablo", flush=True)
        for label in dict.fromkeys(labels):
            if (year, label) in done:
                continue
            try:
                name, data = session.excel(label, answer)
            except Exception as error:  # noqa: BLE001 — one broken table must not stop the year
                print("  HATA", label[:60], type(error).__name__, error, flush=True)
                continue
            folder = OUT / year[:9]
            folder.mkdir(exist_ok=True)
            (folder / name).write_bytes(data)
            with index.open("a", encoding="utf-8") as handle:
                handle.write(f"{year}\t{label}\t{year[:9]}/{name}\t{len(data)}\n")
            print("  ", name, len(data), label[:70], flush=True)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
