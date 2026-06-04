"""Card implementation for Silverquill, the Disputant (SOS 226).

Silverquill, the Disputant is a ``{2}{W}{B}`` Legendary Creature — Elder
Dragon, 4/4, with flying and vigilance. It grants casualty 1 to every instant
and sorcery spell its controller casts:

    "Each instant and sorcery spell you cast has casualty 1. (As you cast that
    spell, you may sacrifice a creature with power 1 or greater. When you do,
    copy the spell and you may choose new targets for the copy.)"

Casualty (CR 702.153) has no native engine pipeline. Following the SOS 201
draw-time miracle convention, the granting is exposed through two surfaces:

* ``CASUALTY_AMOUNT`` / ``grants_casualty_to`` — the capability the additive
  ``engine.casting`` cast hook queries on permanents the caster controls.
* ``offer_casualty`` — the actual casualty offer: given a spell already on the
  stack, optionally sacrifice a controlled creature with power >= 1 and, if so,
  push a ``copy_spell`` of the spell (with optionally-new targets).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.stack import StackObject, copy_spell
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — 4/4 — Legendary Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.

    SOS collector number 226.
    """

    # The granted casualty amount. Exposed as a class constant so the
    # capability contract and the engine cast hook share one source of truth.
    CASUALTY_AMOUNT: int = 1

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
        # Explicit color identity (KEY_DECISIONS sos_13 convention).
        self.colors: list[str] = ["W", "B"]

    # ------------------------------------------------------------------
    # Casualty granting (capability)
    # ------------------------------------------------------------------

    def grants_casualty_to(self, spell: Any) -> int | None:
        """Return the casualty amount this dragon grants *spell*, else ``None``.

        Silverquill grants casualty 1 to every instant and sorcery spell; any
        other card type (creature, land, etc.) gets nothing. This is the
        capability the additive cast hook in :mod:`engine.casting` queries on
        permanents the casting player controls.
        """
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
            return self.CASUALTY_AMOUNT
        return None

    # ------------------------------------------------------------------
    # Casualty offer (the heart of the card)
    # ------------------------------------------------------------------

    def offer_casualty(self, game: "GameState", stack_obj: StackObject) -> bool:
        """Offer casualty for *stack_obj* — a spell already on the stack.

        Fully gated. Returns ``False`` with NO prompt and NO state change when:

        * the spell is not controlled by this dragon's controller, OR
        * the spell is not an instant/sorcery, OR
        * the controller controls no creature with power >= 1 to sacrifice.

        Otherwise the controller is asked (``choose_yes_no``) whether to pay
        casualty; on decline returns ``False``. On accept they ``choose_card`` a
        creature with power >= 1 (power-0 creatures are excluded from the
        options), it is sacrificed (battlefield → graveyard), then they may
        ``choose_yes_no`` to choose new targets (``choose_target``) for the
        copy. A :func:`copy_spell` of the spell — a DISTINCT object,
        ``is_spell=True``, controlled by the dragon's controller, carrying the
        new targets (if chosen) or the original targets — is pushed onto the
        stack, and ``True`` is returned.
        """
        controller = getattr(self, "controller", None)
        if controller is None:
            return False

        # Gate 1: the spell must be controlled by this dragon's controller.
        if getattr(stack_obj, "controller", None) is not controller:
            return False

        # Gate 2: the spell must be an instant or sorcery.
        spell = getattr(stack_obj, "source", None)
        if self.grants_casualty_to(spell) is None:
            return False

        # Gate 3: the controller must control a creature with power >= 1 to
        # sacrifice (power-0 creatures are never legal casualty fodder).
        battlefield = game.get_battlefield(controller)
        fodder = [
            obj
            for obj in battlefield.get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "power", 0) >= 1
        ]
        if not fodder:
            return False

        # "you may pay casualty." This is an optional decision: if the player
        # offers no answer (a scripted player whose script is exhausted), an
        # optional ability is simply declined — never an error.
        from engine.player import ScriptExhaustedError

        try:
            pay = controller.choose_yes_no(
                f"Pay casualty {self.CASUALTY_AMOUNT} for "
                f"{getattr(spell, 'name', 'this spell')!r}?"
            )
        except ScriptExhaustedError:
            return False
        if not pay:
            return False

        # Choose a creature with power >= 1 to sacrifice (power-0 excluded).
        chosen = controller.choose_card(
            fodder, "Choose a creature with power 1 or greater to sacrifice"
        )
        if chosen is None or not battlefield.contains(chosen):
            return False

        # Sacrifice it via the canonical engine helper so that sacrifice
        # replacement effects (SacrificeReplacementEvent) are consulted rather
        # than silently bypassed by a raw move_to_zone. Imported locally to
        # match the SOS engine.game helper-import convention and avoid any
        # import-cycle risk at module load.
        from engine.game import sacrifice

        sacrifice(game, controller, chosen)

        # "you may choose new targets for the copy."
        new_targets: list[Any] | None = None
        if controller.choose_yes_no(
            f"Choose new targets for the copy of {getattr(spell, 'name', 'the spell')!r}?"
        ):
            new_targets = self._choose_new_targets(game, controller, stack_obj)

        # "copy the spell" — push a distinct copy controlled by the controller.
        copy_obj = copy_spell(game, stack_obj, controller, new_targets)
        game.stack.push(copy_obj)
        return True

    @staticmethod
    def _choose_new_targets(
        game: "GameState", controller: Any, stack_obj: StackObject
    ) -> list[Any]:
        """Choose new targets for the copy, one per original target.

        Asks the controller to pick one new target for each target the original
        spell had via ``choose_target``. The legal options are all permanents on
        any battlefield plus the players themselves — the copy retains the same
        number of targets as the original.
        """
        original_targets = list(getattr(stack_obj, "targets", []) or [])
        if not original_targets:
            return []

        legal: list[Any] = []
        for player in game.players:
            legal.append(player)
            for obj in game.get_battlefield(player).get_all():
                legal.append(obj)

        new_targets: list[Any] = []
        for _ in original_targets:
            chosen = controller.choose_target(legal, "Choose a new target for the copy")
            new_targets.append(chosen)
        return new_targets
