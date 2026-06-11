"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(
        1
        for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )


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

    def get_targets(self, game: "GameState") -> list[Any]:
        def _is_creature(obj: Any) -> bool:
            return CardType.CREATURE in getattr(obj, "card_types", set())

        return [
            TargetRequirement(
                filter_fn=_is_creature,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's prepared,
    you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced card's name is the whole "front // back" string so the
        # engine and tests can find it by name when constructed bare.
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
        self.prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB. Implemented here (not via a self-ETB trigger) because the
        engine fires a permanent's enter event *before* registering its own
        triggers, so a self-watching ETB trigger would miss its own entry —
        the same pattern FDN ETB creatures (Gorehorn Raider, Felidar Savior)
        use."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates a 1/1 white-and-black Inkling with flying.
        try:
            target_player = controller.choose(
                list(game.players), "Choose target player to create an Inkling"
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

        # Then if an opponent controls more creatures than you, become prepared.
        # This card is resolving and about to enter the battlefield, so count it
        # among your creatures (it will be on the battlefield when this check
        # conceptually happens).
        your_count = _creature_count(game, controller) + 1
        opp_count = max(
            (_creature_count(game, p) for p in game.players if p is not controller),
            default=0,
        )
        if opp_count > your_count:
            self.prepared = True

    def cast_prepared_spell(self, game: "GameState") -> bool:
        """While prepared, cast a copy of Swords to Plowshares from exile for
        free; doing so unprepares this creature. Returns ``True`` if the spell
        was cast. The target is taken from the controller's choices (script the
        target before calling, as for any cast)."""
        if not getattr(self, "prepared", False):
            return False
        controller = self.controller
        if controller is None:
            return False

        # Swords targets a creature — without a legal target you can't cast it,
        # so it stays prepared.
        has_creature = any(
            CardType.CREATURE in getattr(c, "card_types", set())
            for p in game.players
            for c in game.get_battlefield(p).get_all()
        )
        if not has_creature:
            return False

        from engine.casting import cast_spell_free

        swords = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(swords)
        try:
            cast_spell_free(game, controller, swords, Zone.EXILE)
        except Exception:
            # Couldn't cast (e.g. no legal target) — clean up, stay prepared.
            if controller.zones[Zone.EXILE].contains(swords):
                controller.zones[Zone.EXILE].remove(swords)
            return False
        self.prepared = False
        return True
