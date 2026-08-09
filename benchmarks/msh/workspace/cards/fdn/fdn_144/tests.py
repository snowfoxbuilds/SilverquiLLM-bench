"""Reference test for FDN 144 — Mischievous Pup.

Pattern 1 — optional ("up to one") targeted ETB on a creature. The target is a
permanent you control, chosen at cast via a real Player Query, captured on the
stack, and bounced in ``on_resolve``. Because the target is optional, the spell
is castable with zero targets (no legal choice, or a decline). No dead test
backdoors — targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_144.card_impl import MischievousPup
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name="Bear"):
    return Creature(name=name, base_power=2, base_toughness=2)


class TestMischievousPupProperties:
    def test_static_data(self):
        pup = MischievousPup(owner=None)
        assert pup.name == "Mischievous Pup"
        assert pup.mana_cost == ManaCost.parse("{2}{W}")
        assert (pup.base_power, pup.base_toughness) == (3, 1)
        assert "Dog" in pup.subtypes
        assert Keyword.FLASH in pup.keywords


class TestMischievousPupETB:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        pup = MischievousPup(owner=p1, controller=p1)
        bear = _bear()
        set_board_state(game, 0, hand=[pup], battlefield=[bear], mana={ManaType.WHITE: 3})
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        return game, p1, p2, pup, bear

    def test_bounces_chosen_permanent(self):
        game, p1, p2, pup, bear = self._setup()
        cast_spell(game, 0, "Mischievous Pup", targets=[bear])
        assert game.get_hand(p1).contains(bear)          # returned to owner's hand
        assert not game.get_battlefield(p1).contains(bear)
        assert game.get_battlefield(p1).contains(pup)     # the Pup itself entered

    def test_castable_with_no_legal_target(self):
        """'Up to one' → castable when the controller has no other permanent."""
        game = create_game()
        p1, p2 = game.players
        pup = MischievousPup(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[pup], mana={ManaType.WHITE: 3})
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        cast_spell(game, 0, "Mischievous Pup")  # no target offered, no query
        assert game.get_battlefield(p1).contains(pup)

    def test_optional_target_can_be_declined(self):
        """A legal target exists but the controller declines — nothing bounced."""
        game, p1, p2, pup, bear = self._setup()
        # An intent that matches the Pup's target query but expresses no
        # preference: a min==0 (optional) query is declined rather than filled.
        p1.start_intent("decline", Intent(
            pattern=GameRef(card=frozenset({("name", "Mischievous Pup")})),
            preferences=(),
        ))
        cast_spell(game, 0, "Mischievous Pup")
        p1.end_intent("decline")
        assert game.get_battlefield(p1).contains(bear)   # not bounced
        assert game.get_battlefield(p1).contains(pup)
