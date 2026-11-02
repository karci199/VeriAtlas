import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
exec(open("C:/veri-ham/analiz/kent_kir/_secim_duzeltme/ortak.py",encoding="utf-8").read())
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
CU=['AK PARTİ','MHP','BÜYÜK BİRLİK','CUMHUR İTTİFAKI']
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
rows=[];G={'kent':[0,0,0,0],'kır':[0,0,0,0]};pts=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    H=json.load(open(f"C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/secim-ho2017-mahalle-TR-{p}.json",encoding="utf-8"))
    M=json.load(open(f"C:/veri/public/tiles/secim-mv2018-mahalle-TR-{p}.json",encoding="utf-8"))
    A={'kent':[0,0,0,0],'kır':[0,0,0,0]}
    for a,h in H.items():
        m=M.get(a)
        if not m or h['o']>=h['k']+20 or m['o']>=m['k']+20:continue
        e=h['v'].get('Evet oyları',0);hy=h['v'].get('Hayır oyları',0)
        cu=sum(m['v'].get(q,0) for q in CU);tm=sum(m['v'].values())
        g=cls(p,a,m,True)
        for X in(A[g],G[g]):X[0]+=e;X[1]+=e+hy;X[2]+=cu;X[3]+=tm
        if e+hy>=100 and tm>=100:pts.append((g,e/(e+hy),cu/tm,e+hy))
    if min(A['kent'][1],A['kır'][1])<500:continue
    rows.append((names.get(f'TR-{p}',p),A))
print("il|kent: evet 2017|Cumhur 2018|fark|kır: evet 2017|Cumhur 2018|fark")
for nm,A in sorted(rows,key=lambda r:-(100*r[1]['kent'][0]/r[1]['kent'][1]-100*r[1]['kent'][2]/r[1]['kent'][3])):
    k=A['kent'];r=A['kır']
    ek,ck=100*k[0]/k[1],100*k[2]/k[3];er,cr=100*r[0]/r[1],100*r[2]/r[3]
    print(f"{nm}|{ek:.2f}|{ck:.2f}|{ek-ck:+.2f}|{er:.2f}|{cr:.2f}|{er-cr:+.2f}")
for g in('kent','kır'):
    X=G[g];print(f"TOPLAM {g}|{100*X[0]/X[1]:.2f}|{100*X[2]/X[3]:.2f}|{100*X[0]/X[1]-100*X[2]/X[3]:+.2f}")
import statistics
for g in('kent','kır'):
    P=[(e,c,w) for gg,e,c,w in pts if gg==g]
    n=len(P);xs=[p[0] for p in P];ys=[p[1] for p in P]
    mx,my=sum(xs)/n,sum(ys)/n
    cov=sum((x-mx)*(y-my) for x,y in P and zip(xs,ys));vx=sum((x-mx)**2 for x in xs);vy=sum((y-my)**2 for y in ys)
    print(g,'mahalle',n,'korelasyon %.3f'%(cov/(vx*vy)**.5),'eğim %.3f'%(cov/vx))
