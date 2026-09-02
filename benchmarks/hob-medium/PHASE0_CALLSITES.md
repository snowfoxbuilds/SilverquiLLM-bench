# Phase 0 — Call-site map & baseline (MSH Task #1)

Recon for the V1 → Player Query migration. Every row below must be converted by
Phase 2 (engine) / Phase 4 (FDN cards). The five V1 `Player` methods being
deleted are `choose_target`, `choose`, `choose_yes_no`, `assign_damage_order`,
`choose_card`, plus `ScriptExhaustedError`.

## Action layer vs. choice layer

Per the spec ("the engine stays deterministic and imperative; only the *choice*
layer becomes query-driven; the action layer — cast this, activate that —
remains directive-driven"), call sites split two ways:

- **Choice layer → Player Query.** The engine, mid-resolution / mid-rule, asks
  the player to pick among engine-computed legal options (targets, modes, mana
  colors, optional/additional costs, sacrifices, discards, ordering, searches,
  legend-rule keep). These become `answer(PlayerQuery) -> Answer`.
- **Action layer → directive (NOT a query).** Proactive turn-based actions a
  player initiates with priority: priority-action selection and combat
  declaration of attackers/blockers. These remain directive-driven via the
  surviving action channel; the exact mechanism is settled in Phase 2/3.

This split is a judgment call recorded in `KEY_DECISIONS.md` (2026-06-11); the
spec wins if Phase 2 reveals a site must flip.

## Decision kinds referenced below

`OBJECT` (permanent/card instance), `PLAYER`, `BOOL` (yes/no), `NUMBER`,
`MANA` (mana color, possibly restricted via Modifier), `ABILITY`,
`MODE` (modal choice — kind finalized in Phase 1), `COLOR` (choose-a-color —
kind finalized in Phase 1).

## Engine call sites (`benchmarks/msh/workspace/engine/`)

| File:line | V1 method | Purpose | Becomes |
| --- | --- | --- | --- |
| `casting.py:179` | `choose_target` | spell/ability target selection | Player Query — OBJECT/PLAYER target |
| `casting.py:331` | `choose_target` | spell/ability target selection | Player Query — OBJECT/PLAYER target |
| `combat.py:235` | `choose` | declare attackers (multi) | Action layer — directive |
| `combat.py:297` | `choose` | declare blockers (assignment) | Action layer — directive |
| `combat.py:356` | `assign_damage_order` | damage assignment order | Player Query — OBJECT ordering (`min==max==len`) |
| `replacement_effects.py:110` | `choose` | choose replacement-effect order | Player Query — ordering |
| `stack.py:156` | `choose` | priority: choose action or pass | Action layer — directive |
| `state_based_actions.py:181` | `choose` | legend rule: which to keep | Player Query — OBJECT |
| `turn.py:115` | `choose_card` | discard to hand size (cleanup) | Player Query — OBJECT discard |

`turn.py:104-116` catches `ScriptExhaustedError` (auto-discard fallback) — the
catch goes away with the exception; cleanup discard becomes a Player Query
answered by the baseline intent (or auto-resolved when min==max).

`engine/player.py:13` defines `ScriptExhaustedError`; `engine/player.py:40-95`
defines the five abstract methods; `engine/player.py:98-146` is the V1
`DeterministicPlayer`. All deleted in Phase 2/3.

## FDN card implementation call sites (`cards/fdn/*/card_impl.py`)

Each is a card-level choice that must be re-expressed as a Player Query raised
through the engine's query machinery (Phase 4). Mapping of method → kind:
`choose_card` → OBJECT (zone attr per source); `choose_yes_no` → BOOL;
`choose_target` → OBJECT/PLAYER; `choose` → MODE/COLOR/OBJECT per prompt.

| File:line | V1 method | Purpose | Becomes |
| --- | --- | --- | --- |
| `cards/fdn/fdn_106/card_impl.py:78` | `choose_card` | creature to put onto the battlefield | Player Query — OBJECT |
| `cards/fdn/fdn_108/card_impl.py:56` | `choose_card` | creature to put +1/+1 counters on | Player Query — OBJECT |
| `cards/fdn/fdn_113/card_impl.py:64` | `choose_card` | choose mode: counter or token | Player Query — OBJECT |
| `cards/fdn/fdn_113/card_impl.py:70` | `choose_card` | creature to put +1/+1 counter on | Player Query — OBJECT |
| `cards/fdn/fdn_115/card_impl.py:71` | `choose_card` | creature card to return from graveyard | Player Query — OBJECT |
| `cards/fdn/fdn_117/card_impl.py:50` | `choose_card` | creature to get +X/+X and trample | Player Query — OBJECT |
| `cards/fdn/fdn_118/card_impl.py:51` | `choose_card` | card to discard | Player Query — OBJECT |
| `cards/fdn/fdn_118/card_impl.py:75` | `choose_card` | card to discard | Player Query — OBJECT |
| `cards/fdn/fdn_122/card_impl.py:63` | `choose` | flicker | Player Query — MODE/COLOR/OBJECT |
| `cards/fdn/fdn_122/card_impl.py:70` | `choose_card` | creature to exile and return at end step | Player Query — OBJECT |
| `cards/fdn/fdn_124/card_impl.py:72` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_124/card_impl.py:81` | `choose_card` | discard a card or lose 3 life | Player Query — OBJECT |
| `cards/fdn/fdn_125/card_impl.py:50` | `choose` | gain_life | Player Query — MODE/COLOR/OBJECT |
| `cards/fdn/fdn_126/card_impl.py:58` | `choose_card` | creature to get +1/+1 counter ({i + 1}/2) | Player Query — OBJECT |
| `cards/fdn/fdn_126/card_impl.py:86` | `choose_card` | creature/artifact to double counters ({i + 1}/2) | Player Query — OBJECT |
| `cards/fdn/fdn_154/card_impl.py:53` | `choose_card` | Choose a nonland permanent to copy | Player Query — OBJECT |
| `cards/fdn/fdn_157/card_impl.py:46` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_158/card_impl.py:44` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_158/card_impl.py:57` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_166/card_impl.py:68` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_170/card_impl.py:52` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_177/card_impl.py:79` | `choose_card` | Choose a card to discard | Player Query — OBJECT |
| `cards/fdn/fdn_181/card_impl.py:80` | `choose_card` | Choose a nonland card to discard | Player Query — OBJECT |
| `cards/fdn/fdn_184/card_impl.py:39` | `choose_card` | Choose a card to put into your hand | Player Query — OBJECT |
| `cards/fdn/fdn_185/card_impl.py:62` | `choose_card` | Choose a Vampire to put a +1/+1 counter on | Player Query — OBJECT |
| `cards/fdn/fdn_193/card_impl.py:55` | `choose_card` | Choose a target for 4 damage | Player Query — OBJECT |
| `cards/fdn/fdn_193/card_impl.py:65` | `choose_card` | Choose target {i + 1} for 3 damage (optional) | Player Query — OBJECT |
| `cards/fdn/fdn_194/card_impl.py:57` | `choose_yes_no` | Cast {getattr(card,  | Player Query — BOOL |
| `cards/fdn/fdn_198/card_impl.py:60` | `choose_yes_no` | Pay {R} to return Flamewake Phoenix from graveyard? | Player Query — BOOL |
| `cards/fdn/fdn_199/card_impl.py:43` | `choose_yes_no` | Pay {R} to make a creature unable to block? | Player Query — BOOL |
| `cards/fdn/fdn_199/card_impl.py:59` | `choose_card` | Choose a creature that can | Player Query — OBJECT |
| `cards/fdn/fdn_211/card_impl.py:57` | `choose` | creature to fight | Player Query — MODE/COLOR/OBJECT |
| `cards/fdn/fdn_225/card_impl.py:65` | `choose_card` | basic land to search for | Player Query — OBJECT |
| `cards/fdn/fdn_234/card_impl.py:75` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_24/card_impl.py:85` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_248/card_impl.py:80` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_248/card_impl.py:96` | `choose_target` |  | Player Query — OBJECT/PLAYER |
| `cards/fdn/fdn_257/card_impl.py:60` | `choose_card` | Choose a basic land to put onto the battlefield | Player Query — OBJECT |
| `cards/fdn/fdn_267/card_impl.py:58` | `choose` |  | Player Query — MODE/COLOR/OBJECT |
| `cards/fdn/fdn_267/card_impl.py:90` | `choose` |  | Player Query — MODE/COLOR/OBJECT |
| `cards/fdn/fdn_28/card_impl.py:59` | `choose_yes_no` | Surveil 1: Put {getattr(top_card,  | Player Query — BOOL |
| `cards/fdn/fdn_3/card_impl.py:60` | `choose_card` | target creature for +1/+1 counter | Player Query — OBJECT |
| `cards/fdn/fdn_31/card_impl.py:54` | `choose_target` | creature an opponent controls | Player Query — OBJECT/PLAYER |
| `cards/fdn/fdn_32/card_impl.py:64` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_34/card_impl.py:66` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_34/card_impl.py:86` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_38/card_impl.py:50` | `choose_target` | creature an opponent controls | Player Query — OBJECT/PLAYER |
| `cards/fdn/fdn_42/card_impl.py:50` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_43/card_impl.py:65` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_45/card_impl.py:46` | `choose_card` | Choose a card to discard | Player Query — OBJECT |
| `cards/fdn/fdn_45/card_impl.py:75` | `choose_yes_no` | Create Scion of the Deep token? | Player Query — BOOL |
| `cards/fdn/fdn_48/card_impl.py:128` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_51/card_impl.py:49` | `choose_card` | Choose an instant or sorcery card to gain flashback | Player Query — OBJECT |
| `cards/fdn/fdn_53/card_impl.py:78` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_53/card_impl.py:94` | `choose_yes_no` |  | Player Query — BOOL |
| `cards/fdn/fdn_54/card_impl.py:67` | `choose_card` | creature card to exile from graveyard | Player Query — OBJECT |
| `cards/fdn/fdn_55/card_impl.py:56` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/fdn_57/card_impl.py:69` | `choose_card` | sacrifice a creature | Player Query — OBJECT |
| `cards/fdn/fdn_60/card_impl.py:63` | `choose_card` | card to keep on top of library | Player Query — OBJECT |
| `cards/fdn/fdn_61/card_impl.py:51` | `choose_card` | sacrifice a creature for +1/+1 counter | Player Query — OBJECT |
| `cards/fdn/fdn_70/card_impl.py:63` | `choose_card` | card to exile from graveyard | Player Query — OBJECT |
| `cards/fdn/fdn_70/card_impl.py:82` | `choose_card` | second card to exile | Player Query — OBJECT |
| `cards/fdn/fdn_72/card_impl.py:58` | `choose_card` | discard a card | Player Query — OBJECT |
| `cards/fdn/fdn_74/card_impl.py:46` | `choose_card` | sacrifice a creature for draw + unblockable | Player Query — OBJECT |
| `cards/fdn/fdn_77/card_impl.py:61` | `choose_card` | Zombie creature to cast from graveyard | Player Query — OBJECT |
| `cards/fdn/fdn_78/card_impl.py:49` | `choose_card` | creature to get +1/+0 and menace | Player Query — OBJECT |
| `cards/fdn/fdn_81/card_impl.py:54` | `choose_card` | Choose one exiled card to play this turn | Player Query — OBJECT |
| `cards/fdn/fdn_86/card_impl.py:51` | `choose_card` | Equipment to exile | Player Query — OBJECT |
| `cards/fdn/fdn_89/card_impl.py:72` | `choose_card` | target for 2 damage | Player Query — OBJECT |
| `cards/fdn/fdn_96/card_impl.py:79` | `choose_card` | card to play until end of next turn | Player Query — OBJECT |
| `cards/fdn/spg_76/card_impl.py:66` | `choose_card` |  | Player Query — OBJECT |
| `cards/fdn/spg_83/card_impl.py:134` | `choose_card` | Search for creature with MV ≤ {x_value} | Player Query — OBJECT |

## fdn_81 & lazy-target private-attribute pokes (must not survive migration)

| File:line | Poke | Re-expressed as |
| --- | --- | --- |
| `fdn_81/card_impl.py:88` | `getattr(pw, '_damage_assignments', ...)` | damage-order Player Query |
| `fdn_81/card_impl.py:93` | `getattr(pw, '_resolve_targets', ...)` | target Player Query / intent |
| `fdn_105/card_impl.py:35` | `getattr(card, '_resolve_targets', ...)` | target Player Query / intent |
| `fdn_162/card_impl.py:35` | `getattr(card, '_resolve_targets', ...)` | target Player Query / intent |
| `fdn_212/card_impl.py:35` | `getattr(card, '_resolve_targets', ...)` | target Player Query / intent |

(The fdn_81 pokes are explicitly named in the Task #1 prompt; fdn_105/162/212
share the same lazy-target idiom and are migrated the same way.)

## Baseline replay report (parity bar for Phase 6)

Corpus: `data/replays/` → `sample_replay.json` (the only FDN replay present;
`card_id_map.json` is metadata). Run via the replay pipeline
(`parse_replay` → `ReplayExecutor` → `validate_replay`) with the MSH V1 engine on
`sys.path`.

| Replay file | Snapshots | Successful | Divergences | By type |
| --- | --- | --- | --- | --- |
| `sample_replay.json` | 12 | 12 | **0** | (none) |

**Parity bar:** per-file divergence count after migration must be **≤ 0** for
`sample_replay.json` (i.e. it must stay at zero divergences).

## Passing-test inventory (coverage bar for Phase 5 / acceptance)

Run with the repo venv's pure-python pytest under Python 3.11 (the committed
venv was built for 3.12; interpreter drifted — see `KEY_DECISIONS.md`).

| Suite | Command | Result |
| --- | --- | --- |
| Engine tests | `pytest benchmarks/msh/workspace/engine_tests/ -q` | **1145 passed** |
| FDN reference tests | `pytest benchmarks/msh/workspace/cards/fdn/ -q` | **39 passed** (5 colocated `tests.py`: fdn_13, fdn_142, fdn_205, fdn_215, fdn_244) |

These are the green sets that Phase 5 (engine_tests) and Phase 4 (FDN reference
tests) must restore under the new protocol.
