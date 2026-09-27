import json, numpy as np, polars as pl, rasterio, shapely
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from pyproj import Transformer
from pathlib import Path
S=Path(__file__).parent; ROOT=Path("C:/veri")
T=Transformer.from_crs(4326,"ESRI:54009",always_xy=True)
feats=[]
for f in sorted((ROOT/"public/geo/neighbourhoods").glob("TR-16-*.geojson")):
    for x in json.loads(f.read_text(encoding="utf-8"))["features"]:
        g=shapely.from_geojson(json.dumps(x["geometry"]))
        feats.append((x["properties"]["area_id"], shapely.transform(g, lambda a: np.column_stack(T.transform(a[:,0],a[:,1])))))
allg=shapely.union_all([g for _,g in feats]); b=allg.bounds
out={}
for key,fn in (("v","GHS_BUILT_V_E2020_GLOBE_R2023A_54009_100_V1_0_R5_C21.tif"),("nres","GHS_BUILT_V_NRES_E2020_GLOBE_R2023A_54009_100_V1_0_R5_C21.tif")):
    with rasterio.open(f"C:/veri-ham/ghsl/{fn}") as src:
        w=from_bounds(*b,src.transform).round_offsets().round_lengths()
        arr=src.read(1,window=w).astype("float64"); tr=src.window_transform(w)
        nod=src.nodata
    if nod is not None: arr[arr==nod]=0
    out[key]=arr
lab=rasterize([(g,i+1) for i,(_,g) in enumerate(feats)], out_shape=out["v"].shape, transform=tr, fill=0, dtype="int32")
n=len(feats)+1
V=np.bincount(lab.ravel(),weights=out["v"].ravel(),minlength=n); N=np.bincount(lab.ravel(),weights=out["nres"].ravel(),minlength=n)
cells=np.bincount(lab.ravel(),minlength=n)
rows=[dict(area_id=a,vol=V[i+1],vol_nres=N[i+1],cells=int(cells[i+1])) for i,(a,_) in enumerate(feats)]
pl.DataFrame(rows).write_csv(S/"ghsl_16_mahalle.csv"); print("yazildi", len(rows), "toplam hacim m3", round(V.sum()/1e6,1),"mn")
