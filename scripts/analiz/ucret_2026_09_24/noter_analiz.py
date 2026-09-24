import sys

import duckdb
import numpy as np
import polars as pl

S = sys.argv[1]
AREAS = r"C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/"
c = duckdb.connect(r"C:/veri/warehouse.duckdb", read_only=True)
c.execute("create temp view nt as select * from read_parquet('" + S + "/notaries.parquet')")


def q(sql):
    return c.sql(sql).pl()


def latest(ind, level, where="true", agg="sum(value)"):
    return f"""(select area_id, {agg} v from fact where indicator_id='{ind}' and area_level='{level}'
      and period_start=(select max(period_start) from fact where indicator_id='{ind}' and area_level='{level}')
      and {where} group by 1)"""


print(q("select distinct regexp_extract(dims,'education_level=([a-z_0-9]+)',1) l from fact where indicator_id='education_level_district'"))

# ---------------- province ----------------
prov = q(f"""
with n as (select area_id,
   sum(value) noter,
   sum(value) filter (where dims='notary_class=first') n1,
   sum(value) filter (where dims='notary_class=second') n2,
   sum(value) filter (where dims='notary_class=third') n3
 from nt where area_level='province' group by 1)
select a.area_id, a.name_tr il, coalesce(n.noter,0) noter, coalesce(n1,0) n1, coalesce(n2,0) n2, coalesce(n3,0) n3,
  p.v nufus,
  g.v gsyh_kb, gt.v gsyh,
  vt.v arac_devir, hs.v konut_satis, co.v sirket_kurulus, bd.v mevduat, bl.v kredi,
  bb.v banka_sube, ph.v eczane, ea.v ort_gunluk_kazanc,
  ter.v / edu.v * 100 yuksekogretim_pct,
  de.v yogunluk, ma.v medyan_yas, mn.v net_goc, dv.v bosanma, mr.v evlilik, ex.v ihracat, cs.v zincir_magaza,
  ps.v tasinmaz_satis_ay
from read_csv('{AREAS}areas_tr.csv') a
left join n using(area_id)
left join {latest('population', 'province')} p using(area_id)
left join {latest('province_gdp_per_capita', 'province', "dims='gdp_currency=try;gdp_price=current'")} g using(area_id)
left join {latest('province_gdp_current', 'province', "dims='gdp_sector=gdp'")} gt using(area_id)
left join {latest('vehicles_transferred', 'province')} vt using(area_id)
left join {latest('housing_sales', 'province')} hs using(area_id)
left join {latest('tobb_companies', 'province', "dims like 'company_event=established%'")} co using(area_id)
left join {latest('bank_deposits', 'province')} bd using(area_id)
left join {latest('bank_loans', 'province')} bl using(area_id)
left join {latest('bank_branch_locations', 'province')} bb using(area_id)
left join {latest('pharmacies', 'province')} ph using(area_id)
left join {latest('sgk_average_daily_earnings', 'province', "dims='earnings_segment=total'")} ea using(area_id)
left join {latest('education_attainment', 'province', "dims similar to '.*(tertiary|postgraduate).*'")} ter using(area_id)
left join {latest('education_attainment', 'province', "dims not like '%unknown%'")} edu using(area_id)
left join {latest('population_density', 'province')} de using(area_id)
left join {latest('median_age', 'province', "dims='sex=total'")} ma using(area_id)
left join {latest('migration_net', 'province')} mn using(area_id)
left join {latest('divorces', 'province')} dv using(area_id)
left join {latest('marriages', 'province')} mr using(area_id)
left join {latest('tim_exports', 'province')} ex using(area_id)
left join {latest('chain_stores', 'province')} cs using(area_id)
left join {latest('property_sales_monthly', 'province', "dims='property_type=dwelling;sale_type=total'")} ps using(area_id)
where a.area_level='province' order by noter desc
""")
prov.write_parquet(f"{S}/prov.parquet")
print(prov.select(pl.len(), pl.col("noter").sum(), pl.col("nufus").sum()))
print(prov.null_count())
