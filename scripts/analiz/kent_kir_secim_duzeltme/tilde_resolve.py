import json,csv,glob,os,collections,sys,re
sys.stdout.reconfigure(encoding="utf-8")
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
W="C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/"
fam={'ho2017':W,'mv2018':"C:/veri/public/tiles/",'mv2023':"C:/veri/public/tiles/"}
allnames={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-'):allnames[r[0]]=r[2]
tr=str.maketrans("ıİşŞçÇğĞöÖüÜâîû","iissccggoouuaiu")
def tok(s):
    s=s.translate(tr).lower();s=re.sub(r"\(b\)|\(belde\)"," ",s)
    return {t for t in re.sub(r"[^\w ]"," ",s).split() if t not in('mah','koy','mahallesi','koyu','belediyesi','merkez')}
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
OUT={};UN=[]
plates=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R):continue
    plates.append(p)
    def kk(b):
        if b in K:return b
        d,c=b.rsplit('-',1)
        return f"{d}-{int(c)+2000000}" if c.isdigit() and f"{d}-{int(c)+2000000}" in K else None
    belde=collections.defaultdict(set)
    for b in R:
        k=kk(b)
        if k and K[k].get('y'):belde[b.rsplit('-',1)[0]].add((frozenset(tok(K[k]['y'])),'kent' if isk(K[k]['s']) else 'kır'))
    for fm,base in fam.items():
        T=json.load(open(f"{base}secim-{fm}-mahalle-TR-{p}.json",encoding="utf-8"))
        for a,v in T.items():
            if '~' not in a:continue
            pre=a.split('~')[0];ad=tok(v.get('ad') or '')
            key=f"{p}|{a}"
            if key in OUT:continue
            cand=[b for b in R if b.startswith(pre+'-') and ad and ad<=tok(R[b]['name'])]
            cls={('kent' if isk(K[kk(b)]['s']) else 'kır') for b in cand if kk(b)}
            if len(cls)==1:OUT[key]=(cls.pop(),'ad-eşleşti');continue
            bm={c for t,c in belde.get(pre,()) if ad and t==ad}
            if len(bm)==1:OUT[key]=(bm.pop(),'belde-adı');continue
            old=[i for i,n in allnames.items() if i.startswith(pre+'-') and i not in R and ad and tok(n)==ad]
            if old:
                n=allnames[old[0]].translate(tr).lower()
                OUT[key]=('kır' if 'koy' in n else 'kent','eski-kimlik');continue
            OUT[key]=(None,'çözülemedi');UN.append((p,pre,v.get('ad'),v['g'],v['k'],fm))
json.dump(OUT,open("C:/Users/katan/AppData/Local/Temp/claude/C--veri--claude-worktrees-nerede-kaldik-60b0da/09d35bec-4acb-47c1-8594-85d303f66f97/scratchpad/tilde_class.json","w",encoding="utf-8"),ensure_ascii=False)
c=collections.Counter(v[1] for v in OUT.values());print(dict(c),len(OUT))
# çözülemeyenler: oy ve ad
agg=collections.defaultdict(lambda:[0,0])
for p,pre,ad,g,k,fm in UN:
    if fm=='ho2017':agg[(p,pre,ad)][0]+=g;agg[(p,pre,ad)][1]=max(agg[(p,pre,ad)][1],k)
tot=sum(v[0] for v in agg.values())
print('çözülemeyen ho2017 oy',tot)
for (p,pre,ad),(g,k) in sorted(agg.items(),key=lambda x:-x[1][0])[:40]:print(p,pre[-3:],ad,g,k)
