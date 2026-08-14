"""Ortam degiskenleri ve proje yollari.

Sirlar .env dosyasindan okunur; .env depoya girmez (.gitignore).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

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
    for d in (RAW, PUBLIC):
        d.mkdir(parents=True, exist_ok=True)
