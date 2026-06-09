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
    """Swords to Plowshares — {W} — Instant (the prepare spell / back face).

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

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        power = getattr(target, "power", 0)
        owner = getattr(target, "controller", None) or getattr(target, "owner", None)
        exile(game, target)
        if owner is not None and hasattr(owner, "life"):
            owner.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.  The card's name is the whole `front // back`
    string so the engine/tests can find it.
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
        self.prepared: bool = False
        self._prepared_copy: SwordsToPlowshares | None = None

    def register_triggers(self, game: "GameState") -> None:
        # NOTE: In this engine, a permanent's own ETB triggered ability does
        # NOT fire via EntersBattlefieldTriggeredEvent (move_to_zone fires the
        # ETB event *before* calling register_triggers). register_triggers is
        # invoked exactly once, right after the creature enters — so the ETB
        # effect is performed here, where `self` is already on the battlefield
        # (and thus counted among your creatures).
        self._on_enter(game)

    def _on_enter(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return

        # Target player creates a 1/1 W/B Inkling with flying.
        try:
            target_player = ctrl.choose(list(game.players), "Choose target player")
        except Exception:
            target_player = ctrl
        if target_player not in game.players:
            target_player = ctrl
        token = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # Then if an opponent controls more creatures than you → prepared.
        def _creatures(p):
            return sum(1 for c in game.get_battlefield(p).get_all() if _is_creature(c))

        mine = _creatures(ctrl)
        opp_more = any(
            _creatures(p) > mine for p in game.players if p is not ctrl
        )
        if opp_more:
            self._become_prepared(game)

    def _become_prepared(self, game: "GameState") -> None:
        # Rule 722.3c: on becoming prepared, create a copy of the prepare spell
        # in exile; the controller may cast that copy (paying its cost).
        if self.prepared:
            return
        ctrl = self.controller
        self.prepared = True
        copy = SwordsToPlowshares(owner=ctrl, controller=ctrl)
        self._prepared_copy = copy
        if ctrl is not None:
            game.get_exile(ctrl).add(copy)

    def cast_prepared(self, game: "GameState") -> bool:
        """Cast the prepared copy (Swords to Plowshares) from exile.

        Per rule 722.3c this is a normal cast — the controller pays the copy's
        mana cost ({W}). Targets are chosen through the real cast pipeline
        (scripted in tests). On a successful cast the permanent is unprepared.
        Returns True if the spell was cast.
        """
        from engine.casting import cast_spell_free

        ctrl = self.controller
        copy = self._prepared_copy
        if not self.prepared or ctrl is None or copy is None:
            return False
        if not game.get_exile(ctrl).contains(copy):
            return False
        # Must have a legal target (a creature on the battlefield).
        has_target = any(
            _is_creature(c)
            for p in game.players
            for c in game.get_battlefield(p).get_all()
        )
        if not has_target:
            return False
        # Pay the copy's mana cost ({W}); this is a normal cast, not free.
        if not ctrl.mana_pool.can_pay(copy.mana_cost):
            return False
        ctrl.mana_pool.pay(copy.mana_cost)
        # cast_spell_free handles the zone move + targeting + stack push
        # (we have already paid the cost above).
        cast_spell_free(game, ctrl, copy, Zone.EXILE)
        self.prepared = False
        self._prepared_copy = None
        return True
