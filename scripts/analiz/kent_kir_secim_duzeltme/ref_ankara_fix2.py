import csv,json,collections,sys,glob,re
sys.stdout.reconfigure(encoding="utf-8")
W="C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/"
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
P='06'
R={r['area_id']:r for r in csv.DictReader(open(f"C:/veri-ham/analiz/kent_kir/{P}/kent_{P}_ikili.csv",encoding="utf-8"))}
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith(f'TR-{P}-'):names[r[0]]=r[2]
tr=str.maketrans("ıİşŞçÇğĞöÖüÜ","iissccggoouu")
tok=lambda s:{t for t in re.sub(r"[^\w ]"," ",s.translate(tr).lower()).split() if t not in('mah','koy','mahallesi','koyu')}
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde')
def nrm(a):
    if a in K:return a
    if a.rsplit('-',1)[-1].isdigit():
        d,c=a.rsplit('-',1);b=f"{d}-{int(c)-2000000}"
        if b in K:return b
T=json.load(open(f"{W}secim-ho2017-mahalle-TR-{P}.json",encoding="utf-8"))
inv={}
for a,r in R.items():inv.setdefault(a.rsplit('-',1)[0],r['district'])
S=collections.defaultdict(lambda:{'kent':[0,0],'kır':[0,0]});how=collections.Counter();unres=collections.Counter()
for a,v in T.items():
    if v['o']>=v['k']+20:continue
    e=v['v'].get('Evet oyları',0);h=v['v'].get('Hayır oyları',0)
    pre=a.split('~')[0] if '~' in a else a.rsplit('-',1)[0]
    d=inv.get(pre)
    if '~' not in a:
        n=nrm(a);g='kent' if (n and isk(K[n]['s'])) else 'kır'
    else:
        ad=tok(v.get('ad') or '')
        g=None
        cand=[b for b in R if b.startswith(pre+'-') and ad and ad<=tok(R[b]['name'])]
        cls={('kent' if isk(K[nrm(b)]['s']) else 'kır') for b in cand if nrm(b)}
        if len(cls)==1:g=cls.pop();how['güncel mahalle adıyla eşleşti']+=e+h
        else:
            old=[i for i,n in names.items() if i.startswith(pre+'-') and i not in R and ad and tok(n)==ad]
            if old:
                n=names[old[0]]
                g='kır' if 'koy' in n.translate(tr).lower() else 'kent';how['eski kimlik adı ("Mah."=kent, "Köy"=kır)']+=e+h
            else:
                man={'Aşağı Dikmen':'kent','Peyami Sefa':'kent','Anayurt':'kent','Sindiren':'kır'}
                g=man.get(v.get('ad'),'kır');how['elle (kent sokak/mahalle: Aşağı Dikmen, Peyami Sefa, Anayurt; Sindiren köy)']+=e+h
    if d:S[d][g][0]+=e;S[d][g][1]+=h
print(dict(how));print('çözülemeyen:',dict(unres))
hp=lambda x:100*x[1]/sum(x) if sum(x) else float('nan')
print("ilçe|kent hayır %|kent hayır (kişi)|kent evet (kişi)|kır hayır %|kır oy|ilçe hayır %|fark")
tk=[0,0];tr_=[0,0]
for d in sorted(S,key=lambda d:-hp(S[d]['kent']) if sum(S[d]['kent']) else 0):
    k,r=S[d]['kent'],S[d]['kır'];t=[k[0]+r[0],k[1]+r[1]]
    for i in(0,1):tk[i]+=k[i];tr_[i]+=r[i]
    print(f"{d}|{hp(k):.2f}|{k[1]}|{k[0]}|{hp(r):.2f}|{sum(r)}|{hp(t):.2f}|{hp(k)-hp(r):+.2f}")
t=[tk[0]+tr_[0],tk[1]+tr_[1]]
print(f"ANKARA|{hp(tk):.2f}|{tk[1]}|{tk[0]}|{hp(tr_):.2f}|{sum(tr_)}|{hp(t):.2f}|{hp(tk)-hp(tr_):+.2f}")
