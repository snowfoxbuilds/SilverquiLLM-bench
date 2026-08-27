"""Reference test for FDN 98 — Ambush Wolf.

Exemplar for an **"up to one target" ETB** (Phase D, Pattern 1 with
``optional=True``): the enters ability exiles up to one target card from a
graveyard. The single optional requirement is declinable — an empty graveyard
set casts the creature with zero targets rather than making it uncastable.
"""

from __future__ import annotations

from cards.fdn.fdn_98.card_impl import AmbushWolf
from engine.card import Creature
from engine.types import Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


class TestAmbushWolfProperties:
    def test_static_data(self):
        card = AmbushWolf(owner=None)
        assert card.name == "Ambush Wolf"
        assert card.mana_cost == ManaCost.parse("{2}{G}")
        assert (card.base_power, card.base_toughness) == (4, 2)
        assert card.subtypes == {"Wolf"}
        assert Keyword.FLASH & card.keywords

    def test_target_is_optional(self):
        game = create_game()
        wolf = AmbushWolf(owner=game.players[0], controller=game.players[0])
        set_board_state(game, 0, battlefield=[wolf])
        specs = wolf.get_targets(game)
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

        cast_spell(game, 0, "Ambush Wolf", targets=[victim])
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

        cast_spell(game, 0, "Ambush Wolf")  # no targets available
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

        spec = wolf.get_targets(game)[0]
        assert spec.filter_fn(in_gy) is True
        assert spec.filter_fn(on_bf) is False
        assert spec.filter_fn(p1) is False
