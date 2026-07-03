"""Tests for SOS 43 — Divergent Equation."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_43.card_impl import DivergentEquation
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestDivergentEquationProperties:
    """Static card data should match the SOS 43 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(DivergentEquation(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = DivergentEquation(owner=None)
        assert card.name == "Divergent Equation"
        assert card.mana_cost == ManaCost.parse("{X}{X}{U}")


class TestDivergentEquationTargeting:
    """Divergent Equation should target instant and sorcery cards in your graveyard."""

    def test_x_value_two_returns_two_graveyard_target_requirements(self) -> None:
        game = create_game()
        card = DivergentEquation(owner=game.players[0], controller=game.players[0])
        card.x_value = 2  # type: ignore[attr-defined]
        reqs = card.get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert all(isinstance(req, TargetRequirement) for req in reqs)
        assert all(req.zone == Zone.GRAVEYARD for req in reqs)

    def test_target_filter_accepts_only_your_instant_and_sorcery_cards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = DivergentEquation(owner=p1, controller=p1)
        card.x_value = 1  # type: ignore[attr-defined]
        req = card.get_targets(game)[0]

        friendly_instant = Instant(name="Friendly Instant", owner=p1, controller=p1)
        friendly_sorcery = Sorcery(name="Friendly Sorcery", owner=p1, controller=p1)
        friendly_creature = Creature(
            name="Friendly Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        opposing_instant = Instant(name="Opposing Instant", owner=p2, controller=p2)

        assert req.filter_fn(friendly_instant) is True
        assert req.filter_fn(friendly_sorcery) is True
        assert req.filter_fn(friendly_creature) is False
        assert req.filter_fn(opposing_instant) is False

    def test_x_value_zero_returns_no_target_requirements(self) -> None:
        game = create_game()
        card = DivergentEquation(owner=game.players[0], controller=game.players[0])
        card.x_value = 0  # type: ignore[attr-defined]

        assert card.get_targets(game) == []


class TestDivergentEquationResolution:
    """Divergent Equation should return graveyard spells to hand and exile itself."""

    def test_on_resolve_returns_the_chosen_targets_to_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant_card = Instant(name="Recovered Insight", owner=p1, controller=p1)
        sorcery_card = Sorcery(name="Recovered Thesis", owner=p1, controller=p1)
        other_card = Creature(
            name="Stays Buried",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[instant_card, sorcery_card, other_card])
        card = DivergentEquation(owner=p1, controller=p1)
        card.x_value = 2  # type: ignore[attr-defined]
        card.chosen_targets = [instant_card, sorcery_card]

        card.on_resolve(game)

        assert game.get_hand(p1).contains(instant_card)
        assert game.get_hand(p1).contains(sorcery_card)
        assert not game.get_graveyard(p1).contains(instant_card)
        assert not game.get_graveyard(p1).contains(sorcery_card)
        assert game.get_graveyard(p1).contains(other_card)

    def test_paid_cast_exiles_itself_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Instant(name="Recovered Insight", owner=p1, controller=p1)
        spell = DivergentEquation(owner=p1, controller=p1)
        spell.x_value = 1  # type: ignore[attr-defined]

        set_board_state(
            game,
            0,
            hand=[spell],
            graveyard=[target],
            mana={ManaType.BLUE: 3},
        )
        p1._script.append(target)

        cast_spell_paid(game, p1, spell, alternative_cost=ManaCost.parse("{2}{U}"))
        resolve_top(game)

        assert game.get_hand(p1).contains(target)
        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)
