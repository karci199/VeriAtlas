import csv,json,urllib.request,sys
sys.stdout.reconfigure(encoding="utf-8")
P,DI,GC=sys.argv[1],sys.argv[2],sys.argv[3]
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
G={f['properties']['area_id'] for f in json.load(open(f"C:/veri/public/geo/neighbourhoods/TR-{P}-{GC}.geojson",encoding="utf-8"))['features']}
upd={};un=[]
for r in csv.DictReader(open(f"C:/veri-ham/analiz/kent_kir/{P}/kent_{P}_ikili.csv",encoding="utf-8")):
    if r['district']!=DI:continue
    a=r['area_id']
    if a in K:continue
    un.append(r['name']);d,c=a.rsplit('-',1);alt=f"{d}-{int(c)+2000000}"
    upd[a]={'s':'Köy'}
    if alt in G:upd[alt]={'s':'Köy'}
print(len(un),'işaretsiz ->',len(upd),'kayıt')
if '--yaz' in sys.argv:
    req=urllib.request.Request('http://127.0.0.1:8123/karar',data=json.dumps(upd,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST');print(urllib.request.urlopen(req).status)
