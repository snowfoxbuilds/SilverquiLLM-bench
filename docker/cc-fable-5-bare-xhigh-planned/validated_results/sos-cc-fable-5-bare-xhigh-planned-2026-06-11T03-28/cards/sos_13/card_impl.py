"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """The prepare spell — {W} — Instant.

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

    def can_cast(self, game: "GameState") -> bool:
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        return [TargetRequirement(
            filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: "GameState") -> None:
        from engine.events import GainsLifeTriggeredEvent
        from engine.game import exile

        targets = getattr(self, "chosen_targets", None) or []
        target = targets[0] if targets else None
        if target is None:
            return
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)
        exile(game, target)
        if target_controller is not None and power > 0:
            target_controller.life += power
            game.trigger_manager.fire_event(
                game, GainsLifeTriggeredEvent(player=target_controller, amount=power)
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
        self._prepared: bool = False
        self._prepare_copy: Any | None = None

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    # ------------------------------------------------------------------
    # ETB — engine convention: a permanent's own enters-the-battlefield
    # effect runs in on_resolve (mirroring fdn_205), because move_to_zone
    # fires the ETB event before registering the entering card's triggers.
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Target player creates a 1/1 white and black Inkling with flying.
        requirement = TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life") and hasattr(obj, "zones"),
            description="target player",
            zone=Zone.BATTLEFIELD,
        )
        target_player = controller.choose_target(list(game.players), requirement)
        if target_player is not None and hasattr(target_player, "zones"):
            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(game, target_player, token)

        # Then: if an opponent controls more creatures than you, become
        # prepared.  This runs while the card is still on the stack, so
        # count it as one of your creatures (it enters as this resolves).
        def _creatures(player: Any) -> int:
            return sum(
                1 for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )

        yours = _creatures(controller) + 1
        if any(
            _creatures(p) > yours for p in game.players if p is not controller
        ):
            self._become_prepared(game)

    def _become_prepared(self, game: "GameState") -> None:
        """Gain the prepared designation: per rule 722.3c the controller
        creates a copy of the prepare spell in exile, castable while this
        stays prepared."""
        if self._prepared:
            return  # already prepared — designation can't be gained twice
        controller = self.controller
        if controller is None:
            return
        self._prepared = True
        copy_spell_card = SwordsToPlowshares(owner=controller, controller=controller)
        controller.zones[Zone.EXILE].add(copy_spell_card)
        self._prepare_copy = copy_spell_card

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepare-spell copy from exile, paying its {W} cost
        (rule 722.3c: the copy is cast normally).  Casting it unprepares
        this creature.

        Raises:
            CastingError: If not prepared, the cost can't be paid, or the
                copy has no legal target.
        """
        from engine.casting import CastingError, cast_spell_free
        from engine.types import ManaType

        controller = self.controller
        copy_spell_card = self._prepare_copy
        if not self._prepared or copy_spell_card is None or controller is None:
            raise CastingError("Not prepared — no prepare spell to cast")
        if not game.get_battlefield(controller).contains(self):
            raise CastingError("Prepared permanent is no longer on the battlefield")
        if not copy_spell_card.can_cast(game):
            raise CastingError("No legal target for Swords to Plowshares")
        if not controller.mana_pool.pay(
            ManaCost.parse("{W}"), for_instant_sorcery=True
        ):
            raise CastingError("Cannot pay {W} for the prepare spell")
        try:
            cast_spell_free(game, controller, copy_spell_card, Zone.EXILE)
        except CastingError:
            controller.mana_pool.add(ManaType.WHITE, 1)  # refund
            raise
        # The designation is lost as the spell becomes cast (rule 722.3c),
        # and the cast copy ceases to exist once it leaves the stack —
        # modeled by the token state-based action.
        self._prepared = False
        self._prepare_copy = None
        copy_spell_card.is_token = True
