"""Build the single-file page: one .html you can double-click, no server.

The served version fetches its CSS and data; a file:// page cannot. So this inlines
both — stylesheets into a <style> block, data into an EMBEDDED map the page reads
instead of fetching.

The only thing left outside is the plotting library, which still comes from a CDN. That
means the file needs an internet connection the first time, but not a server.

Run:  uv run python scripts/build_page.py
"""

import json
import sys

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC, ROOT

WEB = ROOT / "web"
TARGET = ROOT / "VeriAtlas.html"

#: Paths the page asks for, exactly as they appear in the source.
DATA = {
    "../public/tfr.csv": PUBLIC / "tfr.csv",
    "../public/population.csv": PUBLIC / "population.csv",
    "../public/meta.json": PUBLIC / "meta.json",
}


def main() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")

    for name in ("theme.css", "app.css"):
        link = '<link rel="stylesheet" href="' + name + '">'
        style = "<style>\n" + (WEB / name).read_text(encoding="utf-8") + "</style>"
        if link not in html:
            raise SystemExit("beklenen stil bağlantısı bulunamadı: " + name)
        html = html.replace(link, style)

    missing = [str(path) for path in DATA.values() if not path.exists()]
    if missing:
        raise SystemExit(
            "önce veriyi üret (uv run python scripts/export_web.py): "
            + ", ".join(missing)
        )

    embedded = {key: path.read_text(encoding="utf-8") for key, path in DATA.items()}
    payload = (
        "<script>globalThis.EMBEDDED = "
        + json.dumps(embedded, ensure_ascii=False)
        + ';</script>\n<script type="module">'
    )
    html = html.replace('<script type="module">', payload, 1)

    TARGET.write_text(html, encoding="utf-8")
    print("yazildi:", TARGET, round(TARGET.stat().st_size / 1024), "KB")
    print(
        "cift tiklayarak acilir; sunucu gerekmez (grafik kutuphanesi icin internet lazim)"
    )


if __name__ == "__main__":
    main()
