"""Card implementation for Silverquill, the Disputant (SOS 226)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} — Legendary Creature — Elder Dragon.

    Flying, vigilance.
    Each instant and sorcery spell you cast has casualty 1.  (As you cast that
    spell, you may sacrifice a creature with power 1 or greater.  When you do,
    copy the spell and you may choose new targets for the copy.)

    SOS collector number 226.
    """

    #: The casualty value Silverquill grants to the instants/sorceries its
    #: controller casts.  "Casualty" is a printed keyword label, NOT an
    #: evergreen ``engine.types.Keyword`` enum member (that enum is frozen at
    #: 16 members), so it is recorded as a printed-keyword label below.
    CASUALTY_LABEL = "Casualty 1"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("subtypes", {"Dragon", "Elder"})
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
        # Explicit colour identity (W+B) so the colour is stable even when the
        # cost is unavailable (e.g. on copies); the cost pips already encode it.
        self.colors: list[Color] = [Color.WHITE, Color.BLACK]
        # Printed-keyword label surface — Casualty is a printed keyword, not an
        # evergreen ``Keyword`` enum member.
        self.printed_keywords: list[str] = [self.CASUALTY_LABEL]

    # ------------------------------------------------------------------
    # Casualty grant — queryable surface
    # ------------------------------------------------------------------

    def get_casualty_value(self, game: "GameState", spell: Any) -> int | None:
        """Return the casualty value this card grants to *spell*, or ``None``.

        Silverquill grants casualty 1 to every instant and sorcery spell *its
        controller casts*.  This is the queryable grant surface the tests probe:
        it returns ``1`` only when

        * Silverquill is on the battlefield,
        * *spell* is an instant or a sorcery, and
        * *spell* is controlled by / in the hand of Silverquill's controller,

        and ``None`` otherwise (creatures, an opponent's spell, etc.).
        """
        from engine.casualty import CASUALTY_ONE, is_instant_or_sorcery

        controller = self.controller
        if controller is None:
            return None
        if not _is_on_battlefield(game, self):
            return None
        if not is_instant_or_sorcery(spell):
            return None
        if not self._spell_is_controllers(game, spell, controller):
            return None
        return CASUALTY_ONE

    def _spell_is_controllers(
        self, game: "GameState", spell: Any, controller: Any
    ) -> bool:
        """Return ``True`` if *spell* belongs to Silverquill's controller.

        The grant only applies to spells *you* cast (CR 702.153a is granted to
        "each instant and sorcery spell you cast").  With no live cast pipeline,
        a spell is treated as the controller's when it is in the controller's
        hand (the observable proxy the tests use) or already controlled by the
        controller (a spell on the stack)."""
        # A spell on the stack carries an explicit controller.
        spell_controller = getattr(spell, "controller", None)
        if spell_controller is controller:
            return True
        # Otherwise treat a card in the controller's hand as the proxy.
        if game.get_hand(controller).contains(spell):
            return True
        # If the spell lives in another player's hand, it is not yours.
        for player in game.players:
            if player is controller:
                continue
            if game.get_hand(player).contains(spell):
                return False
        # Unknown zone with no contradicting evidence — not granted.
        return False

    # ------------------------------------------------------------------
    # Continuous grant + casualty pay/copy hook wiring
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register the continuous casualty grant and the cast/copy hook."""
        self._apply_casualty_grant(game)
        self._register_casualty_cast_hook(game)

    def register_replacement_effects(self, game: "GameState") -> None:
        """Refresh the casualty grant whenever effects are recomputed."""
        self._apply_casualty_grant(game)

    def _apply_casualty_grant(self, game: "GameState") -> None:
        """Write casualty 1 onto every instant/sorcery in the controller's hand.

        Reuses the additive :func:`engine.casualty.grant_casualty_to_hand` so the
        grant is queryable both via :meth:`get_casualty_value` (above) and via the
        ``casualty`` attribute the framework writes onto each affected hand card.
        No-ops while Silverquill is not on the battlefield.
        """
        from engine.casualty import (
            CASUALTY_ONE,
            clear_casualty_grants,
            grant_casualty_to_hand,
        )

        controller = self.controller
        if controller is None:
            return
        if not _is_on_battlefield(game, self):
            clear_casualty_grants(game, self)
            return
        grant_casualty_to_hand(game, self, controller, CASUALTY_ONE)

    def _register_casualty_cast_hook(self, game: "GameState") -> None:
        """Wire the cast-time casualty offer (pay-by-sacrifice + copy, 702.153).

        Registers (deduped per source) a
        :class:`~engine.events.SpellCastTriggeredEvent` trigger that fires when
        Silverquill's controller casts an instant or sorcery spell.  When it
        fires, the controller is offered the optional casualty cost: sacrifice a
        creature with power 1 or greater; on payment, the spell is copied onto
        the stack with optional new targets (CR 702.153a/c)."""
        from engine.casualty import CASUALTY_ONE, is_instant_or_sorcery, offer_casualty
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        registry = getattr(game, "_casualty_cast_hooks", None)
        if registry is None:
            registry = set()
            game._casualty_cast_hooks = registry  # type: ignore[attr-defined]
        if id(self) in registry:
            return
        registry.add(id(self))

        source = self
        controller = self.controller or game.active_player

        def _condition(g: "GameState", event: Any) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if not _is_on_battlefield(g, source):
                return False
            caster = getattr(event, "player", None) or getattr(
                event, "controller", None
            )
            if caster is not ctrl:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None or not is_instant_or_sorcery(spell):
                return False
            source._casualty_pending_spell = spell  # type: ignore[attr-defined]
            return True

        def _effect(g: "GameState") -> None:
            spell = getattr(source, "_casualty_pending_spell", None)
            source._casualty_pending_spell = None  # type: ignore[attr-defined]
            if spell is None:
                return
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            offer_casualty(g, ctrl, spell, CASUALTY_ONE)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
