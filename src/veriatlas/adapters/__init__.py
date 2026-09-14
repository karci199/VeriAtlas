"""Source adapters. One module per source; the contract lives in `base`."""

from .base import Adapter, Manifest, history, ingest
from .evds_archive import EVDS_ARCHIVE_ADAPTERS
from .evds_housing import EVDS_HOUSING_ADAPTERS
from .evds_prices import EVDS_PRICE_ADAPTERS
from .evds_series import EVDS_SERIES_ADAPTERS
from .evds_tourism import EvdsVisitorsByNationality
from .kgm import KGM_ADAPTERS
from .sgk_national import SGK_NATIONAL_ADAPTERS
from .sgk_provinces import SGK_ADAPTERS
from .tbb_provinces import TBB_ADAPTERS
from .tuik_birth_order import TuikBirthOrder
from .tuik_child_police import CHILD_POLICE_ADAPTERS
from .tuik_crops import CROP_ADAPTERS
from .tuik_death_cause import TuikDeathCause
from .tuik_district_population import TuikDistrictPopulation
from .tuik_education_district import EDUCATION_DISTRICT_ADAPTERS
from .tuik_household import TuikHouseholdSize, TuikHouseholdTenure
from .tuik_housing_monthly import MONTHLY_HOUSING_ADAPTERS
from .tuik_marital import TuikMarital
from .tuik_median_age import TuikMedianAge
from .tuik_migration_matrix import TuikMigrationMatrix
from .tuik_municipal import MUNICIPAL_ADAPTERS
from .tuik_neighbourhoods import TuikNeighbourhoodPopulation
from .tuik_origin_district import ORIGIN_ADAPTERS
from .tuik_population import TuikPopulationAgeSex
from .tuik_registry import TuikRegistryPopulation
from .tuik_simple import NARROW_ADAPTERS
from .tuik_tfr import TuikTfr
from .tuik_topics import TOPIC_ADAPTERS
from .tuik_vehicle_km import VEHICLE_KM_ADAPTERS
from .tuik_vehicles import VEHICLE_ADAPTERS
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
    "tuik_birth_order": TuikBirthOrder,
    "tuik_death_cause": TuikDeathCause,
    "tuik_household_by_size": TuikHouseholdSize,
    "tuik_household_by_tenure": TuikHouseholdTenure,
    "tuik_marital": TuikMarital,
    "tuik_migration_matrix": TuikMigrationMatrix,
    "tuik_registry_population": TuikRegistryPopulation,
    # One class per narrow measure, generated from a table: the contract is one
    # adapter per indicator, and eleven measures share the same parser.
    **NARROW_ADAPTERS,
    # Births and deaths: same download, transposed file, so a parser of their own.
    **VITAL_ADAPTERS,
    # The same two events at district level are *different measures* in MEDAS, with
    # different codes in the header and shorter series. Their own parser for that reason.
    **DISTRICT_VITAL_ADAPTERS,
    # District × province squares: hemşehrilik, diaspora, birthplace.
    **ORIGIN_ADAPTERS,
    # Municipal water, wastewater, waste and electricity.
    **MUNICIPAL_ADAPTERS,
    # Motor vehicles: registrations, stock by fuel, brand, engine size, mean age.
    **VEHICLE_ADAPTERS,
    # Health and road accidents.
    **TOPIC_ADAPTERS,
    # Housing sales published monthly only, summed to years.
    **MONTHLY_HOUSING_ADAPTERS,
    # Crop production: area, production, yield by crop.
    **CROP_ADAPTERS,
    # Vehicle-kilometres, TÜİK Veri Portalı.
    **VEHICLE_KM_ADAPTERS,
    # District education level and literacy.
    **EDUCATION_DISTRICT_ADAPTERS,
    # Children referred to police units (Türkiye).
    **CHILD_POLICE_ADAPTERS,
    # CBRT housing and commercial property prices and rents, at published frequency.
    **EVDS_HOUSING_ADAPTERS,
    # Banks Association: deposits, loans, employees, ATM/POS by province.
    **TBB_ADAPTERS,
    # Consumer prices and the dollar rate (EVDS), the deflators.
    **EVDS_PRICE_ADAPTERS,
    # Price index trees, monthly property sales by province, monthly permits.
    **EVDS_SERIES_ADAPTERS,
    # EVDS archive groups, one indicator per retired table.
    **EVDS_ARCHIVE_ADAPTERS,
    "evds_foreign_visitors_by_nationality": EvdsVisitorsByNationality,
    # SGK yearbooks: insured, workplaces, pensions, work accidents by province.
    **SGK_ADAPTERS,
    # KGM: distances, road lengths, motorways, bridges.
    **KGM_ADAPTERS,
    # SGK yearbooks, Türkiye-wide work accident and occupational disease tables.
    **SGK_NATIONAL_ADAPTERS,
}

__all__ = [
    "ADAPTERS",
    "DISTRICT_VITAL_ADAPTERS",
    "MUNICIPAL_ADAPTERS",
    "NARROW_ADAPTERS",
    "ORIGIN_ADAPTERS",
    "TOPIC_ADAPTERS",
    "VEHICLE_ADAPTERS",
    "VITAL_ADAPTERS",
    "Adapter",
    "Manifest",
    "TuikBirthOrder",
    "TuikDeathCause",
    "TuikDistrictPopulation",
    "TuikHouseholdSize",
    "TuikHouseholdTenure",
    "TuikMarital",
    "TuikMedianAge",
    "TuikMigrationMatrix",
    "TuikNeighbourhoodPopulation",
    "TuikPopulationAgeSex",
    "TuikRegistryPopulation",
    "TuikTfr",
    "TuikVillagePopulation",
    "history",
    "ingest",
]
