"""Reference test for FDN 205 — Seismic Rupture.

Illustrative test covering **untargeted mass damage with a keyword filter**:
the spell hits every creature *without flying* on every battlefield, so it
takes no targets and does not care who controls the creature. Damage is dealt
through ``engine.game.deal_damage`` so lethal marks feed state-based actions.
"""

from __future__ import annotations

from cards.fdn.fdn_205.card_impl import SeismicRupture
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _ground(name: str, power: int = 3, toughness: int = 3) -> Creature:
    return Creature(name=name, subtypes={"Bear"}, base_power=power, base_toughness=toughness)


def _flyer(name: str, power: int = 1, toughness: int = 1) -> Creature:
    return Creature(
        name=name, subtypes={"Bird"}, keywords=Keyword.FLYING,
        base_power=power, base_toughness=toughness,
    )


class TestSeismicRuptureProperties:
    """Static card data should match the FDN 205 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(SeismicRupture(owner=None), Sorcery)

    def test_name(self) -> None:
        assert SeismicRupture(owner=None).name == "Seismic Rupture"

    def test_mana_cost(self) -> None:
        assert SeismicRupture(owner=None).mana_cost == ManaCost.parse("{2}{R}")

    def test_takes_no_targets(self) -> None:
        """Mass damage is untargeted — the card offers no target spec."""
        game = create_game()
        card = SeismicRupture(owner=game.players[0], controller=game.players[0])
        assert card.get_targets(game) == []


class TestSeismicRuptureDamage:
    """Deals 2 to each creature without flying, on every battlefield."""

    def test_ground_creature_takes_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = _ground("Grizzly Bears")
        set_board_state(game, 0, battlefield=[bear])
        rupture = SeismicRupture(owner=p1, controller=p1)

        rupture.on_resolve(game)

        assert bear.damage_marked == 2

    def test_flyer_is_untouched(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bird = _flyer("Storm Crow", power=1, toughness=2)
        set_board_state(game, 0, battlefield=[bird])
        rupture = SeismicRupture(owner=p1, controller=p1)

        rupture.on_resolve(game)

        assert bird.damage_marked == 0

    def test_hits_both_battlefields(self) -> None:
        """Untargeted: the caster's own ground creatures are hit too."""
        game = create_game()
        p1, p2 = game.players
        mine = _ground("My Bear")
        theirs = _ground("Their Bear")
        set_board_state(game, 0, battlefield=[mine])
        set_board_state(game, 1, battlefield=[theirs])
        rupture = SeismicRupture(owner=p1, controller=p1)

        rupture.on_resolve(game)

        assert mine.damage_marked == 2
        assert theirs.damage_marked == 2

    def test_lethal_ground_creature_dies_via_sba(self) -> None:
        """2 damage is lethal to a 2-toughness ground creature; a
        2-toughness flyer survives untouched."""
        from engine.state_based_actions import resolve_state_based_actions

        game = create_game()
        p1, p2 = game.players
        small = _ground("Goblin", power=2, toughness=2)
        bird = _flyer("Storm Crow", power=1, toughness=2)
        set_board_state(game, 1, battlefield=[small, bird])
        rupture = SeismicRupture(owner=p1, controller=p1)

        rupture.on_resolve(game)
        resolve_state_based_actions(game)

        bf = game.get_battlefield(p2).get_all()
        assert small not in bf
        assert game.players[1].zones[Zone.GRAVEYARD].contains(small)
        assert bird in bf  # flyer never took damage

    def test_deals_damage_through_the_cast_pipeline(self) -> None:
        """End-to-end: casting the spell resolves the sweep on the board."""
        game = create_game()
        p1, p2 = game.players
        victim = _ground("Their Bear")
        set_board_state(game, 1, battlefield=[victim])
        set_board_state(
            game, 0,
            hand=[SeismicRupture(owner=p1, controller=p1)],
            mana={ManaType.RED: 3},
        )

        cast_spell(game, 0, "Seismic Rupture")

        assert victim.damage_marked == 2
        assert game.players[0].zones[Zone.GRAVEYARD].get_all()  # spell to GY
