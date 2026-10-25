# Citable-rate rebuild runbook

This checklist replaces the "Runbook" section of Task 13 in
`2026-10-24-full-byline-and-citable-rate.md`. It covers rulings R1, R2, R5, R26
and R31 and the final-review items (I2, I4 and the runbook minors in R36).

Rules for the whole run:

- Do the steps in order. Check each one off and write down what it says to
  record. If a stop condition is hit, stop and report to the owner. Do not
  work around it.
- Run everything from the main checkout, `REPO=/Users/dtyrrell/Projects/IMPACT`
  (R1). The worktree has no `data/`, and a lock taken there would not pause
  the launchd weekly job.
- The code work and the final review are finished before step 1 (R5). Steps
  with **OWNER** need an explicit go-ahead from the owner before they run.
- Use `python` = `/Users/dtyrrell/miniconda3/bin/python` (the interpreter the
  weekly wrapper uses).

```bash
REPO=/Users/dtyrrell/Projects/IMPACT
PY=/Users/dtyrrell/miniconda3/bin/python
WT=$REPO/.worktrees/citable-rate
cd "$REPO"; mkdir -p logs
```

---

## 0. Precondition: take the lock, then fast-forward (R1)

The lock has to be held **before** the new code reaches the main checkout.
If it isn't, a Monday weekly run could pick up the new code partway through.
`rebuild_lock.py` only exists on the feature branch so far, so the holder
starts from the worktree and points at the main checkout's lock directory.
That is the same directory the main checkout's default lock path resolves to
after the fast-forward.

```bash
nohup $PY $WT/scripts/rebuild_lock.py hold --lock-dir $REPO/data/.weekly_update.lock \
    > $REPO/logs/rebuild_lock.log 2>&1 &
$PY $WT/scripts/rebuild_lock.py status --lock-dir $REPO/data/.weekly_update.lock; echo "exit $?"
```

- Record: the holder's pid and the `status` line.
- Stop if: `status` does not exit 0. If `hold` reported "lock held by pid …",
  a weekly run is in progress. Wait for it to finish and retry.
- The holder ignores SIGHUP, so closing the terminal is safe. Do **not**
  remove the worktree while it runs, because its script lives there.

Then fast-forward. As of 2026-10-24 the main checkout is on
`fix/pubmed-fetch-resilience`, which is an ancestor of `feat/citable-rate`.
Its only local change is the weekly-written `docs/data/index.json`, which the
branch does not touch.

```bash
git -C $REPO status --short | grep -v '^??'      # expect only docs/data/index.json
git -C $REPO merge --ff-only feat/citable-rate
git -C $REPO log --oneline -1                     # expect the feat/citable-rate tip
$PY scripts/rebuild_lock.py status; echo "exit $?"   # default path, now in $REPO
```

- Record: the commit now checked out.
- Stop if: the merge is not a fast-forward, or `status` (default lock path)
  does not exit 0.

## 1. Disk space

```bash
df -h $REPO/data
```

- Record: free space. The owner has cleared space; about 290 GiB was free at
  the last check.
- Stop if: less than 100 GB is free. Tell the owner before ingesting.

## 2. Sample ingest and size projection

```bash
rm -f data/pubmed_full.sample.db data/pubmed_full.sample.db-wal data/pubmed_full.sample.db-shm
$PY scripts/build_pubmed_full.py --sample 12 2>&1 | tee logs/build_sample.log; echo "exit $?"
```

- Record: in-scope papers sampled, bytes per paper, projected
  `author_tables_gb`, projected `pubmed_gb`.
- Stop if: projected `author_tables_gb` > 20 (the script exits 2).
- Afterwards, either way:
  `rm -f data/pubmed_full.sample.db data/pubmed_full.sample.db-wal data/pubmed_full.sample.db-shm`

## 3. Full ingest (background)

```bash
nohup $PY scripts/build_pubmed_full.py > logs/build_pubmed_full.log 2>&1 &
tail -f logs/build_pubmed_full.log      # "n / total files (name)"
```

The build stops on its own in four cases, and each is safe to re-run because
it resumes at the first unprocessed file:

- exit 1: the lock holder went away. The log says "rebuild lock holder is
  gone". Restart the holder (step 0) and re-run.
- exit 3: free disk dropped below 30 GB.
- exit 4: a file still failed after retries.

**Size check at about 25% of files.** Run this when `n / total` passes a
quarter. The `dbstat` scan is read-only but takes a while on a large file.

```bash
ls -l data/pubmed_full.db*
sqlite3 -readonly data/pubmed_full.db "SELECT m.tbl_name, ROUND(SUM(s.pgsize)/1e9,2) AS gb
  FROM dbstat s JOIN sqlite_master m ON s.name = m.name GROUP BY m.tbl_name ORDER BY gb DESC;"
```

- Record: files done / total, `pubmed_full.db` size, and the summed size of
  `authors + affil_strings + affil_countries + author_affils`. Project each
  linearly with `size × total / done`.
- Stop if: the author tables project over 20 GB. Stop the build with
  `kill <pid>` (finished files are kept) and report to the owner.

Done when the log shows `total / total files`. That was 1,694 on 2026-10-24
(1,334 baseline and 360 update files); use whatever the listing returns.

## 4. Size and country match rate

```bash
ls -l data/pubmed_full.db*
sqlite3 -readonly data/pubmed_full.db "SELECT m.tbl_name, ROUND(SUM(s.pgsize)/1e9,2)
  FROM dbstat s JOIN sqlite_master m ON s.name = m.name GROUP BY m.tbl_name ORDER BY 2 DESC;"
sqlite3 -readonly -header -column data/pubmed_full.db "
  SELECT p.pub_year AS year, COUNT(*) AS first_authors_with_affil,
         SUM(s.country IS NOT NULL) AS with_country,
         ROUND(100.0 * SUM(s.country IS NOT NULL) / COUNT(*), 1) AS pct
  FROM author_affils aa JOIN pubmed p ON p.pmid = aa.pmid
  JOIN affil_strings s ON s.affil_id = aa.affil_id
  WHERE aa.position = 1 AND aa.affil_order = 0
  GROUP BY p.pub_year ORDER BY p.pub_year;"
```

- Record: the final `pubmed_full.db` size, the size of each author table, and
  the country match rate for each year.
- Stop if: the author tables total more than 20 GB, or a recent year's match
  rate is far below its neighbours. Report either to the owner.

## 5. Gate before apply (I4, R2)

The gate runs **before** anything is written to impact.db. Both commands are
read-only.

```bash
$PY scripts/validate_doc_class.py     # -> docs/superpowers/specs/2026-10-24-doc-class-validation.md
$PY scripts/apply_pubmed_full.py --dry-run | tee logs/apply_dry_run.log
```

- Record: from the dry-run, papers that would be updated and the count
  "missing from pubmed_full" (this can include records PubMed deleted
  upstream), plus the class counts. From the report, record the overall
  reclassification, the per-journal research → commentary share, and the
  **research → commentary by signal and pagination** table. That table splits
  each journal's changes into short only / iCite only / both and bare-number
  / range / other pagination, with a short & bare column, for the detector
  journals plus Nature Communications, PLoS ONE, Scientific Reports and Cell
  Reports. Also record the reclassified-title samples and the research-letter
  samples for JAMA, NEJM and Lancet.
- **OWNER CHECKPOINT.** The owner reviews the report and decides:
  - `max_pages`, `use_icite` and `recover_letters` in `src/pipeline/doc_class.py` INFERENCE.
  - Whether a bare-number MedlinePgn should keep counting as one page. A bare
    "5" can be a start page or a genuine one-page highlight, so
    `parse_page_count` stays unchanged unless the owner rules otherwise.

  If the rule changes, make the code change with tests on the branch,
  fast-forward again, and re-run this step.
- Stop if: the owner has not approved the report.

Then apply and checkpoint:

```bash
$PY scripts/apply_pubmed_full.py | tee logs/apply.log; echo "exit $?"
sqlite3 data/impact.db "PRAGMA wal_checkpoint(TRUNCATE);"
ls -l data/impact.db*
```

- Record: the summary line and class counts. Also record that `impact.db-wal`
  is 0 bytes or absent.
- Stop if: the exit code is not 0. Exit 1 means the lock holder went away,
  and the log says so; restart the holder and re-run. Exit 3 means low disk.
  In both cases finished batches are committed.

## 6. Revise the gate-dependent methodology text (R31)

Edit the passages marked `<!-- revise after doc_class validation gate -->` in
`METHODOLOGY.md` (2 markers) and `docs/index.html` (2 markers) so that they
match the INFERENCE values and letter handling the owner approved. Commit
with a `docs:` prefix. Do not push.

- Record: the commit SHA.

## 7. Full recompute and export validation

```bash
df -h $REPO/data
RUN_DATE=$(date +%F)
$PY scripts/compute_snapshots.py --workers 4 > logs/compute_snapshots.log 2>&1; echo "exit $?"
df -h $REPO/data
$PY scripts/validate_exports.py --since $RUN_DATE
```

- Record: `df -h` before and after, `RUN_DATE`, and the validate_exports line.
- Stop if: compute exits non-zero, or validate_exports FAILED. Stale files
  (`last_updated` before `RUN_DATE`), missing v2 fields, missing `flags` and
  missing `classes/{slug}.json` all count as failures.

Spot-check 2024-12 `rolling_if` against the spec's estimates:

```bash
$PY - <<'EOF'
import json
est = {"nature": 26.05, "circulation": 27.37,
       "journal-of-the-american-college-of-cardiology": 19.01,
       "arteriosclerosis-thrombosis-and-vascular-biology": 6.00, "plos-one": 1.95}
for slug, e in est.items():
    d = json.load(open(f"docs/data/journals/{slug}.json"))
    p = next((p for p in d["timeseries"] if p["month"] == "2024-12"), None)
    print(f"{slug:50s} est {e:6.2f}  got {p and p['rolling_if']}")
EOF
```

- Record: the table. Detector journals are expected to move further than
  this, toward their review rate.
- Stop if: a named journal is far off its estimate with no explanation.
  Report it to the owner.

## 8. Flag distribution (plan Task 9 Step 5)

```bash
$PY - <<'EOF'
import json, glob, collections
c, n = collections.Counter(), 0
for f in glob.glob("docs/data/journals/*.json"):
    n += 1; c.update(json.load(open(f)).get("flags", []))
print(f"{n} journals")
for k, v in c.most_common(): print(f"  {k}: {v} ({100*v/n:.1f}%)")
EOF
```

- Record: the distribution.
- Stop if: any flag fires on more than a third of journals. Report it to the
  owner before keeping that threshold.
- Then edit the passages marked `<!-- revise after flag distribution -->` in
  `METHODOLOGY.md` (1 marker) and `docs/index.html` (1 marker) to state the
  final thresholds. Commit with a `docs:` prefix. Do not push.

## 9. Browser check of the real export (R2)

```bash
$PY -m http.server -d docs 8000      # open http://localhost:8000 (local data path)
```

Check, and record what you see for each:

- Journals: the metric cards for Nature, ATVB and one detector journal. Check
  the flag lines, which should read "In the window ending YYYY-MM: …" with a
  month about 12 months before the latest. Check that the composition chart
  shows Other (black) and Commentary (grey) as separate areas.
- Influence: PMID 35510553. Check the net-effect, peak and benchmark cards.
  Try a seed that is not citable as well; it should show "No effect … no
  citable paper to remove".
- Methodology: open `#methodology`. The window table should read "the 24
  months ending 12 months before M", and the revised passages should be
  present.
- No console errors. The Network tab should show `data/…` requests.
- Stop if: anything is broken or a field is missing. Fix it on the branch
  first.

## 10. Gap catch-up (I2)

The weekly job has been paused since the lock was taken, and the last
successful weekly run was **2026-10-19**. Cover the gap before release:

```bash
DAYS=$(( ( $(date +%s) - $(date -j -f %F 2026-10-19 +%s) ) / 86400 + 3 ))
echo $DAYS
$PY scripts/run_weekly_update.py --days $DAYS > logs/catchup.log 2>&1; echo "exit $?"
grep "matched to tracked journals" logs/catchup.log
$PY scripts/validate_exports.py --since $RUN_DATE
```

- Splitting: `run_weekly_update.py` only takes `--days N` (the N days ending
  today) and walks them one day at a time. There is no start/end option, so a
  date range cannot be split across separate runs without a code change. If
  `DAYS` is large (more than about 45), tell the owner before running. The
  options are a single long run, or adding an end-date option on the branch
  first.
- Record: `DAYS`, the exit code, and the ISSN match rate, computed as
  matched / (matched + untracked) from the log lines. Compare it with the old
  ~98.6%.
- Stop if: the exit code is not 0, the match rate is well below 98.6%, or
  validate_exports FAILED.

## 11. Upload to v2/ (OWNER, R26)

```bash
$PY scripts/upload_to_r2.py --dry-run      # default prefix v2/
```

- **OWNER go-ahead**, then: `$PY scripts/upload_to_r2.py`
- Record: the number of files uploaded, and confirm that every key is under
  `v2/`.
- Stop if: any key lands outside `v2/`.

## 12. Push main (OWNER)

- **OWNER go-ahead**, then move `main` to the checked-out tip and push it:

```bash
git -C $REPO status --short | grep -v '^??'
git -C $REPO switch main && git -C $REPO merge --ff-only fix/pubmed-fetch-resilience
git -C $REPO push origin main
```

(If the main checkout is still on `fix/pubmed-fetch-resilience`, that branch
now holds the feature tip and the doc commits from steps 6 and 8.)

- Then confirm that the Pages deploy succeeded, that the live `index.html`
  references `app.js?v=37` and `chart-manager.js?v=7`, and that the Network
  panel shows `…/v2/index.json` loading.
- Stop if: the deploy fails, or the live site still loads the root
  `index.json`.

## 13. Commit the regenerated index.json

```bash
git -C $REPO add docs/data/index.json
git -C $REPO commit -m "feat: regenerate index.json for the citable-items rate"
```

Push it with the owner's go-ahead (or include it in the step 12 push if done
before it).

- Record: the commit SHA.

## 14. Release the lock; verify the next weekly run

```bash
sqlite3 -readonly data/impact.db "SELECT MAX(pmid) FROM papers;"   # record as MAXPMID
$PY scripts/rebuild_lock.py release
$PY scripts/rebuild_lock.py status; echo "exit $?"                 # expect exit 1
```

After the next Monday weekly run, check `logs/weekly-update-<date>.log`:

```bash
sqlite3 -readonly data/impact.db "SELECT COUNT(*), SUM(doc_class IS NOT NULL) FROM papers WHERE pmid > MAXPMID;"
sqlite3 -readonly data/pubmed_full.db "SELECT COUNT(DISTINCT pmid) FROM authors WHERE pmid > MAXPMID;"
grep -n "v2/" logs/weekly-update-*.log | tail
```

- Record: new papers, how many have `doc_class`, how many have `authors`
  rows, and that the upload keys are under `v2/`.
- Stop if: new papers lack `doc_class` or `authors` rows, or the upload went
  to the bucket root.

## 15. Retire pubmed_bulk.db (after the owner confirms the live site)

```bash
du -ch data/pubmed_bulk.db data/pubmed_bulk.db-shm data/pubmed_bulk.db-wal 2>/dev/null | tail -1
df -h $REPO/data
rm -f data/pubmed_bulk.db data/pubmed_bulk.db-shm data/pubmed_bulk.db-wal
df -h $REPO/data
```

- Record: the space freed.
- Deleting the old R2 root keys (the pre-v2 layout) is a separate owner
  decision. It is not part of this runbook.
