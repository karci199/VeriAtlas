import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
exec(open("C:/veri-ham/analiz/kent_kir/_secim_duzeltme/ortak.py",encoding="utf-8").read())
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
P5={'AKP':['AK PARTİ'],'MHP':['MHP'],'CHP':['CHP'],'İYİ':['İYİ PARTİ'],'YSP/HDP':['YEŞİL SOL PARTİ','HDP']}
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
def agg(c):
    t=sum(c.values())
    out={k:sum(c[q] for q in L) for k,L in P5.items()}
    ittif=sum(n for q,n in c.items() if q.endswith('İTTİFAKI') or q=='MİLLET')
    out['diğer']=t-sum(out.values())-ittif;out['ittifak']=ittif;out['T']=t;return out
G={g:{y:collections.Counter() for y in('mv2018','mv2023')} for g in('kent','kır')}
IL=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R) or p in('19','65'):continue
    L={'kent':{y:collections.Counter() for y in G['kent']},'kır':{y:collections.Counter() for y in G['kır']}}
    for yr in('mv2018','mv2023'):
        M=json.load(open(f"C:/veri/public/tiles/secim-{yr}-mahalle-TR-{p}.json",encoding="utf-8"))
        for a,m in M.items():
            if m['o']>=m['k']+20:continue
            g=cls(p,a,m,True)
            L[g][yr].update(m['v']);G[g][yr].update(m['v'])
    IL.append((names.get(f'TR-{p}',p),L))
print("30 il toplamı (Çorum, Van dışarıda: İYİ 2023'te ayrı liste çıkarmadı). Pay % 2018 → 2023, fark puan; oy sayısı farkı")
for g in('kent','kır'):
    a,b=agg(G[g]['mv2018']),agg(G[g]['mv2023'])
    print(f"\n{g.upper()} (geçerli oy 2018: {a['T']}, 2023: {b['T']})")
    for k in list(P5)+['ittifak','diğer']:
        print(f"{k}|{100*a[k]/a['T']:.2f}|{100*b[k]/b['T']:.2f}|{100*b[k]/b['T']-100*a[k]/a['T']:+.2f}|{b[k]-a[k]:+d}")
print("\nİL KENT: pay farkı (puan) 2018→2023: AKP|MHP|CHP|İYİ|YSP|diğer  (en çok kaybeden)")
for nm,L in IL:
    a,b=agg(L['kent']['mv2018']),agg(L['kent']['mv2023'])
    d={k:100*b[k]/b['T']-100*a[k]/a['T'] for k in list(P5)+['diğer']}
    lose=min((k for k in P5),key=lambda k:d[k])
    print(f"{nm}|"+"|".join(f"{d[k]:+.2f}" for k in list(P5)+['diğer'])+f"|{lose}")
