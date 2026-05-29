# Run Decisions

Decisions made during this run only. Before the run ends, migrate anything worth preserving into `KEY_DECISIONS.md`.


## Untestable partial: sos_1
- Requirement: "you may" optionality for cast-from-graveyard trigger (declining the cast)
- Decision: Accept partial coverage (b). The main path (casting) is tested; declining is hard to script without knowing internal choice key.
- Marker will be added to card_impl.py: `# UNVERIFIED: player may decline the cast trigger — DeterministicPlayer lacks clear 'decline may-trigger' script path`

## Untestable partial: sos_13
1. Token dual-color (white+black): Accept partial coverage. The engine doesn't expose a colors field on tokens. UNVERIFIED marker added.
2. "You may" optionality for prepared ability: Accept partial coverage same as sos_1 precedent.

## Untestable partial: sos_57
1. BeginningOfMainPhaseTriggeredEvent missing: Implementer needs to add this to engine/events.py and fire it from engine/turn.py. This is an engine addition (allowable). Directing Implementer to do this.
2. X-cost spell tracking: Accept partial coverage. Use CMC from mana_cost (treating X as 0). UNVERIFIED marker added.

## Untestable partial: sos_97
1. Surveil ordering: Accept partial coverage. Test verifies cards are put in graveyard/stay in library, not ordering.
2. -2 MV>3 filter: Accept partial coverage. Target filtering tested via direct resolution tests only.
3. -7 turn skip: Direct Implementer to add `turns_to_skip` field to Player and honor it in turn.py. UNVERIFIED marker for actual turn engine integration.

## Untestable partial: sos_120
1. Multi-cast player choice loop: Accept partial coverage. Tests verify cards are in exile and eligible; actual multi-cast loop is UNVERIFIED.
2. Paradigm copy-cast from exile: Accept partial coverage. Tests verify trigger registration and exile-on-resolution. Full copy-cast integration UNVERIFIED.

## Untestable partial: sos_201
- Miracle cast pipeline: Accept partial coverage. Tests verify miracle flag is set when card is drawn as first card of turn. Full cast-for-miracle-cost integration is UNVERIFIED. Marker added to impl.

## Untestable partial: sos_226
- Casualty sacrifice+copy mechanic: Accept partial coverage. Tests verify casualty_cost attribute is set; actual sacrifice+copy during casting needs engine additions (optional additional cost, sacrifice hook, copy-spell API). Directing Implementer to add basic casualty infrastructure. UNVERIFIED for full end-to-end.

## Untestable partial: sos_257
1. Conditional mana restriction: Accept partial coverage. Engine limitation - mana restriction to instants/sorceries cannot be enforced. UNVERIFIED marker.
2. +1/+0 until EOT expiry: Accept partial coverage. Tests verify pump happens on spell cast; EOT expiry verification deferred. UNVERIFIED marker.
