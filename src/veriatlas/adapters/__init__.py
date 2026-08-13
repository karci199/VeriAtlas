"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_district_population import TuikDistrictPopulation
from .tuik_population import TuikPopulationAgeSex
from .tuik_tfr import TuikTfr

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {
    "tuik_tfr": TuikTfr,
    "tuik_population": TuikPopulationAgeSex,
    "tuik_district_population": TuikDistrictPopulation,
}

__all__ = [
    "ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikDistrictPopulation",
    "TuikPopulationAgeSex",
    "TuikTfr",
    "history",
    "ingest",
]
