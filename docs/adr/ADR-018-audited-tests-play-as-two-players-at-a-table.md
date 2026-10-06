Status: ACCEPTED
Date: 2026-10-05

# ADR-018: Audited Tests Play as Two Players at a Table

## Context

Audited Tests wrote the step, the active player, the mana pool and zones mid-game, called the engine's stepping functions, and read power, counters, keywords, effects and engine events directly.
Each direct write was a separate driver of the step lifecycle, and the source of the handoff bugs #160's review rounds kept finding (#167); each direct read tied a hidden test to an attribute a candidate's engine rewrite need not keep.

## Decision

An Audited Test plays two novice players who have come to a board state: the engine tells them what they may do and what happens, and they notice only what is visible on the table.
A test constructs the whole position, including the step and active player, before play; afterwards state changes only through play, driven by one `run` driver.
The test takes no actions itself: each player's script answers every question the engine asks — actions, targets, trigger order, damage division alike, with no Intents or defaults — and the test fails as soon as play leaves the script.
A test reads the game only through the Player View — zones and their objects by predefined class, tapped status, life totals, the step and whose turn it is, and the game's result — compares it with the view it expects at every action question, and judges every other property, such as power, counters or keywords, by what it causes in play.
The rule binds Audited Tests from smoke and fra-hard-v2 onward; Reference Tests and Agent Tests are free of it.

## Consequences

- **Positive**: A candidate engine need keep only a handful of names — the Test Interface's engine surface — for every Audited Test to run against it.
- **Positive**: A test passes only when the behavior shows up in play, so an engine that stores the right number but never acts on it fails.
- **Positive**: No test can advance the game outside the one step lifecycle.
- **Negative**: Tests are longer and use supporting cards; a property such as a +1/+1 counter takes a combat to show.
- **Negative**: Every existing Audited Test that writes state, calls engine stepping or reads hidden details must be rewritten.
- **Neutral**: Reference Tests keep their current form, so the workspace's own tests and the hidden ones differ in style.

## Alternatives Considered

- **Keep direct reads and writes, routed through engine-owned setup helpers**: Rejected, because each helper remains a way into the lifecycle and hidden tests stay coupled to engine attributes.
- **Reach every position by playing from turn 1**: Rejected, because every test would run turn 1's upkeep and draw, firing triggers unrelated to the behavior under test, and could not start with mana in a pool.
- **Expose counters, power and toughness in the view**: Rejected, because a test could then pass an engine that records a value but never applies it.
