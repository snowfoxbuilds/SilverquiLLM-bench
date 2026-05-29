"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestManaSculptProperties:
    """Static card data should match the card spec."""

    def test_is_an_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should only be cast with a spell on the stack."""

    def test_can_cast_is_false_with_no_spell_on_the_stack(self) -> None:
        game = create_game()

        assert ManaSculpt(owner=None).can_cast(game) is False

    def test_get_targets_returns_a_single_spell_target_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target_spell = Instant(
            name="Target Spell",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 1})

        engine_cast_spell(game, p2, target_spell)

        requirements = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert len(requirements) == 1
        assert isinstance(requirements[0], TargetRequirement)
        assert requirements[0].description == "target spell"
        assert requirements[0].zone == Zone.STACK
        assert requirements[0].filter_fn(game.stack.peek()) is True


class TestManaSculptResolution:
    """Resolution should counter the chosen spell and set up the delayed mana effect."""

    @staticmethod
    def _wizard(owner) -> Creature:
        return Creature(
            name="Student Wizard",
            owner=owner,
            controller=owner,
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
        )

    @staticmethod
    def _advance_until_next_main_phase_for(game, player) -> None:
        for _ in range(20):
            game.advance_phase()
            if game.active_player is player and game.phase in {
                Phase.PRECOMBAT_MAIN,
                Phase.POSTCOMBAT_MAIN,
            }:
                return
        raise AssertionError("Did not reach the player's next main phase")

    def test_on_resolve_without_a_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ManaSculpt(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 0

    def test_casting_it_counters_the_target_spell_and_puts_it_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        target_spell = Instant(
            name="Volcanic Reply",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{R}"),
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 1})

        engine_cast_spell(game, p2, target_spell)
        p1._script.appendleft(game.stack.peek())  # type: ignore[attr-defined]
        engine_cast_spell(game, p1, mana_sculpt)
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p2).contains(target_spell)
        assert p2.zones[Zone.STACK].contains(target_spell) is False
        assert game.stack.is_empty()

    def test_controlling_a_wizard_adds_colorless_equal_to_the_actual_mana_spent_at_your_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        archaic = TheDawningArchaic(owner=p2, controller=p2)

        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            battlefield=[self._wizard(p1)],
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            hand=[archaic],
            graveyard=[
                Instant(name="Opt", mana_cost=ManaCost.parse("{U}")),
                Instant(name="Negate", mana_cost=ManaCost.parse("{1}{U}")),
                Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}")),
            ],
            mana={ManaType.COLORLESS: 7},
        )

        engine_cast_spell(game, p2, archaic)
        p1._script.appendleft(game.stack.peek())  # type: ignore[attr-defined]
        engine_cast_spell(game, p1, mana_sculpt)
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        assert game.get_graveyard(p2).contains(archaic)

        self._advance_until_next_main_phase_for(game, p1)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 7
        assert p1.mana_pool.total() == 7

    def test_without_controlling_a_wizard_it_adds_no_mana_at_your_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)
        target_spell = Instant(
            name="Costly Burst",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{R}"),
        )

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        set_board_state(
            game,
            0,
            hand=[mana_sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        set_board_state(
            game,
            1,
            hand=[target_spell],
            mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
        )

        engine_cast_spell(game, p2, target_spell)
        p1._script.appendleft(game.stack.peek())  # type: ignore[attr-defined]
        engine_cast_spell(game, p1, mana_sculpt)
        while not game.stack.is_empty():
            game.stack.pop().on_resolve(game)

        while game.phase != Phase.POSTCOMBAT_MAIN:
            game.advance_phase()

        assert p1.mana_pool.total() == 0
