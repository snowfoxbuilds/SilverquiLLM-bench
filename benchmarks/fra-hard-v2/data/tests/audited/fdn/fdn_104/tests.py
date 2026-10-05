"""Reference test for FDN 104 — Elvish Regrower.

Exemplar for a **targeted ETB creature** (Phase D, Pattern 1) that returns a
*permanent* card (creature / artifact / enchantment / land / planeswalker) from
your graveyard to your hand. The target is chosen at cast (``get_targets``) and
the return applied in ``on_resolve``.
"""

from __future__ import annotations

from cards.fdn.fdn_104.card_impl import ElvishRegrower
from engine.card import Creature, Instant, Land, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.stack import resolve_top_of_stack
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import (
    cast_spell,
    set_board_state,
)
from test_utils import (
    scenario_game as create_game,
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
    prefs = tuple(Decision.obj(instance=game.refs.instance_id(t, zone.value)) for t in targets)
    player.start_intent(
        "cast",
        Intent(
            pattern=GameRef(card=frozenset({("printed", printed_class(card))})),
            preferences=prefs,
        ),
    )
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
        game,
        0,
        hand=[regrower],
        graveyard=[dead],
        mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2},
    )
    game.phase = Phase.PRECOMBAT_MAIN
    return game, p1, p2, regrower, dead


class TestElvishRegrowerProperties:
    def test_static_data(self):
        card = ElvishRegrower(owner=None)
        assert printed_class(card) is ElvishRegrower
        assert card.mana_cost == ManaCost.parse("{2}{G}{G}")
        assert (card.base_power, card.base_toughness) == (4, 3)
        assert card.subtypes == {"Elf", "Druid"}


class TestElvishRegrowerETB:
    def test_returns_targeted_land_card_to_hand(self):
        game, p1, _p2, regrower, dead = _setup(Land(name="Fallen Forest"))
        cast_spell(game, 0, ElvishRegrower, targets=[dead])
        assert game.get_hand(p1).contains(dead)
        assert not game.get_graveyard(p1).contains(dead)
        assert game.get_battlefield(p1).contains(regrower)

    def test_option_set_any_permanent_card_but_not_instant(self):
        from engine.card import Artifact, Enchantment, Planeswalker
        from test_utils import cast_card, object_preference, prefer

        for dead in [
            Creature(name="Creature", base_power=2, base_toughness=2),
            Land(name="Land"),
            Artifact(name="Artifact"),
            Enchantment(name="Enchantment"),
            Planeswalker(name="Walker"),
        ]:
            game, p1, _p2, regrower, dead = _setup(dead)
            prefer(p1, object_preference(game, dead))
            cast_card(game, p1, regrower)
            assert game.get_hand(p1).contains(dead)
        game, p1, _p2, regrower, dead = _setup(Instant(name="Not permanent"))
        cast_card(game, p1, regrower)
        assert not game.get_hand(p1).contains(dead)

    def test_target_no_longer_permanent_card_does_nothing(self):
        """Resolution-time revalidation (rule 608.2b): the ETB re-checks the
        FULL predicate, not merely graveyard membership. If the chosen card
        ceases to be a *permanent* card before resolution, it is not returned —
        the Regrower still enters, but the graveyard card stays put."""
        game, p1, _p2, regrower, dead = _setup(Land(name="Fallen Forest"))
        _cast_no_resolve(game, 0, regrower, [dead], zone=Zone.GRAVEYARD)
        # The chosen card stops being a permanent card while the spell resolves.
        dead.card_types = {CardType.INSTANT}
        resolve_top_of_stack(game)
        assert game.get_graveyard(p1).contains(dead)  # not returned
        assert not game.get_hand(p1).contains(dead)
        assert game.get_battlefield(p1).contains(regrower)  # creature entered

    def test_no_legal_target_removes_the_trigger(self):
        """With only an instant in the graveyard, the Regrower enters and its
        enters trigger is not put on the stack (rule 603.3c)."""
        game = create_game()
        p1, _p2 = game.players
        game.active_player_index = 0
        regrower = ElvishRegrower(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[regrower],
            graveyard=[Instant(name="Only Instant")],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 2},
        )
        game.phase = Phase.PRECOMBAT_MAIN
        cast_spell(game, 0, ElvishRegrower)
        assert game.get_battlefield(p1).contains(regrower)
        assert game.stack.is_empty()
