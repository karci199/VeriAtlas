import json,csv,glob,os,collections,sys,re
sys.stdout.reconfigure(encoding="utf-8")
SP="C:/Users/katan/AppData/Local/Temp/claude/C--veri--claude-worktrees-nerede-kaldik-60b0da/09d35bec-4acb-47c1-8594-85d303f66f97/scratchpad/"
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
TC=json.load(open(SP+"tilde_class.json",encoding="utf-8"))
W="C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/"
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
tr=str.maketrans("ıİşŞçÇğĞöÖüÜ","iissccggoouu")
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
def heur(ad,k):
    a=(ad or '').translate(tr).lower()
    if 'koy' in a:return 'kır'
    if re.search(r'evler|merkez|orta|cumhuriyet|yenimahalle|mayis|karsiyaka|firat|yeni|mah',a) and k>=800:return 'kent'
    return 'kent' if k>=2000 else 'kır'
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
def cls(p,a,v,eski):
    if '~' not in a:
        n=nrm(a);return 'kent' if (n and isk(K[n]['s'])) else 'kır'
    if not eski:return 'kır'
    c=TC.get(f"{p}|{a}")
    if c and c[0]:return c[0]
    return heur(v.get('ad'),v['k'])
plates=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk>=0.97*len(R):plates.append(p)
res={}
for eski in(True,False):
    for p in plates:
        T=json.load(open(f"{W}secim-ho2017-mahalle-TR-{p}.json",encoding="utf-8"))
        A={'kent':[0,0],'kır':[0,0]}
        for a,v in T.items():
            if v['o']>=v['k']+20:continue
            g=cls(p,a,v,eski);A[g][0]+=v['v'].get('Evet oyları',0);A[g][1]+=v['v'].get('Hayır oyları',0)
        res[(eski,p)]=A
hp=lambda x:100*x[1]/sum(x) if sum(x) else float('nan')
print("== REFERANDUM 2017 HAYIR: il|kent (önce→sonra)|kır (önce→sonra)|fark önce→sonra|kent hayır (kişi) sonra|kır hayır (kişi) sonra")
tot={True:{'kent':[0,0],'kır':[0,0]},False:{'kent':[0,0],'kır':[0,0]}}
order=[]
for p in plates:
    a,b=res[(False,p)],res[(True,p)]
    for e in(True,False):
        for g in('kent','kır'):
            for i in(0,1):tot[e][g][i]+=res[(e,p)][g][i]
    order.append((hp(b['kent'])-hp(b['kır']),p))
for _,p in sorted(order):
    a,b=res[(False,p)],res[(True,p)]
    print(f"{names.get('TR-'+p,p)}|{hp(a['kent']):.2f}→{hp(b['kent']):.2f}|{hp(a['kır']):.2f}→{hp(b['kır']):.2f}|{hp(a['kent'])-hp(a['kır']):+.2f}→{hp(b['kent'])-hp(b['kır']):+.2f}|{b['kent'][1]}|{b['kır'][1]}")
for e,t in((False,'ÖNCE'),(True,'SONRA')):
    k,r=tot[e]['kent'],tot[e]['kır'];print(f"TOPLAM {t}|kent hayır {hp(k):.2f} ({k[1]} hayır, {k[0]} evet)|kır hayır {hp(r):.2f} ({r[1]} hayır, {r[0]} evet)|fark {hp(k)-hp(r):+.2f}")
