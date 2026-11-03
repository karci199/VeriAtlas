import csv,json,duckdb,collections,sys
from shapely.geometry import shape
sys.stdout.reconfigure(encoding="utf-8")
P_,D_=sys.argv[1],sys.argv[2]
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
R={r['area_id']:r for r in csv.DictReader(open(f"C:/veri-ham/analiz/kent_kir/{P_}/kent_{P_}_ikili.csv",encoding="utf-8")) if r['district']==D_}
did=next(iter(R)).rsplit('-',1)[0]
c=duckdb.connect('C:/veri/warehouse.duckdb',read_only=True)
P=collections.defaultdict(dict)
for a,y,v in c.sql(f"select area_id,year(period_start),value from fact where indicator_id='population' and ((area_level='village' and dims='') or (area_level<>'village' and dims in ('age=0-17','age=18+'))) and year(period_start) in (2013,2019,2025) and area_id like '{did}-%'").fetchall():P[a][y]=P[a].get(y,0)+(v or 0)
def pop(a,y):
    d,c_=a.rsplit('-',1);return (P.get(a) or P.get(f"{d}-{int(c_)+2000000}") or {}).get(y,0)
geo={f['properties']['area_id']:shape(f['geometry']) for f in json.load(open(f"C:/veri/public/geo/neighbourhoods/{did}.geojson",encoding="utf-8"))['features']}
g=lambda a:a if a in geo else f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}"
cls=lambda a:K.get(a,{}).get('s','YOK')
print(did,len(R),dict(collections.Counter(cls(a) for a in R)),'nüfus',sum(pop(a,2025) for a in R),'(2013:',sum(pop(a,2013) for a in R),')')
rows=sorted(((pop(a,2025),pop(a,2013),pop(a,2019),R[a]['name'],R[a]['son_sinif'],cls(a),a) for a in R),reverse=True)
for x in rows[:int(sys.argv[3]) if len(sys.argv)>3 else 9]:
    s=geo[g(x[6])];print(f"{x[3]:18} {x[0]:6.0f} (2013 {x[1]:6.0f}, 2019 {x[2]:6.0f}) oto:{x[4]:13} işaret:{cls(x[6]):13} {s.area*111*111*.76:5.1f}km2",[R[b]['name'] for b in R if b!=x[6] and s.buffer(0.0004).intersects(geo[g(b)])][:4],'|',R[x[6]]['note'][:45])
print('otomatik merkez/belde ama işaretli değil:',[(x[3],x[0]) for x in rows if x[4] in('merkez','kasaba','kentsel_belde','kirsal_belde') and x[5] in('YOK','Köy')][:10])
