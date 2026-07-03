"""Card implementation for Root Manipulation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery, Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RootManipulation(Sorcery):
    """Root Manipulation — {3}{B}{G} — Sorcery.

    Until end of turn, creatures you control get +2/+2 and gain menace and
    "Whenever this creature attacks, you gain 1 life."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Root Manipulation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{G}"))
        kwargs.setdefault(
            "rules_text",
            'Until end of turn, creatures you control get +2/+2 and gain menace '
            'and "Whenever this creature attacks, you gain 1 life."',
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Apply +2/+2, menace, and attack trigger to all creatures you control."""
        controller = self.controller
        if controller is None:
            return

        bf = game.get_battlefield(controller)
        creatures = [
            obj for obj in bf.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ]

        for creature in creatures:
            # +2/+2 bonus
            creature._temp_power_bonus = getattr(creature, "_temp_power_bonus", 0) + 2
            creature._temp_toughness_bonus = getattr(creature, "_temp_toughness_bonus", 0) + 2

            # Grant menace
            creature.keywords = creature.keywords | Keyword.MENACE

            # Grant attack trigger
            original_trigger = getattr(creature, "trigger_attack", None)
            ctrl_ref = controller

            def _make_trigger(c, orig, ctrl):
                def _trigger_attack(game: "GameState") -> None:
                    ctrl.life += 1
                    if orig is not None:
                        orig(game)
                return _trigger_attack

            creature.trigger_attack = _make_trigger(creature, original_trigger, ctrl_ref)

        # Register EOT cleanup
        if not hasattr(game, "_eot_cleanup_callbacks"):
            game._eot_cleanup_callbacks = []

        captured_creatures = list(creatures)
        original_keywords = {id(c): c.keywords & ~Keyword.MENACE for c in creatures}

        def _cleanup():
            for c in captured_creatures:
                c._temp_power_bonus = getattr(c, "_temp_power_bonus", 0) - 2
                c._temp_toughness_bonus = getattr(c, "_temp_toughness_bonus", 0) - 2
                # Remove menace - restore original keywords
                if id(c) in original_keywords:
                    c.keywords = original_keywords[id(c)]
                # Remove attack trigger
                if hasattr(c, "trigger_attack"):
                    del c.trigger_attack

        game._eot_cleanup_callbacks.append(_cleanup)
