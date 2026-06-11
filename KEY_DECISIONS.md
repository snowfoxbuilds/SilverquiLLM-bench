# Key Decisions

Persistent architectural and convention decisions across runs. Periodically drained into specs/ADRs

## MSH Task #1 — Player Query / Player Decision protocol

Format: date — decision — why — rejected alternative.

- 2026-06-11 — Module layout `engine/{decisions,queries,refs_registry,player,intent_player}.py` per the locked split. — Locked by prompt + MSH-DECISION-MODEL.md "Concrete protocol surface". — A single mega-module (rejected: tangles data layer, protocol, and test player).
- 2026-06-11 — Exception split `ProtocolError` (engine-fault) vs `IntentError` (test-fault) with the named subclasses. — Locked by prompt; replaces `ScriptExhaustedError` with attributable signals. — One flat exception type (rejected: loses engine-vs-test fault attribution).
- 2026-06-11 — `Answer(selected: tuple[PlayerDecision, ...])`; decline is `Answer(())` legal iff `min==0`. — Locked by prompt; no separate Decline type keeps the surface minimal. — A dedicated `Decline` sentinel (rejected: redundant with empty selection).
- 2026-06-11 — Ordering queries use `min == max == len(options)` with answer order = assignment order. — Locked by prompt; reuses the selection mechanism for damage/trigger ordering. — A separate ordering API (rejected: duplicates the Answer machinery).
- 2026-06-11 — `Intent(pattern: GameRef, preferences: tuple[PlayerDecision,...], postcondition)`; name passed to `start_intent`, not stored on Intent. — Locked by prompt. — Storing name on Intent (rejected: couples identity to the registry key).
- 2026-06-11 — Single Baseline-Intent slot: a regular Intent with empty pattern, consulted only when no card intent matches; at most one active. — Locked by prompt. — A stack of baselines (rejected: ambiguous fallthrough order).
- 2026-06-11 — Stable option order = sort by `(timestamp, zone_index)` game-state key, never set/dict iteration; the key is recorded here. — Determinism requirement; timestamp is the engine's existing ordering primitive. — set/dict iteration order (rejected: nondeterministic, forbidden by prompt).
- 2026-06-11 — Action-vs-choice split: priority-action selection (`stack.py`) and combat declaration of attackers/blockers (`combat.py`) stay action-layer/directive-driven; all other V1 choice sites become Player Queries. — Spec: engine stays imperative, only the choice layer is query-driven ("cast this / activate that" remain directives). — Converting declare-attackers/priority to queries (rejected: the spec reserves proactive turn-based actions for the action channel); spec wins if Phase 2 disproves this.
- 2026-06-11 — Tests run under `/usr/bin/python3.11` with the committed venv's pure-python site-packages on `PYTHONPATH` (`venv/lib/python3.12/site-packages`). — The committed venv was built for 3.12 but only 3.11 remains on this host; pytest/click are pure-python and import cleanly; engine collects with no syntax errors. — Rebuilding the venv (rejected: no need; would touch environment outside task scope).
