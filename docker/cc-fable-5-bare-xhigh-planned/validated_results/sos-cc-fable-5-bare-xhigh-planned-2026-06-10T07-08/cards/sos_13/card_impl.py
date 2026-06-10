"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """The prepare spell: {W} — Exile target creature. Its controller gains
    life equal to its power.  (Helper class; copies of this are created in
    exile when the Emeritus becomes prepared, per rule 722.3c.)"""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
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
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        creature_controller = getattr(target, "controller", None)
        power = getattr(target, "power", 0)
        exile(game, target)
        if creature_controller is not None and hasattr(creature_controller, "life"):
            creature_controller.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3
    Creature — Cat Cleric, with prepare spell Swords to Plowshares ({W}).

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # The full double-faced name — the engine keys cards off `name`.
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        # The front face's cost is the card's castable cost ("{1}{W}{W} // {W}"
        # is not a parseable single cost; the prepare spell's {W} lives on
        # the SwordsToPlowshares helper).
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Cat", "Cleric"}
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
        # The exiled prepare-spell copy (rule 722.3c), while one exists.
        self._prepared_copy: SwordsToPlowshares | None = None

    @property
    def prepared(self) -> bool:
        """Alias for the prepared designation."""
        return self.is_prepared

    # ------------------------------------------------------------------
    # Cast-time targeting: "target player creates ... token"
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    # ------------------------------------------------------------------
    # ETB trigger
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        # Register the ETB trigger before the engine moves this card to the
        # battlefield: move_to_zone fires the entry event *before* calling
        # register_triggers on the entering card, so a trigger registered
        # only at entry would miss its own ETB.
        self.register_triggers(game)

    def register_triggers(self, game: GameState) -> None:
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        from engine.events import EntersBattlefieldTriggeredEvent

        # Idempotent — on_resolve registers first, then move_to_zone calls
        # this hook again on entry.
        if game.trigger_manager.get_triggers_for_source(self):
            return

        source = self

        def _condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # 1. Target player creates the Inkling token.  Falls back to the
            #    controller when no cast-time target was chosen (e.g. the
            #    creature was put onto the battlefield directly).
            chosen = getattr(source, "chosen_targets", None)
            target_player = chosen[0] if chosen else None
            if target_player is None or not hasattr(target_player, "life"):
                target_player = controller
            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            token.colors = {"W", "B"}
            create_token(game, target_player, token)

            # 2. Then: if an opponent controls more creatures than you,
            #    this creature becomes prepared.
            def _creature_count(player: Any) -> int:
                return sum(
                    1
                    for c in game.get_battlefield(player).get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                )

            mine = _creature_count(controller)
            if any(
                _creature_count(p) > mine
                for p in game.players
                if p is not controller
            ):
                source._become_prepared(game)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Prepared (rule 722.3)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: GameState) -> None:
        """Gain the prepared designation; create the spell copy in exile."""
        if self.is_prepared:
            return  # 722.3a — can't gain the designation twice
        controller = self.controller
        if controller is None:
            return
        self.is_prepared = True
        copy_card = SwordsToPlowshares()
        copy_card.owner = copy_card.controller = controller
        controller.zones[Zone.EXILE].add(copy_card)
        self._prepared_copy = copy_card

    def cast_prepared_spell(self, game: GameState) -> None:
        """Cast the exiled Swords to Plowshares copy (paying its {W} cost,
        per rule 722.3c casting is normal), then unprepare.

        Raises:
            CastingError: If not prepared, the cost can't be paid, or the
                copy can't legally be cast.
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        copy_card = self._prepared_copy
        if not self.is_prepared or copy_card is None or controller is None:
            raise CastingError("Not prepared — no spell copy to cast")
        if not game.get_battlefield(controller).contains(self):
            raise CastingError("Prepared creature is no longer on the battlefield")

        # The copy's mana cost ({W}) is paid — the rulebook gives no free
        # cast.  Check first, pay after the cast succeeds (cast_spell_free
        # rolls itself back on failure; nothing mutates the pool in between).
        if not controller.mana_pool.can_pay(copy_card.mana_cost, spell=copy_card):
            raise CastingError("Cannot cast prepared spell — insufficient mana")

        cast_spell_free(game, controller, copy_card, Zone.EXILE)
        controller.mana_pool.pay(copy_card.mana_cost, spell=copy_card)

        # The permanent loses the designation as the spell becomes cast
        # (722.3c / 601.2i).
        self.is_prepared = False
        self._prepared_copy = None
