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
  unpromoted, tampered, or legacy candidate cannot be published. The
  candidate must be what the tree holds: a real `candidates/<slug>--<hash8>/`
  directory with a real `bundle/`, never a symlink — even one pointing at a
  valid bundle elsewhere on the host is refused, not followed. The source run
  record is proven through every ancestor — `results/`, the candidate-hash
  directory and the run directory real directories, `manifest.json` and
  `scores.json` regular files — and proven again immediately before each
  copy; a record behind a symlinked ancestor is never publishable, however
  valid its target.
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
is skipped — provided it is a real directory holding both files as regular
files, since a symlinked record or record file is refused even when it
resolves to identical bytes — and one that differs is a conflict — a
published record is never overwritten. The success summary prints only
after the commit.

If the process dies mid-way, the next invocation against that destination
reads the journal first and finishes the job: a transaction that had already
committed every record is completed, anything less is rolled back. The journal
is trusted only as a real regular file in the destination: it is opened
without following a link and its type is proven on the open descriptor before
a byte is read, so a symlinked journal (even one pointing at a plausible
journal elsewhere), a directory, a FIFO or a device under its name is refused,
never followed — by recovery and by `--dry-run` alike. Recovery removes only
what the journal proves the transaction created: every name in it must be a
plain child of the destination, and every directory it would remove is proven
— before anything goes — to be a real directory directly under the destination
holding only `manifest.json` and `scores.json` as regular files (a directory,
symlink, FIFO, socket or device under either name is refused; a record still
in staging may hold one of the two, a committed record must hold both). A
symlink is refused, never followed; every target is checked before the first
is removed; and a journal that fails any check is refused whole with every
byte, name and mtime unchanged. A rollback that itself fails is reported
prominently and keeps the journal; nothing publishes into that destination
until recovery succeeds. Do not delete a journal by hand unless you have
inspected the directories it names.

`--dry-run` is read-only: it checks every run and lists what would be
published, and if a journal is pending it reports the recovery that would
occur (`RECOVERY REQUIRED …`) and exits nonzero without performing it —
bytes and mtimes under the destination stay exactly as they were.

How this tree is organized (per blog post, per experiment, …) is manual.
Tooling discovers published results by manifest, never by path: any directory
under `published/` holding `manifest.json` beside `scores.json` whose pair
re-proves as a Run Record named after the directory is a published run
(`scripts/publish_results.py`, `iter_published_records`); dot-prefixed
directories (a transaction's staging) never are. A published record is a
real in-tree directory holding regular files: discovery never follows a
symlinked directory and refuses a symlink or special file under a record
file's name. Heavy artifacts (transcripts, workspaces) never enter git.
