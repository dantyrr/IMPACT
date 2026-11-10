import numpy as np,sqlite3,sys,csv
S=sys.argv[1]
z=np.load(S+'/screen.npz'); u,k,pu,pk,NJ=z['u'],z['k'],z['pu'],z['pk'],int(z['NJ'])
c=sqlite3.connect('file:data/impact.db?mode=ro',uri=True,timeout=60)
ab={r[0]:r[1] or r[2] for r in c.execute('select id,abbreviation,name from journals')}
d=np.load('data/analysis/cites.npz'); pmid,jid,py,dc=d['pmid'],d['journal_id'],d['pub_year'],d['doc_class']
m=((py==2022)|(py==2023))&(dc<=3)
items=np.bincount(jid[m],minlength=NJ)
cited=u//NJ; citing=u%NJ
tot=np.bincount(cited,weights=k,minlength=NJ)
self_=np.zeros(NJ); s=cited==citing; self_[cited[s]]=k[s]
unk=citing==NJ-1
print('all',k.sum(),'untracked share',k[unk].sum()/k.sum())
out_by=np.bincount(citing[~unk],weights=k[~unk],minlength=NJ); share=out_by/out_by.sum()   # citing journal's share of all citations
ext=(~s)&(~unk)
exp=share[citing]*tot[cited]
ex=k-exp
rows=[]
order=np.lexsort((-k[ext],cited[ext])); ce,ci,ke,ee=cited[ext][order],citing[ext][order],k[ext][order],ex[ext][order]
first=np.r_[True,ce[1:]!=ce[:-1]]
for a,b,kk,e in zip(ce[first],ci[first],ke[first],ee[first]):
    if items[a]>=100 and tot[a]>=500: rows.append((a,b,kk,kk/tot[a],e/tot[a]))
rows.sort(key=lambda r:-r[3])
print('\n## top single external citing journal share, 100+ items, 500+ cites, n=',len(rows))
for r in rows[:22]:
    a=r[0]; print(f"{ab[a][:32]:32} items {items[a]:5} rate {tot[a]/items[a]:6.2f} -> {(tot[a]-r[2])/items[a]:6.2f} self {self_[a]/tot[a]:4.0%} | {ab[r[1]][:30]:30} {r[2]:6} {r[3]:.0%}")
print('\n## highest self-citation, same filter')
ids=[a for a in range(NJ) if items[a]>=100 and tot[a]>=500]
for a in sorted(ids,key=lambda a:-self_[a]/tot[a])[:12]: print(f"{ab[a][:36]:36} items {items[a]:5} rate {tot[a]/items[a]:6.2f} self {self_[a]/tot[a]:.0%}")
# paper x citing journal
row=pu//NJ; cj=pu%NJ
ok=(cj!=NJ-1)&(jid[row]!=cj)
ptot=np.bincount(np.unique(row,return_inverse=True)[1],weights=pk)
ur=np.unique(row); pt=dict(zip(ur.tolist(),ptot.tolist()))
r2,c2,k2=row[ok],cj[ok],pk[ok]
o=np.argsort(-k2)[:4000]
res=[]
for i in o:
    j=int(jid[r2[i]]); t=pt[int(r2[i])]
    if items[j]>=100 and tot[j]>=500 and t>=30: res.append((int(pmid[r2[i]]),j,int(c2[i]),int(k2[i]),t,k2[i]/t,k2[i]/tot[j]))
print('\n## single paper x single citing journal, as share of cited journal 2024 citations')
res.sort(key=lambda r:-r[6])
seen=set()
for r in res[:40]:
    t=c.execute('select title from papers where pmid=?',(r[0],)).fetchone()[0]
    print(f"{ab[r[1]][:24]:24} {ab[r[2]][:26]:26} {r[3]:5} of paper's {int(r[4]):5} ({r[5]:.0%}), {r[6]:.0%} of journal | {t[:58]}")
print('\n## papers where one journal gives 50%+ of citations, 100+ cites in 2024')
res2=[r for r in res if r[5]>=.5 and r[4]>=100]; res2.sort(key=lambda r:-r[3])
for r in res2[:25]:
    t=c.execute('select title from papers where pmid=?',(r[0],)).fetchone()[0]
    print(f"{ab[r[1]][:24]:24} <- {ab[r[2]][:26]:26} {r[3]:5}/{int(r[4]):5} ({r[5]:.0%}) | {t[:62]}")
ijs=[j for j,a in ab.items() if a=='Int J Surg'][0]
sis=[j for j,a in ab.items() if a and a in('Int J Surg Case Rep','Ann Med Surg (Lond)')]
print('\nIJS',ijs,'items',items[ijs],'tot',tot[ijs],'rate',tot[ijs]/items[ijs])
for b in np.argsort(-np.where(cited==ijs,k,0))[:8]: print(ab.get(int(citing[b]),'untracked'),k[b],round(k[b]/tot[ijs],3))
print(sis,[ab[x] for x in sis])
