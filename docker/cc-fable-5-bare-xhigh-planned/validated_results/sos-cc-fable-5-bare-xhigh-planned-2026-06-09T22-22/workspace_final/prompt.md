Implement the following SOS cards: 1, 4, 13, 57, 97, 120, 201, 226, 245, 257 in `/workspace/cards/sos/`. Each card directory contains a `card_spec.json` with the card's details and a `card_impl.py` template to fill in.
Use the completed FDN cards in `/workspace/cards/fdn/` as implementation examples. Refer to `RULEBOOK.txt` for the full deep-reference rules text.
For engine API discovery, read the source modules directly — they have rich docstrings: `engine/card.py`, `engine/events.py`, `engine/triggers.py`, `engine/replacement_effects.py`, `engine/zones.py`.
You are expected to make changes to the engine to implement new keywords and mechanics. The existing code base may not be perfect, you are free to make changes that don't break current behavior.

Do not modify any files under workspace/engine_tests/. These tests are staged for your local verification only; the runner uses its own authoritative copies for grading. Modifying the workspace tests will not change your score — it will only mislead you about whether your engine changes are correct.
