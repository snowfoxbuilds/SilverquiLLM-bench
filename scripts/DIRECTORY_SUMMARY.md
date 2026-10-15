# Directory Summary — `scripts/`

## Purpose

What remains of the standalone scripts. The bench repo holds no scripts: the benchmark tooling runs as `silverquillm` commands from `silverquillm/tools/` (`data`, `build`, `audit`, `qualify`), and the analyses of runs live in the Results Repo (`scripts/legacy/` there) (#222).

## Key Files

| File | Responsibility |
|------|---------------|
| `triage_divergences.py` | Clusters replay divergences. It is a grading input: the grader copies it into the grading root and `grading_inputs` fingerprints it at `scripts/triage_divergences.py`, so moving it changes every grading-inputs digest that includes it. It stays here until that change is made deliberately. |
