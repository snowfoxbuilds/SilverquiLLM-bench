Status: RENAME RECORD

Date: 2026-11-18

# ADR-024: Login Cooldown is renamed Cooldown

## Renames

A window in which no new run may take a resource now applies to GPU Slots as well as Login Profiles, and a resource may hold several of them, in force or still to come, as its Cooldown Schedule (grilling 2026-11-18).
"Login Cooldown" named a login-only, single hold, so the term is generalized rather than paralleled by a second one for GPUs.

| Old | New |
| --- | --- |
| Login Cooldown | Cooldown, one window of a Login Profile's or a GPU Slot's Cooldown Schedule |
| "a Login Profile is under at most one Login Cooldown; setting another replaces it" | a Cooldown Schedule may hold any number of Cooldowns |
| the cooldown file `cooldown.json` (one end time) | `cooldowns.json` (a list of windows); an existing `cooldown.json` is converted once and removed |

## Where the old names were replaced

- The glossary, the Karn Benchmark Contract, Run Monitoring, Local Model Server and the operator documentation use the new name.
  No compatibility alias is part of the rename.
- Source symbols, the slot directory's file, `silverquillm login cooldown`, `silverquillm top` and their tests follow with the Cooldown Schedule's implementation.

## Where the old names stay

- History keeps its words: every Amendments log and Relevant PRs entry, and dated grilling tags.
- The glossary lists the old name as a term to avoid.

## Relevant PRs

- The docs pull request of the Cooldown Schedule chain renames the term in the glossary and specifications; the code follows in the chain's implementation pull requests.
