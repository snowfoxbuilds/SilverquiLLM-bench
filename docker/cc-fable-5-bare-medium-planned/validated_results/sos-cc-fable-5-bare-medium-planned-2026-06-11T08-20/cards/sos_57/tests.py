"""Tests for Mana Sculpt (sos_57)."""

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Creature, Instant
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase
from test_utils import create_game, set_board_state


def _advance_to_own_precombat_main(game, player):
    """Advance phases until *player*'s precombat main begins (fresh entry)."""
    for _ in range(40):
        game.advance_phase()
        if game.phase is Phase.PRECOMBAT_MAIN and game.active_player is player:
            return
    raise AssertionError("never reached player's precombat main")


def _counter_setup(wizard=True, spell_cost="{2}"):
    game = create_game(scripts=(["pass"] * 20, ["pass"] * 20))
    p0 = game.players[0]
    bf = []
    if wizard:
        bf.append(Creature(name="Lab Wizard", subtypes={"Wizard"},
                           base_power=1, base_toughness=1))
    bear = Creature(name="Bear", base_power=2, base_toughness=2,
                    mana_cost=ManaCost.parse(spell_cost))
    sculpt = ManaSculpt()
    set_board_state(game, 0, battlefield=bf, hand=[bear, sculpt],
                    mana={ManaType.BLUE: 2, ManaType.COLORLESS: 4})
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, p0, bear)          # bear on the stack
    target_so = game.stack.peek()
    p0._script.appendleft(target_so)           # Mana Sculpt's target
    engine_cast_spell(game, p0, sculpt)
    priority_loop(game)
    return game, p0, bear


class TestManaSculpt:
    def test_counters_target_spell(self):
        game, p0, bear = _counter_setup()
        assert game.get_graveyard(p0).contains(bear)
        assert not game.get_battlefield(p0).contains(bear)

    def test_delayed_colorless_with_wizard(self):
        game, p0, _ = _counter_setup(wizard=True, spell_cost="{2}")
        _advance_to_own_precombat_main(game, p0)
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2

    def test_no_wizard_no_delayed_mana(self):
        game, p0, _ = _counter_setup(wizard=False)
        _advance_to_own_precombat_main(game, p0)
        priority_loop(game)
        assert p0.mana_pool.total() == 0

    def test_one_shot_only_first_main_phase(self):
        game, p0, _ = _counter_setup(wizard=True)
        _advance_to_own_precombat_main(game, p0)
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 2
        _advance_to_own_precombat_main(game, p0)
        priority_loop(game)
        assert p0.mana_pool.total() == 0  # trigger unregistered after firing

    def test_amount_is_mana_actually_spent(self):
        # {1}{U}{U} spell countered -> 3 colorless later
        game = create_game(scripts=(["pass"] * 20, ["pass"] * 20))
        p0 = game.players[0]
        wiz = Creature(name="Wiz", subtypes={"Wizard"}, base_power=1, base_toughness=1)
        spell = Instant(name="Pricey Trick", mana_cost=ManaCost.parse("{1}{U}{U}"))
        sculpt = ManaSculpt()
        set_board_state(game, 0, battlefield=[wiz], hand=[spell, sculpt],
                        mana={ManaType.BLUE: 5, ManaType.COLORLESS: 1})
        engine_cast_spell(game, p0, spell)
        p0._script.appendleft(game.stack.peek())
        engine_cast_spell(game, p0, sculpt)
        priority_loop(game)
        _advance_to_own_precombat_main(game, p0)
        priority_loop(game)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 3

    def test_cannot_cast_with_empty_stack(self):
        game = create_game()
        sculpt = ManaSculpt()
        set_board_state(game, 0, hand=[sculpt], mana={ManaType.BLUE: 3})
        assert not sculpt.can_cast(game)
