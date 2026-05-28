"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 Legendary Creature — Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with "
            "power 1 or greater. When you do, copy the spell and you may "
            "choose new targets for the copy.)",
        )
        # Set up supertypes: Legendary
        supertypes = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs["supertypes"] = supertypes
        # Set up subtypes: Elder Dragon
        subtypes = (kwargs.get("subtypes") or set()) | {"Elder", "Dragon"}
        kwargs["subtypes"] = subtypes
        # Keywords: Flying + Vigilance
        existing_kw = kwargs.get("keywords") or Keyword(0)
        kwargs["keywords"] = existing_kw | Keyword.FLYING | Keyword.VIGILANCE

        super().__init__(**kwargs)

        # Will hold the most recently created copy StackObject (per coordinator directives)
        self._last_copy: Any = None

    def register_triggers(self, game: "GameState") -> None:
        """Register the casualty trigger for instants and sorceries."""
        from engine.events import SpellCastTriggeredEvent
        from engine.stack import copy_spell, StackObject
        from engine.triggers import TriggerRegistration
        from engine.types import Zone

        source = self

        def _condition(game: Any, event: Any) -> bool:
            """Fire when the controller casts an instant or sorcery."""
            # Must be the controller casting the spell
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            ctrl = getattr(source, "controller", None)
            if caster is not ctrl:
                return False
            # Must be an instant or sorcery
            spell_card = getattr(event, "card", None)
            if spell_card is None:
                spell_obj = getattr(event, "spell", None)
                spell_card = getattr(spell_obj, "source", None) if spell_obj is not None else None
            if spell_card is None:
                return False
            card_types = getattr(spell_card, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: Any) -> None:
            """Offer casualty sacrifice; if paid, copy the spell."""
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Ask if the controller wants to pay casualty
            try:
                wants_to_sacrifice = ctrl.choose_yes_no(
                    "Pay casualty 1? (Sacrifice a creature with power 1 or greater to copy this spell)"
                )
            except Exception:
                wants_to_sacrifice = False

            if not wants_to_sacrifice:
                return

            # Find legal sacrifice targets: creatures on controller's battlefield with power >= 1
            battlefield = game.get_battlefield(ctrl)
            legal_victims = [
                c for c in battlefield.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", 0) >= 1
            ]

            if not legal_victims:
                return

            # Ask controller to choose a victim
            try:
                victim = ctrl.choose_card(legal_victims, "Choose a creature to sacrifice for casualty")
            except Exception:
                victim = legal_victims[0]

            # Validate the chosen victim has power >= 1
            if getattr(victim, "power", 0) < 1:
                return

            # Sacrifice the victim: move from battlefield to graveyard
            battlefield = game.get_battlefield(ctrl)
            if not battlefield.contains(victim):
                return
            victim_owner = getattr(victim, "owner", ctrl) or ctrl
            battlefield.remove(victim)
            game.get_graveyard(victim_owner).add(victim)

            # Find the spell to copy on the stack (the most recent instant/sorcery
            # pushed by the controller)
            original_so: Any = None
            # Search from top to bottom
            for so in reversed(game.stack._items):
                if getattr(so, "controller", None) is ctrl:
                    spell_card = getattr(so, "source", None)
                    card_types = getattr(spell_card, "card_types", set()) if spell_card else set()
                    if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                        original_so = so
                        break

            if original_so is None:
                return

            # May choose new targets for the copy
            new_targets: list[Any] | None = None
            if original_so.targets:
                try:
                    if ctrl.choose_yes_no(
                        f"Choose new targets for copy of {original_so.source.name}?"
                    ):
                        requirements = getattr(
                            original_so.source, "get_targets", lambda _: []
                        )(game)
                        new_targets = []
                        for req in requirements:
                            legal: list[Any] = []
                            for p in game.players:
                                for obj in game.get_battlefield(p).get_all():
                                    if req.filter_fn(obj):
                                        legal.append(obj)
                                if req.filter_fn(p):
                                    legal.append(p)
                            if legal:
                                chosen = ctrl.choose_target(legal, req)
                                new_targets.append(chosen)
                except Exception:
                    new_targets = None

            # Create and push the copy
            copy_obj = copy_spell(game, original_so, ctrl, new_targets)
            game.stack.push(copy_obj)
            source._last_copy = copy_obj

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
