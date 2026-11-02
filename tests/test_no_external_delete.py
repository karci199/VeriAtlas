"""Scripts never call external delete commands.

On 2026-11-02 a quoting mistake in another project's test turned a cleanup line into
`rmdir /s /q \\` and it started deleting from the root of C:. This tree survived only because
the deletion stopped first; `C:/veri-ham` has no other copy.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("scripts", "src", "tests")
SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh"}
FORBIDDEN = re.compile(
    r"""(?ix)
    (^|[\s"'(&;|])
    (rmdir | rd\s+/s | del\s+/ | erase\s+/ | rm\s+-rf | format\s+[a-z]: | diskpart | clear-disk)
    \b
    """
)


def _scripts() -> list[Path]:
    found = []
    for folder in FOLDERS:
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in SUFFIXES and path.name != Path(__file__).name:
                found.append(path)
    return found


def test_scan_sees_the_scripts() -> None:
    assert len(_scripts()) >= 100


def test_pattern_catches_the_line_that_did_it() -> None:
    assert FORBIDDEN.search('& cmd /c "rmdir /s /q \\"x\\""')
    assert not FORBIDDEN.search("path.unlink(missing_ok=True)")


def test_no_script_calls_an_external_delete() -> None:
    hits = []
    for path in _scripts():
        for number, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
            if not line.lstrip().startswith("#") and FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}")
    assert not hits, hits
