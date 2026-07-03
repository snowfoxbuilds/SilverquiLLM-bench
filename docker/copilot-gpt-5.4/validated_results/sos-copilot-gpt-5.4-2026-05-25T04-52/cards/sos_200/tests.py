"""Tests for SOS 200 — Lorehold Charm."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_200.card_impl import LoreholdCharm
from benchmarks.sos.workspace.engine.card import Artifact, CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestLoreholdCharmProperties:
    """Static card data should match the SOS 200 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(LoreholdCharm(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = LoreholdCharm(owner=None)

        assert card.name == "Lorehold Charm"
        assert card.mana_cost == ManaCost.parse("{R}{W}")


class TestLoreholdCharmModes:
    """Lorehold Charm should expose its three printed modes."""

    def test_exposes_the_three_printed_modes(self) -> None:
        modes = LoreholdCharm(owner=None).get_modes()

        assert len(modes) == 3
        assert "sacrifices a nontoken artifact" in modes[0].description
        assert "mana value 2 or less" in modes[1].description
        assert "gain trample until end of turn" in modes[2].description


class TestLoreholdCharmTargeting:
    """Target requirements should follow the selected mode."""

    def test_first_and_third_modes_have_no_targets(self) -> None:
        game = create_game()
        first_mode_spell = LoreholdCharm(owner=game.players[0], controller=game.players[0])
        first_mode_spell.selected_mode = 0
        third_mode_spell = LoreholdCharm(owner=game.players[0], controller=game.players[0])
        third_mode_spell.selected_mode = 2

        assert first_mode_spell.get_targets(game) == []
        assert third_mode_spell.get_targets(game) == []

    def test_second_mode_targets_a_single_artifact_or_creature_card_with_mana_value_two_or_less_in_your_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = LoreholdCharm(owner=p1, controller=p1)
        spell.selected_mode = 1
        cheap_artifact = Artifact(owner=p1, controller=p1, name="Small Relic", mana_cost=ManaCost.parse("{1}"))
        cheap_creature = Creature(
            owner=p1,
            controller=p1,
            name="Small Bear",
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
        )
        expensive_creature = Creature(
            owner=p1,
            controller=p1,
            name="Big Bear",
            mana_cost=ManaCost.parse("{3}{W}"),
            base_power=4,
            base_toughness=4,
        )
        your_sorcery = CardImpl(name="Notes", owner=p1, controller=p1, mana_cost=ManaCost.parse("{1}"))
        opponent_artifact = Artifact(owner=p2, controller=p2, name="Opponent Relic", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, graveyard=[cheap_artifact, cheap_creature, expensive_creature, your_sorcery])
        set_board_state(game, 1, graveyard=[opponent_artifact])
        reqs = spell.get_targets(game)

        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.GRAVEYARD
        assert reqs[0].filter_fn(cheap_artifact) is True
        assert reqs[0].filter_fn(cheap_creature) is True
        assert reqs[0].filter_fn(expensive_creature) is False
        assert reqs[0].filter_fn(your_sorcery) is False
        assert reqs[0].filter_fn(opponent_artifact) is False


class TestLoreholdCharmResolution:
    """Each Lorehold Charm mode should resolve as printed."""

    def test_first_mode_makes_each_opponent_sacrifice_a_nontoken_artifact_of_their_choice(self) -> None:
        game = create_game()
        p1, p2 = game.players
        relic = Artifact(name="Ancient Relic", owner=p2, controller=p2, mana_cost=ManaCost.parse("{1}"))
        token = Artifact(name="Treasure", owner=p2, controller=p2)
        token.is_token = True  # type: ignore[attr-defined]
        set_board_state(game, 1, battlefield=[relic, token])
        p2._script.append(relic)

        spell = LoreholdCharm(owner=p1, controller=p1)
        spell.selected_mode = 0
        spell.on_resolve(game)

        assert game.get_graveyard(p2).contains(relic)
        assert not game.get_battlefield(p2).contains(relic)
        assert game.get_battlefield(p2).contains(token)

    def test_second_mode_returns_a_targeted_small_artifact_or_creature_card_from_your_graveyard_to_the_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Creature(
            name="Recovered Assistant",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{W}"),
            base_power=2,
            base_toughness=2,
        )
        filler = CardImpl(name="Unreturned Notes", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[target, filler])

        spell = LoreholdCharm(owner=p1, controller=p1)
        spell.selected_mode = 1
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert game.get_battlefield(p1).contains(target)
        assert not game.get_graveyard(p1).contains(target)
        assert game.get_graveyard(p1).contains(filler)

    def test_third_mode_gives_your_creatures_plus_one_plus_one_and_trample_until_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ally_a = Creature(
            name="Ally A",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        ally_b = Creature(
            name="Ally B",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
        )
        enemy = Creature(
            name="Enemy",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[ally_a, ally_b])
        set_board_state(game, 1, battlefield=[enemy])

        spell = LoreholdCharm(owner=p1, controller=p1)
        spell.selected_mode = 2
        spell.on_resolve(game)

        assert ally_a.power == 3
        assert ally_a.toughness == 3
        assert ally_b.power == 2
        assert ally_b.toughness == 4
        assert Keyword.TRAMPLE in ally_a.keywords
        assert Keyword.TRAMPLE in ally_b.keywords
        assert enemy.power == 2
        assert enemy.toughness == 2
        assert Keyword.TRAMPLE not in enemy.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert ally_a.power == 2
        assert ally_a.toughness == 2
        assert ally_b.power == 1
        assert ally_b.toughness == 3
        assert Keyword.TRAMPLE not in ally_a.keywords
        assert Keyword.TRAMPLE not in ally_b.keywords

