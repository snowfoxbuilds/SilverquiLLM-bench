"""Card implementation for Emeritus of Truce // Swords to Plowshares.

Split-card / Prepared simplification: ``ManaCost.parse`` cannot handle the
``"{1}{W}{W} // {W}"`` split cost, so only the creature side (``{1}{W}{W}``)
is modelled as the card's mana cost.

"Prepared" is not a :class:`Keyword` flag, so it is tracked with the boolean
``self.prepared``.  While prepared, the controller may "cast a copy of its
spell" — the Swords to Plowshares half — which is modelled as an activated
ability costing ``{W}`` (exile target creature; its controller gains life
equal to its power).  Casting the copy unprepares the creature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState

_SWORDS_COST = "{W}"


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _all_creatures(game: "GameState") -> list[Any]:
    result: list[Any] = []
    for player in game.players:
        for obj in game.get_battlefield(player).get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                result.append(obj)
    return result


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying.  Then if an opponent controls more
    creatures than you, this creature becomes prepared.  (While it's
    prepared, you may cast a copy of its spell — Swords to Plowshares.
    Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.colors = {Color.WHITE}
        self.prepared: bool = False

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: "GameState", e: Any) -> bool:
            return getattr(e, "permanent", None) is source

        def _effect(g: "GameState") -> None:
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # --- Resolve the "target player" for the Inkling token. ---
            target = None
            chosen = getattr(source, "chosen_targets", None)
            if chosen:
                target = chosen[0]
            if target is None:
                target = getattr(source, "_resolve_target", None)
            if target is None or not hasattr(target, "life"):
                target = ctrl

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            token.colors = {Color.WHITE, Color.BLACK}
            create_token(g, target, token)

            # --- Prepared: if an opponent controls more creatures than you. ---
            my_count = _count_creatures(g, ctrl)
            for opp in g.players:
                if opp is ctrl:
                    continue
                if _count_creatures(g, opp) > my_count:
                    source.prepared = True
                    break

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def cast_swords_copy(self, game: "GameState", target_creature: Any) -> None:
        """Resolve a copy of the Swords to Plowshares half.

        Exile *target_creature*; its controller gains life equal to its
        power.  Unprepares this creature.
        """
        from engine.zones import move_to_zone

        if target_creature is None:
            return
        if not any(
            game.get_battlefield(p).contains(target_creature) for p in game.players
        ):
            return

        tc = getattr(target_creature, "controller", None)
        power = getattr(target_creature, "power", 0)
        move_to_zone(game, target_creature, Zone.BATTLEFIELD, Zone.EXILE)
        if tc is not None and hasattr(tc, "life"):
            tc.life += power
        self.prepared = False

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        if not getattr(self, "prepared", False):
            return []

        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            cost = ManaCost.parse(_SWORDS_COST)
            if not ctrl.mana_pool.can_pay(cost):
                return False
            ctrl.mana_pool.pay(cost)
            return True

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            creatures = _all_creatures(game)
            if not creatures:
                return
            target = ctrl.choose_card(
                creatures, "Choose a creature to exile with Swords to Plowshares"
            )
            if target is None:
                return
            source.cast_swords_copy(game, target)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Prepared — {W}: Exile target creature; its controller "
                    "gains life equal to its power."
                ),
            )
        ]
