"""Ortam degiskenleri ve proje yollari.

Sirlar .env dosyasindan okunur; .env depoya girmez (.gitignore).
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

#: Where raw downloads live. Two branches settled this two ways — one kept `raw/` inside the
#: checkout, the other moved the default to `C:/veri-ham` after a worktree cleanup emptied
#: the shared store (2026-09-07). Both environment names are honoured; without either, the
#: checkout's own `raw/` is used when it exists and the external store otherwise.
_RAW_ENV = os.environ.get("VERIATLAS_RAW") or os.environ.get("VERIATLAS_HAM")
RAW = Path(_RAW_ENV) if _RAW_ENV else (ROOT / "raw" if (ROOT / "raw").exists() else Path("C:/veri-ham"))
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
    for d in (RAW, PUBLIC):
        d.mkdir(parents=True, exist_ok=True)
