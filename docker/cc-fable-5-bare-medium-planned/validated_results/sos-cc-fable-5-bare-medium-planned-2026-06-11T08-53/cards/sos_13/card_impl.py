"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (Emeritus of Truce's prepare
    spell): exile target creature; its controller gains life equal to its
    power."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to "
            "its power.",
        )
        super().__init__(**kwargs)

    def can_cast(self, game: GameState) -> bool:
        for player in game.players:
            for perm in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(perm, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: GameState) -> list:
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
        from engine.zones import move_to_zone

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return
        power = getattr(target, "power", 0)
        controller = getattr(target, "controller", None)
        move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
        if controller is not None and power > 0:
            controller.life += power
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=controller, amount=power)
            )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 —
    Creature — Cat Cleric // Instant.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

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
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared. (While it's prepared, you may cast a copy "
            "of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def get_targets(self, game: GameState) -> list:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life")
                and hasattr(obj, "zones"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_cast(self, game: GameState) -> None:
        """Register the ETB trigger at cast time: the engine fires the
        ENTERS_BATTLEFIELD event *before* calling ``register_triggers`` on
        the entering permanent, so a self-ETB trigger must already exist
        when the spell resolves."""
        game.trigger_manager.unregister(self)  # idempotent on recast
        self._register_etb_trigger(game)

    def register_triggers(self, game: GameState) -> None:
        # Entering the battlefield is a fresh object — never prepared.
        self.is_prepared = False
        # Already registered via on_cast?  Don't duplicate.
        if game.trigger_manager.get_triggers_for_source(self):
            return
        self._register_etb_trigger(game)

    def _register_etb_trigger(self, game: GameState) -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(game: GameState) -> None:
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            chosen = getattr(source, "chosen_targets", None)
            target_player = chosen[0] if chosen else ctrl
            if target_player is None:
                target_player = ctrl

            token = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
            )
            create_token(game, target_player, token)

            # Then: prepared if an opponent controls more creatures than you.
            def _creatures(p: Any) -> int:
                return sum(
                    1
                    for perm in game.get_battlefield(p).get_all()
                    if CardType.CREATURE in getattr(perm, "card_types", set())
                )

            mine = _creatures(ctrl)
            if any(
                _creatures(p) > mine for p in game.players if p is not ctrl
            ):
                source.is_prepared = True

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """While prepared, the controller may cast a copy of the prepare
        spell (Swords to Plowshares) from exile, paying its {W} cost
        (CR 722.3c — the copy is cast normally, not for free).  Exposed
        as an activated ability because the engine has no other player
        entry point for casting from exile."""
        source = self

        def _cost(game: GameState, src: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or not source.is_prepared:
                return False
            cost = ManaCost.parse("{W}")
            if not ctrl.mana_pool.can_pay(cost):
                return False
            return ctrl.mana_pool.pay(cost)

        def _effect(game: GameState) -> None:
            from engine.casting import CastingError, cast_spell_free

            ctrl = getattr(source, "controller", None)
            if ctrl is None or not source.is_prepared:
                return
            copy_spell = SwordsToPlowshares(owner=ctrl, controller=ctrl)
            game.get_exile(ctrl).add(copy_spell)
            try:
                cast_spell_free(game, ctrl, copy_spell, Zone.EXILE)
            except CastingError:
                game.get_exile(ctrl).remove(copy_spell)
                return
            source.is_prepared = False

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Cast a copy of Swords to Plowshares ({W}; only while "
                    "prepared — unprepares this creature)"
                ),
            )
        ]
