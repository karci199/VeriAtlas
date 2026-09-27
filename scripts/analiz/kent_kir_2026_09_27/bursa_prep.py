import math, csv, io, httpx, duckdb, shapely, polars as pl
from pathlib import Path
b=pl.read_parquet("C:/veri-ham/osm/sinir_il_ilce.parquet")
geo=shapely.from_wkb(b["wkb"].to_list())
il=[g for g,l,n in zip(geo,b["admin_level"],b["name"]) if l=="4" and n=="Bursa"][0]
minx,miny,maxx,maxy=il.bounds; print("bbox",il.bounds)
def tile(lat,lon,z=9):
    x=(lon+180)/360; s=math.sin(math.radians(lat)); y=0.5-math.log((1+s)/(1-s))/(4*math.pi)
    n=2**z; tx=int(x*n); ty=int(y*n); q=""
    for i in range(z,0,-1):
        m=1<<(i-1); q+=str((1 if tx&m else 0)+(2 if ty&m else 0))
    return q
ks=set()
lat=miny
while lat<=maxy+0.05:
    lon=minx
    while lon<=maxx+0.05:
        if shapely.intersects(il, shapely.box(lon-0.3,lat-0.25,lon+0.3,lat+0.25)): ks.add(tile(min(lat,maxy),min(lon,maxx)))
        lon+=0.2
    lat+=0.15
links=list(csv.DictReader(io.StringIO(httpx.get("https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv",timeout=60).text)))
tr={r["QuadKey"]:r for r in links if r["Location"]=="Turkey"}
ks=sorted(k for k in ks if k in tr); print("karo", ks, [tr[k]["Size"] for k in ks], flush=True)
for k in ks:
    out=Path(f"C:/veri-ham/msbuildings/{k}.csv.gz")
    if not out.exists(): out.write_bytes(httpx.get(tr[k]["Url"],timeout=600).content); print("indi",k,out.stat().st_size,flush=True)
c=duckdb.connect(); c.sql("load spatial")
c.sql(f"""copy (select tags['name'] AS nm, tags['place'] AS place, lat, lon from st_readosm('C:/veri-ham/osm/turkey-latest.osm.pbf')
 where kind='node' and map_contains(tags,'place') and lat between {miny} and {maxy} and lon between {minx} and {maxx})
 to '{Path(__file__).parent.as_posix()}/bursa_places.parquet' (format parquet)""")
print("yer noktalari", c.sql(f"select place, count(*) from '{Path(__file__).parent.as_posix()}/bursa_places.parquet' group by 1").fetchall())
