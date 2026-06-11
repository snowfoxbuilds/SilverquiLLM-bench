"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant (sos_13's prepare spell).

    Exile target creature. Its controller gains life equal to its power.

    Only ever instantiated as the prepared copy created in exile by
    Emeritus of Truce (rule 722.3c) — it is not a standalone card.
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
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is not None:
            power = getattr(target, "power", 0)
            target_controller = getattr(target, "controller", None)
            exile(game, target)
            if target_controller is not None:
                target_controller.life += power
                game.trigger_manager.fire_event(
                    game,
                    GainsLifeTriggeredEvent(player=target_controller, amount=power),
                )

        # This object is a copy of a spell — it ceases to exist after
        # resolving instead of going to a graveyard.
        owner = self.owner or self.controller
        if owner is not None:
            stack_zone = owner.zones[Zone.STACK]
            if stack_zone.contains(self):
                stack_zone.remove(self)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 —
    Creature — Cat Cleric (preparation card; prepare spell: Swords to
    Plowshares, {W} Instant).

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared. (While it's
    prepared, you may cast a copy of its spell. Doing so unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        # The whole double-faced name — the engine keys cards off `name`.
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
        self._prepared_copy: SwordsToPlowshares | None = None

    # ------------------------------------------------------------------
    # ETB effect — implemented in on_resolve, the codebase's pattern for
    # "when this creature enters" abilities (the engine fires the ETB
    # event before registering the entering card's own triggers, so a
    # self-ETB trigger registration would never fire; see fdn_12).
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        ctrl = self.controller
        if ctrl is None:
            return
        try:
            chosen_player = ctrl.choose(
                list(game.players), "target player creates an Inkling token"
            )
        except Exception:
            chosen_player = ctrl
        if chosen_player not in game.players:
            chosen_player = ctrl
        token = Creature(
            name="Inkling",
            base_power=1,
            base_toughness=1,
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
        )
        create_token(game, chosen_player, token)

        # Then, if an opponent controls more creatures than you, this
        # creature becomes prepared.  on_resolve runs just before this
        # card moves to the battlefield, so count it as +1 for "you".
        def _count(player: Any) -> int:
            return sum(
                1
                for c in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            )

        mine = _count(ctrl) + 1  # self is about to enter
        if any(_count(p) > mine for p in game.players if p is not ctrl):
            self._become_prepared(game)

    # ------------------------------------------------------------------
    # Prepared (rule 722.3)
    # ------------------------------------------------------------------

    def _become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation and create the prepare-spell copy
        in exile (rule 722.3c). No-op if already prepared."""
        if self.is_prepared or self.controller is None:
            return
        self.is_prepared = True
        spell_copy = SwordsToPlowshares(owner=self.controller, controller=self.controller)
        self.controller.zones[Zone.EXILE].add(spell_copy)
        self._prepared_copy = spell_copy

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepared copy from exile, paying its mana cost ({W},
        per rule 722.3c the copy is cast normally), then unprepare.

        Raises:
            CastingError: if not prepared, the cost can't be paid, or the
                cast is illegal (e.g. no legal target).
        """
        from engine.casting import CastingError, cast_spell_free

        controller = self.controller
        spell_copy = self._prepared_copy
        if not self.is_prepared or controller is None or spell_copy is None:
            raise CastingError("Cannot cast prepare spell — this creature is not prepared")

        cost = spell_copy.mana_cost
        if not controller.mana_pool.can_pay(cost, allow_restricted=True):
            raise CastingError("Cannot cast prepare spell — insufficient mana")

        # cast_spell_free performs the cast from exile without payment, so
        # pay the copy's cost explicitly first (rolled back on failure).
        controller.mana_pool.pay(cost, allow_restricted=True)
        try:
            cast_spell_free(game, controller, spell_copy, Zone.EXILE)
        except CastingError:
            from engine.types import ManaType

            controller.mana_pool.add(ManaType.WHITE, 1)
            raise

        # Doing so unprepares it (722.3c — at cast time).
        self.is_prepared = False
        self._prepared_copy = None
