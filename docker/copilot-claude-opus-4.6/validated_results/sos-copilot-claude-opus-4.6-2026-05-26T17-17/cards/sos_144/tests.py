"""Tests for SOS 144 — Efflorescence.

Efflorescence is a {2}{G} Instant:
  Put two +1/+1 counters on target creature.
  Infusion — If you gained life this turn, that creature also gains
  trample and indestructible until end of turn.
"""

from __future__ import annotations

from cards.sos.sos_144.card_impl import Efflorescence
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestEfflorescenceProperties:
    """Static card data should match spec."""

    def test_is_instant(self) -> None:
        assert isinstance(Efflorescence(owner=None), Instant)

    def test_name(self) -> None:
        assert Efflorescence(owner=None).name == "Efflorescence"

    def test_mana_cost(self) -> None:
        assert Efflorescence(owner=None).mana_cost == ManaCost.parse("{2}{G}")


class TestEfflorescenceResolution:
    """Resolution: counters + conditional trample/indestructible."""

    def _setup_game(self, life_gained_this_turn=False):
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Test Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        bear.plus_one_counters = 0
        bear.keywords = Keyword(0)

        set_board_state(game, 0, battlefield=[bear])

        if life_gained_this_turn:
            # Mark that player gained life this turn
            if hasattr(p1, 'life_gained_this_turn'):
                p1.life_gained_this_turn = 3
            else:
                p1.life_gained_this_turn = 3

        return game, p1, bear

    def test_adds_two_plus_one_counters(self) -> None:
        """Always puts two +1/+1 counters on the target."""
        game, p1, bear = self._setup_game(life_gained_this_turn=False)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.plus_one_counters == 2

    def test_no_life_gain_no_keywords(self) -> None:
        """Without life gained this turn, no trample/indestructible."""
        game, p1, bear = self._setup_game(life_gained_this_turn=False)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.TRAMPLE not in bear.keywords
        assert Keyword.INDESTRUCTIBLE not in bear.keywords

    def test_life_gained_grants_trample(self) -> None:
        """With life gained this turn, target gains trample."""
        game, p1, bear = self._setup_game(life_gained_this_turn=True)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.TRAMPLE in bear.keywords

    def test_life_gained_grants_indestructible(self) -> None:
        """With life gained this turn, target gains indestructible."""
        game, p1, bear = self._setup_game(life_gained_this_turn=True)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert Keyword.INDESTRUCTIBLE in bear.keywords

    def test_counters_still_applied_with_infusion(self) -> None:
        """Counters are always applied, even when infusion triggers."""
        game, p1, bear = self._setup_game(life_gained_this_turn=True)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.plus_one_counters == 2

    def test_power_toughness_after_counters(self) -> None:
        """Power and toughness should reflect the +1/+1 counters."""
        game, p1, bear = self._setup_game(life_gained_this_turn=False)

        spell = Efflorescence(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        assert bear.get_power() == 4
        assert bear.get_toughness() == 4
