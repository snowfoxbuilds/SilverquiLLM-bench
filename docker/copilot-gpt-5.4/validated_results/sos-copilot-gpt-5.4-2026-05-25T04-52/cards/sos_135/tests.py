"""Tests for SOS 135 — Tome Blast."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_135.card_impl import TomeBlast
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestTomeBlastProperties:
    """Static card data should match the SOS 135 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(TomeBlast(owner=None), Sorcery)

    def test_name_cost_and_flashback_cost(self) -> None:
        card = TomeBlast(owner=None)

        assert card.name == "Tome Blast"
        assert card.mana_cost == ManaCost.parse("{1}{R}")
        assert card.flashback_cost == ManaCost.parse("{4}{R}")


class TestTomeBlastTargeting:
    """Tome Blast should target any creature, planeswalker, or player."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = TomeBlast(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_players_creatures_and_planeswalkers_only(self) -> None:
        game = create_game()
        req = TomeBlast(owner=None).get_targets(game)[0]

        creature = Creature(name="Target Bear", base_power=2, base_toughness=2)
        planeswalker = Planeswalker(name="Visitor", starting_loyalty=3)
        non_target = CardImpl(name="Lecture Notes")

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(creature) is True
        assert req.filter_fn(planeswalker) is True
        assert req.filter_fn(non_target) is False


class TestTomeBlastResolution:
    """Tome Blast should deal 2 damage to its target and support flashback."""

    def test_on_resolve_deals_two_damage_to_target_creature(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        game.get_battlefield(p2).add(target)

        spell = TomeBlast(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_marked == 2

    def test_on_resolve_deals_two_damage_to_target_player(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = TomeBlast(owner=p1, controller=p1)
        before_life = p2.life

        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert p2.life == before_life - 2

    def test_on_resolve_deals_two_damage_to_target_planeswalker(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Planeswalker(
            name="Target Walker",
            owner=p2,
            controller=p2,
            starting_loyalty=4,
        )
        game.get_battlefield(p2).add(target)

        spell = TomeBlast(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.loyalty == 2

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=3,
        )
        spell = TomeBlast(owner=p1, controller=p1)
        game.get_battlefield(p2).add(target)
        game.get_graveyard(p1).add(spell)
        p1.mana_pool.add(ManaType.RED, 5)
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert target.damage_marked == 2
