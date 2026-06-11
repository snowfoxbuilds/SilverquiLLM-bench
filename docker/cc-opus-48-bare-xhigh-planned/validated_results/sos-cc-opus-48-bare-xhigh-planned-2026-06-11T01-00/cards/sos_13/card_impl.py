"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
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
            for o in game.get_battlefield(p).get_all():
                if CardType.CREATURE in getattr(o, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: "GameState") -> list:
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
        on_bf = any(game.get_battlefield(p).contains(target) for p in game.players)
        if not on_bf or CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        power = getattr(target, "power", 0)
        tcontroller = getattr(target, "controller", None)
        exile(game, target)
        if tcontroller is not None and hasattr(tcontroller, "life"):
            tcontroller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}.

    Creature — Cat Cleric // Instant. 3/3.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.  A double-faced card's name is the whole
    ``front // back`` string, so the class bakes the full name in and
    constructs with no arguments.  The ETB effect is implemented in
    ``on_resolve`` (the engine fires the ETB event before registering a
    card's own triggers, so self-ETB triggers are missed — this mirrors the
    FDN convention, e.g. fdn_12).
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

    def get_targets(self, game: "GameState") -> list:
        """The ETB targets a player (who creates the Inkling token)."""
        players = list(game.players)
        return [
            TargetRequirement(
                filter_fn=lambda obj: obj in players,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        chosen = getattr(self, "chosen_targets", None)
        target_player = chosen[0] if chosen else None
        if target_player not in game.players:
            target_player = ctrl

        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # "Then if an opponent controls more creatures than you" — this check
        # resolves after Emeritus is on the battlefield, so count it (+1) even
        # though it is still on the stack during on_resolve.
        mine = _count_creatures(game, ctrl) + 1
        if any(
            _count_creatures(game, p) > mine
            for p in game.players
            if p is not ctrl
        ):
            self._prepared = True

    # ------------------------------------------------------------------
    # Prepared: cast a copy of the back-face spell
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        if not getattr(self, "_prepared", False):
            return []
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            return getattr(src, "_prepared", False)

        def _effect(game: "GameState") -> None:
            source.cast_prepared_spell(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="While prepared: cast a copy of Swords to Plowshares "
                "from exile without paying its mana cost (unprepares this).",
            )
        ]

    def cast_prepared_spell(self, game: "GameState") -> bool:
        """Create a Swords to Plowshares copy, exile it, and cast it for free.

        Doing so unprepares this creature.  Returns ``True`` if cast; if there
        is no legal target the copy is removed and the creature stays prepared.
        """
        from engine.casting import cast_spell_free

        if not getattr(self, "_prepared", False):
            return False
        ctrl = self.controller
        if ctrl is None:
            return False
        swords = SwordsToPlowshares(owner=ctrl, controller=ctrl)
        ctrl.zones[Zone.EXILE].add(swords)
        try:
            cast_spell_free(game, ctrl, swords, Zone.EXILE)
        except Exception:
            if ctrl.zones[Zone.EXILE].contains(swords):
                ctrl.zones[Zone.EXILE].remove(swords)
            return False
        self._prepared = False
        return True
