"""Civil-servant net salaries by title from memurlar.net's salary robot (/maas/{title}/).

The robot computes an itemised payslip (indicator salary, base salary, side payment,
special service compensation, extra payment, flat increase, deductions) from the
official coefficients for any month from 2014-01. One month per half-year is asked:
February and August, so the January/July transition items (e.g. "14 günlük maaş farkı")
stay out. robots.txt allows /maas/.

Profiles are fixed so every period is comparable: single, no children, not a union
member, no private pension, Ankara. "entry" is the lowest grade the robot holds for the
title (9/1 for most university posts, 8/1 for engineers, doctors and vets, 10/1 for the
technical and security services, 13/1 for high-school posts; 0 years); "senior" is 1/4
with 25 years. The robot only knows a title's own grade range: asking 9/1 of an engineer
answers "henüz programa girilmemiştir" for every period.

Raw pages go to C:/veri-ham/ucret/memur/memurlarnet/pages (gzip), parsed rows to
salaries.jsonl. Re-running only asks for what is missing (sweep until gain stops,
docs/cekiciler.md).

Run: .venv/Scripts/python.exe scripts/fetch_memurlarnet_salary.py
"""

import gzip
import html
import json
import re
import sys
import time
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/ucret/memur/memurlarnet")
PAGES = OUT / "pages"
ROWS = OUT / "salaries.jsonl"
# The robot answers 200 with "henüz programa girilmemiştir" for titles/periods it has no
# data for. That is a real gap, not a failure: it is recorded here and never retried.
NA = OUT / "not_available.jsonl"
NA_TEXT = "programa girilmemi"
BASE = "https://www.memurlar.net/maas/{slug}/"
DELAY = 1.2

# (key, slug, condition, degree, grade, years)
UNI = 9
HIGH = 13
PROFILES = [
    ("memur", "memur", "Önlisans veya Lisans Mezunu", UNI, 1, 0),
    ("memur_lise", "memur", "Lise veya Ortaokul Mezunu", HIGH, 1, 0),
    ("ogretmen", "ogretmen", "1 - Lisans Mezunu", UNI, 1, 0),
    (
        "polis",
        "polis-baspolis-kidemli-baspolis",
        "Önlisans veya Lisans Mezunu",
        UNI,
        1,
        0,
    ),
    ("hemsire", "hemsire", "Lisans Mezunu - Sağlık Bakanlığı", UNI, 1, 0),
    ("ebe", "ebe", None, UNI, 1, 0),
    ("tabip_pratisyen_8", "tabip", "Pratisyen", 8, 1, 0),
    ("muhendis_8", "muhendis", None, 8, 1, 0),
    ("avukat", "avukat", None, UNI, 1, 0),
    ("imam", "imam-hatip", "Önlisans veya Lisans Mezunu", UNI, 1, 0),
    ("arastirma_gorevlisi_8", "arastirma-gorevlisi", None, 8, 1, 0),
    ("veteriner_8", "veteriner-hekim", None, 8, 1, 0),
    ("eczaci", "eczaci", None, UNI, 1, 0),
    ("zabita_10", "zabita", None, 10, 1, 0),
    ("itfaiyeci_10", "itfaiyeci", None, 10, 1, 0),
    ("infaz_koruma_10", "infaz-ve-koruma-memuru", None, 10, 1, 0),
    ("hizmetli", "hizmetli", None, HIGH, 1, 0),
    ("sofor_10", "sofor", None, 10, 1, 0),
    ("teknisyen_10", "teknisyen", None, 10, 1, 0),
    # senior
    ("memur_kidemli", "memur", "Önlisans veya Lisans Mezunu", 1, 4, 25),
    ("ogretmen_kidemli", "ogretmen", "1 - Lisans Mezunu", 1, 4, 25),
    (
        "polis_kidemli",
        "polis-baspolis-kidemli-baspolis",
        "Önlisans veya Lisans Mezunu",
        1,
        4,
        25,
    ),
    ("hemsire_kidemli", "hemsire", "Lisans Mezunu - Sağlık Bakanlığı", 1, 4, 25),
    ("tabip_uzman_kidemli", "tabip", "Uzman", 1, 4, 25),
    ("muhendis_kidemli", "muhendis", None, 1, 4, 25),
    ("imam_kidemli", "imam-hatip", "Önlisans veya Lisans Mezunu", 1, 4, 25),
    ("sube_muduru_kidemli", "sube-muduru", "Yüksek Öğrenim Mezunu", 1, 4, 25),
    ("profesor_kidemli", "profesor", None, 1, 4, 25),
    (
        "hakim_kidemli",
        "hakim",
        "1. sınıfa ayrılan 1. derecedeki hakim ve savcı",
        1,
        4,
        25,
    ),
]
PERIODS = [f"{y}-{m:02d}-15" for y in range(2014, 2027) for m in (2, 8)]

FIXED = {
    "action": "salary",
    "advanced": "",
    "Salary_Day": "1",
    "Salary_Month": "1",
    "Salary_Year": "2014",
    "Salary_MaritalStatus": "1",
    "Salary_PartnerStatus": "notworking",
    "Salary_Toddlers": "0",
    "Salary_Children": "0",
    "Salary_Toddlers_Disabled": "0",
    "Salary_Children_Disabled": "0",
    "Salary_UnionMember": "0",
    "Salary_Location_City": "6",
    "Salary_Location_County": "128",
    "Salary_Bes": "false",
    "Salary_BesIndicator": "3",
    "Salary_LanguageA1": "0",
    "Salary_LanguageA2": "0",
    "Salary_LanguageB": "0",
    "Salary_LanguageC": "0",
    "Salary_DisabledLevel": "0",
    "Salary_Ilksan": "false",
    "Salary_Polsan": "false",
    "Salary_Bail": "false",
    "Salary_MaktuNufus": "63435",
}
NUM = re.compile(r"-?[\d,]+\.\d+|-?[\d,]+")


def num(s):
    m = NUM.search(s.replace("\xa0", " "))
    return float(m.group().replace(",", "")) if m else None


def parse(page):
    """Rows of the result table; an error page or a page without a net line is None."""
    m = re.search(r'<table class="Salary_Result">(.*?)</table>', page, flags=re.DOTALL)
    if not m:
        return None
    title = None
    items = []
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), flags=re.DOTALL):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.DOTALL)
        ]
        if len(cells) == 1 and title is None:
            title = cells[0]
        elif len(cells) == 3 and cells[2]:
            items.append([cells[0], cells[1], num(cells[2])])
    net = next((v for n, _, v in items if n.startswith("Net Maa")), None)
    if net is None:
        return None
    return {"title": title, "items": items, "net": net}


def key(p, period):
    return f"{p[0]}|{period}"


def done():
    keys = set()
    for path in (ROWS, NA):
        if path.exists():
            keys |= {json.loads(line)["key"] for line in path.open(encoding="utf-8")}
    return keys


def mark_na(k, reason):
    with NA.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": k, "reason": reason}, ensure_ascii=False) + "\n")


def sweep(client):
    have = done()
    # newest first: once the robot has no data for a period, it has none for older ones
    todo = [
        (p, d) for p in PROFILES for d in reversed(PERIODS) if key(p, d) not in have
    ]
    print(f"sweep: {len(todo)} eksik", flush=True)
    failed = []
    cutoff = {}
    for i, (p, d) in enumerate(todo):
        k, slug, cond, deg, grade, years = p
        if k in cutoff:
            mark_na(key(p, d), f"older than first missing period {cutoff[k]}")
            continue
        params = dict(
            FIXED,
            Salary_Degree=str(deg),
            Salary_Grade=str(grade),
            Salary_TotalYears=str(years),
            Salary_Date=d,
        )
        if cond:
            params["Salary_Condition"] = cond
        try:
            r = client.get(BASE.format(slug=slug), params=params)
            page = r.content.decode("cp1254", "replace")
            row = parse(page) if r.status_code == 200 else None
        except httpx.HTTPError as e:
            row, page = None, str(e)
        if row is None and NA_TEXT in page:
            mark_na(key(p, d), "robot has no data")
            cutoff[k] = d
        elif row is None:
            failed.append(key(p, d))
        else:
            name = f"{k}_{d}.html.gz"
            with gzip.open(PAGES / name, "wt", encoding="utf-8") as f:
                f.write(page)
            row.update(
                key=key(p, d),
                profile=k,
                slug=slug,
                condition=cond,
                degree=deg,
                grade=grade,
                years=years,
                date=d,
            )
            with ROWS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if i % 25 == 0:
            print(
                f"  {i}/{len(todo)} {k} {d} -> {row['net'] if row else 'HATA'}",
                flush=True,
            )
        time.sleep(DELAY)
    return failed


def main():
    PAGES.mkdir(parents=True, exist_ok=True)
    missing = None
    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (veriatlas; kamu maas serisi)"}, timeout=60
    ) as client:
        for _ in range(6):
            left = sweep(client)
            if not left:
                print("BITTI: eksik yok", flush=True)
                return
            if missing is not None and len(left) >= missing:
                print(f"BITTI: gecis kazanc getirmedi, {len(left)} eksik:", flush=True)
                for k in left:
                    print("  ", k, flush=True)
                return
            missing = len(left)
    print("BITTI: tur tavani", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
