"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. "
            "(As you cast that spell, you may sacrifice a creature with power 1 "
            "or greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    def get_casualty_value(self, card: Any) -> int | None:
        """Return 1 if *card* is an instant or sorcery controlled by this card's controller.

        Returns None (falsy) for non-instant/sorcery cards, opponent's cards,
        or when this permanent has no controller.
        """
        # Guard: uncontrolled Silverquill grants nothing.
        ctrl = getattr(self, "controller", None)
        if ctrl is None:
            return None

        # Only grant casualty to spells controlled by this dragon's controller.
        card_ctrl = getattr(card, "controller", None) or getattr(card, "owner", None)
        if card_ctrl is not None and card_ctrl is not ctrl:
            return None

        # Only instants and sorceries qualify.
        card_types = getattr(card, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return 1

        return None

    def _apply_casualty_for_spell(self, game: "GameState", spell: Any) -> None:
        """Apply the casualty 1 mechanic for *spell* if applicable.

        Casualty 1 only applies to instants and sorceries.  If there are no
        eligible creatures with power >= 1 on the controller's battlefield,
        the casualty offer is skipped.  Otherwise the controller is asked
        whether they want to sacrifice a creature; if yes they choose which
        creature (power >= 1) to sacrifice, the creature goes to the
        graveyard, and a copy of the spell is pushed onto the stack.

        Parameters:
            game: The current game state.
            spell: The card being cast (must be instant or sorcery for casualty
                to apply).
        """
        from engine.game import sacrifice
        from engine.player import ScriptExhaustedError
        from engine.stack import StackObject, copy_spell

        # Casualty only applies to instants and sorceries.
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Resolve controller: use spell.controller as the primary source.
        # Only skip if spell.controller is actually None — do not silently fall
        # back to self.controller, which would incorrectly apply casualty to
        # uncontrolled or opponent spells.
        ctrl = spell.controller
        if ctrl is None:
            return

        # Only apply casualty when the spell's controller matches Silverquill's
        # controller.  Opponent's spells must not trigger this effect.
        if ctrl is not self.controller:
            return

        # Collect eligible sacrifice targets: creatures with power >= 1
        # controlled by ctrl that are on the battlefield.
        # Silverquill itself is excluded — it cannot be its own casualty sacrifice.
        bf = game.get_battlefield(ctrl)
        eligibles = [
            c for c in bf.get_all()
            if (
                c is not self
                and CardType.CREATURE in getattr(c, "card_types", set())
                and getattr(c, "power", getattr(c, "base_power", 0)) >= 1
            )
        ]

        # If no eligible creatures, casualty cannot be used.
        if not eligibles:
            return

        # Ask the controller if they want to use casualty.
        try:
            wants_casualty = ctrl.choose_yes_no(
                "Silverquill, the Disputant: Sacrifice a creature for casualty 1?"
            )
        except ScriptExhaustedError:
            wants_casualty = False

        if not wants_casualty:
            return

        # Ask which creature to sacrifice.
        try:
            chosen = ctrl.choose_card(eligibles, "Choose a creature to sacrifice for casualty 1")
        except ScriptExhaustedError:
            chosen = eligibles[0] if eligibles else None

        if chosen is None:
            return

        # Sacrifice the chosen creature.
        sacrifice(game, ctrl, chosen)

        # Use the engine's copy_spell utility (via a temporary StackObject wrapper)
        # so the copy has independent mutable state and avoids shared-state bugs.
        original_targets = list(getattr(spell, "chosen_targets", []))
        temp_stack_obj = StackObject(
            source=spell,
            controller=ctrl,
            targets=original_targets,
        )
        copy_obj = copy_spell(game, temp_stack_obj, ctrl)
        game.stack.push(copy_obj)

    def register_triggers(self, game: "GameState") -> None:
        """Register a trigger so each instant/sorcery the controller casts has casualty 1."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        # Use a mutable container to pass the matched spell from _condition to
        # _effect since the TriggerRegistration effect receives only (game).
        _pending: list[Any] = []

        def _condition(g: "GameState", event: Any) -> bool:
            # Silverquill must still be on the battlefield.
            ctrl = source.controller
            if ctrl is None:
                return False
            on_bf = any(
                g.get_battlefield(p).contains(source) for p in g.players
            )
            if not on_bf:
                return False

            # Only fire for instant/sorcery spells cast by Silverquill's controller.
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            spell_ctrl = getattr(spell, "controller", None)
            if spell_ctrl is not ctrl:
                return False
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False

            # Capture spell reference so _effect can invoke casualty.
            _pending.clear()
            _pending.append(spell)
            return True

        def _effect(g: "GameState") -> None:
            if not _pending:
                return
            spell = _pending.pop()
            source._apply_casualty_for_spell(g, spell)

        ctrl = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=ctrl,
            )
        )
