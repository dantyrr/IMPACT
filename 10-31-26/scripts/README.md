# Analysis code for "Quantifying Biomedical Publishing and Citation Metrics"

These scripts build every figure, figure legend and the Data S1 workbook of the paper, from the IMPACT databases that the rest of this repository builds. The paper's Supplementary Materials (Materials and Methods) describe each analysis.

## What is here and what is not

- Here: the Python scripts, run in the versions the figures went through (`v2_*` to `v16_*`), and the checks in `test_v2.py`.
- Not here: the databases (about 89 GB) and the figure files. The data behind every panel is in Data S1, published with the paper.
- The Retraction Watch Database is not redistributed. It was created by the Center for Scientific Integrity and is made openly available by Crossref: https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/. The scripts read it from `data/retraction_watch/retraction_watch.csv`.

## Inputs

Build these with the pipeline in `scripts/` and `src/pipeline/` (see the repository README and METHODOLOGY.md):

- `data/impact.db`: journals, papers, document classes and citations.
- `data/pubmed_full.db`: every PubMed record with authors and affiliations.
- `data/retraction_watch/retraction_watch.csv`: the Retraction Watch Database (download from the link above).

The scripts write intermediate files to `data/analysis/` and figures to `10-31-26/vN/`, with the plotted values for each panel as CSV files in `10-31-26/vN/data/`.

## Where the scripts look for files

The scripts were run with the repository at `/Users/dtyrrell/Projects/IMPACT`, and that path is written into them. To run them elsewhere, replace it with your own path, for example:

```
grep -rl /Users/dtyrrell/Projects/IMPACT 10-31-26/scripts | xargs sed -i '' "s#/Users/dtyrrell/Projects/IMPACT#$PWD#g"   # macOS
grep -rl /Users/dtyrrell/Projects/IMPACT 10-31-26/scripts | xargs sed -i "s#/Users/dtyrrell/Projects/IMPACT#$PWD#g"      # Linux
```

Run every script from the repository root, for example `python 10-31-26/scripts/v16_figs.py setup`.

## Order

1. Analysis files, once: `build_matrix.py`, `author_counts.py`, `institutions.py`, `citing_geography.py`, `publishers_retractions.py`, `citation_ages.py`, `citation_ages_long.py`, `annual_reports.py`.
2. Figure versions in order, `v2` to `v16`. Each version starts from the previous version's figures and redraws only what changed; each script's opening docstring lists its jobs and their order. `v2` starts with `v2_panels.py`, `v2_pairs.py` and `v2_inst_country.py`; `v13` to `v16` start with `vN_figs.py setup`.
3. The final figures are in `10-31-26/v16/`: `python 10-31-26/scripts/v16_figs.py setup`, then `s1`, then `timing`; legends with `v16_legends.py`.
4. Data S1: `python 10-31-26/scripts/v16_data_s1_extra.py pairs fig2f`, then `python 10-31-26/scripts/v16_data_s1.py "Data S1.xlsx"`.

Checks: `python -m pytest 10-31-26/scripts/test_v2.py -q`.

Random draws and shuffles use fixed seeds. Run with Python 3.13, NumPy 2.4, SciPy 1.17, Matplotlib 3.10, pandas 3.0 and openpyxl 3.1.

## Licence

MIT, as for the rest of the repository (see `LICENSE`).
