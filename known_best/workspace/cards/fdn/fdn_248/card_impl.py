"""Card implementation for Thousand-Year Storm."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment
from engine.card_queries import query_yes_no
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.stack import StackObject


@dataclass(frozen=True)
class _StormTriggerState:
    """Immutable facts one Storm trigger captured when it went on the stack.

    Owned by a single trigger instance (stored on its ``StackObject``), so two
    Storm triggers pending at once never share or overwrite each other's spell
    or count.

    Attributes:
        spell: The instant/sorcery whose cast fired this trigger.
        stack_object: That spell's :class:`~engine.stack.StackObject` at fire
            time. Re-checked at resolution — if it has since left the stack
            (countered, resolved), no copies are made.
        copies: How many copies this trigger must create — the number of instant
            and sorcery spells the fire-time controller had cast *before* this one
            this turn (rule: "for each *other* instant and sorcery spell you've
            cast before it this turn"). Read at fire time as the immutable
            prior-cast count that the casting pipeline stamped on *this exact cast
            occurrence's* StackObject
            (:attr:`~engine.stack.StackObject.prior_qualifying_casts`). Because
            each cast mints its own StackObject, recasting the same physical card
            this turn yields counts 0, 1, 2 …, and "this" cast is excluded exactly
            once — never every earlier occurrence of the same object, as an
            identity filter over raw cast history would wrongly do. Never
            reconstructed from resolved triggers or from a scalar on this
            enchantment.
    """

    spell: Any
    stack_object: "StackObject | None"
    copies: int


class ThousandYearStorm(Enchantment):
    """Thousand-Year Storm — {4}{U}{R} — Enchantment.

    Whenever you cast an instant or sorcery spell, copy it for each
    other instant and sorcery spell you've cast before it this turn.
    You may choose new targets for the copies.

    FDN collector number 248.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Thousand-Year Storm')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{R}'))
        kwargs.setdefault(
            'rules_text',
            "Whenever you cast an instant or sorcery spell, copy it for each "
            "other instant and sorcery spell you've cast before it this turn. "
            "You may choose new targets for the copies.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        # No source-local spell tally lives here. The copy count is read at fire
        # time as the immutable prior-cast count the casting pipeline stamped on
        # the triggering spell's own StackObject (its
        # ``prior_qualifying_casts``) — the number of instant/sorcery spells its
        # controller had cast before this occurrence this turn. That count is
        # fixed once, at the authoritative cast site, from the per-player turn
        # history — so every Storm trigger this turn sees the same count for a
        # given cast (a late or second Storm is not under-counted), and recasting
        # the same physical card counts each occurrence separately (0, 1, 2 …)
        # instead of collapsing them by object identity.

        def _condition(game: Any, event: Any) -> bool:
            # Side-effect free: only decide whether this cast triggers. The
            # controller of "you" is the source's *current* controller.
            ctrl = getattr(source, 'controller', None)
            caster = getattr(event, 'player', None) or getattr(event, 'controller', None)
            if caster is not ctrl:
                return False
            spell = getattr(event, 'spell', None) or getattr(event, 'card', None)
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _capture(game: 'GameState', event: Any, controller: Any) -> _StormTriggerState:
            # Runs as this trigger is put on the stack (fire time), once per
            # matching cast. Fixes this firing's facts immutably: which spell, and
            # how many copies to make.
            #
            # Correlate this trigger to the triggering spell's StackObject now, by
            # identity. At fire time (immediately after this spell was cast) the
            # spell sits on the stack in exactly one StackObject — the stack
            # representation of *this* cast occurrence — so a recast of the same
            # object never confuses this correlation. Stored per-trigger, so a
            # later cast's trigger cannot make this one copy a different spell.
            spell = getattr(event, 'spell', None) or getattr(event, 'card', None)
            original_so: "StackObject | None" = None
            for so in game.stack._items:
                if so.source is spell:
                    original_so = so
                    break
            # The copy count is the prior-cast count the casting pipeline stamped
            # on that occurrence's StackObject — the number of instant and sorcery
            # spells cast *before* this one this turn ("for each *other* … spell").
            # Read straight off the occurrence, so recasting the same object gives
            # 0, 1, 2 …; this occurrence is excluded exactly once (it is counted
            # nowhere in its own prior count), never by an identity filter that
            # would drop every earlier cast of the same object. No StackObject
            # (the spell already left the stack) → no copies to make.
            copies = 0
            if original_so is not None:
                copies = getattr(original_so, 'prior_qualifying_casts', None) or 0
            return _StormTriggerState(spell=spell, stack_object=original_so, copies=copies)

        def _effect(game: 'GameState', controller: Any, state: _StormTriggerState) -> None:
            from engine.stack import copy_spell
            from engine.casting import CastingError, query_spell_target

            if state is None or controller is None:
                return
            copies_to_make = state.copies
            if copies_to_make <= 0:
                return
            original_so = state.stack_object
            # Fail safe: the triggering spell must still be on the stack. If it
            # was countered or otherwise left, this trigger makes no copies — it
            # never falls back to copying some *other* pending spell.
            if original_so is None or original_so not in game.stack._items:
                return
            for _ in range(copies_to_make):
                new_targets: list[Any] | None = None
                if original_so.targets:
                    if query_yes_no(
                        game,
                        controller,
                        f"Choose new targets for copy of {original_so.source.name}?",
                        source_card=source,
                    ):
                        # Re-choose each target through the shared spell-retargeting
                        # path, which applies the COMPLETE cast-time legality
                        # contract *for the copied spell*: zone, the (arity-aware,
                        # so dependent) target filter, distinctness via `exclude`,
                        # and protection from the copied spell — a protected
                        # permanent is never offered. A required spec with no legal
                        # target, or a declined optional one, keeps the original
                        # target at that position.
                        specs = original_so.source.get_targets(game)
                        new_targets = []
                        for i, spec in enumerate(specs):
                            try:
                                chosen = query_spell_target(
                                    game,
                                    controller,
                                    original_so.source,
                                    spec,
                                    exclude=new_targets,
                                )
                            except CastingError:
                                chosen = None
                            if chosen is None and i < len(original_so.targets):
                                chosen = original_so.targets[i]
                            new_targets.append(chosen)
                copy_obj = copy_spell(game, original_so, controller, new_targets)
                game.stack.push(copy_obj)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
            capture=_capture,
        ))
