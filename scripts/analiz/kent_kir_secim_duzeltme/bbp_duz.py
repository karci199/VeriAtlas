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
rows=[];ilce=[];G={'kent':[0,0],'kır':[0,0]};b18=[0,0]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    inv={}
    for a,r in R.items():inv.setdefault(a.rsplit('-',1)[0],r['district'])
    M3=json.load(open(f"C:/veri/public/tiles/secim-mv2023-mahalle-TR-{p}.json",encoding="utf-8"))
    M8=json.load(open(f"C:/veri/public/tiles/secim-mv2018-mahalle-TR-{p}.json",encoding="utf-8"))
    Y=json.load(open(f"C:/veri/public/tiles/secim-yerel_bel_2024-mahalle-TR-{p}.json",encoding="utf-8"))
    A={'kent':[0,0,0,0],'kır':[0,0,0,0]};S=collections.defaultdict(lambda:{'kent':[0,0],'kır':[0,0]})
    for a,m in M3.items():
        if m['o']>=m['k']+20:continue
        g=cls(p,a,m,True)
        t=sum(m['v'].values());b=m['v'].get('BÜYÜK BİRLİK',0)
        A[g][0]+=b;A[g][1]+=t;G[g][0]+=b;G[g][1]+=t
        d=inv.get(a.split('~')[0] if '~' in a else a.rsplit('-',1)[0])
        if d:S[d][g][0]+=b;S[d][g][1]+=t
    for a,m in M8.items():
        if m['o']>=m['k']+20:continue
        b18[0]+=m['v'].get('BÜYÜK BİRLİK',0);b18[1]+=sum(m['v'].values())
    for a,m in Y.items():
        if m['o']>=m['k']+20:continue
        g=cls(p,a,m,True)
        A[g][2]+=m['v'].get('BÜYÜK BİRLİK',0);A[g][3]+=sum(m['v'].values())
    if min(A['kent'][1],A['kır'][1])>=500:rows.append((names.get(f'TR-{p}',p),A))
    for d,v in S.items():
        if v['kent'][1]>=3000 and v['kır'][1]>=1000:ilce.append((names.get(f'TR-{p}',p),d,100*v['kent'][0]/v['kent'][1],100*v['kır'][0]/v['kır'][1],v['kent'][1],v['kır'][1]))
print("il|kent BBP 2023|kır BBP 2023|fark (kır−kent)|kent BBP 2024 belediye|kır BBP 2024")
for nm,A in sorted(rows,key=lambda r:-(100*r[1]['kent'][0]/r[1]['kent'][1])):
    k,r=A['kent'],A['kır']
    f=lambda x,i:100*x[i]/x[i+1] if x[i+1] else float('nan')
    print(f"{nm}|{f(k,0):.2f}|{f(r,0):.2f}|{f(r,0)-f(k,0):+.2f}|{f(k,2):.2f}|{f(r,2):.2f}")
print(f"TOPLAM|{100*G['kent'][0]/G['kent'][1]:.2f}|{100*G['kır'][0]/G['kır'][1]:.2f}")
print('BBP 2018 (ayrı liste):',b18)
print("\nİLÇE (kent BBP 2023 en yüksek 10)")
for o in sorted(ilce,key=lambda o:-o[2])[:10]:print(f"{o[0]}|{o[1]}|{o[2]:.2f}|{o[3]:.2f}|{o[4]}|{o[5]}")
print("İLÇE (kır BBP 2023 en yüksek 10)")
for o in sorted(ilce,key=lambda o:-o[3])[:10]:print(f"{o[0]}|{o[1]}|{o[2]:.2f}|{o[3]:.2f}|{o[4]}|{o[5]}")
