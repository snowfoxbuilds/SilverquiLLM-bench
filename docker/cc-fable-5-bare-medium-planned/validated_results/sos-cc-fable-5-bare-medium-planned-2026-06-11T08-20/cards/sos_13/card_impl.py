"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (sos_13's prepare spell).

    Exile target creature.  Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to "
            "its power.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: GameState) -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        if CardType.CREATURE not in getattr(target, "card_types", set()):
            return
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game,
                GainsLifeTriggeredEvent(player=target_controller, amount=power),
            )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying.  Then if an opponent controls more
    creatures than you, this creature becomes prepared.  (While it's
    prepared, you may cast a copy of its spell.  Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # A double-faced card's name is the full "front // back" string.
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
        self.is_prepared: bool = False
        self._prepared_copy: SwordsToPlowshares | None = None

    def on_resolve(self, game: GameState) -> None:
        # "When this creature enters" implemented at resolution (mirrors
        # fdn_157): the engine fires the ETB event before registering the
        # entering card's own triggers, so a registered self-ETB trigger
        # would never see its own entry.
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates the Inkling token.
        try:
            target_player = controller.choose(
                list(game.players), "Target player creates a 1/1 Inkling "
                "creature token with flying"
            )
        except Exception:
            target_player = controller
        if target_player not in game.players:
            target_player = controller

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        create_token(game, target_player, token)

        # Then: if an opponent controls more creatures than you, become
        # prepared.  Counts include the new token, and this creature itself
        # (it is mid-entry — on the stack, about to hit the battlefield).
        def _creature_count(p: Any) -> int:
            return sum(
                1
                for obj in game.get_battlefield(p).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        mine = _creature_count(controller) + 1
        if any(
            _creature_count(p) > mine
            for p in game.players
            if p is not controller
        ):
            self._become_prepared(game)

    def _become_prepared(self, game: GameState) -> None:
        """Gain the prepared designation — a Swords copy appears in exile."""
        if self.is_prepared:
            return  # rule 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.is_prepared = True
        copy_card = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(copy_card)
        self._prepared_copy = copy_card

    def cast_prepared_spell(self, game: GameState) -> bool:
        """Cast the prepared Swords copy from exile (paying its {W} cost).

        Returns True if the spell was put on the stack.  Casting it
        unprepares this creature (rule 722.3c).
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        copy_card = self._prepared_copy
        if not self.is_prepared or controller is None or copy_card is None:
            return False
        # No legal target → the spell cannot be cast.
        has_creature = any(
            CardType.CREATURE in getattr(obj, "card_types", set())
            for p in game.players
            for obj in game.get_battlefield(p).get_all()
        )
        if not has_creature:
            return False
        # The copy is cast by normal rules — pay its {W} cost, then use the
        # free-cast pipeline for the cast-from-exile zone handling.
        cost = copy_card.mana_cost
        if not controller.mana_pool.can_pay(cost, spell=copy_card):
            return False
        try:
            controller.mana_pool.pay(cost, spell=copy_card)
            cast_spell_free(game, controller, copy_card, Zone.EXILE)
        except CastingError:
            return False
        # Unprepared at cast time (rule 601.2i / 722.3c).
        self.is_prepared = False
        self._prepared_copy = None
        return True
