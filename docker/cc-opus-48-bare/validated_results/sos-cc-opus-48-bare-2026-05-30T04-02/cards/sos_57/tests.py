"""Tests for SOS 57 — Mana Sculpt (counter + delayed Wizard mana)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import create_game, set_board_state


def _put_spell_on_stack(
    game: Any, player: Any, *, name: str = "Victim", mana_spent: int = 3
) -> tuple[Any, StackObject]:
    """Place a dummy sorcery spell on the stack as if it had been cast."""
    victim = Sorcery(name=name, owner=player, controller=player)
    victim.mana_cost = ManaCost.parse("{2}{R}")
    victim.mana_spent = mana_spent  # type: ignore[attr-defined]
    player.zones[Zone.STACK].add(victim)
    obj = StackObject(source=victim, controller=player, on_resolve=lambda g: None)
    game.stack.push(obj)
    return victim, obj


def _resolve_top(game: Any) -> None:
    obj = game.stack.pop()
    obj.on_resolve(game)


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt().name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt().mana_cost == ManaCost.parse("{1}{U}{U}")

    def test_is_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt().card_types

    def test_color(self) -> None:
        assert ManaSculpt().colors == ["U"]


class TestManaSculptCounter:
    def _setup(self, *, with_wizard: bool):
        game = create_game(scripts=([], []))
        p1, p2 = game.players
        sculpt = ManaSculpt(owner=p1, controller=p1)
        battlefield = []
        if with_wizard:
            wiz = Creature(
                name="Wiz",
                owner=p1,
                controller=p1,
                base_power=1,
                base_toughness=1,
                subtypes={"Wizard"},
            )
            wiz.card_types = {CardType.CREATURE}
            battlefield.append(wiz)
        set_board_state(
            game,
            0,
            battlefield=battlefield,
            hand=[sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        victim, victim_obj = _put_spell_on_stack(game, p2, mana_spent=3)
        # Script the counter target for the casting player.
        p1._script.appendleft(victim_obj)
        return game, p1, p2, sculpt, victim, victim_obj

    def test_counters_target_spell(self) -> None:
        game, p1, p2, sculpt, victim, victim_obj = self._setup(with_wizard=False)
        engine_cast_spell(game, p1, sculpt)
        # Stack now holds the victim and Mana Sculpt; resolve Mana Sculpt.
        _resolve_top(game)
        # Victim countered: off the stack, in p2's graveyard.
        assert victim_obj not in game.stack.objects()
        assert not p2.zones[Zone.STACK].contains(victim)
        assert game.get_graveyard(p2).contains(victim)

    def test_wizard_grants_delayed_mana(self) -> None:
        game, p1, p2, sculpt, victim, victim_obj = self._setup(with_wizard=True)
        engine_cast_spell(game, p1, sculpt)
        _resolve_top(game)  # Mana Sculpt resolves, registers delayed trigger
        assert game.stack.is_empty()
        # No mana yet — only at the beginning of the next main phase.
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
        # Fire the controller's next main phase.
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_top(game)  # delayed mana effect resolves
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_delayed_mana_fires_once(self) -> None:
        game, p1, p2, sculpt, victim, victim_obj = self._setup(with_wizard=True)
        engine_cast_spell(game, p1, sculpt)
        _resolve_top(game)
        # First main phase: mana added.
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        _resolve_top(game)
        p1.mana_pool.empty()
        # Second main phase: trigger already unregistered, nothing happens.
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_no_wizard_no_mana(self) -> None:
        game, p1, p2, sculpt, victim, victim_obj = self._setup(with_wizard=False)
        engine_cast_spell(game, p1, sculpt)
        _resolve_top(game)
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.PRECOMBAT_MAIN),
        )
        # No delayed trigger registered → stack stays empty, no mana.
        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
