"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 Legendary Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black Inkling
    creature token with flying. Then if an opponent controls more creatures than you,
    this creature becomes prepared. (While it's prepared, you may cast a copy of its
    spell. Doing so unprepares it.)

    The 'spell' is Swords to Plowshares (back face): exile target creature; its
    controller gains life equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent controls "
            "more creatures than you, this creature becomes prepared. (While it's "
            "prepared, you may cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def get_targets(self, game: "GameState") -> list:
        """ETB trigger targets: target player."""
        return []  # Target is chosen inside the ETB trigger handler

    def register_triggers(self, game: "GameState") -> None:
        """Push the ETB effect directly onto the stack.

        The engine fires EntersBattlefieldTriggeredEvent BEFORE calling
        register_triggers, so TriggerRegistration cannot catch the card's
        own entry. Instead, we push a StackObject here — the card is
        already on the battlefield at this point, so creature counts are
        correct when the effect resolves.
        """
        from engine.game import create_token
        from engine.stack import StackObject

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Choose target player to create token
            try:
                target_player = ctrl.choose(game.players, "choose player to get Inkling")
            except Exception:
                target_player = ctrl

            # Create 1/1 white-black Inkling with flying
            inkling = Creature(
                name="Inkling",
                base_power=1,
                base_toughness=1,
                keywords=Keyword.FLYING,
            )
            create_token(game, target_player, inkling)

            # Check if an opponent controls more creatures than the controller
            ctrl_count = sum(
                1 for p in game.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(p, "card_types", set())
            )
            for opp in game.players:
                if opp is ctrl:
                    continue
                opp_count = sum(
                    1 for p in game.get_battlefield(opp).get_all()
                    if CardType.CREATURE in getattr(p, "card_types", set())
                )
                if opp_count > ctrl_count:
                    source._prepared = True
                    break

        game.stack.push(StackObject(source=source, controller=controller, on_resolve=_effect))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """While prepared, may cast a copy of Swords to Plowshares."""
        source = self

        def _prepared_cost(game: Any, src: Any) -> bool:
            if not source._prepared:
                return False
            return True

        def _prepared_effect(game: "GameState") -> None:
            from engine.casting import cast_spell_free, CastingError
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            # Create a fresh SwordsToPlowshares copy, exile it, then cast from exile
            swords = SwordsToPlowshares()
            swords.owner = ctrl
            swords.controller = ctrl
            exile_zone = game.get_exile(ctrl)
            exile_zone.add(swords)
            try:
                cast_spell_free(game, ctrl, swords, Zone.EXILE)
            except CastingError:
                exile_zone.remove(swords)
                return
            source._prepared = False

        return [
            ActivatedAbility(
                cost=_prepared_cost,
                effect=_prepared_effect,
                description="Cast a copy of Swords to Plowshares (unprepares).",
            )
        ]


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

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

    def get_targets(self, game: "GameState") -> list:
        """Target creature on the battlefield."""
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        """Exile target creature; its controller gains life = its power."""
        from engine.game import exile as _exile

        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Power before exile
        power = getattr(target, "power", 0)
        target_controller = getattr(target, "controller", None)

        _exile(game, target)

        if target_controller is not None and power > 0:
            target_controller.life += power
