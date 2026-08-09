"""Card implementation for Zimone, Paradox Sculptor."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.events import BeginningOfCombatTriggeredEvent
from engine.stack import surviving_targets
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


def _controls(controller: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is currently controlled by *controller*."""
    return getattr(obj, "controller", None) is controller


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


def _is_creature_or_artifact(obj: Any) -> bool:
    types = getattr(obj, "card_types", set())
    return CardType.CREATURE in types or CardType.ARTIFACT in types


def _choose_up_to_two(
    game: Any,
    controller: Any,
    source: Any,
    candidates: list[Any],
    prompt: str,
) -> list[Any]:
    """Choose up to two *distinct* objects from *candidates* (rule 601.2c).

    Each pick is genuinely declinable ("up to two"), so the result may hold
    zero, one, or two objects. A decline stops the selection.
    """
    chosen: list[Any] = []
    for i in range(min(2, len(candidates))):
        remaining = [c for c in candidates if c not in chosen]
        if not remaining:
            break
        pick = choose_object(
            game,
            controller,
            remaining,
            f"{prompt} ({i + 1}/2)",
            source_card=source,
            optional=True,
        )
        if pick is None:
            break
        chosen.append(pick)
    return chosen


class ZimoneParadoxSculptor(Creature):
    """Zimone, Paradox Sculptor — {2}{G}{U} — 1/4 — Legendary Human Wizard.

    At the beginning of combat on your turn, put a +1/+1 counter on each
    of up to two target creatures you control.
    {G}{U}, {T}: Double the number of each kind of counter on up to two
    target creatures and/or artifacts you control.

    FDN collector number 126.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Zimone, Paradox Sculptor')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}{U}'))
        kwargs.setdefault('subtypes', {'Human', 'Wizard'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'At the beginning of combat on your turn, put a +1/+1 counter on each of up to two target creatures you control.\n{G}{U}, {T}: Double the number of each kind of counter on up to two target creatures and/or artifacts you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register the beginning-of-combat trigger.

        "Put a +1/+1 counter on each of up to two target creatures you control."
        The targets are chosen when the trigger is put on the stack (rule 603.3d)
        via the trigger's ``targeting`` hook — not re-chosen at resolution — and
        revalidated against the activation-time controller and stint on resolve.
        """
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return game.active_player is ctrl

        def _targeting(game: Any, event: Any) -> list[Any]:
            # Fix the targets as the trigger goes on the stack: up to two
            # distinct creatures the trigger's controller controls.
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return []
            candidates = [
                c for c in game.get_battlefield(ctrl).get_all()
                if _is_creature(c) and _controls(ctrl, c)
            ]
            return _choose_up_to_two(
                game, ctrl, source, candidates,
                "creature you control to get a +1/+1 counter",
            )

        def _effect(game: 'GameState', targets: list[Any], context: Any = None) -> None:
            ctrl = context.controller if context is not None else getattr(source, 'controller', None)
            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: _is_creature(t) and _controls(ctrl, t),
            )
            for target in legal:
                add_counter(game, target, '+1/+1')

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfCombatTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                targeting=_targeting,
            )
        )

    def get_activated_abilities(self) -> list:
        """{G}{U}, {T}: Double counters on up to two target creatures/artifacts you control."""
        source = self

        def _can_activate(game: 'GameState', src: Any, controller: Any) -> bool:
            # Legality (rule 602.2a): source on the battlefield and untapped
            # (the {T} cost). Instant speed — no timing gate.
            if controller is None:
                return False
            if getattr(src, 'is_tapped', False):
                return False
            for player in game.players:
                if game.get_battlefield(player).contains(src):
                    return True
            return False

        def _targeting(
            game: 'GameState', src: Any, controller: Any
        ) -> list[Any] | None:
            # Choose up to two distinct creatures/artifacts the controller
            # controls, at activation (rule 602.2b/2c), before the cost is paid.
            # Genuinely optional: an empty list is a legal (zero-target) choice,
            # so this returns [] (never None) even when nothing is chosen.
            candidates = [
                c for c in game.get_battlefield(controller).get_all()
                if _is_creature_or_artifact(c) and _controls(controller, c)
            ]
            return _choose_up_to_two(
                game, controller, src, candidates,
                "creature/artifact you control to double counters on",
            )

        def _cost(game: 'GameState', src: Any = source) -> bool:
            if getattr(src, 'is_tapped', False):
                return False
            ctrl = getattr(src, 'controller', None)
            if ctrl is None:
                return False
            mana_cost = ManaCost.parse('{G}{U}')
            if not ctrl.mana_pool.can_pay(mana_cost):
                return False
            src.is_tapped = True
            ctrl.mana_pool.pay(mana_cost)
            return True

        def _double_effect(
            game: 'GameState', targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import add_counter

            ctrl = context.controller if context is not None else getattr(source, 'controller', None)
            legal = surviving_targets(
                game, context, targets,
                is_legal=lambda t: _is_creature_or_artifact(t) and _controls(ctrl, t),
            )
            for target in legal:
                # Double every kind of counter: adding N of a counter type the
                # object already has N of doubles it.
                for ctype, count in dict(getattr(target, 'counters', {})).items():
                    if count > 0:
                        add_counter(game, target, ctype, count)

        ability = ActivatedAbility(
            cost=_cost,
            effect=_double_effect,
            targeting=_targeting,
            can_activate=_can_activate,
            description='{G}{U}, {T}: Double counters on up to two target creatures/artifacts you control.',
        )
        ability.tap_cost = True
        return [ability]
