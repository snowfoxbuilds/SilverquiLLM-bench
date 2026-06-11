"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(
        1
        for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """The prepare spell of Emeritus of Truce — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.
    Only ever cast as a copy from exile via the prepared mechanic.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: "GameState") -> bool:
        """Needs a creature on the battlefield to target."""
        return any(
            CardType.CREATURE in getattr(c, "card_types", set())
            for p in game.players
            for c in game.get_battlefield(p).get_all()
        )

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
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
        # Fizzle if the creature already left the battlefield.
        if not any(
            game.get_battlefield(p).contains(target) for p in game.players
        ):
            return
        gained = max(0, getattr(target, "power", 0))
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += gained


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 —
    Creature — Cat Cleric // Instant.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced card's name is the whole "front // back" string.
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB effect, run at spell resolution (the engine's convention for
        "when this creature enters" on the entering card itself — its own
        triggers register only after the ETB event fires; mirrors fdn_205).
        """
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        req = TargetRequirement(
            filter_fn=_is_player,
            description="target player creates an Inkling token",
            zone=Zone.BATTLEFIELD,
        )
        chosen_player = ctrl.choose_target(list(game.players), req)
        if chosen_player is not None and _is_player(chosen_player):
            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            create_token(game, chosen_player, token)

        # "Then if an opponent controls more creatures than you ..."
        # This card is still on the stack here, so count it as ours.
        mine = _creature_count(game, ctrl)
        if not game.get_battlefield(ctrl).contains(self):
            mine += 1
        if any(
            _creature_count(game, opp) > mine
            for opp in game.players
            if opp is not ctrl
        ):
            self.prepared = True

    # ------------------------------------------------------------------
    # Prepared — cast a copy of the prepare spell
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            # Casting the copy is a normal cast (CR 722.3c): pay {W}.
            if not src.prepared:
                return False
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(pips={ManaType.WHITE: 1}))

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = source.controller
            if ctrl is None or not source.prepared:
                return
            # Create an actual copy of the prepare spell in exile and cast
            # it from there ({W} was paid as the activation cost).
            spell_copy = SwordsToPlowshares(owner=ctrl, controller=ctrl)
            ctrl.zones[Zone.EXILE].add(spell_copy)
            try:
                cast_spell_free(game, ctrl, spell_copy, Zone.EXILE)
            except CastingError:
                # Not castable (e.g. no legal target) — remove the copy
                # and stay prepared.
                ctrl.zones[Zone.EXILE].remove(spell_copy)
                return
            # Casting the copy unprepares the permanent (CR 722.3c).
            source.prepared = False
            # LIMITATION: the resolved copy ends in the graveyard; the
            # engine has no "a spell copy ceases to exist" state-based action.

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared — cast a copy of Swords to Plowshares "
                "({W}); doing so unprepares this creature.",
            )
        ]
