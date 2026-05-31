"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon 4/4.

    Flying, vigilance
    Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
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
        # Stores the pending spell StackObject waiting for casualty resolution.
        self._pending_casualty_spell: Any = None

    def register_triggers(self, game: "GameState") -> None:
        """Register the casualty-granting trigger for instant/sorcery spells."""
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            caster = getattr(event, "player", None) or getattr(event, "controller", None)
            if caster is not getattr(source, "controller", None):
                return False
            spell_obj = getattr(event, "spell", None)
            if spell_obj is None:
                return False
            card = getattr(spell_obj, "source", spell_obj)
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            # Capture the spell for use in the effect.
            source._pending_casualty_spell = spell_obj
            return True

        def _effect(game: "GameState") -> None:
            spell_obj = source._pending_casualty_spell
            source._pending_casualty_spell = None
            if spell_obj is None:
                return

            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return

            # Find valid sacrifice targets: creatures with power >= 1.
            valid_creatures = _get_valid_casualty_creatures(game, ctrl, min_power=1)
            if not valid_creatures:
                return

            # "You may" — ask controller whether to use casualty.
            try:
                use_casualty = ctrl.choose_yes_no("Use casualty 1?")
            except Exception:
                return

            if not use_casualty:
                return

            # Choose a creature to sacrifice.
            try:
                chosen = ctrl.choose_card(
                    valid_creatures, "Choose a creature to sacrifice for casualty 1"
                )
            except Exception:
                return

            if chosen is None:
                return

            # Validate: chosen creature must still be on battlefield with power >= 1.
            if getattr(chosen, "power", 0) < 1:
                return
            if not _is_on_battlefield(game, ctrl, chosen):
                return

            # Sacrifice the creature.
            from engine.game import sacrifice
            sacrifice(game, ctrl, chosen)

            # Verify the spell is still on the stack.
            if spell_obj not in game.stack._items:
                return

            # Build the copy, offering new targets.
            from engine.stack import copy_spell

            new_targets: list[Any] | None = None
            try:
                choose_new = ctrl.choose_yes_no("Choose new targets for the copy?")
                if choose_new:
                    # Use the same targets as the original by default; the
                    # controller can override this by having scripted targets.
                    new_targets = list(spell_obj.targets)
                    card = getattr(spell_obj, "source", None)
                    if card is not None:
                        try:
                            new_target_specs = card.get_targets(game)
                            if new_target_specs:
                                chosen_targets = []
                                for spec in new_target_specs:
                                    t = ctrl.choose_target(new_target_specs, spec)
                                    chosen_targets.append(t)
                                new_targets = chosen_targets
                        except Exception:
                            pass
            except Exception:
                new_targets = None

            copy_obj = copy_spell(game, spell_obj, ctrl, new_targets=new_targets)
            game.stack.push(copy_obj)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_valid_casualty_creatures(
    game: "GameState", player: Any, *, min_power: int
) -> list[Any]:
    """Return creatures on *player*'s battlefield with power >= *min_power*."""
    bf = game.get_battlefield(player)
    result = []
    for obj in bf.get_all():
        types = getattr(obj, "card_types", set())
        if CardType.CREATURE not in types:
            continue
        if getattr(obj, "power", 0) >= min_power:
            result.append(obj)
    return result


def _is_on_battlefield(game: "GameState", player: Any, permanent: Any) -> bool:
    """Return True if *permanent* is on *player*'s battlefield."""
    return game.get_battlefield(player).contains(permanent)

