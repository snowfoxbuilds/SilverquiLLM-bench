Status: ACCEPTED
Date: 2026-09-29

# ADR-015: The Results Repo Keeps Graded Workspaces as Diffs from One Shared Baseline

## Context

Records from several hosts share one results repository, but each run's graded workspace stayed in the run artifacts of the host that ran it, so only that host could re-grade the run after grading inputs changed.
The results repository's rule that heavy artifacts never enter git kept clones small; a hob-medium workspace is about 6.6 MB in 1,200 files, so a full copy per run would grow a clone and its checkout by gigabytes over a few hundred runs.
Every run of a benchmark input starts from the same staged workspace, and an agent changes a few dozen files of it.

## Decision

The results repository carries each record's graded workspace, the one exception to "heavy artifacts never enter git".
It stores each benchmark input's staged baseline once, as a git bundle at `baselines/<tree-id>.bundle`, and each record's graded workspace as a binary diff from that baseline at `workspaces/<candidate-hash>/<run-id>/workspace.patch`, with `workspace.json` naming both tree ids and the graded copy's content digest.
The archived tree is exactly the copy grading used, so its content digest equals the one the record's `grading_source` states.
Both files are write-once: an existing baseline is verified to hold the same tree and never replaced.
Trees are built and rebuilt with git plumbing in a scratch repository, so no workspace attribute, filter, ignore rule or host configuration changes a byte, and a run's own `.git` is never read or written.
Every write is preceded by a full rebuild from the bytes about to be written, and every read refuses a rebuild whose tree id or content digest differs.

## Consequences

- **Positive**: Any host can re-grade any archived run; a record, its archive and its exclusions travel together.
- **Positive**: A hob-medium archive is about 15–20 KB, and the shared baseline about 1 MB.
- **Negative**: A workspace is readable only through the bench's rebuild, not as a plain directory in a checkout.
- **Negative**: A diff over 16 MB is refused rather than archived, and stays only on its host.
- **Neutral**: Records stay immutable; the archive sits beside a record, so records from before archives are backfilled without editing them.

## Alternatives Considered

- **Full workspace copies per run**: Rejected for clone and checkout size, since git would share unchanged blobs but every checkout would still hold every file of every run.
- **A tarball per run**: Rejected because compressed tarballs share nothing across runs, about 1.5 MB each.
- **Diff against the benchmark data in the bench repo**: Rejected because the results repository must stay self-contained, and the bench's benchmark data changes over time.
- **Storing workspaces outside git, e.g. in object storage**: Rejected as a second system to operate and keep in step with the records.

## Relevant PRs

- #113 — Adds workspace archives, run provenance and exclusions to the shared results repository.
