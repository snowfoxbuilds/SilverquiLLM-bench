"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.events import MainPhaseBeganTriggeredEvent
from engine.stack import StackObject
from engine.types import ManaCost, ManaType, TargetRequirement, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


def _spell_on_stack(game, player, name="TargetSpell", cost="{2}", mana_spent=2):
    card = Instant(name=name, mana_cost=ManaCost.parse(cost))
    card.owner = player
    card.controller = player
    card.mana_spent = mana_spent
    player.zones[Zone.STACK].add(card)
    obj = StackObject(source=card, controller=player)
    game.stack.push(obj)
    return card, obj


class TestProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestCanCast:
    def test_false_with_empty_stack(self) -> None:
        game = create_game()
        ms = ManaSculpt(owner=game.players[0], controller=game.players[0])
        assert ms.can_cast(game) is False

    def test_true_with_a_spell_on_stack(self) -> None:
        game = create_game()
        p2 = game.players[1]
        _spell_on_stack(game, p2)
        ms = ManaSculpt(owner=game.players[0], controller=game.players[0])
        assert ms.can_cast(game) is True


class TestTargeting:
    def test_target_requirement_present(self) -> None:
        game = create_game()
        _spell_on_stack(game, game.players[1])
        reqs = ManaSculpt(owner=game.players[0]).get_targets(game)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_no_target_when_stack_empty(self) -> None:
        game = create_game()
        assert ManaSculpt(owner=game.players[0]).get_targets(game) == []


class TestCounter:
    def test_counters_spell_to_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card, obj = _spell_on_stack(game, p2, mana_spent=3)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [obj]
        ms.on_resolve(game)
        assert obj not in game.stack.objects()
        assert p2.zones[Zone.GRAVEYARD].contains(card)

    def test_no_delayed_mana_without_wizard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        set_board_state(game, 0, mana={})
        card, obj = _spell_on_stack(game, p2, mana_spent=3)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [obj]
        ms.on_resolve(game)
        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, MainPhaseBeganTriggeredEvent(player=p1)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0


class TestDelayedMana:
    def test_wizard_grants_colorless_next_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(
            name="Academy Wizard",
            base_power=1,
            base_toughness=1,
            subtypes={"Wizard"},
        )
        set_board_state(game, 0, battlefield=[wizard], mana={})
        card, obj = _spell_on_stack(game, p2, mana_spent=4)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [obj]
        ms.on_resolve(game)

        game.active_player_index = 0
        game.trigger_manager.fire_event(
            game, MainPhaseBeganTriggeredEvent(player=p1)
        )
        _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_delayed_mana_fires_once(self) -> None:
        game = create_game()
        p1, p2 = game.players
        wizard = Creature(
            name="Wiz", base_power=1, base_toughness=1, subtypes={"Wizard"}
        )
        set_board_state(game, 0, battlefield=[wizard], mana={})
        card, obj = _spell_on_stack(game, p2, mana_spent=2)
        ms = ManaSculpt(owner=p1, controller=p1)
        ms.chosen_targets = [obj]
        ms.on_resolve(game)
        game.active_player_index = 0
        for _ in range(2):
            game.trigger_manager.fire_event(
                game, MainPhaseBeganTriggeredEvent(player=p1)
            )
            _resolve_top_of_stack(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == 2
