"""Reference test for FDN 98 — Ambush Wolf.

Exemplar for an **"up to one target" enters trigger**: the Wolf enters, then
its enters ability goes on the stack choosing up to one target card in a
graveyard (rule 603.3d) and exiles it as it resolves. The single optional
requirement is declinable — with no graveyard card the trigger targets nothing
and the Wolf is unaffected.
"""

from __future__ import annotations

from cards.fdn.fdn_98.card_impl import AmbushWolf
from engine.card import Creature, printed_class
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestAmbushWolfProperties:
    def test_static_data(self):
        card = AmbushWolf(owner=None)
        assert printed_class(card) is AmbushWolf
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert (card.base_power, card.base_toughness) == (4, 2)
        assert card.subtypes == {"Wolf"}
        assert Keyword.FLASH & card.keywords

    def test_target_is_optional(self):
        game = create_game()
        wolf = AmbushWolf(owner=game.players[0], controller=game.players[0])
        set_board_state(game, 0, battlefield=[wolf])
        assert wolf.get_targets(game) == []  # the spell targets nothing
        specs = wolf._enters_targets(game, game.players[0])
        assert len(specs) == 1
        assert specs[0].optional is True


class TestAmbushWolfETB:
    def test_exiles_targeted_graveyard_card(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        wolf = AmbushWolf(owner=p1, controller=p1)
        victim = _bear("Graveyard Bear")
        set_board_state(game, 0, hand=[wolf],
                        mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})
        set_board_state(game, 1, graveyard=[victim])
        game.phase = Phase.PRECOMBAT_MAIN

        cast_spell(game, 0, AmbushWolf, targets=[victim])
        # Exiled from the opponent's graveyard to its owner's exile.
        assert p2.zones[Zone.EXILE].contains(victim)
        assert not game.get_graveyard(p2).contains(victim)
        assert game.get_battlefield(p1).contains(wolf)

    def test_castable_with_zero_targets_when_no_graveyard_card(self):
        """Option-set invariant: 'up to one' declines cleanly with an empty
        candidate set — the Wolf still enters."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        wolf = AmbushWolf(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[wolf],
                        mana={ManaType.GREEN: 1, ManaType.COLORLESS: 2})
        game.phase = Phase.PRECOMBAT_MAIN

        cast_spell(game, 0, AmbushWolf)  # no targets available
        assert game.get_battlefield(p1).contains(wolf)

    def test_option_set_only_graveyard_cards(self):
        """The filter accepts a card sitting in any graveyard and rejects a
        battlefield permanent (not a graveyard card) and the players."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        wolf = AmbushWolf(owner=p1, controller=p1)
        in_gy = _bear("In Graveyard")
        on_bf = _bear("On Battlefield")
        set_board_state(game, 0, battlefield=[wolf, on_bf])
        set_board_state(game, 1, graveyard=[in_gy])

        spec = wolf._enters_targets(game, p1)[0]
        assert spec.filter_fn(in_gy) is True
        assert spec.filter_fn(on_bf) is False
        assert spec.filter_fn(p1) is False
