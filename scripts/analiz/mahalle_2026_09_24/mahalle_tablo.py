"""Endeksa neighbourhood demography, all of Türkiye, flattened to one table.

Input: C:/veri-ham/endeksa/demography/TR-<plate>-<district>.json (research copy, not for
publication). Output: C:/veri-ham/analiz/mahalle/mahalle.parquet.

Kept apart: ADNKS counts (population, age, education, marital status; 2024) and
Endeksa's own model fields (SES, income, expense, prices, e-commerce). Money fields are of
unknown vintage and are used only as ranks and ratios. A record with HouseholdCount == 0
is an empty template (docs/endeksa.md): its model fields and age bands are dropped.
"""

import glob
import json
import re
from pathlib import Path

import polars as pl

OUT = Path("C:/veri-ham/analiz/mahalle")
OUT.mkdir(parents=True, exist_ok=True)
SALE_YEARS = range(2010, 2025)
rows = []
for path in sorted(glob.glob("C:/veri-ham/endeksa/demography/TR-*.json")):
    plate = int(re.search(r"TR-(\d+)-", path).group(1))
    for mid, rec in json.load(open(path, encoding="utf-8")).items():
        d = rec.get("demography") or {}
        if not d or not d.get("PopulationTotal"):
            continue
        ok = (d.get("HouseholdCount") or 0) > 0
        pop = d["PopulationTotal"]
        edu = sum(d.get(k) or 0 for k in ("EduNonLiterated", "EduLiteratedUntutored", "EduPrimarySchool", "EduMiddleSchool",
                                           "EduPrimaryEducation", "EduHighSchool", "EduLicenseDegree", "EduGraduate", "EduDoctorate"))
        uni = sum(d.get(k) or 0 for k in ("EduLicenseDegree", "EduGraduate", "EduDoctorate"))
        mar = sum(d.get(k) or 0 for k in ("MarriedNever", "Married", "Divorced", "Widow"))
        ses = sum(d.get(k) or 0 for k in ("SesGroupAPlus", "SesGroupA", "SesGroupB", "SesGroupC", "SesGroupD"))
        age = sum(d.get(k) or 0 for k in ("Age_Group_0_14", "Age_Group_15_29", "Age_Group_30_44", "Age_Group_45_59", "Age_Group_60"))
        r = {
            "plate": plate, "district": d.get("CountyName"), "province": d.get("CityName"), "neighbourhood": d.get("DistrictName"),
            "id": int(mid), "pop": pop, "households": d.get("HouseholdCount") if ok else None, "valid": ok,
            "uni_share": uni / edu * 100 if edu else None,
            "low_edu_share": ((d.get("EduNonLiterated") or 0) + (d.get("EduLiteratedUntutored") or 0)) / edu * 100 if edu else None,
            "divorced_share": (d.get("Divorced") or 0) / mar * 100 if mar else None,
            "never_married_share": (d.get("MarriedNever") or 0) / mar * 100 if mar else None,
            "ses_ab_share": ((d.get("SesGroupAPlus") or 0) + (d.get("SesGroupA") or 0) + (d.get("SesGroupB") or 0)) / ses * 100 if ses else None,
            "ses_d_share": (d.get("SesGroupD") or 0) / ses * 100 if ses else None,
            "turkey_index": d.get("TurkeyIndex"),
            "area_km2": d.get("Area"), "density": d.get("PopulationDensity"),
            "housing": d.get("HousingCount"), "commercial": d.get("CommercialCount"),
        }
        if ok:
            r.update({
                "income": d.get("HouseIncome"), "saving": d.get("SavingTotal"), "expense": d.get("ExpenseTotal"),
                "exp_food": d.get("ExpenseFood"), "exp_shelter": d.get("ExpenseShelter"), "exp_education": d.get("ExpenseEducation"),
                "exp_restaurant": d.get("ExpenseRestaurant"), "exp_transport": d.get("ExpenseTransportation"),
                "child_share": (d.get("Age_Group_0_14") or 0) / age * 100 if age else None,
                "elder_share": (d.get("Age_Group_60") or 0) / age * 100 if age else None,
                "hh_size": pop / d["HouseholdCount"],
                "owner_share": d.get("OwnerShare"), "renter_share": d.get("RentedShare"),
                "car_ratio": d.get("CarRatio"), "ecom_ratio": d.get("ECommerceRatio"), "ecom_density": d.get("ECommerceDensity"),
                "house_price": d.get("HouseUnitPriceForSale") or None, "house_rent": d.get("HouseUnitPriceForRent") or None,
                "atm": d.get("AtmCount"), "bank": d.get("BankBranchCount"), "pharmacy": d.get("PharmacyCount"),
                "mobile_user": d.get("MobileUser"), "betting": d.get("OnlineLegalBetting"),
            })
        for y in SALE_YEARS:
            r[f"sale_{y}"] = d.get(f"Total_BB_Sale_{y}")
            r[f"mort_{y}"] = d.get(f"Total_BBMortgaged_Sale_{y}")
        rows.append(r)
df = pl.DataFrame(rows, infer_schema_length=None)
df.write_parquet(OUT / "mahalle.parquet")
print(df.height, "mahalle", df["plate"].n_unique(), "il", df["district"].n_unique(), "ilçe adı", "nüfus", int(df["pop"].sum()))
print("geçerli (hane>0)", df.filter(pl.col("valid")).height, "nüfusu", int(df.filter(pl.col("valid"))["pop"].sum()))
print(df.select([pl.col(c).is_not_null().mean().alias(c) for c in ("income", "uni_share", "ses_ab_share", "elder_share", "owner_share", "house_price", "ecom_ratio")]))
