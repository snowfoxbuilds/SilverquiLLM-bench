"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(1 for obj in game.get_battlefield(player).get_all() if _is_creature(obj))


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying.  Then if an opponent controls more
    creatures than you, this creature becomes *prepared*.

    While it's prepared, you may cast a copy of its spell — Swords to
    Plowshares (``{W}``: exile target creature, its controller gains life
    equal to its power).  Casting the copy unprepares it.

    SOS collector number 13.

    Modeled card-locally: the prepared copy is exposed as an activated
    ability whose cost requires the ``prepared`` designation plus the prepare
    spell's mana cost (``{W}``); paying it removes the designation (rule
    601.2i — the permanent loses ``prepared`` when the spell becomes cast).
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
            "unprepares it.)\n"
            "Swords to Plowshares {W}: Exile target creature. Its controller "
            "gains life equal to its power.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # ETB — handled in on_resolve (the self-entry event fires before
    # register_triggers, so a self-ETB trigger could never catch it).
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        target_player = controller.choose(
            list(game.players), "Choose target player to create the Inkling token"
        )
        if target_player is None:
            return

        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        token.colors = ["W", "B"]
        create_token(game, target_player, token)

        # The ability resolves with this creature already on the battlefield,
        # but on_resolve runs while it is still on the stack — count it as one
        # of *your* creatures.
        my_creatures = _count_creatures(game, controller) + 1
        for opponent in game.players:
            if opponent is controller:
                continue
            if _count_creatures(game, opponent) > my_creatures:
                self.is_prepared = True
                break

    # ------------------------------------------------------------------
    # Prepared copy — Swords to Plowshares
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            if not source.is_prepared:
                return False
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if not ctrl.mana_pool.pay(ManaCost.parse("{W}")):
                return False
            # Casting the copy unprepares the permanent (rule 601.2i).
            source.is_prepared = False
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import exile

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            candidates = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _is_creature(obj)
            ]
            if not candidates:
                return
            victim = ctrl.choose_target(candidates, "target creature to exile")
            if victim is None:
                return
            victim_controller = getattr(victim, "controller", None)
            gained = getattr(victim, "power", 0)
            exile(game, victim)
            if victim_controller is not None:
                victim_controller.life += gained

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="Prepared — {W}: Exile target creature. Its "
                "controller gains life equal to its power.",
            )
        ]
