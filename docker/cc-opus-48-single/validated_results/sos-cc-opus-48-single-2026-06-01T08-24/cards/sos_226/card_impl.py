"""Card implementation for Silverquill, the Disputant (SOS 226).

{2}{W}{B} Legendary Creature — Elder Dragon, 4/4 (white & black) with Flying
and Vigilance.

Static ability: "Each instant and sorcery spell you cast has casualty 1. (As
you cast that spell, you may sacrifice a creature with power 1 or greater. When
you do, copy the spell and you may choose new targets for the copy.)"

The creature itself (static data, Flying/Vigilance) and the casualty-granting
ability are modeled as card-local helpers the casting machinery (or a test) can
drive:

    * ``casualty_value``                            — the granted casualty number (1)
    * ``grants_casualty_to(game, spell)``           — predicate: your instant/sorcery
    * ``is_valid_casualty_sacrifice(creature)``     — power >= 1 creature
    * ``apply_casualty(game, stack_obj, sac, ...)`` — sacrifice + copy the spell

The deep "as you cast that spell" REAL casting-pipeline integration has no
existing engine hook; see ``# UNVERIFIED`` note below and ``untestable.json``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine import game as game_module
from engine.card import Creature
from engine.stack import StackObject, copy_spell
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature permanent/card."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_instant_or_sorcery(obj: Any) -> bool:
    """Return ``True`` if *obj* is an instant or sorcery spell."""
    types = getattr(obj, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} Elder Dragon, 4/4."""

    #: The granted ability is *casualty 1* (sacrifice one creature, one copy).
    casualty_value: int = 1

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
            "Each instant and sorcery spell you cast has casualty 1. (As you "
            "cast that spell, you may sacrifice a creature with power 1 or "
            "greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)
        self.colors: set[Color] = {Color.WHITE, Color.BLACK}

    # ------------------------------------------------------------------
    # Casualty grant — which spells qualify
    # ------------------------------------------------------------------

    def grants_casualty_to(self, game: "GameState", spell: Any) -> bool:
        """Return ``True`` if *spell* is one of your instant/sorcery spells.

        "Each instant and sorcery spell **you** cast has casualty 1." Only the
        Silverquill controller's instant and sorcery spells qualify; creature
        spells and opponents' spells do not.
        """
        if not _is_instant_or_sorcery(spell):
            return False
        return getattr(spell, "controller", None) is self.controller

    # ------------------------------------------------------------------
    # Casualty sacrifice legality
    # ------------------------------------------------------------------

    def is_valid_casualty_sacrifice(self, creature: Any) -> bool:
        """Return ``True`` if *creature* may be sacrificed for casualty.

        The casualty cost is "sacrifice a creature with power 1 or greater."
        """
        if not _is_creature(creature):
            return False
        power = getattr(creature, "power", None)
        if power is None:
            power = getattr(creature, "base_power", 0)
        return power >= 1

    # ------------------------------------------------------------------
    # Applying casualty — sacrifice + copy the spell
    # ------------------------------------------------------------------

    def apply_casualty(
        self,
        game: "GameState",
        spell_stack_object: StackObject,
        sacrifice_creature: Any,
        new_targets: list[Any] | None = None,
    ) -> StackObject:
        """Pay casualty: sacrifice *sacrifice_creature* and copy the spell.

        Sacrifices the chosen creature, then places exactly one copy of the
        spell on the stack controlled by the spell's controller (you), carrying
        *new_targets* when supplied (else the original's targets).

        Returns the copy's :class:`StackObject` (now on top of the stack).
        """
        controller = spell_stack_object.controller
        sac_controller = getattr(sacrifice_creature, "controller", controller)
        game_module.sacrifice(game, sac_controller, sacrifice_creature)

        copy_obj = copy_spell(
            game,
            spell_stack_object,
            controller,
            new_targets=new_targets,
        )
        game.stack.push(copy_obj)
        return copy_obj

    # ------------------------------------------------------------------
    # As-you-cast pipeline integration
    # ------------------------------------------------------------------
    # UNVERIFIED: "As you cast that spell, you may sacrifice a creature with
    #   power 1 or greater" — the base casting pipeline (engine/casting.py
    #   cast_spell / cast_spell_alternative) exposes no "additional cost as you
    #   cast" / casualty hook, and there is no scriptable choice point to drive
    #   the optional "you may" sacrifice during a real engine-driven cast.
    #   Adding such a hook would touch the heavily-tested cast path with no
    #   no-op-by-default surface available, so the cast pipeline is left
    #   untouched. The card-local helpers above (grants_casualty_to /
    #   is_valid_casualty_sacrifice / apply_casualty) fully model and test the
    #   observable casualty mechanic. See untestable.json.
