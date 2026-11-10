"""2024 JIF-style citations (to 2022-23 citable items) by citing journal, for every journal."""
import sqlite3,numpy as np,csv,sys
S=sys.argv[1]
d=np.load('../data/analysis/cites.npz')
pmid,jid,py,dc=d['pmid'],d['journal_id'],d['pub_year'],d['doc_class']
row=np.full(pmid.max()+1,-1,np.int32); row[pmid]=np.arange(len(pmid),dtype=np.int32)
c=sqlite3.connect('file:../data/impact.db?mode=ro',uri=True)
cur=c.execute("select cited_pmid,citing_pmid from citations where citing_class is null and citing_year=2024")
NJ=int(jid.max())+2
keys=[];pk=[]
n=0
while True:
    ch=cur.fetchmany(4000000)
    if not ch: break
    a=np.array(ch,np.int64); n+=len(a)
    a=a[(a[:,0]<len(row))]
    r=row[a[:,0]]; ok=r>=0; a=a[ok]; r=r[ok]
    ok=((py[r]==2022)|(py[r]==2023))&(dc[r]<=3); a=a[ok]; r=r[ok]
    s=np.where(a[:,1]<len(row),row[np.minimum(a[:,1],len(row)-1)],-1)
    cj=np.where(s>=0,jid[np.maximum(s,0)],NJ-1).astype(np.int64)
    u,k=np.unique(jid[r].astype(np.int64)*NJ+cj,return_counts=True); keys.append((u,k))
    u,k=np.unique(r.astype(np.int64)*NJ+cj,return_counts=True); pk.append((u,k))
    print(n,flush=True)
def merge(l):
    u=np.concatenate([x[0] for x in l]);k=np.concatenate([x[1] for x in l])
    uu,inv=np.unique(u,return_inverse=True); return uu,np.bincount(inv,k).astype(np.int64)
u,k=merge(keys); pu,pkk=merge(pk)
np.savez(S+'/screen.npz',u=u,k=k,pu=pu,pk=pkk,NJ=NJ)
