import re,sys
D="C:/veri-ham/analiz/kent_kir/_secim_duzeltme/"
SP="C:/Users/katan/AppData/Local/Temp/claude/C--veri--claude-worktrees-nerede-kaldik-60b0da/09d35bec-4acb-47c1-8594-85d303f66f97/scratchpad/"
src=open(D+"duzeltilmis.py",encoding="utf-8").read().split("res={}")[0].replace('SP="'+SP+'"','SP="'+D+'"')
open(D+"ortak.py","w",encoding="utf-8").write(src)
pat=re.compile(r"n=nrm\(a\);\s*g='kent' if \(n and isk\(K\[n\]\['s'\]\)\) else 'kır'|n=nrm\(a\)\n(\s*)g='kent' if \(n and isk\(K\[n\]\['s'\]\)\) else 'kır'")
for f in sys.argv[1:]:
    t=open(SP+f+".py",encoding="utf-8").read()
    var='m8' if f=='iyi_analiz' else 'm'
    t,n=pat.subn(lambda mo:"g=cls(p,a,%s,True)"%var if mo.group(1) is None else "g=cls(p,a,%s,True)"%var,t)
    t=t.replace("C:/veri/public/tiles/secim-ho2017","C:/veri/.claude/worktrees/kent-kir-secim-analizi-7b3b2f/public/tiles/secim-ho2017")
    t=t.replace("sys.stdout.reconfigure(encoding=\"utf-8\")","sys.stdout.reconfigure(encoding=\"utf-8\")\nexec(open(\"%sortak.py\",encoding=\"utf-8\").read())"%D,1)
    open(D+f+"_duz.py","w",encoding="utf-8").write(t);print(f,n)
