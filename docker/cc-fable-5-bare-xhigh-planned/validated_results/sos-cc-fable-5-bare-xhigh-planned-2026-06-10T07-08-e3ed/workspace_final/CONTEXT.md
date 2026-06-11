# SOS Card Implementation — Glossary

The shared vocabulary for implementing the ten SOS cards in this workspace.
This file is a **glossary only** — it defines what each term *is*, not how to
build it. The build plan, engine symbols, and per-card guidance live in
`TODO.md`. When `card_spec.json` oracle text uses one of these words, this is
what it means; confirm timing and edge cases against `RULEBOOK.txt`.

## Keyword mechanics on the target cards

**Converge**
A spell whose effect scales on *X = the number of different colors of mana
spent to cast it* (not its mana value). Appears on sos_4.

**Affinity for creatures**
A cost reduction: the spell costs {1} less to cast for each creature its
controller controls. Reduces generic mana only, never colored pips. On sos_245
(and, granted by sos_245, on its controller's instant/sorcery spells).

**Miracle**
An alternative cast opportunity: the first card a player draws in a turn may be
cast for its miracle cost instead of its normal cost, immediately upon being
drawn. On sos_201 it is *granted* to instant/sorcery cards in the controller's
hand.

**Casualty N**
As a spell is cast, its controller may sacrifice a creature with power N or
greater; when they do, the spell is copied and the controller may choose new
targets for the copy. On sos_226 it is granted (Casualty 1) to the controller's
instant/sorcery spells.

**Prepared** *(SOS-specific)*
A state a creature can be in. While a creature is prepared, its controller may
cast a copy of that creature's associated spell; doing so makes it un-prepared.
On sos_13.

**Paradigm** *(SOS-specific)*
After a spell with Paradigm first resolves, it is exiled, and at the beginning
of each of the controller's *first* main phases thereafter they may cast a copy
of it from exile without paying its mana cost. On sos_120.

**Surveil N**
Look at the top N cards of your library, then put any number of them into your
graveyard and the rest back on top in any order. On sos_97 (the +1 ability).

## Implementation terms

**SOS card**
A card in the SOS set, implemented in `cards/sos/sos_<N>/card_impl.py`. The ten
to build here are 1, 4, 13, 57, 97, 120, 201, 226, 245, 257.

**FDN reference card / analogue**
A completed, correct card in `cards/fdn/`. The reference library: the nearest
FDN card that already does a mechanic is the example to mirror.

**Spec**
`card_spec.json` — name, mana cost, type line, and `oracle_text`. Together with
`RULEBOOK.txt`, the spec is the **source of truth** for a card's behavior. Not
your own tests, and not this plan.

**Shared seam**
An existing engine extension point (a card hook, a registry, or a helper
function) that more than one target card reuses. Building or learning a seam
once and reusing it is the goal.

**Engine gap**
A mechanic no existing seam covers. Each gap on these ten cards is needed by
exactly one card; a gap is filled with the smallest card-local change, never a
general subsystem.

**Cost reduction**
Lowering the generic-mana portion of a spell's cost by some count. The engine
clamps it at zero and never reduces colored pips.

**Free cast**
Putting a card onto the stack and resolving it without paying its mana cost,
often from a zone other than hand (graveyard, exile).

**Spell copy**
A copy of a spell placed on the stack; it resolves on its own and never moves
between zones. New targets may be chosen for the copy.

**Additive-only engine rule**
The engine may be extended (new methods, classes, helpers, files) and existing
function bodies may be edited, but nothing existing may be renamed, moved, or
deleted. Other modules import engine symbols by name, so a rename or move breaks
those imports.

**Card location invariant**
Each card's class must remain importable from its own
`cards/sos/sos_<N>/card_impl.py`. Card directories are never moved or renamed.
