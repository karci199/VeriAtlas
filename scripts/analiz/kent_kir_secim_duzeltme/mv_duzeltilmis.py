import json,csv,glob,os,collections,sys,re
sys.stdout.reconfigure(encoding="utf-8")
exec(open("C:/Users/katan/AppData/Local/Temp/claude/C--veri--claude-worktrees-nerede-kaldik-60b0da/09d35bec-4acb-47c1-8594-85d303f66f97/scratchpad/duzeltilmis.py",encoding="utf-8").read().split("res={}")[0])
P5={'AKP':['AK PARTİ'],'MHP':['MHP'],'CHP':['CHP'],'İYİ':['İYİ PARTİ'],'YSP/HDP':['YEŞİL SOL PARTİ','HDP']}
G={e:{g:{y:collections.Counter() for y in('mv2018','mv2023')} for g in('kent','kır')} for e in(False,True)}
for p in plates:
    if p in('19','65'):continue
    for yr in('mv2018','mv2023'):
        T=json.load(open(f"C:/veri/public/tiles/secim-{yr}-mahalle-TR-{p}.json",encoding="utf-8"))
        for a,v in T.items():
            if v['o']>=v['k']+20:continue
            for e in(False,True):
                g=cls(p,a,v,e);X=G[e][g][yr]
                X['k']+=v['k'];X['o']+=v['o'];X['g']+=v['g']
                for q,n in v['v'].items():
                    hit=False
                    for kk,L in P5.items():
                        if q in L:X[kk]+=n;hit=True
                    if not hit:X['ittif' if (q.endswith('İTTİFAKI') or q=='MİLLET') else 'diğer']+=n
print("KENT/KIR: önce → sonra (2018 | 2023 | fark), mutlak kişi")
for g in('kent','kır'):
    print("\n"+g.upper())
    for k,lab in(('k','kayıtlı seçmen'),('o','kullanılan oy'),('g','geçerli oy'),('AKP','AKP'),('MHP','MHP'),('CHP','CHP'),('İYİ','İYİ'),('YSP/HDP','YSP/HDP'),('diğer','diğer partiler')):
        row=[]
        for e in(False,True):
            a,b=G[e][g]['mv2018'][k],G[e][g]['mv2023'][k];row.append(f"{a:,}|{b:,}|{b-a:+,}")
        print(f"{lab}|{row[0]} ⇒ {row[1]}")
print("\nPAYLAR (geçerli oy içinde %), önce → sonra")
for g in('kent','kır'):
    for k in('AKP','MHP','CHP','İYİ','YSP/HDP','diğer'):
        r=[]
        for e in(False,True):
            a=100*G[e][g]['mv2018'][k]/G[e][g]['mv2018']['g'];b=100*G[e][g]['mv2023'][k]/G[e][g]['mv2023']['g'];r.append(f"{a:.2f}→{b:.2f} ({b-a:+.2f})")
        print(f"{g} {k}|{r[0]} ⇒ {r[1]}")
for e in(False,True):
    for g in('kent','kır'):
        for y in('mv2018','mv2023'):
            X=G[e][g][y];print(e,g,y,'katılım %.2f'%(100*X['o']/X['k']),'geçersiz %.2f'%(100*(X['o']-X['g'])/X['o']))
