# Workspace layout

engine/ contains the editable game engine; cards/fdn/ contains reference cards. engine_tests/ and existing cards/fdn/*/tests.py are regression tests.

The ten targets live in cards/fra/fra_<N>/ and cards/hob/hob_<N>/. Each has card_spec.json and card_impl.py; add your tests.py there. Specs with card_faces describe every component of one target card.

instructions.md and AGENTS.md describe the task. test_utils.py and test_utils.md provide test helpers. RULEBOOK.txt contains the Comprehensive Rules; skills/grep-rulebook explains rules lookup.
