"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import copy as _copy_module
from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault("rules_text", "Exile target creature. Its controller gains life equal to its power.")
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if target is None:
            return

        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)

        exile(game, target)

        if target_controller is not None and power > 0:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}
    Creature — Cat Cleric 3/3.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        # The card's full name is the double-faced name.
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", set())
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        from engine.types import Keyword

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _etb_effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Choose target player to receive token.
            try:
                target_player = ctrl.choose(list(g.players), "Choose a player to create an Inkling token")
            except Exception:
                target_player = ctrl

            # Create a 1/1 white-black Inkling with flying.
            inkling = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            create_token(g, target_player, inkling)

            # Check if an opponent controls more creatures than you.
            ctrl_creatures = sum(
                1
                for obj in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )
            for opponent in g.players:
                if opponent is ctrl:
                    continue
                opp_creatures = sum(
                    1
                    for obj in g.get_battlefield(opponent).get_all()
                    if CardType.CREATURE in getattr(obj, "card_types", set())
                )
                if opp_creatures > ctrl_creatures:
                    source._prepared = True
                    break

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_etb_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list:
        """If prepared, expose ability to cast a copy of Swords to Plowshares."""
        from engine.card import ActivatedAbility

        source = self

        def _can_cast_prepared(game: "GameState") -> bool:
            return source._prepared and CardType.CREATURE in source.card_types

        def _cast_prepared(game: "GameState") -> None:
            if not source._prepared:
                return
            ctrl = source.controller
            if ctrl is None:
                return

            # Create a copy of Swords to Plowshares, put in exile, cast from exile.
            swords_copy = SwordsToPlowshares()
            swords_copy.owner = ctrl
            swords_copy.controller = ctrl

            exile_zone = game.get_exile(ctrl)
            exile_zone.add(swords_copy)

            try:
                from engine.casting import cast_spell_free
                cast_spell_free(game, ctrl, swords_copy, Zone.EXILE)
                source._prepared = False
            except Exception:
                # If cast fails, remove from exile and keep prepared.
                if exile_zone.contains(swords_copy):
                    exile_zone.remove(swords_copy)

        return [
            ActivatedAbility(
                cost=_can_cast_prepared,
                effect=_cast_prepared,
                description="Cast a copy of Swords to Plowshares (unprepares).",
            )
        ]
