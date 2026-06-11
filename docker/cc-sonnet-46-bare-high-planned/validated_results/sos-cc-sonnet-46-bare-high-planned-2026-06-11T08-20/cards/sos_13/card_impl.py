"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _get_chosen_target(card: Any, game: Any) -> Any:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


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
        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.zones import move_to_zone

        target = _get_chosen_target(self, game)
        if target is None:
            return

        # Verify still on battlefield
        found = False
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                found = True
                break
        if not found:
            return

        ctrl = getattr(target, "controller", None)
        power = getattr(target, "power", getattr(target, "base_power", 0))

        # Exile target creature
        from engine.game import exile
        exile(game, target)

        # Its controller gains life equal to its power
        if ctrl is not None and power > 0:
            ctrl.life += power


def _make_inkling_token() -> Creature:
    """Create a 1/1 white-black Inkling creature token with flying."""
    token = Creature(
        name="Inkling",
        base_power=1,
        base_toughness=1,
        keywords=Keyword.FLYING,
        subtypes={"Inkling"},
    )
    return token


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} // {W}.

    Creature — Cat Cleric 3/3
    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", set())
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.\n"
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(g: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return

            # Target player creates a 1/1 Inkling with flying.
            target_player = ctrl.choose(g.players, "Choose target player to create Inkling token")
            inkling = _make_inkling_token()
            create_token(g, target_player, inkling)

            # If an opponent controls more creatures than you, become prepared.
            my_creatures = sum(
                1 for c in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            )
            for opp in g.players:
                if opp is ctrl:
                    continue
                opp_creatures = sum(
                    1 for c in g.get_battlefield(opp).get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                )
                if opp_creatures > my_creatures:
                    source._prepared = True
                    break

        game.trigger_manager.register(TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cast_swords_cost(game: Any, src: Any) -> bool:
            # ENGINE LIMITATION: sorcery-speed timing not enforced here.
            return getattr(src, "_prepared", False)

        def _cast_swords_effect(game: Any) -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            if not source._prepared:
                return

            # Create a copy of Swords to Plowshares, put in exile, cast free.
            copy_card = SwordsToPlowshares()
            copy_card.owner = ctrl
            copy_card.controller = ctrl
            ctrl.zones[Zone.EXILE].add(copy_card)

            source._prepared = False  # unprepare

            try:
                from engine.casting import cast_spell_free
                cast_spell_free(game, ctrl, copy_card, Zone.EXILE)
            except Exception:
                pass

        return [ActivatedAbility(
            cost=_cast_swords_cost,
            effect=_cast_swords_effect,
            description="Cast a copy of Swords to Plowshares (while prepared).",
        )]
