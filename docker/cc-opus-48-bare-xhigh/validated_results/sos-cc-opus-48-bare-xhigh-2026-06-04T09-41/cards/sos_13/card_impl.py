"""Card implementation for Emeritus of Truce // Swords to Plowshares.

Emeritus of Truce is a *preparation card* (CR 722).  Its inset "prepare
spell" is Swords to Plowshares.  While Emeritus is *prepared*, a copy of
the prepare spell sits in its controller's exile zone and may be cast;
casting it removes the prepared designation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (Emeritus's prepare spell).

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
        self.colors = {"W"}

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        return [TargetRequirement(_is_creature, "target creature", Zone.BATTLEFIELD)]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        target_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if target_controller is not None:
            target_controller.life += power


def _make_inkling_token() -> Creature:
    from engine.types import Keyword

    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        base_power=1,
        base_toughness=1,
        keywords=Keyword.FLYING,
    )
    token.is_token = True
    token.colors = {"W", "B"}
    return token


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    """

    # The prepare spell associated with this preparation card.
    prepare_spell_factory = SwordsToPlowshares

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
        self.colors = {"W"}
        self.prepared: bool = False
        self._prepared_copy: SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: "GameState", event: Any) -> bool:
            return getattr(event, "permanent", None) is source

        def _effect(g: "GameState") -> None:
            self._etb(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller or self.owner,
            )
        )

    def _etb(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates the Inkling token.
        target_player = controller.choose(
            list(game.players), "choose target player to create an Inkling token"
        )
        if target_player is None:
            target_player = controller
        create_token(game, target_player, _make_inkling_token())

        # Then: if an opponent controls more creatures than you, become prepared.
        my_creatures = _count_creatures(game, controller)
        for opponent in game.players:
            if opponent is controller:
                continue
            if _count_creatures(game, opponent) > my_creatures:
                self._become_prepared(game)
                break

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation (CR 722.3c).

        Create a copy of the prepare spell in the controller's exile zone;
        it may be cast for as long as Emeritus stays prepared.
        """
        controller = self.controller
        if controller is None or self.prepared:
            return
        copy = self.prepare_spell_factory()
        copy.owner = controller
        copy.controller = controller
        controller.zones[Zone.EXILE].add(copy)
        self._prepared_copy = copy
        self.prepared = True

    def unprepare(self, game: "GameState") -> None:
        """Remove the prepared designation; the exiled copy ceases to exist."""
        controller = self.controller
        copy = self._prepared_copy
        if controller is not None and copy is not None:
            exile_zone = controller.zones[Zone.EXILE]
            if exile_zone.contains(copy):
                exile_zone.remove(copy)
        self._prepared_copy = None
        self.prepared = False

    def cast_prepared(self, game: "GameState") -> None:
        """Cast the prepared copy from exile (paying its mana cost).

        Casting it removes the prepared designation (CR 722.3c).  Targets
        are chosen through the controller's normal target selection.
        """
        from engine.casting import CastingError, cast_spell

        controller = self.controller
        copy = self._prepared_copy
        if not self.prepared or controller is None or copy is None:
            return
        try:
            cast_spell(game, controller, copy, from_zone=Zone.EXILE)
        except CastingError:
            return
        # The spell has been cast — lose the prepared designation.
        self._prepared_copy = None
        self.prepared = False


def _count_creatures(game: "GameState", player: "Player") -> int:
    return sum(
        1
        for c in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(c, "card_types", set())
    )
