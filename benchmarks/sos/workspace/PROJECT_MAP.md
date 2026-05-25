# PROJECT_MAP.md — Directory Layout

```
AGENTS.md          — Workspace orientation and rules
PROJECT_MAP.md     — This file; directory summary
RULEBOOK.txt       - The entire comprehensive MTG rules. Grep from it instead of reading directly.
prompt.md          — Per-run task prompt (written at stage time)
run_manifest.json  — Per-run manifest with timeout info (written at stage time)
pytest.ini         — Pytest configuration for the workspace
.gitignore         — Git ignore rules
engine/            — Canonical game engine source (shared with bench tooling)
cards/             — Card implementations (fdn/ references, sos/ stubs to implement)
tests/             — Test suites (engine regression tests)
skills/            — Workspace-local skills (e.g. grep-rulebook/SKILL.md)
```
