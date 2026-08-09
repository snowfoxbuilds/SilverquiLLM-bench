"""Reference test for FDN 104 — Elvish Regrower.

Exemplar for a **targeted ETB creature** (Phase D, Pattern 1) that returns a
*permanent* card (creature / artifact / enchantment / land / planeswalker) from
your graveyard to your hand. The target is chosen at cast (``get_targets``) and
the return applied in ``on_resolve``.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_104.card_impl import ElvishRegrower
from engine.card import Creature, Instant, Land
from engine.types import ManaCost, ManaType, Phase, Zone
from test_utils import (
    TestSetupError as _TestSetupError,
    cast_spell,
    create_game,
    set_board_state,
)


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _setup(dead=None):
    game = create_game()
    p1, p2 = game.players
    game.active_player_index = 0
    regrower = ElvishRegrower(owner=p1, controller=p1)
    dead = dead if dead is not None else Land(name="Fallen Forest")
    set_board_state(
        game, 0, hand=[regrower], graveyard=[dead],
        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2},
    )
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, regrower, dead


class TestElvishRegrowerProperties:
    def test_static_data(self):
        card = ElvishRegrower(owner=None)
        assert card.name == "Elvish Regrower"
        assert card.mana_cost == ManaCost.parse("{2}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 3)
        assert card.subtypes == {"Elf", "Druid"}


class TestElvishRegrowerETB:
    def test_returns_targeted_land_card_to_hand(self):
        game, p1, p2, regrower, dead = _setup(Land(name="Fallen Forest"))
        cast_spell(game, 0, "Elvish Regrower", targets=[dead])
        assert game.get_hand(p1).contains(dead)
        assert not game.get_graveyard(p1).contains(dead)
        assert game.get_battlefield(p1).contains(regrower)

    def test_option_set_any_permanent_card_but_not_instant(self):
        """Legality invariant: any permanent card in your graveyard is legal
        (creature, land, …) but an instant/sorcery card is not, and an
        opponent's graveyard is excluded."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        regrower = ElvishRegrower(owner=p1, controller=p1)
        my_creature = _bear("My Creature")
        my_land = Land(name="My Land")
        my_instant = Instant(name="My Instant")
        opp_land = Land(name="Their Land")
        set_board_state(game, 0, battlefield=[regrower],
                        graveyard=[my_creature, my_land, my_instant])
        set_board_state(game, 1, graveyard=[opp_land])

        spec = regrower.get_targets(game)[0]
        assert spec.filter_fn(my_creature) is True
        assert spec.filter_fn(my_land) is True
        assert spec.filter_fn(my_instant) is False
        assert spec.filter_fn(opp_land) is False

    def test_no_legal_target_makes_cast_illegal(self):
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        regrower = ElvishRegrower(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[regrower],
                        graveyard=[Instant(name="Only Instant")],
                        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2})
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(_TestSetupError):
            cast_spell(game, 0, "Elvish Regrower")
        # The cast was rejected — the Regrower never resolved onto the field.
        assert not game.get_battlefield(p1).contains(regrower)
