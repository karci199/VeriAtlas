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
out=[]
for p in sorted({a.split('-')[1] for a in K}):
    if p in('19','65'):continue
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    inv={}
    for a,r in R.items():inv.setdefault(a.rsplit('-',1)[0],r['district'])
    M8=json.load(open(f"C:/veri/public/tiles/secim-mv2018-mahalle-TR-{p}.json",encoding="utf-8"))
    M3=json.load(open(f"C:/veri/public/tiles/secim-mv2023-mahalle-TR-{p}.json",encoding="utf-8"))
    S=collections.defaultdict(lambda:{'kent':[0,0,0,0],'kır':[0,0,0,0]})
    for yr,M,off in((2018,M8,0),(2023,M3,2)):
        for a,m in M.items():
            if m['o']>=m['k']+20:continue
            did=a.split('~')[0] if '~' in a else a.rsplit('-',1)[0]
            d=inv.get(did)
            if not d:continue
            g=cls(p,a,m,True)
            X=S[d][g];X[off]+=m['v'].get('İYİ PARTİ',0);X[off+1]+=sum(m['v'].values())
    for d,v in S.items():
        k,r=v['kent'],v['kır']
        if k[1]>=3000 and k[3]>=3000 and r[1]>=1000 and r[3]>=1000:
            out.append((names.get(f'TR-{p}',p),d,100*k[0]/k[1],100*k[2]/k[3],100*r[0]/r[1],100*r[2]/r[3],k[3],r[3]))
print(len(out),'ilçe')
def pr(t,L):
    print("\n"+t);print("il|ilçe|kent 2018|kent 2023|fark|kır 2018|kır 2023|fark|kent oy 23|kır oy 23")
    for o in L:print(f"{o[0]}|{o[1]}|{o[2]:.2f}|{o[3]:.2f}|{o[3]-o[2]:+.2f}|{o[4]:.2f}|{o[5]:.2f}|{o[5]-o[4]:+.2f}|{o[6]}|{o[7]}")
pr("KENT İYİ EN YÜKSEK 10 (2023)",sorted(out,key=lambda o:-o[3])[:10])
pr("KENT İYİ 2018→2023 EN ÇOK ARTAN 10",sorted(out,key=lambda o:-(o[3]-o[2]))[:10])
pr("KENT İYİ 2018→2023 EN ÇOK DÜŞEN 10",sorted(out,key=lambda o:(o[3]-o[2]))[:10])
