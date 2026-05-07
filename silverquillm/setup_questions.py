"""Setup-questions validation for agent adapters.

Loads a JSON file of setup questions and sends each to an
:class:`~silverquillm.adapters.base.AgentAdapter`, checking whether the
response contains the expected keywords or matches an optional regex
pattern.  Returns ``True`` only when every question passes.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from silverquillm.adapters.base import AgentAdapter

logger = logging.getLogger(__name__)


def load_setup_questions(path: Path) -> list[dict[str, Any]]:
    """Load setup questions from a JSON file.

    Parameters
    ----------
    path:
        Path to a JSON file containing a list of question objects.
        Each object must have ``question`` (str) and
        ``expected_keywords`` (list[str]).  An optional
        ``answer_pattern`` (str) field is treated as a regex.

    Returns
    -------
    list[dict]
        The parsed list of question dicts.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the top-level structure is not a list, or if a question
        is missing required fields.
    """
    with open(path) as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON array in {path}, got {type(data).__name__}"
        )

    for idx, item in enumerate(data):
        if "question" not in item:
            raise ValueError(
                f"Question at index {idx} is missing required field 'question'"
            )
        if "expected_keywords" not in item:
            raise ValueError(
                f"Question at index {idx} is missing required field 'expected_keywords'"
            )

    return data


def _check_answer(answer: str, question: dict[str, Any]) -> bool:
    """Return ``True`` if *answer* satisfies the question's constraints."""
    answer_lower = answer.lower()

    # Check expected keywords (all must be present, case-insensitive)
    for kw in question["expected_keywords"]:
        if kw.lower() not in answer_lower:
            return False

    # Check optional regex pattern
    pattern = question.get("answer_pattern")
    if pattern is not None:
        if not re.search(pattern, answer, re.IGNORECASE):
            return False

    return True


def validate_setup(
    adapter: AgentAdapter,
    questions_path: Path,
    workspace: Path,
) -> bool:
    """Validate the agent can answer setup questions correctly.

    Loads questions from *questions_path*, sends each to *adapter*,
    and checks responses against expected keywords / patterns.

    Parameters
    ----------
    adapter:
        An already-set-up :class:`AgentAdapter`.
    questions_path:
        Path to the ``setup_questions.json`` file.
    workspace:
        Working directory passed to ``adapter.run()``.

    Returns
    -------
    bool
        ``True`` if **all** questions pass, ``False`` otherwise.
    """
    questions = load_setup_questions(questions_path)

    if not questions:
        logger.warning("No setup questions found in %s", questions_path)
        return True

    all_passed = True
    for idx, q in enumerate(questions, start=1):
        prompt = q["question"]
        logger.info(
            "Setup question %d/%d: %s", idx, len(questions), prompt
        )

        try:
            answer = adapter.run_with_retries(prompt, workspace, retries=0)
        except Exception:
            logger.exception(
                "Setup question %d/%d FAILED (adapter error)", idx, len(questions)
            )
            all_passed = False
            continue

        if _check_answer(answer, q):
            logger.info("Setup question %d/%d PASSED", idx, len(questions))
        else:
            logger.warning(
                "Setup question %d/%d FAILED — answer did not match expectations. "
                "Answer: %s",
                idx,
                len(questions),
                answer[:200],
            )
            all_passed = False

    return all_passed
