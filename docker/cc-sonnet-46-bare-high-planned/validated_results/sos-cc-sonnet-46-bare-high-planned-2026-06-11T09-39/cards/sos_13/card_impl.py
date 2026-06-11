"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

import copy as _copy
from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone

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
        from engine.types import TargetRequirement
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile target creature; its controller gains life equal to its power."""
        from engine.zones import move_to_zone

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return
        target = chosen[0]
        if target is None:
            return

        target_controller = getattr(target, "controller", None)
        power = getattr(target, "modified_power", getattr(target, "base_power", 0))

        # Exile the creature
        bf = game.get_battlefield(target_controller or self.controller)
        if bf.contains(target):
            move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)

        # Its controller gains life equal to its power
        if target_controller is not None and power is not None and power > 0:
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.\n"
            "(While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger: create Inkling token + maybe become prepared."""
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _etb_condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _etb_effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Target player creates a 1/1 Inkling with Flying
            target_player = _choose_target_player(game, ctrl)
            _create_inkling(game, target_player)

            # Check if prepared condition is met
            source._prepared = _opponent_controls_more_creatures(game, ctrl)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_etb_condition,
                effect=_etb_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the Prepared activated ability: cast Swords to Plowshares copy."""
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Requires the creature to be prepared (no mana cost)."""
            return getattr(src, "_prepared", False)

        def _effect(game: Any) -> None:
            """Create a SwordsToPlowshares copy in exile and cast it free."""
            from engine.casting import cast_spell_free, CastingError

            controller = getattr(source, "controller", None)
            if controller is None:
                return

            source._prepared = False

            swords = SwordsToPlowshares()
            swords.owner = controller
            swords.controller = controller

            exile_zone = controller.zones[Zone.EXILE]
            exile_zone.add(swords)
            try:
                cast_spell_free(game, controller, swords, Zone.EXILE)
            except CastingError:
                if exile_zone.contains(swords):
                    exile_zone.remove(swords)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="While prepared, cast a copy of Swords to Plowshares. Unprepares it.",
            )
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _choose_target_player(game: Any, controller: Any) -> Any:
    """Prompt the controller to choose a target player."""
    players = game.players
    try:
        chosen = controller.choose(players, "Choose a player to create an Inkling token for")
        if chosen in players:
            return chosen
    except Exception:
        pass
    return controller  # fallback: self


def _create_inkling(game: Any, player: Any) -> None:
    """Create a 1/1 white-black Inkling creature token with flying under player's control."""
    from engine.game import create_token
    token = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        keywords=Keyword.FLYING,
        subtypes={"Inkling"},
    )
    create_token(game, player, token)


def _opponent_controls_more_creatures(game: Any, controller: Any) -> bool:
    """Return True if any opponent controls more creatures than controller."""
    ctrl_creatures = sum(
        1
        for p in game.players
        if p is controller
        for c in game.get_battlefield(p).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )
    for opp in game.players:
        if opp is controller:
            continue
        opp_creatures = sum(
            1
            for c in game.get_battlefield(opp).get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        )
        if opp_creatures > ctrl_creatures:
            return True
    return False
