"""Tests for SOS 25 — Practiced Offense."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_25.card_impl import PracticedOffense
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPracticedOffenseProperties:
    """Static card data should match the SOS 25 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(PracticedOffense(owner=None), Sorcery)

    def test_name_cost_and_flashback_cost(self) -> None:
        card = PracticedOffense(owner=None)
        assert card.name == "Practiced Offense"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.flashback_cost == ManaCost.parse("{1}{W}")


class TestPracticedOffenseTargeting:
    """Practiced Offense should target a player and a creature."""

    def test_returns_player_then_creature_target_requirements(self) -> None:
        game = create_game()
        reqs = PracticedOffense(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD
        assert reqs[1].zone == Zone.BATTLEFIELD

    def test_target_filters_accept_players_for_the_first_target_and_creatures_for_the_second(self) -> None:
        game = create_game()
        p1 = game.players[0]
        reqs = PracticedOffense(owner=p1, controller=p1).get_targets(game)
        creature = Creature(name="Helpful Bear", base_power=2, base_toughness=2)

        assert reqs[0].filter_fn(p1) is True
        assert reqs[0].filter_fn(creature) is False
        assert reqs[1].filter_fn(creature) is True
        assert reqs[1].filter_fn(p1) is False


class TestPracticedOffenseResolution:
    """Practiced Offense should distribute counters and grant one temporary keyword."""

    def test_puts_counters_on_each_creature_target_player_controls_and_grants_exactly_one_keyword(self) -> None:
        game = create_game()
        p1, p2 = game.players
        veteran = Creature(name="Veteran", owner=p1, controller=p1, base_power=2, base_toughness=2)
        trainee = Creature(name="Trainee", owner=p1, controller=p1, base_power=1, base_toughness=1)
        opponent = Creature(name="Opponent", owner=p2, controller=p2, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[veteran, trainee])
        set_board_state(game, 1, battlefield=[opponent])
        p1._script.append(Keyword.DOUBLE_STRIKE)
        card = PracticedOffense(owner=p1, controller=p1)
        card.chosen_targets = [p1, veteran]

        card.on_resolve(game)

        assert veteran.plus_one_counters == 1
        assert trainee.plus_one_counters == 1
        assert opponent.plus_one_counters == 0
        assert (Keyword.DOUBLE_STRIKE in veteran.keywords) ^ (Keyword.LIFELINK in veteran.keywords)

    def test_granted_keyword_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        veteran = Creature(name="Veteran", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(veteran)
        p1._script.append(Keyword.DOUBLE_STRIKE)
        card = PracticedOffense(owner=p1, controller=p1)
        card.chosen_targets = [p1, veteran]

        card.on_resolve(game)
        assert (Keyword.DOUBLE_STRIKE in veteran.keywords) ^ (Keyword.LIFELINK in veteran.keywords)

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert Keyword.DOUBLE_STRIKE not in veteran.keywords
        assert Keyword.LIFELINK not in veteran.keywords

    def test_paid_flashback_cast_from_graveyard_exiles_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        veteran = Creature(name="Veteran", owner=p1, controller=p1, base_power=2, base_toughness=2)
        trainee = Creature(name="Trainee", owner=p1, controller=p1, base_power=1, base_toughness=1)
        spell = PracticedOffense(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[veteran, trainee], graveyard=[spell], mana={ManaType.WHITE: 2})
        p1._script.extend([p1, veteran, Keyword.DOUBLE_STRIKE])

        cast_spell_paid(game, p1, spell, from_zone=Zone.GRAVEYARD)

        assert game.stack.peek().source is spell
        assert not game.get_graveyard(p1).contains(spell)

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert veteran.plus_one_counters == 1
        assert trainee.plus_one_counters == 1
        assert (Keyword.DOUBLE_STRIKE in veteran.keywords) ^ (Keyword.LIFELINK in veteran.keywords)
