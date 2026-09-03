# Published results

The curated public set of benchmark results (#39 §4, #66;
`docs/specs/BENCHMARK-CANDIDATES.md`). Each published run is one directory
holding its Run Record byte for byte — `manifest.json` + `scores.json` —
ported from the private Results Repo by:

```bash
python scripts/publish_results.py --results-repo <clone> --dest published/<subdir> RUN_ID...
```

The script is a porter with two checks and never commits:

- **Traceability — hard refusal.** The run's candidate identity must be
  checked in under `candidates/` and verify by recomputation. A run of an
  unpromoted, tampered, or legacy candidate cannot be published.
- **Validity — warning.** `leaderboard_valid: false` (a Resume Leg, an
  ineligible benchmark, an unevaluated run) publishes only with
  `--allow-invalid`; the flag travels with the record and leaderboard tooling
  filters on it mechanically.

Review the published files and commit them — the commit is the approval stamp.

## Publication is a transaction

Every run is checked before a byte is written. New records are copied into a
private staging directory beside the destination, re-read and proven byte
identical to their sources, and only then moved into place — one atomic
rename per record — under a journal (`<dest>/.publish-journal.json`) that
names exactly the directories that invocation creates. A failure at any step
rolls back every directory the transaction created and leaves records that
were already there untouched; a record that already exists byte-identically
is skipped, and one that differs is a conflict — a published record is never
overwritten. The success summary prints only after the commit.

If the process dies mid-way, the next invocation against that destination
reads the journal first and finishes the job: a transaction that had already
committed every record is completed, anything less is rolled back. A
rollback that itself fails is reported prominently and keeps the journal;
nothing publishes into that destination until recovery succeeds. Do not
delete a journal by hand unless you have inspected the directories it names.

How this tree is organized (per blog post, per experiment, …) is manual.
Tooling discovers published results by manifest, never by path: any directory
under `published/` holding `manifest.json` beside `scores.json` whose pair
re-proves as a Run Record named after the directory is a published run
(`scripts/publish_results.py`, `iter_published_records`); dot-prefixed
directories (a transaction's staging) never are. Heavy artifacts
(transcripts, workspaces) never enter git.
