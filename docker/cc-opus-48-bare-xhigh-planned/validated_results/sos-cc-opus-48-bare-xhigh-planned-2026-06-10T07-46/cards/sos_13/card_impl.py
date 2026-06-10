"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import (
    CardType,
    Keyword,
    ManaCost,
    Supertype,
    TargetRequirement,
    Zone,
)

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(player: Any) -> int:
    return sum(
        1
        for c in player.zones[Zone.BATTLEFIELD].get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the back face / prepared spell).

    Exile target creature. Its controller gains life equal to its power.
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
        for p in game.players:
            for o in p.zones[Zone.BATTLEFIELD].get_all():
                if CardType.CREATURE in getattr(o, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: "GameState") -> list:
        return [
            TargetRequirement(
                filter_fn=lambda o: CardType.CREATURE in getattr(o, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        target = (getattr(self, "chosen_targets", []) or [None])[0]
        if target is None:
            return
        # Read power before exiling.
        tctrl = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if tctrl is not None and hasattr(tctrl, "life"):
            tctrl.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.  Double-faced; ``name`` is the whole front // back
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
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        # The engine fires a permanent's enter event before registering its own
        # triggers, so a self-ETB trigger never sees its own entry.  We run the
        # enter effect here (the cast path).  Emeritus is still on the stack at
        # this point, so it is counted among "your" creatures with a +1.
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # "target player creates a 1/1 white and black Inkling with flying"
        try:
            target_player = controller.choose(
                list(game.players), "choose target player for the Inkling token"
            )
        except Exception:
            target_player = controller
        if target_player not in game.players:
            target_player = controller
        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # "Then if an opponent controls more creatures than you, ~ becomes
        # prepared."  +1 because Emeritus is about to enter (still on the stack).
        your_count = _count_creatures(controller) + 1
        opp_max = max(
            (_count_creatures(p) for p in game.players if p is not controller),
            default=0,
        )
        if opp_max > your_count:
            self._prepared = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        # "While it's prepared, you may cast a copy of its spell."  Modelled as
        # a no-cost special action available only while prepared.
        if not getattr(self, "_prepared", False):
            return []
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            return True

        def _effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free

            ctrl = source.controller
            if ctrl is None or not getattr(source, "_prepared", False):
                return
            swords = SwordsToPlowshares(owner=ctrl, controller=ctrl)
            ctrl.zones[Zone.EXILE].add(swords)
            try:
                cast_spell_free(game, ctrl, swords, Zone.EXILE)
            except Exception:
                # No legal target — can't cast the copy; stay prepared.
                if ctrl.zones[Zone.EXILE].contains(swords):
                    ctrl.zones[Zone.EXILE].remove(swords)
                return
            # "Doing so unprepares it."
            source._prepared = False

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared: cast a copy of Swords to Plowshares.",
            )
        ]
