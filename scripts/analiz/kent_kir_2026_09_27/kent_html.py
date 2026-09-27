import gzip, json, math, sys, shapely, numpy as np, polars as pl
from pathlib import Path
ROOT=Path("C:/veri"); S=Path(sys.argv[1]); DIDS=sys.argv[2].split(",")
mah=pl.read_csv(S/"kent_16_mahalle.csv"); URB={r["area_id"]:r for r in mah.iter_rows(named=True)}
geo=json.loads((ROOT/"public/geo/districts/TR-16.geojson").read_text(encoding="utf-8"))
DG={f["properties"]["area_id"]:(f["properties"]["name_tr"],shapely.from_geojson(json.dumps(f["geometry"]))) for f in geo["features"]}
allb=shapely.union_all([DG[d][1] for d in DIDS]); minx,miny,maxx,maxy=allb.bounds
raw=[]
for f in sorted(Path("C:/veri-ham/msbuildings").glob("*.csv.gz")):
    with gzip.open(f,"rt") as fh:
        for line in fh:
            g=json.loads(line)["geometry"]["coordinates"][0]; x,y=g[0]
            if minx<=x<=maxx and miny<=y<=maxy: raw.append(g)
out={}
for did in DIDS:
    name,dg=DG[did]; lat0=shapely.centroid(dg).y; KX=111320*math.cos(math.radians(lat0)); KY=110574
    P=lambda g: shapely.transform(g, lambda a: a*np.array([KX,KY])); U=lambda g: shapely.transform(g, lambda a: a/np.array([KX,KY]))
    B=shapely.polygons([shapely.linearrings([(a*KX,b*KY) for a,b in g]) for g in raw]); cent=shapely.centroid(B)
    dgp=P(dg); idx=np.where(shapely.contains(dgp,cent))[0]; small=idx[shapely.area(B[idx])<5000]
    parts=shapely.get_parts(shapely.intersection(shapely.buffer(shapely.union_all(shapely.buffer(B[small],50)),-50),dgp)); parts=parts[shapely.area(parts)>0]
    ng=json.loads((ROOT/f"public/geo/neighbourhoods/{did}.geojson").read_text(encoding="utf-8"))
    ug=shapely.union_all([P(shapely.from_geojson(json.dumps(f["geometry"]))) for f in ng["features"] if URB.get(f["properties"]["area_id"],{}).get("urban")])
    town=[p for p in parts if shapely.area(shapely.intersection(p,ug))>0.5*shapely.area(p)]
    other=[p for p in parts if shapely.area(shapely.intersection(p,ug))<=0.5*shapely.area(p) and shapely.area(p)>20000]
    feats=[]
    for f in ng["features"]:
        r=URB.get(f["properties"]["area_id"],{})
        feats.append({"type":"Feature","geometry":f["geometry"],"properties":{"ad":f["properties"]["name_tr"],"kent":bool(r.get("urban")),"nufus":r.get("pop2025"),"bina":r.get("buildings"),"kumede":r.get("in_town"),"ilk":r.get("first_seen")}})
    tu=U(shapely.union_all(town))
    out[did]={"ad":name,"mahalle":{"type":"FeatureCollection","features":feats},
              "kent":json.loads(shapely.to_geojson(shapely.simplify(tu,0.00003))),
              "diger":json.loads(shapely.to_geojson(shapely.simplify(U(shapely.union_all(other)),0.00003))) if other else None,
              "alan":round(shapely.area(shapely.union_all(town))/1e6,2),
              "merkez":[tu.centroid.y,tu.centroid.x]}
    print(name, out[did]["alan"], flush=True)
html=(S/"kent_template.html").read_text(encoding="utf-8").replace("__DATA__",json.dumps(out,ensure_ascii=False))
(S/"kent_harita.html").write_text(html,encoding="utf-8"); print("yazildi", (S/"kent_harita.html").stat().st_size)
