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
    """Swords to Plowshares — {W} — Instant (back face / prepare spell).

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
        has_creature = any(
            _is_creature(o)
            for p in game.players
            for o in game.get_battlefield(p).get_all()
        )
        if not has_creature:
            return []
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
        if target is None or not _is_creature(target):
            return
        power = getattr(target, "power", 0)
        controller = getattr(target, "controller", None)
        exile(game, target)
        if controller is not None and hasattr(controller, "life"):
            controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.  (While it's prepared,
    you may cast a copy of its spell — Swords to Plowshares. Doing so
    unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
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
        self._prepared = False
        self._prepared_copy: SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # ETB effect (run in on_resolve, the codebase pattern for a creature's
    # own enter-the-battlefield ability — cf. fdn_205, since move_to_zone
    # fires the ETB event before a card registers its own triggers).
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        self._etb(game)

    def _etb(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        # "target player creates a 1/1 white and black Inkling with flying"
        target_player = ctrl.choose(
            list(game.players), "choose target player to create an Inkling"
        )
        if target_player not in game.players:
            target_player = ctrl
        inkling = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, inkling)

        # "Then if an opponent controls more creatures than you, this creature
        # becomes prepared."  on_resolve runs just before Emeritus is moved to
        # the battlefield, so count it explicitly among your creatures.
        opponent = next((p for p in game.players if p is not ctrl), None)
        if opponent is None:
            return
        your = 1 + sum(
            1 for o in game.get_battlefield(ctrl).get_all() if _is_creature(o)
        )
        opp = sum(
            1 for o in game.get_battlefield(opponent).get_all() if _is_creature(o)
        )
        if opp > your:
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Preparation (rule 722.3c)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation; create the prepare-spell copy in exile."""
        if self._prepared:
            return
        ctrl = self.controller
        if ctrl is None:
            return
        self._prepared = True
        copy = SwordsToPlowshares(owner=ctrl, controller=ctrl)
        ctrl.zones[Zone.EXILE].add(copy)
        self._prepared_copy = copy

    @property
    def prepared(self) -> bool:
        return self._prepared

    def cast_prepared_spell(self, game: "GameState") -> bool:
        """Cast the prepared copy (Swords to Plowshares), then unprepare.

        Per rule 722.3c the copy is cast normally (its {W} cost is paid).  The
        engine only casts from hand, so the copy is routed hand->cast (its
        source zone is observationally irrelevant).  Targets/mana come from the
        controller as usual; the caller resolves the stack.
        """
        from engine.casting import cast_spell as _cast

        if not self._prepared or self._prepared_copy is None:
            return False
        ctrl = self.controller
        if ctrl is None:
            return False
        copy = self._prepared_copy
        if ctrl.zones[Zone.EXILE].contains(copy):
            ctrl.zones[Zone.EXILE].remove(copy)
        ctrl.zones[Zone.HAND].add(copy)
        _cast(game, ctrl, copy)
        # "loses the prepared designation at the time the spell becomes cast"
        self._prepared = False
        self._prepared_copy = None
        return True
