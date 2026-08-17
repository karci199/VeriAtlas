"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .tuik_births_by_age import TuikBirthsByAge
from .tuik_births_marital import TuikBirthsMarital
from .tuik_consanguineous_marriage import TuikConsanguineousMarriage
from .tuik_district_population import TuikDistrictPopulation
from .tuik_literacy import TuikLiteracy
from .tuik_literacy_age import TuikLiteracyAge
from .tuik_literacy_district import TuikLiteracyDistrict
from .tuik_marital import TuikMarital
from .tuik_median_age import TuikMedianAge
from .tuik_neighbourhoods import TuikNeighbourhoodPopulation
from .tuik_population import TuikPopulationAgeSex
from .tuik_registry import TuikRegistryPopulation
from .tuik_simple import NARROW_ADAPTERS
from .tuik_tfr import TuikTfr
from .tuik_vehicles import TuikVehicles
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
    "tuik_vehicles": TuikVehicles,
    "tuik_literacy_district": TuikLiteracyDistrict,
    "tuik_literacy": TuikLiteracy,
    "tuik_literacy_age": TuikLiteracyAge,
    "tuik_births_by_age": TuikBirthsByAge,
    "tuik_births_marital": TuikBirthsMarital,
    "tuik_consanguineous_marriage": TuikConsanguineousMarriage,
    # One class per narrow measure, generated from a table: the contract is one
    # adapter per indicator, and eleven measures share the same parser.
    **NARROW_ADAPTERS,
    # Births and deaths: same download, transposed file, so a parser of their own.
    **VITAL_ADAPTERS,
    # The same two events at district level are *different measures* in MEDAS, with
    # different codes in the header and shorter series. Their own parser for that reason.
    **DISTRICT_VITAL_ADAPTERS,
}

__all__ = [
    "ADAPTERS",
    "DISTRICT_VITAL_ADAPTERS",
    "NARROW_ADAPTERS",
    "VITAL_ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikBirthsByAge",
    "TuikBirthsMarital",
    "TuikConsanguineousMarriage",
    "TuikDistrictPopulation",
    "TuikLiteracy",
    "TuikLiteracyAge",
    "TuikLiteracyDistrict",
    "TuikMarital",
    "TuikMedianAge",
    "TuikNeighbourhoodPopulation",
    "TuikPopulationAgeSex",
    "TuikRegistryPopulation",
    "TuikTfr",
    "TuikVehicles",
    "TuikVillagePopulation",
    "history",
    "ingest",
]
