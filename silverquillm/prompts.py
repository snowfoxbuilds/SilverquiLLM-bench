"""Parameterized prompt templates for the benchmark runner.

Templates use ``str.format_map`` with ``{placeholder}`` substitution.
No f-strings with complex logic — all prompts are plain template strings.
"""

from silverquillm.template_gen import card_name_to_class_name

# ---------------------------------------------------------------------------
# Step 1 — Blind implementation prompt
# ---------------------------------------------------------------------------

_BLIND_IMPLEMENTATION_TEMPLATE = """\
You are implementing a Magic: The Gathering card for the SilverquiLLM-bench game engine.

Card: {card_name}
Mana Cost: {mana_cost}
Type: {type_line}
Rules Text: {oracle_text}

Implement this card by completing the class in template.py.
You have access to:
- engine_api.md (game engine API reference)
- engine/ (game engine source — you may extend it if this card needs mechanics not yet supported)
- base_classes.py (card base classes)
- rules_overview.md + rules lookup tool (search MTG rules by keyword/number)
- foundations/ (browse working card implementations as reference)
- card_spec.json (contains details on the cards you are implementing)
- template.py (contains the starter template for your card implementation)
- test_utils.py (you are not asked to write tests yet)

Write your implementation to `blind_impl.py`.
If you need to add or modify engine files, do so — but all previous cards' tests
will be re-run, so your engine changes must not break existing functionality.
Do not rename the class. Do not write tests."""


def blind_implementation_prompt(card_spec: dict) -> str:
    """Build the Step 1 (blind implementation) prompt from *card_spec*.

    Parameters
    ----------
    card_spec:
        Card specification dictionary.  Must contain at least ``name``,
        ``mana_cost``, ``type_line``, and ``oracle_text``.

    Returns
    -------
    str
        Fully-substituted prompt with no remaining ``{placeholder}`` tokens.
    """
    return _BLIND_IMPLEMENTATION_TEMPLATE.format_map(
        {
            "card_name": card_spec["name"],
            "mana_cost": card_spec["mana_cost"],
            "type_line": card_spec["type_line"],
            "oracle_text": card_spec["oracle_text"],
        }
    )


# ---------------------------------------------------------------------------
# Step 2 — Test-informed implementation prompt
# ---------------------------------------------------------------------------

_TEST_INFORMED_TEMPLATE = """\
Now write a comprehensive test suite for your implementation of {card_name}.

Constraints:
- You MUST use the test_utils helpers (create_game, set_board_state, cast_spell, etc.)
  See test_utils.md for the full API.
- Maximum 30 tests per card. Focus on quality over quantity.
- Tests must import from card_impl (e.g. `from card_impl import {class_name}`)

Test for:
- Basic functionality (correct stats, mana cost, card types)
- Core abilities working correctly
- Edge cases (no valid targets, empty board, etc.)
- Interaction with game rules (stack, priority, state-based actions)

You have access to:
- engine_api.md (game engine API reference)
- engine/ (game engine source — you may extend it if this card needs mechanics not yet supported)
- base_classes.py (card base classes)
- rules_overview.md + rules lookup tool (search MTG rules by keyword/number)
- foundations/ (browse working card implementations as reference)
- card_spec.json (contains details on the cards you are implementing)
- template.py (contains the starter template for your card implementation)
- test_utils.py (you are not asked to write tests yet)

Save your updated implementation to `tested_impl.py`.
Save your tests to `tests.py`.
You may also modify engine/ files if needed — but all previous cards' tests
will be re-run, so engine changes must not break existing functionality.
You have up to {max_rounds} rounds to iterate on both tests and code.
"""

_TEST_INFORMED_FEEDBACK_SECTION = """

Previous test results (round {round_num}):
{prev_test_results}

Use these results to fix failing tests or update your implementation."""


def test_informed_prompt(
    card_spec: dict,
    round_num: int,
    max_rounds: int = 3,
    prev_test_results: str | None = None,
) -> str:
    """Build the Step 2 (test-informed) prompt from *card_spec*.

    Parameters
    ----------
    card_spec:
        Card specification dictionary.  Must contain ``name``.
    round_num:
        Current iteration round (1-indexed).
    max_rounds:
        Total allowed rounds from the benchmark config.
    prev_test_results:
        Optional raw test output from the previous round.  When provided the
        prompt includes a feedback section so the agent can see what
        passed/failed.

    Returns
    -------
    str
        Fully-substituted prompt.
    """
    # Derive PascalCase class name from card name
    class_name = card_name_to_class_name(card_spec["name"])

    base = _TEST_INFORMED_TEMPLATE.format_map(
        {
            "card_name": card_spec["name"],
            "class_name": class_name,
            "max_rounds": max_rounds,
        }
    )

    if prev_test_results is not None:
        base += _TEST_INFORMED_FEEDBACK_SECTION.format_map(
            {
                "round_num": round_num,
                "prev_test_results": prev_test_results,
            }
        )

    return base


# ---------------------------------------------------------------------------
# Iteration feedback prompt (between rounds)
# ---------------------------------------------------------------------------

_ITERATION_FEEDBACK_TEMPLATE = """\
Test run results (round {round_num} of {max_rounds}):

{test_output}

Fix the failing tests or update your implementation, then resubmit both files.

Write your tests to `tests.py`.
If you update your implementation, save it to `tested_impl.py`.
You may also modify engine/ files if needed — but all previous cards' tests
will be re-run, so engine changes must not break existing functionality.
"""


def iteration_feedback_prompt(
    test_output: str,
    round_num: int,
    max_rounds: int,
) -> str:
    """Build the iteration-feedback prompt shown between test rounds.

    Parameters
    ----------
    test_output:
        Raw test runner output (passed/failed summary, tracebacks, etc.).
    round_num:
        Current round number (1-indexed).
    max_rounds:
        Maximum allowed rounds.

    Returns
    -------
    str
        Fully-substituted feedback prompt.
    """
    return _ITERATION_FEEDBACK_TEMPLATE.format_map(
        {
            "round_num": round_num,
            "max_rounds": max_rounds,
            "test_output": test_output,
        }
    )
