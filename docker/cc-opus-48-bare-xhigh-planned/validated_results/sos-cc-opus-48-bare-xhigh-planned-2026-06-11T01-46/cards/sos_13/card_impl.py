"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _creature_count(game: "GameState", player: "Player") -> int:
    return sum(
        1 for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the back face of sos_13).

    Exile target creature.  Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
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

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        # Verify still on a battlefield.
        on_bf = any(game.get_battlefield(p).contains(target) for p in game.players)
        if not on_bf:
            return
        owner_player = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if owner_player is not None:
            owner_player.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying.  Then if an opponent controls more
    creatures than you, this creature becomes prepared.  (While it's prepared,
    you may cast a copy of its spell.  Doing so unprepares it.)

    SOS collector number 13.  The card name is the whole ``front // back``
    string so the engine/tests can find it by name.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def on_cast(self, game: "GameState") -> None:
        """Register the ETB trigger here so it catches this creature's own
        entry — the engine fires the ETB event before calling
        ``register_triggers`` on the entering permanent."""
        from engine.triggers import TriggerRegistration
        from engine.events import EntersBattlefieldTriggeredEvent

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _effect(g: "GameState") -> None:
            self._etb(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or game.active_player,
            )
        )

    def _etb(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates the token.
        target_player = controller.choose(
            list(game.players), "Target player creates an Inkling token"
        )
        if target_player not in game.players:
            target_player = controller

        inkling = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, inkling)

        # Then if an opponent controls more creatures than you, become prepared.
        you = _creature_count(game, controller)
        opponent = max(
            (_creature_count(game, p) for p in game.players if p is not controller),
            default=0,
        )
        if opponent > you:
            self._prepared = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """While prepared, you may cast a copy of Swords to Plowshares."""
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None or not getattr(src, "_prepared", False):
                return False
            return game.get_battlefield(ctrl).contains(src)

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            if ctrl is None or not source._prepared:
                return
            swords = SwordsToPlowshares(owner=ctrl, controller=ctrl)
            swords.is_token = True  # the copy ceases to exist after resolving
            game.get_exile(ctrl).add(swords)
            source._prepared = False  # casting the copy unprepares it
            cast_spell_free(game, ctrl, swords, Zone.EXILE)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="While prepared: cast a copy of Swords to Plowshares.",
            )
        ]
