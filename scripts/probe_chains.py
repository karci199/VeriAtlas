r"""Which chain store finders can be read, and how — one pass over a long list.

Every chain is a separate little problem: some ship the whole list in the page, some have
a JSON endpoint, some answer only "the stores near this point", and some refuse robots to
us by name. Working that out by hand takes ten minutes each; this does the first pass in
one run and leaves a table saying where to spend the ten minutes.

For each domain it records:

* whether robots.txt can be read at all (a 403 is its own answer: the site is behind bot
  protection and we do not go further),
* whether our user agent is named there, and whether that rule is Allow or Disallow,
* which of the usual store-finder paths answer 200, and whether the answer already
  carries place names — a page with `İstanbul` and `Mah.` in it is holding the list, one
  without them is holding a map that will fetch it later.

Nothing is fetched beyond those few pages, and the robots decision is respected: a
`Disallow: /` for our agent stops the probe at the robots file.

Run:  uv run python scripts/probe_chains.py
Out:  C:\veri-ham\zincir_tarama.csv
"""

from __future__ import annotations

import csv
import re
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "zincir_tarama.csv"
AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
#: The names a Turkish site uses for its store finder, in rough order of how often they
#: turn out to be the right one.
PATHS = (
    "/magazalarimiz",
    "/magazalar",
    "/magaza-bul",
    "/subelerimiz",
    "/subeler",
    "/bayilerimiz",
    "/istasyonlar",
    "/store-locator",
    "/stores",
    "/magazalarimiz/",
    "/kurumsal/magazalarimiz",
)
CHAINS = {
    # gıda perakende
    "a101": "a101.com.tr", "bim": "bim.com.tr", "sok": "sokmarket.com.tr",
    "migros": "migros.com.tr", "carrefoursa": "carrefoursa.com", "file": "filemarket.com.tr",
    "tarim_kredi": "tarimkredi.com.tr", "hakmar": "hakmar.com", "onur": "onurmarket.com",
    "happy_center": "happycenter.com.tr", "bizim_toptan": "bizimtoptan.com.tr",
    "metro": "metro-tr.com", "ozdilek": "ozdilekteyim.com",
    # teknoloji
    "teknosa": "teknosa.com", "mediamarkt": "mediamarkt.com.tr", "vatan": "vatanbilgisayar.com",
    "itopya": "itopya.com", "incehesap": "incehesap.com",
    # yapı market
    "koctas": "koctas.com.tr", "bauhaus": "bauhaus.com.tr", "tekzen": "tekzen.com.tr",
    "ikea": "ikea.com.tr", "englishhome": "englishhome.com", "madamecoco": "madamecoco.com",
    "tekno_yapi": "yapimarket.com.tr",
    # giyim
    "lcwaikiki": "lcw.com", "koton": "koton.com", "defacto": "defacto.com.tr",
    "mavi": "mavi.com", "colins": "colins.com.tr", "kigili": "kigili.com",
    "penti": "penti.com", "flo": "flo.com.tr", "boyner": "boyner.com.tr",
    # yeme içme
    "komagene": "komagene.com.tr", "oses": "osescigkofte.com", "cigkoftem": "cigkoftem.com.tr",
    "tavuk_dunyasi": "tavukdunyasi.com", "pidebypide": "pidebypide.com",
    "kahve_dunyasi": "kahvedunyasi.com", "espressolab": "espressolab.com",
    "popeyes": "popeyes.com.tr", "usta_donerci": "ustadonerci.com",
    # akaryakıt
    "petrol_ofisi": "petrolofisi.com.tr", "opet": "opet.com.tr", "shell": "shell.com.tr",
    "aytemiz": "aytemiz.com.tr", "total": "totalenergies.com.tr", "lukoil": "lukoil.com.tr",
}
PLACE = re.compile(r"İstanbul|Ankara|Mah\.|Mahalle", re.IGNORECASE)
AGENT_NAMES = ("claudebot", "claude-user", "claude-web", "anthropic-ai")


def robots_verdict(client: httpx.Client, host: str) -> tuple[str, str]:
    """(durum, karar) — what robots.txt says about us."""
    try:
        response = client.get(f"https://www.{host}/robots.txt")
    except httpx.HTTPError as error:
        return "hata", type(error).__name__
    if response.status_code != 200:
        return str(response.status_code), "okunamadı"

    text = response.text.lower()
    # The agents are often listed as a block of User-agent lines followed by one rule.
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        if not any(name in block for name in AGENT_NAMES):
            continue
        if re.search(r"^\s*disallow:\s*/\s*$", block, re.MULTILINE):
            return "200", "bize yasak"
        if re.search(r"^\s*allow:\s*/\s*$", block, re.MULTILINE):
            return "200", "bize açık"
        return "200", "adımız geçiyor"
    return "200", "genel kural"


def main() -> None:
    rows = []
    headers = {"User-Agent": AGENT}
    with httpx.Client(headers=headers, timeout=25, follow_redirects=True, verify=False) as client:  # noqa: S501
        for name, host in CHAINS.items():
            status, verdict = robots_verdict(client, host)
            row = {"zincir": name, "alan": host, "robots": status, "karar": verdict,
                   "sayfa": "", "boyut": "", "yer_adi": ""}
            if verdict != "bize yasak" and status != "hata":
                for path in PATHS:
                    try:
                        page = client.get(f"https://www.{host}{path}")
                    except httpx.HTTPError:
                        continue
                    if page.status_code != 200 or len(page.text) < 2000:
                        continue
                    hits = len(PLACE.findall(page.text))
                    row.update(sayfa=path, boyut=len(page.text), yer_adi=hits)
                    # A page already naming places is holding the list; stop looking.
                    if hits > 20:
                        break
                    time.sleep(0.4)
            rows.append(row)
            print(f"{name:16} {status:5} {verdict:14} {row['sayfa'] or '-':22} yer adı: {row['yer_adi']}")
            time.sleep(0.6)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    açık = sum(1 for r in rows if r["yer_adi"] and int(r["yer_adi"]) > 20)
    print(f"\n{OUT}: {len(rows)} zincir, listesi sayfada duran {açık}")


if __name__ == "__main__":
    main()
