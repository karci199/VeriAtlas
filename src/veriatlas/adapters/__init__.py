"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_district_population import TuikDistrictPopulation
from .tuik_marital import TuikMarital
from .tuik_median_age import TuikMedianAge
from .tuik_neighbourhoods import TuikNeighbourhoodPopulation
from .tuik_population import TuikPopulationAgeSex
from .tuik_simple import NARROW_ADAPTERS
from .tuik_tfr import TuikTfr
from .tuik_vital import VITAL_ADAPTERS

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {
    "tuik_tfr": TuikTfr,
    "tuik_population": TuikPopulationAgeSex,
    "tuik_district_population": TuikDistrictPopulation,
    "tuik_median_age": TuikMedianAge,
    "tuik_neighbourhoods": TuikNeighbourhoodPopulation,
    "tuik_marital": TuikMarital,
    # One class per narrow measure, generated from a table: the contract is one
    # adapter per indicator, and eleven measures share the same parser.
    **NARROW_ADAPTERS,
    # Births and deaths: same download, transposed file, so a parser of their own.
    **VITAL_ADAPTERS,
}

__all__ = [
    "ADAPTERS",
    "NARROW_ADAPTERS",
    "VITAL_ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikDistrictPopulation",
    "TuikMarital",
    "TuikMedianAge",
    "TuikNeighbourhoodPopulation",
    "TuikPopulationAgeSex",
    "TuikTfr",
    "history",
    "ingest",
]
