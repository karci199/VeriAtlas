"""Source adapters. One module per source; the contract lives in `base`."""

from .afad import AFAD_ADAPTERS
from .ayd_malls import AYD_ADAPTERS
from .base import Adapter, Manifest, history, ingest
from .bddk_finturk import FINTURK_ADAPTERS
from .bkm_sector import BKM_ADAPTERS
from .btk import BTK_ADAPTERS
from .btk_charts import BTK_CHART_ADAPTERS
from .btk_imei import BTK_IMEI_ADAPTERS
from .btk_posta import BTK_POSTA_ADAPTERS
from .btk_prose import BTK_PROSE_ADAPTERS
from .btk_province import BTK_PROVINCE_ADAPTERS
from .btk_summary import BTK_SUMMARY_ADAPTERS
from .btk_tables import BTK_TABLE_ADAPTERS
from .chain_stores import CHAIN_STORE_ADAPTERS
from .dhmi import DHMI_ADAPTERS
from .diyanet import DIYANET_ADAPTERS
from .epdk import EPDK_ADAPTERS
from .epdk_capacity import EPDK_CAPACITY_ADAPTERS
from .epdk_dealer_deliveries import EPDK_DEALER_ADAPTERS
from .epdk_fuel_stations import EPDK_FUEL_STATION_ADAPTERS
from .epdk_history import EPDK_HISTORY_ADAPTERS
from .epdk_monthly import EPDK_MONTHLY_ADAPTERS
from .epdk_sarj import EPDK_SARJ_ADAPTERS
from .etkb import ETKB_ADAPTERS
from .eurostat_regional import EUROSTAT_REGIONAL_ADAPTERS
from .evds_archive import EVDS_ARCHIVE_ADAPTERS
from .evds_housing import EVDS_HOUSING_ADAPTERS
from .evds_prices import EVDS_PRICE_ADAPTERS
from .evds_series import EVDS_SERIES_ADAPTERS
from .evds_tourism import EvdsVisitorsByNationality
from .gsb import GSB_ADAPTERS
from .iskur import ISKUR_ADAPTERS
from .kgm import KGM_ADAPTERS
from .ktb import KTB_ADAPTERS
from .meb_education import MEB_ADAPTERS
from .mgm import MGM_ADAPTERS
from .muhasebat import MUHASEBAT_ADAPTERS
from .networks import NETWORK_ADAPTERS
from .oecd_tl3 import OECD_TL3_ADAPTERS
from .ookla_speed import OOKLA_ADAPTERS
from .pharmacies import PHARMACY_ADAPTERS
from .ptt_postal import PTT_POSTAL_ADAPTERS
from .saglik_yearbook import SAGLIK_YEARBOOK_ADAPTERS
from .sege import SEGE_ADAPTERS
from .sgk_national import SGK_NATIONAL_ADAPTERS
from .sgk_provinces import SGK_ADAPTERS
from .tbb_provinces import TBB_ADAPTERS
from .telecom_operators import TELECOM_ADAPTERS
from .tesk import TESK_ADAPTERS
from .tim import TIM_ADAPTERS
from .tim_countries import TIM_COUNTRY_ADAPTERS
from .tim_sectors import TIM_SECTOR_ADAPTERS
from .tkgm import TKGM_ADAPTERS
from .tobb import TOBB_ADAPTERS
from .tuik_birth_order import TuikBirthOrder
from .tuik_births_by_age import TuikBirthsByAge
from .tuik_births_marital import TuikBirthsMarital
from .tuik_child_police import CHILD_POLICE_ADAPTERS
from .tuik_consanguineous_marriage import TuikConsanguineousMarriage
from .tuik_crops import CROP_ADAPTERS
from .tuik_death_cause import TuikDeathCause
from .tuik_district_population import TuikDistrictPopulation
from .tuik_education_district import EDUCATION_DISTRICT_ADAPTERS
from .tuik_household import TuikHouseholdSize, TuikHouseholdTenure
from .tuik_household_excel import TuikEducationAttainment
from .tuik_housing_monthly import MONTHLY_HOUSING_ADAPTERS
from .tuik_item_prices import TUIK_ITEM_PRICE_ADAPTERS
from .tuik_labour_province import LABOUR_PROVINCE_ADAPTERS
from .tuik_literacy import TuikLiteracy
from .tuik_literacy_age import TuikLiteracyAge
from .tuik_marital import TuikMarital
from .tuik_median_age import TuikMedianAge
from .tuik_migration_matrix import TuikMigrationMatrix
from .tuik_municipal import MUNICIPAL_ADAPTERS
from .tuik_names import TUIK_NAMES_ADAPTERS
from .tuik_neighbourhoods import TuikNeighbourhoodPopulation
from .tuik_origin_district import ORIGIN_ADAPTERS
from .tuik_population import TuikPopulationAgeSex
from .tuik_province_gdp import PROVINCE_GDP_ADAPTERS
from .tuik_registry import TuikRegistryPopulation
from .tuik_retail import RETAIL_ADAPTERS
from .tuik_simple import NARROW_ADAPTERS
from .tuik_tfr import TuikTfr
from .tuik_topics import TOPIC_ADAPTERS
from .tuik_vehicle_km import VEHICLE_KM_ADAPTERS
from .tuik_vehicles import VEHICLE_ADAPTERS
from .tuik_villages import TuikVillagePopulation
from .tuik_vital import VITAL_ADAPTERS
from .tuik_vital_district import DISTRICT_VITAL_ADAPTERS
from .uab_ports import UAB_ADAPTERS
from .vap import VAP_ADAPTERS
from .yks import YKS_ADAPTERS
from .yok_istatistik import YOK_ISTATISTIK_ADAPTERS
from .yok_national import YOK_NATIONAL_ADAPTERS
from .yokatlas import YOKATLAS_ADAPTERS
from .ysk_urbanization import YskUrbanization2015

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
    **OOKLA_ADAPTERS,
    **PROVINCE_GDP_ADAPTERS,
    **UAB_ADAPTERS,
    **AYD_ADAPTERS,
    # Rescued 2026-09-22 from branches that never reached main (docs/dal-temizligi.md).
    "tuik_literacy": TuikLiteracy,
    "tuik_literacy_age": TuikLiteracyAge,
    "tuik_births_by_age": TuikBirthsByAge,
    "tuik_births_marital": TuikBirthsMarital,
    "tuik_consanguineous_marriage": TuikConsanguineousMarriage,
    "tuik_education_attainment": TuikEducationAttainment,
    "ysk_urbanization_2015": YskUrbanization2015,
    **{"meb_" + key: cls for key, cls in MEB_ADAPTERS.items()},
    **BKM_ADAPTERS,
    **PHARMACY_ADAPTERS,
    **TELECOM_ADAPTERS,
    **RETAIL_ADAPTERS,
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
    # EPDK market report annexes: electricity, gas, fuel, LPG by province.
    **EPDK_ADAPTERS,
    # Earlier years from the EPDK Word reports; same keys, so these replace the above.
    **EPDK_HISTORY_ADAPTERS,
    **EPDK_CAPACITY_ADAPTERS,
    **EPDK_MONTHLY_ADAPTERS,
    **EPDK_SARJ_ADAPTERS,
    **EPDK_DEALER_ADAPTERS,
    **TOBB_ADAPTERS,
    **YOKATLAS_ADAPTERS,
    **YOK_ISTATISTIK_ADAPTERS,
    **YOK_NATIONAL_ADAPTERS,
    **YKS_ADAPTERS,
    **BTK_ADAPTERS,
    **BTK_PROVINCE_ADAPTERS,
    **BTK_SUMMARY_ADAPTERS,
    **BTK_IMEI_ADAPTERS,
    **BTK_CHART_ADAPTERS,
    **DHMI_ADAPTERS,
    **DIYANET_ADAPTERS,
    **TESK_ADAPTERS,
    **TKGM_ADAPTERS,
    **CHAIN_STORE_ADAPTERS,
    **NETWORK_ADAPTERS,
    **EPDK_FUEL_STATION_ADAPTERS,
    **PTT_POSTAL_ADAPTERS,
    **LABOUR_PROVINCE_ADAPTERS,
    **TUIK_NAMES_ADAPTERS,
    **TUIK_ITEM_PRICE_ADAPTERS,
    **TIM_ADAPTERS,
    **MUHASEBAT_ADAPTERS,
    **OECD_TL3_ADAPTERS,
    **VAP_ADAPTERS,
    **FINTURK_ADAPTERS,
    **TIM_SECTOR_ADAPTERS,
    **TIM_COUNTRY_ADAPTERS,
    **ISKUR_ADAPTERS,
    **KTB_ADAPTERS,
    **GSB_ADAPTERS,
    **AFAD_ADAPTERS,
    **EUROSTAT_REGIONAL_ADAPTERS,
    **SAGLIK_YEARBOOK_ADAPTERS,
    **ETKB_ADAPTERS,
    **MGM_ADAPTERS,
    **BTK_TABLE_ADAPTERS,
    **BTK_POSTA_ADAPTERS,
    **BTK_PROSE_ADAPTERS,
    # İlçe SEGE-2022 development score, rank and level.
    **SEGE_ADAPTERS,
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
