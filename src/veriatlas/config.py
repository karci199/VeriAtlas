"""Ortam degiskenleri ve proje yollari.

Sirlar .env dosyasindan okunur; .env depoya girmez (.gitignore).
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Raw data lives outside the repository: a worktree cleanup once followed a junction into
# the shared store and emptied it. VERIATLAS_HAM overrides the location.
RAW = Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
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
