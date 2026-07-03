"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(
        1 for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the back face of SOS 13).

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

    def get_targets(self, game: "GameState") -> list[Any]:
        has_creature = any(
            CardType.CREATURE in getattr(o, "card_types", set())
            for p in game.players for o in game.get_battlefield(p).get_all()
        )
        if not has_creature:
            return []
        return [TargetRequirement(
            filter_fn=lambda o: CardType.CREATURE in getattr(o, "card_types", set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        from engine.game import exile
        exile(game, target)
        if controller is not None and hasattr(controller, "life"):
            controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.  Note: the card's name is the full double-faced
    string so the engine/tests can construct it bare and key off ``name``.
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
        """ETB: target player makes an Inkling, then maybe become prepared.

        Done on resolve (mirrors the FDN "when this creature enters" pattern,
        e.g. Wardens of the Cycle).  The creature is about to enter, so it is
        counted as one of "your" creatures for the prepared comparison.
        """
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # "target player creates a 1/1 W/B Inkling with flying"
        target_player = controller.choose(list(game.players), "choose target player")
        if target_player not in game.players:
            target_player = controller
        token = Creature(
            name="Inkling", base_power=1, base_toughness=1,
            subtypes={"Inkling"}, keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # "Then if an opponent controls more creatures than you, become prepared."
        # +1 accounts for this creature, which is resolving and about to enter.
        your_count = _creature_count(game, controller) + 1
        for opp in game.players:
            if opp is controller:
                continue
            if _creature_count(game, opp) > your_count:
                self.is_prepared = True
                break

    def cast_prepared(self, game: "GameState", target: Any | None = None) -> bool:
        """Special action: while prepared, cast a copy of Swords to Plowshares
        from exile without paying its mana cost.  Doing so unprepares this.

        Returns ``True`` if the prepared spell was cast.
        """
        if not getattr(self, "is_prepared", False):
            return False
        controller = self.controller
        if controller is None:
            return False

        from engine.casting import cast_spell_free
        from engine.player import DeterministicPlayer

        swords = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(swords)
        if target is not None and isinstance(controller, DeterministicPlayer):
            controller._script.appendleft(target)
        try:
            cast_spell_free(game, controller, swords, Zone.EXILE)
        finally:
            # Casting the prepared spell unprepares this creature.
            self.is_prepared = False
        return True
