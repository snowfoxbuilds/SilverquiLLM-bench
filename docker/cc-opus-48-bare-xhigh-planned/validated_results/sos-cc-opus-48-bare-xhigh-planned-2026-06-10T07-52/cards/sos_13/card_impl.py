"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the back face's spell).

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

    def get_targets(self, game: "GameState") -> list:
        return [
            TargetRequirement(
                filter_fn=_is_creature,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        target = (getattr(self, "chosen_targets", []) or [None])[0]
        if target is None:
            return
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += power


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(
        1
        for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.  (A double-faced card; the full card name is the
    whole ``front // back`` string.)
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
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        # The engine fires a permanent's ETB event *before* registering the
        # card's own triggers, so a self-ETB cannot be a registered trigger.
        # Run the enter-the-battlefield effect here at resolution instead
        # (this creature is about to enter, accounted for by the +1 below).
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return

        # Target player creates a 1/1 white-black Inkling with flying.
        # (Colour is not modelled by the engine — only the subtype/flying are.)
        target_player = ctrl.choose(
            list(game.players), "Choose target player to create an Inkling"
        )
        if target_player not in game.players:
            target_player = ctrl
        inkling = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, inkling)

        # Then if an opponent controls more creatures than you → prepared.
        # +1 for this creature, which is on the stack now but about to enter.
        your_creatures = _count_creatures(game, ctrl) + 1
        opp_creatures = max(
            (_count_creatures(game, p) for p in game.players if p is not ctrl),
            default=0,
        )
        if opp_creatures > your_creatures:
            self._become_prepared(game)

    def _become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation, creating the Swords copy in exile.

        Per CR 722.3c, the prepare-spell copy is created in exile *as the
        permanent becomes prepared* (not when it is later cast).
        """
        if self.is_prepared:
            return  # a permanent can't gain the designation it already has
        ctrl = self.controller
        if ctrl is None:
            return
        self.is_prepared = True
        swords = SwordsToPlowshares(owner=ctrl, controller=ctrl)
        ctrl.zones[Zone.EXILE].add(swords)
        self._prepared_copy = swords

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Special action: while prepared, cast the Swords-to-Plowshares copy
        from exile.  Per CR 722.3c the copy is cast *normally* — paying its
        mana cost ({W}) — and the permanent loses the prepared designation as
        it becomes cast.  (The TODO suggested a free cast; the rulebook grants
        no cost waiver, so the copy is paid for.)  The caller resolves the
        resulting stack object.
        """
        ctrl = self.controller
        if not self.is_prepared or ctrl is None:
            return
        copy = getattr(self, "_prepared_copy", None)
        if copy is None or not ctrl.zones[Zone.EXILE].contains(copy):
            return
        # Swords needs a legal target (a creature); with none on the
        # battlefield the copy can't be cast.
        has_target = any(
            _is_creature(o)
            for p in game.players
            for o in game.get_battlefield(p).get_all()
        )
        if not has_target:
            return
        # Cast the copy normally: pay its mana cost.
        if not ctrl.mana_pool.can_pay(copy.mana_cost, instant_or_sorcery=True):
            return  # can't pay → can't cast (the action isn't taken)
        ctrl.mana_pool.pay(copy.mana_cost, instant_or_sorcery=True)
        self.is_prepared = False  # loses prepared as it becomes cast
        from engine.casting import cast_spell_free

        cast_spell_free(game, ctrl, copy, Zone.EXILE)
