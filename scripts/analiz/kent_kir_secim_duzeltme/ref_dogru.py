import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
W="C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/"
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
IL=[];ILCE={}
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    inv={}
    for a,r in R.items():inv.setdefault(a.rsplit('-',1)[0],r['district'])
    T=json.load(open(f"{W}secim-ho2017-mahalle-TR-{p}.json",encoding="utf-8"))
    A={'kent':[0,0],'kır':[0,0]};S=collections.defaultdict(lambda:{'kent':[0,0],'kır':[0,0]})
    for a,v in T.items():
        if v['o']>=v['k']+20:continue
        e=v['v'].get('Evet oyları',0);h=v['v'].get('Hayır oyları',0)
        n=nrm(a);g='kent' if (n and isk(K[n]['s'])) else 'kır'
        d=inv.get(a.split('~')[0] if '~' in a else a.rsplit('-',1)[0])
        A[g][0]+=e;A[g][1]+=h
        if d:S[d][g][0]+=e;S[d][g][1]+=h
    IL.append((p,names.get(f'TR-{p}',p),A));ILCE[p]=S
def hp(x):return 100*x[1]/sum(x) if sum(x) else float('nan')
print("== 30 İL: kent hayır %|kır hayır %|fark|kent hayır (kişi)|kent evet (kişi)|kır hayır (kişi)")
tk=[0,0];tr=[0,0]
for p,nm,A in sorted(IL,key=lambda r:-(hp(r[2]['kent'])-hp(r[2]['kır']))*-1):
    k,r=A['kent'],A['kır']
    for i in(0,1):tk[i]+=k[i];tr[i]+=r[i]
    print(f"{nm}|{hp(k):.2f}|{hp(r):.2f}|{hp(k)-hp(r):+.2f}|{k[1]}|{k[0]}|{r[1]}")
print(f"TOPLAM|{hp(tk):.2f}|{hp(tr):.2f}|{hp(tk)-hp(tr):+.2f}|{tk[1]}|{tk[0]}|{tr[1]}")
for p,title in(('16','BURSA'),('61','TRABZON')):
    S=ILCE[p];tk=[0,0];tr=[0,0]
    print(f"\n== {title} ilçe: kent hayır %|kent hayır (kişi)|kent evet (kişi)|kır hayır %|kır oy|ilçe hayır %|fark")
    for d in sorted(S,key=lambda d:-hp(S[d]['kent']) if sum(S[d]['kent']) else 0):
        k,r=S[d]['kent'],S[d]['kır'];t=[k[0]+r[0],k[1]+r[1]]
        for i in(0,1):tk[i]+=k[i];tr[i]+=r[i]
        print(f"{d}|{hp(k):.2f}|{k[1]}|{k[0]}|{hp(r):.2f}|{sum(r)}|{hp(t):.2f}|{hp(k)-hp(r):+.2f}")
    t=[tk[0]+tr[0],tk[1]+tr[1]]
    print(f"{title}|{hp(tk):.2f}|{tk[1]}|{tk[0]}|{hp(tr):.2f}|{sum(tr)}|{hp(t):.2f}|{hp(tk)-hp(tr):+.2f}")
