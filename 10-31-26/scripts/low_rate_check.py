"""What a rate under 1 means for the Zhonghua journals, and whether their citations are undercounted.

Run from the IMPACT root: python 10-31-26/scripts/low_rate_check.py
"""
import sqlite3
from collections import Counter

db = sqlite3.connect("file:data/impact.db?mode=ro", uri=True)
CIT = "('research','review','case_report','guideline')"
names = ["Zhonghua xin xue guan bing za zhi", "Zhonghua yi xue za zhi", "Zhonghua er ke za zhi = Chinese journal of pediatrics",
         "Circulation", "European heart journal", "Arquivos brasileiros de cardiologia"]
lo, hi = 2022 * 12 + 12, 2024 * 12 + 11      # items, Dec 2022 - Nov 2024
clo, chi = 2024 * 12 + 12, 2025 * 12 + 11    # citations, Dec 2024 - Nov 2025
print("journal | items | window cites | rate | % items with 0 | max | % items citing anything | mean refs out | 2022 items: cites/paper in 2 yrs after | % citers in same-language group")
for n in names:
    jid = db.execute("select id from journals where name=?", (n,)).fetchone()[0]
    items = [r[0] for r in db.execute(
        f"select pmid from papers where journal_id=? and doc_class in {CIT} and pub_year*12+pub_month between ? and ?", (jid, lo, hi))]
    q = ",".join(map(str, items))
    per = Counter(dict(db.execute(
        f"select cited_pmid,count(*) from citations where cited_pmid in ({q}) and citing_class is null "
        f"and citing_year*12+citing_month between ? and ? group by 1", (clo, chi)).fetchall()))
    tot = sum(per.values())
    zero = sum(1 for p in items if per[p] == 0)
    out = dict(db.execute(f"select citing_pmid,count(*) from citations where citing_pmid in ({q}) group by 1").fetchall())
    # 2022 papers, followed through 2023 and 2024
    p22 = [r[0] for r in db.execute(f"select pmid from papers where journal_id=? and doc_class in {CIT} and pub_year=2022", (jid,))]
    q22 = ",".join(map(str, p22))
    c22 = db.execute(f"select count(*) from citations where cited_pmid in ({q22}) and citing_class is null and +citing_year in (2023,2024)").fetchone()[0]
    # who cites them
    who = Counter(dict(db.execute(
        f"select j.name,count(*) from citations c join papers p on p.pmid=c.citing_pmid join journals j on j.id=p.journal_id "
        f"where c.cited_pmid in ({q}) and c.citing_class is null group by 1").fetchall()))
    zh = sum(v for k, v in who.items() if k.startswith("Zhonghua"))
    print(flush=True, end=""); print(f"{n[:34]} | {len(items)} | {tot} | {tot/len(items):.2f} | {100*zero/len(items):.0f}% | {max(per.values())} | "
          f"{100*len(out)/len(items):.0f}% | {sum(out.values())/len(items):.1f} | {c22/len(p22):.2f} (n={len(p22)}) | Zhonghua {100*zh/max(sum(who.values()),1):.0f}%")

# reference lists: every Zhonghua journal, 2023 citable items
ids = [r[0] for r in db.execute("select id from journals where name like 'Zhonghua%'")]
n = hit = 0
for j in ids:
    r = db.execute(f"""select count(*), coalesce(sum(exists(select 1 from citations c where c.citing_pmid=p.pmid)),0)
        from papers p where p.journal_id=? and p.pub_year=2023 and p.doc_class in {CIT}""", (j,)).fetchone()
    n += r[0]; hit += r[1]
print(len(ids), "Zhonghua journals; 2023 items", n, f"with any reference recorded {100*hit/n:.1f}%")
