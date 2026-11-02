import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
exec(open("C:/veri-ham/analiz/kent_kir/_secim_duzeltme/ortak.py",encoding="utf-8").read())
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
BIG={'AK PARTİ','MHP','CHP','İYİ PARTİ','YEŞİL SOL PARTİ','HDP'}
ALL=lambda q:q.endswith('İTTİFAKI') or q=='MİLLET'
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
def other(v):return sum(n for q,n in v.items() if q not in BIG and not ALL(q))
rows=[];G={'kent':[0,0,0,0],'kır':[0,0,0,0]};comp=collections.Counter();ilce=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    inv={}
    for a,r in R.items():inv.setdefault(a.rsplit('-',1)[0],r['district'])
    A={'kent':[0,0,0,0],'kır':[0,0,0,0]};S=collections.defaultdict(lambda:{'kent':[0,0,0,0],'kır':[0,0,0,0]})
    for yr,off in(('mv2018',0),('mv2023',2)):
        M=json.load(open(f"C:/veri/public/tiles/secim-{yr}-mahalle-TR-{p}.json",encoding="utf-8"))
        for a,m in M.items():
            if m['o']>=m['k']+20:continue
            g=cls(p,a,m,True)
            t=sum(m['v'].values());o=other(m['v'])
            d=inv.get(a.split('~')[0] if '~' in a else a.rsplit('-',1)[0])
            for X in((A[g],G[g])+((S[d][g],) if d else ())):X[off]+=o;X[off+1]+=t
            if yr=='mv2023':
                for q,nn in m['v'].items():
                    if q not in BIG and not ALL(q):comp[(g,q)]+=nn
    if min(A['kent'][1],A['kır'][1])>=500:rows.append((names.get(f'TR-{p}',p),A))
    for d,v in S.items():
        k,r=v['kent'],v['kır']
        if min(k[1],k[3])>=3000 and min(r[1],r[3])>=1000:ilce.append((names.get(f'TR-{p}',p),d,100*k[0]/k[1],100*k[2]/k[3],100*r[0]/r[1],100*r[2]/r[3]))
print("il|kent diğer 2018|2023|fark|kır diğer 2018|2023|fark")
for nm,A in sorted(rows,key=lambda r:-(100*r[1]['kent'][2]/r[1]['kent'][3])):
    k,r=A['kent'],A['kır']
    a,b,c,d=100*k[0]/k[1],100*k[2]/k[3],100*r[0]/r[1],100*r[2]/r[3]
    print(f"{nm}|{a:.2f}|{b:.2f}|{b-a:+.2f}|{c:.2f}|{d:.2f}|{d-c:+.2f}")
for g in('kent','kır'):
    X=G[g];print(f"TOPLAM {g}|{100*X[0]/X[1]:.2f}|{100*X[2]/X[3]:.2f}|{100*X[2]/X[3]-100*X[0]/X[1]:+.2f}")
print("\n2023 diğer içinde en büyük (30 il, kent / kır oy):")
tot={g:sum(v for (gg,q),v in comp.items() if gg==g) for g in('kent','kır')}
qs=sorted({q for g,q in comp},key=lambda q:-(comp[('kent',q)]+comp[('kır',q)]))[:10]
for q in qs:print(f"{q}|{100*comp[('kent',q)]/tot['kent']:.1f}|{100*comp[('kır',q)]/tot['kır']:.1f}")
print("\nİLÇE diğer 2023 kent en yüksek 8");
for o in sorted(ilce,key=lambda o:-o[3])[:8]:print(f"{o[0]}|{o[1]}|{o[2]:.2f}→{o[3]:.2f}|kır {o[4]:.2f}→{o[5]:.2f}")
print("İLÇE diğer 2018→2023 en çok artan 8")
for o in sorted(ilce,key=lambda o:-(o[3]-o[2]))[:8]:print(f"{o[0]}|{o[1]}|{o[2]:.2f}→{o[3]:.2f}|kır {o[4]:.2f}→{o[5]:.2f}")
