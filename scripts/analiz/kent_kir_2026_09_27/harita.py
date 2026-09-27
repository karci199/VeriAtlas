import gzip, json, math, sys, shapely, numpy as np, polars as pl
from pathlib import Path
DID, OUT = sys.argv[1], sys.argv[2]
ROOT=Path("C:/veri"); S=Path(OUT).parent
geo=json.loads((ROOT/f"public/geo/districts/TR-{DID[3:5]}.geojson").read_text(encoding="utf-8"))
dg=[shapely.from_geojson(json.dumps(f["geometry"])) for f in geo["features"] if f["properties"]["area_id"]==DID][0]
lat0=shapely.centroid(dg).y; KX=111320*math.cos(math.radians(lat0)); KY=110574
proj=lambda g: shapely.transform(g, lambda a: a*np.array([KX,KY]))
dgp=proj(dg); minx,miny,maxx,maxy=dg.bounds
polys=[]
for f in sorted(Path("C:/veri-ham/msbuildings").glob("*.csv.gz")):
    with gzip.open(f,"rt") as fh:
        for line in fh:
            g=json.loads(line)["geometry"]["coordinates"][0]; x,y=g[0]
            if minx<=x<=maxx and miny<=y<=maxy: polys.append([(a*KX,b*KY) for a,b in g])
B=shapely.polygons([shapely.linearrings(p) for p in polys]); cent=shapely.centroid(B)
idx=np.where(shapely.contains(dgp,cent))[0]; small=idx[shapely.area(B[idx])<5000]
parts=shapely.get_parts(shapely.intersection(shapely.buffer(shapely.union_all(shapely.buffer(B[small],50)),-50),dgp)); parts=parts[shapely.area(parts)>0]
mah=pl.read_csv(S/f"kent_{DID[3:5]}_mahalle.csv").filter(pl.col("area_id").str.starts_with(DID))
URB={r["area_id"]:r for r in mah.iter_rows(named=True)}
ng=json.loads((ROOT/f"public/geo/neighbourhoods/{DID}.geojson").read_text(encoding="utf-8"))
NG=[(f["properties"]["area_id"],f["properties"]["name_tr"],proj(shapely.from_geojson(json.dumps(f["geometry"])))) for f in ng["features"]]
# town = clusters that contain buildings of urban nbhds (reconstruct: cluster intersecting urban nbhd building majority)
urban_ids=[a for a,r in URB.items() if r["urban"]]
ug=shapely.union_all([g for a,n,g in NG if a in urban_ids]) if urban_ids else None
town=[p for p in parts if ug is not None and shapely.area(shapely.intersection(p,ug))>0.5*shapely.area(p)]
townu=shapely.union_all(town) if town else None
# view: bbox of town + 2.5 km
vx0,vy0,vx1,vy1=shapely.buffer(townu,2500).bounds
W=1100; sc=W/(vx1-vx0); H=int((vy1-vy0)*sc)
def path(g):
    out=[]
    for p in shapely.get_parts(g):
        if p.geom_type!="Polygon": continue
        for ring in [p.exterior,*p.interiors]:
            c=np.asarray(ring.coords); out.append("M"+" L".join(f"{(x-vx0)*sc:.1f},{(vy1-y)*sc:.1f}" for x,y in c)+"Z")
    return " ".join(out)
view=shapely.box(vx0,vy0,vx1,vy1)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H+70}" viewBox="0 0 {W} {H+70}" font-family="Segoe UI,Arial" style="background:#f7f5ef">']
for a,n,g in NG:
    if not shapely.intersects(g,view): continue
    r=URB.get(a,{}); u=r.get("urban")
    fill="#f4c7b8" if u else "#dfe9d2"
    svg.append(f'<path d="{path(shapely.intersection(g,view))}" fill="{fill}" stroke="#7a7a7a" stroke-width="1.2" fill-rule="evenodd"/>')
vis=small[shapely.intersects(B[small],view)]
svg.append(f'<path d="{" ".join(path(B[i]) for i in vis)}" fill="#333"/>')
for p in parts:
    if shapely.intersects(p,view) and (townu is None or not shapely.intersects(p,townu)):
        svg.append(f'<path d="{path(shapely.intersection(p,view))}" fill="none" stroke="#2f6fb0" stroke-width="1.3" stroke-dasharray="4 3"/>')
svg.append(f'<path d="{path(townu)}" fill="none" stroke="#c0171b" stroke-width="3"/>')
for a,n,g in NG:
    if not shapely.intersects(g,view): continue
    r=URB.get(a,{}); pt=shapely.point_on_surface(shapely.intersection(g,view))
    lab=f'{n} · {int(r["pop2025"]) if r.get("pop2025") else "-"} kişi · {r.get("in_town",0)}/{r.get("buildings",0)} bina kümede'
    svg.append(f'<text x="{(pt.x-vx0)*sc:.0f}" y="{(vy1-pt.y)*sc:.0f}" font-size="13" text-anchor="middle" fill="#111" stroke="#fff" stroke-width="3" paint-order="stroke">{lab}</text>')
y=H+22
svg.append(f'<rect x="10" y="{y-12}" width="16" height="12" fill="#f4c7b8" stroke="#777"/><text x="32" y="{y}" font-size="13">Kent mahallesi (binalarının ≥%50\'si kasaba kümesinde)</text>')
svg.append(f'<rect x="420" y="{y-12}" width="16" height="12" fill="#dfe9d2" stroke="#777"/><text x="442" y="{y}" font-size="13">Kır mahallesi</text>')
svg.append(f'<line x1="570" y1="{y-5}" x2="600" y2="{y-5}" stroke="#c0171b" stroke-width="3"/><text x="606" y="{y}" font-size="13">Kasaba kümesi (bina +50 m birleşik, −50 m) {shapely.area(townu)/1e6:.2f} km²</text>')
svg.append(f'<line x1="10" y1="{y+22}" x2="40" y2="{y+22}" stroke="#2f6fb0" stroke-width="1.3" stroke-dasharray="4 3"/><text x="46" y="{y+27}" font-size="13">Diğer yerleşim kümeleri (köy/mahalle)</text>')
svg.append(f'<rect x="330" y="{y+15}" width="10" height="10" fill="#333"/><text x="346" y="{y+27}" font-size="13">Bina (Microsoft, Şubat 2026) · mahalle sınırı Endeksa · nüfus TÜİK 2025</text>')
svg.append("</svg>")
Path(OUT).write_text("\n".join(svg),encoding="utf-8"); print("yazildi", OUT, W, H)
