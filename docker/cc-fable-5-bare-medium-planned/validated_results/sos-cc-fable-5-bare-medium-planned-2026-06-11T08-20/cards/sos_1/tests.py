"""Tests for The Dawning Archaic (sos_1)."""

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.stack import priority_loop
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, declare_attackers, set_board_state, cast_spell


class LifeGainInstant(Instant):
    """Targetless instant: you gain 1 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Lifegain Trick")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


class TestTheDawningArchaic:
    def test_cost_reduction_per_instant_sorcery_in_graveyard(self):
        game = create_game()
        gy = [
            Instant(name="I1", mana_cost=ManaCost.parse("{1}")),
            Sorcery(name="S1", mana_cost=ManaCost.parse("{1}")),
            Instant(name="I2", mana_cost=ManaCost.parse("{1}")),
            Creature(name="DeadBear", base_power=2, base_toughness=2),
        ]
        set_board_state(game, 0, hand=[TheDawningArchaic()], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        # {10} less {3} (creature in gy does not count) = {7}
        cast_spell(game, 0, "The Dawning Archaic")
        assert game.players[0].mana_pool.total() == 0
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "The Dawning Archaic" for c in bf.get_all())

    def test_has_reach(self):
        card = TheDawningArchaic()
        assert Keyword.REACH in card.keywords

    def test_attack_trigger_casts_from_graveyard_and_exiles(self):
        game = create_game(scripts=(["pass"] * 12, ["pass"] * 12))
        p0 = game.players[0]
        archaic = TheDawningArchaic()
        trick = LifeGainInstant()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[trick])
        archaic.summoning_sick = False
        # Re-register triggers since set_board_state bypasses move_to_zone
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)

        assert p0.life == 21  # spell resolved
        assert game.get_exile(p0).contains(trick)  # exiled instead of graveyard
        assert not game.get_graveyard(p0).contains(trick)

    def test_attack_trigger_empty_graveyard_no_action(self):
        game = create_game(scripts=(["pass"] * 8, ["pass"] * 8))
        archaic = TheDawningArchaic()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[])
        archaic.summoning_sick = False
        archaic.register_triggers(game)

        declare_attackers(game, ["The Dawning Archaic"])
        priority_loop(game)
        assert game.players[0].life == 20

    def test_reduction_clamps_at_zero_generic(self):
        game = create_game()
        gy = [Instant(name=f"I{i}", mana_cost=ManaCost.parse("{1}")) for i in range(12)]
        set_board_state(game, 0, hand=[TheDawningArchaic()], graveyard=gy, mana={})
        # 12 instants -> reduction clamps to generic (10); cast for free
        cast_spell(game, 0, "The Dawning Archaic")
        bf = game.get_battlefield(game.players[0])
        assert any(c.name == "The Dawning Archaic" for c in bf.get_all())
