> 🎯 **Status:** DRAFT — proposed 2026-06-03; sharpened in Grilling 2026-06-03 – 06-04 (added combat declarations, combat illegality, and deferred-capability scoping).
> **Owner:** @Anonymous
> 
> **Purpose:** Define the *only* sanctioned API audited tests may use to interact with the engine. If a behavior cannot be set up, driven, or observed through this API, the API is missing something — fix the API, do not reach around it.
> 
> **Scope:** **SOS (V1) only.** This two-channel API is the frozen SOS paradigm. The MSH benchmark replaces it with the native Player Query / Player Decision intent protocol — see [DECISION-MODEL.md](https://app.notion.com/p/bea4c558a1d2493a82a7a841d85a8fb0). Nothing in this spec applies to `benchmarks/msh/`.

## Philosophy

Audited tests validate behavior **exclusively through the game simulation**. This is the strictest possible stance, and it is deliberate: it gives the most room for implementation variation. Two engines with completely different internals pass the same audited test as long as they produce the same *observable* outcomes from the same setup and the same player actions.

> 🧩 **The API is canonical-only; the tests run against the oracle.** The test API references **only** primitives that exist in the **canonical** (frozen) engine. The audited tests themselves run against the **oracle** engine — and against each candidate engine, which is free to drift. So the API keeps functioning no matter how an engine diverges; only the *test result* depends on what a given engine implements. This is why oracle-only mechanics (sos_57 Mana Sculpt's `mana_spent` refund, sos_226 casualty, sos_201 miracle alt-cost, sos_245 affinity reduction, sos_1 / sos_120 graveyard→exile redirect) need **no** dedicated test-API support: each is exercised *indirectly* — the test drives canonical entrypoints and asserts observable state, and the engine either produces the right outcome (pass) or not (fail). **Building this test API requires no change to any workspace engine.**
> **Imports are a separate question.** An audited test imports whatever engine it runs on — `engine.*` resolves to the oracle, or to a candidate engine — because card behavior emerges from engine churn, so the test drives the *real* engine, not a frozen symbol subset. Portability comes from every candidate implementing the canonical public API, not from restricting imports. The canonical-only rule constrains the **test API** (`test_utils` + the directive vocabulary), which composes canonical-public entrypoints so it functions against any engine, plus the **no-engine-modification** guarantee — it does not forbid importing the running engine. The test API may even define helpers that *duplicate* canonical logic for a zone or cost the public API doesn't directly expose (e.g. `cast_spell_from_exile`, a copy of `cast_spell` that pulls from exile): composition in the test layer, never an engine change. What the paradigm replaces is **private-attribute poking** (`_script`, `_resolve_targets`) — correct behavior comes from *running* the engine, not reaching inside it.

Every audited test has exactly one shape:

1. **Set up** — declare a concrete starting state.
2. **Advance** — run the host-side driver (optionally fast-forwarding between phases).
3. **Assert** — check observable game state against expectations.
> ⛔ **Hard rules**
> - An audited test may touch the engine **only** through methods defined in this spec. Reaching into engine internals, calling private resolution helpers, or probing implementation details is prohibited.
> - State is advanced by the host-side driver — never by hand-resolving objects or mutating state mid-test. The only sanctioned advancers are `priority_loop` and `advance_to_phase`.
> - Assertions read **only** observable state (zones, stack, mana pool, counters, damage, life, etc.). Never assert on internal flags, private fields, call counts, or prompt logs.

### Canonical test shape

```python
def test_lightning_bolt_kills_a_bear():
	game = create_game()

	# 1. SET UP — declare the starting state
	set_board_state(
		game, 0,
		hand=["Lightning Bolt"],
		battlefield=[PermanentSpec("Mountain")],
		life=20,
	)
	set_board_state(
		game, 1,
		battlefield=[PermanentSpec("Grizzly Bears")],
		life=20,
	)

	# 2. SCRIPT players — directive queue (priority) + choice script (engine prompts)
	set_player(game, 0, DeterministicPlayer("P0", script=[
		perform_action(CastSpell("Lightning Bolt", targets=["Grizzly Bears"])),
		no_op(),
	]))
	set_player(game, 1, DeterministicPlayer("P1", script=[no_op(), no_op()]))

	# 3. ADVANCE — run the host-side driver
	priority_loop(game)

	# 4. ASSERT — observable outcomes only
	assert_in_zone(game, 1, Zone.GRAVEYARD, "Grizzly Bears")
	assert_stack_empty(game)
```

---

## Part 1 — Set up

Declare the full starting state up front. Setup writes directly (it does not go through priority); it is the one place where the test is allowed to place the board into an arbitrary legal configuration.

```python
set_board_state(
	game,
	player_index: int,
	*,
	battlefield: list[str | PermanentSpec] = (),
	hand:        list[str] = (),
	graveyard:   list[str] = (),
	library:     list[str] = (),   # ordered; index 0 = top of library
	exile:       list[str] = (),
	life:        int | None = None,
	mana:        dict[ManaType, int] | None = None,  # mana already in pool
) -> None
```

Per-permanent state (tapped, counters, damage, attachments) is expressed with `PermanentSpec` so it can be set wherever a permanent is placed:

```python
@dataclass
class PermanentSpec:
	name: str
	tapped: bool = False
	summoning_sick: bool = False
	counters: dict[str, int] = field(default_factory=dict)  # canonical: "+1/+1", "-1/-1", "loyalty"
	damage_marked: int = 0
	attachments: list[str] = field(default_factory=list)     # auras / equipment attached to this permanent
	controller: int | None = None                            # defaults to player_index
```

> 💡 **No ****`set_stack`**** primitive.** Stacked / mid-resolution states are reached by *casting* — script a player to cast the spell (Part 3), which runs the real cast pipeline. A direct stack-injection helper was considered and dropped: it would have to fabricate cast-time fields (`mana_spent`, `colors_spent`, chosen targets) that only the canonical cast path sets correctly — and some of those fields (e.g. `mana_spent`) don't exist on the canonical engine at all.

**Covers the current gaps.** Today's `set_board_state` only takes `battlefield`, `hand`, `graveyard`, `life`, `mana` — there is no first-class way to set library order, exile, tapped state, counters, or marked damage. This spec closes those (the stack is reached by casting, never set directly).

> 🎲 **Determinism — controlling RNG.** Effects that flip coins or roll dice (sos_97 Ral Zarek's −7: `sum(game.rng.randint(0, 1) for _ in range(5))`) are made deterministic **test-side, with no engine change**: replace the engine RNG with a seeded one (`game.rng = random.Random(seed)`) and **re-derive** the expected value from an identically-seeded `random.Random(seed)` rather than hardcoding a number — the pattern the existing audited tests already use. `create_game(seed=...)` may also seed at construction.

---

## Part 2 — Advancing the game state

There are exactly two sanctioned advancers.

### `priority_loop(game)`

A **host-side driver** that advances the game by polling players — not the engine's own all-pass auto-drain loop. This is the default way to move a test forward.

```python
priority_loop(game) -> None
```

Semantics, per iteration:

1. Check **state-based actions** first (`resolve_state_based_actions`), then place any waiting **triggered abilities**.
2. Poll players for a directive in **APNAP** order. If a player acts (`perform_action` / `perform_illegal_action`), execute it host-side through the canonical entrypoint, push to the stack **without** auto-draining, then re-poll from the active player (retain-on-action).
3. If **no player acts** and the stack is non-empty, resolve **exactly one** object via `resolve_top` (pop → `on_resolve` → re-check SBAs + triggers), then re-poll. Single-step resolution — **not** a full all-pass drain — so every resolution stays observable.
4. Terminate when the stack is empty **and** every player's directive queue is exhausted.
- If a player is polled for a directive, or the engine asks for a resolution-time choice, while the relevant queue is **dry**, raise `ScriptExhaustedError` → **test fails**. A test must never silently pass because the engine stopped asking.
> 🔁 **Caveat — self-draining resolutions.** A few oracle cards drain the stack *inside* their own `on_resolve` — sos_120 Improvisation Capstone casts the exiled spells and resolves them in a loop. A single `resolve_top` of such a card cascades internally, so the test observes only the **end state**, not the intermediate stack between nested casts. That is engine-internal and acceptable under the canonical-only rule (assert final zones/board); don't write assertions that depend on seeing a mid-cascade stack.

### `advance_to_phase(game, phase, step=None)`

Fast-forwards turn structure to reach a phase/step you want to test.

```python
advance_to_phase(game, phase: Phase, step: Step | None = None) -> None
```

> ⚠️ **Use sparingly, and know exactly what it runs.** Fast-forward **processes** the engine's turn-based actions, triggered abilities, and end-of-turn cleanup as it passes each phase/step, so state is correct on arrival (e.g. *until-end-of-turn* effects like sos_257 prowess actually reset). What it does **not** do is open **priority windows** — players take no directives during a fast-forward. The one exception: if a triggered ability *forces a choice* (target / selection / yes-no), that choice is still made, answered FIFO from the player's **choice script** (Channel 2); a dry choice script there fails the test like anywhere else. Only use fast-forward to *reach* the interesting part of the turn; never to skip behavior you assert on. If a player-initiated (priority) action would be needed in a skipped window, raise (test fails) rather than discard it.

> ⚔️ **Combat declarations are choice-script answers, not directives.** The canonical combat steps prompt the active/defending player through the public `choose`: `declare_attackers_step` asks for a **list** of attackers, `declare_blockers_step` for a **dict** `{blocker: attacker}`, and multi-block ordering comes from `assign_damage_order`. So attacking and blocking are scripted on **Channel 2** (the `choices` queue) and answered when `advance_to_phase(COMBAT, …)` runs the declare steps — **no new directive and no engine change**, since combat already flows through `choose`. One choice-script entry supplies the whole attacker list (or the whole block dict). sos_1's attack trigger then fires off the declared attacker, and its own targets/choices come from the same `choices` queue.

`game.run()`, `run_game()`, and `run_turn()` remain **prohibited** in audited tests (they hand control of the whole game to the players and make targeted assertions impossible). Keep the `pytest-timeout` backstop (currently 30s) so a runaway `priority_loop` fails fast instead of hanging the suite.

---

## Part 3 — DeterministicPlayer

Two **explicit, separate, ordered channels** drive a player. Keeping them separate is deliberate: a player-initiated priority action and an engine-prompted sub-decision are different things, scripted independently.

```python
DeterministicPlayer(
	name: str,
	script:  list[Directive] = (),   # CHANNEL 1 — directive queue: consumed each time this player HOLDS PRIORITY
	choices: list = (),              # CHANNEL 2 — choice script: FIFO answers for decisions the engine raises MID-CAST / MID-RESOLUTION
	life: int = 20,
)
```

- **Channel 1 — directive queue (****`script`****).** The host-side paradigm. Top-level actions the player *initiates* while holding priority: `no_op` / `perform_action` / `perform_illegal_action`. The driver polls this queue.
- **Channel 2 — choice script (****`choices`****).** Reuses the canonical answer deque the engine already consumes via `choose_target` / `choose` / `choose_yes_no` / `choose_card` / `assign_damage_order`. Answers sub-decisions the engine raises *during* a cast or resolution.
- **Dry on either channel = test fails** (`ScriptExhaustedError`). A missing directive and a missing choice are both hard failures, never silent passes.
### Priority directives

Each time the player **holds priority**, it consumes one directive:

- `no_op()` — pass priority without acting.
- `perform_action(action)` — take an action the test asserts is **legal**.
- `perform_illegal_action(action)` — take an action the test asserts is **illegal**.
Actions are reusable across both `perform_action` and `perform_illegal_action`:

```python
CastSpell(name, targets=[], x=None, mode=None, mana=None, from_zone=Zone.HAND)  # mana= is an OPTIONAL test-side disambiguator (default None = payment determined by pool contents / pre-cast mana abilities); a directive field composed over canonical cast_spell, never an engine change. from_zone≠HAND routes to a cast_spell_from_exile-style helper for alt-cost casts (sos_13 Prepared: back face from exile for {W})
CastSpellFree(name, from_zone=Zone.HAND)   # alt/free casts mapping to canonical cast_spell_free (e.g. sos_1 / sos_120 exile free-cast)
ActivateAbility(source, ability, targets=[], x=None)   # `ability` = index into source.get_activated_abilities() / get_loyalty_abilities() (printed order); also how MANA abilities are activated — they resolve immediately into the pool
PlayLand(name)
```

> 🎯 **Where targets come from.** The distinction is *who puts the object on the stack.* **Player-initiated** casts and activations carry their targets on the directive — `CastSpell(name, targets=[...])`, `ActivateAbility(source, ability, targets=[...])` — and the driver passes them to the canonical entrypoint. **Engine-initiated** objects (triggered abilities: sos_1's attack trigger, sos_257's prowess, sos_120's Paradigm recur) take no directive — the trigger goes on the stack on its own, so its targets and may-choices come from the **choice script** (Channel 2). This replaces the old `_resolve_targets` internal poke.

> 🧪 **Non-standard casts compose canonical helpers.** A player can cast from a non-hand zone or at an alternative cost — sos_13 Emeritus // Swords (*Prepared*) casts its back face from **exile** for {W}. The test API supplies these as thin helpers that duplicate the canonical cast path for the alternate zone/cost (`cast_spell_from_exile`, a copy of `cast_spell` that pulls from exile); the engine is never touched. `CastSpell(..., from_zone=Zone.EXILE)` and `CastSpellFree(from_zone=...)` resolve to these helpers.

**Measuring mana spent (no ****`mana_spent`**** on canonical).** The canonical `StackObject` has no `mana_spent` field, so there is no `assert_mana_spent`. To exercise mechanics keyed on mana paid, script the player to **activate the relevant mana abilities** (they resolve straight into the pool), then assert the **pool delta** across the cast with `assert_mana_pool`. Effects whose *output* depends on mana spent (e.g. sos_57 Mana Sculpt's {C} refund) are observed directly: set the opponent's spell cost in the test, then assert the resulting pool — the engine derives the amount from its own internal tracking. For **color-counting** mechanics (sos_4 Together as One, Converge X = number of colors spent), pin the colors either way — both valid: pre-set the pool to *exactly* the colored mana the cast needs (mana-minimality, the established discriminator), or script the player to activate specific mana abilities so only those colors are floated — then assert with `assert_colors_spent`. Either way the engine has only one legal payment, so `len(colors_spent)` is deterministic.

### Failure semantics

| Directive | Engine outcome | Result |
| --- | --- | --- |
| `perform_action` | Action is legal and executes | Continue |
| `perform_action` | Engine rejects it as illegal (invalid target, wrong timing, can't pay, etc.) | **TEST FAILS** |
| `perform_illegal_action` | Engine rejects it as illegal | Rejection is swallowed; continue |
| `perform_illegal_action` | Action is accepted / executes | **TEST FAILS** |
| any (script or choices dry) | Engine requests a decision | **TEST FAILS** (`ScriptExhaustedError`) |

This makes both directions of legality a first-class, observable assertion: `perform_illegal_action(CastSpell("Lightning Bolt", targets=["a land"]))` *is* the test that bolt cannot target a land.

> ⚖️ **"Illegal" spans two canonical signals.** Cast/play directives surface rejection as `CastingError`; activate / mana-ability directives surface it as `AbilityError`. The driver treats **either** as the rejection signal — the test author never catches these exceptions directly.
> **Combat is the exception:** the engine **silently filters** illegal attackers/blockers (a non-flyer assigned to a flyer, a summoning-sick or tapped attacker) with no exception raised, so `perform_illegal_action` does not apply to combat — assert combat illegality by **outcome** instead (e.g. the flyer's damage reached the player because the illegal block was dropped). `perform_illegal_action` stays for exception-signaled illegality, including sos_97's once-per-turn loyalty re-activation, which does raise `AbilityError`.

### Resolution-time choices

Forced decisions raised while a spell/ability resolves (modal choice, choose target for a trigger, yes/no, discard, damage-assignment order) are answered FIFO from the `choices` queue, via the existing `choose_target` / `choose` / `choose_yes_no` / `choose_card` / `assign_damage_order` hooks. Bundle a casting spell's own targets/X/mode in the `CastSpell` action; use `choices` for everything the engine asks *after* — including cast-time choices baked into the cast pipeline (casualty's "sacrifice which creature?" for sos_226, miracle's "cast for its miracle cost?" yes/no for sos_201, discard / new-target picks).

> 🩸 **Casualty (sos_226) and other engine-initiated additional-cost choices route through the public choice API.** Casualty's "sacrifice which creature?" prompt is raised *inside* the cast pipeline, so it is answered from the choice script (Channel 2) via the public `choose` / `choose_card` interface — never a private `_script` / `_pop()` poke. The oracle's current `_handle_casualty` special-cases `DeterministicPlayer` and pops a flat private `_script`; it is updated to drop that poke and prompt through public `choose()` (an oracle-engine change — canonical is untouched), which is also what makes the test portable: every candidate engine raises the choice the same public way. **Test recipe:** set up the granter + a sacrificeable creature (power ≥ 1) + a subject instant/sorcery, `CastSpell` it, answer the sacrifice from `choices`, then assert observable outcomes — sacrificed creature in the graveyard and the spell's effect applied **twice** (`assert_on_stack` count of 2, or the doubled board/life result). The oracle copies the spell with the *same* targets, so do not assert retargeting.

---

## Part 4 — Asserting results

All assertions read observable state through public accessors only.

| Area | Assertion | Checks |
| --- | --- | --- |
| Zones | `assert_in_zone(game, player, zone, card, count=1)` | A card is in a zone (optionally N copies) |
| Zones | `assert_zone_count(game, player, zone, n)` | Total object count in a zone |
| Zones | `assert_zone_exact(game, player, zone, [cards])` | Zone contents match exactly (order-insensitive) |
| Library | `assert_library_order(game, player, [top..bottom])` | Ordered library contents |
| Permanent | `assert_tapped(game, perm, tapped=True)` | Tapped / untapped state |
| Permanent | `assert_counters(game, perm, {"+1/+1": 2})` | Counter amounts. Canonical tracks only `+1/+1`, `-1/-1`, `loyalty`; arbitrary counter types are out of scope (deferred — add only if a future audited card forces it). Assert a counter's observable *effect* (P/T, mana, ability), not its presence |
| Permanent | `assert_damage(game, perm, n)` | Marked damage |
| Permanent | `assert_power_toughness(game, perm, power, toughness)` | Current P/T (after all effects) |
| Stack | `assert_stack(game, [names top..bottom])` | Ordered stack contents |
| Stack | `assert_on_stack(game, name)` / `assert_stack_empty(game)` | Presence on / emptiness of the stack (count copies for casualty) |
| Mana | `assert_mana_pool(game, player, {ManaType.RED: 1})` | Mana remaining in pool — also the basis for the mana-spent pool-delta pattern |
| Mana | `assert_colors_spent(game, [Color.RED])` | Colors of the last payment (from `last_payment_colors`) |
| Life | `assert_life_total(game, player, n)` | A player's life total |

> 🧭 **Implementation-agnostic guardrail.** Assert on *outcomes*, never on *mechanism*. "The bear is in the graveyard" is an outcome; "the engine called `destroy()` once" is a mechanism. Illegality is asserted via `perform_illegal_action` for exception-signaled actions (casts, activations), or by **outcome** for silently-filtered ones (illegal attacks/blocks) — never by catching engine-internal exceptions.

---

## The allow-list

Audited tests may use **only** the following to touch the engine. Anything else is a violation.

- **Setup:** `create_game`, `set_board_state`, `set_player`, `PermanentSpec` (no `set_stack` / `StackObjectSpec` — reach stacked states by casting)
- **Advance:** `priority_loop`, `advance_to_phase`
- **Players & actions:** `DeterministicPlayer`, `no_op`, `perform_action`, `perform_illegal_action`, `CastSpell`, `CastSpellFree`, `ActivateAbility`, `PlayLand`
- **Assertions:** the `assert_*` family above (no `assert_mana_spent` — measure mana via pool deltas)
- **Enums/value types:** `Phase`, `Step`, `Zone`, `ManaType`, `Color`, `CardType`, `Keyword`
---

## Relationship to existing conventions

- **Revises **[**TESTING-CONVENTIONS.md**](https://app.notion.com/p/c6553b4b515e4a7abdda59586e01d779)** Rule 5.** Entering the priority loop is now *required*, not forbidden — but only via `priority_loop` / `advance_to_phase`. `game.run()` / `run_game()` / `run_turn()` stay banned.
- **Replaces the free-function step helpers for audited tests.** The old `cast_spell(game, ...)` and `resolve_top(game)` shortcuts bypass priority and are no longer permitted in audited tests; casting and resolution now happen through `DeterministicPlayer` directives inside `priority_loop`. (Those helpers may still exist for the engine's own internal unit tests — they are simply outside the audited allow-list.)
- **Keep the ****`pytest-timeout`**** 30s backstop** so a misused loop fails fast.
## Open questions

- [x] ~~Canonical counter key names~~ — resolved: canonical tracks only `+1/+1`, `-1/-1`, `loyalty`; string keys for those three.
- [x] ~~`advance_to_phase`~~~~ semantics~~ — resolved: processes turn-based actions, triggers & end-of-turn cleanup (state correct on arrival) but opens no priority windows; a triggered ability that forces a choice is still answered from the choice script (dry → fail).
- [x] ~~How to identify an activated ability~~ — resolved: `ability` is an index into the card's `get_activated_abilities()` / `get_loyalty_abilities()` (printed order assumed, e.g. Ral Zarek +1/−1/−2/−7); no engine change, no text matching, no new id.
- [x] ~~`SpecialAction`~~~~ directive~~ — resolved: not needed. None of the 10 audited cards require a special action, so the directive vocabulary stays `CastSpell` / `CastSpellFree` / `ActivateAbility` / `PlayLand`. Add one narrowly only if/when a future card needs it (YAGNI).
- [x] ~~Combat declarations & combat illegality~~ — resolved: attackers/blockers are choice-script answers (attackers = a list, blockers = a `{blocker: attacker}` dict, ordering via `assign_damage_order`), reached via `advance_to_phase(COMBAT, …)` — no new directive, no engine change. Illegal attacks/blocks are **silently filtered** by the engine, so they are asserted by *outcome*; `perform_illegal_action` is reserved for exception-signaled illegality (`CastingError` / `AbilityError`).
- [x] ~~Multi-player turn control~~ — resolved: **deferred (YAGNI)**. All 10 audited cards test within P0's turn (P0 attacks, P1 defends via the choice script), and `create_game` starts P0 active; no `set_active_player` / start-of-turn helper until a future card needs P1's turn or a turn-boundary crossing. Tracked on the Backlog.
- [x] ~~Simultaneous-trigger ordering~~ — resolved: **deferred (YAGNI)**. No audited card stacks multiple simultaneous triggers needing a chosen APNAP / controller order; ordering machinery is unspecified until a future card forces it. Tracked on the Backlog.
