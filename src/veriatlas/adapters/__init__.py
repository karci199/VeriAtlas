"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_population import TuikPopulationAgeSex
from .tuik_tfr import TuikTfr

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {"tuik_tfr": TuikTfr, "tuik_population": TuikPopulationAgeSex}

__all__ = [
    "ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikPopulationAgeSex",
    "TuikTfr",
    "history",
    "ingest",
]
