"""Tests for SOS 226 — Silverquill, the Disputant (casualty granting)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class _Bolt(Sorcery):
    """Test sorcery: deal 2 damage to target player."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Test Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        from engine.types import TargetRequirement
        return [TargetRequirement(filter_fn=lambda o: hasattr(o, "life"),
                                  description="target player", zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage
        chosen = getattr(self, "chosen_targets", None) or []
        if chosen:
            deal_damage(game, self, chosen[0], 2)


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant(owner=None).name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert SilverquillTheDisputant(owner=None).mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.base_power == 4 and card.base_toughness == 4

    def test_keywords(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in SilverquillTheDisputant(owner=None).supertypes


def _enter(game, player_index, card):
    from engine.zones import move_to_zone
    move_to_zone(game, card, Zone.HAND, Zone.BATTLEFIELD)


class TestSilverquillCasualty:
    """Each I/S spell you cast gains casualty 1 (copy on sacrifice)."""

    def test_casualty_copies_spell(self) -> None:
        sq = SilverquillTheDisputant(owner=None)
        bolt = _Bolt(owner=None)
        sac = Creature(name="Goat", base_power=2, base_toughness=2)
        game = create_game(scripts=([True, sac], []))
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[sac], hand=[sq, bolt])
        _enter(game, 0, sq)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        set_board_state(game, 1, life=20)
        cast_spell(game, 0, "Test Bolt", targets=[p2])
        # Copy + original each deal 2 -> 4 total.
        assert p2.life == 16
        # The sacrificed creature is gone from the battlefield.
        assert sac not in game.get_battlefield(p1).get_all()
        assert sac in game.get_graveyard(p1).get_all()

    def test_decline_casualty(self) -> None:
        sq = SilverquillTheDisputant(owner=None)
        bolt = _Bolt(owner=None)
        sac = Creature(name="Goat", base_power=2, base_toughness=2)
        game = create_game(scripts=([False], []))
        p1, p2 = game.players
        set_board_state(game, 0, battlefield=[sac], hand=[sq, bolt])
        _enter(game, 0, sq)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        set_board_state(game, 1, life=20)
        cast_spell(game, 0, "Test Bolt", targets=[p2])
        # No copy -> only 2 damage; creature survives.
        assert p2.life == 18
        assert sac in game.get_battlefield(p1).get_all()

    def test_creature_spell_does_not_offer_casualty(self) -> None:
        # Casting a creature spell must not trigger casualty (no sacrifice).
        sq = SilverquillTheDisputant(owner=None)
        sac = Creature(name="Goat", base_power=2, base_toughness=2)
        big = Creature(name="Ogre", base_power=3, base_toughness=3,
                       mana_cost=ManaCost.parse("{1}"))
        game = create_game(scripts=([], []))
        p1, _ = game.players
        set_board_state(game, 0, battlefield=[sac], hand=[sq, big])
        _enter(game, 0, sq)
        set_board_state(game, 0, mana={ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Ogre")
        # Creature spell is not I/S; the sacrificial creature is untouched.
        assert sac in game.get_battlefield(p1).get_all()

