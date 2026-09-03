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

Review the staged files and commit them — the commit is the approval stamp.

How this tree is organized (per blog post, per experiment, …) is manual.
Tooling discovers published results by manifest, never by path: any directory
under `published/` holding `manifest.json` beside `scores.json` whose pair
re-proves as a Run Record named after the directory is a published run
(`scripts/publish_results.py`, `iter_published_records`). Heavy artifacts
(transcripts, workspaces) never enter git.
