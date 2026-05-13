"""Card implementation for MildManneredLibrarian."""

from __future__ import annotations


from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from typing import TYPE_CHECKING, Any
import random



class MildManneredLibrarian(Creature):
    """Mild-Mannered Librarian — {G} — 1/1 — Human Werewolf

    {3}{G}: This creature becomes a Werewolf. Put two +1/+1 counters on
    it and you draw a card. Activate only once.

    FDN collector number 228.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mild-Mannered Librarian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault("subtypes", {"Human", "Werewolf"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{3}{G}: This creature becomes a Werewolf. Put two +1/+1 "
            "counters on it and you draw a card. Activate only once.",
        )
        super().__init__(**kwargs)
        self._librarian_activated = False

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if source._librarian_activated:
                return False
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 4:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{3}{G}"))
            source._librarian_activated = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import add_counter, draw_card

            # Becomes a Werewolf (add subtype, remove Human)
            source.subtypes.discard("Human")
            source.subtypes.add("Werewolf")
            # Put two +1/+1 counters
            add_counter(game, source, "+1/+1", 2)
            # Draw a card
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{3}{G}: This creature becomes a Werewolf. Put "
            "two +1/+1 counters on it and you draw a card. Activate "
            "only once.",
        )]


__all__ = ["MildManneredLibrarian"]
