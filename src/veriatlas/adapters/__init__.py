"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .endeksa import ENDEKSA_ADAPTERS
from .tuik_district_population import TuikDistrictPopulation
from .tuik_marital import TuikMarital
from .tuik_median_age import TuikMedianAge
from .tuik_neighbourhoods import TuikNeighbourhoodPopulation
from .tuik_population import TuikPopulationAgeSex
from .tuik_registry import TuikRegistryPopulation
from .tuik_simple import NARROW_ADAPTERS
from .tuik_tfr import TuikTfr
from .tuik_villages import TuikVillagePopulation
from .tuik_vital import VITAL_ADAPTERS
from .tuik_vital_district import DISTRICT_VITAL_ADAPTERS

#: Everything that can be ingested, by name. `scripts/load.py` runs these.
ADAPTERS = {
    "tuik_tfr": TuikTfr,
    "tuik_population": TuikPopulationAgeSex,
    "tuik_district_population": TuikDistrictPopulation,
    "tuik_median_age": TuikMedianAge,
    "tuik_neighbourhoods": TuikNeighbourhoodPopulation,
    "tuik_villages": TuikVillagePopulation,
    "tuik_marital": TuikMarital,
    "tuik_registry_population": TuikRegistryPopulation,
    # One class per narrow measure, generated from a table: the contract is one
    # adapter per indicator, and eleven measures share the same parser.
    **NARROW_ADAPTERS,
    # Births and deaths: same download, transposed file, so a parser of their own.
    **VITAL_ADAPTERS,
    # The same two events at district level are *different measures* in MEDAS, with
    # different codes in the header and shorter series. Their own parser for that reason.
    **DISTRICT_VITAL_ADAPTERS,
    # Endeksa: one class per indicator, generated from a table (docs/endeksa.md).
    **ENDEKSA_ADAPTERS,
}

__all__ = [
    "ADAPTERS",
    "DISTRICT_VITAL_ADAPTERS",
    "ENDEKSA_ADAPTERS",
    "NARROW_ADAPTERS",
    "VITAL_ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikDistrictPopulation",
    "TuikMarital",
    "TuikMedianAge",
    "TuikNeighbourhoodPopulation",
    "TuikPopulationAgeSex",
    "TuikRegistryPopulation",
    "TuikTfr",
    "TuikVillagePopulation",
    "history",
    "ingest",
]
