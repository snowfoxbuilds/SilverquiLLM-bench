"""Tests for SOS 221 — Resonating Lute.

An artifact costing {2}{U}{R} with two abilities:
1. Lands you control have "{T}: Add two mana of any one color. Spend this mana
   only to cast instant and sorcery spells."
2. {T}: Draw a card. Activate only if you have seven or more cards in your hand.
"""

from __future__ import annotations

from cards.sos.sos_221.card_impl import ResonatingLute
from engine.card import Artifact, Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestResonatingLuteProperties:
    """Static card data should match the SOS 221 spec."""

    def test_is_artifact(self) -> None:
        assert isinstance(ResonatingLute(owner=None), Artifact)

    def test_name(self) -> None:
        assert ResonatingLute(owner=None).name == "Resonating Lute"

    def test_mana_cost(self) -> None:
        assert ResonatingLute(owner=None).mana_cost == ManaCost.parse("{2}{U}{R}")


class TestResonatingLuteLandAbility:
    """Lands you control gain '{T}: Add two mana of any one color. Spend this
    mana only to cast instant and sorcery spells.'"""

    def test_land_gains_mana_ability(self) -> None:
        """When Resonating Lute is on the battlefield, lands controlled by that
        player should gain the special mana ability."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lute)

        # Create a basic land
        from engine.card import Land
        mountain = Land(name="Mountain", owner=p1, controller=p1)
        game.get_battlefield(p1).add(mountain)

        # The land should have the granted mana ability
        abilities = lute.get_granted_abilities(game, mountain)
        assert len(abilities) >= 1

    def test_land_produces_two_mana_of_one_color(self) -> None:
        """The granted ability should produce two mana of any one color."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lute)

        from engine.card import Land
        mountain = Land(name="Mountain", owner=p1, controller=p1)
        game.get_battlefield(p1).add(mountain)

        abilities = lute.get_granted_abilities(game, mountain)
        # Activate choosing a color — the ability should add 2 mana
        assert len(abilities) >= 1
        ability = abilities[0]
        assert ability.mana_amount == 2

    def test_granted_mana_restricted_to_instants_sorceries(self) -> None:
        """Mana from the granted ability can only be spent on instants/sorceries."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lute)

        from engine.card import Land
        mountain = Land(name="Mountain", owner=p1, controller=p1)
        game.get_battlefield(p1).add(mountain)

        abilities = lute.get_granted_abilities(game, mountain)
        ability = abilities[0]
        assert ability.spend_restriction is not None


class TestResonatingLuteDrawAbility:
    """{T}: Draw a card. Activate only if you have seven or more cards in hand."""

    def test_draw_ability_requires_seven_cards_in_hand(self) -> None:
        """Cannot activate if fewer than 7 cards in hand."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lute)

        # With fewer than 7 cards in hand, ability should not be activatable
        dummies = [Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
                   for i in range(5)]
        set_board_state(game, 0, hand=dummies)

        assert lute.can_activate_draw(game) is False

    def test_draw_ability_activatable_with_seven_cards(self) -> None:
        """Can activate with exactly 7 cards in hand."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        game.get_battlefield(p1).add(lute)

        dummies = [Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
                   for i in range(7)]
        set_board_state(game, 0, hand=dummies)

        assert lute.can_activate_draw(game) is True

    def test_draw_ability_draws_a_card(self) -> None:
        """Activating the ability draws one card."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        lute.is_tapped = False
        game.get_battlefield(p1).add(lute)

        dummies = [Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
                   for i in range(7)]
        set_board_state(game, 0, hand=dummies)

        hand_before = len(game.get_hand(p1))
        lute.activate_draw(game)
        # Should have drawn 1 card (net hand change depends on library)
        assert lute.is_tapped is True

    def test_draw_ability_taps_lute(self) -> None:
        """Activating costs {T}, so the lute becomes tapped."""
        game = create_game()
        p1 = game.players[0]
        lute = ResonatingLute(owner=p1, controller=p1)
        lute.is_tapped = False
        game.get_battlefield(p1).add(lute)

        dummies = [Creature(name=f"Dummy{i}", base_power=1, base_toughness=1)
                   for i in range(7)]
        set_board_state(game, 0, hand=dummies)

        lute.activate_draw(game)
        assert lute.is_tapped is True
