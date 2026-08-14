"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_district_population import TuikDistrictPopulation
from .tuik_median_age import TuikMedianAge
from .tuik_population import TuikPopulationAgeSex
from .tuik_tfr import TuikTfr

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {
    "tuik_tfr": TuikTfr,
    "tuik_population": TuikPopulationAgeSex,
    "tuik_district_population": TuikDistrictPopulation,
    "tuik_median_age": TuikMedianAge,
}

__all__ = [
    "ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikDistrictPopulation",
    "TuikMedianAge",
    "TuikPopulationAgeSex",
    "TuikTfr",
    "history",
    "ingest",
]
