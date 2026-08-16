"""Ortam degiskenleri ve proje yollari.

Sirlar .env dosyasindan okunur; .env depoya girmez (.gitignore).
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


#: Where the finished spreadsheets go — **outside** the working tree, on purpose.
#:
#: A git worktree is a copy of the code, not a place to keep deliverables: with three
#: branches checked out at once the same workbook exists three times, each one a little
#: different, and the newest is whichever directory you happened to open. So the outputs
#: leave the checkout entirely and land in one folder, grouped by subject, and every
#: worktree writes to that same folder.
#:
#: Found by walking back out of `.claude/worktrees/<name>` to the repository the worktree
#: belongs to — so this is the same path whether the code is running from the main
#: checkout or from a worktree of it. `VERIATLAS_OUTPUT` overrides it.
def _project_root() -> Path:
    parts = ROOT.parts
    if ".claude" in parts:
        return Path(*parts[: parts.index(".claude")])
    return ROOT


OUTPUT = Path(os.environ.get("VERIATLAS_OUTPUT") or _project_root() / "demografi")

RAW = ROOT / "raw"
PUBLIC = ROOT / "public"
DOCS = ROOT / "docs"
#: Registries and the indicator dictionary — files that are decisions, not observations,
#: so they ship inside the package rather than sitting in `raw/`.
DATA = Path(__file__).resolve().parent / "data"
WAREHOUSE = ROOT / "warehouse.duckdb"


class Settings(BaseSettings):
    """Proje ayarlari. Degerler .env dosyasindan gelir."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    evds_api_key: str = ""

    @property
    def evds_ready(self) -> bool:
        return bool(self.evds_api_key) and self.evds_api_key != "BURAYA_YAPISTIR"


settings = Settings()


def ensure_dirs() -> None:
    for d in (RAW, PUBLIC, OUTPUT):
        d.mkdir(parents=True, exist_ok=True)
