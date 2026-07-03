"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SwordsToPlowshares(Instant):
    """Swords to Plowshares — {W} — Instant.

    Exile target creature. Its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost(pips={ManaType.WHITE: 1}))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        target = targets[0] if targets else None
        if target is None:
            return
        power = getattr(target, "power", 0) or 0
        target_ctrl = getattr(target, "controller", None)
        from engine.zones import move_to_zone
        # Only move if still on battlefield
        for p in game.players:
            if game.get_battlefield(p).contains(target):
                move_to_zone(game, target, Zone.BATTLEFIELD, Zone.EXILE)
                break
        if target_ctrl is not None:
            target_ctrl.life += power


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.
    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost(generic=1, pips={ManaType.WHITE: 2}))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.\n"
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self._prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register ETB trigger: create Inkling token, maybe become prepared."""
        from engine.events import EntersBattlefieldTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(g: Any, event: Any) -> bool:
            return event.permanent is source

        def _effect(g: "GameState") -> None:
            from engine.card import Creature as _Creature
            from engine.game import create_token

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Choose target player for the Inkling token.
            players = list(g.players)
            try:
                target_player = ctrl.choose_card(players, "Choose target player for Inkling token")
            except Exception:
                target_player = ctrl
            if target_player is None:
                target_player = ctrl

            inkling = _Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            create_token(g, target_player, inkling)

            # Count creatures: if any opponent has more than controller → prepared.
            ctrl_bf = [
                c for c in g.get_battlefield(ctrl).get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            ]
            ctrl_count = len(ctrl_bf)
            for opp in g.players:
                if opp is ctrl:
                    continue
                opp_count = sum(
                    1
                    for c in g.get_battlefield(opp).get_all()
                    if CardType.CREATURE in getattr(c, "card_types", set())
                )
                if opp_count > ctrl_count:
                    source._prepared = True
                    break

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
        """While prepared, may cast a copy of Swords to Plowshares from exile."""
        source = self

        def _cost(g: "GameState") -> bool:
            return source._prepared

        def _effect(g: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Create a copy of Swords to Plowshares and put it in exile.
            swords_copy = SwordsToPlowshares()
            swords_copy.owner = ctrl
            swords_copy.controller = ctrl
            ctrl.zones[Zone.EXILE].add(swords_copy)

            from engine.casting import cast_spell_free
            try:
                cast_spell_free(g, ctrl, swords_copy, Zone.EXILE)
                source._prepared = False  # unprepare only on successful cast
            except Exception:
                # Clean up copy from exile if cast failed
                exile = ctrl.zones[Zone.EXILE]
                if exile.contains(swords_copy):
                    exile.remove(swords_copy)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="While prepared: cast a copy of Swords to Plowshares.",
            )
        ]
