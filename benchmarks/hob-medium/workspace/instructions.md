# HOB medium implementation task

Implement all five selected cards in this workspace: The Eagles Are Coming!; Elrond, Moon-Reader; Gollum, Riddle Master; The Notary Hobbits; and Tom, Bert, and William. Each card's card_spec.json is the printed specification, and its instructions.md records relevant rules and pitfalls.

The existing engine lacks some mechanics these cards need. You may change it freely. Keep each card's class in its assigned card_impl.py. Your own tests belong beside your HOB implementations.

Use Player Queries and Intents for every choice. Use the canonical zone transitions, token factory, counter, damage and life primitives so events and state-based actions remain observable. Preserve zone-stint identity for delayed returns and targets; matching a Python object or a card name alone is insufficient after a zone change. Preserve activation-time controllers and per-activation cost information.

The FDN tests and engine_tests are useful regression checks. Run `python3 -m pytest` from the workspace root. In test_utils, advance_to_phase only sets the phase; advance_game_to_phase drives real turn and step events, so use it when exercising delayed triggers. RULEBOOK.txt is available for rules lookups.
