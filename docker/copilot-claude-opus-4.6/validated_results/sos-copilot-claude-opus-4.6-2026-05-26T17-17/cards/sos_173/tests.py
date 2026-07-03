"""Tests for SOS 173 — Ark of Hunger.

A {2}{R}{W} Artifact with:
  "Whenever one or more cards leave your graveyard, this artifact deals 1 damage
   to each opponent and you gain 1 life.
   {T}: Mill a card. You may play that card this turn."
"""

from __future__ import annotations

from cards.sos.sos_173.card_impl import ArkOfHunger
from engine.card import Artifact, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestArkOfHungerProperties:
    """Static card data should match the SOS 173 spec."""

    def test_is_artifact(self) -> None:
        card = ArkOfHunger(owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        assert ArkOfHunger(owner=None).name == "Ark of Hunger"

    def test_mana_cost(self) -> None:
        card = ArkOfHunger(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{R}{W}")

    def test_card_types(self) -> None:
        card = ArkOfHunger(owner=None)
        assert CardType.ARTIFACT in card.card_types


class TestArkOfHungerGraveyardTrigger:
    """Whenever cards leave graveyard: deal 1 to each opponent, gain 1 life."""

    def test_register_triggers_exists(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ArkOfHunger(owner=p1, controller=p1)
        card.register_triggers(game)

    def test_damage_to_opponent_on_graveyard_leave(self) -> None:
        """When cards leave your graveyard, deal 1 damage to each opponent."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArkOfHunger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        # Put a card in the graveyard
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(bear)

        initial_life = p2.life
        # Simulate the card leaving the graveyard (e.g., exile it)
        game.get_graveyard(p1).remove(bear)
        # Process triggers
        if hasattr(game, 'process_triggers'):
            game.process_triggers()

        # Opponent should take 1 damage
        assert p2.life == initial_life - 1

    def test_controller_gains_life_on_graveyard_leave(self) -> None:
        """When cards leave your graveyard, you gain 1 life."""
        game = create_game()
        p1 = game.players[0]
        card = ArkOfHunger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(bear)

        initial_life = p1.life
        game.get_graveyard(p1).remove(bear)
        if hasattr(game, 'process_triggers'):
            game.process_triggers()

        assert p1.life == initial_life + 1

    def test_multiple_cards_leaving_triggers_once(self) -> None:
        """'One or more' — multiple cards leaving at once triggers only once."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = ArkOfHunger(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        card.register_triggers(game)

        bear1 = Creature(name="Bear1", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear2", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        game.get_graveyard(p1).add(bear1)
        game.get_graveyard(p1).add(bear2)

        initial_life = p2.life
        # Both leave simultaneously
        game.get_graveyard(p1).remove(bear1)
        game.get_graveyard(p1).remove(bear2)
        if hasattr(game, 'process_triggers'):
            game.process_triggers()

        # Should be only 1 damage total (triggers once per batch)
        assert p2.life == initial_life - 1


class TestArkOfHungerActivatedAbility:
    """'{T}: Mill a card. You may play that card this turn.'"""

    def test_has_activated_ability(self) -> None:
        card = ArkOfHunger(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activated_ability_requires_tap(self) -> None:
        """The ability costs {T}."""
        card = ArkOfHunger(owner=None)
        abilities = card.get_activated_abilities()
        ability = abilities[0]
        assert getattr(ability, 'tap_cost', None) is True or 'tap' in str(ability.cost).lower()

    def test_mill_moves_top_card_to_graveyard(self) -> None:
        """Activating mills the top card of library to graveyard."""
        game = create_game()
        p1 = game.players[0]
        card = ArkOfHunger(owner=p1, controller=p1)
        card.is_tapped = False
        game.get_battlefield(p1).add(card)

        # Put a known card on top of library
        top_card = Creature(name="Top Card", owner=p1, controller=p1,
                            base_power=1, base_toughness=1)
        set_board_state(game, 0, library=[top_card])

        abilities = card.get_activated_abilities()
        ability = abilities[0]
        ability.effect(game, card)

        # The card should now be in the graveyard
        gy = game.get_graveyard(p1).get_all()
        assert any(getattr(c, 'name', '') == "Top Card" for c in gy)
