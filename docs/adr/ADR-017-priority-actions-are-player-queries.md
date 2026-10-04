Status: ACCEPTED
Date: 2026-10-03

# ADR-017: Priority Actions Are Player Queries

## Context

The V2 engine never asked a player what to do with priority: audited tests cast spells by calling the engine's `cast_spell(game, player, card)` directly, and only forced choices went through Player Queries.
That fixed the casting call as part of the test contract, so a casting design the rules allow could not pass.
On fra-hard, most candidates selected Glamdring's Adventure through a new keyword argument on `cast_spell` (each spelled differently), while the audited tests expected a face question raised inside the unchanged call; the rules (CR 715.3a) only require that the player choose the face as part of casting, which both designs do.

## Decision

When a player receives priority, the engine raises a Player Query whose options are the actions available to that player, and audited tests choose an action through an Intent, the same way they answer any other choice.
The engine, not the test, turns the chosen action into its own casting or activation call, so a candidate may shape that call freely.

Actions reuse the existing Decision kinds: casting a spell or playing a land is an OBJECT option, activating an ability is an ABILITY option, and passing is a decline.
Each face of a multi-face card is a distinct engine object, so an engine may offer each face at priority or offer the card and then ask which face.
A test states its goal once as ordered preferences (for example: cast Gleam of Death, otherwise cast Glamdring and choose Gleam of Death), and the same preferences answer whichever questions the engine asks.
The test then judges the outcome: the intended face is on the stack, or the test fails.

Every card, face and printed line of text has a predefined, behavior-free class in the Workspace, and tests place, choose and assert by those classes, never by raw strings; how a candidate relates the classes, and how its engine presents a multi-face card in any query, is its own design.
Tests draw out the intended choice and fail only when an illegal choice takes effect, never because of how a choice was presented.

Combat declarations follow the same rule: the engine asks which creatures attack or block, instead of the test handing it a list.

The protocol is part of the [Decision Model](../specs/DECISION-MODEL.md) and the Known-Best Engine, and applies to smoke, fra-hard-v2 and every later benchmark.
fra-hard v1, the HOB tiers and SOS keep their directive-driven priority.

## Consequences

- **Positive**: Audited tests no longer depend on the casting call's signature, so any rules-correct way of choosing a face, mode or alternative cost can pass.
- **Positive**: Legality is judged by what the engine allows to take effect: an engine may offer and accept an illegal choice as long as it rejects it with `InvalidPlayerChoiceError`, so tests need not police how options are presented.
- **Negative**: Every audited test, `test_utils` helper and regression suite that casts or activates must move to the priority query, and the Known-Best and fra-hard engines must offer and execute actions.
- **Negative**: Runs graded before the change cannot pass tests that drive play through a priority query their engines lack; fra-hard-v2 is a separate benchmark, and fra-hard v1 runs keep their old grades instead of being regraded.
- **Neutral**: Candidates still follow a documented interface — the action options — but the contract now sits at the player's choice instead of the engine's function signature.

## Alternatives Considered

- **Document that the ordinary cast raises a face question**: Rejected, because it keeps the casting signature in the test contract and fails engines whose only difference is how the player's choice reaches the cast.
- **Define a canonical face argument on `cast_spell`, as `CastMode` does**: Rejected for the same reason in reverse: it fails engines that ask the player during casting.
- **A new ACTION Decision kind carrying the face as an attribute**: Rejected, because faces are distinct objects, so OBJECT and ABILITY options plus a decline already express every priority action, without a benchmark-version event for a new kind.
- **Adapt tests per run to each candidate's keyword**: Rejected, because the keyword is unknowable in advance and the adaptation does not generalize.
