"""Election results of the Istanbul urban-town (kentsel belde) clusters, 2015 Kasim vs 2023 general election.

Cluster membership comes from the user decisions of the Istanbul kent/kir review (kullanici_karar.json).
Old 2015 neighbourhood names that no longer exist are mapped through ALIAS (see docs/secim-eslesmeyen-34.md).
Institutional ballot boxes (votes >= registered + 20) are dropped, which removes Semizkumlar (prison) whole.
"""
import json,sys,collections,csv
sys.stdout.reconfigure(encoding='utf-8')
D='scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json'
d=json.load(open(D,encoding='utf-8')); cls={k:v['s'] for k,v in d.items() if k.startswith('TR-34')}
rows=list(csv.DictReader(open('C:/veri-ham/analiz/kent_kir/34/kent_34_mahalle.csv',encoding='utf-8')))
def fold(t):
    t=t.replace("İ","i").replace("I","ı").lower()
    for a,b in zip("ıöüçşğâîû","ioucsgaiu"): t=t.replace(a,b)
    return "".join(c for c in t if c.isalnum())
byd=collections.defaultdict(list); dist_of={}
for r in rows:
    p=r['area_id'].rsplit('-',1)[0]; byd[p].append((fold(r['name']),r['area_id'])); dist_of[p]=r['district']
unif={p:{cls[a] for _,a in v} for p,v in byd.items()}
eyup=[p for p,n in dist_of.items() if n=='Eyüpsultan'][0]
nid={(r['district'],r['name'].strip()):r['area_id'] for r in rows}
CL={'Arnavutköy Deliklikaya':[('Arnavutköy','Deliklikaya')],'Arnavutköy Ömerli':[('Arnavutköy','Ömerli')],'Arnavutköy Hastane+Hadımköy':[('Arnavutköy','Hastane'),('Arnavutköy','Hadımköy')],
'Beykoz Elmalı+Örnekköy+Zerzavatçı+M.Şevketpaşa':[('Beykoz',x) for x in('Elmalı','Örnekköy','Zerzavatçı','Mahmutşevketpaşa')],
'Beykoz Baklacı+Çiftlik+Y.Selim+Fatih+Çengeldere':[('Beykoz',x) for x in('Baklacı','Çiftlik','Yavuz Selim','Fatih','Çengeldere')],
'Silivri Selimpaşa':[('Silivri','Selimpaşa')],'Silivri Gümüşyaka+2 Çanta':[('Silivri',x) for x in('Gümüşyaka','Çanta Sancaktepe','Çanta Balaban')],
'Silivri Semizkumlar':[('Silivri','Semizkumlar')],'Silivri Değirmenköy':[('Silivri','Değirmenköy Fevzipaşa'),('Silivri','Değirmenköy İsmetpaşa')],
'Sarıyer Uskumruköy+Zekeriyaköy':[('Sarıyer','Uskumruköy'),('Sarıyer','Zekeriyaköy')],'Sarıyer Bahçeköy (3)':[('Sarıyer','Bahçeköy Yeni'),('Sarıyer','Bahçeköy Kemer'),('Sarıyer','Bahçeköy Merkez')],
'Sarıyer Rumelikavağı':[('Sarıyer','Rumelikavağı')],'Sarıyer Kumköy':[('Sarıyer','Kumköy')],
'Çekmeköy Ömerli':[('Çekmeköy','Ömerli')],'Çekmeköy Reşadiye':[('Çekmeköy','Reşadiye')],
'Eyüpsultan Pirinççi':[('Eyüpsultan','Pirinççi')],'Eyüpsultan Göktürk Merkez':[('Eyüpsultan','Göktürk Merkez')],'Eyüpsultan Mithatpaşa+Mimar Sinan':[('Eyüpsultan','Mithatpaşa'),('Eyüpsultan','Mimar Sinan')],
'Tuzla Şifa+Mimar Sinan':[('Tuzla','Şifa'),('Tuzla','Mimar Sinan')],'Tuzla Aydıntepe':[('Tuzla','Aydıntepe')],'Tuzla Orhanlı+Mescit':[('Tuzla','Orhanlı'),('Tuzla','Mescit')],
'Tuzla Orta+Tepeören+Anadolu+Fatih':[('Tuzla','Orta'),('Tuzla','Tepeören'),('Tuzla','Anadolu'),('Tuzla','Fatih')],'Tuzla Akfırat':[('Tuzla','Akfırat')],'Tuzla Aydınlı':[('Tuzla','Aydınlı')],
'Büyükçekmece Kumburgaz kıyı (5)':[('Büyükçekmece',x) for x in('Kumburgaz','Bahçelievler','Yenimahalle','Kamiloba','Celaliye')],'Büyükçekmece Alkent+Karaağaç':[('Büyükçekmece','Alkent 2000'),('Büyükçekmece','Karaağaç')],
'Başakşehir Bahçeşehir 1+2. Kısım':[('Başakşehir','Bahçeşehir 1. Kısım'),('Başakşehir','Bahçeşehir 2. Kısım')],
'Bakırköy Florya':[('Bakırköy','Basınköy'),('Bakırköy','Şenlikköy')],'Sultangazi Yayla':[('Sultangazi','Yayla')],'Sultangazi Habibler+Eski Habipler':[('Sultangazi','Habibler'),('Sultangazi','Eski Habipler')],
'Esenyurt Esenkent kümesi (5)':[('Esenyurt',x) for x in('Akçaburgaz','Orhan Gazi','Esenkent','Koza','Aşık Veysel')],'Avcılar Tahtakale':[('Avcılar','Tahtakale')]}
a2c={}
miss=[]
for c,l in CL.items():
    for x in l:
        a=nid.get(x)
        if not a: miss.append(x)
        else: a2c[a]=c
print('küme',len(CL),'birim',len(a2c),'bulunamayan',miss)
# kentsel belde units not in any cluster
print('kümesiz KB:',[ (r['district'],r['name']) for r in rows if cls[r['area_id']]=='Kentsel Belde' and r['area_id'] not in a2c and 'osb' not in r['name'].lower() and 'Sb' not in r['name']])
ALIAS={('TR-34-033','habipler'):('Sultangazi','Habibler'),('TR-34-034','bozkoca'):('Şile','Bozgoca'),('TR-34-002','mfevzicakmak'):('Arnavutköy','Mareşal Fevzi Çakmak'),
('TR-34-x1325','eyupmerkez'):('Eyüpsultan','Merkez'),('TR-34-030','merkez'):('Sarıyer','Sarıyer Merkez'),('TR-34-030','kemer'):('Sarıyer','Bahçeköy Kemer'),
('TR-34-031','sancaktepe'):('Silivri','Çanta Sancaktepe'),('TR-34-031','balaban'):('Silivri','Çanta Balaban'),('TR-34-031','fevzipasa'):('Silivri','Değirmenköy Fevzipaşa'),
('TR-34-031','ismetpasa'):('Silivri','Değirmenköy İsmetpaşa'),('TR-34-031','kavakli'):('Silivri','Kavaklı İstiklal'),('TR-34-031','hurriyet'):('Silivri','Kavaklı Hürriyet'),('TR-34-031','sinekli'):('Silivri','Büyük Sinekli')}
def party(p):
    u=p.upper()
    for k,v in (('AK PART','AKP'),('CHP','CHP'),('MHP','MHP'),('İYİ','İYİ'),('HDP','Sol/HDP'),('YEŞİL SOL','Sol/HDP')):
        if u.startswith(k): return v
    return 'diğer'
res={}; left_all={}
for e in('mv2015k','mv2023'):
    t=json.load(open(f'C:/veri/public/tiles/secim-{e}-mahalle-TR-34.json',encoding='utf-8'))
    R=collections.defaultdict(lambda:collections.defaultdict(float)); left=[]; tot=0
    for key,v in t.items():
        if v['o']>=v['k']+20: continue
        tot+=sum(v['v'].values()); a=None
        if key in cls: a=key
        elif '~' in key and (key.split('~')[0],key.split('~')[1]) in ALIAS: a=nid[ALIAS[(key.split('~')[0],key.split('~')[1])]]
        else:
            did=key.split('~')[0] if '~' in key else key.rsplit('-',1)[0]
            if did=='TR-34-x1325': did=eyup
            nm=fold(v['ad']); L=byd.get(did,[])
            m=[x for n,x in L if n==nm] or [x for n,x in L if n.startswith(nm) or nm.startswith(n)]
            if len(m)==1: a=m[0]
            elif did in unif and len(unif[did])==1: a=None
            else: left.append((key,v['ad'],int(sum(v['v'].values()))))
        if a in a2c:
            for p,n in v['v'].items(): R[a2c[a]][party(p)]+=n
    res[e]=R; left_all[e]=(left,tot)
print('açıkta kalan',{e:(len(l),int(sum(x[2] for x in l)),f"%{100*sum(x[2] for x in l)/t:.2f}") for e,(l,t) in left_all.items()})
for e,(l,t) in left_all.items():
    if l: print(e,sorted(l,key=lambda x:-x[2])[:20])
out=[]
for c in CL:
    a,b=res['mv2015k'][c],res['mv2023'][c]; sa,sb=sum(a.values()),sum(b.values())
    f=lambda x,s,p:100*x.get(p,0)/s if s else float('nan')
    out.append((c,sa,sb,f(a,sa,'AKP'),f(b,sb,'AKP'),f(a,sa,'CHP'),f(b,sb,'CHP'),f(b,sb,'İYİ'),f(b,sb,'Sol/HDP')))
out.sort(key=lambda r:-r[2])
print('küme|oy2015|oy2023|AKP15|AKP23|CHP15|CHP23|İYİ23|Sol23')
for r in out: print(f"{r[0]}|{int(r[1]):,}|{int(r[2]):,}|{r[3]:.1f}|{r[4]:.1f}|{r[5]:.1f}|{r[6]:.1f}|{r[7]:.1f}|{r[8]:.1f}")
w=csv.writer(open('C:/veri-ham/analiz/kent_kir/34/secim_kentsel_belde_kumeleri_2015k_2023.csv','w',encoding='utf-8-sig',newline=''))
w.writerow(['kume','oy_2015k','oy_2023','akp_2015k','akp_2023','chp_2015k','chp_2023','iyi_2023','sol_2023']); [w.writerow([r[0],int(r[1]),int(r[2])]+[round(x,1) for x in r[3:]]) for r in out]
