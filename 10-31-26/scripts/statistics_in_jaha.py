import sys,os,sqlite3
sys.argv=['x']
sys.path.insert(0,'10-31-26/scripts')
from type_effect import *
c=sqlite3.connect('file:data/impact.db?mode=ro',uri=True)
slug=c.execute("select slug from journals where abbreviation like 'J Am Heart%'").fetchone()[0]
st=stats_papers()
C_=load('circulation'); J_=load(slug); E_=load('european-heart-journal'); A_=load('journal-of-the-american-college-of-cardiology')
end=settled_month(C_)
by=lambda d:{p['month']:p for p in d['timeseries']}
Cm,Jm,Em,Am=by(C_),by(J_),by(E_),by(A_)
def moved(m):
    p,q=Cm[m],Jm.get(m); n,cit=in_window(st,m)
    pc=sum(p['by_type'][t]['papers'] for t in CITABLE); cc=sum(p['by_type'][t]['citations'] for t in CITABLE)
    r=dict(circ=cc/pc,circ_after=(cc-cit)/(pc-n),n=n,cit=cit,pc=pc)
    if q and q.get('papers',0)>0:
        pj=sum(q['by_type'][t]['papers'] for t in CITABLE); cj=sum(q['by_type'][t]['citations'] for t in CITABLE)
        if pj: r.update(jaha=cj/pj,jaha_after=(cj+cit)/(pj+n),pj=pj)
    return r
for m in ['2013-12','2015-12','2017-12','2019-12','2021-12','2023-12','2024-12',end]:
    r=moved(m); print(m,{k:(round(v,2) if isinstance(v,float) else v) for k,v in r.items()},'EHJ',round(rate(Em[m],CITABLE),2),'JACC',round(rate(Am[m],CITABLE),2))
ms=[m for m in sorted(Cm) if '2006-01'<=m<=end and Cm[m].get('papers',0)>0 and m in Em and m in Am]
below=[m for m in ms if moved(m)['circ_after']<max(rate(Em[m],CITABLE),rate(Am[m],CITABLE)) and rate(Cm[m],CITABLE)>=max(rate(Em[m],CITABLE),rate(Am[m],CITABLE))]
print(len(ms),'months; lead lost in',len(below),below[:3],below[-3:])
lead=[m for m in ms if rate(Cm[m],CITABLE)>=max(rate(Em[m],CITABLE),rate(Am[m],CITABLE))]
print('Circ leads',len(lead),lead[:1],lead[-1:])
pct=[(moved(m)['circ']-moved(m)['circ_after'])/moved(m)['circ'] for m in ms]; print('mean drop',sum(pct)/len(pct),max(pct))
pj=[(moved(m)['jaha_after']-moved(m)['jaha'])/moved(m)['jaha'] for m in ms if 'jaha' in moved(m)]; print('JAHA mean rise',sum(pj)/len(pj),max(pj))
