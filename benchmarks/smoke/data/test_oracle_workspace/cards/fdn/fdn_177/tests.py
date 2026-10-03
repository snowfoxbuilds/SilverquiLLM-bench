"""Reference test for FDN 177 — Macabre Waltz.

"Return UP TO TWO target creature cards from your graveyard" → two optional
requirements. Castable with one or zero creature cards in the graveyard; the
engine returns distinct cards.
"""

from __future__ import annotations

from cards.fdn.fdn_177.card_impl import MacabreWaltz
from engine.card import Creature, Instant
from engine.decisions import GameRef
from engine.intent_player import Intent
from engine.types import ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _corpse(p, name):
    return Creature(name=name, base_power=2, base_toughness=2, owner=p, controller=p)


def _permissive_baseline(player):
    """Answer resolution-time choices (the reflexive 'then discard a card')
    first-offered, as the replay executor's baseline does."""
    player.set_baseline(Intent(pattern=GameRef(), preferences=()))


class TestMacabreWaltzProperties:
    def test_static_data(self):
        mw = MacabreWaltz(owner=None)
        assert mw.name == "Macabre Waltz"
        assert mw.mana_cost == ManaCost.parse("{1}{B}")

    def test_two_optional_graveyard_specs(self):
        mw = MacabreWaltz(owner=None)
        specs = mw.get_targets(create_game())
        assert len(specs) == 2
        assert all(s.optional and s.zone == Zone.GRAVEYARD for s in specs)


class TestMacabreWaltz:
    def test_castable_with_empty_graveyard(self):
        """No creature card in the graveyard: the spell still casts (both
        optional targets skipped) rather than raising CastingError."""
        game = create_game()
        p1 = game.players[0]
        mw = MacabreWaltz(owner=p1, controller=p1)
        spare = Instant(name="Spare", mana_cost=ManaCost.parse("{R}"),
                        owner=p1, controller=p1)
        set_board_state(game, 0, hand=[mw, spare], mana={ManaType.BLACK: 2})
        _permissive_baseline(p1)
        cast_spell(game, 0, "Macabre Waltz")   # no target given → castable
        assert game.get_graveyard(p1).contains(mw)   # resolved to graveyard

    def test_returns_one_creature_card(self):
        game = create_game()
        p1 = game.players[0]
        corpse = _corpse(p1, "Corpse")
        mw = MacabreWaltz(owner=p1, controller=p1)
        spare = Instant(name="Spare", mana_cost=ManaCost.parse("{R}"),
                        owner=p1, controller=p1)
        set_board_state(game, 0, hand=[mw, spare], graveyard=[corpse],
                        mana={ManaType.BLACK: 2})
        _permissive_baseline(p1)   # answers the reflexive discard (picks spare)
        cast_spell(game, 0, "Macabre Waltz", targets=[corpse])
        assert game.get_hand(p1).contains(corpse)   # returned to hand, not discarded
