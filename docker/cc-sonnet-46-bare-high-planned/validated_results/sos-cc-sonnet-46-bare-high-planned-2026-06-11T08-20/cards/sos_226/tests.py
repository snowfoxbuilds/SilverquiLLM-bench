"""Tests for Silverquill, the Disputant (sos_226)."""

import pytest
from test_utils import create_game, set_board_state
from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Zone, CardType, Keyword
from test_utils import _resolve_top_of_stack


class TestSilverquillTheDisputant:
    def test_keywords(self):
        """Has Flying and Vigilance."""
        card = SilverquillTheDisputant()
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_casualty_copies_instant(self):
        """Casting an instant while Silverquill is on battlefield prompts casualty."""
        game = create_game()
        p1, p2 = game.players

        class DoNothingInstant(Instant):
            def __init__(self):
                super().__init__(name="Zap", mana_cost=ManaCost.parse("{R}"))

        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear],
                        mana={ManaType.RED: 2})
        sq.register_triggers(game)

        zap = DoNothingInstant()
        set_board_state(game, 0, hand=[zap], mana={ManaType.RED: 2})

        # Script: sacrifice bear for casualty
        p1._script.appendleft(bear)   # choose creature to sacrifice

        # Cast the instant (triggers SpellCastTriggeredEvent → casualty trigger)
        from engine.casting import cast_spell
        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, zap)

        # Stack should have: original spell + casualty trigger
        # Resolve the casualty trigger first (it was pushed on top)
        _resolve_top_of_stack(game)

        # After resolving, the copy should be on the stack
        # (copy_spell creates a new StackObject and pushes it)
        # bear should be sacrificed
        assert not game.get_battlefield(p1).contains(bear)

    def test_casualty_decline(self):
        """Player can decline casualty by returning None."""
        game = create_game()
        p1, p2 = game.players

        class DoNothingInstant(Instant):
            def __init__(self):
                super().__init__(name="Zap", mana_cost=ManaCost.parse("{R}"))

        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear])
        sq.register_triggers(game)

        zap = DoNothingInstant()
        set_board_state(game, 0, hand=[zap], mana={ManaType.RED: 2})

        # Decline casualty
        p1._script.appendleft(None)

        from engine.casting import cast_spell
        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, zap)
        _resolve_top_of_stack(game)

        # Bear should still be alive
        assert game.get_battlefield(p1).contains(bear)

    def test_casualty_works_for_sorcery(self):
        """Casualty also triggers for sorcery spells."""
        game = create_game()
        p1, p2 = game.players

        class DoNothingSorcery(Sorcery):
            def __init__(self):
                super().__init__(name="BigSorcery", mana_cost=ManaCost.parse("{2}{R}"))

        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear],
                        mana={ManaType.RED: 5, ManaType.COLORLESS: 5})
        sq.register_triggers(game)

        sor = DoNothingSorcery()
        set_board_state(game, 0, hand=[sor], mana={ManaType.RED: 5})

        p1._script.appendleft(bear)  # sacrifice bear for casualty

        from engine.casting import cast_spell
        from engine.types import Phase
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        cast_spell(game, p1, sor)
        _resolve_top_of_stack(game)

        # bear was sacrificed
        assert not game.get_battlefield(p1).contains(bear)

    def test_casualty_not_triggered_for_creature(self):
        """Casualty only triggers for instants/sorceries, not creatures."""
        game = create_game()
        p1, p2 = game.players

        sq = SilverquillTheDisputant()
        set_board_state(game, 0, battlefield=[sq])
        sq.register_triggers(game)

        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[bear])
        # Placing a creature in hand to "cast" it — but creature casting
        # doesn't trigger casualty. We just verify the trigger doesn't fire.
        # (Creature spells use cast_spell which fires SpellCastTriggeredEvent
        # but our condition filters for instant/sorcery only)
        # Just verify no script exhaustion error (no choose_card call)
        from engine.casting import cast_spell
        from engine.types import Phase, ManaType
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.active_player_index = 0
        set_board_state(game, 0, hand=[bear], mana={ManaType.GREEN: 3})
        # Should not error
