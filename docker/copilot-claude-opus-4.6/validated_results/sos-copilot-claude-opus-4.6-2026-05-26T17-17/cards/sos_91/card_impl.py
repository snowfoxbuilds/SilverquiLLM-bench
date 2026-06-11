"""Card implementation for Moseo, Vein's New Dean."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import AttacksTriggeredEvent, EndStepTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class MoseoVeinsNewDean(Creature):
    """Moseo, Vein's New Dean — {2}{B} — Legendary Creature — Bird Skeleton Warlock.

    2/1, Flying.
    When Moseo enters, create a 1/1 black and green Pest creature token with
    "Whenever this token attacks, you gain 1 life."
    Infusion — At the beginning of your end step, if you gained life this turn,
    return up to one target creature card with mana value X or less from your
    graveyard to the battlefield, where X is the amount of life you gained this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Moseo, Vein's New Dean")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Bird", "Skeleton", "Warlock"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING)
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Create a 1/1 Pest token with attack-life-gain trigger."""
        from engine.game import create_token

        controller = self.controller
        pest = _PestToken(owner=controller, controller=controller)
        create_token(game, controller, pest)

    def on_end_step(self, game: "GameState", active_player: Any) -> None:
        """Infusion: at beginning of your end step, if you gained life, reanimate."""
        controller = self.controller
        if active_player is not controller:
            return

        life_gained = getattr(controller, "life_gained_this_turn", 0)
        if life_gained <= 0:
            return

        # Find a creature card in graveyard with MV <= life gained
        graveyard = game.get_graveyard(controller)
        target = None
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.CREATURE not in card_types:
                continue
            mc = getattr(card, "mana_cost", None)
            if mc is None:
                mv = 0
            else:
                mv = mc.cmc
            if mv <= life_gained:
                target = card
                break

        if target is None:
            return

        # Move from graveyard to battlefield
        graveyard.remove(target)
        bf = game.get_battlefield(controller)
        target.controller = controller
        bf.add(target)
        if hasattr(target, "register_triggers"):
            target.register_triggers(game)

    def register_triggers(self, game: "GameState") -> None:
        """Register triggers (none needed beyond on_end_step hook)."""
        pass


class _PestToken(Creature):
    """1/1 black and green Pest creature token with attack life gain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pest")
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Pest"})
        super().__init__(**kwargs)
        self.is_token = True

    def register_triggers(self, game: "GameState") -> None:
        """Register 'Whenever this attacks, you gain 1 life.'"""
        controller = self.controller

        def _condition(g: "GameState", event: AttacksTriggeredEvent) -> bool:
            return event.creature is self or event.attacker is self

        def _effect(g: "GameState") -> None:
            owner = self.controller
            owner.life += 1
            if hasattr(owner, "life_gained_this_turn"):
                owner.life_gained_this_turn += 1
            else:
                owner.life_gained_this_turn = 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=AttacksTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
