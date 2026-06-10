"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _creature_count(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (the prepare spell of sos_13).

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

    def get_targets(self, game: "GameState") -> list[TargetRequirement]:
        def _is_creature_on_battlefield(obj: Any) -> bool:
            if CardType.CREATURE not in getattr(obj, "card_types", set()):
                return False
            return any(
                game.get_battlefield(p).contains(obj) for p in game.players
            )

        return [
            TargetRequirement(
                filter_fn=_is_creature_on_battlefield,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None) or []
        target = chosen[0] if chosen else None
        if target is None:
            return  # fizzled
        on_battlefield = any(
            game.get_battlefield(p).contains(target) for p in game.players
        )
        if not on_battlefield:
            return  # target gone — fizzle
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=target_controller, amount=power)
            )


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Double-faced card: the name is the whole "front // back" string.
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
        self.prepared: bool = False
        self._prepare_copy: SwordsToPlowshares | None = None

    @property
    def is_prepared(self) -> bool:
        return self.prepared

    def on_resolve(self, game: "GameState") -> None:
        """ETB ability — the engine resolves a creature's own enters
        ability here (fdn_205 pattern; the ETB event fires before the
        entering card's triggers register, so a self-ETB trigger is inert).
        """
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates the Inkling token.  (Token colors aren't
        # modeled by the engine — colors derive from mana cost.)
        try:
            target_player = controller.choose_target(
                list(game.players), "target player creates an Inkling token"
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

        # "Then if an opponent controls more creatures than you" — this
        # creature is entering, so it counts toward "you".
        yours = _creature_count(game, controller)
        if not any(game.get_battlefield(p).contains(self) for p in game.players):
            yours += 1
        opponents_more = any(
            _creature_count(game, p) > yours
            for p in game.players
            if p is not controller
        )
        if opponents_more:
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Prepared state (rule 722)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState") -> None:
        if self.prepared:
            return  # can't gain the designation twice (722.3a)
        controller = self.controller
        if controller is None:
            return
        self.prepared = True
        # 722.3c — create the prepare-spell copy in exile immediately.
        spell_copy = SwordsToPlowshares(owner=controller, controller=controller)
        self._prepare_copy = spell_copy
        controller.zones[Zone.EXILE].add(spell_copy)

    def _become_unprepared(self, game: "GameState") -> None:
        self.prepared = False
        spell_copy = self._prepare_copy
        self._prepare_copy = None
        if spell_copy is None:
            return
        # An uncast copy ceases to exist when prepared ends (722.3c).
        for player in game.players:
            exile_zone = player.zones[Zone.EXILE]
            if exile_zone.contains(spell_copy):
                exile_zone.remove(spell_copy)
                return

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import LeavesBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(g: "GameState") -> None:
            if source.prepared:
                source._become_unprepared(g)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=LeavesBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    # ------------------------------------------------------------------
    # Casting the prepared copy
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None or not source.prepared:
                return False
            spell_copy = source._prepare_copy
            if spell_copy is None or not controller.zones[Zone.EXILE].contains(
                spell_copy
            ):
                return False
            # Swords needs a legal target to be castable.
            if not any(
                CardType.CREATURE in getattr(obj, "card_types", set())
                for p in game.players
                for obj in game.get_battlefield(p).get_all()
            ):
                return False
            # Casting the copy pays its mana cost (722.3c says "may cast
            # the copy" — no free-cast wording).
            return controller.mana_pool.pay(spell_copy.mana_cost)

        def _effect(game: "GameState") -> None:
            from engine.casting import CastingError, cast_spell_free

            controller = source.controller
            spell_copy = source._prepare_copy
            if controller is None or spell_copy is None:
                return
            try:
                # Mana was paid in the cost step; the stack path is the
                # free-cast pipeline from exile.
                cast_spell_free(game, controller, spell_copy, Zone.EXILE)
            except CastingError:
                return
            # "Doing so unprepares it." — the copy is now a spell on the
            # stack, so only clear the designation (don't delete the copy).
            source.prepared = False
            source._prepare_copy = None

            # A resolved spell copy ceases to exist (rule 707.10a).
            copy_so = game.stack.peek()
            if copy_so is None or copy_so.source is not spell_copy:
                return
            original_resolve = copy_so.on_resolve

            def _resolve_then_vanish(g: "GameState") -> None:
                original_resolve(g)
                for player in g.players:
                    gy = player.zones[Zone.GRAVEYARD]
                    if gy.contains(spell_copy):
                        gy.remove(spell_copy)
                        return

            copy_so.on_resolve = _resolve_then_vanish

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "Cast the prepared Swords to Plowshares copy from exile "
                    "(pays {W}; unprepares this creature)."
                ),
            )
        ]
