# HOB medium implementation task

Implement all five selected cards in this workspace: The Eagles Are Coming!, Elrond, Moon-Reader, Gollum, Riddle Master, The Notary Hobbits, and Tom, Bert, and William. Each card's card_spec.json is the printed specification; instructions.md records the relevant rules and pitfalls found while building the oracle.

The existing engine deliberately lacks some required mechanics. You may change it freely. Grading measures card behavior, FDN regression and engine regression against your final engine. Keep each card's canonical class in its assigned card_impl.py. Hidden tests and oracle implementations are host-side; your own tests belong beside your HOB implementations.

Use Player Queries and Intents for every choice. Use the canonical zone transitions, token factory, counter, damage and life primitives so events and state-based actions remain observable. Preserve zone-stint identity for delayed returns and targets; matching a Python object or a card name alone is insufficient after a zone change. Preserve activation-time controllers and per-activation cost information.

The staged FDN tests and engine_tests are useful local regression checks. Run pytest from the workspace root. They do not expose the authoritative HOB tests. In particular, the staged advance_to_phase helper performs phase setup; use real turn/step events when exercising delayed triggers. RULEBOOK.txt is available for rules lookups.
