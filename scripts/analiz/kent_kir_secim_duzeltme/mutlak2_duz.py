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
def new():return collections.Counter()
G={g:{y:new() for y in('mv2018','mv2023')} for g in('kent','kır')}
IL=[]
for p in sorted({a.split('-')[1] for a in K}):
    f=f"C:/veri-ham/analiz/kent_kir/{p}/kent_{p}_ikili.csv"
    if not os.path.exists(f):continue
    R={r['area_id'] for r in csv.DictReader(open(f,encoding="utf-8"))}
    mk=sum(1 for a in R if a in K or (a.rsplit('-',1)[1].isdigit() and f"{a.rsplit('-',1)[0]}-{int(a.rsplit('-',1)[1])+2000000}" in K))
    if mk<0.97*len(R) or p in('19','65'):continue
    L={g:{y:new() for y in('mv2018','mv2023')} for g in('kent','kır')}
    for yr in('mv2018','mv2023'):
        M=json.load(open(f"C:/veri/public/tiles/secim-{yr}-mahalle-TR-{p}.json",encoding="utf-8"))
        for a,m in M.items():
            if m['o']>=m['k']+20:continue
            g=cls(p,a,m,True)
            for X in(L[g][yr],G[g][yr]):
                X['k']+=m['k'];X['o']+=m['o'];X['g']+=m['g']
                for q,v in m['v'].items():
                    hit=False
                    for kk,Ls in P5.items():
                        if q in Ls:X[kk]+=v;hit=True
                    if not hit and not (q.endswith('İTTİFAKI') or q=='MİLLET'):X['diğer']+=v
                    elif not hit:X['ittif']+=v
    IL.append((names.get(f'TR-{p}',p),L))
def ab(c):
    k, o, g = c['k'], c['o'], c['g']
    return {'kayıtlı seçmen': k, 'kullanılan oy': o, 'oy kullanmayan': k - o, 'geçersiz oy': o - g,
            'geçerli oy': g, 'AKP': c['AKP'], 'MHP': c['MHP'], 'CHP': c['CHP'], 'İYİ': c['İYİ'],
            'YSP/HDP': c['YSP/HDP'], 'ittifak pusulası': c['ittif'], 'diğer partiler': c['diğer']}

NL = chr(10)
for gname in ('kent', 'kır'):
    a, b = ab(G[gname]['mv2018']), ab(G[gname]['mv2023'])
    print(NL + gname.upper() + ": 2018|2023|fark (kişi)|fark %")
    for k in a:
        print(f"{k}|{a[k]:,}|{b[k]:,}|{b[k]-a[k]:+,}|{100*(b[k]/a[k]-1):+.1f}")

ks = ['kayıtlı seçmen', 'kullanılan oy', 'oy kullanmayan', 'geçersiz oy', 'AKP', 'MHP', 'CHP', 'İYİ', 'YSP/HDP', 'diğer partiler']
print(NL + "İL KENT (kişi, 2018→2023 farkı): " + "|".join(ks))
tot = collections.Counter()
for nm, L in sorted(IL, key=lambda r: -ab(r[1]['kent']['mv2023'])['kayıtlı seçmen']):
    a, b = ab(L['kent']['mv2018']), ab(L['kent']['mv2023'])
    print(nm + "|" + "|".join(f"{b[k]-a[k]:+,}" for k in ks))
    for k in ks:
        tot[k] += b[k] - a[k]
print("TOPLAM|" + "|".join(f"{tot[k]:+,}" for k in ks))
