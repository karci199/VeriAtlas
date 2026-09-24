import duckdb
import polars as pl

AREAS = r"C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/"
S = r"C:/veri-ham/analiz/2026-09-24/"
c = duckdb.connect(r"C:/veri/warehouse.duckdb", read_only=True)
QUAKE = ["Kahramanmaraş", "Hatay", "Adıyaman", "Malatya", "Gaziantep", "Osmaniye", "Adana", "Diyarbakır", "Şanlıurfa", "Kilis", "Elazığ"]

d = c.sql(f"""
select f.area_id, a.name_tr il, year(period_start) y,
 sum(value) filter (where dims like 'company_event=established%') kur,
 sum(value) filter (where dims like 'company_event=liquidation%') tasf,
 sum(value) filter (where dims like 'company_event=closed%') kap,
 sum(value) filter (where dims='company_event=established;company_type=company') kur_s,
 sum(value) filter (where dims='company_event=liquidation;company_type=company') tasf_s,
 sum(value) filter (where dims='company_event=closed;company_type=company') kap_s,
 sum(value) filter (where dims='company_event=established;company_type=sole_trader') kur_g,
 sum(value) filter (where dims='company_event=closed;company_type=sole_trader') kap_g
from fact f join read_csv('{AREAS}areas_tr.csv') a on a.area_id=f.area_id
where indicator_id='tobb_companies' and f.area_level='province' group by all
""").pl().fill_null(0)
pop = c.sql("""select area_id, sum(value) nufus from fact where indicator_id='population' and area_level='province'
 and period_start='2025-01-01' group by 1""").pl()
nuts = pl.read_csv(f"{AREAS}nuts_tr.csv", infer_schema_length=0)
print(nuts.head(3), nuts.columns)
d = d.join(pop, on="area_id").with_columns(deprem=pl.col("il").is_in(QUAKE))
d.write_parquet(f"{S}/sirket_il.parquet")
print(d.filter(pl.col("y") == 2025).select(pl.col("kur", "tasf", "kap").sum()))
print("il sayısı/yıl", d.group_by("y").len().sort("y").get_column("len").to_list())
