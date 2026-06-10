"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(1 for c in game.get_battlefield(player).get_all() if _is_creature(c))


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (back face / prepared spell).

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
            _is_creature(c)
            for p in game.players
            for c in game.get_battlefield(p).get_all()
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
        if target is None:
            return
        tctrl = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if tctrl is not None and hasattr(tctrl, "life"):
            tctrl.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}.

    Front (3/3 Cat Cleric): When this creature enters, target player creates a
    1/1 white and black Inkling creature token with flying. Then if an opponent
    controls more creatures than you, this creature becomes prepared.  While
    prepared you may cast a copy of its spell (Swords to Plowshares), which
    unprepares it.

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
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Enters-the-battlefield effect.

        Implemented in ``on_resolve`` because the engine fires the ETB event
        *before* a permanent registers its own triggers, so a self-ETB trigger
        cannot catch its own entry.  ``on_resolve`` runs as the creature
        resolves (just before it enters); "creatures you control" therefore
        counts this Emeritus explicitly (+1) to match the post-entry state.
        """
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # "target player creates a 1/1 white-black Inkling with flying"
        try:
            target_player = controller.choose(
                list(game.players), "Choose target player to create an Inkling"
            )
        except Exception:
            target_player = controller
        if target_player not in game.players:
            target_player = controller

        # Colors are not modeled by the engine; subtype + flying are.
        token = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # "Then if an opponent controls more creatures than you, prepared."
        # +1 because this Emeritus is entering (counts as one you control).
        my_count = _creature_count(game, controller) + 1
        for opp in game.players:
            if opp is controller:
                continue
            if _creature_count(game, opp) > my_count:
                self._prepared = True
                break

    @property
    def prepared(self) -> bool:
        return self._prepared

    def cast_prepared_copy(self, game: "GameState", target: Any = None) -> bool:
        """Special action: while prepared, cast a copy of Swords to Plowshares
        from exile for free; doing so unprepares this creature.

        Returns ``True`` if the copy was cast.  The target is chosen through the
        normal cast pipeline (scripted via the player in tests).
        """
        from engine.casting import cast_spell_free

        if not self._prepared:
            return False
        controller = self.controller
        if controller is None:
            return False
        # No legal target → cannot cast; stays prepared.
        has_creature = any(
            _is_creature(c)
            for p in game.players
            for c in game.get_battlefield(p).get_all()
        )
        if not has_creature:
            return False

        swords = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(swords)
        if target is not None and hasattr(controller, "_script"):
            controller._script.appendleft(target)
        try:
            cast_spell_free(game, controller, swords, Zone.EXILE)
        except Exception:
            return False
        self._prepared = False
        return True
