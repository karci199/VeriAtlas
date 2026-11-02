import csv,json,duckdb,collections,sys,os
sys.stdout.reconfigure(encoding="utf-8")
PL,ILCE=sys.argv[1],sys.argv[2]
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
R={r['area_id']:r for r in csv.DictReader(open(f"C:/veri-ham/analiz/kent_kir/{PL}/kent_{PL}_ikili.csv",encoding="utf-8")) if r['district']==ILCE}
def grp(a):
    v=K[a];s=v['s'].replace('İl Merkezi','İlçe Merkezi')
    return s if s in('İlçe Merkezi','Köy') else f"{s} · {v.get('y') or R[a]['name']}"
G={a:grp(a) for a in R if a in K}
order=lambda g:(0 if g=='İlçe Merkezi' else 1 if g.startswith('Kentsel') else 2 if g.startswith('Kırsal') else 3,g)
c=duckdb.connect('C:/veri/warehouse.duckdb',read_only=True)
P=collections.defaultdict(float)
SH={}
for a in R:
    d_,c_=a.rsplit('-',1)
    if c_.isdigit():SH[f"{d_}-{int(c_)+2000000}"]=a
ids="','".join(list(R)+list(SH))
for a,y,v in c.sql(f"select area_id,year(period_start),value from fact where indicator_id='population' and ((area_level='village' and dims='') or (area_level<>'village' and dims in ('age=0-17','age=18+'))) and year(period_start) in (2013,2019,2025) and area_id in ('{ids}')").fetchall():
    a=SH.get(a,a)
    if a in G and v is not None:P[(G[a],y)]+=v
B=[(0,4),(5,9),(10,14),(15,19),(20,24),(25,29),(30,34),(35,39),(40,44),(45,49),(50,54),(55,59),(60,64)]
did=next(iter(R)).rsplit('-',1)[0]
E=json.load(open(f"C:/veri-ham/endeksa/demography/{did}.json",encoding="utf-8")) if os.path.exists(f"C:/veri-ham/endeksa/demography/{did}.json") else {}
D=collections.defaultdict(lambda:[collections.Counter(),collections.Counter()])
for a,g in G.items():
    code=a.rsplit('-',1)[1];e=E.get(code) or (E.get(str(int(code)+2000000)) if code.isdigit() else None);d=(e or {}).get('demography') or {}
    if not d.get('PopulationTotal'):continue
    for lo,hi in B:D[g][0][lo]+=(d.get(f'Age_{lo}_{hi}_Male',0) or 0)+(d.get(f'Age_{lo}_{hi}_Female',0) or 0)
    D[g][0][65]+=(d.get('Age_65_Male',0) or 0)+(d.get('Age_65_Female',0) or 0)
    for f in('MarriedNever','Married','Divorced','Widow'):D[g][1][f]+=d.get(f,0) or 0
def med(cc):
    t=sum(cc.values());h=t/2;cum=0
    for lo,hi in B:
        if cum+cc[lo]>=h:return lo+(h-cum)/cc[lo]*(hi+1-lo)
        cum+=cc[lo]
print(f"## {ILCE}: nüfus, yıllara göre\ngrup|mahalle|2013|2019|2025|değişim 13→25")
cnt=collections.Counter(G.values())
for g in sorted(cnt,key=order):
    a,b,cc_=P[(g,2013)],P[(g,2019)],P[(g,2025)]
    print(f"{g}|{cnt[g]}|{a:,.0f}|{b:,.0f}|{cc_:,.0f}|{(100*(cc_/a-1)) if a else 0:+.0f}%")
print(f"\n## yaş ve medeni durum (Endeksa 2024)\ngrup|ortanca|0-14|65+|hiç evlenmemiş|boşanmış")
for g in sorted(cnt,key=order):
    cc=D[g][0];t=sum(cc.values())
    if not t:print(g,'veri yok');continue
    m=sum(D[g][1].values())
    print(f"{g}|{med(cc):.1f}|%{100*(cc[0]+cc[5]+cc[10])/t:.0f}|%{100*cc[65]/t:.0f}|%{100*D[g][1]['MarriedNever']/m:.0f}|%{100*D[g][1]['Divorced']/m:.1f}")
for e in('mv2018','mv2023','cb2023t2'):
    T=json.load(open(f"C:/veri/public/tiles/secim-{e}-mahalle-TR-{PL}.json",encoding="utf-8"))
    A=collections.defaultdict(collections.Counter)
    for aid,v in T.items():
        did_,code=aid.rsplit('-',1)
        if code.isdigit() and int(code)>=2000000 and f"{did_}-{int(code)-2000000}" in K:aid=f"{did_}-{int(code)-2000000}"
        if aid not in G or v['o']>=v['k']+20:continue
        for p,n in v['v'].items():A[G[aid]][p]+=n
    print(f"\n## {e}\ngrup|geçerli|"+"|".join(['AKP','CHP','MHP','Yeşil Sol/HDP','İYİ','Diğer']) if e!='cb2023t2' else f"\n## {e}\ngrup|geçerli|Erdoğan|Kılıçdaroğlu")
    for g in sorted(cnt,key=order):
        t=sum(A[g].values())
        if not t:continue
        if e=='cb2023t2':
            ke=sum(n for p,n in A[g].items() if p.startswith('RECEP'));kk=sum(n for p,n in A[g].items() if p.startswith('KEMAL'))
            print(f"{g}|{t}|{100*ke/t:.1f}|{100*kk/t:.1f}")
        else:
            ak=A[g].get('AK PARTİ',0);ch=A[g].get('CHP',0);mh=A[g].get('MHP',0);ys=A[g].get('YEŞİL SOL PARTİ',0)+A[g].get('HDP',0);iy=A[g].get('İYİ PARTİ',0)
            print(f"{g}|{t}|{100*ak/t:.1f}|{100*ch/t:.1f}|{100*mh/t:.1f}|{100*ys/t:.1f}|{100*iy/t:.1f}|{100*(t-ak-ch-mh-ys-iy)/t:.1f}")
