r"""File the Excel exports the user downloads by hand from istatistik.meb.gov.tr.

The portal's robots.txt disallows ClaudeBot, so nothing here fetches; the user downloads
each "Okul Türüne Göre" table with the page's own Excel button and drops it in a folder.
The browser names them "Milli Eğitim İstatistikleri - Okul Sayısı (3).xlsx", which says
nothing, but every file carries its own description in the first two rows:

    Milli Eğitim İstatistikleri - Okul Sayısı
    2024-2025 > Okul Öncesi > Anaokulu

This moves each file to `RAW/meb_portal/<measure>/<year>_<level>_<type>.xlsx`. Two files
that describe the same table are compared: identical ones are dropped, different ones stop
the run, because one of them is not what its title says.

Run:  uv run python scripts/organize_meb_portal.py "C:\Users\katan\OneDrive\Desktop\Şube"
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "meb_portal"
ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def slug(text: str) -> str:
    text = text.translate(ASCII).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def describe(path: Path) -> tuple[str, str]:
    """(measure folder, file stem) from the export's own title rows."""
    # read_only keeps the file open until close(); without it the move below fails.
    book = openpyxl.load_workbook(path, read_only=True)
    try:
        rows = book.active.iter_rows(max_row=2, values_only=True)
        title = str(next(rows)[0])
        trail = str(next(rows)[0])
    finally:
        book.close()
    measure = title.split(" - ", 1)[1]
    parts = [part.strip() for part in trail.split(">")]
    if re.fullmatch(r"\d{4}-\d{4}", parts[0]):
        return slug(measure), "_".join(slug(part) for part in parts)
    # The "Tüm Eğitim Kademeleri" pages put the year last in a sentence:
    # "Eğitim Kademelerine Göre Okul Türü 2024-2025".
    year = re.search(r"\d{4}-\d{4}", trail)
    if not year:
        raise ValueError(f"{path.name}: yıl okunamadı ({trail!r})")
    rest = slug(trail.replace(year.group(0), ""))
    return slug(measure), f"{year.group(0)}_{rest}"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = Path(sys.argv[1])
    moved = dropped = 0
    for path in sorted(source.glob("Milli Eğitim İstatistikleri*.xlsx")):
        folder, stem = describe(path)
        target = OUT / folder / f"{stem}.xlsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(target) != digest(path):
                raise SystemExit(f"aynı başlık, farklı içerik: {path.name} ve {target}")
            path.unlink()
            dropped += 1
            print(f"  aynısı var, silindi: {path.name}")
            continue
        shutil.move(path, target)
        moved += 1
        print(f"  {path.name} -> {target.relative_to(OUT)}")
    print(f"{moved} dosya taşındı, {dropped} çift silindi -> {OUT}")


if __name__ == "__main__":
    main()
