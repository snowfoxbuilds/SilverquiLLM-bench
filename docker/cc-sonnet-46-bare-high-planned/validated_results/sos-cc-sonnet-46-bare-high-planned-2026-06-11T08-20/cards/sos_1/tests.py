"""Tests for The Dawning Archaic (sos_1)."""

import pytest
from test_utils import create_game, set_board_state, declare_attackers
from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.types import ManaCost, ManaType, Zone, CardType


class TestTheDawningArchaic:
    def test_cost_reduction_empty_graveyard(self):
        """No reduction when graveyard is empty."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        archaic.owner = p1
        archaic.controller = p1
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, archaic, p1)
        assert reduction == 0

    def test_cost_reduction_counts_instants_sorceries(self):
        """Cost reduces by 1 per instant/sorcery in graveyard."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        archaic.owner = p1
        archaic.controller = p1

        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        instant.owner = p1
        sorcery = Sorcery(name="Divination", mana_cost=ManaCost.parse("{2}{U}"))
        sorcery.owner = p1
        creature = Creature(name="Bear", base_power=2, base_toughness=2)
        creature.owner = p1

        set_board_state(game, 0, graveyard=[instant, sorcery, creature])
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, archaic, p1)
        assert reduction == 2  # instant + sorcery, creature doesn't count

    def test_cost_reduction_capped_at_10(self):
        """Reduction is clamped at the generic mana cost (10 for Archaic)."""
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic()
        archaic.owner = p1
        archaic.controller = p1
        # Put 15 instants in graveyard
        for i in range(15):
            c = Instant(name=f"Spell{i}", mana_cost=ManaCost.parse("{R}"))
            c.owner = p1
            p1.zones[Zone.GRAVEYARD].add(c)
        from engine.casting import get_cost_reduction
        reduction = get_cost_reduction(game, archaic, p1)
        assert reduction == 10  # capped at generic cost

    def test_reach_keyword(self):
        """Archaic has Reach keyword."""
        from engine.types import Keyword
        archaic = TheDawningArchaic()
        assert Keyword.REACH in archaic.keywords

    def test_attack_trigger_exiles_cast_spell(self):
        """Attack trigger: cast instant from graveyard, it gets exiled after resolve."""
        game = create_game()
        p1, p2 = game.players

        class DoNothingInstant(Instant):
            def __init__(self):
                super().__init__(name="DoNothing", mana_cost=ManaCost.parse("{R}"))

        instant = DoNothingInstant()
        instant.owner = p1
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False

        set_board_state(game, 0, battlefield=[archaic], graveyard=[instant])
        set_board_state(game, 1, life=20)
        # Register triggers (set_board_state bypasses move_to_zone)
        archaic.register_triggers(game)

        # Script: choose the instant to cast, then resolve it
        p1._script.appendleft(instant)  # choose_card for attack trigger

        declare_attackers(game, ["The Dawning Archaic"])
        # Resolve the attack trigger (which casts the instant for free)
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # The instant should now be in exile, not graveyard
        exile = p1.zones[Zone.EXILE].get_all()
        graveyard = p1.zones[Zone.GRAVEYARD].get_all()
        assert instant in exile, "Spell cast from graveyard should be exiled after resolving"
        assert instant not in graveyard, "Spell should NOT be in graveyard"

    def test_attack_trigger_no_legal_target_does_nothing(self):
        """Attack trigger with empty graveyard: no prompts, nothing happens."""
        game = create_game()
        p1, p2 = game.players
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False

        set_board_state(game, 0, battlefield=[archaic])
        set_board_state(game, 1, life=20)
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        # No choose_card script needed — should auto-do-nothing
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)
        # No error means success

    def test_attack_trigger_decline_cast(self):
        """Player may decline to cast by returning None from choose_card."""
        game = create_game()
        p1, p2 = game.players

        instant = Instant(name="Bolt", mana_cost=ManaCost.parse("{R}"))
        instant.owner = p1
        archaic = TheDawningArchaic()
        archaic.summoning_sick = False

        set_board_state(game, 0, battlefield=[archaic], graveyard=[instant])
        set_board_state(game, 1, life=20)
        archaic.register_triggers(game)

        p1._script.appendleft(None)  # player declines

        declare_attackers(game, ["The Dawning Archaic"])
        from test_utils import _resolve_top_of_stack
        _resolve_top_of_stack(game)

        # Instant stays in graveyard
        assert instant in p1.zones[Zone.GRAVEYARD].get_all()
