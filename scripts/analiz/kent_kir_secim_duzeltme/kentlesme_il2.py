import csv,json,duckdb,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
c=duckdb.connect('C:/veri/warehouse.duckdb',read_only=True)
ILT={}
for p_,y_,v_ in c.sql("select split_part(area_id,'-',2),year(period_start),sum(value) from fact where indicator_id='population' and area_id like 'TR-__' and dims like 'age=%sex=%' and year(period_start) in (2013,2025) group by 1,2").fetchall():ILT[(p_,y_)]=v_
rows=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    def key(a):
        if a in K:return a
        d,cc=a.rsplit('-',1)
        if cc.isdigit() and f"{d}-{int(cc)+2000000}" in K:return f"{d}-{int(cc)+2000000}"
    if sum(1 for a in R if key(a))<0.97*len(R):continue
    pop=collections.defaultdict(float)
    for a,y,v in c.sql(f"select area_id,year(period_start),value from fact where indicator_id='population' and ((area_level='village' and dims='') or (area_level<>'village' and dims in ('age=0-17','age=18+'))) and year(period_start) in (2013,2025) and area_id like 'TR-{p}-%'").fetchall():
        if v is None:continue
        d,cc=a.rsplit('-',1)
        base=a if (a in R or a in K) else (f"{d}-{int(cc)-2000000}" if cc.isdigit() and f"{d}-{int(cc)-2000000}" in R else None)
        if base is None or a.count('-')!=3:continue
        k2=key(base)
        if not k2:continue
        pop[('kent' if isk(K[k2]['s']) else 'kır',y)]+=v
    k13,r13,k25,r25=pop[('kent',2013)],pop[('kır',2013)],pop[('kent',2025)],pop[('kır',2025)]
    cv13=(k13+r13)/ILT[(p,2013)];cv25=(k25+r25)/ILT[(p,2025)]
    rows.append((names.get(f'TR-{p}',p),100*k13/(k13+r13),100*k25/(k25+r25),cv13,cv25))
print(len(rows),'il')
print("il|kentleşme 2013|2025|fark (puan)|kapsama 2013|kapsama 2025")
for r in sorted(rows,key=lambda r:-(r[2]-r[1])):print(f"{r[0]}|{r[1]:.2f}|{r[2]:.2f}|{r[2]-r[1]:+.2f}|{100*r[3]:.2f}|{100*r[4]:.2f}")
