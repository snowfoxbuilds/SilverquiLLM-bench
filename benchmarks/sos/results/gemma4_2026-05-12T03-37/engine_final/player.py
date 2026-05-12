"""Player interface and deterministic test player implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from engine.mana import ManaPool
from engine.zones import Zones


class ScriptExhaustedError(Exception):
    """Raised when a DeterministicPlayer's script runs out of predetermined answers."""


class Player(ABC):
    """Abstract base class for all players in the game.

    Attributes:
        name: The player's display name.
        life: Current life total (default 20).
        zones: Per-player zone containers.
        mana_pool: The player's mana pool (forward ref; initialized to None until ManaPool is implemented).
        has_lost: Whether this player has lost the game.
        land_plays_remaining: Number of land plays remaining this turn.
        drawn_from_empty_library: Whether this player attempted to draw from an empty library.
    """

    def __init__(self, name: str, life: int = 20) -> None:
        self.name: str = name
        self.life: int = life
        self.zones: Zones = Zones.new_player()
        self.mana_pool: ManaPool = ManaPool()
        self.has_lost: bool = False
        self.land_plays_remaining: int = 1
        self.drawn_from_empty_library: bool = False
        self.turns_to_skip: int = 0

    @abstractmethod
    def choose_target(self, options: Any, requirement: Any) -> Any:
        """Choose a target from the available options given a requirement.

        Parameters:
            options: The available targets to choose from.
            requirement: The targeting requirement to satisfy.

        Returns:
            The chosen target.
        """

    @abstractmethod
    def choose(self, options: Any, description: str) -> Any:
        """Choose from a list of options.

        Parameters:
            options: The available choices.
            description: Human-readable description of the choice.

        Returns:
            The chosen option.
        """

    @abstractmethod
    def choose_yes_no(self, prompt: str) -> bool:
        """Make a yes/no decision.

        Parameters:
            prompt: Human-readable prompt for the decision.

        Returns:
            True for yes, False for no.
        """

    @abstractmethod
    def assign_damage_order(self, attackers_or_blockers: Any) -> list[Any]:
        """Assign a damage ordering to attackers or blockers.

        Parameters:
            attackers_or_blockers: The creatures to order.

        Returns:
            An ordered list representing the damage assignment order.
        """

    @abstractmethod
    def choose_card(self, cards: Any, description: str) -> Any:
        """Choose a card from a collection.

        Parameters:
            cards: The available cards to choose from.
            description: Human-readable description of why a card is being chosen.

        Returns:
            The chosen card.
        """


class DeterministicPlayer(Player):
    """A scripted player for testing that returns predetermined answers.

    Each abstract method call pops the next answer from the front of the
    script queue. Raises :class:`ScriptExhaustedError` if the script is empty
    when a choice is requested.
    """

    def __init__(self, name: str, script: list[Any], life: int = 20) -> None:
        super().__init__(name, life)
        self._script: deque[Any] = deque(script)

    def _pop(self) -> Any:
        """Pop the next scripted answer from the queue.

        Raises:
            ScriptExhaustedError: If the script has no remaining answers.
        """
        if not self._script:
            raise ScriptExhaustedError(
                f"Player {self.name!r} script exhausted — no more predetermined answers"
            )
        return self._script.popleft()

    @property
    def remaining_choices(self) -> int:
        """Return the number of scripted answers remaining."""
        return len(self._script)

    def choose_target(self, options: Any, requirement: Any) -> Any:
        """Return the next scripted target choice."""
        return self._pop()

    def choose(self, options: Any, description: str) -> Any:
        """Return the next scripted choice."""
        return self._pop()

    def choose_yes_no(self, prompt: str) -> bool:
        """Return the next scripted yes/no decision."""
        return self._pop()

    def assign_damage_order(self, attackers_or_blockers: Any) -> list[Any]:
        """Return the next scripted damage ordering."""
        return self._pop()

    def choose_card(self, cards: Any, description: str) -> Any:
        """Return the next scripted card choice."""
        return self._pop()
