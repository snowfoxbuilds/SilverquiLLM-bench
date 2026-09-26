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
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    TestSetupError as _TestSetupError,
    cast_spell,
    create_game,
    set_board_state,
)


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_no_resolve(game, player_index, card, targets, zone=Zone.BATTLEFIELD):
    """Cast *card* choosing *targets* (in *zone*) but leave it on the stack.

    Mirrors ``test_utils.cast_spell`` but stops before resolution so a test can
    mutate the chosen target and then resolve manually to exercise
    resolution-time target revalidation.
    """
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, zone.value))
        for t in targets
    )
    player.start_intent("cast", Intent(
        pattern=GameRef(card=frozenset({("name", card.name)})),
        preferences=prefs,
    ))
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


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

    def test_target_no_longer_permanent_card_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): the ETB re-checks the
        FULL predicate, not merely graveyard membership. If the chosen card
        ceases to be a *permanent* card before resolution, it is not returned —
        the Regrower still enters, but the graveyard card stays put."""
        game, p1, p2, regrower, dead = _setup(Land(name="Fallen Forest"))
        _cast_no_resolve(game, 0, regrower, [dead], zone=Zone.GRAVEYARD)
        # The chosen card stops being a permanent card while the spell resolves.
        dead.card_types = {CardType.INSTANT}
        resolve_top_of_stack(game)
        assert game.get_graveyard(p1).contains(dead)          # not returned
        assert not game.get_hand(p1).contains(dead)
        assert game.get_battlefield(p1).contains(regrower)    # creature entered

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
