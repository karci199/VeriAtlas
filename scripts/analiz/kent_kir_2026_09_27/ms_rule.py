import gzip, json, math, shapely, numpy as np, sys
towns={"iznik":(40.429,29.720,"122101012"),"yenisehir":(40.264,29.651,"122101012"),"kalecik":(40.0977,33.4093,"122101113")}
for name,(lat,lon,k) in towns.items():
    KX=111320*math.cos(math.radians(lat)); KY=110574
    polys=[]
    with gzip.open(f"C:/veri-ham/msbuildings/{k}.csv.gz","rt") as f:
        for line in f:
            g=json.loads(line)["geometry"]["coordinates"][0]
            if abs(g[0][0]-lon)<0.08 and abs(g[0][1]-lat)<0.06: polys.append([(x*KX,y*KY) for x,y in g])
    geoms=shapely.polygons([shapely.linearrings(p) for p in polys]); a=shapely.area(geoms)
    c=shapely.Point(lon*KX,lat*KY)
    for rule in ("tek kume","zincir","zincir+sanayisiz"):
        use=geoms if rule!="zincir+sanayisiz" else geoms[a<1500]   # buyuk tabanli (>1500 m2) yapilar sanayi/depo sayilir
        parts=shapely.get_parts(shapely.buffer(shapely.union_all(shapely.buffer(use,50)),-50))
        parts=parts[shapely.area(parts)>0]
        tree=shapely.STRtree(use); cnt=np.array([len(tree.query(p,predicate="intersects")) for p in parts])
        main=int(np.argmin(shapely.distance(parts,c)))
        keep={main}
        if rule!="tek kume":
            grow=True
            while grow:
                grow=False; cur=shapely.union_all(parts[list(keep)])
                for i in range(len(parts)):
                    if i not in keep and cnt[i]>=30 and shapely.distance(parts[i],cur)<300: keep.add(i); grow=True
        area=sum(shapely.area(parts[i]) for i in keep)/1e6; nb=int(sum(cnt[i] for i in keep))
        print(f"{name:10} {rule:17} alan {area:5.2f} km2  bina {nb:5}  kume {len(keep)}")
