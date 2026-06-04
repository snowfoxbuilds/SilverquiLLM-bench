"""Card implementation for Silverquill, the Disputant (SOS 226).

Silverquill is a {2}{W}{B} 4/4 Legendary Elder Dragon with Flying and
Vigilance.  Its payoff line grants **casualty 1** to every instant and
sorcery spell its controller casts:

    "Each instant and sorcery spell you cast has casualty 1. (As you cast
     that spell, you may sacrifice a creature with power 1 or greater. When
     you do, copy the spell and you may choose new targets for the copy.)"

Casualty (rule 702.153) has no dedicated engine surface, so the grant is
modelled through the existing cast-trigger machinery: a
:class:`~engine.events.SpellCastTriggeredEvent` trigger scoped to the
controller's own instant/sorcery spells (and only while Silverquill is on
the battlefield).  Resolving the trigger offers the optional casualty
sacrifice (``choose_yes_no``), selects a power>=1 creature (``choose_card``
when more than one is eligible, else auto-selected), sacrifices it via
:func:`engine.game.sacrifice`, then copies the spell via
:func:`engine.stack.copy_spell` (optionally choosing new targets for the
copy).

``SpellCastTriggeredEvent`` is now fired by ``engine.casting.cast_spell``
itself (additive engine change), so the same wiring also fires when a spell
is cast through the normal pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant — {2}{W}{B} 4/4 Legendary Elder Dragon.

    Flying, vigilance.  Each instant and sorcery spell you cast has
    casualty 1.

    SOS collector number 226.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault("colors", {Color.WHITE, Color.BLACK})
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1. (As you "
            "cast that spell, you may sacrifice a creature with power 1 or "
            "greater. When you do, copy the spell and you may choose new "
            "targets for the copy.)",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Casualty grant — wired through the spell-cast trigger machinery.
    # ------------------------------------------------------------------
    def register_triggers(self, game: GameState) -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _spell_from_event(event: Any) -> Any:
            return getattr(event, "spell", None) or getattr(event, "card", None)

        def _condition(game: Any, event: Any) -> bool:
            # Static ability only functions while Silverquill is on the battlefield.
            if not _is_on_battlefield(game, source):
                return False
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            spell = _spell_from_event(event)
            if spell is None:
                return False
            # Only spells YOU cast qualify.
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            spell_controller = getattr(spell, "controller", None)
            if caster is not controller and spell_controller is not controller:
                return False
            # Only instant and sorcery spells get casualty.
            card_types = getattr(spell, "card_types", set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            # Stash the spell so the effect can copy the right object.
            source._casualty_spell = spell
            return True

        def _effect(game: GameState) -> None:
            self._resolve_casualty(game)

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

    # ------------------------------------------------------------------
    # Casualty resolution
    # ------------------------------------------------------------------
    def _resolve_casualty(self, game: GameState) -> None:
        """Offer the casualty sacrifice and, if paid, copy the spell.

        Contract (rule 702.153 modelled as a "when you cast" trigger):

        * Optional via ``controller.choose_yes_no``.
        * Sacrifice target chosen via ``controller.choose_card`` among
          creatures with power >= 1 the controller controls (auto-selected
          when exactly one is eligible).  A 0-power creature is never
          eligible; with no eligible creature there is no sacrifice and no
          copy.
        * The chosen creature is sacrificed via :func:`engine.game.sacrifice`.
        * The spell is copied via :func:`engine.stack.copy_spell`; the
          controller may choose new targets for the copy.
        """
        from engine.game import sacrifice
        from engine.stack import StackObject, copy_spell

        controller = getattr(self, "controller", None)
        spell = getattr(self, "_casualty_spell", None)
        # Clear stash so a later trigger does not reuse a stale spell.
        self._casualty_spell = None
        if controller is None or spell is None:
            return

        # Eligible sacrifices: creatures the controller controls with
        # power >= 1.  Silverquill itself is excluded as the casualty
        # sacrifice candidate so the grant operates on the controller's
        # other creatures.
        eligible = [
            c
            for c in game.get_battlefield(controller).get_all()
            if c is not self
            and CardType.CREATURE in getattr(c, "card_types", set())
            and getattr(c, "power", 0) >= 1
        ]
        if not eligible:
            return

        # Optional ("you may").
        if not controller.choose_yes_no(
            "Pay casualty 1 — sacrifice a creature with power 1 or greater?"
        ):
            return

        if len(eligible) == 1:
            chosen = eligible[0]
        else:
            chosen = controller.choose_card(
                eligible, "Choose a creature to sacrifice for casualty"
            )
        if chosen is None or chosen not in eligible:
            return

        sacrifice(game, controller, chosen)

        # Locate (or synthesise) the original spell's StackObject so we can
        # copy it.  When cast through the normal pipeline the spell has a live
        # StackObject on the game stack; otherwise wrap the spell directly.
        original_so = None
        for so in game.stack.objects():
            if so.source is spell:
                original_so = so
                break
        if original_so is None:
            original_so = StackObject(
                source=spell,
                controller=controller,
                targets=list(getattr(spell, "chosen_targets", []) or []),
            )

        new_targets = self._choose_new_targets(game, controller, original_so)
        copy_obj = copy_spell(game, original_so, controller, new_targets)
        game.stack.push(copy_obj)

    @staticmethod
    def _choose_new_targets(
        game: GameState, controller: Any, original_so: Any
    ) -> list[Any] | None:
        """Optionally choose new targets for the casualty copy.

        Returns ``None`` to keep the original targets (the default), or a new
        list of targets when the controller elects to re-target.  Mirrors the
        FDN copy-with-new-targets convention (FDN 248).
        """
        if not original_so.targets:
            return None
        spell = original_so.source
        get_targets = getattr(spell, "get_targets", None)
        if get_targets is None:
            return None
        if not controller.choose_yes_no(
            f"Choose new targets for the copy of {getattr(spell, 'name', 'the spell')}?"
        ):
            return None

        requirements = get_targets(game) or []
        new_targets: list[Any] = []
        for req in requirements:
            filter_fn = getattr(req, "filter_fn", None)
            legal: list[Any] = []
            for p in game.players:
                for obj in game.get_battlefield(p).get_all():
                    if filter_fn is None or filter_fn(obj):
                        legal.append(obj)
                if filter_fn is None or filter_fn(p):
                    legal.append(p)
            if legal:
                new_targets.append(controller.choose_target(legal, req))
        return new_targets or None

    def on_resolve(self, game: GameState) -> None:
        # Silverquill is a creature permanent; its grant is a static ability
        # handled via register_triggers, so resolution itself is a no-op.
        pass
