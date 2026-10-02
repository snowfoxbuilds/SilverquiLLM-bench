"""Public casting, targeting and temporary flying coverage for Fleeting Flight.

Combat damage prevention is excluded with an unscored baseline diagnostic."""

from __future__ import annotations

from cards.fdn.fdn_13.card_impl import FleetingFlight
from engine.card import Creature, Instant
from engine.types import (
    Keyword,
    ManaCost,
)
from test_utils import scenario_game as create_game


class TestFleetingFlightProperties:
    """Static card data should match the FDN 13 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(FleetingFlight(owner=None), Instant)

    def test_name(self) -> None:
        assert FleetingFlight(owner=None).name == "Fleeting Flight"

    def test_mana_cost(self) -> None:
        assert FleetingFlight(owner=None).mana_cost == ManaCost.parse("{W}")


class TestFleetingFlightTargeting:
    """Only creatures are legal cast targets."""

    def test_artifact_is_not_a_legal_creature_target(self) -> None:
        import pytest
        from engine.card import Artifact
        from engine.casting import CastingError
        from test_utils import cast_card, fund_mana_cost, set_board_state

        game = create_game()
        p1 = game.players[0]
        set_board_state(game, 0, battlefield=[Artifact(name="Not a creature")])
        spell = FleetingFlight(owner=p1)
        fund_mana_cost(p1, spell.mana_cost)
        with pytest.raises(CastingError):
            cast_card(game, p1, spell)


class TestFleetingFlightResolution:
    """Targeting and resolution run through normal casting."""

    def test_missing_required_target_rejects_before_payment(self) -> None:
        import pytest
        from engine.casting import CastingError
        from test_utils import cast_card, fund_mana_cost

        game = create_game()
        p1 = game.players[0]
        spell = FleetingFlight(owner=p1)
        fund_mana_cost(p1, spell.mana_cost)
        with pytest.raises(CastingError):
            cast_card(game, p1, spell)
        assert p1.mana_pool.total() == 1

    def test_chosen_target_receives_counter_and_flying(self) -> None:
        from test_utils import (
            cast_card,
            fund_mana_cost,
            object_preference,
            prefer,
            put_on_battlefield,
        )

        game = create_game()
        p1, _p2 = game.players
        bear = put_on_battlefield(game, p1, Creature(name="Bear", base_power=2, base_toughness=2))
        spell = FleetingFlight(owner=p1)
        fund_mana_cost(p1, spell.mana_cost)
        prefer(p1, object_preference(game, bear))
        cast_card(game, p1, spell)
        assert (bear.power, bear.toughness) == (3, 3) and bear.keywords & Keyword.FLYING
        from engine.types import Phase, Step
        from test_utils import advance_game_to_phase

        advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
        assert not bear.keywords & Keyword.FLYING
        assert (bear.power, bear.toughness) == (3, 3)

    def test_targeted_creature_survives_combat_with_a_four_power_flyer(self) -> None:
        """It gets a +1/+1 counter and "prevent all combat damage that would be
        dealt to it this turn" (rule 615.1): the 2/2 target becomes a flying
        3/3 and survives a block by a 4/4 flyer."""
        from engine.combat import combat_damage_step
        from engine.turn import untap_step
        from engine.types import Keyword
        from test_utils import (
            cast_card,
            declare_attackers,
            declare_blockers,
            fund_mana_cost,
            object_preference,
            prefer,
            put_on_battlefield,
            resolve_stack,
        )

        game = create_game()
        player, opponent = game.players
        target = put_on_battlefield(
            game, player, Creature(name="Protected attacker", base_power=2, base_toughness=2)
        )
        blocker = put_on_battlefield(
            game, opponent,
            Creature(name="Flying blocker", base_power=4, base_toughness=4, keywords=Keyword.FLYING),
        )
        spell = FleetingFlight(owner=player)
        fund_mana_cost(player, spell.mana_cost)
        prefer(player, object_preference(game, target))
        cast_card(game, player, spell)
        assert (target.power, target.toughness) == (3, 3)

        untap_step(game)
        declare_attackers(game, [target.name])
        declare_blockers(game, {target.name: [blocker.name]})
        combat_damage_step(game)
        resolve_stack(game)
        assert game.get_battlefield(player).contains(target)
        assert (target.power, target.toughness) == (3, 3)
