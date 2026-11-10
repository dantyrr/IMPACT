"""S5's institution links with one name per institution -> data/analysis/institutions_v12.pkl.

The same count as institutions.py, with names merged before papers are counted, so a paper listing a university and its hospitals is one link for that university.

Usage: python 10-31-26/scripts/v11_links.py   (from the IMPACT folder)
"""
import csv
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import institutions as I  # noqa: E402

src = inspect.getsource(I.main)
new = src.replace('''    pp, kk = [], []
    for p, a in zip(pa.tolist(), aa.tolist()):
        for k in aff_keys.get(a, ()):
            pp.append(p); kk.append(k)
''', '''    merges = {r["name"]: r["merged_into"] for r in csv.DictReader(open(os.path.join(DATA, "institution_merge_v12.csv")))}
    for child, parent in merges.items():
        if child in key_ids and parent not in key_ids:
            key_ids[parent] = len(key_ids)
            names[parent][parent] += 1
    remap = {i: key_ids[merges[k]] if k in merges and k in key_ids and merges[k] in key_ids else i for k, i in list(key_ids.items())}
    pp, kk = [], []
    for p, a in zip(pa.tolist(), aa.tolist()):
        for k in aff_keys.get(a, ()):
            pp.append(p); kk.append(remap[k])
''').replace('"institutions.pkl"', '"institutions_v12.pkl"')
assert new.count("remap[k]") == 1 and "institutions_v12.pkl" in new
I.csv = csv
exec(new, I.__dict__)

if __name__ == "__main__":
    I.main()
