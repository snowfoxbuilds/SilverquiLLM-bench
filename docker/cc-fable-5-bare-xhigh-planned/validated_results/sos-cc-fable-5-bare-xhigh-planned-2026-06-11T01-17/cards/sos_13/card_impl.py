"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the prepare spell).

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

    def can_cast(self, game: GameState) -> bool:
        """Needs a creature on some battlefield to target."""
        return any(
            CardType.CREATURE in getattr(obj, "card_types", set())
            for p in game.players
            for obj in game.get_battlefield(p).get_all()
        )

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 —
    Creature — Cat Cleric // Instant.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    The prepared cast is exposed via :meth:`cast_prepared_copy` — per rule
    722.3c the copy is a real Swords to Plowshares castable from exile for
    its normal cost ({W}), and casting it unprepares this creature.

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
            "becomes prepared. (While it's prepared, you may cast a copy of "
            "its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_resolve(self, game: GameState) -> None:
        """ETB effect — engine convention places a permanent's own
        enters-the-battlefield ability here (the ETB event fires before the
        entering card's triggers register, so it can't watch its own entry).
        LIMITATION: entering without being cast (e.g. reanimation) skips
        this, matching the FDN reference cards."""
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        # Target player creates the Inkling token.
        target_player = ctrl.choose(
            list(game.players), "Target player creates a 1/1 Inkling token"
        )
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

        # Then: if an opponent controls more creatures than you, this
        # creature becomes prepared.  This card is still on the stack
        # here (it enters the battlefield right after on_resolve), so it
        # counts itself explicitly.
        def _creatures(p: Any) -> int:
            return sum(
                1
                for obj in game.get_battlefield(p).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        mine = _creatures(ctrl) + (
            0 if game.get_battlefield(ctrl).contains(self) else 1
        )
        if any(_creatures(p) > mine for p in game.players if p is not ctrl):
            self.prepared = True

    def cast_prepared_copy(self, game: GameState) -> bool:
        """While prepared, cast a copy of Swords to Plowshares (rule 722.3c).

        Creates the copy in exile, pays its normal {W} cost from the
        controller's pool, and casts it from exile through the real stack.
        Unprepares this creature when the copy becomes cast.

        Returns True if the copy was cast, False otherwise (not prepared,
        cost unpayable, or no legal target — in which case it stays
        prepared and the mana is untouched).
        """
        from engine.casting import CastingError, cast_spell_free

        ctrl = self.controller
        if not self.prepared or ctrl is None:
            return False

        copy = SwordsToPlowshares(owner=ctrl, controller=ctrl)
        # The copy ceases to exist once it leaves the stack — flagging it
        # as a token lets the existing SBA sweep it from the graveyard.
        copy.is_token = True

        if not ctrl.mana_pool.can_pay(copy.mana_cost, spell=copy):
            return False
        exile_zone = ctrl.zones[Zone.EXILE]
        exile_zone.add(copy)
        ctrl.mana_pool.pay(copy.mana_cost, spell=copy)
        try:
            cast_spell_free(game, ctrl, copy, Zone.EXILE)
        except CastingError:
            # Roll back: refund the {W} and discard the copy.
            from engine.types import ManaType

            ctrl.mana_pool.add(ManaType.WHITE, 1)
            if exile_zone.contains(copy):
                exile_zone.remove(copy)
            return False
        # The cast paid {W} (cast_spell_free itself records 0).
        copy.mana_spent = copy.mana_cost.cmc
        self.prepared = False
        return True
