"""Reference test for FDN 75 — Vampire Soulcaller.

Exemplar for a **targeted ETB creature** (Phase D, Pattern 1): the enters
ability targets a creature card in your graveyard. The target is chosen at cast
via ``get_targets`` (answered by an Intent through ``cast_spell(targets=...)``),
stored on the stack object, and applied in ``on_resolve`` before the creature
arrives. The graveyard card returns to hand.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_75.card_impl import VampireSoulcaller
from engine.card import Creature, Instant
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import (
    TestSetupError as _TestSetupError,
    cast_spell,
    create_game,
    set_board_state,
)


def _bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


def _cast_no_resolve(game, player_index, card, targets, zone=Zone.BATTLEFIELD):
    """Cast *card* but leave it on the stack (targets chosen, not resolved)."""
    player = game.players[player_index]
    game.active_player_index = player_index
    game.priority_player_index = player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    prefs = tuple(
        Decision.obj(instance=game.refs.instance_id(t, zone.value)) for t in targets
    )
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("name", card.name)})),
            preferences=prefs,
        ),
    )
    try:
        engine_cast_spell(game, player, card)
    finally:
        player.end_intent("cast")


def _setup():
    """Soulcaller in hand with mana; a creature card waiting in your graveyard."""
    game = create_game()
    p1, p2 = game.players
    game.active_player_index = 0
    soulcaller = VampireSoulcaller(owner=p1, controller=p1)
    dead = _bear("Fallen Vampire")
    set_board_state(
        game, 0, hand=[soulcaller], graveyard=[dead],
        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 4},
    )
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, soulcaller, dead


class TestVampireSoulcallerProperties:
    def test_static_data(self):
        card = VampireSoulcaller(owner=None)
        assert card.name == "Vampire Soulcaller"
        assert card.mana_cost == ManaCost.parse("{4}{B}")
        assert (card.base_power, card.base_toughness) == (3, 2)
        assert card.subtypes == {"Vampire", "Warlock"}
        assert Keyword.FLYING & card.keywords

    def test_declares_a_single_required_target(self):
        game, p1, p2, soulcaller, dead = _setup()
        specs = soulcaller.get_targets(game)
        assert len(specs) == 1
        assert specs[0].optional is False


class TestVampireSoulcallerETB:
    def test_returns_targeted_creature_card_to_hand(self):
        game, p1, p2, soulcaller, dead = _setup()
        assert game.get_graveyard(p1).contains(dead)
        cast_spell(game, 0, "Vampire Soulcaller", targets=[dead])
        # Effect landed: the creature card is back in hand, out of the graveyard.
        assert game.get_hand(p1).contains(dead)
        assert not game.get_graveyard(p1).contains(dead)
        # The Soulcaller itself resolved onto the battlefield.
        assert game.get_battlefield(p1).contains(soulcaller)

    def test_option_set_only_your_creature_cards(self):
        """Legality invariant: only creature cards in *your* graveyard are legal
        targets — not non-creature cards, and not an opponent's graveyard."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        soulcaller = VampireSoulcaller(owner=p1, controller=p1)
        my_creature = _bear("My Creature")
        my_instant = Instant(name="My Instant")
        opp_creature = _bear("Their Creature")
        set_board_state(game, 0, battlefield=[soulcaller],
                        graveyard=[my_creature, my_instant])
        set_board_state(game, 1, graveyard=[opp_creature])

        spec = soulcaller.get_targets(game)[0]
        assert spec.filter_fn(my_creature) is True
        assert spec.filter_fn(my_instant) is False
        assert spec.filter_fn(opp_creature) is False

    def test_no_legal_target_makes_cast_illegal(self):
        """A required target with no legal candidate rejects the cast."""
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        soulcaller = VampireSoulcaller(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[soulcaller],
                        mana={ManaType.BLACK: 1, ManaType.COLORLESS: 4})
        game.phase = Phase.PRECOMBAT_MAIN
        with pytest.raises(_TestSetupError):
            cast_spell(game, 0, "Vampire Soulcaller")
        # The cast was rejected — the Soulcaller never resolved onto the field.
        assert not game.get_battlefield(p1).contains(soulcaller)


class TestVampireSoulcallerRevalidation:
    """Rule 608.2b: the reanimation revalidates the FULL predicate ("a creature
    card in your graveyard") at resolution, not merely graveyard presence."""

    def test_no_return_when_target_ceases_to_be_creature_card(self):
        game, p1, p2, soulcaller, dead = _setup()
        _cast_no_resolve(game, 0, soulcaller, [dead], zone=Zone.GRAVEYARD)
        # Before resolution the target stops being a creature card.
        dead.card_types = set(dead.card_types) - {CardType.CREATURE}
        while not game.stack.is_empty():
            resolve_top_of_stack(game)

        # Effect did nothing: the card stays in the graveyard, not the hand.
        assert game.get_graveyard(p1).contains(dead)
        assert not game.get_hand(p1).contains(dead)
        # The Soulcaller itself still resolved onto the battlefield.
        assert game.get_battlefield(p1).contains(soulcaller)
