# Audited-Test Coupling Backlog (SOS)

Status: OPEN — deferred 2026-06-01. Tracks Implementation-Agnostic-Testing
violations in the SOS audited suite that are **not yet fixable** because the
matching Test Oracle Impl does not exist.

## Context

Per **ADR-010** an audited test may only be changed once it passes against its
**Test Oracle Impl** (`benchmarks/sos/data/test_oracle_workspace/cards/sos/<cn>/card_impl.py`),
enforced by `tests/test_audited_against_reference.py`. A scan on 2026-06-01 found
**201** audited test files coupling to non-canonical (oracle-only / invented)
card surface — but only **5** of them had a non-stub oracle impl to validate a
fix against. The other **196 have empty stub oracles** (and
`cards/stubs/sos_stubs.py` is 346 identity-only stubs with no game logic), so
their behavioral assertions cannot be run against anything. See memory
`audited-oracle-coverage-gap`.

**Therefore each backlog card needs a Test Oracle Impl built first, then a
canonical rewrite + harness gate — the Phase-18 per-card flow.** Do NOT rewrite
these blind: an unvalidated edit to the grading suite is undetectably worse than
the current state.

Re-scan anytime: `python tmp/inventory_violations.py` (and the per-symbol
grouping snippet used to build the lists below).

## Already fixed (2026-06-01) — not in this backlog

`sos_13`, `sos_57`, `sos_97`, `sos_120`, `sos_257` — rewritten to canonical API
(test + oracle impl) and validated green by the oracle harness. These were the
report's Part A + Part C/sos_57, i.e. the only coupled cards with a non-stub
oracle.

## Canonical replacement table (apply per card, with an oracle impl + harness gate)

| Non-canonical symbol (forbidden) | Canonical replacement |
|---|---|
| `card.set_targets(...)` / `card._targets` | `card.chosen_targets = [...]` (set by the casting pipeline; for direct probes assign it) |
| `card.on_enter_battlefield(...)` | `card.register_triggers(game)` + fire `EntersBattlefieldTriggeredEvent`, or drive via `on_resolve` / `move_to_zone` |
| `card.on_spell_cast(...)` | `register_triggers` + `trigger_manager.fire_event(game, SpellCastTriggeredEvent(...))` |
| `card.on_attack(...)` | `register_triggers` + `AttacksTriggeredEvent` |
| `card.get_adjusted_cost(...)` | `card.cost_reduction(game)` (canonical hook) / observe required mana via casting |
| `card._cast_via_flashback(...)` | drive through the casting pipeline (`cast_spell_from_exile` / graveyard cast) and assert the outcome |

Trigger-driving pattern proven in sos_120/sos_57: read the trigger's own event
type from `trigger_manager.get_triggers_for_source(card)` and fire it via
`fire_event` — never name an engine-internal event class, never touch
`trigger_manager._triggers`.

## Backlog by symbol (196 cards; a card can appear under more than one)

### set_targets / _targets → chosen_targets  (129)
soa_11 soa_13 soa_14 soa_15 soa_20 soa_26 soa_27 soa_29 soa_30 soa_36 soa_38 soa_4 soa_42 soa_43 soa_45 soa_5 soa_50 soa_51 soa_52 soa_54 soa_56 soa_65 soa_8 soa_9 sos_10 sos_101 sos_103 sos_104 sos_106 sos_110 sos_112 sos_116 sos_118 sos_119 sos_121 sos_127 sos_128 sos_129 sos_135 sos_136 sos_137 sos_138 sos_139 sos_141 sos_142 sos_143 sos_144 sos_146 sos_15 sos_151 sos_153 sos_154 sos_155 sos_156 sos_157 sos_159 sos_164 sos_165 sos_167 sos_172 sos_173 sos_179 sos_18 sos_181 sos_187 sos_188 sos_192 sos_193 sos_195 sos_196 sos_197 sos_203 sos_207 sos_208 sos_209 sos_210 sos_213 sos_22 sos_220 sos_221 sos_228 sos_233 sos_235 sos_236 sos_239 sos_240 sos_241 sos_242 sos_248 sos_25 sos_250 sos_251 sos_253 sos_254 sos_26 sos_260 sos_263 sos_264 sos_29 sos_31 sos_32 sos_34 sos_37 sos_38 sos_39 sos_41 sos_43 sos_54 sos_58 sos_59 sos_6 sos_61 sos_62 sos_63 sos_66 sos_71 sos_75 sos_77 sos_78 sos_83 sos_84 sos_89 sos_9 sos_95 sos_96 spg_149 spg_152 spg_154

### on_enter_battlefield → register_triggers / on_resolve  (51)
soa_32 soa_61 soa_7 sos_107 sos_108 sos_111 sos_114 sos_123 sos_124 sos_125 sos_133 sos_14 sos_140 sos_161 sos_163 sos_168 sos_175 sos_180 sos_182 sos_183 sos_189 sos_190 sos_194 sos_199 sos_2 sos_200 sos_206 sos_21 sos_212 sos_215 sos_223 sos_224 sos_229 sos_24 sos_247 sos_3 sos_33 sos_42 sos_44 sos_45 sos_48 sos_5 sos_55 sos_69 sos_7 sos_70 sos_73 sos_8 sos_91 sos_93 spg_156

### _cast_via_flashback → casting pipeline  (10)
soa_40 sos_10 sos_112 sos_115 sos_135 sos_17 sos_204 sos_216 sos_25 sos_9

### on_spell_cast → SpellCastTriggeredEvent  (9)
sos_16 sos_196 sos_20 sos_227 sos_29 sos_35 sos_84 sos_87 sos_90

### on_attack → AttacksTriggeredEvent  (8)
sos_199 sos_206 sos_238 sos_3 sos_45 sos_8 sos_91 sos_93

### get_adjusted_cost → cost_reduction  (4)
soa_61 sos_218 sos_243 spg_157

## Note for whoever picks this up

The validation harness `tests/test_audited_against_reference.py` hardcodes its
card set in `_AUDITED_CARDS` (currently 10). When you build a new oracle impl,
add the card there (or generalize `_discover_oracle_cards()` to scan all
non-stub oracle dirs) so the new pairing is actually gated in CI.
