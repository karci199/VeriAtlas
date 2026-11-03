import csv,json,collections,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8")
K=json.load(open("C:/veri/.claude/worktrees/istanbul-devam-e9426f/scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json",encoding="utf-8"))
names={}
for f in glob.glob("C:/veri/src/veriatlas/data/areas*.csv"):
    for r in csv.reader(open(f,encoding="utf-8")):
        if len(r)>2 and r[0].startswith('TR-') and r[0].count('-')==1:names[r[0]]=r[2]
up=lambda s:s.replace('i','İ').replace('ı','I').upper()
isk=lambda s:s in('İlçe Merkezi','Kentsel Belde','İl Merkezi')
rows=[];TOT={'kent':[0,0,0],'kır':[0,0,0]};ILCE=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id']:r for r in csv.DictReader(open(f,encoding="utf-8"))}
    def key(a):
        if a in K:return a
        d,cc=a.rsplit('-',1)
        if cc.isdigit() and f"{d}-{int(cc)+2000000}" in K:return f"{d}-{int(cc)+2000000}"
    if sum(1 for a in R if key(a))<0.97*len(R):continue
    il=up(names.get(f'TR-{p}',p))
    A={'kent':[0,0,0],'kır':[0,0,0]};AD=collections.defaultdict(lambda:{'kent':[0,0,0],'kır':[0,0,0]})
    dd=sorted({a.rsplit('-',1)[0] for a in R})
    for did in dd:
        fp=f"C:/veri-ham/endeksa/fellowcountryman/{did}.json";dp=f"C:/veri-ham/endeksa/demography/{did}.json"
        if not(os.path.exists(fp) and os.path.exists(dp)):continue
        F=json.load(open(fp,encoding="utf-8"));D=json.load(open(dp,encoding="utf-8"))
        for a,r in R.items():
            if not a.startswith(did+'-'):continue
            k=key(a)
            if not k:continue
            code=a.rsplit('-',1)[1];g='kent' if isk(K[k]['s']) else 'kır'
            fc=F.get(code) or F.get(str(int(code)+2000000)) or {}
            tot=((D.get(code) or D.get(str(int(code)+2000000)) or {}).get('demography') or {}).get('PopulationTotal') or 0
            lst=fc.get('fellowcountryman') or []
            if not tot or not lst:continue
            yerli=sum(x['CountOf'] for x in lst if x['CitizenCity']==il);top=sum(x['CountOf'] for x in lst)
            for X in(A[g],AD[r['district']][g]):X[0]+=yerli;X[1]+=tot;X[2]+=top
    if not A['kent'][1] or not A['kır'][1]:continue
    for g in A:
        for i in range(3):TOT[g][i]+=A[g][i]
    rows.append((names.get(f'TR-{p}',p),100*A['kent'][0]/A['kent'][1],100*A['kır'][0]/A['kır'][1],A['kent'][1],A['kır'][1],100*A['kent'][2]/A['kent'][1]))
    for d,v in AD.items():
        if v['kent'][1]>=5000 and v['kır'][1]>=1000:ILCE.append((names.get(f'TR-{p}',p),d,100*v['kent'][0]/v['kent'][1],100*v['kır'][0]/v['kır'][1],v['kent'][1],v['kır'][1]))
print("il|kent yerli % (il içi kayıtlı)|kır yerli %|fark (kır−kent)|kent nüfus|kır nüfus|top10 kapsama kent %")
for r in sorted(rows,key=lambda r:r[1]):print(f"{r[0]}|{r[1]:.2f}|{r[2]:.2f}|{r[2]-r[1]:+.2f}|{r[3]}|{r[4]}|{r[5]:.1f}")
print(f"TOPLAM|{100*TOT['kent'][0]/TOT['kent'][1]:.2f}|{100*TOT['kır'][0]/TOT['kır'][1]:.2f}")
json.dump(ILCE,open("C:/Users/katan/AppData/Local/Temp/claude/C--veri--claude-worktrees-nerede-kaldik-60b0da/09d35bec-4acb-47c1-8594-85d303f66f97/scratchpad/yerlilik_ilce.json","w",encoding="utf-8"),ensure_ascii=False)
