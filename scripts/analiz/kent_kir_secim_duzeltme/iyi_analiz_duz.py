import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
exec(open("C:/veri-ham/analiz/kent_kir/_secim_duzeltme/ortak.py",encoding="utf-8").read())
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
rows=[];G={g:[0,0,0,0] for g in('kent','kır')};pts=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    M8=json.load(open(f"C:/veri/public/tiles/secim-mv2018-mahalle-TR-{p}.json",encoding="utf-8"))
    M3=json.load(open(f"C:/veri/public/tiles/secim-mv2023-mahalle-TR-{p}.json",encoding="utf-8"))
    H=json.load(open(f"C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/secim-ho2017-mahalle-TR-{p}.json",encoding="utf-8"))
    A={'kent':[0,0,0,0],'kır':[0,0,0,0]}
    for a,m8 in M8.items():
        m3=M3.get(a)
        if m8['o']>=m8['k']+20:continue
        g=cls(p,a,m8,True)
        t8=sum(m8['v'].values());i8=m8['v'].get('İYİ PARTİ',0)
        A[g][0]+=i8;A[g][1]+=t8;G[g][0]+=i8;G[g][1]+=t8
        if m3 and m3['o']<m3['k']+20:
            t3=sum(m3['v'].values());i3=m3['v'].get('İYİ PARTİ',0)
            A[g][2]+=i3;A[g][3]+=t3;G[g][2]+=i3;G[g][3]+=t3
        h=H.get(a)
        if h and t8>=100 and sum(h['v'].values())>=100:
            hy=h['v'].get('Hayır oyları',0)/sum(h['v'].values());pts.append((g,hy,i8/t8))
    if min(A['kent'][1],A['kır'][1])<500:continue
    rows.append((names.get(f'TR-{p}',p),A))
print("il|kent İYİ 2018|2023|fark|kır İYİ 2018|2023|fark")
for nm,A in sorted(rows,key=lambda r:-(100*r[1]['kent'][0]/r[1]['kent'][1])):
    k=A['kent'];r=A['kır']
    f=lambda x:(100*x[0]/x[1],100*x[2]/x[3] if x[3] else float('nan'))
    a,b=f(k);c,d=f(r)
    print(f"{nm}|{a:.2f}|{b:.2f}|{b-a:+.2f}|{c:.2f}|{d:.2f}|{d-c:+.2f}")
for g in('kent','kır'):
    X=G[g];print(f"TOPLAM {g}|{100*X[0]/X[1]:.2f}|{100*X[2]/X[3]:.2f}")
for g in('kent','kır'):
    P=[(h,i) for gg,h,i in pts if gg==g];n=len(P)
    mx=sum(p[0] for p in P)/n;my=sum(p[1] for p in P)/n
    cov=sum((x-mx)*(y-my) for x,y in P);vx=sum((x-mx)**2 for x,y in P);vy=sum((y-my)**2 for x,y in P)
    print(g,'mahalle',n,'hayır 2017 ↔ İYİ 2018 korelasyon %.3f eğim %.3f'%(cov/(vx*vy)**.5,cov/vx))
