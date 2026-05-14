"""Card implementation for Spinner of Souls."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class SpinnerOfSouls(Creature):
    """Spinner of Souls — {2}{G} — 4/3 — Spider Spirit — Reach

    Whenever another nontoken creature you control dies, you may reveal
    cards from the top of your library until you reveal a creature card.
    Put that card into your hand and the rest on the bottom of your
    library in a random order.

    FDN collector number 112.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Spinner of Souls")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("subtypes", {"Spider", "Spirit"})
        kwargs.setdefault("keywords", Keyword.REACH)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Reach\nWhenever another nontoken creature you control dies, "
            "you may reveal cards from the top of your library until you "
            "reveal a creature card. Put that card into your hand and "
            "the rest on the bottom of your library in a random order.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False
            controller = getattr(source, "controller", None)
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            if getattr(creature, "is_token", False):
                return False
            return True

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            hand = controller.zones[Zone.HAND]
            revealed: list[Any] = []
            found_creature = None
            while len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                card_types = getattr(card, "card_types", set())
                if CardType.CREATURE in card_types:
                    found_creature = card
                    break
                revealed.append(card)
            # Put found creature into hand
            if found_creature is not None:
                hand.add(found_creature)
            # Put the rest on the bottom in random order
            import random
            random.shuffle(revealed)
            for card in revealed:
                library.add(card, position="bottom")

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
